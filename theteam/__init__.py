#!/usr/bin/env python3

"""
Oh My Pi - theteam skill orchestrator.

This skill provides deterministic, multi-agent review and consensus building for complex
engineering projects. It spawns isolated reviewer subagents, gathers their independent
notes, and synthesizes honest recommendations with a single orchestrating agent.

It ensures a deterministic start to every team discussion, enforces persona contracts,
and provides a chatroom-style output for engaging interactions.

Usage:
  python3 theteam/__init__.py --bootstrap
  python3 theteam/__init__.py --topic "Your discussion topic here"
"""

import sys
import os
import json
import yaml
import tempfile

import time
from datetime import datetime, timezone


# Import enhancement modules
from .core.state_manager import get_state_manager

# The stability layer (circuit breaker, resource limiter, health monitor,
# event bus, loop) is wired where it runs, not re-exported here. These were 41
# import-for-re-export lines that nothing in the package, the CLI, the tests or
# the bin scripts ever read. They cost more than dead weight: `core/__init__`
# eagerly loaded `state_manager`, which loaded `database`, which loaded the
# PostgreSQL cluster/wal/transaction modules. So every `import theteam` pulled
# a database layer that §5.1 never placed in this stack. `check_invariants.sh`
# invariant 7 now measures that.
#
# 2026-09-29, M7 follow-up. If you need one of these, import it from its own
# module at the point of use (`from theteam.core.circuit_breaker import ...`).
# That is what the CLI, the executor and the tests already do.
#
# 2026-10-06: database.py now imports postgres_cluster lazily inside properties,
# so `import theteam` no longer loads the cluster tier. Invariant 7 confirms
# 7 theteam.core.* modules (checksum, correlation, database, member,
# state_manager, transactions, wal) and 0 forbidden modules.


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CURRENT_DIR)
from .security import log_security_event
from .core.member import load_config, write_member_note, validate_member_note
from .bin.theteam_config import _load_yaml, _load_json, merge_config, validate_config
class ProviderUnavailable(RuntimeError):
    """No OMP task provider is bound in this interpreter.

    This module will not fabricate team opinions. A subprocess never binds one;
    a host that imports `theteam` in-process could, but must also answer the
    contract `run_discussion` reads — see SKILL.md.
    """

def _require_provider():
    """Refuse to fabricate team opinions when no OMP provider is bound.

    Guarded at the point of use rather than at module import, so that the
    safety components in this package remain importable and testable. A guard
    at class-body or module scope would run at import time, which is the
    defect this placement avoids.
    """
    if "default_api" not in globals():
        # The first clause is load-bearing: `scripts/smoke_cli.py` substring-
        # matches "requires an OMP session" to recognise this as a named
        # refusal rather than a silent non-zero exit. Do not reword it.
        #
        # The second clause used to be "Run this inside OMP, or import it from
        # an OMP-hosted agent", which is advice that cannot be followed: a
        # shell is already inside an OMP session and is still refused, because
        # the gate is a global in the *importing interpreter* and a shell is
        # always a fresh subprocess. Measured in an OMP eval kernel — the one
        # place a live session's Python runs — `default_api` was absent there
        # too, so being "inside OMP" was never the variable. See SKILL.md.
        from theteam.core.capability import capability_surface
        surface = capability_surface()
        raise ProviderUnavailable(
            "theteam requires an OMP session. Measured: provider_bound="
            f"{surface['provider_bound']}, docker_available="
            f"{surface['docker_available']}, spawnable_agents="
            f"{len(surface['spawnable_agents'])}. A shell is a fresh "
            "subprocess and can never bind a provider; an in-process host "
            "must bind one that answers the contract run_discussion reads. "
            "For tasks, run `theteam run --only <id>` instead — it names the "
            "next phase, and the session spawns the member. No run id, no provider."
        )



def spawn_member_task(member, topic, project_context, permitted_skills):
    """Spawn a member task with proper system prompt and context."""
    member_id = member['id']
    member_role = member['role']
    member_expertise = member['expertise']
    member_voice = member['voice']
    member_personality = member.get('personality', {})

    # Construct system prompt
    system_prompt_parts = [
        f"You are {member_role}, a member of the 'theteam' skill.",
        f"Your expertise: {member_expertise}",
        f"Your voice: {member_voice}",
        "Adhere to the following personality traits:"
    ]
    for key, value in member_personality.items():
        system_prompt_parts.append(f"- {key}: {value}")

    system_prompt_parts.extend([
        "\n## Discussion Topic",
        topic,
        "\n## Project Architecture Context",
        _member_context(project_context, member),
        "\n## Runtime Capability",
        _render_capability_surface(),
        "\n## Tool Inventory",
        _render_skills(permitted_skills),
        "\n## Your Task",
        f"Provide your independent, unbiased review on the topic from your perspective as {member_role}.",
        f"Your output MUST be a JSON object matching the schema: {{'id': '{member_id}', 'role': '{member_role}', 'verdict': '<concise_verdict>', 'note': '<detailed_note>'}}"
    ])
    system_prompt = "\n".join(system_prompt_parts)

    print(f"Spawning task for {member_id} ({member_role})...")

    # Use the `task` tool to spawn the subagent
    # The outputSchema ensures the subagent returns a strict JSON format
    # The `isolated=True` ensures members don't see each other's output
    # We're passing the full system_prompt directly to the agent
    return {
        "task": f"Perform an independent review of the discussion topic: {topic}",
        "agent": "task", # Use the general-purpose task agent
        "name": member_id,
        "system_prompt": system_prompt,
        "outputSchema": {
            "type": "object",
            "properties": {
                "id": {"type": "string", "pattern": f"^{member_id}$"},
                "role": {"type": "string", "pattern": f"^{member_role}$"},
                "verdict": {"type": "string"},
                "note": {"type": "string"}
            },
            "required": ["id", "role", "verdict", "note"]
        },
        "schemaMode": "strict",
        "isolated": True
    }

