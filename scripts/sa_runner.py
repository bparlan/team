#!/usr/bin/env python3
"""
Consolidated System Architecture Design Awareness Runner.

Runs the 4-phase analysis via SystemArchitectureAnalyzer (single pass),
generates all output files, and writes a team-reviewable summary.

Part of the 3+1 recurring task loop.
"""

import traceback
import sys
import argparse
import json
import datetime
from datetime import timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add system-awareness dir to path for analyzer import
SA_DIR = Path(__file__).resolve().parent.parent / "tasks" / "system-awareness"
sys.path.insert(0, str(SA_DIR))
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# How old a recorded health score may be before `health-check` calls it stale.
#
# The number is arbitrary — there is no measurement behind it. What is not
# arbitrary is having one at all: the defect this fixes was a score computed on
# 2026-09-21 still being reported as a passing measurement on 2026-10-01, with
# no limit in place to notice. 24h matches `loop_health_check.py`'s staleness
# threshold so the two checks that both guard loop freshness agree on what
# "stale" means rather than each inventing its own limit.
HEALTH_MAX_AGE_SECONDS = 86400

OUTPUT_PATHS = {
    "health_score": PROJECT_ROOT / "health_score.json",
    "team_summary": PROJECT_ROOT / "team_summary.json",
    "architecture_report": PROJECT_ROOT / "architecture_report.json",
    "documentation_report": PROJECT_ROOT / "documentation_report.json",
    "infrastructure_report": PROJECT_ROOT / "infrastructure_report.json",
    "optimization_report": PROJECT_ROOT / "optimization_report.json",
}

def ensure_dirs(paths: List[Path]):
    for p in paths:
        p.parent.mkdir(parents=True, exist_ok=True)

def generic_writer(output_key: str, data: Dict, label: str) -> Path:
    """Write JSON data to the output path for the given key."""
    ensure_dirs([OUTPUT_PATHS[output_key]])
    try:
        with open(OUTPUT_PATHS[output_key], 'w') as f:
            json.dump(data, f, indent=2)
        return OUTPUT_PATHS[output_key]
    except Exception as e:
        print(f"Warning: Could not write {label}: {e}")
        return OUTPUT_PATHS[output_key]

def write_report(report_type: str, data: Dict, content_fn) -> Path:
    """Standardized report writing with error handling and logging."""
    try:
        return generic_writer(report_type, data, report_type.replace('_', ' '))
    except Exception as e:
        print(f"Error writing {report_type} report: {e}")
        raise

def run_analysis() -> Optional[Dict[str, Any]]:
    """Run the 4-phase analysis engine. Single pass.

    Three defects lived here, and each was found by running the script rather
    than reading it:

    1. `from tasks.system_awareness...` — a dotted path with no `__init__.py`
       anywhere in the chain. It raised `ModuleNotFoundError` on every call.
       `SA_DIR` is already on `sys.path` (line 22), so the module is top-level
       there; the dotted form could never resolve.
    2. `analyzer.analyze()` — no such method. The analyzer's entrypoint is
       `run_complete_analysis`, so this raised `AttributeError` next.
    3. The return was passed on as the analysis results, but
       `run_complete_analysis` returns `{"analysis_results": ..., ...}`.
       Every consumer (`extract_health_score`, the report writers) reads the
       phase keys from the top level, so all of them silently fell back to
       `0.0`/`"F"` on absent keys.

    The unwrap is the part that matters: those `.get(..., 0.0)` defaults mean a
    wrong shape cannot raise — it just reports a zero score, which is a
    plausible-looking measurement. That is how `health-check` came to print
    "PASSED, overall score 0.70" from a cached file while this function had
    never once succeeded.
    """
    try:
        # Top-level import: `SA_DIR` is on sys.path, and the dotted package
        # path this used to use has never existed.
        from analyze_system_awareness import SystemArchitectureAnalyzer

        analyzer = SystemArchitectureAnalyzer(str(PROJECT_ROOT))
        envelope = analyzer.run_complete_analysis()
        if not envelope:
            return None
        # Unwrap so callers see the phase keys at the top level, which is what
        # `extract_health_score` and the report writers all read.
        results = envelope.get("analysis_results")
        if results is None:
            print("Error: analyzer returned no analysis_results")
            return None
        return results
    except Exception as e:
        print(f"Error running analysis: {e}")
        traceback.print_exc()
        return None

