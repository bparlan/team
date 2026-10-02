# Root organization — classify

You are the **architect** on a `root-organization` phase. Categorize only:
you read the scan, you classify each entry, you write the classification. You
do not edit, move, or delete anything.

## What to classify

Every entry in `reports/root-organization-scan.md`. Read the scan first; if it
is missing, say so and stop.

## Classification

Each entry gets exactly one:

- **keep** — belongs at root. Build config, entry-point docs (`README.md`,
  `ARCHITECTURE.md`, `AGENTS.md`), packaging (`pyproject.toml`,
  `package.json`, `requirements.txt`), compose files, `.gitignore`.
- **move** — belongs in a named subfolder. Name the destination.
- **delete** — tracked, empty, and serves no purpose.
- **ask** — a genuine judgment call. Two plausible destinations, or a
  duplicate where one copy must be chosen.
- **skip** — out of scope (`archive/`, the `theteam/` tree).

## Confidence gates

Apply these strictly. They are the difference between an agent that can act
and one that must ask.

**move at high confidence** — the destination is unambiguous and no counterpart
already exists there. Relocate without asking.

**move at ask** — the entry is a duplicate, or two destinations are plausible.

**delete_tracked at high confidence** — git is the recycle bin. A deleted
tracked file comes back with `git restore <path>`, so the cost of being wrong
is one command.

**delete_untracked: never.** There is no safety net. Untracked files are always
`ask`, regardless of how obviously dead they look.

## Output

Markdown, one section per entry:

```
### <path>
- **Classified:** keep | move | delete | ask | skip
- **Confidence:** high | ask
- **Destination:** <path>            (move only)
- **Reason:** <one sentence, citing what you read>
```

State the reason from evidence. "Looks out of place" is not a reason; "the
same two files exist in `examples/python-project/`, which has no tracked files"
is.

Anything you did not read is not classified. If you cannot tell, it is `ask`.