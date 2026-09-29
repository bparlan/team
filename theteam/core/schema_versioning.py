#!/usr/bin/env python3
"""
Schema versioning for theteam.

This module provides schema versioning for state files and events,
ensuring forward and backward compatibility checks.
"""

import json
import hashlib
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Union, Type
from dataclasses import dataclass, asdict, field
from enum import Enum
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)
class SchemaVersionError(Exception):
    """Exception raised for schema versioning errors."""
    pass
class SchemaVersion(str, Enum):
    """Supported schema versions."""
    # Event Log Schema Versions
    EVENT_V1 = "event_v1"
    EVENT_V2 = "event_v2"
    
    # State File Schema Versions
    STATE_V1 = "state_v1"
    STATE_V2 = "state_v2"
    
    # Combined Schema Versions
    COMBINED_V1 = "combined_v1"

    @classmethod
    def get_latest(cls, schema_type: str) -> 'SchemaVersion':
        """
        Get the latest schema version for a given type.

        Args:
            schema_type: Type of schema ('event', 'state', or 'combined')

        Returns:
            Latest schema version
        """
        if schema_type == 'event':
            return cls.EVENT_V2
        elif schema_type == 'state':
            return cls.STATE_V2
        elif schema_type == 'combined':
            return cls.COMBINED_V1
        else:
            raise ValueError(f"Unknown schema type: {schema_type}")
