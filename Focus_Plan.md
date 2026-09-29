# theteam v1 — Discussion Focus Plan

**Version 1.0** · Scope: discussion-only team orchestration · No factory features

## 0. What this is and isn't

`theteam` is a discussion orchestrator. It spawns independent reviewer subagents, makes them file notes blind to each other, and synthesizes one honest pass. It is **not** a software factory — no task queue, no sandboxing, no persistent state, no autonomous loop. Those were explicitly excluded.

This plan hardens the discussion core with four behavior changes, all at prompt/config level. Nothing here needs new infrastructure.

## 1. Grounding — what the research says

Four sources shaped this, and they constrain the design more than they inspire it.

**DocuTeam (KAIST, Sep 2026, N=20)** — the closest match. Anchored discussions to document regions; agents proactively initiated threads. Measured results: **46% fewer steering messages**, **39% more document modifications**, outcomes rated more novel/relevant/specific, cognitive load unchanged. Four design implications:

| DI | Implication |
|---|---|
| DI1 | Task-oriented discussion modes (Idea / Discussion / Evaluation) |
| DI2 | Surface focus, flow, disagreements without continuous monitoring |
| DI3 | Direct *and* indirect steering |
| DI4 | Selective incorporation of ideas back into the work |

**MindStudio** — four patterns: orchestrator-worker, split-and-merge, planner-generator-evaluator, **consensus-and-debate**. The last is most relevant: independent errors are unlikely to all point the same wrong direction.

**Routing paper (arXiv 2501.07813)** — *"guiding each query to a precise subset of agents ensures that only the most relevant agents respond, avoiding computational inefficiencies and unrelated information."*

