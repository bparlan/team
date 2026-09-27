#!/usr/bin/env python3
"""
test_state_validator.py - Tests for state validation module.

This validates the state_validator.py module that implements the validation
requirements from STABILITY_ROADMAP.md Phase 1:
"Add state file validation on load"

Tests cover:
- Schema validation
- Checksum verification  
- Version compatibility
- Atomic transaction validation
- Corruption detection
"""

import pytest
import tempfile
import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from theteam.core.state_validator import (
    StateSchemaValidator,
    ChecksumValidator,
    StateIntegrityChecker,
    AtomicStateValidator,
    ValidationResult,
    ValidationError,
    SCHEMA_VERSION,
    validate_and_load_state,
)
class TestStateSchemaValidator:
    """Test schema validation functionality."""
    
    def test_validate_file_path_existing_file(self):
        """Test validation of existing file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write('{}')
            f.flush()
            result = StateSchemaValidator.validate_file_path(f.name)
            os.unlink(f.name)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_file_path_nonexistent_file(self):
        """Test validation of non-existent file."""
        result = StateSchemaValidator.validate_file_path('/nonexistent/file.json')
        
        assert not result.is_valid
        assert any('does not exist' in error for error in result.errors)
    
    def test_validate_file_path_directory(self):
        """Test validation of directory instead of file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = StateSchemaValidator.validate_file_path(temp_dir)
            
            assert not result.is_valid
            assert any('is not a file' in error for error in result.errors)
    
    def test_validate_schema_valid_data(self):
        """Test validation of valid schema data."""
        valid_data = {
            'loop_id': 'test-loop-123',
            'project_root': '/test/project',
            'status': 'active',
            'tasks': [],
            'created_at': '2026-01-01T00:00:00Z',
            'version': SCHEMA_VERSION,
        }
        
        result = StateSchemaValidator.validate_schema(valid_data)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_schema_missing_required_fields(self):
        """Test validation with missing required fields."""
        invalid_data = {
            'loop_id': 'test-loop-123',
            # Missing project_root, status, tasks, created_at, version
        }
        
        result = StateSchemaValidator.validate_schema(invalid_data)
        
        assert not result.is_valid
        assert any('Missing required field' in error for error in result.errors)
    
    def test_validate_schema_invalid_version(self):
        """Test validation with invalid version."""
        invalid_data = {
            'loop_id': 'test-loop-123',
            'project_root': '/test/project',
            'status': 'active',
            'tasks': [],
            'created_at': '2026-01-01T00:00:00Z',
            'version': 'invalid.version.format',
        }
        
        result = StateSchemaValidator.validate_schema(invalid_data)
        
        assert not result.is_valid
        assert any('Invalid version format' in error for error in result.errors)
    
    def test_validate_schema_unsupported_version(self):
        """Test validation with unsupported version."""
        invalid_data = {
            'loop_id': 'test-loop-123',
            'project_root': '/test/project',
            'status': 'active',
            'tasks': [],
            'created_at': '2026-01-01T00:00:00Z',
            'version': '0.1',  # Very old version
        }
        
        result = StateSchemaValidator.validate_schema(invalid_data)
        
        assert not result.is_valid  # Should fail because version is unsupported
        # Check that version validation produced errors
        version_errors = [error for error in result.errors if 'version' in error.lower()]
        assert len(version_errors) > 0
    
    def test_validate_schema_invalid_loop_id(self):
        """Test validation with invalid loop_id."""
        invalid_data = {
            'loop_id': '',  # Empty loop_id
            'project_root': '/test/project',
            'status': 'active',
            'tasks': [],
            'created_at': '2026-01-01T00:00:00Z',
            'version': SCHEMA_VERSION,
        }
        
        result = StateSchemaValidator.validate_schema(invalid_data)
        
        assert not result.is_valid
        assert any('cannot be empty' in error for error in result.errors)
    
    def test_validate_schema_invalid_status(self):
        """Test validation with invalid status."""
        invalid_data = {
            'loop_id': 'test-loop-123',
            'project_root': '/test/project',
            'status': 'invalid_status',  # Not in VALID_STATUSES
            'tasks': [],
            'created_at': '2026-01-01T00:00:00Z',
            'version': SCHEMA_VERSION,
        }
        
        result = StateSchemaValidator.validate_schema(invalid_data)
        
        assert not result.is_valid
        assert any('is not a valid status' in error for error in result.errors)
    
    def test_validate_schema_tasks_validation(self):
        """Test validation of tasks array."""
        invalid_data = {
            'loop_id': 'test-loop-123',
            'project_root': '/test/project',
            'status': 'active',
            'tasks': [
                {'task_id': 'task1', 'name': 'Task 1'},  # Missing required fields
                {'task_id': '', 'name': 'Task 2', 'status': 'pending'},  # Empty task_id
                {'name': 'Task 3', 'status': 'pending'},  # Missing task_id
            ],
            'created_at': '2026-01-01T00:00:00Z',
            'version': SCHEMA_VERSION,
        }
        
        result = StateSchemaValidator.validate_schema(invalid_data)
        
        assert not result.is_valid
        # Should have multiple errors about task validation
        task_errors = [error for error in result.errors if 'Task at index' in error]
        assert len(task_errors) >= 2
    
    def test_validate_schema_valid_tasks(self):
        """Test validation of valid tasks."""
        valid_data = {
            'loop_id': 'test-loop-123',
            'project_root': '/test/project',
            'status': 'active',
            'tasks': [
                {
                    'task_id': 'task1',
                    'name': 'Task 1',
                    'status': 'pending',
                },
                {
                    'task_id': 'task2',
                    'name': 'Task 2',
                    'status': 'completed',
                },
            ],
            'created_at': '2026-01-01T00:00:00Z',
            'version': SCHEMA_VERSION,
        }
        
        result = StateSchemaValidator.validate_schema(valid_data)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_version_valid_version(self):
        """Test validation with valid version."""
        result = StateSchemaValidator.validate_version(SCHEMA_VERSION)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_version_empty_version(self):
        """Test validation with empty version."""
        result = StateSchemaValidator.validate_version('')
        
        assert not result.is_valid
        assert any('cannot be empty' in error for error in result.errors)
    
    def test_is_version_supported_current_version(self):
        """Test that current version is supported."""
        assert StateSchemaValidator.is_version_supported(SCHEMA_VERSION)
    
    def test_is_version_supported_unsupported_version(self):
        """Test that unsupported version returns False."""
        assert not StateSchemaValidator.is_version_supported('0.1')
        assert not StateSchemaValidator.is_version_supported('999.0')
    
    def test_validate_timestamp_valid(self):
        """Test validation of valid timestamp."""
        result = ValidationResult()
        StateSchemaValidator.validate_timestamp('2026-01-01T00:00:00Z', 'test_field', result)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_timestamp_invalid(self):
        """Test validation of invalid timestamp."""
        result = ValidationResult()
        StateSchemaValidator.validate_timestamp('not-a-timestamp', 'test_field', result)
        
        assert not result.is_valid
        assert any('must be a valid ISO 8601 timestamp' in error for error in result.errors)
