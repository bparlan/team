# Weekly Analysis Routine

**Schedule**: 09:00 every Monday (09:00 UTC)
**Phase**: 1-3 (Inspect + Diagnose + Propose)
**Priority**: Medium
**Evidence Required**: Pattern detection + gap analysis

## Overview

Weekly analysis routine performs deeper pattern detection and gap analysis based on project evolution. It identifies architectural patterns, team skill alignment issues, and provides strategic recommendations for team composition and project evolution.

## Execution Flow

### Phase 1: Inspect (08:00-8:15)

**Goal**: Enhanced evidence collection with pattern focus

1. **Evidence Collection**
   - Daily maintenance data aggregation (5 minutes)
   - Pattern detection across all files (10 minutes)
   - Skill gap analysis (10 minutes)
   - Team performance metrics (5 minutes)

2. **Enhanced Structure Analysis**
   - Architectural pattern identification
   - Code quality metrics
   - Team skill coverage assessment
   - Project complexity evolution

### Phase 2: Diagnose (8:15-8:45)

**Goal**: Strategic gap analysis and pattern evaluation

1. **Pattern Analysis**
   - Architecture patterns (MVC, Microservices, etc.)
   - Technology stack evolution
   - Development workflow patterns
   - Dependency management patterns

2. **Gap Analysis**
   - Team skill vs. project requirements
   - Architecture vs. implementation alignment
   - Coverage gaps in critical areas
   - Evolution readiness assessment

3. **Strategic Recommendations**
   - Team composition adjustments
   - Skill development priorities
   - Architecture improvement initiatives
   - Process evolution suggestions

### Phase 3: Propose (8:45-9:00)

**Goal**: Create actionable strategic recommendations

1. **Migration Planning**
   - Phased implementation approach
   - Resource allocation recommendations
   - Timeline and dependency planning

2. **Change Proposal**
   - Minimum viable strategic changes
   - Risk assessment for strategic initiatives
   - Success criteria definition

## Expected Outputs

### 1. Weekly Strategic Report
```
Routine Engine - Weekly Analysis Report
Generated: YYYY-MM-DD HH:MM:SS

## Executive Summary
- Project Evolution Score: X/100
- Pattern Health: Healthy/Stable/Concerning
- Team Alignment: Aligned/Marginal/Problematic
- Strategic Initiatives: N (Priority: High/Medium/Low)

## Pattern Analysis
### Architecture Patterns
- Detected: [Pattern 1, Pattern 2]
- Health: [Healthy/Stable/Concerning]
- Impact: [Positive/Neutral/Negative]

### Technology Patterns
- Stack Evolution: [Assessment]
- Integration Patterns: [Assessment]
- Dependency Management: [Assessment]

## Gap Analysis
### Team Skill Gaps
1. [Skill Gap 1] - Coverage: X% | Target: Y%
2. [Skill Gap 2] - Coverage: X% | Target: Y%

### Architecture Gaps
1. [Architecture Gap 1] - Impact: [Assessment]
2. [Architecture Gap 2] - Impact: [Assessment]

## Strategic Recommendations
### Team Composition
1. [Recommendation 1] - Priority: [High/Medium/Low]
   - Impact: [Team effectiveness improvement]
   - Timeline: [Immediate/Next sprint/Monthly]

### Architecture Improvements
1. [Recommendation 1] - Priority: [High/Medium/Low]
   - Impact: [Technical debt reduction]
   - Complexity: [Simple/Moderate/Complex]

### Process Evolution
1. [Recommendation 1] - Priority: [High/Medium/Low]
   - Impact: [Workflow optimization]
   - Adoption: [Easy/Moderate/Challenging]

## Evolution Forecasts
### 3-Month Projection
- [Trend 1] - [Assessment]
- [Trend 2] - [Assessment]
- [Risk 1] - [Mitigation strategy]
- [Opportunity 1] - [Exploitation strategy]
```

### 2. Knowledge Base Updates
- `team/context/weekly-analysis-insights.md` - Pattern insights
- `routine-engine/config/weekly-metrics.json` - Weekly performance data
- `team/context/team-evolution-recommendations.md` - Team composition updates

## Success Criteria

### Quantitative
- **Pattern Detection Accuracy**: >90%
- **Gap Identification Rate**: >85% of real gaps found
- **Recommendation Actionability**: >80% of recommendations implementable
- **Execution Time**: <20 minutes total

