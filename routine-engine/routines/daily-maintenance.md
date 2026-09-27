# Daily Maintenance Routine

**Schedule**: 00:30 daily (00:30 UTC)
**Phase**: 1-2 (Inspect + Diagnose)
**Priority**: High
**Evidence Required**: Project structure analysis

## Overview

Daily maintenance routine performs comprehensive project structure inspection and diagnosis using evidence-based analysis. This routine ensures ongoing stability and identifies structural issues before they impact development.

## Execution Flow

### Phase 1: Inspect (8:00-8:15)

**Goal**: Map current project structure with evidence

1. **Evidence Collection**
   - File system analysis (10 minutes)
   - Git status assessment (5 minutes)
   - Configuration validation (5 minutes)
   - Dependency verification (10 minutes)

2. **Structure Mapping**
   - Identify source code components
   - Classify test files vs production code
   - Documentation assessment
   - Configuration analysis
   - Script inventory
   - Generated content detection
   - Build artifacts identification

3. **Structural Health Assessment**
   - Stability scoring (0-100)
   - Drift analysis
   - Issue prioritization

### Phase 2: Diagnose (8:15-8:45)

**Goal**: Identify specific problems with evidence

1. **Problem Identification**
   - Generated outputs in source directories
   - Configuration scattering
   - Path fragility issues
   - Agent infrastructure drift
   - Dependency pollution
   - Backup/version confusion
   - Test/production mixing
   - Unclear directory ownership

2. **Evidence Validation**
   - Cross-reference findings
   - Verify problem severity
   - Assess impact on infrastructure

3. **Recommendations Generation**
   - Minimum viable fixes
   - Risk assessment
   - Implementation priority

## Expected Outputs

### 1. Daily Integrity Report
```
Routine Engine - Daily Maintenance Report
Generated: YYYY-MM-DD HH:MM:SS

## Executive Summary
- Project Health Score: X/100
- Issues Found: N (Critical: C, Medium: M, Low: L)
- Recommended Actions: A
- Infrastructure Impact: Minimal/Medium/High

## Structural Analysis
- Source Code: X files
- Tests: Y files  
- Documentation: Z files
- Configuration: W files

## Problems Identified
1. [Problem 1] - Evidence: [references]
2. [Problem 2] - Evidence: [references]

## Recommendations
1. [Action 1] - Priority: [High/Medium/Low]
2. [Action 2] - Priority: [High/Medium/Low]

## Remaining Issues
[List any unresolved issues]
```

### 2. Knowledge Base Updates
- `team/context/daily-maintenance-knowledge.md` - Updated with findings
- `routine-engine/config/daily-metrics.json` - Performance metrics

## Success Criteria

### Quantitative
- **Health Score**: >85/100 for healthy projects
- **Issue Resolution**: >80% of identified issues addressed
- **Execution Time**: <15 minutes total
- **Failure Rate**: <5%

### Qualitative
- **Evidence Quality**: All recommendations supported by evidence
- **Impact Assessment**: Clear infrastructure impact analysis
- **Risk Management**: Low risk implementation approach
- **User Experience**: No disruption to development workflow

## Integration with theteam

### Skill Invocation
- Uses existing proposal mechanism
- Respects `block_edits_without_plan` controls
- Only uses permitted skills for research

### Communication
- Proactive conversation comments on OMP outputs
- Evidence-first approach to problem identification
- Clear reporting of findings and recommendations

## Automation Features

### Scheduled Execution
- Daily at 00:30 UTC
- Automatic dependency checking
- Retry logic with exponential backoff
- Integration with existing CI/CD pipeline

### Manual Invocation
```
> team-run routine daily-maintenance
```

### Status Monitoring
```
> team-run routine status daily-maintenance
```

## Configuration

### Routine Parameters
```yaml
routine_name: "daily-maintenance"
phases:
  - "inspect"
  - "diagnose"

schedule:
  time: "00:30"
  enabled: true
  days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

parameters:
  evidence_collection: true
  auto_report: true
  min_health_score: 85
  max_execution_time: 900  # 15 minutes in seconds

safety:
  pre_execution_validation: true
  auto_rollback: true
  validation_timeout: 300
```

### Evidence Thresholds
- **Critical Issues**: Immediate action required (health score < 70)
- **Medium Issues**: Address within 48 hours (health score 70-85)
- **Low Issues**: Address within weekly review (health score > 85)

## Maintenance Requirements

### Required Files
- `routine-engine/engine/scheduler.py` - Core scheduling logic
- `routine-engine/engine/executor.py` - Execution engine
- `routine-engine/main.py` - Entry point
- `routine-engine/config/routines.yaml` - Routine configuration
- `routine-engine/config/daily-metrics.json` - Daily metrics storage

### Generated Files
- `reports/daily-maintenance-YYYY-MM-DD.json` - Execution records
- `knowledge/daily-maintenance-findsings.md` - Collected findings
- `artifacts/daily-structure-map.json` - Project structure snapshot

## Evolution Considerations

### Skill Updates
- `ponytail` skills: Refactor maintenance loops
- `evolve-skills` skills: Update evolution recommendations
- `code-search` skills: Enhance pattern detection

### Knowledge Base Evolution
- Update best practices based on daily findings
- Refine issue detection algorithms
- Improve health scoring methodology

### Team Composition Impact
- Daily routine informs team member assignments
- Performance metrics influence skill development
- Issue patterns guide recruitment recommendations

## Troubleshooting

### Common Issues

1. **Evidence Collection Failures**
   - Check file system permissions
   - Verify network access for remote dependencies
   - Validate configuration file syntax

2. **Performance Degradation**
   - Optimize evidence collection algorithms
   - Implement parallel processing where possible
   - Consider incremental analysis for large projects

3. **False Positives**
   - Refine issue detection criteria
   - Add manual override capability
   - Implement confirmation workflows

### Recovery Procedures
- Rollback to previous successful state
- Manual override with evidence documentation
- Emergency maintenance mode for critical issues
- Escalation to team lead for unresolved issues

## Continuous Improvement

### Metrics Tracking
- Daily execution success rate
- Issue detection accuracy
- Response time to identified problems
- User satisfaction with routine output

### Feedback Loop
- Regular routine reviews
- User feedback collection
- Algorithm refinement
- Process optimization

## Next Steps

### Immediate Actions
1. Deploy routine engine infrastructure
2. Configure daily execution schedule
3. Integrate with existing theteam system
4. Establish initial metrics tracking

### Medium-term Goals
1. Enhance pattern detection capabilities
2. Implement advanced analytics
3. Add machine learning for issue prediction
4. Create custom routine templates

### Long-term Vision
1. Fully automated maintenance ecosystem
2. Predictive maintenance based on usage patterns
3. Integration with development workflow
4. Self-evolving maintenance intelligence

## Conclusion

The daily maintenance routine establishes a foundation for automated, evidence-based project structure management. By running consistently and generating actionable insights, it ensures ongoing project health while respecting existing infrastructure and team workflows.