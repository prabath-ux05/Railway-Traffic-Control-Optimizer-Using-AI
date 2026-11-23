# Comprehensive Technical Diagnostics Report (Batch 1)

> **Document Type:** Read-Only Technical Architecture & Empirical Data Diagnostics  
> **Target Scope:** Benchmark Delays, Service Cohort Scaling, Graph Topology Hops, Timetable Anomalies, and Simulation Timestamps  
> **Date:** November 2026  
> **Status:** All findings CONFIRMED with empirical evidence from codebase inspection and execution.

---

## Diagnostic Findings Summary Matrix

| Issue ID | Diagnostic Domain | Status | Key Finding / Root Cause |
|---|---|:---:|---|
| **DIAG-01** | Zero-Delay FIFO Delay Decomposition | **CONFIRMED** | Discrepancy between published timetable runtime and physical graph travel times dominates delay (adds 25–44 min per express); plus 1,415 min midnight wrap-around on `SRV_16159_01`. Queueing is minor in comparison. |
| **DIAG-02** | 4-Service `completed_services: 47` Metric | **CONFIRMED** | `load_count` genuinely limits the simulated and optimized cohort. The metric `completed_services` logged `len(state.train_states)` (all 47 initialized in state) rather than counting `status == COMPLETED`. |
| **DIAG-03** | 22 Route Hops Without Directional Tracks | **CONFIRMED** | Exactly 22 route hops across 8 routes have no directional track section match, falling back to nominal 3.0 min travel time in simulation. |
| **DIAG-04** | Time-Order Anomaly in `SRV_16159_01` | **CONFIRMED** | Timetable crosses midnight (`MS 23:10` -> `CGL 00:08`). Without day-wrap offset (+1440 min), `00:08` is parsed as 8.0 min from midnight, creating 1,415.0 min of artificial delay. |
| **DIAG-05** | Origin of `simulation_timestamp_str` in `/what-if` | **CONFIRMED** | Not wall-clock based. Represents the discrete simulation clock time when the last service in the evaluated cohort reaches its destination. |
| **DIAG-06** | Architectural Overlap in Evaluation Modules | **CONFIRMED** | `consolidation.py` vs `metrics_consolidation.py` and `scalability.py` vs `scalability_framework.py` serve distinct operational scopes (runtime execution vs paper table aggregation; single-corridor micro-benchmarks vs division-wide macro-frameworks) and must not be merged. |

---

## 1. Zero-Delay FIFO Delay Decomposition (DIAG-01)

### 1.1 Context & Observations
In `phase34_4_benchmark_results.json` and `consolidated_research_metrics.json`, evaluating nominal timetables with **zero injected departure delay** yields the following First-In-First-Out (FIFO) baseline delays:
* **20 Services:** 133.0 min (or 1,843.0 min when including `SRV_16159_01`)
* **30 Services:** 1,781.0 min (or 1,897.0 min)
* **40 Services:** 1,926.0 min (or 1,920.0 min)

### 1.2 Quantitative Decomposition
Running `FeasibleBaselineScheduler` across cohorts isolates the three constituent causes of delay:
1. **Physical Modeled Travel Time vs. Published Schedule:**
   In `timetable.json`, published running times for express services reflect aggressive schedules that assume non-stop clear signals and higher speeds than the conservative minimum sectional runtimes defined in `data/track_sections/`.
   * `SRV_12607_01` (Lalbagh Exp, MAS -> AJJ): Published runtime = **58.0 min**; physical graph sum of minimum section travel times = **90.0 min** (+32.0 min discrepancy).
   * `SRV_12639_01` (Brindavan Exp, MAS -> AJJ): Published runtime = **48.0 min**; physical graph travel time = **90.0 min** (+42.0 min discrepancy).
   * `SRV_12675_01` (Kovai Exp, MAS -> AJJ): Published runtime = **43.0 min**; physical graph travel time = **87.0 min** (+44.0 min discrepancy).
   * `SRV_22625_01` (Double Decker, MAS -> AJJ): Published runtime = **43.0 min**; physical graph travel time = **87.0 min** (+44.0 min discrepancy).
   * `SRV_12609_01` (Intercity Exp, MAS -> AJJ): Published runtime = **58.0 min**; physical graph travel time = **87.0 min** (+29.0 min discrepancy).
   * `SRV_16057_01` (Sapthagiri Exp, MAS -> AJJ): Published runtime = **63.0 min**; physical graph travel time = **88.0 min** (+25.0 min discrepancy).
   * `SRV_16203_01` (Garudadri Exp, MAS -> AJJ): Published runtime = **63.0 min**; physical graph travel time = **92.0 min** (+29.0 min discrepancy).

