# Changelog

The honest history of this project is the milestone order in
[`ARCHITECTURE.md`](../ARCHITECTURE.md) Part 6. This file records what each one changed and
what it falsified. The previous version of this file was a 435-line pre-M0 changelog ending
2026-09-20 describing a system that no longer exists: a `subskills/task-stack/` daemon, a curses
`ui/terminal_ui.py`, a `discussion_manager.py` that was renamed, and a "Phase 4 Optimization"
roadmap that was never planned. Those entries were removed rather than carried forward. The
pre-M0 reports they described are preserved in
`archive/docs-theteam/pre-m0-reports/`, where they are history rather than documentation.

## M9 Phase 1 — Wire the selector

`theteam/advisory/selector.py` was live, tested, deterministic code with **no production
caller**. `theteam discuss` spawned every `enabled` member for every topic. This phase
connects the two, and closes two defects found on the way. Later phases (manager,
context efficiency, `runner: llm`, diagrams) are not in this entry.

**1.1 — Members are told which tools they may use.** The code read
`.omp/theteam/tool-manifest.json` and defaulted to the literal string `"N/A"`. That file
does not exist, so *every* member prompt carried `## Tool Inventory` / `N/A`. A boundary
the constrained party cannot see is enforced by luck. `spawn_member_task`'s fourth
argument is now `permitted_skills`, read from the project's own `theteam.config` and
rendered under the same heading. An empty list renders as
`none declared by this project's theteam.config` rather than a blank section, because a
blank boundary is still an invisible one.
Falsified by: `test_m9_selection_wiring.py::TestToolInventoryIsTheRealBoundary`, and by
executing the pre-change `spawn_member_task` directly — its prompt contained `N/A` and
named none of the configured skills.

**1.2 — Selection decides who speaks.** `run_discussion` builds a minimal `SessionSlice`
from the topic and calls `select_members` unchanged. No fifth signal was added: the topic
arrives as `last_user_messages` (signal 2 in §4.5) and any source file it names arrives as
`touched_paths` (signal 1). Adding a topic-scoring heuristic is the dead end
`selector.py:201-207` records — a gate that cannot fail is not a gate. The intro spawn was
**also** re-deriving "every enabled member", so a capped discussion would have reported one
roster and paid for another; it now honours the same selection.
Measured, on this project's 5-member roster, via a recording provider injected into
`run_discussion`:

```
refactor scheduler.py            -> Selector chose 1 member(s): devops
should we ship or simplify scope -> Selector chose 1 member(s): pragmatist
the docker deploy pipeline ...   -> Selector chose 1 member(s): devops
hm                               -> Selector chose 1 member(s): skeptic
```

Five enabled members; one speaks. That is the observable M9 exists to change.

**1.3 — The cap is enforced and reported.** `select_members` already truncated to
`MEMBER_CAP = 4` and returned `truncated: True`, but a caller that reports the overflow
cannot recover the number: re-deriving it from `len(members)` after the slice is zero **by
construction**, so a "1 suppressed" line is a line that can never fire. The selector now
returns `suppressed` and the caller prints from it. Falsified by
`test_advisory.py::test_truncation_reports_how_many_were_suppressed`, and by running the
selector against a 9-member roster where 4 speak and the rest are counted.

**Two pre-existing defects found and fixed in the path being edited.** Neither was
introduced by M9; both are why `theteam discuss` had never been observed to work.

- `run_discussion` called `aggregate_project_context` and **it was imported nowhere in the
  package.** `git log -S` finds no commit that ever added the import. Every discussion that
  got past `_require_provider` would have died on a `NameError` two lines into the
  function. No test caught it because no test runs this path with a provider. Imported at
  point of use, as check 7 requires.
- `theteam/core/state_manager.py` calls `self._notify_listeners` 12 times; the method is
  defined on `UnifiedStateManager`, not on `DiscussionState` or its siblings, so
  `start_discussion` raises `AttributeError`. **Not fixed here** — it is a different module
  and outside Phase 1's scope. It is recorded in Part 8 below as a real defect, not
  worked around in the product code.

**Invariant 7 broken deliberately, with the reason, in the same change.** `run_discussion`
was byte-identical from M5 until now; §7.2 item 7 is updated in place to state what the
invariant was *for* and what now holds instead.

**Import budget.** A module-scope `from .advisory.selector import ...` pushed `import
theteam` to 91 modules and failed check 7. The selector is imported at point of use; the
entry point now loads **88** modules against a budget of 90.

`789 passed` (772 + 17 new), gate 7/7, `import theteam` succeeds.

## M9 Phase 2 — `theteam manager`: the team that staffs itself

`theteam discuss` spawned whoever was on the roster, and the roster was frozen at
bootstrap. This phase adds the command that grows it from the topic, and answers the four
open questions §M9 left.

**The decision is deterministic; the LLM is not involved.** `advisory/manager.py`'s
`detect_triggers` reads the project flags and the topic and returns candidates with their
evidence. Two independent triggers, as §M9 requires: a focus flag no member covers, or topic
vocabulary no member's `expertise` covers. Falsified by
`test_m9_manager.py::TestTwoIndependentTriggers` — project context alone gives the same team
for every question (a topic about rate limiting adds nobody), and topic alone gives a team
blind to the repo.

**`--topic` proposes. `--apply` persists.** A bare `--topic` writes nothing, deliberately:
`--topic` also fires on every uncovered *project* flag, so a version that wrote on propose
would grow a committed config as a side effect of asking a question. That is the HITL
premise, not a prompt. Falsified by
`test_m9_manager.py::test_a_bare_topic_proposal_writes_nothing`, which byte-compares the
config across the call.

