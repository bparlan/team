#!/usr/bin/env python3
"""
Check that every task in `tasks/` is one the executor can actually run.

Six tasks audit content -- files, docs, features. None audits the task
registry, which is the layer that drives all of them. The cost is concrete:
`scripts/sa_runner.py` declares six outputs and writes two, and nothing
noticed. That is not a judgement call, so it does not need an LLM to find.

Every check here is mechanical. A check that needs interpretation belongs in
`doc-truth`, which audits prose against code; this audits structure against
structure. Keeping the split sharp is the point -- an audit that reads more
than it checks produces findings nobody reads.

Usage:
    check_task_contract.py [project_root]

Writes a JSON handoff to `.omp/theteam/reports/task-contract.json` and exits
0 whether or not it found anything. This is a reporting task, not a gate: a
defect here is a defect in the registry, and refusing to run is how a stale
registry stays stale. Exit 1 only for a usage error.

Checks, each naming the refusal it prevents:

    1  every llm phase declares prompt_file, output, agent_type
    2  every declared prompt_file exists
    3  every declared agent_type is one a session can spawn
    4  a script phase's declared output is one its script actually writes
    5  reports/ is written only by a task's final phase, and only as HTML
    6  every task has at least one phase, and phases have unique names
"""
import ast
import json
import sys
from pathlib import Path

import yaml

#: Mirrors `theteam.tasks.runners.llm.AGENT_TYPES`. Duplicated rather than
#: imported so this script stays runnable as a bare file with no PYTHONPATH --
#: it is a phase `script:`, and a phase that cannot import its own checker is
#: the exact defect class it hunts. `test_task_contract.py` asserts the two
#: stay equal, so drift fails the suite rather than this file.
AGENT_TYPES = (
    "advisor", "default", "designer", "explore", "scout", "task",
    "Tester", "vision", "reviewer", "security-reviewer", "librarian", "sonic",
)

MACHINE_ROOTS = (".omp/theteam/reports/", "reports/.handoff/")
HUMAN_ROOT = "reports/"


def _finding(task, phase, check, detail, fix):
    return {
        "task": task,
        "phase": phase,
        "check": check,
        "detail": detail,
        "fix": fix,
    }


def _declared_output_keys(tree):
    """Declared output keys of a module-level `NAME = {"key": path}` mapping.

    `scripts/sa_runner.py` declares `OUTPUT_PATHS = {"health_score": ...}`;
    a declared key nothing ever writes is the defect this exists to find.

    Returns `(keys, mapping_names)`. The names come back too because the
    consumer has to match a subscript against the *name*, not the key -- an
    earlier version returned only keys and so never matched anything, which
    made check 4 silently vacuous.
    """
    keys = {}
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Dict):
            continue
        for target in node.targets:
            name = getattr(target, "id", None) or getattr(target, "attr", None)
            if name not in ("OUTPUT_PATHS", "OUTPUT_FILES", "OUTPUTS"):
                continue
            names.add(name)
            for key_node, val_node in zip(node.value.keys, node.value.values):
                if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                    keys[key_node.value] = (getattr(val_node, "lineno", node.lineno),
                                            _path_text(val_node))
    return keys, names


def _path_text(node):
    """The string inside `Path(...) / "x" / "y"`, joined. Best effort."""
    parts = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            parts.append(sub.value)
    return "/".join(p for p in parts if p not in (".", "/")) or ""


def _keys_used_as_write_targets(tree, mapping_names):
    """Declared keys that are used as an output rather than only declared.

    Two shapes reach a writer, and a check that understands only one of them
    is worse than no check -- it reports working code as broken.

    `generic_writer(OUTPUT_PATHS["health_score"], ...)` -- a subscript on the
    mapping.

    `generic_writer("team_summary", summary, ...)` -- a bare string, because
    the writer takes the *key* and resolves the path itself. `sa_runner.py`
    writes almost everything this way: `write_team_summary` at sa_runner.py:191
    is called from two sites. Crediting only subscripts reported 5 of its 6
    declared outputs as never written -- all five false.

    Every string literal would be too loose: a label like
    `"Architecture Report"` is prose. So a literal counts only as an argument
    to a call whose name mentions write/output/report/save/dump/export.
    """
    used = set()
    writer_names = ("write", "output", "report", "save", "dump", "export")

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript):
            owner = node.value
            name = getattr(owner, "id", None) or getattr(owner, "attr", None)
            if name in mapping_names:
                key = node.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    used.add(key.value)

        elif isinstance(node, ast.Call):
            func = node.func
            fname = (getattr(func, "id", None)
                     or getattr(func, "attr", None) or "").lower()
            if not any(w in fname for w in writer_names):
                continue
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    used.add(arg.value)

    return used


def _literal_output_paths(tree):
    """Every path-looking string literal in a script, as a set of suffixes.

    The fallback for scripts with no declared-output mapping: a phase that
    writes `"reports/foo.json"` with `open()` gets credit for it. Matching on
    the tail keeps this from caring how the script builds the path.
    """
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if "/" in v and ("." in v.rsplit("/", 1)[-1]):
                out.add(v.lstrip("./"))
    return out


