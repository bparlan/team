# theteam Skill - Simple Context Summary

## Current State (Evidence-Based)

### What Exists
- `theteam/__init__.py` — Complete discussion orchestrator (bootstrap, config validation, member intros, user selection, synthesis, report)
- `theteam/bin/theteam_config.py` — Config validation, init, roster commands
- `theteam/bin/theteam_report.py` — Note loading, synthesis loading, markdown report rendering
- `theteam/theteam-template.config` — Default 3-persona roster
- `package.json` — Depends on `@earendil-works/pi ^3.0.0`
- `test-integration.sh` — Basic validation
- `ANALYSIS.md` — Documents missing components
- `Scientific and Theoretical Foundation.md` — Broader OMP architecture context
- `theteam/SKILL.md` — Full workflow documentation
- **No** `theteam.config` in project root

### What's Broken
- Root `__init__.py` is a broken stub (not functional — the real implementation is in `theteam/__init__.py`)

### What Needs to Happen
1. **Delete root `__init__.py`** (stub serves no purpose)
2. **Run bootstrap** to create `theteam.config`
3. **Test one discussion** to verify end-to-end

### Entry Points
```bash
# Bootstrap (first time only)
python3 theteam/__init__.py --bootstrap

# Run discussion (after config exists)
python3 theteam/__init__.py --topic "Your topic here?"
```

### After Bootstrap
- `theteam.config` created in project root
- Reports go to `.omp/theteam/reports/`
- Discussions produce markdown with member notes + synthesis + recommendation

### Subskill Integration
- `project-structure-maintenance` subskill ready to propose from member notes
- Proposals use `propose_subskill` JSON field in member notes
- Requires user approval before any filesystem changes

### Verification (Run These)
```bash
# 1. Delete root stub (if keeping things simple)
rm /Users/bparlan/devcode/team/__init__.py

# 2. Bootstrap
cd /Users/bparlan/devcode/team && python3 theteam/__init__.py --bootstrap

# 3. Verify config exists
ls theteam.config

# 4. Run discussion
python3 theteam/__init__.py --topic "Test discussion topic?"

# 5. Check report was written
ls .omp/theteam/reports/
```

### Key Files - Canonical vs Stale

| File | Status |
|------|--------|
| `theteam/__init__.py` | ✅ Canonical, complete |
| `theteam/bin/theteam_config.py` | ✅ Canonical, functional |
| `theteam/bin/theteam_report.py` | ✅ Canonical, functional |
| `theteam/theteam-template.config` | ✅ Canonical, valid |
| `theteam/SKILL.md` | ✅ Canonical, complete |
| `theteam/team-skill.sh` | ❌ Stale/backup |
| `theteam/__init__.py` (root) | ❌ Broken stub, should delete |
| `theteam/README.md` | ✅ Reference only |
| `docs/*` | ✅ Reference only |