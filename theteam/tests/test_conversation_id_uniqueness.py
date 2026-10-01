"""Uniqueness of the conversation id `run_discussion` generates.

The id names BOTH the temp notes directory (`theteam-notes-<id>`) and the
written report filename. At second resolution two discussions started in the
same second produced the same id, so the second read the first's notes and
overwrote the first's report. Found by running the suite concurrently:
`run_discussion reported success but wrote no state`, with a synthesis file left
behind by a sibling process.

These tests call the production function `new_conversation_id`, not a copy of
its format string. A test that inlines the constant proves only that the
constant in the test file is unique — it stays green when production regresses
to seconds, which is exactly what a mutation check confirmed. `when` is
injectable so the clock is deterministic and no test sleeps.

`run_discussion` itself is not exercised. Calling it twice in rapid succession
needs a bound OMP provider, a bootstrapped project, a config and a state
manager, and even then two calls are separated by real wall-clock time, so they
cannot demonstrate a sub-second collision. The generator is the contract.
"""

from datetime import datetime, timedelta, timezone

from theteam import new_conversation_id

BASE = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_rapid_succession_ids_are_unique():
    """1000 ids one microsecond apart are all distinct.

    REVERTING-CHECK: with `'%Y%m%d_%H%M%S'` production this collapses to at
    most 2 unique ids across that span, so this assertion fails.
    """
    ids = [new_conversation_id(BASE + timedelta(microseconds=i)) for i in range(1000)]
    assert len(set(ids)) == 1000


def test_same_second_different_microsecond():
    """Two ids inside one wall-clock second differ."""
    early = new_conversation_id(BASE)
    late = new_conversation_id(BASE + timedelta(microseconds=999999))
    assert early != late


def test_second_boundary_is_distinct():
    """`:00.999999` and `:01.000000` are different ids."""
    before = new_conversation_id(BASE + timedelta(microseconds=999999))
    after = new_conversation_id(BASE + timedelta(seconds=1))
    assert before != after


def test_id_is_stable_for_a_fixed_instant():
    """The same instant yields the same id — uniqueness is per-microsecond, not random."""
    assert new_conversation_id(BASE) == new_conversation_id(BASE)


def test_caller_with_no_instant_gets_a_fresh_id():
    """The no-argument path production uses is microsecond-precise too.

    Two consecutive calls with no argument must differ; under second resolution
    they routinely would not, and that is the defect.
    """
    assert new_conversation_id() != new_conversation_id()