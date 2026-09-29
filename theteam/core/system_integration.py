#!/usr/bin/env python3
"""
System Awareness Integration for theteam skill enhancement.

This module provides comprehensive integration between theteam skill and system awareness,
enabling automated discussions, health monitoring, and intelligent task triggering.
"""

import os
import json
import sys
import time
import threading
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
import logging
from collections import defaultdict
import uuid

from theteam.core.agent_isolation import AgentIsolation, IsolationPolicy

# Directory that CONTAINS the `theteam` package: what a subprocess needs on
# PYTHONPATH to `import theteam.*`. Derived from the package itself, so it is
# correct at any install depth and in any checkout.
import theteam as _theteam

PROJECT_ROOT = str(Path(_theteam.__file__).resolve().parent.parent)

logger = logging.getLogger(__name__)
class SystemIntegration:
    def __init__(self, project_root: str, state_manager=None, discussion_manager=None):
        self.project_root = Path(project_root).resolve()
        self.state_manager = state_manager
        self.discussion_manager = discussion_manager

        # Per-agent container isolation (roadmap criterion 6). `isolation=None`
        # disables it; the env switch lets an operator turn it off without a
        # code change when no Docker daemon is present.
        self.isolation: Optional[AgentIsolation] = None
        if os.environ.get("THETEAM_AGENT_ISOLATION", "1") not in ("0", "false", "no"):
            self.isolation = AgentIsolation(
                IsolationPolicy(image=os.environ.get("THETEAM_AGENT_IMAGE", "theteam"))
            )
        
        # System monitoring
        self.health_metrics = {}
        self.system_metrics_history = []
        self.analysis_triggers = []
        self.active_integrations = []
        
        # Configuration
        self.monitoring_enabled = True
        self.health_thresholds = {
            'cpu_usage': 80.0,
            'memory_usage': 80.0,
            'disk_usage': 90.0,
            'response_time': 1000.0  # milliseconds
        }
        
        # Background threads
        self.monitoring_thread = None
        self.analysis_thread = None
        self.should_stop = False

    def start_system_monitoring(self, interval: int = 30):
        """Start continuous system monitoring."""
        if self.monitoring_thread is None:
            self.monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                daemon=True,
                name="SystemMonitoring"
            )
            self.monitoring_thread.start()
            logger.info(f"Started system monitoring with {interval}s interval")

    def stop_system_monitoring(self):
        """Stop system monitoring."""
        self.should_stop = True
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=10)
            self.monitoring_thread = None
        logger.info("System monitoring stopped")

    def add_analysis_trigger(self, trigger: Dict[str, Any]):
        """Add a trigger for automated system analysis."""
        trigger['trigger_id'] = f"trigger_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        trigger['created_at'] = datetime.now(timezone.utc).isoformat()
        trigger['enabled'] = True
        
        self.analysis_triggers.append(trigger)
        logger.info(f"Added analysis trigger: {trigger.get('name', 'unnamed')}")

    def start_system_analysis(self, analysis_type: str, project_root: str, 
                            force: bool = False) -> Dict[str, Any]:
        """Start a system awareness analysis with integration."""
        try:
            # Check if analysis is already running
            active_analyses = self.get_active_system_analyses()
            for analysis in active_analyses:
                if analysis['type'] == analysis_type and analysis['status'] == 'running':
                    return {
                        'success': False,
                        'error': f"System analysis of type '{analysis_type}' already running"
                    }
            
            # Create analysis context
            analysis_context = {
                'analysis_id': f"analysis_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
                'type': analysis_type,
                'project_root': project_root,
                'started_at': datetime.now(timezone.utc).isoformat(),
                'status': 'running',
                'progress': 0.0,
                'health_metrics': self.health_metrics,
                'discussion_triggered': False,
                'discussion_id': None,
                'results': None,
                'errors': []
            }
            
            self.active_integrations.append(analysis_context)
            
            # Trigger integrated system analysis
            result = self._run_integrated_system_analysis(analysis_context)
            
            if result['success']:
                # Update health metrics from analysis results
                if 'health_metrics' in result:
                    self.health_metrics.update(result['health_metrics'])
                    self.system_metrics_history.append({
                        **result['health_metrics'],
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                
                # Trigger discussion if analysis indicates issues
                if self._should_trigger_discussion(result):
                    discussion_result = self._trigger_discussion_from_analysis(analysis_context, result)
                    analysis_context['discussion_triggered'] = True
                    analysis_context['discussion_id'] = discussion_result.get('discussion_id')
                
                # Update analysis status
                analysis_context['completed_at'] = datetime.now(timezone.utc).isoformat()
                analysis_context['status'] = 'completed'
                analysis_context['results'] = result
                analysis_context['progress'] = 100.0
                
                logger.info(f"Completed system analysis {analysis_context['analysis_id']} of type: {analysis_type}")
                
                return {
                    'success': True,
                    'analysis_id': analysis_context['analysis_id'],
                    'discussion_triggered': analysis_context['discussion_triggered'],
                    'discussion_id': analysis_context['discussion_id'],
                    'results': result
                }
            
            else:
                analysis_context['completed_at'] = datetime.now(timezone.utc).isoformat()
                analysis_context['status'] = 'failed'
                analysis_context['errors'] = [result.get('error', 'Unknown error')]
                
                return {
                    'success': False,
                    'error': result.get('error', 'System analysis failed'),
                    'analysis_id': analysis_context['analysis_id']
                }
                
        except Exception as e:
            logger.error(f"Error starting system analysis: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _run_integrated_system_analysis(self, analysis_context: Dict[str, Any]) -> Dict[str, Any]:
        """Run integrated system analysis with discussion triggers."""
        analysis_type = analysis_context['type']
        project_root = analysis_context['project_root']
        
        try:
            # Import consolidated system awareness runner
            runner_script = Path(project_root) / "scripts" / "sa_runner.py"
            
            if not runner_script.exists():
                # Fall back to optimized runner if consolidated not available
                sys.path.insert(0, str(Path(project_root) / "tasks" / "system-awareness"))
                from optimized_system_awareness_runner import OptimizedSystemAwarenessRunner
                runner = OptimizedSystemAwarenessRunner(project_root)
                result = runner.run_optimized_analysis()
            else:
                # Per-agent container isolation (roadmap criterion 6). The
                # agent runs in a bounded container - read-only root, capped
                # memory/CPU/PIDs, no network, project mounted read-only -
                # instead of as a bare subprocess in this process's space.
                runner_cmd = [sys.executable, str(runner_script), "run",
                              "--project-root", project_root]

                if self.isolation is not None and self.isolation.available():
                    runner_result = self.isolation.run(
                        runner_cmd,
                        container_name=f"theteam-agent-{uuid.uuid4().hex[:12]}",
                        project_root=project_root,
                        env={"PYTHONPATH": PROJECT_ROOT},
                    )
                    returncode, stdout, stderr = (
                        runner_result["exit_code"],
                        runner_result["stdout"],
                        runner_result["stderr"],
                    )
                else:
                    logger.warning(
                        "Container isolation unavailable; running agent in-process"
                    )
                    import subprocess
                    _proc = subprocess.run(
                        runner_cmd,
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    returncode, stdout, stderr = _proc.returncode, _proc.stdout, _proc.stderr
                
                # Parse consolidated runner output for results
                result = {
                    "success": returncode in (0, 2),
                    "analysis_results": None,
                    "health_metrics": {},
                    "console_output": stdout,
                    "console_error": stderr,
                    "exit_code": returncode,
                    "isolated": self.isolation is not None and self.isolation.available(),
                }

                # Extract health score from output
                if returncode == 0:
                    result["health_metrics"] = {"status": "HEALTHY"}
                elif returncode == 2:
                    result["health_metrics"] = {"status": "WARNING"}
                else:
                    result["health_metrics"] = {"status": "CRITICAL"}
                
                # Update health metrics
                self._update_health_metrics(result["health_metrics"])

            return result
        except Exception as e:
            logger.error(f"Error running integrated system analysis: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _fallback_system_analysis(self, analysis_context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback system analysis when optimized runner is not available."""
        logger.info("Running fallback system analysis")
        
        # Simulate analysis based on current health metrics
        issues_found = []
        
        if self.health_metrics:
            if self.health_metrics.get('cpu_usage', 0) > self.health_thresholds['cpu_usage']:
                issues_found.append("High CPU usage detected")
            
            if self.health_metrics.get('memory_usage', 0) > self.health_thresholds['memory_usage']:
                issues_found.append("High memory usage detected")
            
            if self.health_metrics.get('disk_usage', 0) > self.health_thresholds['disk_usage']:
                issues_found.append("High disk usage detected")
        
        # Generate simulated results
        result = {
            'success': True,
            'analysis_type': analysis_context['type'],
            'project_root': analysis_context['project_root'],
            'analyzed_at': datetime.now(timezone.utc).isoformat(),
            'health_metrics': self.health_metrics,
            'issues_found': issues_found,
            'recommendations': self._generate_recommendations(issues_found),
            'generated_files': [],
            'performance': {
                'analysis_time': 2.5,
                'cpu_usage': self.health_metrics.get('cpu_usage', 0),
                'memory_usage': self.health_metrics.get('memory_usage', 0)
            }
        }
        
        return result

    def _should_trigger_discussion(self, analysis_result: Dict[str, Any]) -> bool:
        """Determine if analysis should trigger a team discussion."""
        issues_found = analysis_result.get('issues_found', [])
        
        # Check if issues meet discussion threshold
        critical_issues = [issue for issue in issues_found if any(
            critical in issue.lower() for critical in ['security', 'critical', 'urgent', 'high priority']
        )]
        
        # Trigger discussion for critical issues or multiple issues
        if len(critical_issues) > 0 or len(issues_found) >= 2:
            return True
        
        # Check if health metrics exceed thresholds
        health_metrics = analysis_result.get('health_metrics', {})
        if (health_metrics.get('cpu_usage', 0) > self.health_thresholds['cpu_usage'] or
            health_metrics.get('memory_usage', 0) > self.health_thresholds['memory_usage'] or
            health_metrics.get('disk_usage', 0) > self.health_thresholds['disk_usage']):
            return True
        
        return False

    def _trigger_discussion_from_analysis(self, analysis_context: Dict[str, Any], 
                                         analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a team discussion based on analysis results."""
        if not self.discussion_manager:
            logger.warning("Discussion manager not available - cannot trigger discussion")
            return {'success': False, 'error': 'Discussion manager not available'}
        
        # Generate discussion topic based on analysis
        issues_found = analysis_result.get('issues_found', [])
        if issues_found:
            topic = f"System Analysis: {', '.join(issues_found[:3])}"
        else:
            topic = f"System Analysis Results: {analysis_context['type'].replace('_', ' ').title()}"
        
        # Create discussion
        discussion = self.discussion_manager.create_discussion(
            topic, 
            ['architect', 'pragmatist', 'skeptic', 'security']
        )
        
        # Add analysis context to discussion
        analysis_context['discussion_id'] = discussion['discussion_id']
        
        # Add initial tasks for discussion
        tasks = [
            {
                'title': 'Review system health metrics',
                'priority': 'high',
                'assignee': 'architect',
                'phase': 'health_assessment',
                'description': 'Analyze current system health metrics and identify issues'
            },
            {
                'title': 'Develop mitigation strategies',
                'priority': 'medium',
                'assignee': 'pragmatist',
                'phase': 'solution_design',
                'description': 'Propose practical solutions for identified system issues'
            },
            {
                'title': 'Security impact assessment',
                'priority': 'critical',
                'assignee': 'security',
                'phase': 'security_review',
                'description': 'Assess security implications of system issues'
            }
        ]
        
        for task in tasks:
            try:
                task_id = self.discussion_manager.add_task(discussion['discussion_id'], task)
                logger.info(f"Added task {task_id} to discussion {discussion['discussion_id']}")
            except Exception as e:
                logger.error(f"Error adding task to discussion: {e}")
        
        # Add analysis results note
        analysis_note = {
            'type': 'analysis_results',
            'content': f"System analysis completed. Issues found: {', '.join(analysis_result.get('issues_found', ['None']))}",
            'analysis_id': analysis_context['analysis_id'],
            'recommendations': analysis_result.get('recommendations', [])
        }
        
        self.discussion_manager.add_note(discussion['discussion_id'], 'system', analysis_note)
        
        # Update analysis context
        analysis_context['discussion_id'] = discussion['discussion_id']
        analysis_context['discussion_triggered'] = True
        
        logger.info(f"Triggered discussion {discussion['discussion_id']} for analysis {analysis_context['analysis_id']}")
        
        return {
            'success': True,
            'discussion_id': discussion['discussion_id'],
            'topic': topic,
            'analysis_id': analysis_context['analysis_id']
        }

    def _check_system_issues_for_discussion(self, analysis_result: Dict[str, Any]):
        """Check system analysis results for issues that should trigger discussion."""
        issues = analysis_result.get('issues_found', [])
        
        # Check for critical patterns that should trigger discussion
        critical_patterns = [
            'security',
            'vulnerability',
            'critical',
            'urgent',
            'performance',
            'high priority'
        ]
        
        for issue in issues:
            issue_lower = issue.lower()
            if any(pattern in issue_lower for pattern in critical_patterns):
                # Add this as a trigger
                self.add_analysis_trigger({
                    'name': 'Critical Issue Trigger',
                    'description': f"Critical issue detected: {issue}",
                    'trigger_type': 'issue',
                    'issue': issue,
                    'severity': 'high'
                })

    def _generate_recommendations(self, issues_found: List[str]) -> List[str]:
        """Generate recommendations based on issues found."""
        recommendations = []
        
        for issue in issues_found:
            issue_lower = issue.lower()
            
            if 'cpu' in issue_lower:
                recommendations.extend([
                    "Upgrade CPU resources or optimize running processes",
                    "Implement load balancing if applicable",
                    "Consider auto-scaling configuration"
                ])
            
            elif 'memory' in issue_lower:
                recommendations.extend([
                    "Increase available memory or optimize memory usage",
                    "Implement memory leak detection and fixes",
                    "Consider caching optimizations"
                ])
            
            elif 'disk' in issue_lower:
                recommendations.extend([
                    "Clean up temporary files and logs",
                    "Implement disk space monitoring",
                    "Consider storage optimization or upgrade"
                ])
            
            elif 'security' in issue_lower:
                recommendations.extend([
                    "Conduct security audit and vulnerability assessment",
                    "Implement security patches and updates",
                    "Review access controls and permissions"
                ])
        
        # Add generic recommendations
        if issues_found:
            recommendations.extend([
                "Schedule regular system health checks",
                "Implement automated monitoring and alerting",
                "Create disaster recovery and backup procedures"
            ])
        
        return list(set(recommendations))[:5]  # Limit to 5 unique recommendations

    def _monitoring_loop(self):
        """Background system monitoring loop."""
        while not self.should_stop:
            try:
                # Update health metrics
                self._update_health_metrics()
                
                # Check analysis triggers
                self._check_analysis_triggers()
                
                # Save state if state manager available
                if self.state_manager:
                    self.state_manager.save_state()
                
                # Sleep until next iteration
                time.sleep(30)  # 30 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                time.sleep(60)  # Wait longer on error

    def _update_health_metrics(self):
        """Update current health metrics from system."""
        # This is a simulated implementation - in production, this would
        # collect actual system metrics from monitoring tools
        
        current_metrics = {
            'cpu_usage': 45.2 + (hash(time.time()) % 30) / 100,  # Simulated fluctuation
            'memory_usage': 62.8 + (hash(time.time() * 2) % 25) / 100,
            'disk_usage': 78.3 + (hash(time.time() * 3) % 15) / 100,
            'response_time': 245.0 + (hash(time.time() * 4) % 500),
            'active_processes': 150 + (hash(time.time() * 5) % 50),
            'network_io': 1024.5 + (hash(time.time() * 6) % 500),
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Update metrics
        self.health_metrics.update(current_metrics)
        self.system_metrics_history.append(current_metrics)
        
        # Keep history manageable
        if len(self.system_metrics_history) > 1000:
            self.system_metrics_history = self.system_metrics_history[-1000:]
        
        logger.debug(f"Updated health metrics: {current_metrics}")

    def _check_analysis_triggers(self):
        """Check if any analysis triggers should be executed."""
        for trigger in self.analysis_triggers[:]:  # Copy to avoid modification during iteration
            if not trigger.get('enabled', True):
                continue
            
            # Check trigger conditions based on type
            should_trigger = False
            
            if trigger.get('trigger_type') == 'issue':
                # Trigger based on current health metrics
                issues = trigger.get('issues', [])
                current_issues = self._identify_current_issues()
                
                for issue in issues:
                    if issue.lower() in current_issues:
                        should_trigger = True
                        break
            
            elif trigger.get('trigger_type') == 'threshold':
                # Trigger based on metric thresholds
                metrics = trigger.get('metrics', {})
                if self._check_threshold_conditions(metrics):
                    should_trigger = True
            
            elif trigger.get('trigger_type') == 'schedule':
                # Trigger based on schedule
                if self._check_schedule_conditions(trigger):
                    should_trigger = True
            
            if should_trigger:
                # Execute trigger
                trigger['last_triggered'] = datetime.now(timezone.utc).isoformat()
                trigger['trigger_count'] = trigger.get('trigger_count', 0) + 1
                
                # Disable trigger if one-time
                if trigger.get('one_time', False):
                    trigger['enabled'] = False
                
                # Run analysis
                analysis_type = trigger.get('analysis_type', 'infrastructure_assessment')
                result = self.start_system_analysis(
                    analysis_type, 
                    str(self.project_root),
                    force=False
                )
                
                logger.info(f"Triggered analysis from {trigger.get('name', 'unnamed')} trigger: {result}")
                
                # Remove executed one-time triggers
                if trigger.get('one_time', False):
                    self.analysis_triggers.remove(trigger)

    def _identify_current_issues(self) -> List[str]:
        """Identify current system issues based on health metrics."""
        issues = []
        
        if self.health_metrics:
            if self.health_metrics.get('cpu_usage', 0) > self.health_thresholds['cpu_usage']:
                issues.append('cpu usage')
            
            if self.health_metrics.get('memory_usage', 0) > self.health_thresholds['memory_usage']:
                issues.append('memory usage')
            
            if self.health_metrics.get('disk_usage', 0) > self.health_thresholds['disk_usage']:
                issues.append('disk usage')
            
            if self.health_metrics.get('response_time', 0) > self.health_thresholds['response_time']:
                issues.append('response time')
        
        return issues

    def _check_threshold_conditions(self, metrics: Dict[str, Any]) -> bool:
        """Check if current metrics meet threshold conditions."""
        for metric_name, threshold in metrics.items():
            current_value = self.health_metrics.get(metric_name)
            if current_value is not None and current_value > threshold:
                return True
        return False

    def _check_schedule_conditions(self, trigger: Dict[str, Any]) -> bool:
        """Check if schedule conditions are met for trigger."""
        # This is a simplified implementation
        # In production, this would check against actual schedule
        return False

    def get_active_system_analyses(self) -> List[Dict[str, Any]]:
        """Get all active system analyses."""
        return [analysis for analysis in self.active_integrations 
                if analysis.get('status') == 'running']

    def get_system_analysis_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get system analysis history."""
        # This would normally retrieve from database or ledger
        return []

    def get_health_metrics_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get health metrics history."""
        return self.system_metrics_history[-limit:] if self.system_metrics_history else []

    def get_system_integration_status(self) -> Dict[str, Any]:
        """Get overall system integration status."""
        active_analyses = self.get_active_system_analyses()
        
        return {
            'monitoring_active': self.monitoring_thread is not None,
            'active_analyses': len(active_analyses),
            'analysis_triggers': len(self.analysis_triggers),
            'health_metrics_updated': len(self.system_metrics_history) > 0,
            'health_metrics': self.health_metrics,
            'status': 'healthy' if len(active_analyses) == 0 else 'analyzing',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

    def cleanup_completed_analyses(self, max_age_hours: int = 24):
        """Clean up completed analyses that are too old."""
        current_time = datetime.now(timezone.utc)
        cutoff_time = current_time.timestamp() - (max_age_hours * 3600)
        
        to_remove = []
        for analysis in self.active_integrations:
            if analysis.get('status') == 'completed':
                completed_at = datetime.fromisoformat(analysis.get('completed_at', '')).timestamp()
                if completed_at < cutoff_time:
                    to_remove.append(analysis)
        
        for analysis in to_remove:
            self.active_integrations.remove(analysis)
            logger.info(f"Cleaned up completed analysis {analysis.get('analysis_id')}")
        
        return len(to_remove)

    def __del__(self):
        """Cleanup when object is deleted."""
        self.should_stop = True
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=5)
        logger.info("System integration cleaned up")
if __name__ == "__main__":
    # Example usage
    import sys
    
    project_root = sys.argv[1] if len(sys.argv) > 1 else "./"
    
    # Initialize integration
    integration = SystemIntegration(project_root)
    
    # Start system monitoring
    integration.start_system_monitoring()
    
    # Add some example triggers
    integration.add_analysis_trigger({
        'name': 'High CPU Usage Trigger',
        'description': 'Trigger analysis when CPU usage exceeds 80%',
        'trigger_type': 'threshold',
        'metrics': {'cpu_usage': 80.0},
        'analysis_type': 'infrastructure_assessment'
    })
    
    integration.add_analysis_trigger({
        'name': 'Memory Alert Trigger',
        'description': 'Trigger analysis when memory usage exceeds 90%',
        'trigger_type': 'threshold',
        'metrics': {'memory_usage': 90.0},
        'analysis_type': 'performance_analysis'
    })
    
    # Start an example analysis
    result = integration.start_system_analysis('infrastructure_assessment', project_root)
    print(f"Started system analysis: {result}")
    
    # Check integration status
    status = integration.get_system_integration_status()
    print(f"Integration status: {status}")
    
    print("\nSystem integration example completed successfully!")