def _check_task_contract(root, task, findings):
    tid = task.get("id", "?")
    phases = task.get("phases") or []

    if not phases:
        findings.append(_finding(tid, None, "phases", "task declares no phases",
                                 "add at least one phase, or delete the task"))
        return

    names = [p.get("name") for p in phases]
    dupes = {n for n in names if names.count(n) > 1}
    for name in sorted(dupes):
        findings.append(_finding(tid, name, "phases",
                                 f"phase name '{name}' appears more than once",
                                 "phase names address phases; make them unique"))

    for phase in phases:
        pname = phase.get("name", "?")
        runner = phase.get("runner")

        if runner == "llm":
            for field, refusal in (
                ("prompt_file", "runner is llm but names no prompt_file"),
                ("output", "names no output, so it cannot prove it ran"),
                ("agent_type", "names no agent_type"),
            ):
                if not phase.get(field):
                    findings.append(_finding(tid, pname, "llm_fields",
                                             f"llm phase missing '{field}'",
                                             f"add {field}: -- the executor refuses without it "
                                             f"({refusal})"))

            pf = phase.get("prompt_file")
            if pf and not (root / pf).exists():
                findings.append(_finding(tid, pname, "prompt_exists",
                                         f"prompt_file not found: {pf}",
                                         "create the prompt or point at an existing one"))

            at = phase.get("agent_type")
            if at and at not in AGENT_TYPES:
                findings.append(_finding(tid, pname, "agent_type",
                                         f"'{at}' is not one a session can spawn",
                                         f"use one of: {', '.join(AGENT_TYPES)}"))

        out = phase.get("output")
        if out:
            if not out.startswith(MACHINE_ROOTS + (HUMAN_ROOT,)):
                findings.append(_finding(tid, pname, "output_root",
                                         f"output '{out}' is outside every known report root",
                                         "use .omp/theteam/reports/, reports/.handoff/, or reports/"))
            elif out.startswith(HUMAN_ROOT) and not out.startswith("reports/.handoff/"):
                if not out.endswith(".html"):
                    findings.append(_finding(tid, pname, "human_surface",
                                             f"'{out}' is markdown on the human surface",
                                             "move machine intermediates to reports/.handoff/, "
                                             "leave only the final HTML page in reports/"))
                if names and pname != names[-1]:
                    findings.append(_finding(tid, pname, "human_surface",
                                             f"non-final phase '{pname}' writes the human surface",
                                             "only the last phase of a task may write reports/"))

        if runner == "script":
            script = phase.get("script")
            if not script:
                findings.append(_finding(tid, pname, "script_phase",
                                         "script phase names no script",
                                         "add script:, or change runner to llm"))
                continue
            spath = root / script
            if not spath.exists():
                findings.append(_finding(tid, pname, "script_exists",
                                         f"script not found: {script}",
                                         "create it or point at an existing script"))
                continue
            try:
                tree = ast.parse(spath.read_text(encoding="utf-8"))
            except SyntaxError as e:
                findings.append(_finding(tid, pname, "script_parses",
                                         f"{script} does not parse: {e}",
                                         "fix the syntax error; the executor cannot run it either"))
                continue

            declared, mapping_names = _declared_output_keys(tree)
            if declared:
                used = _keys_used_as_write_targets(tree, mapping_names)
                for key, (line, _) in sorted(declared.items()):
                    if key not in used:
                        findings.append(_finding(
                            tid, pname, "output_never_written",
                            f"{script}:{line} declares output '{key}' that nothing writes",
                            "remove the declaration, or write it"))
            elif out:
                # No mapping: credit any path literal that ends in the output.
                literals = _literal_output_paths(tree)
                tail = out.rsplit("/", 1)[-1]
                if not any(p.endswith(tail) or out in p for p in literals):
                    findings.append(_finding(
                        tid, pname, "output_never_written",
                        f"{script} declares no output mapping and never names '{out}'",
                        "the phase completes only when that file exists; "
                        "nothing in the script creates it"))


def main(argv):
    root = Path(argv[1] if len(argv) > 1 else ".").resolve()
    tasks_dir = root / "tasks"
    if not tasks_dir.is_dir():
        print(f"no tasks/ at {root}", file=sys.stderr)
        return 1

    findings = []
    checked = 0
    for path in sorted(tasks_dir.glob("task-*.yaml")):
        try:
            task = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            findings.append(_finding(path.stem, None, "task_parses",
                                     f"{path.name} does not parse: {e}",
                                     "fix the YAML"))
            continue
        if not isinstance(task, dict):
            continue
        checked += 1
        _check_task_contract(root, task, findings)

    report = {
        "tasks_checked": checked,
        "findings": len(findings),
        "details": findings,
    }
    body = json.dumps(report, indent=2, ensure_ascii=False)

    # A `script:` phase runs in a container with the project mounted read-only
    # unless it opts into `writable_project` (executor.py:291). Writing the
    # handoff is worth the opt-in, but failing to write it must never be the
    # reason a check does not report -- so the write is attempted, and a
    # read-only mount degrades to stdout rather than to a non-zero exit.
    # `loop_health_check.py` and `run_pytest.py` take the same shape: they
    # report on stdout and ask for no write access at all.
    out_dir = root / ".omp/theteam/reports"
    written_to = None
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "task-contract.json").write_text(body, encoding="utf-8")
        written_to = out_dir / "task-contract.json"
    except OSError as e:
        print(f"# no handoff written ({e}); reporting on stdout only",
              file=sys.stderr)

    print(f"{checked} tasks checked, {len(findings)} findings"
          + (f" -> {written_to}" if written_to else " (stdout only)"))
    print(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))