**The four open questions, answered from the code rather than from preference:**

1. **Manual, not automatic.** §M9 reads "separate HITL process" as manual, and it is the only
   honest option: an automatic manager spends an LLM call per discussion to change state
   nobody approved.
2. **`theteam.config`, versioned.** The roster is a team composition, so every change is a
   reviewable diff. A state file is disposable; this is not. Writes go through
   `theteam_config.validate_config` and are **refused** if the result would be invalid.
3. **The cap is the catalog: 9 members.** §M9 warned a manager that grows every run reaches
   30, at which point the selector picks 4 from 30 on stale signals. The code already
   answers this: `theteam.BASE_MEMBERS` + `theteam.FOCUS_MEMBERS` define every member that
   can exist. A member outside the catalog is not addable. Falsified by
   `test_the_catalog_is_finite_and_small` and by a kitchen-sink topic over a
   every-flag-fired project.
4. **`permitted_skills`, not a new key.** One list, one boundary. Two keys would need a rule
   for which wins.

**`--status` states why, or says it cannot.** A member with no recorded evidence is listed
under `no recorded reason` rather than given a plausible line. This is load-bearing: running
it against **this repository's own `theteam.config`** reports `designer` and `devops` as
unjustified, because the committed roster (hand-edited at M0) disagrees with the project's
own detectors — `api_focus` and `database_focus` fire and `api`/`data` are absent. The
manager reports the drift instead of papering over it.

**A topic-triggered addition records its reason at apply time.** `--status` cannot re-derive
it: a member added for "auth" is unjustified by any project flag, so a re-deriving `--status`
reports the member the manager *just added* as unjustified. `added_reason` and
`added_for_topic` are written with the member. A recorded fact is a fact; a re-derivation is
a guess.

**Two pre-existing defects found and fixed:**

- **`generate_team_members_from_context` emitted a config with no `schema_version`**, so its
  own output can never pass `validate_config`. `theteam bootstrap` only ever worked because
  `merge_config` inherited the value from the template; anything using the return value
  directly got a config it was forbidden to write — which is exactly what `manager --reset`
  does. Falsified by running `validate_config(generate_team_members_from_context("."))`,
  which returned `Missing 'schema_version' key` before the fix.
- **The member catalog was duplicated in three places** once `manager` needed to read it.
  Extracted to `theteam.BASE_MEMBERS` / `FOCUS_MEMBERS` / `FOCUS_FLAG_BY_MEMBER` at module
  scope, which is also what makes the catalog the roster cap. The generated roster is
  byte-identical before and after the extraction.

**End to end**, with a recording provider in `run_discussion`:

```
roster before:            [architect, pragmatist, skeptic, designer, devops]
manager --topic:          proposed 1 addition; nothing written yet
roster after propose:     [architect, pragmatist, skeptic, designer, devops]   (unchanged)
manager --topic --apply:  roster grew to 6
roster after apply:       [architect, pragmatist, skeptic, designer, devops, security]
discuss "auth token...":  Selector chose 1 member(s): security   -> spawned: [security]
```

**Which store the roster lives in — measured, because there are two.** `run_discussion`
reads `theteam.config` through `load_config`; `CommentaryController` reads
`<state_dir>/roster.json` through `advisory/roster.py`. The manager writes `theteam.config`,
which is the store the `discuss` and `manager` commands actually read. Growing `roster.json`
instead would have left `theteam discuss` spawning the same old members while the command
reported success. The two-store split is pre-existing and is recorded in Part 9; this
milestone did not merge them.

`816 passed` (789 + 27 new), gate 7/7, `import theteam` succeeds.

## M9 Phase 3 — Context efficiency

`theteam/__init__.py:93` did `yaml.dump(project_context)` into **every** member's prompt, so
the same tokens were paid N times. Measured on this repository: **2,499 characters per
member, 12,495 across a 5-member roster**, of which `runtime_config` alone was 1,272.

`advisory/context_slice.py` delivers the sections a member's declared focus implies. After:

```
                before    after
architect        2499     1398     (runtime_config: architecture, contract, layering)
pragmatist       2499      126
skeptic          2499      126
designer         2499      126
devops           2499     1398     (runtime_config: ci, infrastructure, stability)
                -----    -----
total           12495     3174     75% less
```

**There are no flags in the context, and the milestone assumed there were.** §M9 says "slice
`project_context` per member by the flag its focus implies", but
`aggregate_project_context` returns `project_goal`, `runtime_config`, `token_budget`,
`registered_structure`, `last_health_scan`, `production_invariants`, `timestamp`,
`project_root` — no `security_focus`, no `database_focus`. Those flags come from
`analyze_project_context` and decide the **roster** (`manager.py` reads them). So the phase
means slicing by *section*, matched against the member's declared vocabulary.

**A single incidental token is not evidence, and the milestone's own instruction covers it.**
§M9: "add an explicit mapping only if the match proves unreliable in testing." It proved
unreliable. An unfiltered match carried `runtime_config` — 91% of a member's whole budget —
to four of five members on the strength of `scope` and `reviewer` appearing once in a
package description. `MATCH_THRESHOLD = 2` requires corroboration: 75% saved instead of 39%,
and `runtime_config` reaches only the members matching on multiple terms. The fix is a
threshold, **not** a hand-written section-to-member table — a mapping would be a second
source of truth beside `FOCUS_TOKENS`. Pinned by
`test_the_threshold_is_two_matching_tokens`.

