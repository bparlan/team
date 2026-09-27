#!/usr/bin/env python3
"""
Workflow modules for theteam skill enhancement.

This package contains workflow management components including discussion management
and context aggregation for the enhanced theteam skill.
"""

# Discussion management - use refactored version for maintainability
from theteam.workflow.discussion_manager_refactored import create_discussion_manager, LightweightDiscussionManager, LegacyDiscussionManager

# Legacy DiscussionManager alias for backward compatibility
DiscussionManager = LegacyDiscussionManager

# Version
__version__ = "1.0.0"

# Export key components
__all__ = [
    'DiscussionManager',
    'LightweightDiscussionManager',
    'LegacyDiscussionManager',
    'create_discussion_manager',
    '__version__'
]

# Initialize logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)