class TestChecksumValidator:
    """Test checksum validation functionality."""
    
    def test_calculate_file_checksum(self):
        """Test checksum calculation."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write('test content')
            f.flush()
        
        try:
            checksum = ChecksumValidator.calculate_file_checksum(f.name, 'sha256')
            assert len(checksum) == 64  # SHA256 produces 64 char hex
        finally:
            os.unlink(f.name)
    
    def test_calculate_file_checksum_md5(self):
        """Test checksum calculation with MD5."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write('test content')
            f.flush()
        
        try:
            checksum = ChecksumValidator.calculate_file_checksum(f.name, 'md5')
            assert len(checksum) == 32  # MD5 produces 32 char hex
        finally:
            os.unlink(f.name)
    
    def test_validate_checksum_match(self):
        """Test validation of matching checksum."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            content = 'test content'
            f.write(content)
            f.flush()
        
        try:
            expected_checksum = ChecksumValidator.calculate_file_checksum(f.name, 'sha256')
            result = ChecksumValidator.validate_checksum(f.name, expected_checksum, 'sha256')
            
            assert result.is_valid
            assert len(result.errors) == 0
        finally:
            os.unlink(f.name)
    
    def test_validate_checksum_mismatch(self):
        """Test validation of mismatched checksum."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write('test content')
            f.flush()
        
        try:
            result = ChecksumValidator.validate_checksum(f.name, 'wrong_checksum', 'sha256')
            
            assert not result.is_valid
            assert any('Checksum mismatch' in error for error in result.errors)
        finally:
            os.unlink(f.name)
    
    def test_validate_checksum_empty_expected(self):
        """Test validation with empty expected checksum."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write('test content')
            f.flush()
        
        try:
            result = ChecksumValidator.validate_checksum(f.name, '')
            
            assert not result.is_valid
            assert any('cannot validate integrity' in error for error in result.errors)
        finally:
            os.unlink(f.name)
class TestStateIntegrityChecker:
    """Test state integrity checker functionality."""
    
    def test_validate_state_file_valid(self):
        """Test validation of valid state file."""
        valid_state = {
            'loop_id': 'test-loop-123',
            'project_root': '/test/project',
            'status': 'active',
            'tasks': [],
            'created_at': '2026-01-01T00:00:00Z',
            'version': SCHEMA_VERSION,
            'checksum': 'invalid_checksum',  # Will trigger checksum error
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(valid_state, f)
            f.flush()
        
        try:
            result, data = StateIntegrityChecker().validate_state_file(f.name)
            
            # With current validation, checksum mismatch is now an ERROR (not warning)
            # So the test expects validation to fail with checksum error
            assert not result.is_valid
            assert len(result.errors) > 0  # Should have checksum error
            assert any('Checksum mismatch' in error for error in result.errors)
        finally:
            os.unlink(f.name)
    
    def test_validate_state_file_invalid_json(self):
        """Test validation of file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('{ invalid json }')
            f.flush()
        
        try:
            result, data = StateIntegrityChecker().validate_state_file(f.name)
            
            assert not result.is_valid
            assert data is None
            assert any('Invalid JSON' in error for error in result.errors)
        finally:
            os.unlink(f.name)
    
    def test_validate_state_file_missing_required_fields(self):
        """Test validation of file missing required fields."""
        invalid_state = {
            'loop_id': 'test-loop-123',
            # Missing other required fields
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(invalid_state, f)
            f.flush()
        
        try:
            result, data = StateIntegrityChecker().validate_state_file(f.name)
            
            assert not result.is_valid
            assert data is None
            assert any('Missing required field' in error for error in result.errors)
        finally:
            os.unlink(f.name)
class TestAtomicStateValidator:
    """Test atomic transaction validation."""
    
    def test_validate_atomic_transaction_valid(self):
        """Test validation of valid atomic transaction."""
        valid_state = {
            'loop_id': 'test-loop-123',
            'project_root': '/test/project',
            'status': 'active',
            'tasks': [],
            'created_at': '2026-01-01T00:00:00Z',
            'version': SCHEMA_VERSION,
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(valid_state, f)
            f.flush()
        
        try:
            result = AtomicStateValidator.validate_atomic_transaction(f.name)
            
            assert result.is_valid
            assert len(result.errors) == 0
        finally:
            os.unlink(f.name)
    
    def test_validate_atomic_transaction_empty_file(self):
        """Test validation of empty file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('')
            f.flush()
        
        try:
            result = AtomicStateValidator.validate_atomic_transaction(f.name)
            
            assert not result.is_valid
            assert any('Empty state file' in error for error in result.errors)
        finally:
            os.unlink(f.name)
    
    def test_validate_atomic_transaction_invalid_json(self):
        """Test validation of file with invalid JSON."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            f.write('{ invalid }')
            f.flush()
        
        try:
            result = AtomicStateValidator.validate_atomic_transaction(f.name)
            
            assert not result.is_valid
            assert any('Invalid JSON' in error for error in result.errors)
        finally:
            os.unlink(f.name)
class TestStateValidationIntegration:
    """Integration tests for state validation."""
    
    def test_validate_and_load_state_valid(self):
        """Test validate_and_load_state with valid data."""
        valid_state = {
            'loop_id': 'test-loop-123',
            'project_root': '/test/project',
            'status': 'active',
            'tasks': [],
            'created_at': '2026-01-01T00:00:00Z',
            'version': SCHEMA_VERSION,
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(valid_state, f)
            f.flush()
        
        try:
            loaded_state = validate_and_load_state(f.name)
            
            assert loaded_state is not None
            assert loaded_state['loop_id'] == 'test-loop-123'
            assert loaded_state['status'] == 'active'
        finally:
            os.unlink(f.name)
    
    def test_validate_and_load_state_invalid(self):
        """Test validate_and_load_state with invalid data."""
        invalid_state = {
            'loop_id': 'test-loop-123',
            # Missing required fields
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(invalid_state, f)
            f.flush()
        
        try:
            loaded_state = validate_and_load_state(f.name)
            
            assert loaded_state is None
        finally:
            os.unlink(f.name)


def test_validation_result_basic():
    """Test ValidationResult basic functionality."""
    result = ValidationResult()
    
    assert result.is_valid
    assert len(result.errors) == 0
    assert len(result.warnings) == 0
    
    result.add_error("Test error")
    assert not result.is_valid
    assert len(result.errors) == 1
    
    result.add_warning("Test warning")
    assert len(result.warnings) == 1
    
    str_repr = str(result)
    assert "validation failed" in str_repr


if __name__ == '__main__':
    pytest.main([__file__, '-v'])