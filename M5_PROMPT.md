# OMP Prompt — Milestone M5: The team comments

Fresh OMP session at `/Users/bparlan/devcode/team`. **Last milestone in
`ARCHITECTURE.md` Part 6.**

Advisor mode ON; read-only (`read`, `grep`, `glob`), cannot execute. You supply evidence.

---

## PROMPT START

M0–M4 done and committed. 668 tests, clean tree. Safety layer is wired and falsified.
Task store is YAML-only. The last milestone builds the **advisory layer** — the team that
reads your real session and speaks when there is something to say.

**This milestone is conditional.** `ARCHITECTURE.md` §M5 names three gates. All three must
pass or you **cut M5** and ship only `selector.py` + `roster.py` + the existing engine. Do
not build a controller whose gate failed.

### Three corrections to `ARCHITECTURE.md` — read these before you plan

**C1. `advisory/engine.py` does not exist.** §4.1 and the M5 guard both name it as
"byte-identical before and after". The real engine is `run_discussion` at
**`theteam/__init__.py:585`**, inside a 919-line module. That is what must not change
behaviour.

**Do not extract it into `advisory/engine.py` as part of M5.** That is a 900-line refactor
of a module holding the M0 provider guard, the config loader, and five `default_api` call
sites — in the one milestone whose premise is "do not fork the discussion path." Move it if
M6 exists; not here.

The M5 guard therefore becomes: **the diff of `theteam/__init__.py` touches no line inside
`run_discussion` (585–end) and changes no `default_api` call site.** Verify:

```bash
cd /Users/bparlan/devcode/team
git diff <base>..HEAD -- theteam/__init__.py | grep -E "^[-+].*default_api|^[-+].*def run_discussion"
# expect: no output
```

**C2. The session path in §4.3 needs a precision rule.** It says the reader "must select
the top-level `.jsonl` and refuse any file inside a subdirectory." Measured in this
environment:

```bash
find ~/.omp/agent/sessions/-devcode-team -maxdepth 1 -name "*.jsonl" | wc -l   # 59
find ~/.omp/agent/sessions/-devcode-team -mindepth 2 -name "*.jsonl" | wc -l   # 285
```

**285 subagent transcripts against 59 real sessions.** Selecting "the newest file" without
the depth rule comments on a subagent and presents it as the user's work. `SessionReader`
must take an explicit session path, default to the newest **maxdepth-1** `.jsonl` in the
slug directory, and refuse anything whose parent is a session directory. A
`__advisor.jsonl` is never a session.

**C3. `comment` takes no subcommand today.** `cli.py:398` has `"comment": "M5"` in
`MILESTONE_OF` and builds a bare parser. `theteam comment on` currently errors on
arguments. M5 adds `on|off|status` (§2). Build the real parser.

### Read

`ARCHITECTURE.md` Part 4 (§4.1–4.7) and M5 in Part 6. Then `theteam/__init__.py` around
`run_discussion` — read it, do not touch it. Then `analyze_project_context`
(`__init__.py:204`) for the signals `selector` reuses.

### Baseline

```bash
cd /Users/bparlan/devcode/team
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5
python3 -m theteam.cli --project-root . comment on 2>&1 | head -2
```

Expect 668. Different? Stop, report, do not edit.

---

### `advisory/session_reader.py`

Read the OMP session JSONL. Return §4.4's `SessionSlice` — `last_user_messages` (last 3,
400 chars), `recent_activity` (last 8 tool **names**), `touched_paths`, `digest`.

**Tool results are never returned.** A `read` result can be an entire file; §4.4 caps the
slice under 200 tokens. Names and the paths they were given are enough.

Honour the C2 depth rule. Also honour §4.2's failure table exactly: missing file →
`{spoke: false, reason: "no_session"}` plus the path looked for; malformed → raise, name
file and line; empty or subagent → `no_session`.

**Gate 1 — prove it against a real file, not a fixture.** A test that reads a checked-in
fixture proves nothing about the real format. Use the live session, assert the digest
changes when the file changes, and skip (do not fake-pass) when no session exists:

```bash
ls ~/.omp/agent/sessions/-devcode-team/*.jsonl | tail -1
```

**Fails → cut M5.** Per §M5, `session_reader` is the blocking unknown; if it cannot read a
real session, nothing downstream is honest.

### `advisory/selector.py`

Pick which roster members speak, capped at 4, **deterministically, zero LLM calls**
(§4.5). Reuse `analyze_project_context`'s evidence flags — they are already computed from
files, not guesses. Signals per §4.5: file extensions in `touched_paths`, latest user
message token-matched against each member's declared focus, task `type`, current phase.

If no signal fires, the **skeptic speaks alone**. A lone skeptic is correct; a unanimous
chorus is one voice repeated.

**Gate 2 — deterministic, and it actually differentiates.** Same slice in, same members
out, twice. A frontend slice and a database slice select **different** members. Assert
both. A selector that returns the same roster regardless of input fails.

**Fails → cut M5.**

