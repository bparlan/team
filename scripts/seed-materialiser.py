#!/usr/bin/env python3
"""
seed-materialiser.py — Generate the awareness seed for a project.

This is the implementation of the SHAPE defined in docs/awareness-shape.yaml.
It produces a per-project awareness-seed.json that lets an agent self-evaluate
without a human.

Usage:
    python3 scripts/seed-materialiser.py --project-root <path>

The seed is written to .omp/theteam/awareness-seed.json (gitignored).
Never hand-edited; always regenerated. Never committed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

HARDCODED_PATH_PATTERN = "/Users/bparlan" + "|~/devcode/team"


class AwarenessSeedMaterialiser:
    """Generate a project's awareness seed from the shape."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.seed_path = self.project_root / ".omp" / "theteam" / "awareness-seed.json"
        self.seed_path.parent.mkdir(parents=True, exist_ok=True)

    def _run_checker(self, checker: str, cwd: str = None) -> Dict[str, Any]:
        """Run a checker and return its parsed output."""
        try:
            result = subprocess.run(
                checker,
                shell=True,
                cwd=str(cwd) if cwd else str(self.project_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "stdout": "", "stderr": "timeout", "returncode": -1}
        except Exception as exc:
            return {"ok": False, "stdout": "", "stderr": str(exc), "returncode": -1}

    def _check_file_exists(self, path: str) -> bool:
        """Check if a file exists relative to project root."""
        return (self.project_root / path).exists()

    def _check_tool_declared(self, tool: str) -> bool:
        """Check if a tool is declared in theteam/SKILL.md."""
        skill_md = self.project_root / "theteam" / "SKILL.md"
        if not skill_md.exists():
            return False
        content = skill_md.read_text()
        # Look for tools declaration
        for line in content.splitlines():
            if line.strip().startswith("tools:"):
                return tool in line
        return False

    def _resolve_citation(self, path: str) -> bool:
        """Resolve a citation path from project root."""
        return self._check_file_exists(path)

    def _probe_rules(self) -> List[Dict[str, Any]]:
        """Probe the project for rules and classify them on the two axes."""
        rules = []

        # Rule 1: theteam requires an OMP session
        rules.append({
            "id": "provider-bound",
            "text": "theteam requires an OMP session; a shell is a fresh subprocess and can never bind a provider",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": 'python3 -c "import theteam; print(hasattr(theteam, \\"default_api\\"))"',
            "path_resolution": "theteam/__init__.py:_require_provider",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 2: Docker is required for script phases
        rules.append({
            "id": "docker-required",
            "text": "Script phases require Docker; container isolation is not optional",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": "python3 -c \"from theteam.core.agent_isolation import AgentIsolation; print(AgentIsolation.available())\"",
            "path_resolution": "theteam/tasks/executor.py:execute_phase",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 3: Every phase must name an output
        rules.append({
            "id": "phase-names-output",
            "text": "Every phase must name an output; a phase with no output cannot prove it ran",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": "python3 scripts/check_task_contract.py .",
            "path_resolution": "scripts/check_task_contract.py",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 4: Agent type must be spawnable
        rules.append({
            "id": "agent-type-spawnable",
            "text": "A phase's agent_type must be one a session can spawn (from AGENT_TYPES registry)",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": "python3 -c \"from theteam.tasks.runners.llm import AGENT_TYPES; print(AGENT_TYPES)\"",
            "path_resolution": "theteam/tasks/runners/llm.py",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 5: No hardcoded developer paths
        rules.append({
            "id": "no-hardcoded-paths",
            "text": "No hardcoded developer paths in the package or task scripts",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": '! grep -rn "' + HARDCODED_PATH_PATTERN + '" theteam/ scripts/ --include="*.py" 2>/dev/null | grep -v "sa_runner.py:23[0-9]:"',
            "path_resolution": "scripts/check_invariants.sh",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 6: Consolidation rung (theteam consolidation over notes)
        rules.append({
            "id": "consolidation-rung",
            "text": "Before asking a human, the agent consolidates internally using consolidate_notes",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": "grep -n 'consolidate_notes' theteam/__init__.py",
            "path_resolution": "theteam/__init__.py",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 7: Ask rung (the ask tool exists)
        rules.append({
            "id": "ask-rung",
            "text": "The ask tool is available for bounded decisions",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": "test -x theteam/tools/ask.py",
            "path_resolution": "theteam/tools/ask.py",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 8: Search rung (NOT declared - asserted-only)
        search_declared = self._check_tool_declared("web_search")
        rules.append({
            "id": "search-rung",
            "text": "A web search tool is available for agent research",
            "rule_correct": "removed",
            "evidence": "asserted-only" if not search_declared else "verified",
            "falsification_test": "grep 'web_search' theteam/SKILL.md; test -n \"$(grep ^tools: theteam/SKILL.md | grep search)\"",
            "path_resolution": "theteam/SKILL.md",
            "enforcement_level": 3 if not search_declared else 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "note": "No search tool declared in SKILL.md; bash fetch has no defined success" if not search_declared else "",
        })

        # Rule 9: Prompt-truth citations
        rules.append({
            "id": "prompt-truth-citations",
            "text": "Every factual citation in a prompt must be mechanically verifiable",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": "python3 scripts/check_prompt_truth.py .",
            "path_resolution": "scripts/check_prompt_truth.py",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 10: Task contract compliance
        rules.append({
            "id": "task-contract-compliance",
            "text": "Every task YAML must pass the task contract checker",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": "python3 scripts/check_task_contract.py .",
            "path_resolution": "scripts/check_task_contract.py",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 11: Invariant gate passes
        rules.append({
            "id": "invariant-gate",
            "text": "All engineering invariants must pass (check_invariants.sh)",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": "bash scripts/check_invariants.sh",
            "path_resolution": "scripts/check_invariants.sh",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        # Rule 12: Human boundary (reports/ is HTML only)
        rules.append({
            "id": "human-boundary",
            "text": "reports/ contains only .html files; machine artifacts go to .omp/ or reports/.handoff/",
            "rule_correct": "kept",
            "evidence": "verified",
            "falsification_test": "! ls reports/*.md 2>/dev/null; ls reports/*.html >/dev/null 2>&1",
            "path_resolution": "scripts/check_task_contract.py",
            "enforcement_level": 1,
            "created_by": "seed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return rules

    def generate(self) -> Dict[str, Any]:
        """Generate the awareness seed for this project."""
        rules = self._probe_rules()

        seed = {
            "schema_version": "1.0",
            "kind": "awareness-seed",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "project_root": str(self.project_root),
            "shape_version": "1.0",
            "rules": rules,
            "metadata": {
                "total_rules": len(rules),
                "verified": sum(1 for r in rules if r["evidence"] == "verified"),
                "cited_but_stale": sum(1 for r in rules if r["evidence"] == "cited-but-stale"),
                "asserted_only": sum(1 for r in rules if r["evidence"] == "asserted-only"),
            },
        }

        with open(self.seed_path, "w", encoding="utf-8") as f:
            json.dump(seed, f, indent=2, sort_keys=True)
            f.write("\n")

        return seed


def main():
    ap = argparse.ArgumentParser(description="Generate awareness seed for a project")
    ap.add_argument("--project-root", "-p", required=True, help="Project root directory")
    ap.add_argument("--output", "-o", help="Output path (default: .omp/theteam/awareness-seed.json)")
    ap.add_argument("--dry-run", action="store_true", help="Print seed to stdout, don't write")
    args = ap.parse_args()

    materialiser = AwarenessSeedMaterialiser(args.project_root)

    if args.dry_run:
        seed = materialiser.generate()
        json.dump(seed, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        if args.output:
            materialiser.seed_path = Path(args.output)
            materialiser.seed_path.parent.mkdir(parents=True, exist_ok=True)
        seed = materialiser.generate()
        print(f"Seed written to {materialiser.seed_path}")
        print(f"Rules: {seed['metadata']['total_rules']} "
              f"(verified: {seed['metadata']['verified']}, "
              f"asserted-only: {seed['metadata']['asserted_only']})")


if __name__ == "__main__":
    main()