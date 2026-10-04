#!/usr/bin/env python3
"""Document citation truth checker.

ARCHITECTURE.md, README.md, theteam/SKILL.md and theteam/CLI.md carry
path-shaped citations and nothing verifies one. check_prompt_truth.py guards
prompts/, check_task_contract.py guards tasks/*.yaml, update_team_check.py
hashes the files diagrams cite. Prose is the surface an agent reads first,
and it is the only one with no gate.

Two wrong ARCHITECTURE.md citations were published into a delivered report
once already, both caught by hand. This checker exists so the next one is
caught mechanically.

Measurement (p0) is delegated to measure_citations.measure(), which imports
CLAIM, IGNORED_DIRS and GENERATED_ROOTS from check_prompt_truth.py rather
than retyping them. A hand-copied regex is how earlier counts of 36, 335 and
373 came out of these same four documents; the lookbehind and the optional
line group are load-bearing and drift silently.

The split is always printed as three numbers plus raw, never one bare total.
"389 checked" would be a false all-clear: it is the same shape as nine wrong
diagram citations behind a green gate, and as an exit code that cannot say how
many diagrams it read.

Resolution (p1). A citation may be written three ways, and all three occur:
  theteam/state.py            relative to repo root
  tasks/executor.py           relative to the citing document's directory
  repository.py               a bare filename
The first two resolve mechanically. The third resolves only when exactly one
file carries the name; __init__.py matches ten in the product tree, so those
claims are reported ambiguous and never guessed. A wrong guess is a false
finding about a document that was correct.

Enforcement (p2). --enforce makes existence and range failures exit 2. This
is the one named exception to "report, do not gate", recorded in
archive/tasks/document-citation-truth.yaml p2: all 12 checkable claims pass
today, so wiring it cannot break the tree. Every other class reports and
exits 0.

Usage:
  check_doc_truth.py [root] [document ...] [--enforce]
"""

import re
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_prompt_truth import CLAIM, IGNORED_DIRS, GENERATED_ROOTS, EXAMPLE_MARKERS
from measure_citations import measure

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DOCS = ["ARCHITECTURE.md", "README.md", "theteam/SKILL.md", "theteam/CLI.md"]

#: _island/ holds seven extra __init__.py files and is not part of the product.
EXCLUDE_DIRS = ("_island",)

#: Frozen baseline from archive/tasks/document-citation-truth.yaml,
#: counts_measured_2026_10_04, produced by measure_citations.py.
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


def _is_example(prose):
    low = prose.lower()
    return any(m in low for m in EXAMPLE_MARKERS)


def resolve_pkg(ref, root):
    """Resolve a bare filename by searching the tree. Returns (path | None, [all])."""
    stem = Path(ref).name
    out = []
    for p in sorted(root.rglob(stem)):
        if any(d in p.parts for d in EXCLUDE_DIRS):
            continue
        if p.is_file():
            out.append(str(p.relative_to(root)))
    return (out[0] if len(out) == 1 else None, out)


def classify(root, docs):
    """Classify every claim. Returns one row per CLAIM match."""
    rows = []
    for rel in docs:
        text = (root / rel).read_text(encoding="utf-8")
        for m in CLAIM.finditer(text):
            ref, line, end = m.group(1), m.group(2), m.group(3)
            prose = m.string[max(0, m.start() - 120):m.end()]
            row = {
                "doc": rel, "ref": ref, "line": line, "end": end,
                "at": m.start(),
                "ignored": _is_ignored(ref), "generated": _is_generated(ref),
                "example": _is_example(prose),
            }
            if row["ignored"] or row["generated"]:
                row["class"] = "skipped"
            elif line is None:
                row["class"] = "path_only"
            else:
                resolved, candidates = _resolve_cited(root, rel, ref)
                row["candidates"] = len(candidates)
                if "/" not in ref:
                    # A bare filename. Resolvable only if exactly one file
                    # carries the name; otherwise package-relative prose that
                    # only the surrounding sentence can disambiguate.
                    row["class"] = "line_cited_pkg"
                    row["resolved_ref"] = resolved
                    row["ambiguous"] = resolved is None
                elif resolved is None:
                    # Directory-qualified and matched by none of the three
                    # resolution forms: the cited file is gone.
                    row["class"] = "missing_file"
                else:
                    row["class"] = "line_cited_repo"
                    row["resolved_ref"] = resolved
                    try:
                        n = len((root / resolved).read_text(encoding="utf-8").splitlines())
                        if int(line) > n:
                            row["out_of_range"] = True
                    except (ValueError, OSError):
                        pass
            rows.append(row)
    return rows

