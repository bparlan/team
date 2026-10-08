#!/usr/bin/env python3
"""Self-Evolving theteam Apply Updates Script.

This script applies the improvements identified in the generate-updates phase
to the actual skill files.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


def main():
    """Apply self-evolving improvements to skill files."""
    # Read the updates JSON from the generate-updates phase
    updates_path = Path("/tmp/theteam-notes-updates.json")
    if not updates_path.exists():
        print("ERROR: No updates JSON found at /tmp/theteam-notes-updates.json", file=sys.stderr)
        sys.exit(2)

    with open(updates_path) as f:
        updates = json.load(f)

    evolveskill_path = Path("/Users/bparlan/.omp/agent/skills/evolve-skills/SKILL.md")
    theteamskill_path = Path("/Users/bparlan/.omp/agent/skills/theteam/SKILL.md")
    evolution_path = Path("/Users/bparlan/.omp/agent/skills/evolve-skills/EVOLUTION.md")

    errors = []

    # Apply version bump if needed
    version_bump = updates.get("version_bump", "none")
    if version_bump not in ("none", "none required"):
        try:
            old_version, new_version = version_bump.split("→")
            # Read and update evolve-skills SKILL.md
            content = evolveskill_path.read_text()
            # Update version in frontmatter
            new_content = re.sub(
                r'version:\s*[\d.]+',
                f"version: {new_version.strip()}",
                content
            )
            if new_content == content:
                errors.append(f"Could not find version field in {evolveskill_path}")
            else:
                evolveskill_path.write_text(new_content)
                # Append to EVOLUTION.md
                today = datetime.now().strftime("%Y-%m-%d")
                evolution_entry = f"""## [{today}] - M5SA1

### Skill: evolve-skills
- **Old Version**: {old_version.strip()}
- **New Version**: {new_version.strip()}
- **Rationale**: {updates.get("notes", "Self-evolving improvement applied")}
- **Changes**:
  - Self-evolving theteam skill improvement
- **References**: {updates.get("evidence_links", [])}

"""
                if evolution_path.exists():
                    existing = evolution_path.read_text()
                    # Add entry before the closing if present, or append
                    if existing.rstrip().endswith("### Skill:"):
                        new_existing = existing.rstrip() + evolution_entry
                    else:
                        new_existing = existing.rstrip() + "\n" + evolution_entry
                    evolution_path.write_text(new_existing)
                else:
                    evolution_path.write_text(evolution_entry)
        except Exception as e:
            errors.append(f"Failed to apply version bump: {e}")

    # Apply prompt improvements to theteam SKILL.md
    for imp in updates.get("improvements", []):
        category = imp.get("category", "")
        target = imp.get("target", "")
        proposed_fix = imp.get("proposed_fix", "")

        if category == "prompt" and target and proposed_fix:
            # Apply to theteam SKILL.md out of scope section
            thema_content = theteamskill_path.read_text()
            # Look for Out of Scope section and add guardrail
            if "## Out of Scope" in thema_content:
                # Add the guardrail after the section header
                guardrail_line = f"- **Never {proposed_fix.strip()}** — automated guardrail from self-evolution"
                lines = thema_content.split("\n")
                new_lines = []
                in_scope = False
                for i, line in enumerate(lines):
                    if line.strip() == "## Out of Scope":
                        in_scope = True
                        new_lines.append(line)
                    elif in_scope and line.strip().startswith("- **Never"):
                        # Don't duplicate
                        pass
                    elif in_scope and line.strip().startswith("- **"):
                        # Add before this guardrail
                        new_lines.append(guardrail_line)
                        new_lines.append(line)
                        in_scope = False
                    else:
                        new_lines.append(line)
                thema_content = "\n".join(new_lines)
                theteamskill_path.write_text(thema_content)

    if errors:
        print(f"ERRORS applying self-evolving updates: {'; '.join(errors)}", file=sys.stderr)
        sys.exit(2)

    print("Self-evolving updates applied successfully")
    sys.exit(0)


if __name__ == "__main__":
    main()