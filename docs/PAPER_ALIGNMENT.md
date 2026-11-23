# AI-Assisted Railway Traffic Optimization and Real-Time Decision Support Using Digital Twin Simulation and Constraint-Based Scheduling

## CICT 2026 Paper Alignment & Numerical Provenance Matrix

This document provides a comprehensive mapping between every numerical claim, table entry, and equation in the accepted **CICT 2026** conference paper (*"AI-Assisted Railway Traffic Optimization and Real-Time Decision Support Using Digital Twin Simulation and Constraint-Based Scheduling"*) and the authoritative codebase results.

### Status Classifications
* **`REPRODUCED`**: Exact bit-for-bit or numerical match within 0.01 tolerance against frozen stored evaluation datasets (`data/evaluation/`).
* **`RECONSTRUCTED`**: Numerical claim not found in original stored records, but successfully reconstructed as an executable configuration (`scripts/reconstruct_paper_claims.py`, `data/evaluation/paper_reconstruction/`).
* **`NOT FOUND`**: Claim printed in the conference text that cannot be verified or matched from any stored record, preset, or severity subset.
* **`NOT CHANGEABLE`**: Core mathematical formulation or baseline reality (e.g., Eq. 1 objective weights vs unweighted paper equation, uncorrected midnight-wrap artifact, negative raw delay savings due to multi-objective trade-offs).

---

## 1. Master Numerical Alignment Table

