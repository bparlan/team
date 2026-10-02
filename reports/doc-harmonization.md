> Copied from `.omp/theteam/reports/` on 2026-10-01. That path is gitignored as
> runtime state, so the reports live here to survive a fresh clone. The
> originals remain in `.omp/theteam/reports/` and are the ones the tasks write.

# Doc harmonization — second pass

Input: `reports/ground-truth-audit.md` (9 findings, all `Confidence: verified`).
Every edit was applied after re-reading the cited region and confirming it matched the audit's
quotation. Three files touched: `ARCHITECTURE.md`, `README.md`, `tasks/README.md`. No code was
edited; no new `.md` file was created.

The run1 report and run1 audit were left read-only, as instructed.

---

## Findings handled

### The milestone diagram's HTML and JSON do not agree
- **File:** `ARCHITECTURE.md:13`, `:21-28`
- **Was:** "The committed `.html` and `.json` are a consistent pair of seven milestones" … "An 11-milestone JSON was built with M7–M10 added" (framed as a discarded experiment) … "**The milestone diagram is frozen at seven milestones**, and its HTML and JSON agree."
- **Now:** "The committed `.json` carries eleven milestones (`m0`–`m10`); the committed `.html` renders seven (`m0`–`m6`), so the pair is out of sync" … "The committed `.json` is the 11-milestone source (M7–M10 added to the original seven) … The committed `.html` is the seven-node render from before M7–M10 landed, so the pair is out of sync, and regenerating either is blocked by the tool, not by the content."
- **Why this is enough:** the paragraph now states which of the two committed files is the 11-milestone one and which is the 7-milestone one, so no reader is told they match.

**Follow-up (not a document fix):** the generated artifacts are still out of sync. Regenerating
`diagrams/active-usage-milestones.html` from the 11-node JSON is a task, not an edit to this
document; `archify` is currently refusing the source, which is the reason the document gives.

### The delivery-order diagram renders M0–M6, but the authoritative JSON holds eleven
- **File:** `ARCHITECTURE.md:10`, `README.md:202`
- **Was:** "| Delivery order | Part 6, the seven milestones this diagram can render |" and "| Delivery order | M0–M6 and their gates |"
- **Now:** "| Delivery order | Part 6, the seven milestones this diagram renders (the JSON next to it carries eleven, M0–M10) |" and "| Delivery order | M0–M6 and their gates (the JSON next to it carries M0–M10) |"
- **Why this is enough:** each table now says what the HTML renders and what the JSON beside it carries, which matches `README.md:204-205`'s own rule that the JSON is authoritative.

### Part 6 says "Nine milestones"; it has eight sections
- **File:** `ARCHITECTURE.md:792`
- **Was:** "Nine milestones, ordered by user-visible outcome, not by subsystem. … M7 and M8 shipped before M9 was written and are recorded in `theteam/CHANGELOG.md`; both were documentation audits rather than new capability, so neither has a section here."
- **Now:** "Eight milestones, ordered by user-visible outcome, not by subsystem. … M7 and M8 … neither has a section here. M10, M11 and M12 are recorded in `theteam/CHANGELOG.md` and have no section here either."
- **Why this is enough:** the count now matches the eight `## M<n>` headings, and the sentence no longer leaves M10–M12 unexplained the way it left M7/M8 unexplained.

Per the audit's reasoning the count was taken from the headings (eight) rather than from the
milestones that exist in total (twelve), because the sentence introduces the sections that follow.

### The YAML repository carries five tasks, not six
- **File:** `ARCHITECTURE.md:795-796`
- **Was:** "the YAML repository carries six, so the count is now taken from `TaskRepository` rather than asserted here."
- **Now:** "the YAML repository carries five, so the count is now taken from `TaskRepository` rather than asserted here."
- **Why this is enough:** the sentence's own justification for delegating the count to `TaskRepository` no longer contradicts it. Confirmed: `TaskRepository('.').list_tasks()` returns five, and `tasks/` holds five `task-*.yaml` files.

### `tasks/README.md` still listed the deleted `system-awareness` task
- **File:** `tasks/README.md:16`, `:24`, `:91`, `:347`, `:212-215`
- **Was:** a `| \`system-awareness\` | 2 | script | … |` row in "Current tasks"; "`theteam tasks` displays the *sequence position* (0-5 here)"; `system-awareness` in the **Routine** row and in the self-sufficiency table; "`system-awareness` … it now runs green."
- **Now:** the row is gone; "(0-4 here)"; Routine is `project-integrity`, `maintenance`; the self-sufficiency row is gone; and the failure-history bullet reads "The `system-awareness` task, since deleted, failed five times before its fixes landed … All were fixed before its removal."
- **Why this is enough:** `theteam run --only system-awareness` reports `Task not found`, so a current-state table may not list it; the dated failure-history sections are retained but marked as about a deleted task rather than a live one.

