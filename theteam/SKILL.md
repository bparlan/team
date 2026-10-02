---
name: theteam
version: 1.0.0
description: Orchestrates independent reviewer subagents into deterministic team discussions, consensus-building, and actionable engineering reports.
tools: bash, read, write, edit, glob, grep, hub, task, todo, ask
user-invocable: true
---

# theteam

`theteam` is not a single persona — it's an orchestrator that spawns
independent reviewer subagents (via the native `task` tool), makes them file
notes without seeing each other's work, and then does one honest synthesis
pass. It never lets a single voice pass itself off as "the team's" opinion.

This skill's judgment calls (does this note actually disagree with that one,
what's the real recommendation) stay with you, the orchestrating agent. The
mechanical parts — config schema validity, "did every enabled member actually
report in," report formatting — are enforced by the Python scripts in `bin/`,
not by prose self-checking. If a script exits non-zero, that is a hard stop:
report the exact stderr to the user, do not paraphrase it into a softer
"looks like something's off," and do not proceed around it.

Every invocation of this skill starts here:

## The `default_api` gate — why the CLI cannot spawn

`discuss` and every task whose phases are `runner: llm` (`root-organization`,
`doc-truth`, `native-feature-loop`) need a task provider bound into `theteam`
as `default_api` in order to spawn a member.