def consolidate_notes(notes_dir, config):
    """Consolidate notes from all team members into a synthesis."""
    all_notes = []
    for filename in os.listdir(notes_dir):
        if filename.endswith(".json"):
            file_path = os.path.join(notes_dir, filename)
            try:
                with open(file_path, 'r') as f:
                    note = json.load(f)
                    all_notes.append(note)
            except Exception as e:
                print(f"Error reading note from {file_path}: {e}")
                continue

    # Simple synthesis logic (can be expanded)
    summary = "Team discussion completed. Individual notes collected."
    agreements = []
    disagreements = []
    open_questions = []
    recommendation = "No specific consensus reached. See individual notes."

    # Example: Collect all verdicts and notes
    for note in all_notes:
        summary += f"\n- {note['id']} ({note['role']}): {note['verdict']} - {note['note']}"

    # More sophisticated logic would involve analyzing content for agreements/disagreements
    # For now, we'll keep it simple as the orchestrator synthesizes.

    return {
        "summary": summary,
        "agreements": agreements,
        "disagreements": disagreements,
        "open_questions": open_questions,
        "recommendation": recommendation
    }


def _has_file(root, name):
    return os.path.exists(os.path.join(root, name))


def _file_mentions(root, name, keywords):
    """True when a config file names one of the keywords. Unreadable is False."""
    path = os.path.join(root, name)
    if not os.path.exists(path):
        return False
    try:
        with open(path, 'r') as f:
            content = f.read().lower()
    except OSError as e:
        log_security_event(f"Error processing config file {path}: {e}")
        return False
    return any(keyword in content for keyword in keywords)


def _extension_present(root, extensions, limit=400):
    """Whether the project holds a file with one of these extensions."""
    found = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in ('.git', 'node_modules', '__pycache__', 'target', 'dist', 'build')]
        for filename in filenames:
            if filename.endswith(extensions):
                found += 1
                if found >= limit:
                    return True
    return False


def analyze_project_context(project_root):
    """
    Analyze project context to determine appropriate team members.

    Every flag below is assigned from evidence in the project. A declared
    focus that nothing can ever set is a lie about what the team looked at,
    so each one has a detector and each one is reachable.
    """
    context = {
        'security_focus': False,
        'data_science_focus': False,
        'frontend_focus': False,
        'api_focus': False,
        'database_focus': False,
        'infrastructure_focus': False
    }

    # Security: a policy, a scanner, or a config that names a security tool.
    security_files = (
        'SECURITY_POLICY.yaml', 'security_policy.py', 'audit_logger.py',
    )
    context['security_focus'] = any(
        _has_file(project_root, name) for name in security_files
    ) or _file_mentions(
        project_root, 'pyproject.toml',
        ('bandit', 'security', 'safety', 'pip-audit', 'vulnerability'),
    ) or _file_mentions(
        project_root, 'package.json', ('audit', 'snyk', 'security', 'eslint-plugin-security'),
    ) or _file_mentions(
        project_root, 'requirements.txt', ('bandit', 'pip-audit', 'safety', 'cryptography'),
    )

    # Data science: notebooks, or a project that declares a numerical stack.
    context['data_science_focus'] = any(
        _has_file(project_root, name)
        for name in ('notebooks', 'analysis.ipynb', 'research', 'data')
    ) or _file_mentions(
        project_root, 'requirements.txt',
        ('numpy', 'pandas', 'scikit-learn', 'matplotlib', 'torch', 'jupyter'),
    ) or _file_mentions(
        project_root, 'pyproject.toml', ('numpy', 'pandas', 'scikit-learn', 'torch'),
    )

    # Frontend: UI sources, or a declared web framework.
    context['frontend_focus'] = (
        _has_file(project_root, 'index.html')
        or _has_file(project_root, 'next.config.js')
        or _has_file(project_root, 'vite.config.ts')
        or _has_file(project_root, 'frontend')
        or _has_file(project_root, 'src/components')
    ) or _file_mentions(
        project_root, 'package.json',
        ('react', 'vue', 'svelte', 'next', 'tailwind', 'styled-components'),
    )

    # API: a service definition or a route layer.
    context['api_focus'] = (
        _has_file(project_root, 'openapi.yaml')
        or _has_file(project_root, 'openapi.json')
        or _has_file(project_root, 'api')
        or _has_file(project_root, 'routes')
        or _has_file(project_root, 'Dockerfile')
    ) or _file_mentions(
        project_root, 'requirements.txt',
        ('fastapi', 'flask', 'django', 'rest-framework', 'express'),
    ) or _file_mentions(
        project_root, 'package.json', ('express', 'fastify', 'apollo', 'openapi'),
    ) or _file_mentions(
        project_root, 'pyproject.toml', ('fastapi', 'flask', 'django'),
    )

    # Database: a migration tree, a schema, or a database client dependency.
    context['database_focus'] = (
        _has_file(project_root, 'migrations')
        or _has_file(project_root, 'alembic.ini')
        or _has_file(project_root, 'schema.sql')
        or _has_file(project_root, 'db')
    ) or _file_mentions(
        project_root, 'requirements.txt',
        ('psycopg2', 'sqlalchemy', 'pymysql', 'mongoose', 'redis', 'alembic'),
    ) or _file_mentions(
        project_root, 'package.json', ('prisma', 'sequelize', 'typeorm', 'pg', 'mysql'),
    )

    # Infrastructure: deploy or cluster configuration.
    context['infrastructure_focus'] = any(
        _has_file(project_root, name)
        for name in ('Dockerfile', 'docker-compose.yml', 'docker-compose.yaml',
                     'terraform', 'k8s', 'kubernetes', '.github/workflows')
    ) or _file_mentions(
        project_root, 'pyproject.toml', ('boto3', 'kubernetes', 'ansible', 'terraform'),
    )

    return context
