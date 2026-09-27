#!/usr/bin/env python3
"""
Rate limiting implementation for theteam.

This module provides event rate limiting to prevent event storms,
ensuring system stability under high load.
"""

import time
import threading
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Set, Callable
from collections import defaultdict, deque
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class RateLimitError(Exception):
    """Exception raised when rate limits are exceeded."""
    pass
class RateLimitWindow:
    """
    Rate limiting window for tracking event counts.

    Tracks events within a sliding time window to enforce rate limits.
    """

    def __init__(self, window_size: int, max_events: int):
        self.window_size = window_size  # Time window size in seconds
        self.max_events = max_events    # Maximum events allowed in window
        self.events: deque[Tuple[float, str]] = deque()  # (timestamp, event_type)
        self._lock = threading.RLock()

    def add_event(self, event_type: str) -> bool:
        """
        Add an event to the rate limiting window.

        Args:
            event_type: Type of event being added

        Returns:
            True if event was added, False if it would exceed rate limit
        """
        current_time = time.time()

        with self._lock:
            # Remove events outside the window
            while self.events and current_time - self.events[0][0] > self.window_size:
                self.events.popleft()

            # Check if adding this event would exceed the limit
            if len(self.events) >= self.max_events:
                logger.warning(f"Rate limit exceeded for event type '{event_type}': "
                            f"{len(self.events)} events in {self.window_size}s window")
                return False

            # Add the event
            self.events.append((current_time, event_type))
            return True

    def get_event_count(self) -> int:
        """Get number of events in current window."""
        current_time = time.time()

        with self._lock:
            # Remove events outside the window
            while self.events and current_time - self.events[0][0] > self.window_size:
                self.events.popleft()

            return len(self.events)

    def get_event_types(self) -> Set[str]:
        """Get unique event types in current window."""
        current_time = time.time()

        with self._lock:
            # Remove events outside the window
            while self.events and current_time - self.events[0][0] > self.window_size:
                self.events.popleft()

            return {event_type for _, event_type in self.events}

    def clear(self):
        """Clear all events from the window."""
        with self._lock:
            self.events.clear()

    def get_window_stats(self) -> Dict[str, Any]:
        """Get window statistics."""
        current_time = time.time()

        with self._lock:
            # Remove events outside the window
            while self.events and current_time - self.events[0][0] > self.window_size:
                self.events.popleft()

            event_types = defaultdict(int)
            for _, event_type in self.events:
                event_types[event_type] += 1

            return {
                'window_size': self.window_size,
                'max_events': self.max_events,
                'current_events': len(self.events),
                'event_types': dict(event_types)
            }
class RateLimitConfig:
    """
    Rate limiting configuration.

    Defines rate limits for different components and operations.
    """

    def __init__(self):
        # Default rate limits
        self.default_window_size = 60  # 1 minute
        self.default_max_events = 100  # 100 events per minute

        # Component-specific rate limits
        self.component_limits = {
            'state_change': {
                'window_size': 60,
                'max_events': 200
            },
            'system_event': {
                'window_size': 60,
                'max_events': 50
            },
            'discussion': {
                'window_size': 60,
                'max_events': 30
            },
            'task': {
                'window_size': 60,
                'max_events': 100
            },
            'health_check': {
                'window_size': 30,
                'max_events': 10
            },
            'user_interaction': {
                'window_size': 60,
                'max_events': 1000
            },
            'event': {
                'window_size': 60,
                'max_events': 200
            },
            'wal': {
                'window_size': 60,
                'max_events': 500
            }
        }

    def get_limit(self, event_type: str) -> Tuple[int, int]:
        """
        Get rate limit for event type.

        Args:
            event_type: Event type to get limit for

        Returns:
            Tuple of (window_size, max_events)
        """
        if event_type in self.component_limits:
            config = self.component_limits[event_type]
            return config['window_size'], config['max_events']

        # Return default limits
        return self.default_window_size, self.default_max_events

    def add_component_limit(self, event_type: str, window_size: int, max_events: int):
        """
        Add rate limit for component.

        Args:
            event_type: Event type to configure
            window_size: Time window size in seconds
            max_events: Maximum events allowed in window
        """
        self.component_limits[event_type] = {
            'window_size': window_size,
            'max_events': max_events
        }

    def remove_component_limit(self, event_type: str):
        """
        Remove rate limit for component.

        Args:
            event_type: Event type to remove
        """
        self.component_limits.pop(event_type, None)

    def get_all_limits(self) -> Dict[str, Dict[str, int]]:
        """Get all rate limits."""
        return self.component_limits.copy()
