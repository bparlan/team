#!/usr/bin/env python3
"""
Event Log implementation for theteam.

This module provides Event Sourcing that stores all state changes as immutable events
and enables state reconstruction from the event log.
"""

import os
import json
import hashlib
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple, Callable
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class Event:
    """Immutable event containing state change information."""

    def __init__(self, event_id: str, timestamp: str, event_type: str,
                 data: Dict[str, Any], prev_event_id: Optional[str] = None):
        self.event_id = event_id
        self.timestamp = timestamp
        self.event_type = event_type
        self.data = data
        self.prev_event_id = prev_event_id
        # Compute event hash for integrity verification
        self.event_hash = self._compute_event_hash()

    def _compute_event_hash(self) -> str:
        """Compute hash of the event (excluding previous event ID for chain integrity)."""
        event_data = {
            'event_id': self.event_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'data': self.data
        }
        event_str = json.dumps(event_data, sort_keys=True)
        return hashlib.sha256(event_str.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            'event_id': self.event_id,
            'timestamp': self.timestamp,
            'event_type': self.event_type,
            'data': self.data,
            'prev_event_id': self.prev_event_id,
            'event_hash': self.event_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Event':
        """Create event from dictionary."""
        event = cls(
            event_id=data['event_id'],
            timestamp=data['timestamp'],
            event_type=data['event_type'],
            data=data['data'],
            prev_event_id=data.get('prev_event_id')
        )
        # Verify the stored hash matches computed hash
        if event.event_hash != data.get('event_hash'):
            raise ValueError(f"Event hash mismatch for event {event.event_id}")
        return event

    def verify_integrity(self, all_events: Dict[str, 'Event']) -> Tuple[bool, List[str]]:
        """
        Verify event integrity by checking chain and hash.

        Args:
            all_events: Dictionary of all events indexed by event_id

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Verify event hash
        if self.event_hash != self._compute_event_hash():
            errors.append(f"Event {self.event_id}: Hash verification failed")

        # Verify chain integrity
        if self.prev_event_id and self.prev_event_id not in all_events:
            errors.append(f"Event {self.event_id}: Previous event {self.prev_event_id} not found")

        return len(errors) == 0, errors
class EventLog:
    """
    Event Log for immutable event storage and replay.

    All state changes are stored as immutable events, enabling complete
    state reconstruction and audit trail.
    """

    def __init__(self, event_file: str = "events.jsonl", max_events: int = 100000):
        self.event_file = event_file
        self.max_events = max_events
        self.events_lock = threading.Lock()
        self._ensure_event_directory()
        self._index: Dict[str, Event] = {}  # Event ID to Event mapping
        self._index_lock = threading.Lock()
        self._dirty_index = True

    def _ensure_event_directory(self):
        """Ensure the directory for event file exists."""
        event_dir = os.path.dirname(os.path.abspath(self.event_file))
        if event_dir:
            os.makedirs(event_dir, exist_ok=True)

    def append_event(self, event_type: str, data: Dict[str, Any],
                    prev_event_id: Optional[str] = None) -> str:
        """
        Append a new event to the log.

        Args:
            event_type: Type of event (e.g., 'state_change', 'system_event')
            data: Event data
            prev_event_id: ID of the previous event for chain integrity

        Returns:
            Event ID of the appended event
        """
        event_id = f"{int(time.time() * 1000000)}_{hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()

        event = Event(event_id, timestamp, event_type, data, prev_event_id)

        with self.events_lock:
            # Load existing events
            existing_events = self._load_events()

            # For first event, prev_event_id should be None
            # For subsequent events, verify prev_event_id if provided
            if existing_events and prev_event_id:
                latest_event = existing_events[-1]
                if latest_event.get('event_id') != prev_event_id:
                    logger.warning(f"Event {event_id}: Previous event {prev_event_id} does not match latest event {latest_event.get('event_id')}")

            # Add new event
            existing_events.append(event.to_dict())

            # Trim if necessary
            if len(existing_events) > self.max_events:
                existing_events = existing_events[-self.max_events:]

            # Write to disk
            self._write_events(existing_events)

            # Update index
            self._dirty_index = True

        logger.info(f"Event appended: {event_id} - {event_type}")
        return event_id

    def _load_events(self) -> List[Dict[str, Any]]:
        """Load events from disk."""
        if not os.path.exists(self.event_file):
            return []

        try:
            with open(self.event_file, 'r') as f:
                events = []
                for line in f:
                    line = line.strip()
                    if line:
                        events.append(json.loads(line))
                return events
        except Exception as e:
            logger.error(f"Error loading events: {e}")
            return []

    def _write_events(self, events: List[Dict[str, Any]]):
        """Write events to disk (JSONL format for append efficiency)."""
        try:
            # Write to temporary file first for atomicity
            temp_file = f"{self.event_file}.tmp"
            with open(temp_file, 'w') as f:
                for event in events:
                    f.write(json.dumps(event) + '\n')

            # Atomic rename
            os.replace(temp_file, self.event_file)
        except Exception as e:
            logger.error(f"Error writing events: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")

    def get_event(self, event_id: str) -> Optional[Event]:
        """Get a specific event by ID."""
        with self._index_lock:
            if self._dirty_index:
                self._build_index()
            return self._index.get(event_id)

    def _build_index(self):
        """Build the event index from disk."""
        events = self._load_events()
        self._index.clear()
        for event_data in events:
            try:
                event = Event.from_dict(event_data)
                self._index[event.event_id] = event
            except Exception as e:
                logger.error(f"Error building index for event {event_data.get('event_id', 'unknown')}: {e}")

    def get_events(self, limit: int = 100, event_type: Optional[str] = None) -> List[Event]:
        """
        Get events from the log.

        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type (optional)

        Returns:
            List of events
        """
        with self._index_lock:
            if self._dirty_index:
                self._build_index()

        events = list(self._index.values())

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        # Sort by timestamp (most recent first)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    def replay_events(self, callback: Callable[[Event], None]) -> int:
        """
        Replay events to a callback function.

        Args:
            callback: Function to call for each event

        Returns:
            Number of events replayed
        """
        events = self._load_events()
        count = 0

        for event_data in events:
            try:
                event = Event.from_dict(event_data)
                callback(event)
                count += 1
            except Exception as e:
                logger.error(f"Error replaying event {event_data.get('event_id', 'unknown')}: {e}")

        return count

    def clear_events(self):
        """Clear all events from the log."""
        with self.events_lock:
            try:
                if os.path.exists(self.event_file):
                    os.remove(self.event_file)
                self._index.clear()
                self._dirty_index = True
                logger.info(f"Cleared all events from {self.event_file}")
            except Exception as e:
                logger.error(f"Error clearing events: {e}")

    def close(self):
        """Close the event log."""
        pass
class EventSourcingManager:
    """
    Event Sourcing Manager for theteam.

    Coordinates event storage, state reconstruction, and event processing
    with error handling and recovery capabilities.
    """

    def __init__(self, event_file: str = "events.jsonl", max_events: int = 100000):
        self.event_log = EventLog(event_file, max_events)
        self._event_handlers: Dict[str, List[Callable]] = {}
        self._handlers_lock = threading.Lock()

    def register_event_handler(self, event_type: str, handler: Callable):
        """
        Register a handler for a specific event type.

        Args:
            event_type: Type of event to handle
            handler: Function to call when event occurs
        """
        with self._handlers_lock:
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].append(handler)

    def process_events(self, limit: int = 10) -> int:
        """
        Process pending events with registered handlers.

        Args:
            limit: Maximum number of events to process

        Returns:
            Number of events processed
        """
        events = self.event_log.get_events(limit=limit)
        processed = 0

        for event in events:
            try:
                handlers = self._get_handlers_for_event_type(event.event_type)
                for handler in handlers:
                    handler(event)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing event {event.event_id}: {e}")

        return processed

    def _get_handlers_for_event_type(self, event_type: str) -> List[Callable]:
        """Get handlers for a specific event type."""
        with self._handlers_lock:
            return self._event_handlers.get(event_type, []).copy()

    def get_event_log_stats(self) -> Dict[str, Any]:
        """Get statistics about the event log."""
        events = self.event_log._load_events()
        event_types = {}

        for event_data in events:
            event_type = event_data.get('event_type', 'unknown')
            event_types[event_type] = event_types.get(event_type, 0) + 1

        return {
            'total_events': len(events),
            'max_events': self.event_log.max_events,
            'event_types': event_types,
            'event_file': self.event_log.event_file
        }

    def close(self):
        """Close the event sourcing manager."""
        self.event_log.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()