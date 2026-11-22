# Contract Changes Log

This log documents all additive changes to API endpoints and runtime contracts.

## Batch 1: Test Isolation & State Management Contracts

| Scope | Identifier / Parameter | Type | Default | Description / Reason |
|---|---|:---:|:---:|---|
| Environment Variable | `RAILWAY_RUNTIME_DIR` | String (Directory Path) | `runtime/` | Sets the target directory for live simulation state persistence (`runtime_simulation_state.json`). Allows tests to isolate runtime state to a temporary directory without mutating repository datasets. |
| Python API | `get_simulation_manager(network, state_file_path)` | String (Optional Path) | `None` | Additive optional parameter enabling callers and tests to specify an explicit state file path instead of the global default. |
| REST API | N/A | N/A | N/A | No public REST API endpoints or schemas were modified in Batch 1. All changes are internal runtime isolation mechanisms. |

## Batch 2: Result Integrity, Infeasible Handling, Objective Reporting & Validation

| Endpoint | Field / Parameter | Direction | Type | Default | Reason / Description |
|---|---|:---:|:---:|:---:|---|
| `/api/v1/optimize` | `objective_mode` | Request | `Optional[str]` | `"WEIGHTED"` | Specifies optimization objective mode: `"WEIGHTED"` (minimizing weighted penalty + origin deviation + max delay) or `"TOTAL_DELAY"` (minimizing plain sum of delays). |
| `/api/v1/optimize` | `blocked_sections` | Request | `Optional[List[str]]` | `[]` | List of completely blocked track section IDs (capacity 0). Validated against network track sections (returns 400 on unknown ID). |
| `/api/v1/optimize` | `solution_available` | Response | `bool` | `True` | Flag indicating whether solver produced a valid schedule (`OPTIMAL` or `FEASIBLE`). `False` if `INFEASIBLE`. |
| `/api/v1/optimize` | `optimized_total_delay_minutes` | Response | `Optional[float]` | `None` (if infeasible) | Changed from non-null float to optional; returns `null` when `solution_available` is `False`. |
| `/api/v1/optimize` | `net_delay_savings_minutes` | Response | `Optional[float]` | `None` (if infeasible) | Changed from non-null float to optional; returns `null` when `solution_available` is `False`. |
| `/api/v1/optimize` | `net_delay_savings_percent` | Response | `Optional[float]` | `None` (if infeasible) | Changed from non-null float to optional; returns `null` when `solution_available` is `False`. |
| `/api/v1/optimize` | `fifo_weighted_objective` | Response | `Optional[float]` | `None` | Multi-objective penalty evaluation of the feasible FIFO baseline schedule. |
| `/api/v1/optimize` | `optimized_weighted_objective` | Response | `Optional[float]` | `None` | Multi-objective penalty evaluation of the CP-SAT optimized schedule (null if infeasible). |
| `/api/v1/optimize` | `objective_mode` | Response | `str` | `"WEIGHTED"` | Objective mode used during optimization. |
| `/api/v1/what-if` | `objective_mode` | Request | `Optional[str]` | `"WEIGHTED"` | Specifies optimization objective mode: `"WEIGHTED"` or `"TOTAL_DELAY"`. |
| `/api/v1/what-if` | `solution_available` | Response | `bool` | `True` | Flag indicating whether solver produced a valid schedule (`OPTIMAL` or `FEASIBLE`). `False` if `INFEASIBLE`. |
| `/api/v1/what-if` | `total_optimized_delay_minutes` | Response | `Optional[float]` | `None` (if infeasible) | Returns `null` when `solution_available` is `False`. Prevents reporting false 0.0 delay on infeasibility. |
| `/api/v1/what-if` | `net_delay_savings_minutes` | Response | `Optional[float]` | `None` (if infeasible) | Returns `null` when `solution_available` is `False`. Prevents reporting false 100% savings on infeasibility. |
| `/api/v1/what-if` | `net_delay_savings_percent` | Response | `Optional[float]` | `None` (if infeasible) | Returns `null` when `solution_available` is `False`. Prevents reporting false savings on infeasibility. |
| `/api/v1/what-if` | `fifo_weighted_objective` | Response | `Optional[float]` | `None` | Multi-objective penalty evaluation of the feasible FIFO baseline schedule. |
| `/api/v1/what-if` | `optimized_weighted_objective` | Response | `Optional[float]` | `None` | Multi-objective penalty evaluation of the CP-SAT optimized schedule (null if infeasible). |
| `/api/v1/what-if` | `objective_mode` | Response | `str` | `"WEIGHTED"` | Objective mode used during optimization. |
| `/api/v1/what-if` | `simulation_timestamp_str` | Response | `str` | N/A | Clarified contract semantics: Authoritative discrete simulation clock time (HH:MM) corresponding to arrival of final simulated service in cohort. Strictly deterministic model time, not wall-clock based. |
| `/api/v1/what-if`, `/api/v1/optimize` | `departure_delays`, `station_delays` | Request | `Dict` | `{}` | Pydantic field validator enforces `ge=0` (HTTP 422 Unprocessable Entity for negative delays). |
| `/api/v1/what-if`, `/api/v1/optimize` | `service_ids` | Request | `List[str]` | `None` (default 4) | Empty list `[]` rejected with HTTP 400 Bad Request. Unknown IDs rejected with HTTP 400 Bad Request. |
| `/api/v1/what-if`, `/api/v1/optimize` | `blocked_sections` | Request | `List[str]` | `[]` | Unknown track section IDs rejected with HTTP 400 Bad Request with list of valid IDs returned in error detail. |
| Advisor Directive | `NO_FEASIBLE_SCHEDULE` | Recommendation | Type | N/A | When solver status is `INFEASIBLE`, advisor sets `OperationalSeverity.EMERGENCY` and returns exactly one directive recommendation titled `"No feasible schedule with the blocked resources: <list>"`. Never returns `"Maintain published timetable"`. |

