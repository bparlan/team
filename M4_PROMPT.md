# OMP Prompt — Milestone M4: The loop is safe

Fresh OMP session at `/Users/bparlan/devcode/team`. Advisor mode ON; the advisor is
read-only (`read`, `grep`, `glob`) and cannot execute — you supply the evidence.

---

## PROMPT START

**Milestone M4** of `theteam`. M0–M3 done and committed. Task store is YAML-only,
`subskills/task_stack/` is gone, `theteam run` is `{ran:0}`.

M4 wires the safety layer. Four components exist, are tested, and have **no caller** —
`grep -rl "CircuitBreaker\|ResourceLimiter\|AgentIsolation\|AuditLogger" theteam/tasks/`
returns nothing. This milestone is adding the call sites. Do not rewrite the components.

**Read:** `ARCHITECTURE.md` §3.3, §5.1, §5.2, M4 in Part 6, §7.1 (1, 5–7), §7.2 (1, 2, 8).
Then `theteam/tasks/executor.py` in full — it is small and it is what you change.
Then the four components in `theteam/core/`, and their existing tests.

**Baseline before any edit:**

```bash
cd /Users/bparlan/devcode/team
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5
```

Record the number. If it is not 625, stop and report before editing.

---

### S1 — `CircuitBreaker` into task execution

Per-task breaker on consecutive failures. §7.1.5: five consecutive failures trips it and
the task stops burning cycles. Visible in `theteam tasks` **and** `theteam history`.

`repository.py` `_row()` already emits `breaker` defaulting to `"closed"`. That is a
fabricated default — §3.3. Wire it to real breaker state or delete the field. Same rule
for any breaker/health value you surface: from a real component, never a literal.

### S2 — `ResourceLimiter` and `AgentIsolation` into phase execution

Every phase has a mandatory `memory_limit_mb` (§5.4). Exceeding it kills the phase and
reports it. §7.1.6. The kill must be observable: exit 137, named in the result.

### S3 — `AuditLogger` into the task lifecycle

Every create, edit, delete, execution appends to the hash chain. `theteam status`
verifies it. §7.1.1.

### S4 — bound the execution log

`.omp/theteam/task-execution.log` is ~275 KB and unbounded. Apply `ResourceLimiter`'s
retention policy.

### The invariant

`ARCHITECTURE.md` §5.1, stated as non-negotiable:

> Layer 3 may not call `subprocess` without a Layer 4 guard in the same call frame.

`AgentIsolation` was built for this and never got a caller. That is the whole milestone.

```bash
grep -n "subprocess" theteam/tasks/executor.py                      # every site guarded
grep -rl "CircuitBreaker\|ResourceLimiter\|AgentIsolation\|AuditLogger" theteam/tasks/  # non-empty
```

### `theteam history` and `theteam status`

`history` refuses with "not implemented yet (M4)". Per-task success rate, last run, last
failure, consecutive failures (§7.1.7). It reads S1's and S3's state — build those first.

`status`: the trust surface (§3.1). The audit check is stubbed at `cli.py:106` with
`"reason": "chain verification lands with the M4 audit wiring"`. Land it. A field reading
`intact` without a check behind it is `MockAPI` with a friendlier name.

---

### Verify

```bash
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5     # no regression
python3 -m theteam.cli --project-root . run --json                 # {ran:0}, twice, identical
python3 -m theteam.cli --project-root . status --json | head -40   # audit chain verified
python3 -m theteam.cli --project-root . history --json | head -20
grep -rn "MockAPI" theteam/ --include="*.py"                       # empty
```

`run` twice identical is the check that catches a silent regression. §6's ordering rule
holds at every commit: all four tasks still execute.

Falsification, all four:

1. Five consecutive failures trip a breaker — paste output from **both** `tasks` and `history`.
2. A phase over `memory_limit_mb` is killed at exit 137 and reported — paste exit code and result line.
3. Every task mutation is in the audit chain and `status` verifies it.
4. `history` shows success rate, last run, last failure, consecutive failures.

---

### Constraints

