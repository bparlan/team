#!/usr/bin/env python3
"""
theteam_config.py — validates and creates project-level theteam.config.

This skill bootstraps project-local team rosters and enforces strict schema
compliance. Its validation gate ensures that malformed configs never reach
production, preventing silent drift and orphaned agent states.

Schema version: 1
"""
import sys
import os
import json
try:
    import yaml
except ImportError:
    yaml = None

# `bin.utilities` is a sibling module, so it is importable only when this
# file's PARENT directory is on `sys.path`. Python puts the script's own
# directory (`bin/`) there, not the parent — so running this by absolute path
# from anywhere but the skill root raised `ModuleNotFoundError: No module
# named 'bin'`. `cd` to the skill root does not help either, because the
# script's own directory shadows the parent. Insert the parent explicitly so
# the script runs the same way regardless of who invoked it, or from where.
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

from bin.utilities import _fatal

# ======= CONFIGURATION DEFINITION =======

REQUIRED_TOP_KEYS = ["schema_version", "project", "team", "permitted_skills", "behavior", "output"]
REQUIRED_PROJECT_KEYS = ["name", "root", "description"]
REQUIRED_MEMBER_KEYS = ["id", "role", "expertise", "voice", "enabled"]
REQUIRED_BEHAVIOR_KEYS = [
    "proactive_plan_required",
    "block_edits_without_plan",
    "pre_analysis_search",
    "max_discussion_rounds",
    # Retired 2026-09-29. `option_selection_required` gated a prompt that
    # offered "Abort Discussion" and then ran the discussion to completion
    # regardless of the answer — a control that lied about its own effect,
    # which §3.3 forbids. The prompt and its three-option fallback are gone
    # from `run_discussion`. The key is still accepted, so a config written
    # against the old schema still validates; it is no longer required and
    # nothing reads it.
    "enable_persona_comments",
    "chat_mode",
    "gamification_enabled",
    "auto_summarization",
    "dynamic_interaction",
    "persona_response_variety"
]
REQUIRED_OUTPUT_KEYS = ["report_dir", "keep_last"]
SUPPORTED_SCHEMA_VERSIONS = [1]

# ======= ERROR HANDLING =======

class ConfigError(Exception):
    """Raised on any schema violation. Message is the human-readable reason."""

def _require(condition, message):
    if not condition:
        raise ConfigError(message)


def _load_yaml(path):
    """Safely load YAML."""
    if yaml is None:
        sys.stderr.write("FATAL: PyYAML not installed. Install with: pip install PyYAML\n")
        sys.exit(4)
    return yaml.safe_load(open(path, "r"))

def _load_json(path):
    """Safely load JSON."""
    return json.load(open(path, "r"))

# ======= FILE I/O =======

def load_raw(path):
    """Load and return parsed YAML/JSON from the given path."""
    if not os.path.isfile(path):
        raise ConfigError(f"Config file not found: {path}")

    try:
        # Check file content first to determine if it's YAML or JSON
        with open(path, 'r') as f:
            content = f.read()
            
        # Check if file looks like YAML (contains ':' and indentation)
        if ':' in content and ('\n' in content and content.count('\n') > 2):
            # This looks like YAML, parse it with _load_yaml
            return _load_yaml(path)
        else:
            # Try JSON first
            try:
                return _load_json(path)
            except json.JSONDecodeError:
                # If JSON fails, try YAML for any file
                return _load_yaml(path)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Failed to parse config: {e}")
    except yaml.YAMLError as e:
        raise ConfigError(f"Failed to parse config: {e}")
    except Exception as e:
        raise ConfigError(f"Failed to load config: {e}")


# ======= VALIDATION =======

def validate_config(data):
    """Validates the configuration data against the schema.

    Returns:
        tuple: (is_valid, error_message)
    """
    try:
        # Validate schema version
        if "schema_version" not in data:
            return False, "Missing 'schema_version' key"
        
        if data["schema_version"] not in SUPPORTED_SCHEMA_VERSIONS:
            return False, f"Unsupported schema_version: {data['schema_version']}. Supported: {SUPPORTED_SCHEMA_VERSIONS}"
        
        # Validate top-level structure
        for key in REQUIRED_TOP_KEYS:
            if key not in data:
                return False, f"Missing required top-level key: {key}"
        
        # Validate project structure
        if not isinstance(data.get("project"), dict):
            return False, "'project' must be a dictionary"
        
        for key in REQUIRED_PROJECT_KEYS:
            if key not in data["project"]:
                return False, f"Project missing required key: {key}"
        
        # Validate team structure
        if not isinstance(data.get("team"), list):
            return False, "'team' must be a list"
        
        for i, member in enumerate(data["team"]):
            if not isinstance(member, dict):
                return False, f"Team member {i} must be a dictionary"
            
            for key in REQUIRED_MEMBER_KEYS:
                if key not in member:
                    return False, f"Team member {i} missing required key: {key}"
        
        # Validate permitted_skills
        if not isinstance(data.get("permitted_skills"), list):
            return False, "'permitted_skills' must be a list"
        
        # Validate behavior structure
        if not isinstance(data.get("behavior"), dict):
            return False, "'behavior' must be a dictionary"
        
        for key in REQUIRED_BEHAVIOR_KEYS:
            if key not in data["behavior"]:
                return False, f"Behavior missing required key: {key}"
        
        # Validate output structure
        if not isinstance(data.get("output"), dict):
            return False, "'output' must be a dictionary"
        
        for key in REQUIRED_OUTPUT_KEYS:
            if key not in data["output"]:
                return False, f"Output missing required key: {key}"
        
        return True, "Configuration is valid"
        
    except Exception as e:
        return False, f"Unexpected validation error: {e}"


