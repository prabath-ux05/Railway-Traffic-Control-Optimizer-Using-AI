"""
tests/test_corridor_performance_backend.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Backend test suite verifying Requirement #8:
Corridor performance aggregation across the 7 authoritative corridors:
- West
- North
- South
- MRTS
- Beach–North Bypass
- Cross/Bypass (topology-only)
- PTMS

Validates:
1. Dynamic computation of real metrics (service_count, delay, savings, throughput, OTP, conflicts, utilization, stress).
2. Authoritative attribution of services and track sections.
3. Preservation of Cross/Bypass as topology-only (no fabricated services).
4. Full contract serialization in ScenarioComparison, BaselineOptimizationComparison, /api/v1/optimize, and /api/v1/what-if.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.api import get_network
from backend.app.main import app
from decision_support.advisor import DecisionSupportAdvisor
from decision_support.models import BaselineOptimizationComparison
from optimization.scenarios import AUTHORITATIVE_CORRIDORS, Scenario, ScenarioRunner
from simulation.conflicts import Conflict, ConflictSeverity, ConflictType


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def runner():
    return ScenarioRunner()


def test_authoritative_corridors_definition():
    """Verify that all 7 authoritative corridors are precisely defined."""
    corridor_names = [c["corridor_name"] for c in AUTHORITATIVE_CORRIDORS]
    corridor_ids = [c["corridor_id"] for c in AUTHORITATIVE_CORRIDORS]

    expected_names = [
        "West",
        "North",
        "South",
        "MRTS",
        "Beach–North Bypass",
        "Cross/Bypass",
        "PTMS",
    ]
    assert corridor_names == expected_names
    assert len(corridor_ids) == 7

    # Cross/Bypass is explicitly topology-only
    cross_entry = next(c for c in AUTHORITATIVE_CORRIDORS if c["corridor_name"] == "Cross/Bypass")
    assert cross_entry["is_topology_only"] is True

    # Other corridors are operational
    for c in AUTHORITATIVE_CORRIDORS:
        if c["corridor_name"] != "Cross/Bypass":
            assert c["is_topology_only"] is False


def test_corridor_performance_single_corridor(runner):
    """Test corridor performance aggregation with a single perturbed corridor (West)."""
    scenario = Scenario(
        scenario_id="SCEN_TEST_WEST_DELAY",
        name="West Late Departure",
        description="20 min departure delay on West train 12607",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
        departure_delays={"SRV_12607_01": 20.0},
    )
    comp = runner.run_scenario(scenario)
    summary = comp.build_corridor_performance_summary(runner.network)

    assert len(summary) == 7

    summary_by_name = {c["corridor_name"]: c for c in summary}

    # Verify West corridor has real metrics
    west = summary_by_name["West"]
    assert west["is_topology_only"] is False
    assert west["service_count"] == 2
    assert "SRV_12607_01" in west["active_service_ids"]
    assert "SRV_12609_01" in west["active_service_ids"]
    assert west["baseline_delay_minutes"] > 0.0
    assert west["optimized_delay_minutes"] > 0.0
    assert west["delay_savings_minutes"] >= 0.0
    assert west["throughput"] == 2
    assert 0.0 <= west["on_time_performance_percent"] <= 100.0
    assert west["track_sections_count"] > 100
    assert west["stress_level"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]

    # Delays match total scenario comparison
    assert west["baseline_delay_minutes"] == pytest.approx(comp.baseline_total_delay, abs=0.01)
    assert west["optimized_delay_minutes"] == pytest.approx(comp.optimized_total_delay, abs=0.01)
    assert west["delay_savings_minutes"] == pytest.approx(comp.delay_savings_minutes, abs=0.01)

    # Cross/Bypass remains topology-only
    cross = summary_by_name["Cross/Bypass"]
    assert cross["is_topology_only"] is True
    assert cross["service_count"] == 0
    assert cross["total_registered_services"] == 0
    assert cross["track_sections_count"] == 22
    assert cross["baseline_delay_minutes"] == 0.0
    assert cross["optimized_delay_minutes"] == 0.0
    assert cross["delay_savings_minutes"] == 0.0
    assert cross["stress_level"] == "TOPOLOGY_ONLY"

    # Other unperturbed corridors are UNCONTESTED
    for name in ["North", "South", "MRTS", "Beach–North Bypass", "PTMS"]:
        entry = summary_by_name[name]
        assert entry["service_count"] == 0
        assert entry["baseline_delay_minutes"] == 0.0
        assert entry["optimized_delay_minutes"] == 0.0
        assert entry["stress_level"] == "UNCONTESTED"


def test_corridor_performance_multi_corridor(runner):
    """Test corridor performance aggregation across multiple simultaneous corridors."""
    scenario = Scenario(
        scenario_id="SCEN_MULTI_CORRIDOR_PERF",
        name="Multi-Corridor Operation",
        description="Services across 6 active corridors with perturbations",
        affected_service_ids=[
            "SRV_12607_01",  # West (RT_WEST_MAS_AJJ)
            "SRV_12712_01",  # North (RT_NORTH_MAS_SPE)
            "SRV_40001_01",  # South (RT_SOUTH_MSB_TBM_SHORT)
            "SRV_41001_01",  # MRTS (RT_MRTS_MSB_VLCY)
            "SRV_42601_01",  # Beach–North Bypass (RT_BEACH_NORTH_BYPASS)
            "SRV_43102_01",  # PTMS (RT_PTMS_MAS)
        ],
        departure_delays={
            "SRV_12607_01": 25.0,
            "SRV_12712_01": 15.0,
        },
    )
    comp = runner.run_scenario(scenario)
    summary = comp.build_corridor_performance_summary(runner.network)
    summary_by_name = {c["corridor_name"]: c for c in summary}

    assert len(summary) == 7

    # Verify each operational corridor has exactly its service attributed
    assert summary_by_name["West"]["active_service_ids"] == ["SRV_12607_01"]
    assert summary_by_name["North"]["active_service_ids"] == ["SRV_12712_01"]
    assert summary_by_name["South"]["active_service_ids"] == ["SRV_40001_01"]
    assert summary_by_name["MRTS"]["active_service_ids"] == ["SRV_41001_01"]
    assert summary_by_name["Beach–North Bypass"]["active_service_ids"] == ["SRV_42601_01"]
    assert summary_by_name["PTMS"]["active_service_ids"] == ["SRV_43102_01"]
    assert summary_by_name["Cross/Bypass"]["active_service_ids"] == []

    # Cross/Bypass has zero services invented
    assert summary_by_name["Cross/Bypass"]["service_count"] == 0
    assert summary_by_name["Cross/Bypass"]["is_topology_only"] is True
    assert summary_by_name["Cross/Bypass"]["stress_level"] == "TOPOLOGY_ONLY"

    # Verify Delay Conservation: Sum of corridor delays equals Scenario total delay
    sum_baseline_delay = sum(c["baseline_delay_minutes"] for c in summary)
    sum_optimized_delay = sum(c["optimized_delay_minutes"] for c in summary)
    sum_delay_savings = sum(c["delay_savings_minutes"] for c in summary)

    assert sum_baseline_delay == pytest.approx(comp.baseline_total_delay, abs=0.01)
    assert sum_optimized_delay == pytest.approx(comp.optimized_total_delay, abs=0.01)
    assert sum_delay_savings == pytest.approx(comp.delay_savings_minutes, abs=0.01)

    # Verify Throughput: Sum of corridor throughput equals scenario throughput
    assert sum(c["throughput"] for c in summary) == comp.throughput

    # Verify West and North received delayed services
    assert summary_by_name["West"]["baseline_delay_minutes"] > 0.0
    assert summary_by_name["North"]["baseline_delay_minutes"] > 0.0

    # Verify OTP is non-negative and <= 100
    for c in summary:
        assert 0.0 <= c["on_time_performance_percent"] <= 100.0


def test_corridor_conflict_attribution(runner):
    """Test that conflicts on corridor resources are correctly attributed to the corridor."""
    # Inject an explicit conflict at BBQ (throat junction shared with West and North)
    conflict = Conflict(
        conflict_id="CONF_BBQ_WEST_TEST",
        conflict_type=ConflictType.INSUFFICIENT_HEADWAY,
        affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
        affected_train_ids=["12607", "12609"],
        resource_id="JCT_BBQ",
        conflict_time=360.0,
        severity=ConflictSeverity.CRITICAL,
        description="Headway contention at BBQ junction",
    )

    scenario = Scenario(
        scenario_id="SCEN_CONFLICT_TEST",
        name="BBQ Conflict Injection",
        description="Conflict at BBQ junction",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
        injected_conflicts=[conflict],
    )
    comp = runner.run_scenario(scenario)
    summary = comp.build_corridor_performance_summary(runner.network)
    summary_by_name = {c["corridor_name"]: c for c in summary}

    west = summary_by_name["West"]
    assert west["initial_conflicts"] >= 1


def test_scenario_comparison_to_dict_includes_corridor_performance(runner):
    """Verify ScenarioComparison.to_dict() contains corridor_performance."""
    scenario = Scenario(
        scenario_id="SCEN_TO_DICT",
        name="To Dict Test",
        description="Verify serialization",
        affected_service_ids=["SRV_12607_01"],
    )
    comp = runner.run_scenario(scenario)
    d = comp.to_dict()

    assert "corridor_performance" in d
    assert isinstance(d["corridor_performance"], list)
    assert len(d["corridor_performance"]) == 7

    corridor_names = [c["corridor_name"] for c in d["corridor_performance"]]
    assert corridor_names == [
        "West",
        "North",
        "South",
        "MRTS",
        "Beach–North Bypass",
        "Cross/Bypass",
        "PTMS",
    ]


def test_baseline_optimization_comparison_model():
    """Verify BaselineOptimizationComparison retains corridor_performance."""
    comp_obj = BaselineOptimizationComparison(
        published_reference_delay_minutes=10.0,
        feasible_baseline_delay_minutes=20.0,
        feasible_baseline_max_delay_minutes=15.0,
        feasible_baseline_conflicts_remaining=0,
        feasible_baseline_throughput=2,
        optimized_delay_minutes=5.0,
        optimized_max_delay_minutes=5.0,
        optimized_conflicts_remaining=0,
        optimized_throughput=2,
        delay_savings_minutes=15.0,
        delay_savings_percent=75.0,
        solver_status="OPTIMAL",
        solve_time_seconds=0.12,
        corridor_performance=[{"corridor_name": "West", "service_count": 2}],
    )
    d = comp_obj.to_dict()
    assert "corridor_performance" in d
    assert len(d["corridor_performance"]) == 1
    assert d["corridor_performance"][0]["corridor_name"] == "West"


def test_api_optimize_endpoint_returns_corridor_performance(client):
    """Verify POST /api/v1/optimize returns corridor_performance."""
    payload = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "departure_delays": {"SRV_12607_01": 15.0},
    }
    response = client.post("/api/v1/optimize", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "corridor_performance" in data
    assert data["corridor_performance"] is not None
    assert len(data["corridor_performance"]) == 7

    corridors = {c["corridor_name"]: c for c in data["corridor_performance"]}
    assert "West" in corridors
    assert "Cross/Bypass" in corridors
    assert corridors["Cross/Bypass"]["is_topology_only"] is True
    assert corridors["Cross/Bypass"]["service_count"] == 0
    assert corridors["West"]["service_count"] == 2


def test_api_what_if_endpoint_returns_corridor_performance(client):
    """Verify POST /api/v1/what-if returns corridor_performance top-level and in baseline_comparison."""
    payload = {
        "scenario_id": "SCEN_WHAT_IF_CORRIDORS",
        "scenario_name": "What-If Corridor Test",
        "description": "Multi-corridor evaluation",
        "service_ids": ["SRV_12607_01", "SRV_42015_01"],
        "departure_delays": {"SRV_12607_01": 20.0},
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Top-level corridor_performance
    assert "corridor_performance" in data
    assert data["corridor_performance"] is not None
    assert len(data["corridor_performance"]) == 7

    # Inside baseline_comparison
    assert "baseline_comparison" in data
    assert "corridor_performance" in data["baseline_comparison"]
    assert len(data["baseline_comparison"]["corridor_performance"]) == 7

    corridors = {c["corridor_name"]: c for c in data["corridor_performance"]}
    assert corridors["West"]["service_count"] == 1
    assert corridors["North"]["service_count"] == 1
    assert corridors["Cross/Bypass"]["is_topology_only"] is True
    assert corridors["Cross/Bypass"]["service_count"] == 0