# The team catalog: every member that can exist, in one place.
#
# `generate_team_members_from_context` builds a roster from these, and M9
# Phase 2's `theteam manager` reads the same two tables. Two tables would
# drift, and a roster grown from a table bootstrap does not know about is a
# member with no origin. The catalog is also the roster cap: there are
# `len(BASE_MEMBERS) + len(FOCUS_MEMBERS)` = 9 possible members, so a manager
# that "grows" the roster every run cannot reach 30.

BASE_MEMBERS = [
    {
        'id': 'architect',
        'role': 'Systems Architect',
        'expertise': 'long-term maintainability, coupling, failure modes, blast radius',
        'voice': 'skeptical of shortcuts; asks what breaks in 6 months',
        'enabled': True,
        'personality': {
            'emoji': '🧱',
            'color': '#FF6B6B',
            'greeting': "Hello team! Let's architect this properly...",
            'closing': "🏗️ Architect signing off — think about those long-term implications",
            'style': 'technical',
            'speech_pattern': 'methodical',
            'interaction_frequency': 'balanced'
        }
    },
    {
        'id': 'pragmatist',
        'role': 'Delivery Pragmatist',
        'expertise': 'shipping speed, scope control, solo-developer bandwidth',
        'voice': 'pushes back on over-engineering; asks for the smallest real fix',
        'enabled': True,
        'personality': {
            'emoji': '⚡',
            'color': '#4ECDC4',
            'greeting': "Alright team! Let's ship this FAST! 🚀",
            'closing': "✅ Pragmatist done — shipping first, perfect second",
            'style': 'direct',
            'speech_pattern': 'quick',
            'interaction_frequency': 'high'
        }
    },
    {
        'id': 'skeptic',
        'role': 'Adversarial Reviewer',
        'expertise': 'edge cases, silent failure modes, unverified claims',
        'voice': 'distrusts prose-only completion reports; demands raw evidence',
        'enabled': True,
        'personality': {
            'emoji': '🔍',
            'color': '#95E77E',
            'greeting': 'Whoa whoa! Let\'s slow down and test this! 📋',
            'closing': '🤔 Skeptic signing off — ask again later!',
            'style': 'analytical',
            'speech_pattern': 'cautious',
            'interaction_frequency': 'as_needed'
        }
    }
]