def _resolve_cited(root, doc, ref):
    """Resolve a citation. Returns (path | None, [candidates]).

    Three forms occur in these documents, and all three are real:
      theteam/state.py     relative to repo root
      tasks/executor.py    relative to the citing document's directory
      repository.py        a bare filename, resolvable by tree search
    The bare form resolves only when exactly one file carries the name.
    """
    if (root / ref).exists():
        return ref, [ref]
    sibling = root / Path(doc).parent / ref
    if sibling.exists():
        return str(sibling.relative_to(root)), [ref]
    unique, all_cands = resolve_pkg(ref, root)
    return unique, all_cands

def expected_fragments(prose: str) -> list[str]:
    """Literal strings the prose expects the cited line to contain.

    Tier 3 only works where the prose names something checkable. Three shapes
    occur in these documents and are extracted mechanically:

      `code` inside backticks, adjacent to the citation
      "a quoted string"
      def/class NAME() in backticks, which is a symbol the line must define

    Anything else yields no fragment, and a claim with no fragment is
    reported as unverifiable rather than passing. A tier that silently
    checked nothing would be the same false all-clear this repo has twice.
    """
    out = []
    for frag in re.findall(r"`([^`\n]{2,60})`", prose):
        f = frag.strip()
        if f and not _looks_like_path(f) and not f.endswith((":", ",", ";", ".")):
            out.append(f.rstrip("()").split(".")[-1] if f.endswith("()") else f)
    for frag in re.findall(r'"([^"\n]{2,60})"', prose):
        out.append(frag)
    return [f for f in out if len(f) >= 3]


def _looks_like_path(token: str) -> bool:
    return "/" in token or bool(re.search(r"\.(py|md|json|yaml|yml|sh|toml)$", token))


def content_check(root, doc_text, row) -> dict:
    """Does the cited line hold the fragment the prose expects?

    Returns {status: verified | mismatch | unverifiable, ...}. A range
    citation (`:72-80`) is checked against the whole span, not one line,
    because the prose describes a block.
    """
    target = root / row["resolved_ref"]
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {"status": "unverifiable", "reason": "cited file unreadable"}
    lo = int(row["line"])
    hi = int(row["end"]) if row.get("end") else lo
    if hi > len(lines) or lo < 1:
        return {"status": "unverifiable", "reason": "range outside file"}
    span = "\n".join(lines[lo - 1:hi])
    # Fragments come from the claim's OWN prose line, not a window. A
    # 200-character window pulls fragments out of neighbouring sentences and
    # reports mismatches on citations that are correct -- 7 of 15 on the real
    # tree. A tier that cries wolf gets switched off and then catches nothing,
    # so the extractor is deliberately narrow: unverifiable beats wrong.
    ls = doc_text.rfind("\n", 0, row["at"]) + 1
    le = doc_text.find("\n", row["at"])
    le = le if le > 0 else len(doc_text)
    prose = doc_text[ls:le]
    frags = expected_fragments(prose)
    if not frags:
        return {"status": "unverifiable", "reason": "prose names no checkable fragment"}
    hits = [f for f in frags if f in span]
    if hits:
        return {"status": "verified", "fragments": hits}
    return {"status": "mismatch", "fragments": frags, "span": span.strip()[:200]}



