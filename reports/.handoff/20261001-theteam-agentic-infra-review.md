# theteam — theteam agentic infra: modular, deterministic self-care infrastructure

- **Project:** theteam-stability
- **Generated:** 2026-10-01 09:05 UTC
- **Members reporting:** architect, designer, devops, pragmatist, skeptic

## Individual notes

Each member's note below was written independently, before the synthesis pass — no member has seen another's note.

### Systems Architect (`architect`)

**Verdict:** approve_with_changes

# Systems Architect — review

## Verdict: approve_with_changes

The documentation is more honest than most codebases get — `ARCHITECTURE.md:517-545` names its own orphans individually, including one it nearly deleted by mistake. That is worth something. But the *instruments* that are supposed to stop the next drift measure the wrong quantities, and the accretion pattern behind F6 is a rule, not an accident.

## F6 is not one orphan; it is the accretion mechanism

`state.py:69-71` (`proposals`) is the visible instance. The pattern generalises two levels down:

`theteam/core/state_manager.py:271-275` constructs five collaborators in `__init__`:

```python
self.wal = WriteAheadLog()
self.checksum = ChecksumManager()
self.db = DatabaseManager()
self.tx = TransactionManager()
self.correlation = CorrelationManager()
```

Grep for `self.db`, `self.tx`, `self.correlation` across `theteam/`, `bin/`, `scripts/`, `theteam/tests/` returns **only these three constructor lines**. Zero readers, zero tests. `DatabaseManager()` (database.py:549) builds a `DatabaseMigrations` object per construction and never opens a connection; `TransactionManager` and `CorrelationManager` are never called. The accepted reason for their presence is "something might need it later" — which is exactly the reasoning that produced `proposals`. Three instantiations of the same rule, plus the rule itself, and no gate in `check_invariants.sh` can see any of them, because all seven checks scan *source text* or *loaded modules*, never *constructed objects*.

## F12's budget measures the wrong quantity

`check_import_graph.py:52-54` computes `set(sys.modules) - before` — every module, stdlib, PyYAML and `theteam.*` summed into one number. That makes 88/90 a figure dominated by the transitive closure of `import yaml`, which grows if a stdlib import moves, and is insensitive to the coupling anyone actually cares about.

The coupling number is on the next line: `check_import_graph.py:58-59`, `theteam.core.*` = 7 against a budget of 8. And of those seven, five (`wal`, `checksum`, `database`, `transactions`, `correlation`) are on the entry point solely because `state_manager.py:26-30` imports four modules eagerly in order to construct three objects nobody reads. So the invariant the repo calls "the only one that measures load instead of scanning text" is measuring stdlib closure for its headline number and a state-manager fan-out for its real one.

## Which boundaries are real, which are fictional

**Real:** `theteam/tasks/` and `theteam/advisory/` are genuinely disjoint — `advisory/manager.py:51` and `advisory/commentary.py:31-33` reach only `theteam.*` and `theteam.state`; `tasks/executor.py:24-26` reaches only `theteam.core`. Nothing crosses.

**Fictional #1 — the config schema.** `theteam/bin/theteam_config.py:26-44` makes ten `behavior` keys *mandatory*. Grepping every one of them (`keep_last`, `gamification_enabled`, `dynamic_interaction`, `auto_summarization`, `chat_mode`, `max_discussion_rounds`, `proactive_plan_required`, `persona_response_variety`, `enable_persona_comments`) across `theteam/`, `bin/`, `scripts/` returns only the validator's own `REQUIRED_BEHAVIOR_KEYS` list. `keep_last` is required, validated on every write, and read by nothing. `enable_persona_comments` is required *and* documented in-line as retired (`:31-38`: "nothing reads it"). A mandatory field that exists so that nothing can read it is the F2 defect promoted into the schema.

**Fictional #2 — two modules, one name, disjoint schemas.** `bin/theteam_config.py:23-25` requires `["chat_mode","verbose","auto_approve","conversations","max_iterations"]`. `theteam/bin/theteam_config.py:26-44` requires a set with *zero* overlap. `package.json:7` wires `npm run validate` to the root copy — so the published validation command checks a schema the product never writes and would reject every config `theteam bootstrap` produces.

**Fictional #3 — the state directory is centralised, and one call site bypasses it.** `state.py` exists specifically to resolve `.omp/theteam` in one place. `__init__.py:699` does `get_state_manager(os.path.join(project_root, '.omp', 'theteam', 'state.json'))` — hardcoding the layout `state_dir()` was written to stop hardcoding, and bypassing `THETEAM_STATE_DIR` entirely. Set that env var and the audit chain goes to the scratch dir while `state.json` goes to the project.

## F4: "all derived state is gitignored" is false in the one place that matters

GitHygiene verified on request: `wal.json` is **git-tracked**, 1,048,978 bytes / 872 lines, 17 `auto-checkpoint:` commits inside one day, with **676 distinct `pytest-of-bparlan/pytest-NNN/test_*` paths** embedded in its entries. Cause: `wal.py:70` defaults `wal_file="wal.json"`, resolved CWD-relative at `state_manager.py:271`. `THETEAM_STATE_DIR` feeds `StateStore` only and never reaches the WAL.

