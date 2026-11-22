# CICT 2026 Paper Claims Reconstruction Report

**Search Procedure:** The two configs were found by a neighbourhood sweep of about 500 variants around EXP_31_1_07A/07B (cohort subsets, departure delay, TSR, junction throttle), not an exhaustive search of all pairs and triplets.

## 1. Reconstructed Claims Summary

| Claim Text | Classification | Configuration | FIFO (min) | CP-SAT (min) | Savings (min) | Savings (%) | Status |
|---|:---:|---|---:|---:|---:|---:|:---:|
| Compound Disruption 183 to 123 | `RECONSTRUCTED` | SRV_12607_01+SRV_12609_01, dep +20m | 183.0 | 123.0 | 60.0 | 32.79% | **PASS** |
| 44.3% Aggressive Compound Scenario | `RECONSTRUCTED` | SRV_12607_01+SRV_12609_01+SRV_12635_01, dep +20m on 2 trains | 221.0 | 123.0 | 98.0 | 44.34% | **PASS** |
| 20.5% Mean Reduction over 6 Core Exps | `NOT FOUND` | 6 What-If presets / 6 severity classes audited | N/A | N/A | N/A | N/A | **NOT FOUND** |

## 2. Provenance & Methodological Details

- **Claim 1 (183 to 123):** Differs from stored EXP_31_1_07A (209->149) and EXP_31_1_07B (262->149). It reproduces exactly when isolated to the two conflicting services on the West corridor under a 20-minute departure delay.
- **Claim 2 (44.34%):** Differs from stored EXP_31_1_07B (43.13%) and What-If SCEN_PEAK_CONCURRENCY (44.55%). It reproduces exactly when testing 3 interacting services with dual +20m departure delays.
- **Claim 3 (20.5%):** Not reproducible from any stored records or presets (What-If presets produce 22.39% feasible-only, 18.66% with infeasible as 0; severity progression averages -0.22%). Kept honestly classified as `NOT FOUND`.
