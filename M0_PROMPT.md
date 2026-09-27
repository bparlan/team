# OMP Prompt — Milestone M0: The Team Cannot Lie

Copy everything below the rule into a fresh OMP session started at `/Users/bparlan/devcode/team`.

---

## PROMPT START

You are implementing **Milestone M0** of the `theteam` project at `/Users/bparlan/devcode/team`. Work in this repository.

### Read this first, in this order

1. `ARCHITECTURE.md` — the single source of truth. Read the header, then Part 3 (Trust and Failure Modes), then §6 M0 (lines ~356-402). Do not read the other parts yet; they describe milestones that do not exist yet.
2. `/Users/bparlan/.omp/agent/AGENTS.md` and `/Users/bparlan/devcode/team/AGENTS.md` — the project rules. Both apply. The project one is stricter and wins on conflict.
3. The two diagrams, if you want the rendered shape: `diagrams/active-usage-architecture.html` and `diagrams/active-usage-milestones.html`. They are supplementary. If they disagree with `ARCHITECTURE.md`, `ARCHITECTURE.md` wins.

### Context you need

`theteam` is an OhMyPi skill that runs a panel of expert reviewers over your work. Its core was stabilized across 5 phases with 613 passing tests. The usability work has not started.

Your job is M0, and M0 is **pure deletion**. There is no new feature. Do not add one.

`theteam/__init__.py` currently defines a class `MockAPI` that fabricates team opinions. Every member gets `"Insight from {id}: System appears stable after fixes."` and every user choice gets `{"next_action": "proceed_with_plan"}`. When OhMyPi does not inject a `default_api` provider, the module silently binds `MockAPI` instead.

This is the most dangerous defect in the codebase. It is a consensus tool returning fake consensus, indistinguishable from a real answer until someone acts on it.

### What to do

**Step 1 — verify the current state before changing anything.**

Run these and record the actual output:

```bash
cd /Users/bparlan/devcode/team
grep -rn "MockAPI" theteam/ --include="*.py"
grep -rn "default_api" theteam/ --include="*.py"
grep -rn "run_task_loop\|task_archive" theteam/ --include="*.py"
python3 -c "import theteam; print('IMPORT OK — no error')"
```

That last command currently prints a fabricated result rather than failing. That is the defect. Note what it prints.

Also establish the test baseline:

```bash
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -20
```

Note the exact pass/fail count. If the suite is already failing, stop and report that before making any change. Do not fix a pre-existing failure inside M0 — report it.

### Step 2 — replace the fallback with a hard failure, at the point of use

In `theteam/__init__.py`:

- Delete the `MockAPI` class entirely (currently lines 4-18).
- Delete the `try/except NameError` block that binds `default_api = MockAPI()` (currently lines 20-25).
- Delete the orphaned trailing comment `# Mocking default_api for local execution if not available` at the end of the file (currently line 868 — it is a duplicate of the comment at line 3).
- Define a single named error so a caller with no provider fails with an explanation instead of silently degrading:

```python
class ProviderUnavailable(RuntimeError):
    """No OMP task provider is bound.

    This module will not fabricate team opinions. Run inside an OMP
    session so a task provider is injected, then retry.
    """
```

- Add a helper that checks the provider and raises:

```python
def _require_provider():
    """Refuse to fabricate team opinions when no OMP provider is bound."""
    if "default_api" not in globals():
        raise ProviderUnavailable(
            "theteam requires an OMP session. Run this inside OMP, "
            "or import it from an OMP-hosted agent."
        )
```

- Call it as the **first statement** of `run_discussion`, before the state manager and before config loading:

```python
def run_discussion(project_root, topic):
    """Run a team discussion on a specific topic with actual task spawning."""
    _require_provider()
    state_manager = get_state_manager(...)
    ...
```

This guard belongs at the point of use, not at module scope. Two reasons:

1. **A module-scope raise kills the test suite.** 28 test files import `theteam` for its safety components — `UnifiedLoop`, `CircuitBreaker`, `ResourceLimiter`, `AgentIsolation`, `AuditLogger`, `EventBus` — not for discussion. A raise at import time turns 584 passing tests into 0 collection errors. The requirement is that a *caller* with no provider raises, and `run_discussion` is that caller.
2. **The guard must run before config loading.** `run_discussion` calls `load_config` and prints "Failed to load config" before reaching any `default_api` site. If the guard is placed after config load, the function returns `False` and the guard never fires.

All five `default_api` call sites live inside `run_discussion`, so one entry guard covers every path. The existing call sites stay as they are — with the guard in place they are unreachable outside OMP. Do not rewrite them.

**Step 3 — delete the orphaned scripts and dead files.**
Verified to have zero importers under `theteam/`:

```bash
rm scripts/run_task_loop.py scripts/task_archive.py
rm theteam/core/event_bus.py.backup
rm theteam/core/loop_manager.py.bak
rm theteam/core/rate_limiting.py.bak
rm theteam/tests/test_state_validator.py.backup
rm test_final_validation.py.backup
rm test_unified_loop.py.backup
rmdir theteam/ui/web_dashboard/.web.backup
```

