# Phase 5C Targeted Volatile-Signal Characterization

## Interpretation boundary

This is outcome-blind eligibility decision support. Track presence is not
volatile exposure, and a positive recorded value is not a finalized TIVA
exclusion rule. No exposure definition or cutoff was selected.

## Accounting and preflight gate

| Measure | Count / status |
|---|---:|
| Analysis-universe cases | 3219 |
| Duplicate cases | 0 |
| Missing cases | 0 |
| Case×track rows | 22533 |
| Preflight disk gate | True |
| Preflight operational gate | True |

## Track outcomes and descriptive positive recording

| Exact track | Present | Complete | Empty | Failed | All observed values zero | Positive in anesthesia window |
|---|---:|---:|---:|---:|---:|---:|
| `Primus/EXP_SEVO` | 1390 | 1390 | 0 | 0 | 1017 | 369 |
| `Primus/INSP_SEVO` | 1390 | 1390 | 0 | 0 | 1030 | 356 |
| `Primus/EXP_DES` | 991 | 991 | 0 | 0 | 610 | 375 |
| `Primus/INSP_DES` | 991 | 991 | 0 | 0 | 622 | 363 |
| `Solar8000/GAS2_EXPIRED` | 544 | 544 | 0 | 0 | 0 | 538 |
| `Solar8000/GAS2_INSPIRED` | 544 | 544 | 0 | 0 | 21 | 517 |
| `Primus/MAC` | 3209 | 3209 | 0 | 0 | 2540 | 659 |

## Track-level distributions of case summaries

Each cell below is the across-case q05 / q50 / q95 of the named case-level
summary. This avoids silently weighting cases by their number of recorded samples.

| Exact track | Case empirical median | Case maximum | Positive fraction | Longest positive run in anesthesia window (s) |
|---|---:|---:|---:|---:|
| `Primus/EXP_SEVO` | 0 / 0 / 0 | 0 / 0 / 3.6 | 0 / 0 / 0.3291 | 0 / 0 / 1460 |
| `Primus/INSP_SEVO` | 0 / 0 / 0 | 0 / 0 / 5.9 | 0 / 0 / 0.2276 | 0 / 0 / 1086 |
| `Primus/EXP_DES` | 0 / 0 / 1 | 0 / 0 / 6 | 0 / 0 / 0.779 | 0 / 0 / 1977 |
| `Primus/INSP_DES` | 0 / 0 / 0.6 | 0 / 0 / 7.8 | 0 / 0 / 0.5809 | 0 / 0 / 1395 |
| `Solar8000/GAS2_EXPIRED` | 0.3 / 0.9 / 3.7 | 0.6 / 3.1 / 7 | 0.9913 / 1 / 1 | 240 / 998 / 1.318e+04 |
| `Solar8000/GAS2_INSPIRED` | 0 / 1 / 4.6 | 0.7 / 4.5 / 9.8 | 0.4219 / 0.8942 / 1 | 96.02 / 742 / 1.106e+04 |
| `Primus/MAC` | 0 / 0 / 0 | 0 / 0 / 1.2 | 0 / 0 / 0.1127 | 0 / 0 / 1112 |

All per-case minimum, empirical quantiles, maximum, counts, fractions, and
positive-run measures remain in the machine-readable summary and track manifest.
Quantiles use observed values only; no resampling, interpolation, smoothing,
clipping, or abnormal-value deletion was performed.

## Exact track-presence combinations

