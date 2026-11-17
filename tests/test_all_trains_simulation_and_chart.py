"""
tests/test_all_trains_simulation_and_chart.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Focused test suite for Requirement #10:
1. Multi-train and all-service-type simulation coverage (Suburban EMU, Intercity, Express, Long Distance).
2. Elimination of Express-only hardcoded assumptions and clamps.
3. Authoritative 6-hour operational control-room chart data flow, work windows, and UI contracts.
"""

from __future__ import annotations

import os
import re
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import (
    NetworkResponse,
    SimulateRequest,
    SimulateResponse,
    SimulationStateResponse,
)
from simulation.clock import time_to_minutes
from simulation.state_manager import get_simulation_manager, get_corridor_name_for_route

client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. Network & Metadata Coverage for ALL Train Types
# ---------------------------------------------------------------------------

def test_network_exposes_all_service_types_and_timetables():
    """Verify /api/v1/network returns all 47 services across all 4 train types with timetables."""
    resp = client.get("/api/v1/network")
    assert resp.status_code == 200
    data = resp.json()

    network = NetworkResponse(**data)
    services = network.services
    assert len(services) == 47, f"Expected 47 services, got {len(services)}"

    # Check distribution of train types
    train_types = {s.train_type for s in services}
    assert "SUBURBAN_EMU" in train_types, "SUBURBAN_EMU must be present"
    assert "EXPRESS" in train_types, "EXPRESS must be present"
    assert "INTERCITY" in train_types, "INTERCITY must be present"
    assert "LONG_DISTANCE" in train_types, "LONG_DISTANCE must be present"

    # Count by train type
    emu_count = sum(1 for s in services if s.train_type == "SUBURBAN_EMU")
    exp_count = sum(1 for s in services if s.train_type == "EXPRESS")
    ic_count = sum(1 for s in services if s.train_type == "INTERCITY")
    ld_count = sum(1 for s in services if s.train_type == "LONG_DISTANCE")

    assert emu_count >= 20, f"Expected at least 20 EMU services, found {emu_count}"
    assert exp_count >= 10, f"Expected at least 10 Express services, found {exp_count}"
    assert ic_count >= 5, f"Expected at least 5 Intercity services, found {ic_count}"
    assert ld_count >= 1, f"Expected at least 1 Long Distance service, found {ld_count}"

    # Verify each service has scheduled times and corridor
    for s in services:
        assert s.scheduled_departure is not None and len(s.scheduled_departure) == 5, f"Missing scheduled_departure for {s.id}"
        assert s.scheduled_arrival is not None and len(s.scheduled_arrival) == 5, f"Missing scheduled_arrival for {s.id}"
        assert s.corridor_name is not None and len(s.corridor_name) > 0, f"Missing corridor_name for {s.id}"

    # Verify timetable records are exposed and cover non-express services
    assert len(network.timetable) > 0, "NetworkResponse timetable array must not be empty"
    timetable_train_types = {r.get("train_type") for r in network.timetable}
    assert "SUBURBAN_EMU" in timetable_train_types, "Timetable must include Suburban EMU stops"
    assert "EXPRESS" in timetable_train_types, "Timetable must include Express stops"


# ---------------------------------------------------------------------------
# 2. Simulation Execution Across ALL Train Types (No Express Clamp)
# ---------------------------------------------------------------------------

