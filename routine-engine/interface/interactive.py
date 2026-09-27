#!/usr/bin/env python3
"""
Routine Engine Interactive Interface
Enables team members to run routines with "run my routine" commands and proactive conversation.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class InteractiveInterface:
    def __init__(self, project_root: str = ".", routine_engine_dir: str = "routine-engine"):
        self.project_root = Path(project_root)
        self.routine_engine_dir = Path(routine_engine_dir)
        self.context_dir = self.project_root / "team" / "context"
        # Ensure context directory exists
        self.context_dir.mkdir(parents=True, exist_ok=True)
        # Ensure conversation_log.json exists
        conversation_log = self.context_dir / "conversation_log.json"
        if not conversation_log.exists():
            with open(conversation_log, 'w') as f:
                json.dump([], f)
        self.config_dir = self.routine_engine_dir / "config"
        
        # Load configuration
        self.config = self._load_config()
        
        # Conversation state
        self.conversation_history = []
        self.active_routines = []
        self.user_context = {}
        
    def _load_config(self) -> dict:
        """Load interactive interface configuration"""
        config_file = self.config_dir / "interactive_config.json"
        
        default_config = {
            "conversation": {
                "enabled": True,
                "proactive_comments": True,
                "suggestion_frequency": "always",
                "conversation_style": "collaborative"
            },
            "commands": {
                "run_routine": {
                    "triggers": ["run my routine", "execute routine", "start routine", "run routine"],
                    "parameters": ["routine_name", "parameters"]
                },
                "routine_status": {
                    "triggers": ["routine status", "check routine", "routine progress"],
                    "parameters": ["routine_name"]
                },
                "evolution_status": {
                    "triggers": ["evolution status", "team status", "knowledge base"],
                    "parameters": []
                },
                "help": {
                    "triggers": ["help", "commands", "routines"],
                    "parameters": []
                }
            },
            "conversation_patterns": {
                "proactive_suggestions": True,
                "routine_recommendations": True,
                "evolution_insights": True,
                "maintenance_reminders": True
            }
        }
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def parse_command(self, message: str) -> Dict:
        """Parse team member command and determine intent"""
        message_lower = message.lower().strip()
        
        # Check for routine execution commands
        for command_name, command_config in self.config["commands"].items():
            for trigger in command_config["triggers"]:
                if trigger in message_lower:
                    return {
                        "command": command_name,
                        "trigger": trigger,
                        "parameters": self._extract_parameters(message, command_config["parameters"]),
                        "original_message": message
                    }
        
        # Default: proactive conversation
        return {
            "command": "converse",
            "trigger": "default",
            "parameters": {},
            "original_message": message
        }
    def _extract_parameters(self, message: str, expected_params: List[str]) -> Dict:
        """Extract parameters from message"""
        params = {}

        if "routine_name" in expected_params:
            # First priority: Check if any complete routine name appears in the message
            message_lower = message.lower()
            
            # Complete routine names to match
            routine_names = ["daily-maintenance", "weekly-analysis", "monthly-evolution", "custom-routine"]
            
            for routine_name in routine_names:
                if routine_name in message_lower:
                    params["routine_name"] = routine_name
                    break
            
            # If no complete routine name found, check keywords
            if "routine_name" not in params:
                words = message_lower.split()
                keyword_to_routine = {
                    "maintenance": "daily-maintenance",
                    "daily": "daily-maintenance",
                    "analysis": "weekly-analysis", 
                    "weekly": "weekly-analysis",
                    "evolution": "monthly-evolution",
                    "monthly": "monthly-evolution",
                    "custom": "custom-routine"
                }
                
                # Check for keywords
                for word in words:
                    if word in keyword_to_routine:
                        params["routine_name"] = keyword_to_routine[word]
                        break
                
                # If still not found, check multi-word phrases
                if "routine_name" not in params and len(words) > 1:
                    for i in range(len(words) - 1):
                        phrase = f"{words[i]} {words[i+1]}"
                        # Check if phrase matches part of a routine name
                        for routine_name in routine_names:
                            if phrase in routine_name.replace("-", " "):
                                params["routine_name"] = routine_name
                                break
                        if "routine_name" in params:
                            break

        if "parameters" in expected_params:
            # Extract any additional parameters
            words = message.lower().split()
            extra_params = [w for w in words if len(w) > 3 and w not in ["routine", "my", "run", "execute", "the", "and", "for", "of"]]
            if extra_params:
                params["additional_params"] = extra_params

        return params
    def process_command(self, command_data: Dict) -> Dict:
        """Process parsed command and execute appropriate action"""
        command = command_data["command"]
        
        if command == "run_routine":
            return self._handle_run_routine(command_data)
        elif command == "routine_status":
            return self._handle_routine_status(command_data)
        elif command == "evolution_status":
            return self._handle_evolution_status(command_data)
        elif command == "help":
            return self._handle_help(command_data)
        else:
            return self._handle_conversation(command_data)
    
    def _handle_run_routine(self, command_data: Dict) -> Dict:
        """Handle 'run my routine' command"""
        params = command_data["parameters"]
        routine_name = params.get("routine_name", "daily-maintenance")
        
        # Validate routine exists
        if routine_name not in self.config["capabilities"]:
            return {
                "status": "error",
                "message": f"Routine '{routine_name}' not found. Available routines: {list(self.config['capabilities'])}",
                "suggestion": f"Try running 'daily-maintenance' or ask for available routines"
            }
        
        # Proactively suggest parameters based on routine
        suggestions = self._get_routine_suggestions(routine_name)
        
        # Log the request
        self._log_interaction("routine_request", {
            "routine_name": routine_name,
            "parameters": params,
            "suggestions": suggestions
        })
        
        # Return confirmation with routine details
        return {
            "status": "confirmed",
            "message": f"Starting {routine_name} routine... (continued)",
            "routine": routine_name,
            "estimated_duration": suggestions.get("estimated_duration", "5-10 minutes"),
            "risk_level": suggestions.get("risk_level", "low"),
            "action": "executing",
            "prompt": "Would you like me to proceed with these parameters, or would you like to modify them?"
        }

    def _handle_routine_status(self, command_data: Dict) -> Dict:
        """Handle routine status requests"""
        params = command_data["parameters"]
        routine_name = params.get("routine_name", "daily-maintenance")
        
        # Get routine status from scheduler
        from routine_engine.engine.scheduler import RoutineScheduler
        scheduler = RoutineScheduler()
        status = scheduler.get_routine_status(routine_name)
        
        # Format status information
        formatted_status = self._format_routine_status(status, routine_name)
        
        return {
            "status": "status",
            "routine": routine_name,
            "formatted_status": formatted_status,
            "next_execution": status.get("next_execution"),
            "last_executed": status.get("last_executed"),
            "execution_count": status.get("execution_count", 0),
            "success_rate": status.get("success_rate", 0.0),
            "message": f"Routine '{routine_name}' status retrieved successfully"
        }
    
    def _handle_evolution_status(self, command_data: Dict) -> Dict:
        """Handle evolution status requests"""
        # Get knowledge base status
        kb_status = self._get_knowledge_base_status()
        
        # Get team evolution status
        team_status = self._get_team_evolution_status()
        
        return {
            "status": "evolution_status",
            "knowledge_base": kb_status,
            "team_evolution": team_status,
            "recent_changes": self._get_recent_evolution_changes(),
            "message": "Evolution status retrieved successfully"
        }
    
    def _handle_help(self, command_data: Dict) -> Dict:
        """Handle help requests"""
        help_info = {
            "available_commands": list(self.config["commands"].keys()),
            "routine_triggers": {
                "run_routine": self.config["commands"]["run_routine"]["triggers"],
                "routine_status": self.config["commands"]["routine_status"]["triggers"],
                "evolution_status": self.config["commands"]["evolution_status"]["triggers"]
            },
            "available_routines": self.config["capabilities"],
            "example_usage": {
                "run_daily": "Run daily maintenance routine",
                "run_weekly": "Run weekly analysis routine",
                "check_status": "Check routine status",
                "evolution_info": "Get evolution status"
            },
            "conversation_features": {
                "proactive_suggestions": "Enabled - I suggest routines based on context",
                "pattern_recognition": "Enabled - I detect patterns in your work",
                "evolution_tracking": "Enabled - I track team evolution"
            }
        }
        
        return {
            "status": "help",
            "help_info": help_info,
            "message": "Help information retrieved successfully"
        }
    
    def _handle_conversation(self, command_data: Dict) -> Dict:
        """Handle general conversation with proactive insights"""
        message = command_data["original_message"]
        
        # Generate proactive insights
        insights = self._generate_conversation_insights(message)
        
        # Check for routine recommendations based on message content
        routine_recommendation = self._get_routine_recommendation(message)
        
        # Log conversation
        self._log_interaction("conversation", {
            "message": message,
            "insights": insights,
            "routine_recommendation": routine_recommendation
        })
        
        return {
            "status": "conversation",
            "insights": insights,
            "routine_recommendation": routine_recommendation,
            "proactive_comment": self._generate_proactive_comment(message),
            "message": "Processing your message with proactive insights"
        }
    
    def _get_routine_suggestions(self, routine_name: str) -> Dict:
        """Get routine-specific suggestions"""
        suggestions = {
            "daily-maintenance": {
                "estimated_duration": "5-10 minutes",
                "risk_level": "low",
                "recommended_params": {
                    "evidence_collection": True,
                    "auto_report": True,
                    "validation": "basic"
                }
            },
            "weekly-analysis": {
                "estimated_duration": "10-15 minutes",
                "risk_level": "medium",
                "recommended_params": {
                    "pattern_detection": True,
                    "gap_analysis": True,
                    "evolution_planning": True
                }
            },
            "monthly-evolution": {
                "estimated_duration": "15-20 minutes",
                "risk_level": "high",
                "recommended_params": {
                    "team_composition": True,
                    "skill_evolution": True,
                    "knowledge_updates": True
                }
            }
        }
        
        return suggestions.get(routine_name, {
            "estimated_duration": "unknown",
            "risk_level": "unknown",
            "recommended_params": {}
        })
    
    def _format_routine_status(self, status: Dict, routine_name: str) -> str:
        """Format routine status for display"""
        if isinstance(status, dict) and "error" in status:
            return f"Error: {status['error']}"
        
        formatted = f"**Routine: {routine_name}**"
        # Build formatted string line by line
        lines = []
        lines.append(f"**Routine: {routine_name}")
        lines.append(f"- Last Executed: {status.get('last_executed', 'Never')}")
        lines.append(f"- Execution Count: {status.get('execution_count', 0)}")
        lines.append(f"- Success Rate: {status.get('success_rate', 0.0) * 100:.1f}%")
        lines.append(f"- Next Execution: {status.get('next_execution', 'Unknown')}")
        lines.append(f"- Enabled: {status.get('enabled', False)}")
        return "\n".join(lines)
    
    def _get_knowledge_base_status(self) -> Dict:
        """Get knowledge base status"""
        kb_files = list(self.context_dir.glob("*.md"))
        recent_updates = []
        
        for file in kb_files:
            if file.name.endswith("-knowledge.md") or file.name.endswith("-insights.md"):
                mtime = datetime.fromtimestamp(file.stat().st_mtime)
                recent_updates.append({
                    "file": file.name,
                    "last_modified": mtime.isoformat(),
                    "age_hours": (datetime.now() - mtime).total_seconds() / 3600
                })
        
        return {
            "total_files": len(kb_files),
            "recent_updates": recent_updates,
            "needs_update": len([u for u in recent_updates if u["age_hours"] > 24]) > 0
        }
    
    def _get_team_evolution_status(self) -> Dict:
        """Get team evolution status"""
        # This would integrate with the existing team skill management
        return {
            "skill_evolution_enabled": True,
            "persona_updates": "active",
            "knowledge_base_updates": "enabled",
            "evolution_history": []
        }
    
    def _get_recent_evolution_changes(self) -> List[Dict]:
        """Get recent evolution changes"""
        # This would track changes over time
        return []
    
    def _generate_conversation_insights(self, message: str) -> List[str]:
        """Generate insights based on conversation"""
        insights = []
        
        # Look for patterns in message
        if "maintenance" in message.lower():
            insights.append("🔧 Project maintenance mentioned - daily routine may help")
        
        if "structure" in message.lower():
            insights.append("📊 Structural analysis suggested - weekly routine recommended")
        
        if "team" in message.lower():
            insights.append("👥 Team composition discussed - evolution routine may provide insights")
        
        if "problem" in message.lower():
            insights.append("⚠️ Problem identification - diagnosis routine may help")
        
        # Check if routine is overdue
        from routine_engine.engine.scheduler import RoutineScheduler
        scheduler = RoutineScheduler()
        
        for routine in ["daily-maintenance", "weekly-analysis", "monthly-evolution"]:
            status = scheduler.get_routine_status(routine)
            next_execution = status.get("next_execution")
            if next_execution:
                days_until = (next_execution - datetime.now()).days
                if days_until <= 1:
                    insights.append(f"📅 {routine} routine is due soon")
        
        return insights
    
    def _get_routine_recommendation(self, message: str) -> Dict:
        """Get routine recommendation based on message content"""
        message_lower = message.lower()
        
        # Simple recommendation logic
        if any(word in message_lower for word in ["problem", "issue", "error", "broken"]):
            return {
                "routine": "daily-maintenance",
                "reason": "Problem indicators detected - diagnostic routine recommended"
            }
        
        elif any(word in message_lower for word in ["pattern", "trend", "analysis", "improve"]):
            return {
                "routine": "weekly-analysis",
                "reason": "Analysis/improvement mentioned - pattern detection recommended"
            }
        
        elif any(word in message_lower for word in ["team", "skill", "persona", "composition"]):
            return {
                "routine": "monthly-evolution",
                "reason": "Team composition discussed - evolution routine recommended"
            }
        
        # Default recommendation
        return {
            "routine": "daily-maintenance",
            "reason": "General maintenance suggested - starting with daily routine"
        }
    
    def _generate_proactive_comment(self, message: str) -> str:
        """Generate proactive comment based on message"""
        message_lower = message.lower()
        
        if "structure" in message_lower:
            return "💡 I notice you're working with structure. Consider running the daily maintenance routine to keep your project healthy and identify any structural drift before it becomes problematic."
        
        elif "team" in message_lower:
            return "👥 Team dynamics mentioned. The weekly analysis routine could provide insights into team skill alignment and suggest composition improvements."
        
        elif "maintenance" in message_lower:
            return "🔧 Maintenance topic. Regular maintenance routines prevent larger issues down the line. Which routine would be most helpful right now?"
        
        elif "problem" in message_lower:
            return "⚠️ Problem indicators detected. I recommend running the daily maintenance routine to diagnose and address issues systematically."
        
        else:
            return "💭 Working on something interesting. Would you like me to suggest which routine might be most beneficial for your current task?"
    
    def _log_interaction(self, interaction_type: str, data: Dict):
        """Log interaction for learning and improvement"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": interaction_type,
            "data": data
        }
        
        log_file = self.context_dir / "conversation_log.json"
        
        # Read existing logs
        logs = []
        if log_file.exists():
            with open(log_file, 'r') as f:
                logs = json.load(f)
        
        # Add new log entry
        logs.append(log_entry)
        
        # Keep only last 1000 entries
        if len(logs) > 1000:
            logs = logs[-1000:]
        
        # Write back
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2)

# Standalone execution function
def process_team_message(message: str) -> Dict:
    """Process team member message with interactive interface"""
    interface = InteractiveInterface()
    command_data = interface.parse_command(message)
    return interface.process_command(command_data)

def get_routine_recommendation(message: str) -> Dict:
    """Get routine recommendation for team message"""
    interface = InteractiveInterface()
    routine_rec = interface._get_routine_recommendation(message)
    return {
        "recommended_routine": routine_rec["routine"],
        "reason": routine_rec["reason"],
        "action_suggestion": f"Use 'run my routine {routine_rec['routine']}' to execute"
    }

if __name__ == "__main__":
    # Example usage
    test_message = "I need to run my routine for the project structure"
    result = process_team_message(test_message)
    
    print("=== Team Message Processing ===")
    print(f"Original: {test_message}")
    print(f"Status: {result['status']}")
    print(f"Message: {result.get('message', '')}")
    
    if "insights" in result:
        print(f"Insights: {result['insights']}")
    
    if "routine_recommendation" in result:
        print(f"Routine Recommendation: {result['routine_recommendation']}")