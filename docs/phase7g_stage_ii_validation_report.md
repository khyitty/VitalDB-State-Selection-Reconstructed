# Phase 7G Stage II validation report

## Scope

Phase 7G implements a dependency-free, synthetic-only closed-loop anesthesia environment core around the immutable Stage I PK/PD simulator. It provides reset/step return semantics compatible with a future adapter, but it does not import or install Gymnasium, Stable-Baselines3, PyTorch, or any PPO implementation.

No VitalDB raw signal, subject metadata, actual observation template, real patient profile, split, test seal, modeling array, checkpoint, training, evaluation, prediction, or statistical analysis was created or accessed.

## Approved contracts

- P0 uses finite causal BIS in [0,100] with an inclusive 30-second staleness cap and ignores SQI.
- P1 additionally requires exact-timestamp finite SQI >=50 and uses an inclusive 20-second cap. Nearest matching and interpolation are absent.
- Missing BIS is encoded as value 0, mask 0, and capped age; genuine BIS 0 retains mask 1.
- Propofol action means mg delivered over the next 10-second interval. It is clipped once to [0,27.7] and converted to mg/min by multiplication by six.
- Remifentanil schedules are deterministic, synthetic, nonnegative, and right-continuous. Changes inside a control interval split the exact ZOH transition.
- Reward is `1 / (abs(50 - latent endpoint BIS) + 1)` and does not use controller-visible BIS.
- S0 has 34 finite ordered fields. S1 has the identical S0 prefix plus eight dose and PK fields, totaling 42.

## Synthetic validation

Five fixed-input engineering scenarios cover perfect observation, low SQI, missing observation, irregular intra-interval events, and piecewise remifentanil. Each scenario instantiates P0S0, P1S0, P0S1, and P1S1 from the same synthetic profile, template, schedule, seed, and action sequence.

The checks require equal latent states, rewards, and applied actions across all four conditions; exact 34/42 shapes; finite observations; and exact S0 prefixes in S1. These are interface and scientific-transition checks, not control-performance results.

## Claim boundary

The 3,600-second default is a configurable synthetic Stage II engineering horizon, not an approved final training or evaluation horizon. MC-019–MC-030, MC-033, and MC-034 remain `recommended_pending_human_approval`. No policy was implemented, trained, compared, or selected.
