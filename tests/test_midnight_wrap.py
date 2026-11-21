"""
tests/test_midnight_wrap.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for Batch 6.6: Midnight wrap opt-in flag and v2 evaluation artifacts.

Verifies:
1. Default solver and scenario behavior remains unwrapped (apply_midnight_wrap=False).
2. Opt-in flag (apply_midnight_wrap=True) correctly resolves +1440 day offset for post-midnight arrivals (SRV_16159_01).
3. API endpoints (/optimize and /what-if) accept apply_midnight_wrap.
4. Corrected evaluation results in data/evaluation/v2/ exist and master datasets remain untouched.
"""

import json
import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from evaluation.scalability_framework import SCALABILITY_COHORTS
from optimization.model import OptimizationRequest
from optimization.scenarios import Scenario, ScenarioRunner


def test_default_opt_in_flag_off():
    """Default solver behavior has apply_midnight_wrap=False and preserves unwrapped timings."""
    req = OptimizationRequest()
    assert req.apply_midnight_wrap is False

    runner = ScenarioRunner()
    scen = Scenario(
        scenario_id="TEST_UNWRAPPED_16159",
        name="Test Unwrapped 16159",
        affected_service_ids=["SRV_16159_01"],
    )
    res = runner.run_scenario(scen, apply_midnight_wrap=False)
    adj = res.feasible_baseline_result.adjusted_timetables.get("SRV_16159_01", [])
    cgl_stop = next(a for a in adj if a.station_id == "CGL")

    # In unwrapped mode, CGL arrival (00:08) is evaluated as 8.0 min, giving 1415.0 min delay
    assert cgl_stop.original_arrival == 8.0
    assert cgl_stop.delay_minutes == 1415.0
    assert res.baseline_total_delay >= 1415.0


def test_opt_in_midnight_wrap_on():
    """When apply_midnight_wrap=True, +1440 day offset is applied, eliminating artificial delay."""
    runner = ScenarioRunner()
    scen = Scenario(
        scenario_id="TEST_WRAPPED_16159",
        name="Test Wrapped 16159",
        affected_service_ids=["SRV_16159_01"],
    )
    res = runner.run_scenario(scen, apply_midnight_wrap=True)
    adj = res.feasible_baseline_result.adjusted_timetables.get("SRV_16159_01", [])
    cgl_stop = next(a for a in adj if a.station_id == "CGL")

    # In wrapped mode, CGL arrival is evaluated as 1448.0 min (00:08 + 1440), giving 0.0 delay
    assert cgl_stop.original_arrival == 1448.0
    assert cgl_stop.delay_minutes == 0.0
    assert res.baseline_total_delay == 0.0
    assert res.optimized_total_delay == 0.0


def test_api_optimize_with_midnight_wrap():
    """POST /optimize supports opt-in apply_midnight_wrap flag with and without departure delays."""
    with TestClient(app) as client:
        # 1. Nominal with apply_midnight_wrap=True
        resp_wrap = client.post(
            "/api/v1/optimize",
            json={
                "service_ids": ["SRV_16159_01"],
                "apply_midnight_wrap": True,
            },
        )
        assert resp_wrap.status_code == 200
        data_wrap = resp_wrap.json()
        assert data_wrap["solution_available"] is True
        assert data_wrap["optimized_total_delay_minutes"] == 0.0

        # 2. With default (apply_midnight_wrap omitted/False)
        resp_def = client.post(
            "/api/v1/optimize",
            json={
                "service_ids": ["SRV_16159_01"],
            },
        )
        assert resp_def.status_code == 200
        data_def = resp_def.json()
        assert data_def["solution_available"] is True

        # 3. Non-midnight service SRV_12607_01 with 25 min departure delay and wrap=True
        resp_non = client.post(
            "/api/v1/optimize",
            json={
                "service_ids": ["SRV_12607_01", "SRV_12609_01"],
                "departure_delays": {"SRV_12607_01": 25.0},
                "apply_midnight_wrap": True,
            },
        )
        assert resp_non.status_code == 200
        data_non = resp_non.json()
        assert data_non["solution_available"] is True
        assert data_non["solver_status"] in ("OPTIMAL", "FEASIBLE")
        assert data_non["optimized_total_delay_minutes"] is not None
        assert data_non["optimized_total_delay_minutes"] < 500.0

        # 4. Midnight service SRV_16159_01 with 15 min departure delay and wrap=True
        resp_mid = client.post(
            "/api/v1/optimize",
            json={
                "service_ids": ["SRV_16159_01"],
                "departure_delays": {"SRV_16159_01": 15.0},
                "apply_midnight_wrap": True,
            },
        )
        assert resp_mid.status_code == 200
        data_mid = resp_mid.json()
        assert data_mid["solution_available"] is True
        assert data_mid["solver_status"] in ("OPTIMAL", "FEASIBLE")
        assert data_mid["optimized_total_delay_minutes"] is not None
        assert data_mid["optimized_total_delay_minutes"] < 100.0


