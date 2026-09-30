#!/usr/bin/env python3
"""
Backup and restore for theteam state.

Phase 4 deliverable. This is the single canonical implementation: the previous
logic was duplicated byte-for-byte in `scripts/backup.py` and in
`UnifiedLoop.create_backup`/`restore_from_backup` (both deleted in M10 with the
module they belonged to), and it wrote a literal
`"checksum": "TODO"` that nothing ever verified.

Design rules that matter:
  * Back up DATA, not source. The old code copied a production module into the
    backup, which is not a state backup.
  * Verify before mutating. `restore_from_backup` checks every sha256 against
    the manifest first and raises `BackupIntegrityError` without touching live
    state if anything is wrong.
  * Bounded growth. `prune()` enforces a retention count over the backup dir.
"""

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"
BACKUP_VERSION = "2.0"

# What gets captured. State and data only - never source code.
CAPTURED_PATHS: Tuple[str, ...] = (
    "state",
    ".omp/theteam/state.json",
    ".omp/theteam/event_log.json",
)


class BackupIntegrityError(RuntimeError):
    """Raised when a backup fails verification and must not be restored."""


class BackupManager:
    """
    Create, verify, restore and prune state backups.

    Backups land in `<project_root>/backups/backup_<UTC timestamp>` so they sort
    chronologically and never collide within a second-granularity timestamp
    (a numeric suffix is appended if needed).
    """

    def __init__(self, project_root: str) -> None:
        self.project_root = Path(project_root).resolve()
        self.backup_root = self.project_root / "backups"

    # -- helpers -----------------------------------------------------------

    def _files_under(self, path: Path) -> List[Path]:
        if path.is_file():
            return [path]
        if path.is_dir():
            return sorted(p for p in path.rglob("*") if p.is_file())
        return []

    def _captured_files(self) -> List[Path]:
        found: List[Path] = []
        for rel in CAPTURED_PATHS:
            found.extend(self._files_under(self.project_root / rel))
        return found

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _allocate_backup_dir(self) -> Path:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        candidate = self.backup_root / f"backup_{stamp}"
        suffix = 1
        while candidate.exists():
            candidate = self.backup_root / f"backup_{stamp}_{suffix}"
            suffix += 1
        return candidate

    # -- create ------------------------------------------------------------

    def create_backup(self, destination: Optional[str] = None) -> Path:
        """
        Capture current state into a new backup directory.

        Returns the backup path. A backup with nothing to capture still writes
        a valid (empty) manifest, so restore is well-defined either way.
        """
        backup_dir = Path(destination).resolve() if destination else self._allocate_backup_dir()
        data_dir = backup_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        entries: List[Dict[str, str]] = []
        for source in self._captured_files():
            relative = source.relative_to(self.project_root)
            target = data_dir / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            entries.append({
                "path": relative.as_posix(),
                "sha256": self._sha256(target),
                "size": str(target.stat().st_size),
            })

        manifest = {
            "version": BACKUP_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "project_root": str(self.project_root),
            "file_count": len(entries),
            "files": entries,
        }
        (backup_dir / MANIFEST_NAME).write_text(json.dumps(manifest, indent=2))

        logger.info(f"Backup created at {backup_dir} ({len(entries)} files)")
        return backup_dir

    # -- verify / restore --------------------------------------------------

    def _read_manifest(self, backup_path: Path) -> Dict:
        manifest_file = backup_path / MANIFEST_NAME
        if not manifest_file.exists():
            raise BackupIntegrityError(f"Manifest missing: {manifest_file}")
        try:
            return json.loads(manifest_file.read_text())
        except json.JSONDecodeError as e:
            raise BackupIntegrityError(f"Manifest unreadable: {e}") from e

    def verify(self, backup_path: Path) -> Dict[str, bool]:
        """
        Check every file against its recorded digest.

        Returns {relative_path: ok}. A missing file reports False rather than
        raising, so callers can report all problems at once.
        """
        backup_path = Path(backup_path)
        manifest = self._read_manifest(backup_path)
        results: Dict[str, bool] = {}
        for entry in manifest.get("files", []):
            target = backup_path / "data" / entry["path"]
            if not target.exists():
                results[entry["path"]] = False
                continue
            try:
                results[entry["path"]] = self._sha256(target) == entry.get("sha256")
            except OSError:
                results[entry["path"]] = False
        return results

    def restore_from_backup(self, backup_path: Path) -> None:
        """
        Restore state from a backup, verifying integrity first.

        Nothing is written unless every file verifies. Raises
        `BackupIntegrityError` listing the offending files otherwise.
        """
        backup_path = Path(backup_path)
        if not backup_path.is_dir():
            raise BackupIntegrityError(f"Backup directory not found: {backup_path}")

        results = self.verify(backup_path)
        corrupt = sorted(path for path, ok in results.items() if not ok)
        if corrupt:
            raise BackupIntegrityError(
                f"Backup {backup_path} failed integrity check; live state untouched. "
                f"Corrupt files: {corrupt}"
            )

        manifest = self._read_manifest(backup_path)
        for entry in manifest.get("files", []):
            source = backup_path / "data" / entry["path"]
            target = self.project_root / entry["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            # Replace rather than merge so restore is idempotent.
            if target.is_dir():
                shutil.rmtree(target)
            shutil.copy2(source, target)

        logger.info(f"Restored {manifest.get('file_count', 0)} files from {backup_path}")

    # -- retention ---------------------------------------------------------

    def list_backups(self) -> List[Path]:
        """Return backup directories, newest first."""
        if not self.backup_root.exists():
            return []
        dirs = [d for d in self.backup_root.iterdir() if d.is_dir() and (d / MANIFEST_NAME).exists()]
        return sorted(dirs, key=lambda d: d.name, reverse=True)

    def prune(self, keep: int = 10) -> List[Path]:
        """
        Delete all but the `keep` newest backups. Returns the deleted paths.

        This is the retention policy that keeps `backups/` from growing without
        bound on a long-running deployment.
        """
        if keep < 1:
            raise ValueError("keep must be >= 1")
        deleted: List[Path] = []
        for backup_dir in self.list_backups()[keep:]:
            try:
                shutil.rmtree(backup_dir)
                deleted.append(backup_dir)
            except OSError as e:
                logger.error(f"Could not prune {backup_dir}: {e}")
        if deleted:
            logger.info(f"Pruned {len(deleted)} backups, keeping newest {keep}")
        return deleted

    def verify_and_audit(self, backup_path: Path, audit: Optional["AuditLogger"] = None) -> Dict[str, bool]:
        """
        Verify a backup and record the result in the audit trail.

        Verification is a security-relevant action, so it is logged when an
        audit logger is supplied.
        """
        results = self.verify(Path(backup_path))
        if audit is not None:
            for name, ok in sorted(results.items()):
                audit.log_integrity_check(name, "", ok)
        return results