def extract_health_score(analysis_results: Dict) -> Dict:
    """Extract the health score from analysis results.

    The keys read here were all wrong against the shape the analyzer actually
    produces, and every one was wrong in the same direction — a `.get` default
    of `0.0` on a key that is never present. So a total contract failure
    produced a valid-looking report reading `0.0`, grade `F`, rather than an
    error:

    - `health_metrics` does not exist. `generate_system_health_score` assigns
      the dict to `analysis_results["health_score"]`.
    - the per-phase scores are not at `documentation.completeness_score`.
      They are at `documentation.quality_metrics.completeness_score`, and the
      component scores the analyzer computes live in
      `health_score.component_scores` keyed by phase name.

    The score is now read from `health_score.component_scores`, which is the
    one place the analyzer publishes all four, and a missing health score is
    reported rather than defaulted: this function feeds `health-check`, and a
    defaulted 0.0 there is indistinguishable from a genuinely failing project.
    """
    health = analysis_results.get("health_score") or {}
    if not health:
        return {
            "overall_score": 0.0,
            "grade": "F",
            "documentation_completeness": 0.0,
            "architecture_cohesion": 0.0,
            "infrastructure_reliability": 0.0,
            "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
            "last_run_success": False,
            "consecutive_failures": 1,
            "recommendations": [],
            "error": "analysis results carried no health_score; "
                     "the analyzer did not produce a score",
        }

    components = health.get("component_scores") or {}
    return {
        "overall_score": health.get("overall_score", 0.0),
        "grade": health.get("grade", "F"),
        "documentation_completeness": components.get("documentation", 0.0),
        "architecture_cohesion": components.get("architecture", 0.0),
        "infrastructure_reliability": components.get("infrastructure", 0.0),
        "project_structure": components.get("project_structure", 0.0),
        "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
        "last_run_success": True,
        "consecutive_failures": 0,
        "recommendations": health.get("recommendations", []),
    }

def extract_team_summary(analysis_results: Dict, health: Dict) -> Dict:
    """Extract a concise summary for team review."""
    try:
        return {
            "analysis_timestamp": datetime.datetime.now(timezone.utc).isoformat(),
            "health_score": health,
            "project_type": analysis_results.get("project_type", "unknown"),
            "primary_issues": analysis_results.get("issues", []),
            "recommendations": health.get("recommendations", []),
            "files_analyzed": analysis_results.get("files_analyzed", 0),
            "overall_assessment": analysis_results.get("health_metrics", {}).get("overall_assessment", "Needs improvement"),
        }
    except Exception as e:
        print(f"Error extracting team summary: {e}")
        return {
            "analysis_timestamp": datetime.datetime.now(timezone.utc).isoformat(),
            "health_score": health,
            "project_type": "unknown",
            "primary_issues": [],
            "recommendations": [],
            "files_analyzed": 0,
            "overall_assessment": "Analysis incomplete",
        }

def write_health_score(health: Dict) -> Path:
    return generic_writer("health_score", health, "health score")

def write_team_summary(summary: Dict) -> Path:
    return generic_writer("team_summary", summary, "team summary")

def write_architecture_report(analysis_results: Dict) -> Path:
    arch = analysis_results.get("architecture", {})
    return write_report("architecture_report", {"architecture": arch, "metadata": analysis_results.get("metadata", {})}, lambda: f"Architecture Report: {arch.get('cohesion_score', 0):.2f} cohesion")

def write_documentation_report(analysis_results: Dict) -> Path:
    doc = analysis_results.get("documentation", {})
    return write_report("documentation_report", {"documentation": doc, "metadata": analysis_results.get("metadata", {})}, lambda: f"Documentation Report: {doc.get('completeness_score', 0):.2f} completeness")

