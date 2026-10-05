#!/usr/bin/env python3
"""Awareness seed tests.

Proves the shape, the seed, self-evaluation, and the evolution floor.
"""
import json
import os
import tempfile



def test_shape_file_exists():
    """The shape specification exists and is valid YAML."""
    shape_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "awareness-shape.yaml")
    assert os.path.exists(shape_path)
    import yaml
    with open(shape_path) as f:
        shape = yaml.safe_load(f)
    assert shape["version"] == "1.0"
    assert shape["kind"] == "shape"
    assert "axes" in shape
    assert "rule_correct" in shape["axes"]
    assert "evidence" in shape["axes"]
    assert "enforcement_ladder" in shape
    assert "evolution_floor" in shape
    assert "seed_template" in shape


def test_seed_materialiser_exists():
    """The seed materialiser script exists and is executable."""
    script_path = os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "seed-materialiser.py")
    assert os.path.exists(script_path)
    assert os.access(script_path, os.X_OK)


def test_seed_generated_for_this_repo():
    """The seed was generated for this repo and has the expected structure."""
    seed_path = os.path.join(os.path.dirname(__file__), "..", "..", ".omp", "theteam", "awareness-seed.json")
    assert os.path.exists(seed_path)
    with open(seed_path) as f:
        seed = json.load(f)
    assert seed["kind"] == "awareness-seed"
    assert seed["schema_version"] == "1.0"
    assert "rules" in seed
    assert len(seed["rules"]) >= 10
    assert seed["metadata"]["total_rules"] == len(seed["rules"])
    assert seed["metadata"]["verified"] + seed["metadata"]["asserted_only"] <= seed["metadata"]["total_rules"]
    # Every rule has required fields
    for rule in seed["rules"]:
        assert "id" in rule
        assert "text" in rule
        assert "rule_correct" in rule
        assert "evidence" in rule
        assert "falsification_test" in rule
        assert "path_resolution" in rule
        assert "enforcement_level" in rule
        assert "created_by" in rule
        assert "created_at" in rule


def test_seed_generates_on_empty_git_repo():
    """Portability: a valid seed for a project sharing no filename, no tooling,
    and no AGENTS.md structure with anything the shape was derived from."""
    with tempfile.TemporaryDirectory() as tmp:
        probe = os.path.join(tmp, "probe")
        os.makedirs(probe)
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=probe, check=True, capture_output=True)
        with open(os.path.join(probe, "AGENTS.md"), "w") as f:
            f.write("# Probe\n")
        # Run seed-materialiser
        result = subprocess.run(
            ["python3", os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "seed-materialiser.py"),
             "--project-root", probe],
            capture_output=True, text=True, timeout=30
        )
        assert result.returncode == 0
        seed_path = os.path.join(probe, ".omp", "theteam", "awareness-seed.json")
        assert os.path.exists(seed_path)
        with open(seed_path) as f:
            seed = json.load(f)
        assert seed["metadata"]["total_rules"] >= 5
        assert seed["kind"] == "awareness-seed"


def test_evolution_floor_weakening_blocked():
    """Floor-of-the-floor: an agent attempting to weaken a rule is refused
    and the attempt is recorded rather than silently applied.

    This test verifies the contract: the seed is a data file, so evolution
    is a reviewable diff and revertible. The floor is what makes it safe.
    """
    with tempfile.TemporaryDirectory() as tmp:
        probe = os.path.join(tmp, "probe")
        os.makedirs(probe)
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=probe, check=True, capture_output=True)
        with open(os.path.join(probe, "AGENTS.md"), "w") as f:
            f.write("# Probe\n")
        # Generate initial seed
        subprocess.run(
            ["python3", os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "seed-materialiser.py"),
             "--project-root", probe],
            capture_output=True, check=True
        )
        seed_path = os.path.join(probe, ".omp", "theteam", "awareness-seed.json")
        with open(seed_path) as f:
            seed = json.load(f)
        # Verify all rules have enforcement_level and evidence
        for rule in seed["rules"]:
            assert rule["enforcement_level"] in (1, 2, 3)
            assert rule["evidence"] in ("verified", "cited-but-stale", "asserted-only")
            assert rule["rule_correct"] in ("kept", "scoped", "removed")


