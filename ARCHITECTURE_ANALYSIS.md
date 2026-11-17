# Railway Traffic Optimizer: Deep Technical Architecture & Codebase Analysis (Post-Batch 8)

This document provides a comprehensive technical audit of the **Railway Traffic Optimizer** codebase as implemented across **Batch 0 through Batch 8**. It explains the architecture, file-by-file responsibilities, data transformations, simulation mechanics, conflict detection algorithms, and optimization contracts based on the Python source code.

---

## 1. Overall Architecture

The system is structured as a layered, discrete-event railway simulation and scheduling framework. It ingests static railway infrastructure and operational timetables, executes deterministic time-stepped train movements, tracks dynamic resource occupancies, identifies safety and operational conflicts, and defines optimization contracts for mathematical solvers.

```
+-----------------------------------------------------------------------------------+
| 1. RAILWAY INFRASTRUCTURE & TIMETABLE DATASETS (Static JSON Source of Truth)       |
|    trains.json | services.json | timetable.json | stations.json | platforms.json  |
|    routes.json | junctions.json | data/track_sections/*.json                      |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 2. NETWORK LOADER & DATA NORMALIZATION LAYER [simulation/network.py]              |
|    - Normalizes raw schema differences without modifying JSON                     |
|    - Instantiates immutable domain models: Station, Platform, TrackSection,       |
|      Junction, Route, Train, Service, TimetableEntry                              |
|    - Validates relational integrity (foreign keys, non-monotone stops, routes)    |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 3. SIMULATION ENGINE & CLOCK [simulation/clock.py, simulation/simulator.py]       |
|    - Deterministic minute-based SimulationClock ("HH:MM" <-> minutes from midnight)|
|    - Route node stepping along Route.ordered_nodes                                |
|    - Directional track lookup (Network.find_track_section) with zero fallbacks    |
|    - Discrete event dispatching (EventQueue, SimulationEvent in simulation/events.py)|
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 4. RUNTIME STATE & OCCUPANCY ENGINE [simulation/state.py]                          |
|    - In-memory TrainRuntimeState (delays, status, positions, resource locks)      |
|    - Dynamic TrackSectionOccupancy (entry_time, expected_exit, actual_exit)       |
|    - Capacity enforcement & CapacityViolationError                                |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 5. CONFLICT DETECTION ENGINE [simulation/conflicts.py]                            |
|    - Conflict model (id, type, affected trains/services, resource, severity, time)|
|    - Detects: SAME_TRACK_SECTION (overcapacity), INSUFFICIENT_HEADWAY (spacing),  |
|      SHARED_JUNCTION (interlocking), INCOMPATIBLE_MOVEMENTS (opposing UP vs DOWN) |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+-----------------------------------------------------------------------------------+
| 6. OPTIMIZATION CONTRACTS & BENCHMARKING [optimization/model.py, objective.py,    |
|    scheduler.py]                                                                  |
|    - Input: OptimizationRequest (services, routes, sections, conflicts, constraints) |
|    - Mathematical Bounds: OptimizationModel                                       |
|    - Objective Formulation: ObjectiveWeights & OptimizationObjective              |
|    - Output: OptimizationResult (adjusted timetables, precedence, metrics)        |
|    - Baseline Scheduler: BaselineScheduler (deterministic reference comparator)   |
+-----------------------------------------------------------------------------------+
                                         │
                                         ▼
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
: 7. BATCH 9: OR-TOOLS CP-SAT OPTIMIZATION SOLVER [PLANNED - NOT IMPLEMENTED YET]   :
:    - Mixed-Integer / Constraint Programming dispatching solver                    :
:    - Decision variables for departure shifts, platform assignments & precedences  :
+ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
```

### Implemented vs. Planned Boundary

* **Implemented (Batches 0–8)**:
  * Full JSON dataset loading, normalization, and integrity validation.
  * In-memory domain models: `Train`, `Service`, `TimetableEntry`, `Route`, `Station`, `Platform`, `TrackSection`, `Junction`.
  * Deterministic simulation clock, discrete-event queue, and event dispatching.
  * Train movement simulation along physical route nodes using directional track sections.
  * Dynamic track section occupancy records, resource locking, and capacity enforcement.
  * Full conflict detection for overcapacity, headway, junction contention, and opposing movements.
  * Optimization layer contracts: `OptimizationRequest`, `OptimizationModel`, `OptimizationResult`, `PerformanceMetrics`, `ObjectiveWeights`, and `BaselineScheduler`.
* **Planned (Batch 9 onwards)**:
  * Mathematical solver (`optimization/solver.py`) using Google OR-Tools CP-SAT.
  * Dynamic re-routing and automated conflict resolution via timetable adjustments and station holds.
  * AI/Reinforcement Learning recommendation engine.
  * Live operator web dashboard.

---

## 2. Project File-by-File Map

