# M7 — The documentation tells the truth

## Goal

The code reached its final state at M6. The documentation did not follow. This milestone makes every
documented surface equal to the running code, verifies the plan that produced it against the diagrams
that render it, and rewrites the README as a complete command reference for humans and agents.

Two deliverables, one rule: **a document that names a path, a command, a flag, or an option is a claim
about the code. Verify it against the code. If it disagrees, the code is the defect** (`ARCHITECTURE.md:12`).

## Baseline

```
$ git log --oneline -3
$ python -m pytest -q          # 744 passed in 44.45s
$ bash scripts/check_invariants.sh   # invariant gate PASSED, 6/6
```

Measured at HEAD `14b7fb9`. If the count is not 744, the tree is not the tree this prompt describes.
Re-derive and write the real number into the README; do not copy 744 from here.

## R1 — The plan evaluates against the diagrams

Three artifacts, three claims. Audit them against each other and against the tree, then correct the
wrong one. `ARCHITECTURE.md:12` sets the conflict order: **this document defines intent, the diagrams
define rendered shape, the running code defines fact. If a document and the code disagree, the code is
the defect.**

| Artifact | Claim | Known state |
|---|---|---|
| `ARCHITECTURE.md` Part 6 | M0–M6, seven milestones | M6 added at line 518. Correct. |
| `diagrams/active-usage-milestones.json` | "Six milestones" | 6 nodes `m0`–`m5`, 5 edges. **M6 absent.** |
| `diagrams/active-usage-architecture.json` | architecture view | subtitle names `theteam/subskills/task_stack`, deleted in M2. |

**R1.1 — Add M6 to the milestones diagram.** Edit the JSON source, never the rendered HTML; the
`.html` is regenerated from the `.json` and the source is what is authoritative. Add node `m6`, add the
edge `m5 → m6`, add a lane if the existing six do not fit M6's theme, and update `meta.subtitle`
("Six milestones" → seven). Then regenerate both HTML files by whatever mechanism produced them.

**R1.2 — Fix the architecture diagram subtitle.** It grounds itself in a deleted directory. Re-ground it
in what the package actually contains now, or re-derive the components from `theteam/` — the
`components` array still lists `TaskStore` and `TaskManager`, which are not modules in the tree
(verified: `theteam/core/` has neither). A diagram whose components do not import is a second
`task_stack_adapter.py` in picture form.

**R1.3 — Report the plan evaluation.** Write a section in the README: what the plan ordered, what the
diagrams render, where they now disagree, and which one you changed and why. This is a deliverable, not
a process note. A reader must be able to audit the plan from the README alone.

**R1.4 — Do not invent a M7 in Part 6.** M7 is this documentation milestone. It is a documentation
milestone, not a product milestone. Do not add a Part 6 M7 section describing a renderer or a command
that does not exist. This prompt is not `ARCHITECTURE.md`.

## R2 — The command surface is complete and truthful

`theteam --help` lists eleven subcommands. `ARCHITECTURE.md` §2 documents ten. The gap is `loop`, which
is fully implemented (`cli.py:158` `cmd_loop` → `TaskRepository.schedule_task`) and has never been
documented anywhere. The renderer `watch` was added to §2 in M6 but its flag surface is not documented.

**R2.1 — Document every command, in both forms of §2.** §2 has a code block listing commands and a
table listing arguments and output. Both must be complete and must agree. Every row needs: command,
every flag with its type, default, and cap, and the output shape.

The full surface, from the parser:

| Command | Arguments and flags |
|---|---|
| `theteam bootstrap [path]` | `--interactive`, `--json` |
| `theteam status` | `--json` |
| `theteam discuss <topic>` | `--json` |
| `theteam serve` | `--port N` (default `$THETEAM_METRICS_PORT` or 8000), `--json` |
| `theteam loop <task_id>` | `--interval N` minutes (default 60), `--json` |
| `theteam tasks` | `--json` |
| `theteam run` | `--only <id>`, `--json` |
| `theteam history` | `--task <id>`, `--json` |
| `theteam task create` | `--path <file.yaml>` (required), `--json` |
| `theteam task edit <task_id>` | `--patch <file>` (required), `--json` |
| `theteam task delete <task_id>` | `--yes`, `--json` |
| `theteam task show <task_id>` | `--json` |
| `theteam comment on` | `--max-members N` (default 3, hard cap 4), `--json` |
| `theteam comment off` | `--json` |
| `theteam comment status` | `--json` |
| `theteam watch <status\|tasks\|history>` | `--once`, `--interval SECONDS` (default `DEFAULT_INTERVAL`), `--json` |
| global | `--project-root PATH` (default `$THETEAM_PROJECT_ROOT` or `$PWD`), `--json` |