The Routine table and the sequence-position line were the two stale cross-references the deletion
created, so they were fixed with the row rather than left behind.

### A missing task script is not rejected at `task create`
- **File:** `ARCHITECTURE.md:285`
- **Was:** "| Task script missing | Rejected at `task create`. Also reported by `run` if it disappeared after creation. |"
- **Now:** "| Task script missing | Not checked at `task create`. Reported by `run` as `missing script: <path>`, recorded as a skip. |"
- **Why this is enough:** `TaskRepository._check_writable` (`repository.py:72-86`) validates only `id` and `memory_limit_mb` and never touches the filesystem, so the row now states the behaviour the product actually has.

The neighbouring true claim at `ARCHITECTURE.md:637` about `memory_limit_mb` being rejected at
write time was left untouched, as instructed.

**Follow-up (the code is the defect, not the document):** the product performs no write-time
existence check on a phase's `script:`, so a task pointing at a nonexistent file is created
successfully and fails later as a skip. Whether write-time validation *should* exist is a product
decision, not a documentation one; recorded here for a task rather than fixed here.

### §2.3 cited three `routines/*.md` files and two symbols that do not exist
- **File:** `ARCHITECTURE.md:203-206`
- **Was:** "`routine` was also already a loaded noun in this repo (`RoutineScheduler`, `run_routine`, three `routines/*.md`) belonging to a different data model — markdown phases rather than YAML."
- **Now:** the sentence is deleted; the paragraph reads "**`loop` was not renamed.** It schedules one registered task once and prints `next_run`; it does not iterate, so `routine` would promise a repetition the command does not perform. If the name ever reads wrong, `schedule` is the accurate one: it maps 1:1 onto `TaskRepository.schedule_task`."
- **Why this is enough:** the paragraph's actual argument — `loop` does not iterate, so `routine` over-promises — is self-contained and needs no external evidence, and the ungreppable evidence it cited is gone.

`routines/` does not exist and `RoutineScheduler` / `run_routine` have no hit in `theteam/**/*.py`.
A first attempt replaced the sentence with a description of `config/routine-engine/`; that was
withdrawn on inspection because the five files there are engine configuration
(`routines.yaml`, `routines_engine.yaml`, `engine_config.json`,
`auto_discovery_config.json`, `interactive_config.json`) and none of them defines markdown phases.
Rather than substitute a claim I could not verify, the sentence was deleted.

**Follow-up:** `config/routine-engine/` is still git-tracked and is described nowhere in any
document read by the audit. Whether it should be documented or removed is a task.

### `web_search` did not join `permitted_skills`
- **File:** `ARCHITECTURE.md:955`, `:1096-1098`, `:1122-1123`
- **Was:** "**Decisions locked 2026-09-30.** `web_search` joins `permitted_skills` for members and manager." (plus "the `web_search` default plus **a note that it was added by user request on 2026-09-30 and why**" in the Phase 6 plan, plus the open question "Does `web_search` belong in `permitted_skills`, or a separate `research_tools` key?")
- **Now:** "**Decisions locked 2026-09-30.** `permitted_skills` stays at its three defaults — `ponytail`, `evolve-skills`, `code-search` — for members and manager; `web_search` was not added." The Phase 6 plan item now reads "the `permitted_skills` default of `ponytail`, `evolve-skills`, `code-search`", and the open question is deleted.
- **Why this is enough:** all three passages asserted the same widening, and the product's default is the three skills `SKILL.md:202` and `ONBOARDING.md:101` already state correctly, so `ARCHITECTURE.md` is now the one that agrees with the code.

`grep -rn "web_search" theteam/ --include="*.py"` returns nothing. The two other documents were
already correct and were not edited.

### The architecture diagram has 13 components and 12 connections, not 12 and 14
- **File:** `README.md:270`
- **Was:** "Its 12 components and 14 edges are factually correct and every source path is verified against git"
- **Now:** "Its 13 components and 12 connections are factually correct and every source path is verified against git"
- **Why this is enough:** the counts now match `diagrams/active-usage-architecture.json`
(`components` = 13, `connections` = 12), and the surrounding sentence — that the source paths are
correct and the remaining issues are composition geometry — is unchanged and still true.

