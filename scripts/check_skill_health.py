#!/usr/bin/env python3
"""Check that agent skills are healthy."""
from pathlib import Path
import json
import re
import sys

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = Path.home() / ".omp" / "agent" / "skills"
PROJECT_SKILLS = ROOT / "theteam" / "skill"
REPORTS_DIR = ROOT / ".omp" / "theteam" / "reports"


def find_skill_dirs():
    dirs = []
    if SKILLS_DIR.is_dir():
        for d in sorted(SKILLS_DIR.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                dirs.append(d)
    if PROJECT_SKILLS.is_dir():
        for d in sorted(PROJECT_SKILLS.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                dirs.append(d)
    return dirs


def check_skill(skill_dir):
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return {"id": skill_dir.name, "verdict": "missing", "missing_files": []}

    text = skill_md.read_text(encoding="utf-8")
    missing = []

    for match in re.finditer(r"`([^`]+\.py[^`]*)`", text):
        script_ref = match.group(1)
        for base in (skill_dir, ROOT):
            script_path = base / script_ref
            if script_path.exists():
                break
        else:
            missing.append({"ref": script_ref, "resolved": False})

    for match in re.finditer(r"skill://([^`\s]+)", text):
        skill_ref = match.group(1)
        skill_path = SKILLS_DIR / skill_ref / "SKILL.md"
        if not skill_path.exists():
            missing.append({"ref": f"skill://{skill_ref}", "resolved": False})

    verdict = "pass" if not missing else "findings"
    return {"id": skill_dir.name, "verdict": verdict, "missing_files": missing}


def main():
    skill_dirs = find_skill_dirs()
    if not skill_dirs:
        print("cannot-evaluate: no skill directories found", file=sys.stderr)
        sys.exit(2)

    results = []
    for skill_dir in skill_dirs:
        results.append(check_skill(skill_dir))

    total_findings = sum(1 for r in results if r["verdict"] != "pass")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = {"total_skills": len(skill_dirs), "total_findings": total_findings, "results": results}
    (REPORTS_DIR / "skill-health.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print(f"skill-health: {total_findings} findings")
    for r in results:
        if r["verdict"] != "pass":
            print(f"  {r['id']}: {r['verdict']}")
            for m in r["missing_files"]:
                print(f"    missing: {m['ref']}")

    if total_findings > 0:
        sys.exit(3)
    sys.exit(0)


if __name__ == "__main__":
    main()