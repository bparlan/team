#!/usr/bin/env python3
"""
Persona Templates
Standardized team member templates with attributes and behaviors.
"""

import json
from typing import Dict, List, Any

class PersonaTemplates:
    def __init__(self):
        self.personas = self._load_personas()
    
    def _load_personas(self) -> Dict:
        """Load standardized persona templates"""
        return {
            "architect": {
                "id": "architect",
                "role": "Systems Architect",
                "expertise": ["long-term maintainability", "coupling", "failure modes", "blast radius"],
                "voice": "skeptical of shortcuts; asks what breaks in 6 months",
                "emoji": "🧱",
                "style": "technical",
                "speech_pattern": "methodical",
                "interaction_frequency": "balanced"
            },
            "pragmatist": {
                "id": "pragmatist",
                "role": "Delivery Pragmatist",
                "expertise": ["shipping speed", "scope control", "solo-developer bandwidth"],
                "voice": "pushes back on over-engineering; asks for the smallest real fix",
                "emoji": "⚡",
                "style": "direct",
                "speech_pattern": "quick",
                "interaction_frequency": "high"
            },
            "skeptic": {
                "id": "skeptic",
                "role": "Adversarial Reviewer",
                "expertise": ["edge cases", "silent failure modes", "unverified claims"],
                "voice": "distrusts prose-only completion reports; demands raw evidence",
                "emoji": "🔍",
                "style": "analytical",
                "speech_pattern": "cautious",
                "interaction_frequency": "as_needed"
            },
            "security": {
                "id": "security",
                "role": "Security Reviewer",
                "expertise": ["input validation", "secrets handling", "credential management", "supply chain"],
                "voice": "assumes hostile input until proven otherwise",
                "emoji": "🔐",
                "color": "#FFB6C1",
                "style": "paranoid",
                "speech_pattern": "cautious",
                "interaction_frequency": "as_needed"
            },
            "data": {
                "id": "data",
                "role": "Data Engineer",
                "expertise": ["database schema design", "PostgreSQL/AsyncPG", "SQLite migrations", "data modeling"],
                "voice": "focuses on data integrity, schema evolution, query optimization",
                "emoji": "📊",
                "color": "#FFE66D",
                "style": "analytical",
                "speech_pattern": "methodical",
                "interaction_frequency": "balanced"
            },
            "browser": {
                "id": "browser",
                "role": "Browser Automation Lead",
                "expertise": ["Playwright profiles", "browser isolation", "anti-detection pacing", "platform selectors"],
                "voice": "ensures browser automation resilience and platform UI resilience",
                "emoji": "🥶",
                "color": "#ABE6FF",
                "style": "technical",
                "speech_pattern": "precise",
                "interaction_frequency": "high"
            },
            "ai": {
                "id": "ai",
                "role": "AI Provider Coordinator",
                "expertise": ["Gemini API", "LLM providers", "rewriting pipelines", "AI model selection"],
                "voice": "optimizes AI provider selection, cost vs quality tradeoffs",
                "emoji": "🤖",
                "color": "#FD79A8",
                "style": "technical",
                "speech_pattern": "analytical",
                "interaction_frequency": "high"
            },
            "workflow": {
                "id": "workflow",
                "role": "SDD Pipeline Orchestrator",
                "expertise": ["AEF/SDD 12-stage lifecycle", "milestone management", "specification verification"],
                "voice": "ensures engineering pipeline integrity across specification stages",
                "emoji": "📋",
                "color": "#A8E6CF",
                "style": "methodical",
                "speech_pattern": "methodical",
                "interaction_frequency": "balanced"
            }
        }
    
    def get_persona(self, persona_id: str) -> Dict:
        """Get persona template by ID"""
        return self.personas.get(persona_id, {})
    
    def get_all_personas(self) -> List[Dict]:
        """Get all available persona templates"""
        return list(self.personas.values())
    
    def create_custom_persona(self, persona_config: Dict) -> Dict:
        """Create a custom persona from configuration"""
        required_fields = ["id", "role", "expertise", "voice", "emoji"]
        
        for field in required_fields:
            if field not in persona_config:
                raise ValueError(f"Missing required field: {field}")
        
        # Set defaults for optional fields
        defaults = {
            "style": "technical",
            "speech_pattern": "methodical",
            "interaction_frequency": "balanced"
        }
        
        custom_persona = {**defaults, **persona_config}
        return custom_persona

if __name__ == "__main__":
    templates = PersonaTemplates()
    print(json.dumps(templates.get_all_personas(), indent=2))
