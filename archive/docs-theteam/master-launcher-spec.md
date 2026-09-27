# Master Launcher Specification - `bin/omp-maintain.sh`

## Overview

`bin/omp-maintain.sh` serves as the **central orchestrator** for the autonomous self-care loop system. It coordinates maintenance across multiple projects while maintaining provider resilience and human workflow integration.

## System Role

The master launcher implements the **execution control plane** for the decentralized maintenance system:

- **Project Discovery:** Automatic and manual project identification
- **Provider Health Monitoring:** Real-time FreeLLMAPI status tracking
- **Phase Management:** Two-phase maintenance cycle coordination
- **State Orchestration:** Project lifecycle and cooldown management
- **Evidence Collection:** Results aggregation and logging

## Core Architecture

### 1. Project Discovery Engine

```bash
discover_projects() {
    if [ -f ".team/registry.yml" ]; then
        # Manual override mode
        parse_registry_file
    else
        # Auto-discovery mode
        find "." -maxdepth 3 \(
            -name "pyproject.toml" -o
            -name "package.json" -o
            -name "setup.py" \n        \) -exec dirname {} \; | sort -u
    fi
}
```

#### Registry Override Format

```yaml
# .team/registry.yml
projects:
  - name: "python-project"
    enabled: true
    iterations: 5
    priority: "high"
  - name: "typescript-service" 
    enabled: true
    iterations: 3
    cooldown: "30m"
  - name: "experimental-app"
    enabled: false
    reason: "requires manual review"
```

### 2. Provider Health Management

```bash
check_provider_health() {
    local attempts=0
    local cooloff=$INITIAL_COOLOFF
    
    while true; do
        local status
        status=$(curl -s -o /dev/null -w "%{http_code}" "${FREELLMAPI_URL}/models" || echo "000")
        
        if [ "$status" -eq 200 ]; then
            return 0
        fi
        
        handle_provider_error "$status" "$attempts" "$cooloff"
        
        attempts=$((attempts + 1))
        cooloff=$((cooloff * 2)) # Exponential backoff
        if [ "$cooloff" -gt 300 ]; then cooloff=300; fi
    done
}

handle_provider_error() {
    local status="$1"
    local attempts="$2"
    local cooloff="$3"
    
    case "$status" in
        429)
            echo "[!] Rate limit (429). Cooldown active (${cooloff}s)..." >&2
            ;;
        503)
            echo "[!] Service unavailable (503). Cooldown active (${cooloff}s)..." >&2
            ;;
        *)
            echo "[!] Provider health check failed (HTTP $status). Cooldown active (${cooloff}s)..." >&2
            ;;
    esac
    
    sleep "$cooloff"
    rotate_provider_endpoint
}
```

### 3. Phase Management System

```bash
execute_project_maintenance() {
    local project_dir="$1"
    local state_file="$2"
    
    # Load project state or initialize
    load_or_initialize_state "$state_file"
    
    # Execute 5-pass maintenance cycle
    for ((iteration=1; iteration<=MAX_PASSES; iteration++)); do
        echo "==> [Project: $(basename "$project_dir")] Iteration $iteration/$MAX_PASSES"
        
        # Check provider health before each iteration
        check_provider_health || continue
        
        # Execute OMP in fresh process (prevents context degradation)
        execute_omp_iteration "$project_dir" "$iteration" "$current_phase"
        
        # Update state on successful completion
        update_project_state "$state_file" "$((current_iteration + iteration))" "SUCCESS"
    done
    
    # Post-cycle analysis and cooldown
    analyze_and_cooldown "$project_dir" "$state_file"
}

execute_omp_iteration() {
    local project_dir="$1"
    local iteration="$2"
    local phase="$3"
    
    (
        cd "$project_dir"
        omp --profile compact --prompt \
            "Execute maintenance iteration $iteration for $(basename "$project_dir") in phase $phase. Follow .team/MAINTENANCE.md protocol."
    ) || {
        echo "[!] OMP iteration $iteration failed for $(basename "$project_dir")"
        return 1
    }
}
```

### 4. State Management

