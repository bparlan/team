#!/usr/bin/env python3
"""
Archetype Database
Industry-standard project archetypes with member matching recommendations.
"""

import json
from typing import Dict, List, Any

class ArchetypeDatabase:
    def __init__(self):
        self.archetypes = self._load_archetypes()
    
    def _load_archetypes(self) -> Dict:
        """Load predefined project archetypes"""
        return {
            "web_api": {
                "name": "Web API",
                "description": "FastAPI, REST endpoints, microservices",
                "recommended_members": ["architect", "pragmatist"],
                "skills_required": ["backend_development", "api_design", "database"],
                "complexity_range": [1, 5]
            },
            "data_pipeline": {
                "name": "Data Pipeline",
                "description": "PostgreSQL, ETL workflows, data processing",
                "recommended_members": ["architect", "data", "workflow"],
                "skills_required": ["data_engineering", "etl", "database"],
                "complexity_range": [3, 8]
            },
            "browser_automation": {
                "name": "Browser Automation",
                "description": "Playwright, 10+ platform handlers, web scraping",
                "recommended_members": ["architect", "browser", "ai", "workflow"],
                "skills_required": ["browser_automation", "playwright", "web_scraping"],
                "complexity_range": [5, 10]
            },
            "ai_system": {
                "name": "AI System",
                "description": "Gemini/LLM pipelines, AI model integration",
                "recommended_members": ["ai", "skeptic", "data", "security"],
                "skills_required": ["machine_learning", "ai_integration", "data_science"],
                "complexity_range": [5, 10]
            },
            "full_stack_platform": {
                "name": "Full-Stack Platform",
                "description": "Multi-platform, AI, Browser, comprehensive system",
                "recommended_members": ["architect", "pragmatist", "skeptic", "security", "data", "browser", "ai", "workflow"],
                "skills_required": ["full_stack", "ai", "browser", "database", "security"],
                "complexity_range": [8, 15]
            }
        }
    
    def match_archetype(self, complexity_score: float, patterns: List[str]) -> Dict:
        """Match project to best archetype"""
        best_match = None
        best_score = 0
        
        for arch_name, arch_data in self.archetypes.items():
            # Check if complexity is in range
            min_comp, max_comp = arch_data["complexity_range"]
            if min_comp <= complexity_score <= max_comp:
                # Calculate match score based on patterns
                pattern_match = 0
                for pattern in patterns:
                    if pattern in arch_data["name"].lower() or any(
                        skill in pattern for skill in arch_data["skills_required"]
                    ):
                        pattern_match += 1
                
                if pattern_match > best_score:
                    best_score = pattern_match
                    best_match = arch_data
        
        if best_match:
            return {
                "archetype": best_match["name"],
                "description": best_match["description"],
                "recommended_members": best_match["recommended_members"],
                "skills_required": best_match["skills_required"],
                "match_confidence": best_score / max(len(patterns), 1)
            }
        
        # Fallback to full_stack
        return self.archetypes["full_stack_platform"]
    
    def get_all_archetypes(self) -> List[Dict]:
        """Get all available archetypes"""
        return [
            {
                "name": data["name"],
                "description": data["description"],
                "recommended_members": data["recommended_members"],
                "complexity_range": data["complexity_range"]
            }
            for name, data in self.archetypes.items()
        ]

if __name__ == "__main__":
    db = ArchetypeDatabase()
    print(json.dumps(db.get_all_archetypes(), indent=2))
