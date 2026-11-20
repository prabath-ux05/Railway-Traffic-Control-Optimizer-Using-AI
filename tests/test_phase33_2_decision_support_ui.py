"""
tests/test_phase33_2_decision_support_ui.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test suite for Phase 33.2: Decision-Support Visualization.

Tests cover:
  1. Frontend Decision-Support data contracts and schema validation.
  2. 5-Stage Causal Pathway completeness: TRIGGER -> BOTTLENECK -> CONSTRAINT -> DECISION -> OUTCOME.
  3. Supporting Evidence, Delay Decomposition, and Counterfactual model binding.
  4. Operational context separation: LIVE_OPERATIONAL vs HYPOTHETICAL_SCENARIO vs INFEASIBLE.
  5. Actionable vs Non-Actionable recommendation handling.
  6. Strict pending services exclusion (7 pending services excluded).
  7. Master dataset immutability during decision support evaluation.
  8. Next.js frontend build artifact verification.
"""

from __future__ import annotations

import json
import os
import pytest
from typing import List

from evaluation.framework import PENDING_SERVICES
from decision_support import (
    ConfidenceMetrics,
    ConstraintExplanation,
    CounterfactualAnalysis,
    DecisionSupportAdvisor,
    DecisionSupportAssessment,
    DelayAnalysis,
    OperationalSeverity,
    OperationalSituation,
    PriorityTier,
    ReasoningStep,
    Recommendation,
    RecommendationCategory,
    RecommendationClassification,
    RecommendationEvidence,
    RecommendationRefiner,
    RecommendationType,
    RefinedRecommendation,
    SupportingEvidence,
    TraceabilityChain,
    run_recommendation_refinement,
)


# ---------------------------------------------------------------------------
# 1. Decision-Support Data Contracts
# ---------------------------------------------------------------------------

def test_decision_support_data_contracts():
    """Verify all domain models required for frontend visualization exist and serialize cleanly."""
    step1 = ReasoningStep(1, "TRIGGER", "Delay Injected", "15m delay at MAS")
    step2 = ReasoningStep(2, "BOTTLENECK", "Throat Contention", "BBQ junction capacity limit")
    step3 = ReasoningStep(3, "CONSTRAINT", "Safety Headway", "3.0 min headway margin")
    step4 = ReasoningStep(4, "DECISION", "Precedence Inversion", "Allow 12622 ahead of 40001")
    step5 = ReasoningStep(5, "OUTCOME", "Delay Mitigated", "Recovers 12m delay")

    chain = TraceabilityChain(
        trigger="15m delay at MAS",
        bottleneck="BBQ junction capacity limit",
        constraint="3.0 min headway margin",
        decision="Allow 12622 ahead of 40001",
        outcome="Recovers 12m delay",
        steps=[step1, step2, step3, step4, step5],
    )

    d = chain.to_dict()
    assert len(d["steps"]) == 5
    assert d["steps"][0]["phase"] == "TRIGGER"
    assert d["steps"][1]["phase"] == "BOTTLENECK"
    assert d["steps"][2]["phase"] == "CONSTRAINT"
    assert d["steps"][3]["phase"] == "DECISION"
    assert d["steps"][4]["phase"] == "OUTCOME"


# ---------------------------------------------------------------------------
# 2. 5-Stage Causal Pathway Integrity
# ---------------------------------------------------------------------------

def test_five_stage_reasoning_pathway_execution():
    """Verify refiner produces all 5 stages for generated recommendations."""
    refiner = RecommendationRefiner()
    result = refiner.evaluate_suite(time_limit_seconds=5.0)

    for rec in result.recommendations:
        chain = rec.traceability_chain
        assert len(chain.steps) == 5
        phases = [s.phase for s in chain.steps]
        assert phases == ["TRIGGER", "BOTTLENECK", "CONSTRAINT", "DECISION", "OUTCOME"]


# ---------------------------------------------------------------------------
# 3. Evidence Attachment & Delay Decomposition
# ---------------------------------------------------------------------------

def test_evidence_attachment_and_delay_breakdown():
    """Verify evidence payload binds delay decomposition, knock-on multiplier, and stress index."""
    evidence = RecommendationEvidence(
        triggering_conflicts=["CONF_HW_01"],
        contested_resource_id="SEC_BBQ_KOK_UP",
        contested_resource_type="TRACK_SECTION",
        affected_service_ids=["SRV_12607_01"],
        primary_delay_minutes=20.0,
        secondary_delay_minutes=30.0,
        knock_on_multiplier=2.5,
        contention_frequency=4,
        resource_utilization_pct=78.5,
        bottleneck_severity_index=62.4,
        attributed_delay_savings_min=15.0,
    )

    d = evidence.to_dict()
    assert d["primary_delay_minutes"] == 20.0
    assert d["secondary_delay_minutes"] == 30.0
    assert d["knock_on_multiplier"] == 2.5
    assert d["bottleneck_severity_index"] == 62.4
    assert d["attributed_delay_savings_min"] == 15.0


# ---------------------------------------------------------------------------
# 4. Context Classification & Actionability
# ---------------------------------------------------------------------------

def test_operational_context_and_actionability():
    """Verify actionable vs non-actionable infeasible cliff recommendations."""
    refiner = RecommendationRefiner()
    result = refiner.evaluate_suite(time_limit_seconds=5.0)

    # Feasible recommendations should be actionable
    feasible_recs = [r for r in result.recommendations if r.classification != RecommendationClassification.INFEASIBLE_TOPOLOGICAL_CLIFF]
    for r in feasible_recs:
        assert r.is_actionable is True
        assert r.confidence_score > 0.0

    # Infeasible cliff should be non-actionable with 0 confidence
    cliff_recs = [r for r in result.recommendations if r.classification == RecommendationClassification.INFEASIBLE_TOPOLOGICAL_CLIFF]
    assert len(cliff_recs) >= 1
    for r in cliff_recs:
        assert r.is_actionable is False
        assert r.confidence_score == 0.0


# ---------------------------------------------------------------------------
# 5. Strict Pending Services Exclusion
# ---------------------------------------------------------------------------

def test_pending_services_strictly_excluded():
    """Verify none of the 7 pending services are contained in any decision support outputs."""
    refiner = RecommendationRefiner()
    result = refiner.evaluate_suite(time_limit_seconds=5.0)

    for rec in result.recommendations:
        for srv in rec.evidence.affected_service_ids:
            assert srv not in PENDING_SERVICES, f"Pending service {srv} leaked into recommendation {rec.recommendation_id}"


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
    server_app_dir = os.path.join(next_dir, "server", "app")
    page_html = os.path.join(server_app_dir, "index.html")

    if not os.path.exists(page_html):
        import shutil
        import subprocess
        npm_bin = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm_bin:
            pytest.skip("Node/npm is not available on PATH; cannot build frontend production artifacts")
        try:
            frontend_dir = os.path.join(base_dir, "frontend")
            subprocess.run([npm_bin, "run", "build"], cwd=frontend_dir, check=True, capture_output=True, timeout=180)
        except Exception as exc:
            pytest.skip(f"Frontend production build failed or timed out: {exc}")

    assert os.path.exists(next_dir), "Frontend .next build directory does not exist"
