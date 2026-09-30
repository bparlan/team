#!/usr/bin/env python3
"""
Regression tests for the 5 stability/consistency fixes.

Each test defends one specific gap identified in the project-wide analysis:
  1. Duplicate/corrupted sa_runner variants (scripts/ canonical uniqueness)
  2. (removed in M4: task_stack_adapter PID validation, along with the adapter)
  3. Ledger bloat (size-based rotation in optimized runner)
  4. Test isolation leaks (no module-level sys.path mutation)
  5. Deterministic report writing (generic_writer contract)

Run: python3 -m pytest theteam/tests/test_stability_fixes.py -q
"""

import ast
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


def _module_level_path_inserts(tree):
    """Every `sys.path.insert` that runs at import time, and nothing else.

    Module level means: not inside a function or class body. An insert inside a
    `with` block that is itself at module level is still module level, and so is
    one under `if __name__ == "__main__"`. Recursing into `FunctionDef` and
    `ClassDef` is therefore the whole rule — and it is the rule a substring
    search cannot express, which is why this is written as an AST walk.
    """
    def visit(node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef, ast.Lambda)):
                continue
            if (isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Attribute)
                    and child.func.attr == "insert"
                    and isinstance(child.func.value, ast.Attribute)
                    and child.func.value.attr == "path"):
                yield child
            yield from visit(child)

    return list(visit(tree))


class TestTestIsolation(unittest.TestCase):
    """Fix 4: No module-level sys.path mutation in test files."""

    def test_no_module_level_sys_path_insert(self):
        # Swept across the suite, and checked with `ast` rather than a substring
        # search. Both changes matter:
        #
        #   * the original pointed at one named file, so it guarded that file and
        #     silently stopped guarding anything once M10 deleted it;
        #   * the original matched the *text*, so it could not tell a
        #     module-level insert (which leaks into every later session) from an
        #     insert inside a function that adds and removes its own entry.
        #     `test_utils.py` does the latter, correctly, and a text search would
        #     have reported it as a violation.
        #
        # Two files are exempt by name, each for a stated reason below.
        exempt = {
            # This file imports the project root so it can load `scripts/`
            # helpers directly. Documented bootstrap, not a leak.
            Path(__file__).name,
            # pytest imports test modules as `theteam.tests.<name>` (the
            # package has an `__init__.py`), so a sibling in the same
            # directory is NOT importable by bare name. This one insert is the
            # standard way to reach it, and the insert is idempotent.
            "test_theteam.py",
        }
        offenders = []
        for test_file in sorted((PROJECT_ROOT / "theteam" / "tests").glob("test_*.py")):
            if test_file.name in exempt:
                continue
            tree = ast.parse(test_file.read_text())
            offenders.extend(
                f"{test_file.name}:{call.lineno}"
                for call in _module_level_path_inserts(tree))
        self.assertEqual(offenders, [],
                         "Module-level sys.path.insert leaks across test sessions: "
                         + ", ".join(offenders))

    def test_tempdirs_are_cleaned_up(self):
        # Any test that creates `self.temp_dir` must also tear it down, or the
        # directory outlives the test that made it. Swept across the suite for
        # the same reason as the sys.path guard above.
        offenders = []
        for test_file in sorted((PROJECT_ROOT / "theteam" / "tests").glob("test_*.py")):
            source = test_file.read_text()
            if "self.temp_dir" in source and \
                    "shutil.rmtree(self.temp_dir, ignore_errors=True)" not in source:
                offenders.append(test_file.name)
        self.assertEqual(offenders, [],
                         "self.temp_dir created without teardown: " + ", ".join(offenders))
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