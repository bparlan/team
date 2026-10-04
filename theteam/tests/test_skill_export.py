"""The repo copy and the installed skill copy must not drift silently.

`export_skill.py` exists because "manual copying is how that drift
accumulates". It is the only writer of ~/.omp/agent/skills/theteam/, and
until now nothing checked that what it last wrote still matches the repo.
That is the same shape as the defect class this milestone removes: true
today, unchecked, diverging later -- and a divergence here means OMP
executes a different theteam_report.py than the one the suite tests.

Read-only by contract. This test never writes to the home directory;
`export_skill.py` stays the only writer.
"""
import ast
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = PROJECT_ROOT / "scripts/export_skill.py"

#: SKILL.md is rewritten on export -- export_skill.py replaces repo-relative
#: paths with absolute ones -- so it can never be byte-identical. Comparing it
#: raw would fail on a correct export, and a check that always fails is a
#: check nobody runs. It is compared after applying the same rewrite.
REWRITTEN_ON_EXPORT = frozenset({"SKILL.md"})


def _load_export_module():
    spec = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    namespace = {"__name__": "export_skill_under_test", "__file__": str(SCRIPT)}
    exec(compile(spec, str(SCRIPT), "exec"), namespace)
    return namespace


class TestSkillCopiesDoNotDrift(unittest.TestCase):
    def setUp(self):
        self.ns = _load_export_module()
        self.production = self.ns["PRODUCTION"]
        self.sources = self.ns["SOURCES"]
        if not self.production.is_dir():
            self.skipTest(
                f"installed skill dir absent at {self.production}; nothing to "
                "compare against. Run scripts/export_skill.py on the host.")

    def test_every_manifest_entry_is_byte_identical(self):
        drifted = []
        for target_rel, source_rel in sorted(self.sources.items()):
            source = PROJECT_ROOT / source_rel
            target = self.production / target_rel
            if not source.exists():
                drifted.append(f"{source_rel}: repo copy missing")
                continue
            if not target.exists():
                drifted.append(f"{target_rel}: installed copy missing")
                continue
            if target_rel in REWRITTEN_ON_EXPORT:
                expected = self.ns["rewrite_paths"](source.read_text(encoding="utf-8"))
                if target.read_text(encoding="utf-8") != expected:
                    drifted.append(f"{target_rel}: installed copy is stale")
                continue
            if source.read_bytes() != target.read_bytes():
                drifted.append(f"{target_rel}: installed copy is stale")
        self.assertEqual(drifted, [], (
            "repo and installed skill copies have drifted; run "
            f"`python3 {SCRIPT.relative_to(PROJECT_ROOT)}` to resync:\n  "
            + "\n  ".join(drifted)))

    def test_manifest_sources_all_exist(self):
        missing = [rel for rel in self.sources.values()
                   if not (PROJECT_ROOT / rel).exists()]
        self.assertEqual(missing, [], f"manifest names missing sources: {missing}")

    def test_manifest_entries_are_all_declared(self):
        """MANIFEST and SOURCES must cover the same files, or export copies
        something it never lists -- and the drift test above would not see it."""
        self.assertEqual(
            sorted(self.ns["MANIFEST"]), sorted(self.sources),
            "MANIFEST and SOURCES have drifted apart; a file copied but not "
            "listed is invisible to the drift check")


if __name__ == "__main__":
    unittest.main()