**R2.2 — Verify the table above against the parser before writing it down.** It is transcribed from
`cli.py:600-745` at M6. If M6's `watch` lacks `--json` — and it does, unlike every other command —
then that is a defect to report, not a row to document. §2:87 promises "Every command supports
`--json`." Decide and say so in the report: fix the parser, or amend the contract. Do not silently
document the exception. Do not silently leave the gap.

**R2.3 — Document exit codes and failure shapes.** All commands return `0` on success, `1` on error.
`main()` catches `KeyError`/`ValueError` and bare `Exception`, emitting `{"ok": false, "error": ...}` in
JSON mode and `theteam <command>: <reason>` on stderr in text mode. `KeyboardInterrupt` returns 1.
Usage errors from argparse exit 2, except a bare `theteam comment`, which is deliberately `required=False`
so it reaches `cmd_comment` and exits 1 with its own usage message. This is intentional and must be
documented as such, or the next agent will "fix" it back to 2.

**R2.4 — Document the environment variables.** `THETEAM_PROJECT_ROOT`, `THETEAM_METRICS_PORT`. These
are real inputs the parser reads at build time. An agent that does not know about them cannot predict
the default.

**R2.5 — Document the honesty contract, because it changes how output must be read.** §3.3: no code
path returns a synthesized opinion, a default standing in for a real one, or a placeholder that reads
like a result. Concretely, for a reader parsing this output: `never run` is not `closed`; `absent` is
not `intact`; `-` is not `0`; a null renders as its own word, never as a passing-looking value. If you
see a value that looks like a healthy measurement, that is a bug — report it.

## R3 — The README is a complete reference

The root `README.md` is fiction. It documents `src/`, `tests/`, `config/`, PostgreSQL, `npm install -g
@oh-my-pi/archify`, `npm run test:archify`, and five `diagrams/*-candidate.json` files. None exist. It
claims five diagrams were "validated against the showcase quality profile" for artifacts that were
deleted. It instructs `python -m src.main`.

**R3.1 — Rewrite it.** It must serve two readers with different needs, and both must be served by the
same file:

- **A user** who wants to know what this is, install it, and run it. What it does, the four
  capabilities, install, quickstart, the commands, where state lives, exit codes.
- **An agent** that must call these commands and predict their output. Every command, every flag,
  every default, every exit code, every JSON shape, every environment variable, and the honesty
  contract that tells it what a returned value actually means.

Suggested shape, not mandated:

```
# theteam
  one-paragraph what-it-is
  Requirements, Install, Quickstart (bootstrap → status → watch)
  The four capabilities (§1.3 of ARCHITECTURE.md)
  Command reference        <- complete table, every flag, both readers
  Output honesty           <- §3.3, what nulls look like
  Exit codes and failure shapes
  Environment variables
  State directory
  Architecture and delivery order   <- links ARCHITECTURE.md
  Development: test, gate, CI
  Milestone history M0-M6
```

**R3.2 — Every command in the README must be executable as written.** Copy-paste a command from the
README into a shell and run it. If it fails, the README is defective. This is the falsification test
for R3 and it is not negotiable.

**R3.3 — Do not document `python -m theteam`.** It does not work: `__main__.py` was deleted in M1
(`ARCHITECTURE.md:314`), so it fails with `No module named theteam.__main__`. The working entry points
are the `theteam` console script (from `[project.scripts]`) and `python -m theteam.cli`. `ci.yml:43`
runs `python -m theteam --help || true` and the `|| true` hides the failure — that step is decorative
and the README must not inherit the error.

**R3.4 — Say what the project is not.** The old README's "Future Directions" promised multi-tenancy,
Kubernetes, Grafana, and ML-based scheduling. None are planned, none are in the tree, none are in
`ARCHITECTURE.md`. Delete the section. A reader must not carry a roadmap the project does not have.

## R4 — The other documents are brought current

`ARCHITECTURE.md` is the source of truth and is mostly correct. The rest are pre-M0 artifacts describing
a system that no longer exists.

| Document | State | Action |
|---|---|---|
| `ARCHITECTURE.md` | accurate, gaps noted below | fix the gaps, keep the structure |
| `README.md` | fiction | rewrite per R3 |
| `theteam/CLI.md` | pre-M0, documents `python3 theteam/__init__.py --bootstrap` | rewrite against the parser |
| `theteam/README.md` | pre-M0 skill description, no CLI surface | bring current, or fold into the root README and delete |
| `theteam/CHANGELOG.md` | 434 lines, ends 2026-09-20, predates M0 | add M0–M6 entries, or replace with a milestone table |
| `theteam/SKILL.md` | frontmatter current, body pre-M0 | verify each claim against the tree |
| `theteam/ONBOARDING.md` | references `bin/theteam_config.py` | verify the script exists; fix or remove |
| `theteam/ANALYSIS.md`, `FINAL_REPORT.md`, `IMPLEMENTATION_GUIDE.md`, `DISCUSSION_WORKFLOW_DESIGN.md`, `VALIDATION_DOCUMENTATION.md`, `Phase4_LOOP_MANAGER_VALIDATION.md` | pre-M0 reports | delete, or move to `archive/` |

