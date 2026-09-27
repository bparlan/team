# Project Contract Template - `.team/MAINTENANCE.md`

## Overview

The `.team/MAINTENANCE.md` file serves as the **project-specific maintenance contract** that defines how autonomous maintenance should operate for each repository. This document enables the master launcher to understand project requirements, constraints, and capabilities without central coordination.

## Contract Structure

```yaml
# .team/MAINTENANCE.md

## Stack
- Language: python|typescript|javascript|bash|other
- Build: make|npm|pip|cargo|gradle|custom
- Test: pytest|jest|mocha|custom

## Health
- Lint: command
- Build: command  
- Test: command
- Type Check: command

## Safe Operations
- action1
- action2

## Forbidden Operations
- action1
- action2

## Documentation
- documentation_links

## Maintenance Priorities
1. priority1
2. priority2

## Infrastructure
- env_info

## Human Gates
- gate1
- gate2
```

## Required Sections

### 1. Stack Identification

**Purpose:** Define project technology stack for autonomous maintenance

```markdown
## Stack
- Language: python
- Build: make
- Test: pytest
```

**Examples:**
- **Python Project:** `Language: python, Build: make, Test: pytest`
- **TypeScript Project:** `Language: typescript, Build: npm run build, Test: jest`
- **JavaScript Project:** `Language: javascript, Build: npm run build, Test: jest`
- **Bash Project:** `Language: bash, Build: custom, Test: bash tests/`

### 2. Health Configuration

**Purpose:** Specify exact commands for health verification

```markdown
## Health
- Lint: flake8 src/
- Build: make build
- Test: pytest
- Type Check: mypy src/
```

**Command Format Guidelines:**
- Use **exact project commands** (no assumptions)
- Include **exit codes** in documentation
- Specify **working directories** when needed
- List **all required dependencies**

**Health Command Categories:**

#### Linting Commands
- **Python:** `flake8 src/`, `black --check src/`, `isort --check src/`
- **JavaScript/TypeScript:** `eslint .`, `prettier --check .`
- **General:** `shellcheck scripts/`, `hadolint Dockerfile`

#### Build Commands  
- **Python:** `python setup.py build`, `pip install -e .[dev]`
- **Node.js:** `npm run build`, `yarn build`
- **Go:** `go build ./...`, `go test ./...`

#### Test Commands
- **Python:** `pytest`, `python -m unittest discover`, `coverage run -m pytest`
- **JavaScript:** `npm test`, `jest`, `mocha`
- **General:** `go test ./...`, `cargo test`

#### Type Checking Commands
- **Python:** `mypy src/`, `pyright src/`
- **TypeScript:** `tsc --noEmit`, `pyright`
- **General:** `pnpm typecheck`, `bun check`

### 3. Safe Operations List

**Purpose:** Define autonomous actions that are always permitted

```markdown
## Safe Operations
- Fix syntax errors in source files
- Remove unused imports and variables
- Format code with project formatter
- Update non-breaking dependency versions
- Fix failing tests
- Clean up temporary files
- Update documentation links
```

**Safe Operation Categories:**

#### Code Cleanup
- Remove unused imports (`isort --remove-unused-imports`)
- Sort imports (`isort format`)
- Format code (`black format`, `prettier format`)
- Remove duplicate code (`refactor --remove-duplicates`)

#### Non-Breaking Updates
- Update dependencies with `^` version constraints
- Fix typos and minor documentation errors
- Update code comments and variable names
- Remove dead code and unused functions

#### Test Improvements
- Fix test syntax errors
- Update test data
- Add test comments
- Remove duplicate test cases

### 4. Forbidden Operations List

**Purpose:** Clearly define manual-only operations

```markdown
## Forbidden Operations
- Modify architectural decisions
- Change public API contracts
- Update production configuration
- Deploy to production environments
- Modify database schemas
- Add new external service integrations
- Commit secrets or credentials
```

**Manual-Only Categories:**

