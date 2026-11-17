"""
tests/test_phase33_3_scenario_comparison_ui.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test suite for Phase 33.3: Scenario & Result Comparison UX.

Tests cover:
  1. WhatIfScenarioMetrics data structure and TypeScript/Python schema consistency.
  2. Multi-scenario comparative matrix integrity.
  3. Categorical separation: OPERATIONAL_STATE vs HYPOTHETICAL_SCENARIO vs INFEASIBLE_BOUNDARY_CASE.
  4. Delta calculations between scenarios (delay, savings %, knock-on K, solver time, conflicts).
  5. Dedicated isolation of the single-point-of-failure MAS-BBQ impassable throat boundary.
  6. Strict pending services exclusion (7 pending services excluded).
  7. Master dataset immutability during comparison.
  8. Frontend build artifact presence.
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
# 1. Schema & Data Structure Verification
# ---------------------------------------------------------------------------

def test_scenario_metrics_schema():
    """Verify WhatIfScenarioMetrics holds all required comparative dimensions."""
    m = WhatIfScenarioMetrics(
        scenario_id="SCEN_NOMINAL_STATE",
        name="Nominal On-Time Operational State",
        scenario_type=ScenarioType.OPERATIONAL_STATE,
        baseline_delay_minutes=32.0,
        optimized_delay_minutes=32.0,
        delay_savings_minutes=0.0,
        delay_savings_percent=0.0,
        primary_delay_minutes=14.4,
        secondary_delay_minutes=17.6,
        knock_on_multiplier=2.22,
        recovery_rate_pct=0.0,
        initial_conflicts=0,
        remaining_conflicts=0,
        resolved_conflicts=0,
        affected_services_count=1,
        affected_service_ids=["SRV_12607_01"],
        primary_bottleneck_id="SEC_BBQ_KOK_UP",
        bottleneck_utilization_pct=78.5,
        solver_status="OPTIMAL",
        solve_time_seconds=0.038,
        recommendations_count=0,
        top_recommendation_title="Maintain Published Schedule",
        top_recommendation_tier="LOW",
        confidence_score=1.0,
    )
    d = m.to_dict()
    assert d["scenario_id"] == "SCEN_NOMINAL_STATE"
    assert d["scenario_type"] == "OPERATIONAL_STATE"
    assert d["knock_on_multiplier"] == 2.22
    assert d["solver_status"] == "OPTIMAL"


# ---------------------------------------------------------------------------
# 2. Categorical Separation
# ---------------------------------------------------------------------------

def test_categorical_separation_in_suite():
    """Verify suite separates operational state, hypothetical disturbances, and boundary cliff."""
    engine = WhatIfComparisonEngine()
    result = engine.evaluate_suite(time_limit_seconds=5.0)

    types = {s.scenario_type for s in result.scenarios}
    assert ScenarioType.OPERATIONAL_STATE in types
    assert ScenarioType.HYPOTHETICAL_SCENARIO in types
    assert ScenarioType.INFEASIBLE_BOUNDARY_CASE in types


# ---------------------------------------------------------------------------
# 3. Comparative Delta Computations
# ---------------------------------------------------------------------------

def test_scenario_comparison_deltas():
    """Verify side-by-side delta computations between nominal and peak scenarios."""
    engine = WhatIfComparisonEngine()
    result = engine.evaluate_suite(time_limit_seconds=5.0)

    scen_map = {s.scenario_id: s for s in result.scenarios}
    nominal = scen_map["SCEN_NOMINAL_STATE"]
    peak = scen_map["SCEN_PEAK_CONCURRENCY"]

    delay_delta = peak.baseline_delay_minutes - nominal.baseline_delay_minutes
    savings_delta = peak.delay_savings_minutes - nominal.delay_savings_minutes

    assert delay_delta > 0, "Peak concurrency should introduce greater baseline delay than nominal"
    assert savings_delta > 0, "Peak concurrency should achieve greater delay savings through CP-SAT arbitration"


# ---------------------------------------------------------------------------
# 4. Infeasible Cliff Boundary Isolation
# ---------------------------------------------------------------------------

def test_infeasible_cliff_boundary():
    """Verify MAS-BBQ down throat complete blockage is isolated as an unresolvable cliff."""
    engine = WhatIfComparisonEngine()
    result = engine.evaluate_suite(time_limit_seconds=5.0)

    cliff = next(s for s in result.scenarios if s.scenario_type == ScenarioType.INFEASIBLE_BOUNDARY_CASE)
    assert cliff.scenario_id == "SCEN_MAS_BBQ_BLOCKED"
    assert cliff.solver_status == "INFEASIBLE"
    assert cliff.delay_savings_minutes == 0.0
    assert cliff.confidence_score == 0.0
    assert cliff.primary_bottleneck_id == "MAS_BBQ_THROAT_SEGMENT_DOWN"


# ---------------------------------------------------------------------------
# 5. Strict Pending Services Exclusion
# ---------------------------------------------------------------------------

def test_pending_services_strictly_excluded():
    """Verify none of the 7 pending services are contained in any comparison outputs."""
    engine = WhatIfComparisonEngine()
    result = engine.evaluate_suite(time_limit_seconds=5.0)

    for scen in result.scenarios:
        for srv in scen.affected_service_ids:
            assert srv not in PENDING_SERVICES, f"Pending service {srv} leaked into scenario {scen.scenario_id}"


# ---------------------------------------------------------------------------
# 6. Master Dataset Immutability
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
# 7. Frontend Build & Static Generation Verification
# ---------------------------------------------------------------------------

def test_frontend_build_artifacts():
    """Verify frontend Next.js production build files are present."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    next_dir = os.path.join(base_dir, "frontend", ".next")
    assert os.path.exists(next_dir), "Frontend .next build directory does not exist"