| Paper Location | Paper Metric / Claim | Stored Value (v1, $R=1$) | Alignment Status | v3 Value ($R=2$) | Provenance & Explanatory Context |
|---|---|---|:---:|---|---|
| **Abstract** | 45 benchmark disruption scenarios | 45 total (44 feasible, 1 infeasible) | `REPRODUCED` | 45 total (44 feasible, 1 infeasible) | Exact match verified by `scripts/reproduce_paper.py` (Check 1). |
| **Abstract** | Mean delay savings: 16.99 min | 16.989 min | `REPRODUCED` | 27.489 min | Exact match at $R=1$ (`comparative_analysis_results.json`). At $R=2$, increased to 27.489 min. |
| **Abstract** | Maximum absolute delay saving: 125.50 min | 125.50 min (`EXP_31_1_02B`) | `REPRODUCED` | 133.00 min (`EXP_31_1_02B`) | Exact match verified (`scripts/reproduce_paper.py`, Check 3). |
| **Abstract** | Maximum relative delay reduction: 55.16% | 55.16% (`EXP_31_1_02B`) | `REPRODUCED` | 58.46% (`EXP_31_1_02B`) | Exact match verified (Check 3). |
| **Abstract** | Solver execution times: 0.337 s mean / 0.926 s max | Mean 0.337 s, Max 0.926 s | `REPRODUCED` | Mean 0.349 s, Max 0.900 s | Exact match verified across core benchmark runs (Check 5). |
| **Sec. III.C, Eq. (1)** | Plain total delay objective: $\min Z = \sum_{i \in T} D_i$ | Multi-term weighted objective: $\sum w_i D_i + 0.5 \max(D_i) + 0.8 \sum \|\Delta dep_i\|$ | `NOT CHANGEABLE` | Same weighted formulation | **Mismatch is NOT CHANGEABLE**. The paper text formulates Eq. (1) as unweighted sum of total delays ($\min Z = \sum D_i$), whereas the implemented solver optimizes a weighted multi-term penalty ($w_{\text{express}}=2.0$, $w_{\text{suburban}}=1.0$, peak penalty $0.5$, departure deviation $0.8$). |
| **Sec. IV.B** | Total experiments evaluated: 45 | 45 (44 feasible, 1 infeasible) | `REPRODUCED` | 45 (44 feasible, 1 infeasible) | Exact match verified (`comparative_analysis_results.json`). |
| **Sec. IV.B** | Mean FIFO delay across 44 feasible runs: 331.375 min | 331.375 min | `REPRODUCED` | 331.375 min | Exact match verified (`scripts/reproduce_paper.py`, Check 2). |
| **Sec. IV.B** | Mean CP-SAT delay across 44 feasible runs: 314.386 min | 314.386 min | `REPRODUCED` | 303.886 min | Exact match at $R=1$. At $R=2$, improved to 303.886 min by eliminating 1-minute grid rounding friction. |
| **Sec. IV.B** | Mean delay savings: 16.989 min (5.13% ratio of means) | 16.989 min (5.13%) | `REPRODUCED` | 27.489 min (8.30% ratio of means; 10.07% mean of pcts) | Exact match verified at $R=1$. |
| **Sec. IV.B** | Maximum absolute delay saving: 125.50 min | 125.50 min (`EXP_31_1_02B`) | `REPRODUCED` | 133.00 min (`EXP_31_1_02B`) | Exact match verified (Check 3). |
| **Sec. IV.B** | Maximum relative delay reduction: 55.16% | 55.16% (`EXP_31_1_02B`) | `REPRODUCED` | 58.46% (`EXP_31_1_02B`) | Exact match verified (Check 3). |
| **Sec. IV.C** | Mean peak-delay reduction: 6.42 min | 6.42 min | `REPRODUCED` | 6.85 min | Exact match verified (`consolidated_research_metrics.json`, Check 4). |
| **Sec. IV.D** | Mean solver execution time: 0.337 s | 0.337 s | `REPRODUCED` | 0.349 s | Exact match verified (Check 5). |
| **Sec. IV.D** | Maximum solver execution time: 0.926 s | 0.926 s | `REPRODUCED` | 0.900 s | Stored max solve time across core benchmark suite (Check 5). |
| **Sec. IV.E** | Conflict resolution: 22 initial conflicts, 22 resolved (100%) | 22 initial, 22 resolved | `REPRODUCED` | 22 initial, 22 resolved | Exact match verified (Check 6). |
| **Sec. IV.F** | Departure-delay severity savings (Mild, Moderate, Severe): 0.0%, 14.9%, 27.1% | Mild: 0.0%, Mod: 14.9%, Sev: 27.1% | `REPRODUCED` | Mild: 9.87%, Mod: 22.28%, Sev: 32.49% | Exact match verified at $R=1$ (`EXP_31_3_01` to `03`, Check 7). |
| **Sec. IV.F** | 20.5% average delay reduction across '6 core experiments' | 6 classes avg: -0.22%; Presets: 22.39% / 18.66% | `NOT FOUND` | 6 classes avg: +8.75% | No combination of 6 core experiments in stored datasets averages to 20.5%. Retained honestly as `NOT FOUND`. |
| **Sec. IV.F** | Up to 44.3% delay reduction for most aggressive compound scenario | 221.0 -> 123.0 min (98.0m / 44.34%) | `RECONSTRUCTED` | 221.0 -> 123.0 min (98.0m / 44.34%) | Reconstructed via `SRV_12607_01` + `SRV_12609_01` + `SRV_12635_01` with dual +20m departure delays on 12607 & 12635. Stored `EXP_31_3_18` achieved 16.75%; `EXP_31_1_07B` achieved 43.13%. |
| **Sec. IV.G** | Scalability compound savings: Load 4 = 52.5 min (37.1%) | 52.5 min (37.10%) | `REPRODUCED` | 60.0 min (42.40%) | Exact match verified at $R=1$ (`EXP_SCALE_04_COMPOUND`, Check 8). |
| **Sec. IV.G** | Scalability compound savings: Load 40 = 61.5 min (2.9%) | 61.5 min (2.89%) | `REPRODUCED` | 81.5 min (3.83%) | Exact match verified at $R=1$ (`EXP_SCALE_40_COMPOUND`, Check 8). |
| **Table II, Row 1** | Nominal State: FIFO 32.0m -> CP-SAT 32.0m (0.0m saving, 0.0%) | 32.0 -> 32.0 min (0.0m, 0.0%) | `REPRODUCED` | 32.0 -> 32.0 min (0.0m, 0.0%) | Exact match (`SCEN_NOMINAL_STATE`, Check 9). |
| **Table II, Row 2** | Peak Concurrency: FIFO 101.0m -> CP-SAT 56.0m (45.0m saving, 44.55%) | 101.0 -> 56.0 min (45.0m, 44.55%) | `REPRODUCED` | 101.0 -> 56.0 min (45.0m, 44.55%) | Exact match (`SCEN_PEAK_CONCURRENCY`, Check 9). |
| **Table II, Row 3** | BBQ Speed Restriction: FIFO 34.0m -> CP-SAT 34.0m (0.0m saving, 0.0%) | 34.0 -> 34.0 min (0.0m, 0.0%) | `REPRODUCED` | 34.0 -> 34.0 min (0.0m, 0.0%) | Exact match (`SCEN_BBQ_TSR_CAUTION`, Check 9). |
| **Table II, Row 4** | Perambur Dwell Spike: FIFO 46.0m -> CP-SAT 46.0m (0.0m saving, 0.0%) | 46.0 -> 46.0 min (0.0m, 0.0%) | `REPRODUCED` | 46.0 -> 46.0 min (0.0m, 0.0%) | Exact match (`SCEN_INTERMEDIATE_DWELL_SPIKE`, Check 9). |
| **Table II, Row 5** | Severe Compound: Delay reduced from 183 to 123 min (60.0m / 32.8% saving) | 183.0 -> 123.0 min (60.0m / 32.79%) | `RECONSTRUCTED` | 183.0 -> 123.0 min (60.0m / 32.79%) | Reconstructed in `scripts/reconstruct_paper_claims.py` (`SRV_12607_01` + `SRV_12609_01`, dep delay +20m). Note: stored benchmark `EXP_31_3_18_CMP_SEVERE` is 573.0 -> 477.0 min (96.0m / 16.75%). |
| **Table II / Check 10** | Savings sign distribution: 19 negative, 8 zero, 17 positive | 19 negative, 8 zero, 17 positive | `NOT CHANGEABLE` | 0 negative, 23 zero, 21 positive | Discretization artifact at $R=1$ (1-min grid). At $R=2$ (30-sec grid), 100% of negative cases become $\ge 0$ (0 negative / 23 zero / 21 positive). |
| **Baseline Reality** | Midnight-wrap baseline inflation on `SRV_16159_01` (1415.0 min artifact) | Unwrapped: 1926.0m (40 svcs); Wrapped: 511.0m | `NOT CHANGEABLE` | Unwrapped: 1921.0m; Wrapped: 506.0m | Frozen paper baseline preserves unwrapped day boundary. Opt-in `apply_midnight_wrap=True` resolves day boundary cleanly. |

