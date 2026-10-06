#!/usr/bin/env python3
"""Check the project's security policy against the codebase."""
from pathlib import Path
import json
import sys
import yaml

ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "tasks" / "SECURITY_POLICY.yaml"
DESTRUCTIVE = ["rm -rf", "sudo", "chmod 777", "dd if=", "mkfs"]
SECRET = [".env", "credentials", "secrets", "id_rsa"]
SKIP = {"check_security_policy.py", "security_policy.py"}
EXCLUDE_DIRS = {"scripts/replica", "scripts/init-replica"}
EXCLUDE_PATHS = {
    "scripts/run_pytest.py",
    "scripts/loop_infrastructure_check.py",
    "__init__.py", "cli.py", "state.py",
}
EXCLUDE_PREFIXES = {"theteam/", "_island/", "scripts/replica/", "scripts/init-replica/"}
EXCLUDE_TASKS = {"tasks/system-awareness/"}


def _read(p):
    try:
        return p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _scan(patterns):
    findings = []
    for ext in ("*.py", "*.sh", "*.md"):
        for path in ROOT.rglob(ext):
            if path.name.startswith("."):
                continue
            if path.name in SKIP:
                continue
            rel = str(path.relative_to(ROOT))
            if rel in EXCLUDE_PATHS:
                continue
            if any(rel.startswith(p) for p in EXCLUDE_PREFIXES):
                continue
            if any(rel.startswith(t) for t in EXCLUDE_TASKS):
                continue
            text = _read(path)
            if not text:
                continue
            for pat in patterns:
                for i, line in enumerate(text.splitlines(), 1):
                    if pat in line and not line.strip().startswith("#"):
                        findings.append({
                            "rule": "no-destructive-commands" if pat in DESTRUCTIVE else "no-secret-access",
                            "file": str(path.relative_to(ROOT)),
                            "line": i,
                            "pattern": pat,
                            "text": line.strip()[:100],
                        })
    return findings


def check_isolation():
    findings = []
    tasks_dir = ROOT / "tasks"
    if not tasks_dir.is_dir():
        return findings
    for task_file in sorted(tasks_dir.glob("task-*.yaml")):
        try:
            task = yaml.safe_load(task_file.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(task, dict):
            continue
        for phase in task.get("phases", []):
            if phase.get("runner") == "llm":
                continue
            script = phase.get("script")
            if not script:
                continue
            writable = phase.get("writable_project", False)
            script_path = ROOT / script
            if script_path.exists():
                text = _read(script_path)
                writers = ["shutil.rmtree", ".unlink(", "write_text(", "write("]
                has_writes = any(w in text for w in writers)
                if has_writes and not writable:
                    findings.append({
                        "rule": "require-isolation",
                        "task": task.get("id", "?"),
                        "phase": phase.get("name", "?"),
                        "script": script,
                        "detail": "script writes but writable_project is not set",
                    })
    return findings


def check_max_execution_time():
    findings = []
    tasks_dir = ROOT / "tasks"
    if not tasks_dir.is_dir():
        return findings
    for task_file in sorted(tasks_dir.glob("task-*.yaml")):
        try:
            task = yaml.safe_load(task_file.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if not isinstance(task, dict):
            continue
        for phase in task.get("phases", []):
            timeout = phase.get("timeout_seconds")
            if timeout is None:
                findings.append({"rule": "max-execution-time", "task": task.get("id", "?"), "phase": phase.get("name", "?"), "detail": "no timeout_seconds declared"})
            elif timeout > 300:
                findings.append({"rule": "max-execution-time", "task": task.get("id", "?"), "phase": phase.get("name", "?"), "detail": f"timeout {timeout}s exceeds max 300s"})
    return findings


def main():
    if not POLICY_PATH.exists():
        print("cannot-evaluate: SECURITY_POLICY.yaml not found", file=sys.stderr)
        sys.exit(2)
    try:
        yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        print(f"cannot-evaluate: policy parse error: {e}", file=sys.stderr)
        sys.exit(2)

    all_findings = []
    all_findings.extend(_scan(DESTRUCTIVE))
    all_findings.extend(_scan(SECRET))
    all_findings.extend(check_isolation())
    all_findings.extend(check_max_execution_time())

    out_dir = ROOT / ".omp/theteam/reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"total_rules": 4, "total_findings": len(all_findings), "findings": all_findings}
    (out_dir / "security-scan.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"security-scan: {len(all_findings)} findings")
    for f in all_findings[:10]:
        loc = f.get("file", f.get("script", "?"))
        print(f"  {f['rule']}: {loc}:{f.get('line', '?')}")

    if all_findings:
        sys.exit(3)
    sys.exit(0)


if __name__ == "__main__":
    main()