#!/usr/bin/env python3
"""
Circuit Breaker implementation for theteam.

This module provides circuit breaker functionality to prevent cascading failures
by monitoring health scores and automatically recovering with backoff.
"""

import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import logging
from dataclasses import dataclass

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker state enumerator."""
    CLOSED = "closed"          # Normal operation, requests allowed
    OPEN = "open"              # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"    # Testing recovery, limited requests allowed
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: int = 60,
                 health_score_threshold: float = 0.7,
                 max_requests_in_half_open: int = 3,
                 backoff_multiplier: float = 2.0,
                 max_backoff: int = 300,
                 history_retention_hours: int = 168):  # 7 days
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.health_score_threshold = health_score_threshold
        self.max_requests_in_half_open = max_requests_in_half_open
        self.backoff_multiplier = backoff_multiplier
        self.max_backoff = max_backoff
        self.history_retention_hours = history_retention_hours
@dataclass
class CircuitBreakerStats:
    """Circuit breaker statistics."""
    state: CircuitState
    failure_count: int = 0
    success_count: int = 0
    total_requests: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    recovery_deadline: Optional[datetime] = None
    requests_in_half_open: int = 0
    backoff_timeout: int = 0
class CircuitBreaker:
    """Health-score-driven circuit breaker to prevent cascading failures."""

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats(state=CircuitState.CLOSED)
        self._lock = threading.RLock()
        self._health_score_callback = None
        self._on_state_change_callback = None
        self._request_history: List[Dict[str, Any]] = []
        self._max_history = 1000
        self._running = True

    def set_health_score_callback(self, callback: Callable[[], float]) -> None:
        """Set callback to get current health score for health-based tripping."""
        self._health_score_callback = callback

    def set_on_state_change_callback(self, callback: Callable[[CircuitState, CircuitState], None]) -> None:
        """Set callback to be notified when circuit state changes."""
        self._on_state_change_callback = callback

    def _update_stats(self, success: bool) -> None:
        """Update circuit breaker statistics."""
        with self._lock:
            self.stats.total_requests += 1
            self.stats.last_failure_time = datetime.now(timezone.utc) if not success else None
            self.stats.last_success_time = datetime.now(timezone.utc) if success else None

            if success:
                self.stats.success_count += 1
                self.stats.consecutive_failures = 0
            else:
                self.stats.failure_count += 1
                self.stats.consecutive_failures += 1

            # Record request for history
            self._request_history.append({
                'timestamp': datetime.now(timezone.utc),
                'success': success,
                'state': self.stats.state.value
            })

            # Maintain history size
            if len(self._request_history) > self._max_history:
                self._request_history = self._request_history[-self._max_history:]
            self._evaluate_state()

    def _transition_to(self, new_state: CircuitState) -> bool:
        """Move to a new state, firing the change callback. Returns True if moved."""
        previous = self.stats.state
        if previous == new_state:
            return False
        self.stats.state = new_state
        logger.info(
            f"CircuitBreaker '{self.name}': {previous.value} -> {new_state.value}"
        )
        callback = self._on_state_change_callback
        if callback is not None:
            try:
                callback(previous, new_state)
            except Exception as e:
                logger.error(f"State change callback failed for '{self.name}': {e}")
        return True

    def _recovery_deadline(self) -> datetime:
        """When an OPEN breaker becomes eligible to probe again."""
        timeout = self.config.recovery_timeout
        if self.stats.backoff_timeout:
            timeout = self.stats.backoff_timeout
        return datetime.now(timezone.utc) + timedelta(seconds=timeout)

    def _evaluate_state(self) -> None:
        """
        Drive the state machine after a recorded outcome.

        CLOSED -> OPEN on consecutive failure threshold, or when a health-score
        callback reports a score below the configured floor. OPEN -> HALF_OPEN
        once the recovery deadline passes. HALF_OPEN -> CLOSED after enough
        consecutive successes, or back to OPEN on a single failure.
        """
        state = self.stats.state
        threshold = max(1, self.config.failure_threshold)

        if state == CircuitState.CLOSED:
            tripped = self.stats.consecutive_failures >= threshold
            if not tripped and self._health_score_callback is not None:
                try:
                    score = float(self._health_score_callback())
                    tripped = score < self.config.health_score_threshold
                except Exception as e:
                    logger.debug(f"Health score callback failed for '{self.name}': {e}")
            if tripped:
                self.stats.recovery_deadline = self._recovery_deadline()
                self.stats.requests_in_half_open = 0
                self._transition_to(CircuitState.OPEN)
            return

        if state == CircuitState.OPEN:
            deadline = self.stats.recovery_deadline
            if deadline and datetime.now(timezone.utc) >= deadline:
                self.stats.requests_in_half_open = 0
                self._transition_to(CircuitState.HALF_OPEN)
            return

        if state == CircuitState.HALF_OPEN:
            if self.stats.consecutive_failures > 0:
                # A failed probe re-opens and doubles the backoff.
                base = self.stats.backoff_timeout or self.config.recovery_timeout or 1
                self.stats.backoff_timeout = min(
                    self.config.max_backoff,
                    base * self.config.backoff_multiplier,
                )
                self.stats.recovery_deadline = self._recovery_deadline()
                self.stats.requests_in_half_open = 0
                self._transition_to(CircuitState.OPEN)
            elif self.stats.consecutive_failures == 0 and self.stats.requests_in_half_open > 0:
                self.stats.backoff_timeout = 0
                self.stats.recovery_deadline = None
                self._transition_to(CircuitState.CLOSED)

    def cleanup_history(self) -> int:
        """Clean up old request history based on retention policy."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.config.history_retention_hours)
        initial = len(self._request_history)
        self._request_history = [
            entry for entry in self._request_history
            if datetime.fromisoformat(entry['timestamp'].isoformat()) > cutoff
        ]
        cleaned_count = initial - len(self._request_history)
        if cleaned_count > 0:
            logger.debug(f"CircuitBreaker '{self.name}': Cleaned up {cleaned_count} old history entries")
        return cleaned_count

    def start_cleanup_thread(self) -> None:
        """Start background thread for periodic history cleanup."""
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name=f"CircuitBreakerCleanup-{self.name}"
        )
        self._cleanup_thread.start()
        logger.info(f"CircuitBreaker '{self.name}': Cleanup thread started")

    def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while self._running:
            try:
                self.cleanup_history()
                time.sleep(3600)  # Run cleanup every hour
            except Exception as e:
                logger.error(f"Error in CircuitBreaker '{self.name}' cleanup loop: {e}")
                time.sleep(300)  # Wait 5 minutes before retry

    def stop_cleanup(self) -> None:
        """Stop the cleanup thread."""
        self._running = False
        if hasattr(self, '_cleanup_thread'):
            self._cleanup_thread.join(timeout=5)
            logger.info(f"CircuitBreaker '{self.name}': Cleanup thread stopped")

    def get_request_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent request history."""
        with self._lock:
            return self._request_history[-limit:]

    def is_closed(self) -> bool:
        """Check if circuit is closed."""
        return self.stats.state == CircuitState.CLOSED

    def is_open(self) -> bool:
        """Check if circuit is open."""
        return self.stats.state == CircuitState.OPEN

    def is_half_open(self) -> bool:
        """Check if circuit is half-open."""
        return self.stats.state == CircuitState.HALF_OPEN

    def record_success(self) -> None:
        """Record a successful request."""
        self._update_stats(success=True)

    def record_failure(self) -> None:
        """Record a failed request."""
        self._update_stats(success=False)

    def allow_request(self) -> bool:
        """Gate a request on circuit state.

        Returns True when the circuit permits the request (closed, or half-open
        admitting a probe). Callers must pair a granted request with
        record_success() or record_failure().
        """
        with self._lock:
            # An OPEN breaker blocks everything; the deadline check also lets
            # an elapsed recovery window admit a probe.
            if self.is_open():
                self._evaluate_state()
                if self.is_open():
                    return False
            if self.is_half_open():
                if self.stats.requests_in_half_open >= self.config.max_requests_in_half_open:
                    return False
                self.stats.requests_in_half_open += 1
            return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_cleanup()