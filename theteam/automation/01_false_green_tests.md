# Prompt 1 – Fix three false-green tests

## Baseline (verified)
- Repo HEAD: `b3a7708` (clean, 619 tests passing)
- Three tests in `theteam/tests/` return `True`:
  * `test_architectural_resolution` – line 176
  * `test_basic_functionality` – line 83
  * `test_integration_requirements` – line 177

## Target
Convert each `return True/False` into an explicit `assert` on the
value being returned.

## Acceptance
1. `python3 -m pytest theteam/tests/ -q` → 619 passed, **0** `PytestReturnNotNoneWarning`.
2. Each test can be made to fail by inverting the assertion
   (prove failure → revert → success).

## Skills
- `/ponytail` – to scope the change to the three files.
- `/caveman-review` – to produce a one-line diff review before commit.

## Commit
- One commit with a clear message, e.g.
  `fix(tests): replace return True with assert in three test files`.
- No other files touched.