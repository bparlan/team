# Prompt 5 – Two CLI gaps

## Baseline (verified)
- `theteam/cli.py:305` – `comment`, `task`, `history` appear in the
  help but have no description.
- `theteam bootstrap --project-root /tmp/x` fails (positional `path`
  already consumes the argument).

## Target
1. Add a `help=` string to the three pending subparsers, taken from
   the §2 table in `ARCHITECTURE.md`.
2. Add `--project-root` to each subparser (as a positional‑agnostic
   flag) so it can appear before or after the subcommand.

## Acceptance
1. `theteam --help` lists all 10 commands with descriptions.
2. `theteam bootstrap --project-root /tmp/x --json` exits 0.
3. `theteam --json status` and `theteam status --json` remain byte‑identical.
4. All tests pass.

## Skills
- `/caveman-commit` – for the commit message.

## Commit
- One commit, e.g.
  `docs: add help to pending CLI commands and make --project-root positional‑agnostic`.