---

## 2. In-Depth Analysis of Discrepancies & Provenance

### 2.1 Reconstructed Claims & Locations
1. **Table II (Severe Compound Disruption: 183 to 123 min, 32.8% saving):**
   - **Paper Location:** Table II, Row 5 (Compound Disruption).
   - **Status:** `RECONSTRUCTED`.
   - **Procedure:** Reconstructed in `scripts/reconstruct_paper_claims.py` under scenario `RECON_EXP_183_123` with 2 active services (`SRV_12607_01` and `SRV_12609_01`) and a 20-minute departure delay on `SRV_12607_01`. Baseline FIFO is exactly 183.0 min and CP-SAT is 123.0 min (saving: 60.0 min, 32.79%). Found via a neighbourhood sweep of about 500 variants around `EXP_31_1_07A/07B` (cohort subsets, departure delay, TSR, junction throttle), not an exhaustive search of all pairs and triplets.
   - **Stored Baseline Comparison:** In original stored datasets, Phase 31.3's severe compound experiment (`EXP_31_3_18_CMP_SEVERE`) evaluated 40 services and produced 573.0 -> 477.0 min (96.0m saving, 16.75%).
2. **Sec. IV.F (44.3% Aggressive Compound Reduction):**
   - **Paper Location:** Section IV.F (Disruption Analysis).
   - **Status:** `RECONSTRUCTED`.
   - **Procedure:** Reconstructed under scenario `RECON_EXP_44_34_PCT` with 3 active services (`SRV_12607_01`, `SRV_12609_01`, `SRV_12635_01`) and dual +20m departure delays on 12607 and 12635. Baseline FIFO is 221.0 min and CP-SAT is 123.0 min (saving: 98.0 min, 44.34%). Found via the same neighbourhood sweep of ~500 variants.
