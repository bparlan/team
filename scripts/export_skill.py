#!/usr/bin/env python3
"""
Export the theteam skill from the development tree to the production install.

## Why this exists

`theteam/` in this repository is the development tree. The copy OMP actually
loads lives at `~/.omp/agent/skills/theteam/`. They are separate directories on
separate timelines, and the gap between them is where the bugs live: two
`SKILL.md` files had already drifted into different path styles, and the
production tree was missing `bin/utilities.py` and `bin/__init__.py` entirely —
which is precisely what `theteam/bin/theteam_config.py:19` imports.

Manual copying is how that drift accumulates. Copying a whole directory is
worse: it would ship `subskills/`, `ANALYSIS.md`, `test_theteam.py` and the
`.backup` files, none of which the production skill needs.

So this copies an explicit **manifest** of six files, rewrites the paths inside
`SKILL.md`, and then verifies.

## What it does, in order

1. **Gates on the test suite.** An export of a broken tree produces a broken
   production skill, and the failure surfaces later, in a different directory,
   with no obvious cause. Abort non-zero if the suite fails.
2. **Copies** the manifest, creating `bin/` as needed.
3. **Rewrites** repo-relative `theteam/bin/...` paths in `SKILL.md` to the
   absolute production form. Without this the two files diverge on every sync,
   which is how they diverged in the first place.
4. **Prunes** `__pycache__` and `*.backup` — build noise, safe to remove.
5. **Reports** every production file outside the manifest, and does **not**
   delete any of them. They may be live (`subskills/`), and removing something
   this script did not create is not its call to make.
6. **Verifies** — each manifest path exists and its content matches the source
   after rewriting — and exits non-zero listing anything that does not.

## What it is not

Not a daemon, not a watcher, not a two-way sync. It is one command that copies
a known list and proves the copy is right. Git remains the source of truth for
history; this is a deployment step, not a version-control step — it does not
commit and it does not push.
"""

import filecmp
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PRODUCTION = Path.home() / ".omp" / "agent" / "skills" / "theteam"

#: The files the production skill actually needs. Deliberately explicit: a
#: mirror would ship development-only files, and a manifest that drifts is a
#: manifest someone has to remember to update.
MANIFEST = (
    "SKILL.md",
    "theteam-template.config",
    "bin/theteam_config.py",
    "bin/theteam_report.py",
    "bin/utilities.py",
    "bin/__init__.py",
)

#: Where each manifest entry comes from. `bin/theteam_report.py` lives at the
#: repo root because ARCHITECTURE.md:558 records that M10 *moved* it there
#: rather than deleting it, and two runtime callers resolve against that path
#: (`theteam/__init__.py:936` and `scripts/loop_infrastructure_check.py:30`).
#: `bin/utilities.py` and `bin/__init__.py` live under `theteam/bin/`, which is
#: where `from bin.utilities import _fatal` resolves them from.
SOURCES = {
    "SKILL.md": "theteam/SKILL.md",
    "theteam-template.config": "theteam/theteam-template.config",
    "bin/theteam_config.py": "theteam/bin/theteam_config.py",
    "bin/theteam_report.py": "bin/theteam_report.py",
    "bin/utilities.py": "theteam/bin/utilities.py",
    "bin/__init__.py": "theteam/bin/__init__.py",
}

#: Build noise and editor leftovers. Safe to remove: none is source.
PRUNE_SUFFIXES = (".backup", ".pyc")
PRUNE_DIRS = ("__pycache__",)


def log(message: str) -> None:
    print(f"[export] {message}", flush=True)


def run_suite() -> bool:
    """The gate. A failing suite must not produce a production install."""
    log("running the test suite (gate)")
    # test_skill_export.py is deselected: it asserts the installed copy matches
    # the repo, and this script is the thing that makes them match. Gating the
    # resync on its own precondition means a pending resync can never be
    # performed -- the only fix is the command that is being blocked. It still
    # runs in the normal suite, where it is the check that matters.
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "theteam/tests/", "-q",
         "--deselect", "theteam/tests/test_skill_export.py"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    tail = [line for line in result.stdout.strip().splitlines() if line.strip()]
    if tail:
        log(f"suite: {tail[-1]}")
    if result.returncode != 0:
        log("SUITE FAILED — refusing to export")
        return False
    return True


