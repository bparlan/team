# theteam Skill Analysis

## Current State

The `theteam` skill currently consists of:
- `SKILL.md` - Detailed orchestration logic but no implementation
- `bin/theteam_config.py` - Config validation and initialization
- `bin/theteam_report.py` - Report generation from notes + synthesis
- `theteam-template.config` - Template for project configs

**Missing Critical Components:**

1. **Main Orchestrator (`__init__.py`)** - The skill entry point that should:
   - Implement the entire workflow from SKILL.md
   - Handle config validation, bootstrap, and discussion phases
   - Manage todo plan creation and execution
   - Spawn team members via `task` tool
   - Coordinate synthesis pass
   - Generate reports

2. **Tool Integration** - Ensure proper access to:
   - `todo` - For plan management
   - `ask` - For user questions during bootstrap
   - `hub` - For messaging and coordination
   - `task` - For spawning team members
   - `write`/`edit` - For file operations
   - `bash` - For running thebin scripts

## Required Tool Dependencies

Based on SKILL.md, the team skill MUST have access to:

### Core Orchestration Tools
- `todo` - For creating and managing execution plans
- `ask` - For user questions during bootstrap phase
- `hub` - For messaging and coordination
- `task` - For spawning independent team member subagents
- `bash` - For running config and report scripts

### File System Tools
- `write` - For creating config files, notes, synthesis, reports
- `edit` - For modifying existing files
- `read` - For reading project structure and configs

### Research Tools (per config)
- `graph-curation-expert` - If permitted in project config
- `brave-search` - If permitted in project config

## Expected Workflow

1. **Config Validation** - Check for `theteam.config` in project root
2. **Bootstrap** - If config missing, guide user through creation
3. **Discussion** - Execute full team discussion with:
   - Todo plan creation
   - Pre-analysis search
   - Independent member notes
   - Synthesis pass
   - Report generation

## Architecture Issues

1. **No Entry Point** - Missing `__init__.py` means skill has no trigger
2. **No Tool Access** - May not be properly integrated with OMP tool system
3. **Missing Bootstrap Logic** - SKILL.md describes complex bootstrap but nothing implements it
4. **No Safety Gates** - Missing validation of permitted_skills before use
5. **No Error Handling** - SKILL.md mentions error conditions but no implementation

## Implementation Priority

1. Create main orchestrator (`__init__.py`) with:
   - Skill trigger detection ("theteam", "ask the team", etc.)
   - Config validation via bash script calls
   - Full bootstrap flow implementation
   - Discussion phase orchestration

2. Ensure tool integration:
   - Proper tool declarations
   - Tool access validation
   - Error handling for tool calls

3. Implement safety features:
   - Config validation before operations
   - Todo plan enforcement
   - Permitted skills checking