"""
tests/test_realtime_simulation_state.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Verification suite for Section 1 real-time simulation and state behaviors:
1. Multi-service simultaneous injection and concurrent execution.
2. Authoritative backend state persistence across browser refresh / reloads.
3. Automatic IST (Asia/Kolkata, UTC+05:30) synchronization.
4. Simulation advance during idle windows when no train is active in real time.
5. Immediate state propagation of controller disruptions.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import (
    HealthResponse,
    SimulationControlRequest,
    SimulationStateResponse,
    SimulateRequest,
    SimulateResponse,
)
from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.state_manager import (
    IST_TIMEZONE,
    get_ist_now,
    get_ist_time_str,
    get_simulation_manager,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Multi-Service Simultaneous Injection Test
# ---------------------------------------------------------------------------

def test_multi_service_simultaneous_injection():
    """Verify injecting delays for multiple selected services runs simultaneously and deterministically."""
    selected = ["SRV_43501_01", "SRV_12675_01", "SRV_16057_01"]
    delays = {
        "SRV_43501_01": 15.0,
        "SRV_12675_01": 20.0,
    }

    payload = {
        "service_ids": selected,
        "departure_delays": delays,
        "start_time": "06:00",
        "current_time": "06:35",
    }

    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = SimulateResponse(**data)
    assert validated.total_services_simulated == 3
    assert len(validated.train_positions) == 3
    assert validated.delayed_services_count == 2
    assert validated.total_network_delay_minutes >= 35.0

    pos_map = {p.service_id: p for p in validated.train_positions}
    assert pos_map["SRV_43501_01"].delay_minutes == 15.0
    assert pos_map["SRV_12675_01"].delay_minutes == 20.0
    assert pos_map["SRV_16057_01"].delay_minutes == 0.0


# ---------------------------------------------------------------------------
# 2. Authoritative Backend State Persistence Test
# ---------------------------------------------------------------------------

def test_authoritative_backend_state_persistence():
    """Verify backend simulation state is authoritative and persists across requests."""
    # 1. Update state via control endpoint
    control_payload = {
        "current_minute": 395.0,
        "start_minute": 360.0,
        "end_minute": 540.0,
        "is_playing": True,
        "playback_speed": 2,
        "service_ids": ["SRV_43501_01", "SRV_12675_01"],
        "departure_delays": {"SRV_43501_01": 12.0},
    }

    ctrl_resp = client.post("/api/v1/simulation/control", json=control_payload)
    assert ctrl_resp.status_code == 200
    ctrl_data = ctrl_resp.json()
    assert ctrl_data["current_minute"] == 395.0
    assert ctrl_data["is_playing"] is True
    assert ctrl_data["playback_speed"] == 2
    assert "SRV_43501_01" in ctrl_data["selected_service_ids"]
    assert ctrl_data["departure_delays"]["SRV_43501_01"] == 12.0

    # 2. Retrieve state via GET endpoint (simulating browser refresh / new session)
    get_resp = client.get("/api/v1/simulation/state")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    validated = SimulationStateResponse(**get_data)

    assert validated.current_minute == 395.0
    assert validated.current_time_str == "06:35"
    assert validated.is_playing is True
    assert validated.playback_speed == 2
    assert validated.selected_service_ids == ["SRV_43501_01", "SRV_12675_01"]
    assert validated.departure_delays == {"SRV_43501_01": 12.0}
    assert validated.snapshot.total_services_simulated == 2


# ---------------------------------------------------------------------------
# 3. Automatic IST Operational Clock Synchronization Test
# ---------------------------------------------------------------------------

def test_automatic_ist_synchronization():
    """Verify health and state endpoints return timestamps synchronized with Asia/Kolkata (UTC+05:30)."""
    # Verify local IST calculation
    ist_now = get_ist_now()
    expected_offset = timedelta(hours=5, minutes=30)
    assert ist_now.utcoffset() == expected_offset

    # Check /health endpoint
    h_resp = client.get("/api/v1/health")
    assert h_resp.status_code == 200
    h_data = h_resp.json()
    assert h_data["timezone"] == "Asia/Kolkata (IST)"
    assert "ist_time_str" in h_data
    assert len(h_data["ist_time_str"]) == 8  # "HH:MM:SS"

    # Check /simulation/state endpoint
    s_resp = client.get("/api/v1/simulation/state")
    assert s_resp.status_code == 200
    s_data = s_resp.json()
    assert s_data["timezone"] == "Asia/Kolkata (IST)"
    assert "ist_time_str" in s_data


# ---------------------------------------------------------------------------
# 4. Simulation Advance with No Active Trains Test
# ---------------------------------------------------------------------------

def test_simulation_advance_when_no_trains_active():
    """Verify simulation executes and advances smoothly even when 0 trains are active at the current epoch."""
    # Query an idle early-morning epoch (04:30 = 270 min) where morning fleet has not yet started
    payload = {
        "service_ids": ["SRV_12675_01", "SRV_16057_01"],  # Departures at 06:15 and 06:30
        "start_time": "04:00",
        "current_time": "04:30",
        "time_limit_minutes": 270.0,
    }

    response = client.post("/api/v1/simulate", json=payload)
    assert response.status_code == 200
    data = response.json()

    validated = SimulateResponse(**data)
    assert validated.simulation_time_str == "04:30"
    assert validated.total_services_simulated == 2
    assert validated.active_occupancies_count == 0
    assert len(validated.detected_conflicts) == 0

    # All services must be in SCHEDULED status awaiting origin departure
    for pos in validated.train_positions:
        assert pos.status == "SCHEDULED"
        assert pos.current_track_section is None


# ---------------------------------------------------------------------------
# 5. Immediate State Propagation Test
# ---------------------------------------------------------------------------

def test_immediate_state_propagation():
    """Verify controller changes immediately reflect in the updated simulation response without extra calls."""
    # Inject delay for Lalbagh Express
    payload = {
        "service_ids": ["SRV_12607_01"],
        "departure_delays": {"SRV_12607_01": 25.0},
        "start_time": "15:00",
        "current_time": "15:30",
    }

    resp = client.post("/api/v1/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    pos = data["train_positions"][0]
    assert pos["service_id"] == "SRV_12607_01"
    assert pos["delay_minutes"] == 25.0
    assert data["total_network_delay_minutes"] == 25.0
    assert data["delayed_services_count"] == 1
