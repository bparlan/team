#!/usr/bin/env python3
"""
Behavioral-Based Team Generator for theteam Enhancement

This module generates optimal team compositions based on project analysis
and behavioral requirements.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import random

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
class TeamGenerator:
    """
    Generates behavioral-based team compositions for projects.
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.project_analyzer = ProjectAnalyzer(project_root)
        self.project_analysis = None
        self.generated_teams = []

    def analyze_and_generate_teams(self) -> Dict[str, Any]:
        """
        Perform project analysis and generate optimal team compositions.

        Returns:
            Dict containing generated teams and analysis.
        """
        # Perform comprehensive project analysis
        self.project_analysis = self.project_analyzer.analyze_project()

        # Generate teams based on analysis
        self.generated_teams = self._generate_teams_based_on_analysis()

        return {
            "project_analysis": self.project_analysis,
            "generated_teams": self.generated_teams,
            "team_recommendations": self._get_team_recommendations(),
            "behavioral_assessment": self._assess_behavioral_compatibility(),
            "generation_timestamp": datetime.now().isoformat()
        }

    def _generate_teams_based_on_analysis(self) -> List[Dict[str, Any]]:
        """
        Generate team compositions based on project analysis.
        """
        teams = []

        # Get team recommendations from project analysis
        team_recs = self.project_analysis.get("behavioral_recommendations", {})
        recommended_roles = team_recs.get("recommended_roles", [])
        behavioral_priorities = team_recs.get("behavioral_priorities", [])

        # Base team (current default)
        base_team = self._create_base_team()

        # Enhanced teams based on project needs
        enhanced_teams = []

        # Generate teams based on project complexity and characteristics
        complexity = self.project_analysis.get("code_complexity", {})
        doc_needs = self.project_analysis.get("documentation_needs", {})
        testing = self.project_analysis.get("testing_requirements", {})

        # Team generation strategies
        if complexity.get("structural_complexity", 0) > 0.7:
            # High complexity: Need analytical and methodical team
            enhanced_teams.extend(self._generate_analytical_team())
            enhanced_teams.extend(self._generate_documented_team())
        elif doc_needs.get("needs_enhanced_documentation", False):
            # Documentation-heavy: Need methodical and technical team
            enhanced_teams.extend(self._generate_documented_team())
            enhanced_teams.extend(self._generate_practical_team())
        elif testing.get("quality_assurance_level") == "advanced":
            # Advanced testing: Need analytical and adversarial team
            enhanced_teams.extend(self._generate_analytical_team())
            enhanced_teams.extend(self._generate_skeptical_team())
        elif complexity.get("structural_complexity", 0) > 0.3:
            # Medium complexity: Need balanced team
            enhanced_teams.extend(self._generate_balanced_team())
        else:
            # Low complexity: Need pragmatic team
            enhanced_teams.extend(self._generate_pragmatic_team())

        # Add project-specific recommendations
        project_type = self.project_analysis.get("project_type", {}).get("type", "unknown")
        if project_type == "web_application":
            enhanced_teams.extend(self._generate_web_application_team())
        elif project_type == "data_science":
            enhanced_teams.extend(self._generate_data_science_team())
        elif project_type == "devops":
            enhanced_teams.extend(self._generate_devops_team())

        # Combine all teams
        teams.extend([base_team])
        teams.extend(enhanced_teams)

        # Remove duplicates (same team composition)
        unique_teams = self._remove_duplicate_teams(teams)

        # Sort teams by suitability score
        unique_teams.sort(key=lambda x: x.get("suitability_score", 0), reverse=True)

        return unique_teams

    def _create_base_team(self) -> Dict[str, Any]:
        """
        Create the current base team (backward compatibility).
        """
        return {
            "team_id": "base_team",
            "name": "Core Team (Current Configuration)",
            "suitability_score": 0.8,
            "description": "Current default team configuration",
            "behavioral_completeness": 0.9,
            "team_members": [
                {
                    "id": "architect",
                    "role": "Systems Architect",
                    "behavioral_profile": {
                        "core_style": "technical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🧑‍💼",
                        "color": "#FF6B6B",
                        "style": "technical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                },
                {
                    "id": "pragmatist",
                    "role": "Delivery Pragmatist",
                    "behavioral_profile": {
                        "core_style": "direct",
                        "communication_approach": "quick",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "aggressive",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🚀",
                        "color": "#4ECDC4",
                        "style": "direct",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                },
                {
                    "id": "skeptic",
                    "role": "Adversarial Reviewer",
                    "behavioral_profile": {
                        "core_style": "analytical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "conservative",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "🔍",
                        "color": "#95E77E",
                        "style": "analytical",
                        "speech_pattern": "cautious",
                        "interaction_frequency": "as_needed"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.8,
                "communication_effectiveness": 0.8,
                "decision_speed": "medium",
                "conflict_resolution": "collaborative"
            },
            "project_fit": "good",
            "behavioral_coverage": 0.9,
            "recommendations": [
                "Maintain current team for baseline functionality",
                "Consider adding specialized roles based on project complexity",
                "Focus on enhancing existing behavioral traits rather than adding new members"
            ]
        }

    def _generate_analytical_team(self) -> List[Dict[str, Any]]:
        """
        Generate a team focused on analytical capabilities.
        """
        team = {
            "team_id": "analytical_team",
            "name": "Analytical Excellence Team",
            "suitability_score": 0.95,
            "description": "Optimized for complex, high-stakes projects requiring rigorous analysis",
            "behavioral_completeness": 0.95,
            "team_members": [
                {
                    "id": "lead_analyst",
                    "role": "Lead Analyst",
                    "behavioral_profile": {
                        "core_style": "analytical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🔬",
                        "color": "#FF6B6B",
                        "style": "analytical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                },
                {
                    "id": "technical_architect",
                    "role": "Technical Architect",
                    "behavioral_profile": {
                        "core_style": "technical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "conservative",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "🏗️",
                        "color": "#4ECDC4",
                        "style": "technical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "as_needed"
                    }
                },
                {
                    "id": "adversarial_reviewer",
                    "role": "Adversarial Reviewer",
                    "behavioral_profile": {
                        "core_style": "analytical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "conservative",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "🔍",
                        "color": "#95E77E",
                        "style": "analytical",
                        "speech_pattern": "cautious",
                        "interaction_frequency": "as_needed"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.9,
                "communication_effectiveness": 0.95,
                "decision_speed": "slow",
                "conflict_resolution": "direct"
            },
            "project_fit": "excellent",
            "behavioral_coverage": 0.95,
            "recommendations": [
                "Excellent for complex systems requiring rigorous analysis",
                "Ideal for security-critical applications",
                "May need additional pragmatic perspectives for rapid delivery"
            ]
        }

        return [team]

    def _generate_pragmatic_team(self) -> List[Dict[str, Any]]:
        """
        Generate a team focused on pragmatic, rapid delivery.
        """
        team = {
            "team_id": "pragmatic_team",
            "name": "Pragmatic Delivery Team",
            "suitability_score": 0.9,
            "description": "Optimized for rapid development and practical implementation",
            "behavioral_completeness": 0.85,
            "team_members": [
                {
                    "id": "delivery_lead",
                    "role": "Delivery Lead",
                    "behavioral_profile": {
                        "core_style": "direct",
                        "communication_approach": "quick",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "aggressive",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "⚡",
                        "color": "#FFD93D",
                        "style": "direct",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                },
                {
                    "id": "implementation_expert",
                    "role": "Implementation Expert",
                    "behavioral_profile": {
                        "core_style": "practical",
                        "communication_approach": "quick",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "low",
                        "risk_tolerance": "aggressive",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🔧",
                        "color": "#6BCF7F",
                        "style": "practical",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                },
                {
                    "id": "quality_assurance",
                    "role": "Quality Assurance",
                    "behavioral_profile": {
                        "core_style": "direct",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "✅",
                        "color": "#FF8B94",
                        "style": "direct",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.8,
                "communication_effectiveness": 0.9,
                "decision_speed": "fast",
                "conflict_resolution": "collaborative"
            },
            "project_fit": "excellent",
            "behavioral_coverage": 0.85,
            "recommendations": [
                "Perfect for rapid development and MVP delivery",
                "Ideal for startup environments and competitive markets",
                "May need additional analytical depth for complex systems"
            ]
        }

        return [team]

    def _generate_documented_team(self) -> List[Dict[str, Any]]:
        """
        Generate a team focused on documentation and methodical approaches.
        """
        team = {
            "team_id": "documented_team",
            "name": "Documentation & Methodical Team",
            "suitability_score": 0.85,
            "description": "Optimized for documentation-heavy projects requiring systematic approaches",
            "behavioral_completeness": 0.9,
            "team_members": [
                {
                    "id": "documentation_lead",
                    "role": "Documentation Lead",
                    "behavioral_profile": {
                        "core_style": "technical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "📚",
                        "color": "#6C5CE7",
                        "style": "technical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                },
                {
                    "id": "process_architect",
                    "role": "Process Architect",
                    "behavioral_profile": {
                        "core_style": "strategic",
                        "communication_approach": "methodical",
                        "decision_making_approach": "consensus_based",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🗺️",
                        "color": "#A8E6CF",
                        "style": "strategic",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "as_needed"
                    }
                },
                {
                    "id": "quality_controller",
                    "role": "Quality Controller",
                    "behavioral_profile": {
                        "core_style": "technical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "conservative",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "🔎",
                        "color": "#FF9F43",
                        "style": "technical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.8,
                "communication_effectiveness": 0.95,
                "decision_speed": "medium",
                "conflict_resolution": "diplomatic"
            },
            "project_fit": "excellent",
            "behavioral_coverage": 0.9,
            "recommendations": [
                "Ideal for documentation-heavy projects",
                "Perfect for compliance and regulatory environments",
                "Excellent for complex systems requiring thorough documentation"
            ]
        }

        return [team]

    def _generate_balanced_team(self) -> List[Dict[str, Any]]:
        """
        Generate a balanced team with mixed behavioral approaches.
        """
        team = {
            "team_id": "balanced_team",
            "name": "Balanced Team",
            "suitability_score": 0.88,
            "description": "Optimized for medium-complexity projects with balanced approach",
            "behavioral_completeness": 0.9,
            "team_members": [
                {
                    "id": "team_lead",
                    "role": "Team Lead",
                    "behavioral_profile": {
                        "core_style": "strategic",
                        "communication_approach": "methodical",
                        "decision_making_approach": "consensus_based",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "👑",
                        "color": "#FDCB6E",
                        "style": "strategic",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "as_needed"
                    }
                },
                {
                    "id": "implementer",
                    "role": "Implementer",
                    "behavioral_profile": {
                        "core_style": "practical",
                        "communication_approach": "quick",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🛠️",
                        "color": "#95A5A6",
                        "style": "practical",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                },
                {
                    "id": "reviewer",
                    "role": "Reviewer",
                    "behavioral_profile": {
                        "core_style": "analytical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "📋",
                        "color": "#E74C3C",
                        "style": "analytical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.85,
                "communication_effectiveness": 0.9,
                "decision_speed": "medium",
                "conflict_resolution": "collaborative"
            },
            "project_fit": "good",
            "behavioral_coverage": 0.9,
            "recommendations": [
                "Suitable for medium-complexity projects",
                "Good balance of skills and approaches",
                "Can adapt to various project requirements"
            ]
        }

        return [team]

    def _generate_web_application_team(self) -> List[Dict[str, Any]]:
        """
        Generate a team optimized for web applications.
        """
        team = {
            "team_id": "web_app_team",
            "name": "Web Application Team",
            "suitability_score": 0.87,
            "description": "Optimized for web application development and deployment",
            "behavioral_completeness": 0.9,
            "team_members": [
                {
                    "id": "frontend_lead",
                    "role": "Frontend Lead",
                    "behavioral_profile": {
                        "core_style": "creative",
                        "communication_approach": "quick",
                        "decision_making_approach": "intuitive",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "aggressive",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🌐",
                        "color": "#FF7675",
                        "style": "creative",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                },
                {
                    "id": "backend_developer",
                    "role": "Backend Developer",
                    "behavioral_profile": {
                        "core_style": "technical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "⚙️",
                        "color": "#74B9FF",
                        "style": "technical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                },
                {
                    "id": "devops_engineer",
                    "role": "DevOps Engineer",
                    "behavioral_profile": {
                        "core_style": "hands_on",
                        "communication_approach": "quick",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🚀",
                        "color": "#00B894",
                        "style": "hands_on",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.9,
                "communication_effectiveness": 0.9,
                "decision_speed": "medium",
                "conflict_resolution": "collaborative"
            },
            "project_fit": "good",
            "behavioral_coverage": 0.85,
            "recommendations": [
                "Perfect for web application development",
                "Good mix of frontend, backend, and DevOps expertise",
                "Can handle rapid iteration and deployment needs"
            ]
        }

        return [team]

    def _generate_data_science_team(self) -> List[Dict[str, Any]]:
        """
        Generate a team optimized for data science projects.
        """
        team = {
            "team_id": "data_science_team",
            "name": "Data Science Team",
            "suitability_score": 0.86,
            "description": "Optimized for data science and machine learning projects",
            "behavioral_completeness": 0.85,
            "team_members": [
                {
                    "id": "data_scientist",
                    "role": "Data Scientist",
                    "behavioral_profile": {
                        "core_style": "analytical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "📊",
                        "color": "#FDCB6E",
                        "style": "analytical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                },
                {
                    "id": "ml_engineer",
                    "role": "ML Engineer",
                    "behavioral_profile": {
                        "core_style": "creative",
                        "communication_approach": "quick",
                        "decision_making_approach": "intuitive",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "aggressive",
                        "detail_orientation": "medium",
                        "innovation_preference": "disruptive"
                    },
                    "personality": {
                        "emoji": "🤖",
                        "color": "#00CEC9",
                        "style": "creative",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                },
                {
                    "id": "data_engineer",
                    "role": "Data Engineer",
                    "behavioral_profile": {
                        "core_style": "practical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "🔧",
                        "color": "#636E72",
                        "style": "practical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.85,
                "communication_effectiveness": 0.9,
                "decision_speed": "medium",
                "conflict_resolution": "collaborative"
            },
            "project_fit": "good",
            "behavioral_coverage": 0.85,
            "recommendations": [
                "Ideal for data science and machine learning projects",
                "Good balance of analytical, creative, and practical skills",
                "Can handle complex data challenges and innovation"
            ]
        }

        return [team]

    def _generate_devops_team(self) -> List[Dict[str, Any]]:
        """
        Generate a team optimized for DevOps and infrastructure projects.
        """
        team = {
            "team_id": "devops_team",
            "name": "DevOps Excellence Team",
            "suitability_score": 0.85,
            "description": "Optimized for DevOps, infrastructure, and deployment projects",
            "behavioral_completeness": 0.9,
            "team_members": [
                {
                    "id": "devops_architect",
                    "role": "DevOps Architect",
                    "behavioral_profile": {
                        "core_style": "strategic",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🏗️",
                        "color": "#FF7675",
                        "style": "strategic",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "as_needed"
                    }
                },
                {
                    "id": "infrastructure_engineer",
                    "role": "Infrastructure Engineer",
                    "behavioral_profile": {
                        "core_style": "hands_on",
                        "communication_approach": "quick",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "🖥️",
                        "color": "#74B9FF",
                        "style": "hands_on",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                },
                {
                    "id": "security_specialist",
                    "role": "Security Specialist",
                    "behavioral_profile": {
                        "core_style": "analytical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "conservative",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "🔒",
                        "color": "#E74C3C",
                        "style": "analytical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.9,
                "communication_effectiveness": 0.95,
                "decision_speed": "slow",
                "conflict_resolution": "direct"
            },
            "project_fit": "excellent",
            "behavioral_coverage": 0.9,
            "recommendations": [
                "Perfect for DevOps and infrastructure projects",
                "Excellent for security and compliance requirements",
                "Can handle complex systems and scale operations"
            ]
        }

        return [team]

    def _generate_skeptical_team(self) -> List[Dict[str, Any]]:
        """
        Generate a team focused on adversarial review and risk assessment.
        """
        team = {
            "team_id": "skeptical_team",
            "name": "Adversarial Review Team",
            "suitability_score": 0.84,
            "description": "Optimized for security review, risk assessment, and adversarial testing",
            "behavioral_completeness": 0.85,
            "team_members": [
                {
                    "id": "security_reviewer",
                    "role": "Security Reviewer",
                    "behavioral_profile": {
                        "core_style": "analytical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "conservative",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "🛡️",
                        "color": "#E74C3C",
                        "style": "analytical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                },
                {
                    "id": "risk_assessor",
                    "role": "Risk Assessor",
                    "behavioral_profile": {
                        "core_style": "analytical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "conservative",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "⚠️",
                        "color": "#FDCB6E",
                        "style": "analytical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "as_needed"
                    }
                },
                {
                    "id": "compliance_auditor",
                    "role": "Compliance Auditor",
                    "behavioral_profile": {
                        "core_style": "analytical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "analytical",
                        "complexity_sensitivity": "high",
                        "risk_tolerance": "conservative",
                        "detail_orientation": "high",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "📜",
                        "color": "#A8E6CF",
                        "style": "analytical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.8,
                "communication_effectiveness": 0.9,
                "decision_speed": "slow",
                "conflict_resolution": "direct"
            },
            "project_fit": "good",
            "behavioral_coverage": 0.85,
            "recommendations": [
                "Ideal for security-critical applications",
                "Perfect for compliance and regulatory environments",
                "Excellent for risk assessment and adversarial testing"
            ]
        }

        return [team]

    def _generate_practical_team(self) -> List[Dict[str, Any]]:
        """
        Generate a team focused on practical implementation.
        """
        team = {
            "team_id": "practical_team",
            "name": "Practical Implementation Team",
            "suitability_score": 0.87,
            "description": "Optimized for practical implementation and results-focused development",
            "behavioral_completeness": 0.85,
            "team_members": [
                {
                    "id": "implementation_lead",
                    "role": "Implementation Lead",
                    "behavioral_profile": {
                        "core_style": "practical",
                        "communication_approach": "quick",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "low",
                        "risk_tolerance": "aggressive",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "⚡",
                        "color": "#FFA502",
                        "style": "practical",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                },
                {
                    "id": "operations_expert",
                    "role": "Operations Expert",
                    "behavioral_profile": {
                        "core_style": "practical",
                        "communication_approach": "quick",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "low",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "medium",
                        "innovation_preference": "traditional"
                    },
                    "personality": {
                        "emoji": "🔄",
                        "color": "#FDCB6E",
                        "style": "practical",
                        "speech_pattern": "quick",
                        "interaction_frequency": "high"
                    }
                },
                {
                    "id": "process_improver",
                    "role": "Process Improver",
                    "behavioral_profile": {
                        "core_style": "practical",
                        "communication_approach": "methodical",
                        "decision_making_approach": "autonomous",
                        "complexity_sensitivity": "medium",
                        "risk_tolerance": "moderate",
                        "detail_orientation": "medium",
                        "innovation_preference": "incremental"
                    },
                    "personality": {
                        "emoji": "🔄",
                        "color": "#A8E6CF",
                        "style": "practical",
                        "speech_pattern": "methodical",
                        "interaction_frequency": "balanced"
                    }
                }
            ],
            "team_dynamics": {
                "diversity_score": 0.8,
                "communication_effectiveness": 0.9,
                "decision_speed": "fast",
                "conflict_resolution": "collaborative"
            },
            "project_fit": "excellent",
            "behavioral_coverage": 0.85,
            "recommendations": [
                "Perfect for operational excellence",
                "Ideal for process improvement and optimization",
                "Excellent for rapid implementation and delivery"
            ]
        }

        return [team]

    def _remove_duplicate_teams(self, teams: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Remove duplicate teams based on member composition.
        """
        unique_teams = []
        seen_compositions = set()

        for team in teams:
            # Create a unique signature based on member roles and core styles
            team_signature = (
                tuple(sorted(member.get("role", "") for member in team["team_members"])),
                tuple(sorted(member.get("behavioral_profile", {}).get("core_style", "") 
                         for member in team["team_members"]))
            )
            if team_signature not in seen_compositions:
                seen_compositions.add(team_signature)
                unique_teams.append(team)

        return unique_teams

    def _get_team_recommendations(self) -> List[str]:
        """
        Get recommendations based on project analysis.
        """
        recommendations = []
        analysis = self.project_analysis

        if analysis.get("code_complexity", {}).get("structural_complexity", 0) > 0.7:
            recommendations.extend([
                "Use analytical team for high-complexity projects",
                "Consider documentation-heavy team for complex systems",
                "Add pragmatic perspective for rapid delivery"
            ])
        elif analysis.get("documentation_needs", {}).get("needs_enhanced_documentation", False):
            recommendations.extend([
                "Use documentation team for documentation-heavy projects",
                "Combine with analytical team for complex systems",
                "Add diplomatic team for stakeholder communication"
            ])
        elif analysis.get("testing_requirements", {}).get("quality_assurance_level") == "advanced":
            recommendations.extend([
                "Use adversarial team for advanced testing",
                "Combine with analytical team for comprehensive coverage",
                "Add pragmatic team for practical implementation"
            ])
        else:
            recommendations.extend([
                "Use balanced team for medium-complexity projects",
                "Maintain base team for baseline functionality",
                "Consider project-specific enhancements based on characteristics"
            ])

        return recommendations

    def _assess_behavioral_compatibility(self) -> Dict[str, Any]:
        """
        Assess behavioral compatibility of generated teams.
        """
        assessment = {
            "diversity_scores": [],
            "compatibility_ratings": [],
            "behavioral_coverage": 0.0,
            "synergy_potential": 0.0,
            "conflict_risk": 0.0
        }

        for team in self.generated_teams:
            # Calculate behavioral diversity score
            core_styles = set()
            for member in team["team_members"]:
                core_styles.add(member["behavioral_profile"]["core_style"])

            diversity_score = len(core_styles) / len(team["team_members"])
            assessment["diversity_scores"].append(diversity_score)

            # Calculate behavioral compatibility
            compatibility = self._calculate_team_compatibility(team)
            assessment["compatibility_ratings"].append(compatibility)

        # Calculate overall scores
        if assessment["diversity_scores"]:
            assessment["behavioral_coverage"] = (
                sum(assessment["diversity_scores"]) / len(assessment["diversity_scores"])
            )

        if assessment["compatibility_ratings"]:
            assessment["synergy_potential"] = (
                sum(assessment["compatibility_ratings"]) / len(assessment["compatibility_ratings"])
            )

        assessment["conflict_risk"] = 1.0 - assessment["synergy_potential"]

        return assessment

    def _calculate_team_compatibility(self, team: Dict[str, Any]) -> float:
        """
        Calculate compatibility score for a team.
        """
        members = team["team_members"]
        if len(members) < 2:
            return 0.0

        total_compatibility = 0
        compatibility_count = 0

        for i, member1 in enumerate(members):
            for j, member2 in enumerate(members):
                if i != j:
                    style1 = member1["behavioral_profile"]["core_style"]
                    style2 = member2["behavioral_profile"]["core_style"]

                    if style1 in BEHAVIORAL_COMPATIBILITY_MATRIX:
                        if style2 in BEHAVIORAL_COMPATIBILITY_MATRIX[style1]["compatible_with"]:
                            total_compatibility += 1
                        compatibility_count += 1

        return total_compatibility / max(compatibility_count, 1)

    def save_teams(self, output_path: str = "generated_teams.json"):
        """
        Save generated teams to a file.
        """
        team_data = {
            "project_analysis": self.project_analysis,
            "generated_teams": self.generated_teams,
            "team_recommendations": self._get_team_recommendations(),
            "behavioral_assessment": self._assess_behavioral_compatibility(),
            "generation_timestamp": datetime.now().isoformat()
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(team_data, f, indent=2, default=str)

    def __str__(self):
        return f"TeamGenerator(project_root='{self.project_root}')"