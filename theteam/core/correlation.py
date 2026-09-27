#!/usr/bin/env python3
"""
Correlation ID implementation for theteam.

This module provides correlation ID functionality for structured observability,
ensuring all operations can be traced and correlated across components.
"""

import uuid
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Set
from collections import defaultdict
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class CorrelationError(Exception):
    """Exception raised for correlation ID errors."""
    pass
class CorrelationState(str, Enum):
    """Correlation state enumerator."""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
class CorrelationContext:
    """
    Correlation context for tracking operations across components.

    Provides thread-safe correlation ID management with propagation
    across system boundaries.
    """

    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or str(uuid.uuid4())
        self.parent_correlation_id = None
        self.operation_name = ""
        self.component = ""
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.state = CorrelationState.ACTIVE
        self.tags: Dict[str, Any] = {}
        self.metadata: Dict[str, Any] = {}
        self._local_data: Dict[str, Any] = {}
        self._child_contexts: Set[str] = set()
        self._lock = threading.RLock()

    def add_tag(self, key: str, value: Any):
        """Add a tag to the correlation context."""
        with self._lock:
            self.tags[key] = value

    def add_metadata(self, key: str, value: Any):
        """Add metadata to the correlation context."""
        with self._lock:
            self.metadata[key] = value

    def set_component(self, component: str):
        """Set the component for this correlation context."""
        with self._lock:
            self.component = component

    def set_operation(self, operation: str):
        """Set the operation name for this correlation context."""
        with self._lock:
            self.operation_name = operation

    def add_child(self, child_correlation_id: str):
        """Add a child correlation ID."""
        with self._lock:
            self._child_contexts.add(child_correlation_id)

    def remove_child(self, child_correlation_id: str):
        """Remove a child correlation ID."""
        with self._lock:
            self._child_contexts.discard(child_correlation_id)

    def get_child_contexts(self) -> Set[str]:
        """Get all child correlation IDs."""
        with self._lock:
            return self._child_contexts.copy()

    def set_state(self, state: CorrelationState):
        """Set correlation state."""
        with self._lock:
            self.state = state

    def to_dict(self) -> Dict[str, Any]:
        """Convert correlation context to dictionary."""
        with self._lock:
            return {
                'correlation_id': self.correlation_id,
                'parent_correlation_id': self.parent_correlation_id,
                'operation_name': self.operation_name,
                'component': self.component,
                'timestamp': self.timestamp,
                'state': self.state.value,
                'tags': self.tags.copy(),
                'metadata': self.metadata.copy(),
                'child_contexts': self._child_contexts.copy()
            }

    def to_span(self) -> Dict[str, Any]:
        """Convert correlation context to span format for observability."""
        with self._lock:
            span = {
                'span_id': self.correlation_id,
                'trace_id': self.correlation_id,
                'parent_span_id': self.parent_correlation_id,
                'name': f"{self.component}.{self.operation_name}",
                'kind': 'INTERNAL',
                'start_time': self.timestamp,
                'status': self.state.value,
                'tags': self.tags.copy(),
                'attributes': self.metadata.copy(),
                'local_data': self._local_data.copy()
            }
            
            # Add child spans
            if self._child_contexts:
                span['child_spans'] = list(self._child_contexts)
            
            return span

    def set_local_data(self, key: str, value: Any):
        """Set local data for this correlation context."""
        with self._lock:
            self._local_data[key] = value

    def get_local_data(self, key: str, default: Any = None) -> Any:
        """Get local data for this correlation context."""
        with self._lock:
            return self._local_data.get(key, default)
