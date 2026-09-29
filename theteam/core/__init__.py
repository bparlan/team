#!/usr/bin/env python3
"""
Core modules for theteam skill enhancement.

This package contains the core infrastructure for the enhanced theteam skill,
including state management, system integration, and discussion management.
"""

# Nothing is imported eagerly here. `theteam/__init__` imports
# `theteam.core.state_manager`, and an eager re-export block made every
# `import theteam` load the whole core tree: the metrics registry, the backup
# manager, the audit log, the resource limiter, and the PostgreSQL cluster
# layer with its connection pool, failover manager and read replicas. §5.1
# places none of the database tier in this stack, and `check_invariants.sh`
# invariant 7 now fails the build if it reappears.
#
# These names are still importable exactly as before - `from theteam.core
# import get_state_manager` and `from theteam.core import PostgresClusterConfig`
# both work - they are resolved on first access by `__getattr__` below instead
# of at package import. Every production consumer already imports from the
# module it needs (`theteam.core.metrics`, `theteam.core.audit`, ...), so this
# changes load order, not behaviour.

# Version
__version__ = "1.0.0"

_LAZY = {
    "get_state_manager": "state_manager",
    "UnifiedStateManager": "state_manager",
    "DiscussionState": "state_manager",
    "SystemAwarenessState": "state_manager",
    "TaskState": "state_manager",
    "StateEventType": "state_manager",
    "SystemIntegration": "system_integration",
    "MetricsCollector": "metrics",
    "MetricsRegistry": "metrics",
    "get_registry": "metrics",
    "REGISTRY": "metrics",
    "BackupManager": "backup",
    "BackupIntegrityError": "backup",
    "AuditLogger": "audit",
    "ResourceLimiter": "resource_limiter",
    "ResourceType": "resource_limiter",
    "PostgresClusterConfig": "postgres_cluster",
    "FailoverManager": "postgres_cluster",
    "FailoverError": "postgres_cluster",
    "ReadReplicaRouter": "postgres_cluster",
}


def __getattr__(name):
    """PEP 562. Resolve a re-exported name on first access, not at import."""
    module = _LAZY.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module
    value = getattr(import_module(f".{module}", __name__), name)
    globals()[name] = value          # cached: later accesses skip this
    return value


def __dir__():
    return sorted(__all__)


# Initialize logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