### Qualitative
- **Strategic Value**: High impact on team effectiveness
- **Implementation Feasibility**: Clear, actionable recommendations
- **Risk Management**: Low-risk strategic initiatives
- **User Adoption**: Proactive, conversation-integrated outputs

## Integration with theteam

### Evolution Features
- Dynamic team member attribute updates
- Skill matrix evolution recommendations
- Persona adaptation based on project needs
- Knowledge base continuous improvement

### Communication Integration
- Proactive evolution suggestions during OMP outputs
- Pattern-based team composition recommendations
- Evidence-based evolution planning

## Configuration

### Routine Parameters
```yaml
routine_name: "weekly-analysis"
phases:
  - "inspect"
  - "diagnose"
  - "propose"

schedule:
  time: "09:00"
  day: "mon"
  enabled: true

parameters:
  pattern_detection: true
  gap_analysis: true
  evolution_planning: true
  auto_report: true
  min_accuracy: 0.90
  max_execution_time: 1200  # 20 minutes in seconds

safety:
  pre_execution_validation: true
  auto_rollback: true
  validation_timeout: 600
```

### Pattern Detection Thresholds
- **Strong Pattern**: Detected in >3 files or 2+ related areas
- **Emerging Pattern**: Detected in 1-2 files
- **Weak Pattern**: Detected in <1 file or single instance
- **Fading Pattern**: Present in <50% of recent commits

## Maintenance Requirements

### Required Files
- `routine-engine/engine/pattern-detector.py` - Pattern analysis engine
- `routine-engine/engine/gap-analyzer.py` - Gap identification logic
- `routine-engine/engine/evolution-recommender.py` - Evolution planning
- `routine-engine/config/pattern-database.json` - Known patterns
- `routine-engine/config/team-skills-matrix.json` - Team skill profiles

### Generated Files
- `patterns/weekly-pattern-analysis.json` - Pattern detection results
- `gaps/weekly-gap-analysis.json` - Gap identification results
- `evolution/weekly-evolution-plan.json` - Evolution recommendations

## Evolution-Specific Features

### Team Composition Evolution
1. **Dynamic Persona Updates**
   - Adjust member expertise based on project needs
   - Update interaction frequencies
   - Modify response styles

2. **Skill Matrix Evolution**
   - Track skill development progress
   - Identify emerging skill requirements
   - Recommend skill acquisition

3. **Knowledge Base Evolution**
   - Continuous learning from routine outputs
   - Best practices refinement
   - Pattern database updates

### Integration with team evolution
```
Weekly Analysis → Pattern Detection → Gap Analysis → Evolution Recommendations → Team Updates → Knowledge Base Updates
```

## Custom Routine Templates

### Template: Architecture Review
- Focus: Architectural pattern assessment
- Duration: 30 minutes
- Outputs: Architecture recommendations

### Template: Team Performance Review
- Focus: Team effectiveness analysis
- Duration: 25 minutes
- Outputs: Team composition recommendations

### Template: Technical Debt Assessment
- Focus: Code quality and debt identification
- Duration: 20 minutes
- Outputs: Debt reduction strategies

## Troubleshooting

### Pattern Detection Issues
- **False Positives**: Refine pattern matching criteria
- **Missed Patterns**: Enhance detection algorithms
- **Noise**: Filter out irrelevant patterns

### Gap Analysis Challenges
- **Subjective Gaps**: Add quantitative metrics
- **Dynamic Gaps**: Implement time-based analysis
- **Hidden Gaps**: Use correlation analysis

## Next Steps for Routine Engine Foundation

### Immediate Implementation
1. **Complete Weekly and Monthly Routines**
   - Create `monthly-evolution.md`
   - Implement pattern detector and gap analyzer
   - Build evolution recommender system

2. **Integrate with Team Evolution**
   - Connect with existing skill management
   - Implement dynamic knowledge base updates
   - Add conversation integration features

3. **Establish Monitoring**
   - Create performance metrics tracking
   - Implement health scoring systems
   - Add user feedback collection

### Integration with Existing System
- Connect to `~/devcode/team/context/project-structure-maintenance.md`
- Use existing `theteam` proposal mechanisms
- Respect all existing safety and permission controls
- Follow existing reporting formats

## Conclusion

The weekly analysis routine provides strategic insight into project evolution and team effectiveness. By combining pattern detection with gap analysis, it generates actionable recommendations that drive continuous improvement while maintaining alignment with project goals and team capabilities.

This routine, combined with the daily maintenance and future monthly evolution routines, creates a comprehensive maintenance ecosystem that ensures ongoing project health and team effectiveness.