#!/usr/bin/env python3
"""Regression tests for theteam.core.backup.BackupManager.

Contracts defended here, all observable through the public API:

  * A backup/restore round trip returns captured state byte-for-byte.
  * The manifest carries a real sha256 of each captured file's bytes.
  * Restore verifies every digest BEFORE writing anything; a corrupt backup
    raises and leaves live state bit-for-bit untouched.
  * prune() keeps the newest N backups by name order and deletes the rest.
"""

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest


from theteam.core.backup import (
    BACKUP_VERSION,
    MANIFEST_NAME,
    BackupIntegrityError,
    BackupManager,
)

# Sample live state, mirroring the paths BackupManager claims to capture.
SAMPLE_STATE = {
    "state/discussions.json": b'{"discussions": [{"id": "d1", "topic": "alpha"}]}',
    "state/nested/deep.txt": b"deeply nested state bytes\n",
    ".omp/theteam/state.json": b'{"version": 3, "tasks": {}}',
    ".omp/theteam/event_log.json": b'[{"seq": 1, "event": "created"}]',
}

# A source file that must NEVER be captured (backing up data, not code).
SOURCE_FILE = "theteam/core/unified_loop.py"
SOURCE_BYTES = b"# production source, not state\n"


def _original_snapshot() -> dict:
    """The live state as `_make_state` left it, including the source file."""
    payload = dict(SAMPLE_STATE)
    payload[SOURCE_FILE] = SOURCE_BYTES
    return payload


def _make_state(root: Path) -> None:
    """Create the sample live state under `root`."""
    for rel, payload in SAMPLE_STATE.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    source = root / SOURCE_FILE
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(SOURCE_BYTES)


def _manager(tmp_path: Path) -> BackupManager:
    root = tmp_path / "project"
    root.mkdir()
    _make_state(root)
    return BackupManager(str(root))


def _snapshot(root: Path) -> dict:
    """Map every file under `root` (excluding `backups/`) to its bytes."""
    return {
        p.relative_to(root).as_posix(): p.read_bytes()
        for p in sorted(root.rglob("*"))
        if p.is_file() and "backups" not in p.relative_to(root).parts
    }


def _manifest(backup: Path) -> dict:
    return json.loads((backup / MANIFEST_NAME).read_text())


def _create_at(manager: BackupManager, name: str) -> Path:
    """Create a backup at a deterministic location under backups/."""
    return manager.create_backup(str(manager.backup_root / name))


def _corrupt(backup: Path, rel: str) -> None:
    """Flip the bytes of one captured file inside the backup, manifest untouched."""
    target = backup / "data" / rel
    target.write_bytes(target.read_bytes() + b"CORRUPTION")


# -- round trip ------------------------------------------------------------


def test_restore_returns_captured_state_byte_for_byte(tmp_path):
    """Whatever create_backup captured, restore puts back exactly."""
    manager = _manager(tmp_path)
    root = manager.project_root
    before = _snapshot(root)

    backup = manager.create_backup()
    assert manager.verify(backup) == {rel: True for rel in SAMPLE_STATE}

    # Destroy the live state: overwrite, blank out, delete one file entirely.
    (root / "state/discussions.json").write_bytes(b'DEGRADED {"discussions": []}')
    (root / ".omp/theteam/state.json").write_bytes(b"{}")
    (root / "state/nested/deep.txt").write_bytes(b"")
    (root / ".omp/theteam/event_log.json").unlink()

    manager.restore_from_backup(backup)

    assert _snapshot(root) == before


def test_restore_recreates_a_deleted_captured_file(tmp_path):
    """Restore is a put-back, not an in-place patch: deleted state reappears."""
    manager = _manager(tmp_path)
    root = manager.project_root
    backup = manager.create_backup()

    (root / ".omp/theteam/event_log.json").unlink()
    assert not (root / ".omp/theteam/event_log.json").exists()

    manager.restore_from_backup(backup)

    assert (root / ".omp/theteam/event_log.json").read_bytes() == SAMPLE_STATE[
        ".omp/theteam/event_log.json"
    ]


