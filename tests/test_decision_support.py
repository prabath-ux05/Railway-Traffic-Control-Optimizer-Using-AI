"""
tests/test_decision_support.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Comprehensive unit and integration test suite for Batch 18:
Dynamic Decision-Support Layer Foundation.

Validates:
1. Operational situation assessment and severity tiering.
2. Deterministic conflict prioritization and scoring.
3. Dynamic bottleneck identification (junction vs platform vs track section vs station).
4. Service delay-impact analysis (direct vs propagated secondary delay).
5. Recommendation synthesis, ranking, and evidence basis (zero hallucination).
6. What-If scenario decision support with feasible baseline vs CP-SAT comparison.
7. Controller-oriented situation summary, Markdown/ASCII generation, and deterministic repeatability.
"""

import pytest

from decision_support import (
    BaselineOptimizationComparison,
    ContestedBottleneck,
    DecisionSupportAdvisor,
    DecisionSupportAssessment,
    OperationalSeverity,
    OperationalSituation,
    PrioritizedConflict,
    PriorityTier,
    Recommendation,
    RecommendationType,
    ServiceDelayImpact,
)
from optimization.scenarios import Scenario
from simulation.conflicts import Conflict, ConflictSeverity, ConflictType
from simulation.network import Network
from simulation.state import SimulationState


@pytest.fixture(scope="module")
def advisor() -> DecisionSupportAdvisor:
    return DecisionSupportAdvisor()


# ---------------------------------------------------------------------------
# 1. Operational Situation Assessment Tests
# ---------------------------------------------------------------------------

class TestOperationalSituationAssessment:
    """Verify situational awareness and severity tiering from simulation state."""

    def test_clean_state_situation_is_normal(self, advisor: DecisionSupportAdvisor):
        state = SimulationState()
        state.initialize_from_network(advisor.network)

        situation = advisor.assess_current_state(state)
        assert situation.severity == OperationalSeverity.NORMAL
        assert situation.total_active_delay_minutes == 0.0
        assert len(situation.active_conflicts) == 0
        assert situation.delayed_train_count == 0

    def test_disrupted_state_escalates_severity(self, advisor: DecisionSupportAdvisor):
        state = SimulationState()
        state.initialize_from_network(advisor.network)

        # Inject delay on a train state
        train_st = state.get_train_state("SRV_12607_01")
        train_st.record_delay(35.0)

        situation = advisor.assess_current_state(state)
        assert situation.severity in (OperationalSeverity.WARNING, OperationalSeverity.CRITICAL)
        assert situation.total_active_delay_minutes >= 35.0
        assert situation.peak_delay_minutes == 35.0
        assert situation.peak_delay_service == "SRV_12607_01"
        assert "SRV_12607_01" in situation.affected_services

    def test_situation_to_dict_format(self, advisor: DecisionSupportAdvisor):
        state = SimulationState()
        state.initialize_from_network(advisor.network)
        situation = advisor.assess_current_state(state)

        d = situation.to_dict()
        assert "timestamp" in d
        assert "timestamp_str" in d
        assert "severity" in d
        assert "active_train_count" in d
        assert "total_active_delay_minutes" in d


# ---------------------------------------------------------------------------
# 2. Conflict Prioritization Tests
# ---------------------------------------------------------------------------

