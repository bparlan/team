#!/usr/bin/env python3
"""
Task execution. Layer 3: runs one phase, collects its result.

Moved here from `subskills/task_stack/executor.py`, which §5.3 removes. The
behaviour is unchanged; the M4 safety wrapper (`ResourceLimiter`,
`AgentIsolation`, `CircuitBreaker`) lands on this class, not on a directory
that is on its way out.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict

from theteam.core.agent_isolation import AgentIsolation, IsolationError, IsolationPolicy

# M4 wiring. §5.1: every phase runs inside an AgentIsolation container, so no
# Layer 3 call to subprocess is left without a Layer 4 guard in the same call
# frame. CircuitBreaker/ResourceLimiter/AuditLogger call sites live in the
# siblings' surfaces (S1, S3) and are not duplicated here.

# Image used for isolated phase execution. Override per environment; the
# default is a tag that exists on this machine (the bare `theteam` image
# does not). Kept as a named constant so the choice is visible and the
# literal is not scattered through the method body.
IMAGE_ENV_VAR = "THETEAM_AGENT_IMAGE"
DEFAULT_IMAGE = "theteam:p4final"

class TaskExecutor:
    def __init__(self, project_root: str = "."):
        from theteam.state import StateStore

        self.project_root = Path(project_root)
        self.execution_log = StateStore(str(self.project_root)).execution_log

    def execute_phase(self, phase: Dict) -> Dict:
        script = phase.get("script")
        args = phase.get("args", [])
        timeout = phase.get("timeout_seconds", 300)

        script_path = self.project_root / script
        if not script_path.exists():
            return {"success": False, "error": f"Script not found: {script}"}

        cmd = ["python3", str(script_path)] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.project_root),
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Phase timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute_task(self, task_def: Dict) -> Dict:
        results = []
        for phase in task_def.get("phases", []):
            phase_result = self.execute_phase(phase)
            phase_result["phase"] = phase["name"]
            results.append(phase_result)
            if not phase_result["success"]:
                break

        return {
            "task_id": task_def["id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phases": results,
            "overall_success": all(r["success"] for r in results)
        }

    def log_execution(self, result: Dict):
        self.execution_log.parent.mkdir(parents=True, exist_ok=True)
        with open(self.execution_log, 'a') as f:
            f.write(json.dumps(result) + "\n")