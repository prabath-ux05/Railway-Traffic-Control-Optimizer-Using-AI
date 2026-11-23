# Railway Traffic Optimizer - API Contract Specification

This document defines the REST and Server-Sent Events (SSE) API contract exposed by the FastAPI backend (`backend/app/api.py`, `backend/app/main.py`, `backend/app/schemas.py`).

Base URL: `http://localhost:8000` (or configured `API_HOST:API_PORT`)  
OpenAPI Documentation: `http://localhost:8000/docs`

---

## 1. Security & Authentication Model

> **Plain Security Notice:**
> The API operates without authentication, session cookies, or Role-Based Access Control (RBAC). It is designed to be hosted within an isolated operations network or local controller workstation.
>
> **State-Mutating Endpoints:**
> The following endpoints mutate runtime state, alter timetables, or inject disruptions:
> - `POST   /api/v1/simulation/control`
> - `POST   /api/v1/simulation/reset`
> - `POST   /api/v1/simulation/events`
> - `DELETE /api/v1/simulation/events/{event_id}`
> - `POST   /api/v1/simulation/reoptimize`
> - `POST   /api/v1/simulation/proposals/{proposal_id}/accept`
> - `POST   /api/v1/simulation/proposals/{proposal_id}/reject`
> - `POST   /api/v1/simulate`

---

## 2. System Diagnostics Endpoints

### 2.1 Root Metadata
* **`GET /`**
* **Response `200 OK`**:
  ```json
  {
    "service": "Railway Traffic Optimization & Decision Support API",
    "version": "1.0.0",
    "status": "operational",
    "docs": "/docs",
    "endpoints": {
      "health": "/api/v1/health",
      "network": "/api/v1/network",
      "simulate": "/api/v1/simulate",
      "optimize": "/api/v1/optimize",
      "what_if": "/api/v1/what-if"
    }
  }
  ```

