# Project Structure Maintenance - Subskill Integration

**Parent Skill**: theteam
**Subskill Name**: project-structure-maintenance
**Status**: Active Integration

---

## Integration Overview

The project-structure-maintenance subskill provides a structured workflow for maintaining the Ledras Lament project structure when structural issues are observed. It follows evidence-first principles and integrates seamlessly with the theteam workflow.

## Integration Points

### 1. Team Member Proposal Mechanism

Team members can propose structural maintenance by including this JSON in their notes:

```json
{
  "propose_subskill": "project-structure-maintenance",
  "trigger": "observed structural issue description",
  "evidence": "specific files, paths, or behaviors observed",
  "severity": "low|medium|high",
  "affected_infrastructure": ["list of scripts, configs, agents, tests that could break"],
  "minimum_viable_change": "suggested minimal fix",
  "risk_level": "Low|Medium|High"
}
```

### 2. Orchestrator Evaluation Flow

1. **Member Observation**: Team member observes structural issue during review
2. **Proposal Submission**: Member includes `propose_subskill` field in their note
3. **Orchestrator Evaluation**: You (orchestrator) evaluates proposal using checklist:
   - Is this a real observed problem or aesthetic preference?
   - Does evidence support the claim?
   - Is severity justified?
   - Are affected infrastructure items accurate?
4. **User Approval Gate**: Present proposal to user with problem, evidence, proposed changes, risks
5. **Execution**: If approved, run 8-phase maintenance workflow

### 3. Maintenance Workflow Trigger

When a proposal is approved, the orchestrator runs:

```bash
python3 /Users/bparlan/devcode/ledraslament/project_structure_checker.py
```

This executes all 8 phases:
1. **Phase 1**: Source Code Analysis
2. **Phase 2**: Configuration Analysis
3. **Phase 3**: Asset & Generated Output Analysis
4. **Phase 4**: Test & Documentation Analysis
5. **Phase 5**: Dependency Analysis
6. **Phase 6**: Git Status Analysis
7. **Phase 7**: Path Dependency Analysis
8. **Phase 8**: Agent Infrastructure Analysis

### 4. Output and Reporting

The workflow generates:

1. **JSON Report**: `project_structure_analysis.json` in `.omp/theteam/reports/`
2. **Structural Maintenance Report**: Markdown report for human review
3. **Team Integration**: Reports include proposed changes, risks, and affected infrastructure

## Team Member Roles

### Architect (Lena 'Stone Craft' Romano)
**Focus**: Long-term coupling, blast radius, dependency graph integrity
**Evaluation Questions**:
- Will this move create future maintenance pain?
- What's the impact 6 months from now?
- Does this change affect any critical pipeline paths?

### Cultural Scenarist (Marcus 'Amphitheaters' Vassos)
**Focus**: Cultural context, aesthetic organization, narrative coherence
**Evaluation Questions**:
- Is this change culturally appropriate for the Mediterranean project?
- Does this affect the aesthetic progression of scenes?
- Is the structure clear for future cultural researchers?

### Production Orchestrator (Sofia 'Flow' Marinova)
**Focus**: Scope control, smallest fix, deployment impact
**Evaluation Questions**:
- Is this the minimal change needed?
- What's the deployment impact?
- Can this be done without breaking current functionality?

## Integration with theteam Config

The subskill respects all theteam configuration:

- **`proactive_plan_required`**: Team must post a `todo` plan before any file edits
- **`block_edits_without_plan`**: No filesystem changes without approved plan
- **`permitted_skills`**: Only uses `graph-curation-expert` and `brave-search` for research
- **`output.report_dir`**: Reports go to the same location as main theteam reports
- **`max_discussion_rounds`**: Limited to prevent scope creep

## Usage Examples

### Example 1: Generated Output Pollution

**Trigger**: "During review of scene generation pipeline, observed that stage/ directory contains both guideline assets (guideline_line_out.png) and generated depth templates (depth_template.jpg)"

**Evidence**:
```
src/fal_generate.py:47 references stage/guideline_line_out.png as control input
imagine-config.json:12 references stage/guideline_line_out.png as guideline_image
No .gitignore entry for stage/depth_template.jpg - unclear if generated or source
assets/generated/scene-05-v002.png exists but no manifest tracking versions
```

**Affected Infrastructure**:
- `src/fal_generate.py` (ensure_line_out function)
- `imagine-config.json` (guideline_image path)
- `graph-curation-expert` (for infrastructure research)

### Example 2: Path Fragility

**Trigger**: "Found executable script using relative paths that could break when working directory changes"

**Evidence**:
```
src/fal_generate.py:47 uses relative path to stage/
This script may break if invoked from different directory
```

**Affected Infrastructure**:
- `src/fal_generate.py`
- Any CI/CD pipeline that runs the script
- Documentation referencing this script

## Decision Rule

> **Evidence of improvement × confidence in safe migration must exceed the risk of disrupting existing infrastructure.**

When uncertain: **Preserve the working structure and report the issue instead of making speculative changes.**

## Next Steps for Integration

1. **Update theteam-skill integration** to handle subskill proposals
2. **Create todo plan template** for structural maintenance
3. **Set up automated testing** for the maintenance workflow
4. **Document approval process** for team members

## Files Created

- `skill://theteam/subskills/project-structure-maintenance/SKILL.md` - Subskill documentation
- `skill://theteam/subskills/project-structure-maintenance/IMPLEMENTATION.md` - Implementation details
- `skill://theteam/subskills/project-structure-maintenance/TEAM_MEMBER_PROPOSAL.md` - Team member proposal guide
- `/Users/bparlan/devcode/ledraslament/project_structure_checker.py` - Main maintenance checker script

---

**Note**: This subskill is advisory + execution (with approval). It requires explicit user approval before any filesystem changes and follows the stability-first maintenance principles.