**Stop words were removed first, and the measurement shows it was not sufficient.** The
unfiltered match carried `runtime_config` on `in` (from "pack**in**-module scope"), `and`,
and `for`. Filtering those via the selector's existing `STOP_TOKENS` left only real words —
but not few enough, which is what the threshold addresses. Both changes reuse the selector's
tables rather than re-declaring them; a second copy of "what summons the architect" is the
dead end `selector.py:201-207` records.

**A section delivered to nobody is reported, not dropped.** Every discussion now prints:

```
context section 'production_invariants' reached no member (all 5 missed it)
context section 'registered_structure' reached no member (all 5 missed it)
```

Both are genuinely orphaned on this roster — `production_invariants` is config settings and
`registered_structure` a directory listing, neither matching any member's declared
vocabulary. The report is the feature working: §M9 asks for it precisely so a member cannot
silently stop knowing something. `timestamp` is dropped by design and is never reported,
because delivering it would make two identical discussions produce two different prompts.

`836 passed` (816 + 20 new), gate 7/7, `import theteam` loads 88 modules (budget 90).


## M9 Phase 4 — Prompt-shaped work as registered tasks

A second kind of task phase. `script:` runs a Python file; `runner: llm` hands a
`prompt_file` to a team member. Both share the executor, the breaker, and the
`ok`/`failed`/`skipped` outcomes, so a run of the two kinds is indistinguishable
from outside except by what it produced.

**The three commands §M9 names, measured:**

```
theteam run --only ground-truth-audit
  -> {"ran": 1, "failures": 1, "results": [{"id": "ground-truth-audit",
       "result": "failed",
       "detail": "llm runner requires an OMP session (phase 'audit'). Run this
                  inside an OMP session, where a task provider is bound."}]}
     exit 1
theteam tasks  ->  7 tasks, 7 in YAML
theteam run     ->  nothing due, exit 0
```

**A missing provider is a named failure, never a synthesized result** — the M0
defect in a new place. The prompt is real and the member is not; producing
something anyway is `MockAPI` with a different signature. Falsified by
`test_the_llm_phase_outside_omp_*`: the result is a failure, and **no output file
is written** (asserted, because "no file" is the part a stub would fake).

**Two decisions the spec left open, answered from the code:**

- **`--only <id>` now bypasses the schedule.** It previously filtered the *due*
  set, so naming an unscheduled task reported `nothing due` — which made every
  one of these three commands inert on a project where the user had never run
  `theteam loop`. An explicit id is the request; a schedule is what makes a task
  due *without* being named. `due()` still advances nothing, so §7.1.4
  idempotence is untouched.
- **Outside OMP, exit 1** rather than a skip, because the task did not do its
  work and a `ran: 0` reads like success-ish.

**Three defects found while building it, all pre-existing:**

1. **The three task files were invisible.** `repository.py:148` only reads
   names starting with `task-`, so `tasks/ground-truth-audit.yaml` was never
   loaded — `theteam tasks` showed 4 and `--only ground-truth-audit` resolved to
   nothing. Renamed to `task-ground-truth-audit.yaml` (id unchanged) rather than
   weakening the prefix guard, which exists because `tasks/SECURITY_POLICY.yaml`
   is not parseable YAML.
2. **A failed run recorded no reason.** `cmd_run` built the failure detail from
   `returncode`, which an `llm` phase does not have, so the recorded detail was
   `returncode None` — a reason that explains nothing, on exactly the path §3.3
   governs. The detail now comes from the phase's own `error` when it has one.
3. **`theteam run` returned 0 on failure.** A shell could not distinguish a red
   suite from a green one without parsing JSON. It now returns 1, which §2.1
   already names. **This is a behaviour change for the pre-existing four tasks**
   and is called out in §2.

**The missing-script check did not weaken.** A phase naming neither runner is
refused by name (`phase 'x' names no runner: needs script or runner: llm`)
rather than becoming a silent skip, which is the hole §3.3 forbids: a check
that only understood `script` would have turned every llm phase into a
"missing script" skip.

**`native-feature-loop` keeps its test phase a `script:`** (skeptic recon →
pragmatist implement → **pytest** → doc sync), through a new
`scripts/run_pytest.py` that propagates pytest's real exit code. A test suite is
deterministic and must not be judged by a model; a wrapper returning 0 on
failure would make the task report success for a red suite.

`execute_phase` gained a `task` parameter rather than reading instance state —
`self._current_task` would have been undefined, and state outliving one task is
wrong anyway. Three test stubs that mirrored the old one-arg signature were
updated to match.

`859 passed` (836 + 23 new), gate 7/7, `import theteam` loads 88 modules.



## M11 — The headline command could not run

`theteam discuss` is the skill's primary command. It crashed on its third statement, and
when it did not crash it silently persisted nothing.

### Two hard defects in one function, 653 tests green

`run_discussion` reached `DiscussionState.start_discussion`, which calls
`self._notify_listeners` — a method defined only on `UnifiedStateManager`, never on
`DiscussionState`, `SystemAwarenessState` or `TaskState`. Ten call sites, zero definitions:

```
AttributeError: 'DiscussionState' object has no attribute '_notify_listeners'
```

