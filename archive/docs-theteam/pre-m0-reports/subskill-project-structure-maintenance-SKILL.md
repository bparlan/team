# Subskill: Project Structure Maintenance

**Parent Skill**: theteam
**Trigger**: Proactive — any team member may propose this when structural drift is observed
**Mode**: Advisory + Execution (with approval)

---

## Purpose

This subskill provides a structured workflow for theteam members to proactively identify, diagnose, and (with user approval) remediate project structural issues that threaten maintainability, reproducibility, or agent infrastructure stability.

It is NOT a general cleanup skill. It is a **stability-first maintenance task** that runs only when a team member observes a concrete structural problem during other work.

---

## When to Propose

Any enabled team member should propose invoking this subskill when they observe:

1. **Generated outputs polluting source directories** — e.g., `assets/generated/` files appearing in `src/`, test fixtures in production code
2. **Configuration scattering** — same config keys duplicated across multiple files with unclear authority
3. **Path fragility** — scripts using relative paths that break when working directory changes
4. **Agent infrastructure drift** — skill configs, OMP instructions, or `.omp/` structure becoming inconsistent
5. **Dependency pollution** — `node_modules`, `__pycache__`, `.venv`, or build artifacts committed or unignored
6. **Backup/version confusion** — `*.bak`, `*_old`, `v2/` directories mixed with active code
7. **Test/production mixing** — test files in `src/`, or production code in `tests/`
8. **Unclear directory ownership** — directories with no obvious purpose or conflicting purposes

**Do NOT propose** for:
- Aesthetic preferences ("it would look nicer if…")
- Hypothetical future needs ("we might want a `src/` later")
- Personal organizational style differences
- Any change without observed evidence of actual harm

---

## Workflow

### Step 1: Team Member Observation (Proposal)

When a member notices a structural issue during their review work, they include in their note:

```json
{
  "propose_subskill": "project-structure-maintenance",
  "trigger": "observed structural issue description",
  "evidence": "specific files, paths, or behaviors observed",
  "severity": "low|medium|high",
  "affected_infrastructure": ["list of scripts, configs, agents, tests that could break"]
}
```

### Step 2: Orchestrator Evaluation

The orchestrating agent (you) evaluates:
- Is this a real observed problem or aesthetic preference?
- Does the evidence support the claim?
- Is the severity justified?
- Are the affected infrastructure items accurate?

If yes → proceed to **Step 3**. If no → note in synthesis that proposal was considered but not acted on.

### Step 3: User Approval Gate

**MANDATORY**: Before any structural changes, present the proposal to the user with:

1. Problem statement with evidence
2. Proposed changes (minimum viable)
3. Affected infrastructure and migration plan
4. Risk assessment

Only proceed with user's explicit approval.

### Step 4: Execute Maintenance Phases

Follow the 8-phase process from the maintenance guide:

1. **Inspect** — Map current structure with evidence
2. **Diagnose** — Identify specific problems with evidence
3. **Protect** — Find all references to affected paths
4. **Propose Minimum Change** — Create migration plan
5. **Environment Safety** — Classify any dependency artifacts
6. **Execute Safely** — Incremental moves with verification
7. **Validate** — Run proportional checks
8. **Report** — Document changes, decisions, remaining issues

---

## Team Member Roles in This Subskill

| Role | Focus |
|------|-------|
| **Architect** | Long-term coupling, blast radius of moves, dependency graph integrity |
| **Pragmatist** | Scope control — smallest fix that solves the observed problem |
| **Skeptic** | Evidence verification — is the problem real? Will the fix actually help? |
| **Security** (if enabled) | Secret exposure risk, `.env` handling, credential leakage during moves |

---

## Output Format

When this subskill runs, it produces a **Structural Maintenance Report** at:
```
.omp/theteam/reports/<timestamp>-structural-maintenance.md
```

The report follows the Phase 8 format from the maintenance guide.

---

## Integration with theteam

- This subskill is **invoked by the orchestrator**, not spawned as a separate member
- It runs **after** a discussion where at least one member proposed it
- It uses the **same todo plan gate** as the main discussion (`behavior.proactive_plan_required`)
- It **respects `block_edits_without_plan`** — no filesystem changes without approved plan
- It **uses permitted skills only** (from theteam config) for any research needed

---

## Decision Rule (from maintenance guide)

> **Evidence of improvement × confidence in safe migration must exceed the risk of disrupting existing infrastructure.**

When uncertain: **Preserve the working structure and report the issue instead of making speculative changes.**

---

## Example Proposal (for team members to reference)

```markdown
### Structural Maintenance Proposal

**Trigger**: During review of scene generation pipeline, observed that `stage/` directory contains both structural guideline assets (`guideline_line_out.png`) and generated depth templates (`depth_template.jpg`), while `assets/generated/` contains versioned outputs but no clear separation from input assets.

**Evidence**:
- `src/fal_generate.py:47` references `stage/guideline_line_out.png` as control input
- `imagine-config.json:12` references `stage/guideline_line_out.png` as `guideline_image`
- No `.gitignore` entry for `stage/depth_template.jpg` — unclear if generated or source
- `assets/generated/scene-05-v002.png` exists but no manifest tracking versions

**Severity**: Medium — risk of committing generated assets, path confusion for new agents

**Affected Infrastructure**:
- `src/fal_generate.py` (ensure_line_out function)
- `imagine-config.json` (guideline_image path)
- Any agent skills referencing `stage/` or `assets/generated/`

**Proposed Minimum Change**:
1. Add `.gitignore` for `stage/depth_template.jpg` if generated, or move to `assets/reference/` if source
2. Document `stage/` as "structural guideline inputs only" in README
3. Add version manifest for `assets/generated/`

**Risk**: Low — only path references and documentation
```