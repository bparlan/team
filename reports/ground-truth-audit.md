> Copied from `.omp/theteam/reports/` on 2026-10-01. That path is gitignored as
> runtime state, so the reports live here to survive a fresh clone. The
> originals remain in `.omp/theteam/reports/` and are the ones the tasks write.

# Ground-truth audit — second pass

Reconnaissance only. Every finding below was checked by reading the cited source, not by
inferring from the claim's own wording. This pass audits the tree **after** the harmonization
described in `reports/doc-harmonization.run1.md`, so the primary question is
whether that phase made the documents true and whether it introduced new drift.

Scope read in full: `README.md`, `ARCHITECTURE.md` (1314 lines), `theteam/README.md`,
`theteam/CLI.md`, `theteam/ONBOARDING.md`, `theteam/SKILL.md`, `theteam/CHANGELOG.md`
(partial), `tasks/README.md`, `scripts/check_invariants.sh`, `scripts/smoke_cli.py` (partial),
`.github/workflows/ci.yml`, `pyproject.toml`, both `diagrams/*.json`, both
`diagrams/*.html` (structurally), and the source named by each finding.

---

## Verdict on the harmonization

**All 9 run1 findings that were acted on are correctly fixed. I re-verified each against the
code, not against the harmonization report, and found no wrong correction, no incomplete
correction, and no new falsehood introduced inside any corrected passage.** The specific
concerns this pass was asked to look for — a corrected line sitting inside a paragraph that
still contradicts it, a table row or cross-reference left behind — did not materialise in
any of the five edited documents.

That is the headline result. The findings below are **pre-existing drift the run1 pass did not
reach**, in areas run1 explicitly declined to read (the diagrams, `tasks/README.md`, the
M9/M10/M11/M12 milestone prose). Four of them are new since run1 only in the sense that no
earlier pass looked there; the tree has not changed under them.

Two run1 items remain open and are restated below for the record, not as new findings:
`ARCHITECTURE.md:341` (live-session statistics) is still unmeasurable here, and
`scripts/smoke_cli.py`'s check count is now measured (§ "Verified accurate", below — it is
wrong).

---

## Findings

### `ARCHITECTURE.md` says the milestone diagram's HTML and JSON agree; they do not
- **Claim:** "**The milestone diagram is frozen at seven milestones**, and its HTML and JSON agree." — `ARCHITECTURE.md:26-27`
- **Code says:** `diagrams/active-usage-milestones.json` carries **11** nodes (`m0`–`m10`), a subtitle of `"Eleven milestones, each a runnable command with a falsification test"`, and 10 edges. `diagrams/active-usage-milestones.html` carries 7 `data-node-id` values (`m0`–`m6`) and no occurrence of `m7`–`m9` as a node. The JSON is newer: `stat` reports `json 2026-09-30 23:12:18`, `html 2026-09-30 23:05:07`.
- **Difference:** A reader who opens the pair as the document tells them to finds the authoritative JSON carrying four milestones the rendered view cannot show — the exact `M6`-was-absent defect README's own Plan-evaluation table records being fixed in M7 (`README.md:250`), reintroduced for M7–M10.
- **Confidence:** verified

The surrounding paragraph makes this worse, not better. `ARCHITECTURE.md:20-25` says an
11-milestone JSON "was built" and every layout variant failed — so the JSON is described as a
discarded experiment, while in the tree it is the committed authoritative artifact. The same
sentence at `ARCHITECTURE.md:30` says the *architecture* diagram's "pair is synced", which is
true (`ARCHITECTURE.md` diagram json and html both carry the same 13 component ids, verified).
The milestone claim is the one that is false.

### `README.md` says the milestone diagram renders M0–M6; the JSON says eleven
- **Claim:** "| Delivery order | M0–M6 and their gates | [`diagrams/active-usage-milestones.html`](diagrams/active-usage-milestones.html) |" — `README.md:202`
- **Claim:** "Both diagrams are generated from the JSON next to them. **The JSON is authoritative; the HTML is the rendered view.**" — `README.md:204-205`
- **Code says:** Per that stated conflict order, the authoritative JSON holds `m0`–`m10` and the subtitle "Eleven milestones". The HTML is the seven-node view. `ARCHITECTURE.md:10` describes the same file as "Part 6, the seven milestones this diagram can render".
- **Difference:** Following the README's own instruction — read the JSON, it is authoritative — a reader concludes the delivery order has eleven milestones, four of which (`M7`–`M10`) appear nowhere in the rendered diagram and `M10` appears nowhere in Part 6's prose either (Part 6 has M0–M6 and M9 headings only).
- **Confidence:** verified

