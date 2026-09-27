#!/usr/bin/env python3
"""
Folder Structure Monitor - Agentic-Friendly Data Layer

Lightweight monitoring for project folder structure health.
Provides compact JSON summaries for agents to quickly assess state.
"""

import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

def _project_root() -> Path:
    return Path(os.environ.get("THETEAM_PROJECT_ROOT") or os.getcwd())


def _state():
    from theteam.state import StateStore

    return StateStore(str(_project_root()))


def _monitor_log() -> Path:
    return _state().folder_monitor_log

EXPECTED_ROOT_FILES = {
    "README.md", "theteam.config", "system-awareness-config.json",
    "package.json", "IMPLEMENTATION_CONTEXT.md", "IMPLEMENTATION_PLAN.md"
}

EXPECTED_FOLDERS = {
    "critical": ["theteam", "tasks", "docs", "config", "diagrams", ".omp"],
    "secondary": ["scripts", "security", "team", "team/context"],
    "optional": ["python-project", "typescript-project", "bash-project", "routine-engine"]
}

FOLDER_PLACEMENT_RULES = {
    "diagrams": ["*.html", "*.svg", "*.png", "*.json", "*.md"],
    ".omp/theteam": ["ledger.json", "tasks-ledger.json", "health-score.json"],
    "theteam/reports": ["*.md", "*.json"],
    "tasks": ["*.py", "*.yaml", "*.json", "*.md"],

}


def assess_folder_structure() -> Dict:
    """Assess and log folder structure health."""
    issues = []
    recommendations = []
    project_root = _project_root()
    state = _state()

    # Check critical folders exist
    for folder in EXPECTED_FOLDERS["critical"]:
        if not (project_root / folder).exists():
            issues.append(f"Critical folder missing: {folder}")

    # Check for files in wrong locations
    root_files = [f for f in project_root.iterdir()
                  if f.is_file() and f.name not in EXPECTED_ROOT_FILES]

    if root_files:
        unexpected = [f.name for f in root_files]
        recommendations.append(f"Move unexpected files from root: {unexpected[:5]}...")

    # Check ledger locations
    ledger_paths = [
        project_root / "system-awareness-ledger.json",
        state.root / "ledger.json"
    ]
    ledger_found = any(p.exists() for p in ledger_paths)
    if not ledger_found:
        issues.append("System awareness ledger not found in expected locations")

    # Check for duplicate awareness runners
    awareness_runners = list(project_root.glob("tasks/*awareness*.py"))
    if len(awareness_runners) > 3:
        recommendations.append(f"Too many awareness runners ({len(awareness_runners)}), consider consolidating")

    # Check diagrams folder
    if not (project_root / "diagrams").exists():
        issues.append("Diagrams folder missing - architecture files should be organized here")

    # Generate report
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "issues": issues,
        "recommendations": recommendations,
        "folder_count": len([d for d in project_root.iterdir() if d.is_dir()]),
        "file_count": len([f for f in project_root.iterdir() if f.is_file()]),
        "ledger_location": str(ledger_paths[1] if ledger_paths[1].exists() else ledger_paths[0]),
        "awareness_runners": len(awareness_runners),
        "diagrams_folder_exists": (project_root / "diagrams").exists()
    }

    return report


def get_compact_summary() -> Dict:
    """Get lightweight compact summary for agents."""
    report = assess_folder_structure()
    
    return {
        "project": "team",
        "timestamp": report["timestamp"],
        "folder_health": {
            "critical_folders_ok": len(report["issues"]) == 0,
            "root_clutter": report["file_count"] - len(EXPECTED_ROOT_FILES),
            "ledger_exists": "ledger_location" in report,
            "diagrams_ready": report["diagrams_folder_exists"]
        },
        "system_awareness": {
            "primary_runner": "scripts/sa_runner.py",
            "enabled": True,
            "last_analysis": report["timestamp"],
            "consolidated": True
        },
        "recommendations": report["recommendations"][:3]  # Top 3 only
    }


def log_assessment() -> None:
    """Append assessment to log file."""
    report = assess_folder_structure()
    log_path = _monitor_log()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, 'a') as f:
        f.write(json.dumps(report) + "\n")


if __name__ == "__main__":
    print(json.dumps(get_compact_summary(), indent=2))
    log_assessment()