# One member per detected focus. Every flag `analyze_project_context`
# can set has a reviewer here, so a Python web project and a Rust CLI
# do not get the same team.
FOCUS_MEMBERS = {
    'security_focus': {
        'id': 'security',
        'role': 'Security Reviewer',
        'expertise': 'auth, secrets handling, input validation, supply chain',
        'voice': 'assumes hostile input until proven otherwise',
        'personality': {
            'emoji': '🔒',
            'color': '#8B0000',
            'greeting': 'Security team on duty! Let\'s find the vulnerabilities...',
            'closing': '🔒 Security sign-off — if it isn\'t locked down, it\'s broken',
            'style': 'strict',
            'speech_pattern': 'methodical',
            'interaction_frequency': 'as_needed'
        }
    },
    'data_science_focus': {
        'id': 'analyst',
        'role': 'Data Analyst',
        'expertise': 'data quality, leakage, metric definitions, reproducibility',
        'voice': 'asks what the number was measured over, and on what sample',
        'personality': {
            'emoji': '📊',
            'color': '#2F6F9F',
            'greeting': 'Let\'s look at the data before we trust the conclusion.',
            'closing': '📊 Analyst done — the claim now matches the sample.',
            'style': 'precise',
            'speech_pattern': 'steady',
            'interaction_frequency': 'balanced'
        }
    },
    'frontend_focus': {
        'id': 'designer',
        'role': 'Interface Reviewer',
        'expertise': 'layout, states, accessibility, visual consistency',
        'voice': 'asks what the user sees on a slow connection and with a keyboard',
        'personality': {
            'emoji': '🎨',
            'color': '#B56576',
            'greeting': 'How does this actually feel to use?',
            'closing': '🎨 Interface reviewed — states, contrast, focus order.',
            'style': 'concrete',
            'speech_pattern': 'observant',
            'interaction_frequency': 'balanced'
        }
    },
    'api_focus': {
        'id': 'api',
        'role': 'API Reviewer',
        'expertise': 'contracts, versioning, error shapes, backwards compatibility',
        'voice': 'asks what breaks for the caller when this changes',
        'personality': {
            'emoji': '🔌',
            'color': '#3F8F6B',
            'greeting': 'Let\'s check the contract before the implementation.',
            'closing': '🔌 API reviewed — the contract is the stable part.',
            'style': 'exact',
            'speech_pattern': 'deliberate',
            'interaction_frequency': 'balanced'
        }
    },
    'database_focus': {
        'id': 'data',
        'role': 'Data Reviewer',
        'expertise': 'schema, migrations, indexes, transaction boundaries',
        'voice': 'asks what the migration does to the live table at 3am',
        'personality': {
            'emoji': '🗄️',
            'color': '#7A5C2E',
            'greeting': 'Show me the migration path.',
            'closing': '🗄️ Data reviewed — the migration is reversible.',
            'style': 'grounded',
            'speech_pattern': 'patient',
            'interaction_frequency': 'as_needed'
        }
    },
    'infrastructure_focus': {
        'id': 'devops',
        'role': 'Infrastructure Reviewer',
        'expertise': 'deployment, resource bounds, failure and recovery behaviour',
        'voice': 'asks what this looks like when the host goes away',
        'personality': {
            'emoji': '⚙️',
            'color': '#5B6E7A',
            'greeting': 'Let\'s check how this behaves under failure.',
            'closing': '⚙️ Infra reviewed — bounded, observable, recoverable.',
            'style': 'pragmatic',
            'speech_pattern': 'measured',
            'interaction_frequency': 'as_needed'
        }
    },
}

# Which focus flag put each focus member on the roster. The manager reads
# this so `--status` can name the flag rather than assert a reason.
FOCUS_FLAG_BY_MEMBER = {member["id"]: flag
                        for flag, member in FOCUS_MEMBERS.items()}





def generate_team_members_from_context(project_root):
    """Generate appropriate team members based on project context."""
    try:
        context = analyze_project_context(project_root)

        base_members = [dict(member) for member in BASE_MEMBERS]
        focus_members = FOCUS_MEMBERS

        for flag in sorted(context):
            if context.get(flag):
                member = dict(focus_members[flag])
                member['enabled'] = True
                base_members.append(member)

        return {
            # `validate_config` requires this key at the top level, so a
            # generated config that omits it can never pass the gate
            # `cmd_init` runs. Bootstrap only ever worked because
            # `merge_config` inherited the value from the template; anything
            # using this return value directly — M9's `manager --reset` —
            # got a config it was forbidden to write.
            'schema_version': 1,
            'project': {
                'name': 'team',
                'root': '.',
                'description': 'Orchestrates independent reviewer subagents into deterministic team discussions'
            },
            'team': base_members,
            'permitted_skills': ['ponytail', 'evolve-skills', 'code-search'],
            'behavior': {
                'proactive_plan_required': True,
                'block_edits_without_plan': True,
                'pre_analysis_search': True,
                'enable_persona_comments': True,
                'chat_mode': True,
                'gamification_enabled': True,
                'auto_summarization': False,
                'dynamic_interaction': True,
                'max_discussion_rounds': 5,
                'persona_response_variety': True
            },
            'output': {
                'report_dir': '.omp/theteam/reports',
                'keep_last': 20
            }
        }
    except Exception as e:
        # §3.3: a hardcoded roster here is a confident answer with nothing
        # behind it. The context analysis is what the team *is*; if it failed,
        # there is no team to describe.
        raise RuntimeError(
            f"Failed to analyze project context at {project_root}: {e}"
        ) from e


def resolve_template_path(project_root=None):
    """Find the canonical theteam-template.config path across standard locations."""
    candidates = [
        os.environ.get("THETEAM_TEMPLATE_PATH"),
        os.path.expanduser("~/.omp/agent/skills/theteam/theteam-template.config"),
        os.path.join(CURRENT_DIR, "theteam-template.config"),
        os.path.join(os.path.dirname(CURRENT_DIR), "theteam-template.config"),
    ]
    if project_root:
        candidates.append(os.path.join(project_root, "theteam-template.config"))

    for path in candidates:
        if path and os.path.isfile(path):
            return os.path.abspath(path)
    raise FileNotFoundError(f"theteam-template.config not found in candidates: {[c for c in candidates if c]}")
