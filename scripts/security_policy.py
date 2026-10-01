#!/usr/bin/env python3
"""
Security policy validator for theteam skill.

Validates task definitions against security rules before execution.
Blocks destructive commands, warns on secret access, and enforces isolation.
"""

import os
import re
import yaml
import sys
from pathlib import Path

# Resolved from this file, not from $PWD: a task script can be invoked
# from anywhere, and the hardcoded developer-home path this replaced
# resolved to a home directory on every machine that was not that one.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

class SecurityPolicy:
    """Validates tasks against security policy rules."""
    
    def __init__(self, policy_file=None):
        if policy_file is None:
            # Look for policy file in task archive
            archive_dir = os.path.join(PROJECT_ROOT, "tasks")
            policy_file = os.path.join(archive_dir, "SECURITY_POLICY.yaml")
        
        self.policy_file = policy_file
        self.rules = self._load_policy()
    
    def _load_policy(self):
        """Load security policy from YAML file."""
        if not os.path.exists(self.policy_file):
            return self._default_policy()
        
        try:
            with open(self.policy_file, 'r') as f:
                policy = yaml.safe_load(f)
                return policy.get('rules', [])
        except (yaml.YAMLError, IOError):
            return self._default_policy()
    
    def _default_policy(self):
        """Return default security policy."""
        return [
            {
                "name": "no-destructive-commands",
                "pattern": "rm -rf|sudo|chmod 777|dd if=|mkfs",
                "action": "block",
                "severity": "critical"
            },
            {
                "name": "no-secret-access",
                "pattern": r"\.env|credentials|secrets|id_rsa",
                "action": "warn",
                "severity": "high"
            },
            {
                "name": "require-isolation",
                "pattern": "task.*--isolated",
                "action": "require",
                "severity": "medium"
            },
            {
                "name": "max-execution-time",
                "value": 300,
                "action": "timeout",
                "severity": "medium"
            }
        ]
    
    def validate_task(self, task):
        """Validate a task against security policy rules."""
        violations = []
        
        # Check execution commands
        execution = task.get('execution', '')
        for rule in self.rules:
            if 'pattern' not in rule:
                continue
            
            pattern = rule['pattern']
            action = rule.get('action', 'warn')
            severity = rule.get('severity', 'medium')
            
            if re.search(pattern, execution, re.IGNORECASE):
                violation = {
                    "rule": rule['name'],
                    "pattern": pattern,
                    "action": action,
                    "severity": severity,
                    "message": f"Security rule '{rule['name']}' triggered"
                }
                violations.append(violation)
        
        return violations
    
    def is_blocked(self, task):
        """Check if task should be blocked based on security policy."""
        violations = self.validate_task(task)
        
        for violation in violations:
            if violation['action'] == 'block':
                return True, violation
        
        return False, None
    
    def get_warnings(self, task):
        """Get security warnings for a task."""
        violations = self.validate_task(task)
        warnings = []
        
        for violation in violations:
            if violation['action'] == 'warn':
                warnings.append(violation)
        
        return warnings
    
    def get_max_execution_time(self):
        """Get maximum allowed execution time in seconds."""
        for rule in self.rules:
            if rule['name'] == 'max-execution-time' and 'value' in rule:
                return rule['value']
        return 300  # default 5 minutes

def main():
    """Main entry point for security policy."""
    policy = SecurityPolicy()
    
    if len(sys.argv) < 2:
        print("Usage: security_policy.py <command> [args]")
        print("Commands: validate <task-file>, check <task-name>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "validate":
        if len(sys.argv) < 3:
            print("Usage: security_policy.py validate <task-file>")
            sys.exit(1)
        
        task_file = sys.argv[2]
        with open(task_file, 'r') as f:
            content = f.read()
        
        # Simple task parsing
        task = {"name": os.path.basename(task_file)[5:-3], "execution": content}
        violations = policy.validate_task(task)
        
        if violations:
            print(f"Security violations found: {len(violations)}")
            for v in violations:
                print(f"  - {v['rule']}: {v['message']} (severity: {v['severity']})")
        else:
            print("No security violations found")
    
    elif command == "check":
        if len(sys.argv) < 3:
            print("Usage: security_policy.py check <task-name>")
            sys.exit(1)
        
        task_name = sys.argv[2]
        task_file = os.path.join(PROJECT_ROOT, "tasks", f"task-{task_name}.md")
        
        if not os.path.exists(task_file):
            print(f"Task file not found: {task_file}")
            sys.exit(1)
        
        with open(task_file, 'r') as f:
            content = f.read()
        
        task = {"name": task_name, "execution": content}
        blocked, violation = policy.is_blocked(task)
        
        if blocked:
            print(f"BLOCKED: {violation['message']}")
            sys.exit(1)
        else:
            warnings = policy.get_warnings(task)
            if warnings:
                print(f"Warnings: {len(warnings)}")
                for w in warnings:
                    print(f"  - {w['rule']}: {w['message']}")
            else:
                print("Task is safe to execute")
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)

if __name__ == "__main__":
    main()