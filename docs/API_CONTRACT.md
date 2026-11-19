# Railway Traffic Optimizer - API Contract Specification

This document defines the REST and Server-Sent Events (SSE) API contract exposed by the FastAPI backend (`backend/app/api.py`, `backend/app/main.py`).

Base URL: `http://localhost:8000` (or configured `API_HOST:API_PORT`)  
OpenAPI Documentation: `http://localhost:8000/docs`

---

## 1. Security & Authentication Model

> **Plain Security Notice:**
> The API currently operates without authentication, session cookies, or Role-Based Access Control (RBAC). It is designed to be hosted within an isolated operations network or local controller workstation.
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

## 2. System Endpoints

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

### 2.2 Health Check
* **`GET /api/v1/health`**
* **Response `200 OK`**:
  ```json
  {
    "status": "healthy",
    "timestamp": "2026-11-18T19:30:00Z",
    "environment": "production",
    "data_loaded": true,
    "active_services": 40,
    "excluded_services": 7
  }
  ```

---

## 3. Network Topology & Service Provenance

### 3.1 Network Topology & Service Registry
* **`GET /api/v1/network`**
* Returns physical railway topology and service directory with active provenance flags.
* **Response `200 OK`**:
  ```json
  {
    "stations": [
      {
        "id": "MAS",
        "name": "Chennai Central",
        "corridor": "MAINLINE",
        "platform_count": 2,
        "is_junction": true
      }
    ],
    "tracks": [...],
    "corridors": [...],
    "switches": [...],
    "services": [
      {
        "id": "SRV_12607_01",
        "train_number": "12607",
        "name": "Lalbagh Express",
        "priority": "HIGH",
        "corridor": "MAINLINE",
        "active": true,
        "exclusion_reason": null
      },
      {
        "id": "SRV_40143_01",
        "train_number": "40143",
        "name": "Tambaram Local",
        "priority": "NORMAL",
        "corridor": "SUBURBAN",
        "active": false,
        "exclusion_reason": "No published timetable evidence"
      }
    ],
    "active_services_count": 40,
    "excluded_services_count": 7
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
    "start_minute": 360,
    "end_minute": 540,
    "step_size_minutes": 1.0
  }
  ```
* **Response `200 OK`**: Contains array of simulated snapshots, dynamic occupancies, conflict lists, and aggregate delays.

### 4.2 Timetable Optimization
* **`POST /api/v1/optimize`**
* Formulates and solves a CP-SAT constraint programming model over active services.
* **Request Body**:
  ```json
  {
    "service_ids": ["SRV_12607_01", "SRV_12609_01"],
    "time_window_start": 360,
    "time_window_end": 540,
    "solver_timeout_seconds": 10.0
  }
  ```
* **Response `200 OK`**: Returns optimized timetable shifts, precedence ordering, conflict resolutions, and solver stats.

### 4.3 What-If Disruption Rescheduling
* **`POST /api/v1/what-if`**
* Reschedules trains under simulated disruptions (track blockages, speed limits, delays).
* **Request Body**:
  ```json
  {
    "scenario_name": "Perambur Down Block",
    "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"],
    "blocked_sections": ["PER_PCW_SUBURBAN_DOWN", "PER_PCW_MAIN_DOWN"],
    "speed_restrictions": {},
    "initial_delays": {}
  }
  ```
* **Response `200 OK`**:
  - If feasible:
    ```json
    {
      "scenario_name": "Perambur Down Block",
      "solution_available": true,
      "solver_status": "OPTIMAL",
      "baseline_delay_minutes": 114.0,
      "optimized_delay_minutes": 42.0,
      "net_delay_savings_minutes": 72.0,
      "adjusted_timetables": [...],
      "recommendations": [...]
    }
    ```
  - If infeasible:
    ```json
    {
      "scenario_name": "Perambur Down Block",
      "solution_available": false,
      "solver_status": "INFEASIBLE",
      "baseline_delay_minutes": 114.0,
      "optimized_delay_minutes": null,
      "net_delay_savings_minutes": null,
      "adjusted_timetables": {},
      "recommendations": [
        "EMERGENCY: Infrastructure capacity exhausted. Hold departures and verify alternate routing."
      ]
    }
    ```

---

## 5. Live Runtime Simulation Engine & SSE Stream

### 5.1 Authoritative Simulation State
* **`GET /api/v1/simulation/state`**
* Returns current playback minute, playing state, active train coordinates, and current occupancies.

### 5.2 Simulation Control
* **`POST /api/v1/simulation/control`**
* **Request Body**:
  ```json
  {
    "is_playing": true,
    "playback_speed": 2.0,
    "target_minute": 420.0,
    "step_size": 1.0
  }
  ```

### 5.3 Simulation Reset
* **`POST /api/v1/simulation/reset`**
* Restores simulation state and clock back to origin (`start_minute = 360.0`).

### 5.4 Live SSE Stream
* **`GET /api/v1/simulation/stream`**
* Content-Type: `text/event-stream`
* Emits live events periodically while simulation is playing:
  ```
  event: simulation_step
  data: {"current_minute": 361.0, "is_playing": true, "playback_speed": 1.0, "trains": [...], "conflicts": [...]}
  ```

---

## 6. Disruption Events & Re-Optimization Proposals

### 6.1 List Disruption Events
* **`GET /api/v1/simulation/events`**
* Returns list of injected disruptions (`TrackBlockageEvent`, `SpeedRestrictionEvent`).

### 6.2 Inject Disruption Event
* **`POST /api/v1/simulation/events`**
* **Request Body**:
  ```json
  {
    "event_type": "TRACK_BLOCKAGE",
    "track_section_id": "PER_PCW_MAIN_DOWN",
    "start_minute": 380.0,
    "end_minute": 440.0,
    "severity": "CRITICAL",
    "description": "Signal cable fault"
  }
  ```

### 6.3 Remove Disruption Event
* **`DELETE /api/v1/simulation/events/{event_id}`**

### 6.4 Trigger Re-Optimization Proposal
* **`POST /api/v1/simulation/reoptimize`**
* Runs CP-SAT solver against the current state and active disruptions to generate a candidate dispatch proposal.
* Returns `ReoptimizationProposal` object with `proposal_id`, baseline delay, proposed delay, affected trains, and adjustments.

### 6.5 Accept / Reject Re-Optimization Proposal
* **`POST /api/v1/simulation/proposals/{proposal_id}/accept`**: Applies the proposal's adjusted timetable to the live authoritative simulation.
* **`POST /api/v1/simulation/proposals/{proposal_id}/reject`**: Marks proposal as rejected and leaves timetable unaltered.