**R4.1 — Do not create new documentation files.** `AGENTS.md:39-45` forbids planning documents and the
roadmap is the plan. The exception is this milestone: the user asked for documentation. Write into the
files that exist. Correct a wrong document; delete one that only describes deleted code.

**R4.2 — One README.** If `theteam/README.md` duplicates the root README's subject, the root README
is the one a human lands on and the one an agent reads first. Fold the content, delete the duplicate, and
leave a pointer. Two READMEs that disagree is the defect this milestone exists to close.

**R4.3 — Every surviving document must pass one test:** grep it for backticked paths and commands, then
check each one exists or runs. No exceptions for "this is a design doc." A design doc that names a
deleted module is a lie with a header.

## R5 — Documentation cannot break the code

**R5.1 — The suite stays green.** `744 passed` before and after. Documentation changes touch
`ARCHITECTURE.md`, `README.md`, and diagram JSON; none of that is imported. If a test reads a document,
it reads the *content*, and content changes legitimately, so an assertion that greps a document's prose
prose is a brittle test — if one exists, report it rather than contorting the prose to satisfy it.

**R5.2 — Regenerate the diagrams, do not hand-edit the HTML.** The `.html` and `.json` pair: the JSON
is the source, the HTML is the rendered view. Editing the HTML alone leaves the source lying. Confirm
which is authoritative by reading `diagrams/active-usage-architecture.html`'s generator comment or
`meta.schema_version` before editing.

**R5.3 — Report the plan evaluation as a deliverable.** The comparison in R1 is the reason this
milestone exists. It goes in the README (R1.3), where a reader can audit it, not only in a chat message.

## Verification

```
# baseline unchanged
python -m pytest -q                          # 744 passed
bash scripts/check_invariants.sh             # invariant gate PASSED, 6/6

# R1: plan vs diagrams
python3 -c "import json; d=json.load(open('diagrams/active-usage-milestones.json'));
print([n['id'] for n in d['nodes']])"        # must include m6
grep -c "subskills/task_stack" diagrams/active-usage-architecture.json   # must be 0
grep -rn "subskills/task_stack" ARCHITECTURE.md theteam/README.md README.md   # historical, ok

# R2: surface complete
theteam --help                               # 11 subcommands
grep -n "theteam loop" ARCHITECTURE.md       # must match
python3 -c "import argparse,sys; sys.path.insert(0,'.');
from theteam.cli import build_parser
p=build_parser()
print(sorted(p._subparsers._group_actions[0].choices))"   # must equal the 11

# R3: every documented command runs
for c in bootstrap status tasks run history watch; do
  theteam --project-root "$PWD" "$c" --json >/dev/null 2>&1; echo "$c -> $?";
done                                          # each must be 0 or an honest 1

# R4: no stale claims survive
grep -rn "python -m src.main\|archify\|PostgreSQL or other relational" README.md theteam/*.md   # 0
grep -rn "theteam_config.py" theteam/*.md   # 0 unless the script exists
grep -rn "python3 theteam/__init__.py --bootstrap" theteam/*.md   # 0
```

## Deliver the report

Six sections, no more:

1. **Plan evaluation** — Part 6 vs both diagrams vs the tree, every disagreement, which artifact you
   changed, and the justification.
2. **Command surface** — the 11 commands, what was missing (`loop`), the `watch --json` finding if it
   reproduced, and what you did about it.
3. **README** — what was fiction, what it says now, and the run-it-as-written verification evidence.
4. **Documents** — the disposition of each file in the R4 table, with the reason.
5. **Test and gate** — the before/after counts and the invariant gate output.
6. **What is still false** — anything you found and did not fix, with the reason. An empty section is
   the target; an empty section claimed without having looked is not.

## Anti-drift

- **The code is the fact.** Verify every claim against HEAD, not against this prompt. Where the two
  disagree, the code wins and the prompt is wrong.
- **No new features.** No new commands, no new flags, no refactors. This milestone changes documents
  and the diagram JSON. If the code needs a change to satisfy a documented promise (R2.2), that is the
  one exception, and it is a one-line parser fix, not a milestone.
- **No test changes to make things pass.** 744 green before and after.
- **No new planning documents.** This file is the milestone brief. It is not a deliverable. It is not
  tracked in Part 6.
- **Do not re-audit what is already verified.** The baseline, the M5 corrections, and the M6 results are
  settled. Start from HEAD `14b7fb9`.
