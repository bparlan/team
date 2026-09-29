#!/usr/bin/env python3
"""
Event Bus for theteam skill enhancement.

Central event system for real-time communication between components.
"""

import json
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Callable, Set
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Import Phase 2 modules for robust event handling
from .event_log import EventLog
from .rate_limiting import EventRateLimiter

class EventType(Enum):
    # UI Events
    UI_UPDATE = "ui_update"
    UI_COMMAND = "ui_command"
    UI_REFRESH = "ui_refresh"

    # Task Stack Events
    TASK_REGISTERED = "task_registered"
    TASK_EXECUTED = "task_executed"
    TASK_SCHEDULED = "task_scheduled"
    TASK_FAILED = "task_failed"

    # System Integration Events
    SYSTEM_ANALYSIS_STARTED = "system_analysis_started"
    SYSTEM_ANALYSIS_COMPLETED = "system_analysis_completed"
    SYSTEM_HEALTH_UPDATED = "system_health_updated"
    SYSTEM_ISSUE_DETECTED = "system_issue_detected"

    # Discussion Events
    DISCUSSION_CREATED = "discussion_created"
    DISCUSSION_UPDATED = "discussion_updated"
    TASK_ASSIGNED = "task_assigned"

    # State Events
    STATE_CHANGED = "state_changed"
    RESOURCE_CONSTRAINT = "resource_constraint"
class Event:
    def __init__(self, event_type: EventType, data: Dict[str, Any], source: str = None):
        self.event_id = f"{int(time.time() * 1000000)}_{str(hash(str(data)))[-8:]}"
        self.event_type = event_type
        self.data = data
        self.source = source
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.sequence_id = f"{self.event_type.value}_{self.event_id}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'data': self.data,
            'source': self.source,
            'timestamp': self.timestamp,
            'sequence_id': self.sequence_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        event = cls(
            event_type=EventType(data['event_type']),
            data=data['data'],
            source=data.get('source')
        )
        event.event_id = data['event_id']
        event.timestamp = data['timestamp']
        event.sequence_id = data.get('sequence_id')
        return event

    def to_log_dict(self) -> Dict[str, Any]:
        return {
            'event_id': self.event_id,
            'event_type': self.event_type.value,
            'data': self.data,
            'source': self.source,
            'timestamp': self.timestamp,
            'sequence_id': self.sequence_id
        }