```bash
load_or_initialize_state() {
    local state_file="$1"
    
    if [ ! -f "$state_file" ]; then
        # Initialize state file
        cat > "$state_file" <<EOF
{
  "project": "$(basename "$(dirname "$state_file")")",
  "state": "HEALTHY",
  "current_phase": "BASELINE",
  "iteration": 0,
  "consecutive_skips": 0,
  "last_success": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "cooldown_until": null,
  "provider_cooldown_until": null
}
EOF
    fi
}

update_project_state() {
    local state_file="$1"
    local new_iteration="$2"
    local status="$3"
    
    local temp_file="${state_file}.tmp"
    
    jq --argjson iter "$new_iteration" --arg status "$status" \
       '.iteration = $iter | .last_success = (now | strftime("%Y-%m-%dT%H:%M:%SZ")) | .state = $status' \
       "$state_file" > "$temp_file" && \
       mv "$temp_file" "$state_file"
}
```

### 5. Evidence Collection

```bash
collect_iteration_evidence() {
    local project_dir="$1"
    local iteration="$2"
    local phase="$3"
    
    local evidence_dir="${project_dir}/.team/evidence"
    mkdir -p "$evidence_dir"
    
    local evidence_file="${evidence_dir}/iteration-${iteration}-${phase}-$(date +%s).json"
    
    # Capture command execution results
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    cat > "$evidence_file" <<EOF
{
  "timestamp": "$timestamp",
  "project": "$(basename "$project_dir")",
  "iteration": $iteration,
  "phase": "$phase",
  "commands": [
    {
      "command": "omp --profile compact --prompt ...",
      "exit_code": 0,
      "output": "$(omp --profile compact --prompt ... 2>&1 | jq -R | jq -s)",
      "timestamp": "$timestamp"
    }
  ],
  "provider_health": {
    "status": "healthy",
    "last_check": "$timestamp"
  }
}
EOF
}
```

### 6. Cooldown Management

```bash
analyze_and_cooldown() {
    local project_dir="$1"
    local state_file="$2"
    
    # Analyze evidence for health status
    local health_status="HEALTHY"
    local next_phase="BASELINE"
    
    if analyze_project_health "$project_dir"; then
        # Project is healthy, continue baseline checks
        health_status="HEALTHY"
        next_phase="BASELINE"
    else
        # Project needs attention
        health_status="NEEDS_ATTENTION"
        next_phase="UPDATE"
        
        # Apply project cooldown
        apply_project_cooldown "$state_file"
    fi
    
    # Update state with new health status
    update_project_health_state "$state_file" "$health_status" "$next_phase"
}

apply_project_cooldown() {
    local state_file="$1"
    local cooldown_minutes=15
    local cooldown_until
    cooldown_until=$(date -u -d "+$cooldown_minutes minutes" +%Y-%m-%dT%H:%M:%SZ)
    
    jq --arg cooldown "$cooldown_until" '.cooldown_until = $cooldown' \
       "$state_file" > "${state_file}.tmp" && \
       mv "${state_file}.tmp" "$state_file"
    
    echo "[+] Applied ${cooldown_minutes}min cooldown to project"
}
```

## Error Handling and Recovery

### 1. Provider Error Recovery

```bash
handle_provider_recovery() {
    local project_dir="$1"
    local state_file="$2"
    
    # Check if provider is healthy again
    if check_provider_health; then
        echo "[✓] Provider recovered, resuming maintenance for $(basename "$project_dir")"
        
        # Resume from last successful iteration
        resume_project_maintenance "$project_dir" "$state_file"
    else
        echo "[!] Provider still unhealthy, continuing with other projects"
    fi
}
```

### 2. Project Error Recovery

```bash
handle_project_recovery() {
    local project_dir="$1"
    local state_file="$2"
    
    # Check if project needs human intervention
    if is_project_blocked "$state_file"; then
        echo "[!] Project $(basename "$project_dir") is BLOCKED"
        echo "[!] Review .team/reports/stack.md for intervention required"
        
        # Skip this project for now
        return 0
    fi
    
    # Resume maintenance with fresh start
    reset_project_for_maintenance "$project_dir" "$state_file"
}
```

## Configuration Management

### 1. Environment Variables

```bash
# Core configuration
export FREELLMAPI_URL="http://localhost:3001/v1"
export SEARCH_ROOT="$HOME/projects"
export PROJECTS_REGISTRY=".team/registry.yml"
export INITIAL_COOLOFF=45
export MAX_PASSES=5
export MAX_PHASE_SKIPS=3

# Optional overrides
export PROVIDER_ROTATION_ENDPOINTS="endpoint1,endpoint2,endpoint3"
export PROJECT_COOLDOWN_MINUTES=15
export HUMAN_REVIEW_TIMEOUT_HOURS=24
```

