#!/usr/bin/env python3
"""Exercise every theteam subcommand against a throwaway project.

A guide is only useful if the commands in it are real. This runs each one and
reports what came back, so a flag that was renamed or dropped fails here
instead of in someone's terminal.

Read-only against the repo: it builds its own project under a temp dir and
never touches `.omp/`. Tasks that need Docker or an LLM provider refuse by
name, and a refusal that names itself is the pass condition — §3.3. A command
that exits non-zero *silently* is the failure this exists to catch.

    python3 scripts/smoke_cli.py            # human-readable
    python3 scripts/smoke_cli.py --json     # machine-readable

Exit 0 when every command behaved. Exit 1 otherwise.
"""
import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLI = [sys.executable, "-m", "theteam.cli"]

def run(root, *args, expect_json=False):
    """Run one CLI invocation. Returns (ok, detail).

    `--project-root` goes BEFORE the subcommand: measured, it is rejected after
    it (CLI.md records this). `--json` works either way.
    """
    proc = subprocess.run(
        CLI + ["--project-root", str(root)] + list(args),
        capture_output=True, text=True, cwd=str(REPO), timeout=180,
    )
    out = (proc.stdout + proc.stderr).strip()
    detail = out.splitlines()[0][:120] if out else "(no output)"

    # argparse's usage dump is a bug in the caller, never a product refusal.
    if "unrecognized arguments" in out or out.startswith("usage:"):
        return False, f"BAD INVOCATION: {detail}"

    # A non-zero exit is legitimate only when the command named its reason.
    # The JSON envelope already carries that (`ok: false` + `reason`/`error`),
    # so read it structurally. An earlier version keyword-matched English and
    # counted 23 argparse usage dumps as passes, because the usage text
    # contained the word "error".
    if proc.returncode != 0:
        if not expect_json:
            # `discuss` needs a live OMP session and says so in plain text;
            # there is no envelope to read. Outside OMP this refusal is correct.
            if "requires an OMP session" in out:
                return True, "named refusal: needs a live OMP session"
            return False, f"exit {proc.returncode} with no named reason: {detail}"
        try:
            payload = json.loads(out)
        except json.JSONDecodeError:
            return False, f"exit {proc.returncode}, and output is not JSON: {detail}"
        if payload.get("ok") is False and (payload.get("reason") or payload.get("error")):
            return True, f"named refusal: {payload.get('reason') or payload.get('error')}"
        return False, f"exit {proc.returncode} with no named reason: {detail}"

    if expect_json:
        try:
            json.loads(out)
        except json.JSONDecodeError as e:
            return False, f"claimed --json but did not parse: {e}"
    return True, detail


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--keep", action="store_true",
                    help="keep the temp project for inspection")
    args = ap.parse_args()

    root = Path(tempfile.mkdtemp(prefix="theteam-smoke-"))
    try:
        # Everything below is copied from `--help` output, not from memory:
        # `theteam task edit` takes `--patch FILE` (not `--set`), `task create`
        # takes `--path FILE` (not a positional), `task delete` needs `--yes`,
        # and `loop` takes `--interval MINUTES`.
        checks = [
            ("status --json", ["--json", "status"], True),
            ("tasks --json", ["--json", "tasks"], True),
            ("history --json", ["--json", "history"], True),
            ("history --task", ["--json", "history", "--task", "no-such-task"], True),
            ("manager --status", ["--json", "manager", "--status"], True),
            ("run --dry-run", ["--json", "run", "--dry-run"], True),
            ("run", ["--json", "run"], False),
            ("run --only unknown", ["--json", "run", "--only", "no-such-task"], True),
            ("watch status --once", ["watch", "status", "--once"], False),
            ("watch tasks --once --json", ["watch", "tasks", "--once", "--json"], True),
            ("watch history --once --monitor", ["watch", "history", "--once", "--monitor"], False),
            ("comment status", ["comment", "status"], False),
            ("comment on", ["comment", "on"], False),
            ("comment off", ["comment", "off"], False),
            ("task show missing", ["--json", "task", "show", "no-such-task"], True),
            ("task delete missing", ["--json", "task", "delete", "no-such-task"], True),
            ("task create missing file", ["--json", "task", "create", "--path", "nope.yaml"], True),
            ("task edit missing file", ["--json", "task", "edit", "no-such-task", "--patch", "nope.yaml"], True),
            ("loop unknown task", ["--json", "loop", "no-such-task"], True),
            ("loop --interval", ["--json", "loop", "no-such-task", "--interval", "30"], True),
            ("discuss", ["discuss", "verify the CLI surface"], False),
            ("manager --topic", ["--json", "manager", "--topic", "verify the CLI surface"], False),
        ]

        # bootstrap writes `theteam.config`, so it runs into its own directory
        # first; everything after it needs that config to exist.
        ok, detail = run(root, "bootstrap")
        results = [{"check": "bootstrap", "ok": ok, "detail": detail}]

        for label, argv, expect_json in checks:
            ok, detail = run(root, *argv, expect_json=expect_json)
            results.append({"check": label, "ok": ok, "detail": detail})
            if not args.json:
                print(f"{'PASS' if ok else 'FAIL'}  {label:<28} {detail}")

        failed = [r for r in results if not r["ok"]]
        if args.json:
            print(json.dumps({
                "passed": len(results) - len(failed),
                "failed": len(failed),
                "results": results,
            }, indent=2))
        else:
            print(f"\n{len(results) - len(failed)}/{len(results)} passed")
            if failed:
                print("failed: " + ", ".join(r["check"] for r in failed))

        return 1 if failed else 0
    finally:
        if args.keep:
            print(f"\nproject kept at {root}")
        else:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
