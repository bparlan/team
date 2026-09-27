#!/usr/bin/env python3
"""
Routine Engine Scheduler
Automated loop execution with dependency management and safety controls.
"""

import json
import os
import yaml
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

class RoutineScheduler:
    def __init__(self, routines_dir: str = "routines", safety_dir: str = "safety"):
        self.routines_dir = Path(routines_dir)
        self.safety_dir = Path(safety_dir)
        self.config_file = Path("config/routines.yaml")
        self.load_config()
        self.active_routines: Dict[str, Dict] = {}
        self.execution_history: List[Dict] = []

    def load_config(self):
        """Load routine configuration from YAML file"""
        default_config = {
            "schedules": {
                "daily-maintenance": {
                    "time": "00:30",
                    "enabled": True,
                    "days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                },
                "weekly-analysis": {
                    "time": "09:00",
                    "day": "mon",
                    "enabled": True
                },
                "monthly-evolution": {
                    "time": "17:00", 
                    "day": "1",
                    "enabled": True
                }
            },
            "dependencies": {
                "weekly-analysis": ["daily-maintenance"],
                "monthly-evolution": ["weekly-analysis", "daily-maintenance"]
            },
            "safety": {
                "pre_execution_validation": True,
                "auto_rollback": True,
                "max_retries": 3,
                "retry_delay": 60
            }
        }
        
        if self.config_file.exists():
            with open(self.config_file, 'r') as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = default_config
            self.save_config()
    
    def save_config(self):
        """Save routine configuration to YAML file"""
        self.config_file.parent.mkdir(exist_ok=True)
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)
    
    def add_routine(self, routine_name: str, schedule: Dict, dependencies: List[str] = None):
        """Add a new routine with schedule and dependencies"""
        routine_config = {
            "schedule": schedule,
            "dependencies": dependencies or [],
            "enabled": True,
            "last_executed": None,
            "execution_count": 0,
            "success_rate": 1.0
        }
        
        self.config["schedules"][routine_name] = routine_config
        if dependencies:
            self.config["dependencies"][routine_name] = dependencies
        
        self.save_config()
        return routine_config
    
    def should_execute(self, routine_name: str) -> bool:
        """Check if routine should execute based on schedule"""
        if routine_name not in self.config["schedules"]:
            return False
            
        schedule = self.config["schedules"][routine_name]
        if not schedule["enabled"]:
            return False
            
        now = datetime.now()
        
        if "days" in schedule:
            if now.strftime("%a").lower() not in schedule["days"]:
                return False
                
            # Check time
            current_time = now.strftime("%H:%M")
            if current_time < schedule["time"]:
                return False
                
        elif "day" in schedule:
            # Monthly or weekly schedules
            if "day" in schedule:
                if now.day != int(schedule["day"]):
                    return False
                    
            if "time" in schedule:
                current_time = now.strftime("%H:%M")
                if current_time < schedule["time"]:
                    return False
        
        # Check dependencies
        if routine_name in self.config["dependencies"]:
            for dep in self.config["dependencies"][routine_name]:
                if not self.was_executed_recently(dep):
                    return False
        
        return True
    
    def was_executed_recently(self, routine_name: str, minutes: int = 60) -> bool:
        """Check if routine was executed recently"""
        if routine_name not in self.execution_history:
            return False
            
        last_exec = self.execution_history[routine_name]["last_executed"]
        if not last_exec:
            return False
            
        time_diff = datetime.now() - last_exec
        return time_diff.total_seconds() < (minutes * 60)
    
    def schedule_next_execution(self, routine_name: str) -> datetime:
        """Calculate next execution time for routine"""
        if routine_name not in self.config["schedules"]:
            return None
            
        schedule = self.config["schedules"][routine_name]
        now = datetime.now()
        
        if "days" in schedule:
            # Daily routine - next occurrence at specified time today
            next_run = datetime.strptime(now.strftime("%Y-%m-%d") + f" {schedule['time']}", 
                                       "%Y-%m-%d %H:%M")
            if next_run <= now:
                next_run += timedelta(days=1)
        elif "day" in schedule:
            # Monthly/weekly routine
            next_run = now.replace(day=int(schedule["day"]))
            next_run = next_run.replace(hour=int(schedule["time"].split(":")[0]),
                                      minute=int(schedule["time"].split(":")[1]))
            if next_run <= now:
                if "day" in schedule and schedule["day"] == "1":
                    # Monthly - go to next month
                    if now.month == 12:
                        next_run = now.replace(year=now.year + 1, month=1, day=1)
                    else:
                        next_run = now.replace(month=now.month + 1, day=1)
                else:
                    # Weekly - go to next week
                    next_run += timedelta(weeks=1)
        
        return next_run
    
    def start_routine_execution(self, routine_name: str) -> Dict:
        """Start execution of a routine"""
        start_time = datetime.now()
        execution_id = f"{routine_name}_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        execution_record = {
            "execution_id": execution_id,
            "routine_name": routine_name,
            "start_time": start_time,
            "status": "started",
            "attempts": 0
        }
        
        self.active_routines[execution_id] = execution_record
        
        # Update schedule config
        if routine_name in self.config["schedules"]:
            self.config["schedules"][routine_name]["last_executed"] = start_time
            self.config["schedules"][routine_name]["execution_count"] += 1
        
        self.save_config()
        return execution_record
    
    def complete_routine_execution(self, execution_id: str, success: bool, result: Dict = None):
        """Complete routine execution"""
        if execution_id not in self.active_routines:
            return
            
        execution_record = self.active_routines[execution_id]
        end_time = datetime.now()
        execution_record["end_time"] = end_time
        execution_record["status"] = "completed" if success else "failed"
        execution_record["result"] = result or {}
        execution_record["duration"] = (end_time - execution_record["start_time"]).total_seconds()
        
        # Update success rate
        if routine_name in self.config["schedules"]:
            schedule = self.config["schedules"][routine_name]
            total_executions = schedule["execution_count"]
            if success:
                schedule["success_rate"] = ((schedule["success_rate"] * (total_executions - 1)) + 1) / total_executions
            else:
                schedule["success_rate"] = ((schedule["success_rate"] * (total_executions - 1))) / total_executions
        
        # Add to history
        if "execution_history" not in self.__dict__:
            self.execution_history = {}
        
        routine_name = execution_record["routine_name"]
        if routine_name not in self.execution_history:
            self.execution_history[routine_name] = []
        
        self.execution_history[routine_name].append(execution_record)
        
        # Clean up active routines (keep only recent)
        if len(self.active_routines) > 10:
            oldest_key = min(self.active_routines.keys())
            del self.active_routines[oldest_key]
        
        self.save_config()
    
    def get_routine_status(self, routine_name: str = None) -> Dict:
        """Get status of routines with consistent interface"""
        if routine_name:
            if routine_name not in self.config["schedules"]:
                return {"error": f"Routine {routine_name} not found"}
            
            # Convert config dict to status dict for consistency
            config = self.config["schedules"][routine_name]
            status = {
                "time": config.get("time"),
                "enabled": config.get("enabled", True),
                "last_executed": config.get("last_executed"),
                "execution_count": config.get("execution_count", 0),
                "success_rate": config.get("success_rate", 1.0),
                "next_execution": self.schedule_next_execution(routine_name),
                "dependencies": self.config["dependencies"].get(routine_name, [])
            }
            return status
        else:
            status = {}
            for name, config in self.config["schedules"].items():
                next_execution = self.schedule_next_execution(name)
                status[name] = {
                    "enabled": config.get("enabled", True),
                    "last_executed": config.get("last_executed"),
                    "execution_count": config.get("execution_count", 0),
                    "success_rate": config.get("success_rate", 1.0),
                    "next_execution": next_execution,
                    "dependencies": self.config["dependencies"].get(name, [])
                }
            return status
    
    def pause_routine(self, routine_name: str):
        """Pause a routine"""
        if routine_name in self.config["schedules"]:
            self.config["schedules"][routine_name]["enabled"] = False
            self.save_config()
    
    def resume_routine(self, routine_name: str):
        """Resume a routine"""
        if routine_name in self.config["schedules"]:
            self.config["schedules"][routine_name]["enabled"] = True
            self.save_config()

# Standalone execution function
def execute_daily_maintenance():
    """Execute daily maintenance routine"""
    from engine.executor import RoutineExecutor
    
    executor = RoutineExecutor()
    executor.execute_routine("daily-maintenance")

def execute_weekly_analysis():
    """Execute weekly analysis routine"""
    from engine.executor import RoutineExecutor
    
    executor = RoutineExecutor()
    executor.execute_routine("weekly-analysis")

def execute_monthly_evolution():
    """Execute monthly evolution routine"""
    from engine.executor import RoutineExecutor
    
    executor = RoutineExecutor()
    executor.execute_routine("monthly-evolution")

if __name__ == "__main__":
    import sys
    print("Routine Scheduler initialized")
    print("Available routines:", list(get_routine_status().keys()))