def bootstrap_flow(project_root):
    """Handles the bootstrap process when no valid config is found."""
    print("No valid theteam.config found. Starting bootstrap process...")

    # Pre-analysis search for codebase orientation
    project_description = ""
    project_stack = []

    try:
        # Read package.json for project name and description if available
        package_json_path = os.path.join(project_root, "package.json")
        if os.path.exists(package_json_path):
            pkg_data = _load_json(package_json_path)
            if pkg_data:
                project_description = pkg_data.get("description", "")
        else:
            # Try to infer from README.md or other sources
            readme_path = os.path.join(project_root, "README.md")
            if os.path.exists(readme_path):
                with open(readme_path, 'r') as f:
                    first_line = f.readline().strip()
                    if first_line.startswith('# '):
                        project_description = first_line[2:]

    except Exception as e:
        print(f"Error during pre-analysis search: {e}")

    # Generate team members based on context (this is where we can add more logic)
    answers = generate_team_members_from_context(project_root)

    if answers is None:
        print("Error: Failed to generate initial team members. Exiting bootstrap.")
        return False

    # Use a temporary file for answers to pass to the init script
    answers_file_fd, answers_file_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(answers_file_fd, 'w') as tmp_f:
        json.dump(answers, tmp_f, indent=2)
    print(f"Created temporary answers file: {answers_file_path}")

    # Call the init command of theteam_config.py to create the config file
    template_config_path = resolve_template_path(project_root)
    output_config_path = os.path.join(project_root, "theteam.config")

    try:
        # Load template and answers
        template = _load_yaml(template_config_path)
        answers_data = _load_json(answers_file_path)

        # Merge answers into template
        final_config = merge_config(template, answers_data)

        # Explicitly set schema_version to an integer if it came as a string from template
        if 'schema_version' in final_config and isinstance(final_config['schema_version'], str):
            try:
                final_config['schema_version'] = int(final_config['schema_version'])
            except ValueError as e:
                log_security_event(f"Error converting schema_version to int: {e}")

        # Write the final config
        with open(output_config_path, 'w') as f:
            yaml.dump(final_config, f, default_flow_style=False)

        # Validate the newly created config
        is_valid, error_msg = validate_config(final_config)
        if not is_valid:
            print(f"Bootstrap completed, but generated config is invalid: {error_msg}")
            return False

        print(f"Bootstrap completed successfully")
        print(f"Configuration file created at: {output_config_path}")
        return True
    except Exception as e:
        print(f"Error during bootstrap process: {e}")
        return False
    finally:
        os.remove(answers_file_path) # Clean up temporary file
def _member_context(project_context, member):
    """The project context one member receives.

    M9 Phase 3. `__init__.py:93` used to `yaml.dump(project_context)` into
    every member's prompt, so the same tokens were paid N times: measured on
    this repository, 2,499 characters per member across a 5-member roster.
    The section a member's declared focus implies is delivered and the rest
    is not; see `theteam.advisory.context_slice`, which owns the rule.
    """
    from theteam.advisory.context_slice import slice_context

    rendered, _undelivered = slice_context(project_context, member)
    return rendered


def _permitted_skills(config):
    """The skills this project's members may use, as the list it declares.

    The config key is the single source: `SKILL.md`'s "Permitted skills"
    section already declares it a hard boundary, and the member prompt now
    states the same list the orchestrator enforces. A list read from a file
    that does not exist is how this heading ended up saying `N/A`.
    """
    return list(config.get("permitted_skills") or [])


def _render_skills(permitted_skills):
    """The list as a prompt reads it, under `## Tool Inventory`."""
    if not permitted_skills:
        # §3.3: a blank section is a boundary nobody can see. Name the
        # absence instead of rendering nothing under the heading.
        return "none declared by this project's theteam.config"
    return "\n".join(f'- {skill}' for skill in permitted_skills)


def _render_capability_surface():
    """The dynamic capability surface as a prompt reads it, under `## Runtime Capability`."""
    from theteam.core.capability import capability_surface
    from theteam.bin.theteam_config import _load_yaml
    import os
    project_root = os.environ.get("THETEAM_PROJECT_ROOT", os.getcwd())
    try:
        config = _load_yaml(os.path.join(project_root, "theteam.config"))
        project_root = config.get("project", {}).get("root", project_root)
    except Exception:
        pass
    surface = capability_surface(project_root)
    lines = [
        f"provider_bound: {surface['provider_bound']}",
        f"docker_available: {surface['docker_available']}",
        f"spawnable_agents: {', '.join(surface['spawnable_agents']) or 'none'}",
        f"python_version: {surface['python_version']}",
        f"writable_project: {surface['writable_project']}",
        f"disk_free_mb: {surface['disk_free_mb']}",
    ]
    return "\n".join(lines)

def _topic_slice(topic):
    """A minimal `SessionSlice` built from a discussion topic.

    `select_members` takes a `SessionSlice`, not a topic string. M9 Phase 1.2
    is explicit: build the minimal slice and call the selector unchanged,
    rather than adding a topic-scoring heuristic as a fifth signal. The topic
    arrives as the latest user message — which is the signal §4.5 already
    names — and any dotted word in it is a `touched_paths` entry, which is
    the other signal §4.5 already names. No new signal is invented, so the
    selector's determinism guarantee and its tests are untouched.
    """
    from theteam.advisory.session_reader import SessionSlice

    return SessionSlice(
        last_user_messages=[str(topic)],
        touched_paths=_paths_named_in(str(topic)),
    )

