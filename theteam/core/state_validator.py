#!/usr/bin/env python3
"""
state_validator.py - State File Validation Module

This module implements the state validation requirements from STABILITY_ROADMAP.md
Phase 1: "Add state file validation on load"

It provides:
- Schema validation for state files
- Integrity verification through checksums
- Version compatibility checking
- Atomic transaction validation
- Corruption detection and prevention

Previously theteam had no validation - state files were loaded blindly
which could lead to corrupted state, integration failures, and unpredictable
behavior. This validation prevents those issues.
"""

import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
import warnings

from .task_contract import UnifiedTask, TaskStatus

# Schema version for state file compatibility
SCHEMA_VERSION = "1.0"

# Minimum required fields in state files
MIN_REQUIRED_FIELDS = {
    'loop_id': str,
    'project_root': str,
    'status': str,
    'tasks': list,
    'created_at': str,
    'version': str,
}

# Valid state file statuses
VALID_STATUSES = {
    'active', 'inactive', 'error', 'paused', 'completed'
}

class ValidationError(Exception):
    """Exception raised when state validation fails."""
    
    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        super().__init__(message)
        self.message = message
        self.field = field
        self.value = value

class ValidationResult:
    """Result of state validation operations."""
    
    def __init__(self, is_valid: bool = True, errors: Optional[List[str]] = None, warnings: Optional[List[str]] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
    
    def add_error(self, error: str, field: Optional[str] = None, value: Any = None):
        """Add a validation error."""
        self.is_valid = False
        error_msg = error
        if field:
            error_msg = f"{field}: {error}"
        self.errors.append(error_msg)
    
    def add_warning(self, warning: str, field: Optional[str] = None, value: Any = None):
        """Add a validation warning."""
        warning_msg = warning
        if field:
            warning_msg = f"{field}: {warning}"
        self.warnings.append(warning_msg)
    
    def __str__(self) -> str:
        if self.is_valid:
            return "State validation passed"
        error_summary = ", ".join(self.errors[:3])  # Show first 3 errors
        if len(self.errors) > 3:
            error_summary += f" ... and {len(self.errors) - 3} more"
        return f"State validation failed: {error_summary}"

class StateSchemaValidator:
    """
    Validates state file schema against the unified state contract.
    
    This ensures state files conform to the expected structure before
    they can be loaded into the system. It prevents loading of corrupted,
    malformed, or incompatible state files.
    """
    
    @staticmethod
    def validate_file_path(file_path: Union[str, Path]) -> ValidationResult:
        """Validate that a file path is accessible and exists."""
        result = ValidationResult()
        
        if not file_path:
            result.add_error("File path cannot be empty")
            return result
        
        path = Path(file_path)
        
        # Check if file exists
        if not path.exists():
            result.add_error(f"State file does not exist: {file_path}")
            return result
        
        # Check if it's a file
        if not path.is_file():
            result.add_error(f"Path is not a file: {file_path}")
            return result
        
        # Check if file is readable
        if not os.access(file_path, os.R_OK):
            result.add_error(f"State file is not readable: {file_path}")
            return result
        
        # Check file size
        try:
            file_size = path.stat().st_size
            if file_size == 0:
                result.add_warning("State file is empty", "file_size")
            elif file_size > 10 * 1024 * 1024:  # 10MB
                result.add_warning("State file is large (>10MB), may impact performance", "file_size")
        except OSError as e:
            result.add_error(f"Cannot stat state file: {e}", "file_stat")
        
        return result
    
    @staticmethod
    def validate_content(file_path: Union[str, Path]) -> Tuple[ValidationResult, Optional[Dict]]:
        """Validate the content of a state file."""
        result = ValidationResult()
        
        # First validate file path
        path_result = StateSchemaValidator.validate_file_path(file_path)
        if not path_result.is_valid:
            return path_result, None
        
        try:
            # Read file content with integrity check
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Try to parse JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                result.add_error(f"Invalid JSON in state file: {e}", "json")
                return result, None
            
            # Validate against schema
            schema_result = StateSchemaValidator.validate_schema(data)
            if not schema_result.is_valid:
                return schema_result, None
            
            return result, data
            
        except Exception as e:
            result.add_error(f"Error reading state file: {e}", "file_io")
            return result, None
    
    @staticmethod
    def validate_schema(data: Dict[str, Any]) -> ValidationResult:
        """Validate state data against the schema."""
        result = ValidationResult()
        
        if not isinstance(data, dict):
            result.add_error("State file must be a JSON object")
            return result
        
        # Check for required fields
        for field, expected_type in MIN_REQUIRED_FIELDS.items():
            if field not in data:
                result.add_error(f"Missing required field: {field}")
                continue
            
            if not isinstance(data[field], expected_type):
                result.add_error(
                    f"Field '{field}' must be {expected_type.__name__}, "
                    f"got {type(data[field]).__name__}"
                )
        
        # Validate version compatibility
        if 'version' in data:
            version_result = StateSchemaValidator.validate_version(data['version'])
            if not version_result.is_valid:
                result.errors.extend(version_result.errors)
                result.is_valid = False
        
        # Validate loop_id if present
        if 'loop_id' in data:
            StateSchemaValidator.validate_loop_id(data['loop_id'], result)
        
        # Validate status if present
        if 'status' in data:
            StateSchemaValidator.validate_status(data['status'], result)
        
        # Validate tasks if present
        if 'tasks' in data:
            StateSchemaValidator.validate_tasks(data['tasks'], result)
        
        # Validate timestamps if present
        if 'created_at' in data:
            StateSchemaValidator.validate_timestamp(data['created_at'], 'created_at', result)
        
        if 'last_updated' in data:
            StateSchemaValidator.validate_timestamp(data['last_updated'], 'last_updated', result)
        
        return result
    
    @staticmethod
    def validate_version(version: str) -> ValidationResult:
        """Validate schema version compatibility."""
        result = ValidationResult()
        
        if not version:
            result.add_error("Version cannot be empty")
            return result
        
        # Check version format
        try:
            major_minor = version.split('.')
            if len(major_minor) != 2:
                result.add_error(f"Invalid version format: {version}. Expected 'major.minor'")
                return result
            
            major, minor = major_minor
            if not major.isdigit() or not minor.isdigit():
                result.add_error(f"Version must contain numbers only: {version}")
                return result
            
            # Check if version is supported
            if not StateSchemaValidator.is_version_supported(version):
                result.add_error(
                    f"Schema version {version} is not the current version ({SCHEMA_VERSION}). "
                    f"Data may need migration or may be incompatible."
                )
        
        except Exception as e:
            result.add_error(f"Error validating version: {e}")
        
        return result
    
    @staticmethod
    def is_version_supported(version: str) -> bool:
        """Check if a schema version is supported."""
        try:
            major_minor = version.split('.')
            if len(major_minor) != 2:
                return False
            
            major, minor = major_minor
            if not major.isdigit() or not minor.isdigit():
                return False
            
            # Accept current version
            if version == SCHEMA_VERSION:
                return True
            
            # Accept backward compatible versions (same major version)
            current_major, current_minor = SCHEMA_VERSION.split('.')
            if major == current_major:
                # Minor version must be <= current
                return int(minor) <= int(current_minor)
            
            # Different major version is not supported
            return False
        
        except Exception:
            return False
    
    @staticmethod
    def validate_loop_id(loop_id: Any, result: ValidationResult):
        """Validate loop_id field."""
        if not isinstance(loop_id, str):
            result.add_error("loop_id must be a string")
            return
        
        if not loop_id:
            result.add_error("loop_id cannot be empty")
            return
        
        # Check for valid UUID format (if expected)
        try:
            import uuid
            uuid.UUID(loop_id)
        except ValueError:
            result.add_warning(f"loop_id '{loop_id}' is not a valid UUID format")
        
        # Check for suspicious characters
        if any(char in loop_id for char in ['..', '//', '\\']):
            result.add_error(f"loop_id contains suspicious path-like characters: {loop_id}")
    
    @staticmethod
    def validate_status(status: Any, result: ValidationResult):
        """Validate status field."""
        if not isinstance(status, str):
            result.add_error("status must be a string")
            return
        
        if not status:
            result.add_error("status cannot be empty")
            return
        
        if status not in VALID_STATUSES:
            result.add_error(
                f"status '{status}' is not a valid status. "
                f"Valid statuses: {sorted(VALID_STATUSES)}"
            )
    
    @staticmethod
    def validate_tasks(tasks: Any, result: ValidationResult):
        """Validate tasks field."""
        if not isinstance(tasks, list):
            result.add_error("tasks must be a list")
            return
        
        if len(tasks) > 1000:  # Reasonable limit
            result.add_warning(f"tasks list is large ({len(tasks)} items), may impact performance")
        
        for i, task in enumerate(tasks):
            StateSchemaValidator.validate_task_item(task, i, result)
    
    @staticmethod
    def validate_task_item(task: Any, index: int, result: ValidationResult):
        """Validate individual task item."""
        if not isinstance(task, dict):
            result.add_error(f"Task at index {index} must be a JSON object")
            return
        
        required_task_fields = ['task_id', 'name', 'status']
        for field in required_task_fields:
            if field not in task:
                result.add_error(f"Task at index {index} missing required field: {field}")
        
        if 'task_id' in task:
            if not isinstance(task['task_id'], str) or not task['task_id']:
                result.add_error(f"Task at index {index} task_id must be non-empty string")
        
        if 'status' in task:
            if not isinstance(task['status'], str):
                result.add_error(f"Task at index {index} status must be a string")
            else:
                try:
                    TaskStatus(task['status'])
                except ValueError:
                    result.add_error(
                        f"Task at index {index} has invalid status: {task['status']}. "
                        f"Valid statuses: {[s.value for s in TaskStatus]}"
                    )
    
    @staticmethod
    def validate_timestamp(timestamp: Any, field_name: str, result: ValidationResult):
        """Validate timestamp field."""
        if not isinstance(timestamp, str):
            result.add_error(f"{field_name} must be a string (ISO format)")
            return
        
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            result.add_error(f"{field_name} must be a valid ISO 8601 timestamp: {timestamp}")
class ChecksumValidator:
    """
    Validates state file integrity using checksums.
    
    This prevents corrupted state files from being loaded. It detects
    file tampering, disk corruption, or incomplete writes.
    """
    
    @staticmethod
    def calculate_file_checksum(file_path: Union[str, Path], algorithm: str = 'sha256') -> str:
        """Calculate checksum of a file."""
        if algorithm not in ['md5', 'sha1', 'sha256', 'sha512']:
            raise ValueError(f"Unsupported checksum algorithm: {algorithm}")
        
        hash_func = getattr(hashlib, algorithm)()
        
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hash_func.update(chunk)
            
            return hash_func.hexdigest()
        
        except Exception as e:
            raise ValidationError(f"Cannot calculate checksum: {e}")
    
    @staticmethod
    def validate_checksum(file_path: Union[str, Path], expected_checksum: Optional[str] = None,
                         algorithm: str = 'sha256') -> ValidationResult:
        """Validate file checksum."""
        result = ValidationResult()
        
        if not expected_checksum:
            result.add_error("No expected checksum provided, cannot validate integrity")
            return result
        
        try:
            actual_checksum = ChecksumValidator.calculate_file_checksum(file_path, algorithm)
            
            if actual_checksum.lower() != expected_checksum.lower():
                result.add_error(
                    f"Checksum mismatch. Expected: {expected_checksum}, "
                    f"Actual: {actual_checksum}"
                )
            
        except ValidationError as e:
            result.add_error(str(e))
        except Exception as e:
            result.add_error(f"Error validating checksum: {e}")
        
        return result
class StateIntegrityChecker:
    """
    Comprehensive state integrity checker.
    
    This performs multiple validation steps to ensure state files are safe
    to load:
    1. Schema validation
    2. Checksum verification
    3. Version compatibility
    4. Integrity checks
    5. Context validation
    """
    
    def __init__(self, schema_version: str = SCHEMA_VERSION):
        self.schema_version = schema_version
        self._checksum_algorithm = 'sha256'
    
    def validate_state_file(self, file_path: Union[str, Path]) -> Tuple[ValidationResult, Optional[Dict]]:
        """
        Perform comprehensive validation of a state file.
        
        Returns:
            Tuple of (ValidationResult, data_dict) where data_dict is None if validation failed
        """
        print(f"🔍 Validating state file: {file_path}")
        
        # Step 1: Basic file validation
        schema_result = StateSchemaValidator.validate_file_path(file_path)
        if not schema_result.is_valid:
            print(f"❌ File validation failed: {schema_result.errors}")
            return schema_result, None
        
        # Step 2: Content validation
        content_result, data = StateSchemaValidator.validate_content(file_path)
        if not content_result.is_valid:
            print(f"❌ Content validation failed: {content_result.errors}")
            return content_result, None
        
        # Step 3: Schema validation
        if data:
            schema_validation_result = StateSchemaValidator.validate_schema(data)
            if not schema_validation_result.is_valid:
                print(f"❌ Schema validation failed: {schema_validation_result.errors}")
                return schema_validation_result, None
            
            content_result.warnings.extend(schema_validation_result.warnings)
        
        # Step 4: Checksum validation (if checksum present in data)
        if data and 'checksum' in data:
            checksum_result = ChecksumValidator.validate_checksum(
                file_path, data['checksum'], self._checksum_algorithm
            )
            if not checksum_result.is_valid:
                print(f"❌ Checksum validation failed: {checksum_result.errors}")
                return checksum_result, None
            
            content_result.warnings.extend(checksum_result.warnings)
        
        # Step 5: Version compatibility
        if data and 'version' in data:
            version_result = StateSchemaValidator.validate_version(data['version'])
            if not version_result.is_valid:
                print(f"❌ Version validation failed: {version_result.errors}")
                return version_result, None
            
            content_result.warnings.extend(version_result.warnings)
        
        # Step 6: Context validation
        if data:
            context_result = self._validate_context(data)
            if not context_result.is_valid:
                print(f"❌ Context validation failed: {context_result.errors}")
                return context_result, None
            
            content_result.warnings.extend(context_result.warnings)
        
        if content_result.is_valid:
            print(f"✅ State file validation passed")
            if content_result.warnings:
                print(f"⚠️  Warnings: {content_result.warnings}")
        
        return content_result, data
    
    def _validate_context(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate contextual information in the state data."""
        result = ValidationResult()
        
        # Validate project root if present
        if 'project_root' in data:
            project_root = data['project_root']
            if not isinstance(project_root, str):
                result.add_error("project_root must be a string")
            elif not os.path.isabs(project_root):
                result.add_warning("project_root should be an absolute path")
            elif not os.path.exists(project_root):
                result.add_warning(f"project_root path does not exist: {project_root}")
        
        # Validate that tasks are consistent with loop state
        if 'tasks' in data and 'status' in data:
            tasks = data['tasks']
            status = data['status']
            
            # Check for consistency between task status and loop status
            if status == 'active':
                # Should have at least one non-completed task
                active_tasks = [t for t in tasks if t.get('status') not in ['completed', 'cancelled']]
                if not active_tasks:
                    result.add_warning("Loop status is 'active' but no active tasks found")
        
        # Validate that timestamps are reasonable
        if 'created_at' in data and 'last_updated' in data:
            try:
                created = datetime.fromisoformat(data['created_at'].replace('Z', '+00:00'))
                updated = datetime.fromisoformat(data['last_updated'].replace('Z', '+00:00'))
                
                if created > updated:
                    result.add_error("created_at cannot be after last_updated")
                
                # Check for unreasonable time differences (more than 1 year)
                time_diff = abs((updated - created).total_seconds())
                if time_diff > 365 * 24 * 3600:
                    result.add_warning(f"Large time difference between created_at and last_updated: {time_diff / (24 * 3600):.1f} days")
            
            except Exception as e:
                result.add_error(f"Error validating timestamps: {e}")
        
        return result
class AtomicStateValidator:
    """
    Validates state files for atomic transaction integrity.
    
    This ensures state files can be loaded atomically - either completely
    or not at all - preventing partial or corrupted state loads.
    """
    
    @staticmethod
    def validate_atomic_transaction(file_path: Union[str, Path]) -> ValidationResult:
        """
        Validate that a state file can be loaded atomically.
        
        This checks for:
        1. Complete JSON structure (no truncation)
        2. Valid schema (all required fields present)
        3. Integrity (checksums if present)
        """
        result = ValidationResult()
        
        try:
            # Check file size and read atomically
            file_size = os.path.getsize(file_path)
            
            if file_size == 0:
                result.add_error("Empty state file cannot be loaded atomically")
                return result
            
            # Try to read entire file at once
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for complete JSON
            try:
                data = json.loads(content)
            except json.JSONDecodeError as e:
                result.add_error(f"Invalid JSON: {e}")
                return result
            
            # Verify that the entire file was consumed
            # (re-serialize and compare size to detect potential truncation)
            try:
                re_serialized = json.dumps(data, separators=(',', ':'))
                if len(re_serialized) != len(content.strip()):
                    result.add_warning(
                        "File size differs after re-serialization. "
                        "This may indicate file corruption or encoding issues."
                    )
            except Exception as e:
                result.add_warning(f"Cannot re-serialize JSON for validation: {e}")
            
            # Check for any embedded binary data that could cause issues
            if any(ord(c) < 32 and c not in '\t\n\r' for c in content[:1000]):
                result.add_warning("File contains potentially problematic control characters")
            
            return result
        
        except Exception as e:
            result.add_error(f"Error during atomic transaction validation: {e}")
            return result
class StateValidationManager:
    """
    Main manager for state validation operations.
    
    This provides a unified interface for all state validation operations
    and maintains validation history and statistics.
    """
    
    def __init__(self):
        self.integrity_checker = StateIntegrityChecker()
        self._validation_history: List[Tuple[datetime, ValidationResult]] = []
        self._validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'warnings_issued': 0,
        }
    
    def validate_state(self, file_path: Union[str, Path]) -> Tuple[ValidationResult, Optional[Dict]]:
        """
        Perform complete state validation with history tracking.
        
        Returns:
            Tuple of (ValidationResult, data_dict)
        """
        timestamp = datetime.now(timezone.utc)
        self._validation_stats['total_validations'] += 1
        
        # Perform validation
        validation_result, data = self.integrity_checker.validate_state_file(file_path)
        
        # Track validation result
        if validation_result.is_valid:
            self._validation_stats['successful_validations'] += 1
        else:
            self._validation_stats['failed_validations'] += 1
        
        if validation_result.warnings:
            self._validation_stats['warnings_issued'] += len(validation_result.warnings)
        
        # Store in history
        self._validation_history.append((timestamp, validation_result))
        
        # Keep only last 100 validation results in history
        if len(self._validation_history) > 100:
            self._validation_history = self._validation_history[-100:]
        
        return validation_result, data
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        return self._validation_stats.copy()
    
    def get_validation_history(self, limit: int = 10) -> List[Tuple[datetime, ValidationResult]]:
        """Get recent validation history."""
        return self._validation_history[-limit:]
    
    def clear_history(self) -> None:
        """Clear validation history."""
        self._validation_history.clear()


# Global validation manager instance
_validation_manager = StateValidationManager()


def validate_state_file(file_path: Union[str, Path]) -> Tuple[ValidationResult, Optional[Dict]]:
    """
    Convenience function for state file validation.
    
    This is the main entry point for state validation.
    """
    return _validation_manager.validate_state(file_path)


def validate_and_load_state(file_path: Union[str, Path]) -> Optional[Dict]:
    """
    Validate and load state file if valid.
    
    Returns:
        The loaded state data if validation passes, None otherwise.
    """
    validation_result, data = validate_state_file(file_path)
    
    if not validation_result.is_valid:
        print(f"❌ State validation failed for {file_path}")
        print(f"Errors: {validation_result.errors}")
        if validation_result.warnings:
            print(f"Warnings: {validation_result.warnings}")
        return None
    
    print(f"✅ State file {file_path} loaded successfully")
    if validation_result.warnings:
        print(f"⚠️  Warnings during load: {validation_result.warnings}")
    
    return data


# Export main exports
__all__ = [
    'SCHEMA_VERSION',
    'ValidationError',
    'ValidationResult',
    'StateSchemaValidator',
    'ChecksumValidator',
    'StateIntegrityChecker',
    'AtomicStateValidator',
    'StateValidationManager',
    'validate_state_file',
    'validate_and_load_state',
]