#### Architectural Changes
- Refactor application architecture
- Change design patterns
- Modify component boundaries
- Reorganize module structure

#### API and Schema Changes
- Modify public API signatures
- Change database schemas
- Update configuration formats
- Alter message contracts

#### Production and Deployment
- Deploy to production/VPS
- Modify production configuration
- Update load balancers
- Change security policies

#### Infrastructure Changes
- Add new external services
- Modify network configurations
- Update CI/CD pipelines
- Change monitoring systems

### 5. Documentation Section

**Purpose:** Provide context for autonomous maintenance decisions

```markdown
## Documentation
- [README.md](README.md) - Project overview and setup
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines
- [CHANGELOG.md](CHANGELOG.md) - Version history
- [API.md](API.md) - Public API documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - System design
```

**Documentation Types:**

#### Required Documentation
- **README:** Project purpose, setup instructions
- **API Documentation:** Public interfaces and usage
- **Architecture:** System design and component relationships

#### Helpful Documentation
- **Contributing:** Guidelines for external contributors
- **Changelog:** Version history and breaking changes
- **Security:** Security policies and vulnerability reporting

### 6. Maintenance Priorities

**Purpose:** Define work ordering for autonomous maintenance

```markdown
## Maintenance Priorities
1. Fix critical bugs affecting core functionality
2. Ensure all tests pass with clean linting
3. Update dependencies to latest non-breaking versions
4. Improve code documentation and comments
5. Remove unused code and dependencies
6. Format code according to project standards
7. Add missing test coverage for critical paths
```

**Priority Categories:**

#### Critical Priority (Level 1)
- Security vulnerabilities
- Data corruption risks
- Core functionality failures
- Production downtime

#### High Priority (Level 2)
- Test failures
- Linting violations
- Dependency security issues
- Code style inconsistencies

#### Medium Priority (Level 3)
- Documentation updates
- Code formatting
- Unused import removal
- Comment improvements

#### Low Priority (Level 4)
- Refactoring for readability
- Performance optimizations
- UI improvements
- New feature additions

### 7. Infrastructure Constraints

**Purpose:** Define environment and resource limitations

```markdown
## Infrastructure
- Environment: development
- Tools: python3, pip, pytest, flake8
- Network: localhost only
- Storage: local filesystem only
- Access: read-only external APIs allowed
```

**Infrastructure Categories:**

#### Environment Constraints
- **Operating System:** Linux/macOS only
- **Network:** No external service integration
- **Storage:** Local filesystem only
- **Access:** No cloud service integrations

#### Tool Constraints
- **Development Tools:** Only project-listed tools
- **Dependency Sources:** Only public repositories
- **Authentication:** No external credentials required

#### Resource Limits
- **Memory:** No memory restrictions specified
- **CPU:** No CPU restrictions specified
- **Storage:** Local filesystem capacity

## Contract Validation Rules

### 1. Required Sections
**Mandatory:** All contracts must include:
- Stack identification
- Health configuration
- Safe operations
- Forbidden operations

**Optional:** May include:
- Documentation links
- Maintenance priorities
- Infrastructure constraints

### 2. Format Compliance
```bash
# Valid contract example
lint_project() {
    local contract_file="$1"
    
    # Check required sections
    if ! grep -q "^## Stack$" "$contract_file"; then
        echo "ERROR: Missing Stack section"
        return 1
    fi
    
    if ! grep -q "^## Health$" "$contract_file"; then
        echo "ERROR: Missing Health section"
        return 1
    fi
    
    if ! grep -q "^## Safe Operations$" "$contract_file"; then
        echo "ERROR: Missing Safe Operations section"
        return 1
    fi
    
    if ! grep -q "^## Forbidden Operations$" "$contract_file"; then
        echo "ERROR: Missing Forbidden Operations section"
        return 1
    fi
    
    return 0
}
```

