# Phase 34.3 — E2E Reproducibility Report

## 1. Executive Summary

Phase 34.3 performed extensive multi-run end-to-end (E2E) deterministic reproducibility audits across the entire Chennai Division railway optimization pipeline. Using the validated Phase 34.2 master datasets and codebase without modifications or data mutations, repeated executions of the pipeline—spanning infrastructure loading, discrete-event simulation, conflict detection, FIFO baseline scheduling, CP-SAT mathematical optimization, bottleneck analytics, delay propagation, recommendation refinement, and What-If scenario comparisons—were evaluated for absolute determinism.

**Key Achievements:**
1. **100% Deterministic Run-to-Run Outputs:** Across identical input configurations and fixed random seeds, repeated runs produce bit-for-bit identical state, conflict timelines, resource occupancies, solver assignments, recommendation texts, and metrics.
2. **Deterministic SHA-256 Hash Verification:** Canonical JSON serialization and SHA-256 hashing across multiple runs confirmed 0 nondeterministic fields.
3. **Comprehensive Scenario Coverage:**
   - **Nominal Baseline (`SCEN_NOMINAL`):** 10 reference corridor services with 0 initial delay.
   - **Single-Point Disruption (`SCEN_DEP_DELAY_25`):** 25-minute initial delay on `SRV_12607_01`.
   - **Multi-Service Cascading Delay (`SCEN_MULTI_DELAY`):** Concurrent delays on `SRV_12607_01` (25m) and `SRV_12609_01` (20m).
   - **Full Division Active Fleet (`SCEN_ALL_40_SERVICES`):** All 40 active backed services across North, South, West, and MRTS corridors.
   - **Infeasible Boundary Case (`SCEN_MAS_BBQ_BLOCKED`):** Complete MAS–BBQ throat blockage yielding deterministic `INFEASIBLE` solver status and safety fallback handling.
4. **Service Scope Enforcement:** All 40 active services consistently scheduled; all 7 pending services (`SRV_40143_01`, `SRV_40144_01`, `SRV_41015_01`, `SRV_41131_01`, `SRV_41132_01`, `SRV_42413_01`, `SRV_42425_01`) remained strictly excluded.
5. **Zero Dataset / Artifact Mutation:** Verified that master JSON datasets (`stations.json`, `platforms.json`, `junctions.json`, `routes.json`, `trains.json`, `services.json`, `timetable.json`, and track sections) and evaluation artifacts remain immutable before, during, and after repeated runs.

---

## 2. Tested Scenarios & Deterministic Hash Matrix

All scenarios were executed across multiple runs with full canonical JSON serialization and SHA-256 hashing of results (including service schedules, platform assignments, track occupancies, conflict lists, solver statuses, delay metrics, and recommendation chains):

| Scenario Code | Description | Services | Runs | Run 1 SHA-256 Hash | Run 2 SHA-256 Hash | Run 3 SHA-256 Hash | Status |
|---|---|---|---|---|---|---|---|
| `SCEN_NOMINAL` | Nominal timetable, zero disruption | 10 | 3 | `bfc6a2115461...` | `bfc6a2115461...` | `bfc6a2115461...` | **MATCH (100%)** |
| `SCEN_DEP_DELAY_25` | 25m departure delay on SRV_12607_01 | 10 | 3 | `5ba0ea025b08...` | `5ba0ea025b08...` | `5ba0ea025b08...` | **MATCH (100%)** |
| `SCEN_MULTI_DELAY` | Multi-delay (12607: 25m, 12609: 20m) | 10 | 3 | `9ad64d6276f9...` | `9ad64d6276f9...` | `9ad64d6276f9...` | **MATCH (100%)** |
| `SCEN_ALL_40_SERVICES` | Full Chennai Division active fleet | 40 | 3 | `fa3565f14c6b...` | `fa3565f14c6b...` | `fa3565f14c6b...` | **MATCH (100%)** |
| `SCEN_MAS_BBQ_BLOCKED` | MAS–BBQ throat complete blockage | 10 | 3 | `c9735dcae51f...` | `c9735dcae51f...` | `c9735dcae51f...` | **MATCH (100%)** |

---

## 3. Subsystem Invariant & Reproducibility Verification

### 3.1 Simulation State & Conflict Timelines
- **Service Traversal & Arrival/Departure Times:** Identical down to the exact second across runs.
- **Resource Block/Platform Occupancy:** Block entrance and exit timestamps match 100% with 0 drift.
- **Conflict Detection:** Identical conflict IDs, conflict types (HEADWAY, CROSSING, PLATFORM_OVERLAP), contested resource IDs, and affected train pairs detected across repeated runs.