- **M4 only.** No `advisory/`, no `comment` (M5), no UI work of any kind.
- **No new `*.md` files.** `ARCHITECTURE.md` is the plan.
- **No orphan files, and no references to deleted modules** — a grep returning a deleted path is a broken import waiting to fire.
- **Do not rewrite the four components.** Tested and correct; you are adding callers. If one cannot be called as-is, say so and stop.
- **Do not fabricate a safety value.** `stack_health: "healthy"` — a hardcoded literal in `task_stack_adapter.py` — is the shape of the defect to avoid.
- **Do not fix a test to make broken code pass.** Decide which side is wrong, say which and why.
- Run the suite after every sub-task.

---

### D — cleanup. **Do this last, in its own commit.**

Deletions go last so a crash leaves a recoverable tree. Git history is the archive —
every target below is committed, so **do not move anything to `archive/`**.

Verify the premise before deleting — these are claims, so check them:

```bash
python3 -c "import theteam.ui.terminal_ui" 2>&1 | tail -2   # IndentationError at line 46
grep -c rich requirements.txt                               # 0 — undeclared dependency
grep -n "task-registry" theteam/ui/web_dashboard/theteam_dashboard/state.py   # M2-deleted source
grep -n "stack_health" theteam/ui/task_stack_adapter.py      # hardcoded "healthy"
```

**D1.** `rm -r theteam/ui/web_dashboard/` (69 tracked files). `state.py:78` reads
`task-registry.json`, deleted as a source in M2, and `task-stack-daemon.json`, whose
daemon M2.3 deleted — that file still reports `{"running": true}` for a task retired in
`bb97b45`. It renders dead state as live. §3.3.

**D2.** `rm theteam/ui/terminal_ui.py`. Does not parse, imports undeclared `rich`, no CLI
path reaches it, no test covers it.

**D3.** `rm theteam/ui/task_stack_adapter.py`. Its `"stack_health": "healthy"` is
unconditional, and it still reads `state.task_daemon_status` (line 97) — a daemon M2.3
deleted.

**Keep — do not delete these two:**

- `theteam/ui/components/reflex_renderers.py`. Reflex is not installed and has no
  milestone, but this file is why `import theteam` works with zero dependencies. It is the
  seam. Inert and worth keeping.
- `theteam/tests/test_reflex_renderers.py`. `TestViewModelsAreReflexFree` is the CI gate
  proving the view models import no Reflex, and it runs *because* Reflex is absent. Not a
  renderer test. Deleting it deletes the guard.

**D1–D3 remove three test files' worth of imports. Expected delta, itemised:**

| Deleted | Tests lost | Why |
|---|---|---|
| `web_dashboard/` | **10** | all of `test_visibility_state.py` — it imports `VisibilityState` from the deleted tree and globs `PAGES_DIR` inside it |
| `task_stack_adapter.py` | **2** | `test_stability_fixes.py::TestDaemonPidValidation` — tests PID validation for the daemon M2.3 deleted |

`test_visibility_state.py` is 10 tests, not a rounding error — `visibility_state.py` is
the reflex-backed adapter over `build_visibility()`, and `build_visibility` itself lives in
`ui/components/visibility.py`, which survives. Delete the whole test file with the tree.

**After D, measure and account for every difference.** If the number moved for a reason not
in the table above, that is a blocker, not a rounding error. Do not delete a test to reach a
number.

Also clean up: `integrated_orchestrator.py`'s `terminal_ui=None` parameter and the
`if __name__ == "__main__":` block at line 856 that instantiates the deleted `TerminalUI`.

---

### Delegation

- **`todo` first**, phases `Safety-Wiring` → `Surface` → `Cleanup` → `Verify`. Mark done
  only with the output that proves it. Never yield with a task `in_progress`.
- **Fan out S1, S2, S3** in one `task` batch — independent call sites, one small file. State
  in the batch context: the `executor.py` call frame, the §5.1 no-bare-subprocess rule, the
  fixture pattern from `theteam/tests/`, and that no agent runs the full suite.
- **No agent runs the full suite.** One run from Main after the batch settles. Per-agent
  runs of their own test file are fine.