So the untracked-derived / tracked-code rule holds everywhere *except* at the one place a CWD-relative default leaked out. Two aggravating facts: `max_entries=100000` (wal.py:70) means it will not trim for a long time; and `replay_entries()` (wal.py:198-207), called at `state_manager.py:417`, sorts and **returns** — its result is discarded and it applies nothing. The write side is real, the read side is ceremony.

## Highest-leverage structural change

**Gate constructed-but-unread, using the repo's own best idea.** `check_call_sites.py` already exists precisely because grep fires on the docstring describing the defect it hunts. The same AST approach generalises: walk the package, collect attributes assigned in `__init__`, and for each one that is never read in an attribute-load position, fail the gate. ~30 lines. It catches `proposals`, `self.db`, `self.tx`, `self.correlation` today and every future instance, because the failure mode is a rule, not a list.

**Blast radius, honestly:** zero runtime impact — it is a new check in `check_invariants.sh`, and the three existing offenders must be fixed in the same commit or the gate goes red immediately. Deleting `self.db`/`self.tx`/`self.correlation` is 3 lines in one file with no readers; it also drops three `theteam.core.*` modules off the entry point, freeing core budget.

Routing the WAL through `StateStore` is the *better* fix and a much larger one: `state_manager.py` does not currently import `theteam.state`, so this touches the `get_state_manager` singleton (`:456-480`), the hardcoded path at `__init__.py:699`, and roughly 40 `UnifiedStateManager(...)` construction sites across `test_state_manager.py` and `test_run_discussion_e2e.py`. It is also a behaviour change: anyone whose WAL currently sits at CWD moves it. Do the gate first; treat the WAL relocation as separate work.

### Design Reviewer (`designer`)

**Verdict:** approve_with_changes

Verdict: **approve_with_changes** — the tool is honest and mostly well-behaved, but three surfaces actively mislead the human: a question channel that can never carry a question, a "decide" capability the user asked for that doesn't exist, and a 600s analysis whose output nobody reads. None of these are architecture defects; they are interface defects, and each is fixable without touching the stability layer.

## F7 — the phantom question channel

`bin/theteam_report.py:135-139` renders "**Open questions for you:**" followed by "- (none)". This is worse than omitting the section. A user reading a report after a multi-member discussion sees a channel that *promises* a place where the team hands back uncertainty, and the promise is broken by construction: `theteam/__init__.py:145` initializes `open_questions = []`, `:159` puts it in the synthesis dict, and no code in the tree ever appends to it. The member note schema (`theteam/core/member.py`) is `{id, role, verdict, note}` — no question field, so even if the renderer wanted to show one, no producer could create one.

The fix is not to delete the section. It is to make it a real channel with a real producer and a real consumer:

**Member note schema gains a `questions` field** — an optional list of `{ask, context, blocking}`. `blocking: true` means "we cannot proceed without a human decision"; `blocking: false` means "we went ahead, but the user should know."

**The renderer stops printing "- (none)".** When empty, the section is omitted entirely. A channel that is empty is invisible; a channel that prints a placeholder is a lie.

**The consumer is a new CLI surface.** After a report lands, `theteam ask <conversation-id> "<question>"` writes the answer into the run's state and re-renders the report with the question answered inline. The user's reply becomes part of the artifact, not a side-channel.

Terminal, after a discussion where two members disagreed and one raised a blocking question:

```
$ theteam discuss "should we extract the shared config into a module?"

Selected 3 member(s): architect, security-reviewer, performance-reviewer
context section 'runtime_config' reached no member (all 3 missed it)

# theteam — should we extract the shared config into a module?
- Project: team
- Generated: 2026-10-01 09:12 UTC
- Members reporting: architect, performance-reviewer, security-reviewer

## Consolidated report

The team agrees the config is duplicated in three places and should be
centralized. They disagree on where.

**Where the team agreed:**
- config duplication is a real defect, not a style preference

**Where the team disagreed:**
- architect: extract into `theteam/config.py` as a module
- performance-reviewer: keep it in YAML, load once at startup

**Open questions for you:**
- Where should the canonical config live? (security-reviewer, blocking)

Recommendation: No consensus — see disagreements.
```

And after the user answers:

```
$ theteam ask 20261001_0912_00_123456 "theteam/config.py"

OK: recorded answer for "Where should the canonical config live?"
```

The report re-renders with the question struck through and the answer attached, so the artifact is self-contained and auditable.

## The decide/ask interaction the user asked for

The user's stated desire — "`theteam` should be able to give decisions, and raise `ask` only if it needs" — describes a confidence-ranked output, not a binary one. Today every member files a verdict and a note; there is no confidence signal, so "the team decided X" and "the team is unsure about X" render identically.

Design the terminal around three states:

**Confident.** The team reaches a verdict with no blocking questions and no disagreement on the action. Output is one line, no report file:

```
$ theteam decide "rename the config file?"
✓ extract into theteam/config.py
```

No markdown, no member-by-member breakdown. The user asked a yes/no-ish question; they got an answer.

**Blocked.** A member raises a `blocking: true` question. The tool refuses to fabricate a decision and says exactly what is missing:

```
$ theteam decide "rename the config file?"
✗ needs input
  security-reviewer: cannot assess without knowing whether the
  config holds secrets (blocking)
```