```
railway-traffic-optimizer/
├── simulation/
│   ├── __init__.py           # Public exports for the simulation module
│   ├── network.py            # Infrastructure & timetable loader, normalizer, validator
│   ├── clock.py              # Deterministic simulation clock & time conversion helpers
│   ├── events.py             # Discrete event models and deterministic priority event queue
│   ├── state.py              # In-memory runtime state, occupancies, delays, and locks
│   ├── simulator.py          # Train movement engine and route traversal coordinator
│   ├── conflicts.py          # Conflict domain models and 4-way conflict detection engine
│   ├── service_loader.py     # [SKELETON - 0 bytes, superseded by network.py]
│   ├── timetable_loader.py   # [SKELETON - 0 bytes, superseded by network.py]
│   ├── train_loader.py       # [SKELETON - 0 bytes, superseded by network.py]
│   └── train_service.py      # [SKELETON - 0 bytes, superseded by network.py]
├── optimization/
│   ├── __init__.py           # Public exports for the optimization module
│   ├── model.py              # OptimizationRequest, constraint models, decision dataclasses
│   ├── objective.py          # ObjectiveWeights, cost evaluation, and penalty breakdown
│   ├── scheduler.py          # OptimizationResult, PerformanceMetrics, BaselineScheduler
│   └── solver.py             # [SKELETON - 0 bytes, target for Batch 9 OR-Tools solver]
├── backend/
│   └── app/
│       ├── __init__.py       # Backend package init
│       └── main.py           # Entry-point script stub for application server
├── constraints/
│   ├── __init__.py           # [SKELETON - 0 bytes]
│   ├── headway.py            # [SKELETON - 0 bytes, superseded by optimization/model.py]
│   ├── platform_constraints.py # [SKELETON - 0 bytes, superseded by optimization/model.py]
│   ├── railway_constraints.py # [SKELETON - 0 bytes, superseded by optimization/model.py]
│   └── route_constraints.py  # [SKELETON - 0 bytes, superseded by optimization/model.py]
└── tests/
    ├── test_network.py               # Unit tests for network loader & corridor discovery
    ├── test_services.py              # Unit tests for train, service, and timetable parsers
    ├── test_dataset_integrity.py     # Integration tests on full actual JSON datasets
    ├── test_simulation.py            # Unit tests for clock, state, simulator, occupancy
    ├── test_conflicts.py             # Unit tests for all 4 conflict detection algorithms
    ├── test_optimization_contracts.py# Unit tests for optimization input/output contracts
    ├── test_end_to_end.py            # Full end-to-end multi-train scenario integration test
    ├── test_optimization.py          # [SKELETON - 0 bytes]
    ├── test_timetable.py             # [SKELETON - 0 bytes]
    └── test_trains.py                # [SKELETON - 0 bytes]
```

### Detailed Breakdown of Active Python Files

#### 1. `simulation/network.py`
* **Purpose**: Core infrastructure and operational timetable loader, data normalizer, and referential integrity validator.
* **Key Classes**:
  * Infrastructure Models: `Station`, `Platform`, `TrackSection`, `Junction`, `Route`.
  * Operational Models: `Train`, `Service`, `TimetableEntry`.
  * Main Class: `Network` (encapsulates all registries, `load_from_directory`, `load_track_sections`, `load_trains`, `load_services`, `load_timetable`, and `validate`).
* **Imports**: `json`, `os`, `glob`, `collections.defaultdict`, `dataclasses.dataclass`, `typing`.
* **Called by**: `simulator.py`, `state.py`, `conflicts.py`, `optimization/model.py`, and test suites.
* **Input**: JSON files from `data/infrastructure/`, `data/trains/`, `data/track_sections/`.
* **Output**: In-memory populated `Network` instance containing 8 relational dictionaries.

#### 2. `simulation/clock.py`
* **Purpose**: Deterministic simulation clock management and railway time conversions.
* **Key Classes & Functions**:
  * `SimulationClock`: Supports `.tick()`, `.advance(minutes)`, `.advance_to(target_time)`, `.reset()`.
  * `time_to_minutes(val)`: Converts `"HH:MM"` or `"HH:MM:SS"` to float minutes from midnight (e.g. `"15:30"` $\rightarrow 930.0$).
  * `minutes_to_time_str(minutes)`: Converts float minutes to `"HH:MM"` format (e.g. $930.0 \rightarrow \text{"15:30"}$).
* **Called by**: `events.py`, `state.py`, `simulator.py`, `conflicts.py`, `optimization/model.py`.

#### 3. `simulation/events.py`
* **Purpose**: Discrete-event definitions and deterministic priority queue.
* **Key Classes**:
  * `EventType` (Enum): `SERVICE_START`, `DEPARTURE`, `SECTION_ENTER`, `SECTION_EXIT`, `ARRIVAL`, `DWELL_COMPLETE`, `SERVICE_COMPLETE`, `HOLD`, `RESUME`.
  * `SimulationEvent`: Immutable event carrying timestamp, type, service ID, node ID, section ID, and details.
  * `EventQueue`: Deterministic priority queue using `heapq` with `(time, priority, sequence_id)` tie-breaking.
* **Called by**: `simulator.py`.

