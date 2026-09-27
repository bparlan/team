#!/usr/bin/env python3
"""
Core modules for theteam skill enhancement.

This package contains the core infrastructure for the enhanced theteam skill,
including state management, system integration, and discussion management.
"""

from .state_manager import (
    get_state_manager,
    UnifiedStateManager,
    DiscussionState,
    SystemAwarenessState,
    TaskState,
    StateEventType
)

from .system_integration import SystemIntegration

# Version
__version__ = "1.0.0"


# Phase 4 exports. Each of these modules is reachable from the package entry
# point so none of them is left orphaned on disk.
from .metrics import MetricsCollector, MetricsRegistry, get_registry, REGISTRY
from .backup import BackupManager, BackupIntegrityError
from .audit import AuditLogger
from .resource_limiter import ResourceLimiter, ResourceType
from .postgres_cluster import (
    PostgresClusterConfig,
    FailoverManager,
    FailoverError,
    ReadReplicaRouter,
)

# Export key components
__all__ = [
    'get_state_manager',
    'UnifiedStateManager',
    'DiscussionState',
    'SystemAwarenessState',
    'TaskState',
    'StateEventType',
    'SystemIntegration',
    '__version__',
    # Phase 4: productionization
    'MetricsCollector',
    'MetricsRegistry',
    'get_registry',
    'REGISTRY',
    'BackupManager',
    'BackupIntegrityError',
    'AuditLogger',
    'ResourceLimiter',
    'ResourceType',
    'PostgresClusterConfig',
    'FailoverManager',
    'FailoverError',
    'ReadReplicaRouter',
]

# Initialize logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)