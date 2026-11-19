"""Tests for Batch 2: Result Integrity, Infeasible Handling, Objective Modes, and Validation.

Tests all 3 layers:
1. Solver result layer (optimization/solver.py)
2. API response layer (backend/app/api.py: /optimize and /what-if)
3. Decision support advisor layer (decision_support/advisor.py)
Plus objective verification and validation rules.
"""

import json
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.api import get_network
from optimization.model import OptimizationRequest
from optimization.solver import CPSATScheduler
from optimization.scenarios import Scenario, ScenarioRunner
from decision_support.advisor import DecisionSupportAdvisor
from decision_support.models import OperationalSeverity, RecommendationType


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def network():
    return get_network()


# =========================================================================
# LAYER 1: SOLVER RESULT LAYER
# =========================================================================

def test_solver_infeasible_when_sections_blocked(network):
    """Verify CP-SAT solver returns INFEASIBLE status when critical sections are blocked."""
    runner = ScenarioRunner(network)
    scen = Scenario(
        scenario_id="SCEN_INF_SOLVER",
        name="Critical Blocked Sections",
        description="Blocks both suburban and main lines between PER and PCW.",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"],
        blocked_sections=["PER_PCW_SUBURBAN_DOWN", "PER_PCW_MAIN_DOWN"],
        objective_mode="WEIGHTED",
    )
    comp = runner.run_scenario(scen)
    assert comp.optimization_status == "INFEASIBLE"
    assert comp.solution_available is False
    assert comp.optimized_total_delay is None
    assert comp.delay_savings_minutes is None
    assert comp.delay_savings_percent is None
    assert comp.optimized_result.status == "INFEASIBLE"
    assert comp.optimized_result.adjusted_timetables == {}


def test_solver_objective_modes(network):
    """Verify CP-SAT solver supports both WEIGHTED and TOTAL_DELAY objective modes."""
    runner = ScenarioRunner(network)
    scen_w = Scenario(
        scenario_id="SCEN_OBJ_W",
        name="Weighted Objective",
        description="Run with WEIGHTED objective mode.",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
        objective_mode="WEIGHTED",
    )
    scen_t = Scenario(
        scenario_id="SCEN_OBJ_T",
        name="Total Delay Objective",
        description="Run with TOTAL_DELAY objective mode.",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
        objective_mode="TOTAL_DELAY",
    )
    comp_w = runner.run_scenario(scen_w)
    comp_t = runner.run_scenario(scen_t)
    assert comp_w.optimization_status in ("OPTIMAL", "FEASIBLE")
    assert comp_t.optimization_status in ("OPTIMAL", "FEASIBLE")
    assert comp_w.solution_available is True
    assert comp_t.solution_available is True
    assert comp_w.objective_mode == "WEIGHTED"
    assert comp_t.objective_mode == "TOTAL_DELAY"


def test_solver_feasibility_checker(network):
    """Verify schedule feasibility check helper works correctly on an optimal schedule."""
    req = OptimizationRequest.from_network_and_state(
        network=network,
        service_ids=["SRV_12607_01"],
        time_horizon=(900.0, 1100.0),
    )
    scheduler = CPSATScheduler(time_limit_seconds=5.0)
    result = scheduler.schedule(req)
    assert result.status in ("OPTIMAL", "FEASIBLE")

    is_feasible, violations = scheduler.check_schedule_feasibility(req, result.adjusted_timetables)
    assert is_feasible is True
    assert len(violations) == 0


# =========================================================================
# LAYER 2: API RESPONSE LAYER
# =========================================================================

