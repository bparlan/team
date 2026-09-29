# Team Member Proposal - Project Structure Maintenance

## Proposal Format

When a team member observes a structural issue that warrants maintenance, they should propose this subskill using the following JSON template in their note:

```json
{
  "propose_subskill": "project-structure-maintenance",
  "trigger": "observed structural issue description",
  "evidence": "specific files, paths, or behaviors observed",
  "severity": "low|medium|high",
  "affected_infrastructure": ["list of scripts, configs, agents, tests that could break"]
}
```

## Required Components

### 1. Trigger - Clear Problem Statement
**What specific structural issue was observed?**
- Be concrete and specific
- Reference the Ledras Lament project context
- Example: "During review of scene generation pipeline, observed that stage/ directory contains both structural guideline assets (guideline_line_out.png) and generated depth templates (depth_template.jpg)"

### 2. Evidence - Concrete Proof
**What specific files, paths, or behaviors were observed?**
- File paths with line numbers: `src/fal_generate.py:47`
- Specific file contents: `.gitignore lacks *.png rule`
- Directory structures: `assets/generated/scene-05-v002.png exists without manifest`
- References: `imagine-config.json:12 references stage/guideline_line_out.png`
- Actual observations, not assumptions

### 3. Severity - Impact Assessment
**How severe is this issue?**
- **high**: Risk of data loss, broken functionality, or security issues
- **medium**: May cause confusion, inefficiency, or future problems
- **low**: Minor organizational issue, no immediate impact

### 4. Affected Infrastructure - Dependencies at Risk
**What could break if this is not fixed?**
- Specific scripts: `src/fal_generate.py (ensure_line_out function)`
- Configuration files: `imagine-config.json (guideline_image path)`
- Other agents: `graph-curation-expert`, `brave-search`
- Tests: `test_fal.py`, `test_quality_validation.py`
- Documentation: README.md, AGENTS.md
- Agent infrastructure: `theteam.config`, `.omp/` structure

## Proposal Quality Checklist

### ✅ Good Proposals Include:
- Concrete file paths with evidence
- Clear impact assessment
- Specific affected infrastructure
- Minimum viable change suggestion
- Risk level assessment

### ❌ Bad Proposals (Do NOT submit):
- "Project structure looks messy" - No evidence
- "We should organize files" - No specific problem
- "Add src/ directory" - Hypothetical need, not observed issue
- "Maybe we should add .gitignore" - No evidence of missing rules

## Example Proposal (Good)

```json
{
  "propose_subskill": "project-structure-maintenance",
  "trigger": "During review of scene generation pipeline, observed that stage/ directory contains both structural guideline assets (guideline_line_out.png) and generated depth templates (depth_template.jpg)",
  "evidence": [
    "src/fal_generate.py:47 references stage/guideline_line_out.png as control input",
    "imagine-config.json:12 references stage/guideline_line_out.png as guideline_image",
    "No .gitignore entry for stage/depth_template.jpg - unclear if generated or source",
    "assets/generated/scene-05-v002.png exists but no manifest tracking versions"
  ],
  "severity": "medium",
  "affected_infrastructure": [
    "src/fal_generate.py (ensure_line_out function)",
    "imagine-config.json (guideline_image path)",
    "Any agent skills referencing stage/ or assets/generated/"
  ],
  "minimum_viable_change": "1. Add .gitignore for stage/depth_template.jpg if generated, or move to assets/reference/ if source; 2. Document stage/ as \"structural guideline inputs only\" in README; 3. Add version manifest for assets/generated/",
  "risk_level": "Low - only path references and documentation"
}
```

## Example Proposal (Bad)

```json
{
  "propose_subskill": "project-structure-maintenance",
  "trigger": "Project structure looks messy",
  "evidence": [],
  "severity": "medium",
  "affected_infrastructure": []
}
```

This proposal would be rejected for lack of evidence and concrete problem statement.

## Team Member Responsibilities

### Architect
- Evaluates: Long-term coupling, blast radius, dependency graph integrity
- Questions: Will this move create future maintenance pain? What's the impact 6 months from now?

### Cultural Scenarist
- Evaluates: How does this affect cultural context and aesthetic organization?
- Questions: Is this change culturally appropriate for the Mediterranean project context?

### Production Orchestrator
- Evaluates: Scope control, smallest fix that solves the problem
- Questions: Is this the minimal change needed? What's the deployment impact?

### Technical Visionary
- Evaluates: Advanced pipeline integration, pixel density optimization
- Questions: Does this integrate well with the AI scene generation pipeline?

## Escalation Path

1. **If proposal lacks evidence**: Rejected - note in synthesis that proposal considered but not acted on
2. **If proposal has evidence but high risk**: User approval required before proceeding
3. **If user approves**: Run the 8-phase maintenance workflow
4. **If maintenance runs**: Generates Structural Maintenance Report

## Success Metrics

A good proposal must:
- ✅ Reference specific files/paths with evidence
- ✅ Assess concrete impact and severity
- ✅ List affected infrastructure
- ✅ Suggest minimum viable change
- ✅ Assess risk level
- ✅ Be actionable with clear next steps

## Next Steps After Proposal

1. **Orchestration**: Evaluate proposal using checklist above
2. **User Approval**: Present to user with problem, evidence, proposed changes, risks
3. **Execution**: If approved, run 8-phase maintenance workflow
4. **Validation**: Verify changes work, run relevant tests
5. **Report**: Generate Structural Maintenance Report

---

*This template ensures all project structure maintenance proposals are evidence-based, actionable, and follow the stability-first principles of the maintenance guide.*