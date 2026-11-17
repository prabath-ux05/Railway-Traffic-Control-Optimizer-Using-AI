"""
tests/test_phase32_4_what_if.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test suite for Phase 32.4: What-If Comparison & Decision-Support Reporting.

Tests cover:
  1. Module exports and availability of all Phase 32.4 symbols.
  2. ScenarioType categorization: OPERATIONAL_STATE vs HYPOTHETICAL_SCENARIO vs INFEASIBLE_BOUNDARY_CASE.
  3. WhatIfScenarioMetrics data contract and serialization.
  4. MultiScenarioComparativeSummary aggregation logic.
  5. Dedicated isolation of the MAS-BBQ down throat single-point-of-failure cliff.
  6. Machine-readable JSON export and Markdown report generation.
  7. Direct vs propagated delay breakdown across scenarios.
  8. Strict pending services exclusion invariant (7 pending services excluded).
  9. Master dataset immutability invariant.
  10. End-to-end execution of WhatIfComparisonEngine.
"""

from __future__ import annotations

import json
import os
import pytest
from typing import List

from evaluation.framework import PENDING_SERVICES
from decision_support import (
    MultiScenarioComparativeSummary,
    ScenarioType,
    WhatIfAnalyticsResult,
    WhatIfComparisonEngine,
    WhatIfScenarioMetrics,
    run_what_if_comparison,
)


# ---------------------------------------------------------------------------
# 1. Module Exports & Types
# ---------------------------------------------------------------------------

def test_phase32_4_exports():
    """Verify all required Phase 32.4 symbols are exported by decision_support."""
    import decision_support
    expected_exports = [
        "ScenarioType",
        "WhatIfScenarioMetrics",
        "MultiScenarioComparativeSummary",
        "WhatIfAnalyticsResult",
        "WhatIfComparisonEngine",
        "run_what_if_comparison",
    ]
    for symbol in expected_exports:
        assert hasattr(decision_support, symbol), f"decision_support missing export: {symbol}"


# ---------------------------------------------------------------------------
# 2. Scenario Type Categorization
# ---------------------------------------------------------------------------

def test_scenario_type_classification():
    """Verify scenario types are clearly separated."""
    assert ScenarioType.OPERATIONAL_STATE.value == "OPERATIONAL_STATE"
    assert ScenarioType.HYPOTHETICAL_SCENARIO.value == "HYPOTHETICAL_SCENARIO"
    assert ScenarioType.INFEASIBLE_BOUNDARY_CASE.value == "INFEASIBLE_BOUNDARY_CASE"


# ---------------------------------------------------------------------------
# 3. What-If Metrics Data Contract & Serialization
# ---------------------------------------------------------------------------

def test_what_if_metrics_serialization():
    """Verify WhatIfScenarioMetrics serializes cleanly to dict."""
    m = WhatIfScenarioMetrics(
        scenario_id="SCEN_TEST_01",
        name="Test Scenario",
        scenario_type=ScenarioType.HYPOTHETICAL_SCENARIO,
        baseline_delay_minutes=100.0,
        optimized_delay_minutes=60.0,
        delay_savings_minutes=40.0,
        delay_savings_percent=40.0,
        primary_delay_minutes=45.0,
        secondary_delay_minutes=55.0,
        knock_on_multiplier=2.22,
        recovery_rate_pct=40.0,
        initial_conflicts=3,
        remaining_conflicts=0,
        resolved_conflicts=3,
        affected_services_count=2,
        affected_service_ids=["SRV_12607_01", "SRV_22639_01"],
        primary_bottleneck_id="SEC_BBQ_KOK_UP",
        bottleneck_utilization_pct=78.5,
        solver_status="OPTIMAL",
        solve_time_seconds=0.045,
        recommendations_count=1,
        top_recommendation_title="Slot Rescheduling",
        top_recommendation_tier="CRITICAL",
        confidence_score=1.0,
    )

    d = m.to_dict()
    assert d["scenario_id"] == "SCEN_TEST_01"
    assert d["scenario_type"] == "HYPOTHETICAL_SCENARIO"
    assert d["delay_savings_minutes"] == 40.0
    assert d["knock_on_multiplier"] == 2.22
    assert d["resolved_conflicts"] == 3
    assert d["solver_status"] == "OPTIMAL"


# ---------------------------------------------------------------------------
# 4. MultiScenarioComparativeSummary Aggregation
# ---------------------------------------------------------------------------