def rewrite_paths(text: str) -> str:
    """Repo-relative paths in `SKILL.md` become absolute production paths.

    Only the two forms the repo copy actually uses are rewritten, so a document
    that merely mentions a path in prose is not silently changed.
    """
    text = text.replace(
        "PYTHONPATH=theteam python3 theteam/bin/",
        f"python3 {PRODUCTION}/bin/",
    )
    text = re.sub(
        r"(?<![\w/~.])theteam/bin/(theteam_config\.py|theteam_report\.py|utilities\.py)",
        rf"{PRODUCTION}/bin/\1",
        text,
    )
    return text


def copy_manifest() -> list:
    """Copy every manifest entry, rewriting `SKILL.md` on the way."""
    copied = []
    for target_rel, source_rel in SOURCES.items():
        source = REPO_ROOT / source_rel
        if not source.exists():
            raise SystemExit(f"[export] FATAL: manifest source missing: {source_rel}")

        target = PRODUCTION / target_rel
        target.parent.mkdir(parents=True, exist_ok=True)

        if target_rel == "SKILL.md":
            target.write_text(rewrite_paths(source.read_text(encoding="utf-8")),
                              encoding="utf-8")
        else:
            shutil.copy2(source, target)
        copied.append(target_rel)
        log(f"copied {source_rel} -> {target_rel}")
    return copied


def prune() -> list:
    """Remove build noise. Never touches a source file.

    Directories are pruned before files, and each directory is deleted without
    descending into it afterwards. Walking top-down while deleting is how the
    first version of this function raised `FileNotFoundError`: `rglob` had
    already collected the `.pyc` files inside a `__pycache__` that `rmtree`
    then removed, so the loop tried to unlink paths that no longer existed.
    """
    removed = []
    for directory in sorted((p for p in PRODUCTION.rglob("*") if p.is_dir()),
                            key=lambda p: len(p.parts), reverse=True):
        if directory.name in PRUNE_DIRS:
            shutil.rmtree(directory)
            removed.append(str(directory.relative_to(PRODUCTION)))

    for path in sorted(PRODUCTION.rglob("*")):
        if path.is_file() and path.name.endswith(PRUNE_SUFFIXES):
            path.unlink()
            removed.append(str(path.relative_to(PRODUCTION)))

    for item in sorted(set(removed)):
        log(f"pruned {item}")
    return removed


def report_extras(manifest: tuple) -> list:
    """Production files outside the manifest. Reported, never deleted."""
    expected = set(manifest)
    extras = []
    for path in sorted(PRODUCTION.rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(PRODUCTION))
        if relative in expected or relative in PRUNE_SUFFIXES:
            continue
        if any(part in PRUNE_DIRS for part in path.relative_to(PRODUCTION).parts):
            continue
        extras.append(relative)
    if extras:
        log("production files NOT in the manifest (left alone):")
        for item in extras:
            log(f"  - {item}")
    else:
        log("no production files outside the manifest")
    return extras


def verify(manifest: tuple) -> bool:
    """Prove the copy is right. Any mismatch is a failure, not a warning."""
    problems = []
    for target_rel, source_rel in SOURCES.items():
        target = PRODUCTION / target_rel
        if not target.exists():
            problems.append(f"{target_rel}: missing")
            continue
        source = REPO_ROOT / source_rel
        if target_rel == "SKILL.md":
            expected = rewrite_paths(source.read_text(encoding="utf-8"))
            if target.read_text(encoding="utf-8") != expected:
                problems.append("SKILL.md: content differs after rewrite")
        elif not filecmp.cmp(str(source), str(target), shallow=False):
            problems.append(f"{target_rel}: differs from source")

    if problems:
        log("VERIFY FAILED:")
        for problem in problems:
            log(f"  - {problem}")
        return False

    log(f"verified {len(manifest)} manifest files")
    return True


