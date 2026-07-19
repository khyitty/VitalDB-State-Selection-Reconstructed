# Phase 5D Volatile Exposure Rule Sensitivity Audit

## Interpretation boundary

This is outcome-blind decision support over the unfrozen Phase 5C universe.
No volatile-exposure rule, TIVA decision, signal-quality threshold, protocol
candidate, or cohort was selected. Track presence alone is not exposure.

## Source and accounting

| Measure | Result |
|---|---:|
| Cases | 3219 |
| Duplicate cases | 0 |
| Missing cases | 0 |
| Phase 5C raw signals checksum-verified | 9059 |
| New API requests | False |
| New raw files created | False |

## Continuity and gap handling

Rows and duplicate timestamps are retained in original payload order. For each
case×track, the engineering continuity boundary is three times the median of
strictly positive consecutive timestamp differences inside the anesthesia window.
A zero/negative interval or an interval above that boundary is flagged and breaks
the run; its gap is not added to duration. A single positive sample has duration 0.
Runs are never joined across tracks. This engineering boundary is not a finalized
signal-quality threshold.

- gap multiplier: `3.0`
- cadence estimator: `median_of_strictly_positive_consecutive_timestamp_differences_within_anesthesia_window`
- duplicate handling: `retained_not_averaged_and_break_continuity`

### Observed continuity-boundary distributions

The boundary is case×track-specific. Values below are across present tracks
with an estimable positive timestamp interval.

| Exact track | Available / present | Boundary q05 (s) | q50 (s) | q95 (s) |
|---|---:|---:|---:|---:|
| `Primus/EXP_SEVO` | 1388 / 1390 | 18.765 | 21.03 | 21.45 |
| `Primus/INSP_SEVO` | 1388 / 1390 | 18.765 | 21.03 | 21.45 |
| `Primus/EXP_DES` | 991 / 991 | 18.78 | 21.03 | 21.45 |
| `Primus/INSP_DES` | 991 / 991 | 18.78 | 21.03 | 21.45 |
| `Solar8000/GAS2_EXPIRED` | 538 / 544 | 6 | 6 | 6 |
| `Solar8000/GAS2_INSPIRED` | 538 / 544 | 6 | 6 | 6 |
| `Primus/MAC` | 3208 / 3209 | 18.69 | 21.021 | 21.42 |

### Timestamp and gap warning flags

| Track-level warning | Track rows |
|---|---:|
| `duplicate_timestamp` | 144 |
| `inverted_anesthesia_window` | 5 |
| `long_gap` | 4155 |
| `zero_interval` | 144 |

## Exposure-definition sensitivity — none selected

| Definition | Excluded | Retained | Excluded fraction |
|---|---:|---:|---:|
| `A_any_allowed_positive_once` | 717 | 2502 | 22.27% |
| `B_any_agent_specific_positive_once` | 700 | 2519 | 21.75% |
| `C_agent_specific_or_support_positive_once` | 717 | 2502 | 22.27% |
| `D_longest_positive_run_ge_10s` | 674 | 2545 | 20.94% |
| `E_longest_positive_run_ge_30s` | 641 | 2578 | 19.91% |
| `F_longest_positive_run_ge_60s` | 630 | 2589 | 19.57% |
| `G_longest_positive_run_ge_300s` | 533 | 2686 | 16.56% |
| `H_positive_proportion_ge_0_1pct` | 697 | 2522 | 21.65% |
| `H_positive_proportion_ge_1pct` | 625 | 2594 | 19.42% |
| `H_positive_proportion_ge_5pct` | 581 | 2638 | 18.05% |
| `H_positive_proportion_ge_10pct` | 566 | 2653 | 17.58% |
| `I_agent_specific_and_support_positive` | 672 | 2547 | 20.88% |
| `J_agent_specific_only_positive` | 28 | 3191 | 0.87% |
| `K_support_only_positive` | 17 | 3202 | 0.53% |

Definitions A and C are logically identical because the seven allowed tracks
are exhausted by agent-specific, GAS2, and MAC groups; their disagreement is 0.

## Pairwise disagreement matrix

| Definition | A_any_allowed_positive_once | B_any_agent_specific_positive_once | C_agent_specific_or_support_positive_once | D_longest_positive_run_ge_10s | E_longest_positive_run_ge_30s | F_longest_positive_run_ge_60s | G_longest_positive_run_ge_300s | H_positive_proportion_ge_0_1pct | H_positive_proportion_ge_1pct | H_positive_proportion_ge_5pct | H_positive_proportion_ge_10pct | I_agent_specific_and_support_positive | J_agent_specific_only_positive | K_support_only_positive |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `A_any_allowed_positive_once` | 0 | 17 | 0 | 43 | 76 | 87 | 184 | 20 | 92 | 136 | 151 | 45 | 689 | 700 |
| `B_any_agent_specific_positive_once` | 17 | 0 | 17 | 54 | 85 | 94 | 185 | 31 | 99 | 143 | 158 | 28 | 672 | 717 |
| `C_agent_specific_or_support_positive_once` | 0 | 17 | 0 | 43 | 76 | 87 | 184 | 20 | 92 | 136 | 151 | 45 | 689 | 700 |
| `D_longest_positive_run_ge_10s` | 43 | 54 | 43 | 0 | 33 | 44 | 141 | 27 | 49 | 93 | 108 | 38 | 690 | 663 |
| `E_longest_positive_run_ge_30s` | 76 | 85 | 76 | 33 | 0 | 11 | 108 | 56 | 18 | 60 | 75 | 59 | 667 | 632 |
| `F_longest_positive_run_ge_60s` | 87 | 94 | 87 | 44 | 11 | 0 | 97 | 67 | 17 | 53 | 64 | 66 | 658 | 623 |
| `G_longest_positive_run_ge_300s` | 184 | 185 | 184 | 141 | 108 | 97 | 0 | 164 | 92 | 76 | 85 | 157 | 561 | 532 |
| `H_positive_proportion_ge_0_1pct` | 20 | 31 | 20 | 27 | 56 | 67 | 164 | 0 | 72 | 116 | 131 | 41 | 687 | 686 |
| `H_positive_proportion_ge_1pct` | 92 | 99 | 92 | 49 | 18 | 17 | 92 | 72 | 0 | 44 | 59 | 71 | 653 | 618 |
| `H_positive_proportion_ge_5pct` | 136 | 143 | 136 | 93 | 60 | 53 | 76 | 116 | 44 | 0 | 15 | 115 | 609 | 574 |
| `H_positive_proportion_ge_10pct` | 151 | 158 | 151 | 108 | 75 | 64 | 85 | 131 | 59 | 15 | 0 | 130 | 594 | 559 |
| `I_agent_specific_and_support_positive` | 45 | 28 | 45 | 38 | 59 | 66 | 157 | 41 | 71 | 115 | 130 | 0 | 700 | 689 |
| `J_agent_specific_only_positive` | 689 | 672 | 689 | 690 | 667 | 658 | 561 | 687 | 653 | 609 | 594 | 700 | 0 | 45 |
| `K_support_only_positive` | 700 | 717 | 700 | 663 | 632 | 623 | 532 | 686 | 618 | 574 | 559 | 689 | 45 | 0 |

