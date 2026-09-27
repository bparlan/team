#!/bin/bash
echo "=== Team Skill Integration Test ==="
if [ -f "SKILL.md" ]; then echo "✅ SKILL.md exists"; else echo "❌ SKILL.md missing"; fi
if [ -f "package.json" ]; then echo "✅ package.json exists"; else echo "❌ package.json missing"; fi
if [ -f "pi-integration.json" ]; then echo "✅ pi-integration.json exists"; else echo "❌ pi-integration.json missing"; fi
grep -q "user-invocable: true" SKILL.md && echo "✅ user-invocable flag present" || echo "❌ user-invocable flag missing"
grep -q "tools: [" SKILL.md && echo "✅ tools list present" || echo "❌ tools list missing"
if [ -f "bin/theteam_config.py" ]; then echo "✅ Core implementation files present"; else echo "❌ Core implementation files missing"; fi
if [ -f "bin/theteam_report.py" ]; then echo "✅ Core implementation files present"; else echo "❌ Core implementation files missing"; fi
echo "=== Test Complete ==="
