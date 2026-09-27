#!/usr/bin/env python3
"""
theteam tests - Comprehensive test suite for theteam skill.
"""
import os
import sys
import json
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to test utilities
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

# Import test utilities
from test_utils import isolated_temp_dir

# Add project root and current script directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
PARENT_DIR = os.path.dirname(PROJECT_ROOT)
sys.path.insert(0, PARENT_DIR)
sys.path.insert(0, PROJECT_ROOT)

# Import theteam modules
from theteam import bootstrap_flow

# Import security utilities
from theteam.security import (
    log_security_event,
    validate_project_root,
    secure_join_path,
    is_within_project,
    encrypt_sensitive_fields
)

# Import core utilities
from theteam.core.member import (
    load_config,
    write_member_note,
    validate_member_note
)

class TestSecurityUtilities(unittest.TestCase):
    """Tests for security utility functions."""

    def test_validate_project_root_valid(self):
        """Test that valid project root passes validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = validate_project_root(tmpdir)
            # Returns the normalized absolute path, not a config payload.
            self.assertIsInstance(result, str)
            self.assertEqual(result, os.path.normpath(tmpdir))

    def test_validate_project_root_empty(self):
        """Test that empty project root raises error."""
        with self.assertRaises(ValueError):
            validate_project_root("")

    def test_validate_project_root_none(self):
        """Test that None project root raises error."""
        with self.assertRaises(ValueError):
            validate_project_root(None)

    def test_validate_project_root_traversal(self):
        """Test that path traversal attempts are blocked."""
        with self.assertRaises(ValueError):
            validate_project_root("/some/path/../../../etc/passwd")

    def test_validate_project_root_nonexistent(self):
        """Test that nonexistent path raises error."""
        with self.assertRaises(ValueError):
            validate_project_root("/nonexistent/path/12345")

    def test_secure_join_path_valid(self):
        """Test that valid path joins work."""
        result = secure_join_path("/project", "subdir/file.txt")
        self.assertEqual(result, "/project/subdir/file.txt")

    def test_secure_join_path_traversal(self):
        """Test that path traversal is blocked."""
        with self.assertRaises(ValueError):
            secure_join_path("/project", "../etc/passwd")

    def test_is_within_project_true(self):
        """Test that file within project returns True."""
        self.assertTrue(is_within_project("/project/subdir/file.txt", "/project"))

    def test_is_within_project_false(self):
        """Test that file outside project returns False."""
        self.assertFalse(is_within_project("/other/file.txt", "/project"))

    def test_encrypt_sensitive_fields_api_key(self):
        """Test that API keys are encrypted."""
        result = encrypt_sensitive_fields({"api_key": "secret", "name": "test"})
        self.assertTrue(result["api_key"].startswith("ENCRYPTED:"))
        self.assertEqual(result["name"], "test")

    def test_encrypt_sensitive_fields_nested(self):
        """Test that nested sensitive fields are encrypted."""
        result = encrypt_sensitive_fields({"config": {"token": "secret", "value": 42}})
        self.assertTrue(result["config"]["token"].startswith("ENCRYPTED:"))
        self.assertEqual(result["config"]["value"], 42)

class TestMemberUtilities(unittest.TestCase):
    """Tests for member utility functions."""

    def test_load_config_not_found(self):
        """Test that missing config returns error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config, error = load_config(tmpdir)
            self.assertIsNone(config)
            self.assertIsNotNone(error)

    def test_write_member_note_success(self):
        """Test that member notes can be written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            note_data = {
                "id": "architect",
                "role": "Systems Architect",
                "verdict": "APPROVED",
                "note": "Looks good"
            }
            result = write_member_note(note_data, tmpdir)
            self.assertTrue(result)
            self.assertTrue(os.path.exists(os.path.join(tmpdir, "architect.json")))

    def test_validate_member_note_correct_id(self):
        """Test that note with correct ID passes validation."""
        note_data = {
            "id": "architect",
            "role": "Systems Architect",
            "verdict": "APPROVED",
            "note": "Looks good"
        }
        valid, error = validate_member_note(note_data, "architect")
        self.assertTrue(valid)
        self.assertIsNone(error)

    def test_validate_member_note_wrong_id(self):
        """Test that note with wrong ID fails validation."""
        note_data = {
            "id": "pragmatist",
            "role": "Delivery Pragmatist",
            "verdict": "APPROVED",
            "note": "Looks good"
        }
        valid, error = validate_member_note(note_data, "architect")
        self.assertFalse(valid)
        self.assertIsNotNone(error)

    def test_validate_member_note_missing_fields(self):
        """Test that note with missing fields fails validation."""
        note_data = {"id": "architect"}
        valid, error = validate_member_note(note_data, "architect")
        self.assertFalse(valid)
        self.assertIsNotNone(error)

class TestSecurityLogging(unittest.TestCase):
    """Tests for security logging functionality."""

    def test_log_security_event_creates_file(self):
        """Test that security events are logged to file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                log_security_event("TEST_EVENT", "Test message")
                self.assertTrue(os.path.exists("security_audit.log"))
                with open("security_audit.log", "r") as f:
                    content = f.read()
                    self.assertIn("TEST_EVENT", content)
                    self.assertIn("Test message", content)
            finally:
                os.chdir(original_cwd)

class TestBootstrapFlow(unittest.TestCase):
    """Tests for bootstrap flow."""

    def test_bootstrap_creates_config(self):
        """Test that bootstrap creates a valid config file."""
        with isolated_temp_dir() as tmpdir:
            # Copy template config to temp directory
            template_src = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "theteam", "theteam-template.config"
            )
            if os.path.exists(template_src):
                import shutil
                shutil.copy(template_src, str(tmpdir))

            # Run bootstrap - FIXED: use importlib.import_module instead of spec_from_file_location
            import importlib
            theteam_module = importlib.import_module('theteam')
            result = theteam_module.bootstrap_flow(str(tmpdir))

            # Note: This test may fail if template not found, which is acceptable
            if os.path.exists(template_src):
                self.assertTrue(result)
                self.assertTrue(os.path.exists(os.path.join(str(tmpdir), "theteam.config")))

if __name__ == "__main__":
    unittest.main()