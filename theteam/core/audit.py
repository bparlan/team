#!/usr/bin/env python3
"""
Audit logging for theteam.

Phase 4 deliverable. This module was previously `scripts/audit_logger.py`,
which nothing imported - the roadmap called for an audit module and none was
actually wired in. It now lives in the package where components can import it.

Two properties the original lacked:
  * Tamper evidence. Every entry carries `prev_hash` and its own `hash`, so
    `verify_chain()` detects any edit to the log.
  * Bounded growth. `audit.jsonl` is trimmed to `max_entries` lines on write,
    which is the retention policy for the audit trail.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fields excluded from the hash: `hash` cannot cover itself, and `timestamp`
# is already committed by the previous entry's hash.
_HASH_EXCLUDED = ("hash", "prev_hash")


class AuditLogger:
    """
    Append-only, hash-chained audit trail with retention.

    Writes JSONL to `<log_dir>/audit.jsonl`. Each line is one event. The chain
    makes silent modification detectable; `max_entries` bounds file growth.
    """

    def __init__(self, log_dir: Optional[str] = None, max_entries: int = 10000) -> None:
        if log_dir is None:
            log_dir = os.path.join(os.getcwd(), ".loop-log")
        self.log_dir = log_dir
        self.audit_file = os.path.join(log_dir, "audit.jsonl")
        self.max_entries = max_entries
        os.makedirs(self.log_dir, exist_ok=True)

    # -- hashing -----------------------------------------------------------

    @staticmethod
    def _entry_hash(entry: Dict[str, Any]) -> str:
        """Hash an entry's payload plus its predecessor's hash."""
        payload = {k: v for k, v in entry.items() if k not in _HASH_EXCLUDED}
        payload["prev_hash"] = entry.get("prev_hash", "")
        encoded = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def _last_hash(self) -> str:
        """Hash of the most recent entry, or '' when the log is empty."""
        entries = self._read_all()
        return entries[-1].get("hash", "") if entries else ""

    # -- io ----------------------------------------------------------------

    def _read_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.audit_file):
            return []
        entries: List[Dict[str, Any]] = []
        with open(self.audit_file, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    # A partially written or hand-edited line is evidence of
                    # tampering, so keep it out of the chain view.
                    logger.warning("Skipping malformed audit line")
        return entries

    def _write_entry(self, entry: Dict[str, Any]) -> None:
        """Append an entry and enforce retention."""
        entry.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        entry["prev_hash"] = self._last_hash()
        entry["hash"] = self._entry_hash(entry)

        try:
            # A crash can leave a partial final line with no trailing newline.
            # Appending directly would concatenate the next entry onto that
            # fragment, producing one unparseable line and silently dropping
            # the entry from the trail forever. Terminate the fragment first.
            needs_newline = False
            if os.path.exists(self.audit_file) and os.path.getsize(self.audit_file) > 0:
                with open(self.audit_file, "rb") as probe:
                    probe.seek(-1, os.SEEK_END)
                    needs_newline = probe.read(1) != b"\n"
            prefix = "\n" if needs_newline else ""

            with open(self.audit_file, "a", encoding="utf-8") as handle:
                handle.write(prefix + json.dumps(entry, default=str) + "\n")
        except OSError as e:
            # Losing the audit trail silently would be worse than logging it.
            logger.error(f"Failed to write audit entry: {e}")
            raise
        self._enforce_retention()

    def _enforce_retention(self) -> int:
        """Trim the log to the newest `max_entries` lines. Returns lines dropped."""
        if self.max_entries <= 0 or not os.path.exists(self.audit_file):
            return 0
        # Route through _read_all(), which already skips unparseable lines.
        # A crash can leave a truncated tail fragment; parsing it unguarded
        # here would raise JSONDecodeError inside _write_entry and turn a
        # recoverable fragment into a hard failure of the whole write path.
        entries = self._read_all()
        if len(entries) <= self.max_entries:
            return 0

        keep = entries[-self.max_entries:]
        # Trimming drops the earliest entries, so the new first entry's
        # prev_hash no longer matches the file that is now gone. Rebase the
        # chain so verify_chain() stays true across a retention pass.
        previous = ""
        for entry in keep:
            entry["prev_hash"] = previous
            entry["hash"] = self._entry_hash(entry)
            previous = entry["hash"]

        with open(self.audit_file, "w", encoding="utf-8") as handle:
            for entry in keep:
                handle.write(json.dumps(entry, default=str) + "\n")

        dropped = len(entries) - len(keep)
        logger.info(f"Audit retention: dropped {dropped} entries, kept {len(keep)}")
        return dropped

    # -- event loggers -----------------------------------------------------

    def log_task_start(self, task_name: str, task_data: Dict[str, Any]) -> None:
        """Log task execution start."""
        self._write_entry({
            "event": "task_start",
            "task": task_name,
            "task_type": task_data.get("type", "unknown"),
            "task_priority": task_data.get("priority", 0),
            "execution": str(task_data.get("execution", ""))[:100],
        })

    def log_task_complete(self, task_name: str, result: Dict[str, Any], duration: float) -> None:
        """Log task execution completion."""
        self._write_entry({
            "event": "task_complete",
            "task": task_name,
            "result": result.get("success", False),
            "output": str(result.get("output", ""))[:200],
            "duration_seconds": duration,
        })

    def log_task_failed(self, task_name: str, error: Any, failure_type: str) -> None:
        """Log task execution failure."""
        self._write_entry({
            "event": "task_failed",
            "task": task_name,
            "error": str(error)[:200],
            "failure_type": failure_type,
        })

    def log_security_violation(self, task_name: str, violation: Dict[str, Any]) -> None:
        """Log security policy violation."""
        self._write_entry({
            "event": "security_violation",
            "task": task_name,
            "rule": violation.get("rule", "unknown"),
            "severity": violation.get("severity", "unknown"),
            "action": violation.get("action", "unknown"),
        })

    def log_state_change(self, from_state: Any, to_state: Any, reason: str = "") -> None:
        """Log state transition."""
        self._write_entry({
            "event": "state_change",
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason,
        })

    def log_integrity_check(self, task_name: str, checksum: str, valid: bool) -> None:
        """Log integrity verification result."""
        self._write_entry({
            "event": "integrity_check",
            "task": task_name,
            "checksum": checksum,
            "valid": valid,
        })

    # -- readers -----------------------------------------------------------

    def get_audit_trail(self, task_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve the audit trail, optionally filtered by task name."""
        entries = self._read_all()
        if task_name is None:
            return entries
        return [e for e in entries if e.get("task") == task_name]

    def verify_chain(self) -> bool:
        """
        Walk the log and confirm every entry's hash and linkage.

        Returns False on any tampering. Truncated trailing lines are ignored
        rather than treated as corruption, since a crash mid-write is normal.
        """
        entries = self._read_all()
        if not entries:
            return True
        previous = ""
        for entry in entries:
            if entry.get("prev_hash", "") != previous:
                logger.warning("Audit chain broken: prev_hash mismatch")
                return False
            if self._entry_hash(entry) != entry.get("hash"):
                logger.warning("Audit chain broken: entry hash mismatch")
                return False
            previous = entry.get("hash", "")
        return True

    def compute_checksum(self, file_path: str) -> Optional[str]:
        """Compute the sha256 checksum of a file, or None if unreadable."""
        try:
            digest = hashlib.sha256()
            with open(file_path, "rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError as e:
            logger.error(f"Could not checksum {file_path}: {e}")
            return None