The user types `theteam ask <id> "no secrets, plain config"`, and the next `decide` re-runs the blocked members only — not the whole discussion — and returns the confident shape.

**Unresolved.** Members disagree on the action and no question is blocking. The tool does not invent consensus:

```
$ theteam decide "rename the config file?"
? no consensus
  architect → extract into theteam/config.py
  performance-reviewer → keep in YAML
  (theteam discuss for full report)
```

The `?` glyph, the one-line disagreement, and the pointer to the full report. The user gets enough to act and knows where the detail lives.

The key design rule: **`decide` is the default, `ask` is the exception, and `ask` is always named.** A tool that silently decides is worse than one that says "I need you." The current code already has the vocabulary for this — `verdict`, `note` — it just has no third value between "approve" and "block" and no way to carry a question out of the member process.

## F1/F3 — the 600s report nobody reads

`scripts/sa_runner.py` runs with a 600s timeout and 384MB, writes 6 JSON reports to project root, and zero code in `theteam/` reads any of them (F1). The user never asked for a 600s analysis; they asked for awareness of what the system is doing. Those are different artifacts.

The ideal context artifact is **~2KB, generated on every `theteam run`, and readable in 5 seconds.** It replaces six 600s JSON files with one small document the user actually opens. Shape:

```
# team awareness — 2026-10-01 09:15 UTC
## what ran this tick
- project-integrity: ok (health_check, 1.2s)
- maintenance: skipped (nothing due)
## what is broken
- system-awareness: overdue 14 ticks, breaker open
  (last failure: missing infrastructure_report.json)
## what needs you
- (none)
## costs this tick
0.8s wall, 3 tasks, 0 LLM calls
```

Four sections, ~2KB. "What ran" and "what is broken" are measured from the run that just happened — not from a separate 600s pass. "What needs you" is the question channel, so it inherits the F7 fix: empty → the line is omitted, never "- (none)". "Costs" is one line: wall time, task count, LLM calls. Nothing else. A reader who wants detail runs `theteam history <task>`; the awareness file is a glance, not a dump.

This collapses F3's two pipelines into one: the working `context_aggregator.py` → `context_slice.py` path already produces per-member YAML on every run. Extend it to also emit this awareness file, and delete `sa_runner self-correct` from the task inventory entirely. The 600s cost disappears; the information the user actually wanted (is anything broken, did anything run, do I need to act) was already being computed by the scheduler and thrown away.

## What is confusing in the current CLI outputs

`theteam run` is the strongest surface and still has two problems. The per-task line is good — `project-integrity: ok (health_check, 1.2s)` — but the summary line conflates three different things:

```
2 ran, 1 skipped, 0 failed in 0.8s
```

