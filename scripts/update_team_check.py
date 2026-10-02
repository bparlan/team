#!/usr/bin/env python3
"""Step 0 of the post-implementation sequence: is anything necessary?

This task does the mechanical half and names the rest. Most of the sequence
cannot run inside a `script:` phase, so this one reports what it can and
leaves the rest to the session:

  * archify lives at ~/.omp/agent/skills/archify, outside the project mount.
  * the production skill lives at ~/.omp/agent/skills/theteam, likewise.
  * editing existing files has no output signal for the llm completion rule.

Staleness is measured from the data the diagram JSON already carries, never
from mtime. A rebase or checkout moves mtimes without changing cited content,
so mtime is the wrong key here.

  pinned = diagram["meta"]["repository"]["revision"]
  now   = git rev-parse HEAD
  if pinned == now: nothing necessary
  else: changed = git diff --name-only <pin>..HEAD -- <each sources[].path>

Scope the diff to cited paths rather than to HEAD. The pin is *supposed* to
lag behind HEAD — every commit that only touches docs or diagrams moves HEAD
without making the diagram false. Diffing the whole tree would re-derive on
every commit.

Scope is a trigger, not a verdict. It names files that moved, not files that
are wrong. A node whose cited file changed may still be correct, and
re-deriving it when it isn't is the safe failure mode.

A diagram with zero source anchors has no mechanical staleness test at all.
That is reported, not papered over.

Exit codes reuse the executor's convention (executor.py:59-60), because those
codes carry meaning the executor already acts on. A private numbering makes
every non-zero exit read as a phase failure, which is the opposite of what a
gate reports.

  0  up to date, nothing necessary
  2  cannot evaluate — no git in this environment, no pinned revision, or the
     pinned revision is not in this history. NOT used for a malformed diagram:
     that is a broken input, and reusing the code here would make it read as
     "could not check" rather than as a defect.
  3  findings — a cited path moved. The executor scores this as success and
     records it without advancing the breaker, which is what "something needs
     re-deriving" actually is.
"""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIAGRAM = REPO_ROOT / "diagrams" / "active-usage-architecture.json"
REPORT = REPO_ROOT / ".omp" / "theteam" / "reports" / "update-team.md"

# The executor's exit-code convention (executor.py:59-60). Reusing it is what
# makes a findings result read as findings instead of a failed phase: it sets
# `success: True` and records the fact without advancing the breaker.
OK = 0
CANNOT_EVALUATE = 2
FINDINGS = 3


def _git(*args: str) -> str:
    """Run git in the repo, or return "" when git cannot be run at all.

    The binary is genuinely absent from the phase container image — measured,
    not assumed: `docker run python:3.12-slim git --version` is not found, so
    `subprocess.run` raises FileNotFoundError and an unguarded call would crash
    the phase instead of reporting that it could not check.
    """
    try:
        return subprocess.run(
            ["git", "-C", str(REPO_ROOT), *args],
            capture_output=True, text=True,
        ).stdout.strip()
    except (FileNotFoundError, OSError):
        return ""


def _cited_paths(diagram: dict) -> list[str]:
    return sorted({
        s["path"]
        for c in diagram.get("components", [])
        for s in c.get("sources", [])
    })


def _nearest_symbol(path: str, line: int) -> str | None:
    """The nearest def/class at or before `line`, for the report only."""
    if not (REPO_ROOT / path).exists():
        return None
    out = subprocess.run(
        ["bash", "-c", f'grep -nE "^(def|class) " {path}'],
        cwd=REPO_ROOT, capture_output=True, text=True,
    ).stdout.strip().splitlines()
    best = None
    for entry in out:
        n = int(entry.split(":", 1)[0])
        if n <= line and (best is None or n > best[0]):
            best = (n, entry.split(":", 1)[1])
    return best[1] if best else None


def main() -> int:
    try:
        diagram = json.loads(DIAGRAM.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"[update-team] cannot evaluate: invalid diagram: {e}")
        return CANNOT_EVALUATE

    pinned = diagram.get("meta", {}).get("repository", {}).get("revision")
    if not pinned:
        print("[update-team] cannot evaluate: diagram carries no pinned "
              "revision, so there is no mechanical staleness test")
        return CANNOT_EVALUATE

    cited = _cited_paths(diagram)
    anchors = sum(len(c.get("sources", [])) for c in diagram.get("components", []))

    now = _git("rev-parse", "HEAD")
    if not now:
        print("[update-team] cannot evaluate: git is unavailable here")
        return CANNOT_EVALUATE

    # The pinned revision must still be reachable. If it isn't the diagram was
    # derived from a commit that is no longer in history, and the diff below
    # would be meaningless.
    if pinned not in _git("log", "--format=%H"):
        print(f"[update-team] cannot evaluate: pinned revision {pinned[:8]} "
              f"is not in this history")
        return CANNOT_EVALUATE

    if pinned == now:
        verdict = "nothing necessary"
        exit_code = OK
        changed = ""
    else:
        changed = _git("diff", "--name-only", f"{pinned}..HEAD", "--", *cited)
        verdict = "re-derive needed" if changed else "diagram still true"
        exit_code = FINDINGS if changed else OK

    lines = [
        "# update-team — step 0, staleness",
        "",
        f"- **pinned revision:** `{pinned}`",
        f"- **HEAD now:** `{now}`",
        f"- **verdict:** {verdict}",
        f"- **exit code:** {exit_code}",
        f"- **source anchors:** {anchors} across {len(cited)} distinct cited paths",
        "",
    ]
    if exit_code == FINDINGS:
        lines += ["## Cited paths that moved", ""]
        for path in changed.split():
            sym = _nearest_symbol(path, next(
                s["line"] for c in diagram.get("components", [])
                for s in c.get("sources", []) if s["path"] == path
            ))
            lines.append(f"- `{path}`" + (f" — nearest symbol: `{sym}`" if sym else ""))
        lines += ["", "Re-derive the nodes citing these paths, then re-run step 4."]
    else:
        lines += ["No cited path has moved since the diagram was derived, so the "
                  "diagram is still true. Steps 1–4 remain manual: archify and the "
                  "production skill live outside the project mount, and editing "
                  "existing files has no output signal for the llm completion rule."]

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
