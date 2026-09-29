import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
import logging
from dataclasses import dataclass
from collections import deque

logger = logging.getLogger(__name__)

class HealthStatus(Enum):
    """Health status enumerator."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
class HealthMonitor:
    """System health monitoring component."""

    def __init__(self, project_root: str = None, check_interval: int = 30):
        self.project_root = project_root or "."
        self.check_interval = check_interval
        self.health_metrics: Dict[str, Any] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.monitoring_enabled = True
        self.last_health_check: Optional[datetime] = None
        self.health_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 80.0,
            'disk_usage': 90.0,
            'response_time': 1000.0
        }
        self._lock = threading.RLock()

        # Add alert retention policies
        self.alert_retention_hours: int = 168  # 7 days
        self.max_alerts: int = 10000

    def update_health(self, metrics: Dict[str, Any]) -> None:
        """Update health metrics from system integration."""
        with self._lock:
            self.health_metrics = metrics
            self.last_health_check = datetime.now(timezone.utc)
            self._check_for_alerts(metrics)

    def update_application_metrics(self, metrics: Dict[str, Any]) -> None:
        """Update application-specific health metrics."""
        with self._lock:
            self.health_metrics.update(metrics)

    def _check_for_alerts(self, metrics: Dict[str, Any]) -> None:
        """Check metrics against thresholds and create alerts."""
        for metric_name, threshold in self.health_thresholds.items():
            if metric_name in metrics:
                value = metrics[metric_name]
                if value > threshold:
                    alert = {
                        'type': 'threshold_exceeded',
                        'metric': metric_name,
                        'value': value,
                        'threshold': threshold,
                        'severity': 'warning' if value <= threshold * 1.5 else 'critical',
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    }
                    # Apply max size limit before appending
                    if len(self.alerts) >= self.max_alerts:
                        self.alerts.pop(0)
                    self.alerts.append(alert)

    def cleanup_alerts(self) -> int:
        """Clean up old alerts."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.alert_retention_hours)
        initial = len(self.alerts)
        self.alerts = [a for a in self.alerts
                       if datetime.fromisoformat(a['timestamp']) > cutoff]
        return initial - len(self.alerts)

    def get_health_status(self) -> Dict[str, Any]:
        """Get current health status."""
        with self._lock:
            status = HealthStatus.HEALTHY
            issues = []

            # Check thresholds
            for metric_name, threshold in self.health_thresholds.items():
                if metric_name in self.health_metrics:
                    value = self.health_metrics[metric_name]
                    if value > threshold * 2:
                        status = HealthStatus.CRITICAL
                        issues.append(f"{metric_name}: {value} > {threshold * 2}")
                    elif value > threshold:
                        if status == HealthStatus.HEALTHY:
                            status = HealthStatus.DEGRADED
                        issues.append(f"{metric_name}: {value} > {threshold}")

            return {
                'status': status.value,
                'metrics': self.health_metrics.copy(),
                'thresholds': self.health_thresholds.copy(),
                'issues': issues,
                'alerts': self.alerts.copy(),
                'health_score': self._calculate_health_score(),
                'monitoring_enabled': self.monitoring_enabled,
                'last_check': (
                    self.last_health_check.isoformat()
                    if self.last_health_check else None
                ),
            }

    def get_status_report(self) -> Dict[str, Any]:
        """Get comprehensive health status report."""
        return self.get_health_status()

    def _calculate_health_score(self) -> float:
        """Calculate overall health score (0-1)."""
        if not self.health_metrics:
            return 1.0

        scores = []
        for metric_name, value in self.health_metrics.items():
            if metric_name in self.health_thresholds:
                threshold = self.health_thresholds[metric_name]
                if value <= threshold:
                    scores.append(1.0)
                else:
                    # Score decreases as value exceeds threshold
                    scores.append(max(0.0, 1.0 - (value - threshold) / threshold))

        return sum(scores) / len(scores) if scores else 1.0

    def start_monitoring(self) -> None:
        """Start background health monitoring."""
        if self._monitor_thread is None:
            self._running = True
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                daemon=True,
                name="HealthMonitor"
            )
            self._monitor_thread.start()
            logger.info("Health monitoring started")

    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                self._check_system_health()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)

    def _check_system_health(self) -> None:
        """Check system health using current metrics."""
        self.update_health(self.health_metrics)

    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
            self._monitor_thread = None
            logger.info("Health monitoring stopped")

    def stop(self) -> None:
        """Stop the health monitor."""
        self.stop_monitoring()

    # Add periodic cleanup to monitoring loop
    def start_with_cleanup(self) -> None:
        """Start monitoring with periodic cleanup."""
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop_with_cleanup,
            daemon=True,
            name="HealthMonitorWithCleanup"
        )
        self._monitor_thread.start()
        logger.info("Health monitoring started with cleanup")

    def _monitor_loop_with_cleanup(self) -> None:
        """Background monitoring loop with cleanup."""
        while self._running:
            try:
                self._check_system_health()
                # Run cleanup every 6 hours (3600 seconds * 6)
                self.cleanup_alerts()
                time.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop with cleanup: {e}")
                time.sleep(60)

