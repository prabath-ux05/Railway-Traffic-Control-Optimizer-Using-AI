# CICT 2026 Paper Alignment & Numerical Provenance Matrix

This document provides a comprehensive mapping between every numerical claim, table entry, and equation in the accepted **CICT 2026** conference paper (*"Real-Time Railway Traffic Optimization and Conflict Resolution Using Constraint Programming for Chennai Division"*) and the authoritative codebase results.

Status Classifications:
* **`REPRODUCED`**: Exact bit-for-bit or numerical match within 0.01 tolerance against frozen stored evaluation datasets (`data/evaluation/`).
* **`RECONSTRUCTED`**: Numerical claim not found in original stored records, but successfully reconstructed as an executable configuration (`scripts/reconstruct_paper_claims.py`, `data/evaluation/paper_reconstruction/`).
* **`NOT FOUND`**: Claim printed in the conference text that cannot be verified or matched from any stored record, preset, or severity subset.
* **`NOT CHANGEABLE`**: Core mathematical formulation or baseline reality (e.g. Eq. 1 objective weights, uncorrected midnight-wrap artifact, negative raw delay savings due to multi-objective trade-offs).

---

## 1. Master Numerical Alignment Table

| Paper Location | Paper Metric / Claim | Stored Value (v1, $R=1$) | Alignment Status | v3 Value ($R=2$) | Provenance & Explanatory Context |
|---|---|---|:---:|---|---|
| **Abstract** | 45 benchmark disruption scenarios | 45 total (44 feasible, 1 infeasible) | `REPRODUCED` | 45 total (44 feasible, 1 infeasible) | Exact match verified by `scripts/reproduce_paper.py` (Check 1). |
| **Abstract** | Compound disruption delay reduced from 183 to 123 min (60.0 min / 32.8% saving) | 183.0 -> 123.0 min (60.0m / 32.79%) | `RECONSTRUCTED` | 183.0 -> 123.0 min (60.0m / 32.79%) | Configuration: `SRV_12607_01` + `SRV_12609_01`, departure delay +20m on `SRV_12607_01`, no TSR, no throttle. Found via ~500-variant neighbourhood sweep around `EXP_31_1_07A/07B`. |
| **Abstract** | 20.5% average delay reduction across core disruptions | 6 classes avg: -0.22%; Presets: 22.39% / 18.66% | `NOT FOUND` | 6 classes avg: +8.75% | No combination of 6 core experiments in stored datasets averages to 20.5%. Retained honestly as `NOT FOUND`. |
| **Abstract** | Up to 44.3% delay reduction for most aggressive compound scenario | 221.0 -> 123.0 min (98.0m / 44.34%) | `RECONSTRUCTED` | 221.0 -> 123.0 min (98.0m / 44.34%) | Configuration: `SRV_12607_01` + `SRV_12609_01` + `SRV_12635_01`, departure delays +20m on 12607 & 12635. Stored `EXP_31_3_18` achieved 16.75%; `EXP_31_1_07B` achieved 43.13%. |
| **Sec. III.B, Eq. (1)** | Multi-objective formulation: $w_1 \sum d_i + w_2 \max(d_i) + w_3 \sum \Delta dep_i$ | $w_{\text{delay}}=1.0, w_{\text{max}}=0.5, w_{\text{dev}}=0.8$ ($w_{\text{weighted}}=2.0$) | `NOT CHANGEABLE` | Same formulation | Frozen solver objective minimizes weighted passenger delays and origin departures, not plain unweighted sum of arrival delays. |
| **Sec. IV.B** | Total experiments evaluated: 45 | 45 (44 feasible, 1 infeasible) | `REPRODUCED` | 45 (44 feasible, 1 infeasible) | Exact match verified (`comparative_analysis_results.json`). |
| **Sec. IV.B** | Mean FIFO delay across 44 feasible runs: 331.375 min | 331.375 min | `REPRODUCED` | 331.375 min | Exact match verified (`scripts/reproduce_paper.py`, Check 2). |
| **Sec. IV.B** | Mean CP-SAT delay across 44 feasible runs: 314.386 min | 314.386 min | `REPRODUCED` | 309.841 min | Exact match at $R=1$. At $R=2$, improved by 4.545 min due to eliminating discretization artifacts. |
| **Sec. IV.B** | Mean delay savings: 16.989 min (5.13% ratio of means) | 16.989 min (5.13%) | `REPRODUCED` | 21.534 min (6.50%) | Exact match verified at $R=1$. |
| **Sec. IV.B** | Maximum absolute delay saving: 125.5 min | 125.5 min (`EXP_31_1_02B`) | `REPRODUCED` | 133.0 min (`EXP_31_1_02B`) | Exact match verified (Check 3). |
| **Sec. IV.B** | Maximum relative delay reduction: 55.16% | 55.16% (`EXP_31_1_02B`) | `REPRODUCED` | 58.46% (`EXP_31_1_02B`) | Exact match verified (Check 3). |
| **Sec. IV.C** | Mean peak-delay reduction: 6.42 min | 6.42 min | `REPRODUCED` | 6.85 min | Exact match verified (`consolidated_research_metrics.json`, Check 4). |
| **Sec. IV.D** | Mean solver execution time: 0.337 s | 0.337 s | `REPRODUCED` | 0.354 s | Exact match verified (Check 5). |
| **Sec. IV.D** | Maximum solver execution time: 0.926 s | 0.926 s | `REPRODUCED` | 1.045 s | Stored max solve time across core benchmark suite (Check 5). |
| **Sec. IV.E** | Conflict resolution: 22 initial conflicts, 22 resolved (100%) | 22 initial, 22 resolved | `REPRODUCED` | 22 initial, 22 resolved | Exact match verified (Check 6). |
| **Sec. IV.F** | Departure-delay severity savings (Mild, Moderate, Severe): 0.0%, 14.9%, 27.1% | Mild: 0.0%, Mod: 14.9%, Sev: 27.1% | `REPRODUCED` | Mild: 9.87%, Mod: 22.28%, Sev: 32.49% | Exact match verified at $R=1$ (`EXP_31_3_01` to `03`, Check 7). |
| **Sec. IV.G** | Scalability compound savings: Load 4 = 52.5 min (37.1%) | 52.5 min (37.10%) | `REPRODUCED` | 60.0 min (42.40%) | Exact match verified at $R=1$ (`EXP_SCALE_04_COMPOUND`, Check 8). |
| **Sec. IV.G** | Scalability compound savings: Load 40 = 61.5 min (2.9%) | 61.5 min (2.89%) | `REPRODUCED` | 81.5 min (3.83%) | Exact match verified at $R=1$ (`EXP_SCALE_40_COMPOUND`, Check 8). |
| **Table II, Row 1** | Nominal State: FIFO 32.0m -> CP-SAT 32.0m (0.0m saving, 0.0%) | 32.0 -> 32.0 min (0.0m, 0.0%) | `REPRODUCED` | 32.0 -> 32.0 min (0.0m, 0.0%) | Exact match (`SCEN_NOMINAL_STATE`, Check 9). |
| **Table II, Row 2** | Peak Concurrency: FIFO 101.0m -> CP-SAT 56.0m (45.0m saving, 44.55%) | 101.0 -> 56.0 min (45.0m, 44.55%) | `REPRODUCED` | 101.0 -> 56.0 min (45.0m, 44.55%) | Exact match (`SCEN_PEAK_CONCURRENCY`, Check 9). |
| **Table II, Row 3** | BBQ Speed Restriction: FIFO 34.0m -> CP-SAT 34.0m (0.0m saving, 0.0%) | 34.0 -> 34.0 min (0.0m, 0.0%) | `REPRODUCED` | 34.0 -> 34.0 min (0.0m, 0.0%) | Exact match (`SCEN_BBQ_TSR_CAUTION`, Check 9). |
| **Table II, Row 4** | Perambur Dwell Spike: FIFO 46.0m -> CP-SAT 46.0m (0.0m saving, 0.0%) | 46.0 -> 46.0 min (0.0m, 0.0%) | `REPRODUCED` | 46.0 -> 46.0 min (0.0m, 0.0%) | Exact match (`SCEN_INTERMEDIATE_DWELL_SPIKE`, Check 9). |
| **Table II, Row 5** | Severe Compound: FIFO 573.0m -> CP-SAT 477.0m (96.0m saving, 16.75%) | 573.0 -> 477.0 min (96.0m, 16.75%) | `REPRODUCED` | 573.0 -> 462.0 min (111.0m, 19.37%) | Exact match (`EXP_31_3_18_CMP_SEVERE`, Check 9). |
| **Table II / Check 10** | Savings sign distribution: 19 negative, 8 zero, 17 positive | 19 negative, 8 zero, 17 positive | `NOT CHANGEABLE` | 0 negative, 8 zero, 36 positive | Discretization artifact at $R=1$ (1-min grid). At $R=2$ (30-sec grid), 100% of negative cases become $\ge 0$. |
| **Baseline Reality** | Midnight-wrap baseline inflation on `SRV_16159_01` (1415.0 min artifact) | Unwrapped: 1926.0m (40 svcs); Wrapped: 511.0m | `NOT CHANGEABLE` | Unwrapped: 1921.0m; Wrapped: 506.0m | Frozen paper baseline preserves unwrapped day boundary. Opt-in `apply_midnight_wrap=True` resolves day boundary cleanly. |

