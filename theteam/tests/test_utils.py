#!/usr/bin/env python3
"""
Test utilities for deterministic test isolation.
Resolves non-deterministic test isolation issues caused by tempfile.mkdtemp with no cleanup.
"""

import os
import sys
import tempfile
import shutil
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def isolated_temp_dir():
    """
    Create a temporary directory that auto-cleans on exit.
    
    This context manager ensures proper test isolation by:
    1. Creating a unique temporary directory
    2. Changing to it for the test scope
    3. Adding it to sys.path for imports
    4. Automatically cleaning up and restoring environment on exit
    
    Usage:
        with isolated_temp_dir() as tmpdir:
            # Test code runs in isolated environment
            assert os.path.exists(os.path.join(tmpdir, "test.config"))
    
    Args:
        prefix: Optional prefix for temp directory name
        
    Yields:
        Path: The temporary directory path
    """
    prefix = "theteam_test_"
    tmpdir = tempfile.mkdtemp(prefix=prefix)
    original_cwd = os.getcwd()
    
    try:
        # Change to temp directory
        os.chdir(tmpdir)
        
        # Add to sys.path for imports
        sys.path.insert(0, tmpdir)
        
        # Create a Path object for convenience
        tmpdir_path = Path(tmpdir)
        
        yield tmpdir_path
        
    finally:
        # Restore original working directory
        os.chdir(original_cwd)
        
        # Remove temp dir from sys.path if present
        if tmpdir in sys.path:
            sys.path.remove(tmpdir)
            
        # Clean up temporary directory
        shutil.rmtree(tmpdir, ignore_errors=True)

@contextmanager  
def clean_temp_dir():
    """
    Simple temp directory context manager for basic isolation.
    
    Usage:
        with clean_temp_dir() as tmpdir:
            # Test code runs in temporary directory
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")
            assert test_file.exists()
    """
    tmpdir = tempfile.mkdtemp(prefix="clean_test_")
    original_cwd = os.getcwd()
    
    try:
        os.chdir(tmpdir)
        yield Path(tmpdir)
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)

# For backward compatibility and convenience
def create_test_environment():
    """
    Helper to create a complete isolated test environment.
    
    Returns:
        dict: Contains 'tmpdir' (Path), 'cleanup' function
    """
    tmpdir = tempfile.mkdtemp(prefix="complete_test_")
    
    def cleanup():
        original_cwd = os.getcwd()
        if tmpdir in sys.path:
            sys.path.remove(tmpdir)
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
    
    # Set up environment
    os.chdir(tmpdir)
    sys.path.insert(0, tmpdir)
    
    return {
        'tmpdir': Path(tmpdir),
        'cleanup': cleanup
    }