# ======= COMMAND HANDLERS =======

def cmd_validate(args):
    """Validate an existing config file."""
    if len(args) < 1:
        _fatal(1, "Usage: theteam_config.py validate <config>")
    
    config_path = args[0]
    
    try:
        # Try to load config file
        config_data = load_raw(config_path)
        
        # Validate config
        is_valid, error_message = validate_config(config_data)
        
        if is_valid:
            print(f"OK: Config is valid")
        else:
            _fatal(3, f"Validation failed: {error_message}")
            
    except ConfigError as e:
        _fatal(3, f"Validation failed: {e}")
    except Exception as e:
        _fatal(3, f"Error reading config: {e}")


def cmd_roster(args):
    """Display roster information from a config file."""
    if len(args) < 1:
        _fatal(1, "Usage: theteam_config.py roster <config>")
    
    config_path = args[0]
    
    try:
        # Try to load config file
        config_data = load_raw(config_path)
        
        # Print roster information
        print(f"Project: {config_data['project']['name']}")
        print(f"Root: {config_data['project']['root']}")
        print(f"Description: {config_data['project']['description']}")
        print(f"\nTeam Members ({len(config_data['team'])}):")
        
        for member in config_data["team"]:
            if member["enabled"]:
                print(f"  - {member['id']}: {member['role']}")
                print(f"    Expertise: {member['expertise']}")
                print(f"    Voice: {member['voice']}")
        
        print(f"\nPermitted Skills ({len(config_data['permitted_skills'])}):")
        for skill in config_data["permitted_skills"]:
            print(f"  - {skill}")
            
    except ConfigError as e:
        _fatal(3, f"Error reading config: {e}")
    except Exception as e:
        _fatal(3, f"Error reading config: {e}")


def cmd_init(args):
    """Initialize a new config file from template and user answers."""
    if len(args) < 3:
        _fatal(1, "Usage: theteam_config.py init <template> <answers> <output>")
    
    template_path = args[0]
    answers_path = args[1]
    output_path = args[2]
    
    # Load and validate template
    template_data = load_raw(template_path)
    is_valid, error_message = validate_config(template_data)
    if not is_valid:
        _fatal(1, f"Template validation failed: {error_message}")
    
    # Load and validate user answers
    answers = load_raw(answers_path)
    is_valid, error_message = validate_config(answers)
    if not is_valid:
        _fatal(1, f"Answers validation failed: {error_message}")
    
    # Merge answers into template (simple merge - could be enhanced)
    result = template_data.copy()
    
    # Apply answers to template
    if "project" in answers:
        for key in ["name", "root", "description", "stack"]:
            if key in answers["project"]:
                result["project"][key] = answers["project"][key]
    
    if "team" in answers:
        result["team"] = answers["team"]
    
    if "permitted_skills" in answers:
        result["permitted_skills"] = answers["permitted_skills"]
    
    if "behavior" in answers:
        for key in REQUIRED_BEHAVIOR_KEYS:
            if key in answers["behavior"]:
                result["behavior"][key] = answers["behavior"][key]
    
    if "output" in answers:
        for key in ["report_dir", "keep_last"]:
            if key in answers["output"]:
                result["output"][key] = answers["output"][key]
    
    # Validate final config
    is_valid, error_message = validate_config(result)
    if not is_valid:
        _fatal(1, f"Final config validation failed: {error_message}")
    
    # Write final config
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"OK: wrote valid config to {output_path}")


# ======= MAIN =======

COMMANDS = {"validate": cmd_validate, "roster": cmd_roster, "init": cmd_init}

def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        _fatal(1, f"Usage: {sys.argv[0]} <{'|'.join(COMMANDS.keys())}>")
    COMMANDS[sys.argv[1]](sys.argv[2:])


if __name__ == "__main__":
    main()

# ======= UTILITIES =======

def merge_config(template, answers):
    """Deep merge answers into template configuration."""
    if not isinstance(template, dict) or not isinstance(answers, dict):
        return answers
    
    result = template.copy()
    for key, value in answers.items():
        if key in result:
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_config(result[key], value)
            else:
                result[key] = value
        else:
            result[key] = value
    return result