def test_restore_leaves_files_absent_from_the_backup_alone(tmp_path):
    """Restore replaces captured paths only; unrelated live state survives."""
    manager = _manager(tmp_path)
    root = manager.project_root
    backup = manager.create_backup()

    newcomer = root / "state/created_after_backup.json"
    newcomer.write_bytes(b'{"added": "later"}')
    manager.restore_from_backup(backup)

    assert newcomer.read_bytes() == b'{"added": "later"}'


def test_backup_captures_state_but_not_source_code(tmp_path):
    """Regression: the old implementation copied unified_loop.py into backups."""
    manager = _manager(tmp_path)
    backup = manager.create_backup()

    captured = {entry["path"] for entry in _manifest(backup)["files"]}
    assert captured == set(SAMPLE_STATE)
    assert not any(path.endswith(".py") for path in captured)


def test_manifest_lists_every_captured_file_with_matching_count(tmp_path):
    """file_count and the files list agree with what was actually copied."""
    manager = _manager(tmp_path)
    backup = manager.create_backup()
    manifest = _manifest(backup)

    assert manifest["version"] == BACKUP_VERSION
    assert manifest["file_count"] == len(SAMPLE_STATE)
    assert {entry["path"] for entry in manifest["files"]} == set(SAMPLE_STATE)
    for entry in manifest["files"]:
        assert (backup / "data" / entry["path"]).is_file()


def test_two_backups_in_the_same_second_do_not_clobber_each_other(tmp_path):
    """Collision handling: the second backup must not overwrite the first."""
    manager = _manager(tmp_path)
    first = manager.create_backup()
    second = manager.create_backup()

    assert first != second
    assert first.is_dir() and second.is_dir()
    assert manager.verify(first) == {rel: True for rel in SAMPLE_STATE}
    assert manager.verify(second) == {rel: True for rel in SAMPLE_STATE}


def test_backup_of_an_empty_project_still_restores_cleanly(tmp_path):
    """Documented contract: a backup with nothing to capture is well-defined."""
    root = tmp_path / "bare"
    root.mkdir()
    manager = BackupManager(str(root))

    backup = manager.create_backup()
    manifest = _manifest(backup)

    assert manifest["files"] == []
    assert manifest["file_count"] == 0
    manager.restore_from_backup(backup)  # no-op, must not raise


# -- manifest digests ------------------------------------------------------


def test_manifest_digest_is_the_real_sha256_of_the_captured_bytes(tmp_path):
    """Anti-placeholder contract: digests are computed, not literal strings."""
    manager = _manager(tmp_path)
    backup = manager.create_backup()
    entries = _manifest(backup)["files"]
    assert entries, "expected captured files to assert against"

    for entry in entries:
        copied = (backup / "data" / entry["path"]).read_bytes()
        assert entry["sha256"] == hashlib.sha256(copied).hexdigest()
        # The digest describes the original live bytes, not a re-encoding.
        assert entry["sha256"] == hashlib.sha256(SAMPLE_STATE[entry["path"]]).hexdigest()
        assert entry["sha256"] not in ("", "TODO", "checksum")


def test_verify_reports_false_for_a_deleted_captured_file(tmp_path):
    """verify() reports every problem instead of raising on the first one."""
    manager = _manager(tmp_path)
    backup = manager.create_backup()
    (backup / "data" / "state/nested/deep.txt").unlink()

    results = manager.verify(backup)

    assert results["state/nested/deep.txt"] is False
    assert results["state/discussions.json"] is True


# -- verify before mutate --------------------------------------------------