- **`hub`** for coordination: `hub jobs` to check progress, `hub inbox` to drain findings.
  S1 and S3 both touch the result payload — message them before either edits its shape.
- **Main owns** the `run` result shape, the log bound, the `status` payload, and all of D.
- **Verify every subagent claim by running the command.** A report of "done" is not evidence.

---

### Deliverable

One commit per phase: `Safety-Wiring` (S1–S4), `Surface` (`history` + `status`),
`Cleanup` (D1–D3). Do not start M5.

Summary at most 3 lines (`AGENTS.md`), then report: the after-D test count with the
arithmetic from the table; the exit-137 line; the breaker output from both commands; any
safety value that came from a default; any contradiction with `ARCHITECTURE.md`.

If wiring needs a design decision you cannot make from the architecture, stop and report it.
A blocked M4 with a clear explanation beats a completed one with a hidden defect.

---

## Not in M4

M3 review findings **F1** (stale `or is legacy-only` in an error string,
`repository.py:373`) and **F2** (`create` writes `order:` off by one; the existing test
asserts the bug) are M3 debt. They are two real defects and they are not in this
milestone — F2 requires editing a test assertion, which is never a small task. Fold them
into an M3 follow-up.

A five-member review (`20260928-134516-monitoring-surface-tui-vs-web.md`) decided the UI
surface is **deferred, not cancelled**: delete the dead dashboard and TUI (that is D1–D2),
keep `ui/components/` (1,365 lines, 9 modules, pure stdlib), and build the terminal
renderer only after M4 — so `status` reports real breaker and audit state before anything
monitors it. Adopt the boundary when it comes: `state.py` → `build_visibility()` → one
renderer.

---

# Permanent solution: three rules, not another prompt

Your diagnosis is right, and the fix is not a better prompt. The failure classes are
recurring, so they belong in a mechanism that fires without you being in the loop.

I wrote three files to `~/.omp/agent/rules/`, matching the format of the rule already there:

**`evidence-before-claim.md`** — any count, test result, or completion claim must be
followed by the command that produced it, in the same turn. Includes: never "as specified
above" as a substitute for re-showing changed content; a number you did not measure this
turn is a number you do not know.

**`deletions-need-located-consumers.md`** — the five-step discipline: locate every consumer
(not just imports — path constants, `__main__` blocks, test imports from *outside* the
deleted subtree), state the itemised arithmetic before starting, measure and account for
every delta, delete last in its own commit, and trust git history as the archive instead of
creating an `archive/` directory.

**`prompts-specify-work-not-justification.md`** — the ratio check. A ~30-line milestone
described in a 300-line prompt means nine documents. Plus: one milestone per prompt, a
finding from a *previous* milestone is that milestone's debt, and a task requiring editing
an existing test's assertion is never small.

These fire on patterns, not on intent. A rule that says "be rigorous" is a wish; a rule
with a `condition` regex is a trigger.

## Two things this exercise caught that I had wrong

**My 625→623 arithmetic was wrong, and I only found it by checking.** `test_visibility_state.py`
imports `VisibilityState` from `web_dashboard` and globs `PAGES_DIR` inside it — 10 tests,
not 2. I had asserted a number I never measured. That is precisely what
`evidence-before-claim` now forbids, and I had violated it in the very prompt where I
cited the rule against the dead dashboard. The corrected table is in the prompt.

**Deletions-first was wrong for the reason I identified but did not act on.** You crashed
mid-milestone once. Opening a session with 69 files deleted and then asking for six wiring
tasks means the next crash leaves wiring-on-top-of-deletions. D is now last, in its own
commit.

## One honest limitation

Rules reduce a failure class; they do not eliminate it. The deepest one — an agent
rationalizing a plausible number — is not reachable by regex. That one needs the
measurement in the loop, which is what the `--expected-ids` check did in the team
discussion, and what `run --json` output does for the product itself. A rule can require
the evidence; only a harness can make it hard to skip.

If you want that, the highest-leverage next step is a pre-commit hook or CI gate that runs
the greps from `ARCHITECTURE.md` §7.2 and fails the build — the invariants are already
written down, they are just not enforced anywhere.