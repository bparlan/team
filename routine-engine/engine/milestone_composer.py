#!/usr/bin/env python3
"""
Milestone-Aware Composer
Phase-aware team member assignments for different project milestones.
"""

import json
from typing import Dict, List, Any

class MilestoneComposer:
    def __init__(self):
        self.milestones = self._load_milestones()
    
    def _load_milestones(self) -> Dict:
        """Load milestone-based team compositions"""
        return {
            "initial_setup": {
                "name": "Initial Setup",
                "description": "Project initialization and architecture",
                "required_members": ["architect", "pragmatist"],
                "optional_members": ["skeptic"],
                "focus_areas": ["architecture", "planning", "setup"]
            },
            "security_setup": {
                "name": "Security Setup",
                "description": "Authentication, credentials, and security",
                "required_members": ["security", "architect"],
                "optional_members": ["skeptic"],
                "focus_areas": ["authentication", "credentials", "input_validation"]
            },
            "database_setup": {
                "name": "Database Setup",
                "description": "Schema design and migrations",
                "required_members": ["data", "architect"],
                "optional_members": ["pragmatist"],
                "focus_areas": ["schema_design", "migrations", "data_integrity"]
            },
            "ai_integration": {
                "name": "AI Integration",
                "description": "AI provider setup and model integration",
                "required_members": ["ai", "data"],
                "optional_members": ["skeptic", "security"],
                "focus_areas": ["model_selection", "provider_optimization", "cost_management"]
            },
            "browser_automation": {
                "name": "Browser Automation",
                "description": "Playwright setup and platform handlers",
                "required_members": ["browser", "architect"],
                "optional_members": ["ai", "workflow"],
                "focus_areas": ["playwright_profiles", "platform_selectors", "anti_detection"]
            },
            "pipeline_setup": {
                "name": "Pipeline Setup",
                "description": "SDD pipeline and specification workflow",
                "required_members": ["workflow", "architect"],
                "optional_members": ["pragmatist", "skeptic"],
                "focus_areas": ["specification", "milestone_management", "verification"]
            },
            "content_generation": {
                "name": "Content Generation",
                "description": "AI-powered content creation and rewriting",
                "required_members": ["ai", "workflow"],
                "optional_members": ["skeptic", "browser"],
                "focus_areas": ["content_rewriting", "ai_providers", "quality_control"]
            },
            "posting_execution": {
                "name": "Posting Execution",
                "description": "Multi-platform publishing and execution",
                "required_members": ["browser", "workflow"],
                "optional_members": ["ai", "security"],
                "focus_areas": ["platform_handlers", "execution_resilience", "error_handling"]
            },
            "maintenance_evolution": {
                "name": "Maintenance & Evolution",
                "description": "Ongoing maintenance and team evolution",
                "required_members": ["architect", "pragmatist"],
                "optional_members": ["skeptic", "workflow", "data", "security", "browser", "ai"],
                "focus_areas": ["maintenance", "evolution", "optimization"]
            }
        }
    
    def get_composition_for_milestone(self, milestone_name: str) -> Dict:
        """Get team composition for a specific milestone"""
        if milestone_name not in self.milestones:
            return {"error": f"Milestone {milestone_name} not found"}
        
        milestone = self.milestones[milestone_name]
        return {
            "milestone": milestone_name,
            "name": milestone["name"],
            "description": milestone["description"],
            "required_members": milestone["required_members"],
            "optional_members": milestone["optional_members"],
            "focus_areas": milestone["focus_areas"],
            "total_members": len(milestone["required_members"]) + len(milestone["optional_members"])
        }
    
    def get_all_milestones(self) -> List[Dict]:
        """Get all available milestones"""
        return [
            {
                "name": name,
                "description": data["description"],
                "required_members": data["required_members"],
                "optional_members": data["optional_members"],
                "focus_areas": data["focus_areas"]
            }
            for name, data in self.milestones.items()
        ]
    
    def optimize_composition(self, current_members: List[str], milestone: str) -> Dict:
        """Optimize team composition for a milestone"""
        milestone_data = self.get_composition_for_milestone(milestone)
        
        if "error" in milestone_data:
            return milestone_data
        
        required = milestone_data["required_members"]
        optional = milestone_data["optional_members"]
        
        # Check which required members are missing
        missing_required = [m for m in required if m not in current_members]
        missing_optional = [m for m in optional if m not in current_members]
        
        # Calculate optimization score
        coverage = len(required) - len(missing_required)
        optimization_score = coverage / len(required) if required else 1.0
        
        return {
            "milestone": milestone,
            "current_coverage": optimization_score,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "recommendations": self._generate_recommendations(missing_required, missing_optional)
        }
    
    def _generate_recommendations(self, missing_required: List[str], missing_optional: List[str]) -> List[str]:
        """Generate recommendations for missing members"""
        recommendations = []
        
        if missing_required:
            recommendations.append(f"Add required members: {', '.join(missing_required)}")
        
        if missing_optional:
            recommendations.append(f"Consider adding optional members: {', '.join(missing_optional)}")
        
        if not missing_required and not missing_optional:
            recommendations.append("Team composition is optimal for this milestone")
        
        return recommendations

if __name__ == "__main__":
    composer = MilestoneComposer()
    print(json.dumps(composer.get_all_milestones(), indent=2))
