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



class TestHumanBoundary(unittest.TestCase):
    """reports/ holds only html. Proven both ways: a checker only ever seen
    firing is not known to detect the compliant shape.

    Scope, stated so no reader over-reads it: this asserts the SHAPE of the
    directory. It cannot tell a human's drop-in from a task's output, so it
    makes no claim about which .html is legitimate -- only that reports/
    contains no markdown and nothing that is neither html nor markdown.
    """

    def _findings(self, reports_files):
        namespace = _load_script_module()
        findings = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            reports.mkdir()
            for name in reports_files:
                (reports / name).write_text("x", encoding="utf-8")
            namespace["_check_human_boundary"](root, findings)
        return findings

    def test_markdown_in_reports_is_a_finding(self):
        findings = self._findings(["a.html", "orphan.md"])
        self.assertEqual(len(findings), 1, findings)
        self.assertEqual(findings[0]["check"], "human_surface")
        self.assertIn("orphan.md", findings[0]["detail"])
        self.assertIn(".handoff", findings[0]["fix"])

    def test_non_html_non_md_is_a_finding(self):
        findings = self._findings(["a.html", "notes.txt"])
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("notes.txt", findings[0]["detail"])

    def test_compliant_directory_is_silent(self):
        self.assertEqual(self._findings(["a.html", "b.html"]), [])

    def test_handoff_subdirectory_is_not_scanned(self):
        """reports/.handoff/ is the machine side of the split; markdown
        living there is correct, and the check must stay silent on it."""
        namespace = _load_script_module()
        findings = []
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "reports/.handoff").mkdir(parents=True)
            (root / "reports/a.html").write_text("x", encoding="utf-8")
            (root / "reports/.handoff/machine.md").write_text("x", encoding="utf-8")
            namespace["_check_human_boundary"](root, findings)
        self.assertEqual(findings, [])

    def test_real_reports_directory_is_clean(self):
        reports = PROJECT_ROOT / "reports"
        self.assertTrue(reports.is_dir())
        strays = [p.name for p in reports.iterdir()
                  if p.is_file() and p.suffix != ".html"]
        self.assertEqual(strays, [], f"reports/ must hold only .html, found {strays}")


if __name__ == "__main__":
    unittest.main()