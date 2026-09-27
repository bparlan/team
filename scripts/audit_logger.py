#!/usr/bin/env python3
"""
Audit logger CLI.

Thin wrapper around `theteam.core.audit.AuditLogger`, the canonical
implementation. The class used to live here and was imported by nothing; it
now lives in the package where components can reach it.

Usage:
    python scripts/audit_logger.py log start <task>
    python scripts/audit_logger.py log complete <task>
    python scripts/audit_logger.py log fail <task>
    python scripts/audit_logger.py trail [task]
    python scripts/audit_logger.py verify
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from theteam.core.audit import AuditLogger  # noqa: E402


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 1

    logger = AuditLogger()
    command = argv[0]

    if command == "log":
        if len(argv) < 3:
            print("Usage: audit_logger.py log <start|complete|fail> <task>")
            return 1
        event, task = argv[1], argv[2]
        if event == "start":
            logger.log_task_start(task, {"type": "unknown", "priority": 5})
        elif event == "complete":
            logger.log_task_complete(task, {"success": True, "output": "ok"}, 1.0)
        elif event == "fail":
            logger.log_task_failed(task, "error", "unknown")
        else:
            print(f"Unknown event: {event}")
            return 1
        return 0

    if command == "trail":
        task = argv[1] if len(argv) > 1 else None
        print(json.dumps(logger.get_audit_trail(task), indent=2))
        return 0

    if command == "verify":
        ok = logger.verify_chain()
        print("Audit chain OK" if ok else "Audit chain BROKEN")
        return 0 if ok else 1

    print(f"Unknown command: {command}")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
