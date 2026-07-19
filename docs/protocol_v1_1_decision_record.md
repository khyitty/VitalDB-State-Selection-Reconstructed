# Protocol v1.1 Decision Record

Status: human-approved for Phase 6A on 2026-07-20. This record fixes only the
pre-quality acquisition cohort and the permitted primary-signal acquisition. It
does not freeze final eligibility or select a signal-quality threshold.

## Metadata universe

A case enters the 3,219-case protocol universe only when all of the following
hold: age is at least 18; `anesthesia_type` is exactly `General`; and the exact
tracks `BIS/BIS`, `Orchestra/PPF20_RATE`, and `Orchestra/RFTN20_RATE` are all
present. The universe is inherited from the checksum-verified Phase 5C/5D
artifacts and is not recomputed from a sample.

## Primary volatile exclusion

The primary exclusion is Phase 5D definition
`D_longest_positive_run_ge_10s`: within the anesthesia window, at least one of
the seven Phase 5C exact volatile tracks has a continuous positive run lasting
at least 10 seconds. The verified Phase 5D method is reused without alteration:

- timestamps remain in original payload order;
- the per-case, per-track continuity boundary is three times the median of
  strictly positive consecutive timestamp differences inside the anesthesia
  window;
- duplicate, zero, or negative timestamp intervals break continuity;
- gaps greater than the continuity boundary break continuity and are not added
  to duration;
- runs are never joined across tracks; and
- a single positive sample has duration zero.

The any-positive, 60-second, and corroborated Phase 5D definitions remain
robustness scenarios only. They do not control Phase 6A inclusion.

## Invalid anesthesia window

Case 4476 retains its observed inverted anesthesia window. It is not repaired.
It receives `ineligible_invalid_anesthesia_window` and is excluded from primary
signal acquisition independently of all other exclusion reasons.

## Exact track and unit decisions

The official `Dataset : VitalDB` table was reviewed on 2026-07-20 at the URL
recorded in `configs/track_aliases.yaml`. The retrieved source had SHA-256
`06c1779012389cd80d2a621abf38ad564b1446315ff79264bb1470fbf82db394`.

- `BIS/BIS`: primary BIS signal; unitless; no numeric unit conversion.
- `BIS/SQI`: signal quality index in percent; QC-only; prohibited as a
  prediction feature or PPO state.
- `Orchestra/PPF20_RATE`: mL/hr for propofol 20 mg/mL.
- `Orchestra/RFTN20_RATE`: mL/hr for remifentanil 20 mcg/mL.
- `Orchestra/RFTN50_RATE` is not merged with RFTN20 and is unused in Phase 6A.

Only these four exact Phase 6A signal names may be requested. No alias expansion
or fuzzy matching is allowed.

## Legacy overlap

Only the `caseid` columns of the three preserved actual-use split artifacts at
legacy commit `9501b16a5c4db27f06fa0d0b252a3a75f633967f` may be read. Their
union must contain exactly 98 unique IDs. Split labels, outcomes, results,
metrics, features, and any reconstructed “first 100” set are prohibited. The
new manifest records overlap only as an exclusion provenance flag.

## Phase 6A boundary

The resulting `pre_quality_acquisition_cohort` is not final eligibility and is
not frozen. Phase 6A may acquire only `BIS/BIS`, `BIS/SQI`,
`Orchestra/PPF20_RATE`, and `Orchestra/RFTN20_RATE` after the fixed-seed
25-case operational and two-times-disk-space preflight passes. Acquisition may
not choose coverage, gap, or other quality cutoffs; resample; interpolate;
smooth; clip; form analysis windows; create a split; reconstruct Cp/Ce;
calculate doses; train or select models/features; or execute PPO.
