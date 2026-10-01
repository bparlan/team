> Copied from `.omp/theteam/reports/` on 2026-10-01. That path is gitignored as
> runtime state, so the reports live here to survive a fresh clone. The
> originals remain in `.omp/theteam/reports/` and are the ones the tasks write.

# Self-audit — this session's own changes

The two audit/harmonization cycles covered documents, not code. This session then changed
code (`state_manager.py`, `check_invariants.sh`) and documentation, and **none of it was
independently audited**. This closes that gap.

An earlier attempt at this audit crashed after 24 minutes without writing its report, and its
transcript contained no recoverable conclusions. The findings below were therefore produced by
direct verification against the source.

Audited: uncommitted diff (`ARCHITECTURE.md`, `scripts/check_invariants.sh`) and commit
`ba84a6d` (the WAL fix, three tests, test-count corrections).

---

## Findings

### §5.5 claimed one exception to "every name is a `StateStore` name"; there are two
- **Claim:** "Every name above but one is one `theteam/state.py` resolves. The exception is
  `wal.json`…" — `ARCHITECTURE.md:719` (as written by this session)
- **Code says:** `context.md`, also listed at `ARCHITECTURE.md:701`, is written at
  `core/run_context.py:433` as `state_dir(str(root)) / "context.md"` — it is built from
  `state_dir()`, not from a `StateStore` property. `theteam/state.py` contains no `context`
  name at all. So the list has two exceptions, not one.
- **Difference:** A reader auditing §5.5 against `state.py` finds `context.md` unaccounted for
  after being told exactly one name is, and concludes the section is wrong.
- **Confidence:** verified
- **Fixed in place:** the claim now reads "but two", naming both `wal.json` and `context.md`
  with the line that writes each.

---

## Verified accurate

| Claim | Source | Evidence |
|---|---|---|
| `sa_runner.py:236` holds a comment, not a live literal | `check_invariants.sh:38-45` | `sed -n 236p` → `# Was the literal "~/devcode/team/tasks".` The branch it describes now holds `"task_archive": "tasks"` (`:242`). |
| The carve-out still matches that comment | `check_invariants.sh:45-46` | Regex `^scripts/sa_runner.py:2[34][0-9]:` covers line 236; the only match under `scripts/` is that comment. Removing the carve-out would fail the check on the comment alone. |
| Check 3 scans `theteam/` and `scripts/`, so the "nothing tripped" rationale holds | `check_invariants.sh:46-47` | Pipeline is `grep -rn … theteam/ scripts/ --include="*.py"`. Ran it: `check 3 PASS`. |
| M0 committed the 5 `config/routine-engine/` files | `ARCHITECTURE.md:610` | `git show --shortstat 71ee8d0 -- config/routine-engine/` → `5 files changed, 403 insertions(+)`. The milestone that removed orphaned files added these. |
| `routine-engine/` was deleted in M10 Phase 3 | `ARCHITECTURE.md:610` | `CHANGELOG.md:683` is `### Phase 3 — routine-engine/ deleted`, under `## M10 — One scheduler` at `:619`. |
| Nothing reads the 5 config files by name | `ARCHITECTURE.md:610` | `grep -rn` for all five filenames across `*.py`/`*.sh`/`*.yaml` outside the directory → no hits. |
| `pyproject.toml` packages only `theteam*` | `ARCHITECTURE.md:610` | `pyproject.toml:23` → `include = ["theteam*"]`. |
| Test count 765 | `README.md:210`, `theteam/ONBOARDING.md:78` | `pytest --collect-only -q` → `765 tests collected`. |
| `get_tasks_by_member` is byte-correct after this session's corruption-and-repair | `theteam/core/state_manager.py` | Diffed against pre-session `206ff19`: the method matches exactly. `git diff` on the file shows no changes to it. |
| `uuid` is imported where used | `theteam/core/state_manager.py` | `import uuid` at `:17`, used at the `_wal_path_for` fallback. |
| The three new tests assert the real contract | `theteam/tests/test_state_manager.py` | Each was observed to **fail** when its fix was reverted: reverting `_wal_path_for` fails 2, and pinning the fallback to a fixed path fails the uniqueness test (`assert 1 == 3`). `WriteAheadLog`'s default is the relative `'wal.json'`, which is what makes the CWD assertion meaningful. |
| §5.5 prose matches both `_wal_path_for` branches | `ARCHITECTURE.md:722-729` | With a state file → `<state_dir>/wal.json`. Without → `theteam-wal-<pid>-<uuid>.json` under `tempfile.gettempdir()`. Matches the documented behaviour. |

---

## Not checked

- ~~**The `"five scripts"` count in the check-3 comment.**~~ **Verified true.** `git grep -l
  "devcode/team" 9671d3d -- scripts/` returns exactly five files — `check_invariants.sh` itself
  (the comment), `loop_state.py`, `sa_runner.py`, `security_policy.py`, `task_executor.py`. That is
  the commit where check 3 gained its `scripts/` scope, so the count describes exactly the state
  the comment is about. Four were fixed; `sa_runner.py` retains the comment at `:236` that the
  carve-out still matches. No action.
- **Rendered geometry of `diagrams/*.html`.** `archify` is unavailable in this environment.
  Only node-id sets and counts were compared against the JSONs.
- **`ARCHITECTURE.md:341`'s live-session statistics.** Unmeasurable: it describes a session
  file not in this repository. Carried forward unresolved from both earlier passes.
- **Whether the `config/routine-engine/` files *should* be deleted.** Documented, not decided.