def test_api_what_if_with_midnight_wrap():
    """POST /what-if supports opt-in apply_midnight_wrap flag with and without departure delays."""
    with TestClient(app) as client:
        # 1. Nominal midnight service
        resp = client.post(
            "/api/v1/what-if",
            json={
                "service_ids": ["SRV_16159_01"],
                "apply_midnight_wrap": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["solution_available"] is True
        assert data["total_baseline_delay_minutes"] == 0.0

        # 2. Non-midnight services with departure delay and wrap=True
        resp_non = client.post(
            "/api/v1/what-if",
            json={
                "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"],
                "departure_delays": {"SRV_12607_01": 25.0},
                "apply_midnight_wrap": True,
            },
        )
        assert resp_non.status_code == 200
        data_non = resp_non.json()
        assert data_non["solution_available"] is True
        assert data_non["total_baseline_delay_minutes"] < 500.0
        assert len(data_non["recommendations"]) > 0

        # 3. Midnight service with departure delay and wrap=True
        resp_mid = client.post(
            "/api/v1/what-if",
            json={
                "service_ids": ["SRV_16159_01"],
                "departure_delays": {"SRV_16159_01": 15.0},
                "apply_midnight_wrap": True,
            },
        )
        assert resp_mid.status_code == 200
        data_mid = resp_mid.json()
        assert data_mid["solution_available"] is True
        assert data_mid["total_baseline_delay_minutes"] < 100.0


def test_v2_evaluation_artifacts_exist():
    """Corrected evaluation results are isolated in data/evaluation/v2/."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    v2_dir = os.path.join(base_dir, "data", "evaluation", "v2")

    assert os.path.exists(os.path.join(v2_dir, "nominal_cohort_benchmarks.json"))
    assert os.path.exists(os.path.join(v2_dir, "midnight_wrap_comparison.json"))
    assert os.path.exists(os.path.join(v2_dir, "v2_evaluation_report.md"))

    with open(os.path.join(v2_dir, "midnight_wrap_comparison.json"), "r", encoding="utf-8") as f:
        data = json.load(f)
        assert data["service_id"] == "SRV_16159_01"
        assert data["v1_without_wrap"]["baseline_delay_minutes"] == 1415.0
        assert data["v2_with_wrap"]["baseline_delay_minutes"] == 0.0


def test_sanity_cohorts_v2_le_v1_and_40_baseline():
    """For every cohort, v2 FIFO <= v1 FIFO, and 40-service v2 FIFO is close to 511 min."""
    runner = ScenarioRunner()
    for n in [4, 8, 12, 16, 20, 30, 40]:
        scen = Scenario(
            scenario_id=f"TEST_SANITY_{n}",
            name=f"Sanity {n}",
            affected_service_ids=SCALABILITY_COHORTS[n],
        )
        c1 = runner.run_scenario(scen, apply_midnight_wrap=False)
        c2 = runner.run_scenario(scen, apply_midnight_wrap=True)

        assert c2.baseline_total_delay <= c1.baseline_total_delay + 1e-6
        if n <= 20:
            assert abs(c1.baseline_total_delay - c2.baseline_total_delay) < 1e-6
        else:
            # 30 and 40 cohorts include SRV_16159_01 which has exactly 1415.0m artificial delay removed
            assert abs((c1.baseline_total_delay - c2.baseline_total_delay) - 1415.0) < 1e-6

        if n == 40:
            # Must be close to 511 min (the 39-service result without SRV_16159_01)
            assert 500.0 <= c2.baseline_total_delay <= 520.0
            assert round(c2.baseline_total_delay, 1) == 511.0


def test_non_midnight_service_delays_unchanged():
    """Per-service delays for services that do not cross midnight are unchanged by apply_midnight_wrap.
    
    Also verifies departure delay repro: 40 active services under departure delays with wrap=True
    must remain OPTIMAL and equal nowrap minus 1415.0m.
    """
    runner = ScenarioRunner()
    s_ids = SCALABILITY_COHORTS[40]

    # Nominal 40-service test
    scen = Scenario(
        scenario_id="TEST_NON_MIDNIGHT_UNCHANGED_40",
        name="Test 40 Services",
        affected_service_ids=s_ids,
    )
    res_v1 = runner.run_scenario(scen, apply_midnight_wrap=False)
    res_v2 = runner.run_scenario(scen, apply_midnight_wrap=True)

    adj_v1 = res_v1.feasible_baseline_result.adjusted_timetables
    adj_v2 = res_v2.feasible_baseline_result.adjusted_timetables

    for s_id in s_ids:
        v1_stops = adj_v1.get(s_id, [])
        v2_stops = adj_v2.get(s_id, [])

        v1_service_delay = sum(st.delay_minutes for st in v1_stops)
        v2_service_delay = sum(st.delay_minutes for st in v2_stops)

        if s_id == "SRV_16159_01":
            assert abs((v1_service_delay - v2_service_delay) - 1415.0) < 1e-6
        else:
            assert abs(v1_service_delay - v2_service_delay) < 1e-6

    # Repro 1: SRV_12607_01 +25 min departure delay
    scen1 = Scenario(
        scenario_id="TEST_REPRO_12607",
        name="Repro 12607 Delay 25",
        affected_service_ids=s_ids,
        departure_delays={"SRV_12607_01": 25.0},
    )
    res1_nowrap = runner.run_scenario(scen1, apply_midnight_wrap=False)
    res1_wrap = runner.run_scenario(scen1, apply_midnight_wrap=True)

    assert res1_nowrap.optimization_status == "OPTIMAL"
    assert res1_wrap.optimization_status == "OPTIMAL"
    assert round(res1_nowrap.baseline_total_delay, 1) == 2045.0
    assert round(res1_nowrap.optimized_total_delay, 1) == 1981.0
    assert round(res1_wrap.baseline_total_delay, 1) == 630.0
    assert round(res1_wrap.optimized_total_delay, 1) == 566.0
    assert abs((res1_nowrap.baseline_total_delay - res1_wrap.baseline_total_delay) - 1415.0) < 1e-6
    assert abs((res1_nowrap.optimized_total_delay - res1_wrap.optimized_total_delay) - 1415.0) < 1e-6

    # Repro 2: SRV_43411_01 +15 min departure delay
    scen2 = Scenario(
        scenario_id="TEST_REPRO_43411",
        name="Repro 43411 Delay 15",
        affected_service_ids=s_ids,
        departure_delays={"SRV_43411_01": 15.0},
    )
    res2_nowrap = runner.run_scenario(scen2, apply_midnight_wrap=False)
    res2_wrap = runner.run_scenario(scen2, apply_midnight_wrap=True)

    assert res2_nowrap.optimization_status == "OPTIMAL"
    assert res2_wrap.optimization_status == "OPTIMAL"
    assert round(res2_nowrap.baseline_total_delay, 1) == 2028.0
    assert round(res2_nowrap.optimized_total_delay, 1) == 1978.0
    assert round(res2_wrap.baseline_total_delay, 1) == 613.0
    assert round(res2_wrap.optimized_total_delay, 1) == 563.0
    assert abs((res2_nowrap.baseline_total_delay - res2_wrap.baseline_total_delay) - 1415.0) < 1e-6
    assert abs((res2_nowrap.optimized_total_delay - res2_wrap.optimized_total_delay) - 1415.0) < 1e-6



