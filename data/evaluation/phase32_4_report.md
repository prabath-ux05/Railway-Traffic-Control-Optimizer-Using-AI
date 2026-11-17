# Phase 32.4 — What-If Comparison & Decision-Support Report

**Generated:** `2026-09-20T09:32:25.384430+00:00`  
**Total Scenarios Evaluated:** `5`  
**Mean Delay Savings:** `11.2 min` (`11.1%`)  
**Total Conflicts Resolved:** `0`  
**Mean Solver Computation Time:** `0.028s`  
**Mean Confidence Score:** `80.0%`  

---

## 1. Multi-Scenario Comparative Matrix

| Scenario ID | Type | Baseline Delay | Optimized Delay | Net Savings | Conflicts (Init/Res) | Knock-on ($K$) | Primary Bottleneck | Solver Status | Confidence |
|---|:---:|:---:|:---:|:---:|:---:|:---:|---|:---:|:---:|
| `SCEN_NOMINAL_STATE` | `OPERATIONAL_STATE` | `32.0m` | `32.0m` | 0.0m | `0` / `0` | `2.22x` | `SEC_BBQ_KOK_UP` | `OPTIMAL` | `100.0%` |
| `SCEN_PEAK_CONCURRENCY` | `HYPOTHETICAL_SCENARIO` | `101.0m` | `56.0m` | **45.0m** (44.6%) | `0` / `0` | `2.22x` | `SEC_BBQ_KOK_UP` | `OPTIMAL` | `100.0%` |
| `SCEN_BBQ_TSR_CAUTION` | `HYPOTHETICAL_SCENARIO` | `34.0m` | `34.0m` | 0.0m | `0` / `0` | `2.22x` | `SEC_BBQ_KOK_UP` | `OPTIMAL` | `100.0%` |
| `SCEN_INTERMEDIATE_DWELL_SPIKE` | `HYPOTHETICAL_SCENARIO` | `46.0m` | `46.0m` | 0.0m | `0` / `0` | `2.22x` | `SEC_BBQ_KOK_UP` | `OPTIMAL` | `100.0%` |
| `SCEN_MAS_BBQ_BLOCKED` | `INFEASIBLE_BOUNDARY_CASE` | `360.0m` | `360.0m` | 0.0m | `12` / `0` | `3.00x` | `MAS_BBQ_THROAT_SEGMENT_DOWN` | `INFEASIBLE` | `0.0%` |

---

## 2. Direct vs Propagated Delay & Recovery Profiles

| Scenario ID | Scenario Name | Primary Delay ($D_{\text{pri}}$) | Secondary Delay ($D_{\text{sec}}$) | Knock-on Ratio ($K$) | Buffer Recovery % | Affected Services |
|---|---|:---:|:---:|:---:|:---:|---|
| `SCEN_NOMINAL_STATE` | Nominal On-Time Operational State | `14.4m` | `17.6m` | `2.22x` | `0.0%` | `SRV_12607_01` |
| `SCEN_PEAK_CONCURRENCY` | West Corridor Peak Concurrency | `45.5m` | `55.5m` | `2.22x` | `44.5%` | `SRV_12607_01` |
| `SCEN_BBQ_TSR_CAUTION` | Basin Bridge Speed Caution Order | `15.3m` | `18.7m` | `2.22x` | `0.0%` | `SRV_12607_01` |
| `SCEN_INTERMEDIATE_DWELL_SPIKE` | Perambur Dwell Extension | `20.7m` | `25.3m` | `2.22x` | `0.0%` | `SRV_12675_01` |
| `SCEN_MAS_BBQ_BLOCKED` | MAS-BBQ Down Throat Complete Blockage | `120.0m` | `240.0m` | `3.00x` | `0.0%` | `SRV_12607_01, SRV_12622_01` |

---

## 3. Decision-Support Directives & Recommendation Dynamics

### `SCEN_NOMINAL_STATE`: Nominal On-Time Operational State
- **Category:** `OPERATIONAL_STATE` | **Solver Performance:** `OPTIMAL` (0.038s)
- **Top Actionable Directive:** [LOW] Maintain Published Schedule
- **Attributed Delay Mitigation:** `0.0 min` (Confidence: `100.0%`)
- **Resource Choke-Point:** `SEC_BBQ_KOK_UP` (78.5% utilization)

### `SCEN_PEAK_CONCURRENCY`: West Corridor Peak Concurrency
- **Category:** `HYPOTHETICAL_SCENARIO` | **Solver Performance:** `OPTIMAL` (0.039s)
- **Top Actionable Directive:** [CRITICAL] CP-SAT Dispatch Slot Optimization: West Corridor Peak Concurrency
- **Attributed Delay Mitigation:** `45.0 min` (Confidence: `100.0%`)
- **Resource Choke-Point:** `SEC_BBQ_KOK_UP` (78.5% utilization)

### `SCEN_BBQ_TSR_CAUTION`: Basin Bridge Speed Caution Order
- **Category:** `HYPOTHETICAL_SCENARIO` | **Solver Performance:** `OPTIMAL` (0.023s)
- **Top Actionable Directive:** [HIGH] Speed Management Caution Order: MAS_BBQ_THROAT_SEGMENT_DOWN (+8.0m)
- **Attributed Delay Mitigation:** `0.0 min` (Confidence: `100.0%`)
- **Resource Choke-Point:** `SEC_BBQ_KOK_UP` (78.5% utilization)

### `SCEN_INTERMEDIATE_DWELL_SPIKE`: Perambur Dwell Extension
- **Category:** `HYPOTHETICAL_SCENARIO` | **Solver Performance:** `OPTIMAL` (0.026s)
- **Top Actionable Directive:** [LOW] Maintain Published Schedule
- **Attributed Delay Mitigation:** `0.0 min` (Confidence: `100.0%`)
- **Resource Choke-Point:** `SEC_BBQ_KOK_UP` (78.5% utilization)

### `SCEN_MAS_BBQ_BLOCKED`: MAS-BBQ Down Throat Complete Blockage
- **Category:** `INFEASIBLE_BOUNDARY_CASE` | **Solver Performance:** `INFEASIBLE` (0.015s)
- **Top Actionable Directive:** [CRITICAL] Emergency Infrastructure Boundary: MAS-BBQ Throat Impassable
- **Attributed Delay Mitigation:** `0.0 min` (Confidence: `0.0%`)
- **Resource Choke-Point:** `MAS_BBQ_THROAT_SEGMENT_DOWN` (100.0% utilization)

---

## 4. Operational Invariant Verification & Boundary Isolation

- **Zero Pending Services Contamination**: 100% verified (`SRV_40143_01`, `SRV_40144_01`, `SRV_41015_01`, `SRV_41131_01`, `SRV_41132_01`, `SRV_42413_01`, `SRV_42425_01` excluded).
- **Dataset Immutability**: All underlying network, trains, and timetable JSON files preserved unaltered.
- **Infeasible Case Isolated**: `SCEN_MAS_BBQ_BLOCKED` accurately identified as `INFEASIBLE_BOUNDARY_CASE` with 0 hallucinated delay savings and 0.0 confidence.
- **Explainable & Deterministic**: Zero stochastic elements or LLM/RL heuristics.
