#!/usr/bin/env python3
"""
seed_project.py — One-time seed for project convention infrastructure.

Usage:
    python scripts/seed_project.py --project-root <path> [--dry-run]

Derives the rule shape from the three construction projects (evidence only),
writes a seed.yaml into the target project, and verifies it.

The three projects are recorded as evidence_sources — metadata, never read
at run time.  The shape is portable; it ships no project content.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Evidence sources — the three construction projects used to derive the shape.
# They are recorded here for provenance only; nothing reads them at runtime.
# ---------------------------------------------------------------------------
EVIDENCE_SOURCES = {
    "system_awareness": str(Path.home() / "devcode" / "ledraslament"),
    "documentation_structure": [
        str(Path.home() / "devcode" / "autonomedia-snapshot"),
        str(Path.home() / "devcode" / "BariaDAO"),
    ],
}


SEED_CONTENT: dict = {
    "schema_version": "1.0",
    "evidence_sources": EVIDENCE_SOURCES,
    "rule_template": {
        "name": "Core convention requirement",
        "contract": [
            "Every project must have AGENTS.md defining conventions.",
            "Every project must have README.md for documentation.",
        ],
        "evidence": "verified",
        "rule_correct": "kept",
        "falsification_test": {
            "command": "test -f AGENTS.md && test -f README.md",
            "expected": "Both required files exist",
        },
    },
    "evolution_floor": {
        "can_add_rules": True,
        "can_modify": True,
        "can_delete": False,
        "requires_human_approval": True,
    },
}


def derive_seed(project_root: Path) -> dict:
    """Return the seed dict, optionally enriched by evidence-source inspection."""
    seed = json.loads(json.dumps(SEED_CONTENT))  # deep copy

    # --- inspect evidence sources to confirm the shape generalises ---
    findings: list[dict] = []
    for label, paths in EVIDENCE_SOURCES.items():
        for p in (paths if isinstance(paths, list) else [paths]):
            pp = Path(p)
            has_agents = (pp / "AGENTS.md").exists()
            has_readme = (pp / "README.md").exists()
            findings.append({
                "source": str(pp),
                "label": label,
                "AGENTS.md": has_agents,
                "README.md": has_readme,
            })

    seed["evidence_audit"] = findings
    seed["shape_generalises"] = all(
        f["AGENTS.md"] and f["README.md"] for f in findings
    )
    return seed


def write_seed(project_root: Path, seed: dict, dry_run: bool = False) -> Path:
    """Write seed.yaml into the project root.  Returns the file path."""
    import yaml  # safe_load/safe_dump used elsewhere in theteam

    target = project_root / "seed.yaml"
    if dry_run:
        print(f"[dry-run] would write {target}")
        return target

    target.write_text(yaml.safe_dump(seed, sort_keys=False, allow_unicode=True, width=80))
    return target


def verify_seed(project_root: Path) -> bool:
    """Verify the seed is in place and the project has the required files."""
    seed_path = project_root / "seed.yaml"
    if not seed_path.exists():
        print("✗ seed.yaml missing")
        return False

    required = ["AGENTS.md", "README.md"]
    missing = [f for f in required if not (project_root / f).exists()]
    if missing:
        print(f"✗ Project missing required files: {', '.join(missing)}")
        return False
    print("✓ Project is compliant with core conventions")
    return True
def scaffold_project(project_root: Path, dry_run: bool = False) -> None:
    """Create the minimal AGENTS.md and README.md if missing."""
    agents = project_root / "AGENTS.md"
    readme = project_root / "README.md"

    if not agents.exists():
        content = (
            "# Project Conventions\n\n"
            "This file defines the conventions for this project. "
            "Derived from the team construction projects as evidence — "
            "the shape is portable; no project content is shipped.\n"
        )
        if dry_run:
            print(f"[dry-run] would create {agents}")
        else:
            agents.write_text(content)
            print(f"✓ Created {agents}")

    if not readme.exists():
        content = (
            "# Project Overview\n\n"
            "Essential documentation for this project.\n"
        )
        if dry_run:
            print(f"[dry-run] would create {readme}")
        else:
            readme.write_text(content)
            print(f"✓ Created {readme}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seed a new project with the team convention infrastructure."
    )
    parser.add_argument(
        "--project-root", required=True, help="Absolute path to the project root."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be written without writing."
    )
    parser.add_argument(
        "--verify-only", action="store_true", help="Only verify, do not write."
    )
    args = parser.parse_args(argv)

    project_root = Path(args.project_root).resolve()
    if not project_root.is_dir():
        print(f"✗ Project root does not exist: {project_root}", file=sys.stderr)
        return 2

    seed = derive_seed(project_root)

    if args.verify_only:
        return 0 if verify_seed(project_root) else 1

    target = write_seed(project_root, seed, dry_run=args.dry_run)
    print(f"{'[dry-run] ' if args.dry_run else ''}Seed written to {target}")

    scaffold_project(project_root, dry_run=args.dry_run)

    if not args.dry_run:
        ok = verify_seed(project_root)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())