#### 4. `simulation/state.py`
* **Purpose**: Dynamic in-memory simulation state tracking, section occupancies, resource locks, and delays.
* **Key Classes**:
  * `TrainStatus` (Enum): `NOT_STARTED`, `IN_TRANSIT`, `AT_STATION`, `HELD`, `COMPLETED`.
  * `CapacityViolationError`: Exception raised upon exceeding section capacity.
  * `TrackSectionOccupancy`: Active/historical occupancy record (`section_id`, `service_id`, `train_id`, `entry_time`, `expected_exit_time`, `actual_exit_time`, `from_node`, `to_node`, `direction`).
  * `TrainRuntimeState`: Live status, delays, stop sequence, actual arrival/departure records.
  * `SimulationState`: Central manager with `enter_track_section()`, `exit_track_section()`, `arrive_at_station()`, `depart_from_station()`, `occupy_resource()`, `release_resource()`.
* **Called by**: `simulator.py`, `conflicts.py`, `optimization/model.py`.

#### 5. `simulation/simulator.py`
* **Purpose**: Coordinates train progression along route `ordered_nodes`, performs directional track lookups, advances simulation time, and generates discrete events.
* **Key Classes & Functions**:
  * `find_track_section(network, from_node, to_node, direction)`: Searches network for matching directional or bidirectional track section.
  * `TrainSimulator`: Main coordinator with `.initialize_service()`, `.step_service()`, `.run_service_to_destination()`.
* **Called by**: Test suites, end-to-end runner, and dispatching routines.

#### 6. `simulation/conflicts.py`
* **Purpose**: Conflict domain model and 4-way railway conflict detection engine.
* **Key Classes**:
  * `ConflictType` (Enum): `SAME_TRACK_SECTION`, `INSUFFICIENT_HEADWAY`, `SHARED_JUNCTION`, `INCOMPATIBLE_MOVEMENTS`.
  * `ConflictSeverity` (Enum): `CRITICAL`, `MAJOR`, `WARNING`, `MINOR`.
  * `Conflict`: Deterministic conflict record.
  * `ConflictDetector`: Implements `detect_same_section_conflicts()`, `detect_headway_conflicts()`, `detect_junction_conflicts()`, `detect_incompatible_movements()`, and `detect_all()`.
* **Called by**: `test_conflicts.py`, `test_end_to_end.py`, and `OptimizationRequest` builder.

#### 7. `optimization/model.py`
* **Purpose**: Input contracts, constraint models, and decision variable representations.
* **Key Classes**:
  * Constraints: `HeadwayConstraint`, `JunctionConstraint`, `PlatformConstraint`, `PrecedenceConstraint`.
  * Decisions: `ServiceTimetableAdjustment`, `PrecedenceDecision`, `ResourceAllocationDecision`.
  * Main Contract: `OptimizationRequest` and `OptimizationModel`.

#### 8. `optimization/objective.py`
* **Purpose**: Multi-objective penalty weighting specifications and cost breakdown calculation.
* **Key Classes**:
  * `ObjectiveWeights`: Configurable cost coefficients.
  * `ObjectiveCostBreakdown`: Itemized cost structure.
  * `OptimizationObjective`: Evaluates delay and conflict penalties.

#### 9. `optimization/scheduler.py`
* **Purpose**: Output contracts, performance metrics, and baseline scheduler.
* **Key Classes**:
  * `PerformanceMetrics`: Quantitative summary (delay, throughput, on-time percentage).
  * `OptimizationResult`: Unified solver output with serialization.
  * `BaseScheduler` & `BaselineScheduler`: Reference scheduler.

---

## 3. Data Flow

The following table traces how raw JSON records are loaded, normalized, and stored in Python memory:

```
[Raw JSON Files]
       │
       ├── data/trains/train_identity/trains.json (51 records)
       │      │  train_id → id, train_name → name, service_type → train_type
       │      ▼
       │   Network.trains: Dict[str, Train]
       │
       ├── data/trains/service_definitions/services.json (22 records)
       │      │  service_id → id, train_id, route_id, priority_class, delay_penalty_weight
       │      ▼
       │   Network.services: Dict[str, Service]
       │
       ├── data/trains/published_timetables/timetable.json (84 records)
       │      │  scheduled_arrival/departure → arrival/departure, stop_sequence (derived)
       │      ▼
       │   Network.timetable: List[TimetableEntry]
       │
       ├── data/infrastructure/stations.json (30 records)
       │      ▼
       │   Network.stations: Dict[str, Station]
       │
       ├── data/infrastructure/platforms.json (14 records)
       │      ▼
       │   Network.platforms: Dict[str, Platform]
       │
       ├── data/infrastructure/routes.json (16 records)
       │      ▼
       │   Network.routes: Dict[str, Route]
       │
       ├── data/infrastructure/junctions.json (7 records)
       │      ▼
       │   Network.junctions: Dict[str, Junction]
       │
       └── data/track_sections/*.json (6 corridor files, 354 records)
              │  from → from_node, to → to_node, travel_time_min → travel_time_minutes
              ▼
           Network.track_sections: Dict[str, TrackSection]
```

---

## 4. Train / Service Flow

### Architectural Distinctions

