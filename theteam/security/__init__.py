#!/usr/bin/env python3
"""
theteam.security - Security utilities for theteam skill.
"""
import os
import json
from datetime import datetime, timezone


def log_security_event(event_type, message):
    """Log security events for audit purposes."""
    event = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'event_type': event_type,
        'message': message,
        'source': 'theteam'
    }
    try:
        with open('security_audit.log', 'a') as f:
            f.write(json.dumps(event) + '\n')
    except (IOError, OSError, PermissionError) as e:
        print(f"Warning: Failed to log security event: {e}")


def validate_project_root(project_root):
    """Validate project root to prevent security issues."""
    if not project_root or not isinstance(project_root, str):
        raise ValueError("Invalid project root: must be non-empty string")
    normalized_root = os.path.normpath(project_root)
    if '..' in normalized_root:
        raise ValueError(f"Security violation: path traversal detected in {project_root}")
    if not os.path.exists(normalized_root):
        raise ValueError(f"Project root does not exist: {normalized_root}")
    if not os.path.isdir(normalized_root):
        raise ValueError(f"Project root is not a directory: {normalized_root}")
    return normalized_root


def secure_join_path(base_path, file_path):
    """Safely join paths to prevent directory traversal."""
    base = os.path.normpath(base_path)
    file = os.path.normpath(file_path)
    full_path = os.path.join(base, file)
    full_path = os.path.normpath(full_path)
    if not full_path.startswith(base + os.sep) and full_path != base:
        raise ValueError(f"Security violation: attempted path traversal with {file_path}")
    return full_path


def is_within_project(file_path, project_root):
    """Check if file path is within the project root."""
    try:
        file_path = os.path.normpath(file_path)
        project_root = os.path.normpath(project_root)
        return file_path.startswith(project_root + os.sep) or file_path == project_root
    except Exception:
        return False


def encrypt_sensitive_fields(data):
    """Encrypt sensitive fields in configuration data."""
    if not isinstance(data, dict):
        return data
    encrypted_data = data.copy()
    sensitive_fields = [
        'api_key', 'secret_key', 'token', 'password', 'credential',
        'auth', 'authorization', 'private_key', 'certificate'
    ]
    for key, value in encrypted_data.items():
        if any(sensitive in key.lower() for sensitive in sensitive_fields):
            encrypted_data[key] = f"ENCRYPTED:{hash(str(value))}"
        elif isinstance(value, dict):
            encrypted_data[key] = encrypt_sensitive_fields(value)
        elif isinstance(value, list):
            encrypted_data[key] = [
                encrypt_sensitive_fields(item) if isinstance(item, dict) else item
                for item in value
            ]
    return encrypted_data