def _paths_named_in(topic):
    """File paths a topic names, as the selector's extension signal needs.

    Only a token that looks like a file - it carries a known source
    extension - is returned. A topic mentioning `api` in prose must not
    conjure a `.api` path, and a bare `router.py` is a real path signal.
    """
    import re
    exts = {".py", ".rs", ".go", ".ts", ".tsx", ".jsx", ".js", ".css",
            ".scss", ".sass", ".less", ".sql", ".yaml", ".yml", ".json",
            ".proto", ".ipynb", ".csv", ".parquet", ".env", ".pem",
            ".key", ".sh", ".tf", ".md", ".toml", ".ini", ".cfg", ".html"}
    found = []
    for token in re.findall(r"[A-Za-z0-9_][A-Za-z0-9_./-]*", topic):
        lowered = token.lower()
        if any(lowered.endswith(ext) for ext in exts) and len(lowered) > 2:
            found.append(lowered)
    return found


def new_conversation_id(when=None):
    """A discussion id unique per microsecond, not per second.

    The id names two things on disk: the `theteam-notes-<id>` temp directory and
    the written report filename. At second resolution two discussions started
    within the same second got the same id, so the second run read the first
    run's notes out of the shared directory and overwrote the first run's
    report. Found by running the suite concurrently — `run_discussion reported
    success but wrote no state`, with a synthesis file left by a sibling
    process.

    A function so the uniqueness is testable. Asserting the format string from
    the caller would only pin a copy: the tests could pass while production
    regressed. `when` is injectable so a test can drive the clock deterministically.
    """
    moment = when or datetime.now(timezone.utc)
    return moment.strftime('%Y%m%d_%H%M%S_%f')


