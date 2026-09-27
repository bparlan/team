#!/usr/bin/env python3
"""
Rich-based Terminal UI for theteam skill enhancement.

This module provides a comprehensive terminal user interface with:
- Tabbed interface for different views
- Real-time status dashboards
- Interactive menu systems
- System awareness integration
- Team discussion management

Uses Rich library for modern terminal rendering instead of curses.
"""

import os
import sys
import time
import threading
import queue
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from enum import Enum

# Import Rich components
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.padding import Padding
from rich.align import Align
from rich import print as rprint
from rich import box

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add scripts directory to path for sa_runner imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

    # Try relative imports first, fall back to absolute for standalone execution
    try:
        from .task_stack_adapter import TaskStackAdapter
        from ..core.state_manager import get_state_manager
        from ..workflow.discussion_manager_refactored import DiscussionManager
    except ImportError:
        # Standalone execution - add parent to path
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from task_stack_adapter import TaskStackAdapter
        from theteam.core.state_manager import get_state_manager
        from theteam.workflow.discussion_manager_refactored import create_discussion_manager

# Import sa_runner functions (always absolute since scripts/ is not a package)
from sa_runner import get_loop_state, get_last_health_score
from sa_runner import _load_state, _save_state
from sa_runner import self_correct
from sa_runner import cmd_health_check
from sa_runner import run_analysis

class ViewType(Enum):
    DASHBOARD = "dashboard"
    DISCUSSIONS = "discussions"
    SYSTEM_AWARENESS = "system_awareness"
    TASKS = "tasks"
    MEMBERS = "members"
    REPORTS = "reports"
    SETTINGS = "settings"

