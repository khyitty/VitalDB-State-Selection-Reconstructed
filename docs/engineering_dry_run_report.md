# Random 25-case Engineering Dry Run Report

## Interpretation boundary

This is an engineering execution record, **not a scientific result**. It does not
define eligibility, signal-quality thresholds, an eligible cohort, a split, a
feature set, a prediction result, a Cp/Ce result, or a PPO result.

## Reproducible sample

- Seed: `20260719`
- Method: fixed-seed random sampling without replacement
- Universe check: exactly case IDs 1–6388, with no duplicate or missing ID
- Sample size: 25
- First-25 sample: no
- Case IDs: `347, 355, 1149, 1189, 1213, 1380, 1486, 1655, 2183, 2372, 2440, 2573, 2635, 2840, 2969, 3137, 3430, 3736, 3865, 4094, 4527, 4640, 4998, 5451, 6002`

Metadata parsing completed for all 25 cases. Exact alias counts were recorded, but
no unknown alias was promoted and drug-rate units remain `pending_human_review`.

## Signal dry run

All 25 sampled cases were inserted into the download manifest before attempts.

| Result | Cases |
|---|---:|
| Complete with verified checksums | 12 |
| Explicit non-retryable failure | 13 |
| Total accounted | 25 |

The 13 failures were all `NonRetryableDownloadError` records caused by one or more
required exact tracks being absent. They were not excluded. The manifest attempt
count remained 1 for every case after resume, confirming that completed checksum
matches and non-retryable failures were skipped correctly.

## Runtime and storage observations

- Recorded first-attempt span: 5.473 seconds
- Checksum/resume pass: 0.182 seconds, excluding metadata endpoint fetch
- Raw files: 72
- Raw bytes: 11,479,299
- Completed-case median bytes: 668,450.5
- Completed-case P90 bytes: 2,282,719
- Completed-case median recorded duration: 0.364 seconds
- Completed-case P90 recorded duration: 0.471 seconds
- Case-level failure rate: 13/25 (0.52)
- Retry cases: 0
- Failure-log rows: 13
- Checksum mismatches after independent verification: 0
- Partial `.part` files: 0

The failure rate reflects random-case required-track presence, not network
reliability or cohort eligibility. A full-production time/storage estimate was not
calculated because the authorized candidate count and rate units remain unresolved.

## Commands

```powershell
python -m unittest discover -s tests -v
python scripts/run_engineering_dry_run.py
python scripts/run_engineering_dry_run.py --with-signals
```

Raw files remain Git-ignored. The committed manifests contain per-file SHA-256
checksums, explicit failures, source snapshot hashes, and a checksum inventory for
the small committed dry-run artifacts.