def test_what_if_infeasible_scenario(client):
    """Verify /api/v1/what-if returns solution_available=False and null savings on infeasibility."""
    payload = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"],
        "blocked_sections": ["PER_PCW_SUBURBAN_DOWN", "PER_PCW_MAIN_DOWN"],
    }
    resp = client.post("/api/v1/what-if", json=payload)
    assert resp.status_code == 200
    data = resp.json()

    assert data["solution_available"] is False
    assert data["solver_status"] == "INFEASIBLE"
    assert data["total_optimized_delay_minutes"] is None
    assert data["net_delay_savings_minutes"] is None
    assert data["net_delay_savings_percent"] is None
    assert data["optimized_weighted_objective"] is None
    assert data["operational_severity"] == "EMERGENCY"

    # Controller summary must reflect infeasibility
    summary = data["controller_summary"]
    assert summary["solution_available"] is False
    assert summary["solver_status"] == "INFEASIBLE"
    assert summary["operational_severity"] == "EMERGENCY"
    assert summary["net_delay_savings_minutes"] is None
    assert "No feasible schedule with the blocked resources" in summary["top_recommendation"]
    assert "Maintain published timetable" not in summary["top_recommendation"]

    # Recommendations must contain the single emergency directive
    assert len(data["recommendations"]) == 1
    rec = data["recommendations"][0]
    assert rec["recommendation_type"] == "NO_FEASIBLE_SCHEDULE"
    assert "PER_PCW_MAIN_DOWN" in rec["title"]
    assert "PER_PCW_SUBURBAN_DOWN" in rec["title"]


def test_input_validation_unknown_blocked_sections(client):
    """Unknown blocked section IDs must return 400 with valid IDs listed."""
    resp = client.post("/api/v1/what-if", json={"blocked_sections": ["NON_EXISTENT_TRACK_XYZ"]})
    assert resp.status_code == 400
    detail = resp.json().get("detail", "")
    assert "Unknown blocked_sections IDs" in detail
    assert "NON_EXISTENT_TRACK_XYZ" in detail
    assert "Valid track section IDs are:" in detail


def test_input_validation_negative_delays(client):
    """Negative departure or station delays must be rejected with HTTP 422."""
    # Negative departure delay in /what-if
    r1 = client.post("/api/v1/what-if", json={"departure_delays": {"SRV_12607_01": -15.0}})
    assert r1.status_code == 422

    # Negative station delay in /what-if
    r2 = client.post("/api/v1/what-if", json={"station_delays": {"SRV_12607_01": {"MAS": -5.0}}})
    assert r2.status_code == 422

    # Negative departure delay in /optimize
    r3 = client.post("/api/v1/optimize", json={"departure_delays": {"SRV_12607_01": -2.0}})
    assert r3.status_code == 422


def test_input_validation_service_ids(client):
    """Empty service_ids or unknown service_ids must return HTTP 400."""
    # Empty service_ids in /what-if
    r1 = client.post("/api/v1/what-if", json={"service_ids": []})
    assert r1.status_code == 400
    assert "service_ids cannot be an empty list" in r1.json()["detail"]

    # Unknown service_ids in /what-if
    r2 = client.post("/api/v1/what-if", json={"service_ids": ["SRV_FAKE_99999"]})
    assert r2.status_code == 400
    assert "Invalid service_id 'SRV_FAKE_99999'" in r2.json()["detail"]

    # Empty service_ids in /optimize
    r3 = client.post("/api/v1/optimize", json={"service_ids": []})
    assert r3.status_code == 400

    # Unknown service_ids in /optimize
    r4 = client.post("/api/v1/optimize", json={"service_ids": ["SRV_FAKE_99999"]})
    assert r4.status_code == 400


def test_objective_mode_and_reporting_fields(client):
    """Verify objective_mode, fifo_weighted_objective, and optimized_weighted_objective are present."""
    payload_w = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "objective_mode": "WEIGHTED",
    }
    r_w = client.post("/api/v1/optimize", json=payload_w)
    assert r_w.status_code == 200
    d_w = r_w.json()
    assert d_w["objective_mode"] == "WEIGHTED"
    assert d_w["fifo_weighted_objective"] is not None
    assert d_w["optimized_weighted_objective"] is not None
    assert d_w["solution_available"] is True

    payload_t = {
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "objective_mode": "TOTAL_DELAY",
    }
    r_t = client.post("/api/v1/optimize", json=payload_t)
    assert r_t.status_code == 200
    d_t = r_t.json()
    assert d_t["objective_mode"] == "TOTAL_DELAY"
    assert d_t["fifo_weighted_objective"] is not None
    assert d_t["optimized_weighted_objective"] is not None


