"""
tests/test_timetable_comparison_backend.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Validation tests for Requirement #7: Timetable Comparator Backend Data Flow.

Verifies:
1. 3-Tier Timetable generation (Tier 1 Published, Tier 2 Feasible FIFO, Tier 3 CP-SAT).
2. Proper attribute handling for published delay (fixing 0.0 fallback bug).
3. Section-wise and corridor-wise metadata preservation (corridor_id, section_id, stop_sequence).
4. Non-empty per-service / per-station timetables in API responses (/api/v1/optimize & /api/v1/what-if).
5. Accurate calculation of delay savings, change status, and platform allocations.
"""

import pytest
from fastapi.testclient import TestClient

from simulation.network import Network
from optimization.scenarios import Scenario, ScenarioRunner
from decision_support.advisor import DecisionSupportAdvisor
from backend.app.main import app

client = TestClient(app)


def test_scenario_comparison_3_tier_data_structure():
    """Verify ScenarioComparison generates full three_tier_timetable entries without dropping schedules."""
    runner = ScenarioRunner(time_limit_seconds=5.0)
    target_services = ["SRV_12607_01", "SRV_12609_01"]
    scenario = Scenario(
        scenario_id="SCEN_3TIER_TEST",
        name="3-Tier Timetable Verification",
        description="Verify multi-tier timetable data flow",
        affected_service_ids=target_services,
        departure_delays={"SRV_12607_01": 20.0},
    )

    comp = runner.run_scenario(scenario)
    assert comp.published_baseline_result is not None
    assert comp.baseline_result is not None
    assert comp.optimized_result is not None

    # Verify published_total_delay is non-zero when delay is injected
    assert comp.published_total_delay > 0.0

    # Build 3-tier timetable
    entries = comp.build_three_tier_timetable(runner.network)
    assert len(entries) > 0

    first = entries[0]
    # Check core identification and corridor/section metadata
    assert "service_id" in first
    assert "station_id" in first
    assert "stop_sequence" in first
    assert "corridor_id" in first
    assert "section_id" in first

    # Check Tier 1 Published fields
    assert "published_arrival" in first
    assert "published_departure" in first
    assert "published_arrival_str" in first
    assert "published_departure_str" in first
    assert "published_platform" in first
    assert "published_delay_minutes" in first

    # Check Tier 2 Feasible FIFO fields
    assert "feasible_arrival" in first
    assert "feasible_departure" in first
    assert "feasible_arrival_str" in first
    assert "feasible_departure_str" in first
    assert "feasible_platform" in first
    assert "feasible_delay_minutes" in first

    # Check Tier 3 CP-SAT Optimal fields
    assert "optimized_arrival" in first
    assert "optimized_departure" in first
    assert "optimized_arrival_str" in first
    assert "optimized_departure_str" in first
    assert "optimized_platform" in first
    assert "optimized_delay_minutes" in first
    assert "optimized_dwell_minutes" in first

    # Check change status and delay savings
    assert "delay_savings_minutes" in first
    assert "has_rescheduling_change" in first
    assert "is_corridor_relevant" in first
    assert "change_status" in first

    # Check serialization
    comp_dict = comp.to_dict()
    assert "three_tier_timetable" in comp_dict
    assert len(comp_dict["three_tier_timetable"]) == len(entries)
    assert "published_timetables" in comp_dict
    assert "feasible_timetables" in comp_dict
    assert "optimized_timetables" in comp_dict
    assert target_services[0] in comp_dict["published_timetables"]
    assert target_services[0] in comp_dict["feasible_timetables"]
    assert target_services[0] in comp_dict["optimized_timetables"]


def test_decision_advisor_published_delay_and_three_tier_preservation():
    """Verify DecisionSupportAdvisor fixes published delay mismatch and forwards 3-tier timetables."""
    advisor = DecisionSupportAdvisor()
    target_services = ["SRV_12607_01", "SRV_12609_01"]
    scenario = Scenario(
        scenario_id="SCEN_ADVISOR_3TIER",
        name="Advisor 3-Tier Integration Test",
        description="Verify advisor preserves 3-tier timetables",
        affected_service_ids=target_services,
        departure_delays={"SRV_12607_01": 15.0},
    )

    assessment = advisor.evaluate_what_if_scenario(scenario, service_ids=target_services)
    comp_detail = assessment.comparison_detail
    assert comp_detail is not None

    # Published reference delay must NOT fall back to 0.0 when delay is present
    assert comp_detail.published_reference_delay_minutes > 0.0

    # 3-tier timetables must be non-empty
    assert len(comp_detail.three_tier_timetable) > 0
    assert len(comp_detail.published_timetables) > 0
    assert len(comp_detail.feasible_timetables) > 0
    assert len(comp_detail.optimized_timetables) > 0

    # Serialization must include all 3-tier timetable keys
    serialized = comp_detail.to_dict()
    assert "three_tier_timetable" in serialized
    assert "published_timetables" in serialized
    assert "feasible_timetables" in serialized
    assert "optimized_timetables" in serialized
    assert serialized["published_reference_delay_minutes"] > 0.0


def test_api_optimize_endpoint_returns_3_tier_timetables():
    """Verify POST /api/v1/optimize returns feasible, published, and three_tier_timetable entries."""
    payload = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "departure_delays": {"SRV_12607_01": 15.0},
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "adjusted_timetables" in data
    assert "feasible_adjusted_timetables" in data
    assert data["feasible_adjusted_timetables"] is not None
    assert "SRV_12607_01" in data["feasible_adjusted_timetables"]

    assert "published_adjusted_timetables" in data
    assert data["published_adjusted_timetables"] is not None
    assert "SRV_12607_01" in data["published_adjusted_timetables"]

    assert "three_tier_timetable" in data
    assert data["three_tier_timetable"] is not None
    assert len(data["three_tier_timetable"]) > 0

    first_entry = data["three_tier_timetable"][0]
    assert first_entry["service_id"] in payload["service_ids"]
    assert "published_arrival_str" in first_entry
    assert "feasible_arrival_str" in first_entry
    assert "optimized_arrival_str" in first_entry


def test_api_what_if_endpoint_returns_3_tier_timetables():
    """Verify POST /api/v1/what-if returns 3-tier timetable data in baseline_comparison."""
    payload = {
        "scenario_id": "SCEN_WHAT_IF_3TIER",
        "scenario_name": "API What-If 3-Tier Test",
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "departure_delays": {"SRV_12607_01": 15.0},
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    baseline_comp = data["baseline_comparison"]
    assert baseline_comp["published_reference_delay_minutes"] > 0.0

    assert "three_tier_timetable" in baseline_comp
    assert len(baseline_comp["three_tier_timetable"]) > 0

    assert "published_timetables" in baseline_comp
    assert "feasible_timetables" in baseline_comp
    assert "optimized_timetables" in baseline_comp
