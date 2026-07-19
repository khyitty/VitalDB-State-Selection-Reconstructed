# Phase 5B Eligibility Decision-Support Audit

## Interpretation boundary

This is an outcome-blind decision-support inventory, not an eligibility rule
selection or cohort freeze. Track presence does not prove non-zero drug delivery
or volatile-agent exposure. No raw time-series signal or legacy 98-case ID was
accessed. No alias or unit configuration was approved or changed.

## Complete manifest accounting

| Measure | Count |
|---|---:|
| Phase 5A manifest rows | 6388 |
| Phase 5B presence rows | 6388 |
| Duplicate case IDs | 0 |
| Missing case IDs | 0 |

## Full 6,388-case clinical descriptors

### Anesthesia type

| Exact source value | Cases |
|---|---:|
| `General` | 6043 |
| `Spinal` | 273 |
| `Sedationalgesia` | 72 |

### Operation type

| Exact source value | Cases |
|---|---:|
| `Colorectal` | 1350 |
| `Biliary/Pancreas` | 812 |
| `Others` | 799 |
| `Stomach` | 676 |
| `Major resection` | 584 |
| `Minor resection` | 553 |
| `Breast` | 434 |
| `Transplantation` | 403 |
| `Vascular` | 262 |
| `Hepatic` | 258 |
| `Thyroid` | 257 |

### Emergency status

| Exact source value | Cases |
|---|---:|
| `0` | 5606 |
| `1` | 782 |

### Age and ASA completeness

Observed age range: **0.3–94.0 years**; missing age: **0**.
Adult status is the protocol-defined descriptive flag `age >= 18`; it is not a cohort decision.

| Adult-status flag | Cases |
|---|---:|
| `adult_age_ge_18` | 6331 |
| `not_adult_age_lt_18` | 57 |

ASA is available in **6255** cases and missing in **133** cases.

## Narrow research-relevant unapproved-track review

Only the 21 requested or explicitly volatile-labeled names below were reviewed;
the other Phase 5A names were not semantically classified. All remain
`pending_human_review`, and no RFTN20/RFTN50 merge was performed.

| Track | Official description | Unit in official overview | Cases | Rows |
|---|---|---|---:|---:|
| `BIS/SQI` | Signal quality index | % | 5867 | 5867 |
| `Orchestra/PPF20_VOL` | Infused volume (propofol 20 mg/mL) | mL | 3512 | 3512 |
| `Orchestra/PPF20_CP` | Plasma concentration (propofol 20 mg/mL) | mcg/mL | 3511 | 3511 |
| `Orchestra/PPF20_CE` | Effect-site concentration (propofol 20 mg/mL) | mcg/mL | 3511 | 3511 |
| `Orchestra/PPF20_CT` | Target concentration (propofol 20 mg/mL) | mcg/mL | 3511 | 3511 |
| `Orchestra/RFTN20_VOL` | Infused volume (remifentanil 20 mcg/mL) | mL | 4773 | 4774 |
| `Orchestra/RFTN20_CP` | Plasma concentration (remifentanil 20 mcg/mL) | ng/mL | 4770 | 4771 |
| `Orchestra/RFTN20_CE` | Effect-site concentration (remifentanil 20 mcg/mL) | ng/mL | 4770 | 4771 |
| `Orchestra/RFTN20_CT` | Target concentration (remifentanil 20 mcg/mL) | ng/mL | 4770 | 4771 |
| `Orchestra/RFTN50_RATE` | Infusion rate (remifentanil 50 mcg/mL) | mL/hr | 68 | 69 |
| `Orchestra/RFTN50_VOL` | Infused volume (remifentanil 50 mcg/mL) | mL | 68 | 69 |
| `Orchestra/RFTN50_CP` | Plasma concentration (remifentanil 50 mcg/mL) | ng/mL | 68 | 69 |
| `Orchestra/RFTN50_CE` | Effect-site concentration (remifentanil 50 mcg/mL) | ng/mL | 68 | 69 |
| `Orchestra/RFTN50_CT` | Target concentration (remifentanil 50 mcg/mL) | ng/mL | 68 | 69 |
| `Primus/EXP_SEVO` | Expiratory sevoflurane pressure | not reviewed here | 3687 | 3687 |
| `Primus/INSP_SEVO` | Inspiratory sevoflurane pressure | not reviewed here | 3687 | 3687 |
| `Primus/EXP_DES` | Expiratory desflurane pressure | not reviewed here | 2046 | 2046 |
| `Primus/INSP_DES` | Inspiratory desflurane pressure | not reviewed here | 2046 | 2046 |
| `Solar8000/GAS2_EXPIRED` | Expiratory volatile concentration | not reviewed here | 3097 | 3097 |
| `Solar8000/GAS2_INSPIRED` | Inspiratory volatile concentration | not reviewed here | 3097 | 3097 |
| `Primus/MAC` | Minimum alveolar concentration of volatile | not reviewed here | 6338 | 6338 |

