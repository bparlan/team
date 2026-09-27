#!/usr/bin/env python3
"""
Context aggregator for team discussions.

This script collects and structures project state information for team member discussions.
It reads project configuration, runtime state, and produces a consistent snapshot
for all team members to reference.
"""

import os
import json
import sys
import yaml
from datetime import datetime, timezone
def load_project_config(project_root):
    """Load and validate the project configuration."""
    config_path = os.path.join(project_root, "theteam.config")
    
    if not os.path.exists(config_path):
        return None
    
    try:
        with open(config_path, 'r') as f:
            content = f.read()
        
        if config_path.endswith('.json'):
            config = json.loads(content)
        elif config_path.endswith(('.yaml', '.yml')):
            config = yaml.safe_load(content)
        elif config_path.endswith('.config'):
            # Try YAML first, then JSON if YAML fails
            try:
                config = yaml.safe_load(content)
            except (yaml.YAMLError, json.JSONDecodeError):
                config = json.loads(content)
        else:
            return None
        
        return config
    except Exception as e:
        print(f"Warning: Could not read README: {e}")
def aggregate_project_goal(project_root):
    """Extract project goal from README and other documentation."""
    goal_sources = [
        "README.md",
        "README.rst", 
        "README.txt",
        "CONTRIBUTING.md",
        "PROJECT.md",
        "ARCHITECTURE.md"
    ]
    
    for source in goal_sources:
        source_path = os.path.join(project_root, source)
        if os.path.exists(source_path):
            try:
                with open(source_path, 'r') as f:
                    content = f.read()
                
                # Extract first paragraph or first few lines
                lines = content.split('\n')
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('#') and not line.startswith('---'):
                        if len(line) > 20 and len(line) < 200:
                            return line
                
                # If no suitable line, return first few non-header lines
                non_header_lines = [line.strip() for line in lines if line.strip() and not line.startswith('#') and not line.startswith('---')]
                if non_header_lines:
                    return ' '.join(non_header_lines[:3]).strip()
                    
            except (IOError, OSError) as e:
                print(f"Error reading source file {source}: {e}")
    
    # Fallback to project name from config or directory
    config = load_project_config(project_root)
    if config and 'project' in config:
        return config['project'].get('name', os.path.basename(project_root))
    
    return "Engineering project"
def aggregate_runtime_config(project_root):
    """Extract runtime configuration from various sources."""
    runtime_config = {}
    
    # Look for common config files
    config_files = [
        "config.json",
        "config.yaml", 
        "runtime.json",
        ".env",
        "pyproject.toml",
        "package.json"
    ]
    
    for config_file in config_files:
        config_path = os.path.join(project_root, config_file)
        if os.path.exists(config_path):
            try:
                if config_file.endswith('.json'):
                    with open(config_path, 'r') as f:
                        runtime_config[config_file] = json.load(f)
                elif config_file.endswith(('.yaml', '.yml')):
                    with open(config_path, 'r') as f:
                        runtime_config[config_file] = yaml.safe_load(f)
                elif config_file == '.env':
                    with open(config_path, 'r') as f:
                        content = f.read()
                        runtime_config[config_file] = {line.split('=')[0]: line.split('=')[1] for line in content.split('\n') if '=' in line and not line.startswith('#')}
                elif config_file.endswith('.toml'):
                    with open(config_path, 'r') as f:
                        runtime_config[config_file] = str(f.read())[:1000]  # Limit length
                elif config_file.endswith('.json'):
                    with open(config_path, 'r') as f:
                        runtime_config[config_file] = json.load(f)
            except (IOError, OSError, Exception) as e:
                print(f"Error processing config file {config_file}: {e}")
    
    return runtime_config
def aggregate_token_budget(project_root):
    """Aggregate token budget state from various sources."""
    budget = {}
    
    # Look for token/budget related files
    budget_files = [
        ".token_budget",
        ".budget.json",
        ".usage.json",
        ".limits.json"
    ]
    
    for budget_file in budget_files:
        budget_path = os.path.join(project_root, budget_file)
        if os.path.exists(budget_path):
            try:
                if budget_file.endswith('.json'):
                    with open(budget_path, 'r') as f:
                        budget[budget_file] = json.load(f)
                else:
                    with open(budget_path, 'r') as f:
                        content = f.read()
                        budget[budget_file] = {"content": content[:500]}  # Limit length
            except (IOError, OSError, Exception) as e:
                print(f"Error processing file {filepath}: {e}")
    
    return budget