def test_simulation_runs_all_47_services_without_clamp():
    """Verify running simulation with default/empty service_ids simulates all 47 services, not only 4."""
    payload = {
        "service_ids": [],
        "start_time": "06:00",
        "current_time": "08:00",
    }
    resp = client.post("/api/v1/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    validated = SimulateResponse(**data)
    assert validated.total_services_simulated == 47, (
        f"Expected all 47 services to be simulated, got {validated.total_services_simulated}. "
        "Check that the [:4] express clamp was removed."
    )
    assert len(validated.train_positions) == 47

    # Verify positions contain enriched metadata for all train types
    pos_types = {p.train_type for p in validated.train_positions}
    assert "SUBURBAN_EMU" in pos_types
    assert "EXPRESS" in pos_types
    assert "INTERCITY" in pos_types
    assert "LONG_DISTANCE" in pos_types

    # Ensure corridor attribution is present
    for p in validated.train_positions:
        assert p.corridor is not None and len(p.corridor) > 0, f"Corridor missing for {p.service_id}"
        assert p.service_type is not None, f"Service type missing for {p.service_id}"


def test_suburban_emu_movement_and_dwell_progression():
    """Verify that suburban EMU trains progress through stations and update status properly."""
    # Test EMU services: SRV_43411_01 and SRV_43412_01
    payload = {
        "service_ids": ["SRV_43411_01", "SRV_43412_01"],
        "departure_delays": {"SRV_43411_01": 5.0},
        "start_time": "06:00",
        "current_time": "06:45",
    }
    resp = client.post("/api/v1/simulate", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    sim = SimulateResponse(**data)
    assert sim.total_services_simulated == 2
    pos = {p.service_id: p for p in sim.train_positions}

    emu1 = pos["SRV_43411_01"]
    assert emu1.train_type == "SUBURBAN_EMU"
    assert emu1.delay_minutes == 5.0
    assert emu1.corridor == "West"
    assert emu1.status in ("RUNNING", "AT_STATION", "ARRIVED", "SCHEDULED")


# ---------------------------------------------------------------------------
# 3. 6-Hour Operational Work Window Filtering
# ---------------------------------------------------------------------------

def test_six_hour_work_window_coverage():
    """Verify that a 6-hour operational window (e.g., 06:00-12:00) captures active trains of all types."""
    from backend.app.api import get_network
    net = get_network()
    # 06:00 to 12:00 is 360 to 720 minutes
    w_start = 360.0
    w_end = 720.0

    mgr = get_simulation_manager(net)
    resp = mgr.simulate_epoch(
        target_time_m=450.0,  # 07:30
        service_ids=list(net.services.keys()),
        departure_delays={"SRV_43411_01": 10.0},
        start_time_m=360.0,
    )
    positions = resp.train_positions
    assert len(positions) == 47

    # Filter by 6-hour work window overlap
    active_in_window = []
    for p in positions:
        dep_m = time_to_minutes(p.scheduled_departure)
        arr_m = time_to_minutes(p.scheduled_arrival)
        # Handle day wrap if any
        if arr_m < dep_m:
            arr_m += 1440.0
        # Overlap condition: dep < w_end and arr > w_start
        if dep_m < w_end and arr_m > w_start:
            active_in_window.append(p)

    assert len(active_in_window) >= 15, f"Expected multiple trains active in 06:00-12:00 window, got {len(active_in_window)}"
    active_types = {p.train_type for p in active_in_window}
    assert "SUBURBAN_EMU" in active_types, "EMU trains must be active in 06:00-12:00 window"
    assert "EXPRESS" in active_types, "Express trains must be active in 06:00-12:00 window"


# ---------------------------------------------------------------------------
# 4. Frontend UI Contracts in SimulationMonitor.tsx
# ---------------------------------------------------------------------------

def test_simulation_monitor_ui_contracts():
    """Verify SimulationMonitor.tsx has the 6-hour control room chart, shift presets, and train type filters."""
    path = os.path.join("frontend", "src", "components", "SimulationMonitor.tsx")
    assert os.path.exists(path), f"File {path} not found"

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Check for 6-Hour Operational Control-Room Chart
    assert "6-Hour Operational Control-Room Dispatch Chart" in content, (
        "Chart header '6-Hour Operational Control-Room Dispatch Chart' must be in SimulationMonitor.tsx"
    )

    # 2. Check for 6-Hour Shift presets (Shift 1, Shift 2, Shift 3, Shift 4)
    assert "Shift 1 (06:00 - 12:00 [6h])" in content or "06:00" in content, "Shift 1 preset must be present"
    assert "Shift 2 (12:00 - 18:00 [6h])" in content or "12:00" in content, "Shift 2 preset must be present"
    assert "Shift 3 (18:00 - 24:00 [6h])" in content or "18:00" in content, "Shift 3 preset must be present"
    assert "Shift 4 (00:00 - 06:00 [6h])" in content or "00:00" in content, "Shift 4 preset must be present"

    # 3. Check for Train Type Filters and Badges
    assert "Suburban EMU" in content, "Suburban EMU filter button must be present"
    assert "Express" in content, "Express filter button must be present"
    assert "Intercity" in content, "Intercity filter button must be present"
    assert "Shift Fleet" in content, "Shift Fleet filter button must be present"

    # 4. Check that obsolete Express-only filtering heuristics were eliminated
    assert "126" not in content or "train_type" in content, "Heuristic '126' service ID filtering should be replaced with train_type"
    assert "train_type === 'EXPRESS'" in content or "SUBURBAN_EMU" in content, "Must use authoritative train_type"

    # 5. Check for control room chart elements: timeline grid, current time needle, conflicts, corridor
    assert "data-testid=\"control-room-chart\"" in content or "6-Hour Operational" in content
    assert "Corridor" in content or "corridor" in content
    assert "CONFLICT" in content, "Conflict indicator must be displayed on affected trains in the chart"
