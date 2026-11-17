"""
tests/test_phase32_3_recommendations.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test suite for Phase 32.3: Recommendation & Evidence Refinement.

Tests cover:
  1. Module exports and accessibility of all Phase 32.3 symbols.
  2. TraceabilityChain 5-stage causal structure and serialization.
  3. RecommendationEvidence attribute integrity, delay decomposition, and serialization.
  4. Deterministic priority and confidence score calculations (bounded, reproducible, 0% LLM).
  5. Operational classification: INFRASTRUCTURE_BOTTLENECK vs TRANSIENT_DISRUPTION vs INFEASIBLE_TOPOLOGICAL_CLIFF.
  6. RefinedRecommendation markdown formatting and JSON conversion.
  7. RefinementAnalyticsResult summary statistics and artifact generation.
  8. Boundary isolation of the MAS-BBQ throat single-point-of-failure cliff.
  9. Strict pending services exclusion invariant (7 pending services excluded).
  10. Master dataset immutability invariant.
  11. End-to-end execution of RecommendationRefiner.
"""

from __future__ import annotations

import json
import os
import pytest
from typing import List

from evaluation.framework import PENDING_SERVICES
from decision_support import (
    PriorityTier,
    RecommendationClassification,
    RecommendationEvidence,
    RecommendationRefiner,
    RecommendationType,
    RefinedRecommendation,
    RefinementAnalyticsResult,
    RefinementSummary,
    TraceabilityChain,
    TraceabilityPhase,
    run_recommendation_refinement,
)


# ---------------------------------------------------------------------------
# 1. Module Exports & Types
# ---------------------------------------------------------------------------

def test_phase32_3_exports():
    """Verify all required Phase 32.3 symbols are exported by decision_support."""
    import decision_support
    expected_exports = [
        "RecommendationClassification",
        "RecommendationEvidence",
        "RecommendationRefiner",
        "RefinedRecommendation",
        "RefinementAnalyticsResult",
        "RefinementSummary",
        "TraceabilityChain",
        "TraceabilityPhase",
        "run_recommendation_refinement",
    ]
    for symbol in expected_exports:
        assert hasattr(decision_support, symbol), f"decision_support missing export: {symbol}"


# ---------------------------------------------------------------------------
# 2. 5-Stage Traceability Chain Structure
# ---------------------------------------------------------------------------

def test_traceability_chain_structure():
    """Verify 5-stage causal chain: TRIGGER -> BOTTLENECK -> CONSTRAINT -> DECISION -> OUTCOME."""
    chain = TraceabilityChain(
        trigger="Primary late departure of 15m on SRV_12622_01",
        bottleneck="Junction J_BBQ crossing contention",
        constraint="Headway margin 3.0 min; single occupancy block",
        decision="Hold suburban train SRV_40001_01 for 4 minutes",
        outcome="Recovers 12m secondary delay across 2 following services",
    )
    d = chain.to_dict()
    assert d["trigger"].startswith("Primary late departure")
    assert d["bottleneck"].startswith("Junction J_BBQ")
    assert "Headway margin" in d["constraint"]
    assert "Hold suburban" in d["decision"]
    assert "Recovers 12m" in d["outcome"]

    # Verify Enum phases
    assert TraceabilityPhase.TRIGGER.value == "TRIGGER"
    assert TraceabilityPhase.BOTTLENECK.value == "BOTTLENECK"
    assert TraceabilityPhase.CONSTRAINT.value == "CONSTRAINT"
    assert TraceabilityPhase.DECISION.value == "DECISION"
    assert TraceabilityPhase.OUTCOME.value == "OUTCOME"


# ---------------------------------------------------------------------------
# 3. Evidence Model Attachment
# ---------------------------------------------------------------------------

def test_recommendation_evidence_attachment():
    """Verify evidence model binds conflicts, resources, delay breakdown, and stress metrics."""
    evidence = RecommendationEvidence(
        triggering_conflicts=["CONF_HW_001", "CONF_JCT_002"],
        contested_resource_id="SEC_BBQ_KOK_UP",
        contested_resource_type="TRACK_SECTION",
        affected_service_ids=["SRV_12622_01", "SRV_40001_01"],
        primary_delay_minutes=15.0,
        secondary_delay_minutes=25.5,
        knock_on_multiplier=1.70,
        contention_frequency=5,
        resource_utilization_pct=78.5,
        bottleneck_severity_index=62.4,
        attributed_delay_savings_min=18.0,
    )
    d = evidence.to_dict()
    assert d["contested_resource_id"] == "SEC_BBQ_KOK_UP"
    assert d["primary_delay_minutes"] == 15.0
    assert d["secondary_delay_minutes"] == 25.5
    assert d["knock_on_multiplier"] == 1.70
    assert d["resource_utilization_pct"] == 78.5
    assert d["bottleneck_severity_index"] == 62.4
    assert d["attributed_delay_savings_min"] == 18.0


