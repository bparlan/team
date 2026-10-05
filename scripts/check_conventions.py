#!/usr/bin/env python3
"""
check_conventions.py — Claim-vs-reality checker for project conventions.

Reads seed.yaml from a project root and reports which conventions the project
claims to hold (via seed.yaml) and which it actually holds on disk.

Exit 0 with a JSON findings report (never fails closed). A checker that
fails closed on a false finding gets switched off, and a switched-off checker
catches nothing.

Usage:
    python scripts/check_conventions.py <project-root>
    python scripts/check_conventions.py .  # current directory
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml


def _finding(check: str, detail: str, fix: str) -> dict:
    return {"check": check, "detail": detail, "fix": fix}


def _load_seed(project_root: Path) -> dict | None:
    seed_path = project_root / "seed.yaml"
    if not seed_path.exists():
        return None
    return yaml.safe_load(seed_path.read_text(encoding="utf-8"))


def _check_directory_shape(project_root: Path, seed: dict, findings: list[dict]) -> None:
    """Every convention listed in seed.yaml directory_shape must exist on disk."""
    shape = seed.get("directory_shape", {})
    for label, paths in (("required", shape.get("required", [])),
                         ("optional", shape.get("optional", []))):
        for rel in paths:
            full = project_root / rel
            if not full.exists():
                findings.append(_finding(
                    "directory_shape",
                    f"{rel} ({label}) is missing from project root",
                    f"create {rel}/ or remove it from seed.yaml"))


def _check_required_files(project_root: Path, seed: dict, findings: list[dict]) -> None:
    """Every file in seed.yaml rule_template must exist on disk."""
    rules = seed.get("rule_template", {})
    for rel in rules.get("required_files", []):
        if not (project_root / rel).exists():
            findings.append(_finding(
                "required_files",
                f"{rel} is missing from project root",
                f"create {rel} or remove it from seed.yaml"))


def _check_convention_files(project_root: Path, seed: dict, findings: list[dict]) -> None:
    """Convention files (AGENTS.md, README.md) must exist and be non-empty."""
    for rel in ("AGENTS.md", "README.md"):
        path = project_root / rel
        if not path.exists():
            findings.append(_finding(
                "convention_files",
                f"{rel} is missing from project root",
                f"create {rel} or remove it from seed.yaml"))
        elif path.stat().st_size == 0:
            findings.append(_finding(
                "convention_files",
                f"{rel} exists but is empty",
                f"add content to {rel} or remove it from seed.yaml"))


def check_project(project_root: Path) -> dict:
    """Run all convention checks against a project root. Returns a report dict."""
    seed = _load_seed(project_root)
    if seed is None:
        return {
            "project_root": str(project_root),
            "seed_found": False,
            "error": "no seed.yaml in project root — run seed_project.py first",
            "checked": 0,
            "findings": 0,
            "details": [],
        }

    findings: list[dict] = []
    _check_directory_shape(project_root, seed, findings)
    _check_required_files(project_root, seed, findings)
    _check_convention_files(project_root, seed, findings)

    checked = (
        len(seed.get("directory_shape", {}).get("required", []))
        + len(seed.get("directory_shape", {}).get("optional", []))
        + len(seed.get("rule_template", {}).get("required_files", []))
        + 2  # AGENTS.md + README.md
    )

    return {
        "project_root": str(project_root),
        "seed_found": True,
        "checked": checked,
        "findings": len(findings),
        "details": findings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check a project's conventions against its seed.yaml.")
    parser.add_argument(
        "project_root", nargs="?", default=".",
        help="Path to the project root (default: current directory)")
    parser.add_argument(
        "--json", action="store_true", dest="json_out",
        help="Emit JSON report to stdout")
    args = parser.parse_args(argv)

    report = check_project(Path(args.project_root).resolve())

    out_dir = Path(args.project_root).resolve() / ".omp/theteam/reports"
    body = json.dumps(report, indent=2, ensure_ascii=False)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "conventions.json").write_text(body + "\n", encoding="utf-8")
    except OSError:
        pass  # read-only mount: report on stdout only

    if args.json_out:
        print(body)
    else:
        if report.get("error"):
            print(f"ERROR: {report['error']}", file=sys.stderr)
        else:
            print(f"{report['checked']} checks, {report['findings']} findings")
            for d in report.get("details", []):
                print(f"  ✗ {d['check']}: {d['detail']} → {d['fix']}")

    return 0  # never fails closed


if __name__ == "__main__":
    raise SystemExit(main())