## Batch 3: Data Integrity, Active Services, Route Node Registry & Provenance

| Endpoint / Component | Field / Parameter | Direction | Type | Default | Reason / Description |
|---|---|:---:|:---:|:---:|---|
| `/api/v1/network` | `active_service_count` | Response | `int` | `40` | Count of active services having at least one published timetable record. |
| `/api/v1/network` | `excluded_service_count` | Response | `int` | `7` | Count of services excluded from scheduling due to absence of timetable evidence. |
| `/api/v1/network` | `services[].active` | Response | `bool` | `True` | Flag indicating whether service has published timetable evidence (False for 7 pending services). |
| `/api/v1/network` | `services[].exclusion_reason` | Response | `Optional[str]` | `None` | Provenance reason for excluded services (`"No published timetable evidence"`). |
| `/api/v1/network` | `nodes` | Response | `List[RouteNodeSummary]` | `[]` | Registry of all 107 unique route nodes with `id`, `name` (null when unknown), `has_station_record`, `node_type` (`STATION`, `JUNCTION`, `WAYPOINT`), `corridors`, and `platform_count`. |
| `/api/v1/network` | `data_provenance` | Response | `Optional[Dict[str, Any]]` | `None` | Data provenance summary: timetable row breakdown by source (`erail.in` 103, `railyatri.in` 22, `confirmtkt.com` 2; `PUBLIC_REFERENCE` 127), SHA-256 hashes of all 13 dataset files, and snapshot date (`2026-09-26`). |
| `/api/v1/health` | `integrity_warning_count` | Response | `int` | `836` | Total count of data-integrity warnings logged during network loading. |
| `/api/v1/health` | `integrity_summary` | Response | `Dict[str, int]` | `{}` | Warning count breakdown by category (`station_record_missing_for_route_node` 749, `no_track_section_for_hop` 83, `timetable_references_unknown_station` 4). |
| `/api/v1/health` | `datasets_integrity_status` | Response | `str` | `"WARNINGS"` | Data integrity health status flag (`"WARNINGS"` if warnings > 0, else `"CLEAN"`). |
| `/api/v1/health` | `network_status.*` | Response | `Dict` | N/A | Sub-dictionary also enriched with `integrity_warning_count`, `integrity_summary`, and `datasets_integrity_status` while preserving existing `datasets_intact: True`. |
| `/api/v1/simulate`, `/api/v1/optimize`, `/api/v1/what-if`, `/api/v1/simulation/control` | `service_ids` | Request | `List[str]` | Active services | Explicit request for any of the 7 excluded services rejected with HTTP 400 Bad Request and provenance note (`"Service '<id>' is excluded from operational scheduling: No published timetable evidence."`). Default requests select active services. |
| `OptimizationRequest`, `CPSATScheduler` | `enable_platform_conflicts` | Config / Flag | `bool` | `False` | Feature flag (and `ENABLE_PLATFORM_CONFLICTS` env var). Default `False` preserves legacy empty platform allocations for paper reproducibility; `True` maps station platforms to `{station_id}_P1`/`{station_id}_P2`. |


## Batch 4: Live Runtime Simulation Engine & Event Streaming