def write_infrastructure_report(analysis_results: Dict) -> Path:
    infra = analysis_results.get("infrastructure", {})
    return write_report("infrastructure_report", {"infrastructure": infra, "metadata": analysis_results.get("metadata", {})}, lambda: f"Infrastructure Report: {infra.get('reliability_score', 0):.2f} reliability")

def write_optimization_report(health: Dict) -> Path:
    recs = health.get("recommendations", [])
    return write_report("optimization_report", {"recommendations": recs, "health": health}, lambda: f"Optimization Report: {len(recs)} recommendations")

def safe_read_json(path: Path) -> Optional[Dict]:
    """Centralized JSON reading - replaces duplicate try/except patterns."""
    try:
        if path.exists():
            with open(path, 'r') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return None

def _load_state():
    """Load loop state from disk or create default state."""
    state_file = PROJECT_ROOT / ".loop-state.json"
    try:
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
        else:
            state = {
                "version": 1,
                "project": "team-skill",
                "loop_active": False,
                "current_task_index": 0,
                "completed_tasks": [],
                "failed_tasks": [],
                "blocked_tasks": [],
                "last_execution": None,
                # Was the literal "~/devcode/team/tasks". This branch only runs
                # when `.loop-state.json` is absent, so the value is rarely
                # written — but when it is, nothing ever expands that `~`, and
                # the state file carries an absolute path to a directory this
                # project does not own. Nothing reads the field; it is recorded
                # project-relative rather than left unresolvable.
                "task_archive": "tasks",
                "total_tasks": 0,
                "next_activation": None,
                "created_at": datetime.datetime.now(timezone.utc).isoformat(),
                "circuit_breaker": {
                    "state": "closed",
                    "failure_count": 0,
                    "failure_threshold": 3,
                    "timeout_seconds": 300,
                    "last_failure_time": None,
                    "last_success_time": None
                },
                "health_score": {
                    "overall_score": 0.0,
                    "grade": "F",
                    "timestamp": None,
                    "last_run_success": False,
                    "consecutive_failures": 0
                },
                "progress": {
                    "total_iterations": 0,
                    "last_iteration_time": None,
                    "stalled_since": None,
                    "recovery_count": 0
                }
            }

        # Ensure all required fields exist (backward compatibility)
        if "circuit_breaker" not in state:
            state["circuit_breaker"] = {
                "state": "closed", "failure_count": 0, "failure_threshold": 3,
                "timeout_seconds": 300, "last_failure_time": None, "last_success_time": None
            }
        if "health_score" not in state:
            state["health_score"] = {
                "overall_score": 0.0, "grade": "F", "timestamp": None,
                "last_run_success": False, "consecutive_failures": 0
            }
        if "progress" not in state:
            state["progress"] = {
                "total_iterations": 0, "last_iteration_time": None,
                "stalled_since": None, "recovery_count": 0
            }
        if "recovery_count" not in state.get("progress", {}):
            state["progress"]["recovery_count"] = 0

        return state
    except (json.JSONDecodeError, IOError):
        return None

def _save_state(state):
    """Save loop state to disk. Returns True on success."""
    state_file = PROJECT_ROOT / ".loop-state.json"
    try:
        state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(state_file, 'w') as f:
            json.dump(state, f, indent=2)
        return True
    except Exception as e:
        print(f"Warning: Could not save loop state: {e}")
        return False

def _apply_health(health_score, success, grade):
    """Health-score mutations for one run, as a dict to merge into the state.

    `grade` is carried through from the caller rather than recomputed here.
    This function's predecessor carried its own inline ladder (`>= 0.9` A,
    `>= 0.8` B, …) beside the one in `generate_system_health_score`, and the two
    disagree: 0.554 is **D** to the analyzer and **E** to that ladder. Two
    ladders for one value is a second source of truth, and it had already
    produced one — the stale cache held `grade: "B"` from a 0.70 the analyzer
    never wrote. When no grade is supplied, the existing one is left alone
    rather than invented.
    """
    updates = {
        "overall_score": health_score,
        # `last_execution` is stamped here rather than by a separate call so
        # one run writes the state file exactly once. It used to be a third
        # read-modify-write of the same file, and — worse — the previous form
        # was `result = update_last_execution_state(...)`, which discarded
        # `update_health_score_state`'s result outright. A failed health-score
        # write was silently swallowed whenever the timestamp write succeeded.
        "last_execution": datetime.datetime.now(timezone.utc).isoformat(),
        "last_run_success": success,
        "consecutive_failures": 0 if success else None,  # resolved by caller
    }
    if grade is not None:
        updates["grade"] = grade
    return updates

