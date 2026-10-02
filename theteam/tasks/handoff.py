#!/usr/bin/env python3
"""
theteam.tasks.handoff - the request/result pair an `llm` phase needs to exist.

## Why this module exists

`llm.py` gates `runner: llm` phases on `hasattr(theteam, "default_api")`, a
symbol whose only assignment in the whole repository is a `monkeypatch` in a
test. So the refusal is correct in every environment — and a phase that cannot
prove it ran must stay refused, per §3.3.

What that leaves is the part no subprocess can do: **spawning the member.** The
session owns that capability. So Python does not spawn, and instead writes down
what it asked for. The session does the work and writes down what it produced.
Python reads the pair back and runs the accounting that already exists.

## The rule: freshness is not provenance

A collector that accepted "the output file exists and is non-empty" would be
worse than the refusal it replaces. `reports/root-organization-scan.md` from
last week is non-empty. A file the session writes by hand is non-empty. Both
would flip a phase from `no_task_provider` to green, and the artifact gate added
to `run_llm_phase` would then certify the fabrication — the gate assumes the
member wrote the file, which is exactly what cannot be assumed once the writer
is external.

So acceptance requires a **pair**, not a file:

    request  = executor wrote this, before pausing   (prompt hash pinned)
    result   = session wrote this, naming the hash    (must match)

A result with no request is refused. A result whose hash does not match the
request is refused. A stale artifact at the output path is never consulted at
all, because acceptance never looks at the output path — it looks at the staged
result, and only then moves that into place.

## Why the output directory is created last

`makedirs` before the manifest exists would let a phase succeed on a stale file
sitting in a directory the collector just created. So the order is fixed:
validate the pair, then `makedirs`, then `os.replace`. `root-organization`
writes to `reports/` at the repo root while the other five tasks write to
`.omp/theteam/reports/`; neither location is privileged here, and this module
does not care which one it is.

## What it is not

Not a provider, not a queue, not a daemon. `os.replace` is the same atomic
primitive `TaskRepository._save_schedule` already uses, and the hash comes from
`DataChecksumValidator.compute_checksum`, which the production code did not
call before this. No third mechanism was introduced.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

#: Manifest schema version. Bumped if the pair's fields ever change shape, so
#: a collector can refuse a manifest it does not understand instead of reading
#: fields that mean something else.
HANDOFF_VERSION = 1

#: Where staged requests and results live, relative to the state directory.
HANDOFF_SUBDIR = "handoff"

#: Why a phase is waiting rather than failed. The executor reads this and
#: declines to count the attempt — the same rule `no_task_provider` already
#: uses, because a phase nobody ran has not failed at anything.
AWAITING_MEMBER = "awaiting_member"


def _sha256(text: str) -> str:
    """The prompt's digest, as the request records it.

    Stdlib hashlib rather than `DataChecksumValidator`: that class raises
    `ChecksumError` on unsupported input and serializes dicts as JSON, neither
    of which a prompt string needs, and importing it here would make a hot path
    depend on a component built for state files.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def handoff_dir(project_root: str, run_id: str) -> Path:
    """The directory one run's staged pairs live in.

    Under the state directory, not the project root: `.omp/` is gitignored
    (`.gitignore:48`) and the staged files are runtime state, not deliverables.
    """
    from theteam.state import state_dir

    return Path(state_dir(project_root)) / HANDOFF_SUBDIR / run_id


