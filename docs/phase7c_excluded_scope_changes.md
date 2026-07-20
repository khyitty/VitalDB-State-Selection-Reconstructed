# Phase 7C Excluded Local Changes

The following local changes were created under the superseded full-scaffold instruction before the revised audit-only instruction arrived. They are outside the revised Phase 7C boundary. They were not used as evidence, were not staged or committed, and were preserved without reset or automatic deletion.

Modified tracked files:

- `pyproject.toml`
- `scripts/verify_no_first_n_limit.py`
- `src/vitaldb_state_selection/pkpd/__init__.py`
- `src/vitaldb_state_selection/rl/__init__.py`
- `tests/test_governance.py`

Untracked implementation/test files:

- `src/vitaldb_state_selection/pkpd/simulator.py`
- `src/vitaldb_state_selection/rl/environment.py`
- `src/vitaldb_state_selection/rl/observation.py`
- `src/vitaldb_state_selection/rl/ppo.py`
- `src/vitaldb_state_selection/rl/reward.py`
- `src/vitaldb_state_selection/rl/state.py`
- `tests/test_phase7c_observation.py`
- `tests/test_phase7c_ppo.py`
- `tests/test_phase7c_simulator.py`

The three excluded tests were not rerun after the scope correction. The earlier attempted invocation failed during test-module import because the source package path was not configured; it performed no simulator step or PPO update. A human must later decide whether to delete, revise, or authorize these local changes.
