# Project Structure Maintenance - Main Implementation

**Skill**: project-structure-maintenance (subskill of theteam)
**Purpose**: Stability-first structural maintenance for the Ledras Lament project

---

## Overview

This implementation provides the 8-phase workflow for maintaining project structure when structural issues are observed. It follows the evidence-first principles from the maintenance guide.

## Core Workflow

### Phase 1: Inspect
- Map current project structure with evidence
- Identify source code, scripts, tests, config, assets, data, outputs, temp files
- Check Git status, tracked/untracked files, .gitignore
- Analyze configuration references and path dependencies

### Phase 2: Diagnose
- Identify concrete structural problems with evidence
- Problems must be observed, not aesthetic preferences
- Establish what is wrong, evidence, improvement, affected dependencies

### Phase 3: Protect
- Find all references to paths that might change
- Check imports, shell commands, subprocess calls, configs, environment variables
- Verify no working dependencies on fragile relative paths

### Phase 4: Propose Minimum Change
- Create migration plan with clear before/after paths
- Minimum viable change that solves the problem
- Document affected infrastructure and risks

### Phase 5: Environment Safety
- Classify any dependency artifacts (vendored, virtual env, build artifacts)
- Don't blindly move environment files
- Understand role before deleting artifacts

### Phase 6: Execute Safely
- Incremental moves with preservation of all metadata
- Verify after each change
- Never break working infrastructure

### Phase 7: Validate
- Proportional validation based on change scope
- Run syntax/import checks, relevant tests
- Verify agent infrastructure still works

### Phase 8: Report
- Document all changes and decisions
- Report structural improvements, files moved, risks avoided
- List remaining issues for manual review

## Integration with theteam

### Invocation Flow

1. Team member observes structural issue during review work
2. Member includes `propose_subskill: "project-structure-maintenance"` in their note
3. Orchestrator evaluates proposal for validity
4. If approved, runs the 8-phase workflow

### Evidence Requirements

**Problem must be observed, not imagined:**
```
Example valid evidence:
- "src/fal_generate.py:47" references "stage/guideline_line_out.png"
- "assets/generated/scene-05-v002.png" exists without manifest
- "no .gitignore entry for stage/depth_template.jpg"
```

**Not valid:**
- "Structure looks messy" (aesthetic)
- "We might need src/ later" (hypothetical)
- "Files should be organized" (opinion)

## Implementation Details

### Key Functions

#### inspect_structure()
- Uses glob, read, grep, bash for comprehensive analysis
- Returns structured map of project components
- Includes Git status and configuration analysis

#### diagnose_problems()
- Analyzes inspection results for concrete issues
- Filters out aesthetic preferences
- Returns evidence-backed problem list

#### protect_references()
- Scans for all references to paths that might change
- Returns dependency graph for affected infrastructure

#### execute_plan()
- Runs incremental changes with safety checks
- Verifies each step before proceeding

### Data Structures

```python
ProjectStructure {
    source_files: List[str],
    generated_outputs: List[str],
    configs: List[str],
    scripts: List[str],
    tests: List[str],
    assets: List[str],
    temp_files: List[str],
    backups: List[str],
    dependencies: List[str],
    git_status: GitStatus,
    path_references: Dict[str, List[str]},
}
```

## Team Member Contributions

### Architect
- Focus: Long-term coupling, blast radius, dependency graph
- Evaluates: Will this move create future maintenance pain?

### Pragmatist
- Focus: Scope control, smallest fix
- Evaluates: Is this the minimal change needed?

### Skeptic
- Focus: Evidence verification
- Evaluates: Is the problem real? Will this fix actually help?

## Decision Rule

**Evidence of improvement × confidence in safe migration must exceed the risk of disrupting existing infrastructure.**

When uncertain: **Preserve the working structure and report the issue instead of making speculative changes.**

---

## Example Workflow

### Valid Proposal
```
Trigger: "During review of scene generation pipeline, observed that stage/ directory contains both guideline assets (guideline_line_out.png) and generated depth templates (depth_template.jpg)"

Evidence:
- src/fal_generate.py:47 references "stage/guideline_line_out.png" as control input
- imagine-config.json:12 references "stage/guideline_line_out.png" as guideline_image
- No .gitignore entry for "stage/depth_template.jpg"

Severity: Medium
Affected Infrastructure:
- src/fal_generate.py (ensure_line_out function)
- imagine-config.json (guideline_image path)

Proposed Minimum Change:
1. Determine if depth_template.jpg is generated or source
2. Add .gitignore entry if generated, or move to assets/reference/ if source
3. Update documentation to clarify stage/ purpose
```

### Invalid Proposal
```
Trigger: "The project structure looks messy and needs cleaning up"

Evidence: (none)
Severity: High

Result: Rejected - lacks specific evidence of problem
```

---

## Output Format

Generates a Structural Maintenance Report at:
```
.omp/theteam/reports/<timestamp>-structural-maintenance.md
```

Includes all 8 phases with evidence, decisions, and validation results.

## Configuration Integration

### theteam.config
- This subskill is invoked by orchestrator, not spawned as member
- Runs after discussion with member proposal
- Respects same todo plan gate as main discussion
- Uses same permitted skills as parent theteam

### Integration Points
- Member notes can include "propose_subskill" field
- Orchestrator evaluates before user approval
- Runs under `behavior.block_edits_without_plan` protection
- Outputs to same report directory as main theteam reports