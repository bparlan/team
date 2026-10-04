> Copied from `.omp/theteam/reports/` on 2026-10-01. That path is gitignored as
> runtime state, so the reports live here to survive a fresh clone. The
> originals remain in `.omp/theteam/reports/` and are the ones the tasks write.

# Ground-truth audit

Reconnaissance only. Every finding below was checked by reading the cited source, not by
inferring from the claim's own wording. Findings are grouped by severity. Where a claim
could not be checked with the tools available, that is stated rather than guessed.

Scope read in full: `README.md`, `ARCHITECTURE.md` (all 1304 lines), `theteam/README.md`,
`theteam/CLI.md`, `theteam/ONBOARDING.md`, `theteam/SKILL.md`, `scripts/check_invariants.sh`,
`.github/workflows/ci.yml`, `pyproject.toml`, and the source named by each finding below.

---

## Contradicted claims

### `theteam_report.py` is documented in three places and does not exist
- **Claim:** "`theteam manager` … persists them" and "Render the report: `PYTHONPATH=theteam python3 theteam/bin/theteam_report.py build …`" — `theteam/SKILL.md:181`
- **Claim:** "The helper scripts in `theteam/bin/` — **Two scripts remain.** … Build a report from member notes and a synthesis file" — `theteam/CLI.md:145-157`
- **Claim:** "`bin/theteam_report.py`, and `skill/SKILL_metadata.py`. Measured by an AST scan … and a runtime `sys.modules` check across all three entry points" — `ARCHITECTURE.md:548`
- **Code says:** `theteam/bin/` contains `__init__.py`, `theteam_config.py`, `utilities.py`. There is no `theteam_report.py`. Running the documented invocation yields `can't open file '…/theteam/bin/theteam_report.py': [Errno 2] No such file or directory`.
- **Difference:** A user following `SKILL.md` step 10 — the step that turns a discussion into a deliverable — hits a missing file and produces no report.
- **Confidence:** verified

Note that a copy *does* exist at the repo-root `bin/theteam_report.py`, and `theteam/CLI.md` does
not mention it. So the script was moved, not deleted, and the docs still point at the old path.
This is the same class of defect the CLI.md preamble claims to have fixed.

### `theteam tests/ # 659 tests` is stale in three documents
- **Claim:** "`theteam/tests/                    # 659 tests`" — `theteam/ONBOARDING.md:77`
- **Claim:** "`python -m pytest -q                  # 659 tests`" — `README.md:211`
- **Code says:** `python3 -m pytest --collect-only` reports **762 tests collected**.
- **Difference:** A reader comparing counts sees a 103-test gap and cannot tell whether 103 tests vanished or the doc is old.
- **Confidence:** verified

`ARCHITECTURE.md:1242` states "744 tests passed" for the M7 audit — also stale, but §7.3 is a
dated historical record, so that one is defensible. The README and ONBOARDING counts are
presented as current.

---

## Contradicted claims, continued
### `core/` holds 23 modules; it holds 20 (excluding `__init__`, 21 including it)
- **Claim:** "`core/` holds 23 modules. The tree above names 8; this table assigns the rest, so no module is unowned." — `ARCHITECTURE.md:513`
- **Code says:** `theteam/core/` contains 21 `.py` files. §5.2.1's table assigns 18 of them; `run_context.py` (imported at `cli.py:26`) and `__init__.py` are in neither the tree listing at §5.2 nor the ownership table at §5.2.1.
- **Difference:** The document's own stated purpose for that table — "so no module is unowned" — is false: `run_context.py` is unowned in the doc while being live in `cli.py`.
- **Confidence:** verified

