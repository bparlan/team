#!/usr/bin/env python3
"""
Integrated Orchestrator for theteam skill enhancement.

Coordinates EventBus with all major components (TaskStack, SystemIntegration)
for real-time, event-driven architecture. TerminalUI was deleted in M4 as
unparseable and unreachable; the 17 `if self.terminal_ui:` call sites it
gated were dead branches, not optional behaviour, and went with it.
"""

import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

from theteam.workflow.discussion_manager_refactored import create_discussion_manager

# Phase 4 wiring: the orchestrator previously used EventBus/EventType without
# importing them (guaranteed NameError on construction) and drove tasks through
# loose dicts. It now sits on the canonical EventBus and the canonical
# UnifiedLoop + TaskContract, so there is one loop and one task model.
from theteam.core.event_bus import EventBus, EventType
from theteam.core.unified_loop import UnifiedLoop, LoopConfig
from theteam.core.task_contract import UnifiedTask, TaskStatus, TaskPriority
from theteam.core.metrics import MetricsCollector


def _metrics_port() -> int:
    """Resolve the metrics listen port from the environment (default 8000)."""
    try:
        return int(os.environ.get("THETEAM_METRICS_PORT", "8000"))
    except ValueError:
        logger.warning("Invalid THETEAM_METRICS_PORT, falling back to 8000")
        return 8000