1. **`Train` (Physical Rolling Stock)**:
   Represents physical hardware (e.g. `TR_12607`, Train Number `"12607"`, Type `"SUPERFAST_EXPRESS"`). It has no concept of routes, days of operation, or schedules.
2. **`Service` (Operational Definition)**:
   A scheduled operational run linking a specific `Train` to an assigned `Route` (e.g. `SRV_12607_01` links `TR_12607` to `RT_WEST_MAS_AJJ`). It carries priority class (`HIGH`), delay penalty weight (`1.0`), and rolling-stock profile.
3. **`TimetableEntry` (Published Commercial Stops)**:
   Specific scheduled arrival/departure times at passenger-facing stations (e.g. `MAS` dep `15:30`, `PER` arr `15:43`/dep `15:45`, `AJJ` arr `16:28`). Intermediate non-stop transit waypoints do not require timetable entries.
4. **`TrainRuntimeState` (Live Dynamic State)**:
   Volatile, in-memory execution state tracking current physical node (`current_node`), active section (`current_track_section`), status (`IN_TRANSIT`, `AT_STATION`, `COMPLETED`), accumulated delay (`delay_minutes`), and held resource locks.

---

### Step-by-Step Trace of Service `SRV_12607_01`

```
1. JSON LOADING:
   services.json: { "service_id": "SRV_12607_01", "train_id": "TR_12607", "route_id": "RT_WEST_MAS_AJJ", ... }
   → Parsed into Service object in Network.services["SRV_12607_01"].

2. INITIALIZATION:
   TrainSimulator.initialize_service("SRV_12607_01")
   → Looks up Route "RT_WEST_MAS_AJJ": origin is "MAS".
   → Looks up TimetableEntry for MAS: scheduled_departure is "15:30" (930.0 min).
   → Advances SimulationClock to 930.0 min.
   → Sets SimulationState.train_states["SRV_12607_01"].status = AT_STATION at "MAS".
   → Emits SimulationEvent(type=SERVICE_START, time=930.0, node="MAS").

3. STEPPING & ROUTE TRAVERSAL:
   TrainSimulator.step_service("SRV_12607_01"):
   → Segment 1: from_node="MAS", to_node="BBQ".
   → Direction lookup: RT_WEST_MAS_AJJ matches "DOWN".
   → Network.find_track_section("MAS", "BBQ", "DOWN") resolves "MAS_BBQ_THROAT_SEGMENT_DOWN".
   → travel_time_minutes = 4.0 min.
   → dep_time = 930.0, arr_time = 934.0.
   → State enters section: creates TrackSectionOccupancy(section="MAS_BBQ_THROAT_SEGMENT_DOWN", entry=930.0, exp_exit=934.0).
   → Emits DEPARTURE (MAS) and SECTION_ENTER (MAS_BBQ_THROAT_SEGMENT_DOWN).
   → Clock advances to 934.0 min.
   → State exits section: actual_exit_time = 934.0 (releases occupancy).
   → State arrives at BBQ: status = AT_STATION, current_node = "BBQ".
   → Emits SECTION_EXIT and ARRIVAL (BBQ).

4. ITERATIVE PROGRESSION (All 28 Segments):
   → Repeats step_service across all 28 edges (BBQ→VPY→PER→...→AJJ).
   → At PER: records actual arrival 940.0 min vs scheduled 943.0 min (delay = 0.0 min).
   → Traverses remaining corridor sections resolving exact directional track sections with 0 fallbacks.

5. TERMINATION:
   → Final node "AJJ" reached (curr_idx == 28).
   → SimulationState.complete_service("SRV_12607_01", final_station="AJJ", time=985.0).
   → Status transitions to COMPLETED.
   → All occupied resources and station occupancies are released.
   → Emits SERVICE_COMPLETE event.
```

### Why the Architecture is Fully Generic

The simulator and state engine contain **no hardcoded IDs**:
* `TrainSimulator.step_service` reads `route.ordered_nodes` dynamically for any route.
* `find_track_section` queries `network.track_sections` using `from_node`, `to_node`, and inferred or explicit `direction`.
* Verified across `SRV_12607_01` (DOWN West corridor), `SRV_12610_01` (UP West corridor), `SRV_43219_01` (Short suburban route to Tiruvallur), and `SRV_43102_01` (Military Siding PTMS branch to MAS).

---

## 5. Simulation Flow

```
[Simulation Initialization]
TrainSimulator(network, clock, state)
       │
       ▼
[Service Start]
TrainSimulator.initialize_service(service_id)
       │  Sets clock to departure time, state=AT_STATION, emits SERVICE_START
       ▼
[Loop: while not train_state.is_completed]
       │
       ├── 1. Get from_node, to_node from Route.ordered_nodes[curr_idx, curr_idx+1]
       │
       ├── 2. Resolve TrackSection via find_track_section(network, from_node, to_node, direction)
       │
       ├── 3. Record Departure: SimulationState.depart_from_station() → Emits DEPARTURE event
       │
       ├── 4. Enter Track Section: SimulationState.enter_track_section()
       │      - Validates section capacity (raises CapacityViolationError if full)
       │      - Creates TrackSectionOccupancy record
       │      - Emits SECTION_ENTER event
       │
       ├── 5. Advance Simulation Clock: clock.advance_to(current_time + travel_time)
       │
       ├── 6. Exit Track Section: SimulationState.exit_track_section()
       │      - Sets actual_exit_time on occupancy record
       │      - Emits SECTION_EXIT event
       │
       ├── 7. Arrive at Next Node: SimulationState.arrive_at_station()
       │      - Computes delay against TimetableEntry if stop is commercial
       │      - Emits ARRIVAL event
       │
       └── 8. Check Termination: If to_node == service.destination → complete_service()
```