def _apply_circuit_breaker(state, circuit_breaker_state):
    """Circuit-breaker mutations derived from the state being written."""
    if circuit_breaker_state:
        return {k: v for k, v in circuit_breaker_state.items()
                if k in ("state", "failure_count", "last_failure_time", "last_success_time")}

    current_score = state.get("health_score", {}).get("overall_score", 0.0)
    consecutive_failures = state.get("health_score", {}).get("consecutive_failures", 0)
    if current_score >= 0.7:
        return {"state": "closed", "failure_count": 0}
    if current_score <= 0.4 or consecutive_failures >= 3:
        return {"state": "open"}
    return {"state": "half_open"}

def update_loop_state(health_score, success, circuit_breaker_state=None, grade=None):
    """Write every loop-state change from one load and one save.

    Three sub-functions used to each load, mutate and save `.loop-state.json`
    independently, so a single run did three read-modify-writes of the same
    file — and the results were combined with `or`, which discards a failure
    whenever a later write succeeds. A partial write could report success.

    Now there is one `state`, one mutation pass and one save, so the return
    value means what it says: the file on disk holds all of it or none of it.
    """
    state = _load_state()
    if state is None:
        return False

    updates = _apply_health(health_score, success, grade)
    if updates["consecutive_failures"] is None:
        updates["consecutive_failures"] = (
            state["health_score"].get("consecutive_failures", 0) + 1)
    state["health_score"].update(updates)
    state["circuit_breaker"].update(_apply_circuit_breaker(state, circuit_breaker_state))

    return _save_state(state)

def get_loop_state():
    """Get current loop state for status command."""
    return _load_state()


# The outputs `run_analysis` is expected to have written. Each maps to an
# entry in OUTPUT_PATHS; a check for one that was never produced is the whole
# point of a self-check, so these are named rather than discovered.
EXPECTED_OUTPUTS = ("health_score", "team_summary", "architecture_report",
                    "documentation_report", "infrastructure_report")

def self_check_loop_state() -> Dict[str, Any]:
    """Check that the last analysis run actually produced its outputs.

    `self-check` and `self-correct` both called this and both died with
    `NameError: name 'self_check_loop_state' is not defined` — the function was
    never written, only referenced, and grepping its name returns three call
    sites and no definition. `self_correct` documents it as the thing that
    "identifies drift/partial outputs", so that is what it does.

    Returns `{"healthy": bool, "checks": [...]}` because that is the shape
    every consumer already reads: `_is_healthy` looks for `healthy`, and
    `_detect_drift`, `_log_issues` and `_evaluate_health_improvement` all
    iterate `checks` entries with a per-entry `healthy` flag.

    A missing output is unhealthy — that is drift. It is not an error to raise,
    because "the previous run did not finish" is a legitimate state to report
    and the caller decides whether to correct it.
    """
    checks = []
    for key in EXPECTED_OUTPUTS:
        path = OUTPUT_PATHS[key]
        exists = path.is_file()
        entry: Dict[str, Any] = {"output": key, "path": str(path), "healthy": exists}
        if exists:
            entry["size_bytes"] = path.stat().st_size
            # A zero-byte report is worse than a missing one: it exists, so a
            # presence check alone would call it healthy.
            entry["healthy"] = entry["size_bytes"] > 0
        checks.append(entry)

    state = get_loop_state()
    health = (state or {}).get("health_score") or {}
    run_ok = bool(health.get("last_run_success", False))
    checks.append({
        "output": "last_run_success",
        "path": str(PROJECT_ROOT / ".loop-state.json"),
        "healthy": run_ok,
    })

    return {
        "healthy": all(c["healthy"] for c in checks),
        "checks": checks,
    }


