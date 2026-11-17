"""
tests/test_api.py
~~~~~~~~~~~~~~~~~
Unit and Integration Test Suite for Phase 20 Operational FastAPI Endpoints.

Tests:
1. Health & Diagnostics: GET /api/v1/health
2. Network Topology & Catalogue: GET /api/v1/network
3. Dynamic Movement Simulation: POST /api/v1/simulate
4. CP-SAT Timetable Optimization: POST /api/v1/optimize
5. What-If Scenario Evaluation: POST /api/v1/what-if
6. Invalid request validations & HTTP 400/422 status codes
7. Determinism & repeatability across duplicate API calls
8. Clear architectural separation of Published Ref, FIFO Baseline, Optimized Schedule, and Dynamic State
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import (
    HealthResponse,
    NetworkResponse,
    OptimizeResponse,
    SimulateResponse,
    WhatIfResponse,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Root & Health Endpoint Tests
# ---------------------------------------------------------------------------

def test_root_endpoint():
    """Verify root / info endpoint returns service metadata and endpoints."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "endpoints" in data
    assert data["endpoints"]["health"] == "/api/v1/health"
    assert data["endpoints"]["what_if"] == "/api/v1/what-if"


def test_get_health_endpoint():
    """Verify GET /api/v1/health returns 200, valid schema, and healthy network status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    # Validate with Pydantic schema
    validated = HealthResponse(**data)
    assert validated.status == "healthy"
    assert validated.version == "1.0.0"
    assert validated.network_status["datasets_intact"] is True
    assert validated.network_status["loaded_stations"] == 30
    assert validated.network_status["loaded_junctions"] == 7
    assert validated.network_status["loaded_routes"] == 24
    assert validated.network_status["loaded_services"] == 47
    assert validated.network_status["loaded_trains"] == 51


# ---------------------------------------------------------------------------
# 2. Network Topology & Catalogue Tests
# ---------------------------------------------------------------------------

def test_get_network_endpoint():
    """Verify GET /api/v1/network returns all stations, junctions, routes, and services."""
    response = client.get("/api/v1/network")
    assert response.status_code == 200
    data = response.json()

    validated = NetworkResponse(**data)
    assert validated.station_count == 30
    assert validated.junction_count == 7
    assert validated.route_count == 24
    assert validated.service_count == 47
    assert validated.train_count == 51
    assert validated.track_section_count > 0

    # Verify presence of key stations & junctions
    station_ids = {s.id for s in validated.stations}
    assert "MAS" in station_ids
    assert "AJJ" in station_ids
    assert "MSB" in station_ids

    junction_ids = {j.id for jct in [validated.junctions] for j in jct}
    assert any("BBQ" in j.id for j in validated.junctions)
    assert any("VJM" in j.id for j in validated.junctions)

    # Verify service structure
    svc_12607 = next((s for s in validated.services if s.id == "SRV_12607_01"), None)
    assert svc_12607 is not None
    assert svc_12607.origin == "MAS"
    assert svc_12607.destination == "AJJ"
    assert svc_12607.train_id == "TR_12607"
    assert "Lalbagh" in svc_12607.train_name


# ---------------------------------------------------------------------------
# 3. Dynamic Simulation Endpoint Tests
# ---------------------------------------------------------------------------

def test_post_simulate_default():
    """Verify POST /api/v1/simulate runs simulation for timetable-backed services."""
    payload = {"service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]}
    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = SimulateResponse(**data)
    assert validated.total_services_simulated == 4
    assert len(validated.train_positions) == 4
    assert validated.total_network_delay_minutes >= 0.0
    assert isinstance(validated.active_occupancies, list)
    assert isinstance(validated.detected_conflicts, list)


def test_post_simulate_with_injected_delay():
    """Verify POST /api/v1/simulate correctly applies departure delays."""
    payload = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "departure_delays": {"SRV_12607_01": 25.0},
        "start_time": "06:00",
    }
    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = SimulateResponse(**data)
    assert validated.total_services_simulated == 2
    assert validated.delayed_services_count >= 1
    assert validated.total_network_delay_minutes >= 25.0

    pos_12607 = next(p for p in validated.train_positions if p.service_id == "SRV_12607_01")
    assert pos_12607.delay_minutes >= 25.0


def test_post_simulate_invalid_service_id():
    """Verify POST /api/v1/simulate returns 400 for unknown service ID."""
    payload = {
        "service_ids": ["SRV_INVALID_99999"],
    }
    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 400
    assert "SRV_INVALID_99999" in response.json()["detail"]


def test_post_simulate_invalid_departure_delay_key():
    """Verify POST /api/v1/simulate returns 400 for unknown departure delay key."""
    payload = {
        "departure_delays": {"SRV_NONEXISTENT": 15.0},
    }
    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 400
    assert "SRV_NONEXISTENT" in response.json()["detail"]


def test_post_simulate_stepped_time():
    """Verify POST /api/v1/simulate with current_time advances trains only up to given clock."""
    payload = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "start_time": "06:00",
        "current_time": "06:30",
    }
    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = SimulateResponse(**data)
    assert validated.simulation_time_str == "06:30"
    assert validated.total_services_simulated == 2
    assert len(validated.train_positions) == 2


def test_post_simulate_time_limit_minutes():
    """Verify POST /api/v1/simulate with time_limit_minutes advances clock accordingly."""
    payload = {
        "service_ids": ["SRV_12607_01"],
        "time_limit_minutes": 380.0,
    }
    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = SimulateResponse(**data)
    assert validated.simulation_time_str == "06:20"


# ---------------------------------------------------------------------------
# 4. CP-SAT Timetable Optimization Endpoint Tests
# ---------------------------------------------------------------------------

def test_post_optimize_default():
    """Verify POST /api/v1/optimize produces an optimal/feasible schedule."""
    payload = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = OptimizeResponse(**data)
    assert validated.solver_status in ("OPTIMAL", "FEASIBLE")
    assert validated.computation_time_seconds >= 0.0
    assert "SRV_12607_01" in validated.adjusted_timetables
    assert len(validated.adjusted_timetables["SRV_12607_01"]) > 0


def test_post_optimize_delay_savings():
    """Verify POST /api/v1/optimize resolves conflicts and reports baseline vs optimized delay."""
    payload = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"],
        "departure_delays": {"SRV_12607_01": 20.0, "SRV_12609_01": 15.0},
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = OptimizeResponse(**data)
    assert validated.solver_status in ("OPTIMAL", "FEASIBLE")
    assert validated.feasible_baseline_delay_minutes >= 0.0
    assert validated.optimized_total_delay_minutes >= 0.0
    assert validated.unresolved_conflicts_count == 0


def test_post_optimize_invalid_service():
    """Verify POST /api/v1/optimize returns 400 when an invalid service is passed."""
    payload = {
        "service_ids": ["SRV_UNKNOWN_SVC"],
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 400
    assert "SRV_UNKNOWN_SVC" in response.json()["detail"]


# ---------------------------------------------------------------------------
# 5. What-If Disruption Scenario Endpoint Tests
# ---------------------------------------------------------------------------

def test_post_what_if_disruption_scenario():
    """Verify POST /api/v1/what-if runs full end-to-end pipeline with decision support."""
    payload = {
        "scenario_id": "SCEN_WHAT_IF_TEST",
        "scenario_name": "Test Express Delay Scenario",
        "description": "Simulating a 25 min late departure of Lalbagh Express.",
        "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"],
        "departure_delays": {"SRV_12607_01": 25.0},
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = WhatIfResponse(**data)
    assert validated.scenario_id == "SCEN_WHAT_IF_TEST"
    assert validated.scenario_name == "Test Express Delay Scenario"
    assert validated.operational_severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert validated.active_services_count == 4
    assert validated.solver_status in ("OPTIMAL", "FEASIBLE")
    assert validated.deterministic_hash != ""

    # Controller summary
    assert "status" in validated.controller_summary or "solver_status" in validated.controller_summary
    assert "top_recommendation" in validated.controller_summary

    # Baseline comparison structure
    assert "feasible_baseline_delay_minutes" in validated.baseline_comparison
    assert "optimized_delay_minutes" in validated.baseline_comparison


def test_post_what_if_speed_restriction():
    """Verify POST /api/v1/what-if handles speed restrictions on track sections."""
    payload = {
        "scenario_id": "SCEN_SPEED_RESTRICT",
        "scenario_name": "Track Speed Restriction",
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "speed_restrictions": {"MAS_BBQ_THROAT_SEGMENT_DOWN": 10.0},
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = WhatIfResponse(**data)
    assert validated.solver_status in ("OPTIMAL", "FEASIBLE")
    assert validated.active_services_count == 2


def test_post_what_if_invalid_service():
    """Verify POST /api/v1/what-if returns 400 for unknown service ID."""
    payload = {
        "service_ids": ["SRV_FAKE_ID"],
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 400
    assert "SRV_FAKE_ID" in response.json()["detail"]


def test_what_if_deterministic_repeatability():
    """Verify consecutive calls with identical inputs produce identical deterministic hashes."""
    payload = {
        "scenario_id": "SCEN_DETERMINISTIC_CHECK",
        "scenario_name": "Deterministic Repeatability Test",
        "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_43411_01"],
        "departure_delays": {"SRV_12607_01": 20.0},
    }
    res1 = client.post("/api/v1/what-if", json=payload)
    res2 = client.post("/api/v1/what-if", json=payload)

    assert res1.status_code == 200
    assert res2.status_code == 200

    data1 = res1.json()
    data2 = res2.json()

    assert data1["deterministic_hash"] == data2["deterministic_hash"]
    assert data1["total_baseline_delay_minutes"] == data2["total_baseline_delay_minutes"]
    assert data1["total_optimized_delay_minutes"] == data2["total_optimized_delay_minutes"]
    assert len(data1["recommendations"]) == len(data2["recommendations"])


def test_post_what_if_enroute_dwell_delay():
    """Verify POST /api/v1/what-if handles intermediate station dwell delay injections."""
    payload = {
        "scenario_id": "SCEN_ENROUTE_DWELL",
        "scenario_name": "Perambur Dwell Exceedance",
        "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_43411_01"],
        "station_delays": {"SRV_12607_01": {"PER": 15.0}},
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = WhatIfResponse(**data)
    assert validated.solver_status in ("OPTIMAL", "FEASIBLE")
    assert validated.active_services_count == 3


def test_post_what_if_blocked_section():
    """Verify POST /api/v1/what-if handles blocked track section scenarios."""
    payload = {
        "scenario_id": "SCEN_BLOCKED_SECTION",
        "scenario_name": "Throat Track Blockage",
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "departure_delays": {"SRV_12607_01": 10.0},
        "blocked_sections": ["MAS_BBQ_THROAT_SEGMENT_DOWN"],
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = WhatIfResponse(**data)
    assert validated.solver_status in ("OPTIMAL", "FEASIBLE", "BASELINE", "INFEASIBLE")


def test_post_what_if_junction_contention():
    """Verify POST /api/v1/what-if evaluates multi-train junction contention."""
    payload = {
        "scenario_id": "SCEN_JCT_CONTENTION",
        "scenario_name": "BBQ Dual Express Contention",
        "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"],
        "departure_delays": {"SRV_12607_01": 20.0, "SRV_12609_01": 15.0},
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = WhatIfResponse(**data)
    assert validated.solver_status in ("OPTIMAL", "FEASIBLE")
    assert validated.net_delay_savings_minutes >= 0.0


def test_post_what_if_compound_disruption():
    """Verify POST /api/v1/what-if handles severe compound disruptions (delays + TSR + dwell)."""
    payload = {
        "scenario_id": "SCEN_COMPOUND_DISRUPTION",
        "scenario_name": "Compound Peak-Hour Disruption",
        "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"],
        "departure_delays": {"SRV_12607_01": 35.0, "SRV_12609_01": 25.0},
        "station_delays": {"SRV_12607_01": {"PER": 10.0}},
        "speed_restrictions": {"MAS_BBQ_THROAT_SEGMENT_DOWN": 12.0},
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = WhatIfResponse(**data)
    assert validated.solver_status in ("OPTIMAL", "FEASIBLE")
    assert validated.total_baseline_delay_minutes > 0.0
    assert len(validated.service_delay_impacts) == 4


def test_malformed_request_payload_422():
    """Verify sending invalid data types produces HTTP 422 Unprocessable Entity."""
    # Passing a string instead of a float/number for departure delay
    payload = {
        "departure_delays": {"SRV_12607_01": "not_a_valid_number"},
    }
    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 422