def main(argv):
    enforce = "--enforce" in argv
    rest = [a for a in argv[1:] if a != "--enforce"]
    root = Path(rest[0] if rest else ".").resolve()
    docs = rest[1:] or DEFAULT_DOCS
    is_repo_tree = not rest[1:]

    rows = classify(root, docs)
    counts = {c: sum(1 for r in rows if r["class"] == c) for c in
              ("skipped", "line_cited_repo", "line_cited_pkg", "path_only", "missing_file")}
    checked = counts["line_cited_repo"]
    not_checkable = counts["line_cited_pkg"] + counts["path_only"]
    skipped = counts["skipped"]
    raw = len(rows)
    oob = sum(1 for r in rows if r.get("out_of_range"))
    ambig_rows = [r for r in rows if r.get("ambiguous")]

    tier1 = [r for r in rows if r["class"] in ("line_cited_repo", "missing_file")]
    missing = [r for r in tier1 if r["class"] == "missing_file"]
    oob_rows = [r for r in tier1 if r.get("out_of_range")]

    # Tier 3: does the cited line hold the fragment the prose expects?
    # Report-only. This is the newest and least proven rule, and a check that
    # fails closed on a false finding gets switched off and then catches
    # nothing. Tier 1 keeps its enforcement.
    doc_texts = {rel: (root / rel).read_text(encoding="utf-8") for rel in docs}
    tier3 = []
    for r in tier1:
        if r["class"] != "line_cited_repo" or r.get("out_of_range"):
            tier3.append({**r, "status": "unverifiable", "reason": "not an in-range citation"})
            continue
        tier3.append({**r, **content_check(root, doc_texts[r["doc"]], r)})
    t3_verified = [r for r in tier3 if r["status"] == "verified"]
    t3_mismatch = [r for r in tier3 if r["status"] == "mismatch"]
    t3_unverifiable = [r for r in tier3 if r["status"] == "unverifiable"]

    if enforce and (missing or oob_rows):
        for r in missing:
            print(f"TIER1 FAIL: cited file missing -- {r['ref']} at {r['doc']}:{r['line']}")
        for r in oob_rows:
            n = len((root / r["resolved_ref"]).read_text(encoding="utf-8").splitlines())
            print(f"TIER1 FAIL: cited line past EOF -- {r['resolved_ref']}:{r['line']} "
                  f"at {r['doc']} (file has {n} lines)")
        print(f"TIER1: {len(missing)} missing, {len(oob_rows)} out of range "
              f"of {len(tier1)} enforced")
        return 2

    print("document citation truth")
    print(f"  TIER1: {'enforced' if enforce else 'report-only'} -- "
          f"{len(tier1)} enforced, {len(missing)} missing, {len(oob_rows)} out of range")
    print(f"  raw_matches:              {raw}")
    print(f"  classified_total:         {checked + not_checkable}")
    print(f"  skipped_by_rule:          {skipped}")
    print(f"  line_cited_repo (checked):{checked:>4}")
    print(f"  line_cited_pkg:           {counts['line_cited_pkg']}")
    print(f"  path_only:                {counts['path_only']}")
    print(f"  missing_file:             {counts['missing_file']}")
    print(f"  out_of_range:             {oob}")
    print(f"  example_markers:          {sum(1 for r in rows if r['example'] and r['class'] != 'skipped')}")
    print(f"  TIER3: report-only -- {len(t3_verified)} verified, "
          f"{len(t3_mismatch)} mismatch, {len(t3_unverifiable)} unverifiable "
          f"of {len(tier3)} claims")
    for r in t3_mismatch:
        print(f"    TIER3 MISMATCH: {r['ref']}:{r['line']} at {r['doc']} -- "
              f"prose expects {r['fragments']}, cited span holds "
              f"{r['span']!r}")
    if t3_unverifiable:
        reasons = sorted({r.get('reason', '?') for r in t3_unverifiable})
        print(f"  TIER3 unverifiable reasons: {'; '.join(reasons)}")
    by_doc = {}
    for r in rows:
        by_doc.setdefault(r["doc"], {}).setdefault(r["class"], 0)
        by_doc[r["doc"]][r["class"]] += 1
    for rel, v in by_doc.items():
        print(f"  {rel}: " + " ".join(f"{k}={n}" for k, n in sorted(v.items())))
    if ambig_rows:
        seen = sorted({r["ref"] for r in ambig_rows})
        print(f"  AMBIGUOUS: {len(ambig_rows)} claims over {len(seen)} names "
              f"(refused to guess): {', '.join(seen)}")
        for r in ambig_rows:
            print(f"    {r['ref']} at {r['doc']}:{r['line']} -- "
                  f"{r['candidates']} candidates")
    print(f"SUMMARY: {checked} checked, {not_checkable} not checkable, "
          f"{skipped} skipped by rule, {raw} raw")
    print("  SCOPE NOTE: theteam/SKILL.md is measured but not resolved -- "
          "scripts/export_skill.py rewrites repo-relative paths to absolute on "
          "the way out, so the repo copy and the installed copy are one decision.")

    if is_repo_tree:
        measured = measure(root, docs)
        drift = {k: measured[k] for k in BASELINE if measured.get(k) != BASELINE[k]}
        if drift:
            print(f"DRIFT: parser baseline mismatch -- {drift}")
            print("  Investigate CLAIM in scripts/check_prompt_truth.py, not the documents.")
        else:
            print("BASELINE: matches counts_measured_2026_10_04 "
                  "(389 raw / 11 ignored / 6 generated / 372 classified)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))