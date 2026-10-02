# M9 Execution Prompt

Paste this into a fresh session in `/Users/bparlan/devcode/team`.

---

## Task

Implement milestone **M9 — "The team that staffs itself"** as specified in
`ARCHITECTURE.md` §M9 (lines 641-824). Read that section first; it is the
specification and this prompt is only orientation.

The goal in one line: `theteam discuss` currently spawns every enabled member for
every topic, and a deterministic selector that already decides which members are
relevant exists but is wired to nothing — wire it, add a manager that grows the
roster from the topic, and turn prompt-shaped work into registered tasks.

---

## Read these before changing anything

1. **`ARCHITECTURE.md` §M9** (lines 641-824) — the specification. Every phase,
   gate, decision, and rationale is there.
2. **`ARCHITECTURE.md` §4.5 "Active member selection, no LLM"** and **§4.6
   "Per-turn context budget"** — the contract M9 amends.
3. **`AGENTS.md`** — repo rules. No planning documents. No orphaned files. Tests
   run after every code change.
4. **`theteam/advisory/selector.py`** — the module you are wiring. Read its
   docstring; it explains why it is deterministic and that this matters.
5. **`theteam/advisory/commentary.py:186-258`** — the tick loop that proves the
   controller was written and never connected.

---

## Three findings that shape the work

These are measured, not assumed. Re-verify before building on them.

**1. `theteam/advisory/` is live, tested code with no production caller.**
`CommentaryController` is never instantiated outside tests.
`theteam comment on/off/status` writes `commentary.on` and `commentary_stop`
markers (`cli.py:558`, `cli.py:584`) that nothing reads. `unified_loop.py` never
ticks it. **You are wiring existing code, not building it.**

**2. Two live defects sit in the path you are about to edit.**
- `__init__.py:601-605` reads `.omp/theteam/tool-manifest.json`, which does not
  exist, and defaults to the literal string `"N/A"`. Every member prompt
  therefore contains `## Tool Inventory` / `N/A`. Members are never told which
  tools they may use.
- `__init__.py:93` does `yaml.dump(project_context)` into **every** member's
  prompt. For a large project the same tokens are paid N times.

**3. Selection must stay deterministic. Read `selector.py:201-207` before you
design anything.** It records a previous attempt that collapsed:
> A gate that cannot fail is not a gate.

The manager may be an LLM. **The selector may not.** Do not add a topic-scoring
heuristic to `select_members` — build a minimal `SessionSlice` from the topic and
call it unchanged, so its tests keep passing.

---

## Locked decisions — do not relitigate

| Decision | Value |
|---|---|
| `web_search` | Joins `permitted_skills` for members **and** manager |
| `ask` | **Manager only.** Members never call it — see below |
| `theteam manager` | New command, separate from `theteam discuss` |
| Roster growth | **Topic-driven**, with two triggers — see below |
| "3 then +4" | An example, not a rule. Do not encode a count |
| `autonomedia-snapshot` | **Out of scope.** User tests bootstrap directly |
| Selection | Deterministic, capped at 4, lone skeptic default |

**Why members never call `ask`:** `run_discussion` spawns members in parallel
(`__init__.py:702`) and blocks on `output(handle)` per member
(`__init__.py:715`). A member calling `ask` suspends the parent once per member,
serially. Seven members means seven interruptions, each with no attribution — an
isolated subagent asking a question appears to come from nowhere. The manager
asks once per decision, in the parent session, where the question has visible
provenance.

**Why roster growth needs two triggers:** `analyze_project_context` derives
members from **project** flags (`security_focus`, `database_focus`, …) computed
from the repository. A topic about rate limiting adds nobody. The requirement is
topic-driven, so add a member when **either** the project has an uncovered flag
**or** the topic has vocabulary no member's `expertise` covers.

---

## Execution order

Phases are ordered by dependency and value. **Do not start a phase until the
previous one's gate passes.** Full detail for each is in §M9.

```
Phase 1  Wire the selector              smallest, highest value, do first
Phase 2  theteam manager                HITL, roster growth
Phase 3  Context efficiency             per-member slices
Phase 4  Tasks + runner: llm            the three prompts
Phase 5  Diagrams                       last, final state only, via archify
Phase 6  Documentation                  written WITH each phase, not batched
```

Phase 6 is listed last but runs *with* every phase.

---

## Per-phase gate — run every time

```bash
python3 -m pytest theteam/tests/ -q          # 772 passed at time of writing
bash scripts/check_invariants.sh             # 7/7 at time of writing
```

Both numbers will move. Run the commands. Report the actual output. Never claim
a phase is done on the basis that the code looks right.

---

## Pre-flight harness — do this before your first edit

`run_discussion` is protected by **`ARCHITECTURE.md` §7.2 invariant 7**
(byte-identical since M5). Editing it is a deliberate invariant break.

```bash
cp theteam/__init__.py /tmp/pre_change_init.py
md5sum /tmp/pre_change_init.py
grep -c "option_selection\|theteam_config" /tmp/pre_change_init.py   # must be > 0
```

After every edit to that file, assert:

- the snapshot **still contains** what it did before
- `python3 -c "import theteam"` succeeds

Asserting the baseline is what catches a silently-failed copy. This discipline
caught a real harness failure during M8.

**When you break invariant 7, update it in the same commit with the reason**, or
the gate fails and the break is invisible.

---

## The commands M9 must make work

These are the user-visible outcome. If they do not work, the phase is not done.

```
theteam run --only doc-truth
theteam run --only native-feature-loop --topic "..."
theteam run --only root-organization
```

Plus the new surface:

```
theteam manager --topic "<topic>"     # propose roster, ask once, persist
theteam manager --status              # why every member is on the roster
theteam manager --reset
theteam discuss "<topic>" --json      # selects members; ≤ 4 speak
```

---

## Reporting rules

This project's AGENTS.md requires it and it is the reason M7/M8 exist:

- **Never claim a phase is complete without running its gate.** Paste the output.
- **Never fabricate a member's opinion** to fill a gap — the M0 defect.
- **Re-read every file you edit.** An edit that duplicates a line will pass the
  test suite, because the suite does not read markdown. This happened twice in
  M8.
- **Every claim names the check that would falsify it.** "Added web_search" is
  not a changelog entry; "`grep -rn web_search theteam/` returns the
  `permitted_skills` default and the SKILL.md note" is.
- **If a gate fails, fix the cause.** Do not relax the gate to make it pass.

---

## First action

Read `ARCHITECTURE.md` lines 641-824 and
`theteam/advisory/selector.py` in full. Then report, in three lines: what Phase 1
will change, which files you will touch, and what its gate is. Do not write code
in the first response.