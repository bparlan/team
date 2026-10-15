"""
The execution log is bounded, and the bound drops the oldest lines.

`RoutineExecutor.log_execution` is an append-only JSONL file that `theteam
history` reads. Before M4 it had no cap at all and grew to 282 KB with
nothing enforcing a limit, so the log is now trimmed on every write. A trim
is the one kind of edit that can quietly lose data while still looking
correct: keep the wrong end and `history` reports yesterday's runs as if they
were the latest, and a trim that cuts mid-line leaves a file the reader can no
longer parse. Those two defects are invisible in a "the file exists" test, so
the promises pinned here are content-level:

  * under the cap nothing is dropped - a trim that fires early is silent data
    loss, not a smaller log;
  * over the cap the file is exactly `EXECUTION_LOG_MAX_LINES` lines;
  * the survivors are the NEWEST lines, in their original relative order;
  * every survivor still parses as JSON, including payloads whose string
    values contain a newline.

The cap is read from the module, never hardcoded, so retuning it does not
break this file - but it is asserted to be a positive int, because a cap of 0
(or a negative one used as a slice bound) turns "bounded" into "empty" and
would otherwise pass every count-based assertion.
"""

import json

from theteam.routines.executor import EXECUTION_LOG_MAX_LINES, RoutineExecutor


# ======= scratch project =======


def _executor(root):
    """An executor over a scratch project root; the state dir resolves under it."""
    return RoutineExecutor(str(root))


def _log_path(executor):
    return executor.execution_log


def _seed(executor, payloads):
    """
    Write entries straight into the log, as if earlier runs had appended them.

    Overflow is setup, not the thing under test: seeding is what lets a single
    real `log_execution` call cross the cap without a thousand writes per test.
    The append + trim path under test is still the production one.
    """
    path = _log_path(executor)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for payload in payloads:
            handle.write(json.dumps(payload) + "\n")


def _read(executor):
    """The log's raw lines, newlines intact."""
    return _log_path(executor).read_text(encoding="utf-8").splitlines()


def _payloads(executor):
    return [json.loads(line) for line in _read(executor)]


# ======= 1. the cap is a usable bound =======


def test_the_cap_is_a_positive_int():
    """
    `EXECUTION_LOG_MAX_LINES` bounds the log, so a non-positive cap is not a
    tight bound - it is an empty log, and `lines[-0:]` silently keeps
    everything while `lines[:-1]` drops the newest entry. The line count alone
    cannot tell those apart from a healthy log.
    """
    assert isinstance(EXECUTION_LOG_MAX_LINES, int)
    assert not isinstance(EXECUTION_LOG_MAX_LINES, bool)
    assert EXECUTION_LOG_MAX_LINES > 0


# ======= 2. a first write creates the log =======


def test_a_first_write_creates_the_log_and_its_state_directory(tmp_path):
    """
    The very first execution in a fresh project has no log and no state
    directory. If the write does not create both, the run it records is lost
    before anything can read it back.
    """
    executor = _executor(tmp_path)
    assert not _log_path(executor).parent.exists()

    executor.log_execution({"n": 0, "task_id": "t"})

    assert _payloads(executor) == [{"n": 0, "task_id": "t"}]


# ======= 3. under the cap nothing is dropped =======


def test_every_entry_written_under_the_cap_survives(tmp_path):
    """
    `cap - 1` writes must leave `cap - 1` entries. A trim whose comparison is
    off by one (or that fires on `<` instead of `<=`) loses the last entry
    while the file still looks about the right size.
    """
    cap = EXECUTION_LOG_MAX_LINES
    executor = _executor(tmp_path)
    written = [{"n": i, "task_id": "t"} for i in range(cap - 1)]

    for payload in written:
        executor.log_execution(payload)

    assert _payloads(executor) == written


def test_writing_exactly_the_cap_leaves_the_cap(tmp_path):
    """
    The cap is inclusive: an entry that fills the log to exactly the bound is
    not yet overflow. Trimming at `>=` drops a line the moment the log is
    full, so the file never holds the number of entries it is allowed to.
    """
    cap = EXECUTION_LOG_MAX_LINES
    executor = _executor(tmp_path)
    written = [{"n": i, "task_id": "t"} for i in range(cap)]

    for payload in written:
        executor.log_execution(payload)

    assert _payloads(executor) == written


# ======= 4. over the cap the file is exactly the cap =======


