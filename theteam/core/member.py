#!/usr/bin/env python3
"""
theteam.core.member - Member management utilities.
"""
import os
import json
import yaml
from datetime import datetime, timezone


def load_config(project_root):
    """Load and validate team configuration."""
    config_path = os.path.join(project_root, "theteam.config")
    if not os.path.exists(config_path):
        return None, "theteam.config not found"
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config, None
    except Exception as e:
        return None, f"Failed to load config: {e}"


def write_member_note(note_data, notes_dir):
    """Write a member's note to a file in the notes directory."""
    os.makedirs(notes_dir, exist_ok=True)
    note_path = os.path.join(notes_dir, f"{note_data['id']}.json")
    try:
        with open(note_path, 'w') as f:
            json.dump(note_data, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to write note: {e}")
        return False


def validate_member_note(note_data, expected_id):
    """Validate that a member note has the correct structure and ID."""
    if not isinstance(note_data, dict):
        return False, "Note is not a dictionary"
    if note_data.get('id') != expected_id:
        return False, f"Note ID mismatch or missing. Expected '{expected_id}', got '{note_data.get('id', 'missing')}'"
    required = ['id', 'role', 'verdict', 'note']
    for key in required:
        if key not in note_data:
            return False, f"Missing required key: {key}"
    return True, None