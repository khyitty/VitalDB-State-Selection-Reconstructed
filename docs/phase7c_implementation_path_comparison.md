# Phase 7C Implementation Path Comparison

| Path | Implementation amount | Main risks | Validation required | Expected files | Reproduction potential | Schedule fit |
|---|---:|---|---|---|---|---|
| A — laboratory code reuse | smallest | unavailable code, undocumented dependencies, version mismatch | provenance, clean install, one-step interface, observation adapter invariants | dependency lock, thin adapter, template schema, tests | highest if authoritative code is supplied | best |
| B — legacy refactor | medium | scientific constants are legacy-only; dependency drift; reward/action ambiguity | primary-source PK/PD, locked Gymnasium/SB3, simulator equivalence, reward/action review | selected legacy modules, packaging/config, adapters, synthetic/equivalence tests | reconstruction only unless independently validated | acceptable fallback |
| C — full reconstruction | largest | equation, numerical, PPO, and interface errors; accidental protocol choices | complete unit/equivalence/integration suite and extensive human review | full simulator, environment, PPO stack, configuration, tests | lowest without original code | poor |

Path A is recommended because it adds the least new research logic and offers the strongest chance of matching the laboratory's intended system. Its status is a roadmap recommendation, not authorization to acquire, copy, or execute unreviewed code. Path B is the fallback because the pure legacy simulator already passes a bounded synthetic probe. Path C should be chosen only after A is unavailable and B is shown scientifically inadequate.
