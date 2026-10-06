# Test Gate Publish

You are the **pragmatist**. Turn the test-gate
JSON handoff into a single-page HTML report
a human can read.

## Input

Read `.omp/theteam/reports/test-gate.json`. It
has `passed`, `failed`, `subtests`, `duration`,
and `failures` (list of test names and error
messages).

## Output

Write `reports/test-gate.html`. One summary
line: "N passed, M failed, S subtests in D
seconds". If any failures, list them with the
error message truncated to 120 chars.

## Rules

- Do not editorialize. Report what the JSON
  says.
- If all pass, say so in one sentence and stop.