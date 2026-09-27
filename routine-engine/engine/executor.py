#!/usr/bin/env python3
"""
Routine Engine Executor
Phase-aware routine execution with rollback and validation support.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class RoutineExecutor:
    def __init__(self, safety_dir: str = "safety"):
        self.safety_dir = Path(safety_dir)
        self.current_execution = None
        self.execution_phases = {
            "daily-maintenance": ["inspect", "diagnose", "validate"],
            "weekly-analysis": ["inspect", "diagnose", "propose"],
            "monthly-evolution": ["inspect", "diagnose", "propose", "execute", "validate"]
        }
        
    def execute_routine(self, routine_name: str) -> Dict:
        """Execute a routine with phase awareness"""
        start_time = datetime.now()
        execution_id = f"{routine_name}_{start_time.strftime('%Y%m%d_%H%M%S')}"
        
        if routine_name not in self.execution_phases:
            return {
                "execution_id": execution_id,
                "routine_name": routine_name,
                "status": "error",
                "error": f"Unknown routine: {routine_name}",
                "start_time": start_time,
                "end_time": datetime.now()
            }
        
        execution_record = {
            "execution_id": execution_id,
            "routine_name": routine_name,
            "status": "running",
            "start_time": start_time,
            "phases": {},
            "errors": [],
            "result": {}
        }
        
        self.current_execution = execution_record
        
        try:
            # Execute each phase
            for phase in self.execution_phases[routine_name]:
                phase_result = self.execute_phase(routine_name, phase)
                execution_record["phases"][phase] = phase_result
                
                if not phase_result.get("success", False):
                    execution_record["status"] = "failed"
                    execution_record["error"] = f"Phase {phase} failed"
                    execution_record["failed_phase"] = phase
                    break
            
            if execution_record["status"] == "running":
                execution_record["status"] = "completed"
            
            execution_record["end_time"] = datetime.now()
            execution_record["duration"] = (execution_record["end_time"] - execution_record["start_time"]).total_seconds()
            
        except Exception as e:
            execution_record["status"] = "error"
            execution_record["error"] = str(e)
            execution_record["end_time"] = datetime.now()
        
        self.current_execution = None
        return execution_record
    
    def execute_phase(self, routine_name: str, phase: str) -> Dict:
        """Execute a specific phase of a routine"""
        phase_start = datetime.now()
        
        # Phase-specific logic
        if phase == "inspect":
            return self._execute_inspect_phase(routine_name)
        elif phase == "diagnose":
            return self._execute_diagnose_phase(routine_name)
        elif phase == "propose":
            return self._execute_propose_phase(routine_name)
        elif phase == "execute":
            return self._execute_execute_phase(routine_name)
        elif phase == "validate":
            return self._execute_validate_phase(routine_name)
        else:
            return {
                "phase": phase,
                "success": False,
                "error": f"Unknown phase: {phase}",
                "start_time": phase_start,
                "end_time": datetime.now()
            }
    
    def _execute_inspect_phase(self, routine_name: str) -> Dict:
        """Execute Phase 1: Inspect current structure"""
        phase_start = datetime.now()
        
        try:
            # Evidence collection for project structure
            evidence = self._collect_structure_evidence()
            
            # Identify structural components
            structure_components = self._identify_structure_components()
            
            # Check for structural drift
            drift_analysis = self._analyze_structural_drift(evidence, structure_components)
            
            result = {
                "phase": "inspect",
                "success": True,
                "evidence": evidence,
                "structure_components": structure_components,
                "drift_analysis": drift_analysis,
                "findings": self._generate_inspect_findings(drift_analysis),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
            
        except Exception as e:
            result = {
                "phase": "inspect",
                "success": False,
                "error": str(e),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
        
        return result
    
    def _execute_diagnose_phase(self, routine_name: str) -> Dict:
        """Execute Phase 2: Diagnose specific problems"""
        phase_start = datetime.now()
        
        try:
            # Get evidence from previous phase
            last_execution = self.get_last_execution()
            if not last_execution or "phases" not in last_execution:
                return {
                    "phase": "diagnose",
                    "success": False,
                    "error": "No previous execution available for diagnosis",
                    "start_time": phase_start,
                    "end_time": datetime.now()
                }
            
            inspect_result = last_execution["phases"].get("inspect", {})
            evidence = inspect_result.get("evidence", {})
            
            # Identify problems
            problems = self._identify_problems(evidence)
            
            # Assess severity
            severity_assessment = self._assess_severity(problems)
            
            # Prioritize problems
            prioritized_problems = self._prioritize_problems(problems, severity_assessment)
            
            result = {
                "phase": "diagnose",
                "success": True,
                "problems": prioritized_problems,
                "severity_assessment": severity_assessment,
                "root_causes": self._identify_root_causes(prioritized_problems),
                "recommendations": self._generate_recommendations(prioritized_problems),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
            
        except Exception as e:
            result = {
                "phase": "diagnose",
                "success": False,
                "error": str(e),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
        
        return result
    
    def _execute_propose_phase(self, routine_name: str) -> Dict:
        """Execute Phase 3: Propose minimum changes"""
        phase_start = datetime.now()
        
        try:
            # Get diagnosis from previous phase
            last_execution = self.get_last_execution()
            if not last_execution or "phases" not in last_execution:
                return {
                    "phase": "propose",
                    "success": False,
                    "error": "No previous execution available for proposal",
                    "start_time": phase_start,
                    "end_time": datetime.now()
                }
            
            diagnose_result = last_execution["phases"].get("diagnose", {})
            problems = diagnose_result.get("problems", [])
            
            # Create migration plan
            migration_plan = self._create_migration_plan(problems)
            
            # Validate changes
            validation_result = self._validate_proposed_changes(migration_plan)
            
            result = {
                "phase": "propose",
                "success": validation_result.get("valid", False),
                "migration_plan": migration_plan,
                "validation_result": validation_result,
                "affected_paths": self._get_affected_paths(migration_plan),
                "risk_assessment": self._assess_risk(migration_plan),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
            
            if not result["success"]:
                result["error"] = validation_result.get("error", "Validation failed")
            
        except Exception as e:
            result = {
                "phase": "propose",
                "success": False,
                "error": str(e),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
        
        return result
    
    def _execute_execute_phase(self, routine_name: str) -> Dict:
        """Execute Phase 4: Execute proposed changes"""
        phase_start = datetime.now()
        
        try:
            # Get proposal from previous phase
            last_execution = self.get_last_execution()
            if not last_execution or "phases" not in last_execution:
                return {
                    "phase": "execute",
                    "success": False,
                    "error": "No previous execution available for execution",
                    "start_time": phase_start,
                    "end_time": datetime.now()
                }
            
            propose_result = last_execution["phases"].get("propose", {})
            migration_plan = propose_result.get("migration_plan", {})
            
            # Execute changes with rollback capability
            execution_result = self._execute_migration_plan(migration_plan)
            
            result = {
                "phase": "execute",
                "success": execution_result.get("success", False),
                "changes_made": execution_result.get("changes_made", []),
                "rollback_info": execution_result.get("rollback_info", {}),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
            
            if not result["success"]:
                result["error"] = execution_result.get("error", "Execution failed")
            
        except Exception as e:
            result = {
                "phase": "execute",
                "success": False,
                "error": str(e),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
        
        return result
    
    def _execute_validate_phase(self, routine_name: str) -> Dict:
        """Execute Phase 5: Validate changes"""
        phase_start = datetime.now()
        
        try:
            # Get execution from previous phase
            last_execution = self.get_last_execution()
            if not last_execution or "phases" not in last_execution:
                return {
                    "phase": "validate",
                    "success": False,
                    "error": "No previous execution available for validation",
                    "start_time": phase_start,
                    "end_time": datetime.now()
                }
            
            execute_result = last_execution["phases"].get("execute", {})
            changes_made = execute_result.get("changes_made", [])
            
            # Validate changes
            validation_result = self._validate_changes(changes_made)
            
            # Run verification checks
            verification_results = self._run_verification_checks(validation_result)
            
            result = {
                "phase": "validate",
                "success": validation_result.get("valid", False) and all(v.get("passed", False) for v in verification_results),
                "validation_result": validation_result,
                "verification_results": verification_results,
                "improvements": self._identify_improvements(validation_result),
                "remaining_issues": self._identify_remaining_issues(verification_results),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
            
            if not result["success"]:
                failed_checks = [v for v in verification_results if not v.get("passed", False)]
                result["error"] = f"Validation failed: {len(failed_checks)} checks failed"
            
        except Exception as e:
            result = {
                "phase": "validate",
                "success": False,
                "error": str(e),
                "start_time": phase_start,
                "end_time": datetime.now()
            }
        
        return result
    
    # Helper methods for evidence collection and analysis
    def _collect_structure_evidence(self) -> Dict:
        """Collect evidence about current project structure"""
        evidence = {
            "files": [],
            "directories": [],
            "git_status": {},
            "config_files": [],
            "dependencies": [],
            "imports": [],
            "timestamp": datetime.now().isoformat()
        }
        
        # Collect file system evidence
        for root, dirs, files in os.walk("."):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path)
                
                # Get file info
                stat = os.stat(file_path)
                file_info = {
                    "path": rel_path,
                    "size": stat.st_size,
                    "modified": stat.st_mtime,
                    "type": "file"
                }
                
                evidence["files"].append(file_info)
            
            for dir in dirs:
                dir_path = os.path.join(root, dir)
                rel_path = os.path.relpath(dir_path)
                evidence["directories"].append({
                    "path": rel_path,
                    "type": "directory"
                })
        
        # Get git status
        try:
            import subprocess
            git_status = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True
            ).stdout
            evidence["git_status"] = git_status
        except:
            pass
        
        return evidence
    
    def _identify_structure_components(self) -> Dict:
        """Identify key structure components"""
        components = {
            "source_code": [],
            "tests": [],
            "documentation": [],
            "configuration": [],
            "scripts": [],
            "dependencies": [],
            "build_artifacts": [],
            "generated_content": []
        }
        
        # Classify files based on patterns
        for root, dirs, files in os.walk("."):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for file in files:
                if file.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path)
                
                # Classify based on extension and location
                if self._is_source_code(rel_path):
                    components["source_code"].append(rel_path)
                elif self._is_test_file(rel_path):
                    components["tests"].append(rel_path)
                elif self._is_documentation(rel_path):
                    components["documentation"].append(rel_path)
                elif self._is_configuration(rel_path):
                    components["configuration"].append(rel_path)
                elif self._is_script(rel_path):
                    components["scripts"].append(rel_path)
                elif self._is_dependency(file_path):
                    components["dependencies"].append(rel_path)
                elif self._is_build_artifact(rel_path):
                    components["build_artifacts"].append(rel_path)
                elif self._is_generated_content(rel_path):
                    components["generated_content"].append(rel_path)
        
        return components
    
    def _is_source_code(self, path: str) -> bool:
        """Check if path represents source code"""
        source_patterns = [
            ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".cpp", ".c", ".h",
            ".go", ".rs", ".php", ".rb", ".swift", "Dockerfile", "Makefile",
            "requirements.txt", "package.json", "setup.py", "pom.xml"
        ]
        
        for pattern in source_patterns:
            if pattern in path:
                return True
        return False
    
    def _is_test_file(self, path: str) -> bool:
        """Check if path represents a test file"""
        test_patterns = [
            "test_", "_test", ".test.", ".spec.", "tests/", "__tests__/"
        ]
        
        for pattern in test_patterns:
            if pattern in path:
                return True
        return False
    
    def _is_documentation(self, path: str) -> bool:
        """Check if path represents documentation"""
        doc_patterns = [
            "README", "CHANGELOG", "LICENSE", "CONTRIBUTING", "docs/",
            ".md", ".rst", ".txt", "documentation/"
        ]
        
        for pattern in doc_patterns:
            if pattern in path:
                return True
        return False
    
    def _is_configuration(self, path: str) -> bool:
        """Check if path represents configuration"""
        config_patterns = [
            "config", "settings", ".env", "docker-compose", "nginx",
            "ini", "yaml", "yml", "json", ".config"
        ]
        
        for pattern in config_patterns:
            if pattern in path:
                return True
        return False
    
    def _is_script(self, path: str) -> bool:
        """Check if path represents a script"""
        script_patterns = [
            "script", "scripts/", "bin/", "cli/", ".sh", ".bash", ".zsh"
        ]
        
        for pattern in script_patterns:
            if pattern in path:
                return True
        return False
    
    def _is_dependency(self, path: str) -> bool:
        """Check if path represents a dependency"""
        dep_patterns = [
            "node_modules/", "__pycache__/", ".venv/", "venv/", "env/",
            "site-packages/", "lib/", "vendor/"
        ]
        
        for pattern in dep_patterns:
            if pattern in path:
                return True
        return False
    
    def _is_build_artifact(self, path: str) -> bool:
        """Check if path represents a build artifact"""
        artifact_patterns = [
            "build/", "dist/", "out/", "output/", "artifacts/",
            ".egg", ".whl", ".jar", ".war", ".zip", ".tar"
        ]
        
        for pattern in artifact_patterns:
            if pattern in path:
                return True
        return False
    
    def _is_generated_content(self, path: str) -> bool:
        """Check if path represents generated content"""
        gen_patterns = [
            "generated/", "output/", "tmp/", "temp/", "cache/",
            "*.min.js", "*.bundle.js", "*.min.css", "*.bundle.css"
        ]
        
        for pattern in gen_patterns:
            if pattern in path:
                return True
        return False
    
    # Placeholder methods for evidence-based operations
    def _analyze_structural_drift(self, evidence: Dict, components: Dict) -> Dict:
        """Analyze structural drift from evidence"""
        # Implementation would analyze evidence for structural changes
        return {
            "drift_detected": False,
            "drift_score": 0.0,
            "concerning_patterns": [],
            "stability_score": 1.0
        }
    
    def _generate_inspect_findings(self, drift_analysis: Dict) -> List[str]:
        """Generate findings from inspection phase"""
        return []
    
    def _identify_problems(self, evidence: Dict) -> List[Dict]:
        """Identify problems from evidence"""
        return []
    
    def _assess_severity(self, problems: List[Dict]) -> Dict:
        """Assess severity of problems"""
        return {"total": 0, "critical": 0, "medium": 0, "low": 0}
    
    def _prioritize_problems(self, problems: List[Dict], severity: Dict) -> List[Dict]:
        """Prioritize problems based on severity"""
        return []
    
    def _identify_root_causes(self, problems: List[Dict]) -> List[str]:
        """Identify root causes of problems"""
        return []
    
    def _generate_recommendations(self, problems: List[Dict]) -> List[str]:
        """Generate recommendations for problems"""
        return []
    
    def _create_migration_plan(self, problems: List[Dict]) -> Dict:
        """Create migration plan for problems"""
        return {"changes": [], "dependencies": []}
    
    def _validate_proposed_changes(self, migration_plan: Dict) -> Dict:
        """Validate proposed changes"""
        return {"valid": True}
    
    def _get_affected_paths(self, migration_plan: Dict) -> List[str]:
        """Get paths affected by migration plan"""
        return []
    
    def _assess_risk(self, migration_plan: Dict) -> Dict:
        """Assess risk of migration plan"""
        return {"risk_level": "low", "mitigation": []}
    
    def _execute_migration_plan(self, migration_plan: Dict) -> Dict:
        """Execute migration plan with rollback capability"""
        return {"success": True, "changes_made": [], "rollback_info": {}}
    
    def _validate_changes(self, changes_made: List[str]) -> Dict:
        """Validate that changes were made correctly"""
        return {"valid": True}
    
    def _run_verification_checks(self, validation_result: Dict) -> List[Dict]:
        """Run verification checks on changes"""
        return [{"check": "test", "passed": True}]
    
    def _identify_improvements(self, validation_result: Dict) -> List[str]:
        """Identify improvements from changes"""
        return []
    
    def _identify_remaining_issues(self, verification_results: List[Dict]) -> List[str]:
        """Identify remaining issues after validation"""
        return []
    
    def get_last_execution(self) -> Dict:
        """Get the last routine execution"""
        # This would typically read from a persistent storage
        return None

# Standalone execution function
def execute_routine(routine_name: str) -> Dict:
    """Execute a routine by name"""
    executor = RoutineExecutor()
    return executor.execute_routine(routine_name)

if __name__ == "__main__":
    # Example usage
    print("Routine Executor initialized")
    
    # Example: Execute daily maintenance
    result = execute_routine("daily-maintenance")
    print(f"Execution result: {result['status']}")
    if result["status"] == "completed":
        print(f"Duration: {result['duration']:.2f} seconds")
        print(f"Phases completed: {list(result['phases'].keys())}")