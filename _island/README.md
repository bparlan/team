# _island — theteam behavioral modules (stashed 2026-09-29)

These six packages were removed from the production OMP skill at
`~/.omp/agent/skills/theteam/`. They are preserved here because they are
**unique** — the skill directory has no git and no `.backup` copies, and
`~/devcode/team/theteam/` has no `analysis/`, `generation/`, `management/`,
`integration/`, `validation/`, or `config/` counterpart. Deleting them would
have been unrecoverable.

Recoverable copies of all six also exist in the session transcript:
`~/.omp/agent/sessions/-devcode-team/2026-09-19T14-32-01-499Z_...jsonl`
(lines 114, 116, 119, 120, 125, 128).

## Why they were stashed

The production skill's documented path (`bin/theteam_config.py`,
`bin/theteam_report.py`) never imports them. They were written 2026-09-19 in
a session that hit a circular-import bug, compacted, and was aborted twice —
never validated against the skill's contract.

Executed per-module on 2026-09-29:

| Module | Entry point | Result |
|---|---|---|
| `analysis/project_scanner.py` | `analyze_project()` | OK — 11 keys |
| | `get_team_recommendations()` | OK — 2 traits |
| `generation/team_generator.py` | `analyze_and_generate_teams()` | OK — 2 teams |
| `management/team_manager.py` | `perform_action(ADD_MEMBER)` | OK |
| | `_calculate_performance_metrics()` | **FAILS** — 4 undefined methods |
| | `export_management_report()` | **FAILS** — same |
| `integration/behavioral_integration.py` | `run_enhanced_initialization()` | OK — 2 team options |
| `validation/behavioral_validator.py` | — | no public API (only `_import_*` helpers) |

`TeamManager` calls four methods that are defined nowhere in any of the six
packages:

```
_calculate_recommendation_scores
_generate_alternative_teams
_generate_skill_gap_recommendations
_perform_composition_optimization
```

That makes its two headline operations (`_calculate_performance_metrics`,
`export_management_report`) unusable. The island is **incomplete**, not
merely unused.

## Defects fixed before stashing

Two runtime errors found and repaired in `management/team_manager.py`:

- `_analyze_skill_gaps` — `set()` over lists, `TypeError: unhashable type:
  'list'`. Flattened and sorted.
- diversity scoring — `log2` used bare with no `import math` (2 call sites),
  `NameError`. Now `math.log2`.

`analysis/project_scanner.py` was also repaired earlier the same day (5 syntax
errors, 1 `TypeError`, `_is_test_file` glob matching, `test_files` always 0,
`src_structure` picking `tests/`, and a `structural_complexity` drift that
would have flipped 14 role/risk decisions).

## If you want to revive this

The intent was to make `theteam init` choose team composition from project
files rather than a fixed default trio. To finish it:

1. Implement the four missing `TeamManager` methods.
2. Give `validation/behavioral_validator.py` a public API.
3. Wire `bin/theteam_config.py init` to call `analyze_and_generate_teams()`
   so the capability is reachable from the documented path.
4. Re-validate the 14 `structural_complexity` threshold call sites in
   `team_generator.py`, `team_manager.py`, and `behavioral_integration.py`
   against a fixed fixture — those decisions are what the whole island exists
   to make.

Import paths are package-relative, so this directory must stay importable as
a whole (`_island/analysis/…`, not the packages scattered).
