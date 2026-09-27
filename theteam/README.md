# theteam Skill Implementation

## Overview

`theteam` is an orchestrator that spawns independent reviewer subagents (via the native `task` tool), makes them file notes without seeing each other's work, and then does one honest synthesis pass. It never lets a single voice pass itself off as "the team's" opinion.

This skill's judgment calls (does this note actually disagree with that one, what's the real recommendation) stay with you, the orchestrating agent. The mechanical parts — config schema validity, "did every enabled member actually report in," report formatting — are enforced by the Python scripts in `bin/`, not by prose self-checking. If a script exits non-zero, that is a hard stop: report the exact stderr to the user, do not paraphrase it into a softer "looks like something's off," and do not proceed around it.

## Skill Triggers

This skill is invoked by any of the following user requests:
- "theteam"
- "ask the team"
- "get the team's opinion"
- "get the team's comment"
- "get the team's take on X"
- "call the team"
- "team's opinion"
- "team's comment"
- "team's take on"
- "consult the team"
- "discuss with team"
- "get team input"

## Core Workflow

### Step 0 — Locate and check the project config

The project root is the current working directory of the session (not an ancestor-directory walk — this is deliberately scoped to "the project you're in," not AGENTS.md-style inheritance).

```bash
python3 theteam/bin/theteam_config.py validate "$(pwd)/theteam.config" --json
```

- **File doesn't exist** → go to **Bootstrap** below.
- **Exit 2** (unreadable/bad YAML) or **exit 3** (schema invalid) → tell the user exactly what's wrong (the stderr text) and offer to re-bootstrap. Do not try to hand-patch an invalid config yourself — regenerate it through the bootstrap flow so it goes through `init`'s validation gate.
- **Exit 0** → config is good. Load the roster with `theteam_config.py roster "$(pwd)/theteam.config" --json` and go to **Discussion** below.

### Bootstrap (no valid config found)

Run this once per project, the first time `theteam` is invoked in it.

1. **Pre-analysis search.** Before asking the user anything, spend one short pass understanding the project so your questions are informed, not generic:
   - Read the repo root (README, package.json/pyproject.toml, top-level dirs) to infer the stack and what the project does.
   - If `graph-curation-expert` or `brave-search` are available and the project already has a knowledge graph or open research questions worth a quick check, you may invoke them here (see **Permitted skills** below) — but this is a fast scan, not a deep audit.
2. **Ask, don't assume.** Use the `ask` tool for anything you couldn't infer confidently — typically: project name/description if unclear, which personas the user wants beyond a sensible default trio, and whether the default `permitted_skills` list should change for this project. Keep questions few and specific; you already did the pre-analysis pass so you shouldn't need more than 2-4 questions.
3. **Render the config.** Write your answers (merged with sensible defaults from the template — the default 3-persona roster in `theteam-template.config` is a fine starting point if the user has no opinion) into a JSON file and run:
   ```bash
   python3 theteam/bin/theteam_config.py init \
     theteam/theteam-template.config \
     /tmp/theteam-answers.json \
     "$(pwd)/theteam.config"
   ```
   This validates before writing — if it fails, fix your answers JSON and retry. Never write `theteam.config` by hand with a text editor; always go through `init` so an invalid config can't reach disk.
4. Confirm the generated roster back to the user in one short message, then proceed to **Discussion** if they already had a topic in mind.

### Discussion (config exists and is valid)

This is what runs every time the user calls the team for comment on a topic.

#### Deterministic Conversation Start

When the skill is invoked, it must immediately begin a structured round‑robin session:

1. **Member Intros** – each enabled team member posts a short block containing:
   - `name` (from `id`)
   - `responsibility` (their `role`)
   - `personal_insight` – a concise comment on the current situation/topic.
   These are gathered from the members' individual notes before any synthesis.
2. **Team Consolidation TL;DR** – after all intros, the orchestrator drafts a one‑sentence summary of the discussion so far.
3. **User Selection Prompt** – present the four selectable options defined in `selection_options` (see `theteam.config`). The user must choose one before any further back‑and‑forth.

Only after the user selects an option does the skill proceed to the usual synthesis, report rendering, and final output phases.

This flow ensures a deterministic start and chat‑room‑like interaction for every invocation.