### `advisory/commentary.py`

A controller whose tick body **calls the engine**. It does not reimplement selection,
prompting, validation, or synthesis (§4.1). Two discussion systems cannot drift because
there is one.

Per §4.2: max 2 rendered fragments per tick; more than 4 selected → truncate to 4 and
record `truncated: true`; more than 2 opinions → render 2, record `suppressed: N`. Stop
words (`stop` / `halt` / `quiet` / `enough` / `that's all`) match as the **entire leading
clause only** — "stop the current phase" must not silence the team. Stop sentinel:
`.omp/theteam/commentary.stop`.

Every tick reports `spoke: true` with ≤2 fragments, **or** `spoke: false` with a reason.
Silence is always explained — that is what distinguishes it from filler (§4.2).

**Gate 3 — a quiet tick costs zero calls.** Over 10 events: ≤2 rendered fragments, and a
tick with an unchanged digest makes **no** member calls. The budget is §4.6: ≤4 member
calls, ~2k tokens each, ~8k per turn; zero in a quiet session.

**Fails → cut M5.**

### `advisory/roster.py` + `theteam comment`

`roster.py` owns bootstrap and roster persistence. `comment on|off|status` per §2 — real
parser, C3. `off` writes the stop sentinel, effective next tick. `status` reports whether
commentary is on, last digest, last opinion, tick count. `--max-members N` (default 3,
cap 4).

`roster.py` and `selector.py` ship **even if a gate fails** — selection and bootstrap are
useful without the loop (§M5).

---

### Verify

```bash
cd /Users/bparlan/devcode/team
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5     # no regression
python3 -m theteam.cli --project-root . comment on --json
python3 -m theteam.cli --project-root . comment status --json
python3 -m theteam.cli --project-root . comment off --json
python3 -m theteam.cli --project-root . status --json | head -30   # session path + event count
python3 -m theteam.cli --project-root . run --json                 # {ran:0}, twice identical
git diff <base>..HEAD -- theteam/__init__.py | grep -E "^[-+].*default_api"   # empty
bash scripts/check_invariants.sh; echo "exit=$?"
```

Falsification: 10 ticks, ≤2 fragments each; `stop` in the user message →
`{spoke: false, reason: "stopped"}`; `status` shows session path and event count;
`discuss` outside OMP still raises `ProviderUnavailable` (M0's guard, §7.1.2 — M5 must not
weaken it).

---

### Constraints

- **M5 only.** No UI — the terminal renderer is deferred to M6 by team decision. No
  extraction of `run_discussion` (C1). No new `*.md` files.
- **Do not modify `run_discussion`.** Not to "improve" it, not to reuse it. It is the
  engine (§4.1). The diff check above is the guard.
- **No fabricated opinions.** If the engine is unavailable, `spoke: false` with a reason.
  Never a synthesised fragment. This is M0's rule and M5 is where it gets tested hardest.
- **No LLM call in `selector.py`.** Zero. Deterministic. §4.5.
- **Never return tool results from `SessionReader`.** §4.4.
- Run the suite after every sub-task.
- A gate that fails is a **stop**, not a fallback. Report which gate, what it returned,
  and what you shipped instead.

---

### Delegation

**Sequence the three gates — they are dependent, not parallel.** Gate 1 blocks 2, which
blocks 3. Fanning out three subagents to build all three in parallel means two of them are
built before the gate that can cancel them is known. That is wasted work on a conditional
milestone.

- **`todo`**, phases: `Gate1-SessionReader` → `Gate2-Selector` → `Gate3-Commentary` →
  `Surface` → `Verify`. Mark done only with output that proves the gate. Never yield
  `in_progress`.
- One `task` per gate, dispatched **as the previous gate passes**. A gate that fails ends
  the dispatch sequence — the remaining subagents are never spawned.
- `roster.py` and the `comment` parser have no gate dependency: fan those out in parallel
  with Gate 1.
- **No agent runs the full suite.** One run from Main. Per-file runs are fine.
- `hub` to drain findings; S2 and S3 both touch member selection — message them before
  either edits it.
- Verify every subagent claim by running the command. A gate that reports passing without
  output did not pass.

---

### Deliverable

One commit per gate. Do not start M6.

Summary 3 lines max (`AGENTS.md`), then report:

1. **Which gates passed, with the command output for each.** If any failed, say which, what
   it returned, and what you shipped instead.
2. Gate 1 run against a **real** session path — not a fixture. Paste the digest, and the
   evidence that it changes when the file changes.
3. Gate 2: the two slices and the different member sets each selected.
4. Gate 3: the 10-tick fragment count and the zero-call quiet tick.
5. The `run_discussion` diff check output (C1).
6. Any contradiction with `ARCHITECTURE.md` — report it, do not accommodate it.

If a gate cannot be evaluated because a real session file is unavailable, **stop and
report that**. Do not substitute a fixture and declare the gate passed. That is the exact
substitution that let the dead dashboard report four live tasks for three milestones.