### 3. Content Validation
```bash
# Validate health commands
validate_health_commands() {
    local contract_file="$1"
    
    # Extract health section
    local health_section
    health_section=$(sed -n '/^## Health$/,/^## /p' "$contract_file")
    
    # Check for required commands
    if ! echo "$health_section" | grep -q "Lint:"; then
        echo "ERROR: Lint command missing"
        return 1
    fi
    
    if ! echo "$health_section" | grep -q "Build:"; then
        echo "ERROR: Build command missing"
        return 1
    fi
    
    if ! echo "$health_section" | grep -q "Test:"; then
        echo "ERROR: Test command missing"
        return 1
    fi
    
    return 0
}
```

### 4. Safe Operation Validation
```bash
# Validate safe operations
validate_safe_operations() {
    local contract_file="$1"
    
    # Extract safe operations section
    local safe_section
    safe_section=$(sed -n '/^## Safe Operations$/,/^## /p' "$contract_file")
    
    # Check for at least one safe operation
    if [ -z "$safe_section" ] || [ "$(echo "$safe_section" | wc -l)" -eq 0 ]; then
        echo "ERROR: No safe operations defined"
        return 1
    fi
    
    return 0
}
```

## Contract Generation Script

### Automatic Contract Creation
```bash
#!/usr/bin/env bash
# scripts/create_project_contract.sh

create_project_contract() {
    local project_dir="$1"
    
    # Detect project type
    local project_type
    project_type=$(detect_project_type "$project_dir")
    
    # Generate contract template
    cat > "${project_dir}/.team/MAINTENANCE.md" <<EOF
# Maintenance Contract - $(basename "$project_dir")

## Stack
- Language: $(get_language_from_type "$project_type")
- Build: $(get_build_command "$project_type")
- Test: $(get_test_command "$project_type")

## Health
- Lint: $(get_lint_command "$project_type")
- Build: $(get_build_command "$project_type")
- Test: $(get_test_command "$project_type")
- Type Check: $(get_type_check_command "$project_type")

## Safe Operations
$(get_safe_operations "$project_type")

## Forbidden Operations
$(get_forbidden_operations)

## Documentation
- [README.md](README.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)

## Maintenance Priorities
1. Fix critical bugs affecting core functionality
2. Ensure all tests pass with clean linting
3. Update dependencies to latest non-breaking versions
4. Improve code documentation and comments
5. Remove unused code and dependencies

## Infrastructure
- Environment: development
- Tools: $(get_tools_from_type "$project_type")
- Network: localhost only
- Storage: local filesystem only
EOF
    
    echo "[+] Created maintenance contract for $(basename "$project_dir")"
}

detect_project_type() {
    local project_dir="$1"
    
    if [ -f "$project_dir/pyproject.toml" ] || [ -f "$project_dir/setup.py" ]; then
        echo "python"
    elif [ -f "$project_dir/package.json" ]; then
        if grep -q '"type": "module"' "$project_dir/package.json"; then
            echo "typescript"
        else
            echo "javascript"
        fi
    elif [ -f "$project_dir/Makefile" ] || [ -f "$project_dir/Makefile.in" ]; then
        echo "bash"
    else
        echo "generic"
    fi
}

get_language_from_type() {
    local project_type="$1"
    
    case "$project_type" in
        "python") echo "python" ;;
        "typescript") echo "typescript" ;;
        "javascript") echo "javascript" ;;
        "bash") echo "bash" ;;
        *) echo "unknown" ;;
    esac
}

get_build_command() {
    local project_type="$1"
    
    case "$project_type" in
        "python") echo "python setup.py build" ;;
        "typescript") echo "npm run build" ;;
        "javascript") echo "npm run build" ;;
        "bash") echo "make build" ;;
        *) echo "custom build command" ;;
    esac
}

get_test_command() {
    local project_type="$1"
    
    case "$project_type" in
        "python") echo "pytest" ;;
        "typescript") echo "npm test" ;;
        "javascript") echo "npm test" ;;
        "bash") echo "bash tests/" ;;
        *) echo "custom test command" ;;
    esac
}

get_lint_command() {
    local project_type="$1"
    
    case "$project_type" in
        "python") echo "flake8 src/" ;;
        "typescript") echo "eslint ." ;;
        "javascript") echo "eslint ." ;;
        "bash") echo "shellcheck scripts/" ;;
        *) echo "custom lint command" ;;
    esac
}

get_type_check_command() {
    local project_type="$1"
    
    case "$project_type" in
        "python") echo "mypy src/" ;;
        "typescript") echo "tsc --noEmit" ;;
        "javascript") echo "tsc --noEmit" ;;
        "bash") echo "echo 'No type checking for bash projects'" ;;
        *) echo "custom type check command" ;;
    esac
}

get_safe_operations() {
    local project_type="$1"
    
    cat <<EOF
- Fix syntax errors in source files
- Remove unused imports and variables
- Format code with project formatter
- Update non-breaking dependency versions
- Fix failing tests
- Clean up temporary files
- Update documentation links
EOF
}

get_forbidden_operations() {
    cat <<EOF
- Modify architectural decisions
- Change public API contracts
- Update production configuration
- Deploy to production environments
- Modify database schemas
- Add new external service integrations
- Commit secrets or credentials
EOF
}

get_tools_from_type() {
    local project_type="$1"
    
    case "$project_type" in
        "python") echo "python3, pip, pytest, flake8, mypy" ;;
        "typescript") echo "node, npm, typescript, eslint, prettier" ;;
        "javascript") echo "node, npm, eslint, prettier" ;;
        "bash") echo "bash, shellcheck, make" ;;
        *) echo "project-specific tools" ;;
    esac
}
```