2. **Midnight Day-Wrap Anomaly (`SRV_16159_01`):**
   * Service `SRV_16159_01` departs Chennai Egmore (MS) at `23:10` (1390.0m) and arrives at Chengalpattu (CGL) at `00:08` the next day.
   * Because time parsing interprets `00:08` as 8.0 minutes from midnight instead of $1440 + 8 = 1448.0\text{ min}$, arrival at 1423.0m produces an artificial delay of $1423.0 - 8.0 = \mathbf{1415.0\text{ minutes}}$.

3. **Queueing & Headway Buffer:**
   * At 20 services, headway interactions on the West mainline contribute only ~5.0 min of queueing.
   * At 30 services, headway interactions contribute ~22.0 min.
   * At 40 services, cumulative queueing and junction clearance contribute ~45.0 min.

### 1.3 Grouping by Train Type and Corridor
* **By Train Type:**
  * **EXPRESS (15 trains):** Accounts for **1,621.5 min** (84.5% of total delay). Dominated by published-vs-modeled running time deficits (+25m to +44m per train) and the 1,415m overnight wrap on `SRV_16159_01`.
  * **INTERCITY (6 trains):** Accounts for **86.5 min** (avg 14.4m per train). Dominated by modeled track section runtimes.
  * **SUBURBAN_EMU (18 trains):** Accounts for only **9.0 min** (avg 0.5m per train). EMU timetables closely align with modeled section runtimes.
  * **LONG_DISTANCE (1 train):** **0.0 min** delay.
* **By Corridor:**
  * **South Corridor:** Accounts for **1,415.0 min** (entirely due to `SRV_16159_01`).
  * **West Corridor:** Accounts for **287.0 min** (modeled running time exceeds published timetable across 7 express services).
  * **North Corridor:** Accounts for **7.0 min**.
  * **MRTS Corridor:** Accounts for **8.0 min**.
  * **Beach-Bypass & PTMS:** **0.0 min**.

**Dominant Cause:** Physical running time model discrepancy combined with the midnight rollover anomaly dominates over queueing by more than $30\times$.

---

## 2. Benchmark Cohort Scaling vs. `completed_services: 47` (DIAG-02)

### 2.1 Context & Observations
In `phase34_4_benchmark_results.json`, all rows for loads 4, 8, 12, 16, 20, 30, and 40 record:
`"completed_services": 47`.

### 2.2 Investigation & Code Evidence
Inspection of `scratch/run_phase34_4_benchmarks.py` reveals:
```python
# Lines 101-117 of scratch/run_phase34_4_benchmarks.py:
state = SimulationState(clock=sim_clock)
state.initialize_from_network(orchestrator.network)  # <-- Populates all 47 services
simulator = TrainSimulator(...)

for s_id in services:  # <-- Only iterates over the load cohort (e.g. 4 services)
    simulator.run_service_to_destination(s_id, ...)

completed_services = len(state.train_states)  # <-- Returns 47!
```
1. In `simulation/state.py`, `initialize_from_network` iterates over `network.services` (all 47 services) and instantiates a `TrainRuntimeState` with status `NOT_STARTED`.
2. The simulation loop strictly iterates over `services = SCALABILITY_COHORTS[load_count]`. For load 4, exactly 4 trains are simulated to `COMPLETED`. The remaining 43 remain in `NOT_STARTED`.
3. In `optimization/scenarios.py`, `ScenarioRunner.run_scenario` sets:
   `target_service_ids = scenario.affected_service_ids` (exactly the 4 services).
   Both the FIFO baseline scheduler and the CP-SAT solver formulate and solve the model exclusively for those 4 services (confirmed by solve times: 0.145s for load 4 vs 1.112s for load 40).
4. `completed_services = len(state.train_states)` measured the total capacity of the state dictionary, rather than counting `sum(1 for s in state.train_states.values() if s.status == TrainStatus.COMPLETED)`.