def write_request(project_root: str, run_id: str, task_id: str,
                  phase: Dict[str, Any], prompt: str,
                  output: Optional[str]) -> Path:
    """Record what Python asked a member to produce, then let the phase pause.

    Written BEFORE the pause, because a session that starts work with nothing on
    disk to read has no way to know what was requested. The prompt's hash is
    pinned here so the collector can prove the result answers *this* prompt and
    not one edited after the fact.
    """
    directory = handoff_dir(project_root, run_id)
    directory.mkdir(parents=True, exist_ok=True)

    name = str(phase.get("name", "?"))
    manifest = {
        "version": HANDOFF_VERSION,
        "run_id": run_id,
        "task_id": task_id,
        "phase": name,
        "member": phase.get("member"),
        "prompt_file": phase.get("prompt_file"),
        "prompt_sha256": _sha256(prompt),
        "output": output,
        "requested_at": datetime.now(timezone.utc).isoformat(),
    }
    path = directory / f"{name}.request.json"
    # Same temp+replace the schedule uses: a reader must never see half a
    # manifest, because "manifest exists" is the collector's admission test.
    temp = path.with_suffix(".tmp")
    with open(temp, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    os.replace(temp, path)
    return path


def read_request(project_root: str, run_id: str, phase_name: str) -> Optional[Dict[str, Any]]:
    """The request for a phase, or `None` when Python never asked.

    `None` is the refusal case, not an error: a phase with no manifest is a
    phase that was never handed off, and admitting it on the strength of a file
    alone is the fabrication this module exists to prevent.
    """
    path = handoff_dir(project_root, run_id) / f"{phase_name}.request.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("version") != HANDOFF_VERSION:
        return None
    return manifest


def accept_result(project_root: str, run_id: str, phase_name: str,
                  result_path: Path) -> Dict[str, Any]:
    """Accept a staged result only when it answers the request on record.

    Returns the same shape a phase returns, so the executor reads it exactly as
    it reads a script phase's result. Four refusals, each naming its own reason:

    * no request      — Python never asked; nothing here was solicited
    * no result       — the session wrote nothing
    * empty result    — written but with no content (§3.3, same as `llm.py`)
    * hash mismatch   — the result answers a different prompt than the one pinned
    """
    manifest = read_request(project_root, run_id, phase_name)
    if manifest is None:
        return {
            "success": False,
            "skip_reason": AWAITING_MEMBER,
            "error": (f"phase '{phase_name}': no request on record for run {run_id}, "
                      f"so a result cannot be attributed to it"),
        }

    if not result_path.exists():
        return {
            "success": False,
            "skip_reason": AWAITING_MEMBER,
            "error": (f"phase '{phase_name}': request is on record but no result "
                      f"was staged at {result_path}"),
        }

    try:
        produced = result_path.read_text(encoding="utf-8")
    except OSError as error:
        return {
            "success": False,
            "error": f"phase '{phase_name}': staged result unreadable: {error}",
        }

    if not produced.strip():
        return {
            "success": False,
            "error": (f"phase '{phase_name}': staged result at {result_path} "
                      f"is empty"),
        }

    # The provenance check. The session records which prompt it answered; a
    # result whose hash does not match the request is not the answer to it.
    recorded = None
    sidecar = result_path.with_suffix(".meta.json")
    if sidecar.exists():
        try:
            with open(sidecar, "r", encoding="utf-8") as handle:
                recorded = json.load(handle).get("prompt_sha256")
        except (OSError, json.JSONDecodeError):
            recorded = None

    if recorded is None:
        return {
            "success": False,
            "error": (f"phase '{phase_name}': staged result carries no prompt hash, "
                      f"so it cannot be shown to answer the request"),
        }

    if recorded != manifest["prompt_sha256"]:
        return {
            "success": False,
            "error": (f"phase '{phase_name}': staged result answers prompt "
                      f"{recorded[:12]} but the request pinned "
                      f"{str(manifest['prompt_sha256'])[:12]}"),
        }

    output = manifest.get("output")
    if not output:
        return {
            "success": False,
            "error": (f"phase '{phase_name}': request declares no `output`, so "
                      f"success cannot be evidenced"),
        }

    # Only now is a directory created, and only now is anything moved. Before
    # this point nothing on disk has been touched, so a stale file at `output`
    # is inert rather than load-bearing.
    destination = Path(project_root) / output
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(result_path, destination)

    return {
        "success": True,
        "output_path": str(destination),
        "member": manifest.get("member"),
        "phase": phase_name,
    }
