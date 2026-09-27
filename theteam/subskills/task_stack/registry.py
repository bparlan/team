import json
from pathlib import Path
from typing import Dict, List, Optional

class TaskRegistry:
    def __init__(self, registry_path: str = ".mp/theteam/task-registry.json"):
        self.path = Path(registry_path)
        self.registry = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            with open(self.path, 'r') as f:
                return json.load(f)
        return {"tasks": {}}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump(self.registry, f, indent=2)

    def register(self, task_def: Dict) -> bool:
        self.registry["tasks"][task_def["id"]] = task_def
        self._save()
        return True

    def get(self, task_id: str) -> Optional[Dict]:
        return self.registry["tasks"].get(task_id)

    def list_all(self) -> List[Dict]:
        return list(self.registry["tasks"].values())
