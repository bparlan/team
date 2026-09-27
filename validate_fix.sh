#!/bin/bash
set -e

echo "=== PHASE 3/4 DRIFT FIX VALIDATION ==="
FAILED=0

# 1. Check imports
if grep -E "from theteam\.core\.(circuit_breaker|resource_limiter|health_monitor) import" theteam/core/unified_loop.py > /dev/null 2>&1; then
    echo "✅ Phase 3 modules imported"
else
    echo "❌ Phase 3 modules not imported"
    FAILED=1
fi

# 2. Check no duplicate classes
if grep -n "^class CircuitBreaker\|^class ResourceLimiter\|^class HealthMonitor" theteam/core/unified_loop.py | grep -v "import.*circuit_breaker\|import.*resource_limiter\|import.*health_monitor" | grep -q .; then
    echo "❌ Duplicate classes still in unified_loop.py"
    FAILED=1
else
    echo "✅ No duplicate classes"
fi

# 3. Run tests
if python -m pytest test_unified_loop.py test_final_validation.py -v 2>&1 | grep -q "passed"; then
    echo "✅ Tests pass"
else
    echo "❌ Tests failing"
    FAILED=1
fi

# 4. Check roadmap
REMAINING=$(grep -c '\[ \]' STABILITY_ROADMAP.md)
DONE=$(grep -c '\[X\]' STABILITY_ROADMAP.md)
if [ "$REMAINING" -lt 20 ]; then
    echo "✅ Progress: $DONE done, $REMAINING remaining"
else
    echo "❌ Too much work remaining: $REMAINING tasks"
    FAILED=1
fi

# 5. Check Docker file exists
if [ -f "Dockerfile" ] && [ -f "docker-compose.yml" ]; then
    echo "✅ Docker infrastructure exists"
else
    echo "❌ Docker infrastructure missing"
    FAILED=1
fi

# 6. Check backup scripts exist
if [ -f "scripts/backup.py" ]; then
    echo "✅ Backup system exists"
else
    echo "❌ Backup system missing"
    FAILED=1
fi

if [ "$FAILED" -eq 0 ]; then
    echo ""
    echo "🎉 DRIFT FIX COMPLETE - READY FOR PHASE 5"
    exit 0
else
    echo ""
    echo "❌ FIXES NEEDED - Review above failures"
    exit 1
fi
