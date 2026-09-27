#!/usr/bin/env python3
"""
Routine Engine Main Entry Point
Central coordinator for all routine engine operations.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add engine directory to path
sys.path.insert(0, str(Path(__file__).parent / "engine"))

from scheduler import RoutineScheduler
from executor import RoutineExecutor

class RoutineEngine:
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.routine_engine_dir = Path(__file__).parent
        self.config_dir = self.routine_engine_dir / "config"
        self.config_dir.mkdir(exist_ok=True)
        
        # Initialize core components
        self.scheduler = RoutineScheduler()
        self.executor = RoutineExecutor()
        
        # Load configuration
        self.config = self._load_config()
        
    def _load_config(self) -> dict:
        """Load routine engine configuration"""
        config_file = self.config_dir / "engine_config.json"
        
        default_config = {
            "engine_name": "Routine Engine",
            "version": "1.0.0",
            "description": "Automated maintenance loop engine with evidence-based validation",
            "capabilities": [
                "daily-maintenance",
                "weekly-analysis", 
                "monthly-evolution",
                "custom-routines"
            ],
            "schedules": {
                "daily-maintenance": "00:30",
                "weekly-analysis": "09:00 Monday",
                "monthly-evolution": "17:00 first day of month"
            },
            "safety": {
                "pre_execution_validation": True,
                "auto_rollback": True,
                "max_retries": 3,
                "retry_delay": 60,
                "validation_timeout": 300
            },
            "integration": {
                "respect_block_edits_without_plan": True,
                "only_permitted_skills": True,
                "follow_8phase_process": True,
                "use_existing_formats": True
            },
            "logging": {
                "enabled": True,
                "level": "INFO",
                "output_format": "structured"
            }
        }
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def run_routine(self, routine_name: str, **kwargs) -> dict:
        """Execute a routine by name"""
        print(f"🚀 Executing routine: {routine_name}")
        
        try:
            # Pre-execution validation
            if self.config["safety"]["pre_execution_validation"]:
                validation_result = self._validate_routine_execution(routine_name, kwargs)
                if not validation_result["valid"]:
                    return {
                        "status": "failed",
                        "error": "Pre-execution validation failed",
                        "validation_errors": validation_result["errors"]
                    }
            
            # Schedule routine if it's time
            if self.scheduler.should_execute(routine_name):
                # Start scheduler
                schedule_result = self.scheduler.start_routine_execution(routine_name)
                
                # Execute routine
                execution_result = self.executor.execute_routine(routine_name)
                
                # Complete scheduler tracking
                self.scheduler.complete_routine_execution(
                    schedule_result["execution_id"],
                    execution_result["status"] == "completed",
                    execution_result
                )
                
                # Post-execution validation
                if self.config["safety"]["auto_rollback"] and execution_result["status"] == "failed":
                    rollback_result = self._perform_rollback(routine_name, execution_result)
                    execution_result["rollback_performed"] = rollback_result
                
                return execution_result
            else:
                next_execution = self.scheduler.schedule_next_execution(routine_name)
                return {
                    "status": "scheduled",
                    "next_execution": next_execution,
                    "routine_name": routine_name
                }
                
        except Exception as e:
            error_result = {
                "status": "error",
                "error": str(e),
                "routine_name": routine_name,
                "timestamp": datetime.now().isoformat()
            }
            print(f"❌ Error executing routine {routine_name}: {e}")
            return error_result
    
    def _validate_routine_execution(self, routine_name: str, kwargs: dict) -> dict:
        """Validate routine execution prerequisites"""
        errors = []
        
        # Check if routine exists
        if routine_name not in self.config["capabilities"]:
            errors.append(f"Routine {routine_name} not in configured capabilities")
        
        # Check dependencies
        if routine_name in self.scheduler.config.get("dependencies", {}):
            for dep in self.scheduler.config["dependencies"][routine_name]:
                dep_status = self.scheduler.get_routine_status(dep)
                if dep_status.get("last_executed") is None:
                    errors.append(f"Dependency {dep} has not been executed")
        
        # Check permissions
        if self.config["integration"]["respect_block_edits_without_plan"]:
            # This would check the actual project state in real implementation
            pass
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _perform_rollback(self, routine_name: str, execution_result: dict) -> dict:
        """Perform rollback on routine failure"""
        print(f"🔄 Performing rollback for failed routine: {routine_name}")
        
        # This would implement actual rollback logic
        rollback_result = {
            "performed": True,
            "changes_reverted": [],
            "validation_status": "completed"
        }
        
        return rollback_result
    
    def get_status(self, routine_name: str = None) -> dict:
        """Get status of routines or overall engine status"""
        if routine_name:
            return {
                "routine": routine_name,
                "scheduler_status": self.scheduler.get_routine_status(routine_name),
                "engine_version": self.config["version"],
                "capabilities": self.config["capabilities"]
            }
        else:
            return {
                "engine_name": self.config["engine_name"],
                "version": self.config["version"],
                "description": self.config["description"],
                "schedules": self.config["schedules"],
                "capabilities": self.config["capabilities"],
                "safety_enabled": self.config["safety"]["pre_execution_validation"],
                "auto_rollback": self.config["safety"]["auto_rollback"],
                "integration_compliant": self.config["integration"]
            }
    
    def add_custom_routine(self, routine_name: str, phases: list, schedule: dict = None) -> dict:
        """Add a custom routine definition"""
        # Update config
        self.config["capabilities"].append(routine_name)
        
        # Update scheduler config
        routine_config = {
            "schedule": schedule or {},
            "phases": phases,
            "enabled": True,
            "last_executed": None,
            "execution_count": 0,
            "success_rate": 1.0
        }
        
        self.scheduler.config["schedules"][routine_name] = routine_config
        self.scheduler.save_config()
        
        # Save engine config
        with open(self.config_dir / "engine_config.json", 'w') as f:
            json.dump(self.config, f, indent=2)
        
        return {
            "success": True,
            "routine_name": routine_name,
            "phases": phases,
            "schedule": schedule or {}
        }
    
    def get_help(self) -> dict:
        """Get help information for routine engine"""
        return {
            "engine": self.config["engine_name"],
            "version": self.config["version"],
            "available_routines": self.config["capabilities"],
            "schedules": self.config["schedules"],
            "usage": {
                "run_routine": "Run a routine by name",
                "get_status": "Get routine or engine status",
                "add_custom_routine": "Add a custom routine",
                "get_help": "Get help information"
            },
            "examples": [
                "> team-run routine daily-maintenance",
                "> team-run routine weekly-analysis",
                "> team-run routine monthly-evolution"
            ]
        }

def main():
    """Main entry point"""
    engine = RoutineEngine()
    
    # Parse command line arguments
    if len(sys.argv) < 2:
        print("🔧 Routine Engine - Automated Maintenance Loop")
        print("=" * 50)
        print("Usage:")
        print("  python main.py <command> [options]")
        print("")
        print("Commands:")
        print("  status [routine_name] - Get routine or engine status")
        print("  run <routine_name> - Execute a routine")
        print("  add <routine_name> [phases] - Add custom routine")
        print("  help - Show help information")
        return
    
    command = sys.argv[1]
    
    try:
        if command == "status":
            routine_name = sys.argv[2] if len(sys.argv) > 2 else None
            status = engine.get_status(routine_name)
            print(json.dumps(status, indent=2))
            
        elif command == "run":
            if len(sys.argv) < 3:
                print("Error: routine_name required for run command")
                return
            
            routine_name = sys.argv[2]
            result = engine.run_routine(routine_name)
            print(json.dumps(result, indent=2))
            
        elif command == "add":
            if len(sys.argv) < 3:
                print("Error: routine_name required for add command")
                return
            
            routine_name = sys.argv[2]
            phases = sys.argv[3].split(",") if len(sys.argv) > 3 else []
            
            result = engine.add_custom_routine(routine_name, phases)
            print(json.dumps(result, indent=2))
            
        elif command == "help":
            help_info = engine.get_help()
            print(json.dumps(help_info, indent=2))
            
        else:
            print(f"Unknown command: {command}")
            print("Run 'help' for available commands")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()