#!/usr/bin/env python3
"""
Centralized utility functions for theteam skill.
"""
import sys

def _fatal(code, message):
    sys.stderr.write(f"FATAL: {message}\n")
    sys.exit(code)