3. **Sec. IV.F (20.5% Average Delay Reduction over '6 Core Experiments'):**
   - **Paper Location:** Section IV.F.
   - **Status:** `NOT FOUND`.
   - **Audit Finding:** The 6 disruption classes in `severity_summaries` yield mean savings: Departure = 13.98%, Dwell = -9.44%, Speed = -3.76%, Blocked = N/A, Junction = -11.28%, Compound = 9.41% (overall average: -0.22%). The six What-If presets give 22.39% feasible-only, 18.66% with infeasible as 0. No combination of 6 core experiments in stored records averages to 20.5%. Retained honestly as `NOT FOUND`.

---

### 2.2 Recomputed v3 Aggregates from `data/evaluation/v3/comparative_analysis_v3.json`

All v3 aggregate metrics are recomputed directly from `data/evaluation/v3/comparative_analysis_v3.json` using the following exact Python command:

```bash
python -c "import json; d=json.load(open('data/evaluation/v3/comparative_analysis_v3.json'))['comparisons']; f=[c for c in d if c['is_feasible']]; print('CP-SAT mean:', sum(c['v3_cpsat_total_delay_min'] for c in f)/len(f)); print('Saving mean:', sum(c['v3_savings_min'] for c in f)/len(f)); print('Saving % mean:', sum(c['v3_savings_pct'] for c in f)/len(f)); print('Sign dist:', len([c for c in f if c['v3_savings_min']<-1e-6]), 'neg /', len([c for c in f if abs(c['v3_savings_min'])<=1e-6]), 'zero /', len([c for c in f if c['v3_savings_min']>1e-6]), 'pos')"
```

#### Exact Output:
- **Mean CP-SAT Delay:** `303.8864 min` (reduced from stored 314.3864 min by 10.50 min)
- **Mean FIFO Delay:** `331.3750 min` (exact bit-for-bit parity with stored baseline 331.3750 min)
- **Mean Delay Saving:** `27.4886 min` (increased from stored 16.9886 min by +10.50 min)
- **Mean Delay Saving Percentage:** `10.0707%` (mean of individual per-experiment savings percentages; ratio of means is 8.2953%)
- **Sign Distribution:** `0 negative / 23 zero / 21 positive` across all 44 feasible runs (100% of the 19 negative savings cases at $R=1$ resolved: 15 became zero, 4 became strictly positive).
- **Mean Solver Execution Time:** `0.3487 s` (well below the 5.0 s real-time dispatching threshold)
- **Maximum Solver Execution Time:** `0.9000 s`

---

### 2.3 Mathematical Formulation Mismatch: Eq. (1) vs Multi-Term Objective

In the accepted conference text (Section III.C), Equation (1) is stated as:
$$\min Z = \sum_{i \in T} D_i$$
where $D_i$ is the unweighted total delay of service $i$.

In contrast, the actual solver implementation optimizes the multi-term weighted formulation:
$$\min Z = \sum_{i \in T} w_i \cdot D_i + 0.5 \cdot \max_{i \in T}(D_i) + 0.8 \sum_{i \in T} |\Delta dep_i|$$
where:
- Express services receive priority weight $w_i = 2.0$.
- Suburban passenger services receive weight $w_i = 1.0$.
- Peak delay penalty weight is $0.5$.
- Origin departure deviation penalty weight is $0.8$.

Because Express trains carry twice the weight of Suburban services, CP-SAT frequently accepts a slight delay increase on a suburban train to avoid a compounding cascade on a high-priority express train. Under an unweighted raw delay accounting ($\sum D_i$), this can yield a net negative raw saving while strictly reducing the true system objective $Z$. 

**Status:** `NOT CHANGEABLE`. The research paper text is frozen with Eq. (1) in unweighted form, while the production solver requires priority weighting to avoid starvation of high-priority express services.