### 2. Configuration File Structure

```bash
# .team/config.sh (optional)
#!/usr/bin/env bash

# Override defaults here
export FREELLMAPI_URL="${FREELLMAPI_URL:-http://localhost:3001/v1}"
export SEARCH_ROOT="${SEARCH_ROOT:-$HOME/projects}"
export MAX_PASSES="${MAX_PASSES:-5}"

# Environment-specific settings
if [[ "$ENVIRONMENT" == "production" ]]; then
    export INITIAL_COOLOFF=300
    export MAX_PHASE_SKIPS=5
elif [[ "$ENVIRONMENT" == "development" ]]; then
    export INITIAL_COOLOFF=15
    export MAX_PHASE_SKIPS=1
fi
```

## Performance Optimization

### 1. Resource Management

```bash
# Limit concurrent projects for resource management
export CONCURRENT_PROJECTS=3

# Background process management
start_background_processor() {
    local project_dir="$1"
    (
        cd "$project_dir"
        # Run maintenance in background
        bin/omp-maintain.sh "$project_dir" &
        disown
    )
}
```

### 2. Logging and Monitoring

```bash
# Structured logging
log_event() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    echo "[${timestamp}] [${level}] ${message}" >> ".team/maintenance.log"
}

# Performance metrics
collect_metrics() {
    local project_dir="$1"
    local metrics_file="${project_dir}/.team/metrics.json"
    
    cat > "$metrics_file" <<EOF
{
  "project": "$(basename "$project_dir")",
  "start_time": "${START_TIME}",
  "end_time": "${END_TIME}",
  "duration_seconds": $((END_TIME - START_TIME)),
  "iterations": $ITERATION_COUNT,
  "successful_iterations": $SUCCESSFUL_ITERATIONS,
  "failed_iterations": $FAILED_ITERATIONS,
  "provider_health_checks": $PROVIDER_HEALTH_CHECKS,
  "cooldowns_applied": $COOLDOWNS_APPLIED
}
EOF
}
```

## Security Considerations

### 1. Access Control

```bash
# Project-specific permissions
chmod 750 ".team/"
chmod 600 ".team/state.json"
chmod 644 ".team/MAINTENANCE.md"
chmod 600 ".team/reports/stack.md"

# Repository-level restrictions
if [[ "$project_path" == *"production"* ]]; then
    echo "[!] Production project detected, limiting access"
    export RESTRICTED_COMMANDS="true"
fi
```

### 2. Data Protection

```bash
# Sensitive data masking
declare SENSITIVE_PATTERNS=(
    "password"
    "secret"
    "token"
    "key"
    ".env"
)

mask_sensitive_data() {
    local file="$1"
    local temp_file="${file}.tmp"
    
    cp "$file" "$temp_file"
    
    for pattern in "${SENSITIVE_PATTERNS[@]}"; do
        sed -i "s/${pattern}=[^[:space:]]*/${pattern}=****/g" "$temp_file"
    done
    
    mv "$temp_file" "$file"
}
```

## Testing and Validation

### 1. Unit Tests

```bash
# Test project discovery
test_project_discovery() {
    # Test with registry
    # Test without registry
    # Test with mixed environments
}

# Test provider health
# Test cooldown logic
# Test state management
# Test evidence collection
```

### 2. Integration Tests

```bash
# Test full maintenance cycle
integration_test_maintenance_cycle() {
    local test_project="test/fixtures/python-project"
    
    # Run maintenance
    bin/omp-maintain.sh "$test_project"
    
    # Verify results
    assert_project_state_healthy "$test_project"
    assert_evidence_collected "$test_project"
    assert_no_human_gates_required "$test_project"
}
```

## Maintenance and Updates

### 1. Updating the Launcher

```bash
update_launcher() {
    # Pull latest changes
    git pull origin main
    
    # Test launcher functionality
    ./bin/omp-maintain.sh --help
    
    # Restart if changes detected
    if git diff --quiet HEAD~1 HEAD; then
        echo "[!] No changes detected, no restart needed"
    else
        restart_maintenance_services
    fi
}
```

### 2. Troubleshooting

