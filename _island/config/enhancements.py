#!/usr/bin/env python3
"""
Behavioral Trait Definitions for theteam Enhancement

This module defines expanded behavioral role modifiers based on modern
team collaboration research and best practices.
"""

# Core style options - expanded from current 3 to 10+
CORE_STYLES = {
    # Existing styles
    "technical": {
        "description": "Logical, systematic, detail-oriented approach",
        "strengths": ["Precision", "Analytical thinking", "Procedural knowledge"],
        "weaknesses": ["May overlook big picture", "Resistance to change"],
        "ideal_for": ["Architecture", "Infrastructure", "Deep technical work"]
    },
    "direct": {
        "description": "Clear, concise, action-oriented communication",
        "strengths": ["Clarity", "Efficiency", "Quick decision making"],
        "weaknesses": ["May be perceived as harsh", "Impatience with complexity"],
        "ideal_for": ["Project management", "Client communication", "Rapid development"]
    },
    "analytical": {
        "description": "Strategic, objective, evidence-based thinking",
        "strengths": ["Critical thinking", "Risk assessment", "Long-term planning"],
        "weaknesses": ["Analysis paralysis", "Over-cautiousness"],
        "ideal_for": ["Security review", "Architecture review", "Risk analysis"]
    },
    
    # New enhanced styles
    "creative": {
        "description": "Innovative, imaginative, unconventional thinking",
        "strengths": ["Novel solutions", "Brainstorming", "Unbiased perspective"],
        "weaknesses": ["May ignore practical constraints", "Disorganization"],
        "ideal_for": ["UX design", "Product innovation", "Research and development"]
    },
    "practical": {
        "description": "Down-to-earth, results-focused, pragmatic approach",
        "strengths": ["Realistic planning", "Resource optimization", "Quick implementation"],
        "weaknesses": ["May miss strategic opportunities", "Short-term thinking"],
        "ideal_for": ["Operations", "Implementation", "Process improvement"]
    },
    "visionary": {
        "description": "Strategic, big-picture, future-oriented thinking",
        "strengths": ["Strategic vision", "Inspiration", "Long-term insight"],
        "weaknesses": ["May be unrealistic", "Implementation challenges"],
        "ideal_for": ["Strategy", "Product roadmap", "Innovation"]
    },
    "diplomatic": {
        "description": "Sensitive, relationship-focused, consensus-building",
        "strengths": ["Conflict resolution", "Team building", "Client relations"],
        "weaknesses": ["Avoids tough decisions", "Compromise position"],
        "ideal_for": ["Customer success", "Team leadership", "Client management"]
    },
    "assertive": {
        "description": "Confident, decisive, authoritative communication",
        "strengths": ["Clear direction", "Quick decisions", "Leadership"],
        "weaknesses": ["May overwhelm team", "Disregards input"],
        "ideal_for": ["Project leadership", "Crisis management", "Decisive action"]
    },
    "strategic": {
        "description": "Long-term, high-level, organizational thinking",
        "strengths": ["Systems thinking", "Strategic planning", "Resource optimization"],
        "weaknesses": ["May miss operational details", "Slow to act"],
        "ideal_for": ["Executive management", "Strategic planning", "Resource allocation"]
    },
    "hands_on": {
        "description": "Practical, immediate, task-oriented approach",
        "strengths": ["Immediate results", "Problem solving", "Team mentoring"],
        "weaknesses": ["May micromanage", "Limited strategic perspective"],
        "ideal_for": ["Technical implementation", "Team mentoring", "Operations"]
    }
}

