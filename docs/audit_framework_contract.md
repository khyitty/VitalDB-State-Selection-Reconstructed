# Eligibility Audit Framework Contract

## Implemented accounting boundary

The production metadata entry point always constructs case IDs 1–6388 and writes
one schema-validated row per ID. A missing clinical row, duplicate clinical row,
source-query failure, or missing required track becomes an explicit row state; it
is never removed from the manifest.

The code contains no production case-limit option. Both runtime guards and an AST
scanner reject first-N selection constructs in production entry points.

## Deliberately unresolved research decisions

The framework does not decide or infer:

- the 98 legacy case IDs;
- TIVA classification;
- volatile-agent aliases or exposure;
- propofol or remifentanil rate units;
- signal-quality thresholds;
- final eligibility;
- cohort freeze or train/validation/test split.

Those fields remain `null`, `false`, or carry explicit `*_pending` flags. Therefore
the Phase 3 framework produces no human-authorized metadata-stage candidates.

## Exact alias policy

Only these protocol-listed names are active for presence inventory:

- `BIS/BIS`
- `Orchestra/PPF20_RATE`
- `Orchestra/RFTN20_RATE`

Matching is exact. Unknown or similar names are not promoted. Drug-rate units are
still `pending_human_review`, even when an exact track name is present.

## Download behavior

Before any attempt, every requested case receives a download-manifest row. Each
attempt updates that row atomically. Failures include type, message, retryability,
attempt count, and a JSONL traceback record. Network-like failures may be attempted
at most three times. A completed case is skipped only after every stored checksum
matches the on-disk file.

The production download script additionally requires a human authorization file,
a full 1–6388 eligibility manifest, finalized candidate flags, and validated drug
rate units. These prerequisites are intentionally unsatisfied in Phase 3.

## Data source

The independent implementation uses the documented VitalDB Open Dataset Web API:
`https://api.vitaldb.net/cases`, `https://api.vitaldb.net/trks`, and
`https://api.vitaldb.net/{tid}`. No legacy download code or data artifact was copied.

## Interpretation

Synthetic tests establish software invariants only. They do not establish the
number of eligible patients, track semantics, unit validity, signal quality, or any
prediction/control result.