"Skipped" carries four distinct meanings with no visual distinction: breaker-open (a real failure state), misconfigured-phase (a defect to fix), nothing-due (not a skip at all, it's the empty case), and refused-provider. A user glancing at this cannot tell whether the run was healthy. The fix is a glyph per reason, or better, only print the skip line when the reason is actionable:

```
2 ran, 0 failed in 0.8s
  (1 skipped: system-awareness — breaker open, 14 ticks overdue)
```

`theteam tasks` is good on state (the `never run` wording is honest) but silent on consequence. It shows `breaker: open` and next-run timestamps but never says *what a breaker open costs you* — that task will not run until it is reset, and nothing in the output says that. Adding one word to the breaker column (`open → will not run until reset`) would make the state actionable instead of decorative.

`theteam loop` reports `next run <timestamp>` but never says whether the task is due now or how long until then. A relative duration (`next run in 23m`) is what a human reads; an absolute UTC timestamp is what a machine reads. The command already emits both in its payload; only the human line needs the relative form.

None of these require new architecture. They require the renderer to distinguish kinds of skip, to use relative time for humans, and to treat an empty question channel as invisible. The underlying machinery — named reasons, measured breakers, live output streaming, honest exit codes — is already there. What's missing is the last few centimeters of interface honesty.

### Infrastructure Engineer / DevOps (`devops`)

**Verdict:** approve_with_changes

## Verdict: approve_with_changes

The on-call path is sound; the unattended path has four unbounded or unrecoverable resources and one wedge. All findings below are measured this session.

### 1. The interval guard exists only on the write path. Bad schedule state is immortal.

`repository.py:413-418` refuses a new interval shorter than `sum(timeout_seconds)`. Nothing applies that predicate to state already on disk. `.omp/theteam/task-schedule.json` still carries `system-awareness` at `interval_minutes: 1` with `next_run: 2026-10-01T01:01:03Z` — ~7h in the past. It is permanently overdue.

It cannot self-correct, because `record_run` (repository.py:314-320) reads `interval_minutes`, never validates it, and re-stamps `next_run = now + interval`. A 600s task on a 60s cadence re-stamps to `now+60s`, so `due()` (`next_run <= now`, repository.py:266) is true on **every** sweep, forever. The corrupted entry is copied forward on each write.

Proposal — `invalid_schedules()` + `repair_schedules()` in `TaskRepository`, called at the same site as `purge_orphaned_schedules()` (`cli.py:443`), which every sweep already passes through and which already writes + audits. Rule: recompute `worst = sum(p["timeout_seconds"])`; where `interval_minutes * 60 < worst`, set `next_run = now + ceil(worst/60)` and emit `_audit(..., "schedule_interval_repaired", task_id, was, repaired, worst_case_seconds)`. Pure function of (YAML, schedule, now); idempotent — the second run is a no-op. Second, independent predicate worth adding: `next_run` older than `worst_case` at read time is the actual overdue detector and catches drift the interval check misses.

### 2. Retention: three classes, zero enforced bounds

- **`archives/` — unbounded, one-way.** `analyze_system_awareness.py:50-67` does `Path.replace()` into `archives/ledger_<ts>.json` and never prunes. 23 files, 196MB, oldest 10h old. Extrapolating: ~2.3 files/h × 10MB ≈ **~16GB over 30 days**, all gitignored (`.gitignore:117-118`). Separately, `save_ledger` (`:106-111`) checks `st_size > LEDGER_MAX_BYTES` *before* writing whatever is in memory — the measured 11MB ledger is 5.5x the 2MB cap, so the cap bounds nothing between saves. Fix: cap the *in-memory* payload, not the file on disk, and prune to newest-N by name in `_rotate_ledger` itself, the same call that creates the file.
- **`backups/` — the policy is documentation.** `prune(keep=10)` (backup.py:198-216) has **zero production call sites**; grep across `theteam/` returns the definition plus `test_backup.py:309,325,335,348`. `BackupManager` itself is referenced only by the `core/__init__.py:42` registry and tests. The bounded-growth claim in backup.py:17 is not implemented. When it is wired, `shutil.rmtree` at backup.py:210 destroys untracked state with no tombstone: write a `pruned.json` listing deleted names + sizes before deleting, so "what backup existed at T" stays answerable.
- **`.loop-archive/` — age-based, and the job is never run.** `loop_maintenance.py:78-79` rotates at 30 days, but `maintenance` is unscheduled (F10) and the user deferred looping. Unattended, nothing fires it.

### 3. Exit-code taxonomy: one integer, three meanings

`loop_infrastructure_check.py:136` and `loop_health_check.py:98` both `sys.exit(1)` on findings; `sa_runner.py:688,692,697,703,717,722` does the same for a stale or low health score. `agent_isolation.py:330-336` maps that to `success = returncode == 0`, and `executor.py:300-304` calls `breaker.record_failure()` on it (`failure_threshold=5`, executor.py:88).

So **a check that correctly detects a real problem advances the breaker.** Five genuine findings and `project-integrity` is `breaker_open`; `record_skip` deliberately does not restamp `at` (cli.py:489), so the recovery window anchors to the original trip. Unattended for 30 days: window elapses → half-open → re-runs → finds the same real problem → re-trips. A stable oscillation burning 600s of container time per cycle that never produces a new fact.

Proposal — a 4-value phase outcome replacing the boolean:
- `0` clean
- `1` **findings** (the check ran and is reporting; not a defect of the phase)
- `2` **cannot evaluate** (missing dependency, unreadable input — the check could not measure)
- `124`/`137` already reserved for timeout/OOM (executor.py:33-34)

Only `1` and `2` advance the breaker, and only `2` should. Findings persist to the run record without touching breaker state — a task that is *measuring correctly* and a task that *broke* are different facts. This also fixes `cli.py:578` (`EXIT_ERROR if payload["failures"]`), which currently conflates a finding count with an execution verdict. Migration: one sweep of `scripts/` for `sys.exit(1)`, one classification table, tests asserting `1` does not trip.

### 4. F9: the enforceable boundary is a declared write set, verified by the parent

`_writable_mount_args` (executor.py:360-378) returns one bind mount of the whole root with no `mode`, and executor.py:217 then suppresses the ro mount. Everything else is already tight — `--read-only` rootfs, `--tmpfs /tmp`, `--user 999:999`, `--network none` (agent_isolation.py:110-127). The project tree is the only writable surface and it is unbounded within it.

Replace the boolean `writable_project` with `write_set: [".omp/theteam", "system-awareness-ledger.json", ...]` (repository.py's `_check_writable` is the existing hook). Enforcement in two deterministic halves:
1. **Pre-flight, parent-side:** the set is non-empty and intersects no denylist (`.git/`, `tasks/`, `theteam/`, `*.py`, `theteam.config`). Refuse by name, matching the `memory_limit_mb` refusal at executor.py:176-184.
2. **Post-run, parent-side:** the parent snapshots a path+size manifest before the phase and diffs after. Any change outside `write_set` yields `success: false`, `error: "wrote outside declared write set: [...]"`. The child cannot lie about this.

This deliberately avoids Docker mount-nesting semantics as the primary mechanism — a nested ro-parent/rw-child bind may work, but I have not verified it on this image and would not make the boundary depend on it. The parent-side diff is verifiable today and holds regardless.

### 5. 30 days unattended, in the order it breaks

1. **Hour 1 — orphaned containers.** `TICK_JOIN_SECONDS = 5.0` (scheduler.py:28) means `stop()` returns during a 600s phase. A `serve` restart leaves a live `docker run` named `theteam-phase-{os.urandom(6).hex()}` (executor.py:213) with no reaper anywhere in the repo. 60/hour if the 1m schedule survives.
2. **Day 1 — disk.** ~16GB of gitignored archives, zero git pressure.
3. **Day 2 — the breaker wedge** in §3.
4. **Day 7 — `backups/` unbounded**, prune never called.
5. **Day 30 — no recovery surface.** `record_run` and `_save_schedule` write `task-schedule.json` with bare `open(path,"w")` + `json.dump` (repository.py:329-330, 386-390) — no temp+rename, unlike `wal.py:139-150` which does it correctly. `schedule()` (repository.py:165-169) `json.load`s with no guard. A single interrupted write truncates the file to zero bytes; every subsequent `TaskScheduler.tick` raises, is caught at scheduler.py:119, and records the same `last_error` **forever**. That is a permanent outage from one Ctrl-C, and it is the cheapest thing on this list to fix: temp-file + `os.replace` + a `JSONDecodeError` that renames the corrupt file aside and starts from an empty schedule rather than throwing.

**Blocking items: none. Required before unattended use: the write-atomicity fix in §5.5, the exit-code taxonomy in §3, and `repair_schedules()` in §1.**

### Delivery Pragmatist (`pragmatist`)

**Verdict:** approve_with_changes

# Verdict
There is one high‑ROI change and three secondary cleanup items that actually improve on‑call stability and reduce noise. The rest of F1‑F13 are architectural bones worth removing but not worth doing right now for a solo developer—especially with the active interval that is already per your instructions. You asked for the smallest set of changes that gets you to stable on‑call execution and deferred looping.

## Ranks – What to Do (Ordered by ROI)
1) **PROPOSAL: Fix `system-awareness` next_run; keep interval 0 (skip looping).**
   - **F1 hit:** The 600s + 384MB run exists and leaves an unread output. Worse, the task's `next_run` is aggressive (every minute), which under a stable on‑call mental model is noise you already told me to stop.
   - **F4 side benefit:** Less runtime artifact churn lowers mental load, and fewer 600s runs mean less heap allocation pressure under normal rhythms.
   - **Action:** In `.omp/theteam/task-schedule.json`, set `system-awareness` interval to `0` (or remove it if the schema allows). This respects your explicit request to disable automated looping and keeps F1's cost but no scheduled churn.
   - **Effort:** 1 location edit, trivial. **Why ROI is highest:** no-code read that we verified; you get straight away the on‑call stability you asked for with literally zero wiring changes.

2) **IGNORE `context:` keys in task YAML files (F2).**
   - **Findings:** Six `task-*.yaml` files each have a decorative 4‑line `context:` list. `theteam/tasks/repository.py` loads it but nothing in `theteam/` (not even cli.py) ever consumes it. All readers are in legacy `scripts/`, not the on‑call layer.
   - **Harnessment:** The working pipeline is `workflow/context_aggregator.py` + explicit slice into member prompts; this YAML list is inert prose. Maintaining a lie is terrible practice for any on-call product.
   - **Action:** Delete the `context:` block from each YAML (same content across 6 files). Two minutes, 6 deletions, zero behavioral change.
   - **Effort:** <5 min across 6 files. **ROI:** prevents future confusion about why someone wrote context here when it's not used (burned hours debugging unused fields).

