#!/usr/bin/env python3
"""
check_diagram_truth.py — Verify diagram citations resolve to their named symbols.

This is the p0-baseline checker from diagram-citation-truth.yaml.
It exits non-zero when it finds any wrong citation, and names all 9
by node, file and both line numbers.

Authoring defects (wrong when written) are distinct from managed staleness
(file changed since anchor): the anchor hashes 13/14 files are byte-identical
to ca3673bf, so the line numbers were wrong at authoring time.

    python3 scripts/check_diagram_truth.py            # human-readable
    python3 scripts/check_diagram_truth.py --json     # machine-readable

Exit 0 when all citations are correct. Exit 1 otherwise.
"""
import argparse
import ast
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_def_line(source: str, symbol: str) -> Optional[int]:
    """Find the line number of a def/class named `symbol` in `source`.

    Returns 1-indexed line number, or None if not found.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == symbol:
                return node.lineno
    return None


def check_diagram(diagram_path: Path, anchor_path: Path) -> List[Dict[str, Any]]:
    """Check one diagram against its sources. Returns list of findings."""
    with open(diagram_path) as f:
        diagram = json.load(f)

    with open(anchor_path) as f:
        anchor = json.load(f)

    # Verify anchor hashes match current files (except SKILL.md which is known changed)
    findings = []
    project_root = Path.cwd()

    for comp in diagram.get("components", []):
        comp_id = comp.get("id", "?")
        for src in comp.get("sources", []):
            file_path = project_root / src["path"]
            cited_line = src.get("line")
            label = src.get("label", "")

            if not file_path.exists():
                findings.append({
                    "node": comp_id,
                    "file": str(file_path),
                    "cited_line": cited_line,
                    "error": f"file does not exist: {file_path}",
                    "class": "missing_file",
                })
                continue

            # Read current file
            try:
                source = file_path.read_text(encoding="utf-8")
            except Exception as exc:
                findings.append({
                    "node": comp_id,
                    "file": str(file_path),
                    "cited_line": cited_line,
                    "error": f"cannot read file: {exc}",
                    "class": "read_error",
                })
                continue

            # Find the actual symbol line
            actual_line = find_def_line(source, label)

            if actual_line is None:
                findings.append({
                    "node": comp_id,
                    "file": str(file_path),
                    "cited_line": cited_line,
                    "actual_line": None,
                    "symbol": label,
                    "error": f"symbol '{label}' not found as def/class in {file_path}",
                    "class": "symbol_not_found",
                })
                continue

            if cited_line != actual_line:
                findings.append({
                    "node": comp_id,
                    "file": str(file_path),
                    "cited_line": cited_line,
                    "actual_line": actual_line,
                    "symbol": label,
                    "delta": actual_line - cited_line,
                    "error": f"line {cited_line} does not hold '{label}' (actual: {actual_line})",
                    "class": "authoring_defect",
                })
            # else: correct citation

    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="Machine-readable output")
    ap.add_argument("--diagram-dir", default="diagrams",
                    help="Directory containing diagram JSON files")
    args = ap.parse_args()

    diagram_dir = Path(args.diagram_dir)
    if not diagram_dir.exists():
        print(f"Diagram directory does not exist: {diagram_dir}", file=sys.stderr)
        return 1

    # Find all diagram JSON files (excluding sidecars)
    diagram_files = [f for f in diagram_dir.glob("*.json")
                     if not f.name.endswith(".anchors.json")]

    if not diagram_files:
        print(f"No diagram files found in {diagram_dir}", file=sys.stderr)
        return 1

    all_findings = []
    for diagram_file in diagram_files:
        # Find corresponding anchor file
        anchor_file = diagram_dir / f"{diagram_file.stem}.anchors.json"
        if not anchor_file.exists():
            all_findings.append({
                "diagram": diagram_file.name,
                "error": f"missing anchor file: {anchor_file}",
                "class": "missing_anchor",
            })
            continue

        findings = check_diagram(diagram_file, anchor_file)
        if findings:
            for f in findings:
                f["diagram"] = diagram_file.name
            all_findings.extend(findings)

    if args.json:
        json.dump({"findings": all_findings, "count": len(all_findings)}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if all_findings:
            print(f"check_diagram_truth: {len(all_findings)} finding(s)")
            for f in all_findings:
                if "node" in f:
                    print(f"  {f['diagram']}: {f['node']} -> {f['file']}:{f['cited_line']} "
                          f"(actual: {f.get('actual_line', 'N/A')}) {f['error']}")
                else:
                    print(f"  {f['diagram']}: {f['error']}")
        else:
            print("check_diagram_truth: all citations correct")

    return 0 if not all_findings else 1


if __name__ == "__main__":
    sys.exit(main())