class IntegratedOrchestrator:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.event_bus = EventBus(str(self.project_root / ".omp" / "theteam" / "event_log.json"))

        # Canonical loop + task contract (Phase 4): every task this
        # orchestrator registers is a UnifiedTask executed by the one
        # UnifiedLoop, not a loose dict in a second competing loop.
        self.loop = UnifiedLoop(
            str(self.project_root),
            LoopConfig(loop_id="integrated_orchestrator", project_root=str(self.project_root)),
        )
        self.metrics = MetricsCollector(port=_metrics_port())
        self.metrics.bind(loop=self.loop, limiter=self.loop.resource_limiter)
        # terminal_ui removed in M4 along with the TerminalUI class.
        # Component instances
        self.task_stack_orchestrator = None
        self.system_integration = None
        self.state_manager = None
        self.discussion_manager = None
        
        # Background threads
        self.orchestration_thread = None
        self.health_check_thread = None
        self.should_exit = False
        
        # Performance metrics
        self.performance_metrics = {
            'start_time': datetime.now(timezone.utc),
            'events_processed': 0,
            'ui_updates': 0,
            'task_executions': 0,
            'system_analyses': 0
        }
    
    def initialize_components(self, task_stack_orchestrator=None,
                              system_integration=None, state_manager=None,
                              discussion_manager=None):
        """Initialize all components and establish event connections."""
        self.task_stack_orchestrator = task_stack_orchestrator
        self.system_integration = system_integration
        self.state_manager = state_manager
        self.discussion_manager = discussion_manager
        
        # Setup event connections
        self._setup_event_connections()
        
        # Start event processor
        self.event_bus.start_event_processor()

        # Start the canonical loop and expose /metrics + /health for Prometheus
        # and the container healthcheck. A busy port must not block startup.
        self.loop.start()
        self.metrics.start_http_server()
        
        # Setup background orchestration
        self.orchestration_thread = threading.Thread(
            target=self._orchestration_loop,
            daemon=True,
            name="IntegratedOrchestrator"
        )
        self.orchestration_thread.start()
        
        # Setup health monitoring
        self.health_check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name="HealthMonitor"
        )
        self.health_check_thread.start()
        
        logger.info("Integrated orchestrator initialized successfully")
    
    def _setup_event_connections(self):
        """Setup event connections between components."""
        # Task Stack Events -> Terminal UI
        self.event_bus.subscribe(EventType.TASK_REGISTERED, self._handle_task_registered)
        self.event_bus.subscribe(EventType.TASK_EXECUTED, self._handle_task_executed)
        self.event_bus.subscribe(EventType.TASK_SCHEDULED, self._handle_task_scheduled)
        self.event_bus.subscribe(EventType.TASK_FAILED, self._handle_task_failed)
        
        # System Integration Events -> Terminal UI
        self.event_bus.subscribe(EventType.SYSTEM_ANALYSIS_STARTED, self._handle_analysis_started)
        self.event_bus.subscribe(EventType.SYSTEM_ANALYSIS_COMPLETED, self._handle_analysis_completed)
        self.event_bus.subscribe(EventType.SYSTEM_HEALTH_UPDATED, self._handle_health_updated)
        self.event_bus.subscribe(EventType.SYSTEM_ISSUE_DETECTED, self._handle_issue_detected)
        
        # Discussion Events -> Task Stack
        self.event_bus.subscribe(EventType.DISCUSSION_CREATED, self._handle_discussion_created)
        self.event_bus.subscribe(EventType.TASK_ASSIGNED, self._handle_task_assigned)
        
        # State Events -> All Components
        self.event_bus.subscribe(EventType.STATE_CHANGED, self._handle_state_changed)
        
        # Component Events -> Event Bus
        
        if self.task_stack_orchestrator:
            self.task_stack_orchestrator.setup_event_handler(self._handle_task_stack_event)
        
        if self.system_integration:
            self.system_integration.setup_event_handler(self._handle_system_integration_event)
    
    def _handle_task_registered(self, event):
        """Handle task registration event."""
        task_info = event.data
        logger.info(f"Task registered: {task_info.get('task_id', 'unknown')}")
        
        # Update UI
        
        # Check if task should be automatically scheduled
        if task_info.get('auto_schedule', False):
            self._auto_schedule_task(task_info)
    
    def _handle_task_executed(self, event):
        """Handle task execution event."""
        execution_result = event.data
        self.performance_metrics['task_executions'] += 1
        
        logger.info(f"Task executed: {execution_result.get('task_id', 'unknown')} - Success: {execution_result.get('success', False)}")
        
        # Update UI
        
        # Auto-schedule next run if task is recurring
        if execution_result.get('recurring', False):
            self._schedule_recurring_task(execution_result)
        
        # Trigger related discussions if needed
        if execution_result.get('discussion_triggered', False):
            self._trigger_discussion_from_task(execution_result)
    
    def _handle_task_scheduled(self, event):
        """Handle task scheduling event."""
        schedule_info = event.data
        logger.info(f"Task scheduled: {schedule_info.get('task_id', 'unknown')} - Next run: {schedule_info.get('next_run', 'unknown')}")
        
        # Update UI
    
    def _handle_task_failed(self, event):
        """Handle task failure event."""
        failure_info = event.data
        logger.warning(f"Task failed: {failure_info.get('task_id', 'unknown')} - {failure_info.get('error', 'Unknown error')}")
        
        # Update UI with error
        
        # Auto-retry if configured
        if failure_info.get('auto_retry', False):
            self._auto_retry_task(failure_info)
        
        # Trigger system analysis if failure is critical
        if failure_info.get('critical', False):
            self._trigger_emergency_analysis(failure_info)
    
    def _handle_analysis_started(self, event):
        """Handle system analysis start event."""
        analysis_info = event.data
        logger.info(f"System analysis started: {analysis_info.get('analysis_id', 'unknown')}")
        
        # Update UI
    
    def _handle_analysis_completed(self, event):
        """Handle system analysis completion event."""
        analysis_result = event.data
        self.performance_metrics['system_analyses'] += 1
        
        logger.info(f"System analysis completed: {analysis_result.get('analysis_id', 'unknown')}")
        
        # Update UI
        
        # Auto-generate tasks based on analysis results
        generated_tasks = self._generate_tasks_from_analysis(analysis_result)
        if generated_tasks:
            self._auto_register_generated_tasks(generated_tasks)
        
        # Trigger discussions if analysis found issues
        if analysis_result.get('issues_found', []):
            self._trigger_discussion_from_analysis(analysis_result)
    
    def _handle_health_updated(self, event):
        """Handle system health update event."""
        health_info = event.data
        
        # Update UI
        
        # Check thresholds and trigger alerts
        self._check_health_thresholds(health_info)
    
    def _handle_issue_detected(self, event):
        """Handle system issue detection event."""
        issue_info = event.data
        logger.warning(f"System issue detected: {issue_info.get('issue', 'Unknown')}")
        
        # Update UI with warning
        
        # Trigger immediate analysis if critical
        if issue_info.get('severity', 'low') == 'critical':
            self._trigger_emergency_analysis(issue_info)
    
    def _handle_discussion_created(self, event):
        """Handle discussion creation event."""
        discussion_info = event.data
        logger.info(f"Discussion created: {discussion_info.get('discussion_id', 'unknown')}")
        
        # Create related tasks if configured
        related_tasks = self._generate_tasks_from_discussion(discussion_info)
        if related_tasks:
            self._auto_register_generated_tasks(related_tasks)
    
    def _handle_task_assigned(self, event):
        """Handle task assignment event."""
        assignment_info = event.data
        logger.info(f"Task assigned: {assignment_info.get('task_id', 'unknown')} to {assignment_info.get('assignee', 'unknown')}")
        
        # Update UI
    
    def _handle_state_changed(self, event):
        """Handle state change event."""
        state_info = event.data
        logger.debug(f"State changed: {state_info.get('key', 'unknown')} = {state_info.get('value', 'unknown')}")
        
        # Update all components
        
        if self.task_stack_orchestrator:
            self.task_stack_orchestrator.update_state(state_info)
        
        if self.system_integration:
            self.system_integration.update_state(state_info)
    
    def _handle_ui_event(self, event):
        """Handle UI event."""
        ui_event = event.data
        event_type = ui_event.get('event_type')
        
        if event_type == 'command':
            command = ui_event.get('command')
            parameters = ui_event.get('parameters', {})
            self._execute_ui_command(command, parameters)
        elif event_type == 'refresh':
            self._handle_ui_refresh(ui_event)
        elif event_type == 'navigation':
            self._handle_ui_navigation(ui_event)
    
    def _handle_task_stack_event(self, event):
        """Handle task stack event."""
        task_event = event.data
        # Forward to UI
    
    def _handle_system_integration_event(self, event):
        """Handle system integration event."""
        system_event = event.data
        # Forward to UI
    
    def _execute_ui_command(self, command: str, parameters: Dict[str, Any]):
        """Execute UI command."""
        logger.info(f"Executing UI command: {command}")
        
        if command == 'start_task':
            task_id = parameters.get('task_id')
            if task_id and self.task_stack_orchestrator:
                self.task_stack_orchestrator.execute_task(task_id)
        
        elif command == 'schedule_task':
            task_id = parameters.get('task_id')
            interval = parameters.get('interval_minutes', 60)
            if task_id and self.task_stack_orchestrator:
                self.task_stack_orchestrator.loop_task(task_id, interval)
        
        elif command == 'run_analysis':
            analysis_type = parameters.get('analysis_type', 'infrastructure_assessment')
            if self.system_integration:
                self.system_integration.start_system_analysis(analysis_type, str(self.project_root))
    
    def _handle_ui_refresh(self, event):
        """Handle UI refresh event."""
        logger.debug("UI refresh requested")
    
    def _handle_ui_navigation(self, event):
        """Handle UI navigation event."""
        navigation = event.data
        view = navigation.get('view')
        tab_index = navigation.get('tab_index')
        
    
    def _auto_schedule_task(self, task_info: Dict[str, Any]):
        """Automatically schedule a registered task."""
        task_id = task_info.get('task_id')
        interval = task_info.get('auto_schedule_interval', 60)
        
        if task_id and self.task_stack_orchestrator:
            self.task_stack_orchestrator.loop_task(task_id, interval)
            logger.info(f"Auto-scheduled task {task_id} with interval {interval} minutes")
    
    def _schedule_recurring_task(self, execution_result: Dict[str, Any]):
        """Schedule next run for recurring task."""
        task_id = execution_result.get('task_id')
        interval = execution_result.get('recurring_interval', 60)
        
        if task_id and self.task_stack_orchestrator:
            self.task_stack_orchestrator.loop_task(task_id, interval)
            logger.info(f"Scheduled recurring task {task_id} with interval {interval} minutes")
    
    def _auto_retry_task(self, failure_info: Dict[str, Any]):
        """Auto-retry a failed task."""
        task_id = failure_info.get('task_id')
        retry_count = failure_info.get('retry_count', 0)
        max_retries = failure_info.get('max_retries', 3)
        
        if task_id and retry_count < max_retries and self.task_stack_orchestrator:
            # Implement retry logic with exponential backoff
            delay = min(300, 60 * (2 ** retry_count))  # Cap at 5 minutes
            time.sleep(delay)
            self.task_stack_orchestrator.execute_task(task_id)
            logger.info(f"Auto-retrying task {task_id} (attempt {retry_count + 1}/{max_retries})")
    
    def _trigger_discussion_from_task(self, execution_result: Dict[str, Any]):
        """Trigger discussion based on task execution."""
        task_id = execution_result.get('task_id')
        success = execution_result.get('success', False)
        
        if success:
            # Create success discussion if configured
            discussion_topic = f"Task Completed: {task_id}"
            self._create_discussion_from_task(discussion_topic, task_id)
        else:
            # Create failure discussion if critical
            if execution_result.get('critical', False):
                discussion_topic = f"Task Failed: {task_id} - {execution_result.get('error', 'Unknown error')}"
                self._create_discussion_from_task(discussion_topic, task_id)
    
    def _create_discussion_from_task(self, topic: str, task_id: str):
        """Create discussion from task result."""
        if self.discussion_manager:
            discussion = self.discussion_manager.create_discussion(topic, [])
            logger.info(f"Created discussion {discussion['discussion_id']} for task {task_id}")
            
            # Add task reference to discussion
            if self.task_stack_orchestrator:
                self.task_stack_orchestrator.add_task_to_discussion(discussion['discussion_id'], task_id)
    
    def _generate_tasks_from_analysis(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate tasks from system analysis results."""
        generated_tasks = []
        issues = analysis_result.get('issues_found', [])
        
        for issue in issues:
            task = self._create_task_from_issue(issue, 'analysis')
            if task:
                generated_tasks.append(task)
        
        # Generate tasks for recommendations
        recommendations = analysis_result.get('recommendations', [])
        for recommendation in recommendations:
            task = self._create_task_from_recommendation(recommendation, 'analysis')
            if task:
                generated_tasks.append(task)
        
        return generated_tasks
    
    def _generate_tasks_from_discussion(self, discussion_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate tasks from discussion content."""
        generated_tasks = []
        
        # Analyze discussion for actionable items
        topic = discussion_info.get('topic', '')
        participants = discussion_info.get('participants', [])
        
        # Create task for discussion topic if it contains actionable items
        if self._contains_actionable_items(topic):
            task = self._create_task_from_discussion(topic, 'discussion')
            if task:
                generated_tasks.append(task)
        
        # Create tasks for participants if they have specific roles
        for participant in participants:
            task = self._create_participant_task(participant)
            if task:
                generated_tasks.append(task)
        
        return generated_tasks
    
    def _create_task_from_issue(self, issue: str, source: str) -> Optional[Dict[str, Any]]:
        """Create task from system issue."""
        task_templates = {
            'cpu usage': {
                'title': 'Optimize CPU usage',
                'priority': 'high',
                'description': 'Investigate and resolve high CPU usage detected in system analysis',
                'assignee': 'pragmatist'
            },
            'memory usage': {
                'title': 'Optimize memory usage',
                'priority': 'high',
                'description': 'Investigate and resolve high memory usage detected in system analysis',
                'assignee': 'pragmatist'
            },
            'disk usage': {
                'title': 'Clean up disk space',
                'priority': 'medium',
                'description': 'Clean up temporary files and optimize disk usage',
                'assignee': 'pragmatist'
            },
            'security': {
                'title': 'Security audit and remediation',
                'priority': 'critical',
                'description': 'Conduct security audit and implement necessary patches',
                'assignee': 'security'
            }
        }
        
        # Find matching template
        for keyword, template in task_templates.items():
            if keyword in issue.lower():
                task = {
                    'title': template['title'],
                    'description': template['description'],
                    'priority': template['priority'],
                    'assignee': template['assignee'],
                    'source': source,
                    'issue': issue,
                    'auto_generated': True
                }
                logger.debug(f"Generated task from issue: {task['title']}")
                return task
        
        # Generic task for unknown issues
        task = {
            'title': f"Address system issue: {issue[:50]}...",
            'description': f"Handle system issue detected: {issue}",
            'priority': 'medium',
            'assignee': 'architect',
            'source': source,
            'issue': issue,
            'auto_generated': True
        }
        logger.debug(f"Generated generic task from issue: {task['title']}")
        return task
    
    def _create_task_from_recommendation(self, recommendation: str, source: str) -> Optional[Dict[str, Any]]:
        """Create task from recommendation."""
        task = {
            'title': f"Implement recommendation: {recommendation[:50]}...",
            'description': f"Implement system improvement: {recommendation}",
            'priority': 'medium',
            'assignee': 'pragmatist',
            'source': source,
            'recommendation': recommendation,
            'auto_generated': True
        }
        logger.debug(f"Generated task from recommendation: {task['title']}")
        return task
    
    def _create_task_from_discussion(self, topic: str, source: str) -> Optional[Dict[str, Any]]:
        """Create task from discussion topic."""
        if not self._contains_actionable_items(topic):
            return None
        
        task = {
            'title': f"Address discussion: {topic[:50]}...",
            'description': f"Handle team discussion: {topic}",
            'priority': 'medium',
            'assignee': 'architect',
            'source': source,
            'discussion_topic': topic,
            'auto_generated': True
        }
        logger.debug(f"Generated task from discussion: {task['title']}")
        return task
    
    def _create_participant_task(self, participant: str) -> Optional[Dict[str, Any]]:
        """Create task for team member based on their role."""
        # Determine role from participant ID
        role_map = {
            'architect': 'architect',
            'pragmatist': 'pragmatist',
            'skeptic': 'skeptic',
            'security': 'security'
        }
        
        role = role_map.get(participant, 'architect')
        
        task = {
            'title': f"Review team member: {participant}",
            'description': f"Coordinate and review work from team member: {participant}",
            'priority': 'low',
            'assignee': 'architect',
            'source': 'team_member',
            'participant': participant,
            'auto_generated': True
        }
        logger.debug(f"Generated task for participant: {task['title']}")
        return task
    
    def _contains_actionable_items(self, text: str) -> bool:
        """Check if text contains actionable items."""
        actionable_keywords = [
            'fix', 'resolve', 'implement', 'create', 'add', 'update', 'optimize',
            'improve', 'address', 'handle', 'manage', 'configure', 'install'
        ]
        
        text_lower = text.lower()
        for keyword in actionable_keywords:
            if keyword in text_lower:
                return True
        return False
    
    def _auto_register_generated_tasks(self, tasks: List[Dict[str, Any]]):
        """
        Phase 4: tasks are converted to UnifiedTask and handed to the one
        UnifiedLoop, so the loop's scheduler, resource limiter and dead-letter
        queue govern them. The legacy task-stack registration still runs for
        the UI, but the loop is now the system of record.
        """
        for spec in tasks:
            try:
                unified = self._to_unified_task(spec)
                if self.loop.add_task(unified):
                    logger.info(f"Registered task with canonical loop: {spec.get('title')}")
                else:
                    # add_task() rejects duplicates, a stopped loop, an open
                    # circuit breaker, or an exhausted task limit. Silently
                    # dropping the task would hide a real failure.
                    logger.warning(
                        f"Canonical loop rejected task {unified.task_id!r} "
                        f"(loop_running={self.loop._running}, "
                        f"breaker_closed={self.loop.circuit_breaker.is_closed()})"
                    )

                if self.task_stack_orchestrator:
                    # Keep the UI-facing stack in sync with the loop.
                    self.task_stack_orchestrator.register_task(spec)
            except Exception as e:
                logger.error(f"Failed to auto-register task: {e}")

    def _to_unified_task(self, spec: Dict[str, Any]) -> UnifiedTask:
        """Build a canonical UnifiedTask from a generated task spec."""
        return UnifiedTask(
            task_id=spec.get("task_id") or f"gen_{uuid.uuid4().hex[:12]}",
            name=spec.get("title", "generated task"),
            handler=spec.get("handler", lambda: {"success": True, "source": spec.get("source", "analysis")}),
            status=TaskStatus.PENDING,
            priority=TaskPriority.from_str(str(spec.get("priority", "normal"))),
            parameters={"assignee": spec.get("assignee")},
            metadata=dict(spec),
        )
    
    def _check_health_thresholds(self, health_info: Dict[str, Any]):
        """Check system health thresholds and trigger alerts."""
        thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 80.0,
            'disk_usage': 90.0,
            'response_time': 1000.0
        }
        
        for metric, value in health_info.items():
            if metric in thresholds and value > thresholds[metric]:
                self.event_bus.emit_event(
                    EventType.SYSTEM_ISSUE_DETECTED,
                    {
                        'issue': f"High {metric}: {value}%",
                        'metric': metric,
                        'value': value,
                        'threshold': thresholds[metric],
                        'severity': 'high' if metric in ['cpu_usage', 'memory_usage'] else 'medium'
                    },
                    'integrated_orchestrator'
                )
    
    def _trigger_discussion_from_analysis(self, analysis_result: Dict[str, Any]):
        """Trigger discussion from analysis results."""
        issues = analysis_result.get('issues_found', [])
        
        if issues:
            topic = f"System Analysis: {', '.join(issues[:3])}"
            
            if self.discussion_manager:
                discussion = self.discussion_manager.create_discussion(
                    topic,
                    ['architect', 'pragmatist', 'skeptic', 'security']
                )
                logger.info(f"Triggered discussion {discussion['discussion_id']} from analysis")
    
    def _trigger_emergency_analysis(self, event_info: Dict[str, Any]):
        """Trigger emergency system analysis."""
        analysis_type = 'emergency_assessment'
        
        if self.system_integration:
            result = self.system_integration.start_system_analysis(
                analysis_type,
                str(self.project_root),
                force=True
            )
            logger.warning(f"Triggered emergency analysis: {result}")
    
    def _orchestration_loop(self):
        """Background orchestration loop."""
        while not self.should_exit:
            try:
                # Update performance metrics
                self.performance_metrics['events_processed'] = self.event_bus.get_stats()['total_events']
                
                # Check for deadlocks or stuck operations
                self._check_for_deadlocks()
                
                # Perform health checks
                self._perform_orchestration_health_check()
                
                # Clean up old events
                self._cleanup_old_events()
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in orchestration loop: {e}")
                time.sleep(60)  # Wait longer on error
    
    def _health_check_loop(self):
        """Background health check loop."""
        while not self.should_exit:
            try:
                # Check component health
                self._check_component_health()
                
                # Check event bus health
                self._check_event_bus_health()
                
                # Check task stack health
                self._check_task_stack_health()
                
                time.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                time.sleep(120)
    
    def _check_for_deadlocks(self):
        """Check for potential deadlocks."""
        # Check event queue size
        stats = self.event_bus.get_stats()
        if stats['queue_size'] > 1000:
            logger.warning(f"Event queue growing large: {stats['queue_size']} events")
        
        # Check for unresponsive components
        # Implementation would depend on component health checks
    
    def _perform_orchestration_health_check(self):
        """Perform orchestration-specific health checks."""
        # Verify all components are properly connected
        components_ok = True
        
        
        if not self.task_stack_orchestrator:
            logger.warning("Task stack orchestrator not initialized")
            components_ok = False
        
        if not self.system_integration:
            logger.warning("System integration not initialized")
            components_ok = False
        
        if not components_ok:
            self.event_bus.emit_event(
                EventType.SYSTEM_ISSUE_DETECTED,
                {
                    'issue': 'Missing or not properly initialized components',
                    'severity': 'critical'
                },
                'integrated_orchestrator'
            )
    
    def _check_component_health(self):
        """Check health of all components."""
        # Check terminal UI
        
        # Check task stack orchestrator
        if self.task_stack_orchestrator:
            orchestrator_health = self.task_stack_orchestrator.get_health()
            if not orchestrator_health['healthy']:
                self.event_bus.emit_event(
                    EventType.SYSTEM_ISSUE_DETECTED,
                    {
                        'issue': f"Task stack orchestrator unhealthy: {orchestrator_health['issues']}",
                        'component': 'task_stack_orchestrator',
                        'severity': 'high'
                    },
                    'integrated_orchestrator'
                )
        
        # Check system integration
        if self.system_integration:
            system_health = self.system_integration.get_system_integration_status()
            if not system_health['status'] == 'healthy':
                self.event_bus.emit_event(
                    EventType.SYSTEM_ISSUE_DETECTED,
                    {
                        'issue': f"System integration unhealthy: {system_health['status']}",
                        'component': 'system_integration',
                        'severity': 'high'
                    },
                    'integrated_orchestrator'
                )
    
    def _check_event_bus_health(self):
        """Check event bus health."""
        stats = self.event_bus.get_stats()
        
        if stats['queue_size'] > 10000:
            logger.warning(f"Event bus queue size growing: {stats['queue_size']}")
        
        # Check for dropped events
        if stats['total_events'] > 1000:
            # Check recent events
            recent_events = self.event_bus.get_events(limit=100)
            if recent_events and recent_events[-1].timestamp < datetime.now(timezone.utc).timestamp() - 300:
                logger.warning("Potential event processing delay detected")
    
    def _check_task_stack_health(self):
        """Check task stack health."""
        if self.task_stack_orchestrator:
            status = self.task_stack_orchestrator.get_status()
            
            # Check for excessive scheduled tasks
            scheduled_count = status.get('scheduled_tasks', 0)
            if scheduled_count > 1000:
                logger.warning(f"Large number of scheduled tasks: {scheduled_count}")
    
    def _cleanup_old_events(self):
        """Clean up old events from log."""
        # Event bus handles its own cleanup (keeps last 1000 events)
        pass
    
    def get_orchestration_status(self) -> Dict[str, Any]:
        """Get overall orchestration status."""
        stats = self.event_bus.get_stats()
        
        return {
            'event_bus': stats,
            'performance_metrics': self.performance_metrics,
            'components_initialized': {
                'task_stack_orchestrator': self.task_stack_orchestrator is not None,
                'system_integration': self.system_integration is not None,
                'state_manager': self.state_manager is not None,
                'discussion_manager': self.discussion_manager is not None
            },
            'threads_running': {
                'orchestration': self.orchestration_thread is not None and self.orchestration_thread.is_alive(),
                'health_check': self.health_check_thread is not None and self.health_check_thread.is_alive()
            }
        }
    
    def stop(self):
        """Stop the integrated orchestrator."""
        self.should_exit = True
        
        if self.orchestration_thread:
            self.orchestration_thread.join(timeout=5)
        
        if self.health_check_thread:
            self.health_check_thread.join(timeout=5)
        
        if self.event_bus:
            self.event_bus.stop_event_processor()

        # Tear down the observability endpoint and the canonical loop.
        self.metrics.stop()
        self.loop.stop()

        logger.info("Integrated orchestrator stopped")

# The `__main__` block that used to live here started a TerminalUI, which M4
# deleted as unparseable and unreachable. `python -m
# theteam.core.integrated_orchestrator` is not a product entry point;
# ARCHITECTURE.md §5.2 names exactly three, and this is not one of them.