# Enhanced personality structure
ENHANCED_PERSONALITY_TRAITS = {
    "communication_approach": {
        "methodical": {
            "description": "Structured, planned, systematic communication",
            "characteristics": ["Thorough documentation", "Scheduled updates", "Formal processes"],
            "best_for": ["Complex projects", "Documentation-heavy work", "Regulatory environments"]
        },
        "quick": {
            "description": "Rapid, informal, spontaneous communication",
            "characteristics": ["Ad-hoc updates", "Casual tone", "Fast iterations"],
            "best_for": ["Startup environments", "Agile development", "Rapid prototyping"]
        },
        "cautious": {
            "description": "Careful, conservative, risk-averse communication",
            "characteristics": ["Risk analysis", "Conservative estimates", "Safety protocols"],
            "best_for": ["Safety-critical systems", "Financial systems", "Compliance"]
        },
        "diplomatic": {
            "description": "Sensitive, relationship-focused, consensus-driven",
            "characteristics": ["Conflict avoidance", "Win-win solutions", "Team harmony"],
            "best_for": ["Client-facing teams", "Cross-functional collaboration", "Conflict resolution"]
        },
        "assertive": {
            "description": "Direct, decisive, authoritative communication",
            "characteristics": ["Clear directives", "Quick decisions", "Bold statements"],
            "best_for": ["Crisis situations", "Emergency response", "Fast-moving environments"]
        }
    },
    
    "decision_making_approach": {
        "analytical": {
            "description": "Data-driven, logical, systematic decision process",
            "characteristics": ["Evidence collection", "Analysis", "Risk assessment"],
            "best_for": ["Technical decisions", "Financial decisions", "Strategic planning"]
        },
        "intuitive": {
            "description": "Gut feeling, experience-based, rapid decisions",
            "characteristics": ["Experience-based", "Speed", "Pattern recognition"],
            "best_for": ["Creative decisions", "Emergency decisions", "Rapid iteration"]
        },
        "consensus_based": {
            "description": "Group agreement, collaborative, inclusive process",
            "characteristics": ["Team discussion", "Compromise", "Shared ownership"],
            "best_for": ["Team decisions", "Policy changes", "Major direction"]
        },
        "autonomous": {
            "description": "Independent, decisive, leader-driven decisions",
            "characteristics": ["Single-person decisions", "Quick action", "Clear authority"],
            "best_for": ["Emergency response", "Critical decisions", "Command structures"]
        }
    },
    
    "conflict_resolution_style": {
        "direct": {
            "description": "Confrontational, direct, solution-focused",
            "characteristics": ["Call out issues", "Address immediately", "Solution-oriented"],
            "best_for": ["Technical disagreements", "Performance issues", "Safety concerns"]
        },
        "diplomatic": {
            "description": "Mediated, relationship-focused, indirect",
            "characteristics": ["Mediation", "Win-win solutions", "Gradual approach"],
            "best_for": ["Team dynamics", "Client relationships", "Sensitive situations"]
        },
        "avoidant": {
            "description": "Passive, withdrawn, issue avoidance",
            "characteristics": ["Deferral", "Delegation", "Minimization"],
            "best_for": ["Conflict de-escalation", "Low-priority issues", "Timing considerations"]
        },
        "collaborative": {
            "description": "Integrative, win-win, mutual problem solving",
            "characteristics": ["Joint problem solving", "Creative solutions", "Shared credit"],
            "best_for": ["Complex problems", "Cross-functional teams", "Strategic initiatives"]
        }
    },
    
    "communication_preference": {
        "formal": {
            "description": "Structured, professional, documented communication",
            "characteristics": ["Email formalities", "Documentation", "Professional tone"],
            "best_for": ["Client communications", "Formal agreements", "Official documentation"]
        },
        "casual": {
            "description": "Informal, conversational, spontaneous communication",
            "characteristics": ["Chat communication", "Quick updates", "Personal connections"],
            "best_for": ["Team communication", "Daily standups", "Informal updates"]
        },
        "detailed": {
            "description": "Comprehensive, thorough, exhaustive communication",
            "characteristics": ["Detailed specifications", "Complete documentation", "Thorough explanations"],
            "best_for": ["Technical documentation", "Architecture design", "Complex instructions"]
        },
        "concise": {
            "description": "Brief, to-the-point, efficient communication",
            "characteristics": ["Summary communications", "Bullet points", "Key takeaways"],
            "best_for": ["Status reports", "Decision communications", "Emergency updates"]
        }
    },
    
    "work_pacing": {
        "steady": {
            "description": "Consistent, reliable, measured work pace",
            "characteristics": ["Regular schedule", "Predictable delivery", "Quality focus"],
            "best_for": ["Long-term projects", "Quality-critical work", "Stable environments"]
        },
        "fast_paced": {
            "description": "Rapid, agile, quick iteration pace",
            "characteristics": ["Rapid iterations", "Fast delivery", "Continuous improvement"],
            "best_for": ["Startup environments", "MVP development", "Competitive markets"]
        },
        "methodical": {
            "description": "Systematic, structured, planned work pace",
            "characteristics": ["Phased approach", "Structured timeline", "Planned milestones"],
            "best_for": ["Complex systems", "Regulatory compliance", "Large-scale projects"]
        },
        "adaptive": {
            "description": "Flexible, responsive, dynamic work pace",
            "characteristics": ["Responsive to changes", "Dynamic scheduling", "Adaptive planning"],
            "best_for": ["Dynamic environments", "Agile projects", "Uncertain requirements"]
        }
    }
}