**No subprocess binds it.** `default_api` is the namespace Gemini-family
models use to spell a tool call in generated text (`default_api.read(path="x")`
inside a ```` ```tool_code ```` block). It is a wire format OMP parses — not a
Python object — and nothing binds it automatically. Both of these were run
**from a shell**, so they establish the subprocess case and nothing wider:

```bash
python3 -c "import theteam; print(hasattr(theteam,'default_api'))"   # -> False
theteam discuss "anything"   # -> ProviderUnavailable
```

The import check was repeated in an OMP eval kernel, the one place a live
session's Python runs, and `default_api` was absent there too — so "the
runtime does not inject it" is measured rather than inferred, in both places
it could plausibly have been injected.

So the bare CLI returns a **named refusal** (`no_task_provider`) rather than a
fabricated result, and that refusal must be reported as-is. Do not search for
a session flag that enables it — none exists. The refusal now names the
command that runs the task instead: `theteam run --only <id> --run-id <id>`.

For `runner: llm` **tasks** there is a supported path that needs no provider,
described in the next section. `theteam discuss` has no such path: it calls
`default_api` directly, so from a shell it refuses. Report that refusal; do
not retry it, and do not synthesize the notes a discussion would have
produced. The one case where retrying is right is a host that has bound a
correct provider in-process — see the contract below before concluding it
has.

**Where the provider could exist, and what was actually measured.**
`default_api` is a global in the importing interpreter, so a host that
binds one before calling `run_discussion` would satisfy the gate. A shell
(`!`/`bash`) is always a fresh subprocess and can never have it, in a live
session or a dead one.

**A binding is not enough — it has to answer the right contract.**
`run_discussion` reads `spawn_results["tasks"]` as a list of
`{"name", "handle"}` entries and calls `default_api.output(handle)`. Probed in
an OMP eval kernel, the session's own `tool.task` returns `{"text",
"details"}` with no `tasks` key, and `tool.output` is absent from that
kernel's bridge. So a naive binding over the session's task tool would clear
the gate and then fail on the shape — which is why `run_llm_phase` now checks
the envelope and refuses by name instead of raising.

**This has not been tested end to end.** No in-process binding of
`default_api` has been driven through a real `theteam discuss`, so do not
report that path as working. What is established: the gate is satisfiable in
principle, the session's stock task tool does not satisfy the contract, and
an adapter is what any working binding would need.

`tasks`, `run --dry-run`, `history`, `task show`, and `status` work anywhere.

## Running an `llm` task from inside a session

`runner: llm` tasks are **not** blocked — they are unspawned. The gate above is
about spawning, and spawning is the one thing Python cannot do from inside
`theteam run`: the CLI is a subprocess, so it has no channel to this session's
`task` tool. That is why the phases are `runner: llm` and why the bare CLI
answers `no_task_provider`.

The fix inverts the direction. Python stops spawning and starts **recording**:
it writes down what it asked for, pauses, and reads the answer back when one
appears. You do the spawning, because you are the only party that can.

### The loop

```bash
theteam run --only <task-id> --run-id <run-id>     # stages a request, pauses
```

It prints `skipped (awaiting_member)` and writes
`.omp/theteam/handoff/<run-id>/<phase>.request.json`. Read that file: it names
the phase, the member persona, the prompt file, the declared output, and
`prompt_sha256`.

Then, **per phase**:

1. **Spawn one member** with the native `task` tool. Pass the contents of
   `prompt_file` as the task. The persona is already prose inside that prompt
   ("You are the **architect** on a `root-organization` phase") — do **not**
   pass `member:` as an `agent:` type. Those are `theteam.config` persona ids,
   not OMP agent types, and OMP's `scout` is read-only, which would make a
   scan phase unable to write its report. Use `agent: "task"`; the persona is
   in the prompt.
2. **Write the member's answer** to
   `.omp/theteam/handoff/<run-id>/<phase>.result.md`.
3. **Write the hash sidecar** beside it, so the collector can prove the result
   answers the prompt that was pinned. The sidecar path is the result path
   with its `.md` replaced by `.meta.json`:

   ```bash
   python3 -c "import json,sys; json.dump({'prompt_sha256': sys.argv[1]}, open(sys.argv[2],'w'))" \
     "<prompt_sha256 from the request>" \
     ".omp/theteam/handoff/<run-id>/<phase>.result.meta.json"
   ```

4. **Re-run the same command with the same `--run-id`.** The collector accepts
   the pair, moves the result into the declared output, and the loop advances
   to the next phase. Repeat until the task reports a terminal outcome.

Each collected phase leaves a `<phase>.collected.json` marker beside its
request. That marker is what lets a later call with the same `--run-id` skip
the phase instead of re-entering it: `accept_result` *moves* the result to its
declared output, so a request with no result beside it is the normal shape of
a **finished** phase, not a phase still waiting. Without the marker the loop
walked back to phase 1 on every call and no multi-phase task could finish.
Do not delete a `.collected.json` file to "restart" a phase — a fresh
`--run-id` is how you start over, and it discards the phases already done.

Resume *is* re-entry — same `--run-id`, one phase at a time. There is no
resume protocol to follow.

### What the collector refuses, and why you must not route around it

| you stage | outcome |
|---|---|
| nothing | `awaiting_member` — nothing ran |
| a result with no request on record | refused: `no request on record` |
| a result whose hash does not match | refused: `answers prompt <a> but the request pinned <b>` |
| a result with no hash sidecar | refused: `carries no prompt hash` |
| an empty result | refused: `is empty` |

A stale file already sitting at the declared output path is **never**
consulted — acceptance reads the staged result, then moves it into place. That
is deliberate: `reports/root-organization-scan.md` from last week is
non-empty, and accepting it would turn a phase green with no member behind it.
Do not "help" by copying a file to the output path; the collector will not see
it, and if you edit the sidecar to match, you have forged provenance, which is
the exact defect §3.3 forbids.

Without `--run-id`, everything above is inert and `theteam run` behaves exactly
as it always has.

## Step 0 — Locate and check the project config

The project root is the current working directory of the session (not an
ancestor-directory walk — this is deliberately scoped to "the project you're
in," not AGENTS.md-style inheritance).

```bash
# Needs theteam/ on the path: the script imports `bin.utilities` as a
# top-level package. Running it without this fails with
# `ModuleNotFoundError: No module named 'bin'`.
PYTHONPATH=theteam python3 theteam/bin/theteam_config.py validate "$(pwd)/theteam.config" --json
```

- **File doesn't exist** → go to **Bootstrap** below.
- **Exit 2** (unreadable/bad YAML) or **exit 3** (schema invalid) → tell the
  user exactly what's wrong (the stderr text) and offer to re-bootstrap. Do
  **not** try to hand-patch an invalid config yourself — regenerate it
  through the bootstrap flow so it goes through `init`'s validation gate.
- **Exit 0** → config is good. Load the roster and go to **Discussion** below:
  ```bash
  PYTHONPATH=theteam python3 theteam/bin/theteam_config.py roster "$(pwd)/theteam.config" --json
  ```

## Bootstrap (no valid config found)

Run this once per project, the first time `theteam` is invoked in it.

1. **Pre-analysis search.** Before asking the user anything, spend one short
   pass understanding the project so your questions are informed, not
   generic:
   - Read the repo root (README, package.json/pyproject.toml, top-level
     dirs) to infer the stack and what the project does.
   - If any of the project's `permitted_skills` are available (e.g.
     `ponytail`, `code-search`, `evolve-skills`), you may invoke them here
     for a quick codebase orientation pass — but this is a fast scan, not a
     deep audit. (See **Permitted skills** below.)
2. **Ask, don't assume.** Use the `ask` tool for anything you couldn't infer
   confidently — typically: project name/description if unclear, which
   personas the user wants beyond a sensible default trio, and whether the
   default `permitted_skills` list should change for this project. Keep
   questions few and specific; you already did the pre-analysis pass so you
     shouldn't need more than 2-4 questions.
3. **Render the config.** Write your answers (merged with sensible defaults
   from the template — the default 3-persona roster in
   `theteam-template.config` is a fine starting point if the user has no
   opinion) into a JSON file and run:
   ```bash
   PYTHONPATH=theteam python3 theteam/bin/theteam_config.py init \
     theteam/theteam-template.config \
     /tmp/theteam-answers.json \
     "$(pwd)/theteam.config"
   ```
   This validates before writing — if it fails, fix your answers JSON and
   retry. Never write `theteam.config` by hand with a text editor; always
   go through `init` so an invalid config can't reach disk.
4. Confirm the generated roster back to the user in one short message, then
   proceed to **Discussion** if they already had a topic in mind.

## Discussion (config exists and is valid)

This is what runs every time the user calls the team for comment on a topic.

### Deterministic Conversation Start

When the skill is invoked, it must immediately begin a structured round‑robin session:

1. **Member Intros** – each **selected** team member (see step 7) posts a short
   block containing:
   - `name` (from `id`)
   - `responsibility` (their `role`)
   - `personal_insight` – a concise comment on the current situation/topic.
   These are gathered from the members' individual notes before any synthesis.
2. **Team Consolidation TL;DR** – after all intros, the orchestrator drafts a one‑sentence summary of the discussion so far.
3. **Gate** – the discussion proceeds to synthesis and report rendering. There is no user-choice
   prompt here; see the correction below.

This flow ensures a deterministic start and chat‑room‑like interaction for every invocation.

> **Corrected 2026-09-29, twice.** This step previously described a four-option selection prompt
> gated on the user choosing one. It was wrong in two separate ways, and the second is the
> important one.
>
> *First*: the four options were never in anyone's config. `selection_options` is not a required
> key, it is in neither the shipped template nor any bootstrapped project, and an agent following
> this file literally was showing the user a prompt the code never produced.
>
> *Second, and the reason the prompt is now gone rather than merely documented*: the code had a
> **different** prompt, and that one lied. `run_discussion` offered "Abort Discussion — Stop the
> current discussion loop", printed the answer, and then ran the discussion to completion
> regardless. A control that reports an effect it does not have is the same defect class as the
> `MockAPI` that M0 removed, and `ARCHITECTURE.md` §3.3 forbids it outright. The prompt, its
> three-option fallback, and the `option_selection_required` gate that drove them have all been
> deleted.
>
> If a user-choice gate is ever reintroduced, it must branch for **every** option it offers —
> including an abort that actually returns before any member is spawned — and only then does
> `selection_options` belong in the schema. A prompt whose answer is printed and discarded should
> not exist. `option_selection_required` is still accepted in configs so old ones keep validating;
> nothing reads it.

All subsequent steps (pre‑analysis, spawning, synthesis, report) follow from the intros.
4. **Guardrail — no edits without an approved plan.** If the discussion
   topic implies a file change, `behavior.block_edits_without_plan` (true by
   default) means: no `write`/`edit` calls happen until the todo plan above
   has been posted and — for anything non-trivial — the user has had a
   chance to react to it. This applies even if a member's note recommends a
   specific code change. A recommendation is not a plan.
5. **Pre-analysis research (if enabled).** If `behavior.pre_analysis_search`
   is true and the topic warrants it, run it via the permitted skills only
   (see below) before spawning members, so all members see the same
   grounding material instead of each doing their own ad hoc research.
6. **Context aggregation.** Before spawning anyone, ground the discussion in actual
   project state. Run the deterministic context aggregator and read the config:
   ```bash
   python3 theteam/workflow/context_aggregator.py "$(pwd)"
   ```
   The aggregator prints a live snapshot of the project goal, runtime config, and
   the production invariants declared in `AGENTS.md`. There is **no
   `.omp/theteam/tool-manifest.json`** in this tree — a pre-M0 document promised
   one. Do not read it and do not report its absence as a problem; if a discussion
   needs a tool contract, read the tool's own source. If the aggregator is
   missing or fails, say so and proceed — never invent config values from memory.

   **Context is sliced per member (M9 Phase 3).** Each selected member receives only the
   project sections its own expertise matches, not the whole snapshot — a section needs two
   matching terms to be delivered, and one incidental word is not evidence. If a discussion
   needs a section no member received, say so; the run reports it as
   `context section '<name>' reached no member`, and that is a gap to name, not to ignore.
7. **Select, then spawn.** Selection is deterministic and happens *before*
   any member is spawned — `theteam.advisory.selector.select_members` decides,
   and at most **4** members speak. It reads two signals: tokens in the topic
   matched against each member's declared `expertise`, and any source file the
   topic names (`.py` → DevOps, `.sql` → data, `.tsx` → Designer). If nothing
   fires, **the skeptic speaks alone** — a lone skeptic is the correct
   default; the alternative is a unanimous chorus that is one voice repeated.
   When the cap truncates, the count is printed: "5 selected, 4 speak, 1
   suppressed". Do not spawn members the selector did not choose, and do not
   substitute an LLM for it: the same topic must select identically every
   time, and a test asserts that.
8. **Spawn each selected member independently**, one `task` call per member
   (isolated — members must not see each other's output). Each member's
   system prompt should be built from its `role`, `expertise`, and `voice`
   fields, plus the topic, the project's `permitted_skills` under
   `## Tool Inventory`, and the project context from step 6. Each member's
   `outputSchema` should require exactly:
   `{id, role, verdict, note}` — matching what `theteam_report.py` expects.
   Write each member's returned JSON to its own file under a scratch notes
   directory, e.g. `/tmp/theteam-notes-<timestamp>/<id>.json`.
9. **You do the synthesis pass** — after all members have reported, read
   every note yourself and write `synthesis.json` with `summary`,
   `agreements`, `disagreements`, `open_questions`, `recommendation`. Be
   honest about disagreement; `"No consensus — see disagreements"` is a
   legitimate recommendation. Do not average away a real split.
10. **Render the report:**
   ```bash
   python3 bin/theteam_report.py build \
     --topic "<topic>" \
     --notes-dir /tmp/theteam-notes-<timestamp> \
     --synthesis /tmp/theteam-synthesis-<timestamp>.json \
     --out "$(pwd)/<output.report_dir from config>/<timestamp>-<slug>.md" \
     --project "<project.name from config>" \
     --expected-ids <comma-separated ids of every member you spawned>
   ```
   The `--expected-ids` check is not optional busywork — it's what catches a
   dropped/failed subagent before you present an incomplete report as
   complete. If it fails, fix the actual gap (missing note file, failed
   task) and rerun; don't drop the missing member from `--expected-ids` just
   to make the command pass.
11. **Present the report to the user**: link/quote the written file, and
   summarize the recommendation and any open questions in your own reply —
   don't just dump the raw markdown unremarked.

## Permitted skills

`theteam` may invoke, via `task` (isolated one-off work) or `hub` (messaging
an already-running one), **only** the skills listed in this project's
`permitted_skills` (default: `ponytail`, `evolve-skills`, `code-search`). If a
discussion genuinely needs another skill or external tool, stop and `ask`
the user rather than reaching for it — this list is a hard boundary, not a
suggestion.

**This boundary is stated to the members, not just enforced on them.** As of
M9 Phase 1 (2026-09-30) every member's system prompt carries the list under
`## Tool Inventory`. Before that, the code read
`.omp/theteam/tool-manifest.json` — a file that has never existed in this
tree — and defaulted to the literal string `N/A`, so every member was given a
tool contract that said nothing. Falsified by
`test_m9_selection_wiring.py::TestToolInventoryIsTheRealBoundary`.

`ask` is an orchestrator tool, not a member tool. Members are spawned in
parallel and the parent blocks on each one, so a member calling `ask`
suspends the parent once per member with no visible provenance. The
orchestrator asks, once, in the parent session.

## Growing the team (M9 Phase 2)

`theteam manager` decides who is *on the roster*; `theteam discuss` decides who *speaks*
from it. Run the manager when a topic needs a perspective the current team has no expertise
for; skip it when the roster already covers the question.

```bash
theteam manager --topic "<topic>"    # PROPOSES. Writes nothing.
theteam manager --topic "<topic>" --apply   # persists
theteam manager --status             # why every member is on the roster
theteam manager --reset              # back to the bootstrapped team
```

**`--topic` never writes on its own.** The manager also proposes members for *uncovered
project flags*, so a version that persisted on propose would edit the user's committed
`theteam.config` as a side effect of asking a question. Read the proposal, then `--apply`.

**An added member must name its evidence.** The manager either names a focus flag the
project fired or quotes the topic tokens no member covered. "You might want a database
person" is not a reason and is not what you should say either. If you cannot state the
reason, do not add the member.

**`--status` reports what it cannot justify.** A member with no recorded reason is listed
under `no recorded reason` rather than given a plausible story. Pass that list to the user;
do not tidy it away. The roster is capped by the team catalog (9 members), so it cannot grow
without bound — and if a topic needs a perspective the catalog has no member for, say so
instead of inventing one.

## Notes on stability

- All schema/format enforcement lives in `bin/theteam_config.py` and
  `bin/theteam_report.py` — deterministic Python, no LLM-judgment path to
  silently drift. If you find yourself wanting to bypass one of these
  scripts "just this once" because a project's config is slightly
  nonstandard, that's a signal to fix the config or the template, not to
  route around the check.
- Never fabricate a member's note, verdict, or the synthesis's agreement /
  disagreement lists to fill a gap. A missing or failed subagent is a loud
  failure (see step 7), not something to paper over with a plausible-sounding
  guess.
- `theteam.config` files are project-local and committed to the project's
  own repo (not this skill's directory). The template and the `bin/` scripts
  ship with the package; everything else lives in the project.

## Output format

Present the report and summarize the recommendation and any open questions in
your own reply. Do not dump raw markdown unremarked.