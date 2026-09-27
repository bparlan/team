#!/usr/bin/env python3
"""
Regression tests for theteam.core.audit.AuditLogger.

The value of an audit trail is not that it records events -- it is that the
record resists later revision. Every test here defends a contract a caller
depends on:

  * entries form a hash chain (prev_hash links to the previous hash),
  * any post-hoc edit, deletion, or forgery is detected by verify_chain(),
  * retention bounds the file without breaking the chain it leaves behind,
  * a broken audit sink never takes down the loop that writes to it.

Tampering is done by rewriting the real persisted file, and sink failure is a
real OSError from the filesystem -- nothing here mocks the class under test.
"""

import hashlib
import json
import os
import sys

import pytest


from theteam.core.audit import AuditLogger
from theteam.core.task_contract import UnifiedTask


# -- helpers ---------------------------------------------------------------

def _entries(alog: AuditLogger):
    """Raw persisted entries, bypassing the logger's own readers."""
    with open(alog.audit_file, "r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _raw_lines(alog: AuditLogger):
    with open(alog.audit_file, "r", encoding="utf-8") as handle:
        return [line for line in handle if line.strip()]


def _rewrite(alog: AuditLogger, entries):
    with open(alog.audit_file, "w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry) + "\n")


def _seed(alog: AuditLogger, count: int, start: int = 0):
    for i in range(start, start + count):
        alog.log_security_violation(f"task-{i}", {
            "rule": f"rule-{i}",
            "severity": "high",
            "action": f"deny-{i}",
        })


# -- chaining --------------------------------------------------------------

def test_entries_form_a_verifiable_hash_chain(tmp_path):
    """Each entry's prev_hash is the previous entry's hash; the log verifies.

    A chain where every prev_hash is "" (or every hash identical) would pass
    a "file is non-empty" test yet detect nothing.
    """
    alog = AuditLogger(str(tmp_path))
    _seed(alog, 4)

    entries = _entries(alog)
    assert len(entries) == 4
    assert entries[0]["prev_hash"] == "", "first entry must anchor the chain"
    for earlier, later in zip(entries, entries[1:]):
        assert later["prev_hash"] == earlier["hash"]

    hashes = [e["hash"] for e in entries]
    assert all(len(h) == 64 for h in hashes)
    assert len(set(hashes)) == 4, "distinct payloads must not collide"
    assert alog.verify_chain() is True


# -- tamper detection ------------------------------------------------------

@pytest.mark.parametrize("field,replacement", [
    ("action", "allow-everything"),
    ("task", "task-0"),
    ("rule", "rule-forged"),
    ("severity", "low"),
    ("prev_hash", "0" * 64),
    ("hash", "f" * 64),
])
def test_verify_chain_detects_an_edited_field(tmp_path, field, replacement):
    """Editing any single field of a persisted entry breaks verification.

    Payload, backlink, and self-hash are each covered: dropping the link
    check, the recompute check, or the hash from the hashed payload all
    leave this test green.
    """
    alog = AuditLogger(str(tmp_path))
    _seed(alog, 3)
    assert alog.verify_chain() is True

    entries = _entries(alog)
    entries[1][field] = replacement
    _rewrite(alog, entries)

    assert alog.verify_chain() is False


def test_verify_chain_detects_a_deleted_entry(tmp_path):
    """Removing a middle entry breaks the link its successor depends on.

    Deletion is the tamper an attacker actually wants: no forged hash needed,
    just an absent line. The successor's prev_hash then points at nothing.
    """
    alog = AuditLogger(str(tmp_path))
    _seed(alog, 4)

    entries = _entries(alog)
    _rewrite(alog, [entries[0]] + entries[2:])

    assert alog.verify_chain() is False


def test_verify_chain_detects_an_inserted_entry(tmp_path):
    """A fabricated entry spliced into the middle is detected."""
    alog = AuditLogger(str(tmp_path))
    _seed(alog, 3)

    entries = _entries(alog)
    forged = {
        "event": "security_violation",
        "task": "task-forged",
        "rule": "rule-forged",
        "severity": "none",
        "action": "allow",
        "timestamp": entries[0]["timestamp"],
        "prev_hash": entries[0]["hash"],
        "hash": "0" * 64,
    }
    _rewrite(alog, [entries[0], forged] + entries[1:])

    assert alog.verify_chain() is False


def test_deleting_an_entry_by_disguising_it_as_junk_is_detected(tmp_path):
    """Overwriting an entry with unparseable junk still breaks the chain.

    Unparseable lines are dropped from the chain view. If the entry after
    the junk still links to the one before it, the removal is invisible and
    verify_chain() reports an intact log -- so replacing a real entry with
    garbage would be a tamper that deletes evidence for free.
    """
    alog = AuditLogger(str(tmp_path))
    _seed(alog, 3)

    lines = _raw_lines(alog)
    lines[1] = "not json at all\n"
    with open(alog.audit_file, "w", encoding="utf-8") as handle:
        handle.writelines(lines)

    assert alog.verify_chain() is False


def test_a_lone_garbage_line_at_the_tail_is_not_treated_as_tampering(tmp_path):
    """A crash-truncated last line is tolerated, per the documented policy.

    A write interrupted by a crash leaves a partial final line. Treating that
    as corruption would make the log report tampering after every unclean
    shutdown, which trains callers to ignore verify_chain() entirely.
    """
    alog = AuditLogger(str(tmp_path))
    _seed(alog, 3)

    with open(alog.audit_file, "a", encoding="utf-8") as handle:
        handle.write('{"event": "task_star')  # crash mid-write

    assert alog.verify_chain() is True
    assert len(alog.get_audit_trail()) == 3


def test_writing_after_a_truncated_tail_does_not_lose_the_entry(tmp_path):
    """The first append after a crash must start a fresh line and survive.

    The sink must not lose events silently: the caller has no way to learn
    that log_state_change() recorded nothing.
    """
    alog = AuditLogger(str(tmp_path))
    alog.log_state_change("a", "b")
    alog.log_state_change("b", "c")
    with open(alog.audit_file, "a", encoding="utf-8") as handle:
        handle.write('{"event": "task_star')

    alog.log_state_change("c", "d")

    trail = alog.get_audit_trail()
    assert [e["to_state"] for e in trail] == ["b", "c", "d"]
    assert alog.verify_chain() is True


def test_retention_with_a_truncated_tail_does_not_raise(tmp_path):
    """A crash fragment must not turn a retention pass into a hard failure.

    _write_entry appends before enforcing retention, so a truncated tail is
    already in the file by the time retention runs. Retention parses every
    retained line; parsing the fragment unguarded would raise
    JSONDecodeError out of the caller's write and lose the entry entirely.
    """
    alog = AuditLogger(str(tmp_path), max_entries=3)
    for value in ("a", "b", "c"):
        alog.log_state_change("state-change", value)
    with open(alog.audit_file, "a", encoding="utf-8") as handle:
        handle.write('{"event": "task_star')

    # This append forces a retention pass (4 entries > max_entries=3).
    alog.log_state_change("state-change", "later")

    trail = alog.get_audit_trail()
    # 4 parseable entries (a, b, c, later); the fragment is skipped, so
    # retention keeps the newest 3.
    assert [e["to_state"] for e in trail] == ["b", "c", "later"]
    assert alog.verify_chain() is True



# -- retention -------------------------------------------------------------

def test_retention_keeps_the_newest_entries_and_preserves_the_chain(tmp_path):
    """Trimming drops the oldest entries, keeps the newest, and rebases.

    Retention is only correct if the survivors still form a chain. Leaving
    the first survivor's prev_hash pointing at a dropped entry would make
    every trimmed log permanently report as tampered.
    """
    alog = AuditLogger(str(tmp_path), max_entries=3)
    _seed(alog, 6)

    entries = _entries(alog)
    assert [e["task"] for e in entries] == ["task-3", "task-4", "task-5"]
    assert entries[0]["prev_hash"] == "", "surviving chain must be rebased"
    for earlier, later in zip(entries, entries[1:]):
        assert later["prev_hash"] == earlier["hash"]
    assert alog.verify_chain() is True


def test_retention_keeps_appending_to_the_rebased_chain(tmp_path):
    """Trimming must not strand the next writer: new entries still link.

    The loop re-creates its AuditLogger on restart. If trimming left a
    dangling anchor, the first entry written afterwards would be
    permanently unverifiable.
    """
    alog = AuditLogger(str(tmp_path), max_entries=2)
    _seed(alog, 4)
    assert alog.verify_chain() is True

    reopened = AuditLogger(str(tmp_path), max_entries=2)
    reopened.log_state_change("running", "paused", reason="test")
    entries = _entries(reopened)

    assert len(entries) == 2
    assert entries[1]["prev_hash"] == entries[0]["hash"]
    assert entries[1]["event"] == "state_change"
    assert reopened.verify_chain() is True


def test_untrimmed_log_is_left_byte_identical(tmp_path):
    """Retention must not rewrite the file while it is within bounds.

    Rewriting on every write would drop the append-only guarantee and rewrite
    a log that needed no trimming, losing nothing yet gaining nothing.
    """
    alog = AuditLogger(str(tmp_path), max_entries=10)
    _seed(alog, 4)

    before = _entries(alog)
    alog.log_task_start("extra", {"type": "batch"})
    after = _entries(alog)[:4]

    assert after == before
    assert alog.verify_chain() is True


# -- field bounds ----------------------------------------------------------

@pytest.mark.parametrize("event,over,exact,field,limit", [
    ("task_start", 500, 100, "execution", 100),
    ("task_complete", 500, 200, "output", 200),
    ("task_failed", 500, 200, "error", 200),
])
def test_long_fields_are_bounded_at_the_limit(tmp_path, event, over, exact, field, limit):
    """Oversized text is truncated to exactly `limit`; at-limit text is whole.

    Asserting only "shorter than the input" would survive an off-by-one in
    the truncation slice, so both edges of each bound are pinned.
    """
    alog = AuditLogger(str(tmp_path))
    fill = {
        "task_start": lambda a, s: a.log_task_start("t", {"execution": "x" * s}),
        "task_complete": lambda a, s: a.log_task_complete("t", {"output": "x" * s}, 1.0),
        "task_failed": lambda a, s: a.log_task_failed("t", "x" * s, "handler"),
    }[event]

    fill(alog, over)
    entry = _entries(alog)[0]
    assert entry["event"] == event
    assert len(entry[field]) == limit

    exact_logger = AuditLogger(str(tmp_path / "exact"))
    fill(exact_logger, exact)
    at_limit = _entries(exact_logger)[0][field]
    assert len(at_limit) == limit
    assert at_limit == "x" * limit


# -- readers ---------------------------------------------------------------

def test_audit_trail_filters_by_task_name(tmp_path):
    """get_audit_trail returns only the named task's entries, all events."""
    alog = AuditLogger(str(tmp_path))
    alog.log_task_start("alpha", {"type": "batch"})
    alog.log_task_complete("alpha", {"success": True, "output": "done"}, 0.5)
    alog.log_task_start("beta", {"type": "batch"})

    assert len(alog.get_audit_trail()) == 3
    alpha = alog.get_audit_trail("alpha")
    assert [e["event"] for e in alpha] == ["task_start", "task_complete"]
    assert all(e["task"] == "alpha" for e in alpha)
    assert alog.get_audit_trail("nobody") == []


# -- sink failure isolation ------------------------------------------------

def test_unwritable_audit_sink_does_not_block_task_admission(tmp_path):
    """A failing audit write is swallowed; the task is still accepted.

    Real failure, not a mock: `audit.jsonl` is a directory, so every read and
    append on it raises OSError. The loop wraps audit calls defensively
    precisely so observability failure cannot become control flow.
    """
    from theteam.core.unified_loop import LoopConfig, UnifiedLoop

    log_dir = tmp_path / ".loop-log"
    log_dir.mkdir()
    (log_dir / "audit.jsonl").mkdir()  # appends to this path raise OSError

    loop = UnifiedLoop(str(tmp_path), LoopConfig(loop_id="audit-sink", project_root=str(tmp_path)))
    with pytest.raises(OSError):
        loop.audit.get_audit_trail()  # guard: the sink really is broken

    assert loop.start() is True, "a broken audit sink must not break start()"
    assert loop.add_task(UnifiedTask("task-1", "Work", lambda: None)) is True
    assert "task-1" in loop.tasks
    assert loop.tasks_started == 1
    assert loop.stop() is True


def test_audit_failure_does_not_mask_the_task_outcome(tmp_path):
    """A skipped line does not turn the sink into a permanent failure.

    Hand-edited or half-flushed lines must not stop the writer: an audit
    sink that raises forever is worse than one that loses a line.
    """
    alog = AuditLogger(str(tmp_path))
    _seed(alog, 2)
    with open(alog.audit_file, "a", encoding="utf-8") as handle:
        handle.write("{ truncated\n")

    alog.log_task_start("after-corruption", {"type": "unified_task"})

    trail = alog.get_audit_trail()
    assert [e["event"] for e in trail] == [
        "security_violation", "security_violation", "task_start",
    ]
    assert alog.verify_chain() is True


# -- checksum --------------------------------------------------------------

def test_compute_checksum_matches_sha256_and_reports_unreadable_files(tmp_path):
    """The integrity helper returns the real digest, and None when it cannot.

    Callers use this to detect file tampering, so a constant or truncated
    digest would silently defeat every integrity check built on it.
    """
    alog = AuditLogger(str(tmp_path))
    target = tmp_path / "artifact.bin"
    payload = b"\x00\xff binary payload \x01"
    target.write_bytes(payload)

    assert alog.compute_checksum(str(target)) == hashlib.sha256(payload).hexdigest()
    assert alog.compute_checksum(str(tmp_path / "absent.bin")) is None