class TestConflictPrioritization:
    """Verify deterministic ranking and scoring of traffic conflicts."""

    def test_classify_resource_types(self, advisor: DecisionSupportAdvisor):
        assert advisor.classify_resource("JCT_BBQ") == "JUNCTION"
        assert advisor.classify_resource("MAS_P1") == "PLATFORM"
        assert advisor.classify_resource("PLAT_AJJ_02") == "PLATFORM"
        assert advisor.classify_resource("SEC_BBQ_KOK") == "TRACK_SECTION"
        assert advisor.classify_resource("NEC_PAB_SUBURBAN_UP") == "TRACK_SECTION"
        assert advisor.classify_resource("MAS") == "STATION"

    def test_conflict_prioritization_scores_and_ranks(self, advisor: DecisionSupportAdvisor):
        c1 = Conflict(
            conflict_id="CONF_001",
            conflict_type=ConflictType.INSUFFICIENT_HEADWAY,
            affected_service_ids=["SRV_43102_01", "SRV_43219_01"],
            affected_train_ids=["TR_43102", "TR_43219"],
            resource_id="SEC_MAS_BBQ",
            conflict_time=360.0,
            severity=ConflictSeverity.MINOR,
            description="Minor headway compression between suburban services",
        )
        c2 = Conflict(
            conflict_id="CONF_002",
            conflict_type=ConflictType.SHARED_JUNCTION,
            affected_service_ids=["SRV_12607_01", "SRV_12610_01"],
            affected_train_ids=["TR_12607", "TR_12610"],
            resource_id="JCT_BBQ",
            conflict_time=362.0,
            severity=ConflictSeverity.CRITICAL,
            description="Critical junction contention between superfast expresses",
        )

        prioritized = advisor.prioritize_conflicts([c1, c2])
        assert len(prioritized) == 2
        # Critical junction contention with superfast trains should rank first
        assert prioritized[0].conflict.conflict_id == "CONF_002"
        assert prioritized[0].resource_type == "JUNCTION"
        assert prioritized[0].priority_score > prioritized[1].priority_score
        assert "JCT_BBQ" in prioritized[0].ranking_explanation
        assert prioritized[0].involved_train_priorities["SRV_12607_01"] == "HIGH"


# ---------------------------------------------------------------------------
# 3. Bottleneck Identification Tests
# ---------------------------------------------------------------------------

class TestBottleneckIdentification:
    """Verify distinguishing junction, platform, track section, and station bottlenecks."""

    def test_distinguish_resource_types(self, advisor: DecisionSupportAdvisor):
        c_jct = Conflict(
            conflict_id="C_JCT",
            conflict_type=ConflictType.SHARED_JUNCTION,
            affected_service_ids=["SRV_43102_01", "SRV_12607_01"],
            affected_train_ids=["TR_43102", "TR_12607"],
            resource_id="JCT_PAB",
            conflict_time=370.0,
            severity=ConflictSeverity.MAJOR,
            description="Junction merge contention",
        )
        c_plat = Conflict(
            conflict_id="C_PLAT",
            conflict_type=ConflictType.SAME_TRACK_SECTION,
            affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
            affected_train_ids=["TR_12607", "TR_12609"],
            resource_id="MAS_P1",
            conflict_time=370.0,
            severity=ConflictSeverity.MAJOR,
            description="Platform track occupancy contention",
        )

        bottlenecks = advisor.identify_contested_bottlenecks(conflicts=[c_jct, c_plat])
        assert len(bottlenecks) == 2
        types = {b.resource_id: b.resource_type for b in bottlenecks}
        assert types["JCT_PAB"] == "JUNCTION"
        assert types["MAS_P1"] == "PLATFORM"

        # Verify criticality score is higher for junction than platform of equal contention
        jct_b = next(b for b in bottlenecks if b.resource_id == "JCT_PAB")
        plat_b = next(b for b in bottlenecks if b.resource_id == "MAS_P1")
        assert jct_b.criticality_score > plat_b.criticality_score


# ---------------------------------------------------------------------------
# 4. Service Delay-Impact Analysis Tests
# ---------------------------------------------------------------------------

class TestDelayImpactAnalysis:
    """Verify calculation of direct vs propagated delay per service."""

    def test_direct_vs_propagated_delay(self, advisor: DecisionSupportAdvisor):
        state = SimulationState()
        state.initialize_from_network(advisor.network)

        # Injected direct delay on train 12607: 15.0m; actual total delay: 22.0m (7.0m secondary propagation)
        st = state.get_train_state("SRV_12607_01")
        st.record_delay(22.0)

        impacts = advisor.analyze_service_delay_impacts(
            service_ids=["SRV_12607_01", "SRV_12609_01"],
            state=state,
            direct_delays={"SRV_12607_01": 15.0},
        )

        assert len(impacts) == 2
        imp_12607 = next(i for i in impacts if i.service_id == "SRV_12607_01")
        assert imp_12607.direct_delay_minutes == 15.0
        assert imp_12607.total_delay_minutes == 22.0
        assert imp_12607.propagated_delay_minutes == 7.0
        assert "Secondary propagated delay: +7.0m" in imp_12607.downstream_impact_summary

        imp_12609 = next(i for i in impacts if i.service_id == "SRV_12609_01")
        assert imp_12609.direct_delay_minutes == 0.0
        assert imp_12609.propagated_delay_minutes == 0.0
        assert imp_12609.total_delay_minutes == 0.0