### 2.2 Health Check & Integrity Diagnostics
* **`GET /api/v1/health`**
* **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "version": "1.0.0",
    "ist_time": "11:00:00",
    "ist_date": "2026-11-23",
    "current_time": "11:00",
    "datasets_intact": true,
    "datasets_integrity_status": "WARNINGS",
    "integrity_warning_count": 836,
    "integrity_summary": {
      "station_record_missing_for_route_node": 749,
      "no_track_section_for_hop": 83,
      "timetable_references_unknown_station": 4
    },
    "network_status": {
      "stations_count": 30,
      "junctions_count": 7,
      "routes_count": 24,
      "services_count": 47,
      "trains_count": 51,
      "datasets_intact": true,
      "integrity_warning_count": 836,
      "integrity_summary": { ... },
      "datasets_integrity_status": "WARNINGS"
    }
  }
  ```

---

## 3. Network Topology & Service Registry

### 3.1 Network Topology & Route Node Registry
* **`GET /api/v1/network`**
* Returns physical railway topology, service directory with active provenance flags, complete 107-node registry, and SHA-256 data provenance.
* **Response `200 OK`**:
  ```json
  {
    "station_count": 30,
    "junction_count": 7,
    "route_count": 24,
    "service_count": 47,
    "active_service_count": 40,
    "excluded_service_count": 7,
    "stations": [...],
    "junctions": [...],
    "routes": [...],
    "services": [
      {
        "id": "SRV_12607_01",
        "service_id": "SRV_12607_01",
        "train_id": "12607",
        "train_name": "Lalbagh Express",
        "service_type": "EXPRESS",
        "train_type": "EXPRESS",
        "origin": "MAS",
        "destination": "SBC",
        "route_id": "ROUTE_MAS_AJJ_UP",
        "priority_class": 1,
        "delay_penalty_weight": 2.0,
        "corridor": "WEST",
        "corridor_name": "WEST",
        "scheduled_departure": "06:00",
        "scheduled_arrival": "07:30",
        "active": true,
        "exclusion_reason": null
      },
      {
        "id": "SRV_40143_01",
        "service_id": "SRV_40143_01",
        "train_id": "40143",
        "train_name": "Tambaram Local",
        "service_type": "SUBURBAN",
        "train_type": "SUBURBAN",
        "origin": "MSB",
        "destination": "TBM",
        "route_id": "ROUTE_MSB_TBM_UP",
        "priority_class": 2,
        "delay_penalty_weight": 1.0,
        "corridor": "SOUTH",
        "corridor_name": "SOUTH",
        "scheduled_departure": "06:30",
        "scheduled_arrival": "07:15",
        "active": false,
        "exclusion_reason": "No published timetable evidence"
      }
    ],
    "nodes": [
      {
        "id": "MAS",
        "name": "Chennai Central",
        "has_station_record": true,
        "node_type": "JUNCTION",
        "corridors": ["WEST"],
        "platform_count": 2
      },
      {
        "id": "AB",
        "name": "Ambur",
        "has_station_record": true,
        "node_type": "STATION",
        "corridors": ["WEST"],
        "platform_count": 0
      }
    ],
    "timetable": [...],
    "platforms": [...],
    "track_sections": [...],
    "data_provenance": {
      "sources": {
        "erail.in": 103,
        "railyatri.in": 22,
        "confirmtkt.com": 2
      },
      "total_timetable_entries": 127,
      "public_reference_entries": 127,
      "snapshot_date": null,
      "snapshot_date_provenance": "Unspecified in source dataset; null per data provenance rules",
      "file_hashes": {
        "stations.json": "...",
        "junctions.json": "..."
      }
    }
  }
  ```

---

## 4. Simulation & Optimization Workflows

### 4.1 Ad-Hoc Simulation
* **`POST /api/v1/simulate`**
* **Request Body**:
  ```json
  {
    "service_ids": ["SRV_12607_01", "SRV_12609_01"],
    "departure_delays": {"SRV_12607_01": 15.0},
    "station_delays": {},
    "speed_restrictions": {},
    "blocked_sections": [],
    "time_horizon": 1440.0,
    "step_size_minutes": 1.0
  }
  ```
* **Response `200 OK`**: Discrete-event snapshot series, occupancies, and conflict list.

### 4.2 Timetable Optimization (`/api/v1/optimize`)
* Formulates and solves a CP-SAT constraint programming model over active services.
* **Request Body (`OptimizeRequest`)**:
  ```json
  {
    "service_ids": ["SRV_12607_01", "SRV_12609_01"],
    "departure_delays": {"SRV_12607_01": 20.0},
    "station_delays": {},
    "speed_restrictions": {},
    "blocked_sections": [],
    "time_horizon": 1440.0,
    "objective_mode": "WEIGHTED",
    "apply_midnight_wrap": false,
    "time_resolution": 1
  }
  ```
* **Parameters**:
  - `objective_mode`: `"WEIGHTED"` (default multi-objective) or `"TOTAL_DELAY"` (plain delay minimization).
  - `apply_midnight_wrap`: `false` (default preserves frozen paper numbers) or `true` (resolves +1440m midnight-crossing services like `SRV_16159_01`).
  - `time_resolution`: `1` (default 1-minute units) or `2` (30-second units). Non-multiples (such as 3 and 61) are strictly rejected with HTTP 400 Bad Request.
* **Response `200 OK` (`OptimizeResponse`)**:
  ```json
  {
    "solver_status": "OPTIMAL",
    "solution_available": true,
    "computation_time_seconds": 0.082,
    "feasible_baseline_delay_minutes": 183.0,
    "optimized_total_delay_minutes": 123.0,
    "net_delay_savings_minutes": 60.0,
    "net_delay_savings_percent": 32.79,
    "fifo_weighted_objective": 549.0,
    "optimized_weighted_objective": 369.0,
    "objective_mode": "WEIGHTED",
    "unresolved_conflicts_count": 0,
    "adjusted_timetables": { ... },
    "precedence_decisions": [ ... ],
    "platform_assignments": [ ... ],
    "published_reference_delay_minutes": 20.0,
    "feasible_adjusted_timetables": { ... },
    "published_adjusted_timetables": { ... },
    "three_tier_timetable": [ ... ],
    "corridor_performance": [ ... ],
    "time_resolution": 1
  }
  ```
* **Infeasible Case (`OptimizeResponse`)**:
  ```json
  {
    "solver_status": "INFEASIBLE",
    "solution_available": false,
    "computation_time_seconds": 0.034,
    "feasible_baseline_delay_minutes": 133.0,
    "optimized_total_delay_minutes": null,
    "net_delay_savings_minutes": null,
    "net_delay_savings_percent": null,
    "fifo_weighted_objective": 399.0,
    "optimized_weighted_objective": null,
    "objective_mode": "WEIGHTED",
    "unresolved_conflicts_count": 1,
    "adjusted_timetables": {},
    "precedence_decisions": [],
    "platform_assignments": [],
    "published_reference_delay_minutes": 0.0,
    "feasible_adjusted_timetables": null,
    "published_adjusted_timetables": null,
    "three_tier_timetable": null,
    "corridor_performance": null,
    "time_resolution": 1
  }
  ```

### 4.3 What-If Disruption Rescheduling (`/api/v1/what-if`)
* Reschedules trains under simulated disruptions and provides 5-stage explainable decision support.
* **Request Body (`WhatIfRequest`)**:
  ```json
  {
    "scenario_id": "SCEN_CUSTOM",
    "scenario_name": "Custom Disruption",
    "description": "Evaluation of corridor bottleneck.",
    "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12635_01"],
    "departure_delays": {"SRV_12607_01": 20.0, "SRV_12635_01": 20.0},
    "station_delays": {},
    "speed_restrictions": {},
    "blocked_sections": [],
    "time_horizon": 1440.0,
    "objective_mode": "WEIGHTED",
    "apply_midnight_wrap": false,
    "time_resolution": 1
  }
  ```
* **Response `200 OK` (`WhatIfResponse`)**:
  ```json
  {
    "scenario_id": "SCEN_CUSTOM",
    "scenario_name": "Custom Disruption",
    "simulation_timestamp_str": "07:30",
    "operational_severity": "MODERATE",
    "active_services_count": 3,
    "delayed_services_count": 2,
    "total_baseline_delay_minutes": 221.0,
    "total_optimized_delay_minutes": 123.0,
    "net_delay_savings_minutes": 98.0,
    "net_delay_savings_percent": 44.34,
    "solver_status": "OPTIMAL",
    "solution_available": true,
    "fifo_weighted_objective": 663.0,
    "optimized_weighted_objective": 369.0,
    "objective_mode": "WEIGHTED",
    "solve_time_seconds": 0.094,
    "execution_time_seconds": 0.125,
    "deterministic_hash": "...",
    "prioritized_conflicts": [...],
    "identified_bottlenecks": [...],
    "service_delay_impacts": [...],
    "recommendations": [...],
    "baseline_comparison": { ... },
    "controller_summary": {
      "solver_status": "OPTIMAL",
      "solution_available": true,
      "operational_severity": "MODERATE",
      "net_delay_savings_minutes": 98.0,
      "recommendation_count": 3,
      "top_recommendation": "Advance SRV_12609_01 ahead of SRV_12607_01 at BBQ"
    },
    "metadata": { ... },
    "corridor_performance": [ ... ],
    "time_resolution": 1
  }
  ```
* **Infeasible Case (`WhatIfResponse`)**:
  ```json
  {
    "solver_status": "INFEASIBLE",
    "solution_available": false,
    "operational_severity": "EMERGENCY",
    "total_baseline_delay_minutes": 133.0,
    "total_optimized_delay_minutes": null,
    "net_delay_savings_minutes": null,
    "net_delay_savings_percent": null,
    "fifo_weighted_objective": 399.0,
    "optimized_weighted_objective": null,
    "recommendations": [
      {
        "category": "EMERGENCY",
        "action_type": "INFRASTRUCTURE_CLOSURE",
        "title": "No feasible schedule with the blocked resources: [...]",
        "description": "Infrastructure capacity exhausted. Hold departures and verify alternate routing."
      }
    ],
    "time_resolution": 1
  }
  ```

---

## 5. Live Runtime Simulation Engine & SSE Stream

### 5.1 Authoritative Simulation State
* **`GET /api/v1/simulation/state`**
* Returns current playback minute, playing state, active train coordinates, and current occupancies.
* Authoritative startup guarantee: Engine always starts paused (`is_playing=false`), even if state file on disk had `is_playing=true`.

### 5.2 Simulation Control
* **`POST /api/v1/simulation/control`**
* **Request Body (`SimulationControlRequest`)**:
  ```json
  {
    "action": "play",
    "speed": 60,
    "seek_minute": 380.0
  }
  ```
* **Speed Semantics**: `speed = N` means N simulation minutes advance per 60 real-world seconds (e.g. at 60x, 1 real second = 1 simulation minute). Supported speeds: `1, 2, 5, 10, 30, 60`.

### 5.3 Simulation Reset
* **`POST /api/v1/simulation/reset?clear_delays=false`**
* Restores clock to start time and optionally clears injected disruptions.

### 5.4 Live SSE Stream
* **`GET /api/v1/simulation/stream`**
* Content-Type: `text/event-stream`
* Header: `Last-Event-ID: <id>` (reconnection replay)
* Emits typed Server-Sent Events:
  - `tick`: Real-time clock progression, train positions, active occupancies, and delays.
  - `conflict_detected`: Conflict alert when train separation is violated.
  - `conflict_cleared`: Clearance notification when trains separate safely.
  - `event_injected`: Disruption injected into active simulation.
  - `event_removed`: Disruption cleared from active simulation.
  - `proposal_ready`: CP-SAT reoptimization proposal ready for controller review.
  - `heartbeat`: Stream keep-alive.

---

## 6. Disruption Events & Re-Optimization Proposals

### 6.1 List Active Events
* **`GET /api/v1/simulation/events`**
* Returns JSONL-persisted disruption events.

### 6.2 Inject Disruption Event
* **`POST /api/v1/simulation/events`**
* Injects `DEPARTURE_DELAY`, `DWELL_DELAY`, `SPEED_RESTRICTION`, or `BLOCKED_SECTION`.

### 6.3 Remove Disruption Event
* **`DELETE /api/v1/simulation/events/{event_id}`**

### 6.4 Trigger Re-Optimization Proposal
* **`POST /api/v1/simulation/reoptimize`**
* Solves CP-SAT over current runtime state, generating candidate proposal stored in `runtime/runtime_simulation_proposals.json` with status `PENDING`.

### 6.5 Accept / Reject Re-Optimization Proposal
* **`POST /api/v1/simulation/proposals/{proposal_id}/accept`**: Applies adjustments to `runtime/runtime_simulation_applied_plan.json` and updates status to `ACCEPTED`.
* **`POST /api/v1/simulation/proposals/{proposal_id}/reject`**: Rejects proposal and updates status to `REJECTED`.

---

## 7. Research Evaluation & Claims Datasets

* **`data/evaluation/comparative_analysis_results.json`**: Stored 45 experiments from accepted CICT 2026 paper ($R=1$).
* **`data/evaluation/v2/`**: Midnight-wrap corrected evaluations (`apply_midnight_wrap=True`).
* **`data/evaluation/v3/`**: Time-resolution $R=2$ evaluations (`time_resolution=2`). Eliminates 100% (19 of 19) of the negative-savings discretization artifacts present at $R=1$.
* **`data/evaluation/paper_reconstruction/`**: Contains reconstructed paper claims for Compound Disruption (183 to 123, 32.79%) and Aggressive Compound (221 to 123, 44.34%) derived from a neighborhood sweep of about 500 variants around `EXP_31_1_07A/07B`.
