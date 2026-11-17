"""
tests/test_timetable_comparison_e2e.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
End-to-end validation test suite for Timetable Comparator Requirement #7.

Validates:
1. Multi-service What-If / Optimization scenario with trains across multiple corridors.
2. Real values for Tier 1 Published, Tier 2 Feasible FIFO, and Tier 3 CP-SAT at relevant stops.
3. Accurate CP-SAT rescheduling, delay recovery, and platform allocation changes.
4. Unaffected / out-of-corridor stops properly tagged as is_corridor_relevant=False and change_status="N/A".
5. Multi-service representation (multiple trains from multiple corridors).
6. Corridor-wise and section-wise filtering correctness.
7. Full end-to-end propagation from /api/v1/what-if and /api/v1/optimize into 3-tier comparative structures.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from optimization.scenarios import Scenario, ScenarioRunner
from simulation.network import Network

client = TestClient(app)


def test_e2e_multi_corridor_what_if_scenario_validation():
    """Execute realistic multi-corridor What-If scenario and verify all Requirement #7 criteria."""
    # 1. Define multi-service What-If request across West and South corridors
    # SRV_12607_01 (West) has 25 min departure delay
    # SRV_12609_01 (West) is following service
    # SRV_40001_01 (South) is an unaffected service on the South corridor
    payload = {
        "scenario_id": "SCEN_E2E_MULTI_CORRIDOR",
        "scenario_name": "Multi-Corridor Conflict & Out-of-Scope Isolation",
        "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_40001_01"],
        "departure_delays": {
            "SRV_12607_01": 25.0,
        },
    }

    resp = client.post("/api/v1/what-if", json=payload)
    assert resp.status_code == 200, f"What-If failed: {resp.text}"
    data = resp.json()

    # Verify response structure
    assert "baseline_comparison" in data
    comp = data["baseline_comparison"]
    assert "three_tier_timetable" in comp
    entries = comp["three_tier_timetable"]
    assert len(entries) > 0

    # 2. Verify multiple trains appear across different corridors
    services_found = set(e["service_id"] for e in entries)
    corridors_found = set(e["corridor_id"] for e in entries)
    assert "SRV_12607_01" in services_found
    assert "SRV_12609_01" in services_found
    assert "SRV_40001_01" in services_found
    assert len(services_found) >= 3

    assert "RT_WEST_MAS_AJJ" in corridors_found
    assert any("SOUTH" in c for c in corridors_found)
    assert len(corridors_found) >= 2

    # 3. Verify Tier 1 / 2 / 3 contain real values for relevant stops on the perturbed corridor
    west_entries = [e for e in entries if e["service_id"] == "SRV_12607_01"]
    mas_stop = next((e for e in west_entries if e["station_id"] == "MAS"), None)
    assert mas_stop is not None
    assert mas_stop["is_corridor_relevant"] is True
    # Tier 1 Published
    assert mas_stop["published_departure"] is not None
    assert mas_stop["published_departure_str"] is not None
    assert mas_stop["published_platform"] is not None
    assert mas_stop["published_delay_minutes"] == 25.0
    # Tier 2 Feasible FIFO
    assert mas_stop["feasible_departure"] is not None
    assert mas_stop["feasible_departure_str"] is not None
    assert mas_stop["feasible_delay_minutes"] == 25.0
    # Tier 3 CP-SAT Optimal
    assert mas_stop["optimized_departure"] is not None
    assert mas_stop["optimized_departure_str"] is not None
    assert mas_stop["optimized_delay_minutes"] is not None
    assert mas_stop["optimized_platform"] is not None

    # 4. Verify Tier 3 reflects CP-SAT rescheduling / recovery changes
    rescheduled_or_recovered = [
        e for e in west_entries 
        if e["change_status"] in ("RESCHEDULED", "DELAY_RECOVERED", "PLATFORM_REASSIGNED")
    ]
    assert len(rescheduled_or_recovered) > 0, "Expected CP-SAT rescheduling changes on delayed corridor"

    # 5. Verify unaffected / out-of-corridor stops correctly show N/A
    south_entries = [e for e in entries if e["service_id"] == "SRV_40001_01"]
    assert len(south_entries) > 0
    for s_entry in south_entries:
        assert s_entry["is_corridor_relevant"] is False, f"Expected {s_entry['station_id']} to be out of scope"
        assert s_entry["change_status"] == "N/A"
        assert s_entry["has_rescheduling_change"] is False
        assert s_entry["delay_savings_minutes"] == 0.0
        # Tier 1 & 2 still contain real physical values at commercial stops (e.g. MSB origin, TBM destination)
        if s_entry["station_id"] in ("MSB", "TBM"):
            assert s_entry["published_departure"] is not None or s_entry["published_arrival"] is not None
            assert s_entry["feasible_departure"] is not None or s_entry["feasible_arrival"] is not None

    # 6. Verify corridor and section filtering logic
    # Filter by Corridor
    west_only = [e for e in entries if e["corridor_id"] == "RT_WEST_MAS_AJJ"]
    assert all(e["service_id"] in ("SRV_12607_01", "SRV_12609_01") for e in west_only)
    assert all("SOUTH" not in e["corridor_id"] for e in west_only)

    south_only = [e for e in entries if "SOUTH" in e["corridor_id"]]
    assert all(e["service_id"] == "SRV_40001_01" for e in south_only)

    # Filter by Section
    sections_with_stops = [e["section_id"] for e in entries if e["section_id"]]
    assert len(sections_with_stops) > 0
    sample_sec = sections_with_stops[0]
    sec_entries = [e for e in entries if e["section_id"] == sample_sec]
    assert len(sec_entries) > 0
    assert all(e["section_id"] == sample_sec for e in sec_entries)

    # 7. Verify changes propagate through /api/v1/optimize as well
    opt_resp = client.post("/api/v1/optimize", json={
        "service_ids": ["SRV_12607_01", "SRV_40001_01"],
        "departure_delays": {"SRV_12607_01": 20.0},
    })
    assert opt_resp.status_code == 200
    opt_data = opt_resp.json()
    assert "three_tier_timetable" in opt_data
    assert len(opt_data["three_tier_timetable"]) > 0

    opt_services = set(e["service_id"] for e in opt_data["three_tier_timetable"])
    assert "SRV_12607_01" in opt_services
    assert "SRV_40001_01" in opt_services