### `theteam/README.md` omits `run_context.py`; the rest of its tree checks out
- **Claim:** "`cli.py  # the only entry point; theteam console script` / `state.py # the single state-directory resolver` / `__init__.py` / `monitor.py` / `tasks/` / `core/` / `advisory/` / `workflow/` / `ui/` / `security/` / `bin/` / `tests/`" — `theteam/ONBOARDING.md:44-78`
- **Code says:** Every path named in that tree exists and means what the annotation says — `tasks/{repository,executor,scheduler}.py`, `tasks/runners/llm.py`, `core/{circuit_breaker,resource_limiter,agent_isolation,audit,audit_chain,metrics,backup,health_monitor,event_bus,event_log,rate_limiting,state_manager,checksum,database,wal,transactions,correlation,member,postgres_cluster}.py`, `advisory/{session_reader,selector,commentary,roster,context_slice,manager}.py`, `workflow/context_aggregator.py`, `ui/terminal.py`, `ui/components/`, `security/`, `bin/`. One live module is missing from the drawing: `core/run_context.py`, imported by `cli.py:26`.
- **Difference:** None a user would observe — the tree is a diagram, and the one omission is a module the diagram does not describe.
- **Confidence:** verified

Recorded because it is the kind of near-miss that is worth saying plainly did *not* turn up
something: the package layout in ONBOARDING is accurate apart from one unlisted file.

### Eleven vs. twelve subcommands
- **Claim:** "Eleven subcommands. `--json` works on **either side** of the subcommand for every one of them." — `README.md:53` (same claim at `ARCHITECTURE.md:93`)
- **Code says:** `--help` lists twelve: `{bootstrap,status,discuss,serve,loop,tasks,run,history,task,comment,manager,watch}`. `theteam/CLI.md:17` says "twelve subcommands" and is right.
- **Difference:** A user counting the commands in `README.md`'s own table finds twelve entries under a heading that says eleven; `manager` was added in M9 and two documents were updated, one was not.
- **Confidence:** verified

---

## Unfalsifiable or unverifiable claims

### §4.4's `SessionSlice` signature was not checked
- **Claim:** "`SessionSlice: last_user_messages: list[str] # last 3 user texts, truncated 400 chars each / recent_activity: list[str] # last 8 tool NAMES … / touched_paths: list[str] / digest: str`" and "`K defaults to 4 messages, hard-capped at 8.`" — `ARCHITECTURE.md:352-362`
- **Code says:** `SessionSlice` is imported from `theteam/advisory/session_reader.py` (`selector.py:31`). I did not read `session_reader.py` in this pass, so I cannot confirm or refute the field set or the K defaults.
- **Difference:** Undetermined.
- **Confidence:** could-not-verify — **left open deliberately; a plausible-looking guess here would be exactly the defect this project is built against.**

### §4.3 session statistics cannot be re-measured
- **Claim:** "Measured on a live session: 289 message events, 1.85 MB, roles `{assistant: 204, toolResult: 317, user: 11, developer: 1}`, parts `{thinking: 129, text: 432, toolCall: 318}`" — `ARCHITECTURE.md:341`
- **Code says:** These are observations of a session file that is not in this repository.
- **Difference:** Undeterminable. The same figures appear in the sample `theteam status` output at `ARCHITECTURE.md:257`.
- **Confidence:** could-not-verify

### §3.1's sample `status` output is not the shape the command prints
- **Claim:** "`$ theteam status` → `roster 5 members active` / `session …` / `session events 289 message events, 1.85 MB, last read 14s ago` / `commentary on, last spoke 3 turns ago, digest a4f2...` / `tasks 4 registered, 1 due, 0 breaker trips` / `audit chain intact, 142 entries, last verified 14s ago`" — `ARCHITECTURE.md:254-260`
- **Code says:** `status_payload` (`cli.py:265-317`) emits exactly five lines: `project`, `state`, `roster`, `tasks`, and the audit chain line. There is no `session` line, no `session events` line, and no `commentary` line anywhere in `status_payload`.
- **Difference:** A user running `theteam status` sees five lines, none of which are `session`, `session events`, or `commentary` — the three lines §3.1 promises as the trust surface's evidence that the team read a real session.
- **Confidence:** verified

This directly contradicts §1.2's checkable promise: "The team reads your real session | `theteam status` shows the session file path, its event count, and the digest the team last saw" (`ARCHITECTURE.md:56`). Neither the path, the count, nor the digest is in the payload. The same promise is repeated in README-adjacent prose and in `ONBOARDING.md` troubleshooting, which says `status` reports a roster when the project is not bootstrapped — that part holds, but the session claim does not.