**Finding:** **CONFIRMED.** `load_count` genuinely limits the cohort that is simulated and optimized. The value 47 is an instrumentation reporting artifact in the benchmark script.

---

## 3. The 22 Route Hops Without Directional Track Sections (DIAG-03)

### 3.1 Context & Observations
In `simulation/simulator.py`, when a train progresses between consecutive route nodes `(u, v)`, `find_track_section(net, u, v, direction)` attempts to look up a directional track section matching `u -> v` and direction `UP` or `DOWN`.

### 3.2 Inventory of Missing Hops
Executing a strict directional audit across all 24 routes in `data/infrastructure/routes.json` reveals exactly **22 route hops** where no directional track section exists in `data/track_sections/`:

| # | Route ID | From Node | To Node | Route Direction | Assigned Train Services |
|:---:|---|:---:|:---:|:---:|---|
| 1 | `RT_NORTH_MAS_GPD_SHORT` | KOK | TVT | None (bidirectional) | `SRV_42015_01` |
| 2 | `RT_NORTH_MAS_GPD_SHORT` | TVT | ENR | None (bidirectional) | `SRV_42015_01` |
| 3 | `RT_NORTH_MAS_GPD_SHORT` | ENR | GPD | None (bidirectional) | `SRV_42015_01` |
| 4 | `RT_SOUTH_MSB_TBM_SHORT` | MS | MBM | None (bidirectional) | `SRV_40001_01` |
| 5 | `RT_SOUTH_MSB_TBM_SHORT` | MBM | GDY | None (bidirectional) | `SRV_40001_01` |
| 6 | `RT_SOUTH_MSB_TBM_SHORT` | GDY | TBM | None (bidirectional) | `SRV_40001_01` |
| 7 | `RT_SOUTH_MAINLINE_REVERSE` | CGL | TBM | None (bidirectional) | *(No active service assigned)* |
| 8 | `RT_SOUTH_MAINLINE_REVERSE` | TBM | GDY | None (bidirectional) | *(No active service assigned)* |
| 9 | `RT_SOUTH_MAINLINE_REVERSE` | GDY | MBM | None (bidirectional) | *(No active service assigned)* |
| 10 | `RT_SOUTH_MAINLINE_REVERSE` | MBM | MS | None (bidirectional) | *(No active service assigned)* |
| 11 | `RT_MRTS_ELEVATED_REV` | GWYR | MYND | None (bidirectional) | `SRV_41002_01`, `SRV_41016_01`, `SRV_41132_01` |
| 12 | `RT_MRTS_ELEVATED_REV` | MYND | MTMY | None (bidirectional) | `SRV_41002_01`, `SRV_41016_01`, `SRV_41132_01` |
| 13 | `RT_BEACH_NORTH_BYPASS_REV` | GPD | ENR | None (bidirectional) | `SRV_42602_01` |
| 14 | `RT_BEACH_NORTH_BYPASS_REV` | ENR | TVT | None (bidirectional) | `SRV_42602_01` |
| 15 | `RT_BEACH_NORTH_BYPASS_REV` | TVT | KOK | None (bidirectional) | `SRV_42602_01` |
| 16 | `RT_SOUTH_MS_CGL_EXPRESS` | MS | TBM | None (bidirectional) | `SRV_12635_01`, `SRV_12605_01`, `SRV_16159_01`, `SRV_12693_01` |
| 17 | `RT_SOUTH_MS_CGL_EXPRESS` | TBM | CGL | None (bidirectional) | `SRV_12635_01`, `SRV_12605_01`, `SRV_16159_01`, `SRV_12693_01` |
| 18 | `RT_SOUTH_CGL_MS_EXPRESS` | CGL | TBM | None (bidirectional) | `SRV_12636_01` |
| 19 | `RT_SOUTH_CGL_MS_EXPRESS` | TBM | MS | None (bidirectional) | `SRV_12636_01` |
| 20 | `RT_BEACH_NORTH_BYPASS` | KOK | TVT | None (bidirectional) | `SRV_42601_01` |
| 21 | `RT_BEACH_NORTH_BYPASS` | TVT | ENR | None (bidirectional) | `SRV_42601_01` |
| 22 | `RT_BEACH_NORTH_BYPASS` | ENR | GPD | None (bidirectional) | `SRV_42601_01` |