# ---------------------------------------------------------------------------
# 4. Deterministic Scoring Formulas
# ---------------------------------------------------------------------------

def test_deterministic_scoring_math():
    """Verify priority score and confidence score are deterministic, explainable, and bounded."""
    refiner = RecommendationRefiner()

    # Priority score test
    score_crit = refiner.compute_priority_score(
        tier=PriorityTier.CRITICAL,
        delay_savings=20.0,
        affected_services=["SRV_1", "SRV_2"],
        knock_on_multiplier=2.0,
        contention_freq=4,
        utilization_pct=80.0,
    )
    # Expected: 40 (base) + 10 (savings) + 4 (services) + 5 (knock-on) + 4 (contention) + 8 (util) = 71.0
    assert score_crit == pytest.approx(71.0, rel=1e-2)

    score_low = refiner.compute_priority_score(
        tier=PriorityTier.LOW,
        delay_savings=0.0,
        affected_services=["SRV_1"],
        knock_on_multiplier=1.0,
        contention_freq=0,
        utilization_pct=20.0,
    )
    # Expected: 10 + 0 + 2 + 0 + 0 + 2 = 14.0
    assert score_low == pytest.approx(14.0, rel=1e-2)

    # Confidence score test (bounded [0.0, 1.0])
    conf_optimal = refiner.compute_confidence_score(
        solver_status="OPTIMAL",
        is_actionable=True,
        has_bottleneck_evidence=True,
        has_propagation_evidence=True,
        constraints_verified_count=5,
    )
    assert 0.95 <= conf_optimal <= 1.0

    conf_infeasible = refiner.compute_confidence_score(
        solver_status="INFEASIBLE",
        is_actionable=False,
        has_bottleneck_evidence=True,
        has_propagation_evidence=True,
        constraints_verified_count=5,
    )
    assert conf_infeasible == 0.0


# ---------------------------------------------------------------------------
# 5. Operational Classification
# ---------------------------------------------------------------------------

def test_operational_classification():
    """Verify correct classification into infrastructure, transient, or infeasible cliff."""
    refiner = RecommendationRefiner()

    c1 = refiner.classify_context(
        scenario_id="SCEN_PEAK_01",
        resource_id="SEC_BBQ_KOK_UP",
        utilization_pct=75.0,
        solver_status="OPTIMAL",
    )
    assert c1 == RecommendationClassification.INFRASTRUCTURE_BOTTLENECK

    c2 = refiner.classify_context(
        scenario_id="SCEN_LATE_12607",
        resource_id="SEC_AVD_TRL_DOWN",
        utilization_pct=40.0,
        solver_status="OPTIMAL",
    )
    assert c2 == RecommendationClassification.TRANSIENT_DISRUPTION

    c3 = refiner.classify_context(
        scenario_id="SCEN_MAS_BBQ_THROAT_DOWN",
        resource_id="MAS_BBQ_THROAT_SEGMENT_DOWN",
        utilization_pct=100.0,
        solver_status="INFEASIBLE",
    )
    assert c3 == RecommendationClassification.INFEASIBLE_TOPOLOGICAL_CLIFF


# ---------------------------------------------------------------------------
# 6. Refined Recommendation Formatting & Serialization
# ---------------------------------------------------------------------------

def test_refined_recommendation_serialization():
    """Verify RefinedRecommendation converts cleanly to dict and markdown."""
    chain = TraceabilityChain(
        trigger="Late arrival of EXP_12622",
        bottleneck="J_BBQ interlocking throat",
        constraint="Headway 3.0 min",
        decision="Invert precedence at BBQ",
        outcome="Saves 14.5m delay",
    )
    evidence = RecommendationEvidence(
        triggering_conflicts=["CONF_1"],
        contested_resource_id="J_BBQ",
        contested_resource_type="JUNCTION",
        affected_service_ids=["SRV_12622_01", "SRV_40001_01"],
        primary_delay_minutes=10.0,
        secondary_delay_minutes=15.0,
        knock_on_multiplier=1.5,
        contention_frequency=3,
        resource_utilization_pct=82.0,
        bottleneck_severity_index=68.5,
        attributed_delay_savings_min=14.5,
    )
    rec = RefinedRecommendation(
        recommendation_id="REC_TEST_01",
        scenario_id="SCEN_TEST",
        title="Advance Superfast 12622 at Basin Bridge",
        recommendation_type=RecommendationType.PRECEDENCE_OVERRIDE,
        category="precedence change",
        classification=RecommendationClassification.INFRASTRUCTURE_BOTTLENECK,
        priority_tier=PriorityTier.HIGH,
        priority_score=55.2,
        confidence_score=0.98,
        traceability_chain=chain,
        evidence=evidence,
        baseline_delay_minutes=25.0,
        expected_delay_minutes=10.5,
        expected_delay_savings=14.5,
        action_details={"lead": "SRV_12622_01", "follow": "SRV_40001_01"},
        is_actionable=True,
        solver_status="OPTIMAL",
    )

    d = rec.to_dict()
    assert d["recommendation_id"] == "REC_TEST_01"
    assert d["classification"] == "INFRASTRUCTURE_BOTTLENECK"
    assert d["expected_delay_savings"] == 14.5

    md = rec.to_markdown()
    assert "REC_TEST_01" in md
    assert "TRIGGER" in md
    assert "BOTTLENECK" in md
    assert "CONSTRAINT" in md
    assert "DECISION" in md
    assert "OUTCOME" in md


