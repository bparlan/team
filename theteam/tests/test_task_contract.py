"""Tests for `scripts/check_task_contract.py` and the `task-contract` task.

The script duplicates `AGENT_TYPES` from `theteam.tasks.runners.llm` so it can
run as a bare file with no PYTHONPATH. A duplication with no test is a
divergence waiting to happen, and a *wrong* spawnable list produces findings
that are all false -- worse than no findings, because they teach a reader to
ignore the page.
"""
import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = PROJECT_ROOT / "scripts/check_task_contract.py"


def _load_script_module():
    """Import the checker as a module, without putting it on sys.path."""
    spec = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    module = ast.Module(body=[n for n in spec.body
                              if not isinstance(n, ast.Expr)
                              or not isinstance(n.value, ast.Constant)],
                        type_ignores=[])
    namespace = {"__name__": "check_task_contract_under_test", "__file__": str(SCRIPT)}
    exec(compile(module, str(SCRIPT), "exec"), namespace)
    return namespace


class TestAgentTypesStayInSync(unittest.TestCase):
    """The duplicated tuple is the one thing that can make this script lie."""

    def test_agent_types_match_the_runner(self):
        from theteam.tasks.runners.llm import AGENT_TYPES

        namespace = _load_script_module()
        self.assertEqual(
            sorted(namespace["AGENT_TYPES"]), sorted(AGENT_TYPES),
            "scripts/check_task_contract.py AGENT_TYPES has drifted from "
            "theteam.tasks.runners.llm.AGENT_TYPES; the script would flag valid "
            "agent types or miss invalid ones",
        )

    def test_no_spawnable_type_is_rejected(self):
        """Every real agent type must pass the script's own membership test."""
        from theteam.tasks.runners.llm import AGENT_TYPES

        namespace = _load_script_module()
        for agent in AGENT_TYPES:
            self.assertIn(agent, namespace["AGENT_TYPES"], agent)


class TestDeclaredOutputDetection(unittest.TestCase):
    """Check 4 is the check with teeth; it needs to not be vacuous."""

    def test_finds_a_declared_output_nothing_writes(self):
        src = '''
OUTPUT_PATHS = {
    "written": ROOT / "written.json",
    "orphan_a": ROOT / "orphan_a.json",
    "orphan_b": ROOT / "orphan_b.json",
}

def main():
    generic_writer(OUTPUT_PATHS["written"], {"ok": True})
'''
        namespace = _load_script_module()
        tree = ast.parse(src)
        declared, names = namespace["_declared_output_keys"](tree)
        used = namespace["_keys_used_as_write_targets"](tree, names)

        self.assertEqual(set(declared), {"written", "orphan_a", "orphan_b"})
        self.assertEqual(used, {"written"})

    def test_quoting_style_does_not_matter(self):
        src = """
OUTPUT_PATHS = {'written': ROOT / "w.json", 'orphan': ROOT / "o.json"}
generic_writer(OUTPUT_PATHS['written'], {})
"""
        namespace = _load_script_module()
        tree = ast.parse(src)
        declared, names = namespace["_declared_output_keys"](tree)
        used = namespace["_keys_used_as_write_targets"](tree, names)
        self.assertEqual(used, {"written"})
        self.assertIn("orphan", declared)

    def test_real_sa_runner_has_no_unwritten_outputs(self):
        """`sa_runner.py` writes all six of its declared outputs. Pin it.

        A discussion note claimed this file "ships a declared output it never
        writes", and the claim looked plausible: the file declares six outputs
        and only one of them is passed as `OUTPUT_PATHS["key"]`. The other five
        go through `generic_writer("key", ...)`, which resolves the path from
        the key itself. An AST check that credited only subscripts reported
        five never-written outputs -- all five false.

        So the real content of this test is the negative: the check must not
        cry wolf here. A check that reports working code as broken gets tuned
        out, and then it catches nothing at all.
        """
        sa = PROJECT_ROOT / "scripts/sa_runner.py"
        if not sa.exists():
            self.skipTest("scripts/sa_runner.py not present")
        namespace = _load_script_module()
        tree = ast.parse(sa.read_text(encoding="utf-8"))
        declared, names = namespace["_declared_output_keys"](tree)
        if not declared:
            self.skipTest("sa_runner.py no longer declares an OUTPUT_PATHS mapping")
        used = namespace["_keys_used_as_write_targets"](tree, names)
        self.assertEqual(
            set(declared) - used, set(),
            "sa_runner.py now leaves an output unwritten. If that is a real "
            "regression, this test should assert the specific key instead of "
            "clearing; if the file was refactored, update it.",
        )

    def test_a_genuinely_unwritten_key_is_still_caught_in_that_shape(self):
        """The sa_runner shape -- `generic_writer("key", ...)` -- must still
        be credited, or a real orphan here would go unreported."""
        src = '''
OUTPUT_PATHS = {"written": ROOT / "w.json", "orphan": ROOT / "o.json"}
def write_written():
    generic_writer("written", {})
'''
        namespace = _load_script_module()
        tree = ast.parse(src)
        declared, names = namespace["_declared_output_keys"](tree)
        used = namespace["_keys_used_as_write_targets"](tree, names)
        self.assertEqual(set(declared) - used, {"orphan"})


class TestScriptRunsAndReports(unittest.TestCase):
    """End to end: the real invocation, on the real registry."""

    def _run(self, root):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(root)],
            capture_output=True, text=True,
        )

    def test_real_registry_is_clean(self):
        result = self._run(PROJECT_ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(
            (PROJECT_ROOT / ".omp/theteam/reports/task-contract.json").read_text())
        self.assertEqual(report["findings"], 0,
                         f"registry has findings: {json.dumps(report['details'], indent=2)}")
        self.assertGreaterEqual(report["tasks_checked"], 7)

    def test_exits_zero_even_with_findings(self):
        """A reporting task, not a gate. Refusing to run is how a stale
        registry stays stale."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tasks").mkdir()
            (root / "tasks/task-bad.yaml").write_text(yaml.safe_dump({
                "id": "bad",
                "phases": [{"name": "p", "runner": "llm", "member": "x",
                            "agent_type": "wizard",
                            "prompt_file": "prompts/nope.md",
                            "output": "reports/x.md"}],
            }))
            result = self._run(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(
                (root / ".omp/theteam/reports/task-contract.json").read_text())
            checks = {f["check"] for f in report["details"]}
            self.assertEqual(checks, {"prompt_exists", "agent_type", "human_surface"})


class TestTaskIsRegistered(unittest.TestCase):
    """The task file obeys the rules the script enforces, plus the two-consumer
    split: `reports/` holds only the final HTML page."""

    def test_task_contract_task_exists_and_is_wellformed(self):
        path = PROJECT_ROOT / "tasks/task-task-contract.yaml"
        self.assertTrue(path.exists(), "task-task-contract.yaml is not registered")
        task = yaml.safe_load(path.read_text())
        self.assertEqual(task["id"], "task-contract")
        names = [p["name"] for p in task["phases"]]
        self.assertEqual(names, ["check", "publish"])
        self.assertEqual(task["phases"][0]["script"], "scripts/check_task_contract.py")
        self.assertEqual(task["phases"][0].get("runner"), None,
                         "a script phase needs no runner: key")
        self.assertEqual(task["phases"][-1]["output"], "reports/task-contract.html")

    def test_publish_prompt_exists(self):
        self.assertTrue(
            (PROJECT_ROOT / "prompts/task-contract-publish.md").exists())


if __name__ == "__main__":
    unittest.main()