def verify_runs() -> bool:
    """Prove the exported skill actually runs, from a directory it does not own.

    A byte-comparison cannot catch this class of failure. The first version of
    this script verified all six files as identical and shipped a skill that
    raised `ModuleNotFoundError: No module named 'bin'` on every invocation,
    because `theteam_config.py` imports a sibling module and the production
    layout does not put the parent directory on `sys.path`.

    So the copied scripts are executed, from a neutral working directory, the
    way the skill will actually be invoked.
    """
    config = REPO_ROOT / "theteam.config"
    checks = (
        ([sys.executable, str(PRODUCTION / "bin/theteam_config.py"),
          "validate", str(config)], "theteam_config.py validate"),
        ([sys.executable, str(PRODUCTION / "bin/theteam_config.py"),
          "roster", str(config)], "theteam_config.py roster"),
    )

    # `theteam_report.py` is checked by importability, not by invocation: both
    # `--help` and a bare `build` exit 1 after printing usage, so neither can
    # distinguish a working script from a broken one. Compiling it proves the
    # module parses where it landed, which is the failure this check exists for.
    checks = checks + ((
        [sys.executable, "-m", "py_compile",
         str(PRODUCTION / "bin/theteam_report.py")],
        "theteam_report.py compiles",
    ),)
    failures = []
    for command, label in checks:
        result = subprocess.run(command, cwd="/", capture_output=True, text=True)
        if result.returncode != 0:
            failures.append(f"{label}: exit {result.returncode} — "
                            f"{(result.stderr.strip().splitlines() or ['?'])[-1]}")
        else:
            log(f"runs: {label}")

    if failures:
        log("EXPORTED SKILL DOES NOT RUN:")
        for failure in failures:
            log(f"  - {failure}")
        return False
    return True


def report_git() -> None:
    """Repository state, for the human to act on. This script never pushes."""
    def git(*args):
        return subprocess.run(["git", *args], cwd=str(REPO_ROOT),
                              capture_output=True, text=True).stdout.strip()

    status = git("status", "--porcelain")
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    log(f"git branch: {branch or '(unknown)'}")
    if status:
        dirty = len(status.splitlines())
        log(f"git: {dirty} uncommitted change(s) — review before pushing")
    else:
        log("git: working tree clean")
    upstream_name = git("rev-parse", "--abbrev-ref", "@{u}")
    counts = git("rev-list", "--left-right", "--count", "@{u}...HEAD")
    if counts:
        behind, ahead = counts.split()
        log(f"git: {ahead} ahead, {behind} behind {upstream_name or '(no upstream)'}")


def main() -> int:
    # Why this is NOT registered as a `script:` task.
    #
    # A `script:` phase runs inside a container that bind-mounts the project
    # and nothing else, so `~/.omp/agent/skills/theteam/` does not exist in
    # there. An override env var was tried and removed: pointed at a path the
    # container CAN see, it would export six files into the container's own
    # throwaway filesystem and report "export complete" — a green run that
    # changed nothing on the host. That is strictly worse than failing.
    #
    # So the destination stays a module constant and the script is invoked
    # directly, from the host, where the production directory actually is:
    #
    #     python3 scripts/export_skill.py
    #
    # `theteam run --only export-skill` is refused by name, because a task that
    # cannot do its work should say so rather than appear to.
    if not PRODUCTION.exists():
        raise SystemExit(
            f"[export] FATAL: production skill directory not found: {PRODUCTION}")

    log(f"source:      {REPO_ROOT / 'theteam'}")
    log(f"destination: {PRODUCTION}")

    if not run_suite():
        return 1

    copy_manifest()
    prune()
    report_extras(MANIFEST)

    if not verify(MANIFEST):
        return 1

    # Byte-identical is not the same as runnable. The first version of this
    # script stopped here and shipped a skill that raised
    # `ModuleNotFoundError` on every call.
    if not verify_runs():
        return 1

    log("export complete")
    report_git()
    return 0


if __name__ == "__main__":
    sys.exit(main())
