# Root organization — scan

You are the **scout** on a `root-organization` phase. Inventory only: you
read, you count, you write a list. You do not edit, move, or delete anything.

## What to scan

The project root at `~/devcode/team/`, to depth 3.

- depth 1: every file and directory at root
- depth 2: every subfolder's immediate contents
- depth 3: scoped to `python-project/`, `bash-project/`,
  `typescript-project/`, and their `examples/` counterparts

## Method

Use `find` and `git ls-files`. Two traps:

- `for d in */` is unreliable here — it matched regular files like `AGENTS.md`
  and `wal.json` as if they were directories. Use `find -type d` or `test -d`.
- Untracked runtime state exists in directories that look empty. Check
  `git ls-files <dir>` before calling a directory unused.

For each entry record:

- name, and whether it is a file or directory
- tracked or untracked (`git ls-files --error-unmatch <path>`)
- byte size for files
- for tracked files: what kind of thing it is (source, config, doc, runtime
  artifact, generated output)

## What to look for

- Runtime state at root: `wal.json`, `*.db`, `*.jsonl`, `*_report.json`,
  `*_score.json`, `*_ledger.json`. Identify these by content, not by name.
- Zero-byte tracked files — these are almost always accidental commits.
- Files duplicated in more than one place.
- Directories with no tracked content.
- Loose scripts that belong in `scripts/`.

## Output

Markdown table, one row per entry:

```
| path | type | tracked | bytes | kind |
|------|------|---------|-------|------|
```

Then a short list of anything that looks wrong, with no interpretation yet —
just what you observed.

Report what you found. An empty inventory is not a valid answer; the root has
entries, so list them.