## Duration and positive-proportion distributions

The proportion metric is the maximum within-track positive fraction per case;
tracks with different sampling rates are not pooled.

| Metric | Minimum | q25 | q50 | q75 | q95 | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| Longest continuous positive duration (s) | 0 | 0 | 0 | 0 | 1424.16 | 27754.9 |
| Maximum within-track positive proportion | 0 | 0 | 0 | 0 | 1 | 1 |

### Duration histogram

| Bin | Cases |
|---|---:|
| `zero` | 2528 |
| `positive_under_10s` | 17 |
| `10_to_under_30s` | 33 |
| `30_to_under_60s` | 11 |
| `60_to_under_300s` | 97 |
| `300_to_under_600s` | 129 |
| `600_to_under_1800s` | 293 |
| `1800_to_under_3600s` | 54 |
| `3600s_or_more` | 57 |

### Positive-proportion histogram

| Bin | Cases |
|---|---:|
| `zero` | 2502 |
| `positive_under_0_1pct` | 20 |
| `0_1_to_under_1pct` | 72 |
| `1_to_under_5pct` | 44 |
| `5_to_under_10pct` | 15 |
| `10_to_under_25pct` | 19 |
| `25_to_under_50pct` | 4 |
| `50_to_under_75pct` | 4 |
| `75_to_100pct` | 539 |

## Agent-specific / GAS2 / MAC combinations

| Positive-recording combination | Cases |
|---|---:|
| `agent_specific_positive=false; gas2_positive=false; mac_positive=false` | 2502 |
| `agent_specific_positive=false; gas2_positive=false; mac_positive=true` | 7 |
| `agent_specific_positive=false; gas2_positive=true; mac_positive=false` | 2 |
| `agent_specific_positive=false; gas2_positive=true; mac_positive=true` | 8 |
| `agent_specific_positive=true; gas2_positive=false; mac_positive=false` | 28 |
| `agent_specific_positive=true; gas2_positive=false; mac_positive=true` | 144 |
| `agent_specific_positive=true; gas2_positive=true; mac_positive=false` | 28 |
| `agent_specific_positive=true; gas2_positive=true; mac_positive=true` | 500 |

## Fixed-seed boundary review samples (seed 20260720)

No sampled case is automatically included or excluded.

| Boundary category | All cases | Sample case IDs |
|---|---:|---|
| `10_to_under_30s` | 33 | 1839, 3143, 3248, 3863, 4150 |
| `30_to_under_60s` | 11 | 3462, 3635, 4289, 4882, 5632 |
| `60_to_under_300s` | 97 | 644, 746, 3881, 4973, 5178 |
| `agent_negative_support_positive` | 17 | 513, 3873, 4153, 4173, 5772 |
| `agent_positive_support_negative` | 28 | 321, 4196, 5296, 5652, 6124 |
| `any_positive_but_under_10s` | 43 | 321, 1074, 2311, 5626, 6097 |
| `duplicate_timestamp_or_abnormal_gap_warning` | 2106 | 1222, 2243, 2732, 4511, 5455 |
| `invalid_anesthesia_window` | 1 | 4476 |
| `positive_only_outside_anesthesia_window` | 10 | 2113, 3731, 4966, 5481, 5502 |

## Named protocol candidates — comparison only

| Candidate | Exact rule | Expected excluded | Expected retained |
|---|---|---:|---:|
| `conservative` | `A_any_allowed_positive_once` | 717 | 2502 |
| `duration-based` | `F_longest_positive_run_ge_60s` | 630 | 2589 |
| `corroborated` | `I_agent_specific_and_support_positive` | 672 | 2547 |

None is recommended or selected. Official documentary descriptions and units
remain evidence only; alias and unit approval remain `pending_human_review`.

## Work deliberately not performed

No API request or raw download occurred. Legacy 98 IDs, BIS, propofol,
remifentanil, CP, CE, VOL, prediction outcomes, and BIS values were not read.
No final rule, TIVA classification, cohort freeze, threshold, split, prediction
dataset, prediction, feature selection, Cp/Ce reconstruction, or PPO was run.
Phase 5D stops here.
