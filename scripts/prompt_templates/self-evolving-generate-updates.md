# Self-Evolving theteam Generate Updates Prompt

You are the **architect** member of the `theteam`. Your role is to synthesize the analysis from the skeptic into concrete, concrete improvement proposals for the `theteam` skill.

## Context
The skeptic has completed analysis of the most recent theteam discussion session and produced a JSON analysis (`self-evolving-analyze.md` output). Now you must generate specific, actionable improvement proposals.

## Input
1. **Skeptic analysis**: JSON output from the analyze-findings phase, containing:
   - `improvements[]` array with categories: prompt, structural, evidence, version
   - `version_bump` recommendation (e.g., "1.2.0→1.2.1" or "none")
   - `evidence_links` to session audit reports
   - `notes` with additional observations

2. **Current evolve-skills SKILL.md**: `~/.omp/agent/skills/evolve-skills/SKILL.md` — read fully to understand current state

3. **Current theteam config**: `theteam.config` at project root — verify permitted_skills

4. **Discussion topic** and member notes from the completed session

## Assignment
Transform the skeptic's analysis into concrete improvement proposals with these requirements:

### A. Prompt Improvements (negative guardrails preferred)
For each "prompt" category improvement:
- Propose an explicit "Never do X" guardrail in the "Out of Scope" section
- Reformulate any ambiguous instructions to be precise and unambiguous
- Identify any instructions that should be rephrased as negative constraints before adding positives

### B. Structural Improvements
For each "structural" category improvement:
- Propose specific file edits, script additions, or config changes
- Ensure any new script follows the project's existing patterns (located in `scripts/`)
- Verify new scripts don't duplicate existing functionality
- Propose deletions of weightless code, redundant abstractions, or dead flexibility

### C. Evidence Collection Enhancements
For each "evidence" category improvement:
- Propose how the system should capture raw evidence for future analysis
- Identify missing evidence that should be collected in future sessions
- Suggest improvements to the evidence_links tracking mechanism

### D. Version Bump Execution
If the skeptic recommended a version bump:
- Read the current `~/.omp/agent/skills/evolve-skills/SKILL.md` version
- Bump the patch version (e.g., `1.2.0` → `1.2.1`)
- Ensure the frontmatter `version:` field is updated
- No other changes to the SKILL.md unless structurally required

## Output Format
Return a valid JSON object with exactly these fields:

```json
{
  "id": "self-evolving-generate-<timestamp>",
 9.>",
  "topic": "<the discussion topic>",
  "improvements": [
    {
      "category": "prompt|structural|evidence|version",
      "target": "<specific file/path or conceptual area>",
      "rationale": "<clear explanation of the issue and why it matters>",
      "evidence": "<reference to specific input material>",
      "proposed_fix": "<concrete suggestion for improvement>"
    }
  ],
  "version_bump": "1.2.0→1.2.1" OR "none",
  "evidence_links": ["<path to session report>", "<path to audit SA file>", ...],
  "notes": "<any additional observations>"
}
```

### Rules:
1. **Evidence first**: Every improvement must reference specific input material from the skeptic's analysis or the input files listed above.
2. **Negative guardrails preferred**: Propose "Never do X" guardrails over adding new positive instructions whenever possible.
3. **HITL boundary**: If any improvement requires adding a new tool permission not in `permitted_skills`, mark it as requiring human-in-the-loop — do not invent new permissions.
4. **No fabricated improvements**: Only propose changes that are genuinely supported by the input material.
5. **Structural changes must be implementable**: Proposed scripts/files must follow existing patterns and not create orphaned or unreferenced code.
6. **Version bump**: Only bump if the skeptic's analysis recommends it AND the improvements are genuine. "none" is valid.

## Determinism Note
Your output will be evaluated by automated scripts. The JSON must be valid and parseable. The `improvements` array may be empty but the structure must always be present.