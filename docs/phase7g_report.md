# Phase 7G report

Phase 7G adds the Stage II dependency-free anesthesia environment and observation core. The implementation consumes the paper-grounded Stage I simulator and introduces only synthetic environment mechanics: physical propofol actions, deterministic remifentanil schedules, timestamp-only observation templates, causal P0/P1 processing, fixed-shape S0/S1 state construction, latent-BIS reward, and four-condition configuration.

The step implementation follows the versioned transition-order contract. It partitions each 10-second interval at BIS, SQI, and schedule-change timestamps, advances the Stage I simulator with exact constant inputs on each subinterval, samples latent BIS only when a BIS event occurs, updates completed-interval histories, then constructs the next observation and reward.

The artifacts record MC-010–MC-018 and MC-031–MC-032 as approved only for this Stage II synthetic core. PPO constants MC-019–MC-030 and MC-033–MC-034 remain pending. This phase does not approve a final horizon, create a subject split, or perform PPO integration.

All validation inputs are explicitly synthetic. The frozen cohort remains 2,460 cases and 2,415 subjects, but no case or subject record is read by the environment implementation.
