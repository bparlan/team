#!/usr/bin/env python3
"""
test_skill_export.py — Byte-identity guard for the installed skill copy.

Verifies every path in export_skill.py SOURCES is byte-identical between the
repo source and the installed skill dir (~/.omp/agent/skills/theteam/).
SKILL.md is compared after applying the same path-rewrite the export does,
since the installed copy intentionally uses absolute paths rather than
repo-relative PYTHONPATH=theteam references.

The test SKIPS with a clear reason when the skill dir is absent, so CI without
an installed skill is not a false failure.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PRODUCTION = Path.home() / ".omp" / "agent" / "skills" / "theteam"

# Must match export_skill.py SOURCES exactly.
SOURCES = {
    "SKILL.md": "theteam/SKILL.md",
    "theteam-template.config": "theteam/theteam-template.config",
    "bin/theteam_config.py": "theteam/bin/theteam_config.py",
    "bin/theteam_report.py": "bin/theteam_report.py",
    "bin/utilities.py": "theteam/bin/utilities.py",
    "bin/__init__.py": "theteam/bin/__init__.py",
}


def _skip_if_no_production():
    if not PRODUCTION.exists():
        pytest.skip(f"installed skill not found at {PRODUCTION}; export_skill.py is the only writer")


def _rewrite_skillmd(text: str) -> str:
    """Apply the same path rewrite export_skill.py uses for SKILL.md."""
    text = text.replace(
        "PYTHONPATH=theteam python3 theteam/bin/",
        f"python3 {PRODUCTION}/bin/",
    )
    text = re.sub(
        r"(?<![\w/~.])theteam/bin/(theteam_config\.py|theteam_report\.py|utilities\.py)",
        rf"{PRODUCTION}/bin/\1",
        text,
    )
    return text


def test_skill_export_sources_byte_identical():
    """Every source file must be byte-identical to its installed counterpart."""
    _skip_if_no_production()

    mismatches = []
    for dest_rel, src_rel in SOURCES.items():
        src = REPO_ROOT / src_rel
        dest = PRODUCTION / dest_rel

        if not src.exists():
            mismatches.append(f"source missing: {src_rel}")
            continue
        if not dest.exists():
            mismatches.append(f"installed missing: {dest_rel}")
            continue

        if dest_rel == "SKILL.md":
            src_bytes = _rewrite_skillmd(src.read_text(encoding="utf-8")).encode("utf-8")
        else:
            src_bytes = src.read_bytes()
        dest_bytes = dest.read_bytes()

        if src_bytes != dest_bytes:
            mismatches.append(
                f"mismatch: {src_rel} -> {dest_rel} "
                f"(source {len(src_bytes)} bytes, installed {len(dest_bytes)} bytes)"
            )

    assert not mismatches, "Skill export drift detected:\n  " + "\n  ".join(mismatches)


def test_skill_export_sources_exist():
    """Sanity: all SOURCES keys exist in the repo (fires even without installed skill)."""
    missing = [src for src in SOURCES.values() if not (REPO_ROOT / src).exists()]
    assert not missing, f"SOURCES references missing files: {missing}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))