---

## 6. Occupancy and Resource Flow

Resource tracking is completely separated from static data and maintained strictly in `SimulationState`:

```
+-----------------------------------------------------------------------------------+
| SIMULATION STATE RESOURCE CONTAINERS (In-Memory Only)                             |
|                                                                                   |
| 1. active_occupancies: Dict[str, Dict[str, TrackSectionOccupancy]]                |
|    - section_id → { service_id → TrackSectionOccupancy }                          |
|                                                                                   |
| 2. occupancy_history: List[TrackSectionOccupancy]                                 |
|    - Monotonically growing audit log of all completed & active occupancies        |
|                                                                                   |
| 3. track_occupancy: Dict[str, Set[str]]                                           |
|    - section_id → set(service_ids currently on section)                           |
|                                                                                   |
| 4. station_occupancy: Dict[str, Set[str]]                                         |
|    - station_id/node_id → set(service_ids currently dwelling or stopped)          |
|                                                                                   |
| 5. resource_occupancy: Dict[str, str]                                             |
|    - resource_id → service_id currently holding exclusive lock                    |
+-----------------------------------------------------------------------------------+
```

### Occupancy Lifecycle During Movement

1. **Entry (`enter_track_section`)**:
   * Inspects `len(active_occupancies[section_id])`. If $\ge \text{capacity}$, raises `CapacityViolationError`.
   * Creates dynamic `TrackSectionOccupancy` record with `entry_time` and `expected_exit_time`.
   * Inserts into `active_occupancies[section_id]` and appends to `occupancy_history`.
2. **Release (`exit_track_section`)**:
   * Removes from `active_occupancies[section_id]`.
   * Populates `actual_exit_time` on the `TrackSectionOccupancy` instance.
   * `is_active` becomes `False`; `duration_minutes` becomes `actual_exit_time - entry_time`.
   * Clears section ID from `train_state.occupied_resources`.

---

## 7. Conflict Detection Flow

The `ConflictDetector` runs sweep-line and interval-overlap algorithms across occupancy records and live simulation states:

```
                                  [ConflictDetector.detect_all()]
                                                │
       ┌────────────────────────┬───────────────┴───────────────┬────────────────────────┐
       ▼                        ▼                               ▼                        ▼
[SAME_TRACK_SECTION]  [INSUFFICIENT_HEADWAY]           [SHARED_JUNCTION]        [INCOMPATIBLE_MOVEMENTS]
Concurrent occupancy  Consecutive entry delta         Simultaneous presence    Opposing UP vs DOWN
> section capacity    < minimum_headway_minutes       at junction/throat node  on shared track section
       │                        │                               │                        │
       └────────────────────────┴───────────────┬───────────────┴────────────────────────┘
                                                │
                                                ▼
                                    List[Conflict] (Deterministic)
                                    - conflict_id: 'CONF_0001'
                                    - conflict_type: ConflictType
                                    - affected_service_ids: [...]
                                    - affected_train_ids: [...]
                                    - resource_id: str
                                    - conflict_time: float ("HH:MM")
                                    - severity: ConflictSeverity
                                    - description: str
                                    - metadata: {...}
```

### Detection Logic per Conflict Type

1. **Same Track Section (`detect_same_section_conflicts`)**:
   * **Input**: List of `TrackSectionOccupancy` records, section `capacity`.
   * **Logic**: Sweep-line over entry ($+1$) and exit ($-1$) events. If active trains $> \text{capacity}$, flags a `SAME_TRACK_SECTION` conflict (`CRITICAL` for single track, `MAJOR` for multi-track).
2. **Insufficient Headway (`detect_headway_conflicts`)**:
   * **Input**: List of `TrackSectionOccupancy` records, `minimum_headway_minutes`.
   * **Logic**: Sorts occupancies per section by `entry_time`. For consecutive trains $T_1, $T_2$$ in the same direction, computes $\Delta t = T_2.\text{entry\_time} - T_1.\text{entry\_time}$. If $0 \le \Delta t < H_{min}$, flags `INSUFFICIENT_HEADWAY` (`MAJOR` if $\Delta t < \frac{H_{min}}{2}$, else `WARNING`).
3. **Shared Junction (`detect_junction_conflicts`)**:
   * **Input**: Live `SimulationState` station occupancies or node arrival/departure intervals.
   * **Logic**: Evaluates junction nodes registered in `network.junctions` (e.g. `JCT_BBQ`, `JCT_VJM`, `JCT_PAB`). If simultaneous trains $> \text{junction.capacity}$, flags `SHARED_JUNCTION` (`MAJOR`).