Fixed with a `_Notifying` mixin: a no-op default, because an unobserved state transition
is a legitimate state of the world rather than an error, plus injection of the manager's
real notifier so a listener registered with `add_listener` still fires. **No `try`/`except`
was wrapped around the call sites** — that is the §3.3 defect class. All three pre-existing
Pyright errors on the file are now gone because the call sites were corrected, not
suppressed.

### `save_state` was reachable, and worse

`run_discussion` calls `save_state` at line 954, at the end of the same function. Not
latent. It was broken three ways:

| | Defect |
|---|---|
| 1 | called `wal.log_state_change`, which does not exist; the real method is `append_entry` |
| 2 | called `checksum.add_checksum(state_data)` and **discarded the return value** — `add_checksum_to_state` returns a new dict, it does not mutate |
| 3 | `except Exception: logger.error(...)` swallowed both |

Measured before the fix: `start_discussion` then `save_state` left **no file on disk** and
returned normally. The command would have printed a synthesis, named a recommendation,
written its report, and reported success having persisted zero state.

`load_state` had the mirror image — `verify_checksum` does not exist, so every load raised
inside the same swallowing `try` and restored nothing. A corrupt state file and a fresh
project were indistinguishable. It now raises a named `ValueError` on mismatch and uses the
same `ChecksumManager` API the writer uses, so a file written by `save_state` verifies.

### `run_discussion` had never been tested

The cause is structural: `_require_provider()` makes `theteam discuss` refuse cleanly
outside OMP, so no smoke test outside a session reaches any of this code.

`theteam/tests/test_run_discussion_e2e.py` drives the whole function with a stub
`default_api` — selection, intros, synthesis, report, save, reload. The fixture bootstraps
via `bootstrap_flow` instead of hand-writing a config; the hand-written version failed with
`KeyError: 'behavior'`, which is precisely how a fixture drifts from the schema and starts
testing something the product never produces.

**Both regressions are proven to bite**: reverting the mixin fails 7 tests, restoring
`log_state_change` fails 3.

**And the reader test had a hole of its own.** The reload test asserted
`discussion_history` and `task_history`; deleting the `active_discussions` restore from
`load_state` still passed it. The reason is not subtle: after a completed discussion both
`active_discussions` and `task_assignments` are **empty**, so comparing them against the
on-disk value cannot distinguish "restored correctly" from "never assigned". Two of five
mutated restores were invisible.

Fixed by a test that writes known values into every field before saving, so each restore is
exercised with something to restore. Measured after the fix: removing any of
`active_discussions`, `discussion_history`, `current_discussion_id`, `task_assignments` or
`tasks` fails. All five are pinned; before, two were not.

`load_state` itself was never wrong — it restores all ten fields. The defect was a reader
test that could not see half of them, which is the same class of problem as the defects it
was written to catch.

### The singleton ignored which project it was asked about

Chasing the reader tests further found a third defect, in `get_state_manager`. It ignored
`state_file` on every call after the first: the process-wide singleton was built with
whichever path happened to arrive first, so a later call naming a **different project**
returned a manager still bound to the first one.

Measured before the fix: two calls with two different paths returned the *same object*, and
the second still pointed at the first project's file — reading it, and writing to it on the
next `save_state`. Nothing in the return value said so.

A differing path now rebuilds the manager and reloads; the same path still takes the cheap
path, which is what the hot path needs (`run_discussion` calls it once per run). The
superseded monitoring thread is left to exit on its own — it is a daemon that sleeps
between sweeps, so joining it would block the caller.

**The first version of that test still had a hole, and it was mine.** It drove two real
discussions and asserted project B did not contain project A's topic — but
`run_discussion` calls `get_state_manager` itself, so by the time the test called it, B's
state was already in memory. The assertions were reading memory the product had just
written, not state loaded from disk. A mutation that rebuilt the manager **without
reloading it** still passed.

The fix is to drop the in-memory manager (`_state_manager = None`) and read B back cold.
Measured after that, all three mutations fail: rebind-without-reload, no-rebind-at-all, and
always-rebuild (which would break the cheap path the hot path depends on).

**Then the cold load was hardened once more**, because passing for the right reason still is
not the same as being able to fail for the right reason. The cold test caught a
rebind-without-reload mutation only because B's own discussion was missing — had
`run_discussion` simply failed to write B, the test would have passed vacuously.

B is now seeded on disk and never written by the test, so the only way `SEEDED` can reach
memory is a real `load_state`. Under that mutation the failure names the value:
`assert [] == ['SEEDED topic for B']`. Four mutations now fail: rebind-without-reload,
no-rebind, always-rebuild, and a `load_state` that silently restores nothing.

**A sharp edge found while seeding, recorded not fixed:** `save_state` does not create its
directory. `StateStore.__init__` does (`state.py:128`), and every product path reaches it,
so nothing in the product is affected. But a direct `UnifiedStateManager(path).save_state()`
into a missing directory raises a raw `FileNotFoundError` from `open`. That is a named
error rather than a silent one, so it is not a §3.3 defect — just worth knowing.

**And the tests were leaking the singleton into the rest of the session.** The rebind test
pointed the module global at a `tmp_path` project and never put it back, so a later test
could inherit a manager whose `state_file` no longer existed — the failure then lands
somewhere unrelated to its cause. The full suite happened to stay green, which is ordering
luck, not correctness.

The fix is an `autouse` fixture that saves the prior value on entry and restores it in a
`finally`. A per-test reset at the top of the test body is not equivalent: a setup reset
restores the *entry* state, never the exit state, which is exactly why the leak survived
three earlier revisions of the test.

