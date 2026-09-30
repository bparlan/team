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
                "task_archive": "~/devcode/team/tasks",
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

def update_health_score_state(health_score, success):
    """Update only health score fields in loop state."""
    state = _load_state()
    if state is None:
        return False

    state["health_score"].update({
        "overall_score": health_score,
        "grade": "A" if health_score >= 0.9 else "B" if health_score >= 0.8 else "C" if health_score >= 0.7 else "D" if health_score >= 0.6 else "E" if health_score >= 0.5 else "F",
        "timestamp": datetime.datetime.now(timezone.utc).isoformat(),
        "last_run_success": success,
        "consecutive_failures": 0 if success else state["health_score"].get("consecutive_failures", 0) + 1
    })

    return _save_state(state)

def update_circuit_breaker_state(circuit_breaker_state=None):
    """Update only circuit breaker fields in loop state."""
    state = _load_state()
    if state is None:
        return False

    cb = state["circuit_breaker"]

    if circuit_breaker_state:
        # Override with explicit values
        if "state" in circuit_breaker_state:
            cb["state"] = circuit_breaker_state["state"]
        if "failure_count" in circuit_breaker_state:
            cb["failure_count"] = circuit_breaker_state["failure_count"]
        if "last_failure_time" in circuit_breaker_state:
            cb["last_failure_time"] = circuit_breaker_state["last_failure_time"]
        if "last_success_time" in circuit_breaker_state:
            cb["last_success_time"] = circuit_breaker_state["last_success_time"]
    else:
        # Compute state from health_score and success tracking
        hs = state.get("health_score", {})
        current_score = hs.get("overall_score", 0.0)
        consecutive_failures = hs.get("consecutive_failures", 0)

        # Health-driven state transitions
        if current_score >= 0.7:  # A-C grade
            cb["state"] = "closed"
            cb["failure_count"] = 0
        elif current_score <= 0.4 or consecutive_failures >= 3:  # D-F grade or too many failures
            cb["state"] = "open"
        else:  # B grade - test recovery
            cb["state"] = "half_open"

    return _save_state(state)

def update_loop_state(health_score, success, circuit_breaker_state=None):
    """Update loop state by delegating to focused sub-functions."""
    result = update_health_score_state(health_score, success)
    result = update_circuit_breaker_state(circuit_breaker_state) or result
    return result

def get_loop_state():
    """Get current loop state for status command."""
    return _load_state()

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
    write_infrastructure_report(results)
    write_optimization_report(health)

def _perform_analysis() -> Optional[Dict[str, Any]]:
    """Run the analysis engine and return results."""
    return run_analysis()

def _evaluate_correction_result(results: Dict[str, Any], report: Dict[str, Any]) -> bool:
    """Evaluate a correction attempt result. Returns True if cycle succeeded."""
    try:
        _run_correction_cycle(results)
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
    """Log current issues as a CORRECTING attempt entry."""
    report["attempts"].append({
        "attempt": len(report["attempts"]) + 1,
        "status": "CORRECTING",
        "issues": [c for c in check["checks"] if not c["healthy"]],
    })

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
                # Correction successful - evaluate improvement
                improvement = _evaluate_health_improvement(report.get("results"), check)
                if improvement > 0:
                    _record_successful_correction(report, report.get("results"))
                    _update_state_with_improvement(report.get("results"), check, improvement)
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
    """Quick health check with explicit exit code semantics."""
    state = get_loop_state()
    health = state.get('health_score') if state else get_last_health_score()
    if health is None:
        print("No health score available")
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