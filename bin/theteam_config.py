#!/usr/bin/env python3
"""
theteam configuration system.

This module provides configuration validation, initialization, and management
for the theteam skill system.
"""

import sys
import os
import json
try:
    import yaml
except ImportError:
    yaml = None

# ======= CONFIGURATION DEFINITION =======

REQUIRED_TOP_KEYS = ["schema_version", "project", "team", "permitted_skills", "behavior", "output"]
REQUIRED_PROJECT_KEYS = ["name", "root", "description"]
REQUIRED_MEMBER_KEYS = ["id", "role", "expertise", "voice", "enabled"]

REQUIRED_BEHAVIOR_KEYS = [
    "chat_mode", "verbose", "auto_approve", "conversations", "max_iterations"
]

REQUIRED_OUTPUT_KEYS = ["report_dir", "keep_last"]

SUPPORTED_SCHEMA_VERSIONS = [1]

# ======= ERROR HANDLING =======

class ConfigError(Exception):
    """Raised on any schema violation. Message is the human-readable reason."""


def _require(condition, message):
    if not condition:
        raise ConfigError(message)


def _fatal(code, message):
    sys.stderr.write(f"FATAL: {message}\n")
    sys.exit(code)


def _load_yaml(path):
    """Safely load YAML."""
    if yaml is None:
        sys.stderr.write("FATAL: PyYAML not installed. Install with: pip install PyYAML\n")
        sys.exit(1)
    return yaml.safe_load(open(path, "r"))


# ======= FILE I/O =======

def load_raw(path):
    """Load and return parsed YAML/JSON from the given path."""
    if not os.path.isfile(path):
        raise ConfigError(f"Config file not found: {path}")
    
    try:
        if path.endswith('.yaml') or path.endswith('.yml'):
            return _load_yaml(path)
        else:
            with open(path, 'r') as f:
                return json.load(f)
    except (ValueError, OSError, json.JSONDecodeError) as e:
        raise ConfigError(f"Failed to parse config: {e}")


# ======= VALIDATION =======

def validate_config(data):
    """Raises ConfigError on the first violation found. Returns nothing."""
    # Schema version check
    _require("schema_version" in data, "Missing schema_version")
    _require(data["schema_version"] in SUPPORTED_SCHEMA_VERSIONS,
             f"Unsupported schema version: {data['schema_version']}")
    
    # Required top-level keys
    for key in REQUIRED_TOP_KEYS:
        _require(key in data, f"Missing top-level key: {key}")
    
    # Project configuration
    _require(isinstance(data["project"], dict), "project must be a dictionary")
    for key in REQUIRED_PROJECT_KEYS:
        _require(key in data["project"], f"Missing project key: {key}")
    
    # Team members
    _require(isinstance(data["team"], list), "team must be a list")
    for member in data["team"]:
        _require(isinstance(member, dict), "team member must be a dictionary")
        for key in REQUIRED_MEMBER_KEYS:
            _require(key in member, f"Missing member key: {key}")
    
    # Behavior configuration
    _require(isinstance(data["behavior"], dict), "behavior must be a dictionary")
    for key in REQUIRED_BEHAVIOR_KEYS:
        _require(key in data["behavior"], f"Missing behavior key: {key}")
    
    # Output configuration
    _require(isinstance(data["output"], dict), "output must be a dictionary")
    for key in REQUIRED_OUTPUT_KEYS:
        _require(key in data["output"], f"Missing output key: {key}")

# ======= COMMAND HANDLERS =======

def cmd_validate(args):
    """Validate an existing config file."""
    if len(args) < 1:
        _fatal(1, "Usage: theteam_config.py validate <path-to-config> [--json]")
    
    path = args[0]
    show_json = "--json" in args
    
    try:
        data = load_raw(path)
        validate_config(data)
        
        if show_json:
            print(json.dumps(data, indent=2))
        else:
            print(f"OK: {path} is valid")
            
    except ConfigError as e:
        print(f"ERROR: {e}")
        if show_json:
            print(json.dumps({"error": str(e)}))
        sys.exit(3)


