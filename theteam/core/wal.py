#!/usr/bin/env python3
"""
Write-Ahead Logging (WAL) implementation for theteam.

This module provides Write-Ahead Logging that ensures all state changes are
always logged to disk before being applied to the actual state.
WAL entries include timestamp, operation, and data hash for integrity.
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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WALEntry:
    """Write-Ahead Log entry containing state change information."""

    def __init__(self, entry_id: str, timestamp: str, operation: str,
                 data: Dict[str, Any], data_hash: str):
        self.entry_id = entry_id
        self.timestamp = timestamp
        self.operation = operation
        self.data = data
        self.data_hash = data_hash

    def to_dict(self) -> Dict[str, Any]:
        """Convert WAL entry to dictionary for serialization."""
        return {
            'entry_id': self.entry_id,
            'timestamp': self.timestamp,
            'operation': self.operation,
            'data': self.data,
            'data_hash': self.data_hash
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WALEntry':
        """Create WAL entry from dictionary."""
        return cls(
            entry_id=data['entry_id'],
            timestamp=data['timestamp'],
            operation=data['operation'],
            data=data['data'],
            data_hash=data['data_hash']
        )

    def compute_data_hash(self) -> str:
        """Compute hash of the data portion."""
        data_str = json.dumps(self.data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    def verify_data_hash(self) -> bool:
        """Verify data hash integrity."""
        return self.compute_data_hash() == self.data_hash
class WriteAheadLog:
    """
    Write-Ahead Log implementation for immutable entry storage and replay.

    All state changes are logged before being applied to the actual state,
    ensuring durability and consistency.
    """

    def __init__(self, wal_file: str = "wal.json", max_entries: int = 100000):
        self.wal_file = wal_file
        self.max_entries = max_entries
        self.entries_lock = threading.Lock()
        self._ensure_wal_directory()
        self._index: Dict[str, WALEntry] = {}  # Entry ID to WALEntry mapping
        self._index_lock = threading.Lock()
        self._dirty_index = True

    def _ensure_wal_directory(self):
        """Ensure the directory for WAL file exists."""
        wal_dir = os.path.dirname(os.path.abspath(self.wal_file))
        if wal_dir:
            os.makedirs(wal_dir, exist_ok=True)

    def append_entry(self, operation: str, data: Dict[str, Any]) -> str:
        """
        Append a new WAL entry.

        Args:
            operation: Type of operation (e.g., 'insert', 'update', 'delete')
            data: Data associated with the operation

        Returns:
            Entry ID of the appended entry
        """
        entry_id = f"{int(time.time() * 1000000)}_{hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        data_hash = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

        entry = WALEntry(entry_id, timestamp, operation, data, data_hash)

        with self.entries_lock:
            # Load existing entries
            existing_entries = self._load_entries()

            # Add new entry
            existing_entries.append(entry.to_dict())

            # Trim if necessary
            if len(existing_entries) > self.max_entries:
                existing_entries = existing_entries[-self.max_entries:]

            # Write to disk
            self._write_entries(existing_entries)

            # Update index
            self._dirty_index = True

        logger.info(f"WAL entry appended: {entry_id} - {operation}")
        return entry_id

    def _load_entries(self) -> List[Dict[str, Any]]:
        """Load WAL entries from disk."""
        if not os.path.exists(self.wal_file):
            return []

        try:
            with open(self.wal_file, 'r') as f:
                entries = []
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))
                return entries
        except Exception as e:
            logger.error(f"Error loading WAL entries: {e}")
            return []

    def _write_entries(self, entries: List[Dict[str, Any]]):
        """Write WAL entries to disk (JSONL format for append efficiency)."""
        try:
            # Write to temporary file first for atomicity
            temp_file = f"{self.wal_file}.tmp"
            with open(temp_file, 'w') as f:
                for entry in entries:
                    f.write(json.dumps(entry) + '\n')

            # Atomic rename
            os.replace(temp_file, self.wal_file)
        except Exception as e:
            logger.error(f"Error writing WAL entries: {e}")
            # Clean up temp file if it exists
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")

    def get_entry(self, entry_id: str) -> Optional[WALEntry]:
        """Get a specific WAL entry by ID."""
        with self._index_lock:
            if self._dirty_index:
                self._build_index()
            return self._index.get(entry_id)

    def _build_index(self):
        """Build the WAL index from disk."""
        entries = self._load_entries()
        self._index.clear()
        for entry_data in entries:
            try:
                entry = WALEntry.from_dict(entry_data)
                self._index[entry.entry_id] = entry
            except Exception as e:
                logger.error(f"Error building index for entry {entry_data.get('entry_id', 'unknown')}: {e}")

    def get_entries(self, limit: int = 100) -> List[WALEntry]:
        """
        Get WAL entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of WAL entries
        """
        with self._index_lock:
            if self._dirty_index:
                self._build_index()

        entries = list(self._index.values())

        # Sort by timestamp (most recent first)
        entries.sort(key=lambda e: e.timestamp, reverse=True)

        return entries[:limit]

    def replay_entries(self) -> List[Dict[str, Any]]:
        """
        Replay all WAL entries for recovery.

        Returns:
            List of WAL entries in chronological order
        """
        entries = self._load_entries()

        # Sort by timestamp (oldest first for replay)
        entries.sort(key=lambda e: e['timestamp'])

        return entries

    def close(self):
        """Close the WAL."""
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
class StateWALManager:
    """
    State WAL Manager for theteam.

    Coordinates WAL storage, state reconstruction, and entry processing
    with error handling and recovery capabilities.
    """

    def __init__(self, wal_file: str = "wal.json", max_entries: int = 100000):
        self.wal = WriteAheadLog(wal_file, max_entries)
        self._operation_handlers: Dict[str, List[Callable]] = {}
        self._handlers_lock = threading.Lock()

    def register_operation_handler(self, operation: str, handler: Callable):
        """
        Register a handler for a specific operation.

        Args:
            operation: Type of operation (e.g., 'insert', 'update', 'delete')
            handler: Function to call when operation occurs
        """
        with self._handlers_lock:
            if operation not in self._operation_handlers:
                self._operation_handlers[operation] = []
            self._operation_handlers[operation].append(handler)

    def process_entries(self, limit: int = 10) -> int:
        """
        Process pending WAL entries with registered handlers.

        Args:
            limit: Maximum number of entries to process

        Returns:
            Number of entries processed
        """
        entries = self.wal.get_entries(limit=limit)
        processed = 0

        for entry in entries:
            try:
                handlers = self._get_handlers_for_operation(entry.operation)
                for handler in handlers:
                    handler(entry)
                processed += 1
            except Exception as e:
                logger.error(f"Error processing WAL entry {entry.entry_id}: {e}")

        return processed

    def _get_handlers_for_operation(self, operation: str) -> List[Callable]:
        """Get handlers for a specific operation."""
        with self._handlers_lock:
            return self._operation_handlers.get(operation, []).copy()

    def get_wal_stats(self) -> Dict[str, Any]:
        """Get statistics about the WAL."""
        entries = self.wal._load_entries()
        operations = {}

        for entry_data in entries:
            operation = entry_data.get('operation', 'unknown')
            operations[operation] = operations.get(operation, 0) + 1

        return {
            'total_entries': len(entries),
            'max_entries': self.wal.max_entries,
            'operations': operations,
            'wal_file': self.wal.wal_file
        }

    def close(self):
        """Close the WAL manager."""
        self.wal.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()