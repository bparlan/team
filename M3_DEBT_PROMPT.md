# OMP Prompt — M0–M3 debt cleanup, before M4

Fresh OMP session at `/Users/bparlan/devcode/team`.

**Mode: ponytail full + caveman full.** Ponytail governs the code (smallest change that
works, no unrequested scope). Caveman governs the prose (terse, no filler). Run both.

This is 3 small items, not a milestone. Baseline is 625 passing. Goal: enter M4 with no
debt from M0–M3 and a gate that stops new debt.

---

## PROMPT START

Clear M0–M3 debt so M4 starts clean. Three items. One commit each, or one commit total
if they land in a single pass.

Read: `AGENTS.md`, `ARCHITECTURE.md` §3.3 and §7.2. Nothing else needed.

Baseline first:

```bash
cd /Users/bparlan/devcode/team
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5
```

Expect 625. Different? Stop, report, do not edit.

---

### F1 — false error message

`theteam/tasks/repository.py:321` and `:373` raise:

```python
KeyError(f"Task '{task_id}' not found or is legacy-only")
```

No legacy registry. M2 deleted it as source. Cause cannot be true. Live:

```
$ theteam task delete nope --yes
theteam task: "Task 'nope' not found or is legacy-only"
```

Drop `or is legacy-only` from both sites.

Second half: `str(KeyError("x"))` returns `"'x'"` — user sees message wrapped in quotes
(`theteam task: "Task 'nope'..."`). Catch `KeyError` in `cli.py`'s handler, print
`exc.args[0]` not `str(exc)`. Same for `ValueError` if it leaks a repr.

Add one test: deleting an unknown id reports a message naming only the id, no
`legacy-only`, no wrapping quotes. Fails before, passes after.

---

### A1 — ARCHITECTURE.md §5.2 describes a tree that no longer exists

Line 283: `ui/  # dashboard, reads through state.py`

That names the dead `web_dashboard`; and "state.py" collides with the real resolver
`theteam/state.py`. M3 also converted order to a per-task key, so §5.2's `tasks/` block
(`schema.py`, `scheduler.py` "gains unschedule") overstates what exists.

Fix §5.2 to match the tree. Rule: the doc is source of truth, so when code moves, the
doc moves with it. Check every path in §5.2 exists; delete or correct the ones that do not.
Run:

```bash
cd /Users/bparlan/devcode/team
grep -oE '^\s+[a-z_]+\.py' ARCHITECTURE.md | tr -d ' ' | sort -u | while read f; do
  found=$(find theteam -name "$(basename $f)" 2>/dev/null | head -1)
  [ -z "$found" ] && echo "MISSING: $f"
done
```

No code change. Doc only.

---

### A2 — the §7.2 invariants are enforced nowhere

Six greppable invariants. All pass now except the one M4 fixes. Nothing runs them. That
is why the dead dashboard survived three milestones: §3.3's compliance test — "grep the
tree for functions that return a plausible-looking value on a failure path" — was never
run against `ui/`.

Add `.github/workflows/ci.yml` step, or a `scripts/check_invariants.sh` the workflow
calls. Six checks, exit 1 on any failure:

| # | Check | Expected today |
|---|---|---|
| 1 | `grep -rl "CircuitBreaker\|ResourceLimiter\|AgentIsolation\|AuditLogger" theteam/tasks/` | **FAILS** — M4 fixes it. Exempt with a `# TODO(M4)` comment, not by deleting the check. |
| 2 | every `subprocess` site in `theteam/tasks/executor.py` inside a Layer 4 guard | **FAILS** — M4 fixes it. Same exemption. |
| 3 | `grep -rn "/Users/bparlan" theteam/ --include="*.py"` | empty |
| 4 | `grep -rn "parents\[" theteam/ --include="*.py"` | empty |
| 5 | `grep -rn "\.mp/theteam" theteam/ --include="*.py"` | only the `DEAD_DIR` guard + its test |
| 6 | `grep -rn "MockAPI" theteam/ --include="*.py"` | empty |

Checks 1 and 2 are M4's falsification tests. The gate is valuable precisely because it
fails now and stops failing when M4 lands. Print which check failed, name the milestone
that owns it.

Look at the existing `ci.yml` first — match its style, do not add a second workflow.

---

### Verify

```bash
cd /Users/bparlan/devcode/team
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5   # no regression
python3 -m theteam.cli --project-root . task delete nope --yes    # no "legacy-only", no quotes
bash scripts/check_invariants.sh 2>&1 || echo "exit=$? — check 1 and 2 are M4's, expected"
python3 -c "import theteam; print('IMPORT OK')"
```

No regression from 625. Do not delete a test to reach a number. If the count moves,
account for every difference by name.

---

### Constraints

- **Three items. No more.** No UI work, no deletions, no safety wiring — those are M4's
  section D and S1–S4.
- **No new `*.md` files.** A2 adds a shell script and/or a CI step, not a document.
- Smallest diff. A1 is doc text. F1 is two strings plus one exception handler plus one test.
  A2 is one script. Nothing here needs an abstraction.
- Do not fix a test to make broken code pass.
- One runnable check per item. F1 has its test; A2 is itself a check; A1 needs none.

---

### Delegation

Do this inline. Three items, one file between them, under 40 lines of real change. `task`
subagents cost more than the work.

Use `todo` if the three do not land in one pass: `F1`, `A1`, `A2`. Mark done with output.
Never yield `in_progress`.

---

### Deliverable

One commit. Summary 3 lines max (`AGENTS.md`), then: the test count, the exact output of
`task delete nope --yes`, and the output of `scripts/check_invariants.sh` including which
checks failed and why that is expected.

If A2 turns out to need more than a script, stop and report rather than designing a
framework. A gate is worth only what its simplest honest form is worth.