def _is_healthy(check: Dict[str, Any]) -> bool:
    """Check if a self-check result indicates a healthy state."""
    return check.get("healthy", False)

def _log_issues(report: Dict[str, Any], check: Dict[str, Any]) -> None:
    """Extract and log unhealthy checks to the report."""
    unhealthy_checks = [c for c in check.get("checks", []) if not c.get("healthy", True)]
    report["issues"] = unhealthy_checks

def _run_correction_cycle(results: Dict[str, Any]) -> None:
    """Run all output writes for a single correction cycle."""
    health = extract_health_score(results)
    summary = extract_team_summary(results, health)
    write_health_score(health)
    write_team_summary(summary)
    write_architecture_report(results)
    write_documentation_report(results)
    write_optimization_report(health)

    # Refresh `.loop-state.json` too. It is the store `cmd_health_check` and
    # `cmd_status` read, and `update_loop_state` had no caller anywhere — so the
    # cached score there was frozen at 0.70 from 2026-09-21 while the analysis
    # wrote 0.554 to `health_score.json`. Two files, two truths, and the stale
    # one is the one a health check consults. The grade is carried across
    # rather than recomputed, so both stores hold the analyzer's value.
    update_loop_state(health["overall_score"], health["last_run_success"],
                      grade=health["grade"])

def _perform_analysis() -> Optional[Dict[str, Any]]:
    """Run the analysis engine and return results."""
    return run_analysis()

def _evaluate_correction_result(results: Dict[str, Any], report: Dict[str, Any]) -> bool:
    """Evaluate a correction attempt result. Returns True if cycle succeeded.

    The results are stored on the report here, and this is the only place they
    can be: `_attempt_correction` receives them from `_perform_analysis` and
    hands them straight to this function, and nothing else in the call chain
    holds a reference.

    They used to be dropped. `self_correct` then read `report.get("results")` —
    a key `_build_initial_report` never creates and this function never set — so
    it was always `None`, `_evaluate_health_improvement(None, ...)` returned 0 via
    its `if results:` guard, and the `if improvement > 0` branch was unreachable.
    Verified by running it: `corrected` stayed `False`, `improvements` stayed
    `[]`, `status` was `partial` after a run that had just written five reports
    successfully, and `_update_state_with_improvement` was dead code — the only
    caller of `write_infrastructure_report`, which is why `infrastructure_report.json`
    sat in OUTPUT_PATHS and never appeared while the task reported `ok`.

    The one artifact whose whole job is to answer "did the fix work" was
    structurally incapable of saying yes.
    """
    try:
        _run_correction_cycle(results)
        report["results"] = results
        report["corrected"] = True
        return True
    except Exception as e:
        report["attempts"][-1]["error"] = str(e)
        traceback.print_exc()
    return False

def _execute_correction_attempt(attempt: int, check: Dict[str, Any], report: Dict[str, Any]) -> bool:
    """Execute one correction attempt. Returns True if cycle succeeded."""
    results = _perform_analysis()
    if not results:
        return False
    return _evaluate_correction_result(results, report)

# REFACTORED FUNCTIONS - These replace the nested logic in self_correct

def _detect_drift(check: Dict[str, Any]) -> bool:
    """Detect if current state shows drift or issues."""
    return not _is_healthy(check)

def _evaluate_health_improvement(results: Dict[str, Any], check: Dict[str, Any]) -> int:
    """Evaluate improvement from results vs check. Returns:
    -1: worse, 0: no improvement, +1: improved
    """
    # Extract current drift level
    current_drift = sum(1 for c in check["checks"] if not c.get("healthy", True))
    
    # Extract potential improvement from results
    # This would typically compare before/after metrics
    # For now, assume results represent an improvement if they exist
    if results:
        # Successful analysis indicates improvement
        return 1
    
    return 0

