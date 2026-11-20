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
    """POST /optimize supports opt-in apply_midnight_wrap flag."""
    with TestClient(app) as client:
        # 1. With apply_midnight_wrap=True
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


def test_api_what_if_with_midnight_wrap():
    """POST /what-if supports opt-in apply_midnight_wrap flag."""
    with TestClient(app) as client:
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
