> Copied from `.omp/theteam/reports/` on 2026-10-01. That path is gitignored as
> runtime state, so the reports live here to survive a fresh clone. The
> originals remain in `.omp/theteam/reports/` and are the ones the tasks write.

# Doc harmonization

Consumes `reports/ground-truth-audit.run1.md`. All 7 `Confidence: verified`
findings were handled. The 2 `could-not-verify` findings (§4.4's `SessionSlice`
signature, §4.3's live-session statistics) were skipped: §4.3's figures were left
exactly as the audit left them, and no claim anywhere was rewritten on the strength
of a guess.

Finding 7 (`scripts/smoke_cli.py`) was never verified by the audit and is not
treated as a finding here. It is passed to the follow-up list below as unchecked.

---

### Report script documented at a path that does not exist (SKILL.md)
- **File:** `theteam/SKILL.md:181`
- **Was:** `PYTHONPATH=theteam python3 theteam/bin/theteam_report.py build \`
- **Now:** `python3 bin/theteam_report.py build \`
- **Why this is enough:** `theteam/bin/theteam_report.py` does not exist and the
  documented invocation fails with `No such file or directory`; `bin/theteam_report.py`
  is the live script, and step 10's cwd is the project root, so this path resolves.
  The `PYTHONPATH=theteam` prefix was also dropped — verified that the script
  imports only `sys, os, json, glob, datetime`, so it has no package dependency
  to satisfy. Confirmed by running `python3 bin/theteam_report.py build --topic t`
  from the repo root: it reaches argument parsing, i.e. the file is found.

### Report script documented at a path that does not exist (CLI.md)
- **File:** `theteam/CLI.md:145-163`
- **Was:** "## The helper scripts in `theteam/bin/`" / "Two scripts remain. They are
  helpers for the skill's config and report generation, not part of the user-facing
  CLI. Note the invocation form: they import `bin.utilities` as a top-level package,
  so they need `theteam/` on the path." / `PYTHONPATH=theteam python3 theteam/bin/theteam_report.py build \`
- **Now:** "## The helper scripts" / "Two scripts remain, in different places.
  `theteam_config.py` is in `theteam/bin/` and is part of the package;
  `theteam_report.py` is at repo-root `bin/`, outside it. Neither is part of the
  user-facing CLI. The config script imports `bin.utilities` as a top-level package,
  so it needs `theteam/` on the path; the report script imports only the standard
  library and needs nothing." / `python3 bin/theteam_report.py build \`
- **Why this is enough:** Both invocations now name files that exist — verified by
  running each: the config script prints `OK: Config is valid`, and the report script
  prints its usage line. The section heading no longer asserts both live in `theteam/bin/`,
  which is what made the second invocation look like it belonged beside the first.

### ARCHITECTURE.md claimed the report script was deleted
- **File:** `ARCHITECTURE.md:548`
- **Was:** "`ui/components/reflex_renderers.py`, `ui/components/visibility.py`, `bin/theteam_report.py`, and `skill/SKILL_metadata.py`."
- **Now:** "`skill/SKILL_metadata.py`. `bin/theteam_report.py` was **moved** to repo-root `bin/`, not deleted."
- **Why this is enough:** The deletion list is a claim that these paths no longer exist;
  `bin/theteam_report.py` exists and runs, so it is moved out of the list and stated
  as a move. Every other entry in the list was left alone.

### Stale test count (ONBOARDING.md)
- **File:** `theteam/ONBOARDING.md:77`
- **Was:** `└── tests/                    # 659 tests`
- **Now:** `└── tests/                    # 762 tests`
- **Why this is enough:** `python3 -m pytest --collect-only` reports `762 tests collected`;
  the count is now the measured one.

### Stale test count (README.md)
- **File:** `README.md:210`
- **Was:** `python -m pytest -q                  # 659 tests`
- **Now:** `python -m pytest -q                  # 762 tests`
- **Why this is enough:** Same measurement, same correction.

### Eleven vs. twelve subcommands (README.md)
- **File:** `README.md:53`
- **Was:** `Eleven subcommands. \`--json\` works on **either side** of the subcommand for every one of them.`
- **Now:** `Twelve subcommands. \`--json\` works on **either side** of the subcommand for every one of them.`
- **Why this is enough:** README's own table below the line has twelve rows, and
  `--help` lists twelve; the count now matches the table it introduces.

### Eleven vs. twelve subcommands, and `manager` missing entirely (ARCHITECTURE.md)
- **File:** `ARCHITECTURE.md:91,93`
- **Was:** a command block ending at `theteam watch status|tasks|history` /
  `Eleven subcommands. The list is the whole surface; nothing else is declared.`
- **Now:** the block gains `theteam manager                     grow the roster from a topic` /
  `Twelve subcommands. The list is the whole surface; nothing else is declared.`
- **Why this is enough:** Fixing the count alone would have made the document false in a
  new way — it says "the list is the whole surface," and `manager` was absent from it.
  The row was added because the doc asserts completeness. A matching row was added to
  the §2 flags table (`ARCHITECTURE.md:114`), which was missing it for the same reason.

### `core/` module count, and an unowned live module
- **File:** `ARCHITECTURE.md:515-516,548`
- **Was:** "`core/` holds 23 modules. The tree above names 8; this table assigns the rest, so no module is unowned." (with no row for `run_context.py`)
- **Now:** "`core/` holds 21 files: 20 modules plus the package's `__init__.py`. The tree
  above names 7; this table assigns the other 13, so no module is unowned." — plus
  `| run_context.py | 2 Task | cli.py (write_run_context, after the sweep) — proven live.
  Read by workflow/context_aggregator.py for member delivery (§5.6). |`
- **Why this is enough:** `theteam/core/` holds 21 `.py` files, and the table's stated
  purpose is that nothing is unowned — which was false, because `run_context.py` is
  imported at `cli.py:26` and appeared in neither the §5.2 tree nor this table. The
  count, the split, and the row now agree with the directory listing. (7 named in the
  tree + 13 rows = the 20 modules.)

### ONBOARDING.md's package tree omitted a live module
- **File:** `theteam/ONBOARDING.md:65-67`
- **Was:** `│   └── state_manager.py, checksum.py, database.py, wal.py,` / `│       transactions.py, correlation.py, member.py, postgres_cluster.py`
- **Now:** the two lines above with their box-drawing markers changed to `├──` / `│   │`, plus `│   └── run_context.py        # \`.omp/theteam/context.md\`, written by every run`
- **Why this is enough:** The section is headed "Package layout, as it is now" and
  enumerates `core/` file by file, so an omitted live module is a false claim about
  the present, not merely an incomplete diagram. One line names it; the branch markers
  were corrected so the tree still reads as a tree.

### §3.1's sample `status` output was not the shape the command prints
- **File:** `ARCHITECTURE.md:255-271`
- **Was:** a six-line sample beginning `roster 5 members active` / `session ~/.omp/agent/sessions/...` / `session events 289 message events, 1.85 MB, last read 14s ago` / `commentary on, last spoke 3 turns ago, digest a4f2...` / `tasks 4 registered, 1 due, 0 breaker trips` / `audit chain intact, 142 entries, last verified 14s ago`, followed by "If the session file is missing, `session` reads `not found`..."
- **Now:** the five lines `status_payload()` actually builds — `project`, `state`,
  `roster`, `tasks`, `audit chain` — followed by "Those are the five lines
  `status_payload()` builds, and `status` emits them unchanged. **The session file is
  not among them**... The session state is on `theteam comment status`, which reports
  the `last_digest` the commentary controller last saw."
- **Why this is enough:** `status_payload` (`theteam/cli.py:265-317`) has no `session`,
  `session events`, or `commentary` line — the three lines were deleted rather than
  hedged, and the surviving five are the ones the function's `lines` list builds,
  including the `chain_line()` format for the audit row. The sample's invented
  `not found` reading was removed along with the line it described.

### §1.2's checkable promise named a field the payload does not carry
- **File:** `ARCHITECTURE.md:56`
- **Was:** `| The team reads your real session | \`theteam status\` shows the session file path, its event count, and the digest the team last saw |`
- **Now:** `| The team reads your real session | \`theteam comment status\` reports the \`last_digest\` the commentary controller last saw, and a tick over a missing session reports \`{spoke: false, reason: "no_session"}\` |`
- **Why this is enough:** The promise is stated as a test the user can run, and no
  `theteam status` output contains the path, the count, or the digest. Both facts the
  promise rests on are real and checkable, just on the command that owns them:
  `last_digest` is in the `comment status` payload (`cli.py:937`), and `no_session` is
  the controller's reason for a missing session file.

### §7.1 invariant 1 could not pass on any project
- **File:** `ARCHITECTURE.md:1139`
- **Was:** `1. \`theteam status\` on a bootstrapped project shows a roster, a bound session, and an intact audit chain.`
- **Now:** `1. \`theteam status\` on a bootstrapped project shows a roster, the state directory, task counts, and an audit chain that reads \`intact\` or names its absence. It reports no session.`
- **Why this is enough:** "A bound session" is unreachable — `status_payload` has no
  session field, so no project satisfies this invariant as written. The replacement
  lists what the command does report and states plainly that it reports no session,
  so an auditor running it finds the product working rather than broken.

### The same false claim, third occurrence
- **File:** `ARCHITECTURE.md:928`
- **Was:** "**Falsification test:** run commentary for 10 turns. At most 2 fragments per turn. `stop` in the user message produces `{spoke: false, reason: "stopped"}`. `theteam status` shows the session path and event count."
- **Now:** the same sentence with the trailing `theteam status` clause deleted.
- **Why this is enough:** Same defect as §1.2 and §7.1, in the M5 gate. The clause was
  cut rather than redirected, because the other two clauses of the falsification test
  were verified true and the gate's value does not depend on it.

---

## Passed through untouched

- **`ARCHITECTURE.md:341`** — the 289-event / 1.85 MB live-session measurement. Marked
  `could-not-verify` by the audit: it describes a session file that is not in this
  repository, so there is nothing to measure it against. Left verbatim. Note that its
  figures no longer appear in §3.1's sample output, because that output was corrected.
- **`ARCHITECTURE.md:352-362`** — the `SessionSlice` field set and the K defaults. Marked
  `could-not-verify`: the audit did not read `advisory/session_reader.py`. Not checked
  here either; no field, default, or bound was changed.

## Not edited, for the record

- **`ARCHITECTURE.md:1242`** — "744 tests passed" in the M7 audit record. The audit judged
  this defensible as a dated historical entry, so it was left alone. It is genuinely
  stale relative to 762, and deliberately remains so.
- **`README.md:62`** — the `tasks` row omits `breaker_consecutive_failures`, which
  `ARCHITECTURE.md:102` lists. The audit recorded this as a minor omission rather than a
  contradiction, so it is not a finding and was not touched.
- **`scripts/smoke_cli.py`'s "23 checks"** (`theteam/CLI.md:53`) — the audit did not run
  the script, so its check count is unverified either way.

## Follow-up tasks (wrong code, not wrong docs — reported, not fixed here)

These are the findings where the code is the defect. No code was edited in this phase.

1. **`theteam status` has no session surface.** §1.2 and §7.1 were promises the product
   made to itself, and the session-reading capability exists in `advisory/` and is
   reported by `comment status`. Either wire the session state into `status_payload`,
   or accept that `comment status` is the command that owns it — the second is what the
   docs now say, so this is a decision, not a bug, but it should be made deliberately.
2. **The report script has two homes.** A copy of the same tool exists at repo-root
   `bin/theteam_report.py` and is gone from `theteam/bin/`, while `theteam/__init__.py:936`
   resolves it as `os.path.join(os.path.dirname(CURRENT_DIR), "bin", "theteam_report.py")`
   — i.e. relative to the *package's parent*, the repo root. The code is self-consistent
   with the move and the docs now agree with it. Worth confirming that the root `bin/`
   location is intended to be permanent rather than an artifact of the move.
3. **`run_context.py` was never assigned a layer.** It is imported at `cli.py:26` and
   documented at §5.6, but until this phase it appeared in neither the §5.2 tree nor the
   §5.2.1 ownership table, despite that table existing to prevent exactly this. §5.2.1
   now assigns it Layer 2 — that assignment is this phase's reading of what it does
   (it writes per-run state that `cmd_run` reads back), and should be reviewed.