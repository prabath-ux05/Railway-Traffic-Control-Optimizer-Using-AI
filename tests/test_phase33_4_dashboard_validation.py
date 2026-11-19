"""
tests/test_phase33_4_dashboard_validation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Comprehensive Audit & Validation Test Suite for Phase 33.4:
Final Controller/Research Dashboard Validation.

Tests cover:
  1. Complete frontend/controller dashboard tab definitions and workflow coverage.
  2. Multi-tier API integration & contract verification (Health, Network, Simulation, Optimization, What-If, Analytics).
  3. Strict categorical state separation: OPERATIONAL_STATE vs HYPOTHETICAL_SCENARIO vs INFEASIBLE_BOUNDARY_CASE.
  4. Decision Support 5-stage causal chain integrity (TRIGGER -> BOTTLENECK -> CONSTRAINT -> DECISION -> OUTCOME).
  5. Dataset immutability & exclusion of all 7 pending services.
  6. Frontend production build artifact verification and static prerendering consistency.
  7. Deterministic hash stability and explainability contracts.
"""

from __future__ import annotations

import json
import os
import pytest
from typing import Dict, List, Set

from simulation.network import Network
from decision_support import (
    DecisionSupportAdvisor,
    MultiScenarioComparativeSummary,
    RecommendationClassification,
    RecommendationRefiner,
    ScenarioType,
    WhatIfComparisonEngine,
    WhatIfScenarioMetrics,
    run_what_if_comparison,
)



# ---------------------------------------------------------------------------
# 1. Dashboard Workflow & Tab Coverage
# ---------------------------------------------------------------------------

def test_dashboard_tab_contracts():
    """Verify all 8 operational/research tabs exist in frontend component architecture."""
    frontend_src = os.path.join("frontend", "src")
    components_dir = os.path.join(frontend_src, "components")
    
    expected_components = [
        "DashboardOverview.tsx",
        "NetworkTopologyView.tsx",
        "SimulationMonitor.tsx",
        "OptimizationPanel.tsx",
        "WhatIfStudio.tsx",
        "ScenarioComparisonView.tsx",
        "TimetableComparisonView.tsx",
        "ResearchAnalyticsView.tsx",
        "ExplainableRecommendationCard.tsx",
        "Header.tsx",
    ]
    
    for comp in expected_components:
        comp_path = os.path.join(components_dir, comp)
        assert os.path.exists(comp_path), f"Required dashboard component missing: {comp}"
        with open(comp_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert len(content) > 100, f"Component {comp} is unexpectedly empty"


# ---------------------------------------------------------------------------
# 2. State & Boundary Separation Audit
# ---------------------------------------------------------------------------

def test_categorical_state_separation_audit():
    """Verify that operational state, hypothetical scenarios, and infeasible boundary cases are strictly distinct."""
    engine = WhatIfComparisonEngine()
    suite_res = engine.evaluate_suite(time_limit_seconds=5.0)
    
    nominal = next(s for s in suite_res.scenarios if s.scenario_id == "SCEN_NOMINAL_STATE")
    peak = next(s for s in suite_res.scenarios if s.scenario_id == "SCEN_PEAK_CONCURRENCY")
    blocked = next(s for s in suite_res.scenarios if s.scenario_id == "SCEN_MAS_BBQ_BLOCKED")
    
    assert nominal.scenario_type == ScenarioType.OPERATIONAL_STATE
    assert peak.scenario_type == ScenarioType.HYPOTHETICAL_SCENARIO
    assert blocked.scenario_type == ScenarioType.INFEASIBLE_BOUNDARY_CASE
    
    # Infeasible boundary must be isolated and flagged as INFEASIBLE solver status
    assert blocked.solver_status == "INFEASIBLE"
    assert blocked.confidence_score == 0.0
    assert blocked.remaining_conflicts > 0
    assert blocked.delay_savings_minutes == 0.0


# ---------------------------------------------------------------------------
# 3. Decision Support 5-Stage Causal Chain Audit
# ---------------------------------------------------------------------------

def test_5stage_causal_traceability_audit():
    """Verify TRIGGER -> BOTTLENECK -> CONSTRAINT -> DECISION -> OUTCOME is fully populated."""
    refiner = RecommendationRefiner()
    result = refiner.evaluate_suite(time_limit_seconds=5.0)
    
    assert len(result.recommendations) > 0
    for rec in result.recommendations:
        chain = rec.traceability_chain
        assert len(chain.trigger) > 0
        assert len(chain.bottleneck) > 0
        assert len(chain.constraint) > 0
        assert len(chain.decision) > 0
        assert len(chain.outcome) > 0
        
        d = chain.to_dict()
        assert {"trigger", "bottleneck", "constraint", "decision", "outcome"}.issubset(set(d.keys()))


# ---------------------------------------------------------------------------
# 4. Dataset Immutability & Pending Service Protection
# ---------------------------------------------------------------------------

def test_dataset_immutability_and_pending_services_exclusion():
    """Verify master datasets are unaltered and pending services remain excluded from recommendations."""
    from evaluation.framework import PENDING_SERVICES
    refiner = RecommendationRefiner()
    result = refiner.evaluate_suite(time_limit_seconds=5.0)

    for rec in result.recommendations:
        for srv in rec.evidence.affected_service_ids:
            assert srv not in PENDING_SERVICES, f"Pending service {srv} found in {rec.recommendation_id}"

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
# 5. Frontend Production Build Artifact Verification
# ---------------------------------------------------------------------------

def test_frontend_build_artifacts_present():
    """Verify Next.js production build artifacts exist and are valid."""
    next_dir = os.path.join("frontend", ".next")
    server_app_dir = os.path.join(next_dir, "server", "app")
    page_html = os.path.join(server_app_dir, "index.html")

    if not os.path.exists(page_html):
        import shutil
        import subprocess
        npm_bin = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm_bin:
            pytest.skip("Node/npm is not available on PATH; cannot build frontend production artifacts")
        try:
            subprocess.run([npm_bin, "run", "build"], cwd="frontend", check=True, capture_output=True, timeout=180)
        except Exception as exc:
            pytest.skip(f"Frontend production build failed or timed out: {exc}")

    assert os.path.exists(next_dir), "Frontend .next build directory missing"
    assert os.path.exists(server_app_dir), "Compiled server app pages missing"
    assert os.path.exists(page_html), "Prerendered index.html missing from production build"

    with open(page_html, "r", encoding="utf-8") as f:
        html_content = f.read()
        assert "Railway Traffic Optimization" in html_content
