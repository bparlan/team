#!/bin/bash

set -e

PROJECT_ROOT="/Users/bparlan/devcode/team"
TASK_RUNNER="/Users/bparlan/devcode/team/tasks/system-awareness-task-runner.py"

echo "🚀 Testing System Awareness Task Runner"
echo "Project Root: $PROJECT_ROOT"
echo "=" * 60

# Remove any existing outputs
rm -f "$PROJECT_ROOT/tasks/system-health-score.json"
rm -f "$PROJECT_ROOT/tasks/architecture-analysis.md"
rm -f "$PROJECT_ROOT/tasks/documentation-audit-report.md"
rm -f "$PROJECT_ROOT/tasks/infrastructure-assessment.md"
rm -f "$PROJECT_ROOT/tasks/optimization-recommendations.md"
rm -f "$PROJECT_ROOT/theteam/reports/system-architecture-analysis-*.md"

# Run with quick mode to bypass interactive prompts
echo "Running with quick-run flag..."
python3 "$TASK_RUNNER" \
    --project-root "$PROJECT_ROOT" \
    --quick-run \
    --no-team-discussion 2>&1 | tee "$PROJECT_ROOT/test-output.log"

# Check if all required outputs were generated
REQUIRED_FILES=(
    "$PROJECT_ROOT/tasks/system-health-score.json"
    "$PROJECT_ROOT/tasks/architecture-analysis.md"
    "$PROJECT_ROOT/tasks/documentation-audit-report.md"
    "$PROJECT_ROOT/tasks/infrastructure-assessment.md"
    "$PROJECT_ROOT/tasks/optimization-recommendations.md"
    "$PROJECT_ROOT/theteam/reports/system-architecture-analysis-*.md"
)

echo ""
echo "📊 Verifying Generated Files"
echo "=" * 60

ALL_GENERATED=true
for file_pattern in "${REQUIRED_FILES[@]}"; do
    # Expand wildcard patterns
    if [[ $file_pattern == *"*"* ]]; then
        matches=$(ls -1 $file_pattern 2>/dev/null | wc -l)
        if [ $matches -gt 0 ]; then
            echo "✅ $file_pattern ($matches files)"
        else
            echo "❌ $file_pattern (0 files)"
            ALL_GENERATED=false
        fi
    else
        if [ -f "$file_pattern" ]; then
            echo "✅ $file_pattern"
        else
            echo "❌ $file_pattern"
            ALL_GENERATED=false
        fi
    fi
done

# Check ledger file
if [ -f "$PROJECT_ROOT/tasks/system-awareness-ledger.json" ]; then
    echo "✅ $PROJECT_ROOT/tasks/system-awareness-ledger.json"
else
    echo "❌ $PROJECT_ROOT/tasks/system-awareness-ledger.json"
    ALL_GENERATED=false
fi

echo ""
echo "📋 Checking Generated Content"
echo "=" * 60

if [ -f "$PROJECT_ROOT/tasks/system-health-score.json" ]; then
    echo "Health Score JSON content:"
    cat "$PROJECT_ROOT/tasks/system-health-score.json" | head -20
fi

echo ""
echo "🏆 Task Test Summary"
echo "=" * 60

if [ "$ALL_GENERATED" = true ]; then
    echo "✅ All required outputs generated successfully!"
    echo "✅ Task passed all functionality tests!"
else
    echo "❌ Some outputs were missing"
    echo "❌ Task failed some tests"
fi

echo ""
echo "📁 Full Task Output (see test-output.log)"
echo "📊 Exit Code: $?"