# OMP Prompt — pre-M5 debt: make M5 start from a true baseline

Fresh OMP session at `/Users/bparlan/devcode/team`.

**Mode: ponytail full + caveman full.** Ponytail for scope (smallest honest change, no
unrequested work). Caveman for prose. Run both.

Four items. Not a milestone. M5 does not start until these are done — M5's own baseline
command cannot currently tell you the truth.

---

## PROMPT START

M0–M4 are done. 668 tests, clean tree, invariant gate green on all six checks. Three
commits of M4 landed a real defect: **`theteam history` reports nothing about any task that
has actually run.** Fix that plus three smaller items, then M5 starts clean.

### Baseline first

```bash
cd /Users/bparlan/devcode/team
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5
bash scripts/check_invariants.sh; echo "gate exit=$?"
```

Expect 668 and exit 0. Different? Stop, report, do not edit.

---

### D1 — `history` is blind to every executed task. **The real bug.**

`TaskExecutor.log_execution` (`executor.py:254`) is the only writer of
`task-execution.log`. **Nothing in production calls it.** Grep confirms: the only callers
are `test_execution_log_bound.py` and `test_history_command.py`.

So the file `history` reads (`cli.py:294`, `StateStore.execution_log`) is never created by
a real run. Reproduce:

```bash
cd /tmp && rm -rf hd && mkdir -p hd/tasks && cd hd
printf 'import sys\nsys.exit(1)\n' > boom.py
cat > c.yaml <<'EOF'
id: c
name: C
type: ops
priority: 9
order: 0
phases:
  - name: b
    script: boom.py
    timeout_seconds: 10
    memory_limit_mb: 64
EOF
export PYTHONPATH=/Users/bparlan/devcode/team
python3 -m theteam.cli --project-root /tmp/hd task create --path /tmp/hd/c.yaml
python3 -m theteam.cli --project-root /tmp/hd loop c --interval 1 >/dev/null
for i in 1 2 3 4 5; do
  python3 -c "
import json;sp='/tmp/hd/.omp/theteam/task-schedule.json';d=json.load(open(sp))
d['scheduled_tasks']['c']['next_run']='2020-01-01T00:00:00+00:00';json.dump(d,open(sp,'w'))" 2>/dev/null
  python3 -m theteam.cli --project-root /tmp/hd run --only c --json >/dev/null 2>&1
done
python3 -m theteam.cli --project-root /tmp/hd history --task c --json
ls /tmp/hd/.omp/theteam/task-execution.log
```

Observed: **5 real failures, breaker open, and `runs: 0`, `failures: 0`,
`last_failure: null`, with no log file on disk.** §7.1.7 requires per-task success rate
and last failure. It reports neither.

The tests never caught it because `test_history_command.py:91` *seeds* the log by hand
instead of running a task — the test asserts against a fixture that only exists in the test.

**Fix:** call `log_execution` from the real execution path in `cmd_run` (`cli.py`, after
`executor.execute_task`) or at the end of `execute_task`. One call site. Do not restructure
the executor.

Then **break the test that hides it**: change `test_history_command.py` to produce runs by
executing a task, not by seeding a file. If that is too slow, seed through
`log_execution` and add one integration test that goes through `run`. Either way, the
history numbers must come from something the product actually did.

Verify the reproduction now shows `runs: 5`, `failures: 5`, `success_rate: 0.0`, and a
real `last_failure` timestamp. A failed task has a rate of 0.0 — that is a measurement.
An *unrun* task stays `null` (M4's correct behaviour, keep it).

---

### D2 — `ARCHITECTURE.md` §5.5 names a file the code does not write

§5.5 says `audit/chain.jsonl`. `AuditLogger` hardcodes `audit.jsonl`
(`theteam/core/audit.py:43`). M4 resolved this in the component and had `status` report the
real path. The doc is still wrong, and the doc is the source of truth.

Fix §5.5 to name `audit.jsonl`. One line. No code change — M4's resolution was right.

While in the file: §5.2 was corrected during the M3 debt run, but check the rest of Part 5
against the tree the same way. Any path that does not exist, correct or delete. One
command per line is enough:

```bash
cd /Users/bparlan/devcode/team
sed -n '250,300p' ARCHITECTURE.md
```

---

### D3 — the invariant gate does not run where M5 will look

`scripts/check_invariants.sh` is in CI (`.github/workflows/ci.yml:52`) and passes. But
`M5_PROMPT.md`'s baseline is `pytest` alone, and the gate is a shell script a Python test
suite will never invoke. A gate that only runs in CI is invisible to the next session.

One line: a test in `theteam/tests/` that runs the gate and asserts exit 0. If the gate
fails, that test fails. No subprocess-parsing cleverness — `subprocess.run(["bash",
"scripts/check_invariants.sh"])` and assert the return code.

If the script is missing or unparseable, fail the test and say so. A test that skips when
the gate is absent is the false-green pattern this project keeps hitting.

---

### D4 — `M5_PROMPT.md` is untracked

`git status` shows `?? M5_PROMPT.md`. Every prior milestone prompt was committed or
removed. Either commit it (it is the plan for the next milestone) or delete it. Do not
leave it untracked — the next session cannot tell a working document from an accident.

**`M3_DEBT_PROMPT.md` and `M4_PROMPT.md` are already gone from the tree.** Follow whichever
of the two the repo shows. Do not add new prompt files for this one; this file is the
prompt.

---

### Verify

```bash
cd /Users/bparlan/devcode/team
python3 -m pytest theteam/tests/ -q --no-header 2>&1 | tail -5   # no regression from 668
bash scripts/check_invariants.sh; echo "exit=$?"                 # 0
python3 -m theteam.cli --project-root . run --json               # {ran:0}, twice identical
python3 -m theteam.cli --project-root . history --json           # real numbers or null, never 0-as-unknown
python3 -c "import theteam; print('IMPORT OK')"
git status --porcelain                                            # only what you intend
```

No regression from 668. If the count moves, name every difference. **Do not delete a test
to reach a number** — that is how the dead dashboard survived three milestones.

---

### Constraints

- **Four items. No more.** No advisory code, no UI, no safety changes. M5 builds the
  advisory layer; this makes its baseline honest.
- **No new `*.md` files.** D2 edits an existing one. This prompt is the doc.
- **D1 is one call site plus one test correction.** The tempting move is to restructure
  the executor or rework the history aggregation. Do neither. The bug is a missing call.
- A failed test means a wrong side somewhere. Say which and why; do not weaken the
  assertion to make it pass.
- Run the suite after every item.

---

### Delegation

Inline. Four items, one shared file, well under 60 lines of real change. `task`
subagents cost more than the work. Use `todo` if they do not land in one pass: `D1`, `D2`,
`D3`, `D4`. Mark done with output. Never yield `in_progress`.

---

### Deliverable

One commit. Summary 3 lines max (`AGENTS.md`), then:

1. The D1 reproduction **after** the fix — paste `history --json` showing real numbers.
2. The test count, and the arithmetic for any change from 668.
3. Which `ARCHITECTURE.md` lines you corrected in D2.
4. The gate test's output.

If D1 turns out to need more than one call site, stop and report. A history that needs
restructuring to become honest is a finding worth surfacing, not a refactor to absorb
quietly.