Before running each `rm`, run `grep -rn "<basename>" theteam/ --include="*.py"` and confirm it returns nothing. If any of these has a live importer, **stop and report it** rather than deleting a working file. An archived copy exists in git history if that becomes necessary.

Note: `theteam/__init__.py.corrupted` does not exist. Do not try to delete it. It was named in an earlier draft and has since been removed.

**Step 4 — archive the stale diagrams.**

The 12 pre-existing diagram JSONs are already moved to `diagrams/archive/`. Confirm they are there:

```bash
ls diagrams/archive/ | wc -l    # expect 12
ls diagrams/                    # expect only the 2 active diagrams + archive/
```

Delete the stale rendered HTML if any remain alongside the current diagrams:

```bash
cd diagrams && rm -f architecture-candidate.html lifecycle-candidate.html workflow-candidate.html
```

Leave `active-usage-architecture.html` and `active-usage-milestones.html` alone. They are the current source of truth for rendered shape.

**Step 5 — verify.**

Run all of these and show the actual output of each:

```bash
- Note the exact pass/fail count. If the suite is already failing, stop and report that before making any change. Do not fix a pre-existing failure inside M0 — report it.

- Also record: does `import theteam` succeed or fail? What does it print? That is the defect — currently it prints a fabricated result rather than failing.
# 1. No fabricator remains
grep -rn "MockAPI" theteam/ --include="*.py"          # expect: no output

# 2. No orphaned importers
grep -rn "run_task_loop\|task_archive" theteam/ --include="*.py"   # expect: no output

# 3. Import succeeds, and the discussion path raises
python3 -c "import theteam; print('IMPORT OK')" 2>&1 | tail -2
python3 -c "import theteam; theteam.run_discussion('/tmp/x','t')" 2>&1 | grep -E "ProviderUnavailable|requires an OMP" | head -2
# expect: IMPORT OK, then ProviderUnavailable naming the OMP requirement.
# NOT a fabricated result. Import must succeed — many test files import this
# module for its safety components, and a raise at import time kills them all.
# 4. The module still parses and its symbols still exist
python3 -c "import ast,sys; ast.parse(open('theteam/__init__.py').read()); print('PARSE OK')"

# 5. The suite is no worse than baseline
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -20
```

On check 5, read the result honestly:

- If the count **matches** the baseline you recorded in Step 1 — good.
- If tests **fail** because a test asserted on `MockAPI` output — that test was asserting on a fabrication. Remove or rewrite that specific test, and **state plainly in your summary that it was asserting on invented output.** That is worth reporting; it is evidence about the suite, not a chore.
- If tests fail for any other reason, do not "fix" it by weakening the test or restoring the fallback. Report the failure and stop.

**Step 6 — confirm you did not break the task system.**
```python
python3 -c "
from theteam.subskills.task_stack.orchestrator import TaskStackOrchestrator
o = TaskStackOrchestrator()
print('orchestrator OK')
print('registered:', len(o.list_tasks()))
" 2>&1 | tail -5
```

If the orchestrator imports cleanly and reports its 4 registered tasks, M0 is contained. Report the actual result. The class is `TaskStackOrchestrator` and the method is `list_tasks()` — if your import fails with a different name, grep the module for the real class rather than guessing.

### Constraints

- **M0 only.** Do not create `cli.py`, do not repoint `pyproject.toml`, do not touch the state directories, do not convert tasks to YAML, do not start M1. Those are M1 and later and they depend on review of this commit.
- **Do not fix unrelated problems.** This repository has four hardcoded absolute paths, a split state directory, and a broken console script. All real, all out of scope. Leave them.
- **Do not fix a test to make broken code pass.** If a test disagrees with the new behavior, first decide which one is wrong, and say which and why.
- **Do not create planning documents.** `AGENTS.md` bans them. `ARCHITECTURE.md` is the plan. Do not add `*.md` files.
- **Do not create orphaned files.** Every module you touch must be imported by something.
- **Do not weaken the guard.** The `ProviderUnavailable` raise is the deliverable. A fallback, a default, or a try/except around it defeats the entire milestone.
- **Do not mark a checkbox** or claim completion without showing the command output that proves it.

### Deliverable

A single commit, self-contained and revertable, containing only M0 changes.

Your summary is **at most 3 lines**, per `AGENTS.md`. Then, separately, report:

1. The exact test count before and after.
2. Whether any test was asserting on `MockAPI` output, and what you did about it.
3. Anything you found that contradicted `ARCHITECTURE.md`'s description of M0 — report the discrepancy, do not silently accommodate it.

If you hit something that makes M0 impossible to complete safely, stop and report that instead of improvising. A blocked M0 with a clear explanation is more useful than a completed one with a hidden defect.