**⚠️ arXiv 2602.01011 — "Multi-Agent Teams Hold Experts Back"** — the critical warning. When a team seeks consensus, it can *suppress* the expert. Under low agreeableness, open-ended research and bargaining **degraded sharply** (Cohen's d up to −12.39 for GPT-4o), while coding stayed near baseline because code has formal constraints that buffer communication degradation. **Design rule: never make every decision by vote.**

**Behaviour-driven role generation (arXiv 2606.27443)** — the paper that answers your "behaviour based role" question directly. Three findings that change the design:

1. **Personality effects are task-structure-dependent, not model-dependent.** Same trait, same model, different domain → different outcome. The mechanism is *artifact-mediated buffering*: structured output media (code, typed JSON) constrain convergence independently of communication quality; unstructured output exposes outcomes directly.
2. **The single-challenger result is the most actionable.** One low-agreeableness "challenger" in an otherwise-baseline team can *match or slightly exceed* baseline — but **only in lead position (position 0)**. Non-lead challengers hurt. Concrete recommendation: *"low agreeableness in a heterogeneous team is best deployed as a bounded, lead-position critic role rather than as a team-wide trait."*
3. **Negatively loaded adjectives inflate effects.** "Very unkind, very uncooperative, very selfish…" triggers safety-adjacent responses beyond the intended trait. Use neutral bipolar markers, not moral adjectives.

**Competitors evaluated** (from the TrueFoundry 2026 survey): Google ADK (hierarchical tree, A2A protocol), Microsoft AutoGen (conversational, human-in-loop), CrewAI (role-based, sequential/hierarchical), Claude Agent SDK + Temporal (durable workflows, parallel tool execution), Kimi K2.6 swarm (300 agents, 1,500 parallel tool calls). All confirm the same pattern: **role + tools + memory + communication channel** per agent, with the orchestrator owning routing and state.

## 2. Four behaviour changes

### Change 1 — Topic→member routing (answers "not all 5 for every conversation")

Each member gets a `trigger` field. The orchestrator scores the topic against triggers and only spawns members above threshold.

```yaml
team:
  - id: skeptic
    role: "Skeptic"
    trigger: "tests, correctness, gaps, edge cases, validation"
  - id: pragmatist
    role: "Delivery Pragmatist"
    trigger: "scope, cost, timeline, smallest fix, shipping"
  - id: architect
    role: "Systems Architect"
    trigger: "architecture, coupling, migration, long-term"
```

Topic *"is the test suite catching edge cases?"* → skeptic + pragmatist. *"Should we split this into a package?"* → architect + skeptic.

**Implementation:** zero code. The schema already accepts arbitrary member fields (`id/role/expertise/voice/enabled` are required, extras are ignored). Routing logic lives in the orchestrator prompt.

**Caveat:** routing is not free. Aggressive routing loses the cross-perspective challenge that makes the team valuable. DocuTeam's answer is *modes* — combine routing with modes, not instead of them.

### Change 2 — Discussion modes (DI1)

One mode today. Three recurring ones:

| Mode | When | Output shape |
|---|---|---|
| **Idea** | Brainstorming, alternatives | A menu of candidate approaches, no convergence |
| **Discussion** | Trade-offs, competing values | Arguments for/against, tension preserved |
| **Evaluation** | Critique of something existing | Defects, criteria ratings, verdict |

Synthesis contract gains a `mode` field; the report template branches on it. Idea mode produces a menu; Evaluation mode produces a verdict.

### Change 3 — Behaviour-driven role composition (your "behaviour based role" requirement)

This is the one the research most directly supports, and it's more subtle than "give each member a personality."

**The finding:** personality composition matters, but *where* you place the challenging voice matters more than *that* you have one. A single bounded critic in lead position outperforms a uniformly adversarial team. A uniformly adversarial team destroys performance on open-ended tasks.

**The design — three layers, not one:**

**Layer A: Role as a behavioural contract.** Each member's `role` is not a label, it's a behavioural specification with four fields:

```yaml
- id: skeptic
  role: "Skeptic"
  stance: "challenges premises; hunts for gaps"     # what they DO
  constraint: "must cite specific evidence or stay silent"  # what constrains them
  trigger: "tests, correctness, edge cases, validation"
  mode_default: "Evaluation"
```

**Layer B: The critic role is bounded, not team-wide.** Per the paper: deploy low-agreeableness as a *lead-position bounded critic*, never as a team-wide trait. The skeptic's constraint field is the mechanism — "must cite specific evidence or stay silent" is the neutral bipolar form the paper recommends, avoiding the negatively-loaded-adjective failure mode.

**Layer C: Role composition adapts to task structure.** This is the paper's core insight and the most valuable design rule:

| Task structure | Composition | Why |
|---|---|---|
| Structured output (typed JSON, code, schema) | Full team safe | Formal constraints buffer communication degradation |
| Unstructured output (prose, ideas, negotiation) | Bounded critic + cooperators only | Unstructured output exposes outcomes directly to communication quality |

The orchestrator infers structure from the topic and the note contract. A topic demanding a typed JSON verdict → full team. A topic demanding "what are the options?" → bounded critic + cooperators.

**Why this is behaviour-driven, not label-driven:** the role generates behaviour from (stance × constraint × task structure), not from a static personality string. Change the task structure and the same role behaves differently — which is exactly what the paper found happens in practice.

### Change 4 — Note contract upgrade

`theteam_report.py:68` requires `{id, role, verdict, note}`. Extend with three optional fields, all backward-compatible:

```json
{
  "id": "skeptic",
  "role": "Skeptic",
  "verdict": "Approve with changes",
  "note": "...",
  "confidence": 0.8,
  "priority": "high",
  "not_applicable": false
}
```

- **`confidence` (0–1)** — weigh notes by confidence in synthesis. Three members at 0.9 on the same point is signal; one at 0.3 is a question.
- **`priority`** — surfaces blocking issues first.
- **`not_applicable`** — **this is the key one.** Distinguishes "didn't report because the topic wasn't relevant" from "didn't report because the task failed." Currently `--expected-ids` treats both as a loud error. A member whose trigger didn't match should file `not_applicable: true` and be listed separately in the report, not counted as a dropped subagent.

## 3. What changes in the pipeline

| Step | Before | After |
|---|---|---|
| 3. Pre-analysis | Always runs | Gated on `pre_analysis_search` |
| 4. Context aggregation | Always runs `context_aggregator.py` | Optional; project-local; skip if absent |
| 5. Spawn | All enabled members | Routed subset per Change 1 |
| 6. Synthesis | One shape | Branches on `mode` (Change 2) |
| 7. Report | `--expected-ids` = all | Expected = routed subset; NA members listed separately (Change 4) |

## 4. Explicitly out of scope

- Task queue, backlog, persistent state, sandboxing, autonomous loops — factory features, excluded by agreement
- Adaptive roster from project file analysis — the stashed island's failed attempt; `trigger`-based routing is a better answer
- Member memory across invocations — deferred; would need a store
- `max_discussion_rounds` / `keep_last` — decorative, no code reads them
- `.backup` files in `bin/` — inert, flagged earlier

## 5. Verification

Each change is independently testable without the others:

1. Routing: topic → expected member set, for 10 topics covering single-match, multi-match, no-match
2. Modes: synthesis JSON shape per mode, 3 fixtures
3. Role composition: structured vs unstructured topic → expected composition, 4 fixtures
4. Note contract: `not_applicable` members excluded from `--expected-ids` failure; `confidence` weighting visible in synthesis
5. Regression: existing 6 tests still pass; documented path (init → validate → roster → report) still green

## 6. Sequencing

Changes 1 and 4 first — they're independent, backward-compatible, and each answers a stated need. Then 2 and 3 together, since modes and role composition interact (a member's `mode_default` only matters once modes exist).

---

**One honest caveat on "behaviour based role":** the research shows personality composition is real but narrow. It matters most on unstructured tasks, and the placement of the challenging voice matters more than its presence. So Change 3 gives you behaviour-driven *selection and bounding* of roles — which is what the evidence supports — not behaviour-driven *creation* of roles from scratch. The roster is still authored by the user at bootstrap. That's a limitation of the current evidence, not a hedge.