# Behavioral modifiers for role adaptation
BEHAVIORAL_MODIFIERS = {
    "complexity_sensitivity": {
        "low": {
            "description": "Handles simple, straightforward tasks well",
            "characteristics": ["Clear requirements", "Well-defined processes", "Stable environment"],
            "best_for": ["Simple automation", "Routine maintenance", "Well-understood domains"]
        },
        "medium": {
            "description": "Handles moderate complexity with guidance",
            "characteristics": ["Some ambiguity", "Need for clarification", "Training required"],
            "best_for": ["Standard development", "Regular projects", "Training environments"]
        },
        "high": {
            "description": "Thrives on complex, ambiguous challenges",
            "characteristics": ["Unclear requirements", "Novel problems", "Dynamic environments"],
            "best_for": ["Innovation projects", "Research", "Cutting-edge technology"]
        }
    },
    
    "risk_tolerance": {
        "conservative": {
            "description": "Risk-averse, safety-focused, cautious approach",
            "characteristics": ["Risk assessment", "Safety protocols", "Conservative estimates"],
            "best_for": ["Safety-critical systems", "Financial systems", "Compliance"]
        },
        "moderate": {
            "description": "Balanced approach to risk and innovation",
            "characteristics": ["Risk-reward analysis", "Balanced innovation", "Managed exposure"],
            "best_for": ["Standard business operations", "Regular product development", "Balanced growth"]
        },
        "aggressive": {
            "description": "Risk-taking, innovation-focused, rapid advancement",
            "characteristics": ["Rapid prototyping", "Market opportunities", "Competitive advantage"],
            "best_for": ["Startup environments", "Market disruption", "Rapid innovation"]
        }
    },
    
    "detail_orientation": {
        "high": {
            "description": "Detail-focused, thorough, precision-oriented",
            "characteristics": ["Quality checks", "Documentation", "Testing"],
            "best_for": ["Quality assurance", "Security review", "Compliance testing"]
        },
        "medium": {
            "description": "Balanced attention to detail",
            "characteristics": ["Appropriate scope", "Quality assurance", "Efficient testing"],
            "best_for": ["Standard development", "Regular projects", "Balanced workflows"]
        },
        "low": {
            "description": "Big-picture focused, strategic, outcome-oriented",
            "characteristics": ["Strategic planning", "Vision", "Outcome focus"],
            "best_for": ["Strategy", "Leadership", "High-level planning"]
        }
    },
    
    "innovation_preference": {
        "traditional": {
            "description": "Conservative, established methods, proven approaches",
            "characteristics": ["Best practices", "Established procedures", "Reliable solutions"],
            "best_for": ["Mature systems", "Stable operations", "Risk-averse environments"]
        },
        "incremental": {
            "description": "Gradual improvements, iterative enhancements",
            "characteristics": ["Continuous improvement", "Process optimization", "Evolutionary changes"],
            "best_for": ["Continuous delivery", "Process improvement", "Stable innovation"]
        },
        "disruptive": {
            "description": "Radical changes, breakthrough innovations",
            "characteristics": ["Revolutionary ideas", "Market transformation", "Paradigm shifts"],
            "best_for": ["Startup phases", "Market entry", "Disruption strategies"]
        }
    }
}

# Team role templates based on behavioral combinations
TEAM_ROLE_TEMPLATES = {
    "technical_architect": {
        "core_style": "technical",
        "communication_approach": "methodical",
        "decision_making_approach": "analytical",
        "conflict_resolution_style": "direct",
        "communication_preference": "detailed",
        "work_pacing": "steady",
        "complexity_sensitivity": "high",
        "risk_tolerance": "moderate",
        "detail_orientation": "high",
        "innovation_preference": "incremental",
        "roles": ["Architecture design", "Technical standards", "System integration"],
        "ideal_projects": ["Complex systems", "Enterprise applications", "Scalable infrastructure"]
    },
    
    "delivery_pragmatist": {
        "core_style": "direct",
        "communication_approach": "quick",
        "decision_making_approach": "autonomous",
        "conflict_resolution_style": "collaborative",
        "communication_preference": "concise",
        "work_pacing": "fast_paced",
        "complexity_sensitivity": "medium",
        "risk_tolerance": "aggressive",
        "detail_orientation": "medium",
        "innovation_preference": "incremental",
        "roles": ["Project delivery", "Scope management", "Resource optimization"],
        "ideal_projects": ["Rapid development", "MVP delivery", "Market launch"]
    },
    
    "adversarial_reviewer": {
        "core_style": "analytical",
        "communication_approach": "methodical",
        "decision_making_approach": "analytical",
        "conflict_resolution_style": "direct",
        "communication_preference": "detailed",
        "work_pacing": "steady",
        "complexity_sensitivity": "high",
        "risk_tolerance": "conservative",
        "detail_orientation": "high",
        "innovation_preference": "traditional",
        "roles": ["Security review", "Quality assurance", "Risk assessment"],
        "ideal_projects": ["Security-critical systems", "Compliance requirements", "Safety standards"]
    },
    
    "creative_innovator": {
        "core_style": "creative",
        "communication_approach": "quick",
        "decision_making_approach": "intuitive",
        "conflict_resolution_style": "diplomatic",
        "communication_preference": "casual",
        "work_pacing": "adaptive",
        "complexity_sensitivity": "high",
        "risk_tolerance": "aggressive",
        "detail_orientation": "low",
        "innovation_preference": "disruptive",
        "roles": ["Product innovation", "UX design", "Research and development"],
        "ideal_projects": ["New product development", "User experience", "Market research"]
    },
    
    "strategic_leader": {
        "core_style": "strategic",
        "communication_approach": "methodical",
        "decision_making_approach": "consensus_based",
        "conflict_resolution_style": "collaborative",
        "communication_preference": "detailed",
        "work_pacing": "steady",
        "complexity_sensitivity": "medium",
        "risk_tolerance": "moderate",
        "detail_orientation": "medium",
        "innovation_preference": "incremental",
        "roles": ["Executive leadership", "Strategic planning", "Resource allocation"],
        "ideal_projects": ["Organizational transformation", "Strategic initiatives", "Long-term vision"]
    }
}