### Manual Contract Editing
```bash
# Edit existing contract
nano <project_dir>/.team/MAINTENANCE.md

# Validate contract syntax
./scripts/validate_project_contract.sh <project_dir>
```

## Contract Management Commands

### 1. Generate Contract
```bash
# Auto-generate contract for a project
./scripts/create_project_contract.sh /path/to/project

# Update contract for existing project  
./scripts/create_project_contract.sh /path/to/project --update
```

### 2. Validate Contract
```bash
# Validate contract for a project
./scripts/validate_project_contract.sh /path/to/project

# Fix common contract issues
./scripts/fix_project_contract.sh /path/to/project
```

### 3. Review Contract
```bash
# Display contract for review
cat <project_dir>/.team/MAINTENANCE.md

# Generate contract validation report
./scripts/generate_contract_report.sh <project_dir>
```

### 4. Contract Maintenance
```bash
# Update safe operations
sed -i '/^## Safe Operations$/,/^## /s/^/    /' <project_dir>/.team/MAINTENANCE.md

# Add new priority
sed -i '/^## Maintenance Priorities$/,/^$/s/^/    /' <project_dir>/.team/MAINTENANCE.md
```

## Troubleshooting

### 1. Missing Contract
```bash
# Generate contract automatically
./scripts/create_project_contract.sh /path/to/project
```

### 2. Invalid Contract
```bash
# Validate contract
./scripts/validate_project_contract.sh /path/to/project

# Fix validation errors
./scripts/fix_project_contract.sh /path/to/project
```

### 3. Contract Update
```bash
# Update contract after project changes
./scripts/create_project_contract.sh /path/to/project --update
```

## Best Practices

### 1. Contract Accuracy
- Keep commands current with project tooling
- Update after major project changes
- Test commands before adding to contract

### 2. Contract Consistency
- Follow standard format
- Use consistent naming
- Maintain documentation links

### 3. Contract Completeness
- Include all necessary operations
- Define clear boundaries
- Specify all dependencies

### 4. Contract Maintenance
- Regular contract reviews
- Update with project evolution
- Keep contracts up to date

---

*Contract Version: 1.0*
*Created: $(date -u +%Y-%m-%d)*
*Last Updated: $(date -u +%Y-%m-%d)*