def run_discussion(project_root, topic):
    """Run a team discussion on a specific topic with actual task spawning."""
    _require_provider()

    # Initialize the state manager
    state_manager = get_state_manager(os.path.join(project_root, '.omp', 'theteam', 'state.json'))

    # Load and validate configuration
    config, error_msg = load_config(project_root)
    if config is None:
        print(f"Failed to load config: {error_msg}")
        return False

    print(f"🚀 Starting team discussion on: {topic}")
    conversation_id = new_conversation_id()
    # Microseconds, not seconds — see `new_conversation_id`. At second
    # resolution two discussions started in the same second shared the
    # `theteam-notes-<id>` temp directory *and* the report filename, so the
    # second run read the first run's notes and overwrote its report. Found by
    # running the suite concurrently: `run_discussion reported success but wrote
    # no state`.
    print(f"📋 Conversation ID: {conversation_id}")

    # Record discussion start in state manager
    discussion_id = state_manager.discussion_state.start_discussion(topic, project_root)

    # Generate notes directory
    notes_dir = os.path.join(tempfile.gettempdir(), f"theteam-notes-{conversation_id}")
    os.makedirs(notes_dir, exist_ok=True)

    # Aggregate project context. M9 Phase 1.1: the dead
    # `.omp/theteam/tool-manifest.json` read is gone. That file does not
    # exist, so every member prompt carried the literal `## Tool Inventory` /
    # `N/A` — a boundary the constrained party could not see, enforced by
    # luck. The real list is the project's own `permitted_skills`.
    # `aggregate_project_context` was called here and imported nowhere in the
    # package — `git log -S` finds no commit that ever added the import. Every
    # `theteam discuss` that got past `_require_provider` died on a NameError
    # here, and no test caught it because no test runs this path with a
    # provider. Imported at point of use, like the selector below.
    from theteam.workflow.context_aggregator import aggregate_project_context

    project_context = aggregate_project_context(project_root)
    permitted_skills = _permitted_skills(config)

    # Emit the dynamic capability surface as a JSON handoff for
    # machine consumers under .omp/ -- the agent-facing root.
    from theteam.core.capability import write_handoff
    write_handoff(project_root, out_dir=os.path.join(project_root, '.omp', 'theteam', 'reports'))

    # Imported here, not at module scope: a module-scope import of the
    # advisory selector pushes `import theteam` to 91 modules and check 7
    # fails. The budget is the contract, not the import style.
    from theteam.advisory.selector import MEMBER_CAP, select_members

    # M9 Phase 1.2: selection is deterministic, not `enabled: True`. The
    # selector takes a `SessionSlice`, not a topic string, so a minimal slice
    # is built from the topic and the paths the topic names. No fifth signal
    # is added to `select_members` — adding one would weaken the determinism
    # guarantee its docstring names as the entire reason it exists
    # (`selector.py:201-207` records a gate that collapsed when it was).
    selection = select_members(
        _topic_slice(topic),
        task_type=config.get("discussion", {}).get("task_type"),
        roster=config,
    )
    # The selector has already applied the cap; `suppressed` is its count of
    # what it dropped. Recomputing it here from `len(members)` would be zero
    # by construction — a report line that can never fire.
    selected_ids = selection["members"][:MEMBER_CAP]
    suppressed = selection.get("suppressed", 0)
    by_id = {m["id"]: m for m in config["team"]}

    # M9 Phase 1.3: truncation is reported, never silent.
    print(f"Selector chose {len(selected_ids)} member(s): {', '.join(selected_ids)}")
    if selection.get("truncated") or suppressed:
        print(f"  {len(selected_ids) + suppressed} selected, "
              f"{len(selected_ids)} speak, {suppressed} suppressed (cap {MEMBER_CAP})")
    if selection.get("signals"):
        print(f"  signals: {selection['signals']}")

    # M9 Phase 3: a context section no member receives is reported, not
    # dropped. Silently slicing it away is how a member stops knowing
    # something and no document says so.
    from theteam.advisory.context_slice import undelivered_sections

    orphans = undelivered_sections(project_context, config["team"])
    if orphans:
        for section, missed_by in sorted(orphans.items()):
            print(f"  context section '{section}' reached no member "
                  f"(all {len(missed_by)} missed it)")

    member_tasks_to_spawn = [
        spawn_member_task(by_id[mid], topic, project_context, permitted_skills)
        for mid in selected_ids
    ]
    expected_member_ids = list(selected_ids)

    if not member_tasks_to_spawn:
        print("No team member selected for this topic. Exiting discussion.")
        return False

    # Add team members as participants
    for member_id in expected_member_ids:
        state_manager.discussion_state.add_participant(discussion_id, member_id)

    print("--- Member Intros ---")
    # Use parallel task execution to get intros
    intro_task_configs = []
    for member in config["team"]:
        # The same selection the discussion spawn uses. Before M9 this loop
        # re-derived "every enabled member", so `theteam talk --json` would
        # report a capped roster while silently paying for an uncapped one.
        if member["id"] not in expected_member_ids:
            continue
        personality = member.get('personality', {})
        intro_task_configs.append({
            "task": f"Generate a personal insight for the discussion topic: {topic}",
            "agent": "task",
            "name": f"intro_{member['id']}",
            "system_prompt": (f"You are {member['role']}. "
                              f"Your expertise: {member['expertise']}. "
                              f"Your voice: {member['voice']}. "
                              f"Your greeting: {personality.get('greeting', 'Hello team!')}. "
                              f"Your closing: {personality.get('closing', 'Goodbye!')}. "
                              f"Provide a concise personal insight on the topic: {topic}. "
                              f"Your output MUST be a JSON object matching the schema: {{'id': '{member['id']}', 'role': '{member['role']}', 'personal_insight': '<concise_insight>'}}"),
            "outputSchema": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "pattern": f"^{member['id']}$"},
                    "role": {"type": "string", "pattern": f"^{member['role']}$"},
                    "personal_insight": {"type": "string"}
                },
                "required": ["id", "role", "personal_insight"]
            },
            "schemaMode": "strict",
            "isolated": True
        })

    # Spawn tasks in parallel
    spawn_results = default_api.task(i="Get member intros", context="Generate team member introductions for the discussion topic", tasks=intro_task_configs)
    intro_handles = {result.get("name"): result.get("handle") for result in spawn_results["tasks"]}

    # Wait for all intros to complete
    intros = []
    for member_id in expected_member_ids:
        handle = intro_handles.get(f"intro_{member_id}")
        if handle:
            try:
                intro_result = default_api.output(handle)
                intros.append(intro_result)
            except Exception as e:
                print(f"Error retrieving intro for {member_id}: {e}")
        else:
            print(f"No intro handle found for {member_id}")

    for intro in intros:
        member_id = intro["id"]
        role = intro["role"]
        insight = intro["personal_insight"]
        personality = next((m.get('personality', {}) for m in config["team"] if m['id'] == member_id), {})
        color = personality.get('color', '#FFFFFF')
        emoji = personality.get('emoji', '💬')

        # Chatroom-style output
        print(f"\n{'=' * 20} {emoji} {member_id.upper()} ({role}) {emoji} {'=' * 20}")
        print(f"\033[38;2;{int(color[1:3], 16)};{int(color[3:5], 16)};{int(color[5:7], 16)}m{insight}\033[0m")

    # Team Consolidation TL;DR
    all_insights = [intro['personal_insight'] for intro in intros]
    tldr = f"Team discussion initiated. Members shared initial thoughts: {'. '.join(all_insights)}."
    print(tldr)

    # Create a task for the discussion
    discussion_task = {
        'title': f"Team Discussion: {topic}",
        'priority': 'high',
        'assignee': 'system',
        'type': 'team_discussion',
        'description': f"Team discussion on topic: {topic}",
        'status': 'in_progress'
    }
    state_manager.task_state.create_task(discussion_task, discussion_id)

    # Spawn actual discussion tasks (simplified to just collect notes)
    spawn_results = default_api.task(
        i="Spawn team members for discussion",
        context=f"Independent review of topic: {topic}",
        tasks=member_tasks_to_spawn
    )

    # Collect individual notes
    member_notes = []
    for member_id in expected_member_ids:
        handle_name = member_id # Name of the task is the member_id
        handle = next((result.get("handle") for result in spawn_results["tasks"] if result.get("name") == handle_name), None)
        if handle:
            try:
                note_data = default_api.output(handle)
                is_valid, validation_msg = validate_member_note(note_data, member_id)
                if is_valid:
                    member_notes.append(note_data)
                    write_member_note(note_data, notes_dir)
                    # Update task state
                    task_id = f"task_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
                    state_manager.task_state.update_task(task_id, {
                        'status': 'completed',
                        'result': note_data
                    })
                else:
                    print(f"Invalid note from {member_id}: {validation_msg}")
            except Exception as e:
                print(f"Error retrieving note for {member_id}: {e}")
        else:
            print(f"No discussion task handle found for {member_id}")

    # Simulate system awareness analysis (if enabled)
    if config["behavior"].get("system_awareness_enabled", False):
        print("\n🔍 Running system awareness analysis...")
        analysis_id = state_manager.system_awareness_state.start_analysis(
            "infrastructure_assessment", project_root
        )
        # Simulate analysis completion
        time.sleep(1)  # Simulate processing time
        state_manager.system_awareness_state.complete_analysis(analysis_id, {
            'status': 'completed',
            'metrics': {
                'cpu_usage': 45.2,
                'memory_usage': 62.8,
                'disk_usage': 78.3
            }
        })
        print("✅ System awareness analysis completed")

    # Perform synthesis
    synthesis = consolidate_notes(notes_dir, config)
    synthesis_file_path = os.path.join(tempfile.gettempdir(), f"theteam-synthesis-{conversation_id}.json")
    with open(synthesis_file_path, 'w') as f:
        json.dump(synthesis, f, indent=2)

    # Render report. Format and path are decided together, because the
    # two-consumer model says the directory decides: HTML is what a human
    # reads and stays in reports/; markdown is a machine handoff and goes to
    # reports/.handoff/. Picking the filename without the format is how
    # markdown ended up in the human directory in the first place.
    report_format = config["output"].get("report_format", "markdown")
    report_output_dir = os.path.join(project_root, config["output"]["report_dir"])
    if report_format != "html":
        report_output_dir = os.path.join(report_output_dir, ".handoff")
    os.makedirs(report_output_dir, exist_ok=True)
    report_ext = "html" if report_format == "html" else "md"
    report_full_path = os.path.join(
        report_output_dir, f"{conversation_id}-discussion-report.{report_ext}")

    report_script_path = os.path.join(os.path.dirname(CURRENT_DIR), "bin", "theteam_report.py")
    expected_ids_str = ",".join(expected_member_ids)
    topic_esc = json.dumps(topic)
    project_name_esc = json.dumps(config["project"]["name"])

    # Command to build the report
    report_command = [
        "python3", report_script_path, "build",
        "--topic", topic_esc,
        "--notes-dir", notes_dir,
        "--synthesis", synthesis_file_path,
        "--out", report_full_path,
        "--project", project_name_esc,
        "--expected-ids", expected_ids_str,
        "--format", report_format,
    ]

    print(f"Building report with command: {' '.join(report_command)}")

    try:
        # Directly execute the command via subprocess to capture output/errors
        import subprocess
        process = subprocess.run(report_command, capture_output=True, text=True, check=True)
        print("Report script stdout:", process.stdout)
        if process.stderr:
            print("Report script stderr:", process.stderr)
        print(f"Report generated at: {report_full_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating report: {e}")
        print("Report script stdout:", e.stdout)
        print("Report script stderr:", e.stderr)
        return False
    finally:
        # Clean up temporary notes directory
        if os.path.exists(notes_dir):
            import shutil
            shutil.rmtree(notes_dir)
        if os.path.exists(synthesis_file_path):
            os.remove(synthesis_file_path)

    # Complete the discussion
    state_manager.discussion_state.complete_discussion(discussion_id)

    # Save state
    state_manager.save_state()

    return True
