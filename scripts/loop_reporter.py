#!/usr/bin/env python3
"""
Loop reporter for theteam skill.

Generates comprehensive reports of loop execution including
task results, duration, summary statistics, and archive storage.
"""

import os
import sys
import json
from datetime import datetime, timezone
from pathlib import Path

# Add current directory to path for imports
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURRENT_DIR)

from loop_state import LoopState

class LoopReporter:
    """Generates and archives reports for task loop execution."""
    
    def __init__(self, project_root=None):
        if project_root is None:
            project_root = os.getcwd()
        self.project_root = project_root
        self.state = LoopState(os.path.join(project_root, ".loop-state.json"))
        self.report_dir = os.path.join(project_root, ".omp", "theteam", "reports")
        self.archive_dir = os.path.join(project_root, ".loop-archive")
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Ensure report and archive directories exist."""
        os.makedirs(self.report_dir, exist_ok=True)
        os.makedirs(self.archive_dir, exist_ok=True)
    
    def generate_report(self, output_path=None):
        """Generate a markdown report of loop execution."""
        summary = self.state.get_summary()
        state_dict = self.state.to_dict()
        
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        if output_path is None:
            output_path = os.path.join(self.report_dir, f"{date_str}-loop-report.md")
        
        # Build markdown report
        lines = [
            f"# theteam — Task Loop Report",
            f"",
            f"- **Project:** {state_dict.get('project', 'team-skill')}",
            f"- **Generated:** {timestamp}",
            f"- **Loop Status:** {'active' if summary['loop_active'] else 'completed'}",
            f"- **Tasks Executed:** {summary['completed_tasks']}/{summary['total_tasks']}",
            f"",
            f"## Task Results",
            f"",
            f"| Task | Status | Result | Output |",
            f"|------|--------|--------|--------|"
        ]
        
        # Add completed tasks
        for task in state_dict.get("completed_tasks", []):
            lines.append(f"| {task['task']} | ✅ completed | {task['result']} | {task.get('output', '')[:40]}... |")
        
        # Add failed tasks
        for task in state_dict.get("failed_tasks", []):
            lines.append(f"| {task['task']} | ❌ failed | {task['error']} | {task.get('output', '')[:40]}... |")
        
        # Add blocked tasks
        for task in state_dict.get("blocked_tasks", []):
            lines.append(f"| {task['task']} | ⚠️ blocked | {task['reason']} | - |")
        
        # Add summary section
        lines.extend([
            f"",
            f"## Summary",
            f"",
            f"- **Total tasks:** {summary['total_tasks']}",
            f"- **Completed:** {summary['completed_tasks']}",
            f"- **Failed:** {summary['failed_tasks']}",
            f"- **Blocked:** {summary['blocked_tasks']}",
            f"- **Last execution:** {summary['last_execution'] or 'Never'}",
            f"",
            f"## Next Steps",
            f"",
            f"- Review failed tasks if any",
            f"- Check task archive for upcoming tasks",
            f"- Use `theteam --loop start` to resume loop"
        ])
        
        report_content = '\n'.join(lines)
        
        # Write report
        with open(output_path, 'w') as f:
            f.write(report_content)
        
        print(f"Report generated: {output_path}")
        
        # Archive report
        self._archive_report(output_path, date_str)
        
        return output_path
    
    def _archive_report(self, report_path, date_str):
        """Archive report to the archive directory."""
        archive_path = os.path.join(self.archive_dir, f"{date_str}-loop-report.md")
        try:
            with open(report_path, 'r') as src, open(archive_path, 'w') as dst:
                dst.write(src.read())
        except IOError as e:
            print(f"Warning: Failed to archive report: {e}")
    
    def print_summary(self):
        """Print a concise summary to terminal."""
        summary = self.state.get_summary()
        print("\n" + "="*50)
        print("THE TEAM - Task Loop Summary")
        print("="*50)
        print(f"Loop Status:     {'ACTIVE' if summary['loop_active'] else 'COMPLETED'}")
        print(f"Completed Tasks: {summary['completed_tasks']}")
        print(f"Failed Tasks:    {summary['failed_tasks']}")
        print(f"Blocked Tasks:   {summary['blocked_tasks']}")
        print(f"Total Tasks:     {summary['total_tasks']}")
        print(f"Last Execution:  {summary['last_execution'] or 'Never'}")
        print("="*50 + "\n")

def main():
    """Main entry point for loop reporter."""
    reporter = LoopReporter()
    
    if len(sys.argv) < 2:
        print("Usage: loop_reporter.py <command> [args]")
        print("Commands: generate, summary")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "generate":
        output_path = sys.argv[2] if len(sys.argv) > 2 else None
        reporter.generate_report(output_path)
    elif command == "summary":
        reporter.print_summary()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()