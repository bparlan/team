#!/usr/bin/env python3
"""
theteam.state - the single place a state path is resolved.

Every component that reads or writes team state asks this module. There is no
module-level constant and no default project root: a caller either passes the
project it means, or the path falls back to the user's home. That is the whole
point. The previous layout hardcoded absolute paths and walked up a fixed
number of parent directories, which resolves correctly in one checkout and
points at a checkout that may not exist everywhere else.
"""

import json
import os
from pathlib import Path
from typing import List, Optional

STATE_DIR_ENV = "THETEAM_STATE_DIR"


def state_dir(project_root: Optional[str] = None) -> Path:
    """The one state directory for a project.

    `THETEAM_STATE_DIR` wins when set, so a container or a test can point the
    whole system at a scratch directory. Otherwise state lives under the
    project it describes; with no project it lives under the user's home.
    """
    override = os.environ.get(STATE_DIR_ENV)
    if override:
        return Path(override).expanduser()
    base = Path(project_root).expanduser() if project_root else Path.home()
    return base / ".omp" / "theteam"


class StateStore:
    """
    Every path the team writes, resolved once from one project root.

    The names below are the files the current components read and write, and
    ARCHITECTURE.md §5.5 lists the same ones. That list was corrected against
    this module: it had claimed `tasks/registry.cache.json` and
    `audit/chain.jsonl`, neither of which is a path anything writes. The YAML
    repository landed in M2 and the audit chain resolved in M4, so this module
    is the source and the doc follows it.
    """

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = Path(project_root).expanduser().resolve() if project_root else None
        self.root = state_dir(project_root)

    # -- directories -------------------------------------------------------

    @property
    def tasks_dir(self) -> Path:
        return self.root / "tasks"

    @property
    def audit_dir(self) -> Path:
        return self.root / "audit"

    @property
    def events_dir(self) -> Path:
        return self.root / "events"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def proposals(self) -> Path:
        return self.root / "proposals"

    @property
    def members(self) -> Path:
        return self.root / "members"

    @property
    def discussions(self) -> Path:
        return self.root / "discussions"

    # -- files -------------------------------------------------------------

    @property
    def task_registry(self) -> Path:
        return self.root / "task-registry.json"

    @property
    def task_schedule(self) -> Path:
        return self.root / "task-schedule.json"

    @property
    def task_stack(self) -> Path:
        return self.root / "task-stack.json"

    @property
    def task_daemon_status(self) -> Path:
        return self.root / "task-stack-daemon.json"

    @property
    def task_daemon_pid(self) -> Path:
        return self.root / "task-stack.pid"

    @property
    def execution_log(self) -> Path:
        return self.root / "task-execution.log"

    @property
    def event_log(self) -> Path:
        return self.root / "event_log.json"

    @property
    def state_file(self) -> Path:
        return self.root / "state.json"

    @property
    def tool_manifest(self) -> Path:
        return self.root / "tool-manifest.json"

    @property
    def commentary_stop(self) -> Path:
        return self.root / "commentary.stop"

    @property
    def folder_monitor_log(self) -> Path:
        return self.root / "folder-monitor.log"

    # -- io ----------------------------------------------------------------

    def ensure(self) -> Path:
        """Create the state directory. Returns it, so callers can report it."""
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    def read_json(self, path: Path) -> dict:
        """Parsed JSON, or `{}` when the file does not exist. Raises on bad JSON."""
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def read_jsonl(self, path: Path) -> List[dict]:
        """Every parseable JSONL record. A malformed line is evidence, not noise."""
        if not path.exists():
            return []
        records = []
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                records.append(json.loads(line))
        return records