class CorrelationManager:
    """
    Correlation manager for tracking operations across the system.

    Manages correlation IDs, provides propagation, and supports
    observability across components.
    """

    def __init__(self, max_active_correlations: int = 1000,
                 correlation_timeout: int = 3600):
        self.max_active_correlations = max_active_correlations
        self.correlation_timeout = correlation_timeout
        self.correlations: Dict[str, CorrelationContext] = {}
        self.correlations_lock = threading.RLock()
        self._cleanup_thread = None
        self._cleanup_running = False
        self._correlation_counter = 0

    def generate_correlation_id(self, parent_id: Optional[str] = None) -> str:
        """
        Generate a new correlation ID.

        Args:
            parent_id: Optional parent correlation ID

        Returns:
            New correlation ID
        """
        correlation_id = str(uuid.uuid4())
        
        with self.correlations_lock:
            # Create correlation context
            context = CorrelationContext(correlation_id)
            
            if parent_id:
                context.parent_correlation_id = parent_id
                # Add to parent's children
                parent_context = self.correlations.get(parent_id)
                if parent_context:
                    parent_context.add_child(correlation_id)

            # Store correlation
            self.correlations[correlation_id] = context

            # Check if we need to cleanup
            if len(self.correlations) > self.max_active_correlations:
                self._cleanup_inactive_correlations()

        logger.debug(f"Generated correlation ID: {correlation_id} (parent: {parent_id})")
        return correlation_id

    def get_correlation_context(self, correlation_id: str) -> Optional[CorrelationContext]:
        """
        Get correlation context by ID.

        Args:
            correlation_id: Correlation ID

        Returns:
            Correlation context or None
        """
        with self.correlations_lock:
            return self.correlations.get(correlation_id)

    def update_correlation_context(self, correlation_id: str,
                                  **updates) -> bool:
        """
        Update correlation context.

        Args:
            correlation_id: Correlation ID
            **updates: Updates to apply

        Returns:
            True if successful, False otherwise
        """
        with self.correlations_lock:
            context = self.correlations.get(correlation_id)
            if not context:
                return False

            for key, value in updates.items():
                if hasattr(context, key):
                    setattr(context, key, value)

            return True

    def complete_correlation(self, correlation_id: str, 
                            success: bool = True,
                            error_message: Optional[str] = None) -> bool:
        """
        Mark correlation as completed.

        Args:
            correlation_id: Correlation ID
            success: Whether operation was successful
            error_message: Optional error message

        Returns:
            True if successful, False otherwise
        """
        with self.correlations_lock:
            context = self.correlations.get(correlation_id)
            if not context:
                return False

            if success:
                context.set_state(CorrelationState.COMPLETED)
            else:
                context.set_state(CorrelationState.FAILED)
                if error_message:
                    context.add_metadata('error_message', error_message)

        logger.debug(f"Completed correlation {correlation_id}: success={success}")
        return True

    def timeout_correlation(self, correlation_id: str) -> bool:
        """
        Mark correlation as timed out.

        Args:
            correlation_id: Correlation ID

        Returns:
            True if successful, False otherwise
        """
        with self.correlations_lock:
            context = self.correlations.get(correlation_id)
            if not context:
                return False

            context.set_state(CorrelationState.TIMEOUT)

        logger.debug(f"Timed out correlation {correlation_id}")
        return True

    def get_correlation_span(self, correlation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get correlation as span for observability.

        Args:
            correlation_id: Correlation ID

        Returns:
            Span dictionary or None
        """
        with self.correlations_lock:
            context = self.correlations.get(correlation_id)
            if not context:
                return None

            return context.to_span()

    def get_correlation_tree(self, correlation_id: str) -> Dict[str, Any]:
        """
        Get correlation tree (all children and descendants).

        Args:
            correlation_id: Correlation ID

        Returns:
            Correlation tree
        """
        with self.correlations_lock:
            context = self.correlations.get(correlation_id)
            if not context:
                return {}

            tree = context.to_dict()
            
            # Get all descendants
            all_descendants = set()
            stack = [correlation_id]

            while stack:
                current_id = stack.pop()
                current_context = self.correlations.get(current_id)
                if current_context:
                    for child_id in current_context.get_child_contexts():
                        if child_id not in all_descendants:
                            all_descendants.add(child_id)
                            stack.append(child_id)

            # Add descendant details
            tree['descendants'] = {}
            for descendant_id in all_descendants:
                descendant_context = self.correlations.get(descendant_id)
                if descendant_context:
                    tree['descendants'][descendant_id] = descendant_context.to_dict()

            return tree

    def _cleanup_inactive_correlations(self):
        """Clean up inactive correlations."""
        current_time = time.time()
        to_remove = []

        with self.correlations_lock:
            for correlation_id, context in self.correlations.items():
                # Check if correlation has timed out
                try:
                    context_time = datetime.fromisoformat(context.timestamp).timestamp()
                    if current_time - context_time > self.correlation_timeout:
                        # Remove correlation and its children
                        if context.get_child_contexts():
                            for child_id in context.get_child_contexts():
                                self.correlations.pop(child_id, None)
                        to_remove.append(correlation_id)
                except Exception as e:
                    logger.error(f"Error checking correlation timeout: {e}")

            # Remove inactive correlations
            for correlation_id in to_remove:
                self.correlations.pop(correlation_id, None)

        logger.debug(f"Cleaned up {len(to_remove)} inactive correlations")

    def get_active_correlations_count(self) -> int:
        """Get number of active correlations."""
        with self.correlations_lock:
            return len(self.correlations)

    def get_all_correlation_ids(self) -> List[str]:
        """Get all correlation IDs."""
        with self.correlations_lock:
            return list(self.correlations.keys())

    def get_correlation_stats(self) -> Dict[str, Any]:
        """Get correlation statistics."""
        with self.correlations_lock:
            active_count = len(self.correlations)
            
            state_counts = defaultdict(int)
            component_counts = defaultdict(int)
            
            for context in self.correlations.values():
                state_counts[context.state] += 1
                if context.component:
                    component_counts[context.component] += 1

            return {
                'active_count': active_count,
                'max_active': self.max_active_correlations,
                'correlation_timeout': self.correlation_timeout,
                'state_counts': dict(state_counts),
                'component_counts': dict(component_counts)
            }

    def start_cleanup_thread(self):
        """Start cleanup thread for inactive correlations."""
        if self._cleanup_running:
            return

        self._cleanup_running = True

        def cleanup():
            while self._cleanup_running:
                try:
                    self._cleanup_inactive_correlations()
                    time.sleep(60)  # Run every minute
                except Exception as e:
                    logger.error(f"Error in correlation cleanup thread: {e}")
                    time.sleep(60)

        self._cleanup_thread = threading.Thread(target=cleanup, daemon=True)
        self._cleanup_thread.start()
        logger.info("Correlation cleanup thread started")

    def stop_cleanup_thread(self):
        """Stop cleanup thread."""
        self._cleanup_running = False
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=10)
            self._cleanup_thread = None
            logger.info("Correlation cleanup thread stopped")

    def close(self):
        """Close correlation manager."""
        self.stop_cleanup_thread()
        with self.correlations_lock:
            self.correlations.clear()
class CorrelationPropagation:
    """
    Correlation propagation utilities.

    Provides utilities for propagating correlation IDs across
    system boundaries and components.
    """

    def __init__(self, correlation_manager: Optional[CorrelationManager] = None):
        self.correlation_manager = correlation_manager or CorrelationManager()

    def propagate_correlation(self, correlation_id: str, operation: str,
                             component: str,
                             **context_data) -> str:
        """
        Propagate correlation to a new operation.

        Args:
            correlation_id: Parent correlation ID
            operation: Operation name
            component: Component name
            **context_data: Additional context data

        Returns:
            New correlation ID
        """
        # Create new correlation ID
        new_correlation_id = self.correlation_manager.generate_correlation_id(correlation_id)

        # Update context
        self.correlation_manager.update_correlation_context(
            new_correlation_id,
            operation_name=operation,
            component=component
        )

        # Add context data
        context = self.correlation_manager.get_correlation_context(new_correlation_id)
        if context:
            for key, value in context_data.items():
                context.add_metadata(key, value)

        logger.debug(f"Propagated correlation {correlation_id} -> {new_correlation_id} ({component}.{operation})")
        return new_correlation_id

    def get_correlation_headers(self, correlation_id: str) -> Dict[str, str]:
        """
        Get correlation headers for inter-component communication.

        Args:
            correlation_id: Correlation ID

        Returns:
            Dictionary of correlation headers
        """
        context = self.correlation_manager.get_correlation_context(correlation_id)
        if not context:
            return {}

        return {
            'x-correlation-id': correlation_id,
            'x-component': context.component,
            'x-operation': context.operation_name,
            'x-parent-correlation-id': context.parent_correlation_id or '',
            'x-timestamp': context.timestamp,
            'x-state': context.state.value
        }

    def extract_correlation_from_headers(self, headers: Dict[str, str]) -> str:
        """
        Extract correlation ID from headers.

        Args:
            headers: Dictionary of headers

        Returns:
            Correlation ID or None if not found
        """
        correlation_id = headers.get('x-correlation-id') or headers.get('correlation-id')
        return correlation_id

    def create_span_from_headers(self, headers: Dict[str, str]) -> Dict[str, Any]:
        """
        Create span from headers.

        Args:
            headers: Dictionary of headers

        Returns:
            Span dictionary
        """
        correlation_id = self.extract_correlation_from_headers(headers)
        if not correlation_id:
            return {}

        return self.correlation_manager.get_correlation_span(correlation_id)
class CorrelationMiddleware:
    """
    Correlation middleware for adding correlation IDs to logs and metrics.

    Provides middleware for adding correlation IDs to logging,
    monitoring, and observability systems.
    """

    def __init__(self, correlation_manager: Optional[CorrelationManager] = None,
                 propagation: Optional[CorrelationPropagation] = None):
        self.correlation_manager = correlation_manager or CorrelationManager()
        self.propagation = propagation or CorrelationPropagation(self.correlation_manager)

    def add_correlation_to_log_record(self, log_record: Dict[str, Any],
                                    correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Add correlation ID to log record.

        Args:
            log_record: Log record to update
            correlation_id: Correlation ID (defaults to current context)

        Returns:
            Updated log record
        """
        if not correlation_id:
            # Try to get correlation from thread-local context
            correlation_id = self._get_current_correlation_id()

        if correlation_id:
            log_record['correlation_id'] = correlation_id

            # Add correlation context to log record
            context = self.correlation_manager.get_correlation_context(correlation_id)
            if context:
                log_record['correlation'] = context.to_dict()

        return log_record

    def add_correlation_to_metric(self, metric: Dict[str, Any],
                                 correlation_id: Optional[str] = None) -> Dict[str, Any]:
        """
            Add correlation ID to metric.

        Args:
            metric: Metric to update
            correlation_id: Correlation ID (defaults to current context)

        Returns:
            Updated metric
        """
        if not correlation_id:
            correlation_id = self._get_current_correlation_id()

        if correlation_id:
            metric['correlation_id'] = correlation_id

        return metric

    def create_correlation_span(self, operation_name: str,
                               component: str,
                               correlation_id: Optional[str] = None) -> str:
        """
        Create a new correlation span.

        Args:
            operation_name: Operation name
            component: Component name
            correlation_id: Optional parent correlation ID

        Returns:
            New correlation ID
        """
        if not correlation_id:
            correlation_id = self._get_current_correlation_id()

        return self.propagation.propagate_correlation(
            correlation_id or '',
            operation_name,
            component
        )

    def get_current_correlation_id(self) -> Optional[str]:
        """Get current correlation ID."""
        return self._get_current_correlation_id()

    def _get_current_correlation_id(self) -> Optional[str]:
        """Get current correlation ID from thread-local storage."""
        # This would typically use thread-local storage
        # For now, return None - implementations can override
        return None

    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for current context."""
        self._set_current_correlation_id(correlation_id)

    def _set_current_correlation_id(self, correlation_id: str):
        """Set correlation ID in thread-local storage."""
        # This would typically use thread-local storage
        # For now, do nothing - implementations can override
        pass
class CorrelationLogger:
    """
    Correlation-aware logger.

    Provides logging methods that automatically include correlation IDs
    and context in log records.
    """

    def __init__(self, middleware: Optional[CorrelationMiddleware] = None,
                 name: str = "correlation"):
        self.middleware = middleware or CorrelationMiddleware()
        self.name = name
        self.logger = logging.getLogger(name)

    def log_with_correlation(self, level: str, message: str,
                            correlation_id: Optional[str] = None,
                            **kwargs) -> None:
        """
        Log message with correlation.

        Args:
            level: Log level
            message: Log message
            correlation_id: Correlation ID
            **kwargs: Additional context
        """
        log_record = {
            'message': message,
            'level': level,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'logger_name': self.name
        }

        # Add correlation
        log_record = self.middleware.add_correlation_to_log_record(
            log_record, correlation_id
        )

        # Add additional context
        log_record.update(kwargs)

        # Log using standard logging
        getattr(self.logger, level.lower())(json.dumps(log_record))

    def debug(self, message: str, correlation_id: Optional[str] = None,
              **kwargs) -> None:
        """Log debug message."""
        self.log_with_correlation('DEBUG', message, correlation_id, **kwargs)

    def info(self, message: str, correlation_id: Optional[str] = None,
             **kwargs) -> None:
        """Log info message."""
        self.log_with_correlation('INFO', message, correlation_id, **kwargs)

    def warning(self, message: str, correlation_id: Optional[str] = None,
                **kwargs) -> None:
        """Log warning message."""
        self.log_with_correlation('WARNING', message, correlation_id, **kwargs)

    def error(self, message: str, correlation_id: Optional[str] = None,
              **kwargs) -> None:
        """Log error message."""
        self.log_with_correlation('ERROR', message, correlation_id, **kwargs)

    def critical(self, message: str, correlation_id: Optional[str] = None,
                 **kwargs) -> None:
        """Log critical message."""
        self.log_with_correlation('CRITICAL', message, correlation_id, **kwargs)

    def with_correlation(self, correlation_id: str) -> 'CorrelationLoggerContext':
        """
        Create logger with correlation context.

        Args:
            correlation_id: Correlation ID

        Returns:
            Logger context
        """
        return CorrelationLoggerContext(self, correlation_id)
class CorrelationLoggerContext:
    """Logger context with correlation."""

    def __init__(self, logger: CorrelationLogger, correlation_id: str):
        self.logger = logger
        self.correlation_id = correlation_id

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(message, self.correlation_id, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        self.logger.info(message, self.correlation_id, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(message, self.correlation_id, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        self.logger.error(message, self.correlation_id, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        self.logger.critical(message, self.correlation_id, **kwargs)