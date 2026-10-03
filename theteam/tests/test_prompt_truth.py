"""Tests for `scripts/check_prompt_truth.py` and the `prompt-truth` task.

The checker shipped reporting zero findings on its own prompts, which is the
outcome that proves nothing on its own: a check that inspects no claims and a
check that finds no drift produce the same number. These tests inject known
bad citations into a real prompt and require them to be caught, so the zero is
a measurement rather than a default.
"""
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = PROJECT_ROOT / "scripts/check_prompt_truth.py"
PROMPT_DIR = PROJECT_ROOT / "prompts"


def _load():
    """Import the checker by path -- it is a bare script, not a package module."""
    spec = importlib.util.spec_from_file_location("check_prompt_truth", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _InjectedClaim:
    """Append a line to a real prompt, then restore it exactly."""

    def __init__(self, filename: str, line: str):
        self.path = PROMPT_DIR / filename
        self.line = line
        self._original: str = ""

    def __enter__(self):
        self._original = self.path.read_text(encoding="utf-8")
        self.path.write_text(self._original + "\n" + self.line + "\n",
                             encoding="utf-8")
        return self

    def __exit__(self, *exc):
        self.path.write_text(self._original, encoding="utf-8")
        return False


class TestDriftIsCaught(unittest.TestCase):
    """A citation pointing at nothing, or past the end of a file."""

    def setUp(self):
        self.checker = _load()

    def _checks_for(self, line):
        with _InjectedClaim("root-organization-scan.md", line):
            report = self.checker.check_project(PROJECT_ROOT)
        return {f["check"] for f in report["details"]}

    def test_line_beyond_end_of_file(self):
        self.assertIn("line_out_of_range", self._checks_for(
            "The default lives at `theteam/cli.py:99999`."))

    def test_range_running_past_the_end(self):
        self.assertIn("line_out_of_range", self._checks_for(
            "See `theteam/cli.py:100-99999` for the resolver."))

    def test_missing_file_with_a_line_number(self):
        self.assertIn("missing_file", self._checks_for(
            "Per `no/such/module.py:12` this cannot work."))

    def test_zero_line_number(self):
        self.assertIn("line_out_of_range", self._checks_for(
            "See `theteam/cli.py:0`."))


class TestRealClaimsAreNotFlagged(unittest.TestCase):
    """The other half. A checker that cries wolf gets disabled."""

    def setUp(self):
        self.checker = _load()

    def _checks_for(self, line):
        with _InjectedClaim("root-organization-scan.md", line):
            report = self.checker.check_project(PROJECT_ROOT)
        return {f["check"] for f in report["details"]}

    def test_a_line_that_exists_is_clean(self):
        self.assertEqual(self._checks_for(
            "The config path is built at `theteam/cli.py:100`."), set())

    def test_a_valid_range_is_clean(self):
        self.assertEqual(self._checks_for(
            "See `scripts/loop_health_check.py:25-33` for why it stays."), set())

    def test_a_glob_pattern_is_not_a_missing_file(self):
        """`*_report.json` names a shape, not a file. Reporting it as a broken
        citation turns a true sentence into a false finding."""
        self.assertEqual(self._checks_for(
            "Runtime state at root includes `*_report.json`, `*_score.json`."), set())

    def test_a_placeholder_in_an_example_is_not_a_missing_file(self):
        self.assertEqual(self._checks_for(
            "touch <same-named-dir-elsewhere>/__probe.py"), set())

    def test_a_phase_output_path_is_not_a_missing_file(self):
        """`.omp/theteam/reports/*.md` names what a phase writes, which does
        not exist until something writes it."""
        self.assertEqual(self._checks_for(
            "Read `.omp/theteam/reports/doc-truth-audit.md` first."), set())


class TestRealPromptsAreClean(unittest.TestCase):
    def test_the_shipped_prompts_have_no_drifted_citations(self):
        report = _load().check_project(PROJECT_ROOT)
        self.assertGreater(
            report["claims_checked"], 10,
            "the checker stopped finding claims at all; a zero here would be "
            "a vacuous pass, not a clean one")
        self.assertEqual(
            report["findings"], 0,
            f"drifted citations: {report['details']}")


class TestScriptRunsAndReports(unittest.TestCase):
    def test_exits_zero_and_writes_a_handoff(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), str(PROJECT_ROOT)],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        handoff = PROJECT_ROOT / ".omp/theteam/reports/prompt-truth.json"
        self.assertTrue(handoff.exists())
        self.assertIn("claims_checked", handoff.read_text())

    def test_missing_prompts_dir_is_a_usage_error(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), tmp],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertIn("no prompts/", result.stderr)


class TestTaskIsRegistered(unittest.TestCase):
    def test_task_file_is_wellformed(self):
        path = PROJECT_ROOT / "tasks/task-prompt-truth.yaml"
        self.assertTrue(path.exists(), "task-prompt-truth.yaml is not registered")
        task = yaml.safe_load(path.read_text())
        self.assertEqual(task["id"], "prompt-truth")
        self.assertEqual([p["name"] for p in task["phases"]], ["check", "publish"])
        self.assertEqual(task["phases"][0]["script"], "scripts/check_prompt_truth.py")
        self.assertEqual(task["phases"][-1]["output"], "reports/prompt-truth.html")

    def test_publish_prompt_exists(self):
        self.assertTrue((PROMPT_DIR / "prompt-truth-publish.md").exists())

    def test_publish_prompt_states_the_limit(self):
        """The check cannot verify meaning. A publish page that implies it did
        would be worse than no page."""
        text = (PROMPT_DIR / "prompt-truth-publish.md").read_text()
        self.assertIn("does **not**\nverify", text.replace("\r", ""))


if __name__ == "__main__":
    unittest.main()