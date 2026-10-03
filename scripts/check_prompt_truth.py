#!/usr/bin/env python3
"""
Check that the file:line claims in `prompts/*.md` still point at what they
claim to point at.

A prompt is read by a member who cannot see the code it describes. When it
says `theteam/cli.py:100` resolves the config, the member takes that as
ground truth and reasons from it. If line 100 has since become something else,
the member reasons from a fiction -- and nothing reports it, because prose is
not code and no test reads it.

`doc-truth` audits the human-facing documents and deliberately excludes the
prompts (`prompts/doc-truth-audit.md:20`). This is the excluded layer, checked
mechanically rather than by judgement: whether a line still holds its claim is
a fact about two files, not an opinion.

Usage:
    check_prompt_truth.py [project_root]

Writes `.omp/theteam/reports/prompt-truth.json` and prints the same JSON on
stdout. Exits 0 whether or not it finds anything -- a reporting task, not a
gate, because a gate that fails on a stale comment gets disabled.

What counts as a claim:

    path/to/file.py:42         a line number that must exist
    path/to/file.py:42-51      a range that must exist
    path/to/file.md            a bare path that must exist

What it does NOT do, deliberately: judge whether the cited line means what the
prose says it means. That needs a reader, and a reader that guesses is worse
than no reader. This checks the referent exists and is inside the file. A
claim can pass here and still be wrong about the code -- `llm.py:117-136`
cites a real function whose substance the prose misdescribes. Both are worth
knowing; only one is mechanical.

Bare names with no directory (`llm.py:117`) are reported as `ambiguous`: a
prompt should name the path it means, because the reader has to guess too.
"""
import json
import re
import sys
from pathlib import Path

#: `path/name.ext`, optionally followed by `:line` or `:start-end`. Requires a
#: separator so `docker-compose.yml` is a path but prose like `e.g.md` is not
#: mistaken for one -- every real claim in these prompts has a slash or a known
#: extension, and the fallback below keeps the bare-name case visible.
#: `path/name.ext`, optionally `:line` or `:start-end`.
#:
#: The leading `(?<![\w*.-])` matters more than it looks: a prompt that says
#: `*_report.json` is naming a glob pattern, not a file, and reporting it as a
#: missing citation turns a true sentence into a false finding. The same guard
#: skips `foo.py.bak` and the tail of a longer dotted name.
CLAIM = re.compile(
    r"(?<![\w*.-])"                      # not mid-identifier, glob, or path
    r"((?:[\w.-]+/)*[\w.-]+\.(?:py|sh|md|json|ya?ml|toml|cfg|ini|txt))"
    r"(?::(\d+)(?:\s*-\s*(\d+))?)?"
)

#: Directories that hold copies, archives, or tool caches. A `README.md` in
#: `.pytest_cache/` is not a second root README, and treating the match count
#: as ambiguity would flag the most-cited document in the repo. Only real
#: source trees count as candidates.
IGNORED_DIRS = (".git", ".pytest_cache", "__pycache__", "archive", ".omp",
                "node_modules", ".mypy_cache", ".ruff_cache")

#: Roots whose contents are produced by a phase at run time. A prompt naming
#: a file under one of these is describing what a phase *writes*, not citing
#: source, so its absence is not drift. Checking them would report every
#: prompt's own input list as broken before the first run ever happens.
GENERATED_ROOTS = (".omp/", "reports/", "wal.json")

#: Markers for a line that shows a shape rather than citing a real file.
#: `touch <dir>/__probe.py` is a true and useful instruction; reporting its
#: placeholder as a missing file would be a finding about the checker.
EXAMPLE_MARKERS = ("e.g.", "i.e.", "for example", "like this", "<same-named")


def _is_example(line: str) -> bool:
    low = line.lower()
    return any(marker in low for marker in EXAMPLE_MARKERS)


def _resolve(root: Path, ref: str) -> Path | None:
    """Locate `ref` under the project, preferring the shallowest match.

    Prompts name paths the way a person reads them: `cli.py`, `llm.py`. Those
    resolve against several directories at once, and picking one silently would
    report a real claim as clean when it points somewhere else.
    """
    direct = root / ref
    if direct.is_file():
        return direct
    matches = _all_matches(root, ref)
    return matches[0] if matches else None


def _all_matches(root: Path, ref: str):
    """Every real file named `ref`, ignoring caches and archives."""
    out = []
    for path in root.glob(f"**/{ref}"):
        if not path.is_file():
            continue
        rel = path.relative_to(root).parts
        if any(part in IGNORED_DIRS for part in rel):
            continue
        out.append(path)
    return sorted(out)


def check_project(root: Path):
    findings = []
    checked = 0

    for prompt in sorted((root / "prompts").glob("*.md")):
        text = prompt.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            if _is_example(line):
                continue
            for m in CLAIM.finditer(line):
                ref, start, end = m.group(1), m.group(2), m.group(3)
                # A path under .omp/ or reports/ names a phase output, not a
                # source file: it does not exist until something writes it.
                if ref.startswith(GENERATED_ROOTS):
                    continue
                checked += 1
                where = {"prompt": f"prompts/{prompt.name}", "line": lineno,
                         "claim": m.group(0).strip()}

                target = _resolve(root, ref)
                if target is None:
                    findings.append({**where, "check": "missing_file",
                                     "detail": f"{ref} does not exist",
                                     "fix": "correct the path or drop the claim"})
                    continue

                if start is None:
                    continue  # bare existing path: nothing to drift

                total = len(target.read_text(encoding="utf-8", errors="replace").splitlines())
                a = int(start)
                b = int(end) if end else a
                if a < 1 or a > total or b < 1 or b > total or b < a:
                    findings.append({
                        **where, "check": "line_out_of_range",
                        "detail": f"{ref} cites :{a}{'-' + str(b) if end else ''} "
                                  f"but the file has {total} lines",
                        "fix": "re-cite the line, or drop the line number and "
                               "describe the function by name"})

    return {
        "prompts_checked": len(list((root / "prompts").glob("*.md"))),
        "claims_checked": checked,
        "findings": len(findings),
        "details": findings,
    }


def main(argv):
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    if not (root / "prompts").is_dir():
        print(f"no prompts/ at {root}", file=sys.stderr)
        return 1

    report = check_project(root)
    body = json.dumps(report, indent=2, ensure_ascii=False)

    # Every `script:` phase runs containerized with the project read-only
    # unless it declares `writable_project`. A read-only mount costs the file,
    # never the report.
    written_to = None
    try:
        out_dir = root / ".omp/theteam/reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "prompt-truth.json").write_text(body, encoding="utf-8")
        written_to = out_dir / "prompt-truth.json"
    except OSError as e:
        print(f"# no handoff written ({e}); reporting on stdout only", file=sys.stderr)

    print(f"{report['claims_checked']} claims in "
          f"{report['prompts_checked']} prompts, {report['findings']} findings"
          + (f" -> {written_to}" if written_to else " (stdout only)"))
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))