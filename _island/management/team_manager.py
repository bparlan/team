#!/usr/bin/env python3
"""
Team Management System for theteam Enhancement

This module provides comprehensive team management capabilities with
behavioral analysis and recommendations for team composition optimization.
"""

import json
import math
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from enum import Enum

# Import behavioral trait definitions
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
class ManagementAction(Enum):
    """Enumeration of management actions."""
    ADD_MEMBER = "add_member"
    EDIT_MEMBER = "edit_member"
    REMOVE_MEMBER = "remove_member"
    RECOMMEND_TEAM = "recommend_team"
    ASSESS_COMPATIBILITY = "assess_compatibility"
    OPTIMIZE_COMPOSITION = "optimize_composition"
    GENERATE_SUGGESTIONS = "generate_suggestions"
class TeamManager:
    """
    Comprehensive team management system with behavioral analysis and recommendations.
    """

    def __init__(self, project_root: str, config_path: str):
        self.project_root = Path(project_root)
        self.config_path = Path(config_path)
        self.project_analyzer = ProjectAnalyzer(project_root)
        self.team_generator = TeamGenerator(project_root)
        self.config = self._load_config()
        self.management_history = []

    def _load_config(self) -> Dict[str, Any]:
        """
        Load the current team configuration.
        """
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # Return default config if file doesn't exist
            return {
                "schema_version": 1,
                "project": {
                    "name": "",
                    "root": ".",
                    "description": "",
                    "stack": []
                },
                "team": [],
                "permitted_skills": [],
                "behavior": {},
                "output": {}
            }

    def save_config(self, config: Dict[str, Any]) -> None:
        """
        Save configuration to file.
        """
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)

    def perform_action(self, action: ManagementAction, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a management action with behavioral analysis.

        Args:
            action: Management action to perform
            parameters: Action-specific parameters

        Returns:
            Dict containing action results and analysis
        """
        result = {
            "action": action.value,
            "timestamp": datetime.now().isoformat(),
            "parameters": parameters,
            "results": {},
            "behavioral_analysis": {},
            "recommendations": [],
            "impact_assessment": {}
        }

        try:
            if action == ManagementAction.ADD_MEMBER:
                result["results"] = self._add_member(parameters)
            elif action == ManagementAction.EDIT_MEMBER:
                result["results"] = self._edit_member(parameters)
            elif action == ManagementAction.REMOVE_MEMBER:
                result["results"] = self._remove_member(parameters)
            elif action == ManagementAction.RECOMMEND_TEAM:
                result["results"] = self._recommend_team(parameters)
            elif action == ManagementAction.ASSESS_COMPATIBILITY:
                result["results"] = self._assess_compatibility(parameters)
            elif action == ManagementAction.OPTIMIZE_COMPOSITION:
                result["results"] = self._optimize_composition(parameters)
            elif action == ManagementAction.GENERATE_SUGGESTIONS:
                result["results"] = self._generate_suggestions(parameters)

            # Perform behavioral analysis for all actions
            result["behavioral_analysis"] = self._perform_behavioral_analysis(action, parameters, result["results"])
            result["recommendations"] = self._generate_management_recommendations(action, parameters, result["behavioral_analysis"])
            result["impact_assessment"] = self._assess_action_impact(action, parameters, result["results"])

        except Exception as e:
            result["error"] = str(e)

        # Log the action
        self.management_history.append(result)

        return result

    def _add_member(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Add a new member to the team with behavioral compatibility analysis.

        Args:
            parameters: Member details including role, expertise, and behavioral traits

        Returns:
            Dict with member addition results
        """
        member_id = parameters.get("member_id")
        member_details = parameters.get("member_details")

        if not member_id or not member_details:
            raise ValueError("member_id and member_details are required")

        # Check for existing member
        existing_members = [m for m in self.config.get("team", []) if m.get("id") == member_id]
        if existing_members:
            return {
                "status": "error",
                "message": f"Member with ID '{member_id}' already exists",
                "existing_member": existing_members[0]
            }

        # Enhance member details with behavioral traits
        enhanced_member = self._enhance_member_details(member_id, member_details)

        # Add to team
        if "team" not in self.config:
            self.config["team"] = []

        self.config["team"].append(enhanced_member)

        # Validate behavioral compatibility
        compatibility = self._assess_member_compatibility(enhanced_member, self.config["team"])

        return {
            "status": "success",
            "message": f"Member '{member_id}' added successfully",
            "member": enhanced_member,
            "compatibility": compatibility,
            "team_size": len(self.config["team"])
        }

    def _edit_member(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Edit an existing member with behavioral analysis.

        Args:
            parameters: Member details to update

        Returns:
            Dict with edit results
        """
        member_id = parameters.get("member_id")
        updates = parameters.get("updates", {})

        # Find existing member
        team_members = self.config.get("team", [])
        member_index = next((i for i, m in enumerate(team_members) if m.get("id") == member_id), None)

        if member_index is None:
            return {
                "status": "error",
                "message": f"Member with ID '{member_id}' not found"
            }

        # Get original member
        original_member = team_members[member_index].copy()

        # Apply updates
        team_members[member_index].update(updates)
        enhanced_member = self._enhance_member_details(member_id, team_members[member_index])

        # Update config
        self.config["team"][member_index] = enhanced_member

        # Assess behavioral impact
        compatibility_before = self._assess_team_behavioral_compatibility(original_member)
        compatibility_after = self._assess_member_compatibility(enhanced_member, self.config["team"])

        return {
            "status": "success",
            "message": f"Member '{member_id}' updated successfully",
            "member": enhanced_member,
            "compatibility": compatibility_after,
            "impact_assessment": {
                "before": compatibility_before,
                "after": compatibility_after,
                "improvement": compatibility_after - compatibility_before if compatibility_after > compatibility_before else 0
            }
        }

    def _remove_member(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove a member from the team with impact assessment.

        Args:
            parameters: Member ID to remove

        Returns:
            Dict with removal results
        """
        member_id = parameters.get("member_id")
        impact_analysis = parameters.get("impact_analysis", False)

        # Find member
        team_members = self.config.get("team", [])
        member = next((m for m in team_members if m.get("id") == member_id), None)

        if not member:
            return {
                "status": "error",
                "message": f"Member with ID '{member_id}' not found"
            }

        # Store member details for impact analysis
        member_to_remove = member.copy()

        # Remove member
        self.config["team"] = [m for m in team_members if m.get("id") != member_id]

        # Assess impact
        impact_assessment = {}
        if impact_analysis:
            impact_assessment = self._assess_team_composition_after_removal(member_to_remove)

        return {
            "status": "success",
            "message": f"Member '{member_id}' removed successfully",
            "removed_member": member_to_remove,
            "new_team_size": len(self.config["team"]),
            "impact_assessment": impact_assessment
        }

    def _recommend_team(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate team recommendations based on project analysis.

        Args:
            parameters: Recommendation parameters

        Returns:
            Dict with team recommendations
        """
        # Analyze project characteristics
        self.project_analyzer.analyze_project()
        project_analysis = self.project_analyzer.analysis_results

        # Generate team recommendations
        recommendations = self._generate_comprehensive_recommendations(project_analysis)

        return {
            "status": "success",
            "message": "Team recommendations generated",
            "project_analysis": project_analysis,
            "recommendations": recommendations,
            "generated_teams": self._generate_alternative_teams(project_analysis),
            "behavioral_scores": self._calculate_recommendation_scores(project_analysis)
        }

    def _assess_compatibility(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess behavioral compatibility of current team composition.

        Args:
            parameters: Compatibility assessment parameters

        Returns:
            Dict with compatibility assessment
        """
        team_members = self.config.get("team", [])

        if not team_members:
            return {
                "status": "error",
                "message": "No team members to assess"
            }

        # Perform comprehensive assessment
        diversity_analysis = self._analyze_behavioral_diversity(team_members)
        compatibility_matrix = self._analyze_member_compatibility(team_members)
        synergy_analysis = self._analyze_team_synergy(team_members)
        skill_gap_analysis = self._analyze_skill_gaps(team_members)

        overall_score = (diversity_analysis["score"] * 0.3 +
                        compatibility_matrix["score"] * 0.4 +
                        synergy_analysis["score"] * 0.2 +
                        skill_gap_analysis["score"] * 0.1)

        return {
            "status": "success",
            "message": "Compatibility assessment completed",
            "team_members": team_members,
            "diversity_analysis": diversity_analysis,
            "compatibility_matrix": compatibility_matrix,
            "synergy_analysis": synergy_analysis,
            "skill_gap_analysis": skill_gap_analysis,
            "overall_score": overall_score,
            "needs_attention": overall_score < 0.7
        }

    def _optimize_composition(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize team composition based on project requirements.

        Args:
            parameters: Optimization parameters

        Returns:
            Dict with optimization results
        """
        team_members = self.config.get("team", [])
        optimization_goal = parameters.get("optimization_goal", "balanced")
        target_complexity = parameters.get("target_complexity", 0.5)

        # Perform optimization
        optimization_result = self._perform_composition_optimization(
            team_members, optimization_goal, target_complexity
        )

        return {
            "status": "success",
            "message": "Team composition optimization completed",
            "current_team": team_members,
            "optimization_result": optimization_result,
            "recommendations": optimization_result.get("recommendations", []),
            "expected_improvements": optimization_result.get("improvements", {})
        }

    def _generate_suggestions(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate team member suggestions based on behavioral requirements.

        Args:
            parameters: Suggestion parameters

        Returns:
            Dict with team suggestions
        """
        team_members = self.config.get("team", [])
        suggestion_type = parameters.get("suggestion_type", "behavioral")
        project_analysis = self.project_analyzer.analyze_project()

        # Generate suggestions based on type
        if suggestion_type == "behavioral":
            suggestions = self._generate_behavioral_suggestions(team_members, project_analysis)
        elif suggestion_type == "skill_gap":
            suggestions = self._generate_skill_gap_suggestions(team_members, project_analysis)
        elif suggestion_type == "diversity":
            suggestions = self._generate_diversity_suggestions(team_members, project_analysis)
        else:
            suggestions = self._generate_general_suggestions(team_members, project_analysis)

        return {
            "status": "success",
            "message": "Team suggestions generated",
            "team_members": team_members,
            "suggestions": suggestions,
            "implementation_priority": self._prioritize_suggestions(suggestions),
            "estimated_impact": self._estimate_suggestion_impact(suggestions)
        }

    def _enhance_member_details(self, member_id: str, member_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enhance member details with behavioral traits and personality structure.
        """
        # Determine core style based on role
        role = member_details.get("role", "")
        core_style = self._infer_core_style_from_role(role)

        # Get personality traits
        personality = self._get_personality_traits(member_id, core_style)

        # Create enhanced member structure
        enhanced_member = {
            "id": member_id,
            "role": member_details.get("role", ""),
            "expertise": member_details.get("expertise", ""),
            "voice": member_details.get("voice", ""),
            "enabled": member_details.get("enabled", True),
            "behavioral_profile": {
                "core_style": core_style,
                "communication_approach": self._determine_communication_approach(member_id),
                "decision_making_approach": self._determine_decision_making_approach(member_id),
                "conflict_resolution_style": self._determine_conflict_resolution_style(member_id),
                "communication_preference": self._determine_communication_preference(member_id),
                "work_pacing": self._determine_work_pacing(member_id),
                "complexity_sensitivity": self._determine_complexity_sensitivity(member_id),
                "risk_tolerance": self._determine_risk_tolerance(member_id),
                "detail_orientation": self._determine_detail_orientation(member_id),
                "innovation_preference": self._determine_innovation_preference(member_id)
            },
            "personality": personality
        }

        return enhanced_member

    def _infer_core_style_from_role(self, role: str) -> str:
        """
        Infer core behavioral style from role description.
        """
        role = role.lower()

        if any(indicator in role for indicator in ["architect", "systems", "technical"]):
            return "technical"
        elif any(indicator in role for indicator in ["delivery", "pragmatist", "practical"]):
            return "direct"
        elif any(indicator in role for indicator in ["reviewer", "adversarial", "skeptical"]):
            return "analytical"
        elif any(indicator in role for indicator in ["creative", "innovator", "designer"]):
            return "creative"
        elif any(indicator in role for indicator in ["strategic", "leadership", "management"]):
            return "strategic"
        elif any(indicator in role for indicator in ["diplomatic", "relationship", "client"]):
            return "diplomatic"
        elif any(indicator in role for indicator in ["hands-on", "implementer", "builder"]):
            return "hands_on"
        elif any(indicator in role for indicator in ["team", "coordinator", "collaborator"]):
            return "strategic"
        else:
            # Default to technical for unknown roles
            return "technical"

    def _get_personality_traits(self, member_id: str, core_style: str) -> Dict[str, Any]:
        """
        Get personality traits for a member based on core style.
        """
        # Generate deterministic personality based on member_id and core style
        color_hash = sum(ord(c) for c in member_id) % 256
        color_code = f"#{color_hash:02x}{color_hash:02x}{color_hash:02x}"

        # Emoji based on core style
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

        emoji = emoji_map.get(core_style, "👤")

        # Generate greetings and closings based on style
        style_greetings = {
            "technical": f"Hello team! Let's architect this properly...",
            "direct": f"Alright team! Let's ship this FAST! 🚀",
            "analytical": f"Whoa whoa! Let's slow down and test this! 📋",
            "creative": f"Hey team! Let's brainstorm some innovative solutions! 💡",
            "strategic": f"Welcome team! Let's focus on our strategic objectives... 🎯",
            "diplomatic": f"Hello everyone! Let's find the best solution together... 🤝",
            "hands_on": f"Hey team! Let's get our hands dirty and build something great! 🛠️",
            "practical": f"Alright team! Let's focus on practical results! ⚡"
        }

        style_closings = {
            "technical": "🏗️ Architect signing off — think about those long-term implications",
            "direct": "✅ Pragmatist done — shipping first, perfect second",
            "analytical": "🤔 Skeptic signing off — ask again later!",
            "creative": "💡 Creative thinking complete — let's build on this! ✨",
            "strategic": "🎯 Strategic thinking complete — ready to execute! 🚀",
            "diplomatic": "🤝 Diplomat signing off — harmony achieved! � peace",
            "hands_on": "🔧 Hands-on work complete — ready for testing! ✅",
            "practical": "⚡ Practical solution delivered — time to ship! 🚀"
        }

        style_speech_patterns = {
            "technical": "methodical",
            "direct": "quick",
            "analytical": "cautious",
            "creative": "adaptive",
            "strategic": "methodical",
            "diplomatic": "cautious",
            "hands_on": "quick",
            "practical": "quick"
        }

        style_interaction_frequencies = {
            "technical": "balanced",
            "direct": "high",
            "analytical": "as_needed",
            "creative": "high",
            "strategic": "as_needed",
            "diplomatic": "as_needed",
            "hands_on": "high",
            "practical": "high"
        }

        return {
            "emoji": emoji,
            "color": color_code,
            "greeting": style_greetings.get(core_style, f"Hello team! Starting work on {member_id}..."),
            "closing": style_closings.get(core_style, f"✅ {member_id.title()} complete!"),
            "style": core_style,
            "speech_pattern": style_speech_patterns.get(core_style, "methodical"),
            "interaction_frequency": style_interaction_frequencies.get(core_style, "balanced")
        }

    def _determine_communication_approach(self, member_id: str) -> str:
        """
        Determine communication approach based on member characteristics.
        """
        approaches = ["methodical", "quick", "cautious", "diplomatic", "assertive"]
        index = sum(ord(c) for c in member_id) % len(approaches)
        return approaches[index]

    def _determine_decision_making_approach(self, member_id: str) -> str:
        """
        Determine decision-making approach based on member characteristics.
        """
        approaches = ["analytical", "intuitive", "consensus_based", "autonomous"]
        index = sum(ord(c) for c in member_id) % len(approaches)
        return approaches[index]

    def _determine_conflict_resolution_style(self, member_id: str) -> str:
        """
        Determine conflict resolution style based on member characteristics.
        """
        styles = ["direct", "diplomatic", "avoidant", "collaborative"]
        index = sum(ord(c) for c in member_id) % len(styles)
        return styles[index]

    def _determine_communication_preference(self, member_id: str) -> str:
        """
        Determine communication preference based on member characteristics.
        """
        preferences = ["formal", "casual", "detailed", "concise"]
        index = sum(ord(c) for c in member_id) % len(preferences)
        return preferences[index]

    def _determine_work_pacing(self, member_id: str) -> str:
        """
        Determine work pacing based on member characteristics.
        """
        paces = ["steady", "fast_paced", "methodical", "adaptive"]
        index = sum(ord(c) for c in member_id) % len(paces)
        return paces[index]

    def _determine_complexity_sensitivity(self, member_id: str) -> str:
        """
        Determine complexity sensitivity based on member characteristics.
        """
        sensitivities = ["low", "medium", "high"]
        index = sum(ord(c) for c in member_id) % len(sensitivities)
        return sensitivities[index]

    def _determine_risk_tolerance(self, member_id: str) -> str:
        """
        Determine risk tolerance based on member characteristics.
        """
        tolerances = ["conservative", "moderate", "aggressive"]
        index = sum(ord(c) for c in member_id) % len(tolerances)
        return tolerances[index]

    def _determine_detail_orientation(self, member_id: str) -> str:
        """
        Determine detail orientation based on member characteristics.
        """
        orientations = ["high", "medium", "low"]
        index = sum(ord(c) for c in member_id) % len(orientations)
        return orientations[index]

    def _determine_innovation_preference(self, member_id: str) -> str:
        """
        Determine innovation preference based on member characteristics.
        """
        preferences = ["traditional", "incremental", "disruptive"]
        index = sum(ord(c) for c in member_id) % len(preferences)
        return preferences[index]

    def _assess_member_compatibility(self, member: Dict[str, Any], team: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Assess compatibility of a member with the team.
        """
        if not team:
            return {
                "overall_score": 1.0,
                "diversity_impact": 1.0,
                "compatibility_impact": 1.0,
                "synergy_impact": 1.0
            }

        member_core_style = member.get("behavioral_profile", {}).get("core_style", "")

        # Calculate diversity impact
        core_styles = [m.get("behavioral_profile", {}).get("core_style", "") for m in team]
        unique_styles = set(core_styles)
        diversity_score = len(unique_styles) / len(team) if team else 0

        # Calculate compatibility impact
        compatibility_score = 0
        compatibility_count = 0

        for other_member in team:
            if other_member.get("id") == member.get("id"):
                continue

            other_core_style = other_member.get("behavioral_profile", {}).get("core_style", "")
            if other_core_style in BEHAVIORAL_COMPATIBILITY_MATRIX:
                if member_core_style in BEHAVIORAL_COMPATIBILITY_MATRIX[other_core_style]["compatible_with"]:
                    compatibility_score += 1
                compatibility_count += 1

        compatibility_impact = compatibility_score / max(compatibility_count, 1)

        # Calculate synergy impact (simplified)
        synergy_impact = (diversity_score * 0.6 + compatibility_impact * 0.4)

        overall_score = (diversity_score * 0.3 + compatibility_impact * 0.4 + synergy_impact * 0.3)

        return {
            "overall_score": overall_score,
            "diversity_impact": diversity_score,
            "compatibility_impact": compatibility_impact,
            "synergy_impact": synergy_impact,
            "compatibility_details": {
                "core_style": member_core_style,
                "compatible_styles": BEHAVIORAL_COMPATIBILITY_MATRIX.get(member_core_style, {}).get("compatible_with", []),
                "diversity_benefit": 1.0 - diversity_score
            }
        }

    def _assess_team_behavioral_compatibility(self, member: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess team compatibility after member addition/removal.
        """
        return self._assess_member_compatibility(member, self.config.get("team", []))

    def _assess_team_composition_after_removal(self, member: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess team composition impact after member removal.
        """
        other_members = [m for m in self.config.get("team", []) if m.get("id") != member.get("id")]

        if not other_members:
            return {
                "impact_level": "critical",
                "recommendations": ["Team too small - consider adding members"],
                "alternatives": []
            }

        # Assess remaining team
        current_compatibility = self._assess_member_compatibility(member, other_members)

        return {
            "impact_level": "critical" if current_compatibility["overall_score"] < 0.5 else "moderate",
            "current_team_compatibility": self._calculate_overall_team_compatibility(other_members),
            "recommendations": self._generate_removal_recommendations(member, other_members),
            "alternatives": self._generate_team_alternatives(member, other_members)
        }

    def _calculate_overall_team_compatibility(self, team_members: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate overall team compatibility.
        """
        if not team_members:
            return {
                "overall_score": 0.0,
                "diversity_score": 0.0,
                "compatibility_score": 0.0
            }

        diversity_score = len(set(m.get("behavioral_profile", {}).get("core_style", "") 
                                for m in team_members)) / len(team_members)

        # Calculate pairwise compatibility
        total_compatibility = 0
        compatibility_count = 0

        for i, member1 in enumerate(team_members):
            for j, member2 in enumerate(team_members):
                if i != j:
                    style1 = member1.get("behavioral_profile", {}).get("core_style", "")
                    style2 = member2.get("behavioral_profile", {}).get("core_style", "")

                    if style1 in BEHAVIORAL_COMPATIBILITY_MATRIX:
                        if style2 in BEHAVIORAL_COMPATIBILITY_MATRIX[style1]["compatible_with"]:
                            total_compatibility += 1
                        compatibility_count += 1

        compatibility_score = total_compatibility / max(compatibility_count, 1)
        overall_score = (diversity_score * 0.4 + compatibility_score * 0.6)

        return {
            "overall_score": overall_score,
            "diversity_score": diversity_score,
            "compatibility_score": compatibility_score
        }

    def _analyze_behavioral_diversity(self, team_members: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze behavioral diversity of team.
        """
        if not team_members:
            return {
                "score": 0.0,
                "diversity_breakdown": {},
                "coverage": 0.0,
                "imbalance": 0.0
            }

        # Count core styles
        core_styles = [m.get("behavioral_profile", {}).get("core_style", "") for m in team_members]
        style_counts = {}
        for style in core_styles:
            style_counts[style] = style_counts.get(style, 0) + 1

        # Calculate diversity score (entropy-based)
        total_members = len(team_members)
        diversity_score = 0
        for count in style_counts.values():
            proportion = count / total_members
            diversity_score -= proportion * math.log2(proportion) if proportion > 0 else 0

        # Normalize to 0-1
        max_diversity = math.log2(len(style_counts)) if style_counts else 0
        diversity_score = diversity_score / max_diversity if max_diversity > 0 else 0

        # Calculate coverage (percentage of essential traits)
        essential_styles = {"technical", "direct", "analytical"}
        covered_styles = set(core_styles)
        coverage = len(essential_styles & covered_styles) / len(essential_styles)

        # Calculate imbalance (concentration of styles)
        imbalance = max(style_counts.values()) / total_members if total_members > 0 else 0

        return {
            "score": diversity_score,
            "diversity_breakdown": style_counts,
            "coverage": coverage,
            "imbalance": imbalance,
            "number_of_styles": len(style_counts),
            "unique_styles": list(style_counts.keys())
        }

    def _analyze_member_compatibility(self, team_members: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze compatibility between team members.
        """
        compatibility_matrix = {}
        overall_compatibility = 0
        total_pairs = 0

        for i, member1 in enumerate(team_members):
            member1_id = member1.get("id", "")
            member1_style = member1.get("behavioral_profile", {}).get("core_style", "")

            compatibility_matrix[member1_id] = {}

            for j, member2 in enumerate(team_members):
                if i == j:
                    continue

                member2_id = member2.get("id", "")
                member2_style = member2.get("behavioral_profile", {}).get("core_style", "")

                if member1_style in BEHAVIORAL_COMPATIBILITY_MATRIX:
                    is_compatible = member2_style in BEHAVIORAL_COMPATIBILITY_MATRIX[member1_style]["compatible_with"]
                    compatibility_matrix[member1_id][member2_id] = is_compatible

                    if is_compatible:
                        overall_compatibility += 1
                    total_pairs += 1

        overall_compatibility_score = overall_compatibility / max(total_pairs, 1)

        return {
            "matrix": compatibility_matrix,
            "score": overall_compatibility_score,
            "total_pairs": total_pairs,
            "compatible_pairs": overall_compatibility
        }

    def _analyze_team_synergy(self, team_members: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze team synergy and collaboration potential.
        """
        synergy_factors = {
            "communication_effectiveness": 0.0,
            "conflict_resolution_capacity": 0.0,
            "decision_making_efficiency": 0.0,
            "innovation_potential": 0.0,
            "adaptability": 0.0
        }

        for member in team_members:
            profile = member.get("behavioral_profile", {})
            style = profile.get("core_style", "")

            # Adjust synergy factors based on behavioral traits
            if style == "technical":
                synergy_factors["communication_effectiveness"] += 0.2
                synergy_factors["decision_making_efficiency"] += 0.2
            elif style == "direct":
                synergy_factors["communication_effectiveness"] += 0.1
                synergy_factors["decision_making_efficiency"] += 0.3
                synergy_factors["conflict_resolution_capacity"] += 0.1
            elif style == "analytical":
                synergy_factors["innovation_potential"] += 0.3
                synergy_factors["adaptability"] += 0.2
                synergy_factors["conflict_resolution_capacity"] += 0.1

        # Normalize scores
        for factor in synergy_factors:
            synergy_factors[factor] = min(1.0, synergy_factors[factor])

        # Calculate overall synergy score
        overall_synergy = sum(synergy_factors.values()) / len(synergy_factors)

        return {
            "synergy_factors": synergy_factors,
            "score": overall_synergy,
            "strongest_areas": [k for k, v in synergy_factors.items() if v > 0.7],
            "improvement_areas": [k for k, v in synergy_factors.items() if v < 0.5]
        }

    def _analyze_skill_gaps(self, team_members: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze skill gaps in the team.
        """
        # Define essential skill areas based on behavioral traits
        essential_skill_areas = {
            "technical": ["Architecture", "System design", "Code review"],
            "direct": ["Project management", "Communication", "Decision making"],
            "analytical": ["Quality assurance", "Risk assessment", "Research"],
            "creative": ["Innovation", "UX design", "Problem solving"],
            "strategic": ["Planning", "Leadership", "Resource allocation"],
            "diplomatic": ["Client relations", "Team building", "Conflict resolution"],
            "hands_on": ["Implementation", "Troubleshooting", "Mentoring"],
            "practical": ["Operations", "Process improvement", "Execution"]
        }

        # Analyze team skill coverage
        team_skills = set()
        for member in team_members:
            team_skills.update(essential_skill_areas.get(
                member.get("behavioral_profile", {}).get("core_style", ""),
                []
            ))

        # Calculate coverage
        total_essential_skills = sum(len(skills) for skills in essential_skill_areas.values())
        coverage = len(team_skills) / total_essential_skills if total_essential_skills > 0 else 0

        # Identify gaps
        skill_gaps = []
        for skill_area, skills in essential_skill_areas.items():
            if skill_area not in team_skills:
                skill_gaps.extend(skills)

        # Assess urgency based on project complexity
        urgency = "low"
        if coverage < 0.5:
            urgency = "high"
        elif coverage < 0.7:
            urgency = "medium"

        return {
            "coverage": coverage,
            "skill_gaps": skill_gaps,
            "urgency": urgency,
            # set() of lists is unhashable — flatten the matching areas instead.
            "missing_skill_areas": sorted(
                {area for skills in essential_skill_areas.values()
                 if any(skill in skill_gaps for skill in skills)
                 for area in ([skills] if isinstance(skills, str) else skills)}
            ),
            "recommendations": self._generate_skill_gap_recommendations(skill_gaps)
        }

    def _generate_comprehensive_recommendations(self, project_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate comprehensive team recommendations.
        """
        recommendations = []

        # Analysis-based recommendations
        complexity = project_analysis.get("code_complexity", {})
        doc_needs = project_analysis.get("documentation_needs", {})
        testing = project_analysis.get("testing_requirements", {})
        project_type = project_analysis.get("project_type", {}).get("type", "unknown")

        if complexity.get("structural_complexity", 0) > 0.7:
            recommendations.extend([
                {
                    "priority": "high",
                    "recommendation": "Use analytical team for complex systems",
                    "rationale": "High structural complexity requires rigorous analysis and risk assessment",
                    "expected_improvement": "Reduce technical debt by 20-30%"
                },
                {
                    "priority": "medium",
                    "recommendation": "Add methodical team for documentation",
                    "rationale": "Complex systems need comprehensive documentation and knowledge transfer",
                    "expected_improvement": "Improve maintainability by 15-20%"
                }
            ])
        elif doc_needs.get("needs_enhanced_documentation", False):
            recommendations.extend([
                {
                    "priority": "high",
                    "recommendation": "Use documentation team for documentation-heavy projects",
                    "rationale": "Enhanced documentation requirements demand methodical communication",
                    "expected_improvement": "Improve onboarding efficiency by 30%"
                }
            ])
        elif testing.get("quality_assurance_level") == "advanced":
            recommendations.extend([
                {
                    "priority": "high",
                    "recommendation": "Use adversarial team for advanced testing",
                    "rationale": "Advanced QA requirements require rigorous adversarial testing",
                    "expected_improvement": "Improve test coverage by 25-30%"
                }
            ])
        else:
            recommendations.extend([
                {
                    "priority": "medium",
                    "recommendation": "Use balanced team for medium-complexity projects",
                    "rationale": "Balanced approach provides flexibility for various project needs",
                    "expected_improvement": "Improve team adaptability by 20%"
                }
            ])

        # Behavioral diversity recommendations
        diversity_score = self._calculate_current_diversity_score()
        if diversity_score < 0.7:
            recommendations.append({
                "priority": "high",
                "recommendation": "Enhance team diversity with additional behavioral styles",
                "rationale": "Low diversity may limit innovation and adaptability",
                "expected_improvement": "Improve innovation potential by 15-25%"
            })

        return recommendations

    def _calculate_current_diversity_score(self) -> float:
        """
        Calculate current team diversity score.
        """
        team_members = self.config.get("team", [])
        if not team_members:
            return 0.0

        core_styles = [m.get("behavioral_profile", {}).get("core_style", "") for m in team_members]
        unique_styles = set(core_styles)
        return len(unique_styles) / len(team_members)

    def _generate_removal_recommendations(self, member: Dict[str, Any], other_members: List[Dict[str, Any]]) -> List[str]:
        """
        Generate recommendations after team member removal.
        """
        recommendations = []
        member_style = member.get("behavioral_profile", {}).get("core_style", "")

        # Assess impact on diversity
        styles = [m.get("behavioral_profile", {}).get("core_style", "") for m in other_members]
        if styles and len(set(styles)) < 2:
            recommendations.append("Team now consists of similar behavioral styles - consider adding diverse perspective")

        # Assess impact on functionality
        if member_style == "technical":
            recommendations.append("Consider adding analytical or strategic perspective for balance")
        elif member_style == "analytical":
            recommendations.append("Add creative or practical perspective for innovation and implementation")
        elif member_style == "direct":
            recommendations.append("Add diplomatic or methodical team for relationship management")

        return recommendations

    def _generate_team_alternatives(self, member: Dict[str, Any], other_members: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generate team alternatives after member removal.
        """
        alternatives = []

        # Generate potential replacement candidates
        potential_replacements = self._generate_potential_team_members()

        for replacement in potential_replacements:
            # Check compatibility with existing team
            compatibility = self._assess_member_compatibility(replacement, other_members)
            if compatibility["overall_score"] > 0.7:
                alternatives.append({
                    "member": replacement,
                    "compatibility_score": compatibility["overall_score"],
                    "reason": self._get_replacement_reason(member, replacement)
                })

        # Sort by compatibility score
        alternatives.sort(key=lambda x: x["compatibility_score"], reverse=True)

        return alternatives

    def _generate_potential_team_members(self) -> List[Dict[str, Any]]:
        """
        Generate potential team members based on behavioral templates.
        """
        templates = [
            "technical_architect",
            "delivery_pragmatist",
            "adversarial_reviewer",
            "creative_innovator",
            "strategic_leader"
        ]

        potential_members = []

        for template_id in templates:
            if template_id in TEAM_ROLE_TEMPLATES:
                template = TEAM_ROLE_TEMPLATES[template_id]

                # Generate a unique member based on template
                member = {
                    "id": f"temp_{template_id}_{hash(template_id) % 10000}",
                    "role": self._get_role_from_template(template_id),
                    "behavioral_profile": template.copy()
                }

                potential_members.append(member)

        return potential_members

    def _get_role_from_template(self, template_id: str) -> str:
        """
        Get role name from template ID.
        """
        role_mapping = {
            "technical_architect": "Technical Architect",
            "delivery_pragmatist": "Delivery Pragmatist",
            "adversarial_reviewer": "Adversarial Reviewer",
            "creative_innovator": "Creative Innovator",
            "strategic_leader": "Strategic Leader"
        }
        return role_mapping.get(template_id, "Team Member")

    def _get_replacement_reason(self, removed_member: Dict[str, Any], replacement: Dict[str, Any]) -> str:
        """
        Get reason for team member replacement.
        """
        removed_style = removed_member.get("behavioral_profile", {}).get("core_style", "")
        replacement_style = replacement.get("behavioral_profile", {}).get("core_style", "")

        if removed_style == replacement_style:
            return "Same behavioral style - maintains consistency"
        elif replacement_style in BEHAVIORAL_COMPATIBILITY_MATRIX.get(removed_style, {}).get("compatible_with", []):
            return "Complementary behavioral style - improves diversity"
        else:
            return "Different behavioral style - provides new perspective"

    def _perform_behavioral_analysis(self, action: ManagementAction, parameters: Dict[str, Any], 
                                   results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform behavioral analysis for management actions.
        """
        behavioral_analysis = {
            "action_impact": {},
            "behavioral_outcomes": {},
            "risk_assessment": {}
        }

        team_members = self.config.get("team", [])

        if action == ManagementAction.ADD_MEMBER:
            new_member = parameters.get("member_details", {})
            if new_member:
                enhanced_member = self._enhance_member_details(
                    new_member.get("member_id", ""), new_member
                )
                compatibility = self._assess_member_compatibility(enhanced_member, team_members)
                behavioral_analysis["action_impact"]["diversity_improvement"] = 1.0 if len(set([
                    m.get("behavioral_profile", {}).get("core_style", "")
                    for m in team_members
                ] + [enhanced_member.get("behavioral_profile", {}).get("core_style", "")])) > len(set(
                    m.get("behavioral_profile", {}).get("core_style", "")
                    for m in team_members
                )) else 0

        elif action == ManagementAction.REMOVE_MEMBER:
            removed_member = parameters.get("member_details", {})
            if removed_member:
                compatibility = self._assess_team_composition_after_removal(removed_member)
                behavioral_analysis["action_impact"]["diversity_reduction"] = compatibility.get("impact_level", "") == "critical"

        # Calculate overall behavioral outcomes
        behavioral_analysis["behavioral_outcomes"]["current_diversity"] = self._calculate_current_diversity_score()
        behavioral_analysis["behavioral_outcomes"]["team_compatibility"] = self._calculate_overall_team_compatibility(team_members).get("overall_score", 0.0)

        return behavioral_analysis

    def _generate_management_recommendations(self, action: ManagementAction, parameters: Dict[str, Any], 
                                           behavioral_analysis: Dict[str, Any]) -> List[str]:
        """
        Generate management recommendations based on action and analysis.
        """
        recommendations = []

        if action == ManagementAction.ADD_MEMBER:
            recommendations.extend([
                "Validate new member's behavioral fit with team",
                "Ensure new member complements existing team diversity",
                "Consider training and onboarding needs"
            ])

        elif action == ManagementAction.REMOVE_MEMBER:
            recommendations.extend([
                "Assess team functionality post-removal",
                "Plan for team gaps that may be created",
                "Consider temporary staffing if critical capabilities are lost"
            ])

        elif action == ManagementAction.RECOMMEND_TEAM:
            recommendations.extend([
                "Align team composition with project requirements",
                "Balance behavioral diversity with project needs",
                "Consider both short-term and long-term project goals"
            ])

        elif action == ManagementAction.ASSESS_COMPATIBILITY:
            recommendations.extend([
                "Monitor team compatibility over time",
                "Plan for team evolution and growth",
                "Develop conflict resolution strategies"
            ])

        return recommendations

    def _assess_action_impact(self, action: ManagementAction, parameters: Dict[str, Any], 
                            results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assess the impact of management actions.
        """
        impact = {
            "immediate_impact": {},
            "long_term_implications": {},
            "risk_level": "low",
            "recommendations": []
        }

        team_members = self.config.get("team", [])

        if action == ManagementAction.ADD_MEMBER:
            impact["immediate_impact"]["team_size_change"] = "increased"
            impact["long_term_implications"]["diversity_potential"] = "positive"
            impact["risk_level"] = "low"

        elif action == ManagementAction.REMOVE_MEMBER:
            impact["immediate_impact"]["team_size_change"] = "decreased"
            impact["long_term_implications"]["cohesion_risk"] = "moderate"
            impact["risk_level"] = "moderate"

        elif action == ManagementAction.ASSESS_COMPATIBILITY:
            compatibility_score = self._calculate_overall_team_compatibility(team_members).get("overall_score", 0.0)
            if compatibility_score < 0.5:
                impact["risk_level"] = "high"
            elif compatibility_score < 0.7:
                impact["risk_level"] = "moderate"
            else:
                impact["risk_level"] = "low"

        return impact

    def _generate_behavioral_suggestions(self, team_members: List[Dict[str, Any]], 
                                        project_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate behavioral suggestions for team improvement.
        """
        suggestions = []

        # Analyze current team
        diversity_analysis = self._analyze_behavioral_diversity(team_members)
        compatibility_matrix = self._analyze_member_compatibility(team_members)

        # Generate suggestions based on analysis
        if diversity_analysis["score"] < 0.7:
            suggestions.append({
                "type": "diversity",
                "priority": "high",
                "suggestion": "Add team members with underrepresented behavioral styles",
                "rationale": f"Current diversity score ({diversity_analysis['score']:.2f}) is below optimal level",
                "expected_benefit": "Improve innovation and adaptability by 15-25%"
            })

        if compatibility_matrix["score"] < 0.7:
            suggestions.append({
                "type": "compatibility",
                "priority": "medium",
                "suggestion": "Evaluate and improve member compatibility",
                "rationale": f"Current compatibility score ({compatibility_matrix['score']:.2f}) indicates potential conflicts",
                "expected_benefit": "Reduce conflict risk by 20-30%"
            })

        # Project-specific suggestions
        complexity = project_analysis.get("code_complexity", {})
        if complexity.get("structural_complexity", 0) > 0.7:
            suggestions.append({
                "type": "complexity",
                "priority": "high",
                "suggestion": "Add analytical team for complex systems",
                "rationale": "High structural complexity requires rigorous analysis",
                "expected_benefit": "Reduce technical debt by 20-30%"
            })

        return suggestions

    def _generate_skill_gap_suggestions(self, team_members: List[Dict[str, Any]], 
                                      project_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate skill gap suggestions for team improvement.
        """
        skill_gaps = self._analyze_skill_gaps(team_members)

        suggestions = []

        if skill_gaps["urgency"] == "high":
            for gap in skill_gaps["skill_gaps"]:
                suggestions.append({
                    "type": "skill_gap",
                    "priority": "high",
                    "suggestion": f"Add expertise in {gap}",
                    "rationale": f"Critical skill gap identified with {skill_gaps['coverage']:.2f} coverage",
                    "expected_benefit": "Close essential capability gap"
                })
        elif skill_gaps["urgency"] == "medium":
            for gap in skill_gaps["skill_gaps"][:3]:  # Limit to top 3
                suggestions.append({
                    "type": "skill_gap",
                    "priority": "medium",
                    "suggestion": f"Consider {gap} expertise",
                    "rationale": f"Skill gap of medium priority with {skill_gaps['coverage']:.2f} coverage",
                    "expected_benefit": "Improve overall capability"
                })

        return suggestions

    def _generate_diversity_suggestions(self, team_members: List[Dict[str, Any]], 
                                       project_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate diversity suggestions for team improvement.
        """
        diversity_analysis = self._analyze_behavioral_diversity(team_members)

        suggestions = []

        # Check for missing essential styles
        essential_styles = {"technical", "direct", "analytical"}
        current_styles = set(diversity_analysis["unique_styles"])
        missing_styles = essential_styles - current_styles

        for missing_style in missing_styles:
            suggestions.append({
                "type": "diversity",
                "priority": "high",
                "suggestion": f"Add member with {missing_style} behavioral style",
                "rationale": f"Missing essential behavioral style: {missing_style}",
                "expected_benefit": "Achieve comprehensive behavioral coverage"
            })

        # Check imbalance
        if diversity_analysis["imbalance"] > 0.7:
            suggestions.append({
                "type": "balance",
                "priority": "medium",
                "suggestion": "Rebalance team to reduce behavioral imbalance",
                "rationale": f"High imbalance detected: {diversity_analysis['imbalance']:.2f}",
                "expected_benefit": "Improve team flexibility and adaptability"
            })

        return suggestions

    def _generate_general_suggestions(self, team_members: List[Dict[str, Any]], 
                                     project_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate general team suggestions.
        """
        suggestions = []

        # Project type suggestions
        project_type = project_analysis.get("project_type", {}).get("type", "unknown")

        if project_type == "web_application":
            suggestions.append({
                "type": "specialization",
                "priority": "medium",
                "suggestion": "Consider web application specialization",
                "rationale": "Web applications require specific expertise and patterns",
                "expected_benefit": "Improve development efficiency by 15-20%"
            })

        # Complexity suggestions
        complexity = project_analysis.get("code_complexity", {})
        if complexity.get("structural_complexity", 0) > 0.5:
            suggestions.append({
                "type": "complexity_handling",
                "priority": "medium",
                "suggestion": "Implement structured approach to complexity management",
                "rationale": "Medium to high complexity requires systematic management",
                "expected_benefit": "Reduce complexity-related risks by 25%"
            })

        return suggestions

    def _prioritize_suggestions(self, suggestions: List[Dict[str, Any]]) -> List[str]:
        """
        Prioritize suggestions based on type and impact.
        """
        priority_order = ["diversity", "skill_gap", "complexity", "compatibility", "balance", "specialization"]

        # Sort suggestions by priority
        prioritized = sorted(suggestions, key=lambda x: (
            priority_order.index(x.get("type", "")) if x.get("type") in priority_order else 999,
            {"high": 0, "medium": 1, "low": 2}.get(x.get("priority", "low"), 3)
        ))

        return [s.get("suggestion", "") for s in prioritized]

    def _estimate_suggestion_impact(self, suggestions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Estimate impact of suggestions.
        """
        impact = {
            "overall_impact": 0.0,
            "confidence_level": 0.0,
            "implementation_timeline": "",
            "resource_requirements": {}
        }

        # Calculate overall impact
        if suggestions:
            total_impact = sum(
                float(s.get("expected_benefit", "0%").replace("%", "")) / 100
                for s in suggestions
            )
            impact["overall_impact"] = min(1.0, total_impact / len(suggestions))

        # Set confidence level based on suggestion type
        confidence_map = {
            "diversity": 0.8,
            "skill_gap": 0.9,
            "complexity": 0.7,
            "compatibility": 0.6,
            "balance": 0.8,
            "specialization": 0.5
        }

        confidence_sum = sum(
            confidence_map.get(s.get("type", ""), 0.5) * 
            ({"high": 1.0, "medium": 0.7, "low": 0.4}.get(s.get("priority", "low"), 0.5))
            for s in suggestions
        )

        impact["confidence_level"] = min(1.0, confidence_sum / max(len(suggestions), 1))

        # Estimate timeline
        if impact["confidence_level"] > 0.8:
            impact["implementation_timeline"] = "short_term"
        elif impact["confidence_level"] > 0.6:
            impact["implementation_timeline"] = "medium_term"
        else:
            impact["implementation_timeline"] = "long_term"

        # Resource requirements
        impact["resource_requirements"]["time"] = f"{len(suggestions) * 2-4} person-days"
        impact["resource_requirements"]["cost"] = "medium"
        impact["resource_requirements"]["expertise"] = "behavioral analysis"

        return impact

    def export_management_report(self) -> Dict[str, Any]:
        """
        Export comprehensive management report.
        """
        team_members = self.config.get("team", [])

        report = {
            "report_metadata": {
                "generated_at": datetime.now().isoformat(),
                "project_root": str(self.project_root),
                "config_path": str(self.config_path)
            },
            "current_team_state": {
                "team_size": len(team_members),
                "member_list": team_members,
                "behavioral_diversity": self._calculate_current_diversity_score(),
                "overall_compatibility": self._calculate_overall_team_compatibility(team_members).get("overall_score", 0.0)
            },
            "behavioral_analysis": self._analyze_behavioral_diversity(team_members),
            "management_history": self.management_history,
            "recommendations": self._generate_current_recommendations(),
            "performance_metrics": self._calculate_performance_metrics()
        }

        return report

    def _generate_current_recommendations(self) -> List[Dict[str, Any]]:
        """
        Generate current recommendations based on team state.
        """
        team_members = self.config.get("team", [])
        recommendations = []

        # Analyze current state
        diversity_analysis = self._analyze_behavioral_diversity(team_members)
        skill_gaps = self._analyze_skill_gaps(team_members)

        # Generate recommendations based on analysis
        if diversity_analysis["score"] < 0.7:
            recommendations.append({
                "priority": "high",
                "category": "diversity",
                "action": "Enhance team diversity",
                "description": "Add members with underrepresented behavioral styles",
                "expected_improvement": "20-30% improvement in innovation potential"
            })

        if skill_gaps["urgency"] == "high":
            recommendations.append({
                "priority": "high",
                "category": "skills",
                "action": "Address critical skill gaps",
                "description": "Fill essential skill areas missing from current team",
                "expected_improvement": "Close capability gaps"
            })

        # Add general recommendations
        recommendations.extend([
            {
                "priority": "medium",
                "category": "performance",
                "action": "Monitor team compatibility",
                "description": "Regularly assess and maintain team behavioral compatibility",
                "expected_improvement": "Sustain high team performance"
            },
            {
                "priority": "low",
                "category": "growth",
                "action": "Plan team evolution",
                "description": "Plan team growth and development for long-term success",
                "expected_improvement": "Ensure long-term team effectiveness"
            }
        ])

        return recommendations

    def _calculate_performance_metrics(self) -> Dict[str, Any]:
        """
        Calculate performance metrics for the team.
        """
        team_members = self.config.get("team", [])

        if not team_members:
            return {
                "performance_score": 0.0,
                "health_score": 0.0,
                "risk_score": 1.0,
                "recommendations": ["Team needs to be formed"]
            }

        diversity_score = self._calculate_current_diversity_score()
        compatibility_score = self._calculate_overall_team_compatibility(team_members).get("overall_score", 0.0)
        synergy_score = self._analyze_team_synergy(team_members).get("score", 0.0)
        skill_coverage = self._analyze_skill_gaps(team_members).get("coverage", 0.0)

        # Calculate overall performance score
        performance_score = (
            diversity_score * 0.25 +
            compatibility_score * 0.30 +
            synergy_score * 0.25 +
            skill_coverage * 0.20
        )

        # Calculate health score (inverse of risk)
        health_score = 1.0 - (
            0.4 * (1.0 - diversity_score) +
            0.3 * (1.0 - compatibility_score) +
            0.2 * (1.0 - synergy_score) +
            0.1 * (1.0 - skill_coverage)
        )

        # Calculate risk score (inverse of health)
        risk_score = 1.0 - health_score

        return {
            "performance_score": performance_score,
            "health_score": health_score,
            "risk_score": risk_score,
            "component_scores": {
                "diversity": diversity_score,
                "compatibility": compatibility_score,
                "synergy": synergy_score,
                "skill_coverage": skill_coverage
            },
            "health_indicators": {
                "behavioral_diversity": "good" if diversity_score > 0.7 else "needs_improvement",
                "team_compatibility": "good" if compatibility_score > 0.7 else "needs_improvement",
                "team_synergy": "good" if synergy_score > 0.7 else "needs_improvement",
                "skill_coverage": "good" if skill_coverage > 0.7 else "needs_improvement"
            },
            "recommendations": self._generate_performance_recommendations(performance_score, health_score)
        }

    def _generate_performance_recommendations(self, performance_score: float, health_score: float):
        """
        Generate performance recommendations based on scores.
        """
        recommendations = []

        if performance_score < 0.5:
            recommendations.extend([
                "Critical: Team needs significant improvement",
                "Consider complete team redesign based on project requirements",
                "Focus on addressing all identified skill gaps and behavioral issues"
            ])
        elif performance_score < 0.7:
            recommendations.extend([
                "Team performance needs improvement",
                "Focus on enhancing behavioral diversity",
                "Address skill gaps and compatibility issues"
            ])
        elif performance_score < 0.85:
            recommendations.extend([
                "Team performance is good but has room for improvement",
                "Consider targeted enhancements to optimize performance",
                "Monitor team dynamics and communication"
            ])
        else:
            recommendations.extend([
                "Team performance is excellent",
                "Maintain current team composition",
                "Focus on continuous improvement and growth"
            ])

        if health_score < 0.6:
            recommendations.append("Team health needs immediate attention - high risk of issues")
        elif health_score < 0.8:
            recommendations.append("Team health could be improved - moderate risk")

        return recommendations

    def __str__(self):
        return f"TeamManager(project_root='{self.project_root}', config_path='{self.config_path}')"