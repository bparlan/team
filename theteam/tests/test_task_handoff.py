"""
The trust boundary between a session that spawns members and Python that
accounts for them.

`runner: llm` phases used to gate on `theteam.default_api`, a symbol nothing
binds outside a test, so every llm phase in the project refused with
`no_task_provider`. The fix is not to inject that symbol — it is to stop
Python spawning: Python writes down what it asked for, the session produces
what it can, and Python reads the pair back.

That makes the acceptance rule load-bearing, and the rule is **not** "the
output file exists". A non-empty file at the declared path is exactly what a
stale artifact from last week looks like, and what a file the session wrote by
hand looks like. Accepting either would flip a phase from refused to green and
let the artifact gate in `run_llm_phase` certify a fabrication — the gate
assumes the member wrote the file, which is the assumption that stops holding
once the writer is external.

So acceptance requires a pair:

    request  Python wrote this, before pausing   (prompt hash pinned)
    result   the session wrote this, naming the hash (must match)

These tests pin the three properties that make the boundary sound. They are
deliberately about the *refusals*: a collector that only ever sees the happy
path is a collector whose safety has never been executed.

The manifest is written to disk before the pause returns, because `theteam run`
is a process that exits between the pause and the session's write. Anything
held in memory would be gone by the time there was something to collect.
"""

import json
from pathlib import Path
from typing import Optional

from theteam.tasks.handoff import (
    AWAITING_MEMBER,
    accept_result,
    handoff_dir,
    read_request,
    write_request,
)

RUN_ID = "test-run-001"


def _phase(name="scan", output: Optional[str] = "out/scan.md", member="scout"):
    return {
        "name": name,
        "runner": "llm",
        "member": member,
        "prompt_file": f"prompts/{name}.md",
        "output": output,
    }


def _stage_request(tmp_path, phase=None, prompt="the prompt body"):
    """Write a request the way the executor does, and return its manifest."""
    phase = phase or _phase()
    write_request(str(tmp_path), RUN_ID, "root-organization", phase, prompt,
                  phase.get("output"))
    return read_request(str(tmp_path), RUN_ID, phase["name"])


def _stage_result(tmp_path, phase, body, prompt_sha256):
    """Stage a result and its sidecar, the way a session would."""
    directory = handoff_dir(str(tmp_path), RUN_ID)
    directory.mkdir(parents=True, exist_ok=True)
    result = directory / f"{phase['name']}.result.md"
    result.write_text(body, encoding="utf-8")
    meta = directory / f"{phase['name']}.result.meta.json"
    meta.write_text(json.dumps({"prompt_sha256": prompt_sha256}), encoding="utf-8")
    return result


class TestTheManifestSurvivesTheProcess:
    """`theteam run` exits between the pause and the session's write."""

    def test_the_request_is_on_disk_before_the_pause_returns(self, tmp_path):
        manifest = _stage_request(tmp_path)
        path = handoff_dir(str(tmp_path), RUN_ID) / "scan.request.json"
        assert path.exists(), "the request must outlive the process that wrote it"
        assert manifest is not None

    def test_it_records_who_what_where_and_which_prompt(self, tmp_path):
        manifest = _stage_request(tmp_path)
        assert manifest["task_id"] == "root-organization"
        assert manifest["phase"] == "scan"
        assert manifest["member"] == "scout"
        assert manifest["output"] == "out/scan.md"
        assert manifest["prompt_sha256"], "the prompt hash is the whole point"

    def test_the_hash_covers_prompt_content_not_the_prompt_path(self, tmp_path):
        """Two phases with the same `prompt_file` but different bodies differ.

        Hashing the path would make every phase of a task agree, and a result
        answering one prompt would then be accepted for another.
        """

        phase_a = _phase(name="a")
        phase_b = _phase(name="b", output="out/b.md")
        # Deliberately the same `prompt_file` on both: only the body differs.
        phase_b["prompt_file"] = phase_a["prompt_file"]

        first = _stage_request(tmp_path, phase_a, prompt="body one")
        second = _stage_request(tmp_path, phase_b, prompt="body two")
        assert first["prompt_file"] == second["prompt_file"]
        assert first["prompt_sha256"] != second["prompt_sha256"]