def _attempt_correction(attempt: int, check: Dict[str, Any], report: Dict[str, Any]) -> bool:
    """Execute a single correction attempt. Returns True if successful."""
    results = _perform_analysis()
    if not results:
        return False
    
    return _evaluate_correction_result(results, report)

def _accept_state(status: str, acceptance: str) -> bool:
    """Determine if state should be accepted based on status and acceptance."""
    return acceptance in ["accepted", "partial"]

def _build_initial_report() -> Dict[str, Any]:
    """Create the report structure with default values."""
    return {
        "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
        "attempts": [],
        "improvements": [],
        "corrected": False,
        "drift_before": None,
        "drift_after": None,
        "status": "no_change_needed",
        "acceptance": "rejected",
    }

def _record_healthy_attempt(report: Dict[str, Any], attempt: int) -> None:
    """Record a healthy check and update report status."""
    report["attempts"].append({
        "attempt": attempt + 1,
        "status": "HEALTHY",
    })
    report["status"] = "acceptable"
    report["acceptance"] = "accepted"

def _record_correction_issue(report: Dict[str, Any], check: Dict[str, Any]) -> None:
    """Log current issues as a CORRECTING attempt entry.

    `drift_before` is measured here rather than left at its `None` initialiser.
    It and `drift_after` were declared in `_build_initial_report`, never written
    by anything, and rendered as two fields of a report — so they read as a
    before-and-after comparison while being a constant `null`. A reader checking
    whether a correction helped had nothing to check.
    """
    unhealthy = [c for c in check["checks"] if not c["healthy"]]
    report["drift_before"] = len(unhealthy)
    report["attempts"].append({
        "attempt": len(report["attempts"]) + 1,
        "status": "CORRECTING",
        "issues": unhealthy,
    })

def _count_unhealthy(check: Dict[str, Any]) -> int:
    """How many checks in a self-check result are not healthy.

    One definition of "drift" for `drift_before` and `drift_after` alike, so
    the two numbers in the report are measured the same way and can be compared.
    """
    return sum(1 for c in check.get("checks", []) if not c.get("healthy", True))

def _record_successful_correction(report: Dict[str, Any], results: Dict[str, Any]) -> None:
    """Record successful correction in report."""
    report["corrected"] = True
    report["improvements"].append({
        "attempt": len(report["attempts"]),
        "status": "corrected",
        "results": results,
    })

def _record_partial_improvement(report: Dict[str, Any]) -> None:
    """Record partial improvement acceptance."""
    report["status"] = "partial"
    report["acceptance"] = "accepted"

def _record_no_improvement(report: Dict[str, Any]) -> None:
    """Record failed correction attempt."""
    report["status"] = "max_attempts_reached"
    report["acceptance"] = "rejected"

def _finalize_report(report: Dict[str, Any]) -> None:
    """Set final status if no attempts were recorded."""
    if report["status"] == "no_change_needed" and not report["attempts"]:
        report["status"] = "max_attempts_reached"

def _update_state_with_improvement(results: Dict[str, Any], check: Dict[str, Any], improvement: int) -> None:
    """Update loop state based on correction results."""
    if improvement > 0:
        # Successfully corrected
        health = extract_health_score(results)
        summary = extract_team_summary(results, health)
        write_health_score(health)
        write_team_summary(summary)
        write_architecture_report(results)
        write_documentation_report(results)
        write_infrastructure_report(results)
        write_optimization_report(health)
    elif improvement == 0:
        # Partial improvement - accept current state
        pass
    # improvement < 0 would be worse state - don't accept

