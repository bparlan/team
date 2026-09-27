import subprocess
import json
from pathlib import Path
from datetime import datetime, timezone
import sys
from typing import Dict

class TaskExecutor:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.execution_log = self.project_root / ".mp" / "theteam" / "task-execution.log"

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