### §7.2 invariants 3–5 were stricter than the gate that enforces them
- **File:** `ARCHITECTURE.md:1153-1155`
- **Was:** "3. `grep -rn "/Users/bparlan" theteam/` returns nothing. 4. `grep -rn "parents\[" theteam/` returns nothing. 5. `grep -rn "\.mp/theteam" theteam/` returns nothing."
- **Now:** "3. No hardcoded developer paths. `grep -rn "/Users/bparlan\|~/devcode/team" theteam/ scripts/ --include="*.py"` returns nothing outside `scripts/sa_runner.py:230-249`, where the literal survives in a comment and a default-state branch the gate exempts by name. 4. `grep -rn "parents\[" theteam/ --include="*.py"` returns nothing. 5. No `.mp/theteam` references outside the guard that rejects them. `grep -rn "\.mp/theteam" theteam/ --include="*.py"` returns nothing but `DEAD_DIR = ".mp/theteam"` (`tasks/repository.py:34`), the guard's own comment, and `tests/test_task_repository.py`."
- **Why this is enough:** each invariant now states the scope the gate actually enforces — `--include="*.py"`, `scripts/` as well as `theteam/`, and the named exemptions — so running the three as written reproduces the gate's 7/7 PASS instead of failing on `__pycache__/*.pyc` and the guard's own text.

The invariant is unchanged in strength: the guard that *rejects* `.mp/theteam` is still the only
place the string is allowed to appear, and a new stray reference still fails. The document had
overstated the invariant, not the gate.

---

## Checked and deliberately not changed

| Claim | Source | Why left alone |
|---|---|---|
| "744 tests passed" | `ARCHITECTURE.md:1252` | The audit records it as defensible: it is a dated figure inside a section describing a past verification, not a live count. The live count is carried elsewhere (`README.md:210`, `ONBOARDING.md:78`, both 762). |
| The M7 Plan-evaluation table | `README.md:247-276` | A dated historical record of what the M7 audit found. Its "what it claimed" column is false against the current tree by design; its corrections describe what was true then. The audit confirmed the present state matches. |
| `memory_limit_mb` rejected at write time | `ARCHITECTURE.md:637`, `:681-682` | Verified true, and adjacent to finding 5 but a separate claim. Not named as a defect, so untouched. |
| M0's "584 tests" and the M9 starting-state table | `ARCHITECTURE.md:863`, `:963-972` | Dated baselines for milestones delivered against a different tree. |

## Follow-ups for a task, not for this phase

1. **Regenerate the milestone diagram.** `diagrams/active-usage-milestones.html` (7 nodes) is out
   of sync with `diagrams/active-usage-milestones.json` (11 nodes). Both are generated artifacts and
   were not hand-edited. Blocked on `archify` refusing the source for
   `composition/desktop-readability`.
2. ~~**Decide whether a missing phase script should be rejected at write time.**~~ **Decided:
   no, by design.** A task YAML is version-controlled and its script may legitimately be written
   after the task is created, in the same commit series; an existence check would reject valid
   work-in-progress. `_phase_problem` already reports `missing script: <path>` as a named skip,
   which is an honest report rather than a silent one. The reasoning is now recorded at
   `ARCHITECTURE.md` §3.2 so it does not reopen as a defect.
3. ~~**`config/routine-engine/`** is git-tracked, is the surviving residue of the `routine-engine/`
   removal described at `ARCHITECTURE.md:180`, and is documented nowhere. Document or remove it.~~
   **Documented** — `ARCHITECTURE.md` §5.3.1 now records what the 5 files are and why nothing reads
   them, measured rather than asserted: no code references them by name, `pyproject.toml` packages
   only `theteam*`, and none is a valid task under §5.4. They remain on disk; deletion is still a
   separate decision. Corrected once before recording: an earlier draft attributed the deletion to
   M0 and said M0 "missed" the files. `CHANGELOG.md:683` puts the deletion in M10 Phase 3, and
   `git show 71ee8d0` shows M0 **committed** all 403 lines — the milestone that removed orphaned
   files added these.
4. **`ARCHITECTURE.md:341`** (live-session statistics: 289 message events, 1.85 MB, role and part
   counts) remains unmeasurable — it describes a session file not in this repository. Carried
   forward unchanged from run1.

## Verification performed

- `bash scripts/check_invariants.sh` → `check 1 PASS` … `check 7 PASS`, `invariant gate PASSED`,
  run after every edit to `ARCHITECTURE.md` §7.2.
- `TaskRepository('.').list_tasks()` → 5 tasks, ids `project-integrity`, `maintenance`,
  `ground-truth-audit`, `doc-harmonization`, `native-feature-loop`.
- `python3 -c` on both diagram JSONs → milestone nodes 11 (`m0`–`m10`), subtitle "Eleven
  milestones…"; architecture components 13, connections 12.
- `grep -o 'data-node-id="m[0-9]*"'` on both HTMLs → milestone HTML 7 (`m0`–`m6`), architecture
  HTML 13, matching its JSON.
- Every touched region re-read after editing, plus a repository-wide grep for `web_search`,
  `RoutineScheduler`, `routines/*.md`, `12 components`, `carries six`, `Nine milestones`, and
  `0-5 here` to confirm no stale cross-reference to a removed claim was left behind.
- `git diff --stat` → 3 files, +26/−31.

---

## Post-audit work (after this phase closed)

Recorded so this report does not misrepresent the tree. Both audit passes and both
harmonization passes were docs-only, as the task requires. The changes below came
afterwards, from following up on the audit's own follow-up list, and they **do**
touch code — so the "`git diff --stat` → 3 files" line above no longer describes
the repository.

### 1. The write-ahead log leaked into the repo root (code defect, fixed)

`UnifiedStateManager.__init__` called `WriteAheadLog()` with its default, a bare
`"wal.json"` resolved against the process CWD — ignoring the `state_file` the
constructor was handed. A manager pointed at a tmpdir therefore appended to
whichever directory the suite was launched from, which is how the git-tracked
`wal.json` at the repo root filled with pytest fixture state on every run. It was
reverted twice during this work and would have reappeared on any local test run.

Fixed by `state_manager._wal_path_for()`: the WAL now sits beside `state.json`,
or under a pid-and-uuid name in the temp dir when there is no state file.

### 2. The first fix introduced a second defect (code defect, fixed)

The stateless fallback was initially a fixed `theteam-wal.json` in the shared temp
dir. The suite constructs **14** stateless managers across two test files, and
`load_state` calls `replay_entries()`, so they would have interleaved entries in
one file and replayed each other's state. Now unique per manager.

### 3. Documentation drift caused by 1 and 2 (docs, fixed)

- `ARCHITECTURE.md` §5.5 lists the contents of `.omp/theteam/`. The change puts
  `wal.json` in that directory in production (`__init__.py:699` passes
  `.omp/theteam/state.json`), so the listing gained the entry.
- The same section claimed "Every name above is one `theteam/state.py` resolves."
  That is now "every name above **but one**", naming `wal.json` and why it is
  resolved by `state_manager._wal_path_for` rather than `StateStore`.
- Added the placement rationale: why not the CWD default, and why the stateless
  fallback is pid-and-uuid.
- Test counts went stale in two places the moment the 3 new tests landed, which is
  the defect class this whole task pair exists to eliminate: `README.md:210` and
  `theteam/ONBOARDING.md:78` → 765.

### 4. Tests

Three added to `theteam/tests/test_state_manager.py`, each proven to fail when its
fix is reverted:

- `test_wal_is_written_beside_the_state_file`
- `test_wal_without_a_state_file_never_lands_in_the_cwd`
- `test_wal_without_a_state_file_is_unique_per_manager`

### 5. Verification of the above

- `python3 -m pytest -q` → **765 passed, 7 subtests** (762 + 3 new)
- `bash scripts/check_invariants.sh` → **7/7 PASS**
- Full suite run leaves the tracked `wal.json` unmodified
- `_wal_path_for` behaviour confirmed directly for both branches
- Working tree is clean: auto-checkpoints `ba84a6d` and `ab9a996` committed the WAL fix,
  the tests, the count corrections, the `§5.5` and `§5.3.1` edits, and the gate comment. The
  changes listed above are on disk, not pending.

### 6. The invariant gate's own comment repeated the false claim (code, fixed)

`scripts/check_invariants.sh` is named in `prompts/ground-truth-audit.md` as a source of
*executable claims*, so its rationale is documentation and is held to the same standard.
Check 3's comment said `sa_runner.py` "is excluded because its default-state branch is the one
place a literal path is not a resolution — it was corrected there, and the string survives in a
comment explaining why." That was the same stale premise `ARCHITECTURE.md` §7.2 invariant 3
carried: the branch was corrected, so it no longer holds a literal, and the only surviving match
is the comment at `:236`.

The comment now states what the exclusion actually does, and why it still has to exist — the
carve-out matches the comment, so removing it would fail the check on the comment alone. Comments
only; the `grep` pipeline is untouched and the gate is still 7/7.