| Endpoint / Component | Field / Parameter | Direction | Type | Default | Reason / Description |
|---|---|:---:|:---:|:---:|---|
| `/api/v1/simulation/control` | `seek_minute` | Request | `Optional[float]` | `None` | Timeline scrubbing target minute. Instantly repositions simulation clock to `seek_minute` clamped to `[start_minute, end_minute]` and recomputes snapshot. |
| `/api/v1/simulation/control` | `playback_speed` | Request | `Optional[int]` | `None` | Extended supported speeds: `1`, `2`, `5`, `10`, `30`, `60` sim-minutes per real-minute. |
| `/api/v1/simulation/events` | N/A | Request (GET) | N/A | N/A | Retrieves list of all active disruption events persisted in `runtime/runtime_simulation_events.jsonl`. |
| `/api/v1/simulation/events` | `SimulationEventCreateRequest` | Request (POST) | JSON Body | N/A | Injects operational disruption event (`DEPARTURE_DELAY`, `DWELL_DELAY`, `SPEED_RESTRICTION`, `BLOCKED_SECTION`). Validates IDs, persists to JSONL, and triggers state recomputation. |
| `/api/v1/simulation/events/{id}` | N/A | Request (DELETE) | Path Param | N/A | Removes injected disruption event by ID, persists change, re-evaluates pure-function state from scratch, and emits `event_removed` SSE event. |
| `/api/v1/simulation/stream` | `Last-Event-ID` | Request Header (GET) | `Optional[str]` | `None` | Server-Sent Events (SSE) stream endpoint. Emits typed events (`tick`, `conflict_detected`, `conflict_cleared`, `event_injected`, `event_removed`, `proposal_ready`, `heartbeat`). Reconnects seamlessly using sequence IDs. |
| `/api/v1/simulation/reoptimize` | N/A | Request (POST) | Empty Body | N/A | Evaluates current simulation snapshot and active disruptions with CP-SAT solver. Stores reoptimization proposal with `PENDING` status in `runtime/runtime_simulation_proposals.json` without altering running plan. |
| `/api/v1/simulation/proposals/{id}/accept` | N/A | Request (POST) | Path Param | N/A | Human-in-the-loop action: marks proposal `ACCEPTED` and applies optimized timetable adjustments to `runtime/runtime_simulation_applied_plan.json`. |
| `/api/v1/simulation/proposals/{id}/reject` | N/A | Request (POST) | Path Param | N/A | Human-in-the-loop action: marks proposal `REJECTED` and preserves current plan. |
| `LiveSimulationEngine` | Startup State | Lifecycle | `bool` | `is_playing=False` | Authoritative startup guarantee: server always starts paused regardless of persisted state file value. Background loop never advances time until explicitly started. |

## Batch 6: Integrity & Provenance Alignment

| Endpoint / Component | Field / Parameter | Direction | Type | Default | Reason / Description |
|---|---|:---:|:---:|:---:|---|
| `/api/v1/network` | `data_provenance.snapshot_date` | Response | `Optional[str]` | `None` (`null`) | Replaced hard-coded literal `"2026-09-26"` with `null` (or configurable via `DATASET_SNAPSHOT_DATE` env var) per Rule 2 since master datasets do not specify snapshot date. |
| `/api/v1/network` | `data_provenance.snapshot_date_provenance` | Response | `str` | `"Unspecified in source dataset; null per data provenance rules"` | Explanatory provenance note describing the source of `snapshot_date`. |
| `/api/v1/optimize`, `/api/v1/what-if` | `apply_midnight_wrap` | Request | `Optional[bool]` | `False` | Opt-in flag (default False). When True, applies +1440 minute day wrap to services crossing midnight (e.g., SRV_16159_01). Corrected evaluation results stored separately in `data/evaluation/v2/`. |
| `OptimizationRequest`, `ScenarioRunner`, `ResearchExperimentRunner` | `apply_midnight_wrap` | Config / Parameter | `bool` | `False` | Internal model/runner parameter enabling day-wrap calculations when opt-in flag is True. Default False preserves frozen paper numbers. |

## Batch 9: Time Resolution Parameterization

| Endpoint / Component | Field / Parameter | Direction | Type | Default | Reason / Description |
|---|---|:---:|:---:|:---:|---|
| `/api/v1/optimize`, `/api/v1/what-if` | `time_resolution` | Request | `Optional[int]` | `1` | Opt-in time resolution multiplier (1 = 1 minute, 2 = 0.5 minute / 30 seconds). Internal CP-SAT integer unit is `1/time_resolution` minutes. Fractional inputs must be exact multiples of `1/time_resolution` or an HTTP 400 Bad Request error is raised. Results are converted back to minutes. |
| `OptimizationRequest`, `CPSATScheduler`, `ScenarioRunner`, `PipelineOrchestrator`, `ResearchExperimentRunner`, `ComparativeAnalyzer` | `time_resolution` | Config / Parameter | `int` | `1` | Configures internal time discretization granularity. Default `1` preserves frozen paper results bit-for-bit. |

## Batch 10: Time Resolution Validation & Response Echoing

| Endpoint / Component | Field / Parameter | Direction | Type | Default | Reason / Description |
|---|---|:---:|:---:|:---:|---|
| `/api/v1/optimize`, `/api/v1/what-if` | `time_resolution` | Response | `int` | `1` | Echoes the active time resolution multiplier (1 for 1-minute units, 2 for 30-second units). |
| `/api/v1/optimize`, `/api/v1/what-if` | `time_resolution` validation | Validation | Request Rule | N/A | Validates that every track section running time, minimum headway, junction clearance, and timetable dwell in the underlying dataset is an exact integer multiple of `1/time_resolution`. If any value is not a multiple, returns HTTP 400 Bad Request with a clear message (e.g., resolutions 3 and 61 are rejected due to 3.5 min and 1.5 min running times). |