Proven with a probe test that observes the global after the e2e file runs: with the fixture,
7 pass; with it stripped, the probe fails with a singleton pointing at a deleted directory.

Recorded because the lesson is not specific to this test: *a test that runs the product and
then inspects the same process's memory has not tested persistence at all.*

**On the framing of the original suggestion.** It proposed seeding `discussion_history`
with a distinct pre-existing value before reload, on the premise that a fresh manager is
already populated. It is not: `DiscussionState.__init__` sets `discussion_history = []`, and
the mutation test confirms the non-emptiness assertion does fail when the restore is
removed. The suggestion did identify a real untested property underneath, though — whether
`load_state` **overwrites** rather than accumulates — and because `get_state_manager` is a
singleton, an already-populated manager is the *normal* case in production. That is now
tested with sentinel values, and the sentinel test is what exposed the singleton bug above.

One assertion of mine was wrong and is recorded as such: I first asserted the discussion
task would be in `task_state.tasks`. It is not, and should not be — `update_task` moves a
task to `task_history` and deletes it on `completed`, which `run_discussion` does before
saving. The test now asserts history.

### Roadmap corrected against measurement

`archive/STABILITY_ROADMAP.md` had **nine** boxes marked `[X]` on the strength of a file
existing rather than a caller existing. The rule now applied: **a box is `[X]` only when a
named, currently-passing check confirms it.** Final tally: 33 kept, 4 `[~]` qualified
(exists, wired to something with no production caller), 4 `[ ]` reopened.

The interesting failure was not staleness but **wiring through a dead module**.
`event_log.py` and `rate_limiting.py` are imported — by `event_bus.py`, which has zero
production importers. Literally true, operationally false. That is the shape of claim that
let three schedulers coexist unnoticed for nine milestones.

I made the same mistake while correcting it: marked `resource_limiter.py` `[X]` citing
`tasks/executor.py`, which names `ResourceLimiter` twice — in **comments** (lines 31, 50),
not imports. Corrected to `[~]`.

### Result

```
656 passed in 13.14s
invariant gate PASSED (7/7)
import theteam: 88 modules (budget 90)
```

Up from 653: 7 state-manager tests and 3 end-to-end tests, for a file that had zero
coverage and a function that had never been called.

## M10 — One scheduler

Three schedulers existed. One worked. `theteam loop` + `theteam run` schedule and execute
YAML tasks through `TaskRepository` and `TaskExecutor`; the other two had no reachable
caller. This milestone collapses them to the one that works and rebuilds `theteam serve`
on it.

### Phase 0 — Baseline, captured before anything changed

| Datum | Value |
|---|---|
| Test suite | 859 passed |
| `import theteam` | 12 `theteam.*`; +cli 14; +terminal 26 |
| `serve` startup | binds, publishes 1063 bytes of `/metrics` |
| `serve` task counters | `tasks_started 0.0`, `tasks_completed 0.0`, `tasks_failed 0.0` |

Those zeros are the evidence the whole milestone rests on. `serve` constructed a
`UnifiedLoop` and nothing ever called `add_task`, because its only producer,
`integrated_orchestrator.py`, had no importer. The endpoint published a static snapshot
of a scheduler with no input.

### Phase 1 — `run_due_tasks()` extracted, behaviour-identical

`cmd_run` carried ~80 lines of inline scheduling: the breaker-state handoff, the
one-runner-per-phase gate, skip-versus-failed recording, the `ran`/`skipped`/`failures`
tally. `serve` has to execute identical work or the two paths drift, so it became
`run_due_tasks(project_root, only)` and `cmd_run` is now a parser and an emitter. The
`Task not found` named failure stays in `cmd_run` because it is a *command* failure.

Verified byte-identical: same payload keys, same exit codes, `ran: 0` twice for an
empty project, and a real task executing through docker isolation.

### Phase 2 — 17 unreachable modules deleted

Selected by AST scan for imports at any nesting level, intersected with a runtime
`sys.modules` check across all three entry points. `integrated_orchestrator`,
`system_integration`, `state_validator`, `schema_versioning`,
`workflow/discussion_interface`, `workflow/team_member_manager`,
`workflow/discussion_manager_refactored`, `core/team_member_manager`,
`advisory/commentary`, `ui/components/{reflex_renderers,visibility}`,
`bin/theteam_report`, `bin/utilities`, `skill/SKILL_metadata` and four empty shells.

Three findings worth keeping:

- **`bin/utilities.py` looked dead and was not.** `theteam_config.py` imports it as
  top-level `bin.utilities`, which the AST scan missed because scripts run with
  `PYTHONPATH=theteam`. Deleting it broke `import theteam` outright.
- **`core/__init__.py`'s `_LAZY` map still named `system_integration`.** Left alone it
  turns `from theteam.core import SystemIntegration` into a `ModuleNotFoundError` from
  inside `__getattr__` instead of the `AttributeError` the contract promises.
- **`advisory/commentary.py` was restored, not deleted.** `ARCHITECTURE.md:753` already
  recorded that `CommentaryController` has no caller outside tests, and an advisory
  argued it was the M9 deliverable. It is not: M9's six phases are the selector, the
  manager, context slicing, `runner: llm`, diagrams and docs, and wiring the controller is
  not among them. But it is designed-and-tested M5 product intent, not scheduler rot, so
  it is out of this milestone's scope and was put back.