#### Guardrail — no edits without an approved plan

If the discussion topic implies a file change, `behavior.block_edits_without_plan` (true by default) means: no `write`/`edit` calls happen until the todo plan above has been posted and — for anything non‑trivial — the user has had a chance to react to it. This applies even if a member's note recommends a specific code change. A recommendation is not a plan.

#### Pre-analysis research (if enabled)

If `behavior.pre_analysis_search` is true and the topic warrants it, run it via the permitted skills only (see below) before spawning members, so all members see the same grounding material instead of each doing their own ad hoc research.

#### Spawn each enabled member independently

One `task` call per member (isolated — members must not see each other's output). Each member's system prompt should be built from its `role`, `expertise`, and `voice` fields, plus the topic and any shared research context from step 3. Each member's `outputSchema` should require exactly:
`{id, role, verdict, note}` — matching what `theteam_report.py` expects.
Write each member's returned JSON to its own file under a scratch notes directory, e.g. `/tmp/theteam-notes-<timestamp>/<id>.json`.

#### You do the synthesis pass

After all members have reported, read every note yourself and write `synthesis.json` with `summary`, `agreements`, `disagreements`, `open_questions`, `recommendation`. Be honest about disagreement; `"No consensus — see disagreements"` is a legitimate recommendation. Do not average away a real split.

#### Render the report

```bash
python3 theteam/bin/theteam_report.py build \
  --topic "<topic>" \
  --notes-dir /tmp/theteam-notes-<timestamp> \
  --synthesis /tmp/theteam-synthesis-<timestamp>.json \
  --out "$(pwd)/<output.report_dir from config>/<timestamp>-<slug>.md" \
  --project "<project.name from config>" \
  --expected-ids <comma-separated ids of every member you spawned>
```

The `--expected-ids` check is not optional busywork — it's what catches a dropped/failed subagent before you present an incomplete report as complete. If it fails, fix the actual gap (missing note file, failed task) and rerun; don't drop the missing member from `--expected-ids` just to make the command pass.

#### Present the report to the user

Link/quote the written file, and summarize the recommendation and any open questions in your own reply — don't just dump the raw markdown unremarked.

## Permitted skills

`theteam` may invoke, via `task` (isolated one-off work) or `hub` (messaging an already-running one), **only** the skills listed in this project's `permitted_skills` (default: `ponytail`, `evolve-skills`, `code-search`). If a discussion genuinely needs another skill or external tool, stop and `ask` the user rather than reaching for it — this list is a hard boundary, not a suggestion.

## Notes on stability

- All schema/format enforcement lives in `bin/theteam_config.py` and `bin/theteam_report.py` — deterministic Python, no LLM-judgment path to silently drift. If you find yourself wanting to bypass one of these scripts "just this once" because a project's config is slightly nonstandard, that's a signal to fix the config or the template, not to route around the check.
- Never fabricate a member's note, verdict, or the synthesis's agreement / disagreement lists to fill a gap. A missing or failed subagent is a loud failure (see step 6), not something to paper over with a plausible‑sounding guess.
- `theteam.config` files are project‑local and committed to the project's own repo (not this skill's directory) — the skill itself (`~/.omp/agent/skills/theteam/`) stays project‑agnostic; only `theteam-template.config` and the `bin/` scripts live here.

## New: Chatroom-Style Output

The skill has been enhanced with a new chatroom-style output format that displays member comments with names centered in the middle of the message flow, as requested. Each member's comment appears with their name and role highlighted in the center, creating a more engaging and collaborative discussion format.

### Chatroom Output Format

Each member's contribution follows this pattern:

```
[HH:MM] **ROLE** (member_id):

  👤 ROLE » member_id «
[HH:MM] VERDICT

  Note content...
```

### Integration

The chatroom format is integrated into the existing discussion workflow:
1. Member intros are formatted with centered names and roles
2. Personal insights are displayed with proper formatting
3. The orchestrator synthesis maintains the same structure
4. All outputs preserve the deterministic conversation flow

### Benefits

- Enhanced visibility of individual team members
- Clear separation of roles and perspectives

The chatroom style improves team interaction visibility while preserving all existing team capabilities and validation checks.