3) **IGNORE unbounded archive rotation; keep `archives/` as a debug artifact out of documentation.**
   - **F4 hit:** `task-system-awareness/analyze_system_awareness.py` rotates `system-awareness-ledger.json` into `archives/` without a retention policy, leaving 196MB on disk. This is noisy but not correctness‑blocking.
   - **Why defer:** Archiving is a privacy/maintenance decision that scales with the frequency of `run_analysis`. Removing rotation widens risk of running out of space on shared devices; freezing rotation preserves cleanliness until a dedicated change lands with a retention budget.
   - **Action:** In a follow-up, add a retention budget (e.g., `MAX_ARCHIVES=7`) and hook it at archive creation time. For now, treat `archives/` like runtime debug state: ignore it in docs and accept unbounded growth as a known pain point.

4) **IGNORE `proposals` and `open_questions` dead fields.**
   - **Scope:** F6 (no `proposals` writer) and F7 (no `open_questions` appender) are skeletal. The infrastructure exists but isn't wired. Hooking them in now would expand scope beyond a dry maintenance pass.
   - **Why defer:** They're slots for future features (configurable tasks and human sign‑off). The Ranks强调 "small set of changes that gets you there"; adding human‑question‑raising machinery is orthogonal.

## What NOT to Do (Spurious Effort)
- **Do not touch `loop_health_check.py` exit code semantics (F11).** That file uses exit code 1 only for infrastructure checks, not for "found a problem" at phase level. The labels you asked for (on‑call stability) are satisfied by removing scheduled noise already in Rank 1.
- **Do not refactor `proposal/apply` pattern (F8) or add `ask` (F5).** They're scaffolding that doesn't exist; fixing them would require a new proposal contract and you promiseddeferred looping first.
- **Do not touch `writable_project` having all‑or‑nothing scope (F9) or import budget (F12).** Those are medium‑term API concerns for you, not on‑call operational pain.

