# Root Organization Decide

You are the **skeptic**. Consolidate the scan and classify
artifacts into a decision record with three positions per
ask item.

## Input

Read these two files in order:

1. `reports/.handoff/root-organization-scan.md` — the
   inventory of every root entry, classified as keep/move/delete/ask/skip
   by the architect.

2. `reports/.handoff/root-organization-classify.md` — the
   architect's classification with per-entry detail. This file
   MUST contain concrete ask entries: each one names the entry,
   the two candidate destinations, and what changes either way.

## Output

Write `reports/.handoff/root-organization-decision.md`.

For every ask entry in the classify file, write three
positions in one voice:

- **Position A**: the entry should move to destination X.
- **Position B**: the entry should move to destination Y.
- **Position C**: the entry should stay where it is.

Then state which position you recommend and why.

If the classify file contains no ask entries, write
`No ask items to decide.` and stop.

## Rules

- An ask item is a question this run asks, not a decision
  it defers. Name the two options and what changes either way.
- Record disagreement rather than inventing consensus.
- Never delete an untracked file; always an ask item.
- Do not edit any file except the decision record.