# ---------------------------------------------------------------------------
# 5. Recommendation Synthesis & Ranking Tests
# ---------------------------------------------------------------------------

class TestRecommendationRanking:
    """Verify recommendation ranking by PriorityTier, delay savings, and confidence."""

    def test_normal_state_recommends_maintain_schedule(self, advisor: DecisionSupportAdvisor):
        state = SimulationState()
        state.initialize_from_network(advisor.network)
        situation = advisor.assess_current_state(state)

        recs = advisor.generate_recommendations(situation)
        assert len(recs) == 1
        rec = recs[0]
        assert rec.recommendation_type == RecommendationType.MAINTAIN_CURRENT_SCHEDULE
        assert rec.priority_tier == PriorityTier.LOW
        assert rec.is_actionable is False
        assert rec.expected_delay_savings == 0.0
        assert "tolerance" in rec.reason.lower()

    def test_recommendation_ranking_order(self):
        r_low = Recommendation(
            recommendation_id="REC_0001",
            recommendation_type=RecommendationType.MAINTAIN_CURRENT_SCHEDULE,
            title="Maintain Schedule",
            reason="Normal",
            affected_services=["S1"],
            affected_resources=[],
            priority_tier=PriorityTier.LOW,
            expected_delay_savings=0.0,
        )
        r_crit_small = Recommendation(
            recommendation_id="REC_0002",
            recommendation_type=RecommendationType.PRECEDENCE_OVERRIDE,
            title="Critical Small Savings",
            reason="Override",
            affected_services=["S2", "S3"],
            affected_resources=["JCT_BBQ"],
            priority_tier=PriorityTier.CRITICAL,
            expected_delay_savings=2.0,
        )
        r_crit_big = Recommendation(
            recommendation_id="REC_0003",
            recommendation_type=RecommendationType.PRECEDENCE_OVERRIDE,
            title="Critical Big Savings",
            reason="Override",
            affected_services=["S4", "S5"],
            affected_resources=["JCT_PAB"],
            priority_tier=PriorityTier.CRITICAL,
            expected_delay_savings=15.0,
        )
        r_high = Recommendation(
            recommendation_id="REC_0004",
            recommendation_type=RecommendationType.HOLD_AT_STATION,
            title="High Priority Hold",
            reason="Hold",
            affected_services=["S6"],
            affected_resources=["MAS"],
            priority_tier=PriorityTier.HIGH,
            expected_delay_savings=5.0,
        )

        tier_order = {PriorityTier.CRITICAL: 0, PriorityTier.HIGH: 1, PriorityTier.MEDIUM: 2, PriorityTier.LOW: 3}
        recs = [r_low, r_crit_small, r_high, r_crit_big]
        recs.sort(key=lambda r: (tier_order.get(r.priority_tier, 99), -r.expected_delay_savings, -r.confidence_score, r.recommendation_id))

        # Expected: r_crit_big (CRITICAL, 15m) -> r_crit_small (CRITICAL, 2m) -> r_high (HIGH, 5m) -> r_low (LOW, 0m)
        assert recs[0].recommendation_id == "REC_0003"
        assert recs[1].recommendation_id == "REC_0002"
        assert recs[2].recommendation_id == "REC_0004"
        assert recs[3].recommendation_id == "REC_0001"


# ---------------------------------------------------------------------------
# 6. What-If Scenario Decision Support Tests
# ---------------------------------------------------------------------------