# Project characteristic detection patterns
PROJECT_CHARACTERISTICS = {
    "code_complexity": {
        "high_complexity_indicators": [
            "many interdependent modules",
            "deep inheritance chains",
            "complex state management",
            "multiple integration points",
            "tight coupling",
            "circular dependencies"
        ],
        "low_complexity_indicators": [
            "single file organization",
            "simple scripts",
            "limited dependencies",
            "clear separation of concerns",
            "straightforward logic"
        ]
    },
    
    "documentation_needs": {
        "high_needs": [
            "complex API documentation",
            "architecture diagrams",
            "deployment procedures",
            "security protocols",
            "operational procedures"
        ],
        "low_needs": [
            "simple scripts",
            "minimal documentation",
            "self-explanatory code",
            "quick implementation"
        ]
    },
    
    "testing_requirements": {
        "high_requirements": [
            "comprehensive unit tests",
            "integration testing",
            "end-to-end testing",
            "performance testing",
            "security testing"
        ],
        "low_requirements": [
            "manual testing",
            "basic functionality checks",
            "user acceptance testing",
            "smoke testing"
        ]
    }
}

# Behavioral compatibility scoring
BEHAVIORAL_COMPATIBILITY_MATRIX = {
    "technical": {"compatible_with": ["creative", "analytical", "strategic"]},
    "direct": {"compatible_with": ["assertive", "practical", "diplomatic"]},
    "analytical": {"compatible_with": ["technical", "strategic", "creative"]},
    "creative": {"compatible_with": ["analytical", "strategic", "diplomatic"]},
    "practical": {"compatible_with": ["direct", "strategic", "hands_on"]},
    "visionary": {"compatible_with": ["strategic", "creative", "analytical"]},
    "diplomatic": {"compatible_with": ["direct", "assertive", "creative"]},
    "assertive": {"compatible_with": ["diplomatic", "direct", "practical"]},
    "strategic": {"compatible_with": ["technical", "creative", "analytical"]},
    "hands_on": {"compatible_with": ["practical", "direct", "strategic"]}
}

# Assessment metrics
ASSESSMENT_METRICS = {
    "behavioral_diversity_score": {
        "description": "Measure of diverse behavioral styles in team",
        "calculation": "number of unique core_styles / total_team_size",
        "ideal_range": [0.6, 1.0]
    },
    "project_team_fit_score": {
        "description": "How well team behavioral composition matches project needs",
        "calculation": "sum of compatibility scores between project characteristics and team behaviors",
        "ideal_range": [0.7, 1.0]
    },
    "team_synergy_score": {
        "description": "Overall team cohesion and effectiveness",
        "calculation": "weighted average of behavioral compatibility and communication patterns",
        "ideal_range": [0.7, 1.0]
    },
    "behavioral_coverage_score": {
        "description": "Coverage of required behavioral traits for project success",
        "calculation": "percentage of essential traits represented in team",
        "ideal_range": [0.8, 1.0]
    }
}

if __name__ == "__main__":
    # Test the behavioral trait definitions
    print("Behavioral Trait Definitions Loaded Successfully")
    print(f"Core styles: {len(CORE_STYLES)}")
    print(f"Enhanced personality traits: {len(ENHANCED_PERSONALITY_TRAITS)}")
    print(f"Behavioral modifiers: {len(BEHAVIORAL_MODIFIERS)}")
    print(f"Team role templates: {len(TEAM_ROLE_TEMPLATES)}")