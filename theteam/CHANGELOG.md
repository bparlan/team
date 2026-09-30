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


## M9 Phase 5 — Diagrams

`diagrams/active-usage-architecture.json` / `.html` re-derived from the M9 source. The three
things §M9 says change, all present: the discussion path is **select-then-spawn**, not
spawn-all; `theteam manager` is a node between the CLI and the roster; and `runner: llm` is a
second phase kind beside `script:`, with `AgentIsolation` reachable only from the script path.

**Delivered with evidence, not assertion:**

- `node bin/archify.mjs validate architecture ... --repo-root <repo>` → `ok: true`,
  validating from the committed repo path, not a scratch copy.
- `deliver` → 9/9 artifact checks, 0 errors, `evidence.verified: true`, pinned to revision
  `2fab70a0`, with all 18 source references verified against the checkout.
- `visual-check` with a real Chrome → `overall: true`, **no overflow at 1440×900, 1600×1000,
  1920×1080 or 2048×1320** (an earlier 18-node draft measured 1622px of content in a 900px
  viewport and failed containment; it is not what shipped).

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
