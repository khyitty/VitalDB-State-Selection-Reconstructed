# Phase 7A Subject Linkage and Patient-Level Split Feasibility Audit

## Boundary

This is an outcome-blind metadata-only linkage and count-feasibility audit. It
creates no train/validation/test membership, provisional split, ID list, test
seal, raw read, modeling array, preprocessing fit, or downstream analysis.

`subjectid` is used only because the official VitalDB parameter definition is
“Subject ID; Deidentified hospital ID of patient”. No re-identification or external linkage was
attempted. Subject IDs are retained only in versioned manifests and are not
listed in this report.

## Source verification

- Frozen eligible cases: 2460.
- Eligible case-ID checksum: `f2c140ccf150648c2d4f46029849f325742e58eaf16ecb30efa05299384fb9bd`.
- Subject-linkage checksum: `102ccc60d9f03a8bfe858e5862366ef0b49f80cef3dcc027dae94afface464f7`.
- Missing or unparsable subject IDs: 0.
- Duplicate or ambiguous case-to-subject mappings: 0.
- Ineligible-case overlap: 0.

## Subject-level accounting

- Unique subjects: 2415.
- Repeated subjects: 37.
- Cases belonging to repeated subjects: 82
  (3.333333% of cases).
- Largest subject cluster: 9 cases.

| Cluster size | Subjects | Cases |
|---:|---:|---:|
| 1 | 2378 | 2378 |
| 2 | 35 | 70 |
| 3 | 1 | 3 |
| 9 | 1 | 9 |

The cases-per-subject distribution and quantiles are machine-readable in the
summary JSON. Exact subject IDs appear only in the linkage and subject-level
manifests.

## Within-subject consistency

Exact-source sex inconsistency warnings: 0. Warnings are preserved
without correcting linkage. Age, height, weight, BMI, ASA, emergency status, and
operation type are described as potentially time-varying case metadata and do
not invalidate linkage.

## Count-only feasibility

- Nearest case targets: train 1722,
  validation 369,
  test 369.
- Nearest subject targets: train 1691,
  validation 362,
  test 362.
- Exact nearest case targets are arithmetically feasible from the cluster-size
  histogram: true.
- Exact joint nearest case and subject targets are arithmetically feasible:
  true.
- Minimum total absolute case-count deviation under nearest subject targets:
  0.

These are count-only facts. No subject or case was assigned to a split. The three
future objective alternatives remain unselected.

## Future metadata inventory

Future subject-level allocation must move every subject with the sum of all its
case-level sex, age-group, BMI-group, ASA-group, emergency-group, and exact
operation-type marginal contributions. A subject must not be collapsed to one
operation type or mean ASA.

## Stop boundary

Phase 7B patient-level allocation is not authorized. No outcome, BIS, SQI, drug
rate, raw signal, API, normalization, imputation, dose, Cp/Ce, persistence,
prediction, feature selection, model, test seal, or PPO operation occurred.