## Summary
- **High‑ROI change:** Set `system-awareness` interval to `0` in `.omp/theteam/task-schedule.json` (ignores F1's noisy profile but kills scheduled churn) and delete decorative `context:` lists across the 6 YAML files (F2). Together they give you the stable on‑call execution base you explicitly asked for and cost <10 minutes of edits.
- **Defer, not remove:** Archive rotation and dead fields are worth addressing later once you're on a solid footing; right now they're distraction.

**My recommendation: take Ranks 1 and 2 as the full implementation; consider Ranks 3 and 4 (plus F11‑F13) as fresh‑to‑fix items in a future maintenance cycle or milestone.**

---
**Evidence used:** grounding document (F1‑F13), `task-schedule.json` (scheduled jobs), `analyze_system_awareness.py` (rotation), repository.py (context load), abject readership grep, and file/line citations for all actions. No behavioral changes introduced; only royal pruning and one minimal config detox.

### Adversarial Reviewer / Skeptic (`skeptic`)

**Verdict:** block

# Adversarial review: the failure mode is not "reports go unread" — it is "the reporting code cannot report"

I went looking for more F1s. I found the F1 mechanism itself is worse than the grounding doc states, and that the same shape recurs at every layer. Ranked by severity.

## D1 — CRITICAL. `self-correct` can never report success, and its success path is dead code

`self_correct` reads `report.get("results")` at `scripts/sa_runner.py:600,602,603`. `_build_initial_report` (`:510-521`) has keys `timestamp, attempts, improvements, corrected, drift_before, drift_after, status, acceptance` — **no `results` key**. The only writer of a `results` key is `_record_successful_correction:546`, which nests it inside an `improvements` entry, not the report. So the argument is **always `None`**, and `_evaluate_health_improvement:490-494` returns `0` for falsy results — therefore `improvement` is **always 0**, forever.

Consequences, all verified by grep across `scripts/ theteam/ tests/ bin/`:
- `if improvement > 0` at `:601` is unreachable → `_update_state_with_improvement`'s body (`:564-575`) is dead → **`write_infrastructure_report:574` is called by nothing**. That is the true F1 cause, and it is not a one-line omission as `CHANGELOG.md:154` claims ("the fix is one line in `_run_correction_cycle`") — adding the call there works, but the correction-*reporting* path is separately broken.
- `_record_successful_correction:540` is dead. `report["corrected"]` is always `False` and `improvements` always `[]` after a run that just wrote five reports successfully.
- Every successful correction is filed as `status: "partial"`, `acceptance: "accepted"` (`:549-552`).
- `drift_before`/`drift_after` (`:517-518`) are initialized `None` and written by nothing. They render as a measurement and are a constant.
- `_accept_state:506` and `_log_issues:430` have **zero call sites**.

**Symptom:** `python3 scripts/sa_runner.py self-correct` prints `{"corrected": false, "improvements": [], "status": "partial", "drift_before": null, "drift_after": null}` after a fully successful run. **Misled how:** the one artifact whose entire job is to say "did the fix work" is structurally incapable of saying yes. A human skimming it sees `partial` and goes looking for a problem that does not exist.

## D2 — CRITICAL. `project-integrity` punishes correct detection and thereby silences itself (F11 traced to consequence)

`scripts/loop_infrastructure_check.py:136` `sys.exit(1)` on findings → `executor.py:223` `success = (exit_code == 0)` → `executor.py:304` `breaker.record_failure()` → `cli.py:510` `record_run(..., "failed", "returncode 1")` → `cli.py:578` exit 1.

The conflation is **directional**, not merely cosmetic. `tasks/task-project-integrity.yaml:15` defines success as "check passed" — so exit 1 is the *product working correctly*. Three genuine detections (a missing directory, a stale loop state) open the breaker permanently, and the task then stops running: the project's real defect becomes permanently unmonitored, and the trip only clears when the problem goes away — the thing nobody is fixing because the monitor is off. Worse, `theteam watch --monitor` fires a "breaker opened" alert (`theteam/monitor.py:165-170` matches `.state`) for correct behaviour, training the operator to ignore the alert that matters.

**Symptom:** `theteam tasks` shows `project-integrity  open` for a task that is behaving perfectly. **Misled how:** the most reliable signal in the system is inverted, and the reason is recorded nowhere.

The vocabulary is the root cause: `runners/llm.py:82-89` documents three outcomes; `executor.py:264,295` adds exactly two. There is no `findings`. Note the asymmetry — `executor.py:281-298` carefully refuses to advance the breaker for *refusals*, with an explicit comment. That care was never applied to "the phase exited non-zero because it worked."

## D3 — HIGH. `maintenance` cannot fail at its own job and reports a count it did not measure

`scripts/loop_maintenance.py:31-33`: `shutil.rmtree(pycache, ignore_errors=True)` then `removed.append(...)` **unconditionally**. Lines 35 and 39 use `unlink(missing_ok=True)`. So `removed` counts directories *found*, printed as "Removed __pycache__ / .pyc files: 128", and every deletion failure is swallowed. `main():93` then `sys.exit(0)` unconditionally.

**Symptom:** `maintenance: ok (1.2s)`, `failures: 0`, exit 0, with 40 MB of stale cache still on disk. **Misled how:** the count is a fabrication produced by the same code that failed to delete. `expected_output` is a string match against a message the script always prints.

## D4 — HIGH. `self-check` exits 0 while reporting `"healthy": false`

`sa_runner.py:767-769` prints the check JSON and falls out of `main()`. There is **no `sys.exit` anywhere in `main()`** (`:757-775`) — every subcommand exits 0 except one that raises. `self_check_loop_state:400-404` correctly finds `infrastructure_report.json` absent and says `healthy: false`; the process then reports success to any exit-code consumer.

**Symptom:** `sa_runner.py self-check; echo $?` → `0`, with `"healthy": false` on screen. **Misled how:** the in-script check is more honest than its own exit code — and the exit code is what automation reads.

## D5 — MEDIUM-HIGH. `agreements`/`disagreements` are worse than F7: they assert unanimity

`__init__.py:144-146` hardcodes all three lists empty and a fixed `recommendation`; `:150-156` appends only to `summary`. `run_discussion:925-928` writes that dict to `theteam-synthesis-*.json` in **`tempfile.gettempdir()`** (i.e. `/tmp`), and `bin/theteam_report.py:117-140` renders `"- (no disagreement recorded)"`.

Three members filing `block`, `approve`, `approve_with_changes` on one topic produce a report headed **"Where the team disagreed:"** followed by **"- (no disagreement recorded)"**. That is a positive claim of unanimity from a list initialised empty. F7's `open_questions` is at worst a void; this is an inversion.

**And the doc is false about the safeguard:** `bin/theteam_report.py:5-9` states "Those come from the orchestrating agent's synthesis pass." Nothing writes that file but `consolidate_notes`, a Python function. There is no path by which an agent supplies it.

## D6 — MEDIUM. F5's consequence, stated precisely

With no `pending`/`needs_input` outcome, an agent facing genuine ambiguity has three options, all bad: guess (confident falsehood in the report); fail the phase (`executor.py:304` → the D2 self-silencing, after 3 ambiguities); or bury the question in `note` prose. The third is the dangerous one: the question lands under "Individual notes," and `Open questions for you: - (none)` (D5) tells the user nothing needs their input. The section is **anti-signal** — it converts a real question into an apparent non-question. `SKILL.md:195` then instructs the orchestrator to summarise "any open questions" from a field that is always empty.

## The systematic test

D1, D4, D5 share one shape: **a value initialised to a plausible constant that no write path can change, surfaced through a renderer that treats it as a measurement.** Grep for a field's name across `theteam/ scripts/ bin/`; if the only hits are its initialiser and its renderer, it is decorative. That single query found `open_questions`, `drift_before`, `drift_after`, `improvements`, `corrected`, `agreements`, `disagreements`, and `state.py:69` `proposals` (F6) in one pass. Apply it to every field the UI prints.

## F4, worst case

`writable_project: true` (`task-system-awareness.yaml:60`, `task-maintenance.yaml:26`) binds the **whole tree rw** (`executor.py:195-201` → `_writable_mount_args:355-378`). If such a phase rewrites `.omp/theteam/audit.jsonl` or `task-schedule.json`, then `git checkout .` restores every `.py` file — `git status` clean, tree pristine — while 2.7 MB of audit history and the whole breaker state are gone. The phase **cannot record that it did this**: `scripts/loop_infrastructure_check.py:16-30` documents that the isolation image has no `git`. The only surviving pre-image is `archives/`, untracked, rotated by one-way `Path.replace()`, 196 MB, no retention policy — so the incident's evidence base is whatever the operator's disk pressure happened to leave.

**Verdict: block.** The self-correct report cannot report success (D1) and the integrity monitor disables itself by working correctly (D2). Fixing the one-line `infrastructure_report` omission without fixing the `report["results"]` bootstrap would ship a green report that is still structurally incapable of the truth.

## Consolidated report

All five members independently converged on the same core finding, reached from four different directions: this system's most expensive machinery produces artifacts nobody consumes, while its most reliable signals are inverted. The 600s/384MB system-awareness analysis writes six JSON reports that zero code in theteam/ reads (F1) — and one of the six is not even written, because its caller is behind an if-branch that can never be taken (D1, verified by running it: status 'partial', infrastructure_report.json absent). In the other direction, loop_infrastructure_check.py exits 1 when it correctly detects a problem, which executor.py:304 converts into breaker.record_failure() — so five true findings permanently disable the monitor, and the trip only clears when the problem is fixed by something nobody is watching (D2, verified: allow_request=False after 5 correct detections). Skeptic returned BLOCK on exactly these two. The other four returned approve_with_changes. The split is not about whether the problems are real — all five agree they are — it is about scope and sequencing.

**Where the team agreed:**

- F1 is a genuine §3.3 defect, not a design choice: 600s + 384MB per run to write JSON that no code in theteam/ reads. Architect, Designer, Pragmatist, Skeptic and DevOps all independently identified it.
- The `context:` YAML key (F2) is decorative in all six task files. The only reader is the legacy scripts/task_executor.py:84. Maintaining prose that injects nothing is a cost with zero benefit.
- F6 (`StateStore.proposals`, state.py:69-71) is dead scaffolding, and Skeptic independently generalised it: architect found three more instances of the same accretion rule — self.db, self.tx, self.correlation in state_manager.py:271-275, constructed and never read.
- F7 (`open_questions` always empty) is worse than absent. Skeptic escalated it: `agreements`/`disagreements` are also initialised empty (__init__.py:144-146), so three members filing three different verdicts render as 'Where the team disagreed: - (no disagreement recorded)'. That is an assertion of unanimity from an empty list.
- F11 (exit-code conflation) is a root cause with a traced consequence chain, not a cosmetic issue. Skeptic and DevOps independently traced it to breaker.record_failure() at executor.py:304.
- The context file should be generated on every `theteam run` and should be small (~2KB). Designer specified the four-section shape; this supersedes the 600s JSON pipeline entirely.
- Nothing here needs new architecture. Every member's proposal is a change to existing files. Designer: 'None of these require new architecture — they require the renderer to distinguish kinds of skip.'

**Where the team disagreed:**

- SCOPE — the central split. Pragmatist: do only two things (disable the 1-minute schedule entry; delete the decorative `context:` blocks), <10 minutes, and defer everything else including F1's 600s cost. Skeptic: block. Shipping anything while the self-correct report is structurally incapable of reporting success and the integrity monitor disables itself by working correctly is not shipping. Architect and DevOps side with Skeptic on severity but propose sequencing rather than a halt.
- F1's remedy. Pragmatist: keep the 600s analysis, just unschedule it — the cost is only paid on demand. Designer and Architect: delete `self-correct` from the task inventory outright and replace it with the ~2KB on-every-run context file. This is a direct conflict on whether the analysis has any remaining value.
- Retention policy for archives/ (196MB, unbounded). Pragmatist: ignore it, it is 'noisy but not correctness-blocking', freezing rotation preserves cleanliness. DevOps: it extrapolates to ~16GB over 30 days, prune() has zero production call sites so the bounded-growth claim is documentation only, and shumai rmtree at backup.py:210 destroys untracked state with no tombstone. DevOps proposes pruning inside _rotate_ledger itself; Skeptic notes the only surviving pre-image in an incident is whatever archives/ happens to still hold.
- The `ask`/decision channel (F5). Pragmatist: explicitly out of scope — 'adding human-question-raising machinery is orthogonal', defer it. Designer: designs it in full — a `questions` field on the member note schema, `theteam ask <id>` to answer, and three terminal states (confident / blocked / unresolved) with a `decide` command. Architect and Skeptic both treat it as load-bearing for safety. This is the sharpest disagreement in the room.
- The interval guard. Pragmatist: hand-edit task-schedule.json to interval 0, one location, done. DevOps: the guard exists only on the write path (repository.py:413-418), record_run re-stamps next_run = now + interval without validating, so the corrupted entry is copied forward on every write and cannot self-heal. DevOps proposes invalid_schedules() + repair_schedules() at the purge_orphaned_schedules() call site (cli.py:443). Same goal, but a hand edit is a one-time patch against a mechanism that regenerates the disease.

**Open questions for you:**

- Is the 600s sa_runner analysis worth keeping at all, or should `self-correct` be deleted from the task inventory in favour of the ~2KB per-run context file? This is the decision that unblocks everything else and the members genuinely split on it (Pragmatist vs Designer/Architect).
- Should the decision channel (`ask` from inside a run) be built now, or after on-call stability is proven? Designer has a full design; Pragmatist says it is orthogonal; Skeptic says its absence forces agents to either guess or bury questions where the empty open_questions section reports '- (none)'.
- Is the WAL relocation (architect: wal.json is git-TRACKED at 1MB with 678 pytest temp paths embedded, because wal.py:70 defaults to a CWD-relative path and THE TEAM_STATE_DIR never reaches it) in scope now, or separate work? Architect's own recommendation is gate-first, WAL-relocation-separate.
- Does the user accept replacing the boolean writable_project with a declared write_set verified parent-side by manifest diff (DevOps §4), given that Docker bind mounts cannot express subdirectory-level read-only within one source?

**Recommendation:**

No full consensus on scope — see disagreements. The five members agree on the diagnosis and on the priority order; they split on how much to do in one pass. A defensible synthesis: (1) Fix D1 and D2 first. Both are small, both are verified-broken today, and both are the 'failure that looks like a success' class this repo exists to prevent — D1 makes the correction report structurally incapable of reporting success, D2 makes the integrity monitor disable itself by working correctly. (2) Ship the ~2KB per-run context file and delete `self-correct` from the inventory, retiring the 600s/384MB cost (Designer + Architect). (3) Add repair_schedules() so bad schedule state self-heals rather than being hand-patched (DevOps), and add the atomic-write fix to task-schedule.json — DevOps flags that one Ctrl-C during a write truncates it to zero bytes and every later tick re-raises the same last_error forever, which he rates the cheapest item on a list where everything else is expensive. (4) Wire the exit-code taxonomy so findings do not trip the breaker (DevOps §3). (5) Deliberately defer the `ask` channel until (1)-(4) hold — but record that its absence is a known forcing function, not a neutral gap. Architect's highest-leverage structural item, the AST gate for constructed-but-unread attributes, is cheap (~30 lines) and catches the accretion rule that produced proposals, self.db, self.tx and self.correlation in one query.
