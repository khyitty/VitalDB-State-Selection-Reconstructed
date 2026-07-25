# Caption drafts

## Main-text recommendation

**Fig. 1 — Controlled experiment framework.** Overview of the controlled 2 × 2
experimental design. Only preprocessing and state representation differ across
configurations, whereas the PPO controller, simulator, reward, training budget,
random seed, and evaluation cases are held fixed. Color identifies preprocessing;
state labels and hatch patterns provide a color-independent encoding.

**Fig. 2 — Final sealed-test control performance.** Points show case-level
medians and error bars show case-level interquartile ranges for 490 evaluation
cases. Panels report mean absolute BIS deviation and time with BIS > 60; lower
values are better for both metrics. Color encodes preprocessing and marker shape
encodes state representation.

## Supplementary candidates

**Paired control effects.** Points are mean within-subject differences and error
bars are 95% paired-bootstrap confidence intervals from 2,000 replicates across
483 subjects. The dotted zero line indicates no paired difference. Negative
values favor the first-named configuration in each contrast, because lower values
indicate better control.

**Training and evaluation workflow.** The common closed-loop path maps observation
history through preprocessing, state construction, policy action, and patient
simulation. The dashed feedback arrow denotes training-only PPO updates;
evaluation uses the frozen policy and frozen preprocessing statistics.
