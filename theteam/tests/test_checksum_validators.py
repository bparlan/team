"""Tests defending `theteam.core.checksum.DataChecksumValidator`.

It hashes in-memory data and a file path, and RAISES `ChecksumError` on
every failure. The second validator this file used to defend
(`theteam.core.state_validator.ChecksumValidator`, which returned a
`ValidationResult` instead of raising) was unreachable from production and was
deleted in M10, so the "these two must not be conflated" cases went with it.
"""

import hashlib
import json

import pytest

from theteam.core.checksum import ChecksumAlgorithm, ChecksumError, DataChecksumValidator

# ---------------------------------------------------------------------------
# DataChecksumValidator (checksum.py) — in-memory, raises on failure
# ---------------------------------------------------------------------------

class TestDataChecksumValidator:
    def setup_method(self):
        self.validator = DataChecksumValidator()

    def test_compute_checksum_is_order_independent(self):
        a = {"b": 2, "a": 1, "c": 3}
        b = {"a": 1, "c": 3, "b": 2}
        assert self.validator.compute_checksum(a) == self.validator.compute_checksum(b)

    def test_compute_checksum_equals_independent_hashlib(self):
        data = {"name": "task-1", "status": "active", "count": 42}
        canonical = json.dumps(data, sort_keys=True).encode()
        expected = hashlib.sha256(canonical).hexdigest()
        assert self.validator.compute_checksum(data) == expected

    def test_compute_checksum_str_and_bytes(self):
        # str and bytes paths both produce real hashes
        assert self.validator.compute_checksum("hello") == hashlib.sha256(b"hello").hexdigest()
        assert self.validator.compute_checksum(b"hello") == hashlib.sha256(b"hello").hexdigest()

    def test_compute_checksum_unsupported_algorithm_raises(self):
        with pytest.raises(ChecksumError):
            self.validator.compute_checksum({"x": 1}, algorithm="bogus")

    def test_get_file_checksum_matches_hashlib(self, tmp_path):
        # The real file digest, not a wrapped AttributeError: this path backs
        # verify_file_checksum, so a broken hash makes every file verification
        # raise instead of reporting.
        payload = b"the quick brown fox\n" * 100
        f = tmp_path / "state.bin"
        f.write_bytes(payload)
        assert self.validator.get_file_checksum(f) == hashlib.sha256(payload).hexdigest()

    def test_get_file_checksum_unsupported_algorithm_raises(self, tmp_path):
        # An unsupported algorithm must surface as this module's error type,
        # not a bare KeyError from the algorithm table lookup.
        f = tmp_path / "x.bin"
        f.write_bytes(b"data")
        with pytest.raises(ChecksumError):
            self.validator.get_file_checksum(f, algorithm="bogus")