## Exact-primary subset (3,289 cases)

### Anesthesia type

| Exact source value | Cases |
|---|---:|
| `General` | 3228 |
| `Sedationalgesia` | 50 |
| `Spinal` | 11 |

### Adult status

| Value | Cases |
|---|---:|
| `adult_age_ge_18` | 3279 |
| `not_adult_age_lt_18` | 10 |

### Volatile-candidate track presence

| Value | Cases |
|---|---:|
| `present` | 3281 |
| `absent` | 8 |

### BIS/SQI and PPF/RFTN support-track presence

| Track-presence field | Present | Absent |
|---|---:|---:|
| `bis_sqi_present` | 3289 | 0 |
| `ppf20_vol_present` | 3289 | 0 |
| `ppf20_cp_present` | 3288 | 1 |
| `ppf20_ce_present` | 3288 | 1 |
| `rftn20_vol_present` | 3289 | 0 |
| `rftn20_cp_present` | 3288 | 1 |
| `rftn20_ce_present` | 3288 | 1 |
| `rftn50_rate_present` | 0 | 3289 |
| `rftn50_vol_present` | 0 | 3289 |
| `rftn50_cp_present` | 0 | 3289 |
| `rftn50_ce_present` | 0 | 3289 |

The full joint combination table is retained in the machine-readable summary
(7 observed combinations; counts sum to 3,289).

## Eligibility scenarios — comparison only

No scenario was selected. `General` is matched as the exact source value, and
the volatile criterion is track presence only, not measured exposure.

| Scenario | Descriptive expected cases | Excluded from 6,388 |
|---|---:|---:|
| `exact_primary_tracks_only` | 3289 | 3099 |
| `exact_primary_plus_adult_plus_exact_general` | 3219 | 3169 |
| `exact_primary_plus_adult_plus_exact_general_plus_no_volatile_candidate_track` | 8 | 6380 |

### Sequential exclusion accounting

**`exact_primary_tracks_only`**

| Reason | Cases |
|---|---:|
| `missing_one_or_more_exact_primary_tracks` | 3099 |

**`exact_primary_plus_adult_plus_exact_general`**

| Reason | Cases |
|---|---:|
| `missing_one_or_more_exact_primary_tracks` | 3099 |
| `not_adult_after_exact_primary` | 10 |
| `anesthesia_type_not_exact_general_after_primary_and_adult` | 60 |

**`exact_primary_plus_adult_plus_exact_general_plus_no_volatile_candidate_track`**

| Reason | Cases |
|---|---:|
| `missing_one_or_more_exact_primary_tracks` | 3099 |
| `not_adult_after_exact_primary` | 10 |
| `anesthesia_type_not_exact_general_after_primary_and_adult` | 60 |
| `volatile_candidate_track_present_after_prior_criteria` | 3211 |

## Primary-source unit and label review

The official VitalDB dataset overview documents `PPF20_RATE`, `RFTN20_RATE`,
and `RFTN50_RATE` as `mL/hr`. It labels PPF20 as propofol 20 mg/mL and
RFTN20/RFTN50 as remifentanil 20/50 mcg/mL. This documentary finding does
not change the versioned unit-review status and does not merge the two
remifentanil track families.

- [Official VitalDB dataset overview](https://vitaldb.net/dataset/?documentId=13qqajnNZzkN7NZ9aXnaQ-47NWy7kx-a6gbrcEsi-gak&query=overview&sectionId=h.vcpgs1yemdb5)
- [Official VitalDB Open Dataset API](https://vitaldb.net/docs/?documentId=API%2FWeb_API_OpenDataset.md)

## Work deliberately not performed

No raw-signal download, legacy-ID access, final alias approval, threshold
finalization, cohort freeze, split, prediction, feature selection, Cp/Ce
reconstruction, or PPO execution occurred. Phase 5B stops here.
