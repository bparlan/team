#!/usr/bin/env python3
"""
Auto-Discovery System
Pattern detection and gap analysis for routine engine integration.
"""

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

class AutoDiscoverySystem:
    def __init__(self, project_root: str = ".", config_dir: str = "routine-engine/config"):
        self.project_root = Path(project_root)
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        
        # Load configuration
        self.config = self._load_config()
        
        # Cache for discovered patterns
        self.pattern_cache = {}
        self.gap_cache = {}
        
    def _load_config(self) -> dict:
        """Load auto-discovery configuration"""
        config_file = self.config_dir / "auto_discovery_config.json"
        
        default_config = {
            "pattern_detection": {
                "enabled": True,
                "min_confidence": 0.7,
                "patterns": {
                    "ai_modules": {
                        "keywords": ["ai", "llm", "gemini", "openai", "model"],
                        "file_patterns": ["ai/", "llm/", "model/", "neural/"],
                        "confidence": 0.9,
                        "enabled": True
                    },
                    "browser_automation": {
                        "keywords": ["playwright", "selenium", "browser", "automation"],
                        "file_patterns": ["browser/", "playwright/", "selenium/"],
                        "confidence": 0.8,
                        "enabled": True
                    },
                    "security": {
                        "keywords": ["security", "auth", "token", "credential", "encryption"],
                        "file_patterns": ["security/", "auth/", "credential/"],
                        "confidence": 0.85,
                        "enabled": True
                    },
                    "database": {
                        "keywords": ["database", "sql", "postgres", "mysql", "redis", "sqlite"],
                        "file_patterns": ["db/", "database/", "migration/"],
                        "confidence": 0.8,
                        "enabled": True
                    },
                    "platform_handlers": {
                        "keywords": ["platform", "handler", "adapter", "integrator"],
                        "file_patterns": ["platform/", "handler/", "adapter/"],
                        "confidence": 0.75,
                        "enabled": True
                    },
                    "sdp_pipeline": {
                        "keywords": ["sdp", "pipeline", "specification", "stage", "milestone"],
                        "file_patterns": ["pipeline/", "specification/", "stage/"],
                        "confidence": 0.85
                    }
                }
            },
            "gap_analysis": {
                "enabled": True,
                "thresholds": {
                    "skill_coverage": 0.90,
                    "knowledge_completeness": 0.95,
                    "team_alignment": 0.85
                },
                "gap_categories": [
                    "skill_match",
                    "knowledge_coverage", 
                    "experience_alignment",
                    "resource_availability"
                ]
            },
            "evolution_detection": {
                "enabled": True,
                "change_patterns": {
                    "new_requirements": {
                        "keywords": ["new", "additional", "extra", "missing"],
                        "confidence": 0.8
                    },
                    "optimization_opportunities": {
                        "keywords": ["optimize", "improve", "enhance", "refactor"],
                        "confidence": 0.75
                    },
                    "team_evolution": {
                        "keywords": ["team", "person", "member", "role", "expertise"],
                        "confidence": 0.7
                    }
                }
            }
        }
        
        if config_file.exists():
            with open(config_file, 'r') as f:
                return json.load(f)
        else:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=2)
            return default_config
    
    def discover_patterns(self, routine_name: str = None) -> Dict:
        """Discover patterns in the project based on routine context"""
        cache_key = f"patterns_{routine_name or 'all'}"
        
        if cache_key in self.pattern_cache:
            return self.pattern_cache[cache_key]
        
        discovery_result = {
            "routine_name": routine_name,
            "discovered_patterns": {},
            "confidence_scores": {},
            "discovery_timestamp": datetime.now().isoformat(),
            "metadata": {
                "project_path": str(self.project_root),
                "files_analyzed": 0,
                "patterns_found": 0
            }
        }
        
        # Analyze project structure
        project_analysis = self._analyze_project_structure()
        
        # Detect specific patterns
        for pattern_name, pattern_config in self.config["pattern_detection"]["patterns"].items():
            if pattern_config["enabled"]:
                pattern_result = self._detect_pattern(pattern_name, pattern_config, project_analysis)
                discovery_result["discovered_patterns"][pattern_name] = pattern_result
                discovery_result["confidence_scores"][pattern_name] = pattern_result.get("confidence", 0.0)
                
                if pattern_result.get("found", False):
                    discovery_result["metadata"]["patterns_found"] += 1
        
        discovery_result["metadata"]["files_analyzed"] = project_analysis.get("total_files", 0)
        
        # Cache the result
        self.pattern_cache[cache_key] = discovery_result
        
        return discovery_result
    
    def analyze_gaps(self, routine_name: str = None) -> Dict:
        """Analyze gaps between project needs and current capabilities"""
        cache_key = f"gaps_{routine_name or 'all'}"
        
        if cache_key in self.gap_cache:
            return self.gap_cache[cache_key]
        
        gap_analysis_result = {
            "routine_name": routine_name,
            "gap_analysis": {},
            "priority_gaps": [],
            "recommendations": [],
            "analysis_timestamp": datetime.now().isoformat(),
            "metadata": {
                "thresholds_used": self.config["gap_analysis"]["thresholds"],
                "categories_analyzed": len(self.config["gap_analysis"]["gap_categories"])
            }
        }
        
        # Get pattern discovery results
        pattern_discovery = self.discover_patterns(routine_name)
        
        # Analyze each gap category
        for category in self.config["gap_analysis"]["gap_categories"]:
            gap_result = self._analyze_gap_category(category, pattern_discovery, routine_name)
            gap_analysis_result["gap_analysis"][category] = gap_result
            
            if gap_result.get("priority", "low") in ["high", "critical"]:
                gap_analysis_result["priority_gaps"].append({
                    "category": category,
                    "details": gap_result,
                    "impact": self._calculate_gap_impact(gap_result)
                })
        
        # Generate recommendations based on gaps
        gap_analysis_result["recommendations"] = self._generate_gap_recommendations(gap_analysis_result)
        
        # Cache the result
        self.gap_cache[cache_key] = gap_analysis_result
        
        return gap_analysis_result
    
    def detect_evolution_patterns(self, routine_name: str = None) -> Dict:
        """Detect evolution patterns and trends"""
        evolution_result = {
            "routine_name": routine_name,
            "evolution_patterns": {},
            "trend_analysis": {},
            "change_indicators": [],
            "evolution_timestamp": datetime.now().isoformat(),
            "recommendations": []
        }
        
        # Get pattern and gap analysis
        pattern_discovery = self.discover_patterns(routine_name)
        gap_analysis = self.analyze_gaps(routine_name)
        
        # Analyze for evolution indicators
        evolution_result["evolution_patterns"] = self._analyze_evolution_indicators(pattern_discovery, gap_analysis)
        
        # Detect changes and trends
        evolution_result["trend_analysis"] = self._analyze_trends(pattern_discovery, gap_analysis)
        
        # Generate evolution recommendations
        evolution_result["recommendations"] = self._generate_evolution_recommendations(evolution_result)
        
        return evolution_result
    
    def _analyze_project_structure(self) -> Dict:
        """Analyze overall project structure"""
        analysis = {
            "total_files": 0,
            "file_types": {},
            "directory_structure": {},
            "key_files": [],
            "dependencies": [],
            "configuration_files": []
        }
        
        for root, dirs, files in os.walk(self.project_root):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', '.git', '.venv']]
            
            # Count and categorize files
            for file in files:
                if file.startswith('.'):
                    continue
                    
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.project_root)
                
                analysis["total_files"] += 1
                
                # File type analysis
                if '.' in file:
                    ext = file.split('.')[-1]
                    analysis["file_types"][ext] = analysis["file_types"].get(ext, 0) + 1
                
                # Key file identification
                if self._is_key_file(rel_path, file):
                    analysis["key_files"].append(rel_path)
                
                # Configuration file detection
                if self._is_config_file(file_path, rel_path):
                    analysis["configuration_files"].append(rel_path)
            
            # Directory structure
            rel_dir = os.path.relpath(root, self.project_root)
            analysis["directory_structure"][rel_dir] = {
                "subdirectories": len(dirs),
                "files": len(files)
            }
        
        return analysis
    
    def _is_key_file(self, rel_path: str, filename: str) -> bool:
        """Check if file is a key file for pattern detection"""
        key_indicators = [
            # Main application files
            "__main__.py", "app.py", "main.py", "server.py",
            "index.py", "__init__.py", "config.py",
            
            # Configuration files
            "settings.py", "config.yaml", "docker-compose.yaml",
            "requirements.txt", "pyproject.toml", "setup.py",
            
            # Pipeline and integration files
            "pipeline.py", "spec.py", "specification.py",
            "stage.py", "milestone.py",
            
            # Database and storage
            "models.py", "schema.py", "database.py",
            "migrations", "seeds",
            
            # AI and ML
            "models/", "training/", "inference/",
            "llm.py", "ai.py", "gemini.py"
        ]
        
        # Check filename
        if any(indicator in filename for indicator in key_indicators):
            return True
        
        # Check path patterns
        path_indicators = ["src/", "app/", "lib/", "core/", "service/"]
        if any(indicator in rel_path for indicator in path_indicators):
            return True
        
        return False
    
    def _is_config_file(self, file_path: str, rel_path: str) -> bool:
        """Check if file is a configuration file"""
        config_extensions = ['.yaml', '.yml', '.json', '.toml', '.cfg', '.ini', '.env']
        config_names = ['config', 'settings', 'environment', 'env', 'setup']
        
        filename = os.path.basename(file_path).lower()
        
        # Check extension
        if any(filename.endswith(ext) for ext in config_extensions):
            return True
        
        # Check filename
        if any(name in filename for name in config_names):
            return True
        
        # Check path
        path_indicators = ['config/', 'settings/', 'env/', 'environment/']
        if any(indicator in rel_path for indicator in path_indicators):
            return True
        
        return False
    
    def _detect_pattern(self, pattern_name: str, pattern_config: dict, project_analysis: dict) -> Dict:
        """Detect a specific pattern"""
        result = {
            "pattern_name": pattern_name,
            "found": False,
            "confidence": 0.0,
            "evidence": [],
            "details": {}
        }
        
        # Pattern-specific detection logic
        if pattern_name == "ai_modules":
            result = self._detect_ai_modules(project_analysis, pattern_config)
        elif pattern_name == "browser_automation":
            result = self._detect_browser_automation(project_analysis, pattern_config)
        elif pattern_name == "security":
            result = self._detect_security_components(project_analysis, pattern_config)
        elif pattern_name == "database":
            result = self._detect_database_components(project_analysis, pattern_config)
        elif pattern_name == "platform_handlers":
            result = self._detect_platform_handlers(project_analysis, pattern_config)
        elif pattern_name == "sdp_pipeline":
            result = self._detect_sdp_pipeline(project_analysis, pattern_config)
        
        return result
    
    def _detect_ai_modules(self, project_analysis: dict, config: dict) -> Dict:
        """Detect AI/ML modules and components"""
        result = {
            "pattern_name": "ai_modules",
            "found": False,
            "confidence": 0.0,
            "evidence": [],
            "details": {
                "ai_files": [],
                "model_files": [],
                "configuration_files": []
            }
        }
        
        # Look for AI-related files and directories
        for file_path in project_analysis["key_files"]:
            if any(keyword in file_path.lower() for keyword in config["keywords"]):
                result["details"]["ai_files"].append(file_path)
                result["evidence"].append(f"Found AI-related file: {file_path}")
            
            if any(pattern in file_path.lower() for pattern in config["file_patterns"]):
                result["details"]["model_files"].append(file_path)
                result["evidence"].append(f"Found AI module directory: {file_path}")
        
        # Check configuration files for AI settings
        for config_file in project_analysis["configuration_files"]:
            if any(keyword in config_file.lower() for keyword in config["keywords"]):
                result["details"]["configuration_files"].append(config_file)
                result["evidence"].append(f"Found AI configuration: {config_file}")
        
        # Calculate confidence based on evidence
        if result["details"]["ai_files"] or result["details"]["model_files"]:
            result["found"] = True
            confidence = min(1.0, len(result["evidence"]) * config["confidence"] / 10)
            result["confidence"] = confidence
        
        return result
    
    def _detect_browser_automation(self, project_analysis: dict, config: dict) -> Dict:
        """Detect browser automation components"""
        result = {
            "pattern_name": "browser_automation",
            "found": False,
            "confidence": 0.0,
            "evidence": [],
            "details": {
                "browser_files": [],
                "playwright_files": [],
                "automation_configs": []
            }
        }
        
        # Similar detection logic for browser automation
        for file_path in project_analysis["key_files"]:
            if any(keyword in file_path.lower() for keyword in config["keywords"]):
                result["details"]["browser_files"].append(file_path)
                result["evidence"].append(f"Found browser automation file: {file_path}")
            
            if any(pattern in file_path.lower() for pattern in config["file_patterns"]):
                result["details"]["playwright_files"].append(file_path)
                result["evidence"].append(f"Found Playwright file: {file_path}")
        
        # Check for browser-related configuration
        for config_file in project_analysis["configuration_files"]:
            if any(keyword in config_file.lower() for keyword in config["keywords"]):
                result["details"]["automation_configs"].append(config_file)
                result["evidence"].append(f"Found browser automation config: {config_file}")
        
        # Calculate confidence
        if result["details"]["browser_files"] or result["details"]["playwright_files"]:
            result["found"] = True
            confidence = min(1.0, len(result["evidence"]) * config["confidence"] / 10)
            result["confidence"] = confidence
        
        return result
    
    def _detect_security_components(self, project_analysis: dict, config: dict) -> Dict:
        """Detect security-related components"""
        result = {
            "pattern_name": "security",
            "found": False,
            "confidence": 0.0,
            "evidence": [],
            "details": {
                "security_files": [],
                "auth_files": [],
                "credential_files": []
            }
        }
        
        # Similar detection logic for security
        for file_path in project_analysis["key_files"]:
            if any(keyword in file_path.lower() for keyword in config["keywords"]):
                result["details"]["security_files"].append(file_path)
                result["evidence"].append(f"Found security file: {file_path}")
        
        # Calculate confidence
        if result["details"]["security_files"]:
            result["found"] = True
            confidence = min(1.0, len(result["evidence"]) * config["confidence"] / 10)
            result["confidence"] = confidence
        
        return result
    
    def _detect_database_components(self, project_analysis: dict, config: dict) -> Dict:
        """Detect database components"""
        result = {
            "pattern_name": "database",
            "found": False,
            "confidence": 0.0,
            "evidence": [],
            "details": {
                "database_files": [],
                "migration_files": [],
                "model_files": []
            }
        }
        
        # Similar detection logic for database
        for file_path in project_analysis["key_files"]:
            if any(keyword in file_path.lower() for keyword in config["keywords"]):
                result["details"]["database_files"].append(file_path)
                result["evidence"].append(f"Found database file: {file_path}")
            
            if any(pattern in file_path.lower() for pattern in config["file_patterns"]):
                result["details"]["migration_files"].append(file_path)
                result["evidence"].append(f"Found database migration: {file_path}")
        
        # Calculate confidence
        if result["details"]["database_files"]:
            result["found"] = True
            confidence = min(1.0, len(result["evidence"]) * config["confidence"] / 10)
            result["confidence"] = confidence
        
        return result
    
    def _detect_platform_handlers(self, project_analysis: dict, config: dict) -> Dict:
        """Detect platform handler components"""
        result = {
            "pattern_name": "platform_handlers",
            "found": False,
            "confidence": 0.0,
            "evidence": [],
            "details": {
                "platform_files": [],
                "handler_files": [],
                "adapter_files": []
            }
        }
        
        # Similar detection logic for platform handlers
        for file_path in project_analysis["key_files"]:
            if any(keyword in file_path.lower() for keyword in config["keywords"]):
                result["details"]["platform_files"].append(file_path)
                result["evidence"].append(f"Found platform file: {file_path}")
            
            if any(pattern in file_path.lower() for pattern in config["file_patterns"]):
                result["details"]["handler_files"].append(file_path)
                result["evidence"].append(f"Found handler file: {file_path}")
        
        # Calculate confidence
        if result["details"]["platform_files"] or result["details"]["handler_files"]:
            result["found"] = True
            confidence = min(1.0, len(result["evidence"]) * config["confidence"] / 10)
            result["confidence"] = confidence
        
        return result
    
    def _detect_sdp_pipeline(self, project_analysis: dict, config: dict) -> Dict:
        """Detect SDP pipeline components"""
        result = {
            "pattern_name": "sdp_pipeline",
            "found": False,
            "confidence": 0.0,
            "evidence": [],
            "details": {
                "pipeline_files": [],
                "specification_files": [],
                "stage_files": []
            }
        }
        
        # Similar detection logic for SDP pipeline
        for file_path in project_analysis["key_files"]:
            if any(keyword in file_path.lower() for keyword in config["keywords"]):
                result["details"]["pipeline_files"].append(file_path)
                result["evidence"].append(f"Found pipeline file: {file_path}")
            
            if any(pattern in file_path.lower() for pattern in config["file_patterns"]):
                result["details"]["specification_files"].append(file_path)
                result["evidence"].append(f"Found specification file: {file_path}")
        
        # Calculate confidence
        if result["details"]["pipeline_files"] or result["details"]["specification_files"]:
            result["found"] = True
            confidence = min(1.0, len(result["evidence"]) * config["confidence"] / 10)
            result["confidence"] = confidence
        
        return result
    
    def _analyze_gap_category(self, category: str, pattern_discovery: dict, routine_name: str) -> Dict:
        """Analyze a specific gap category"""
        gap_result = {
            "category": category,
            "found": False,
            "severity": "low",
            "evidence": [],
            "impact": 0.0,
            "threshold_met": False,
            "details": {}
        }
        
        # Category-specific analysis
        if category == "skill_match":
            gap_result = self._analyze_skill_match_gap(pattern_discovery, routine_name)
        elif category == "knowledge_coverage":
            gap_result = self._analyze_knowledge_coverage_gap(pattern_discovery, routine_name)
        elif category == "experience_alignment":
            gap_result = self._analyze_experience_alignment_gap(pattern_discovery, routine_name)
        elif category == "resource_availability":
            gap_result = self._analyze_resource_availability_gap(pattern_discovery, routine_name)
        
        return gap_result
    
    def _analyze_skill_match_gap(self, pattern_discovery: dict, routine_name: str) -> Dict:
        """Analyze skill match gap"""
        # Determine current skill coverage based on discovered patterns
        skill_coverage = 0.0
        evidence = []
        
        # Check various patterns to estimate skill coverage
        patterns = pattern_discovery["discovered_patterns"]
        
        # AI skills
        if "ai_modules" in patterns and patterns["ai_modules"]["found"]:
            skill_coverage += 0.25
            evidence.append("AI/ML capabilities detected")
        
        # Browser automation skills  
        if "browser_automation" in patterns and patterns["browser_automation"]["found"]:
            skill_coverage += 0.25
            evidence.append("Browser automation capabilities detected")
        
        # Security skills
        if "security" in patterns and patterns["security"]["found"]:
            skill_coverage += 0.25
            evidence.append("Security capabilities detected")
        
        # Database skills
        if "database" in patterns and patterns["database"]["found"]:
            skill_coverage += 0.25
            evidence.append("Database capabilities detected")
        
        # Check against threshold
        threshold = self.config["gap_analysis"]["thresholds"]["skill_coverage"]
        gap_result = {
            "category": "skill_match",
            "found": skill_coverage < threshold,
            "severity": "high" if skill_coverage < threshold * 0.8 else "medium" if skill_coverage < threshold else "low",
            "evidence": evidence,
            "impact": threshold - skill_coverage,
            "threshold_met": skill_coverage >= threshold,
            "details": {
                "current_coverage": skill_coverage,
                "required_coverage": threshold,
                "missing_skills": self._identify_missing_skills(skill_coverage, patterns)
            }
        }
        
        return gap_result
    
    def _analyze_knowledge_coverage_gap(self, pattern_discovery: dict, routine_name: str) -> Dict:
        """Analyze knowledge coverage gap"""
        # Similar analysis for knowledge coverage
        knowledge_coverage = 0.0
        evidence = []
        
        # Based on discovered architectural patterns
        if "platform_handlers" in pattern_discovery["discovered_patterns"]:
            if pattern_discovery["discovered_patterns"]["platform_handlers"]["found"]:
                knowledge_coverage += 0.33
                evidence.append("Platform handler knowledge detected")
        
        if "sdp_pipeline" in pattern_discovery["discovered_patterns"]:
            if pattern_discovery["discovered_patterns"]["sdp_pipeline"]["found"]:
                knowledge_coverage += 0.33
                evidence.append("SDP pipeline knowledge detected")
        
        if "ai_modules" in pattern_discovery["discovered_patterns"]:
            if pattern_discovery["discovered_patterns"]["ai_modules"]["found"]:
                knowledge_coverage += 0.34
                evidence.append("AI module knowledge detected")
        
        # Check against threshold
        threshold = self.config["gap_analysis"]["thresholds"]["knowledge_completeness"]
        gap_result = {
            "category": "knowledge_coverage",
            "found": knowledge_coverage < threshold,
            "severity": "high" if knowledge_coverage < threshold * 0.8 else "medium" if knowledge_coverage < threshold else "low",
            "evidence": evidence,
            "impact": threshold - knowledge_coverage,
            "threshold_met": knowledge_coverage >= threshold,
            "details": {
                "current_coverage": knowledge_coverage,
                "required_coverage": threshold,
                "knowledge_areas": list(pattern_discovery["discovered_patterns"].keys())
            }
        }
        
        return gap_result
    
    def _analyze_experience_alignment_gap(self, pattern_discovery: dict, routine_name: str) -> Dict:
        """Analyze experience alignment gap"""
        # Simplified analysis based on project complexity
        complexity_score = 0.0
        evidence = []
        
        # Estimate complexity based on discovered patterns
        patterns = pattern_discovery["discovered_patterns"]
        high_complexity_patterns = ["platform_handlers", "sdp_pipeline", "ai_modules", "browser_automation"]
        
        for pattern in high_complexity_patterns:
            if pattern in patterns and patterns[pattern]["found"]:
                complexity_score += 0.25
                evidence.append(f"High-complexity component detected: {pattern}")
        
        # Align with project size
        project_analysis = self._analyze_project_structure()
        file_count = project_analysis["total_files"]
        
        if file_count > 100:
            complexity_score += 0.25
            evidence.append(f"Large project size: {file_count} files")
        elif file_count > 50:
            complexity_score += 0.15
            evidence.append(f"Medium project size: {file_count} files")
        
        # Experience requirement
        experience_requirement = min(1.0, complexity_score)
        gap_result = {
            "category": "experience_alignment",
            "found": experience_requirement < 0.8,
            "severity": "high" if experience_requirement < 0.6 else "medium" if experience_requirement < 0.8 else "low",
            "evidence": evidence,
            "impact": 0.8 - experience_requirement,
            "threshold_met": experience_requirement >= 0.8,
            "details": {
                "complexity_score": complexity_score,
                "experience_requirement": experience_requirement,
                "project_size": file_count
            }
        }
        
        return gap_result
    
    def _analyze_resource_availability_gap(self, pattern_discovery: dict, routine_name: str) -> Dict:
        """Analyze resource availability gap"""
        # Based on team composition and resources
        resource_availability = 0.5  # Default medium
        evidence = []
        
        # Check for evidence of resources
        patterns = pattern_discovery["discovered_patterns"]
        
        if "ai_modules" in patterns and patterns["ai_modules"]["found"]:
            resource_availability += 0.2
            evidence.append("AI resources detected")
        
        if "browser_automation" in patterns and patterns["browser_automation"]["found"]:
            resource_availability += 0.2
            evidence.append("Browser automation resources detected")
        
        if "security" in patterns and patterns["security"]["found"]:
            resource_availability += 0.2
            evidence.append("Security resources detected")
        
        # Check against threshold
        threshold = self.config["gap_analysis"]["thresholds"]["resource_availability"]
        gap_result = {
            "category": "resource_availability",
            "found": resource_availability < threshold,
            "severity": "high" if resource_availability < threshold * 0.7 else "medium" if resource_availability < threshold else "low",
            "evidence": evidence,
            "impact": threshold - resource_availability,
            "threshold_met": resource_availability >= threshold,
            "details": {
                "current_availability": resource_availability,
                "required_availability": threshold,
                "resource_types": list(patterns.keys())
            }
        }
        
        return gap_result
    
    def _identify_missing_skills(self, current_coverage: float, patterns: dict) -> List[str]:
        """Identify missing skills based on current coverage"""
        missing_skills = []
        
        # Threshold for each skill area
        threshold = 0.25
        
        # Check each pattern
        for pattern_name, pattern_data in patterns.items():
            if pattern_data.get("found", False):
                # This skill area is covered
                pass
            else:
                # This skill area is missing
                missing_skills.append(pattern_name.replace("_", " ").title())
        
        return missing_skills
    
    def _calculate_gap_impact(self, gap_result: dict) -> float:
        """Calculate the impact of a gap"""
        # Multiply severity by gap size
        severity_impact = {
            "low": 1.0,
            "medium": 2.5,
            "high": 5.0,
            "critical": 10.0
        }
        
        base_impact = severity_impact.get(gap_result.get("severity", "low"), 1.0)
        gap_size = gap_result.get("impact", 0.0)
        
        return base_impact * gap_size
    
    def _generate_gap_recommendations(self, gap_analysis: dict) -> List[Dict]:
        """Generate recommendations based on gap analysis"""
        recommendations = []
        
        for priority_gap in gap_analysis["priority_gaps"]:
            category = priority_gap["category"]
            details = priority_gap["details"]
            impact = priority_gap["impact"]
            
            # Generate specific recommendations
            if category == "skill_match":
                missing_skills = details.get("missing_skills", [])
                for skill in missing_skills:
                    recommendations.append({
                        "type": "skill_development",
                        "target": skill,
                        "priority": "high" if impact > 5.0 else "medium",
                        "effort": "medium",
                        "description": f"Develop {skill} expertise to address skill gap"
                    })
            
            elif category == "knowledge_coverage":
                recommendations.append({
                    "type": "knowledge_acquisition",
                    "target": "architectural_understanding",
                    "priority": "high" if impact > 3.0 else "medium",
                    "effort": "high",
                    "description": f"Enhance knowledge of {', '.join(details.get('knowledge_areas', []))} areas"
                })
            
            elif category == "experience_alignment":
                recommendations.append({
                    "type": "experience_building",
                    "target": "complexity_experience",
                    "priority": "high" if impact > 2.0 else "medium",
                    "effort": "high",
                    "description": f"Gain experience with {details.get('complexity_score', 0):.1f} complexity level"
                })
            
            elif category == "resource_availability":
                recommendations.append({
                    "type": "resource_acquisition",
                    "target": "technical_resources",
                    "priority": "high" if impact > 4.0 else "medium",
                    "effort": "medium",
                    "description": f"Acquire or access {', '.join(details.get('resource_types', []))} resources"
                })
        
        return recommendations
    
    def _analyze_evolution_indicators(self, pattern_discovery: dict, gap_analysis: dict) -> Dict:
        """Analyze evolution indicators"""
        evolution_indicators = {
            "evolution_detected": False,
            "evolution_type": None,
            "confidence": 0.0,
            "indicators": [],
            "trends": {}
        }
        
        # Check for evolution indicators in patterns
        patterns = pattern_discovery["discovered_patterns"]
        
        # Check for new requirements
        new_requirements = any(
            "new" in str(pattern_data.get("evidence", [])).lower() or
            "additional" in str(pattern_data.get("evidence", [])).lower()
            for pattern_name, pattern_data in patterns.items()
        )
        
        # Check for optimization opportunities
        optimization_opportunities = any(
            "optimize" in str(pattern_data.get("evidence", [])).lower() or
            "improve" in str(pattern_data.get("evidence", [])).lower()
            for pattern_name, pattern_data in patterns.items()
        )
        
        # Check for team evolution
        team_evolution = any(
            "team" in str(pattern_data.get("evidence", [])).lower() or
            "person" in str(pattern_data.get("evidence", [])).lower()
            for pattern_name, pattern_data in patterns.items()
        )
        
        # Determine evolution type
        if new_requirements:
            evolution_indicators["evolution_type"] = "expansion"
            evolution_indicators["indicators"].append("New requirements detected")
        elif optimization_opportunities:
            evolution_indicators["evolution_type"] = "optimization"
            evolution_indicators["indicators"].append("Optimization opportunities detected")
        elif team_evolution:
            evolution_indicators["evolution_type"] = "team_evolution"
            evolution_indicators["indicators"].append("Team evolution detected")
        else:
            evolution_indicators["evolution_type"] = "maintenance"
            evolution_indicators["indicators"].append("Maintenance mode")
        
        evolution_indicators["evolution_detected"] = evolution_indicators["evolution_type"] != "maintenance"
        evolution_indicators["confidence"] = min(1.0, len(evolution_indicators["indicators"]) * 0.33)
        
        return evolution_indicators
    
    def _analyze_trends(self, pattern_discovery: dict, gap_analysis: dict) -> Dict:
        """Analyze trends over time"""
        # For now, return basic trend analysis based on current patterns
        trends = {
            "complexity_trend": "stable",
            "skill_coverage_trend": "improving",
            "resource_availability_trend": "stable",
            "confidence": 0.0
        }
        
        # Analyze complexity trend based on gap analysis
        skill_gap = gap_analysis["gap_analysis"]["skill_match"]
        if skill_gap["found"]:
            trends["complexity_trend"] = "increasing"
        
        # Analyze skill coverage trend
        knowledge_gap = gap_analysis["gap_analysis"]["knowledge_coverage"]
        if knowledge_gap["found"]:
            trends["skill_coverage_trend"] = "needs_improvement"
        
        # Calculate confidence
        trends["confidence"] = (skill_gap.get("found", False) + 
                               knowledge_gap.get("found", False)) / 2.0
        
        return trends
    
    def _generate_evolution_recommendations(self, evolution_result: dict) -> List[Dict]:
        """Generate recommendations based on evolution analysis"""
        recommendations = []
        
        evolution_type = evolution_result["evolution_patterns"]["evolution_type"]
        
        if evolution_type == "expansion":
            recommendations.extend([
                {
                    "type": "infrastructure_expansion",
                    "target": "scale_capabilities",
                    "priority": "high",
                    "description": "Expand technical infrastructure to support new requirements"
                },
                {
                    "type": "team_growth",
                    "target": "personnel_expansion",
                    "priority": "medium",
                    "description": "Consider team expansion to handle increased workload"
                }
            ])
        
        elif evolution_type == "optimization":
            recommendations.extend([
                {
                    "type": "performance_optimization",
                    "target": "efficiency_improvements",
                    "priority": "medium",
                    "description": "Optimize existing processes and workflows"
                },
                {
                    "type": "technology_upgrade",
                    "target": "tool_stack_upgrade",
                    "priority": "low",
                    "description": "Consider technology upgrades for better performance"
                }
            ])
        
        elif evolution_type == "team_evolution":
            recommendations.extend([
                {
                    "type": "skill_development",
                    "target": "team_competency_elevation",
                    "priority": "high",
                    "description": "Focus on team skill development and competency elevation"
                },
                {
                    "type": "role_redefinition",
                    "target": "clear_role_responsibilities",
                    "priority": "medium",
                    "description": "Redefine team roles and responsibilities"
                }
            ])
        
        elif evolution_type == "maintenance":
            recommendations.extend([
                {
                    "type": "process_standardization",
                    "target": "workflow_standardization",
                    "priority": "low",
                    "description": "Standardize and document existing processes"
                },
                {
                    "type": "quality_assurance",
                    "target": "maintain_quality_standards",
                    "priority": "medium",
                    "description": "Maintain and improve quality standards"
                }
            ])
        
        return recommendations

