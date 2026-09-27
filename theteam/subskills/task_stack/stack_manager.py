from pathlib import Path
from typing import Dict, List, Optional
import json

class TaskStackManager:
    def __init__(self, stack_path: str):
        self.path = Path(stack_path)
        self.stack = self._load()

    def _load(self) -> Dict:
        if self.path.exists():
            with open(self.path, 'r') as f:
                return json.load(f)
        return {"stack": [], "completed": []}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'w') as f:
            json.dump(self.stack, f, indent=2)

    def push(self, task_id: str, position: Optional[int] = None):
        if position is None:
            self.stack["stack"].append(task_id)
        else:
            self.stack["stack"].insert(position, task_id)
        self._save()

    def pop(self) -> Optional[str]:
        if self.stack["stack"]:
            task_id = self.stack["stack"].pop(0)
            self._save()
            return task_id
        return None

    def peek(self) -> Optional[str]:
        if self.stack["stack"]:
            return self.stack["stack"][0]
        return None

    def get_stack(self) -> List[str]:
        return self.stack["stack"]