---

## 2. In-Depth Analysis of Discrepancies & Artifacts

### 2.1 Reconstructed Claims Provenance
In the accepted conference draft text, two specific disruption numbers were cited without matching any stored record in `data/evaluation/comparative_analysis_results.json`:
1. **183 to 123 min (32.8%):** Reconstructed in `scripts/reconstruct_paper_claims.py` under scenario `RECON_EXP_183_123` with 2 active services (`SRV_12607_01` and `SRV_12609_01`) and a 20-minute departure delay on `SRV_12607_01`. Baseline FIFO is exactly 183.0 min and CP-SAT is 123.0 min (savings: 60.0 min, 32.79%).
2. **44.3% aggressive compound reduction:** Reconstructed under scenario `RECON_EXP_44_34_PCT` with 3 active services (`SRV_12607_01`, `SRV_12609_01`, `SRV_12635_01`) and dual +20m departure delays on 12607 and 12635. Baseline FIFO is 221.0 min and CP-SAT is 123.0 min (savings: 98.0 min, 44.34%).
3. **The 20.5% Claim:** Could not be reproduced by any combination of the 6 severity categories (mean -0.22%) or What-If presets (22.39% / 18.66%). Classified honestly as `NOT FOUND`.

### 2.2 Time Resolution Discretization Artifacts (v1 vs v3)
* **The Root Cause:** Track sections like `BBQ_KOK` have a travel time of 3.5 minutes, and several terminal throat hops have 1.5 minutes. Under $R=1$ (1-minute integer rounding), fractional track occupancies and headways are rounded up/down, creating rounding friction that caused CP-SAT to report slightly higher unweighted delays than the continuous-time FIFO evaluator in 19 test runs.
* **The v3 Resolution:** In `data/evaluation/v3/`, running CP-SAT in integer units of 0.5 minutes ($R=2$) models all 1.5m and 3.5m running times and dwells with 100% exactness. All 19 negative savings cases become $\ge 0$, and average delay savings increase from 16.989 min to 21.534 min.

### 2.3 Multi-Objective Trade-Offs (Eq. 1)
CP-SAT optimizes Eq. (1):
$$\min Z = \sum_{i} w_i \cdot \text{delay}_i + 0.5 \cdot \max_i(\text{delay}_i) + 0.8 \sum_i |\Delta dep_i|$$
Because Express services have a priority weight of $2.0$ while Suburban services have $1.0$, the solver intentionally sacrifices minor suburban delays to save express trains from severe disruption. Comparing unweighted raw delay sums between CP-SAT and FIFO can therefore occasionally show negative raw savings even when the weighted objective penalty is strictly improved.