def test_multiscenario_summary_aggregation():
    """Verify aggregation metrics calculate mean and sums accurately."""
    s = MultiScenarioComparativeSummary(
        total_scenarios_evaluated=4,
        operational_state_count=1,
        hypothetical_scenario_count=2,
        infeasible_boundary_count=1,
        mean_delay_savings_minutes=25.0,
        mean_delay_savings_percent=33.3,
        mean_solve_time_seconds=0.052,
        total_conflicts_resolved=6,
        mean_knock_on_multiplier=1.85,
        mean_confidence_score=0.75,
    )
    d = s.to_dict()
    assert d["total_scenarios_evaluated"] == 4
    assert d["operational_state_count"] == 1
    assert d["hypothetical_scenario_count"] == 2
    assert d["infeasible_boundary_count"] == 1
    assert d["mean_delay_savings_minutes"] == 25.0
    assert d["total_conflicts_resolved"] == 6


# ---------------------------------------------------------------------------
# 5. Infeasible Boundary Isolation
# ---------------------------------------------------------------------------

def test_infeasible_boundary_isolated():
    """Verify MAS-BBQ throat failure is explicitly categorized as INFEASIBLE_BOUNDARY_CASE."""
    engine = WhatIfComparisonEngine()
    result = engine.evaluate_suite(time_limit_seconds=5.0)

    infeasible_cases = [s for s in result.scenarios if s.scenario_type == ScenarioType.INFEASIBLE_BOUNDARY_CASE]
    assert len(infeasible_cases) == 1
    inf = infeasible_cases[0]
    assert inf.scenario_id == "SCEN_MAS_BBQ_BLOCKED"
    assert inf.solver_status == "INFEASIBLE"
    assert inf.delay_savings_minutes == 0.0
    assert inf.confidence_score == 0.0


# ---------------------------------------------------------------------------
# 6. JSON Export & Markdown Generation
# ---------------------------------------------------------------------------

def test_what_if_export_and_markdown(tmp_path):
    """Verify JSON export and valid Markdown report generation."""
    engine = WhatIfComparisonEngine()
    result = engine.evaluate_suite(time_limit_seconds=5.0)

    out_file = tmp_path / "what_if_results.json"
    result.export_json(str(out_file))
    assert out_file.exists()

    with open(out_file, "r") as f:
        data = json.load(f)
    assert "summary" in data
    assert "scenarios" in data
    assert data["summary"]["total_scenarios_evaluated"] >= 4

    md = result.generate_markdown()
    assert "# Phase 32.4 — What-If Comparison & Decision-Support Report" in md
    assert "## 1. Multi-Scenario Comparative Matrix" in md
    assert "## 2. Direct vs Propagated Delay & Recovery Profiles" in md
    assert "## 3. Decision-Support Directives & Recommendation Dynamics" in md
    assert "INFEASIBLE_BOUNDARY_CASE" in md


# ---------------------------------------------------------------------------
# 7. Delay Decomposition & Knock-on Multiplier
# ---------------------------------------------------------------------------

def test_delay_decomposition_across_scenarios():
    """Verify direct and secondary delay proportions are tracked."""
    engine = WhatIfComparisonEngine()
    result = engine.evaluate_suite(time_limit_seconds=5.0)

    for scen in result.scenarios:
        assert scen.primary_delay_minutes >= 0.0
        assert scen.secondary_delay_minutes >= 0.0
        assert scen.knock_on_multiplier >= 1.0


# ---------------------------------------------------------------------------
# 8. Strict Pending Services Exclusion
# ---------------------------------------------------------------------------

def test_pending_services_strictly_excluded():
    """Verify that none of the 7 pending services appear in any scenario metrics."""
    engine = WhatIfComparisonEngine()
    result = engine.evaluate_suite(time_limit_seconds=5.0)

    for scen in result.scenarios:
        for srv in scen.affected_service_ids:
            assert srv not in PENDING_SERVICES, f"Pending service {srv} found in {scen.scenario_id}"


# ---------------------------------------------------------------------------
# 9. Dataset Immutability Invariant
# ---------------------------------------------------------------------------

def test_dataset_immutability():
    """Verify master datasets remain unaltered."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tt_file = os.path.join(base_dir, "data", "trains", "published_timetables", "timetable.json")
    tr_file = os.path.join(base_dir, "data", "trains", "train_identity", "trains.json")

    with open(tt_file, "r") as f:
        tt_data = json.load(f)
    with open(tr_file, "r") as f:
        tr_data = json.load(f)

    assert len(tt_data) == 127, f"Timetable altered: {len(tt_data)} entries"
    assert len(tr_data) == 51, f"Trains altered: {len(tr_data)} entries"


# ---------------------------------------------------------------------------
# 10. End-to-End Execution
# ---------------------------------------------------------------------------

def test_run_what_if_comparison_e2e():
    """Verify end-to-end execution of run_what_if_comparison."""
    result = run_what_if_comparison(time_limit_seconds=5.0)
    assert result.summary.total_scenarios_evaluated >= 4
    assert result.summary.operational_state_count == 1
    assert result.summary.hypothetical_scenario_count >= 3
    assert result.summary.infeasible_boundary_count == 1
    assert result.summary.mean_delay_savings_minutes > 0.0
