#!/usr/bin/env python3
"""Measure path citations in prose documents.

Imports CLAIM, IGNORED_DIRS and GENERATED_ROOTS from check_prompt_truth.py
rather than retyping them. A hand-copied variant is exactly how a previous
count came out 36 when the truth was 308 -- the lookbehind and the optional
line group are the parts that make the count defensible, and a copy drifts
on them silently.

Usage: measure_citations.py [document ...]
Defaults to the four documents measured by archive/tasks/document-citation-truth.yaml.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_prompt_truth import CLAIM, IGNORED_DIRS, GENERATED_ROOTS

DEFAULT_DOCS = ["ARCHITECTURE.md", "README.md", "theteam/SKILL.md", "theteam/CLI.md"]


def measure(root: Path, docs: list[str]) -> dict:
    raw = 0
    ignored = 0
    generated = 0
    line_cited_repo = 0
    line_cited_pkg = 0
    path_only = 0
    by_document = {}

    for rel in docs:
        text = (root / rel).read_text(encoding="utf-8")
        r = i = g = lc = lp = po = 0
        for m in CLAIM.finditer(text):
            ref = m.group(1)
            line = m.group(2)
            r += 1
            if any(ref.startswith(d) or f"/{d}/" in f"/{ref}" for d in IGNORED_DIRS):
                i += 1
                continue
            if any(ref.startswith(g) for g in GENERATED_ROOTS):
                g += 1
                continue
            exists = (root / ref).exists()
            if line is None:
                po += 1
            elif exists:
                lc += 1
            else:
                lp += 1
        classified = r - i - g
        by_document[rel] = {
            "raw": r, "classified": classified,
            "line_cited_repo": lc, "line_cited_pkg": lp, "path_only": po,
            "ignored": i, "generated": g,
        }
        raw += r
        ignored += i
        generated += g
        line_cited_repo += lc
        line_cited_pkg += lp
        path_only += po

    classified = raw - ignored - generated
    return {
        "raw_matches": raw,
        "dropped_by_ignore_rules": ignored,
        "dropped_as_generated_roots": generated,
        "classified_total": classified,
        "line_cited_repo": line_cited_repo,
        "line_cited_pkg": line_cited_pkg,
        "path_only": path_only,
        "by_document": by_document,
    }


def main(argv):
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    docs = argv[2:] or DEFAULT_DOCS
    m = measure(root, docs)
    print(f"raw_matches: {m['raw_matches']}")
    print(f"dropped_by_ignore_rules: {m['dropped_by_ignore_rules']}")
    print(f"dropped_as_generated_roots: {m['dropped_as_generated_roots']}")
    print(f"classified_total: {m['classified_total']}")
    print(f"line_cited_repo: {m['line_cited_repo']}")
    print(f"line_cited_pkg: {m['line_cited_pkg']}")
    print(f"path_only: {m['path_only']}")
    for rel, v in m["by_document"].items():
        print(f"{rel}: raw={v['raw']} classified={v['classified']} "
              f"repo={v['line_cited_repo']} pkg={v['line_cited_pkg']} "
              f"path_only={v['path_only']} ignored={v['ignored']} "
              f"generated={v['generated']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))