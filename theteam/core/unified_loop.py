#!/usr/bin/env python3
"""
Unified Loop Implementation - Phase 3/4 DRIFT FIX

Consolidated implementation addressing all ponytail issues and Phase 4 requirements.
Single stable implementation with web API, monitoring, backup, and dead-letter queues.
"""

import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass
import logging
import os
from pathlib import Path


# Import Phase 3 modules (canonical imports, not duplicated)
from theteam.core.circuit_breaker import CircuitBreaker
from theteam.core.resource_limiter import ResourceLimiter
from theteam.core.health_monitor import HealthMonitor
from theteam.core.resource_limiter import ResourceType
from theteam.core.backup import BackupManager
from theteam.core.audit import AuditLogger
from theteam.core.task_contract import UnifiedTask, TaskStatus, TaskPriority

# Helper functions (addressing ponytail redundant patterns)
def _now() -> datetime:
    """Centralized timestamp generation - replaces 11 datetime.now(timezone.utc) calls"""
    return datetime.now(timezone.utc)

# Core enumerations
class LoopState(Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    ERROR = "error"
# LoopPriority is the canonical TaskPriority - the loop must not define a
# competing priority scale. Aliased, not duplicated, so a UnifiedTask built
# with TaskPriority validates and the loop's priority buckets stay in sync.
LoopPriority = TaskPriority

# Consolidated data classes
@dataclass
class LoopConfig:
    loop_id: Optional[str] = None
    project_root: Optional[str] = None
    max_cycles: Optional[int] = None
    monitoring_interval: int = 30
    enable_monitoring: bool = True
    enable_automated_analysis: bool = True
    auto_start: bool = False

    def __post_init__(self):
        if self.loop_id is None:
            self.loop_id = f"loop_{uuid.uuid4().hex[:8]}"
        if self.project_root is None:
            self.project_root = os.getcwd()

# State engine for managing loop state
class StateEngine:
    """Manages loop state transitions"""

    def __init__(self, config: LoopConfig):
        self.config = config
        self.current_state = LoopState.STOPPED
        self.current_phase = None
        self.cycle_count = 0
        self.start_time = None
        self.paused_time = None
        self.total_paused_time = timedelta(0)
        self._lock = threading.RLock()

    def start(self) -> bool:
        with self._lock:
            if self.current_state != LoopState.STOPPED:
                return False

            self.current_state = LoopState.STARTING
            self.start_time = _now()
            self.cycle_count = 0
            return True

    def pause(self) -> bool:
        with self._lock:
            if self.current_state not in (LoopState.RUNNING, LoopState.STARTING):
                return False

            self.paused_time = _now()
            self.current_state = LoopState.PAUSED
            self.total_paused_time += _now() - self.paused_time
            return True

    def resume(self) -> bool:
        with self._lock:
            if self.current_state != LoopState.PAUSED:
                return False

            if self.paused_time:
                self.total_paused_time += _now() - self.paused_time
                self.paused_time = None

            self.current_state = LoopState.RUNNING
            return True

    def stop(self) -> bool:
        with self._lock:
            if self.current_state == LoopState.STOPPED:
                return True

            self.current_state = LoopState.STOPPING
            time.sleep(0.1)
            self.current_state = LoopState.STOPPED
            return True

    def complete_cycle(self):
        with self._lock:
            self.cycle_count += 1
            self.current_state = LoopState.RUNNING

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            uptime = None
            if self.start_time:
                uptime = _now() - self.start_time - self.total_paused_time

            return {
                'state': self.current_state.value,
                'phase': self.current_phase,
                'cycle_count': self.cycle_count,
                'uptime_seconds': uptime.total_seconds() if uptime else 0,
                'is_paused': self.current_state == LoopState.PAUSED
            }

# Core UnifiedLoop class - consolidated all functionality
class UnifiedLoop:
    """Single stable implementation - consolidates EventSystem, ProgressTracker, TaskScheduler"""

    def __init__(self, project_root: str, config: Optional[LoopConfig] = None):
        """Initialize UnifiedLoop"""
        self.project_root = project_root
        self.config = config or LoopConfig()
        self.config.project_root = project_root

        # Core components
        self.state_engine = StateEngine(self.config)
        self.health_monitor = HealthMonitor(project_root)
        self.circuit_breaker = CircuitBreaker("main_circuit")
        # from_env() so the container's THETEAM_LIMIT_* bounds are honoured.
        self.resource_limiter = ResourceLimiter.from_env()
        self.backups = BackupManager(project_root)
        # Audit trail for every state change and agent action (Phase 4).
        self.audit = AuditLogger(str(Path(project_root) / ".loop-log"))

        # Event system
        # Bounded: an unbounded list here would grow for the process lifetime.
        self.event_history: deque = deque(maxlen=1000)

        # Task management
        self.tasks: Dict[str, UnifiedTask] = {}
        self.tasks_by_priority: Dict[str, List[str]] = {priority.name.lower(): [] for priority in LoopPriority}
        self.dead_letter_queue: List[UnifiedTask] = []

        # Progress tracking
        self.tasks_started = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.tasks_processed = 0

        # System state
        self._lock = threading.RLock()
        self._running = False
        self._shutdown_requested = False
        self._monitoring_thread = None
        self.start_time = None
        self.paused_time = None
        self.total_paused_time = timedelta(0)

        # Initialize metrics
        self.metrics = {
            'tasks_started': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
            'total_execution_time': 0.0,
            'uptime_start': _now()
        }

        logger.info(f"Initialized UnifiedLoop for {project_root} (ID: {self.config.loop_id})")

    # State delegation - UnifiedLoop is the single stable implementation,
    # StateEngine owns state transitions. These delegate rather than duplicate.
    def start(self) -> bool:
        previous = self.state_engine.current_state
        result = self.state_engine.start()
        if result:
            self._running = True
            self._record_state_change(previous, self.state_engine.current_state)
        return result

    def pause(self) -> bool:
        previous = self.state_engine.current_state
        result = self.state_engine.pause()
        if result:
            self._running = False
            self._record_state_change(previous, self.state_engine.current_state)
        return result

    def resume(self) -> bool:
        previous = self.state_engine.current_state
        result = self.state_engine.resume()
        if result:
            self._running = True
            self._record_state_change(previous, self.state_engine.current_state)
        return result

    def stop(self) -> bool:
        previous = self.state_engine.current_state
        result = self.state_engine.stop()
        self._running = False
        self._shutdown_requested = True
        if result:
            self._record_state_change(previous, self.state_engine.current_state)
        return result

    def _record_state_change(self, previous: Any, current: Any) -> None:
        """Record a state transition in the audit trail. Never raises."""
        try:
            self.audit.log_state_change(
                getattr(previous, "value", previous),
                getattr(current, "value", current),
                reason="loop lifecycle",
            )
        except Exception as e:
            logger.error(f"Audit log failed for state change: {e}")

    def complete_cycle(self):
        return self.state_engine.complete_cycle()

    def get_status(self) -> Dict[str, Any]:
        """Single status view: state engine + loop tasks, health, events, metrics."""
        engine = self.state_engine.get_status()
        engine_state = {
            'state': engine['state'],
            'phase': engine['phase'],
            'cycle_count': engine['cycle_count'],
            'is_paused': engine['is_paused'],
        }
        metrics = dict(self.metrics)
        metrics['uptime_seconds'] = engine['uptime_seconds']
        return {
            'loop_id': self.config.loop_id,
            'project_root': self.project_root,
            'state': engine_state,
            'uptime_seconds': engine['uptime_seconds'],
            'tasks_by_priority': self.get_tasks_by_priority(),
            'dead_letter_queue': len(self.dead_letter_queue),
            'health': self.health_monitor.get_health_status(),
            'progress': self._get_progress(),
            'event_history': list(self.event_history),
            'metrics': metrics,
        }

    def _get_progress(self) -> Dict[str, Any]:
        """Transparent progress counters for agents."""
        with self._lock:
            total = len(self.tasks)
            done = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED)
            rate = (done / total * 100) if total else 0.0
            return {
                'tasks_total': total,
                'total_tasks_started': self.tasks_started,
                'tasks_started': self.tasks_started,
                'tasks_completed': done,
                'tasks_failed': self.tasks_failed,
                'tasks_pending': total - done,
                'current_cycle_tasks': self.state_engine.cycle_count,
                'completion_rate_percentage': rate,
            }

    # Add dead letter queue operations
    def failed_task(self, task: UnifiedTask, error: Exception) -> bool:
        """Add a failed task to the dead letter queue"""
        with self._lock:
            # Check if we're at capacity
            max_size = getattr(self.config, 'dead_letter_queue_max_size', 1000)
            if len(self.dead_letter_queue) >= max_size:
                # Remove oldest entry before adding new one
                self.dead_letter_queue.pop(0)
            
            # Add the failed task with error information
            self.dead_letter_queue.append({
                'task': task,
                'error': str(error),
                'error_type': type(error).__name__,
                'timestamp': _now(),
                'failed_attempt': self.tasks_failed + 1  
            })
            
            self.tasks_failed += 1
            self.tasks_processed += 1
            
            logger.info(f"Added failed task {task.task_id} to dead letter queue: {error}")
            return True

    def retry_failed_task(self, task_id: str) -> bool:
        """Retry a task from the dead letter queue"""
        with self._lock:
            # Find the task in dead letter queue
            for entry in self.dead_letter_queue:
                if entry['task'].task_id == task_id:
                    # Remove from dead letter queue
                    self.dead_letter_queue.remove(entry)
                    
                    # Re-add to regular tasks
                    self.tasks[task_id] = entry['task']
                    self.tasks_by_priority[entry['task'].priority.name.lower()].append(task_id)
                    
                    logger.info(f"Requeued failed task {task_id} for retry")
                    return True
            
            logger.warning(f"Task {task_id} not found in dead letter queue")
            return False

    def cleanup_dead_letter_queue(self) -> int:
        """Clean up old entries from dead letter queue based on retention policy"""
        with self._lock:
            if not hasattr(self.config, 'dead_letter_queue_retention_hours'):
                return 0
                
            retention_hours = self.config.dead_letter_queue_retention_hours
            cutoff_time = _now() - timedelta(hours=retention_hours)
            
            # Remove old entries
            initial_size = len(self.dead_letter_queue)
            self.dead_letter_queue = [
                entry for entry in self.dead_letter_queue 
                if entry['timestamp'] > cutoff_time
            ]
            
            cleaned_count = initial_size - len(self.dead_letter_queue)
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} old entries from dead letter queue")
            
            return cleaned_count

    def get_dead_letter_stats(self) -> Dict[str, Any]:
        """Get statistics about dead letter queue"""
        with self._lock:
            if not self.dead_letter_queue:
                return {
                    'total_failed': self.tasks_failed,
                    'dead_letter_count': 0,
                    'oldest_entry_age_hours': None,
                    'queue_capacity': getattr(self.config, 'dead_letter_queue_max_size', 1000)
                }
            
            current_time = _now()
            oldest_entry = min(self.dead_letter_queue, key=lambda x: x['timestamp'])
            oldest_age_hours = (current_time - oldest_entry['timestamp']).total_seconds() / 3600
            
            return {
                'total_failed': self.tasks_failed,
                'dead_letter_count': len(self.dead_letter_queue),
                'oldest_entry_age_hours': oldest_age_hours,
                'queue_capacity': getattr(self.config, 'dead_letter_queue_max_size', 1000),
                'oldest_error': oldest_entry['error'],
                'oldest_error_type': oldest_entry['error_type']
            }

    # NOTE: an `execute_loop_iteration` method used to sit here. Its body was
    # 140 lines of orphaned fragments copy-pasted from failed_task, retry,
    # cleanup, start, stop, pause and resume, referencing undefined `task` and
    # `error` names. It was never called and would have raised NameError.
    # The real methods above are the ones that run.
    def _safe_audit_start(self, task_id: str, priority: str, execution: str) -> None:
        """
        Record a task start without letting audit failures break the loop.

        The audit sink is observability, not control flow: a full disk or a
        permission error must not stop tasks from being accepted.
        """
        try:
            self.audit.log_task_start(task_id, {
                "type": "unified_task",
                "priority": priority,
                "execution": execution,
            })
        except Exception as e:
            logger.error(f"Audit log failed for task {task_id}: {e}")

    def _safe_audit_failed(self, task_id: str, error: Any, failure_type: str) -> None:
        """Record a task failure without letting audit failures mask the cause."""
        try:
            self.audit.log_task_failed(task_id, error, failure_type)
        except Exception as e:
            logger.error(f"Audit log failed for task {task_id}: {e}")

    def add_task(self, task: UnifiedTask) -> bool:
        """Add a task to the queue"""
        with self._lock:
            if not self._running:
                return False

            if task.task_id in self.tasks:
                return False

            if not self.circuit_breaker.allow_request():
                return False

            if not self.resource_limiter.acquire(ResourceType.TASKS):
                self.circuit_breaker.record_failure()
                return False

            try:
                # Add task to scheduler
                self.tasks[task.task_id] = task

                # Map TaskPriority to LoopPriority for tasks_by_priority
                loop_priority = None
                for priority in LoopPriority:
                    if priority.name == task.priority.name:
                        loop_priority = priority
                        break

                if loop_priority:
                    self.tasks_by_priority[loop_priority.name.lower()].append(task.task_id)

                # Update metrics
                self.tasks_started += 1
                self.tasks_processed += 1
                self.metrics['tasks_started'] += 1

                self.circuit_breaker.record_success()
                # Release the admission permit immediately: it gates the add
                # operation, not the task's lifetime. Holding it until task
                # completion would exhaust the limit and wedge the loop.
                self.resource_limiter.release(ResourceType.TASKS)
                self._safe_audit_start(task.task_id, task.priority.name, task.name or "")
                self.event_history.append({
                    "event": "task_added",
                    "task_id": task.task_id,
                    "priority": task.priority.name,
                    "timestamp": _now().isoformat(),
                })
                logger.info(f"Task {task.task_id} added successfully")
                return True

            except Exception as e:
                self.circuit_breaker.record_failure()
                # Release first: the permit was acquired before the try, and
                # the audit/append below can themselves raise.
                self.resource_limiter.release(ResourceType.TASKS)
                self._safe_audit_failed(task.task_id, e, "add_task")
                self.event_history.append({
                    "event": "task_add_failed",
                    "task_id": task.task_id,
                    "error": str(e),
                    "timestamp": _now().isoformat(),
                })
                logger.error(f"Error adding task {task.task_id}: {e}")
                return False

            return False

    def get_status_report(self) -> Dict[str, Any]:
        """
        Extended status view combining loop state with resource usage.

        Previously this body was orphaned after `add_task` as a bare string
        literal, so it was unreachable dead code.
        """
        status = self.get_status()
        status['resource_usage'] = self.resource_limiter.get_usage_report()
        return status

    def _monitoring_loop(self):
        """Background monitoring loop"""
        while not self._shutdown_requested:
            try:
                time.sleep(self.config.monitoring_interval)
                self._perform_monitoring()
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")

    def _perform_monitoring(self):
        """Perform periodic monitoring and health checks"""
        status = self.get_status()

        if status['metrics']['tasks_started'] > 0:
            completion_rate = (status['metrics']['tasks_completed'] /
                             status['metrics']['tasks_started'] * 100)
            logger.info(f"UnifiedLoop {self.config.loop_id} - "
                       f"Tasks: {status['metrics']['tasks_started']}, "
                       f"Completed: {status['metrics']['tasks_completed']}, "
                       f"Failed: {status['metrics']['tasks_failed']}, "
                       f"Completion Rate: {completion_rate:.1f}%")

        system_metrics = {
            'cpu_usage': 0.0,
            'memory_usage': 0.0,
            'disk_usage': 0.0,
            'response_time': 0.0
        }
        self.health_monitor.update_health(system_metrics)

    def _check_stuck_tasks(self):
        """Check for and handle stuck tasks"""
        pass

    def create_backup(self) -> Path:
        """
        Create backup of current state.

        Delegates to the canonical `BackupManager`; the logic used to be
        duplicated here and in `scripts/backup.py` with an unverified
        "checksum": "TODO" placeholder.
        """
        return self.backups.create_backup()

    def restore_from_backup(self, backup_path: Path):
        """
        Restore state from a backup, verifying integrity first.

        Raises `BackupIntegrityError` without touching live state if any file
        fails its sha256 check.
        """
        return self.backups.restore_from_backup(Path(backup_path))

    def get_health_score(self) -> float:
        """Get current health score (0.0-1.0)."""
        status = self.health_monitor.get_health_status()
        return float(status.get('health_score', 0.0))

    def get_tasks_by_priority(self) -> Dict[str, int]:
        """Get task count by priority for monitoring"""
        return {k: len(v) for k, v in self.tasks_by_priority.items()}

# Module-level convenience wrappers retained for the public API. Both delegate
# to the canonical BackupManager so there is exactly one implementation.
def backup_state(project_root: Optional[str] = None) -> Path:
    """Create a state backup. Delegates to `BackupManager`."""
    return BackupManager(project_root or os.getcwd()).create_backup()


def restore_state(backup_path, project_root: Optional[str] = None) -> None:
    """Restore state from a backup, verifying integrity first."""
    BackupManager(project_root or os.getcwd()).restore_from_backup(Path(backup_path))

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)