class TestAStaleArtifactIsNotEvidence:
    """The property the whole module exists for."""

    def test_a_stale_file_at_the_output_path_is_not_accepted(self, tmp_path):
        """Last week's scan report must not turn this phase green."""
        phase = _phase()
        _stage_request(tmp_path, phase)

        stale = tmp_path / "out" / "scan.md"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("SCAN FROM LAST WEEK - nobody ran this\n", encoding="utf-8")

        result = accept_result(str(tmp_path), RUN_ID, "scan",
                               handoff_dir(str(tmp_path), RUN_ID) / "scan.result.md")

        assert result["success"] is False
        assert result["skip_reason"] == AWAITING_MEMBER
        # And the stale file is left exactly as it was: acceptance never
        # consults the output path, so it cannot have overwritten anything.
        assert "LAST WEEK" in stale.read_text(encoding="utf-8")

    def test_a_result_with_no_request_on_record_is_refused(self, tmp_path):
        """Nothing was solicited, so nothing can be attributed."""
        directory = handoff_dir(str(tmp_path), RUN_ID)
        directory.mkdir(parents=True, exist_ok=True)
        staged = directory / "scan.result.md"
        staged.write_text("a result nobody asked for\n", encoding="utf-8")
        (directory / "scan.result.meta.json").write_text(
            json.dumps({"prompt_sha256": "anything"}), encoding="utf-8")

        result = accept_result(str(tmp_path), RUN_ID, "scan", staged)

        assert result["success"] is False
        assert "no request on record" in result["error"]


class TestProvenanceIsCheckedNotAssumed:
    """A result must prove it answers the request that was pinned."""

    def test_a_hash_mismatch_is_refused_by_name(self, tmp_path):
        phase = _phase()
        manifest = _stage_request(tmp_path, phase)
        staged = _stage_result(tmp_path, phase, "forged\n", "deadbeef" * 8)

        result = accept_result(str(tmp_path), RUN_ID, "scan", staged)

        assert result["success"] is False
        assert "answers prompt" in result["error"]
        assert manifest["prompt_sha256"] not in result["error"]

    def test_a_result_with_no_hash_is_refused(self, tmp_path):
        """An unlabelled result cannot be shown to answer anything."""
        phase = _phase()
        _stage_request(tmp_path, phase)
        directory = handoff_dir(str(tmp_path), RUN_ID)
        staged = directory / "scan.result.md"
        staged.write_text("content with no provenance\n", encoding="utf-8")

        result = accept_result(str(tmp_path), RUN_ID, "scan", staged)

        assert result["success"] is False
        assert "no prompt hash" in result["error"]

    def test_an_empty_result_is_refused(self, tmp_path):
        """Written but empty is not a finding. Same rule as `llm.py`."""
        phase = _phase()
        manifest = _stage_request(tmp_path, phase)
        staged = _stage_result(tmp_path, phase, "   \n", manifest["prompt_sha256"])

        result = accept_result(str(tmp_path), RUN_ID, "scan", staged)

        assert result["success"] is False
        assert "empty" in result["error"]


class TestTheHappyPathStillWorks:
    """The gate must refuse only what has no evidence behind it."""

    def test_a_correctly_paired_result_is_accepted_and_placed(self, tmp_path):
        phase = _phase()
        manifest = _stage_request(tmp_path, phase)
        staged = _stage_result(tmp_path, phase, "83 root entries inventoried.\n",
                               manifest["prompt_sha256"])

        result = accept_result(str(tmp_path), RUN_ID, "scan", staged)

        assert result["success"] is True
        destination = Path(result["output_path"])
        assert destination == tmp_path / "out" / "scan.md"
        assert "83 root entries" in destination.read_text(encoding="utf-8")
        # Placed by rename, so a reader never sees a half-written file.
        assert not staged.exists()

    def test_it_carries_the_declared_member_not_the_artifact_claim(self, tmp_path):
        """Identity comes from the request, never from the file's contents."""
        phase = _phase(member="skeptic")
        manifest = _stage_request(tmp_path, phase)
        staged = _stage_result(tmp_path, phase, "I am the architect, honestly.\n",
                               manifest["prompt_sha256"])

        result = accept_result(str(tmp_path), RUN_ID, "scan", staged)

        assert result["success"] is True
        assert result["member"] == "skeptic"

    def test_a_request_declaring_no_output_cannot_report_success(self, tmp_path):
        """`llm.py` refuses a phase with no declared output; so does this."""
        phase = _phase(output=None)
        manifest = _stage_request(tmp_path, phase)
        staged = _stage_result(tmp_path, phase, "content\n",
                               manifest["prompt_sha256"])

        result = accept_result(str(tmp_path), RUN_ID, "scan", staged)

        assert result["success"] is False
        assert "no `output`" in result["error"]
