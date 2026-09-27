#!/usr/bin/env python3
"""
Team Initializer
Integrated system that combines all components for optimal team initialization.
"""

import json
from typing import Dict, List, Any, Optional

# Import all components
from project_analyzer import ProjectStructureAnalyzer
from archetype_database import ArchetypeDatabase
from smart_questions import SmartQuestionsGenerator
from persona_templates import PersonaTemplates
from milestone_composer import MilestoneComposer

class TeamInitializer:
    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self.analyzer = ProjectStructureAnalyzer(project_root)
        self.archetype_db = ArchetypeDatabase()
        self.question_gen = SmartQuestionsGenerator()
        self.persona_templates = PersonaTemplates()
        self.milestone_composer = MilestoneComposer()
        
        self.initialization_result = {}
    
    def initialize_team(self) -> Dict:
        """Perform complete team initialization"""
        print("🔍 Analyzing project structure...")
        scan_result = self.analyzer.scan_project()
        
        print("📊 Matching to archetype...")
        archetype_match = self.archetype_db.match_archetype(
            scan_result["complexity_score"],
            scan_result["patterns_detected"]
        )
        
        print("❓ Generating smart questions...")
        questions = self.question_gen.generate_questions(
            scan_result["patterns_detected"],
            scan_result["complexity_score"]
        )
        
        print("👥 Creating team composition...")
        team_composition = self._create_team_composition(archetype_match, scan_result)
        
        self.initialization_result = {
            "scan_results": scan_result,
            "archetype_match": archetype_match,
            "questions": questions,
            "team_composition": team_composition,
            "initialization_timestamp": json.dumps({"timestamp": "now"}, default=str)
        }
        
        return self.initialization_result
    
    def _create_team_composition(self, archetype_match: Dict, scan_result: Dict) -> Dict:
        """Create optimal team composition"""
        recommended_members = archetype_match.get("recommended_members", [])
        all_personas = self.persona_templates.get_all_personas()
        
        # Create team member details
        team_members = []
        for member_id in recommended_members:
            persona = self.persona_templates.get_persona(member_id)
            if persona:
                team_members.append(persona)
        
        # Calculate coverage
        patterns_covered = self._calculate_coverage(team_members, scan_result["patterns_detected"])
        
        return {
            "recommended_members": recommended_members,
            "team_members": team_members,
            "total_members": len(team_members),
            "patterns_covered": patterns_covered,
            "coverage_percentage": round(patterns_covered / len(scan_result["patterns_detected"]) * 100, 1) if scan_result["patterns_detected"] else 100
        }
    
    def _calculate_coverage(self, team_members: List[Dict], patterns: List[str]) -> int:
        """Calculate how many patterns are covered by team members"""
        covered = 0
        
        for pattern in patterns:
            for member in team_members:
                # Check if member has relevant expertise
                expertise = " ".join(member.get("expertise", [])).lower()
                if pattern.lower() in expertise or any(
                    keyword in expertise for keyword in pattern.split("_")
                ):
                    covered += 1
                    break
        
        return covered
    
    def get_initialization_summary(self) -> Dict:
        """Get summary of initialization results"""
        if not self.initialization_result:
            return {"error": "No initialization performed yet"}
        
        return {
            "project_complexity": self.initialization_result["scan_results"]["complexity_score"],
            "archetype": self.initialization_result["archetype_match"]["archetype"],
            "recommended_team_size": self.initialization_result["team_composition"]["total_members"],
            "patterns_detected": self.initialization_result["scan_results"]["patterns_detected"],
            "coverage_percentage": self.initialization_result["team_composition"]["coverage_percentage"],
            "questions_to_ask": len(self.initialization_result["questions"])
        }

def initialize_team_for_project(project_path: str = ".") -> Dict:
    """Initialize team for a project"""
    initializer = TeamInitializer(project_path)
    result = initializer.initialize_team()
    return {
        "summary": initializer.get_initialization_summary(),
        "full_result": result
    }

if __name__ == "__main__":
    result = initialize_team_for_project()
    print(json.dumps(result["summary"], indent=2))
