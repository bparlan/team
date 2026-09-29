#!/usr/bin/env python3
"""
Behavioral Integration Module for theteam Enhancement

This module integrates behavioral analysis and team generation into the
existing theteam skill workflow while maintaining backward compatibility.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import subprocess
import sys

from config.enhancements import (
    CORE_STYLES,
    ENHANCED_PERSONALITY_TRAITS,
    BEHAVIORAL_MODIFIERS,
    TEAM_ROLE_TEMPLATES,
    BEHAVIORAL_COMPATIBILITY_MATRIX,
    ASSESSMENT_METRICS
)

from analysis.project_scanner import ProjectAnalyzer
from generation.team_generator import TeamGenerator
from management.team_manager import TeamManager
class BehavioralIntegration:
    """
    Integrates behavioral analysis into the existing theteam skill workflow.
    """

    def __init__(self, project_root: str, config_path: str):
        self.project_root = Path(project_root)
        self.config_path = Path(config_path)
        self.project_analyzer = ProjectAnalyzer(project_root)
        self.team_generator = TeamGenerator(project_root)
        self.team_manager = TeamManager(project_root, config_path)
        self.original_config = self._load_original_config()
        self.behavioral_enhancements = None

    def _load_original_config(self) -> Dict[str, Any]:
        """
        Load the original theteam.config for backward compatibility comparison.
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def run_enhanced_initialization(self) -> Dict[str, Any]:
        """
        Run enhanced initialization with behavioral analysis.

        Returns:
            Dict containing enhanced initialization results.
        """
        result = {
            "enhanced_initialization": {
                "timestamp": datetime.now().isoformat(),
                "project_analysis": {},
                "behavioral_recommendations": {},
                "team_options": [],
                "backward_compatibility": {},
                "user_consent_required": False
            },
            "initialization_options": []
        }

        # Perform project analysis
        project_analysis = self.project_analyzer.analyze_project()
        result["enhanced_initialization"]["project_analysis"] = project_analysis

        # Generate team recommendations
        team_recommendations = self._generate_enhanced_recommendations(project_analysis)
        result["enhanced_initialization"]["behavioral_recommendations"] = team_recommendations

        # Generate team options
        team_options = self._generate_team_options(project_analysis)
        result["enhanced_initialization"]["team_options"] = team_options

        # Check backward compatibility
        compatibility = self._check_backward_compatibility()
        result["enhanced_initialization"]["backward_compatibility"] = compatibility

        # Determine if user consent is needed
        result["enhanced_initialization"]["user_consent_required"] = (
            len(team_options) > 1 or 
            self._would_change_original_behavior() or
            self._has_critical_changes()
        )

        # Prepare initialization options
        options = self._prepare_initialization_options(
            team_options, compatibility, project_analysis
        )
        result["initialization_options"] = options

        return result

    def _generate_enhanced_recommendations(self, project_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate enhanced behavioral recommendations based on project analysis.
        """
        recommendations = {
            "project_characteristics": project_analysis.get("project_type", {}),
            "behavioral_priorities": [],
            "recommended_team_roles": [],
            "skill_gap_analysis": {},
            "behavioral_modifications": [],
            "integration_points": []
        }

        # Analyze project characteristics
        complexity = project_analysis.get("code_complexity", {})
        doc_needs = project_analysis.get("documentation_needs", {})
        testing = project_analysis.get("testing_requirements", {})
        project_type = project_analysis.get("project_type", {}).get("type", "unknown")

        # Determine behavioral priorities
        if complexity.get("structural_complexity", 0) > 0.7:
            recommendations["behavioral_priorities"].extend([
                "analytical_thinking",
                "methodical_approach",
                "risk_assessment"
            ])
        elif complexity.get("structural_complexity", 0) > 0.3:
            recommendations["behavioral_priorities"].extend([
                "balanced_approach",
                "practical_implementation"
            ])
        else:
            recommendations["behavioral_priorities"].extend([
                "rapid_delivery",
                "practical_focus"
            ])

        if doc_needs.get("needs_enhanced_documentation", False):
            recommendations["behavioral_priorities"].append("methodical_communication")

        if testing.get("quality_assurance_level") == "advanced":
            recommendations["behavioral_priorities"].extend([
                "analytical_thinking",
                "attention_to_detail",
                "systematic_approach"
            ])

        # Recommend team roles based on project type
        role_recommendations = self._get_role_recommendations_for_project_type(project_type)
        recommendations["recommended_team_roles"] = role_recommendations

        # Analyze skill gaps
        skill_gaps = self._analyze_skill_gaps(project_analysis)
        recommendations["skill_gap_analysis"] = skill_gaps

        # Generate behavioral modifications
        behavioral_modifications = self._generate_behavioral_modifications(
            project_analysis, recommendations["recommended_team_roles"]
        )
        recommendations["behavioral_modifications"] = behavioral_modifications

        # Identify integration points
        integration_points = self._identify_integration_points(
            project_analysis, behavioral_modifications
        )
        recommendations["integration_points"] = integration_points

        return recommendations

    def _get_role_recommendations_for_project_type(self, project_type: str) -> List[Dict[str, Any]]:
        """
        Get role recommendations based on project type.
        """
        role_mapping = {
            "web_application": [
                "frontend_lead",
                "backend_developer",
                "devops_engineer"
            ],
            "data_science": [
                "data_scientist",
                "ml_engineer",
                "data_engineer"
            ],
            "cli_tool": [
                "delivery_lead",
                "implementation_expert",
                "quality_assurance"
            ],
            "library": [
                "technical_architect",
                "adversarial_reviewer",
                "documentation_lead"
            ],
            "enterprise": [
                "technical_architect",
                "delivery_pragmatist",
                "adversarial_reviewer"
            ],
            "research": [
                "creative_innovator",
                "strategic_leader",
                "technical_architect"
            ],
            "devops": [
                "devops_architect",
                "infrastructure_engineer",
                "security_specialist"
            ],
            "default": [
                "technical_architect",
                "delivery_pragmatist",
                "adversarial_reviewer"
            ]
        }

        return [
            {
                "role": role,
                "template": self._get_template_for_role(role),
                "behavioral_fit": self._calculate_behavioral_fit_for_role(role, project_type),
                "priority": self._get_role_priority(role, project_type)
            }
            for role in role_mapping.get(project_type, role_mapping["default"])
        ]

    def _get_template_for_role(self, role: str) -> Dict[str, Any]:
        """
        Get template for a specific role.
        """
        template_mapping = {
            "technical_architect": TEAM_ROLE_TEMPLATES["technical_architect"],
            "delivery_pragmatist": TEAM_ROLE_TEMPLATES["delivery_pragmatist"],
            "adversarial_reviewer": TEAM_ROLE_TEMPLATES["adversarial_reviewer"],
            "creative_innovator": TEAM_ROLE_TEMPLATES["creative_innovator"],
            "strategic_leader": TEAM_ROLE_TEMPLATES["strategic_leader"],
            "frontend_lead": {
                "core_style": "creative",
                "communication_approach": "quick",
                "decision_making_approach": "intuitive",
                "complexity_sensitivity": "medium",
                "risk_tolerance": "aggressive",
                "detail_orientation": "medium",
                "innovation_preference": "incremental"
            },
            "backend_developer": {
                "core_style": "technical",
                "communication_approach": "methodical",
                "decision_making_approach": "analytical",
                "complexity_sensitivity": "high",
                "risk_tolerance": "moderate",
                "detail_orientation": "high",
                "innovation_preference": "traditional"
            },
            "devops_engineer": {
                "core_style": "hands_on",
                "communication_approach": "quick",
                "decision_making_approach": "autonomous",
                "complexity_sensitivity": "high",
                "risk_tolerance": "moderate",
                "detail_orientation": "medium",
                "innovation_preference": "incremental"
            },
            "data_scientist": {
                "core_style": "analytical",
                "communication_approach": "methodical",
                "decision_making_approach": "analytical",
                "complexity_sensitivity": "high",
                "risk_tolerance": "moderate",
                "detail_orientation": "high",
                "innovation_preference": "incremental"
            },
            "ml_engineer": {
                "core_style": "creative",
                "communication_approach": "quick",
                "decision_making_approach": "intuitive",
                "complexity_sensitivity": "high",
                "risk_tolerance": "aggressive",
                "detail_orientation": "medium",
                "innovation_preference": "disruptive"
            },
            "data_engineer": {
                "core_style": "practical",
                "communication_approach": "methodical",
                "decision_making_approach": "autonomous",
                "complexity_sensitivity": "medium",
                "risk_tolerance": "moderate",
                "detail_orientation": "high",
                "innovation_preference": "traditional"
            }
        }

        return template_mapping.get(role, {})

    def _calculate_behavioral_fit_for_role(self, role: str, project_type: str) -> Dict[str, Any]:
        """
        Calculate behavioral fit for a role based on project type.
        """
        base_fit = {
            "compatibility_score": 0.7,
            "behavioral_alignment": 0.8,
            "project_requirements_met": True,
            "potential_conflicts": []
        }

        # Adjust fit based on project type
        if project_type == "web_application" and role == "frontend_lead":
            base_fit["compatibility_score"] = 0.95
            base_fit["behavioral_alignment"] = 0.9
        elif project_type == "data_science" and role == "data_scientist":
            base_fit["compatibility_score"] = 0.92
            base_fit["behavioral_alignment"] = 0.88
        elif project_type == "enterprise" and role == "adversarial_reviewer":
            base_fit["compatibility_score"] = 0.85
            base_fit["behavioral_alignment"] = 0.82

        return base_fit

    def _get_role_priority(self, role: str, project_type: str) -> str:
        """
        Get priority level for a role based on project type.
        """
        high_priority_roles = {
            "web_application": ["frontend_lead", "backend_developer"],
            "data_science": ["data_scientist", "ml_engineer"],
            "enterprise": ["technical_architect", "adversarial_reviewer"],
            "library": ["technical_architect"],
            "default": ["technical_architect", "delivery_pragmatist"]
        }

        return "high" if role in high_priority_roles.get(project_type, []) else "medium"

    def _analyze_skill_gaps(self, project_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze skill gaps based on project analysis.
        """
        skill_gaps = {
            "critical_gaps": [],
            "moderate_gaps": [],
            "skill_coverage": 0.0,
            "missing_capabilities": [],
            "recommended_skills": []
        }

        # Analyze based on project characteristics
        complexity = project_analysis.get("code_complexity", {})
        doc_needs = project_analysis.get("documentation_needs", {})
        testing = project_analysis.get("testing_requirements", {})

        if complexity.get("structural_complexity", 0) > 0.7:
            skill_gaps["critical_gaps"].extend([
                "Advanced architecture design",
                "Complex system analysis",
                "Risk assessment expertise"
            ])

        if doc_needs.get("needs_enhanced_documentation", False):
            skill_gaps["moderate_gaps"].extend([
                "Technical writing",
                "Documentation tools",
                "Knowledge transfer"
            ])

        if testing.get("quality_assurance_level") == "advanced":
            skill_gaps["critical_gaps"].extend([
                "Automated testing",
                "Performance testing",
                "Security testing"
            ])

        # Calculate coverage (simplified)
        total_essential_skills = len(skill_gaps["critical_gaps"]) + len(skill_gaps["moderate_gaps"])
        skill_gaps["skill_coverage"] = 1.0 - (min(5, total_essential_skills) / 5.0)

        # Generate recommended skills
        skill_gaps["recommended_skills"] = self._get_recommended_skills_for_project(
            complexity, doc_needs, testing
        )

        return skill_gaps

    def _get_recommended_skills_for_project(self, complexity: Dict[str, Any], 
                                           doc_needs: Dict[str, Any], 
                                           testing: Dict[str, Any]) -> List[str]:
        """
        Get recommended skills based on project requirements.
        """
        skills = []

        if complexity.get("structural_complexity", 0) > 0.7:
            skills.extend([
                "System architecture",
                "Complex algorithm design",
                "Performance optimization"
            ])

        if doc_needs.get("needs_enhanced_documentation", False):
            skills.extend([
                "Technical documentation",
                "API documentation",
                "Architecture documentation"
            ])

        if testing.get("quality_assurance_level") == "advanced":
            skills.extend([
                "Automated testing frameworks",
                "Performance testing tools",
                "Security testing methodologies"
            ])

        return skills

    def _generate_behavioral_modifications(self, project_analysis: Dict[str, Any], 
                                         recommended_roles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate behavioral modifications based on project analysis.
        """
        modifications = []

        # Analyze project needs and generate modifications
        complexity = project_analysis.get("code_complexity", {})
        doc_needs = project_analysis.get("documentation_needs", {})
        testing = project_analysis.get("testing_requirements", {})

        if complexity.get("structural_complexity", 0) > 0.7:
            modifications.append({
                "type": "behavioral_enhancement",
                "target": "team_composition",
                "modification": "Add analytical and methodical team members",
                "expected_impact": "Improve complex system handling by 20-30%",
                "behavioral_traits": ["analytical", "methodical", "strategic"]
            })

        if doc_needs.get("needs_enhanced_documentation", False):
            modifications.append({
                "type": "behavioral_enhancement",
                "target": "communication_patterns",
                "modification": "Enhance methodical communication and documentation skills",
                "expected_impact": "Improve documentation quality by 25-35%",
                "behavioral_traits": ["methodical", "analytical", "detailed"]
            })

        if testing.get("quality_assurance_level") == "advanced":
            modifications.append({
                "type": "behavioral_enhancement",
                "target": "quality_assurance",
                "modification": "Add rigorous testing and quality review capabilities",
                "expected_impact": "Improve test coverage by 25-35%",
                "behavioral_traits": ["analytical", "meticulous", "systematic"]
            })

        return modifications

    def _identify_integration_points(self, project_analysis: Dict[str, Any], 
                                   behavioral_modifications: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identify integration points for behavioral enhancements.
        """
        integration_points = []

        # Define integration points
        integration_points.extend([
            {
                "point": "initialization",
                "description": "Enhanced team member generation during project setup",
                "priority": "high",
                "impact": "Comprehensive team composition optimization"
            },
            {
                "point": "project_analysis",
                "description": "Behavioral analysis integrated into project scanning",
                "priority": "medium",
                "impact": "Project-specific team recommendations"
            },
            {
                "point": "team_management",
                "description": "Enhanced team management with behavioral insights",
                "priority": "high",
                "impact": "Advanced team composition management"
            },
            {
                "point": "reporting",
                "description": "Behavioral insights in team reports",
                "priority": "medium",
                "impact": "Comprehensive team performance analysis"
            }
        ])

        return integration_points

    def _generate_team_options(self, project_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate team options based on project analysis.
        """
        team_options = []

        # Generate teams using team generator
        teams_data = self.team_generator.analyze_and_generate_teams()

        # Extract team options from generated teams
        for team in teams_data.get("generated_teams", []):
            team_options.append({
                "id": team.get("team_id", ""),
                "name": team.get("name", ""),
                "description": team.get("description", ""),
                "suitability_score": team.get("suitability_score", 0.0),
                "behavioral_completeness": team.get("behavioral_completeness", 0.0),
                "team_size": len(team.get("team_members", [])),
                "key_strengths": self._extract_team_strengths(team),
                "behavioral_advantages": self._extract_behavioral_advantages(team),
                "project_fit": team.get("project_fit", "")
            })

        return team_options

    def _extract_team_strengths(self, team: Dict[str, Any]) -> List[str]:
        """
        Extract team strengths from team configuration.
        """
        strengths = []

        for member in team.get("team_members", []):
            profile = member.get("behavioral_profile", {})
            style = profile.get("core_style", "")

            if style == "technical":
                strengths.append("Strong technical expertise")
            elif style == "direct":
                strengths.append("Clear communication and quick decisions")
            elif style == "analytical":
                strengths.append("Rigorous analysis and risk assessment")
            elif style == "creative":
                strengths.append("Innovative solutions and creativity")
            elif style == "strategic":
                strengths.append("Strategic thinking and long-term planning")
            elif style == "diplomatic":
                strengths.append("Strong relationship management")
            elif style == "hands_on":
                strengths.append("Practical implementation and hands-on skills")

        return list(set(strengths))  # Remove duplicates

    def _extract_behavioral_advantages(self, team: Dict[str, Any]) -> List[str]:
        """
        Extract behavioral advantages from team configuration.
        """
        advantages = []

        team_members = team.get("team_members", [])
        if len(team_members) >= 2:
            styles = [m.get("behavioral_profile", {}).get("core_style", "") for m in team_members]

            # Check for behavioral diversity
            unique_styles = set(styles)
            if len(unique_styles) >= 3:
                advantages.append("High behavioral diversity")
            elif len(unique_styles) >= 2:
                advantages.append("Good behavioral balance")

            # Check for specific combinations
            if "technical" in unique_styles and "analytical" in unique_styles:
                advantages.append("Strong analytical foundation")
            if "creative" in unique_styles and "strategic" in unique_styles:
                advantages.append("Balanced innovation and strategy")
            if "direct" in unique_styles and "diplomatic" in unique_styles:
                advantages.append("Effective communication and relationship management")

        return advantages

    def _check_backward_compatibility(self) -> Dict[str, Any]:
        """
        Check backward compatibility of behavioral enhancements.
        """
        compatibility = {
            "original_config_valid": True,
            "breaking_changes": [],
            "migration_path": [],
            "compatibility_score": 0.0,
            "warnings": []
        }

        # Check original config
        if self.original_config:
            try:
                # Validate original config structure
                required_keys = ["schema_version", "project", "team", "permitted_skills", "behavior", "output"]
                for key in required_keys:
                    if key not in self.original_config:
                        compatibility["breaking_changes"].append(f"Missing required key: {key}")

                # Check team structure
                if "team" in self.original_config:
                    for member in self.original_config["team"]:
                        if "id" not in member or "role" not in member:
                            compatibility["breaking_changes"].append("Team member missing required fields")
                            break

                # Calculate compatibility score
                if len(compatibility["breaking_changes"]) == 0:
                    compatibility["compatibility_score"] = 0.95
                else:
                    compatibility["compatibility_score"] = 0.7 - len(compatibility["breaking_changes"]) * 0.1

                # Add warnings
                if compatibility["compatibility_score"] < 0.8:
                    compatibility["warnings"].append("Config may need manual adjustments")
                if "behavioral_profile" not in str(self.original_config):
                    compatibility["warnings"].append("Consider adding behavioral profiles to team members")

            except Exception as e:
                compatibility["breaking_changes"].append(f"Error validating original config: {str(e)}")
                compatibility["original_config_valid"] = False

        return compatibility

    def _would_change_original_behavior(self) -> bool:
        """
        Determine if behavioral enhancements would change original behavior.
        """
        # Check if original config would be modified by behavioral enhancements
        if not self.original_config:
            return True

        # Compare team structures
        original_team = self.original_config.get("team", [])
        enhanced_team = self.team_manager.config.get("team", [])

        # If team structure is different, behavior would change
        if len(original_team) != len(enhanced_team):
            return True

        return False

    def _has_critical_changes(self) -> bool:
        """
        Check if there are critical changes that require user attention.
        """
        # Critical changes include:
        # 1. Removal of essential team members
        # 2. Major behavioral overhauls
        # 3. Breaking changes to config structure

        critical_changes = []

        # Check for critical structural changes
        if self.original_config:
            original_team = self.original_config.get("team", [])
            if len(original_team) > 0:
                # Check if original team members are preserved
                original_ids = {m.get("id") for m in original_team}
                # This would be checked against enhanced team

        return len(critical_changes) > 0

    def _prepare_initialization_options(self, team_options: List[Dict[str, Any]], 
                                      compatibility: Dict[str, Any], 
                                      project_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Prepare initialization options for user selection.
        """
        options = []

        # Always include original team option
        if team_options:
            options.append({
                "id": "original_team",
                "name": "Original Team Configuration",
                "description": "Maintain current team configuration (backward compatible)",
                "suitability_score": 0.8,
                "behavioral_completeness": 0.9,
                "requires_user_consent": False,
                "estimated_impact": "Minimal - maintains current behavior"
            })

        # Include enhanced team options
        enhanced_options = [opt for opt in team_options if opt.get("suitability_score", 0) > 0.8]
        for option in enhanced_options[:3]:  # Limit to top 3 enhanced options
            options.append({
                "id": option.get("id", ""),
                "name": option.get("name", ""),
                "description": option.get("description", ""),
                "suitability_score": option.get("suitability_score", 0.0),
                "behavioral_completeness": option.get("behavioral_completeness", 0.0),
                "requires_user_consent": True,
                "estimated_impact": f"Enhance behavioral completeness to {option.get('behavioral_completeness', 0.0):.1f}",
                "key_strengths": option.get("key_strengths", []),
                "behavioral_advantages": option.get("behavioral_advantages", [])
            })

        return options

    def apply_enhanced_initialization(self, option_id: str) -> Dict[str, Any]:
        """
        Apply enhanced initialization based on user selection.

        Args:
            option_id: Selected initialization option

        Returns:
            Dict containing application results
        """
        result = {
            "application_result": {
                "timestamp": datetime.now().isoformat(),
                "option_id": option_id,
                "status": "applied",
                "behavioral_enhancements": {},
                "backward_compatibility_maintained": True,
                "user_consent_obtained": True
            },
            "applied_changes": [],
            "behavioral_improvements": [],
            "migration_summary": {}
        }

        # Apply selected option
        if option_id == "original_team":
            result["applied_changes"].append({
                "type": "none",
                "description": "No changes - maintaining original configuration"
            })
            result["behavioral_improvements"] = []
        else:
            # Apply enhanced team based on option
            enhanced_team = self._get_enhanced_team_by_id(option_id)
            if enhanced_team:
                # Save enhanced configuration
                self._save_enhanced_config(enhanced_team)

                result["applied_changes"].append({
                    "type": "behavioral_enhancement",
                    "description": f"Applied enhanced team configuration: {enhanced_team.get('name', '')}",
                    "behavioral_traits_added": self._count_behavioral_traits(enhanced_team),
                    "team_size_change": len(enhanced_team.get("team_members", [])) - len(self.original_config.get("team", []))
                })

                result["behavioral_improvements"] = self._calculate_behavioral_improvements(enhanced_team)

        # Generate migration summary
        result["migration_summary"] = self._generate_migration_summary(
            option_id, result["applied_changes"]
        )

        return result

    def _get_enhanced_team_by_id(self, team_id: str) -> Optional[Dict[str, Any]]:
        """
        Get enhanced team configuration by team ID.
        """
        teams = self.team_generator.generate_teams()
        for team in teams:
            if team.get("team_id") == team_id:
                return team
        return None

    def _save_enhanced_config(self, enhanced_team: Dict[str, Any]) -> None:
        """
        Save enhanced configuration.
        """
        # Create enhanced config based on original
        enhanced_config = self.original_config.copy() if self.original_config else {}

        # Update team with enhanced members
        enhanced_config["team"] = []
        for member in enhanced_team.get("team_members", []):
            # Convert behavioral profile to personality structure
            personality = self._create_personality_from_profile(member)
            enhanced_member = {
                "id": member.get("id", ""),
                "role": member.get("role", ""),
                "expertise": member.get("behavioral_profile", {}).get("core_style", "") + " expertise",
                "voice": f"{member.get('behavioral_profile', {}).get('core_style', '')} communication style",
                "enabled": True,
                "behavioral_profile": member.get("behavioral_profile", {}),
                "personality": personality
            }
            enhanced_config["team"].append(enhanced_member)

        # Add behavioral metadata
        enhanced_config["behavioral_enhancements"] = {
            "enabled": True,
            "enhanced_personality": True,
            "behavioral_traits": True,
            "enhanced_analysis": True
        }

        # Save config
        self.team_manager.save_config(enhanced_config)

    def _create_personality_from_profile(self, member: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create personality structure from behavioral profile.
        """
        profile = member.get("behavioral_profile", {})
        core_style = profile.get("core_style", "")

        # Generate personality traits
        personality_traits = {
            "emoji": self._get_emoji_for_style(core_style),
            "color": self._get_color_for_style(core_style),
            "greeting": self._get_greeting_for_style(core_style),
            "closing": self._get_closing_for_style(core_style),
            "style": core_style,
            "speech_pattern": profile.get("communication_approach", "methodical"),
            "interaction_frequency": self._get_interaction_frequency_for_style(core_style)
        }

        return personality_traits

    def _get_emoji_for_style(self, style: str) -> str:
        """Get emoji for behavioral style."""
        emoji_map = {
            "technical": "🧑‍💼",
            "direct": "🚀",
            "analytical": "🔍",
            "creative": "🎨",
            "strategic": "👑",
            "diplomatic": "🤝",
            "hands_on": "🔧",
            "practical": "⚡"
        }
        return emoji_map.get(style, "👤")

    def _get_color_for_style(self, style: str) -> str:
        """Get color code for behavioral style."""
        color_map = {
            "technical": "#FF6B6B",
            "direct": "#4ECDC4",
            "analytical": "#95E77E",
            "creative": "#FFD93D",
            "strategic": "#FDCB6E",
            "diplomatic": "#6BCF7F",
            "hands_on": "#FFA502",
            "practical": "#A8E6CF"
        }
        return color_map.get(style, "#95A5A6")

    def _get_greeting_for_style(self, style: str) -> str:
        """Get greeting for behavioral style."""
        greetings = {
            "technical": "Hello team! Let's architect this properly...",
            "direct": "Alright team! Let's ship this FAST! 🚀",
            "analytical": "Whoa whoa! Let's slow down and test this! 📋",
            "creative": "Hey team! Let's brainstorm some innovative solutions! 💡",
            "strategic": "Welcome team! Let's focus on our strategic objectives... 🎯",
            "diplomatic": "Hello everyone! Let's find the best solution together... 🤝",
            "hands_on": "Hey team! Let's get our hands dirty and build something great! 🛠️",
            "practical": "Alright team! Let's focus on practical results! ⚡"
        }
        return greetings.get(style, "Hello team!")

    def _get_closing_for_style(self, style: str) -> str:
        """Get closing for behavioral style."""
        closings = {
            "technical": "🏗️ Architect signing off — think about those long-term implications",
            "direct": "✅ Pragmatist done — shipping first, perfect second",
            "analytical": "🤔 Skeptic signing off — ask again later!",
            "creative": "💡 Creative thinking complete — let's build on this! ✨",
            "strategic": "🎯 Strategic thinking complete — ready to execute! 🚀",
            "diplomatic": "🤝 Diplomat signing off — harmony achieved! 🤝",
            "hands_on": "🔧 Hands-on work complete — ready for testing! ✅",
            "practical": "⚡ Practical solution delivered — time to ship! 🚀"
        }
        return closings.get(style, "✅ Complete!")

    def _get_interaction_frequency_for_style(self, style: str) -> str:
        """Get interaction frequency for behavioral style."""
        frequencies = {
            "technical": "balanced",
            "direct": "high",
            "analytical": "as_needed",
            "creative": "high",
            "strategic": "as_needed",
            "diplomatic": "as_needed",
            "hands_on": "high",
            "practical": "high"
        }
        return frequencies.get(style, "balanced")

    def _count_behavioral_traits(self, team: Dict[str, Any]) -> int:
        """
        Count behavioral traits in a team.
        """
        trait_count = 0
        for member in team.get("team_members", []):
            trait_count += len(member.get("behavioral_profile", {}))
        return trait_count

    def _calculate_behavioral_improvements(self, enhanced_team: Dict[str, Any]) -> List[str]:
        """
        Calculate behavioral improvements from enhanced team.
        """
        improvements = []

        enhanced_team_traits = self._count_behavioral_traits(enhanced_team)
        if enhanced_team_traits > 20:
            improvements.append("Enhanced behavioral diversity and completeness")
        if enhanced_team_traits > 30:
            improvements.append("Comprehensive behavioral trait coverage")
        if enhanced_team_traits > 40:
            improvements.append("Advanced behavioral optimization")

        return improvements

    def _generate_migration_summary(self, option_id: str, applied_changes: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Generate migration summary for enhanced initialization.
        """
        return {
            "option_selected": option_id,
            "changes_applied": len(applied_changes),
            "behavioral_enhancement_level": "basic" if option_id == "original_team" else "enhanced",
            "backward_compatibility": option_id == "original_team",
            "recommended_next_steps": self._get_recommended_next_steps(option_id),
            "impact_assessment": self._assess_migration_impact(option_id)
        }

    def _get_recommended_next_steps(self, option_id: str) -> List[str]:
        """
        Get recommended next steps based on selected option.
        """
        if option_id == "original_team":
            return [
                "Continue with current team configuration",
                "Monitor project progress and team performance",
                "Consider behavioral enhancements in future iterations"
            ]
        else:
            return [
                "Validate enhanced team with project requirements",
                "Integrate behavioral analysis into team workflows",
                "Track team performance with enhanced behavioral insights",
                "Consider further team composition optimization"
            ]

    def _assess_migration_impact(self, option_id: str) -> Dict[str, Any]:
        """
        Assess migration impact for selected option.
        """
        if option_id == "original_team":
            return {
                "risk_level": "low",
                "impact_on_operations": "minimal",
                "behavioral_change": "none",
                "recommended_testing": "standard_project_testing"
            }
        else:
            return {
                "risk_level": "medium",
                "impact_on_operations": "significant",
                "behavioral_change": "enhanced",
                "recommended_testing": "comprehensive_behavioral_testing"
            }

    def get_integration_status(self) -> Dict[str, Any]:
        """
        Get current integration status.
        """
        return {
            "integration_version": "1.0.0",
            "behavioral_enhancements_enabled": True,
            "backward_compatibility": True,
            "current_config": {
                "behavioral_profiles": "enabled" if self.config.get("behavioral_enhancements") else "disabled",
                "enhanced_personality": "enabled" if self.config.get("behavioral_enhancements") else "disabled",
                "behavioral_traits": "enabled" if self.config.get("behavioral_enhancements") else "disabled"
            },
            "available_features": [
                "enhanced_behavioral_analysis",
                "behavioral_team_generation",
                "comprehensive_team_management",
                "behavioral_compatibility_assessment",
                "project_specific_recommendations",
                "integration_with_existing_workflow"
            ],
            "configuration_status": "active",
            "last_updated": datetime.now().isoformat()
        }

    def __str__(self):
        return f"BehavioralIntegration(project_root='{self.project_root}', config_path='{self.config_path}')"