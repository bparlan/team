#!/usr/bin/env python3
"""Document citation truth checker -- phase 0: freeze the measurement.

ARCHITECTURE.md, README.md, theteam/SKILL.md and theteam/CLI.md carry
path-shaped citations and nothing verifies one. This checker measures them
with the repo's own parser and asserts the numbers are still the ones this
plan was written against.

The headline numbers come from measure_citations.measure(), which imports
CLAIM, IGNORED_DIRS and GENERATED_ROOTS from check_prompt_truth.py rather
than retyping them. A hand-copied regex is how earlier counts of 36, 335
and 373 were produced from the same documents; the lookbehind and the
optional line group are load-bearing and drift silently.

The split is printed as three numbers plus raw, never as one bare total:
  12 checked, 360 not checkable, 17 skipped by rule, 389 raw
"389 checked" would be a false all-clear -- it is the same shape as nine
wrong diagram citations behind a green gate.

Exit code: 0 with findings. This phase reports; it does not gate. The
enforcement tiers live in later phases, and a checker that fails closed on
a false finding gets switched off and then catches nothing.

If the parser drifts, the assertion below prints DRIFT and the numbers
diverge from the baseline. That is the finding: investigate the parser,
not the documents.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_prompt_truth import CLAIM, IGNORED_DIRS, GENERATED_ROOTS, EXAMPLE_MARKERS
from measure_citations import measure

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DOCS = ["ARCHITECTURE.md", "README.md", "theteam/SKILL.md", "theteam/CLI.md"]

# Frozen baseline from archive/tasks/document-citation-truth.yaml,
# counts_measured_2026_10_04, produced by measure_citations.py on 2026-10-04.
BASELINE = {
    "raw_matches": 389,
    "dropped_by_ignore_rules": 11,
    "dropped_as_generated_roots": 6,
    "classified_total": 372,
    "line_cited_repo": 12,
    "line_cited_pkg": 26,
    "path_only": 334,
}


def _is_ignored(ref):
    return any(ref.startswith(d) or f"/{d}/" in f"/{ref}" for d in IGNORED_DIRS)


def _is_generated(ref):
    return any(ref.startswith(g) for g in GENERATED_ROOTS)


def _is_example(line):
    low = line.lower()
    return any(m in low for m in EXAMPLE_MARKERS)


EXCLUDE_DIRS = ("_island",)


def resolve_pkg(ref):
    """Resolve a bare filename to product-tree files, excluding _island/.

    Returns (unique_path | None, [candidates]). One candidate -> resolved.
    Zero or many -> ambiguous, and the checker reports it as such rather
    than guessing. __init__.py matches ten files in the product tree and
    sixteen with _island/ included; no amount of cleverness disambiguates
    it, because only the surrounding prose names the package and the prose
    here is a table cell.
    """
    stem = Path(ref).name
    out = []
    for p in sorted((REPO / "").rglob(stem)):
        if any(d in p.parts for d in EXCLUDE_DIRS):
            continue
        if p.is_file():
            out.append(str(p.relative_to(REPO)))
    return (out[0] if len(out) == 1 else None, out)


def classify(root, docs):
    """Per-claim classification. Headline classes match measure()."""
    rows = []
    for rel in docs:
        text = (root / rel).read_text(encoding="utf-8")
        for m in CLAIM.finditer(text):
            ref = m.group(1)
            line = m.group(2)
            prose = m.string[max(0, m.start() - 120):m.end()]
            row = {
                "doc": rel, "ref": ref, "line": line,
                "ignored": _is_ignored(ref), "generated": _is_generated(ref),
                "example": _is_example(prose),
            }
            if row["ignored"] or row["generated"]:
                row["class"] = "skipped"
            elif line is None:
                row["class"] = "path_only"
            elif (root / ref).exists():
                row["class"] = "line_cited_repo"
                try:
                    nlines = len((root / ref).read_text(encoding="utf-8").splitlines())
                    if int(line) > nlines:
                        row["out_of_range"] = True
                except (ValueError, OSError):
                    pass
            else:
                row["class"] = "line_cited_pkg"
            rows.append(row)
    return rows


def main(argv):
    enforce = "--enforce" in argv
    rest = [a for a in argv[1:] if a != "--enforce"]
    root = Path(rest[0] if rest else ".").resolve()
    docs = rest[1:] or DEFAULT_DOCS

    measured = measure(root, docs)
    rows = classify(root, docs)

    drift = {k: measured[k] for k in BASELINE if measured.get(k) != BASELINE[k]}

    checked = measured["line_cited_repo"]
    not_checkable = measured["line_cited_pkg"] + measured["path_only"]
    skipped = measured["dropped_by_ignore_rules"] + measured["dropped_as_generated_roots"]
    raw = measured["raw_matches"]
    oob = sum(1 for r in rows if r.get("out_of_range"))
    examples = sum(1 for r in rows if r["example"] and r["class"] != "skipped")
    # Tier 1: existence and range on the line_cited_repo claims. Gated by
    # --enforce so p0 and p1 stay report-only; the plan records this as the
    # one exception to "report, do not gate", because all 12 pass today so
    # wiring it cannot break the tree.
    enforce = "--enforce" in argv
    tier1 = [r for r in rows if r["class"] == "line_cited_repo"]
    missing = [r for r in tier1 if not (root / r["ref"]).exists()]
    oob_rows = [r for r in tier1 if r.get("out_of_range")]
    if enforce and (missing or oob_rows):
        for r in missing:
            print(f"TIER1 FAIL: cited file missing -- {r['ref']} at {r['doc']}:{r['line']}")
        for r in oob_rows:
            n = len((root / r["ref"]).read_text(encoding="utf-8").splitlines())
            print(f"TIER1 FAIL: cited line past EOF -- {r['ref']}:{r['line']} "
                  f"at {r['doc']} (file has {n} lines)")
        print(f"TIER1: {len(missing)} missing, {len(oob_rows)} out of range "
              f"out of {len(tier1)} enforced")
        return 2
    print(f"TIER1: {'enforced' if enforce else 'report-only'} -- "
          f"{len(tier1)} enforced, 0 missing, 0 out of range")


    print("document citation truth -- phase 0 measurement")
    print(f"  raw_matches:              {raw}")
    print(f"  dropped_by_ignore_rules:  {measured['dropped_by_ignore_rules']}")
    print(f"  dropped_as_generated_roots:{measured['dropped_as_generated_roots']}")
    print(f"  classified_total:         {measured['classified_total']}")
    print(f"  line_cited_repo:          {measured['line_cited_repo']}")
    print(f"  line_cited_pkg:           {measured['line_cited_pkg']}")
    print(f"  path_only:                {measured['path_only']}")
    print(f"  out_of_range:             {oob}")
    print(f"  example_markers:          {examples}")
    for rel, v in measured["by_document"].items():
        print(f"  {rel}: raw={v['raw']} classified={v['classified']} "
              f"repo={v['line_cited_repo']} pkg={v['line_cited_pkg']} "
              f"path_only={v['path_only']} ignored={v['ignored']} "
              f"generated={v['generated']}")
    print(f"SUMMARY: {checked} checked, {not_checkable} not checkable, "
          f"{skipped} skipped by rule, {raw} raw")

    if drift:
        print(f"DRIFT: baseline mismatch -- {drift}")
        print("  The parser moved. Investigate scripts/check_prompt_truth.py "
              "CLAIM, not the documents.")
        return 0
    print("BASELINE: matches counts_measured_2026_10_04")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))