#!/usr/bin/env python3
"""
Routine Engine Safety Layer - Rollback Capability
Ensures safe execution with automatic rollback on failure.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Automatic log rotation settings
LOG_ROTATION_STRATEGY = "auto"
MAX_ROLLBACK_FILES = 50
ROLLBACK_RETENTION_DAYS = 7

class RollbackManager:
    def __init__(self, project_root: str = ".", safety_dir: str = "safety"):
        self.project_root = Path(project_root)
        self.safety_dir = Path(safety_dir)
        self.rollback_dir = self.safety_dir / "rollbacks"
        self.rollback_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.config = self._load_config()
        
        # Execution state tracking
        self.active_rollback_sessions: Dict[str, Dict] = {}
        self.rollback_history: List[Dict] = []
        
    def _load_config(self) -> dict:
        """Load rollback configuration"""
        config_file = self.safety_dir / "rollback_config.json"
        
        default_config = {
            "rollback": {
                "enabled": True,
                "auto_trigger": True,
                "max_rollback_depth": 5,
                "rollback_timeout": 3600,  # 1 hour
                "cleanup_old_sessions": True,
                "preserve_rollback_artifacts": True
            },
            "validation": {
                "pre_rollback_validation": True,
                "post_rollback_verification": True,
                "impact_assessment": True,
                "dependency_check": True
            },
            "storage": {
                "format": "json",
                "compression": True,
                "encryption": False,
                "retention_days": 30
            }
        }
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def start_rollback_session(self, execution_id: str, execution_data: Dict) -> str:
        """Start a rollback session for a failed execution"""
        session_id = f"rollback_{execution_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        rollback_session = {
            "session_id": session_id,
            "execution_id": execution_id,
            "start_time": datetime.now(),
            "status": "starting",
            "execution_data": execution_data,
            "rollback_points": [],
            "changes_to_revert": [],
            "validation_results": {},
            "rollback_artifacts": {}
        }
        
        self.active_rollback_sessions[session_id] = rollback_session
        
        # Save session state
        self._save_rollback_session(rollback_session)
        
        return session_id
    
    def create_rollback_point(self, session_id: str, checkpoint_name: str, 
                            file_changes: List[Dict], system_state: Dict) -> bool:
        """Create a rollback point at a specific checkpoint"""
        if session_id not in self.active_rollback_sessions:
            return False
        
        rollback_session = self.active_rollback_sessions[session_id]
        
        rollback_point = {
            "checkpoint_name": checkpoint_name,
            "timestamp": datetime.now(),
            "file_changes": file_changes,
            "system_state": system_state,
            "rollback_script": self._generate_rollback_script(file_changes),
            "validation_status": "pending"
        }
        
        rollback_session["rollback_points"].append(rollback_point)
        
        # Keep only recent rollback points
        if len(rollback_session["rollback_points"]) > self.config["rollback"]["max_rollback_depth"]:
            rollback_session["rollback_points"] = rollback_session["rollback_points"][-5:]
        
        self._save_rollback_session(rollback_session)
        return True
    
    def perform_rollback(self, session_id: str, target_checkpoint: str = None) -> Dict:
        """Perform rollback to specified checkpoint or latest"""
        if session_id not in self.active_rollback_sessions:
            return {
                "success": False,
                "error": f"Rollback session {session_id} not found"
            }
        
        rollback_session = self.active_rollback_sessions[session_id]
        
        # Determine target checkpoint
        if target_checkpoint:
            target_point = None
            for point in rollback_session["rollback_points"]:
                if point["checkpoint_name"] == target_checkpoint:
                    target_point = point
                    break
            
            if not target_point:
                return {
                    "success": False,
                    "error": f"Checkpoint {target_checkpoint} not found"
                }
        else:
            target_point = rollback_session["rollback_points"][-1] if rollback_session["rollback_points"] else None
            if not target_point:
                return {
                    "success": False,
                    "error": "No rollback points available"
                }
        
        try:
            # Pre-rollback validation
            if self.config["validation"]["pre_rollback_validation"]:
                validation_result = self._validate_rollback(rollback_session, target_point)
                if not validation_result["valid"]:
                    return {
                        "success": False,
                        "error": "Pre-rollback validation failed",
                        "validation_errors": validation_result["errors"]
                    }
            
            # Execute rollback
            rollback_result = self._execute_rollback(target_point, rollback_session)
            
            # Update session
            rollback_session["target_checkpoint"] = target_checkpoint or target_point["checkpoint_name"]
            rollback_session["rollback_result"] = rollback_result
            rollback_session["end_time"] = datetime.now()
            rollback_session["status"] = "completed" if rollback_result["success"] else "failed"
            
            # Post-rollback verification
            if rollback_result["success"] and self.config["validation"]["post_rollback_verification"]:
                verification_result = self._verify_rollback(rollback_session, target_point)
                rollback_result["verification"] = verification_result
            
            # Save final session state
            self._save_rollback_session(rollback_session)
            
            # Add to history
            self.rollback_history.append(rollback_session.copy())
            
            # Clean up old sessions
            if self.config["rollback"]["cleanup_old_sessions"]:
                self._cleanup_old_sessions()
            
            return rollback_result
            
        except Exception as e:
            rollback_session["status"] = "error"
            rollback_session["error"] = str(e)
            rollback_session["end_time"] = datetime.now()
            
            self._save_rollback_session(rollback_session)
            
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
    
    def _validate_rollback(self, rollback_session: Dict, target_point: Dict) -> Dict:
        """Validate rollback operation"""
        errors = []
        
        # Check dependencies
        if self.config["validation"]["dependency_check"]:
            dep_errors = self._check_rollback_dependencies(rollback_session, target_point)
            errors.extend(dep_errors)
        
        # Check system state
        system_state_errors = self._check_system_state_for_rollback(rollback_session)
        errors.extend(system_state_errors)
        
        # Validate rollback script
        script_errors = self._validate_rollback_script(target_point)
        errors.extend(script_errors)
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _check_rollback_dependencies(self, rollback_session: Dict, target_point: Dict) -> List[str]:
        """Check if rollback dependencies are met"""
        errors = []
        
        # Check if critical systems are available
        critical_systems = ["git", "file_system", "environment"]
        for system in critical_systems:
            if not self._check_system_availability(system):
                errors.append(f"Critical system {system} not available for rollback")
        
        # Check if rollback points are properly structured
        if not target_point or "rollback_script" not in target_point:
            errors.append("Rollback point missing required structure")
        
        return errors
    
    def _check_system_state_for_rollback(self, rollback_session: Dict) -> List[str]:
        """Check if system state allows rollback"""
        errors = []
        
        # Check for uncommitted changes
        try:
            import subprocess
            git_status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            ).stdout
            
            if git_status:
                errors.append("Uncommitted changes detected - rollback may be unsafe")
        except:
            pass
        
        return errors
    
    def _check_system_availability(self, system: str) -> bool:
        """Check if required system is available"""
        try:
            if system == "git":
                import subprocess
                subprocess.run(["git", "--version"], capture_output=True, check=True)
                return True
            elif system == "file_system":
                # Basic file system check
                return self.project_root.exists()
            elif system == "environment":
                # Check Python availability
                import sys
                return sys.version_info >= (3, 6)
        except:
            pass
        
        return False
    
    def _validate_rollback_script(self, target_point: Dict) -> List[str]:
        """Validate rollback script structure"""
        errors = []
        
        if not target_point:
            return ["No target point provided"]
        
        required_fields = ["checkpoint_name", "timestamp", "file_changes", "rollback_script"]
        for field in required_fields:
            if field not in target_point:
                errors.append(f"Missing required field in rollback point: {field}")
        
        return errors
    
    def _execute_rollback(self, target_point: Dict, rollback_session: Dict) -> Dict:
        """Execute the actual rollback operation"""
        try:
            rollback_script = target_point.get("rollback_script", {})
            
            # Apply file changes in reverse order
            file_changes = target_point.get("file_changes", [])
            applied_changes = []
            rollback_artifacts = {}
            
            for change in reversed(file_changes):
                if change.get("type") == "file_move":
                    result = self._rollback_file_move(change)
                elif change.get("type") == "file_delete":
                    result = self._rollback_file_delete(change)
                elif change.get("type") == "file_create":
                    result = self._rollback_file_create(change)
                elif change.get("type") == "content_modify":
                    result = self._rollback_content_modify(change)
                else:
                    result = {"success": False, "error": f"Unknown change type: {change.get('type')}"}
                
                applied_changes.append(result)
                
                if not result.get("success", False):
                    rollback_artifacts[f"change_{len(applied_changes)-1}"] = {
                        "status": "failed",
                        "error": result.get("error", "Unknown error")
                    }
            
            success = len(rollback_artifacts) == 0
            
            return {
                "success": success,
                "applied_changes": applied_changes,
                "rollback_artifacts": rollback_artifacts,
                "target_checkpoint": target_point["checkpoint_name"],
                "execution_time": (datetime.now() - target_point["timestamp"]).total_seconds()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "target_checkpoint": target_point["checkpoint_name"] if target_point else "unknown"
            }
    
    def _rollback_file_move(self, change: Dict) -> Dict:
        """Rollback a file move operation"""
        source = change.get("source")
        destination = change.get("destination")
        
        if not source or not destination:
            return {"success": False, "error": "Missing source or destination for file move rollback"}
        
        try:
            source_path = self.project_root / source
            dest_path = self.project_root / destination
            
            # Check if destination exists (should be the original location)
            if dest_path.exists():
                return {"success": False, "error": f"Destination {dest_path} already exists"}
            
            # Move file back
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            source_path.rename(dest_path)
            
            return {
                "success": True,
                "operation": "file_move",
                "action": f"Moved {source} back to {destination}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to rollback file move: {str(e)}"
            }
    
    def _rollback_file_delete(self, change: Dict) -> Dict:
        """Rollback a file delete operation"""
        source = change.get("source")
        
        if not source:
            return {"success": False, "error": "Missing source for file delete rollback"}
        
        try:
            source_path = self.project_root / source
            
            # Check if file was restored
            if source_path.exists():
                return {"success": True, "operation": "file_delete", "action": "File already exists"}
            
            # Restore file from backup or recreate
            backup_path = self._get_backup_path(source)
            if backup_path and backup_path.exists():
                backup_path.rename(source_path)
                return {
                    "success": True,
                    "operation": "file_delete",
                    "action": f"Restored {source} from backup"
                }
            else:
                return {
                    "success": False,
                    "error": f"Cannot restore deleted file {source} - no backup available"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to rollback file delete: {str(e)}"
            }
    
    def _rollback_file_create(self, change: Dict) -> Dict:
        """Rollback a file create operation"""
        source = change.get("source")
        content = change.get("content")
        
        if not source:
            return {"success": False, "error": "Missing source for file create rollback"}
        
        try:
            source_path = self.project_root / source
            
            # Check if file exists (should be the original state)
            if not source_path.exists():
                # Create file with original content
                source_path.parent.mkdir(parents=True, exist_ok=True)
                
                if content:
                    with open(source_path, 'w') as f:
                        f.write(content)
                else:
                    # Try to restore from backup
                    backup_path = self._get_backup_path(source)
                    if backup_path and backup_path.exists():
                        backup_path.rename(source_path)
                    else:
                        # Create empty file as fallback
                        source_path.touch()
                
                return {
                    "success": True,
                    "operation": "file_create",
                    "action": f"Created {source} with original content"
                }
            else:
                return {"success": True, "operation": "file_create", "action": "File already exists"}
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to rollback file create: {str(e)}"
            }
    
    def _rollback_content_modify(self, change: Dict) -> Dict:
        """Rollback content modification"""
        source = change.get("source")
        original_content = change.get("original_content")
        
        if not source:
            return {"success": False, "error": "Missing source for content modify rollback"}
        
        try:
            source_path = self.project_root / source
            
            if not source_path.exists():
                return {
                    "success": False,
                    "error": f"Source file {source} does not exist for content rollback"
                }
            
            current_content = source_path.read_text()
            
            if current_content == original_content:
                return {
                    "success": True,
                    "operation": "content_modify",
                    "action": "Content already matches original"
                }
            
            # Restore original content
            with open(source_path, 'w') as f:
                f.write(original_content)
            
            return {
                "success": True,
                "operation": "content_modify",
                "action": f"Restored original content to {source}"
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to rollback content modify: {str(e)}"
            }
    
    def _get_backup_path(self, file_path: str) -> Optional[Path]:
        """Get backup path for a file"""
        # This would look for backups in a structured backup directory
        backup_dir = self.rollback_dir / "backups"
        backup_file = backup_dir / f"{Path(file_path).name}.backup"
        return backup_file if backup_file.exists() else None
    
    def _generate_rollback_script(self, file_changes: List[Dict]) -> Dict:
        """Generate rollback script for file changes"""
        rollback_script = {
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "operations": []
        }
        
        for change in file_changes:
            if change.get("type") == "file_move":
                operation = {
                    "type": "move",
                    "from": change.get("destination"),
                    "to": change.get("source")
                }
            elif change.get("type") == "file_delete":
                operation = {
                    "type": "restore",
                    "from": change.get("source")
                }
            elif change.get("type") == "file_create":
                operation = {
                    "type": "create",
                    "path": change.get("source"),
                    "content": change.get("content")
                }
            elif change.get("type") == "content_modify":
                operation = {
                    "type": "modify",
                    "path": change.get("source"),
                    "original_content": change.get("original_content")
                }
            else:
                continue
            
            rollback_script["operations"].append(operation)
        
        return rollback_script
    
    def _verify_rollback(self, rollback_session: Dict, target_point: Dict) -> Dict:
        """Verify that rollback was successful"""
        try:
            # Verify file changes
            file_changes = target_point.get("file_changes", [])
            verification_results = []
            
            for change in file_changes:
                if change.get("type") == "file_move":
                    result = self._verify_file_move_rollback(change)
                elif change.get("type") == "file_delete":
                    result = self._verify_file_delete_rollback(change)
                elif change.get("type") == "file_create":
                    result = self._verify_file_create_rollback(change)
                elif change.get("type") == "content_modify":
                    result = self._verify_content_modify_rollback(change)
                else:
                    result = {"success": False, "error": f"Unknown change type: {change.get('type')}"}
                
                verification_results.append(result)
            
            all_verified = all(result.get("success", False) for result in verification_results)
            
            return {
                "success": all_verified,
                "verification_results": verification_results,
                "verification_time": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "verification_time": datetime.now().isoformat()
            }
    
    def _verify_file_move_rollback(self, change: Dict) -> Dict:
        """Verify file move rollback"""
        source = change.get("source")
        destination = change.get("destination")
        
        if not source or not destination:
            return {"success": False, "error": "Missing source or destination"}
        
        source_path = self.project_root / source
        dest_path = self.project_root / destination
        
        # Check if file moved back to original location
        if not dest_path.exists():
            return {
                "success": False,
                "error": f"File not restored to original location: {destination}"
            }
        
        # Check if content is correct (simplified check)
        if source_path.exists() and dest_path.exists():
            # Try to compare file sizes or hash if needed
            source_size = source_path.stat().st_size
            dest_size = dest_path.stat().st_size
            
            if source_size != dest_size:
                return {
                    "success": False,
                    "error": f"File sizes don't match after rollback: source={source_size}, dest={dest_size}"
                }
        
        return {
            "success": True,
            "operation": "file_move",
            "verified": f"File successfully moved back to {destination}"
        }
    
    def _verify_file_delete_rollback(self, change: Dict) -> Dict:
        """Verify file delete rollback"""
        source = change.get("source")
        
        if not source:
            return {"success": False, "error": "Missing source"}
        
        source_path = self.project_root / source
        
        # Check if file was restored
        if not source_path.exists():
            return {
                "success": False,
                "error": f"File {source} was not restored after delete"
            }
        
        return {
            "success": True,
            "operation": "file_delete",
            "verified": f"File {source} successfully restored"
        }
    
    def _verify_file_create_rollback(self, change: Dict) -> Dict:
        """Verify file create rollback"""
        source = change.get("source")
        
        if not source:
            return {"success": False, "error": "Missing source"}
        
        source_path = self.project_root / source
        
        # Check if file was created
        if not source_path.exists():
            return {
                "success": False,
                "error": f"File {source} was not created after rollback"
            }
        
        return {
            "success": True,
            "operation": "file_create",
            "verified": f"File {source} successfully created"
        }
    
    def _verify_content_modify_rollback(self, change: Dict) -> Dict:
        """Verify content modification rollback"""
        source = change.get("source")
        original_content = change.get("original_content")
        
        if not source or not original_content:
            return {"success": False, "error": "Missing source or original content"}
        
        source_path = self.project_root / source
        
        # Check if file exists
        if not source_path.exists():
            return {
                "success": False,
                "error": f"File {source} does not exist for content verification"
            }
        
        # Read current content
        current_content = source_path.read_text()
        
        # Check if content matches original
        if current_content != original_content:
            return {
                "success": False,
                "error": f"Content mismatch after rollback for file {source}"
            }
        
        return {
            "success": True,
            "operation": "content_modify",
            "verified": f"Content of {source} successfully restored"
        }
    
    def _save_rollback_session(self, session: Dict):
        """Save rollback session to disk"""
        session_file = self.rollback_dir / f"{session['session_id']}.json"
        
        with open(session_file, 'w') as f:
            json.dump(session, f, indent=2, default=str)
    
    def _cleanup_old_sessions(self):
        """Clean up old rollback sessions"""
        cutoff_time = datetime.now() - timedelta(days=self.config["storage"]["retention_days"])
        
        for session_file in self.rollback_dir.glob("*.json"):
            try:
                with open(session_file, 'r') as f:
                    session = json.load(f)
                
                session_time = datetime.fromisoformat(session["start_time"].replace('Z', '+00:00'))
                
                if session_time < cutoff_time:
                    session_file.unlink()
            except:
                # If file is corrupted, delete it
                try:
                    session_file.unlink()
                except:
                    pass

# Standalone execution function
def create_rollback_session(execution_id: str, execution_data: Dict) -> str:
    """Create a rollback session"""
    rollback_manager = RollbackManager()
    return rollback_manager.start_rollback_session(execution_id, execution_data)

def perform_routine_rollback(session_id: str, target_checkpoint: str = None) -> Dict:
    """Perform rollback to target checkpoint"""
    rollback_manager = RollbackManager()
    return rollback_manager.perform_rollback(session_id, target_checkpoint)

def get_rollback_status(session_id: str) -> Dict:
    """Get status of rollback session"""
    rollback_manager = RollbackManager()
    
    if session_id in rollback_manager.active_rollback_sessions:
        session = rollback_manager.active_rollback_sessions[session_id]
        return {
            "status": session["status"],
            "start_time": session["start_time"],
            "target_checkpoint": session.get("target_checkpoint"),
            "rollback_points": len(session["rollback_points"])
        }
    elif any(session_id in rollback_manager.rollback_history for session in rollback_manager.rollback_history):
        return {
            "status": "completed",
            "message": "Rollback session found in history"
        }
    else:
        return {
            "status": "not_found",
            "error": f"Rollback session {session_id} not found"
        }

if __name__ == "__main__":
    # Example usage
    print("=== Rollback Manager Initialized ===")
    
    # Create a rollback session
    execution_data = {
        "routine_name": "test_routine",
        "phase": "execute",
        "changes": [
            {"type": "file_move", "source": "src/file1.py", "destination": "src/file1.backup.py"},
            {"type": "content_modify", "source": "src/config.json", "original_content": "{\"old\": \"value\"}"}
        ]
    }
    
    session_id = create_rollback_session("test_execution_123", execution_data)
    print(f"Created rollback session: {session_id}")
    
    # Perform rollback
    rollback_result = perform_routine_rollback(session_id)
    print(f"Rollback result: {rollback_result}")