Broadening `test_stability_fixes.py::TestTestIsolation` from one named file to the whole
suite — and from a substring search to an AST walk, so a module-level insert is
distinguished from one inside a function — immediately caught a real leak:
`test_theteam.py` had three unguarded `sys.path.insert` calls. Two were noise; the third
existed to reach `scripts/test_utils.py`, which moved to `theteam/tests/` and is now
imported through a single documented insert.

### Phase 3 — `routine-engine/` deleted

276 KB, 18 tracked files. Zero references from `theteam/`, absent from `pyproject.toml`'s
`packages.find include = ["theteam*"]`, and no test collected it. It duplicated
`theteam/tasks/` function for function: `should_execute` ≈ `due()`, `execute_phase` ≈
`execute_phase`, `safety/rollback.py` ≈ breaker + backup.

It also already owned the word *routine*, which is why `theteam loop` was **not** renamed.
The command schedules one task once and prints `next_run`; it does not iterate, so
`routine` would promise a repetition it does not perform — and would collide with
`RoutineScheduler`, `run_routine` and three `routines/*.md` in a subsystem with a
different data model. If the name ever reads wrong, `schedule` maps 1:1 onto
`TaskRepository.schedule_task`.

### Phase 4 — `serve` rebuilt as a scheduler

`tasks/scheduler.py` owns a clock and nothing else: `run_due_tasks` is injected so it does
not import the CLI. `MetricsCollector.collect()` is duck-typed on `.metrics`, `.tasks`,
`.circuit_breaker` and `.health_monitor`, so the scheduler satisfies it with no change to
`metrics.py` and no second mapping of metric names to producers.

Proven live, not asserted. A task scheduled at `--interval 1` was picked up unattended by
`serve --tick-seconds 2`, executed inside container isolation, and recorded:

```
theteam_tasks_completed 1.0     theteam_tasks_failed 0.0
theteam_tasks_active 1.0        uptime 90.8s
history: runs 1, successes 1, success_rate 100.0, breaker closed
```

Baseline for the same measurement was `0.0` forever.

Two fixture errors surfaced along the way and are worth recording as *my* errors, not the
product's: the first probe wrote to a host `/tmp` the container cannot see, and the second
passed a shell script to `python3`. The read-only `/workspace` mount that rejected the
third attempt is the isolation boundary working correctly.

### Phase 5 — `unified_loop.py` and `task_contract.py` deleted

With `serve` rebuilt, `UnifiedLoop` had no caller. The pair referenced only each other and
was removed together, with `test_final_validation.py` (188 lines, one collected test, every
assertion about a deleted class).

`test_audit.py`'s audit-sink regression was **ported, not deleted**: it defends that
observability failure must not become control flow, and `UnifiedLoop.add_task` was only its
vehicle. It now drives `TaskScheduler.tick`, and a second test covers a raising
`run_due_tasks`. Writing it honestly caught a bug in the port — `start()` fires an
immediate sweep, so the explicit `tick()` double-counted and the assertion read `2.0 == 1.0`.

`test_backup.py` had `SOURCE_FILE = "theteam/core/unified_loop.py"`. The test creates the
file in a tmp tree so it stayed meaningful, but it now names a real module.

### Three modules that lost their importer, recorded not deleted

Deleting `unified_loop.py` removed the last in-package importer of three modules. They are
three different situations and are recorded individually in `ARCHITECTURE.md` §5.2.1:

- **`backup.py` is live.** `scripts/backup.py` is an operator CLI over it. Verified by
  running it: `Backup created: /private/tmp/bk/backups/backup_20260930_194816`. This one
  nearly got deleted on a wrong reading, and the AST scan had called it orphaned.
- **`event_bus.py`** is the mechanism §5.1 names, not a file. Deleting it takes
  `event_log.py` and `rate_limiting.py` with it.
- **`health_monitor.py`** has no importer, but `health_dashboard.py` reads a health score
  from whatever it is handed and is currently handed nothing. The fix is wiring.

### Diagrams

The **architecture** diagram is current: `TaskScheduler` added and repinned to
`ed4dcee1`, `validate` returns `ok: true` from the repo path with 9/9 artifact checks,
0 errors, 13 references verified, and `visual-check` passes with real Chrome at every
viewport.

One caveat on that receipt: the validator checks that each source **file** exists at the
pinned revision. It does not check that the line number names the declared label — a
deliberately wrong line number produced zero errors. The line was corrected by hand to the
measured 32.

The **milestone** diagram is frozen at seven milestones. This is a tool defect, not a
layout problem, and it is measured: `archify validate workflow` fails on the *committed*
7-node source as-is, with a `viewBox` of 1691×528 that projects node text to 11.9px against
a 6px floor — a projection that should pass. An 11-milestone source with M7–M10 was built
and every layout variant tried (9/4/3/2 lanes, widths 190–230px, shortened labels,
columns reduced to the six the checker seats) either collided or failed the same check; the
best variant projected 11.92px label and 9.37px sublabel. Both committed files were
generated by `archify 2.17.0-dev.1` and the installed skill no longer agrees with that
version. The HTML and JSON are a consistent pair and the gap is recorded in
`ARCHITECTURE.md` §1.

### Result

| | Before | After |
|---|---|---|
| Schedulers | 3 | 1 |
| Files deleted | — | 45 (≈15,700 lines) |
| Package modules | 66 | 53 |
| Tests | 859 passed | 646 passed |
| `serve` task counters | `0.0` forever | reports executed work |
| Import budget | 88 / 90 | 88 / 90 |

The test count fell because 213 tests covered code that no production path reached. That
is deletion, not regression: the suite is green, `check_invariants.sh` passes 7/7, and
`import theteam` is unchanged at 88 modules.