# Standalone execution functions
def discover_patterns_for_routine(routine_name: str) -> Dict:
    """Discover patterns for a specific routine"""
    discovery = AutoDiscoverySystem()
    return discovery.discover_patterns(routine_name)

def analyze_gaps_for_routine(routine_name: str) -> Dict:
    """Analyze gaps for a specific routine"""
    discovery = AutoDiscoverySystem()
    return discovery.analyze_gaps(routine_name)

def detect_evolution_for_routine(routine_name: str) -> Dict:
    """Detect evolution patterns for a specific routine"""
    discovery = AutoDiscoverySystem()
    return discovery.detect_evolution_patterns(routine_name)

if __name__ == "__main__":
    print("Auto-Discovery System - Phase 3 Implementation")
    print("=" * 50)
    
    # Example usage
    discovery = AutoDiscoverySystem()
    
    print("1. Pattern Discovery:")
    patterns = discovery.discover_patterns("daily-maintenance")
    print(f"   Patterns found: {len(patterns['discovered_patterns'])}")
    
    print("\n2. Gap Analysis:")
    gaps = discovery.analyze_gaps("daily-maintenance")
    print(f"   Priority gaps: {len(gaps['priority_gaps'])}")
    
    print("\n3. Evolution Detection:")
    evolution = discovery.detect_evolution_patterns("daily-maintenance")
    print(f"   Evolution type: {evolution['evolution_patterns']['evolution_type']}")
    print(f"   Evolution confidence: {evolution['evolution_patterns']['confidence']:.2f}")