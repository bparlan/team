#!/usr/bin/env python3
"""
Regression tests for the stashed behavioral island.

These cover analysis/project_scanner.py, which was removed from the
production skill on 2026-09-29 (see README.md in this directory).

Guards the defects found 2026-09-29:

  1. _is_test_file used `in` against glob patterns ("test_*"), so no file
     ever matched and test_files stayed 0 for every project.
  2. The complexity classifier tested _is_code_file first; a .py test also
     matches "code", so the test_files branch was unreachable even after (1).
  3. src_structure took src_dirs[0] from unordered iterdir(), so a project
     with src/ and tests/ reported "tests".
  4. Reclassifying tests changed which files fed the structural_complexity
     mean, silently crossing the 0.3/0.5/0.7 thresholds that gate 14 role
     and risk decisions across team_generator, team_manager and
     behavioral_integration.

Run: cd _island && python3 test_island.py
"""

import sys
import tempfile
import shutil
import unittest
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from analysis.project_scanner import ProjectAnalyzer  # noqa: E402


def make_project(tmp: Path) -> Path:
    """A small project with both src/ and tests/, so (3) is observable."""
    (tmp / "src").mkdir(parents=True)
    (tmp / "tests").mkdir()
    (tmp / "src" / "__init__.py").write_text("")
    (tmp / "src" / "mod.py").write_text("def h():\n    return 1\n")
    (tmp / "src" / "latest.py").write_text("def x():\n    return 2\n")
    (tmp / "src" / "mod_test.py").write_text("h = 1\n")
    (tmp / "src" / "mod.spec.ts").write_text("export const y = 1;\n")
    (tmp / "tests" / "test_mod.py").write_text("def test_h():\n    assert True\n")
    (tmp / "tests" / "conftest.py").write_text("# fixtures\n")
    (tmp / "README.md").write_text("# demo\n")
    (tmp / "pyproject.toml").write_text('[project]\nname = "demo"\n')
    return tmp


class TestFileClassification(unittest.TestCase):
    """Guards 1 and 2 — test detection."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        make_project(self.tmp)
        self.analyzer = ProjectAnalyzer(str(self.tmp))

    def test_is_test_file_matches_real_conventions(self):
        cases = {
            "test_mod.py": True,
            "mod_test.py": True,
            "mod.spec.ts": True,
            "mod.test.js": True,
            "tests/conftest.py": True,   # unremarkable name, but in tests/
            "src/latest.py": False,      # contains "test" as a substring only
            "src/mod.py": False,
        }
        for name, expected in cases.items():
            with self.subTest(name=name):
                self.assertEqual(self.analyzer._is_test_file(Path(name)), expected)

    def test_test_files_counter_is_non_zero(self):
        self.assertGreater(self.analyzer._analyze_code_complexity()["test_files"], 0)

    def test_classification_partitions_all_files(self):
        """A file must be counted in exactly one bucket."""
        c = self.analyzer._analyze_code_complexity()
        buckets = ["code_files", "test_files", "documentation_files", "config_files"]
        self.assertEqual(
            sum(c[b] for b in buckets), c["total_files"],
            "file classification buckets must sum to total_files",
        )

    def test_test_coverage_ratio_reflects_tests(self):
        ratio = self.analyzer.analyze_project()["project_metrics"]["test_coverage_ratio"]
        self.assertGreater(ratio, 0.0)

    def test_source_dir_preferred_over_tests(self):
        self.assertEqual(
            self.analyzer._analyze_file_organization()["src_structure"], "src"
        )


    def test_complexity_metrics_unchanged_by_reclassification(self):
        """structural_complexity gates 14 role/risk decisions across 4 modules.

        Fixing the test_files count must not shift it: the fix changed which
        files feed the mean, which silently crossed the 0.3/0.5/0.7 thresholds
        and flipped recommended roles. Test files stay in the complexity
        population; only the bucket labels change.
        """
        import fnmatch
        c = self.analyzer.analyze_project()["code_complexity"]

        # Recompute the pre-fix semantics: every file with is_code True.
        scores, imports = [], 0
        for f in self.tmp.rglob("*"):
            if not f.is_file() or self.analyzer._should_ignore_file(f):
                continue
            n = f.name.lower()
            is_test = (
                any(fnmatch.fnmatch(n, p) for p in ("test_*", "*_test", "*_spec"))
                or f.parent.name.lower() in ("tests", "test", "__tests__")
            )
            if self.analyzer._is_code_file(f) or is_test:
                _, i, s = self.analyzer._calculate_file_complexity(f)
                scores.append(s)
                imports += i

        self.assertAlmostEqual(
            c["structural_complexity"], sum(scores) / len(scores), places=9,
            msg="structural_complexity drifted — a role/risk decision may flip",
        )
        self.assertAlmostEqual(
            c["import_complexity"], imports / len(scores), places=9,
            msg="import_complexity denominator must match the population that "
                "contributed imports, including test files",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