def test_restore_of_a_corrupt_backup_raises_and_leaves_live_state_untouched(tmp_path):
    """The data-loss guard: nothing is written when any digest fails.

    The first manifest entry is corrupted and every live file is mutated, so an
    implementation that copies file-by-file while verifying would restore the
    later entries and be caught here.
    """
    manager = _manager(tmp_path)
    root = manager.project_root
    before_backup = _snapshot(root)

    backup = manager.create_backup()
    _corrupt(backup, _manifest(backup)["files"][0]["path"])

    live = _snapshot(root)
    for rel in live:
        (root / rel).write_bytes(b"MUTATED " + rel.encode())
    mutated = _snapshot(root)
    assert mutated != before_backup

    with pytest.raises(BackupIntegrityError) as excinfo:
        manager.restore_from_backup(backup)

    assert _snapshot(root) == mutated
    message = str(excinfo.value)
    assert _manifest(backup)["files"][0]["path"] in message
    assert "untouched" in message


def test_restore_rejects_a_backup_whose_file_disappeared(tmp_path):
    """A missing file is a verification failure, not a silently skipped entry."""
    manager = _manager(tmp_path)
    root = manager.project_root
    backup = manager.create_backup()
    (backup / "data" / "state/discussions.json").unlink()

    with pytest.raises(BackupIntegrityError):
        manager.restore_from_backup(backup)

    assert (root / "state/discussions.json").read_bytes() == SAMPLE_STATE[
        "state/discussions.json"
    ]


@pytest.mark.parametrize(
    "breaker, description",
    [
        (lambda m, b: (b / "data" / "state/discussions.json").unlink(), "missing file"),
        (
            lambda m, b: (b / "data" / "state/discussions.json").write_bytes(b"x"),
            "altered bytes",
        ),
        (lambda m, b: (b / MANIFEST_NAME).unlink(), "missing manifest"),
        (lambda m, b: (b / MANIFEST_NAME).write_text("{not json"), "unreadable manifest"),
        (lambda m, b: shutil.rmtree(b), "deleted backup dir"),
    ],
)
def test_restore_refuses_unusable_backups(tmp_path, breaker, description):
    """Every way a backup can be unusable maps to BackupIntegrityError."""
    manager = _manager(tmp_path)
    root = manager.project_root
    backup = _create_at(manager, "backup_20240101_000000")
    breaker(manager, backup)

    with pytest.raises(BackupIntegrityError):
        manager.restore_from_backup(backup)

    assert _snapshot(root) == _original_snapshot()


# -- retention -------------------------------------------------------------


def test_prune_keeps_the_newest_and_deletes_the_rest(tmp_path):
    """Retention policy: newest N by name order survive, older ones are removed."""
    manager = _manager(tmp_path)
    names = [f"backup_2024010{i}_000000" for i in range(1, 6)]
    created = [_create_at(manager, name) for name in names]

    deleted = manager.prune(keep=2)

    assert deleted == created[:3][::-1]
    surviving = manager.list_backups()
    assert surviving == created[3:][::-1]
    for gone in deleted:
        assert not gone.exists()
    for kept in surviving:
        assert kept.is_dir()


def test_prune_keeps_everything_when_within_retention(tmp_path):
    """Deleting more than exists would be a retention bug, not a cleanup."""
    manager = _manager(tmp_path)
    created = [_create_at(manager, f"backup_20240101_00000{i}") for i in range(3)]

    assert manager.prune(keep=10) == []
    assert set(manager.list_backups()) == set(created)


def test_prune_rejects_a_non_positive_retention_count(tmp_path):
    """keep=0 would delete every backup; that must be refused, not obeyed."""
    manager = _manager(tmp_path)
    created = [_create_at(manager, f"backup_20240101_00000{i}") for i in range(2)]

    with pytest.raises(ValueError):
        manager.prune(keep=0)

    assert all(path.is_dir() for path in created)


def test_surviving_backups_still_restore_after_pruning(tmp_path):
    """Pruning must not damage the backups it keeps."""
    manager = _manager(tmp_path)
    root = manager.project_root
    for i in range(3):
        (root / ".omp/theteam/state.json").write_bytes(b'{"generation": %d}' % i)
        _create_at(manager, f"backup_20240101_00000{i}")

    manager.prune(keep=1)
    survivor = manager.list_backups()[0]

    manager.restore_from_backup(survivor)
    assert (root / ".omp/theteam/state.json").read_bytes() == b'{"generation": 2}'
