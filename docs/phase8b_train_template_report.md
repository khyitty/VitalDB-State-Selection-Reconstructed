# Phase 8B train observation-template report

Phase 8B extracted 1,970 sealed train templates and no test templates. The private store remains ignored and only its aggregate fingerprint is public.

- Train BIS/SQI logical accesses: 3,940 (1,970 BIS, 1,970 SQI)
- Source checksum mismatches: 0
- Test and drug raw accesses: 0
- Raw BIS values persisted: false
- Raw SQI values: private only
- Private-store root SHA-256: `96e9f4d329b0131634a756fc4b4a03acbce5e97a10d65a2a416948130f9d9fb2`
- P0 visible grid points: 2,086,908/2,299,446
- P1 visible grid points: 1,923,357/2,299,446
- Zero-visibility templates: P0=0, P1=0

These visibility counts are a structural audit using fixed latent BIS 50.0, not a prediction or control result. No membership, preprocessing rule, normalization, model, checkpoint, or PPO operation was changed or executed.

The Phase 8A verify-only regression was corrected without changing membership,
the test seal, or any scientific artifact. Generation still requires the exact
Phase 8A starting refs; verify-only accepts only descendants of that starting
commit and continues to require byte-identical deterministic reconstruction.
