#!/usr/bin/env python3
"""
Regression tests for the 5 stability/consistency fixes.

Each test defends one specific gap identified in the project-wide analysis:
  1. Duplicate/corrupted sa_runner variants (scripts/ canonical uniqueness)
  2. Stale daemon state (PID validation in task_stack_adapter)
  3. Ledger bloat (size-based rotation in optimized runner)
  4. Test isolation leaks (no module-level sys.path mutation)
  5. Deterministic report writing (generic_writer contract)

Run: python3 -m pytest theteam/tests/test_stability_fixes.py -q
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCanonicalScriptsUniqueness(unittest.TestCase):
    """Fix 1: Only one canonical sa_runner.py must exist."""

    def test_only_canonical_runner_remains(self):
        scripts_dir = PROJECT_ROOT / "scripts"
        runners = sorted(p.name for p in scripts_dir.glob("sa_runner*.py"))
        # Only the canonical runner should exist; all variant names must be gone
        self.assertEqual(runners, ["sa_runner.py"], f"Unexpected runner variants: {runners}")

    def test_canonical_runner_is_valid_python(self):
        import py_compile
        runner = PROJECT_ROOT / "scripts" / "sa_runner.py"
        py_compile.compile(str(runner), doraise=True)

    def test_canonical_runner_exports_required_api(self):
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        import sa_runner
        for name in ("get_loop_state", "get_last_health_score", "run_analysis",
                     "generic_writer", "write_report"):
            self.assertTrue(hasattr(sa_runner, name), f"sa_runner missing: {name}")


class TestDaemonPidValidation(unittest.TestCase):
    """Fix 2: task_stack_adapter must validate daemon PID against a live process."""

    def setUp(self):
        from theteam.ui.task_stack_adapter import TaskStackAdapter
        self.tmp = Path(tempfile.mkdtemp())
        self.adapter = TaskStackAdapter(str(self.tmp))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write_daemon_state(self, pid, running=True):
        state_dir = self.tmp / ".omp" / "theteam"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "task-stack-daemon.json").write_text(json.dumps({"running": running}))
        (state_dir / "task-stack.pid").write_text(str(pid))

    def test_stale_pid_reports_not_running(self):
        # PID 999999 is extremely unlikely to be a real process
        self._write_daemon_state(999999, running=True)
        status = self.adapter._get_daemon_status()
        self.assertFalse(status.get("pid_valid", True),
                         "Stale PID must be reported as invalid")

    def test_missing_pid_file_reports_not_running(self):
        state_dir = self.tmp / ".omp" / "theteam"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "task-stack-daemon.json").write_text(json.dumps({"running": True}))
        status = self.adapter._get_daemon_status()
        self.assertFalse(status.get("daemon_running", True),
                         "Missing PID file must mean daemon not running")
class TestTestIsolation(unittest.TestCase):
    """Fix 4: No module-level sys.path mutation in test files."""

    def test_no_module_level_sys_path_insert(self):
        test_file = PROJECT_ROOT / "theteam" / "tests" / "test_discussion_manager_refactored.py"
        source = test_file.read_text()
        # The guard comment is allowed; the actual insert call is not
        self.assertNotIn("sys.path.insert", source,
                         "Module-level sys.path.insert leaks across test sessions")

    def test_no_tempfile_leak_in_setUp(self):
        test_file = PROJECT_ROOT / "theteam" / "tests" / "test_discussion_manager_refactored.py"
        source = test_file.read_text()
        # Verify setUp has been refactored to use standard test isolation helpers if applicable,
        # or that no unmanaged global tempdirs are created without tearDown cleanup.
        # This test ensures standard cleanup flows are implemented.
        self.assertIn("shutil.rmtree(self.temp_dir, ignore_errors=True)", source)
class TestLedgerRotation(unittest.TestCase):
    """Fix 3: Ledger writes must rotate when exceeding a deterministic size cap."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _load_runner(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "optimized_runner",
            str(PROJECT_ROOT / "tasks" / "system-awareness" / "optimized_system_awareness_runner.py"),
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.OptimizedSystemAwarenessRunner(str(PROJECT_ROOT))

    def test_runner_has_rotation_threshold(self):
        runner = self._load_runner()
        self.assertGreater(runner._ledger_max_bytes, 0)
        self.assertTrue(callable(runner._rotate_ledger))

    def test_rotation_archives_oversized_ledger(self):
        runner = self._load_runner()
        runner._ledger_max_bytes = 100  # tiny cap to force rotation
        runner.ledger_file = self.tmp / "ledger.json"
        runner.ledger_file.write_text(json.dumps({"big": "x" * 200}))
        # Point archive dir under temp dir to avoid writing to scripts/
        with patch.object(runner, "ledger_file", self.tmp / "ledger.json"):
            runner._rotate_ledger()
        archives = list(self.tmp.glob("archives/ledger_*.json"))
        self.assertEqual(len(archives), 1, "Rotation must archive the old ledger")




class TestReportWriterContract(unittest.TestCase):
    """Fix 5: generic_writer must exist and produce valid JSON."""

    def test_generic_writer_writes_valid_json(self):
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        from sa_runner import generic_writer, OUTPUT_PATHS
        tmp = Path(tempfile.mkdtemp())
        try:
            target = tmp / "report.json"
            # Point OUTPUT_PATHS at temp dir for this test only
            with patch.dict(OUTPUT_PATHS, {"test_report": target}):
                result = generic_writer("test_report", {"score": 0.9}, "test report")
            self.assertEqual(result, target)
            self.assertTrue(target.exists())
            data = json.loads(target.read_text())
            self.assertEqual(data["score"], 0.9)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()