This is a genuine new-drift instance of the class the harmonization was asked to watch for:
the HTML/JSON pair was left untouched, and the two documents describing it each tell half of
an inconsistent story.

### `ARCHITECTURE.md` Part 6 has eight milestone sections; the prose says nine, the repo has twelve
- **Claim:** "Nine milestones, ordered by user-visible outcome, not by subsystem." — `ARCHITECTURE.md:792`
- **Code says:** Part 6 contains eight `## M<n>` headings: `M0, M1, M2, M3, M4, M5, M6, M9` (lines 810, 876, 886, 898, 906, 914, 932, 948). `theteam/CHANGELOG.md` records `## M10 — One scheduler` (line 619), `## M11 — The headline command could not run` (line 446), and `## M12 — the task that reported success without doing anything` (line 967). The milestones diagram JSON goes to `m10`.
- **Difference:** A reader told Part 6 is the delivery order finds M7, M8, M10, M11 and M12 missing from it — including M11, which is where the `status`-has-no-session defect and the `save_state` no-op were closed, and M12, which merged `health-check` into `project-integrity`.
- **Confidence:** verified

The sentence at `ARCHITECTURE.md:792` explains the M7/M8 gap ("both were documentation audits
rather than new capability, so neither has a section here") but says nothing about M10, M11 or
M12, and the count "Nine" matches no reading of the file: eight headings, or twelve milestones
if CHANGELOG and the diagram are counted.

### `ARCHITECTURE.md` says the YAML repository carries six tasks; it carries five
- **Claim:** "the YAML repository carries six, so the count is now taken from `TaskRepository` rather than asserted here." — `ARCHITECTURE.md:795-796`
- **Code says:** `TaskRepository('.').list_tasks()` returns `count 5, yaml_count 5` with ids `['project-integrity', 'maintenance', 'ground-truth-audit', 'doc-harmonization', 'native-feature-loop']`. `tasks/` holds exactly five `task-*.yaml` files. `theteam run --only system-awareness` → `Task not found: system-awareness`; `theteam tasks` prints `5 tasks, 5 in YAML`.
- **Difference:** A reader auditing the ordering rule counts five registered tasks, not six, and the sentence's own justification for taking the number from `TaskRepository` fails on the one thing it names.
- **Confidence:** verified

Related and in the same document: `tasks/README.md:16` still lists `system-awareness` in the
"Current tasks" table, and `tasks/README.md:24-25` says "`theteam tasks` displays the *sequence
position* (0-5 here) rather than the field, which is why the two differ." `theteam tasks` now
prints positions `0`–`4` over five tasks. `system-awareness` has no YAML file
(`git log --diff-filter=D` shows its deletion at `5597651`); only the
`tasks/system-awareness/analyze_system_awareness.py` source and a README table row survive.
I did not find the deletion recorded in any document I read.

### `ARCHITECTURE.md` §3.2 says a missing task script is rejected at `task create`; it is not
- **Claim:** "| Task script missing | Rejected at `task create`. Also reported by `run` if it disappeared after creation. |" — `ARCHITECTURE.md:285`
- **Code says:** `TaskRepository._check_writable` (`repository.py:72-86`) validates only `REQUIRED_FIELDS = ("id",)` and a per-phase `memory_limit_mb`; it never touches the filesystem. I created a task whose only phase names `scripts/does_not_exist.py` against a real project: `{"id": "bad-script-task", "created": true}`, exit 0. The missing script surfaces only at run time as `missing script: <path>` from `_phase_problem` (`cli.py:413`), recorded as `skipped`.
- **Difference:** A user who writes a task pointing at a script that does not exist is told the task was created; the failure appears later, at `theteam run`, as a skip — so the document promises write-time validation the product does not perform.
- **Confidence:** verified

Note the neighbouring claim at `ARCHITECTURE.md:637` — "`memory_limit_mb` is mandatory per
phase — a phase without a bound is rejected at write time" — is **true** and verified: the
`memory_limit_mb` check is the one `_check_writable` does perform. The row at line 285 is a
separate, false claim sitting four lines from a true one about the same validation call.

### `ARCHITECTURE.md` §2.3 says three `routines/*.md` files exist; none does
- **Claim:** "`routine` was also already a loaded noun in this repo (`RoutineScheduler`, `run_routine`, three `routines/*.md`) belonging to a different data model — markdown phases rather than YAML." — `ARCHITECTURE.md:203-205`
- **Code says:** `routines/` does not exist (`ls routines/` → no such directory). `grep -rn "RoutineScheduler\|run_routine" theteam/ --include="*.py"` returns nothing. What exists instead is `config/routine-engine/` — 5 git-tracked files, 20K, of which `routines.yaml` is a markdown-phase routine definition set. That is the residue of the `routine-engine/` M10 removed (`ARCHITECTURE.md:180` describes it as "276 KB, 18 tracked files" deleted), which is not the same thing as "three `routines/*.md`".
- **Difference:** The justification for not renaming `loop` to `routine` cites three files and two symbols as present-noun evidence; a reader who greps for any of them finds none, and finds an unmentioned `config/routine-engine/` directory instead.
- **Confidence:** verified

`ARCHITECTURE.md:180`'s own description of `routine-engine/` is accurate as history — git
confirms 18 engine files were deleted at `40261ea` — but the 5 surviving config files under
`config/routine-engine/` are still tracked and are not mentioned anywhere I read.

### `ARCHITECTURE.md` M9 says `web_search` joined `permitted_skills`; it did not
- **Claim:** "**Decisions locked 2026-09-30.** `web_search` joins `permitted_skills` for members and manager." — `ARCHITECTURE.md:955`
- **Code says:** `grep -rn "web_search" theteam/ --include="*.py"` returns nothing. The default written by `generate_team_members_from_context` is `'permitted_skills': ['ponytail', 'evolve-skills', 'code-search']` (`__init__.py:483`), and this project's `theteam.config:82-85` carries the same three. `theteam/SKILL.md:202` and `theteam/ONBOARDING.md:101` both state the default as `ponytail, evolve-skills, code-search`.
- **Difference:** A member spawned under a config generated by the product gets a `## Tool Inventory` listing three skills, not the four the architecture document says were locked; and M9's Phase 6 plan item — "a note that it was added by user request on 2026-09-30 and why" — has no counterpart in any document, because the widening it documents did not happen.
- **Confidence:** verified

`SKILL.md:200-205` and `ONBOARDING.md:101` are both correct and mutually consistent. This is
drift isolated to `ARCHITECTURE.md:955`, in the M9 milestone prose — an area run1 did not read.

### `README.md` says the architecture diagram has 12 components and 14 edges; it has 13 and 12
- **Claim:** "Its 12 components and 14 edges are factually correct and every source path is verified against git" — `README.md:270-271`
- **Code says:** `diagrams/active-usage-architecture.json` has 13 entries in `components` and 12 in `connections`. The HTML carries the same 13 `data-node-id` values, so the pair is synced and the count is simply wrong. `TaskScheduler` (added at M10) is one of the 13.
- **Difference:** A reader cross-checking the README's own diagram note counts 13 component boxes in the rendered HTML and finds the prose off by one in both directions.
- **Confidence:** verified

Every component in the JSON names a real file and line — I checked all 13 `sources` entries
against the tree, and every path exists. The claim that they are "factually correct" holds; the
counts do not.

### `theteam/CLI.md` says `smoke_cli.py` runs 23 checks; it runs 23 of a different composition
- **Claim:** "`python3 scripts/smoke_cli.py           # human-readable, 23 checks`" — `theteam/CLI.md:53`
- **Code says:** `smoke_cli.py:135-158` defines a list literal of **22** tuples, plus one `bootstrap` check added separately at `smoke_cli.py:162-163` → 23 results total. The count 23 is right.
- **Difference:** None user-visible. The count matches. Recorded because the same figure was left unverified by run1 and is now confirmed, and because the composition is worth stating precisely: the 23 are 1 bootstrap + 22 argument checks, not 23 uniform ones.
- **Confidence:** verified

### `ARCHITECTURE.md` §7.2 invariants 3–5 are false as literally written
- **Claim:** "3. `grep -rn "/Users/bparlan" theteam/` returns nothing. 4. `grep -rn "parents\[" theteam/` returns nothing. 5. `grep -rn "\.mp/theteam" theteam/` returns nothing." — `ARCHITECTURE.md:1153-1155`
- **Code says:** Invariant 3 returns 11 files, all `__pycache__/*.pyc` build artifacts. Invariant 5 returns four source hits: `tasks/repository.py:34` (`DEAD_DIR = ".mp/theteam"`), `tasks/repository.py:58` (the guard's own comment), and `tests/test_task_repository.py:497,502`. Invariant 4 does return nothing. The invariant gate itself scopes all three to `--include="*.py"` and carves out the `DEAD_DIR` guard and its test (`check_invariants.sh:43,69-74`), and reports all three PASS — which I confirmed by running it.
- **Difference:** An auditor running §7.2's invariants as written sees checks 3 and 5 fail on a tree whose own gate reports 7/7, and concludes the product is broken rather than that the document overstates its scope.
- **Confidence:** verified

This is not a code defect and the gate is not wrong — it is a document that states a stricter
invariant than the one it ships. `ARCHITECTURE.md:1252` claims "744 tests passed" for the same
section, also stale but defensible as a dated record; the invariant text is not dated, so it
is a live claim.

---

## Claims checked and confirmed accurate

Verified by reading the code. Recorded so the next reader does not re-check them.

**Corrected by the harmonization, re-verified independently:**

| Claim | Source | Verified by |
|---|---|---|
| "Twelve subcommands" | `README.md:53`, `ARCHITECTURE.md:94` | `--help` lists exactly 12: `{bootstrap,status,discuss,serve,loop,tasks,run,history,task,comment,manager,watch}`. Both counts now match their own tables. |
| `theteam_report.py` lives at repo-root `bin/`, not `theteam/bin/` | `SKILL.md:181`, `CLI.md:145-161`, `ARCHITECTURE.md:558` | `theteam/bin/` holds `__init__.py`, `theteam_config.py`, `utilities.py`; `bin/theteam_report.py` exists (7,675 bytes). `python3 bin/theteam_report.py build --help` reaches argument parsing (`FATAL: unrecognized argument: --help`), so the file is found. Its imports are stdlib-only, so dropping `PYTHONPATH=theteam` is correct. |
| `core/` holds 21 files / 20 modules, all owned | `ARCHITECTURE.md:521-522` | `theteam/core/` has 21 `.py` files. I extracted all 20 table rows programmatically: set difference against the directory is empty in both directions — no unowned module, no phantom row. The `run_context.py` row is present and correct (`cli.py:26` imports it; `workflow/context_aggregator.py:285` reads it). |
| `ONBOARDING.md` tree includes `core/run_context.py` | `ONBOARDING.md:67` | Line present with the right annotation. |
| 762 tests | `README.md:210`, `ONBOARDING.md:78` | `pytest --collect-only` → `762 tests collected`. |
| §3.1's sample `status` output is the five lines the command builds | `ARCHITECTURE.md:255-268` | `status_payload` (`cli.py:309-316`) builds exactly `project`, `state`, `roster`, `tasks`, `chain_line(...)`. No session field in the payload dict (`cli.py:300-308`). |
| §1.2's session promise is checkable on `comment status` | `ARCHITECTURE.md:56` | `cli.py:937` — `"last_digest": state.get("last_digest")` is in `_comment_status_payload`. `read_session` returns `reason="no_session"` at `session_reader.py:118,123,130,141,145,255`. |
| §7.1 invariant 1 is satisfiable | `ARCHITECTURE.md:1139` | Restated to name only what the payload carries. `theteam status` on this project prints roster, state, tasks, breakers, audit chain — and no session line. |

**Carried over from run1 and independently re-confirmed:**

| Claim | Source | Verified by |
|---|---|---|
| `python -m theteam` fails | `README.md:28-30` | `No module named theteam.__main__`, exit 1. |
| `--project-root` after the subcommand exits 2 | `CLI.md:36-38` | `error: unrecognized arguments`, exit 2. |
| Bare `theteam comment` returns 1, not 2 | `README.md:167-170`, `ARCHITECTURE.md:155` | `theteam comment: missing subcommand: on|off|status`, exit 1. `required=False` at `cli.py:1199`. |
| `comment on --max-members 9` is refused, not clamped | `ARCHITECTURE.md:110` | `--max-members 9 exceeds the cap of 4`, exit 1; guard runs before `store.ensure()`. |
| `--json` on either side of the subcommand | `README.md:53` | Parent at `cli.py:1101`, every subparser with `default=argparse.SUPPRESS`; both forms parse. |
| `run` returns 1 when a task failed | `ARCHITECTURE.md:117` | `cli.py:661` — `return EXIT_ERROR if payload["failures"] else EXIT_OK`. |
| `run --only <unknown>` is a named failure | `ARCHITECTURE.md:127` | `cli.py:606` — `Task not found: <id>`, exit 1. |
| `run` with nothing due is `{ran: 0}` and idempotent | `ARCHITECTURE.md:1142` (§7.1.4) | `{ran:0, skipped:0, failures:0, findings:0, …, results:[]}`; `ran` counts only ok/failed (`cli.py:548`). Text mode: `nothing due`, exit 0. |
| `run_due_tasks` shared by `run` and `serve` | `ARCHITECTURE.md:184` | `cli.py:416` defines it; `cmd_serve` (`cli.py:797`) injects it into `TaskScheduler`. |
| `success_rate` is `None`, not `0.0`, with no runs | `README.md:152` | `cli.py:735-737` ternary. |
| `breaker` prints `never run` | `README.md:149` | `cli.py:373` and `cli.py:757` — `or "never run"`. |
| Exit codes 137 / 124 | `ARCHITECTURE.md:1144` (§7.1.6) | `executor.py:66-67` — `OOM_KILL_EXIT_CODE = 137`, `TIMEOUT_EXIT_CODE = 124`. |
| Invariant gate: 7 checks, all pass | `README.md:211` | `check 1 PASS` … `check 7 PASS`, `invariant gate PASSED`. |
| Import graph: ≤90 modules, ≤8 `core.*`, no cluster tier | `ARCHITECTURE.md:1169` | 88 / 7, `postgres_cluster` absent. |
| `PyYAML>=6.0` is the only hard dep; `rich` undeclared and unimported | `README.md:11-13` | `dependencies = ["PyYAML>=6.0"]`; `postgres` extra is `psycopg2-binary`; zero `^import rich\|^from rich` hits. |
| `psycopg2` is an optional extra, not needed by default | `README.md:190-191` | `pyproject.toml:17`; `database.py:88-89` imports it inside a method body, not at module scope. |
| `theteam discuss` outside OMP names the OMP requirement | `ARCHITECTURE.md:58` | `__init__.py:64-66` — `"theteam requires an OMP session. Run this inside OMP, …"`. |
| `MEMBER_CAP = 4`, `SOLO_DEFAULT = "skeptic"` | `ARCHITECTURE.md:325,326` | `selector.py:35,42`. Exact match. |
| Lone skeptic when no signal fires; truncation reported | `SKILL.md:158-160`, `ARCHITECTURE.md:1018` | `selector.py:253-260` returns `[SOLO_DEFAULT]` with `signals: {"default": …}`; `__init__.py:764-766` prints `"N selected, M speak, S suppressed (cap 4)"`. |
| §4.4 `SessionSlice` field set and K defaults | `ARCHITECTURE.md:359-370` | **Now verified, closing run1's open item.** `session_reader.py:50-56` declares exactly `last_user_messages`, `recent_activity`, `touched_paths`, `digest`. `DEFAULT_MESSAGES = 4`, `MAX_MESSAGES = 8`, and the cap is enforced at the call site: `limit = min(max(int(messages), 0), MAX_MESSAGES)` (`:220`). `MESSAGE_CHARS = 400` (`:30,242`), `ACTIVITY_LIMIT = 8` (`:31,259`). Tool **results** are never returned — only `toolCall` names and argument paths (`:243-249`). All four fields, both caps, and the never-return-results rule match. |
| §4.3 the reader refuses subagent transcripts | `ARCHITECTURE.md:354` | `SUBAGENT_MARKER = "__advisor.jsonl"` (`:34`); `resolve_session_path` returns `no_session` for a subagent file (`:128-131`) and for a candidate nested under a slug directory (`:138-142`). |
| §4.2 stop words and whole-leading-clause matching | `ARCHITECTURE.md:322,328` | `STOP_WORDS` at `commentary.py:42-44`; `is_stop` → `leading_clause(message) in STOP_WORDS` (`:106-108`). |
| `MAX_FRAGMENTS = 2`, rest counted not hidden | `ARCHITECTURE.md:326` | `commentary.py:39,248` — `opinions[:MAX_FRAGMENTS]`, `suppressed = len(opinions) - len(fragments)`. |
| `monitor.py` is stdlib-only with no API layer | `ARCHITECTURE.md:141` | Imports are `time`, `collections.deque`, `typing`, plus `theteam.core.audit_chain` in `ui/terminal.py` — not in `monitor.py`. No `get_monitor_status` / `get_recent_events` / `clear_alerts` anywhere in the module. |
| `MAX_EVENTS = 100`, `VISIBLE_EVENTS = 5` | (§2) | `monitor.py:25,28`. |
| `theteam/watch --once --monitor` baseline wording | `README.md:96,110` | `ui/terminal.py:66` emits `"changes     baseline - first frame, nothing compared yet"` verbatim; matches the live frame. |
| `run` payload reports `context: {written, context_bytes}` | `CLI.md:130` | `cli.py:562-566`; live run returned `"context": {"written": true, "context_bytes": 221}`. |
| `agent_isolation` unavailability message and its line | `CLI.md:135-137` | `executor.py:206-213` — `"Phase '<name>' refused: container isolation unavailable (no Docker daemon), and an unguarded run is not permitted"`, at 205-212 as cited. |
| `runners/llm.py` exists with `run_llm_phase` | `ARCHITECTURE.md:1069` | `llm.py:80`, branched from `executor.py:174-176` on `phase.get("runner") == "llm"`. |
| `repository.py` requires only `id`; no `depends_on` | `ARCHITECTURE.md:1082` | `REQUIRED_FIELDS = ("id",)` (`repository.py:32`). |
| `task-` filename prefix gate | `ARCHITECTURE.md:670` | `repository.py:168` — `name.startswith("task-")`. The doc's cited `repository.py:148` is off by 20 lines; the claim is right, the pointer is stale. |
| `memory_limit_mb` rejected at write | `ARCHITECTURE.md:637,681-682` | `repository.py:80-85`. |
| `_save_schedule` atomic; `purge_orphaned_schedules` / `repair_schedules` / `worst_case_seconds` exist | `ARCHITECTURE.md:215,236,241` | `repository.py:459, 352, 488, 478`. `record_run`/`record_skip`/`schedule_task` all funnel through it (`:403,449,574`). |
| `health_monitor.py` and `event_bus.py` have no production importer | `ARCHITECTURE.md:545-546` | `grep` for `event_bus` outside `core/event_bus.py` and tests: nothing. `health_monitor` is read duck-typed via `getattr(loop, "health_monitor", None)` (`metrics.py:288,323`), and `scheduler.py:62` sets it to `None` — so the class is indeed never instantiated. `health_dashboard.py` duck-types (`getattr(monitor, "get_health_score", None)`, `:54`) and tests hand it a `SimpleNamespace` (`test_metrics.py:291`). Both claims hold. |
| `backup.py` is live via `scripts/backup.py` | `ARCHITECTURE.md:566-571` | `scripts/backup.py` implements `create`/`verify`/`restore`/`prune`. |
| `postgres_cluster.py` off the entry point | `ARCHITECTURE.md:550` | Not in the 88-module load; `database.py` imports it inside properties. |
| Manager: `--topic` proposes, `--apply` persists, `--reset`, `--status` reports unjustified | `README.md:73`, `ARCHITECTURE.md:114` | `cli.py:177` (reset), `:209-213` (topic), `:230` (`if not args.apply`), `:254` (write). `--status` collects `no recorded reason` members into `unjustified` (`cli.py:190-198`). Roster cap is 9: `CATALOG` has 9 members, matching `__init__.py:292-299`'s "`len(BASE_MEMBERS) + len(FOCUS_MEMBERS)` = 9". |
| M7.1 invariant 3 — two bootstraps of different projects differ | `ARCHITECTURE.md:1141` | Booted two temp projects (SQL+pyproject vs HTML+package.json): rosters `[architect, pragmatist, skeptic]` vs `[architect, pragmatist, skeptic, designer]`. Differ. |
| `theteam.status` payload key shape | `README.md:128-135` | `cli.py:300-308` — `{project_root, state_dir, roster, tasks, breakers, audit_chain}`, exact match. |
| `tasks` row fields incl. `breaker_consecutive_failures` | `ARCHITECTURE.md:103` | `repository.py:_row` returns all six named plus `name`, `type`, `priority`. README's row (`README.md:62`) omits `breaker_consecutive_failures` — a minor omission run1 recorded; I confirm it is still omitted and still not a contradiction. |
| CI on Python 3.9–3.12, three real steps + one decorative | `README.md:214-215,29-30` | `ci.yml` matrix is `["3.9","3.10","3.11","3.12"]`; the `python -m theteam --help \|\| true` step is present and decorative as described. |
| `M7.2.7` is struck through in the document itself | `ARCHITECTURE.md:1157-1166` | Struck. No live claim to falsify. |
| `M5.3.1` the digest cache does not exist | `ARCHITECTURE.md:408-420` | No `st_mtime`, no cache module; `refresh` appears nowhere in `cli.py`. The correction is accurate. |
| `option_selection_required` read by nothing | `SKILL.md:123-124`, `ONBOARDING.md:99` | One hit, a comment in `theteam_config.py:31` marking it retired. No read site. |
| `proposals/` has a reader and no writer | `ARCHITECTURE.md:706-712` | `state.py:70` resolves it; `run_context.py:385` reads it; nothing writes. |
| `run_context` is in `ALWAYS_DELIVERED` | `ARCHITECTURE.md:749-750` | `context_slice.py:49` — `("project_goal", "project_root", "run_context")`. |
| `M9 Phase 1` replaced the manifest read with `permitted_skills` | `SKILL.md:207-213` | `__init__.py:94-95` renders `## Tool Inventory` from `_render_skills(permitted_skills)`; the manifest read is gone. `test_m9_selection_wiring.py:56` is `TestToolInventoryIsTheRealBoundary`. |
| Deleted modules are absent | `ARCHITECTURE.md:553-558` | `unified_loop.py`, `task_contract.py`, `integrated_orchestrator.py`, `schema_versioning.py`, `system_integration.py`, `state_validator.py`, `team_member_manager.py` — all absent. `skill/SKILL_metadata.py` absent. |
| Part 8's six "verified absent" component names | `ARCHITECTURE.md:1276-1283` | `ConfigStore`, `ToolManifest`, `AgentRegistry`, `MetricsStore`, `Alerting` → 0 hits in `theteam/**/*.py`. `theteam_cli` absent as a module. All 12 archived diagram JSONs are in `diagrams/archive/`. |
| `loop_manager.py.bak2` / `test_state_validator.py.backup2` removed | `ARCHITECTURE.md:604-605` | Both absent. |
| Part 9 row 1b's `save_state`/`load_state` fix | `ARCHITECTURE.md:1304` | `state_manager.py:306-353` now calls `self.wal.append_entry('save', …)`; `load_state` at `:390` no longer calls the non-existent `verify_checksum`. `ChecksumManager.verify_checksum` does exist (`checksum.py:91`), so the doc's parenthetical is now stale in the other direction — the method is real, the M11 call site was the defect. Noted, not filed: the row's claim is about the call sites, and it is accurate about them. |
| Every command takes an explicit `project_root`; every command returns a real exit code | `ARCHITECTURE.md:143` | `main()` (`cli.py:1274-1300`) catches `KeyboardInterrupt`→1, `KeyError`/`ValueError`→named message (unwrapped from `repr`), bare `Exception`→named message. `watch` returns 0 on Ctrl-C (`cli.py:1073-1076`), which is what `README.md:172-173` documents. |

---

## Not checked

Listed for honesty, not as findings.

- **`ARCHITECTURE.md:341`'s live-session statistics** ("289 message events, 1.85 MB, roles
  `{assistant: 204, …}`"). Still unmeasurable: it describes a session file not in this
  repository. Run1 reached the same conclusion and I did not invent a way around it. The
  related path shape at `ARCHITECTURE.md:337-338` is consistent with
  `session_reader.py:76-81` (`~/.omp/agent/sessions/<slug>/…`, `__advisor.jsonl` for
  subagents), which I did verify.
- **`ARCHITECTURE.md:5-30`'s `archify validate` claims** — the 9/9 artifact checks, the
  11.9px-vs-6px projection, the `archify 2.17.0-dev.1` provenance, the exhaustive list of
  layout variants tried. `archify` is not available in this environment, so the measurements
  cannot be re-measured. I verified only the parts the tool would have run against: the
  component/node/edge counts in both JSONs and both HTMLs.
- **The `diagrams/*.html` rendered geometry** — viewBox, font metrics, projected label size,
  edge routing. I compared node-id sets and the subtitle string between each HTML and its
  JSON; I did not measure pixels.
- **`theteam/CHANGELOG.md` in full** (1,121 lines). I read the M8 audit entry, the M10/M11/M12
  headings, and the entry that records the 772 count. Its other entries are historical records
  of what a milestone did, and I did not verify them against the code.
- **M0's "584 tests pass" and "613 tests" correction** (`ARCHITECTURE.md:863,870-871`).
  These are dated baselines for a milestone delivered before the current tree; 584 is not
  measurable now and the document presents it as a record of that milestone's verification,
  not a current count. Same treatment for the M9 "not instantiated outside tests" table
  (`ARCHITECTURE.md:963-972`), which describes the M9 starting state and is therefore true
  only of the commit it was written against — `cli.py:26` imports `run_context` and M10
  re-ran the sweep.
- **The `llm` runner's prompt-driven behaviour.** `tasks/README.md:223-226` says so itself
  ("no `llm` phase has ever been observed producing output … Their behaviour comes from their
  prompt files and is a claim, not a measurement"). I did not run one; it needs an OMP
  session with a provider bound, which this environment does not have.
- **`scripts/smoke_cli.py` executed.** I counted its checks statically (22 + bootstrap) and
  confirmed every script path it names in `tasks/README.md:137-142` exists, but I did not run
  it — it creates temp projects and drives `serve`-adjacent paths. My reconciliation of the
  "23 checks" figure is a static count, not a run.
- **The test suite's own claims** — the 762 tests' assertions, and the M9/M11/M12 tests named as
  falsifiers in the document. I read `test_m9_selection_wiring.py`'s class name and
  `test_metrics.py`'s `SimpleNamespace` usage; I did not read test bodies or run the suite,
  which was out of scope by instruction.
- **`theteam/CLI.md:63-67`'s coverage claim** — that the smoke checks cover the named
  commands. I read the `checks` list and every command it names is there, but "23 checks"
  covering 12 subcommands is a coverage judgement, not a code fact.
- **The 6-task `routine-engine` KB and migration records** under
  `.omp/theteam/ledger.json`, `tasks-ledger.json`, `session-audit/`, and `archive/`. These
  are state artifacts from a different data model; I confirmed `RoutineScheduler` and
  `run_routine` are absent from the source but did not read the ledgers to find where their
  history lives.
- **`ARCHITECTURE.md` Part 6's per-milestone falsification tests.** These are written in
  future or historical tense for milestones M0–M6 that are all delivered; I verified the
  specific mechanics they name (the `run_discussion` guard, the `memory_limit_mb` write check,
  the `chain_line` single-renderer rule) but did not execute each test as written.
- **`README.md:242-265`'s Plan-evaluation (M7) table** — a dated historical record of what the
  M7 audit found. Its claims about the diagrams at that time (six milestones, `TaskStore`,
  `TaskManager`) are false against the current tree *by design*; the document presents them as
  what was true then and what was changed, and I confirmed the present state matches its
  "what was actually true" column's corrections. I did not verify the historical half.