```bash
# Common troubleshooting commands
troubleshoot_provider() {
    echo "=== Provider Health Check ==="
    curl -s -o /dev/null -w "%{http_code}" "${FREELLMAPI_URL}/models"
    
    echo "=== Recent Logs ==="
    tail -20 ".team/maintenance.log"
    
    echo "=== Project States ==="
    find ".team/" -name "state.json" -exec cat {} \;
}

# Reset specific project
reset_project() {
    local project_dir="$1"
    
    echo "[!] Resetting project $(basename "$project_dir")"
    rm -f "${project_dir}/.team/state.json"
    rm -f "${project_dir}/.team/evidence/*.json"
    
    # Reinitialize project
    bin/omp-maintain.sh "$project_dir"
}
```

## Deployment and Operations

### 1. Deployment Script

```bash
#!/usr/bin/env bash
# deploy.sh - Deploy master launcher to production

deploy_maintainer() {
    local target_dir="$1"
    
    echo "[+] Deploying master launcher to $target_dir"
    
    # Copy launcher
    cp bin/omp-maintain.sh "$target_dir/bin/"
    chmod +x "$target_dir/bin/omp-maintain.sh"
    
    # Deploy configuration
    cp .team/registry.yml "$target_dir/.team/"
    
    # Setup environment
    setup_environment "$target_dir"
    
    # Start services
    start_maintenance_services "$target_dir"
}
```

### 2. Monitoring and Alerting

```bash
# Health check script
health_check() {
    local status_file="health.status"
    local timestamp
    timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    
    echo "health_status: healthy" > "$status_file"
    echo "last_check: $timestamp" >> "$status_file"
    echo "active_projects: $(find .team/ -name "state.json" | wc -l)" >> "$status_file"
    echo "provider_health: $(curl -s -o /dev/null -w "%{http_code}" "${FREELLMAPI_URL}/models")" >> "$status_file"
}
```

## Compliance and Governance

### 1. Audit Trail

```bash
# Complete audit capabilities
audit_project() {
    local project_dir="$1"
    local audit_file="${project_dir}/.team/audit.log"
    
    {
        echo "=== Project Audit Trail ==="
        echo "Project: $(basename "$project_dir")"
        echo "Start Time: $(date -u -d "$START_TIME" +%Y-%m-%dT%H:%M:%SZ)"
        echo "End Time: $(date -u -d "$END_TIME" +%Y-%m-%dT%H:%M:%SZ)"
        
        echo "=== State Changes ==="
        find "${project_dir}/.team/" -name "*.json" -exec cat {} \;
        
        echo "=== Evidence Files ==="
        find "${project_dir}/.team/evidence/" -type f -exec ls -la {} \;
        
        echo "=== Human Review Queue ==="
        cat "${project_dir}/.team/reports/stack.md" 2>/dev/null || echo "No review queue"
    } > "$audit_file"
    
    echo "[+] Audit trail saved to $audit_file"
}
```

### 2. Regulatory Compliance

```bash
# GDPR compliance checklist
gdpr_compliance_check() {
    local project_dir="$1"
    
    echo "=== GDPR Compliance Check ==="
    
    # Check for PII data
    if grep -r -E "[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}" "$project_dir" 2>/dev/null; then
        echo "[!] Potential PII data found - review required"
    fi
    
    # Check for sensitive data
    if find "$project_dir" -name "*.pem" -o -name "*.key" -o -name "*.p12" 2>/dev/null; then
        echo "[!] Sensitive cryptographic data found - access control required"
    fi
    
    # Check audit trail completeness
    if [ ! -f "${project_dir}/.team/audit.log" ]; then
        echo "[!] No audit trail - create immediately"
    fi
}
```

## Conclusion

The master launcher (`bin/omp-maintain.sh`) serves as the **central nervous system** of the autonomous self-care loop architecture. It provides:

1. **Deterministic project orchestration** with intelligent phase management
2. **Provider resilience** through comprehensive health monitoring and recovery
3. **Evidence-based operation** with complete audit trails
4. **Human workflow integration** with proper gating and review processes
5. **Enterprise-grade reliability** with comprehensive error handling

This specification ensures consistent, reliable, and maintainable autonomous maintenance across all projects while maintaining the decentralized, project-agnostic design principles.

---

*Last Updated: $(date -u +%Y-%m-%d)*
*Version: 1.0*