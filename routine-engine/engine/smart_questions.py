#!/usr/bin/env python3
"""
Smart Questions Generator
Targeted questions based on detected patterns for team initialization.
"""

import json
from typing import Dict, List, Any

class SmartQuestionsGenerator:
    def __init__(self):
        self.question_templates = self._load_templates()
    
    def _load_templates(self) -> Dict:
        """Load question templates for different scenarios"""
        return {
            "platform_detection": {
                "trigger": "12 platform handlers detected",
                "question": "This project has 12 platform handlers. Would you like to add a browser automation specialist?",
                "options": ["Yes", "No", "Maybe later"]
            },
            "ai_detection": {
                "trigger": "12 AI modules detected",
                "question": "AI modules found. Add an AI provider coordinator to optimize model selection and cost?",
                "options": ["Yes", "No", "Maybe later"]
            },
            "security_detection": {
                "trigger": "17 security files detected",
                "question": "Security components detected. Add a security reviewer for credential management and input validation?",
                "options": ["Yes", "No", "Maybe later"]
            },
            "database_detection": {
                "trigger": "PostgreSQL/AsyncPG detected",
                "question": "Database system found. Add a data engineer for schema design and migration management?",
                "options": ["Yes", "No", "Maybe later"]
            },
            "pipeline_detection": {
                "trigger": "AEF/SDD pipeline detected",
                "question": "Pipeline system found. Add a workflow orchestrator for specification and milestone management?",
                "options": ["Yes", "No", "Maybe later"]
            }
        }
    
    def generate_questions(self, patterns: List[str], complexity: float) -> List[Dict]:
        """Generate targeted questions based on detected patterns"""
        questions = []
        
        if "ai_system" in patterns:
            questions.append(self.question_templates["ai_detection"])
        
        if "security_focused" in patterns:
            questions.append(self.question_templates["security_detection"])
        
        if "database_system" in patterns:
            questions.append(self.question_templates["database_detection"])
        
        if "pipeline_system" in patterns:
            questions.append(self.question_templates["pipeline_detection"])
        
        if "browser_automation" in patterns:
            questions.append(self.question_templates["platform_detection"])
        
        # Add complexity-based question
        if complexity > 8:
            questions.append({
                "trigger": f"High complexity score: {complexity}",
                "question": "This is a complex project. Would you like to review the recommended team composition?",
                "options": ["Review team", "Proceed with defaults", "Customize"]
            })
        
        return questions
    
    def get_suggested_questions(self) -> List[str]:
        """Get list of suggested questions for user"""
        return [
            "What is the primary technology stack?",
            "How many platform integrations are needed?",
            "What AI/ML capabilities are required?",
            "What is the expected team size?",
            "What is the project timeline?"
        ]

if __name__ == "__main__":
    gen = SmartQuestionsGenerator()
    questions = gen.generate_questions(["ai_system", "security_focused"], 10.5)
    print(json.dumps(questions, indent=2))