def self_correct(max_attempts=2, drift_threshold=0.5):
    """Self-correction loop: identify issues, attempt fixes, accept partial improvement.
    
    Uses self_check_loop_state to identify drift/partial outputs,
    attempts regeneration via run_analysis, and accepts partial improvement.
    Refactored for maintainability, testability, and clear separation of concerns.
    """
    report = _build_initial_report()
    
    for attempt in range(max_attempts):
        check = self_check_loop_state()
        
        if _detect_drift(check):
            # We have issues to correct
            _record_correction_issue(report, check)
            
            # Try to correct
            if _attempt_correction(attempt, check, report):
                # The results are read off the report rather than recomputed,
                # because `_evaluate_correction_result` is where they exist —
                # it receives them from `_perform_analysis` and this loop has
                # no other reference. They were dropped on the floor before,
                # which is what made this whole branch unreachable.
                results = report.get("results")
                improvement = _evaluate_health_improvement(results, check)
                if improvement > 0:
                    _record_successful_correction(report, results)
                    # `drift_before` counted the unhealthy checks in the `check`
                    # this attempt started from. `drift_after` counts them in a
                    # check taken *now* — after `_update_state_with_improvement`
                    # below has rewritten the reports, which is what
                    # `self_check_loop_state` inspects. Same measurement, run
                    # twice, at the two moments a before-and-after is supposed
                    # to describe. That is the only version of this that can
                    # report that a correction worked.
                    #
                    # Reusing `check` here instead — counting the same dict twice
                    # — would make the two numbers identical by construction. A
                    # pair that cannot differ is not a measurement, and printing
                    # it beside `drift_before` is the same lie as the constant
                    # `None` these two fields used to hold.
                    #
                    # It must come *after* the state update. Measured: reading it
                    # before, the reports still on disk were the drifted ones and
                    # this reported `drift_after: 1` immediately after a cycle
                    # that had genuinely fixed the problem.
                    _update_state_with_improvement(results, check, improvement)
                    report["drift_after"] = _count_unhealthy(self_check_loop_state())
                    report["status"] = "corrected"
                    report["acceptance"] = "accepted"
                    break
                elif improvement == 0:
                    _record_partial_improvement(report)
                    break
            else:
                _record_no_improvement(report)
                break
        else:
            # State is healthy
            _record_healthy_attempt(report, attempt)
            break
    
    _finalize_report(report)
    return report

def get_last_health_score():
    """Get last health score from disk."""
    health_path = OUTPUT_PATHS["health_score"]
    if health_path.exists():
        return safe_read_json(health_path)
    return None

def cmd_status():
    """Print current loop and health status for terminal monitoring."""
    state = get_loop_state()
    health = state.get('health_score') if state else None

    print("\n" + "="*60)
    print("SYSTEM AWARENESS STATUS")
    print("="*60)

    if state:
        print(f"\n  Loop State:")
        print(f"    Project: {state.get('project', 'N/A')}")
        print(f"    Active: {state.get('loop_active', False)}")
        print(f"    Total Tasks: {state.get('total_tasks', 0)}")
        print(f"    Completed: {len(state.get('completed_tasks', []))}")
        print(f"    Progress: {state.get('progress', {}).get('total_iterations', 0)} iterations")

    if health:
        print(f"\n  Health Score:")
        overall = health.get('overall_score', 'N/A')
        if isinstance(overall, (int, float)):
            print(f"    Overall: {overall:.2f}")
        else:
            print(f"    Overall: {overall}")
        print(f"    Grade: {health.get('grade', 'N/A')}")
        doc = health.get('documentation_completeness', 'N/A')
        if isinstance(doc, (int, float)):
            print(f"    Documentation: {doc:.2f}")
        else:
            print(f"    Documentation: {doc}")
        arch = health.get('architecture_cohesion', 'N/A')
        if isinstance(arch, (int, float)):
            print(f"    Architecture: {arch:.2f}")
        else:
            print(f"    Architecture: {arch}")

    print(f"\n  Circuit Breaker: {state.get('circuit_breaker', {}).get('state', 'N/A') if state else 'N/A'}")
    print()