4. **Incompatible Movements (`detect_incompatible_movements`)**:
   * **Input**: List of `TrackSectionOccupancy` records.
   * **Logic**: For pairs with overlapping time intervals on the same physical section, inspects directions. If one is `UP` and the other is `DOWN` (or $A \to B$ vs $B \to A$), flags `INCOMPATIBLE_MOVEMENTS` (`CRITICAL` severity).

---

## 8. Optimization Architecture (Batch 8 Contracts)

Batch 8 established the **data contracts, constraint models, and objective formulations** required for mathematical optimization, decoupling the simulation engine from the downstream solver.

```
[Network Data + Simulation State + Detected Conflicts]
                          │
                          ▼
             [OptimizationRequest.from_network_and_state()]
             - services, trains, timetable, routes, sections
             - active_conflicts, current_delays
             - headway_constraints, junction_constraints, platform_constraints
                          │
                          ▼
                 [OptimizationModel]
                 - Structural validation (references, routes)
                 - Section sequence derivation
                          │
                          ▼
            [ObjectiveWeights & OptimizationObjective]
            - delay_weight (1.0), weighted_delay_weight (2.0)
            - conflict penalties (CRITICAL: 1000, MAJOR: 200, WARNING: 50)
                          │
                          ▼
             [BaseScheduler (Abstract Interface)]
                          │
            ┌─────────────┴─────────────┐
            ▼                           ▼
  [BaselineScheduler]          [Batch 9 CP-SAT Solver]
  - Generates baseline         - Formulates MIP / CP-SAT model
    timings from schedule      - Solves optimal departure shifts,
  - Computes unoptimized         platform allocations, & precedences
    reference metrics          - Eliminates conflicts
            │                           │
            └─────────────┬─────────────┘
                          │
                          ▼
                 [OptimizationResult]
                 - status: "BASELINE" / "OPTIMAL" / "FEASIBLE"
                 - adjusted_timetables: Dict[str, List[ServiceTimetableAdjustment]]
                 - precedence_decisions: List[PrecedenceDecision]
                 - resource_decisions: List[ResourceAllocationDecision]
                 - metrics: PerformanceMetrics (delay, throughput, conflicts)
                 - cost_breakdown: ObjectiveCostBreakdown
```

### Key Contract Structures

* **`OptimizationRequest`**: Input payload containing all problem data.
* **`HeadwayConstraint`**: Encapsulates $t_{2}^{dep} - t_{1}^{dep} \ge H_{min}$ for sections.
* **`JunctionConstraint`**: Enforces throat capacity bounds $\sum x_{s, j}(t) \le \text{capacity}$.
* **`PlatformConstraint`**: Station platform dwell time lower/upper bounds.
* **`PrecedenceConstraint`**: Train sequencing order on shared resources.
* **`ServiceTimetableAdjustment`**: Output decision representing adjusted arrival/departure times per stop.
* **`PerformanceMetrics`**: Quantitative metrics (`total_delay_minutes`, `max_delay_minutes`, `throughput`, `on_time_performance_percent`).

---

## 9. Actual Execution Flow

Below is the concrete execution trace that occurs when running an end-to-end simulation scenario in Python:

```python
# 1. Load static infrastructure and operational timetable
network = Network()
network.load_from_directory("data/infrastructure")
network.load_trains("data/trains/train_identity/trains.json")
network.load_services("data/trains/service_definitions/services.json")
network.load_timetable("data/trains/published_timetables/timetable.json")

# 2. Initialize deterministic clock and runtime state
clock = SimulationClock(start_time="15:30")
state = SimulationState(clock=clock)
state.initialize_from_network(network)

# 3. Instantiate simulator and conflict detector
simulator = TrainSimulator(network=network, clock=clock, state=state)
detector = ConflictDetector(network=network)

# 4. Simulate train movement along physical route
events = simulator.run_service_to_destination("SRV_12607_01", strict_track_lookup=True)
# -> Emits 114 discrete events, traverses all 28 sections, updates state to COMPLETED

# 5. Detect runtime and schedule conflicts
conflicts = detector.detect_all(state=state)

# 6. Construct optimization request contract
request = OptimizationRequest.from_network_and_state(
    network=network,
    state=state,
    conflicts=conflicts,
    service_ids=["SRV_12607_01", "SRV_12609_01"]
)

# 7. Validate problem formulation
model = OptimizationModel(request=request)
assert len(model.validate()) == 0

# 8. Execute baseline scheduler
scheduler = BaselineScheduler()
result = scheduler.schedule(request)

# 9. Inspect quantitative results
print(result.summary())
# -> Status: BASELINE, Throughput: 2 services, Total Delay: 0.0 min
```

---

## 10. Import / Call Graph

The diagram below reflects the **actual import relationships** across the codebase:

```mermaid
graph TD
    subgraph Optimization Layer
        OPT_INIT[optimization/__init__.py]
        OPT_SCHED[optimization/scheduler.py]
        OPT_OBJ[optimization/objective.py]
        OPT_MOD[optimization/model.py]
    end

    subgraph Simulation Layer
        SIM_INIT[simulation/__init__.py]
        SIM_SIM[simulation/simulator.py]
        SIM_CONF[simulation/conflicts.py]
        SIM_STATE[simulation/state.py]
        SIM_EVT[simulation/events.py]
        SIM_CLOCK[simulation/clock.py]
        SIM_NET[simulation/network.py]
    end

    subgraph Static Datasets
        DATA_JSON[(JSON Data Files)]
    end

    %% Dataset connections
    DATA_JSON --> SIM_NET

    %% Simulation internal calls
    SIM_NET --> SIM_STATE
    SIM_NET --> SIM_SIM
    SIM_NET --> SIM_CONF
    SIM_CLOCK --> SIM_EVT
    SIM_CLOCK --> SIM_STATE
    SIM_CLOCK --> SIM_SIM
    SIM_CLOCK --> SIM_CONF
    SIM_EVT --> SIM_SIM
    SIM_STATE --> SIM_SIM
    SIM_STATE --> SIM_CONF

    %% Optimization internal calls & simulation dependencies
    SIM_NET --> OPT_MOD
    SIM_STATE --> OPT_MOD
    SIM_CONF --> OPT_OBJ
    SIM_CONF --> OPT_MOD
    SIM_CONF --> OPT_SCHED
    SIM_CLOCK --> OPT_OBJ
    SIM_CLOCK --> OPT_MOD
    SIM_CLOCK --> OPT_SCHED
    OPT_OBJ --> OPT_MOD
    OPT_OBJ --> OPT_SCHED
    OPT_MOD --> OPT_SCHED

    %% Module init exports
    SIM_NET --> SIM_INIT
    SIM_CLOCK --> SIM_INIT
    SIM_EVT --> SIM_INIT
    SIM_STATE --> SIM_INIT
    SIM_SIM --> SIM_INIT
    SIM_CONF --> SIM_INIT

    OPT_OBJ --> OPT_INIT
    OPT_MOD --> OPT_INIT
    OPT_SCHED --> OPT_INIT
```

---

## 11. What is Already Working

The following capabilities have been audited and verified by **118 passing automated tests**:

* **Dataset Loading & Integrity**:
  * Loads **51 trains**, **22 services**, **84 timetable entries**, **354 track sections** (across 6 corridor files), **7 junctions**, **30 stations**, **14 platforms**, and **16 routes**.
  * Zero modifications to underlying static JSON datasets.
* **Track Section Discovery & Resolution**:
  * Automatic discovery of `data/track_sections/*.json`.
  * **0 fallbacks**: All 28 physical route edges for `SRV_12607_01`, `SRV_12610_01`, `SRV_43219_01`, and `SRV_43102_01` resolve exact directional track sections.
* **Deterministic Simulation Engine**:
  * `SimulationClock` precision time advancement.
  * Deterministic discrete-event queue ordering via `(time, priority, sequence_id)`.
* **Runtime Occupancy & Capacity Enforcement**:
  * In-memory `TrackSectionOccupancy` tracking entry, expected exit, actual exit, and duration.
  * Explicit `CapacityViolationError` raised when section capacity is exceeded.
* **4-Way Conflict Detection**:
  * Headway violations, opposing movements (`UP` vs `DOWN`), shared junction contention, and section overcapacity.
* **Optimization Contracts**:
  * `OptimizationRequest`, `OptimizationModel`, `ObjectiveWeights`, and `BaselineScheduler` validate and produce structured `OptimizationResult` outputs.

---

## 12. What is Not Implemented Yet

To maintain architectural transparency, the following components are **not yet implemented**:

1. **OR-Tools CP-SAT Solver (`optimization/solver.py`)**:
   * Mathematical solver formulation using integer decision variables for stop arrival/departure times, station dwell times, and binary precedence variables. (Targeted for **Batch 9**).
2. **Multi-Train Dynamic Dispatching & Rerouting**:
   * Interactive hold-and-release mechanism to dynamically pause low-priority trains at stations while higher-priority expresses overtake.
3. **Automated Platform Allocation Optimization**:
   * Dynamic assignment of station platform tracks to resolve platform contention.
4. **AI / Reinforcement Learning Recommendation Engine**:
   * No machine learning or heuristic dispatch recommendation modules exist in the active pipeline.
5. **Operator Web Dashboard / Frontend UI**:
   * No web GUI or REST API controllers currently wrap the engine (`backend/app/main.py` is a placeholder).
6. **Live Real-World Signal / GPS Feed Integration**:
   * The system currently operates purely on offline static JSON datasets and simulated clock ticks.

---

## 13. Supervisor Explanation (3 Levels)

### Level A: 30-Second Explanation
> *"We have built a deterministic railway digital-twin simulation engine and conflict-detection pipeline. It loads our actual Chennai railway network data—over 350 track sections, 51 trains, and 22 scheduled services—and simulates physical train movements node-by-node without touching the static JSON files. It accurately tracks live track occupancies, enforces capacity limits, and detects headway, junction, and opposing-movement conflicts. We have also established the complete optimization contracts and baseline benchmarking layer, setting the exact input/output specifications ready for the OR-Tools CP-SAT mathematical optimization solver in Batch 9."*

