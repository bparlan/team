#!/usr/bin/env python3
"""
Resource Limiter implementation for theteam.

This module provides resource limiting capabilities to prevent runaway resource
consumption with bounded growth enforcement.
"""

import os
import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
import logging
from dataclasses import dataclass
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


def _int_env(name: str, default: Optional[int] = None) -> Optional[int]:
    """Read an int from env, falling back to `default` on missing/invalid."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning(f"Ignoring non-integer {name}={raw!r}")
        return default
    if value <= 0:
        logger.warning(f"Ignoring non-positive {name}={raw!r}")
        return default
    return value


def _float_env(name: str, default: Optional[float] = None) -> Optional[float]:
    """Read a float from env, falling back to `default` on missing/invalid."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning(f"Ignoring non-numeric {name}={raw!r}")
        return default


class ResourceType(Enum):
    """Resource type enumerator."""
    TASKS = "tasks"
    MEMORY = "memory"
    CPU = "cpu"
    DISK = "disk"
    NETWORK = "network"
    CONNECTIONS = "connections"
    THREADS = "threads"
    CACHE = "cache"
class ResourceLimit:
    """Resource limit configuration."""

    def __init__(self,
                 resource_type: ResourceType,
                 limit: int,
                 ttl: Optional[int] = None,
                 retention_policy: str = "expire",
                 alert_threshold: Optional[float] = None):
        self.resource_type = resource_type
        self.limit = limit
        self.ttl = ttl
        self.retention_policy = retention_policy  # "expire", "archive", "retain"
        self.alert_threshold = alert_threshold
        self.current_usage = 0
        self.creation_time = datetime.now(timezone.utc)
        self.last_accessed = datetime.now(timezone.utc)
        self.metadata: Dict[str, Any] = {}
        self._lock = threading.RLock()

    def is_available(self, amount: int = 1) -> bool:
        """Check if resource is available for the specified amount."""
        with self._lock:
            if self.current_usage + amount > self.limit:
                return False
            self.current_usage += amount
            self.last_accessed = datetime.now(timezone.utc)
            return True

    def release(self, amount: int = 1) -> None:
        """Release resource usage."""
        with self._lock:
            self.current_usage = max(0, self.current_usage - amount)

    def get_usage(self) -> int:
        """Get current resource usage."""
        with self._lock:
            return self.current_usage

    def get_utilization(self) -> float:
        """Get resource utilization as percentage."""
        with self._lock:
            if self.limit <= 0:
                return 0.0
            return (self.current_usage / self.limit) * 100.0

    def should_trigger_alert(self) -> bool:
        """Check if alert should be triggered based on threshold."""
        if self.alert_threshold is None:
            return False
        return self.get_utilization() >= self.alert_threshold

    def is_expired(self) -> bool:
        """Check if resource limit should expire based on TTL."""
        if self.ttl is None:
            return False
        return datetime.now(timezone.utc) - self.creation_time > timedelta(seconds=self.ttl)

    def cleanup_expired(self) -> bool:
        """Cleanup expired resource limit. Returns True if cleaned up."""
        if self.is_expired() and self.retention_policy == "expire":
            return True
        return False