class SchemaRegistry:
    """
    Registry for schema definitions and migration functions.
    """

    def __init__(self):
        self._event_schemas: Dict[SchemaVersion, Dict[str, Any]] = {}
        self._state_schemas: Dict[SchemaVersion, Dict[str, Any]] = {}
        self._migrations: Dict[Tuple[SchemaVersion, SchemaVersion], callable] = {}
        self._register_schemas()
        self._register_migrations()

    def _register_schemas(self):
        """Register all schema definitions."""
        # Event schemas
        self._event_schemas[SchemaVersion.EVENT_V1] = {
            'version': SchemaVersion.EVENT_V1,
            'created_at': '2024-01-01T00:00:00Z',
            'description': 'Initial event schema',
            'required_fields': ['event_id', 'timestamp', 'event_type', 'data', 'event_hash'],
            'field_types': {
                'event_id': str,
                'timestamp': str,
                'event_type': str,
                'data': dict,
                'event_hash': str,
                'prev_event_id': Optional[str]
            },
            'validators': {
                'event_id': lambda x: isinstance(x, str) and len(x) > 0,
                'timestamp': lambda x: isinstance(x, str) and 'T' in x and 'Z' in x,
                'event_type': lambda x: isinstance(x, str) and len(x) > 0,
                'data': lambda x: isinstance(x, dict),
                'event_hash': lambda x: isinstance(x, str) and len(x) == 64,
                'prev_event_id': lambda x: x is None or (isinstance(x, str) and len(x) > 0)
            }
        }

        self._event_schemas[SchemaVersion.EVENT_V2] = {
            'version': SchemaVersion.EVENT_V2,
            'created_at': '2024-06-01T00:00:00Z',
            'description': 'Enhanced event schema with correlation IDs',
            'required_fields': ['event_id', 'timestamp', 'event_type', 'data', 'event_hash', 
                              'correlation_id', 'schema_version'],
            'field_types': {
                'event_id': str,
                'timestamp': str,
                'event_type': str,
                'data': dict,
                'event_hash': str,
                'prev_event_id': Optional[str],
                'correlation_id': str,
                'schema_version': str
            },
            'validators': {
                'event_id': lambda x: isinstance(x, str) and len(x) > 0,
                'timestamp': lambda x: isinstance(x, str) and 'T' in x and 'Z' in x,
                'event_type': lambda x: isinstance(x, str) and len(x) > 0,
                'data': lambda x: isinstance(x, dict),
                'event_hash': lambda x: isinstance(x, str) and len(x) == 64,
                'prev_event_id': lambda x: x is None or (isinstance(x, str) and len(x) > 0),
                'correlation_id': lambda x: isinstance(x, str) and len(x) > 0,
                'schema_version': lambda x: isinstance(x, str) and x.startswith('event_')
            }
        }

        # State schemas
        self._state_schemas[SchemaVersion.STATE_V1] = {
            'version': SchemaVersion.STATE_V1,
            'created_at': '2024-01-01T00:00:00Z',
            'description': 'Initial state schema',
            'required_fields': ['version', 'timestamp', 'discussion_state', 'system_awareness_state', 'task_state'],
            'field_types': {
                'version': str,
                'timestamp': str,
                'discussion_state': dict,
                'system_awareness_state': dict,
                'task_state': dict,
                'checksum': Optional[str],
                'checksum_algorithm': Optional[str]
            },
            'validators': {
                'version': lambda x: isinstance(x, str) and x.startswith('state_'),
                'timestamp': lambda x: isinstance(x, str) and 'T' in x and 'Z' in x,
                'discussion_state': lambda x: isinstance(x, dict),
                'system_awareness_state': lambda x: isinstance(x, dict),
                'task_state': lambda x: isinstance(x, dict),
                'checksum': lambda x: x is None or (isinstance(x, str) and len(x) == 64),
                'checksum_algorithm': lambda x: x is None or isinstance(x, str)
            }
        }

        self._state_schemas[SchemaVersion.STATE_V2] = {
            'version': SchemaVersion.STATE_V2,
            'created_at': '2024-06-01T00:00:00Z',
            'description': 'Enhanced state schema with schema versioning and checksums',
            'required_fields': ['version', 'timestamp', 'discussion_state', 'system_awareness_state', 'task_state',
                              'schema_version', 'checksum', 'checksum_algorithm', 'created_at'],
            'field_types': {
                'version': str,
                'timestamp': str,
                'discussion_state': dict,
                'system_awareness_state': dict,
                'task_state': dict,
                'schema_version': str,
                'checksum': str,
                'checksum_algorithm': str,
                'created_at': str,
                'correlation_id': Optional[str]
            },
            'validators': {
                'version': lambda x: isinstance(x, str) and x.startswith('state_'),
                'timestamp': lambda x: isinstance(x, str) and 'T' in x and 'Z' in x,
                'discussion_state': lambda x: isinstance(x, dict),
                'system_awareness_state': lambda x: isinstance(x, dict),
                'task_state': lambda x: isinstance(x, dict),
                'schema_version': lambda x: isinstance(x, str) and x.startswith('state_'),
                'checksum': lambda x: isinstance(x, str) and len(x) == 64,
                'checksum_algorithm': lambda x: isinstance(x, str) and x in ['sha256', 'sha512'],
                'created_at': lambda x: isinstance(x, str) and 'T' in x and 'Z' in x,
                'correlation_id': lambda x: x is None or (isinstance(x, str) and len(x) > 0)
            }
        }

        self._state_schemas[SchemaVersion.COMBINED_V1] = {
            'version': SchemaVersion.COMBINED_V1,
            'created_at': '2024-06-01T00:00:00Z',
            'description': 'Combined schema for state and events',
            'required_fields': ['version', 'timestamp', 'data', 'schema_version', 'checksum'],
            'field_types': {
                'version': str,
                'timestamp': str,
                'data': dict,
                'schema_version': str,
                'checksum': str,
                'event_id': Optional[str],
                'event_type': Optional[str],
                'correlation_id': Optional[str]
            }
        }

    def _register_migrations(self):
        """Register all migration functions."""
        # Event migrations
        self._migrations[(SchemaVersion.EVENT_V1, SchemaVersion.EVENT_V2)] = self._migrate_event_v1_to_v2

        # State migrations
        self._migrations[(SchemaVersion.STATE_V1, SchemaVersion.STATE_V2)] = self._migrate_state_v1_to_v2

        # Combined migrations
        self._migrations[(SchemaVersion.COMBINED_V1, SchemaVersion.COMBINED_V1)] = lambda x: x  # No-op

    def _migrate_event_v1_to_v2(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate event from v1 to v2."""
        migrated = data.copy()
        migrated['correlation_id'] = f"corr_{datetime.now(timezone.utc).timestamp()}"
        migrated['schema_version'] = SchemaVersion.EVENT_V2.value
        return migrated

    def _migrate_state_v1_to_v2(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate state from v1 to v2."""
        migrated = data.copy()
        migrated['schema_version'] = SchemaVersion.STATE_V2.value
        migrated['created_at'] = datetime.now(timezone.utc).isoformat()

        # Add checksum
        checksum_data = json.dumps(migrated, sort_keys=True)
        checksum = hashlib.sha256(checksum_data.encode()).hexdigest()
        migrated['checksum'] = checksum
        migrated['checksum_algorithm'] = 'sha256'

        # Add correlation ID
        migrated['correlation_id'] = f"state_{datetime.now(timezone.utc).timestamp()}"

        return migrated

    def get_schema(self, schema_version: SchemaVersion, schema_type: str) -> Dict[str, Any]:
        """
        Get schema definition.

        Args:
            schema_version: Schema version
            schema_type: Type of schema ('event' or 'state')

        Returns:
            Schema definition
        """
        if schema_type == 'event':
            return self._event_schemas.get(schema_version)
        elif schema_type == 'state':
            return self._state_schemas.get(schema_version)
        else:
            raise ValueError(f"Unknown schema type: {schema_type}")

    def validate_data(self, data: Dict[str, Any], schema_version: SchemaVersion, 
                     schema_type: str) -> Tuple[bool, List[str]]:
        """
        Validate data against a schema.

        Args:
            data: Data to validate
            schema_version: Schema version
            schema_type: Type of schema ('event' or 'state')

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Get schema
        schema = self.get_schema(schema_version, schema_type)
        if not schema:
            errors.append(f"Unknown schema: {schema_version} for {schema_type}")
            return False, errors

        # Check required fields
        for field in schema['required_fields']:
            if field not in data:
                errors.append(f"Missing required field: {field}")

        # Validate field types
        for field, value in data.items():
            if field in schema['field_types']:
                expected_type = schema['field_types'][field]
                if expected_type == Optional[str]:
                    if value is not None and not isinstance(value, str):
                        errors.append(f"Field {field}: Expected str or None, got {type(value)}")
                elif expected_type == Optional[Dict]:
                    if value is not None and not isinstance(value, dict):
                        errors.append(f"Field {field}: Expected dict or None, got {type(value)}")
                elif not isinstance(value, expected_type):
                    errors.append(f"Field {field}: Expected {expected_type}, got {type(value)}")

        # Run custom validators
        for field, validator in schema['validators'].items():
            if field in data and not validator(data[field]):
                errors.append(f"Field {field}: Validation failed")

        return len(errors) == 0, errors

    def migrate_data(self, data: Dict[str, Any], from_version: SchemaVersion, 
                    to_version: SchemaVersion, schema_type: str) -> Dict[str, Any]:
        """
        Migrate data from one schema version to another.

        Args:
            data: Data to migrate
            from_version: Source schema version
            to_version: Target schema version
            schema_type: Type of schema ('event' or 'state')

        Returns:
            Migrated data
        """
        if from_version == to_version:
            return data

        # Find migration function
        migration_key = (from_version, to_version)
        if migration_key in self._migrations:
            return self._migrations[migration_key](data)

        # If no direct migration, try incremental migrations
        errors = []
        current_data = data
        current_version = from_version

        # Get all versions for this schema type
        versions = list(self._event_schemas.keys()) if schema_type == 'event' else list(self._state_schemas.keys())

        # Sort versions by creation date (simplified)
        version_order = sorted(versions, key=lambda v: v.value)

        # Find from_version and to_version indices
        try:
            from_idx = version_order.index(current_version)
            to_idx = version_order.index(to_version)
        except ValueError:
            errors.append(f"Version not found in {schema_type} schema")
            return data

        # Apply migrations incrementally
        if from_idx < to_idx:
            for i in range(from_idx, to_idx):
                next_version = version_order[i + 1]
                migration_key = (current_version, next_version)
                if migration_key in self._migrations:
                    current_data = self._migrations[migration_key](current_data)
                    current_version = next_version
                else:
                    errors.append(f"No migration from {current_version} to {next_version}")
                    break

        if errors:
            raise SchemaVersionError(f"Migration errors: {'; '.join(errors)}")

        return current_data

    def compute_checksum(self, data: Dict[str, Any], algorithm: str = 'sha256') -> str:
        """
        Compute checksum for data.

        Args:
            data: Data to checksum
            algorithm: Checksum algorithm ('sha256' or 'sha512')

        Returns:
            Checksum string
        """
        if algorithm == 'sha256':
            hash_obj = hashlib.sha256
        elif algorithm == 'sha512':
            hash_obj = hashlib.sha512
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")

        # Sort data keys for deterministic checksum
        data_str = json.dumps(data, sort_keys=True)
        return hash_obj(data_str.encode()).hexdigest()

    def verify_checksum(self, data: Dict[str, Any], checksum: str, 
                       algorithm: str = 'sha256') -> bool:
        """
        Verify checksum for data.

        Args:
            data: Data to verify
            checksum: Checksum to verify against
            algorithm: Checksum algorithm

        Returns:
            True if checksum matches
        """
        computed = self.compute_checksum(data, algorithm)
        return computed == checksum
class StateSchemaValidator:
    """
    State schema validator that ensures state files meet schema requirements.
    """

    def __init__(self, registry: Optional[SchemaRegistry] = None):
        self.registry = registry or SchemaRegistry()
        self.supported_versions = {
            SchemaVersion.STATE_V1,
            SchemaVersion.STATE_V2,
            SchemaVersion.COMBINED_V1
        }

    def validate_state_file(self, data: Dict[str, Any], 
                           expected_version: Optional[SchemaVersion] = None) -> Tuple[bool, List[str]]:
        """
        Validate a state file.

        Args:
            data: State file data
            expected_version: Expected schema version (defaults to latest)

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check version
        if 'version' not in data:
            errors.append("Missing version field")
            return False, errors

        try:
            version = SchemaVersion(data['version'])
        except ValueError:
            errors.append(f"Invalid version: {data['version']}")
            return False, errors

        # Check if version is supported
        if version not in self.supported_versions:
            errors.append(f"Unsupported version: {version}")

        # Validate against schema
        is_valid, validation_errors = self.registry.validate_data(data, version, 'state')
        errors.extend(validation_errors)

        # Check checksum if present
        if 'checksum' in data and 'checksum_algorithm' in data:
            if not self.registry.verify_checksum(data, data['checksum'], data['checksum_algorithm']):
                errors.append("Checksum verification failed")

        # Check schema version consistency
        if 'schema_version' in data and data['schema_version'] != version.value:
            errors.append(f"Schema version mismatch: {data['schema_version']} != {version.value}")

        return len(errors) == 0, errors

    def migrate_state_file(self, data: Dict[str, Any], target_version: SchemaVersion) -> Dict[str, Any]:
        """
        Migrate a state file to a target version.

        Args:
            data: State file data
            target_version: Target schema version

        Returns:
            Migrated state file
        """
        # Check current version
        if 'version' not in data:
            raise SchemaVersionError("State file missing version field")

        try:
            current_version = SchemaVersion(data['version'])
        except ValueError:
            raise SchemaVersionError(f"Invalid version: {data['version']}")

        # Migrate
        return self.registry.migrate_data(data, current_version, target_version, 'state')
class EventSchemaValidator:
    """
    Event schema validator that ensures event log entries meet schema requirements.
    """

    def __init__(self, registry: Optional[SchemaRegistry] = None):
        self.registry = registry or SchemaRegistry()
        self.supported_versions = {
            SchemaVersion.EVENT_V1,
            SchemaVersion.EVENT_V2,
            SchemaVersion.COMBINED_V1
        }

    def validate_event(self, data: Dict[str, Any], 
                      expected_version: Optional[SchemaVersion] = None) -> Tuple[bool, List[str]]:
        """
        Validate an event.

        Args:
            data: Event data
            expected_version: Expected schema version (defaults to latest)

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check version
        if 'event_id' not in data:
            errors.append("Missing event_id field")
            return False, errors

        # Check if event is in combined format (has version field)
        if 'version' in data:
            try:
                version = SchemaVersion(data['version'])
            except ValueError:
                errors.append(f"Invalid version: {data['version']}")
                return False, errors

            # Check if version is supported
            if version not in self.supported_versions:
                errors.append(f"Unsupported version: {version}")
        else:
            # Legacy event format - use EVENT_V1
            version = SchemaVersion.EVENT_V1

        # Validate against schema
        is_valid, validation_errors = self.registry.validate_data(data, version, 'event')
        errors.extend(validation_errors)

        return len(errors) == 0, errors

    def migrate_event(self, data: Dict[str, Any], target_version: SchemaVersion) -> Dict[str, Any]:
        """
        Migrate an event to a target version.

        Args:
            data: Event data
            target_version: Target schema version

        Returns:
            Migrated event
        """
        # Check current version
        if 'version' in data:
            try:
                current_version = SchemaVersion(data['version'])
            except ValueError:
                raise SchemaVersionError(f"Invalid version: {data['version']}")
        else:
            current_version = SchemaVersion.EVENT_V1

        # Migrate
        return self.registry.migrate_data(data, current_version, target_version, 'event')
class SchemaValidatorFactory:
    """
    Factory for creating schema validators.
    """

    def __init__(self):
        self._registry = SchemaRegistry()
        self._state_validator = None
        self._event_validator = None

    def get_state_validator(self) -> StateSchemaValidator:
        """Get state schema validator."""
        if self._state_validator is None:
            self._state_validator = StateSchemaValidator(self._registry)
        return self._state_validator

    def get_event_validator(self) -> EventSchemaValidator:
        """Get event schema validator."""
        if self._event_validator is None:
            self._event_validator = EventSchemaValidator(self._registry)
        return self._event_validator

    def get_registry(self) -> SchemaRegistry:
        """Get schema registry."""
        return self._registry