### §7.1 invariant 1 is not satisfiable as written
- **Claim:** "`theteam status` on a bootstrapped project shows a roster, a bound session, and an intact audit chain." — `ARCHITECTURE.md:1129`
- **Code says:** Same as above — `status_payload` has no session field, so this invariant cannot pass on any project.
- **Difference:** A user auditing against §7.1 item 1 will conclude the product is broken when it is only mis-documented.
- **Confidence:** verified

---

## Claims checked and confirmed accurate

Recorded so the next reader does not re-check them. Each was verified by reading the code.

| Claim | Source | Verified by |
|---|---|---|
| Subcommand *names* all match the parser | `README.md:53`, `ARCHITECTURE.md:93`, `theteam/CLI.md:17` | `--help` lists exactly `{bootstrap,status,discuss,serve,loop,tasks,run,history,task,comment,manager,watch}`. The **count** is wrong in two of the three — see the "Eleven vs. twelve" finding above. |
| `python -m theteam` fails; `__main__.py` gone | `README.md:28-30` | `No module named theteam.__main__` reproduced. |
| `THETEAM_STATE_DIR` overrides the state tree | `README.md:182`, `state.py:18-32` | `state_dir()` reads it first and returns before touching `project_root`. |
| `--project-root` before the subcommand only; after it exits 2 | `theteam/CLI.md:36-38` | `theteam status --project-root /tmp` → `error: unrecognized arguments`, exit 2. |
| `comment` subparsers `required=False`, bare `comment` returns 1 | `README.md:167-170`, `ARCHITECTURE.md:153`, `cli.py:1199,1223,973-984` | Parser comment, `set_defaults`, and the `action is None` branch all agree; exit is `EXIT_ERROR` = 1. |
| `comment on --max-members` above 4 is refused, not clamped | `ARCHITECTURE.md:109`, `cli.py:988-991` | Guard runs before any state is created. |
| `--dry-run` exists on `run` (undocumented in README's table) | `cli.py:1152` | Present in the parser; `README.md:63` omits it. Minor omission, not a contradiction. |
| `run` returns 1 when a task failed | `ARCHITECTURE.md:115`, `cli.py:661` | `return EXIT_ERROR if payload["failures"] else EXIT_OK`. |
| `run --only <unknown>` is a named failure | `ARCHITECTURE.md:126`, `cli.py:603-606` | `_fail(..., f"Task not found: {args.only}")`. |
| `run_due_tasks` is shared by `run` and `serve` | `ARCHITECTURE.md:184`, `cli.py:416,776-800` | `cmd_serve` constructs `TaskScheduler(project_root, run_due_tasks, …)`; `scheduler.py:16-17` documents the injection. |
| Atomic schedule writes via `_save_schedule` | `ARCHITECTURE.md:214`, `repository.py:459` | Function exists; `record_run`/`record_skip`/`schedule_task` funnel through it. |
| `purge_orphaned_schedules`, `repair_schedules`, `worst_case_seconds` exist | `ARCHITECTURE.md:230-242` | `repository.py:352, 488, 478`. |
| `MEMBER_CAP = 4`, `SOLO_DEFAULT = "skeptic"` | `ARCHITECTURE.md:956`, `selector.py:35,42` | Exact match. |
| `MAX_FRAGMENTS = 2` | `ARCHITECTURE.md:312`, `commentary.py:39` | Exact match; `suppressed` recorded at `commentary.py:64,79`. |
| `discussion.py:186 tick()` — actually `commentary.py` holds `tick()` | `ARCHITECTURE.md:958` | The doc says `advisory/commentary.py:186 tick()`; verified `tick` lives in `commentary.py`. Line number not re-checked. |
| `MAX_EVENTS = 100`, `VISIBLE_EVENTS = 5` bounded buffers | `monitor.py:25,28` | Exact match; comment states a watch loop is not a log store. |
| `monitor.py` imports only the standard library | `ARCHITECTURE.md:139` | Imports are `time`, `collections.deque`, `typing`. |
| `monitor.py` has no API layer (`get_monitor_status` etc.) | `ARCHITECTURE.md:139` | No such functions in the module. |
| `success_rate` is `None`, not `0.0`, with no runs | `README.md:152`, `cli.py:738-740` | Ternary yields `None` when `runs` is empty. |
| `breaker` prints `never run`, never `closed` | `README.md:153`, `cli.py:373,757` | `task["breaker"] or "never run"`. |
| `status` payload key shape `{project_root, state_dir, roster, tasks, breakers, audit_chain}` | `README.md:128-135`, `cli.py:302-310` | Exact match. |
| `exit 137` for OOM kill, `124` for wall-clock timeout | `executor.py:64-67` | Named constants match. |
| `FINDINGS_EXIT_CODE = 3`, `CANNOT_EVALUATE_EXIT_CODE = 2` | `executor.py:59-60` | Exact match. |
| Invariant gate: 7 checks, all pass | `README.md:211` | `bash scripts/check_invariants.sh` → `check 1 PASS` … `check 7 PASS`, `invariant gate PASSED`. |
| Import-graph budgets: ≤90 modules, ≤8 `core.*`, no cluster tier | `ARCHITECTURE.md:1159` | Measured 88 / 7, `postgres_cluster` absent. |
| Invariants 3, 4, 5, 6 hold in the tree | `ARCHITECTURE.md:1143-1146` | `MockAPI` appears only in three docstring/comment mentions; no `parents[`; `.mp/theteam` confined to `DEAD_DIR` (`repository.py:34`) and its test. Note invariant 3 as literally written — `grep -rn "/Users/bparlan" theteam/` returns nothing — is true; the hits I found are in `theteam/reports/*.md`, outside the invariant's scope, and the gate's own check 3 excludes non-`.py` files. |
| CI runs on Python 3.9–3.12, three steps | `README.md:214-215` | `.github/workflows/ci.yml` matrix is `["3.9","3.10","3.11","3.12"]`; suite, import check, invariant gate all present. The fourth step (`Verify entry point`, `python -m theteam --help \|\| true`) is what README calls decorative. |
| `PyYAML>=6.0` is the only declared dependency | `README.md:11` | `pyproject.toml` `dependencies = ["PyYAML>=6.0"]`; `postgres` extra exists for psycopg2, matching `README.md:191`. |
| `theteam discuss` raises `ProviderUnavailable` naming the OMP requirement | `ARCHITECTURE.md:58`, `__init__.py:57-66,696` | `_require_provider()` is the first statement of `run_discussion`; the message names the OMP session. |
| `runner: llm` phases exist as a second kind | `ARCHITECTURE.md:1047-1061` | `theteam/tasks/runners/llm.py` exists and is imported by the executor. |
| `.omp/theteam/tool-manifest.json` does not exist | `SKILL.md:145-146` | Confirmed absent from the tree. |
| `option_selection_required` is read by nothing | `SKILL.md:123-124`, `ONBOARDING.md:98` | No read site found outside config validation. |
| `theteam-template.config` exists and validates | `SKILL.md:71` | `PYTHONPATH=theteam python3 theteam/bin/theteam_config.py validate … --json` → `OK: Config is valid`, exit 0. |
| `purge_orphaned_schedules` removes entries whose YAML is gone | `ARCHITECTURE.md:239` | Function present at `repository.py:352`; the purge is reported in `cmd_run`'s text output (`cli.py:645-649`). |

---

## Not checked

Listed for honesty, not as findings.

- `theteam/advisory/session_reader.py` internals (§4.4's `SessionSlice` shape and K defaults).
- `theteam/advisory/commentary.py` `tick()` at the cited line 186, and the M9 selector-wiring test named as falsifier.
- Whether `run_discussion` is byte-identical since M5 — §7.2 invariant 7 is struck through in the document itself, so there is no live claim to check.
- The `diagrams/*.json` component lists against the import graph. ARCHITECTURE.md:28-30 asserts `validate` returns `ok: true` with 9/9 artifact checks; `archify` is not available in this environment.
- `scripts/smoke_cli.py`'s claim of "23 checks" (`theteam/CLI.md:53`) — the script exists; I did not run it, since it creates temp projects.