## M9 Phase 5 — Diagrams

`diagrams/active-usage-architecture.json` / `.html` re-derived from the M9 source. The three
things §M9 says change, all present: the discussion path is **select-then-spawn**, not
spawn-all; `theteam manager` is a node between the CLI and the roster; and `runner: llm` is a
second phase kind beside `script:`, with `AgentIsolation` reachable only from the script path.

**Delivered with evidence, not assertion:**

- `node bin/archify.mjs validate architecture ... --repo-root <repo>` → `ok: true`,
  validating from the committed repo path, not a scratch copy.
- `deliver` → 9/9 artifact checks, 0 errors, `evidence.verified: true`, pinned to revision
  `2fab70a0`, with all 12 source references verified against the checkout.
- `visual-check` with a real Chrome → `overall: true`, **no overflow at 1440×900, 1600×1000,
  1920×1080 or 2048×1320** (an earlier 18-node draft measured 1622px of content in a 900px
  viewport and failed containment; it is not what shipped).

**Where the tool is.** `archify` is not a dependency of this package — there is no
`node_modules/`, no `archify` script in `package.json`, and M7's README reference to
`npm install -g @oh-my-pi/archify` described a package that does not exist. It ships as an OMP
skill at `~/.omp/agent/skills/archify`, driven as
`node bin/archify.mjs {validate,deliver,visual-check}`. `visual-check` additionally needs a
Chrome binary; this machine's is at
`~/.cache/puppeteer/chrome/mac_arm-*/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`,
passed through `ARCHIFY_CHROME`. Without it `visual-check` reports every viewport as `skipped`
and returns an error, which is not a pass.

**The milestone diagram was not updated, and that is a real gap.** It still carries the
M7 source (7 milestones) as its `.json` while the `.html` renders 10 nodes including M7, M8
and M9 — the source and the artifact disagree, and ARCHITECTURE.md:12 makes that a defect. I
did not resolve it: the ten-milestone layout failed validation repeatedly
(`desktop-readability` at 5.86px projected against a 6px floor, and a
`viewBox capacity` minimum of 1269px that conflicts with the readability ceiling of 1240px),
and the archify skill's stop rule says to report rather than keep tuning. Reconstructing the
JSON from the rendered HTML got as far as the measured M7/M8 gap — 46 rendered pixels, which
is not the `yOffset` unit the schema wants — before I stopped.

**What this means for a reader:** the milestones diagram understates the delivery, and its
JSON is not the source of its HTML. The architecture diagram carries M9's story correctly.
Fixing the milestone pair is open work, recorded here rather than left as a silent
inconsistency.

**One process note worth recording.** `deliver` writes only the HTML. The JSON beside it is
not updated, so shipping a diagram and syncing its source are two steps, and the first is
easy to mistake for the second. The architecture pair is synced; the milestone pair is not.

## M8 — The docs tell the truth, and one of them is a lie in the code

A follow-up audit, run after the `--monitor` flag landed. The M7 report claimed `--monitor` was
undocumented in both `README.md` and `ARCHITECTURE.md`; it was already documented in both, in
detail. The real findings were elsewhere. Most were documents disagreeing with the code. The last
one was the reverse — and it was the only one that mattered, because it was a control promising
an effect it did not have.

- `--monitor` was missing from `theteam/CLI.md`'s command table. It is the only doc of the three
  that enumerates the surface, and it listed the flag nowhere. Now documented there, with a
  pointer to the full semantics.
- **Stale counts.** `README.md` said 744 tests and "6 checks"; `theteam/ONBOARDING.md` said 744
  tests. The measured numbers are **772** and **7** (gate check 7, the import-graph budget, was
  added in the M7 review and the docs were never updated for it).
- **`ARCHITECTURE.md:14` claimed "Nothing is implemented past M0."** Six milestones and a
  documentation milestone have shipped since. The line was a leftover from the draft, in a
  document whose first page is otherwise accurate.
- **Four wrong rows in the §5.2.1 reachability table**, each verified by grep before correction:
  `audit.py` was attributed to `tasks/audit_chain.py` (it lives in `core/`; `tasks/` has no such
  module), `audit_chain.py` was attributed to `tasks/executor.py` only (five importers),
  `team_member_manager.py` to `workflow/discussion_manager_refactored.py` (it is
  `workflow/discussion_interface.py` that imports it), and `unified_loop.py` to
  `theteam/__init__.py` (nothing there imports it; `cli.py` and `integrated_orchestrator.py` do).
  `task_contract.py` and `backup.py` were also wrong and were corrected in the same pass.
- **Part 8 listed `StateStore` as a component "verified absent from the entire tree."** It is
  `theteam/state.py:35`, and every path in the product resolves through it. Conversely it listed
  `SimpleTaskExecutor`, `SimpleTaskScheduler`, and `InMemoryTaskStore` as real components the
  diagrams missed; none is in the tree, and `git log -S` finds each only in the commit that
  deleted it. Corrected in place, with the correction stated.
- **`SKILL.md` claimed the selection prompt presents four options "defined in `selection_options`
  (see `theteam.config`)."** It does not: the key is optional per `REQUIRED_TOP_KEYS`, absent
  from both the shipped template and this project's config, and `theteam/__init__.py:692` carried
  a divergent three-option fallback. An agent following SKILL.md literally would show the user a
  prompt the code never produced.