class TerminalUI:
    def __init__(self, project_root: str, state_manager=None, discussion_manager=None):
        self.project_root = Path(project_root).resolve()
        self.state_manager = state_manager
        self.discussion_manager = discussion_manager

        # UI state
        self.current_view = ViewType.DASHBOARD
        self.active_tabs = [ViewType.DASHBOARD, ViewType.TASKS, ViewType.REPORTS, ViewType.SYSTEM_AWARENESS]
        self.current_tab_index = 0

        # Interactive state
        self.selected_item = 0
        self.help_text = ""
        self.input_mode = False
        self.input_buffer = ""

        # Threads
        self.refresh_thread = None
        self.input_thread = None
        self.should_exit = False
        self.input_queue = queue.Queue()

        # Rich console
        self.console = Console()

        # Task Stack Adapter
        self.task_stack_adapter = TaskStackAdapter(project_root)

    def refresh_data(self):
        """Fetch latest state from disk safely without blocking UI thread."""
        try:
            from sa_runner import get_loop_state, get_last_health_score
            self.cached_loop_state = get_loop_state() or {}
            self.cached_health_score = get_last_health_score() or {}
            self.last_refresh_time = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f'Error refreshing TUI data: {e}')

    def _refresh_loop(self):
        """Background refresh loop."""
        while not self.should_exit:
            self.refresh_data()
            time.sleep(2)

    def _input_worker(self):
        """Worker thread for non-blocking keyboard input."""
        while not self.should_exit:
            try:
                # Use non-blocking read with timeout
                import select
                if select.select([sys.stdin], [], [], 0.1)[0]:
                    ch = sys.stdin.read(1)
                    if ch:
                        self.input_queue.put(ord(ch))
            except Exception:
                pass

    def handle_input(self, ch: int):
        """Handle keyboard commands and interactive navigation."""
        if ch == -1:
            return

        if ch in (ord('q'), ord('Q')):
            self.should_exit = True
        elif ch in (ord('s'), ord('S')):
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'scripts'))
                from sa_runner import _load_state, _save_state
                state = _load_state()
                if state:
                    state["loop_active"] = True
                    _save_state(state)
                    self.help_text = "Loop started (active=True)"
                else:
                    self.help_text = "Error: Could not load state"
            except Exception as e:
                self.help_text = f"Error: {e}"
        elif ch in (ord('t'), ord('T')):
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'scripts'))
                from sa_runner import _load_state, _save_state
                state = _load_state()
                if state:
                    state["loop_active"] = False
                    _save_state(state)
                    self.help_text = "Loop stopped (active=False)"
                else:
                    self.help_text = "Error: Could not load state"
            except Exception as e:
                self.help_text = f"Error: {e}"
        elif ch in (ord('r'), ord('R')):
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'scripts'))
                from sa_runner import self_correct
                self.help_text = "Running self-correction..."
                self_correct()
                self.help_text = "Self-correction complete."
            except Exception as e:
                self.help_text = f"Error: {e}"
        elif ch in (ord('h'), ord('H')):
            try:
                sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / 'scripts'))
                from sa_runner import run_analysis
                res = run_analysis()
                if res:
                    self.help_text = "Health check completed."
                else:
                    self.help_text = "Health check failed."
            except Exception as e:
                self.help_text = f"Error: {e}"
        elif ch == 260 or ch == 65361:  # LEFT arrow
            self.current_tab_index = (self.current_tab_index - 1) % len(self.active_tabs)
            self.current_view = self.active_tabs[self.current_tab_index]
            self.help_text = f"View: {self.current_view.value}"
        elif ch == 261 or ch == 65363:  # RIGHT arrow
            self.current_tab_index = (self.current_tab_index + 1) % len(self.active_tabs)
            self.current_view = self.active_tabs[self.current_tab_index]
            self.help_text = f"View: {self.current_view.value}"

    def draw_header(self):
        """Draw the UI header."""
        current_time = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        status_text = f"[{current_time}]"
        
        if self.state_manager:
            status_text += " ✅ State Manager Active "
        if self.discussion_manager:
            status_text += "💬 Discussion Manager Active "

        status_text += f" | Tab: {self.active_tabs[self.current_tab_index].value.upper()}"
        
        # Build header content as a single Text object using Text.assemble
        header_content = Text.assemble(
            ("🚀 THE TEAM - Enhanced Skill Suite", "bold cyan"),
            ("\nReal-time Team Discussion & System Analysis Dashboard", "green"),
            ("\n", ""),
            (status_text, "blue")
        )

        return Panel(
            Align.center(header_content),
            title="Header",
            box=box.ROUNDED,
            border_style="cyan"
        )

    def draw_tabs(self):
        """Draw the tabbed interface."""
        tab_line = ""
        for i, tab in enumerate(self.active_tabs):
            if i == self.current_tab_index:
                tab_line += f"  [ {tab.value.upper()} ]  "
            else:
                tab_line += f"   {tab.value.upper()}   "
        
        return Panel(
            Text(tab_line, style="bold white"),
            title="Navigation",
            box=box.ROUNDED,
            border_style="green"
        )

    def draw_dashboard(self):
        """Draw the main dashboard view."""
        state = getattr(self, 'cached_loop_state', {})
        health = getattr(self, 'cached_health_score', {})
        
        # System metrics table
        system_table = Table(title="📊 SYSTEM OVERVIEW", box=box.ROUNDED)
        system_table.add_column("Metric", style="cyan")
        system_table.add_column("Value", style="green")
        
        dashboard_data = self.task_stack_adapter.get_unified_dashboard_data()
        stack_status = dashboard_data.get('task_stack_status', {})
        
        system_table.add_row("Tasks", f"{stack_status.get('total_tasks', 0)} total, {stack_status.get('active_tasks', 0)} active")
        
        if self.state_manager:
            dashboard = self.state_manager.get_unified_dashboard()
            system_table.add_row("Discussions", f"{len(dashboard.get('active_discussions', []))}")
            system_table.add_row("Analyses", f"{len(dashboard.get('active_analyses', []))}")
            system_table.add_row("Pending Tasks", f"{len(dashboard.get('pending_tasks', []))}")
        else:
            system_table.add_row("State Manager", "⚠️ Not Available", style="red")
        
        # System Awareness section
        system_table2 = Table(title="🔄 SYSTEM AWARENESS & HEALTH", box=box.ROUNDED)
        system_table2.add_column("Metric", style="cyan")
        system_table2.add_column("Value", style="green")
        
        overall = health.get("overall_score", state.get("health_score", {}).get("overall_score", 0.0))
        grade = health.get("grade", state.get("health_score", {}).get("grade", "N/A"))
        cb_state = state.get("circuit_breaker", {}).get("state", "N/A")
        active = state.get("loop_active", False)
        
        system_table2.add_row("Overall Health Score", f"{overall:.2f} ({grade})")
        system_table2.add_row("Circuit Breaker State", cb_state.upper(), style="yellow" if cb_state == "open" else "green")
        system_table2.add_row("Loop Status", "ACTIVE" if active else "INACTIVE", style="green" if active else "red")
        
        # Quick Actions section
        actions_table = Table(title="⚡ QUICK ACTIONS", box=box.ROUNDED)
        actions_table.add_column("Action", style="cyan")
        actions_table.add_column("Description", style="green")
        
        actions = [
            ("Start New Discussion", "Create a new team discussion"),
            ("Run System Analysis", "Analyze project system architecture"),
            ("View Reports", "Generate and view analysis reports"),
            ("Manage Team", "Manage team members and roles"),
        ]
        
        for action, description in actions:
            actions_table.add_row(f"  📌 {action}", f"- {description}")
        
        return [system_table, system_table2, actions_table]

    def draw_tasks_view(self):
        """Draw the tasks management view."""
        dashboard_data = self.task_stack_adapter.get_unified_dashboard_data()
        task_stack_status = dashboard_data.get('task_stack_status', {})
        pending_tasks = dashboard_data.get('pending_tasks', [])
        active_tasks = dashboard_data.get('active_tasks', [])
        
        task_table = Table(title="📋 TASK STACK OVERVIEW", box=box.ROUNDED)
        task_table.add_column("Metric", style="cyan")
        task_table.add_column("Value", style="green")
        
        task_table.add_row("Total Tasks", f"{task_stack_status.get('total_tasks', 0)}")
        task_table.add_row("Active Tasks", f"{len(active_tasks)}")
        task_table.add_row("Pending Tasks", f"{len(pending_tasks)}")
        
        # Active tasks table
        tasks_table = Table(title="▶ Active & Pending Tasks (Top 5)", box=box.ROUNDED)
        tasks_table.add_column("Task", style="cyan")
        tasks_table.add_column("Status", style="green")
        
        display_tasks = (active_tasks + pending_tasks)[:5]
        if display_tasks:
            for task in display_tasks:
                title = task.get('title', 'Untitled')
                status = task.get('status', 'unknown')
                tasks_table.add_row(f"  - {title}", f"[{status}]")
        else:
            tasks_table.add_row("No active or pending tasks.", "")
        
        return [task_table, tasks_table]

    def draw_log_view(self):
        """Draw the scrollable log/report view."""
        log_table = Table(title="📜 RECENT LOGS & REPORTS", box=box.ROUNDED)
        log_table.add_column("Log", style="cyan")
        
        log_content = [
            "[Log messages and reports will appear here]",
            "- System status updates",
            "- Circuit breaker events",
            "- Self-correction attempts",
            "- Recent analysis results"
        ]
        
        for line in log_content:
            log_table.add_row(line)
        
        return [log_table]

    def draw_help(self):
        """Draw the help view with task stack info."""
        help_text = [
            "Navigation:",
            "  TAB             - Switch between views/tabs",
            "  ↑/↓             - Navigate lists",
            "  ←/→             - Navigate tabs",
            "",
            "Actions:",
            "  ENTER           - Select/activate item",
            "  'q'             - Quit application",
            "  'h'             - Show/hide help",
            "  '/'             - Filter/search",
            "",
            "Task Stack Actions:",
            "  't'             - Switch to Tasks view",
            "  'r'             - Refresh task data",
            "",
            "Views:",
            "  Dashboard       - Main status overview",
            "  Discussions     - Active team discussions",
            "  System Awareness - System analysis status",
            "  Tasks          - Task management",
            "  Members        - Team member information",
        ]
        
        help_table = Table(title="❓ HELP & KEY BINDINGS", box=box.ROUNDED)
        help_table.add_column("Info", style="cyan")
        
        for line in help_text:
            help_table.add_row(line)
        
        return [help_table]

    def draw_footer(self):
        """Draw interactive keybinding help menu at the bottom."""
        help_bar = " [Q] Quit | [S] Start Loop | [T] Stop Loop | [R] Self-Correct | [H] Run Analysis "
        if self.help_text:
            msg = f" Status: {self.help_text} "
            return Panel(
                Text(msg + help_bar, style="bold cyan"),
                title="Footer",
                box=box.ROUNDED,
                border_style="green"
            )
        else:
            return Panel(
                Text(help_bar, style="bold cyan"),
                title="Footer",
                box=box.ROUNDED,
                border_style="green"
            )

    def draw(self):
        """Main rendering method."""
        # Build layout
        layout = Layout(name="root")
        layout.split(
            Layout(name="header", size=6),
            Layout(name="tabs", size=3),
            Layout(name="main", size=20),
            Layout(name="footer", size=3),
        )
        
        # Header
        layout["header"].update(self.draw_header())
        
        # Tabs
        layout["tabs"].update(self.draw_tabs())
        
        # Main content based on current view
        if self.current_view == ViewType.DASHBOARD:
            main_content = self.draw_dashboard()
        elif self.current_view == ViewType.TASKS:
            main_content = self.draw_tasks_view()
        elif self.current_view == ViewType.REPORTS:
            main_content = self.draw_log_view()
        else:
            main_content = self.draw_dashboard()
        
        # Combine main content tables
        if isinstance(main_content, list):
            # Create a combined panel for multiple tables
            combined_text = ""
            for table in main_content:
                combined_text += str(table) + "\n\n"
            layout["main"].update(Panel(Align.center(Text(combined_text)), title="Main Content", box=box.ROUNDED))
        else:
            layout["main"].update(main_content)
        
        # Footer
        layout["footer"].update(self.draw_footer())
        
        return layout

    def start(self):
        """Start the terminal UI."""
        # Start refresh thread
        self.refresh_thread = threading.Thread(
            target=self._refresh_loop,
            daemon=True
        )
        self.refresh_thread.start()
        
        # Start input worker thread
        self.input_thread = threading.Thread(
            target=self._input_worker,
            daemon=True
        )
        self.input_thread.start()
        
        # Start the Rich Live display
        with Live(
            self.draw(),
            console=self.console,
            screen=True,
            refresh_per_second=4
        ) as live:
            while not self.should_exit:
                try:
                    # Get input from queue with timeout
                    try:
                        ch = self.input_queue.get(timeout=0.1)
                        self.handle_input(ch)
                    except queue.Empty:
                        pass
                    
                    # Refresh the display
                    live.update(self.draw())
                    time.sleep(0.1)
                except KeyboardInterrupt:
                    self.should_exit = True
                except Exception as e:
                    logger.error(f"Error in UI: {e}")
                    self.should_exit = True

    def stop(self):
        """Stop the UI."""
        self.should_exit = True
        if self.refresh_thread:
            self.refresh_thread.join(timeout=5)
        if self.input_thread:
            self.input_thread.join(timeout=5)

    # Example usage
    project_root = sys.argv[1] if len(sys.argv) > 1 else "./"

    # Initialize components
    from theteam.core.state_manager import get_state_manager
    from theteam.workflow.discussion_manager_refactored import create_discussion_manager

    state_manager = get_state_manager()
    discussion_manager = create_discussion_manager(project_root, state_manager)

    # Create and start UI
    ui = TerminalUI(project_root, state_manager, discussion_manager)
    ui.start()