def test_simulation_timestamp_determinism(client):
    """Verify simulation_timestamp_str is deterministic across multiple calls with same cohort."""
    payload = {"service_ids": ["SRV_12607_01", "SRV_12609_01"]}
    r1 = client.post("/api/v1/what-if", json=payload)
    r2 = client.post("/api/v1/what-if", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["simulation_timestamp_str"] == r2.json()["simulation_timestamp_str"]


# =========================================================================
# LAYER 3: ADVISOR LAYER
# =========================================================================

def test_advisor_infeasible_directive(network):
    """Verify advisor creates emergency directive when solver is infeasible."""
    advisor = DecisionSupportAdvisor(network)
    scen = Scenario(
        scenario_id="SCEN_INF",
        name="Infeasible Scenario",
        description="All lines between PER and PCW blocked",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"],
        blocked_sections=["PER_PCW_MAIN_DOWN", "PER_PCW_SUBURBAN_DOWN"],
    )
    assessment = advisor.evaluate_what_if_scenario(
        scen,
        service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"],
    )
    assert assessment.situation.severity == OperationalSeverity.EMERGENCY
    assert len(assessment.recommendations) == 1
    top_rec = assessment.recommendations[0]
    assert top_rec.recommendation_type == RecommendationType.NO_FEASIBLE_SCHEDULE
    assert "No feasible schedule with the blocked resources" in top_rec.title
    assert "PER_PCW_MAIN_DOWN" in top_rec.title
    assert "PER_PCW_SUBURBAN_DOWN" in top_rec.title
    assert "Maintain published timetable" not in top_rec.title


# =========================================================================
# OBJECTIVE COMPARISON & BUG CANDIDATE DOCUMENTATION
# =========================================================================

KNOWN_NEGATIVE_SAVINGS_EXPERIMENT_IDS = {
    # Phase 31.1
    "EXP_31_1_01A_NOMINAL_MULTI",
    "EXP_31_1_04B_TSR_NORTH_TRUNK",
    # Phase 31.2 (Nominal load sweep, 4 to 40 services)
    "EXP_SCALE_04_NOMINAL",
    "EXP_SCALE_08_NOMINAL",
    "EXP_SCALE_12_NOMINAL",
    "EXP_SCALE_16_NOMINAL",
    "EXP_SCALE_20_NOMINAL",
    "EXP_SCALE_30_NOMINAL",
    "EXP_SCALE_40_NOMINAL",
    # Phase 31.3 (Perturbation sweep)
    "EXP_31_3_04_DWL_MILD",
    "EXP_31_3_05_DWL_MOD",
    "EXP_31_3_06_DWL_SEVERE",
    "EXP_31_3_07_TSR_MILD",
    "EXP_31_3_08_TSR_MOD",
    "EXP_31_3_10_BLK_MILD",
    "EXP_31_3_11_BLK_MOD",
    "EXP_31_3_13_JCT_MILD",
    "EXP_31_3_14_JCT_MOD",
    "EXP_31_3_15_JCT_SEVERE",
}


def test_audit_feasible_experiments_objective_and_bug_candidates():
    """Audit stored results for objective comparison.

    Assert that:
    1. Exactly 19 feasible experiments exhibit delay_savings_min < 0
       (matching the 19 negative savings reported in CICT 2026 paper Check 10 and Table II).
    2. These 19 experiments are documented as bug candidates caused by CP-SAT integer runtime
       discretization (ceil/round) versus FIFO fractional running times.
    3. The remaining 25 feasible experiments satisfy non-negative savings (0 or positive).
    """
    with open("data/evaluation/comparative_analysis_results.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    records = data.get("all_records", [])
    violations = []
    satisfied = []

    for r in records:
        exp_id = r.get("experiment_id", "")
        # Only check feasible runs
        if not r.get("is_feasible", False):
            continue

        savings = r.get("delay_savings_min", 0.0)
        if savings < -0.01:
            violations.append(exp_id)
        else:
            satisfied.append(exp_id)

    # Exactly 19 experiments have opt_delay > fifo_delay (negative savings)
    assert len(violations) == 19
    assert len(satisfied) == 25
    # All 19 violations match the exact known experiment IDs
    assert set(violations) == KNOWN_NEGATIVE_SAVINGS_EXPERIMENT_IDS