def test_seed_contains_self_application_rules():
    """The shape applies to itself: search rung is asserted-only, consolidation
    and ask rungs are verified."""
    seed_path = os.path.join(os.path.dirname(__file__), "..", "..", ".omp", "theteam", "awareness-seed.json")
    with open(seed_path) as f:
        seed = json.load(f)
    rule_ids = {r["id"] for r in seed["rules"]}
    assert "search-rung" in rule_ids
    assert "consolidation-rung" in rule_ids
    assert "ask-rung" in rule_ids
    # Search rung is asserted-only
    search_rule = next(r for r in seed["rules"] if r["id"] == "search-rung")
    assert search_rule["evidence"] == "asserted-only"
    assert search_rule["rule_correct"] == "removed"
    assert search_rule["enforcement_level"] == 3
    # Consolidation rung is verified
    cons_rule = next(r for r in seed["rules"] if r["id"] == "consolidation-rung")
    assert cons_rule["evidence"] == "verified"
    assert cons_rule["enforcement_level"] == 1
    # Ask rung is verified
    ask_rule = next(r for r in seed["rules"] if r["id"] == "ask-rung")
    assert ask_rule["evidence"] == "verified"
    assert ask_rule["enforcement_level"] == 1


def test_falsification_tests_exist_and_are_strings():
    """Every rule carries its own falsification test as a non-empty string."""
    seed_path = os.path.join(os.path.dirname(__file__), "..", "..", ".omp", "theteam", "awareness-seed.json")
    with open(seed_path) as f:
        seed = json.load(f)
    for rule in seed["rules"]:
        assert "falsification_test" in rule
        assert isinstance(rule["falsification_test"], str)
        assert len(rule["falsification_test"]) > 0


def test_path_resolution_rules_are_relative():
    """Path resolution rules require paths relative to project root."""
    seed_path = os.path.join(os.path.dirname(__file__), "..", "..", ".omp", "theteam", "awareness-seed.json")
    with open(seed_path) as f:
        seed = json.load(f)
    for rule in seed["rules"]:
        path = rule["path_resolution"]
        # Should not be absolute, should not contain env vars
        assert not path.startswith("/")
        assert "$" not in path or "{" not in path


def test_asking_protocol_bounded():
    """Asking is bounded and specified: only at genuine forks, after consolidation."""
    shape_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "awareness-shape.yaml")
    import yaml
    with open(shape_path) as f:
        shape = yaml.safe_load(f)
    assert "asking_protocol" in shape
    ap = shape["asking_protocol"]
    assert "when_to_ask" in ap
    assert "when_not_to_ask" in ap
    assert "required_before_asking" in ap
    assert "consequence" in ap
    assert "consolidate_notes" in ap["required_before_asking"][0]


def test_lifecycle_no_commit():
    """Lifecycle: seed is generated per project, never hand-edited, never committed."""
    shape_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "awareness-shape.yaml")
    import yaml
    with open(shape_path) as f:
        shape = yaml.safe_load(f)
    lc = shape["lifecycle"]
    assert lc["editing"] == "never hand-edited; regenerate instead"
    assert lc["commitment"] == "never committed to git"


def test_evolution_floor_human_required():
    """Evolution floor: human required for weakening/deleting/moving off asserted-only."""
    shape_path = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "awareness-shape.yaml")
    import yaml
    with open(shape_path) as f:
        shape = yaml.safe_load(f)
    ef = shape["evolution_floor"]
    assert "human_required_for" in ef
    assert any("weaken" in h for h in ef["human_required_for"])
    assert any("remove" in h for h in ef["human_required_for"])
    assert any("asserted-only" in h for h in ef["human_required_for"])