# ---------------------------------------------------------------------------
# 7. Summary & Analytics Result
# ---------------------------------------------------------------------------

def test_analytics_result_and_report_generation(tmp_path):
    """Verify RefinementAnalyticsResult exports JSON and generates valid Markdown."""
    summary = RefinementSummary(
        total_recommendations=5,
        infrastructure_bottleneck_count=3,
        transient_disruption_count=1,
        infeasible_cliff_count=1,
        total_delay_savings_minutes=65.5,
        mean_confidence_score=0.82,
        mean_priority_score=48.5,
    )
    res = RefinementAnalyticsResult(
        timestamp="2026-09-20T14:30:00Z",
        recommendations=[],
        summary=summary,
        scenario_evaluations={},
    )
    out_file = tmp_path / "refined_recommendations.json"
    res.export_json(str(out_file))
    assert out_file.exists()

    with open(out_file, "r") as f:
        data = json.load(f)
    assert data["summary"]["total_recommendations"] == 5
    assert data["summary"]["infrastructure_bottleneck_count"] == 3

    md = res.generate_markdown()
    assert "# Phase 32.3 — Recommendation & Evidence Refinement Report" in md
    assert "INFRASTRUCTURE_BOTTLENECK" in md
    assert "INFEASIBLE_TOPOLOGICAL_CLIFF" in md


# ---------------------------------------------------------------------------
# 8. Boundary Infeasible Isolation
# ---------------------------------------------------------------------------

def test_infeasible_cliff_isolated():
    """Verify MAS_BBQ_THROAT_SEGMENT_DOWN blockage is isolated as an unresolvable topological cliff."""
    refiner = RecommendationRefiner()
    result = refiner.evaluate_suite(time_limit_seconds=5.0)

    # Find cliff recommendation
    cliff_recs = [r for r in result.recommendations if r.classification == RecommendationClassification.INFEASIBLE_TOPOLOGICAL_CLIFF]
    assert len(cliff_recs) >= 1
    cliff = cliff_recs[0]
    assert cliff.is_actionable is False
    assert cliff.confidence_score == 0.0
    assert cliff.expected_delay_savings == 0.0
    assert "MAS_BBQ_THROAT_SEGMENT_DOWN" in cliff.evidence.contested_resource_id or "MAS" in cliff.title


# ---------------------------------------------------------------------------
# 9. Strict Pending Services Exclusion
# ---------------------------------------------------------------------------

def test_pending_services_strictly_excluded():
    """Verify that none of the 7 pending services appear in any refined recommendations."""
    refiner = RecommendationRefiner()
    result = refiner.evaluate_suite(time_limit_seconds=5.0)

    for rec in result.recommendations:
        for srv in rec.evidence.affected_service_ids:
            assert srv not in PENDING_SERVICES, f"Pending service {srv} found in {rec.recommendation_id}"


# ---------------------------------------------------------------------------
# 10. Master Dataset Immutability
# ---------------------------------------------------------------------------

def test_dataset_immutability():
    """Verify master train and timetable datasets remain unaltered."""
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
# 11. End-to-End Suite Execution
# ---------------------------------------------------------------------------

def test_run_recommendation_refinement_e2e():
    """Verify end-to-end execution of run_recommendation_refinement."""
    result = run_recommendation_refinement(time_limit_seconds=5.0)
    assert result.summary.total_recommendations > 0
    assert result.summary.total_delay_savings_minutes > 0.0
    assert 0.0 <= result.summary.mean_confidence_score <= 1.0
    assert result.summary.infrastructure_bottleneck_count >= 1
    assert result.summary.infeasible_cliff_count >= 1
