# Legacy Migration Inventory Summary

## Snapshot

- Source: `khyitty/VitalDB-Feature-Selection`
- Commit: `9501b16a5c4db27f06fa0d0b252a3a75f633967f`
- Tree: `60917f0b61ec1e6a195b9a648faa6466406aeda1`
- Tracked files: 352
- Pre-inspection worktree status: one pre-existing untracked `debug.log`
- Inventory scope: tracked files only
- Migration performed in this phase: none

## Classification result

| Migration type | Files |
|---|---:|
| copy | 0 |
| refactor | 156 |
| rewrite | 10 |
| reject | 186 |
| total | 352 |

| Data/scientific dependency | Files |
|---|---:|
| yes | 186 |
| mixed | 160 |
| no | 6 |

`copy` is intentionally zero. No legacy implementation is considered safe for
verbatim transfer before independent validation. `refactor` and `rewrite` are
future dispositions, not authorization to migrate during Phase 2.

## Decision rules

- `data/`, `outputs/`, notebooks, frozen legacy configurations, and
  inspected-test/frozen-result workflows are `reject`.
- Legacy download entry points are `rewrite` because they contain first-N behavior.
- Algorithmic source and tests are at most `refactor`; old metrics and outputs
  cannot serve as test oracles.
- Uncertain scientific dependencies remain `mixed`.
- A rejected row has target `NOT_MIGRATED`.
- Pending rows require the tests named in `required_tests` before any later move.

## First-N evidence

- `main.py:10`: `DEFAULT_N_CASES = 100`
- `main.py:219`: environment-driven `N_CASES`
- `main.py:220`: `caseids[:n_cases]`
- `explore_vitaldb_sample.py:301`: `N_CASES = min(30, ...)`
- `explore_vitaldb_sample.py:305`: `caseids[:N_CASES]`

These files are classified `rewrite`; their cohort-selection logic is not copied.

## Boundary

This inventory is not an assertion that any pending code is scientifically valid.
It contains no legacy case IDs, split, scaler, checkpoint, result, prediction,
feature ranking, model output, or data file.