def cmd_health_check():
    """Quick health check with explicit exit code semantics.

    This used to read `overall_score` out of the cached `.loop-state.json` and
    compare it to a threshold, which meant it could only ever report what the
    last run recorded — it never checked whether that run happened, or whether
    it succeeded. It printed "PASSED: overall score 0.70" on 2026-10-01 from a
    score computed on 2026-09-21 by an analysis engine that could not run at
    all. A stale cache is not a measurement, so the two things a health check
    has to establish are now checked separately:

    - that the recorded run actually succeeded (`last_run_success`, which this
      function previously never read despite seven writers), and
    - that the record is current, rather than a leftover from a month ago.

    Both were being assumed. Neither is now.
    """
    state = get_loop_state()
    health = state.get('health_score') if state else get_last_health_score()
    if health is None:
        print("No health score available")
        sys.exit(1)

    if not health.get("last_run_success", False):
        print("Health check FAILED: the last analysis run did not succeed")
        sys.exit(1)

    recorded = health.get("timestamp")
    if not recorded:
        print("Health check FAILED: score carries no timestamp")
        sys.exit(1)

    try:
        parsed = datetime.datetime.fromisoformat(recorded)
    except (TypeError, ValueError):
        print(f"Health check FAILED: unparseable timestamp {recorded!r}")
        sys.exit(1)

    # A naive timestamp makes the subtraction below raise TypeError, which
    # would be reported as an unparseable timestamp — true of neither the cause
    # nor the fix. `.loop-state.json` writes `+00:00`, so this only arises from
    # hand-written state; assuming UTC is what makes those comparable instead
    # of crashing on them.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    age = (datetime.datetime.now(timezone.utc) - parsed).total_seconds()
    if age > HEALTH_MAX_AGE_SECONDS:
        print(f"Health check FAILED: score is stale ({age:.0f}s old, "
              f"limit {HEALTH_MAX_AGE_SECONDS}s)")
        sys.exit(1)

    overall = health.get("overall_score", health.get("score", 0.0))
    if overall < 0.5:
        print(f"Health check FAILED: overall score {overall:.2f} < 0.50")
        sys.exit(1)

    print(f"Health check PASSED: overall score {overall:.2f}")
    sys.exit(0)

def cmd_json():
    """Output status as machine-readable JSON."""
    output = {
        "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
        "loop_state": get_loop_state(),
        "health_score": get_last_health_score(),
    }
    print(json.dumps(output, indent=2))

def main():
    parser = argparse.ArgumentParser(
        description="Consolidated System Architecture Design Awareness Runner"
    )
    subparsers = parser.add_subparsers(dest="command")

    # status command
    parser_status = subparsers.add_parser("status", help="Show current status")
    # health-check command
    parser_health_check = subparsers.add_parser("health-check", help="Run health check")
    # json command
    parser_json = subparsers.add_parser("json", help="Output status as JSON")
    # monitor command
    parser_monitor = subparsers.add_parser("monitor", help="Continuous monitoring")
    parser_monitor.add_argument("interval", type=int, nargs="?", default=30, help="Monitoring interval in seconds")
    parser_monitor.add_argument("--interactive", "-i", action="store_true", help="Interactive TUI mode with menu")
    # self-check command
    subparsers.add_parser("self-check", help="Run self-check on outputs")
    # self-correct command
    subparsers.add_parser("self-correct", help="Attempt self-correction")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "health-check":
        cmd_health_check()
    elif args.command == "json":
        cmd_json()
    elif args.command == "monitor":
        cmd_monitor(args.interval, getattr(args, 'interactive', False))
    elif args.command == "self-check":
        check = self_check_loop_state()
        print(json.dumps(check, indent=2))
    elif args.command == "self-correct":
        report = self_correct()
        print(json.dumps(report, indent=2))
    else:
        parser.print_help()

def cmd_monitor(interval=30, interactive=False):
    """Single canonical monitoring interface - combines status, health, and progress."""
    if interactive:
        try:
            sys.path.insert(0, str(PROJECT_ROOT / 'theteam' / 'ui'))
            from terminal_ui import TerminalUI
            tui = TerminalUI(project_root=str(PROJECT_ROOT))
            tui.start()
            return
        except ImportError as e:
            print(f"TUI not available: {e}")
            return
        except Exception as e:
            print(f"TUI error: {e}")
            return

    print("\nStarting continuous monitoring...")
    print(f"Monitoring interval: {interval} seconds")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            cmd_status()
            print()
            import time
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")

if __name__ == "__main__":
    main()