class EventRateLimiter:
    """
    Event rate limiter for preventing event storms.

    Enforces rate limits on events and provides detailed metrics
    and alerting for rate limit violations.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self.rate_limiters: Dict[str, RateLimitWindow] = {}
        self.rate_limiters_lock = threading.RLock()
        self.violation_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._cleanup_thread = None
        self._cleanup_running = False

    def check_event(self, event_type: str, correlation_id: Optional[str] = None,
                   event_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        window_size, max_events = self.config.get_limit(event_type)

        with self.rate_limiters_lock:
            if event_type not in self.rate_limiters:
                self.rate_limiters[event_type] = RateLimitWindow(window_size, max_events)
            else:
                # Check if limit configuration has changed
                limiter = self.rate_limiters[event_type]
                if limiter.window_size != window_size or limiter.max_events != max_events:
                    # Create new limiter with updated configuration
                    self.rate_limiters[event_type] = RateLimitWindow(window_size, max_events)
                    limiter = self.rate_limiters[event_type]

            # Try to add event
            can_process = limiter.add_event(event_type)
            current_count = limiter.get_event_count()

        metadata = {
            "event_type": event_type,
            "window_size": window_size,
            "max_events": max_events,
            "current_count": current_count,
            "can_process": can_process,
            "correlation_id": correlation_id,
            "event_data": event_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if not can_process:
            self._handle_rate_limit_violation(event_type, metadata)

        return can_process, metadata
    def add_violation_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Add callback for rate limit violations.

        Args:
            callback: Callback function
        """
        self.violation_callbacks.append(callback)

    def _handle_rate_limit_violation(self, event_type: str, metadata: Dict[str, Any]):
        """
        Handle rate limit violation.

        Args:
            event_type: Event type that exceeded rate limit
            metadata: Violation metadata
        """
        logger.warning(f"Rate limit violation for event type '{event_type}': "
                      f"{metadata['current_count']} events in {metadata['window_size']}s window")

        # Call violation callbacks
        for callback in self.violation_callbacks:
            try:
                callback(event_type, metadata)
            except Exception as e:
                logger.error(f"Error in rate limit violation callback: {e}")

    def get_rate_limit_stats(self, event_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get rate limit statistics.

        Args:
            event_type: Optional event type (returns all if None)

        Returns:
            Dictionary with rate limit statistics
        """
        with self.rate_limiters_lock:
            if event_type:
                if event_type in self.rate_limiters:
                    stats = self.rate_limiters[event_type].get_window_stats()
                    stats['event_type'] = event_type
                    return stats
                else:
                    return {'event_type': event_type, 'error': 'Event type not found'}
            else:
                # Return stats for all event types
                all_stats = {}
                for event_type, limiter in self.rate_limiters.items():
                    all_stats[event_type] = limiter.get_window_stats()

                return {
                    'total_event_types': len(self.rate_limiters),
                    'event_types': all_stats
                }

    def reset_rate_limit(self, event_type: str):
        """
        Reset rate limit for event type.

        Args:
            event_type: Event type to reset
        """
        with self.rate_limiters_lock:
            if event_type in self.rate_limiters:
                self.rate_limiters[event_type].clear()
                logger.info(f"Reset rate limit for event type '{event_type}'")

    def get_component_limits(self) -> Dict[str, Dict[str, int]]:
        """Get component rate limits."""
        return self.config.get_all_limits()

    def update_component_limit(self, event_type: str, window_size: int, max_events: int):
        """
        Update rate limit for component.

        Args:
            event_type: Event type to update
            window_size: New time window size in seconds
            max_events: New maximum events
        """
        self.config.add_component_limit(event_type, window_size, max_events)

        # Update existing limiter if it exists
        with self.rate_limiters_lock:
            if event_type in self.rate_limiters:
                self.rate_limiters[event_type] = RateLimitWindow(window_size, max_events)

    def start_cleanup_thread(self):
        """Start cleanup thread for old rate limiters."""
        if self._cleanup_running:
            return

        self._cleanup_running = True

        def cleanup():
            while self._cleanup_running:
                try:
                    self._cleanup_old_limiters()
                    time.sleep(300)  # Run every 5 minutes
                except Exception as e:
                    logger.error(f"Error in rate limit cleanup thread: {e}")
                    time.sleep(300)

        self._cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        self._cleanup_thread.start()
        logger.info("Rate limit cleanup thread started")

    def _cleanup_old_limiters(self):
        """Clean up rate limiters with no recent activity."""
        current_time = time.time()
        to_remove = []

        with self.rate_limiters_lock:
            for event_type, limiter in self.rate_limiters.items():
                # Check if limiter has been inactive for a while
                stats = limiter.get_window_stats()
                if stats['current_events'] == 0:
                    to_remove.append(event_type)

            # Remove inactive limiters
            for event_type in to_remove:
                del self.rate_limiters[event_type]
                logger.debug(f"Removed inactive rate limiter for event type '{event_type}'")

    def stop_cleanup_thread(self):
        """Stop cleanup thread."""
        self._cleanup_running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=10)
            self._cleanup_thread = None
            logger.info("Rate limit cleanup thread stopped")

    def close(self):
        """Close rate limiter."""
        self.stop_cleanup_thread()
        with self.rate_limiters_lock:
            self.rate_limiters.clear()
class EventRateLimitingManager:
    """
    Event rate limiting manager that coordinates all rate limiting operations.

    Provides unified interface for rate limiting configuration,
    monitoring, and control.
    """

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self.rate_limiter = EventRateLimiter(self.config)

    def check_event(self, event_type: str, correlation_id: Optional[str] = None,
                   event_data: Optional[Dict[str, Any]] = None) -> Tuple[bool, Dict[str, Any]]:
        window_size, max_events = self.config.get_limit(event_type)

        with self.rate_limiters_lock:
            if event_type not in self.rate_limiters:
                self.rate_limiters[event_type] = RateLimitWindow(window_size, max_events)
            else:
                # Check if limit configuration has changed
                limiter = self.rate_limiters[event_type]
                if limiter.window_size != window_size or limiter.max_events != max_events:
                    # Create new limiter with updated configuration
                    self.rate_limiters[event_type] = RateLimitWindow(window_size, max_events)
                    limiter = self.rate_limiters[event_type]

            # Try to add event
            can_process = limiter.add_event(event_type)
            current_count = limiter.get_event_count()

        metadata = {
            "event_type": event_type,
            "window_size": window_size,
            "max_events": max_events,
            "current_count": current_count,
            "can_process": can_process,
            "correlation_id": correlation_id,
            "event_data": event_data,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if not can_process:
            self._handle_rate_limit_violation(event_type, metadata)

        return can_process, metadata
    def add_violation_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add callback for rate limit violations."""
        self.rate_limiter.add_violation_callback(callback)

    def get_rate_limit_stats(self, event_type: Optional[str] = None) -> Dict[str, Any]:
        """Get rate limit statistics."""
        return self.rate_limiter.get_rate_limit_stats(event_type)

    def reset_rate_limit(self, event_type: str):
        """Reset rate limit for event type."""
        self.rate_limiter.reset_rate_limit(event_type)

    def get_component_limits(self) -> Dict[str, Dict[str, int]]:
        """Get component rate limits."""
        return self.rate_limiter.get_component_limits()

    def update_component_limit(self, event_type: str, window_size: int, max_events: int):
        """
        Update rate limit for component.

        Args:
            event_type: Event type to update
            window_size: New time window size in seconds
            max_events: New maximum events
        """
        self.rate_limiter.update_component_limit(event_type, window_size, max_events)

    def start_cleanup_thread(self):
        """Start cleanup thread."""
        self.rate_limiter.start_cleanup_thread()

    def stop_cleanup_thread(self):
        """Stop cleanup thread."""
        self.rate_limiter.stop_cleanup_thread()

    def close(self):
        """Close rate limiting manager."""
        self.rate_limiter.close()