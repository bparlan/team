#!/usr/bin/env python3
"""
Behavioral Validator for theteam Enhancement

This module validates behavioral enhancements and ensures they meet
quality standards and requirements.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import sys

# Deferred imports to avoid circular dependencies
_config_enhancements_imported = False
_project_analyzer_imported = False  
_team_manager_imported = False

def _import_config():
    global _config_enhancements_imported
    if not _config_enhancements_imported:
        from config.enhancements import (
            CORE_STYLES,
            ENHANCED_PERSONALITY_TRAITS,
            BEHAVIORAL_MODIFIERS,
            TEAM_ROLE_TEMPLATES,
            BEHAVIORAL_COMPATIBILITY_MATRIX,
            ASSESSMENT_METRICS
        )
        _config_enhancements_imported = True
    return (
        CORE_STYLES, ENHANCED_PERSONALITY_TRAITS,
        BEHAVIORAL_MODIFIERS, TEAM_ROLE_TEMPLATES,
        BEHAVIORAL_COMPATIBILITY_MATRIX, ASSESSMENT_METRICS
    )

def _import_analysis():
    global _project_analyzer_imported
    if not _project_analyzer_imported:
        analysis_path = Path(__file__).parent / 'analysis'
        if analysis_path.exists():
            import sys
            sys.path.insert(0, str(analysis_path))
            from project_scanner import ProjectAnalyzer
            _project_analyzer_imported = True
    return ProjectAnalyzer if _project_analyzer_imported else None

def _import_management():
    global _team_manager_imported
    if not _team_manager_imported:
        management_path = Path(__file__).parent / 'management'
        if management_path.exists():
            import sys
            sys.path.insert(0, str(management_path))
            from team_manager import TeamManager
            _team_manager_imported = True
    return TeamManager if _team_manager_imported else None

# End of deferred imports