### 3.3 Simulation Impact
When `strict_track_lookup=False` is passed (as used in the pipeline and benchmarks), the simulation engine gracefully falls back to a nominal 3.0-minute default running time with synthetic section ID `SEC_{u}_{v}`.

**Finding:** **CONFIRMED.** Exactly 22 route hops across 8 routes lack explicit directional track records.

---

## 4. Timetable Time-Order Anomaly in `SRV_16159_01` (DIAG-04)

### 4.1 Observations
Inspecting `data/trains/published_timetables/timetable.json` for service `SRV_16159_01` (Mangalore Mail connecting via South Line):
```json
{"service_id": "SRV_16159_01", "station_id": "MS",  "scheduled_arrival": null,    "scheduled_departure": "23:10"}
{"service_id": "SRV_16159_01", "station_id": "TBM", "scheduled_arrival": "23:38", "scheduled_departure": "23:40"}
{"service_id": "SRV_16159_01", "station_id": "CGL", "scheduled_arrival": "00:08", "scheduled_departure": null}
```

### 4.2 Mathematical Root Cause
1. `time_to_minutes("23:10")` = $23 \times 60 + 10 = 1390.0\text{ min}$.
2. `time_to_minutes("23:38")` = $23 \times 60 + 38 = 1378.0\text{ min}$.
3. `time_to_minutes("00:08")` = $0 \times 60 + 8 = 8.0\text{ min}$.
4. The train departs MS at 1390.0 min. With physical travel time MS -> TBM (17m) + dwell (2m) + TBM -> CGL (14m) = 33m, arrival at CGL occurs at $1390.0 + 33.0 = 1423.0\text{ min}$.
5. Delay calculation computes:
   $$\text{Delay} = \text{Actual Arrival} - \text{Scheduled Arrival} = 1423.0 - 8.0 = \mathbf{1415.0\text{ minutes}}.$$

**Finding:** **CONFIRMED.** The timetable entry crossed midnight into the following calendar day, but time-to-minutes conversion does not add the 1,440-minute day wrap.

---

## 5. Origin of `simulation_timestamp_str` in `/what-if` (DIAG-05)

### 5.1 Observations
Across distinct `/what-if` API invocations, the returned `simulation_timestamp_str` showed values such as `"18:20"`, `"21:25"`, `"19:45"`, raising the question of whether this field is wall-clock based.

### 5.2 Code Evidence
Inspection of `backend/app/pipeline.py` reveals:
```python
# Line 136 of backend/app/pipeline.py:
return PipelineExecutionResult(
    scenario_id=scenario.scenario_id,
    scenario_name=scenario.name,
    simulation_timestamp=state.clock.current_time,
    simulation_timestamp_str=state.clock.current_time_str,  # <-- From state.clock
    ...
)
```
1. `state.clock` is initialized to `SimulationClock(start_time="00:00")`.
2. In Step 2 of `run_pipeline`, the simulation iterates through `selected_svcs`:
   ```python
   for s_id in selected_svcs:
       simulator.run_service_to_destination(s_id, start_time=base_dep + dep_delay)
   ```
3. Inside `simulator.run_service_to_destination`, each route edge advances `state.clock` using `self.clock.advance_to(departure_time)` and `self.clock.advance(travel_time)`.
4. When the loop completes, `state.clock.current_time_str` retains the timestamp at which the **final service in the cohort reached its destination**.
   * Cohort `['SRV_12607_01', 'SRV_12609_01']` ends at **18:20** (12609 finishes).
   * Cohort `['SRV_12607_01', 'SRV_12609_01', 'SRV_12610_01', 'SRV_43411_01']` ends at **21:10** (43411 finishes).
   * Other cohort orders finish at **21:25** or **19:45**.

**Finding:** **CONFIRMED.** `simulation_timestamp_str` is strictly deterministic simulation model time, representing the completion timestamp of the last processed train service in the evaluation cohort. It is **NOT** wall-clock based.

---

## 6. Evaluation Modules Architectural Overlap Analysis (DIAG-06)

### 6.1 `evaluation/consolidation.py` vs. `evaluation/metrics_consolidation.py`

