# Phase 8B train-template decision record

The approved operational anesthesia-window source is `data/manifests/primary_signal_quality_case_manifest.csv` at SHA-256 `911e4b44e626cc9f7d4944c825011c8e6b7b5b2be486dd8d7a29af9586913d5d`. Its upstream authoritative lineage is `data/manifests/volatile_signal_case_manifest.csv` at SHA-256 `66c65af9fa72467c29544e6d9c84550449370e61781b703461f83508964f30a8`. Exact strings and finite numeric interpretations matched for all 1,970 sealed train cases.

Only `BIS/BIS` and `BIS/SQI` were read through the train-only SplitGuard. One private pseudonymous template is reused for P0 and P1. BIS values were used transiently only to derive availability; SQI exact matches remain private. Test templates, drug histories, normalization, outcome access, simulation with real profiles, PPO, models, and checkpoints remain prohibited.

The Phase 8A verify-only source gate was made descendant-compatible while its
generation gate remains exact-starting-ref only. This is a maintenance fix, not
a protocol amendment; Phase 8A membership, seed, manifests, and seal are unchanged.
