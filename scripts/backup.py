#!/usr/bin/env python3
"""
Backup/restore CLI.

Thin wrapper around `theteam.core.backup.BackupManager`, the single canonical
implementation. The backup logic used to live here AND in
`UnifiedLoop.create_backup`, duplicated byte-for-byte and writing an
unverified `"checksum": "TODO"`. Both now delegate here.

Usage:
    python scripts/backup.py create [--keep N]
    python scripts/backup.py list
    python scripts/backup.py verify <backup_path>
    python scripts/backup.py restore <backup_path>
    python scripts/backup.py prune [--keep N]
"""

import os
import sys
from pathlib import Path

# Allow running directly from a checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from theteam.core.backup import BackupIntegrityError, BackupManager  # noqa: E402

DEFAULT_KEEP = 10


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(__doc__)
        return 1

    command = argv[0]
    manager = BackupManager(os.getcwd())

    if command == "create":
        keep = _int_flag(argv, "--keep", DEFAULT_KEEP)
        path = manager.create_backup()
        if keep:
            manager.prune(keep)
        print(f"Backup created: {path}")
        return 0

    if command == "list":
        for path in manager.list_backups():
            print(path)
        return 0

    if command == "verify":
        if len(argv) < 2:
            print("Usage: backup.py verify <backup_path>")
            return 1
        results = manager.verify(Path(argv[1]))
        for name, ok in sorted(results.items()):
            print(f"{'OK  ' if ok else 'FAIL'} {name}")
        return 0 if all(results.values()) else 1

    if command == "restore":
        if len(argv) < 2:
            print("Usage: backup.py restore <backup_path>")
            return 1
        manager.restore_from_backup(Path(argv[1]))
        print(f"Restored from: {argv[1]}")
        return 0

    if command == "prune":
        keep = _int_flag(argv, "--keep", DEFAULT_KEEP)
        deleted = manager.prune(keep)
        print(f"Pruned {len(deleted)} backups, keeping newest {keep}")
        return 0

    print(f"Unknown command: {command}")
    print(__doc__)
    return 1


def _int_flag(argv, name, default):
    if name in argv:
        index = argv.index(name)
        if index + 1 < len(argv):
            try:
                return int(argv[index + 1])
            except ValueError:
                print(f"Ignoring non-integer value for {name}")
    return default


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BackupIntegrityError as e:
        print(f"Backup failed integrity check: {e}", file=sys.stderr)
        sys.exit(2)