- **That prompt lied, and it is deleted.** `run_discussion` offered "Abort Discussion — Stop the
  current discussion loop", printed the answer at `__init__.py:712`, and then ran the discussion
  to completion regardless, under the comment "For now, we'll proceed with a default path." A
  control that reports an effect it does not have is the `MockAPI` defect class §3.3 forbids, so
  this was a code defect the documentation pass uncovered, not a documentation defect.
  `run_discussion` no longer offers a choice: the `ask` call, the three-option fallback, and the
  `option_selection_required` gate that drove them are gone. `SKILL.md` step 3 is now a plain
  gate, and the discussion's step list was renumbered 1–10 after removing the one that described
  the prompt. `option_selection_required` is no longer required by the schema and is no longer
  emitted by bootstrap or the template, but the validator ignores unknown keys, so every config
  written before this change still validates — verified against this project's own config, which
  still carries the key. Falsified: `theteam discuss` outside OMP still raises
  `ProviderUnavailable` naming the OMP requirement, and `grep -rn "Abort Discussion" theteam/`
  returns nothing outside `CHANGELOG.md`.

`772 passed`, gate 7/7.

## M7 — The documentation tells the truth

Every document audited against the code it names. Where a document and the code disagreed, the
code won and the document changed.

- `README.md` rewritten. It previously documented `src/`, `tests/`, `config/`, PostgreSQL,
  `npm install -g @oh-my-pi/archify`, `npm run test:archify`, five deleted
  `diagrams/*-candidate.json` files, and `python -m src.main`. None of those exist. It now
  carries the complete command surface, exit codes, environment variables, and the output
  honesty contract, plus the plan evaluation.
- **Code change:** `theteam watch` gained `--json` on its own subparser. It was the one command
  whose `--json` had to precede the subcommand, because it was declared only on the parent —
  `theteam watch status --json` was a usage error. `cmd_watch` gained the branch that prints
  the payload the frame draws. This is the one code change the milestone made, to satisfy a
  documented promise; everything else was documents and diagram JSON.
- `ARCHITECTURE.md` Part 2 completed: `loop` was implemented (`cli.py:158`) and documented
  nowhere. Exit codes, failure shapes, and the environment variables added as §2.1 and §2.2.
- `diagrams/active-usage-milestones.json`: added `m6` and the `m5 → m6` edge, a `Terminal`
  lane, and the "Seven milestones" subtitle. The diagram had stopped one milestone behind the
  plan.
- `diagrams/active-usage-architecture.json`: re-derived from the actual import graph. Its
  subtitle grounded itself in `theteam/subskills/task_stack`, deleted in M2, and its components
  listed `TaskStore` and `TaskManager`, which are not modules in the tree. Every component now
  cites the file it came from, verified against git.
- `theteam/CLI.md` rewritten against the parser. `theteam/README.md` reduced to a pointer.
  `theteam/ONBOARDING.md` rewritten; it named a deleted daemon, TUI, and `loop_controller.py`.
  `theteam/SKILL.md` corrected: the `.omp/theteam/tool-manifest.json` it told the agent to
  read does not exist, and the `bin/` scripts need `PYTHONPATH=theteam`.
- Seven pre-M0 reports archived to `archive/docs-theteam/pre-m0-reports/`.

## M6 — The terminal shows the truth

`theteam/ui/terminal.py` and `theteam watch status|tasks|history`. Deferred by the M5 review
until after M4, so that what the renderer displays is real. Stdlib only: `rich` is installed
transitively in one developer's environment and declared nowhere, so a module-scope import is
green locally and red in CI. The same measurement found that `pyproject.toml` declared no
dependencies while `theteam/__init__.py` imports `yaml` at module scope, and fixed it.

The invariant test: in a project with no audit chain and no run tasks, the frame shows `absent`
and `never run`, and never the literal `closed`, `intact`, or `0%`.

## M5 — The team comments

`advisory/` with `session_reader`, `selector`, and `commentary`; `theteam comment on|off|status`.
Conditional on three gates: the session reader's digest must change when a real session changes;
the selector must pick different members for a frontend and a database session; a tick must
produce at most two fragments. The one-shot discussion path, `run_discussion()` in
`theteam/__init__.py`, is byte-identical before and after — if it had changed, the controller
would have forked the discussion path.

## M4 — The loop is safe

`CircuitBreaker`, `ResourceLimiter`, and `AgentIsolation` wired into execution for the first
time; `AuditLogger` into the task lifecycle; the execution log bounded; `theteam history` added.
`AgentIsolation` had been written and had no caller, which was the standing risk in a system
that runs project scripts.

Falsified: a task failing five consecutive times trips a breaker; a phase exceeding 64 MB is
killed at exit 137 rather than left running.

## M3 — Create, edit, delete

The single-task write surface, validated at write time rather than at run time. `task create`
rejects an invalid definition before it reaches disk.

## M2 — Tasks are YAML

One task store, in your repo. The legacy loader and the `subskills/task_stack/` tree were
deleted, taking `task_stack_adapter.py` with them — the adapter existed only because two task
stores did.

## M1 — Reach it from a shell

`cli.py` as the single entry point, one state-directory resolver replacing hardcoded absolute
paths, and `theteam bootstrap`. `__main__.py` was deleted here, which is why
`python -m theteam` does not work.

## M0 — The team cannot lie

`MockAPI` removed, along with every code path that could return a plausible-looking value on a
failure path, and the planning documents that described a system that was never built. This is
the milestone every later one assumes: the product's core failure was not a crash, it was a
system that returned confident output with nothing behind it.
