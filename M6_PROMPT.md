# OMP Prompt — Milestone M6: The terminal shows the truth

Fresh OMP session at `/Users/bparlan/devcode/team`. **First milestone not named in
`ARCHITECTURE.md` Part 6** — Part 6 ends at M5. This one is added, not inherited.

Advisor mode ON; read-only (`read`, `grep`, `glob`), cannot execute. You supply evidence.

---

## PROMPT START

M0–M5 done and committed. 718 tests, gate green on 6/6. Task store is YAML-only, safety
layer is wired and falsified, the advisory layer reads real OMP sessions and speaks when
there is something to say.

M6 builds the **terminal renderer** — the management and monitoring surface a user can
drive from inside the terminal they are already in. A five-member review deferred this
until after M4 precisely so that what it displays is real. That condition is now met.

**Read:** `ARCHITECTURE.md` §5.1 (layers), §5.2 (`ui/` — note it was rewritten during M4
and now says no TUI is wired; correct it as part of this milestone), §3.3, §7.1. Then
`theteam/ui/components/visibility.py` in full, and `theteam/cli.py`'s existing `status`,
`tasks`, `history` commands.

### Baseline

```bash
cd /Users/bparlan/devcode/team
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5
bash scripts/check_invariants.sh; echo "gate exit=$?"
python3 -m theteam.cli --project-root . status --json
```

Expect 718 and exit 0. Different? Stop, report, do not edit.

---

### C1 — `build_visibility` is a reflex-shaped function, and that is the problem

`theteam/ui/components/visibility.py:21` is the boundary the team review chose, and it is
the right boundary. But look at what it returns:

```python
"recovery_lines": "\n".join(...)   # Joined text, not a list: reflex cannot
                                   # foreach an untyped nested Var.
```

The comment says why. That constraint is reflex's, not the domain's. `recovery_lines` is a
string where a list belongs, and every future consumer inherits a workaround for a UI
framework this project does not use.

**Decide before you write a renderer.** Two honest options:

- **(a) Return the list.** Change `recovery_lines` to a list of strings, and let the
  renderer join it. Costs one line, breaks reflex, which is not installed and has no
  milestone.
- **(b) Keep it, and say why in the docstring.** The field is used by no live caller today.
  If you keep a reflex-shaped compromise, name the framework it serves.

Prefer (a) unless you find a live consumer I have not. Do not build a renderer that works
around a constraint for a UI that does not exist.

### C2 — the data is available, and it is honest

Every input `build_visibility` needs already exists as command output. No new data source
is required, and inventing one is the failure mode this milestone could plausibly fall into:

| View | Source today |
|---|---|
| status | `theteam status --json` — roster, task counts, breaker trips, audit chain state |
| tasks | `theteam tasks --json` — id, order, next_run, last_result, breaker, consecutive |
| history | `theteam history --json` — runs, success_rate, last_failure, consecutive |

Note the honest absences, which the renderer must **pass through, not fill in**: an absent
audit chain reports `intact: null, state: "absent"`; an unrun task reports `breaker: null`.
A renderer that prints `closed` or `intact` for those is fabricating (§3.3), and that is
the one thing this milestone must not do.

### C3 — the command surface

`ARCHITECTURE.md` §2 names the user-facing commands. M6 adds one:

```
theteam watch [status|tasks|history]   the trust surface, in the terminal
```

`--once` renders a single frame and exits (this is what the test suite calls). Without
`--once` it re-renders on an interval. `--interval N` seconds, default matching the cadence
you choose — name it in `--help`.

`theteam status`, `tasks`, `history` **do not change output**. They are the machine
surface. A TUI that improves them by rewriting their output has broken the agentic
interface §2 promises.

---

### R1 — the boundary, written down before any renderer exists

`state.py` → `build_visibility()` → **one** renderer. Presentation is a pure function of
state, never a peer. Write the contract first, in `build_visibility`'s docstring or a
test, so a second renderer cannot grow its own adapter. That is exactly how
`task_stack_adapter.py` came to exist in M2.

Test: two different inputs produce different view models, and the view model contains no
path resolution, no file reads, and no subprocess. It is a pure function.

### R2 — the renderer

`theteam/ui/terminal.py`.

**The `rich` decision — read the measurement, not the vibe.** Measured this session:

```bash
python3 -c "import rich; print('IMPORT OK')"          # IMPORT OK on THIS machine
grep -c rich requirements.txt                          # 0 — not declared
grep -A2 '^dependencies' pyproject.toml                # dependencies = []
grep -n 'pip install' .github/workflows/ci.yml         # pip install -e . ; pip install pytest
```

`rich` 14.3.4 is installed **in this pyenv only**, transitively. `pyproject.toml` declares
`dependencies = []` and CI installs from that. So rich is **present here and absent on
every clean CI runner.** A renderer that imports rich at module scope passes the 718-test
suite on your machine and turns it red in CI — the exact "green locally, red in CI"
failure that `test_invariant_gate.py` was written to close.

Pick one, and make the suite honest either way:

- **(a) Use rich.** Add `rich>=13` to BOTH `requirements.txt` and `pyproject.toml`
  `dependencies` (they must agree; the repo currently keeps PyYAML in `requirements.txt`
  and declares nothing in `pyproject.toml`, which is itself drift worth fixing). Then
  verify against a clean environment, not this one:

  ```bash
  python3 -m venv /tmp/clean && /tmp/clean/bin/pip install -q -e . pytest && \
    /tmp/clean/bin/python -m pytest theteam/tests/ -q --no-header 2>&1 | tail -3
  ```

- **(b) Use stdlib.** `curses`, or plain `print`. Zero dependency, and the whole
  environment story stays as it is. A terminal renderer that needs a rendering library to
  print three tables has defeated its own purpose.

**Whichever you pick: no import of a third-party library at module scope without it being
declared in `pyproject.toml`.** If rich is genuinely optional, the import goes inside the
function with a fallback, and the test asserts the fallback path. An undeclared import is
not "optional", it is a broken clone.

Three views, from the review:

- **status** — the trust screen. Roster, task counts, breaker trips, audit chain state.
- **tasks** — id, order, next run, last result, breaker state.
- **history** — success rate, last run, last failure, consecutive failures.

Nothing else is scope. No config file, no theme, no colour scheme beyond what
`design_tokens.py` already defines, no plugin system.

`design_tokens.py` exists and is tested — use it for severity colours and state visuals
rather than inventing a second palette. The state semantics are already decided: `open` is
the **bad** state, `closed` is good.

### R3 — no fabricated values, ever

Every cell traces to a command output. Nulls render as `-` or "never run", never `0`, never
`closed`, never `intact`. `build_visibility` already does this; the renderer inherits it
or breaks it.

One test: given a project with an absent audit chain and unrun tasks, the rendered output
contains no `closed`, no `intact`, and no `0%`. Assert the absence.

---

### Verify

```bash
cd /Users/bparlan/devcode/team
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5     # no regression
bash scripts/check_invariants.sh; echo "exit=$?"                    # 6/6
python3 -m theteam.cli --project-root . watch status --once         # renders, exits 0
python3 -m theteam.cli --project-root . watch tasks --once
python3 -m theteam.cli --project-root . watch history --once
python3 -m theteam.cli --project-root . status --json               # UNCHANGED
python3 -m theteam.cli --project-root . tasks --json                # UNCHANGED
python3 -m theteam.cli --project-root . run --json                  # {ran:0}, twice identical
```

Falsification:

1. `watch status --once` in a project with **no** audit chain and **no** run tasks shows
   `absent` / `never run` / `-`. Paste the frame.
2. The same view in a project with a tripped breaker shows the trip. Paste it.
3. `status --json` output is byte-identical before and after M6. Prove it.
4. `build_visibility` is pure: same input, same output, twice. And it opens no file.

---

### Constraints

- **M6 only.** No reflex, no web dashboard, no `advisory/` changes. The terminal renderer
  is the deliverable and nothing else.
- **No new `*.md` files.** Correct `ARCHITECTURE.md` §5.2 (it says no TUI is wired; that
  becomes false) and add an M6 entry to Part 6. Those are edits to an existing file.
- **No changes to `run_discussion`, `default_api`, or the advisory layer.** The M5 C1
  guard still holds and still applies:

  ```bash
  git diff 82d7acf..HEAD -- theteam/__init__.py | grep -E "^[-+].*default_api"   # empty
  ```

- **No second renderer.** One surface. If you find yourself writing a second adapter, that
  is R1 failing.
- **Do not reformat or "improve" the existing command output.** §2 is a contract with
  agentic consumers.
- Run the suite after every sub-task.

---

### Delegation

- **`todo`**, phases: `Boundary` (C1 + R1) → `Renderer` (C2 + R2) → `Honesty` (R3) →
  `Surface` (C3) → `Docs` → `Verify`. Mark done only with output. Never yield
  `in_progress`.
- R1 must land **before** R2. The boundary is cheap to write and expensive to retrofit.
- R2's three views are genuinely independent — dispatch them as one `task` batch, each
  owning one view, after R1 is committed. State in the batch context: `build_visibility`
  is the only data source, the three `--json` shapes from C2, `design_tokens.py` for
  visuals, and that no agent runs the full suite.
- **No agent runs the full suite.** One run from Main.
- `hub` to drain findings. The three views share one renderer file — name one integration
  owner and serialize the shared file rather than fanning out three edits to it. Fan out
  the *tests* if that is the cleaner split.
- Verify every subagent claim by running the command.

---

### Deliverable

One commit per phase. M6 closes Part 6; do not start an M7.

Summary 3 lines max (`AGENTS.md`), then report:

1. The C1 decision — list or string — and the live consumer evidence, or the absence of it.
2. Frames from all three views in a project with **no** audit chain and no runs. Paste them.
3. Proof that `status --json` is byte-identical before and after.
4. Whether `rich` was added, and if not, what you used instead and why.
5. The `build_visibility` purity test result.
6. Any contradiction with `ARCHITECTURE.md` — report it, do not accommodate it.

If C1 turns out to have a live reflex consumer I have not found, stop and report it. That
would mean reflex is wired somewhere I did not look, and it changes the decision.