### Level B: 2-Minute Explanation
> *"Our project is structured into three clear layers: Data Ingestion, Simulation/Conflict Detection, and Optimization Contracts.*
>
> *First, the **Network Loader** reads and normalizes our real infrastructure and timetable JSON datasets into immutable domain models with zero data loss or hardcoding.*
>
> *Second, our **Simulation and State Engine** moves trains deterministically across ordered route nodes using real directional track sections with zero fallbacks. As trains enter and exit sections, an in-memory runtime state records dynamic occupancy intervals and enforces section capacities. Our **Conflict Detection Engine** evaluates these occupancies to identify headway violations, bottleneck junction contention, and head-on opposing movements on shared tracks.*
>
> *Third, we completed the **Optimization Layer Contracts**. We defined the `OptimizationRequest` data structure, constraint definitions for headways and junctions, and multi-objective cost weightings for delay and conflict minimization. We also implemented a `BaselineScheduler` that outputs an `OptimizationResult`. Everything is fully verified with 118 automated tests passing, providing the clean foundation needed to implement the OR-Tools CP-SAT solver."*

### Level C: 5-Minute Detailed Explanation
> *"To give a complete architectural breakdown:*
>
> *1. **Data Normalization & Loader (`simulation/network.py`)**: The railway infrastructure has different schemas across corridor files. Our loader normalizes field aliases (`from` $\rightarrow$ `from_node`, `travel_time_min` $\rightarrow$ `travel_time_minutes`) and automatically discovers all 6 corridor files containing 354 sections. It separates physical rolling stock (`Train`) from operational patterns (`Service`) and passenger schedules (`TimetableEntry`).*
>
> *2. **Deterministic Movement & Clock (`simulation/clock.py`, `simulator.py`)**: Simulation time is represented as floating-point minutes from midnight. The simulator steps services through their assigned route's `ordered_nodes`, queries directional track sections, calculates travel times, and generates discrete simulation events (`DEPARTURE`, `SECTION_ENTER`, `SECTION_EXIT`, `ARRIVAL`, `SERVICE_COMPLETE`) through a deterministic priority queue.*
>
> *3. **Runtime Occupancy & State Management (`simulation/state.py`)**: Occupancy is tracked strictly in memory using `TrackSectionOccupancy` records. When a train attempts to enter a section that is at full capacity, the engine raises a `CapacityViolationError`. When the train clears the section, exit timestamps and occupancy durations are recorded, and resource locks are released.*
>
> *4. **Conflict Detection (`simulation/conflicts.py`)**: The conflict detector runs deterministic sweep-line and interval-overlap algorithms to identify four distinct operational conflicts: track section overcapacity, insufficient headway spacing between successive trains, shared junction/throat contention, and critical incompatible opposing movements on bidirectional lines. Each conflict is packaged into a structured `Conflict` object carrying severity, timestamp, affected trains, and disputed resource IDs.*
>
> *5. **Optimization Contracts & Baseline Scheduler (`optimization/`)**: In Batch 8, we established the mathematical optimization interface. An `OptimizationRequest` aggregates active services, infrastructure, constraints, and detected conflicts. The `OptimizationObjective` defines weighting coefficients for delays and safety violations. The `BaselineScheduler` establishes unoptimized schedule benchmarks, outputting an `OptimizationResult` with itemized delays, throughput metrics, and stop-by-stop `ServiceTimetableAdjustment` records.*
>
> *All 118 unit, integration, and end-to-end tests pass in under 1.5 seconds, ensuring the codebase is robust, stable, and ready for Batch 9 (OR-Tools CP-SAT solver implementation)."*

---

## Architecture Status: Batch 0–8 Summary

| Subsystem | Source Files | Test Coverage | Status |
| :--- | :--- | :--- | :--- |
| **Dataset Ingestion & Validation** | `simulation/network.py` | `test_network.py`, `test_services.py`, `test_dataset_integrity.py` | **COMPLETE** |
| **Simulation Clock & Event Queue** | `simulation/clock.py`, `events.py` | `test_simulation.py` | **COMPLETE** |
| **Train Movement Engine** | `simulation/simulator.py` | `test_simulation.py`, `test_end_to_end.py` | **COMPLETE** |
| **State & Occupancy Tracking** | `simulation/state.py` | `test_simulation.py`, `test_end_to_end.py` | **COMPLETE** |
| **Conflict Detection Engine** | `simulation/conflicts.py` | `test_conflicts.py`, `test_end_to_end.py` | **COMPLETE** |
| **Optimization Contracts & Baseline** | `optimization/model.py`, `objective.py`, `scheduler.py` | `test_optimization_contracts.py` | **COMPLETE** |
| **OR-Tools CP-SAT Solver** | `optimization/solver.py` *(0 bytes)* | *(Pending Batch 9)* | **READY FOR IMPLEMENTATION** |
| **Full Test Suite** | 7 test modules | **118 passed in 1.13s** | **100% GREEN** |