| Exact-track presence combination | Cases |
|---|---:|
| `primus_exp_sevo=false; primus_insp_sevo=false; primus_exp_des=false; primus_insp_des=false; solar8000_gas2_expired=false; solar8000_gas2_inspired=false; primus_mac=false` | 8 |
| `primus_exp_sevo=false; primus_insp_sevo=false; primus_exp_des=false; primus_insp_des=false; solar8000_gas2_expired=false; solar8000_gas2_inspired=false; primus_mac=true` | 976 |
| `primus_exp_sevo=false; primus_insp_sevo=false; primus_exp_des=false; primus_insp_des=false; solar8000_gas2_expired=true; solar8000_gas2_inspired=true; primus_mac=false` | 2 |
| `primus_exp_sevo=false; primus_insp_sevo=false; primus_exp_des=false; primus_insp_des=false; solar8000_gas2_expired=true; solar8000_gas2_inspired=true; primus_mac=true` | 8 |
| `primus_exp_sevo=false; primus_insp_sevo=false; primus_exp_des=true; primus_insp_des=true; solar8000_gas2_expired=false; solar8000_gas2_inspired=false; primus_mac=true` | 631 |
| `primus_exp_sevo=false; primus_insp_sevo=false; primus_exp_des=true; primus_insp_des=true; solar8000_gas2_expired=true; solar8000_gas2_inspired=true; primus_mac=true` | 204 |
| `primus_exp_sevo=true; primus_insp_sevo=true; primus_exp_des=false; primus_insp_des=false; solar8000_gas2_expired=false; solar8000_gas2_inspired=false; primus_mac=true` | 1052 |
| `primus_exp_sevo=true; primus_insp_sevo=true; primus_exp_des=false; primus_insp_des=false; solar8000_gas2_expired=true; solar8000_gas2_inspired=true; primus_mac=true` | 182 |
| `primus_exp_sevo=true; primus_insp_sevo=true; primus_exp_des=true; primus_insp_des=true; solar8000_gas2_expired=false; solar8000_gas2_inspired=false; primus_mac=true` | 8 |
| `primus_exp_sevo=true; primus_insp_sevo=true; primus_exp_des=true; primus_insp_des=true; solar8000_gas2_expired=true; solar8000_gas2_inspired=true; primus_mac=true` | 148 |

## Primus agent-specific, GAS2, and MAC positive-recording combinations

These are descriptive anesthesia-window recording combinations, not exposure
or TIVA classifications.

| Recorded-positive combination | Cases |
|---|---:|
| `agent_specific_positive=false; gas2_positive=false; mac_positive=false` | 2502 |
| `agent_specific_positive=false; gas2_positive=false; mac_positive=true` | 7 |
| `agent_specific_positive=false; gas2_positive=true; mac_positive=false` | 2 |
| `agent_specific_positive=false; gas2_positive=true; mac_positive=true` | 8 |
| `agent_specific_positive=true; gas2_positive=false; mac_positive=false` | 28 |
| `agent_specific_positive=true; gas2_positive=false; mac_positive=true` | 144 |
| `agent_specific_positive=true; gas2_positive=true; mac_positive=false` | 28 |
| `agent_specific_positive=true; gas2_positive=true; mac_positive=true` | 500 |

## Fixed-seed boundary samples (seed 20260720)

| Review category | Case IDs |
|---|---|
| `agent_specific_vs_gas2_or_mac_discordant` | 2118, 2953, 3431, 3956, 4173 |
| `download_parse_or_value_warning` | 2317, 3369, 4805, 4859, 4899 |
| `positive_only_outside_anesthesia_window` | 3414, 4006, 4476, 5311, 5502 |
| `present_track_all_zero` | 831, 2925, 3538, 6123, 6338 |


## Possible exposure definitions — descriptive comparison only

| Candidate definition | Cases |
|---|---:|
| `any_allowed_track_positive_anywhere` | 727 |
| `any_allowed_track_positive_in_anesthesia_window` | 717 |
| `primus_agent_specific_positive_in_anesthesia_window` | 700 |
| `solar_gas2_positive_in_anesthesia_window` | 538 |
| `primus_mac_positive_in_anesthesia_window` | 659 |
| `agent_specific_and_gas2_or_mac_positive_in_anesthesia_window` | 672 |

## Primary-source descriptions

The official VitalDB overview describes Primus sevoflurane/desflurane
tracks in kPa, Solar8000 GAS2 tracks in %, and Primus/MAC as unitless.
These descriptions are recorded without changing versioned approval status.

- [Official VitalDB dataset overview](https://vitaldb.net/dataset/?documentId=13qqajnNZzkN7NZ9aXnaQ-47NWy7kx-a6gbrcEsi-gak&query=overview&sectionId=h.vcpgs1yemdb5)

## Work deliberately not performed

Legacy 98 IDs were not accessed. No final volatile/TIVA determination, alias
or unit approval, threshold, cohort freeze, split, BIS/drug signal download,
prediction preprocessing, prediction, feature selection, Cp/Ce reconstruction,
or PPO execution occurred. Phase 5C stops here.
