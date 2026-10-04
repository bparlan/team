#!/usr/bin/env python3
"""Diagram citation truth checker.

Every symbol-bearing citation in diagrams/active-usage-architecture.json
names a file, a line and a symbol. A citation is wrong when the line does
not hold the named symbol -- an authoring defect, not staleness. Staleness
(the file moved) is a different class and is the existing anchor gate's job;
this checker only looks at whether the line is the line of the symbol.

Exit code:
  0   no findings
  1   usage error
  2   findings (deliberate exception to the report-does-not-gate rule --
      this is the only thing standing between nine wrong numbers and the
      next nine, and a checker nobody runs is indistinguishable from no
      checker)

Markdown citations (the session node cites theteam/SKILL.md) are out of
scope: there is no def/class to resolve, and the anchor gate already
catches the one case where that file genuinely changed.
"""

import ast
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
DIAGRAM = REPO / "diagrams" / "active-usage-architecture.json"


def resolve_symbol(path, label):
    """Line of the first def/class named `label` in `path`, or None."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == label:
                return node.lineno
    return None


def check(diagram_path=DIAGRAM):
    diagram = json.loads(diagram_path.read_text())
    findings = []
    for component in diagram.get("components", []):
        for source in component.get("sources", []):
            path = source.get("path", "")
            line = source.get("line")
            label = source.get("label")
            if not (path and line and label):
                continue
            full = REPO / path
            if not full.suffix == ".py":
                continue  # markdown citations are not symbol-bearing
            actual = resolve_symbol(full, label)
            if actual is None:
                findings.append({
                    "node": component["id"],
                    "file": path,
                    "cited_line": line,
                    "symbol": label,
                    "problem": "symbol not found in file",
                })
            elif actual != line:
                findings.append({
                    "node": component["id"],
                    "file": path,
                    "cited_line": line,
                    "resolved_line": actual,
                    "symbol": label,
                    "problem": "cited line does not hold the named symbol",
                })
    return findings


def main(argv):
    diagram = pathlib.Path(argv[1]) if len(argv) > 1 else DIAGRAM
    if not diagram.exists():
        print(f"diagram not found: {diagram}", file=sys.stderr)
        return 1
    findings = check(diagram)
    report = {
        "diagram": str(diagram),
        "components_checked": len(json.loads(diagram.read_text()).get("components", [])),
        "findings": findings,
    }
    print(json.dumps(report, indent=2))
    return 2 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))