def test_one_write_past_the_cap_leaves_exactly_the_cap_lines(tmp_path):
    """
    The whole point of the bound: an append that crosses the cap leaves a file
    of exactly the cap, not cap+1 (trim never ran) and not cap-1 (off by one).
    """
    cap = EXECUTION_LOG_MAX_LINES
    executor = _executor(tmp_path)
    _seed(executor, [{"n": i, "task_id": "t"} for i in range(cap + 5)])

    executor.log_execution({"n": "new", "task_id": "t"})

    assert len(_read(executor)) == cap


# ======= 5. the survivors are the newest =======


def test_the_newest_entries_are_the_ones_kept(tmp_path):
    """
    The assertion that catches a trim from the wrong end. Trimming the oldest
    line produces a file of the right length whose contents are stale, and
    `history` would report the first runs ever recorded as the latest state.
    So: the first surviving entry is the one that sat just past the cap
    before the append, the appended entry is last, and everything earlier than
    the first survivor is gone.
    """
    cap = EXECUTION_LOG_MAX_LINES
    overflow = 5
    executor = _executor(tmp_path)
    _seed(executor, [{"n": i, "task_id": "t"} for i in range(cap + overflow)])

    executor.log_execution({"n": "new", "task_id": "t"})

    kept = _payloads(executor)
    assert kept[0] == {"n": overflow + 1, "task_id": "t"}
    assert kept[-1] == {"n": "new", "task_id": "t"}
    assert [p["n"] for p in kept[:-1]] == list(range(overflow + 1, cap + overflow))


def test_repeated_writes_past_the_cap_converge_and_stay_bounded(tmp_path):
    """
    Appending at the cap over and over must not ratchet the file upward: each
    write converges back to exactly the cap, and the tail is the newest run.
    A trim applied only on the first overflow, or one that keeps re-trimming
    an already-trimmed file, shows up here as a growing line count.
    """
    cap = EXECUTION_LOG_MAX_LINES
    executor = _executor(tmp_path)
    _seed(executor, [{"n": i, "task_id": "t"} for i in range(cap)])

    for round_ in range(3):
        executor.log_execution({"n": f"live-{round_}", "task_id": "t"})
        assert len(_read(executor)) == cap, f"round {round_}"

    kept = _payloads(executor)
    assert [p["n"] for p in kept[-3:]] == ["live-0", "live-1", "live-2"]


# ======= 6. survivors stay parseable =======


def test_every_surviving_line_still_parses_as_json(tmp_path):
    """
    A trim that cuts mid-line leaves a half-written record the reader cannot
    load, so every survivor has to round-trip through the parser. The
    survivor here carries a newline and a carriage return inside a string
    value: legal JSON only while escaped, and one physical line. A trim that
    splits on raw newlines instead of keeping whole lines would break this
    entry in half while the line count still looked right.
    """
    cap = EXECUTION_LOG_MAX_LINES
    executor = _executor(tmp_path)
    awkward = {
        "n": "awkward",
        "task_id": "t",
        "stdout": "first line\nsecond line\r\nthird",
        "unicode": "ünïcødé ✓",
    }
    _seed(
        executor,
        [{"n": i, "task_id": "t"} for i in range(cap + 5)]
        + [awkward],
    )

    executor.log_execution({"n": "new", "task_id": "t"})

    lines = _read(executor)
    assert len(lines) == cap
    # The awkward record is the newest seeded entry, so the trim must have
    # kept it whole rather than slicing into it.
    assert json.loads(lines[-2]) == awkward
    for line in lines:
        json.loads(line)


def test_a_dropped_entry_leaves_nothing_of_itself_in_the_survivors(tmp_path):
    """
    A trim on bytes or characters instead of whole lines leaves the tail of
    the evicted record as the head of its successor. The evicted record here
    is long and distinctive, so a fragment of it appearing at the start of
    the first survivor is caught by content, not by a count that still
    reads the cap.
    """
    cap = EXECUTION_LOG_MAX_LINES
    executor = _executor(tmp_path)
    evicted = {"n": 0, "task_id": "t", "stdout": "EVICTEDTAIL" + "x" * 20000}
    first_survivor = {"n": 1, "task_id": "t", "stdout": "keep me"}
    _seed(
        executor,
        [evicted, first_survivor] + [{"n": i, "task_id": "t"} for i in range(2, cap)],
    )

    executor.log_execution({"n": "new", "task_id": "t"})

    survivors = _payloads(executor)
    assert survivors[0] == first_survivor
    assert all("EVICTEDTAIL" not in str(p) for p in survivors)