def cmd_roster(args):
    """Display roster information from a config file."""
    if len(args) < 1:
        _fatal(1, "Usage: theteam_config.py roster <path-to-config> [--json]")
    
    path = args[0]
    show_json = "--json" in args
    
    try:
        data = load_raw(path)
        validate_config(data)
        
        roster = []
        for member in data["team"]:
            roster.append({
                "id": member["id"],
                "role": member["role"],
                "expertise": member["expertise"],
                "voice": member["voice"],
                "enabled": member["enabled"]
            })
        
        if show_json:
            print(json.dumps({"team": roster}, indent=2))
        else:
            print(f"Team Roster ({len(roster)} members):")
            for member in roster:
                print(f"  {member['id']}: {member['role']} - {member['expertise']}")
                
    except ConfigError as e:
        print(f"ERROR: {e}")
        sys.exit(3)


def cmd_init(args):
    """Initialize a new config file from template and user answers."""
    if len(args) < 3:
        _fatal(1,
            "Usage: theteam_config.py init <template> <answers> <output> [--json]")
    
    template_path = args[0]
    answers_path = args[1]
    output_path = args[2]
    show_json = "--json" in args
    
    try:
        # Load template
        template = load_raw(template_path)
        
        # Load answers
        with open(answers_path, 'r') as f:
            answers = json.load(f)
        
        # Merge template with answers
        config = template.copy()
        
        # Apply answers
        for key, value in answers.items():
            if key in config:
                config[key] = value
            else:
                # Create nested structure if needed
                keys = key.split('.')
                target = config
                for k in keys[:-1]:
                    if k not in target:
                        target[k] = {}
                    target = target[k]
                target[keys[-1]] = value
        
        # Validate
        validate_config(config)
        
        # Write output
        with open(output_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        if show_json:
            print(json.dumps(config, indent=2))
        else:
            print(f"OK: wrote valid config to {output_path}")
            
    except Exception as e:
        if show_json:
            print(json.dumps({"error": str(e)}))
        else:
            print(f"ERROR: {e}")
        sys.exit(2)

# Analyze functions command - detect declared vs implemented
def cmd_analyze_functions(args):
    """Analyze Python functions for declarations vs implementations"""
    project_root = os.getcwd()
    if args and args[0] == '--path' and len(args) >= 2:
        project_root = args[1]
        args = args[2:]
    
    # Import and run the function analyzer
    sys.path.insert(0, os.path.join(project_root, 'scripts'))
    from function_check import FunctionAnalyzer
    
    analyzer = FunctionAnalyzer(project_root)
    report = analyzer.analyze_functions()
    
    summary = report['summary']
    print(f"Function Analysis Summary:")
    print(f"  Total declared: {summary['total_functions_declared']}")
    print(f"  Total implemented: {summary['total_functions_implemented']}")
    print(f"  Unimplemented: {summary['unimplemented_functions']}")
    print(f"  Stub functions: {summary['stub_functions']}")
    print(f"  Implementation rate: {summary['implementation_rate']}")
    
    if summary['unimplemented_functions'] > 0:
        print(f"\nUnimplemented functions:")
        for func in report['unimplemented_functions'][:10]:
            print(f"  - {func['name']}() in {func['path']}:{func['line']}")
    
    if summary['stub_functions'] > 0:
        print(f"\nStub functions:")
        for func in report['stub_functions'][:10]:
            print(f"  - {func['name']}() in {func['path']}")
    
    # Save report for theteam system
    report_path = os.path.join(project_root, '.loop-log', 'function-analysis-report.json')
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nReport saved to: {report_path}")

# ======= MAIN =======

COMMANDS = {
    "validate": cmd_validate,
    "roster": cmd_roster,
    "init": cmd_init,
    "analyze-functions": cmd_analyze_functions
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        _fatal(1, f"Usage: {sys.argv[0]} <{'|'.join(COMMANDS.keys())}>")
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()