class EventBus:
    def __init__(self, event_log_path: str = None):
        self.event_log = EventLog(event_file=event_log_path or "events.jsonl", max_events=100000)
        self.listeners: Dict[EventType, List[Callable]] = {}
        self.queue_lock = threading.RLock()
        self.listeners_lock = threading.RLock()
        self.event_queue: List[Event] = []
        self.should_exit = False
        self.event_processor_thread = None

        # Dead-letter queue for failed event processing
        self.dead_letter_queue: List[Dict[str, Any]] = []
        self.dead_letter_max_size: int = 1000
        self.dead_letter_retention_hours: int = 168  # 7 days

        # Event retention policies
        self.event_retention_hours: int = 720  # 30 days
        self._cleanup_interval: int = 3600  # 1 hour

    def emit_event(self, event_type: EventType, data: Dict[str, Any], source: str = None):
        """Emit a new event to the bus."""
        event = Event(event_type, data, source)
        self._process_event(event)
        return event

    def subscribe(self, event_type: EventType, callback: Callable):
        """Subscribe to events of a specific type."""
        with self.listeners_lock:
            if event_type not in self.listeners:
                self.listeners[event_type] = []
            self.listeners[event_type].append(callback)
            logger.debug(f"Subscribed callback for {event_type.value} events")

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """Unsubscribe a callback from events of a specific type."""
        with self.listeners_lock:
            if event_type in self.listeners:
                try:
                    self.listeners[event_type].remove(callback)
                    logger.debug(f"Unsubscribed callback for {event_type.value} events")
                except ValueError:
                    pass

    def _process_event(self, event: Event):
        """Process an event by logging it and notifying listeners."""
        try:
            # Log the event
            event_dict = event.to_log_dict()
            self.event_log.append_event(
                event_type=event.event_type.value,
                data=event_dict,
                prev_event_id=event.sequence_id
            )

            # Notify all listeners
            with self.listeners_lock:
                event_type = event.event_type
                listeners = self.listeners.get(event_type, []).copy()

            for callback in listeners:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"Error in event listener for {event_type.value}: {e}")
                    # Add to dead-letter queue
                    self._add_to_dead_letter(event, str(e))

        except Exception as e:
            logger.error(f"Error processing event {event.event_type.value}: {e}")
            # Add to dead-letter queue for processing failures
            self._add_to_dead_letter(event, str(e))

    def _add_to_dead_letter(self, event: Event, error: str) -> None:
        """Add a failed event to the dead-letter queue."""
        dead_letter_entry = {
            'event': event.to_dict(),
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        with self.queue_lock:
            if len(self.dead_letter_queue) >= self.dead_letter_max_size:
                self.dead_letter_queue.pop(0)
            self.dead_letter_queue.append(dead_letter_entry)

    def get_dead_letter_queue(self) -> List[Dict[str, Any]]:
        """Get current dead-letter queue entries."""
        return self.dead_letter_queue.copy()

    def cleanup_dead_letter_queue(self) -> int:
        """Clean up old entries from dead-letter queue."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.dead_letter_retention_hours)
        initial = len(self.dead_letter_queue)
        self.dead_letter_queue = [
            e for e in self.dead_letter_queue
            if datetime.fromisoformat(e['timestamp']) > cutoff
        ]
        return initial - len(self.dead_letter_queue)

    def start_cleanup_threads(self):
        """Start background cleanup threads."""
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="EventBusCleanup"
        )
        self.cleanup_thread.start()
        logger.info("EventBus cleanup thread started")

    def _cleanup_loop(self):
        """Background cleanup loop."""
        while not self.should_exit:
            try:
                self._cleanup_old_events()
                time.sleep(self._cleanup_interval)
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                time.sleep(60)

    def _cleanup_old_events(self):
        """Clean up old events from the event log."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.event_retention_hours)
        events = self.event_log._load_events()
        initial_count = len(events)
        events = [e for e in events
                  if datetime.fromisoformat(e['timestamp']) > cutoff]

        if len(events) != initial_count:
            # Clean up temp file and write remaining events
            temp_file = f"{self.event_log.event_file}.tmp"
            try:
                with open(temp_file, 'w') as f:
                    for event in events:
                        f.write(json.dumps(event) + '\n')
                os.replace(temp_file, self.event_log.event_file)
                logger.info(f"Cleaned up {initial_count - len(events)} old events")
            except Exception as e:
                logger.error(f"Error cleaning up events: {e}")
                if os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError as e:
                        logger.warning(f"Failed to clean up temp file {temp_file}: {e}")

    def get_events(self, event_type: EventType = None, limit: int = 100) -> List[Event]:
        """Get events from the log."""
        events = self.event_log._load_events()

        if event_type:
            events = [e for e in events if e['event_type'] == event_type.value]

        # Convert to Event objects
        event_objects = [Event.from_dict(e) for e in events[-limit:]]
        return event_objects
    def start_event_processor(self):
        """Start background event processor."""
        if self.event_processor_thread is None:
            self.event_processor_thread = threading.Thread(
                target=self._event_processor_loop,
                daemon=True,
                name="EventProcessor"
            )
            self.event_processor_thread.start()
            logger.info("Event processor started")

    def stop_event_processor(self):
        """Stop background event processor."""
        self.should_exit = True
        if self.event_processor_thread:
            self.event_processor_thread.join(timeout=5)
            self.event_processor_thread = None
            logger.info("Event processor stopped")

    def _event_processor_loop(self):
        """Background event processor loop."""
        while not self.should_exit:
            try:
                with self.queue_lock:
                    if self.event_queue:
                        # Process all queued events
                        while self.event_queue:
                            event = self.event_queue.pop(0)
                            self._process_event(event)

                time.sleep(0.1)  # Small delay to prevent busy waiting

            except Exception as e:
                logger.error(f"Error in event processor loop: {e}")
                time.sleep(1)

    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        events = self.event_log._load_events()
        event_counts = {}

        for event in events:
            event_type = event['event_type']
            event_counts[event_type] = event_counts.get(event_type, 0) + 1

        return {
            'total_events': len(events),
            'event_counts': event_counts,
            'listeners': {event_type.value: len(listeners) for event_type, listeners in self.listeners.items()},
            'queue_size': len(self.event_queue),
            'dead_letter_queue_size': len(self.dead_letter_queue)
        }

    def stop(self):
        """Stop the event bus."""
        self.should_exit = True
        self.stop_event_processor()
        if hasattr(self, 'cleanup_thread'):
            self.cleanup_thread.join(timeout=5)
if __name__ == "__main__":
    # Example usage
    event_bus = EventBus()

    def sample_callback(event):
        print(f"Received event: {event.event_type.value}")

    event_bus.subscribe(EventType.UI_UPDATE, sample_callback)

    print("EventBus example - emitting events...")
    event_bus.emit_event(EventType.UI_UPDATE, {"message": "Test update"})
    event_bus.emit_event(EventType.TASK_EXECUTED, {"task_id": "task123"})

    print("\nEventBus stats:", event_bus.get_stats())

    # Start cleanup threads
    event_bus.start_cleanup_threads()

    event_bus.stop()