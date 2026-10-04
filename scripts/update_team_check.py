#!/usr/bin/env python3
"""Step 0 of the post-implementation sequence: is anything necessary?

The staleness gate for `diagrams/active-usage-architecture.json`. It answers
one question — has any file this diagram cites changed since it was derived?

## Why content hashes and not git

The obvious implementation is `git diff --name-only <pin>..HEAD -- <cited
paths>`. It cannot run here, and that is measured rather than assumed:

    docker run --rm theteam:p4final sh -c "which git"
    NO-GIT-BINARY

`theteam:p4final` is the phase image (`executor.py:39`), and it has no git
binary. A git-based gate therefore exits CANNOT_EVALUATE on every run, which
the executor scores as a failure (`executor.py:339`) — five breaker trips and
then the task never runs again. A gate that cannot run in its own container is
not a gate.

So staleness is measured by hashing instead. The derived state lives in
`diagrams/<name>.anchors.json`, written by `--record`:

    {
      "revision": "<the commit the diagram was derived at>",
      "cited":  {"theteam/cli.py": "<sha256[:16]>", ...}
    }

A cited file whose hash differs from the recorded one changed since the
diagram was derived. That answers the same question git would, works inside
the container, and needs nothing but the standard library.

The revision is retained for the report and for a human diff — it is context,
not the gate.

## What this is and is not

Scope is a trigger, not a verdict. A cited file that changed may leave its
node perfectly correct, and re-deriving it when it did not need it is the
safe failure mode. The opposite — staying quiet about a file that did change —
is the failure this exists to prevent.

A diagram with no anchor sidecar, or one whose cited files have all vanished,
has no mechanical staleness test. That is reported as could-not-evaluate
rather than reported as up to date.

Exit codes reuse the executor's convention (`executor.py:59-60`), because
those codes carry meaning the executor already acts on:

  0  up to date, nothing necessary
  2  could not evaluate — no anchor sidecar, no pinned revision, or a cited
     file that no longer exists
  3  findings — a cited file changed since the diagram was derived. Scored as
     success by the executor, which records it without advancing the breaker.

Invalid JSON exits 1, the code an uncaught traceback produces, so a broken
input is never mistaken for a measurement.
"""

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_diagram_truth import resolve_symbol

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGRAM_DIR = REPO_ROOT / "diagrams"
SIDECAR_SUFFIX = ".anchors.json"
#: An evidence receipt, not a diagram. Excluded from _diagram_paths() for the
#: same reason as the sidecar: it is not something the anchor gate evaluates.
VISUAL_CHECK_SUFFIX = ".visual-check.json"

OK = 0
BROKEN_INPUT = 1
CANNOT_EVALUATE = 2
FINDINGS = 3
BAD_CITATION = 4

REPORT = REPO_ROOT / ".omp" / "theteam" / "reports" / "update-team.md"


def _sidecar_for(diagram_path: Path) -> Path:
    return diagram_path.with_name(diagram_path.stem + SIDECAR_SUFFIX)


def _cited_paths(diagram: dict) -> list[str]:
    return sorted({
        s["path"]
        for c in diagram.get("components", [])
        for s in c.get("sources", [])
    })

