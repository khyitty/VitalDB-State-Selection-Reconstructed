# Phase 6B Primary Signal Quality Characterization

## Facts

- Phase 6A acquisition cases: `2470`.
- Exact case×track rows characterized: `9880`.
- All measures retain original row order and distinguish the full recording from the inherited anesthesia window.
- Common observed span is only the overlap of first/last finite timestamp ranges; it is not continuous coverage.
- Long gaps are descriptive. Event-style drug-rate cadence may not represent missingness.
- BIS/SQI remains QC-only and was not added to any feature or PPO universe.

## Track accounting

| Exact track | Cases | Duplicate-timestamp cases | Negative-interval cases |
|---|---:|---:|---:|
| `BIS/BIS` | 2470 | 7 | 0 |
| `BIS/SQI` | 2470 | 7 | 0 |
| `Orchestra/PPF20_RATE` | 2470 | 17 | 0 |
| `Orchestra/RFTN20_RATE` | 2470 | 17 | 0 |

## Interpretation boundary

No quality cutoff, valid-BIS range, SQI threshold, gap rule, or combined scenario was selected.
The tables are outcome-blind sensitivity material for a future Protocol v1.2 human decision.

Observed-span ratios use only first/last timestamps. Timestamp-gap rules are descriptive and may behave differently for event-style drug-rate recordings.

## Scenario definitions

- `permissive`: anesthesia >=20 min; common span >=10 min; BIS 0-100 fraction >=80%; both drug tracks have >=1 positive record; no negative rate.
- `moderate`: anesthesia >=30 min; common span >=20 min; BIS 10-100 fraction >=80%; SQI >=50 fraction >=50%; both drug tracks have >=3 positive records; no negative rate.
- `strict`: anesthesia >=60 min; common span >=30 min; BIS 10-100 fraction >=90%; SQI >=50 fraction >=80%; both drug tracks have >=3 positive records; no negative rate.

## Combined scenario comparison

| Scenario | Pass | Fail | Selected |
|---|---:|---:|---|
| permissive | 2464 | 6 | no |
| moderate | 2333 | 137 | no |
| strict | 1723 | 747 | no |

## Marginal sensitivity

Every row below is an independent comparison, not a selected rule.

