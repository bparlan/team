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

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGRAM_DIR = REPO_ROOT / "diagrams"
SIDECAR_SUFFIX = ".anchors.json"

OK = 0
BROKEN_INPUT = 1
CANNOT_EVALUATE = 2
FINDINGS = 3

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


def _report(lines: list[str]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def record() -> int:
    """Write the sidecar for every diagram that carries source anchors."""
    written = 0
    for diagram_path in sorted(DIAGRAM_DIR.glob("*.json")):
        if diagram_path.name.startswith("."):
            continue
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


def check() -> int:
    for diagram_path in sorted(DIAGRAM_DIR.glob("*.json")):
        if diagram_path.name.startswith("."):
            continue
        try:
            diagram = json.loads(diagram_path.read_text())
        except json.JSONDecodeError as e:
            _report([f"# update-team — cannot check", "",
                     f"`{diagram_path.name}` is not valid JSON: {e}"])
            return BROKEN_INPUT

        sidecar = _sidecar_for(diagram_path)
        if not sidecar.exists():
            continue

        recorded = json.loads(sidecar.read_text()).get("cited", {})
        missing = [p for p in recorded if not (REPO_ROOT / p).exists()]
        if missing:
            _report(["# update-team — cannot check", "",
                     f"`{diagram_path.name}` cites files that no longer exist: "
                     + ", ".join(f"`{p}`" for p in missing)])
            return CANNOT_EVALUATE

        changed = [p for p, was in sorted(recorded.items())
                   if _hash(REPO_ROOT / p) != was]

        lines = [
            f"# update-team — {diagram_path.name}",
            "",
            f"- **anchors recorded:** {len(recorded)}",
            f"- **verdict:** {'re-derive may be needed' if changed else 'nothing necessary'}",
            f"- **exit code:** {FINDINGS if changed else OK}",
            "",
        ]
        if changed:
            lines += ["## Cited files that changed", ""]
            lines += [f"- `{p}`" for p in changed]
            lines += ["", "Re-derive the nodes citing these files, then re-run "
                          "step 4. Scope is a trigger, not a verdict: a changed "
                          "file may leave its node correct."]
        else:
            lines += ["No cited file has changed since the diagram was derived, so "
                      "the diagram is still true. Steps 1–4 remain manual: archify "
                      "and the production skill live outside the project mount, and "
                      "editing existing files has no output signal for the llm "
                      "completion rule."]
        _report(lines)
        return FINDINGS if changed else OK

    _report(["# update-team — cannot check", "",
             "No diagram has an anchor sidecar. Run "
             "`python3 scripts/update_team_check.py --record` on the host to "
             "create one, then re-run this task."])
    return CANNOT_EVALUATE


if __name__ == "__main__":
    sys.exit(record() if "--record" in sys.argv else check())
