from datetime import datetime, timezone
from typing import Dict, List, Optional

class ConversationConverter:
    def __init__(self, project_root: str = "."):
        self.project_root = project_root

    def convert_recent_chat(self, lines: int = 50) -> Dict:
        task_id = f"conv-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        return {
            "id": task_id,
            "name": "Converted Conversation Task",
            "type": "conversation",
            "priority": "medium",
            "schedule": {"mode": "once"},
            "phases": [
                {
                    "name": "analyze",
                    "script": "theteam/workflow/context_aggregator.py",
                    "args": ["--compact"],
                    "timeout_seconds": 60
                }
            ],
            "outputs": [
                {"path": ".omp/theteam/conversation-task.json", "type": "json"}
            ],
            "metadata": {
                "created_by": "converter",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": "recent_chat",
                "lines_analyzed": lines
            }
        }

    def convert_user_request(self, request: str) -> Dict:
        task_id = f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        task_type = self._classify_request(request)
        return {
            "id": task_id,
            "name": self._suggest_task_name(request),
            "type": task_type,
            "priority": "medium",
            "schedule": {"mode": "once"},
            "phases": [
                {
                    "name": "analyze",
                    "script": "theteam/workflow/context_aggregator.py",
                    "args": ["--compact"],
                    "timeout_seconds": 60
                },
                {
                    "name": "execute",
                    "script": "theteam/subskills/task_stack/orchestrator.py",
                    "args": ["execute", task_id],
                    "timeout_seconds": 300
                }
            ],
            "outputs": [
                {"path": ".omp/theteam/user-task.json", "type": "json"}
            ],
            "metadata": {
                "created_by": "converter",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "source": "user_request",
                "request_preview": request[:100]
            }
        }

    def _classify_request(self, request: str) -> str:
        request_lower = request.lower()
        if any(word in request_lower for word in ["loop", "repeat", "schedule", "every"]):
            return "loop"
        if any(word in request_lower for word in ["build", "create", "implement", "develop"]):
            return "one-shot"
        return "one-shot"

    def _suggest_task_name(self, request: str) -> str:
        words = request.split()[:5]
        return " ".join(words).title()