* **Lexical Similarity:** 3.29% (difflib SequenceMatcher).
* **Line Counts:** `consolidation.py` (801 lines) vs. `metrics_consolidation.py` (637 lines).
* **Role of `evaluation/consolidation.py` (Live API Runner):**
  - Defines data classes: `ConsolidatedCaseMetrics`, `ConsolidatedAggregateStats`, `ConsolidatedResearchReport`, `ConsolidatedResearchRunner`.
  - Exposes entry point: `run_consolidated_research(network, state_manager=None) -> ConsolidatedResearchReport`.
  - Dynamically constructs and executes 10 comprehensive operational scenarios (Nominal, Peak Concurrency, West Bottleneck, Speed Restriction, Compound Disruption, Dwell Delay, Blocked Section, Junction Contention, Multiple Bottlenecks, Scale Stress 20) by invoking `TrainSimulator` and `CPSATScheduler`.
  - Consumers: Imported directly by `backend/app/api.py` to power the live `/api/v1/analytics` endpoint, as well as `tests/test_consolidation.py` and `tests/test_analytics.py`.
* **Role of `evaluation/metrics_consolidation.py` (Offline Paper Table Aggregator):**
  - Defines reporting schemas: `ResearchKPISummary`, `GroupKPISummary`, `ScalabilityKPISummary`, `SeverityKPISummary`, `InfeasibleBoundarySummary`, `BottleneckKPISummary`, `ConsolidatedResearchMetrics`, `MetricsConsolidator`.
  - Exposes entry point: `run_metrics_consolidation(...) -> ConsolidatedResearchMetrics`.
  - Operates as a post-processing meta-aggregator for Phase 31.5. Instead of executing simulations itself, it reads the pre-computed outputs of Phase 31.1 (comparative analysis), Phase 31.2 (scalability framework), Phase 31.3 (severity progression), and Phase 31.4 (comparative benchmarks) and formats them into the exact JSON schemas and Markdown tables required for the CICT 2026 conference paper (`data/evaluation/consolidated_research_metrics.json`).
  - Consumers: `tests/test_phase31_5_metrics.py`, `scratch/run_phase31_5.py`.
* **Overlap Findings:**
  - The two files share naming conventions (`Consolidated...`) but have completely disjoint architectures. One is a dynamic simulation testbench runner; the other is a static benchmark metrics formatter.
  - Merging them would create unnecessary coupling between live API endpoints and offline paper publication scripts. They should remain separate.

### 6.2 `evaluation/scalability.py` vs. `evaluation/scalability_framework.py`

* **Lexical Similarity:** 2.39% (difflib SequenceMatcher).
* **Line Counts:** `scalability.py` (791 lines) vs. `scalability_framework.py` (405 lines).
* **Role of `evaluation/scalability.py` (Corridor-Specific Micro-Benchmark):**
  - Defines schemas: `ScalabilityLoadLevel`, `ScalabilityMetrics`, `ScalabilityResult`, `ScalabilityReport`, `ScalabilityRunner`.
  - Exposes: `create_west_corridor_load_levels()`, `run_scalability_suite()`.
  - Focuses on single-corridor stress testing on the West Mainline (`MAS_AJJ`), scaling service load levels from 4 to 20 services.
  - Drives internal profiling tests in `tests/test_scalability.py` and `tests/test_analysis.py`.
* **Role of `evaluation/scalability_framework.py` (Division-Wide Macro-Framework):**
  - Defines schemas: `ScalabilitySuiteResult`.
  - Exposes: `create_scalability_scenario()`, `create_scalability_experiment_config()`, `create_scalability_suite()`, `run_scalability_experiments()`.
  - Authoritative source of `SCALABILITY_COHORTS` (7 cohorts: 4, 8, 12, 16, 20, 30, 40 services) and `COHORT_20`.
  - Generates both Nominal and Compound Disruption benchmark suites across the entire Chennai Division network, feeding directly into `evaluation/comparative_analysis.py`, `scripts/run_v3_evaluation.py`, and Section IV.G of the research paper.
  - Consumers: Imported by 10+ core test modules (`test_phase31_2_scalability.py`, `test_phase34_4_performance.py`, `test_midnight_wrap.py`, `test_time_resolution.py`).
* **Overlap Findings:**
  - `scalability.py` is a specialized West-corridor simulator runner; `scalability_framework.py` is the generalized division-wide scenario generator.
  - The framework module (`scalability_framework.py`) is the official driver for conference paper results and multi-resolution evaluations.
  - Both modules serve distinct experimental layers and must not be merged.