| Category | Metric | Threshold | Pass | Fail | Missing measure |
|---|---|---:|---:|---:|---:|
| anesthesia_window_duration | `anesthesia_duration_seconds` | >=10min | 2470 | 0 | 0 |
| anesthesia_window_duration | `anesthesia_duration_seconds` | >=20min | 2470 | 0 | 0 |
| anesthesia_window_duration | `anesthesia_duration_seconds` | >=30min | 2470 | 0 | 0 |
| anesthesia_window_duration | `anesthesia_duration_seconds` | >=60min | 2447 | 23 | 0 |
| anesthesia_window_duration | `anesthesia_duration_seconds` | >=120min | 1769 | 701 | 0 |
| common_observed_span_duration | `common_observed_span_duration_seconds` | >=10min | 2465 | 5 | 2 |
| common_observed_span_duration | `common_observed_span_duration_seconds` | >=20min | 2464 | 6 | 2 |
| common_observed_span_duration | `common_observed_span_duration_seconds` | >=30min | 2458 | 12 | 2 |
| common_observed_span_duration | `common_observed_span_duration_seconds` | >=60min | 2310 | 160 | 2 |
| common_observed_span_ratio | `common_observed_span_to_anesthesia_duration_ratio` | >=50% | 2431 | 39 | 2 |
| common_observed_span_ratio | `common_observed_span_to_anesthesia_duration_ratio` | >=70% | 2269 | 201 | 2 |
| common_observed_span_ratio | `common_observed_span_to_anesthesia_duration_ratio` | >=80% | 1922 | 548 | 2 |
| common_observed_span_ratio | `common_observed_span_to_anesthesia_duration_ratio` | >=90% | 1131 | 1339 | 2 |
| common_observed_span_ratio | `common_observed_span_to_anesthesia_duration_ratio` | >=95% | 475 | 1995 | 2 |
| bis_descriptive_range_fraction | `bis_0_100_fraction_of_finite` | >=50% | 2468 | 2 | 2 |
| bis_descriptive_range_fraction | `bis_0_100_fraction_of_finite` | >=70% | 2468 | 2 | 2 |
| bis_descriptive_range_fraction | `bis_0_100_fraction_of_finite` | >=80% | 2468 | 2 | 2 |
| bis_descriptive_range_fraction | `bis_0_100_fraction_of_finite` | >=90% | 2468 | 2 | 2 |
| bis_descriptive_range_fraction | `bis_0_100_fraction_of_finite` | >=95% | 2468 | 2 | 2 |
| bis_descriptive_range_fraction | `bis_10_100_fraction_of_finite` | >=50% | 2461 | 9 | 2 |
| bis_descriptive_range_fraction | `bis_10_100_fraction_of_finite` | >=70% | 2432 | 38 | 2 |
| bis_descriptive_range_fraction | `bis_10_100_fraction_of_finite` | >=80% | 2334 | 136 | 2 |
| bis_descriptive_range_fraction | `bis_10_100_fraction_of_finite` | >=90% | 1743 | 727 | 2 |
| bis_descriptive_range_fraction | `bis_10_100_fraction_of_finite` | >=95% | 992 | 1478 | 2 |
| sqi_descriptive_fraction | `sqi_ge_20_fraction_of_finite` | >=50% | 2461 | 9 | 2 |
| sqi_descriptive_fraction | `sqi_ge_20_fraction_of_finite` | >=70% | 2428 | 42 | 2 |
| sqi_descriptive_fraction | `sqi_ge_20_fraction_of_finite` | >=80% | 2331 | 139 | 2 |
| sqi_descriptive_fraction | `sqi_ge_20_fraction_of_finite` | >=90% | 1716 | 754 | 2 |
| sqi_descriptive_fraction | `sqi_ge_20_fraction_of_finite` | >=95% | 943 | 1527 | 2 |
| sqi_descriptive_fraction | `sqi_ge_50_fraction_of_finite` | >=50% | 2458 | 12 | 2 |
| sqi_descriptive_fraction | `sqi_ge_50_fraction_of_finite` | >=70% | 2406 | 64 | 2 |
| sqi_descriptive_fraction | `sqi_ge_50_fraction_of_finite` | >=80% | 2173 | 297 | 2 |
| sqi_descriptive_fraction | `sqi_ge_50_fraction_of_finite` | >=90% | 1250 | 1220 | 2 |
| sqi_descriptive_fraction | `sqi_ge_50_fraction_of_finite` | >=95% | 437 | 2033 | 2 |
| sqi_descriptive_fraction | `sqi_ge_80_fraction_of_finite` | >=50% | 2196 | 274 | 2 |
| sqi_descriptive_fraction | `sqi_ge_80_fraction_of_finite` | >=70% | 962 | 1508 | 2 |
| sqi_descriptive_fraction | `sqi_ge_80_fraction_of_finite` | >=80% | 315 | 2155 | 2 |
| sqi_descriptive_fraction | `sqi_ge_80_fraction_of_finite` | >=90% | 37 | 2433 | 2 |
| sqi_descriptive_fraction | `sqi_ge_80_fraction_of_finite` | >=95% | 2 | 2468 | 2 |
| timestamp_gap | `BIS/BIS longest strictly positive gap` | <=30s | 2258 | 212 | 2 |
| timestamp_gap | `BIS/BIS longest strictly positive gap` | <=60s | 2376 | 94 | 2 |
| timestamp_gap | `BIS/BIS longest strictly positive gap` | <=120s | 2403 | 67 | 2 |
| timestamp_gap | `BIS/BIS longest strictly positive gap` | <=300s | 2435 | 35 | 2 |
| timestamp_gap | `BIS/BIS longest strictly positive gap` | <=600s | 2444 | 26 | 2 |
| timestamp_gap | `Orchestra/PPF20_RATE longest strictly positive gap` | <=30s | 2025 | 445 | 0 |
| timestamp_gap | `Orchestra/PPF20_RATE longest strictly positive gap` | <=60s | 2152 | 318 | 0 |
| timestamp_gap | `Orchestra/PPF20_RATE longest strictly positive gap` | <=120s | 2206 | 264 | 0 |
| timestamp_gap | `Orchestra/PPF20_RATE longest strictly positive gap` | <=300s | 2305 | 165 | 0 |
| timestamp_gap | `Orchestra/PPF20_RATE longest strictly positive gap` | <=600s | 2409 | 61 | 0 |
| timestamp_gap | `Orchestra/RFTN20_RATE longest strictly positive gap` | <=30s | 2054 | 416 | 0 |
| timestamp_gap | `Orchestra/RFTN20_RATE longest strictly positive gap` | <=60s | 2170 | 300 | 0 |
| timestamp_gap | `Orchestra/RFTN20_RATE longest strictly positive gap` | <=120s | 2235 | 235 | 0 |
| timestamp_gap | `Orchestra/RFTN20_RATE longest strictly positive gap` | <=300s | 2325 | 145 | 0 |
| timestamp_gap | `Orchestra/RFTN20_RATE longest strictly positive gap` | <=600s | 2419 | 51 | 0 |
| drug_evidence | `propofol_positive_record_count` | >=1 | 2469 | 1 | 0 |
| drug_evidence | `propofol_positive_record_count` | >=3 | 2469 | 1 | 0 |
| drug_evidence | `remifentanil_positive_record_count` | >=1 | 2469 | 1 | 0 |
| drug_evidence | `remifentanil_positive_record_count` | >=3 | 2469 | 1 | 0 |
| drug_evidence | `both_drugs_positive_record_count` | each>=1 | 2469 | 1 | 0 |
| drug_evidence | `both_drugs_positive_record_count` | each>=3 | 2469 | 1 | 0 |

## Boundary review

Fixed seed `20260720`; at most five IDs per category. Samples do not alter inclusion.

- `bis_10_100_fraction_70_80pct`: 98 cases in category
- `bis_10_100_fraction_80_90pct`: 591 cases in category
- `bis_no_finite`: 2 cases in category
- `common_span_10_20m`: 1 cases in category
- `common_span_20_30m`: 6 cases in category
- `duplicate_or_negative_timestamp_interval`: 17 cases in category
- `longest_gap_30_60s`: 142 cases in category
- `longest_gap_60_120s`: 71 cases in category
- `propofol_no_positive`: 1 cases in category
- `remifentanil_no_positive`: 1 cases in category
- `sqi_ge_50_fraction_40_50pct`: 5 cases in category

## Prohibited work

No API request, raw rewrite, interpolation, resampling, cohort freeze, split, prediction, Cp/Ce, dose calculation, feature selection, or PPO execution occurred.
