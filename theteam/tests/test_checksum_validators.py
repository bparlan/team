"""Tests defending the two distinct checksum validators.

`theteam.core.checksum.DataChecksumValidator` hashes in-memory data and
RAISES `ChecksumError`. `theteam.core.state_validator.ChecksumValidator`
hashes files and returns a `ValidationResult`. They must not be conflated.
"""

import hashlib
import json

import pytest

from theteam.core.checksum import ChecksumAlgorithm, ChecksumError, DataChecksumValidator
from theteam.core.state_validator import ChecksumValidator, ValidationResult


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
# ---------------------------------------------------------------------------
# ChecksumValidator (state_validator.py) — files, returns ValidationResult
# ---------------------------------------------------------------------------

class TestStateChecksumValidator:
    @staticmethod
    def _write(tmp_path, name, payload):
        f = tmp_path / name
        f.write_bytes(payload)
        return f

    def test_calculate_file_checksum_matches_hashlib(self, tmp_path):
        payload = b"state file contents\n"
        f = self._write(tmp_path, "state.json", payload)
        assert ChecksumValidator.calculate_file_checksum(f) == hashlib.sha256(payload).hexdigest()

    def test_unsupported_algorithm_raises_value_error(self, tmp_path):
        f = self._write(tmp_path, "state.json", b"{}")
        with pytest.raises(ValueError):
            ChecksumValidator.calculate_file_checksum(f, algorithm="rot13")

    def test_validate_checksum_correct_returns_valid(self, tmp_path):
        payload = b'{"version": "1.0"}'
        f = self._write(tmp_path, "state.json", payload)
        expected = hashlib.sha256(payload).hexdigest()
        result = ChecksumValidator.validate_checksum(f, expected)
        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert result.errors == []

    def test_validate_checksum_wrong_returns_invalid_with_errors(self, tmp_path):
        payload = b'{"version": "1.0"}'
        f = self._write(tmp_path, "state.json", payload)
        result = ChecksumValidator.validate_checksum(f, "00" * 32)
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Checksum mismatch" in result.errors[0]

    def test_validate_checksum_missing_file_reports_not_raises(self, tmp_path):
        result = ChecksumValidator.validate_checksum(tmp_path / "missing.json", "abc")
        assert result.is_valid is False
        assert len(result.errors) > 0

    def test_validate_checksum_no_expected_reports_not_raises(self, tmp_path):
        f = self._write(tmp_path, "state.json", b"{}")
        result = ChecksumValidator.validate_checksum(f, None)
        assert result.is_valid is False
        assert len(result.errors) > 0


# ---------------------------------------------------------------------------
# Cross-cutting: the two classes are distinct and not interchangeable
# ---------------------------------------------------------------------------

class TestDistinctValidators:
    def test_classes_are_distinct_objects(self):
        assert DataChecksumValidator is not ChecksumValidator

    def test_class_names_differ(self):
        assert DataChecksumValidator.__name__ == "DataChecksumValidator"
        assert ChecksumValidator.__name__ == "ChecksumValidator"

    def test_data_validator_raises_while_state_returns(self, tmp_path):
        payload = b"corrupt"
        f = tmp_path / "state.json"
        f.write_bytes(payload)
        # DataChecksumValidator raises on a missing file
        with pytest.raises(ChecksumError):
            DataChecksumValidator().get_file_checksum(tmp_path / "missing.json")
        # ChecksumValidator returns a ValidationResult for the same scenario
        result = ChecksumValidator.validate_checksum(tmp_path / "missing.json", "abc")
        assert result.is_valid is False