class TestWhatIfScenarioDecisionSupport:
    """Verify What-If evaluation with CP-SAT solver integration and comparison structure."""

    def test_single_delay_what_if_assessment(self, advisor: DecisionSupportAdvisor):
        scenario = Scenario(
            scenario_id="SCEN_TEST_LATE_12607",
            name="Late Departure of 12607 Express",
            description="Test What-If: Lalbagh Express delayed by 15 min at MAS.",
            departure_delays={"SRV_12607_01": 15.0},
        )

        services = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]
        assessment = advisor.evaluate_what_if_scenario(scenario, service_ids=services)

        assert isinstance(assessment, DecisionSupportAssessment)
        assert assessment.what_if_scenario_id == "SCEN_TEST_LATE_12607"
        assert assessment.solver_status in ("OPTIMAL", "FEASIBLE")
        assert len(assessment.recommendations) > 0
        assert assessment.comparison_detail is not None
        assert assessment.comparison_detail.feasible_baseline_delay_minutes >= 15.0
        assert assessment.comparison_detail.optimized_delay_minutes >= 15.0
        assert len(assessment.service_delay_impacts) == 4
        assert assessment.controller_summary["scenario_id"] == "SCEN_TEST_LATE_12607"

    def test_multi_delay_what_if_assessment(self, advisor: DecisionSupportAdvisor):
        scenario = Scenario(
            scenario_id="SCEN_TEST_MULTI",
            name="Multiple Simultaneous Delays",
            description="Simultaneous departure and junction delays on West corridor.",
            departure_delays={"SRV_12607_01": 20.0, "SRV_12609_01": 15.0},
        )

        services = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]
        assessment = advisor.evaluate_what_if_scenario(scenario, service_ids=services)

        assert assessment.situation.delayed_train_count >= 2
        assert len(assessment.recommendations) >= 1
        assert any(r.is_actionable for r in assessment.recommendations)
        assert assessment.comparison_detail.feasible_baseline_delay_minutes >= 35.0


# ---------------------------------------------------------------------------
# 7. Reporting, Serialization & Determinism Tests
# ---------------------------------------------------------------------------

class TestReportingAndDeterminism:
    """Verify Markdown generation, ASCII formatting, and deterministic repeatability."""

    @pytest.fixture(scope="class")
    @classmethod
    def sample_assessment(cls, advisor: DecisionSupportAdvisor) -> DecisionSupportAssessment:
        scenario = Scenario(
            scenario_id="SCEN_DEMO_EVAL",
            name="Demonstration Disruption Evaluation",
            description="Evaluation for reporting verification.",
            departure_delays={"SRV_12607_01": 10.0},
        )
        services = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]
        return advisor.evaluate_what_if_scenario(scenario, service_ids=services)

    def test_markdown_report_generation(self, sample_assessment: DecisionSupportAssessment):
        md = sample_assessment.generate_markdown()
        assert "# Dynamic Decision-Support Assessment" in md
        assert "## 1. Controller Situation Summary" in md
        assert "## 2. Comparative Impact Summary (Feasible Baseline vs CP-SAT)" in md
        assert "## 6. Ranked Actionable Dispatching Recommendations" in md

    def test_ascii_summary_generation(self, sample_assessment: DecisionSupportAssessment):
        txt = sample_assessment.generate_summary_ascii()
        assert "DYNAMIC DECISION-SUPPORT ASSESSMENT REPORT" in txt
        assert "CONTROLLER SITUATION SUMMARY:" in txt
        assert "RANKED OPERATIONAL RECOMMENDATIONS:" in txt

    def test_assessment_to_dict_serializable(self, sample_assessment: DecisionSupportAssessment):
        d = sample_assessment.to_dict()
        assert "situation" in d
        assert "recommendations" in d
        assert "net_delay_savings" in d
        assert "solver_status" in d
        assert "prioritized_conflicts" in d
        assert "identified_bottlenecks" in d
        assert "service_delay_impacts" in d
        assert "comparison_detail" in d
        assert "controller_summary" in d

    def test_deterministic_repeatability(self, advisor: DecisionSupportAdvisor):
        scenario = Scenario(
            scenario_id="SCEN_DETERM_TEST",
            name="Deterministic Check",
            departure_delays={"SRV_12607_01": 12.0},
        )
        services = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]

        res1 = advisor.evaluate_what_if_scenario(scenario, service_ids=services)
        res2 = advisor.evaluate_what_if_scenario(scenario, service_ids=services)

        assert res1.deterministic_hash == res2.deterministic_hash
        assert res1.baseline_total_delay == res2.baseline_total_delay
        assert res1.optimized_total_delay == res2.optimized_total_delay
        assert len(res1.recommendations) == len(res2.recommendations)