def aggregate_registered_structure(project_root):
    """Aggregate registered project structure."""
    structure = []
    
    try:
        # Add root directory info
        root_info = {
            "name": os.path.basename(project_root) or "project_root",
            "type": "root",
            "path": project_root,
            "has_git": os.path.exists(os.path.join(project_root, ".git")),
            "has_pyproject": os.path.exists(os.path.join(project_root, "pyproject.toml")),
            "has_setup_py": os.path.exists(os.path.join(project_root, "setup.py"))
        }
        structure.append(root_info)
        
        # Add key directories (limited depth for readability)
        important_dirs = ["src", "lib", "tests", "docs", "bin", "scripts", ".git", ".github", ".omp"]
        for dir_name in important_dirs:
            dir_path = os.path.join(project_root, dir_name)
            if os.path.exists(dir_path) and os.path.isdir(dir_path):
                try:
                    files = os.listdir(dir_path)
                    dir_info = {
                        "name": dir_name,
                        "type": "directory",
                        "path": dir_path,
                        "file_count": len(files),
                        "has_init": os.path.exists(os.path.join(dir_path, "__init__.py"))
                    }
                    structure.append(dir_info)
                except (IOError, OSError, Exception) as e:
                    print(f"Error processing file {filepath}: {e}")
                    
    except (IOError, OSError, Exception) as e:
        print(f"Error traversing directory: {e}")
    
    return structure
def aggregate_last_health_scan(project_root):
    """Aggregate last health scan information."""
    health_files = [
        "health.json",
        ".health.json",
        "scan.json",
        ".scan.json"
    ]
    
    for health_file in health_files:
        health_path = os.path.join(project_root, health_file)
        if os.path.exists(health_path):
            try:
                with open(health_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError, OSError) as e:
                print(f"Warning: Failed to load health scan {health_file}: {e}")
                continue
    
    return {}
def aggregate_production_invariants(project_root):
    """Extract production invariants from configuration and documentation."""
    invariants = {}
    
    # Look for AGENTS.md or similar documentation files
    agents_file = os.path.join(project_root, "AGENTS.md")
    if os.path.exists(agents_file):
        try:
            with open(agents_file, 'r') as f:
                content = f.read()
                # Extract rules A-F or similar patterns
                import re
                rule_patterns = [r'Rule [A-F]:[^\n]*', r'[Rr]ule [A-F][^\n]*']
                for pattern in rule_patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        invariants['agents_rules'] = matches
                        break
        except (IOError, OSError, Exception) as e:
            print(f"Warning: Failed to read AGENTS.md: {e}")
    
    # Extract from project configuration
    config = load_project_config(project_root)
    if config:
        invariants['schema_version'] = config.get('schema_version')
        invariants['behavior_settings'] = config.get('behavior', {})
    
    return invariants
def aggregate_project_context(project_root):
    """Aggregate all project context into a comprehensive snapshot."""
    context = {
        "project_goal": aggregate_project_goal(project_root),
        "runtime_config": aggregate_runtime_config(project_root),
        "token_budget": aggregate_token_budget(project_root),
        "registered_structure": aggregate_registered_structure(project_root),
        "last_health_scan": aggregate_last_health_scan(project_root),
        "production_invariants": aggregate_production_invariants(project_root),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project_root": project_root
    }
    
    return context
def main():
    """Main entry point when run as script."""
    if len(sys.argv) < 2:
        print("Usage: python3 theteam/workflow/context_aggregator.py <project_root>")
        sys.exit(1)
    
    project_root = sys.argv[1]
    context = aggregate_project_context(project_root)
    
    # Output as structured JSON
    print(json.dumps(context, indent=2))
if __name__ == "__main__":
    main()