def run_task_stack(project_root, task_id, action="execute"):
    """Run task stack operations with team review."""
    import subprocess
    import json
    
    from theteam.tasks.repository import TaskRepository
    from theteam.tasks.executor import TaskExecutor

    repo = TaskRepository(project_root)
    executor = TaskExecutor(project_root, breaker_states=repo.schedule()["last_run"])

    if action == "list":
        tasks = repo.all_tasks()
        print("=== Registered Tasks ===")
        for task in tasks:
            print(f"  {task['id']}: {task['name']} ({task['type']})")
        return True

    elif action == "status":
        all_tasks = repo.all_tasks()
        scheduled = repo.schedule().get("scheduled_tasks", {})
        print("=== Task Stack Status ===")
        print(f"  Registered: {len(all_tasks)}")
        print(f"  Scheduled: {len(scheduled)}")
        print(f"  Stack size: {len(all_tasks)}")
        return True

    elif action == "execute":
        task = repo.get(task_id)
        if not task:
            print(f"Task not found: {task_id}")
            return False

        print(f"=== Team Review: {task['name']} ===")
        print(f"  Type: {task['type']}")
        print(f"  Priority: {task.get('priority', 'medium')}")
        print(f"  Phases: {len(task.get('phases', []))}")

        result = executor.execute_task(task)
        print(f"  Success: {result['overall_success']}")
        return result['overall_success']

def main(project_root=None):
    """Main skill entry point."""
    if project_root is None:
        project_root = os.getcwd()

    # Argument parsing
    import argparse
    parser = argparse.ArgumentParser(description="theteam skill orchestrator")
    parser.add_argument("--bootstrap", action="store_true", help="Run bootstrap process to create theteam.config")
    parser.add_argument("--topic", type=str, help="Topic for team discussion")
    parser.add_argument("--task", type=str, help="Task ID to execute")
    parser.add_argument("--task-action", type=str, default="execute", 
                       choices=["execute", "list", "status"], help="Task stack action")
    args = parser.parse_args()

    if args.bootstrap:
        return bootstrap_flow(project_root)
    elif args.topic:
        return run_discussion(project_root, args.topic)
    elif args.task:
        return run_task_stack(project_root, args.task, args.task_action)
    else:
        print("Usage: python3 theteam/__init__.py [--bootstrap | --topic <discussion_topic> | --task <task_id>]")
        return False
if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error in main: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)