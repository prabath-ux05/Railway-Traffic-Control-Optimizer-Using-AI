# CICT 2026 Paper Reproducibility Audit Report

**Audit Status:** PASSED (10/10 Verified Checks Passed)

## Verified Claims Table (Tolerance: 0.01)

| Check ID | Description | Expected | Actual | Status |
|---|---|---|---|:---:|
| `CHECK_01_EXP_COUNTS` | 45 total experiments, 44 feasible, 1 infeasible | total=45, feasible=44, infeasible=1 | total=45, feasible=44, infeasible=1 | **PASS** |
| `CHECK_02_DELAY_MEANS` | Mean FIFO delay 331.375, CP-SAT delay 314.386, saving 16.989 min, ratio 5.13% | FIFO=331.375, CPSAT=314.386, saving=16.989, ratio=5.13% | FIFO=331.375, CPSAT=314.386, saving=16.989, ratio=5.13% | **PASS** |
| `CHECK_03_MAX_SAVINGS` | Maximum saving 125.5 min and maximum relative reduction 55.16% | max_saving=125.5 min, max_pct=55.16% | max_saving=125.5 min, max_pct=55.16% | **PASS** |
| `CHECK_04_PEAK_REDUCTION` | Mean peak-delay reduction 6.42 min | mean_peak_reduction=6.42 min | mean_peak_reduction=6.42 min | **PASS** |
| `CHECK_05_SOLVER_TIME` | Solver time: mean 0.337 s, maximum 0.926 s | mean_solve=0.337 s, max_solve=0.926 s | mean_solve=0.337 s, max_solve=0.926 s | **PASS** |
| `CHECK_06_CONFLICTS` | Conflicts: 22 initial, 22 resolved | initial=22, resolved=22 | initial=22, resolved=22 | **PASS** |
| `CHECK_07_DEP_SEVERITY` | Departure-delay severity savings (mild, moderate, severe): 0%, 14.9%, 27.1% | mild=0.0%, moderate=14.9%, severe=27.1% | mild=0.0%, moderate=14.9%, severe=27.1% | **PASS** |
| `CHECK_08_SCALABILITY_COMPOUND` | Scalability compound disruption: 52.5m (37.1%) at load 4; 61.5m (2.9%) at load 40 | load 4: saving=52.5m, rel=37.1%; load 40: saving=61.5m, rel=2.9% | load 4: saving=52.5m, rel=37.1%; load 40: saving=61.5m, rel=2.9% | **PASS** |
| `CHECK_09_TABLE_II_ROWS` | Table II rows: Nominal 32->32; Peak 101->56; BBQ TSR 34->34; PER Dwell 46->46; Severe Compound 573->477 | Nominal=32->32, Peak=101->56, BBQ=34->34, PER=46->46, Severe=573->477 | Nominal=32.0->32.0, Peak=101.0->56.0, BBQ=34.0->34.0, PER=46.0->46.0, Severe=573.0->477.0 | **PASS** |
| `CHECK_10_SAVINGS_SIGN_DISTRIBUTION` | Sign of savings among 44 feasible runs: 19 negative, 8 zero, 17 positive | negative=19, zero=8, positive=17 | negative=19, zero=8, positive=17 | **PASS** |

## Audit of Unverified Paper Text Claims

The following three claims printed in the conference paper text were explicitly audited against all stored records in `data/evaluation/`:

### Claim: "Compound Disruption 183 to 123 (saving 60.0 min, 32.8%)"
- **Classification:** `NOT REPRODUCIBLE`
- **Evidence & Provenance:** Audited all compound disruption runs in stored datasets. In Phase 31.3: EXP_31_3_16 is 195.0->191.0 (4.0m, 2.05%); EXP_31_3_17 is 318.0->288.0 (30.0m, 9.43%); EXP_31_3_18 is 573.0->477.0 (96.0m, 16.75%). In Phase 31.1: EXP_31_1_07A is 209.0->149.0 (60.0m, 28.71%); EXP_31_1_07B is 262.0->149.0 (113.0m, 43.13%). No stored record contains baseline delay 183.0 or CP-SAT delay 123.0.

### Claim: "20.5% mean reduction over '6 core experiments'"
- **Classification:** `NOT REPRODUCIBLE`
- **Evidence & Provenance:** Audited all group aggregations and experiment classes in stored results. The 6 disruption classes in severity_summaries yield mean savings: Departure=13.98%, Dwell=-9.44%, Speed=-3.76%, Blocked=N/A, Junction=-11.28%, Compound=9.41% (overall average: -0.22%). The 5 What-If scenarios yield an average savings of 11.14%. No subset of 6 core experiments in the stored datasets averages to 20.5%.

### Claim: "44.3% for the most aggressive compound scenario"
- **Classification:** `NOT REPRODUCIBLE`
- **Evidence & Provenance:** Audited all compound scenarios in stored datasets. The most aggressive compound scenario in Phase 31.3 (EXP_31_3_18_CMP_SEVERE) achieves a 16.75% reduction (96.0m saving). In Phase 31.1, EXP_31_1_07B (Multi-Corridor Peak Compound) achieves 43.13% (113.0m saving). In What-If, SCEN_PEAK_CONCURRENCY achieves 44.55% (45.0m saving), but this is peak concurrency, not compound disruption. No stored compound scenario yields 44.3%.