def _hash(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _bad_citations(diagram: dict) -> list[dict]:
    """Citations whose line does not hold its named symbol.

    A distinct class from a changed file. The hash check asks whether a file
    moved; this asks whether the recorded line still names the symbol the
    diagram claims. A changed file may have correct lines, and a correct line
    in an unchanged file is the authoring defect this exists to catch, so the
    two must never be reported as the same thing.

    Reuses scripts/check_diagram_truth.py's resolver rather than
    reimplementing it -- two copies of an AST walk drift apart silently.
    """
    return [
        {"node": c["id"], "file": s["path"], "line": s["line"],
         "symbol": s["label"], "resolved": resolved}
        for c, s, resolved in (
            (c, s, resolve_symbol(REPO_ROOT / s["path"], s["label"]))
            for c in diagram.get("components", [])
            for s in c.get("sources", [])
            if s.get("path") and s.get("line") and s.get("label")
        )
        if (REPO_ROOT / s["path"]).suffix == ".py"
        and resolved is not None
        and resolved != s["line"]
    ]


def _report(lines: list[str], name: str = "update-team") -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    if name != "update-team":
        # One file per diagram so a second verdict cannot overwrite the first.
        # The combined report above is the summary a caller reads first.
        (REPORT.parent / f"update-team-{name}.md").write_text(
            "\n".join(lines) + "\n")

def record() -> int:
    """Write the sidecar for every diagram that carries source anchors.

    Iterates _diagram_paths(), not glob('*.json'), for the same reason
    check() does: a sidecar is not a diagram, and recording one would write
    'active-usage-architecture.anchors.anchors.json' beside it.
    """
    written = 0
    for diagram_path in _diagram_paths():
        try:
            diagram = json.loads(diagram_path.read_text())
        except json.JSONDecodeError:
            continue
        cited = _cited_paths(diagram)
        if not cited:
            print(f"[update-team] {diagram_path.name}: no source anchors, "
                  f"no sidecar — judgment-only")
            continue
        payload = {
            "revision": diagram.get("meta", {})
                              .get("repository", {})
                              .get("revision"),
            "cited": {p: _hash(REPO_ROOT / p) for p in cited},
        }
        _sidecar_for(diagram_path).write_text(json.dumps(payload, indent=2) + "\n")
        print(f"[update-team] recorded {len(cited)} anchors for {diagram_path.name}")
        written += 1
    return 0 if written else CANNOT_EVALUATE


def _diagram_paths() -> list[Path]:
    """Diagrams only. Excluded by construction, not by accident or by luck
    of ordering.

    Two kinds of file live in diagrams/ and are not diagrams:

      *.anchors.json         the recorded-hash sidecar. glob('*.json')
                             matches it, sorted() puts it first, and
                             _sidecar_for() then looks for a sidecar OF
                             the sidecar.
      *.visual-check.json    an evidence receipt -- `evidenceKind`,
                             `artifact.sha256`, `visualReview: pending`.
                             It records that a render was checked; it is
                             not a rendered diagram, so counting it
                             produced a could-not-evaluate verdict for a
                             file that was never meant to be evaluated.

    Both are recognised by suffix, so a new one is excluded by the same rule
    rather than needing this list edited.
    """
    excluded = (SIDECAR_SUFFIX, VISUAL_CHECK_SUFFIX)
    return [
        p for p in sorted(DIAGRAM_DIR.glob("*.json"))
        if not p.name.startswith(".") and not p.name.endswith(excluded)
    ]


def _check_one(diagram_path: Path) -> tuple[int, list[str]]:
    """Evaluate one diagram. Returns (exit code, report lines)."""
    try:
        diagram = json.loads(diagram_path.read_text())
    except json.JSONDecodeError as e:
        return BROKEN_INPUT, [
            f"# update-team — {diagram_path.name}", "",
            f"- **verdict:** cannot check — invalid JSON: {e}",
        ]

    sidecar = _sidecar_for(diagram_path)
    if not sidecar.exists():
        return CANNOT_EVALUATE, [
            f"# update-team — {diagram_path.name}", "",
            "- **verdict:** could-not-evaluate — no anchor sidecar.",
            "", "Run `python3 scripts/update_team_check.py --record` on the host. "
            "Absence of a sidecar is never 'up to date'.",
        ]

    recorded = json.loads(sidecar.read_text()).get("cited", {})
    missing = [p for p in recorded if not (REPO_ROOT / p).exists()]
    if missing:
        return CANNOT_EVALUATE, [
            f"# update-team — {diagram_path.name}", "",
            "- **verdict:** cannot check — cited files no longer exist:",
            *[f"  - `{p}`" for p in missing],
        ]

    changed = [p for p, was in sorted(recorded.items()) if _hash(REPO_ROOT / p) != was]
    bad = _bad_citations(diagram)

    lines = [
        f"# update-team — {diagram_path.name}",
        "",
        f"- **anchors recorded:** {len(recorded)}",
        f"- **changed files:** {len(changed)}",
        f"- **bad citations:** {len(bad)}",
        f"- **verdict:** {_verdict(changed, bad)}",
        f"- **exit code:** {_exit_for(changed, bad)}",
        "",
    ]
    if changed:
        lines += ["## Cited files that changed", ""]
        lines += [f"- `{p}`" for p in changed]
        lines += ["", "Re-derive the nodes citing these files, then re-run step 4. "
              "Scope is a trigger, not a verdict: a changed file may leave its "
              "node correct."]
    if bad:
        lines += ["", "## Citations whose line does not hold the named symbol", "",
                  "A different defect from a changed file: the file never moved, "
                  "the number was wrong. Fix the number; do not re-derive.", ""]
        lines += [f"- `{b['node']}` — `{b['file']}:{b['line']}` holds "
                  f"`{b['symbol']}` at line {b['resolved']}" for b in bad]
    if not changed and not bad:
        lines += ["No cited file has changed and every symbol citation resolves to "
                  "its symbol, so the diagram is still true. Steps 1-4 remain "
                  "manual: archify and the production skill live outside the "
                  "project mount, and editing existing files has no output signal "
                  "for the llm completion rule."]
    return _exit_for(changed, bad), lines


def _verdict(changed, bad) -> str:
    if bad and changed:
        return "fix the numbers, and re-derive may be needed"
    if bad:
        return "fix the numbers — cited lines do not hold their symbols"
    if changed:
        return "re-derive may be needed"
    return "nothing necessary"


def _exit_for(changed, bad) -> int:
    if bad:
        return BAD_CITATION
    if changed:
        return FINDINGS
    return OK


def check() -> int:
    """Evaluate every diagram with a sidecar in one run.

    The exit code is the plain verdict class -- 0 ok, 2 cannot evaluate,
    3 a cited file changed, 4 a cited line does not hold its symbol -- and
    nothing else. It is consumed by tasks/task-update-team.yaml through
    theteam/tasks/executor.py, which branches on exactly those codes; an
    earlier version packed the evaluated count into it as n*10+class and
    silently broke that consumer, turning a working gate into a failing
    phase. Coverage is reported in the report text, where a reader sees it,
    rather than encoded in a code nobody can decode.
    """
    diagrams = _diagram_paths()
    reports: list[list[str]] = []
    worst = OK
    evaluated = 0
    for diagram_path in diagrams:
        code, lines = _check_one(diagram_path)
        reports.append(lines)
        if code != CANNOT_EVALUATE:
            evaluated += 1
        # BAD_CITATION(4) outranks FINDINGS(3) outranks OK(0); a diagram that
        # cannot be evaluated does not mask a real finding in another.
        if code == BAD_CITATION or (code == FINDINGS and worst == OK):
            worst = code
        _report(lines, name=diagram_path.stem)

    code = CANNOT_EVALUATE if evaluated == 0 else worst
    header = [
        "# update-team",
        "",
        f"- **diagrams present:** {len(diagrams)}",
        f"- **diagrams evaluated:** {evaluated}",
        f"- **diagrams could-not-evaluate:** {len(diagrams) - evaluated}",
        f"- **verdict class:** {_verdict_class(code)}",
        f"- **exit code:** {code}",
        "",
    ]
    for report in reports:
        header += report + [""]
    _report(header)
    return code


def _verdict_class(code: int) -> str:
    return {OK: "ok", FINDINGS: "cited-file-changed",
            BAD_CITATION: "bad-citation"}.get(code, "cannot-evaluate")


if __name__ == "__main__":
    sys.exit(record() if "--record" in sys.argv else check())