@dataclass
class ResourceUsageEntry:
    """Resource usage tracking entry."""
    timestamp: datetime
    operation: str
    resource_type: ResourceType
    amount: int
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
class ResourceLimiter:
    """Resource limiter to prevent runaway resource consumption."""

    def __init__(self, max_resources: int = 1000, cleanup_interval: int = 300,
                 max_alerts: int = 1000, max_usage_history: int = 10000,
                 env_prefix: str = "THETEAM_LIMIT_"):
        self.max_resources = max_resources
        self.cleanup_interval = cleanup_interval
        self.env_prefix = env_prefix
        self.limits: Dict[str, ResourceLimit] = {}  # resource_id -> ResourceLimit
        # Both buffers are bounded: an unbounded alerts list or history deque
        # is a slow memory leak in a long-running process.
        self.max_alerts = max_alerts
        self.usage_history: deque = deque(maxlen=max_usage_history)
        self.alerts: deque = deque(maxlen=max_alerts)
        self.monitoring_enabled = True
        self._lock = threading.RLock()
        self._cleanup_running = False

        # Initialize default resource limits
        self._initialize_default_limits()

    @classmethod
    def from_env(cls) -> "ResourceLimiter":
        """Build a limiter with limits overlaid from environment variables.

        Env vars follow ``THETEAM_LIMIT_<RESOURCE>`` (e.g. ``THETEAM_LIMIT_TASKS=7``)
        and ``THETEAM_ALERT_<RESOURCE>`` for thresholds. Invalid or non-numeric
        values are ignored with a warning rather than raising, so a typo in
        production config degrades to the safe default instead of crashing.
        """
        limiter = cls(
            max_alerts=_int_env("THETEAM_MAX_ALERTS", 1000),
            max_usage_history=_int_env("THETEAM_MAX_USAGE_HISTORY", 10000),
        )
        for resource_type in ResourceType:
            name = resource_type.name
            configured = _int_env(f"THETEAM_LIMIT_{name}")
            if configured is not None:
                target = limiter.get_limit(resource_type)
                if target is not None:
                    target.limit = configured
            threshold = _float_env(f"THETEAM_ALERT_{name}")
            if threshold is not None:
                target = limiter.get_limit(resource_type)
                if target is not None:
                    target.alert_threshold = threshold
        return limiter

    def _initialize_default_limits(self) -> None:
        """Initialize default resource limits."""
        # Initialize common resource limits with reasonable defaults
        default_limits = {
            ResourceType.TASKS: ResourceLimit(ResourceType.TASKS, 100, ttl=3600, alert_threshold=90.0),
            ResourceType.CONNECTIONS: ResourceLimit(ResourceType.CONNECTIONS, 50, ttl=300, alert_threshold=80.0),
            ResourceType.THREADS: ResourceLimit(ResourceType.THREADS, 200, ttl=None, alert_threshold=95.0),
            ResourceType.CACHE: ResourceLimit(ResourceType.CACHE, 1000, ttl=7200, alert_threshold=85.0),
            ResourceType.MEMORY: ResourceLimit(ResourceType.MEMORY, 8192, ttl=None, alert_threshold=90.0),  # MB
            ResourceType.CPU: ResourceLimit(ResourceType.CPU, 100, ttl=60, alert_threshold=95.0),  # Percentage
            ResourceType.DISK: ResourceLimit(ResourceType.DISK, 1000, ttl=None, alert_threshold=90.0),  # GB
            ResourceType.NETWORK: ResourceLimit(ResourceType.NETWORK, 1000, ttl=300, alert_threshold=80.0)  # MB/sec
        }

        for resource_type, limit in default_limits.items():
            resource_id = f"{resource_type.value}_default"
            self.limits[resource_id] = limit

    def get_limit(self, resource_type: ResourceType, resource_id: str = None) -> Optional[ResourceLimit]:
        """Get resource limit by type and ID."""
        if resource_id is None:
            resource_id = f"{resource_type.value}_default"
        return self.limits.get(resource_id)

    def acquire(self, resource_type: ResourceType, amount: int = 1, resource_id: str = None) -> bool:
        """Acquire resource with specified type and amount."""
        limit = self.get_limit(resource_type, resource_id)
        if limit is None:
            # Create limit on-demand
            limit = ResourceLimit(resource_type, self.max_resources, alert_threshold=90.0)
            resource_id = resource_id or f"{resource_type.value}_dynamic"
            self.limits[resource_id] = limit

        success = limit.is_available(amount)
        if success:
            self.usage_history.append(ResourceUsageEntry(
                timestamp=datetime.now(timezone.utc),
                operation="acquire",
                resource_type=resource_type,
                amount=amount,
                metadata={"resource_id": resource_id}
            ))

        return success

    def release(self, resource_type: ResourceType, amount: int = 1, resource_id: str = None) -> None:
        """Release resource usage."""
        limit = self.get_limit(resource_type, resource_id)
        if limit:
            limit.release(amount)

            self.usage_history.append(ResourceUsageEntry(
                timestamp=datetime.now(timezone.utc),
                operation="release",
                resource_type=resource_type,
                amount=-amount,
                metadata={"resource_id": resource_id}
            ))

    def try_acquire_with_timeout(self, resource_type: ResourceType, timeout: int, amount: int = 1, resource_id: str = None) -> bool:
        """Acquire resource with timeout."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.acquire(resource_type, amount, resource_id):
                return True
            time.sleep(0.1)

        return False

    def get_usage_report(self) -> Dict[str, Any]:
        """Get comprehensive resource usage report."""
        with self._lock:
            report = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'total_resources': len(self.limits),
                'active_resources': sum(1 for limit in self.limits.values() if not limit.is_expired()),
                'total_usage': 0,
                'total_alerts': len(self.alerts),
                'resource_breakdown': {},
                'alerts': []
            }

            # Aggregate resource usage by type
            by_type: Dict[ResourceType, Dict[str, Any]] = defaultdict(lambda: {'count': 0, 'usage': 0, 'utilization': 0.0})

            for resource_id, limit in self.limits.items():
                if limit.is_expired():
                    continue

                resource_type = limit.resource_type
                usage = limit.get_usage()
                utilization = limit.get_utilization()

                by_type[resource_type]['count'] += 1
                by_type[resource_type]['usage'] += usage
                # Accumulate and average below; overwriting here reported the
                # last limit seen under the key 'average_utilization'.
                by_type[resource_type]['utilization'] += utilization

                # Check for alerts
                if limit.should_trigger_alert():
                    report['alerts'].append({
                        'resource_type': resource_type.value,
                        'resource_id': resource_id,
                        'current_usage': usage,
                        'limit': limit.limit,
                        'utilization': utilization,
                        'threshold': limit.alert_threshold,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })

            # Add resource breakdown
            for resource_type, stats in by_type.items():
                count = stats['count']
                report['resource_breakdown'][resource_type.value] = {
                    'resource_count': count,
                    'total_usage': stats['usage'],
                    'average_utilization': (stats['utilization'] / count) if count else 0.0
                }

            report['total_usage'] = sum(stats['usage'] for stats in by_type.values())

            return report

    def cleanup_expired_resources(self) -> int:
        """Clean up expired resources. Returns number of cleaned up."""
        with self._lock:
            cleaned_up = 0
            expired_ids = []

            for resource_id, limit in self.limits.items():
                if limit.cleanup_expired():
                    expired_ids.append(resource_id)

            for resource_id in expired_ids:
                del self.limits[resource_id]
                cleaned_up += 1

                self.usage_history.append(ResourceUsageEntry(
                    timestamp=datetime.now(timezone.utc),
                    operation="cleanup",
                    resource_type=ResourceType.CACHE,  # Generic cleanup type
                    amount=-1,
                    metadata={"resource_id": resource_id, "reason": "expired"}
                ))

            if cleaned_up > 0:
                logger.info(f"Cleaned up {cleaned_up} expired resources")

            return cleaned_up

    def start_monitoring(self) -> None:
        """Start background resource monitoring."""
        if self._cleanup_running:
            return

        self._cleanup_running = True

        def monitor_loop():
            while self._cleanup_running:
                if self.monitoring_enabled:
                    self.cleanup_expired_resources()
                time.sleep(self.cleanup_interval)

        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop background resource monitoring."""
        self._cleanup_running = False

    def get_usage_history(self, resource_type: ResourceType = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get usage history."""
        with self._lock:
            history = []

            for entry in self.usage_history:
                if resource_type is None or entry.resource_type == resource_type:
                    history.append({
                        'timestamp': entry.timestamp.isoformat(),
                        'operation': entry.operation,
                        'resource_type': entry.resource_type.value,
                        'amount': entry.amount,
                        'metadata': entry.metadata
                    })

            return history[-limit:] if limit else history

    def to_dict(self) -> Dict[str, Any]:
        """Serialize configuration and current usage for health/metrics endpoints."""
        with self._lock:
            limits = {}
            for resource_id, limit in self.limits.items():
                limits[resource_id] = {
                    'resource_type': limit.resource_type.value,
                    'limit': limit.limit,
                    'usage': limit.get_usage(),
                    'utilization': limit.get_utilization(),
                    'alert_threshold': limit.alert_threshold,
                    'ttl': limit.ttl,
                    'retention_policy': limit.retention_policy,
                }
            return {
                'max_resources': self.max_resources,
                'cleanup_interval': self.cleanup_interval,
                'max_alerts': self.max_alerts,
                'max_usage_history': self.usage_history.maxlen,
                'limits': limits,
                'alerts_retained': len(self.alerts),
                'history_retained': len(self.usage_history),
            }

    def validate_config(self) -> List[str]:
        """
        Report configuration problems.

        Used by the production config path so a bad limit is surfaced at
        startup rather than discovered when traffic is already flowing.
        """
        problems: List[str] = []
        with self._lock:
            if self.max_resources <= 0:
                problems.append("max_resources must be > 0")
            for resource_id, limit in self.limits.items():
                if limit.limit <= 0:
                    problems.append(f"{resource_id}: limit must be > 0")
                if limit.alert_threshold is not None and not 0 < limit.alert_threshold <= 100:
                    problems.append(f"{resource_id}: alert_threshold must be in (0, 100]")
        return problems