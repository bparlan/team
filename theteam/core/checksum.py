#!/usr/bin/env python3
"""
Checksum implementation for theteam.

This module provides checksum functionality for state files,
ensuring data integrity and corruption detection.

NOTE: there are two checksum validators in the codebase and they are NOT
interchangeable:
  * `checksum.DataChecksumValidator` (here) hashes IN-MEMORY data - dicts,
    JSON, bytes - and raises `ChecksumError`. Algorithm-typed via the
    `ChecksumAlgorithm` enum. Used by `state_manager` for state payloads.
  * `state_validator.ChecksumValidator` hashes FILES and returns a
    `ValidationResult` rather than raising, so a corrupt file surfaces as a
    reportable error instead of an exception.

They previously shared the name `ChecksumValidator`, which made either import
look correct while returning an unrelated type. They were renamed, not merged:
their failure contracts (raise vs. return) are deliberately different.
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class ChecksumAlgorithm(str, Enum):
    """Supported checksum algorithms."""
    SHA256 = "sha256"
    SHA512 = "sha512"
    MD5 = "md5"
    SHA1 = "sha1"

    @classmethod
    def get_default(cls) -> 'ChecksumAlgorithm':
        """Get the default checksum algorithm."""
        return cls.SHA256
class ChecksumError(Exception):
    """Exception raised when checksum operations fail."""
    pass
class DataChecksumValidator:
    """
    Computes checksums for in-memory data (dicts, JSON, bytes).

    Distinct from `state_validator.ChecksumValidator`, which hashes files and
    returns a `ValidationResult`. This one RAISES `ChecksumError`; that one
    reports. Do not substitute one for the other.
    """

    def __init__(self):
        self.supported_algorithms = {
            ChecksumAlgorithm.SHA256: hashlib.sha256,
            ChecksumAlgorithm.SHA512: hashlib.sha512,
            ChecksumAlgorithm.MD5: hashlib.md5,
            ChecksumAlgorithm.SHA1: hashlib.sha1
        }

    def compute_checksum(self, data: Union[Dict[str, Any], str, bytes], 
                       algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256,
                       sort_keys: bool = True) -> str:
        """
        Compute checksum for data.

        Args:
            data: Data to checksum (dict will be serialized as JSON)
            algorithm: Checksum algorithm to use
            sort_keys: Whether to sort dict keys for deterministic checksum

        Returns:
            Checksum string
        """
        if algorithm not in self.supported_algorithms:
            raise ChecksumError(f"Unsupported algorithm: {algorithm}")

        hash_func = self.supported_algorithms[algorithm]

        # Convert data to bytes
        if isinstance(data, dict):
            data_str = json.dumps(data, sort_keys=sort_keys)
        elif isinstance(data, str):
            data_str = data
        elif isinstance(data, bytes):
            return hash_func(data).hexdigest()
        else:
            raise ChecksumError(f"Unsupported data type: {type(data)}")

        return hash_func(data_str.encode()).hexdigest()

    def verify_checksum(self, data: Union[Dict[str, Any], str, bytes],
                       checksum: str,
                       algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256,
                       sort_keys: bool = True) -> bool:
        """
        Verify checksum for data.

        Args:
            data: Data to verify
            checksum: Checksum to verify against
            algorithm: Checksum algorithm used
            sort_keys: Whether keys were sorted during checksum computation

        Returns:
            True if checksum matches
        """
        try:
            computed = self.compute_checksum(data, algorithm, sort_keys)
            return computed.lower() == checksum.lower()
        except Exception:
            return False

    def get_file_checksum(self, file_path: Union[str, Path],
                         algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> str:
        """
        Compute checksum for a file.

        Args:
            file_path: Path to file
            algorithm: Checksum algorithm to use

        Returns:
            Checksum string
        """
        file_path = Path(file_path)
        if algorithm not in self.supported_algorithms:
            # Surface an unsupported algorithm as this module's error type
            # rather than letting the dict lookup raise a bare KeyError.
            raise ChecksumError(f"Unsupported checksum algorithm: {algorithm}")
        # supported_algorithms maps to the hashlib CONSTRUCTOR, so it must be
        # instantiated before use. Assigning the constructor itself makes
        # .update() fail on every file.
        hash_func = self.supported_algorithms[algorithm]()

        try:
            with open(file_path, 'rb') as f:
                # Read file in chunks to handle large files
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_func.update(chunk)
            return hash_func.hexdigest()
        except OSError as e:
            raise ChecksumError(f"Error computing file checksum: {e}")

    def verify_file_checksum(self, file_path: Union[str, Path],
                           expected_checksum: str,
                           algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> bool:
        """
        Verify checksum for a file.

        Args:
            file_path: Path to file
            expected_checksum: Expected checksum
            algorithm: Checksum algorithm used

        Returns:
            True if checksum matches
        """
        try:
            computed = self.get_file_checksum(file_path, algorithm)
            return computed.lower() == expected_checksum.lower()
        except Exception:
            return False
class StateFileChecksumManager:
    """
    Manages checksums for state files with automatic validation.
    """

    def __init__(self, validator: Optional[DataChecksumValidator] = None):
        self.validator = validator or DataChecksumValidator()
        self.checksum_field = "checksum"
        self.algorithm_field = "checksum_algorithm"
        self.version_field = "version"

    def add_checksum(self, state_data: Dict[str, Any],
                    algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> Dict[str, Any]:
        """
        Add checksum to state data.

        Args:
            state_data: State data to checksum
            algorithm: Checksum algorithm to use

        Returns:
            State data with checksum added
        """
        # Create a copy to avoid modifying the original
        data_with_checksum = state_data.copy()

        # Compute checksum for the data
        checksum = self.validator.compute_checksum(state_data, algorithm)

        # Add checksum fields
        data_with_checksum[self.checksum_field] = checksum
        data_with_checksum[self.algorithm_field] = algorithm.value

        # Add timestamp
        data_with_checksum['checksum_timestamp'] = datetime.now(timezone.utc).isoformat()

        return data_with_checksum

    def verify_state_file(self, file_path: Union[str, Path]) -> Tuple[bool, List[str]]:
        """
        Verify checksum of a state file.

        Args:
            file_path: Path to state file

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        try:
            # Load the state file
            with open(file_path, 'r') as f:
                state_data = json.load(f)

            # Check if checksum fields exist
            if self.checksum_field not in state_data:
                errors.append(f"Missing checksum field '{self.checksum_field}'")
                return False, errors

            if self.algorithm_field not in state_data:
                errors.append(f"Missing checksum algorithm field '{self.algorithm_field}'")
                return False, errors

            # Get algorithm and checksum
            algorithm_str = state_data[self.algorithm_field]
            try:
                algorithm = ChecksumAlgorithm(algorithm_str)
            except ValueError:
                errors.append(f"Invalid checksum algorithm: {algorithm_str}")
                return False, errors

            expected_checksum = state_data[self.checksum_field]

            # Remove checksum fields from data for verification
            verification_data = {k: v for k, v in state_data.items() 
                               if k not in [self.checksum_field, self.algorithm_field, 'checksum_timestamp']}

            # Verify checksum
            if not self.validator.verify_checksum(verification_data, expected_checksum, algorithm):
                errors.append(f"Checksum verification failed for {file_path}")

        except json.JSONDecodeError as e:
            errors.append(f"Invalid JSON in state file: {e}")
        except Exception as e:
            errors.append(f"Error verifying state file: {e}")

        return len(errors) == 0, errors

    def verify_state_data(self, state_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Verify checksum of state data.

        Args:
            state_data: State data to verify

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check if checksum fields exist
        if self.checksum_field not in state_data:
            errors.append(f"Missing checksum field '{self.checksum_field}'")
            return False, errors

        if self.algorithm_field not in state_data:
            errors.append(f"Missing checksum algorithm field '{self.algorithm_field}'")
            return False, errors

        # Get algorithm and checksum
        algorithm_str = state_data[self.algorithm_field]
        try:
            algorithm = ChecksumAlgorithm(algorithm_str)
        except ValueError:
            errors.append(f"Invalid checksum algorithm: {algorithm_str}")
            return False, errors

        expected_checksum = state_data[self.checksum_field]

        # Remove checksum fields from data for verification
        verification_data = {k: v for k, v in state_data.items() 
                           if k not in [self.checksum_field, self.algorithm_field, 'checksum_timestamp']}

        # Verify checksum
        if not self.validator.verify_checksum(verification_data, expected_checksum, algorithm):
            errors.append("Checksum verification failed for state data")

        return len(errors) == 0, errors

    def rebuild_checksum(self, file_path: Union[str, Path],
                        algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> Dict[str, Any]:
        """
        Rebuild checksum for a state file.

        Args:
            file_path: Path to state file
            algorithm: Checksum algorithm to use

        Returns:
            Updated state data with new checksum
        """
        try:
            # Load the state file
            with open(file_path, 'r') as f:
                state_data = json.load(f)

            # Remove existing checksum fields
            for field in [self.checksum_field, self.algorithm_field, 'checksum_timestamp']:
                if field in state_data:
                    del state_data[field]

            # Add new checksum
            updated_data = self.add_checksum(state_data, algorithm)

            # Write back to file
            with open(file_path, 'w') as f:
                json.dump(updated_data, f, indent=2)

            logger.info(f"Checksum rebuilt for {file_path}")
            return updated_data

        except Exception as e:
            raise ChecksumError(f"Error rebuilding checksum: {e}")
class IntegrityChecker:
    """
    Checks integrity of state files and data structures.
    """

    def __init__(self, checksum_manager: Optional[StateFileChecksumManager] = None):
        self.checksum_manager = checksum_manager or StateFileChecksumManager()

    def check_file_integrity(self, file_path: Union[str, Path]) -> Tuple[bool, List[str]]:
        """
        Check integrity of a state file.

        Args:
            file_path: Path to state file

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check if file exists
        if not Path(file_path).exists():
            errors.append(f"File not found: {file_path}")
            return False, errors

        # Check checksum
        is_valid, checksum_errors = self.checksum_manager.verify_state_file(file_path)
        if not is_valid:
            errors.extend(checksum_errors)

        # TODO: Add more integrity checks (schema validation, etc.)

        return len(errors) == 0, errors

    def check_data_integrity(self, state_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Check integrity of state data.

        Args:
            state_data: State data to check

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check required fields
        required_fields = ['version', 'timestamp']
        for field in required_fields:
            if field not in state_data:
                errors.append(f"Missing required field: {field}")

        # Check checksum
        is_valid, checksum_errors = self.checksum_manager.verify_state_data(state_data)
        if not is_valid:
            errors.extend(checksum_errors)

        return len(errors) == 0, errors

    def validate_state_structure(self, state_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate the structure of state data.

        Args:
            state_data: State data to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check top-level structure
        expected_keys = ['version', 'timestamp', 'discussion_state', 
                        'system_awareness_state', 'task_state']
        for key in expected_keys:
            if key not in state_data:
                errors.append(f"Missing top-level key: {key}")

        # Check nested structures
        if 'discussion_state' in state_data:
            if not isinstance(state_data['discussion_state'], dict):
                errors.append("discussion_state must be a dict")

        if 'system_awareness_state' in state_data:
            if not isinstance(state_data['system_awareness_state'], dict):
                errors.append("system_awareness_state must be a dict")

        if 'task_state' in state_data:
            if not isinstance(state_data['task_state'], dict):
                errors.append("task_state must be a dict")

        return len(errors) == 0, errors
class ChecksumManager:
    """
    Main checksum manager that coordinates all checksum operations.
    """

    def __init__(self):
        self.validator = DataChecksumValidator()
        self.checksum_manager = StateFileChecksumManager(self.validator)
        self.integrity_checker = IntegrityChecker(self.checksum_manager)

    def compute_checksum(self, data: Any, algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> str:
        """Compute checksum for data."""
        return self.validator.compute_checksum(data, algorithm)

    def verify_state_file(self, file_path: Union[str, Path]) -> Tuple[bool, List[str]]:
        """Verify checksum of a state file."""
        return self.checksum_manager.verify_state_file(file_path)

    def verify_state_data(self, state_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Verify checksum of state data."""
        return self.checksum_manager.verify_state_data(state_data)

    def add_checksum_to_state(self, state_data: Dict[str, Any],
                            algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> Dict[str, Any]:
        """Add checksum to state data."""
        return self.checksum_manager.add_checksum(state_data, algorithm)

    def rebuild_file_checksum(self, file_path: Union[str, Path],
                            algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> Dict[str, Any]:
        """Rebuild checksum for a state file."""
        return self.checksum_manager.rebuild_checksum(file_path, algorithm)

    def check_file_integrity(self, file_path: Union[str, Path]) -> Tuple[bool, List[str]]:
        """Check integrity of a state file."""
        return self.integrity_checker.check_file_integrity(file_path)

    def check_data_integrity(self, state_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Check integrity of state data."""
        return self.integrity_checker.check_data_integrity(state_data)

    def validate_state_structure(self, state_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate the structure of state data."""
        return self.integrity_checker.validate_state_structure(state_data)

    def get_supported_algorithms(self) -> List[str]:
        """Get list of supported checksum algorithms."""
        return [algorithm.value for algorithm in ChecksumAlgorithm]

    def compute_file_checksum(self, file_path: Union[str, Path],
                            algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> str:
        """Compute checksum for a file."""
        return self.validator.get_file_checksum(file_path, algorithm)

    def verify_file_checksum(self, file_path: Union[str, Path],
                           expected_checksum: str,
                           algorithm: ChecksumAlgorithm = ChecksumAlgorithm.SHA256) -> bool:
        """Verify checksum for a file."""
        return self.validator.verify_file_checksum(file_path, expected_checksum, algorithm)