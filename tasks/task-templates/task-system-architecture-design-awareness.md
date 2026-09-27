```## Task Template

## Metadata
- **Task Name**: task-system-architecture-design-awareness
- **Display Name**: System Architecture Design Awareness
- **Description**: Comprehensive 4-phase system architecture analysis with health scoring and continuous monitoring
- **Priority**: medium
- **Estimated Duration**: 3-5 minutes
- **Required**: true

## Execution
```
#!/usr/bin/env python3
python3 /Users/bparlan/devcode/team/run_system_awareness.py
```

## Expected Output

### Core Files Generated
- `tasks/system-health-score.json` - System health metrics and overall score
- `tasks/architecture-analysis.md` - Architectural patterns and design decisions
- `tasks/documentation-audit-report.md` - Documentation quality assessment
- `tasks/infrastructure-assessment.md` - Infrastructure and build systems analysis
- `tasks/optimization-recommendations.md` - Actionable improvement recommendations
- `theteam/reports/system-architecture-analysis-{timestamp}.md` - Comprehensive analysis report

### Output Characteristics
- **Health Score**: Numerical score 0.0-1.0 with letter grade (A+ through F)
- **Phases**: 4 phases executed sequentially (1. Project Structure, 2. Documentation, 3. Architecture, 4. Infrastructure)
- **Analysis Depth**: Recursive scan of project files (*.py, *.md, *.json, *.yaml, *.yml)
- **Output Format**: JSON for machine-readable data, Markdown for human-readable reports

## Integration Points

### Ledger Integration
- **Input**: Project structure analysis results
- **Processing**: Updates `tasks/system-awareness-ledger.json` with:
  - Analysis history (last 10 entries)
  - Phase progress tracking
  - Team discussions (disabled for main loop)
  - User interactions (disabled for main loop)
- **Output**: Consolidated analysis results and health metrics

### Failure Handling
- **Configuration**: Continue mode (diagnostic task, non-blocking)
- **Error Recovery**: Graceful degradation with partial results
- **Retry Logic**: Automatic phase re-execution on user request (HITL only)
- **Exit Codes**: 0 for success, 1 for failure

### Dependencies
- **Required**: None (self-contained analysis)
- **Optional**: theteam skill (for team discussions - disabled in main loop)
- **External**: Python 3.12+, standard library only

## Verification Criteria

### Technical Validation
- ✅ All 6 output files generated with correct format
- ✅ Health score calculated within valid range (0.0-1.0)
- ✅ Ledger file updated with analysis history
- ✅ Phase progression tracked correctly
- ✅ Timestamped comprehensive report generated

### Quality Assurance
- ✅ Project structure analyzed (modules, relationships, metrics)
- ✅ Documentation coverage assessed (completeness, quality, structure)
- ✅ Architecture patterns identified (design patterns, decisions, debt)
- ✅ Infrastructure systems cataloged (build systems, configs)
- ✅ Recommendations actionable and prioritized

## Monitoring

### Key Metrics
- **Execution Time**: Target 3-5 minutes
- **Memory Usage**: Target < 500MB
- **Output Files**: All 6 files with minimum size 100 bytes
- **Health Score Threshold**: 0.6 (pass/fail)

### Alert Conditions
- Task timeout (> 5 minutes)
- Missing required output files
- Health score below threshold (0.6)
- Ledger write failures
- Analysis data corruption

## Configuration

### Environment Variables
```bash
SYSTEM_AWARENESS_ENABLED=true
SYSTEM_AWARENESS_PRIORITY=medium
SYSTEM_AWARENESS_TIMEOUT=300
SYSTEM_AWARENESS_HEALTH_THRESHOLD=0.6
```

### Configuration File
File: `system-awareness-config.json`

```json
{
  "project_root": "/Users/bparlan/devcode/team",
  "output_paths": {
    "ledger": "tasks/system-awareness-ledger.json",
    "reports": "theteam/reports",
    "health_score": "tasks/system-health-score.json",
    "architecture_report": "tasks/architecture-analysis.md",
    "documentation_report": "tasks/documentation-audit-report.md",
    "infrastructure_report": "tasks/infrastructure-assessment.md",
    "optimization_recommendations": "tasks/optimization-recommendations.md"
  },
  "phases": [
    {
      "id": "structure_analysis",
      "name": "Project Structure Analysis",
      "required": true,
      "description": "Analyze project structure, modules, dependencies, and complexity"
    },
    {
      "id": "documentation_audit",
      "name": "Documentation Audit",
      "required": true,
      "description": "Evaluate documentation completeness and quality"
    },
    {
      "id": "architecture_review",
      "name": "Architecture Review",
      "required": true,
      "description": "Review design patterns and architectural decisions"
    },
    {
      "id": "infrastructure_assessment",
      "name": "Infrastructure Assessment",
      "required": true,
      "description": "Assess build systems and infrastructure configuration"
    }
  ],
  "hitl_settings": {
    "phase_review_required": false,
    "team_discussion_trigger": false,
    "optimization_recommendations": true,
    "continuity_checkpoint": true
  },
  "team_discussion": {
    "enabled": false,
    "topic": "System Architecture Analysis Results",
    "required_for_completion": false
  }
}
```

## Maintenance

### Update Process
1. Run task to generate baseline outputs
2. Review health score and recommendations
3. Update analysis criteria if needed
4. Commit generated files to repository
5. Update configuration as needed

### Troubleshooting
- **Missing Files**: Ensure task executed without errors
- **Invalid Health Score**: Check analysis data integrity
- **Ledger Issues**: Verify file permissions and disk space
- **Performance Issues**: Consider increasing timeout or checking system resources

## Completion Status
**Integration Complete**: The system architecture analysis task has been successfully integrated into the main task loop using the optimized runner. The task provides comprehensive architectural insights while maintaining compatibility with the existing theteam skill infrastructure.

**Key Achievements**:
- ✅ Modular decomposition (analysis engine vs integration runner)
- ✅ HITL and team discussion removal for main loop integration
- ✅ All output files generation preserved
- ✅ Ledger integration maintained
- ✅ Performance optimized for continuous execution
- ✅ Follows Ponytail principles (minimal complexity, maximal effectiveness)