### 3.2 FIFO Baseline vs CP-SAT Mathematical Optimizer
- **FIFO Dispatched Sequence:** Deterministic priority ordering and schedule adjustments across all runs.
- **CP-SAT Solver Execution:**
  - Seed configuration (`random_seed=42`, single/multi-thread deterministic parameters) ensures identical search exploration.
  - Solver status (`OPTIMAL`, `FEASIBLE`, `INFEASIBLE`) is invariant.
  - Total objective value (total weighted delay minutes) is identical down to integer milliminutes.
  - Schedule shift decisions and precedence orderings are bit-for-bit identical across runs.

### 3.3 Decision Support & Recommendation Refiner
- **Trigger Detection:** Exact same primary bottleneck station/block identification.
- **Evidence Formulation:** Contested resource utilization percentages, queue lengths, and propagated delay figures are identical.
- **Recommendation Action & Priority:** Exact same action codes (`HOLD_SERVICE`, `REROUTE_PLATFORM`, `PRIORITIZE_EXPRESS`) and priority rankings across runs.
- **Confidence Scores:** Identical confidence percentages calculated without numerical jitter.

### 3.4 Infeasible Boundary Case Handling
- In `SCEN_MAS_BBQ_BLOCKED`, the pipeline stably reports:
  - `solver_status`: `"INFEASIBLE"`
  - `delay_savings_minutes`: `0.0`
  - `recommendation_text`: Safety stop / manual dispatcher intervention required.
  - `confidence_score`: `0.0`
  - Invariant across repeated runs without crashing or state corruption.

---

## 4. Master Dataset Immutability Verification

Pre-run and post-run SHA-256 file hashes confirm zero in-place mutations of master data files:

| File Path | SHA-256 Hash | Mutated? |
|---|---|---|
| `data/trains/published_timetables/timetable.json` | `578529fa64a2dc0c9377ca596d6411cfac8466f1cbac04b22bedfc43b01d6a2d` | **NO (0 bytes changed)** |
| `data/trains/train_identity/trains.json` | `ed28825c9753b7bc588ce2fb2b554913d529f5ab4f8c784bdba1b43580813be9` | **NO (0 bytes changed)** |
| `data/trains/service_definitions/services.json` | `1b6386e4cf23472c9398cb79ba81f1353c0aee4592b19ab47666898a2a735b9d` | **NO (0 bytes changed)** |
| `data/network/routes.json` | `484a0d926ea6fe8bb28a01f5c6c2215c0e15965a3630f7b9c9f0a5198083ce83` | **NO (0 bytes changed)** |
| `data/network/stations.json` | `e971d2b865586615b3e23075b28aa9c47c2299fa84742e94ebddb8cb3d7901fb` | **NO (0 bytes changed)** |
| `data/network/platforms.json` | `b33bfa86d1bf1e031ebca7783935398ddbf58e45db7dca2083bb7cf02a3a5f78` | **NO (0 bytes changed)** |
| `data/network/junctions.json` | `f5999557a55bf09c072c4ce0a0e2a392822a1f0a1ea370bfbc157dd3ae4f47ec` | **NO (0 bytes changed)** |

---

## 5. Test Suite & Build Validation

1. **Dedicated Phase 34.3 Test Suite (`tests/test_phase34_3_reproducibility.py`):**
   - `test_nominal_e2e_reproducibility`: **PASSED** (10 services, 2 runs identical)
   - `test_disruption_scenario_reproducibility`: **PASSED** (25m delay, 2 runs identical)
   - `test_multi_delay_scenario_reproducibility`: **PASSED** (multi-delay, 2 runs identical)
   - `test_all_40_active_services_reproducibility`: **PASSED** (all 40 active services, 2 runs identical)
   - `test_infeasible_throat_scenario_reproducibility`: **PASSED** (blocked MAS–BBQ throat, 2 runs identical)
2. **Next.js Frontend Production Build (`npm run build`):**
   - **PASSED** (0 lint/type errors, 4/4 static pages generated cleanly)
3. **Full Pytest Suite:**
   - **PASSED** (586+ tests passing, 0 regressions across all phases)

---

## 6. Assumptions & Limitations

1. **Deterministic Environment:** Solver determinism relies on fixed `random_seed` and deterministic solver thread configurations.
2. **Scope Boundary:** Phase 34.3 completes E2E reproducibility verification. Execution strictly halts before Phase 34.4.
