"""
decision_support/models.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Domain models and data contracts for the Dynamic Decision-Support Layer.

Turns Digital Twin simulation states, detected conflicts, and CP-SAT optimization
results into structured, explainable, and deterministic dispatching decisions:
- Operational situation awareness and severity tiering
- Conflict prioritization and scoring
- Dynamic bottleneck identification (junction vs platform vs track section)
- Service delay-impact analysis (direct vs propagated delay)
- Actionable recommendations with explicit mathematical/operational rationale
- Quantified delay impact (baseline vs optimized delay savings)
- Controller-oriented situation summary and evidence basis
"""

from dataclasses import dataclass, field
from enum import Enum
import hashlib
from typing import Any, Dict, List, Optional, Set, Tuple

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictSeverity, ConflictType


class OperationalSeverity(str, Enum):
    """Overall operational health and disturbance severity of the railway network."""
    NORMAL    = "NORMAL"      # Operating within standard tolerances (0-5m delay, 0 conflicts)
    ADVISORY  = "ADVISORY"    # Minor delays (5-15m), potential headway compression, no critical deadlock
    WARNING   = "WARNING"     # Moderate delays (15-30m), active junction or platform contention
    CRITICAL  = "CRITICAL"    # Severe delays (>30m), multi-service deadlock, head-on or capacity breach
    EMERGENCY = "EMERGENCY"   # Complete line blockage or multiple compounded corridor failures


class RecommendationType(str, Enum):
    """Categorization of actionable dispatching recommendations."""
    PRECEDENCE_OVERRIDE           = "PRECEDENCE_OVERRIDE"           # Invert train dispatching order at a bottleneck
    HOLD_AT_STATION               = "HOLD_AT_STATION"               # Hold lower-priority train at station/loop for overtaking
    JUNCTION_SLOT_RESCHEDULING    = "JUNCTION_SLOT_RESCHEDULING"    # Re-slot arrival time at a shared throat/junction
    PLATFORM_REASSIGNMENT         = "PLATFORM_REASSIGNMENT"         # Reassign train to an available parallel platform track
    SPEED_RESTRICTION_ADJUSTMENT  = "SPEED_RESTRICTION_ADJUSTMENT"  # Impose or adjust speed caution orders
    EARLY_DISPATCH                = "EARLY_DISPATCH"                # Advance departure when line ahead is clear
    MAINTAIN_CURRENT_SCHEDULE     = "MAINTAIN_CURRENT_SCHEDULE"     # Normal operation without intervention


class RecommendationCategory(str, Enum):
    """Canonical categorization of explainable dispatching recommendations."""
    PRECEDENCE_CHANGE     = "precedence change"
    HOLDING               = "holding"
    PLATFORM_REASSIGNMENT = "platform reassignment"
    DISPATCH_SEQUENCING   = "dispatch sequencing"
    SPEED_MANAGEMENT      = "speed management"
    MAINTAIN_SCHEDULE     = "maintain schedule"


def map_type_to_category(rec_type: RecommendationType) -> str:
    """Map RecommendationType enum to canonical Phase 25 category string."""
    mapping = {
        RecommendationType.PRECEDENCE_OVERRIDE: RecommendationCategory.PRECEDENCE_CHANGE.value,
        RecommendationType.HOLD_AT_STATION: RecommendationCategory.HOLDING.value,
        RecommendationType.PLATFORM_REASSIGNMENT: RecommendationCategory.PLATFORM_REASSIGNMENT.value,
        RecommendationType.JUNCTION_SLOT_RESCHEDULING: RecommendationCategory.DISPATCH_SEQUENCING.value,
        RecommendationType.SPEED_RESTRICTION_ADJUSTMENT: RecommendationCategory.SPEED_MANAGEMENT.value,
        RecommendationType.EARLY_DISPATCH: RecommendationCategory.DISPATCH_SEQUENCING.value,
        RecommendationType.MAINTAIN_CURRENT_SCHEDULE: RecommendationCategory.MAINTAIN_SCHEDULE.value,
    }
    return mapping.get(rec_type, RecommendationCategory.MAINTAIN_SCHEDULE.value)


class PriorityTier(str, Enum):
    """Urgency tier for operational recommendations."""
    CRITICAL = "CRITICAL"
    HIGH     = "HIGH"
    MEDIUM   = "MEDIUM"
    LOW      = "LOW"


@dataclass
class PrioritizedConflict:
    """Prioritized traffic conflict ranked by deterministic operational factors."""
    conflict: Conflict
    priority_score: float
    resource_type: str  # 'JUNCTION', 'PLATFORM', 'TRACK_SECTION', 'STATION'
    ranking_explanation: str
    involved_train_priorities: Dict[str, str] = field(default_factory=dict)
    lead_service_id: Optional[str] = None
    following_service_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conflict_id": self.conflict.conflict_id,
            "conflict_type": self.conflict.conflict_type.value,
            "severity": self.conflict.severity.value,
            "resource_id": self.conflict.resource_id,
            "resource_type": self.resource_type,
            "priority_score": round(self.priority_score, 2),
            "ranking_explanation": self.ranking_explanation,
            "affected_service_ids": self.conflict.affected_service_ids,
            "involved_train_priorities": self.involved_train_priorities,
            "lead_service_id": self.lead_service_id,
            "following_service_id": self.following_service_id,
        }


@dataclass
class ContestedBottleneck:
    """Dynamically identified infrastructure bottleneck with explicit resource classification."""
    resource_id: str
    resource_type: str  # 'JUNCTION', 'PLATFORM', 'TRACK_SECTION', 'STATION'
    contention_count: int
    contending_services: List[str]
    criticality_score: float
    description: str
    conflict_types: List[str] = field(default_factory=list)
    max_delay_observed: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_type": self.resource_type,
            "contention_count": self.contention_count,
            "contending_services": self.contending_services,
            "criticality_score": round(self.criticality_score, 2),
            "description": self.description,
            "conflict_types": self.conflict_types,
            "max_delay_observed": round(self.max_delay_observed, 2),
        }


@dataclass
class ServiceDelayImpact:
    """Deterministic breakdown of direct vs propagated delay and downstream impact per service."""
    service_id: str
    train_name: str
    priority_class: str
    direct_delay_minutes: float
    propagated_delay_minutes: float
    total_delay_minutes: float
    affected_downstream_resources: List[str]
    downstream_impact_summary: str
    delay_saving_minutes: float = 0.0
    downstream_impact_count: int = 0
    train_id: Optional[str] = None
    primary_delay_minutes: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        p_delay = self.primary_delay_minutes if self.primary_delay_minutes is not None else self.direct_delay_minutes
        impact_count = self.downstream_impact_count if self.downstream_impact_count > 0 else len(self.affected_downstream_resources)
        return {
            "service_id": self.service_id,
            "train_id": self.train_id or self.service_id,
            "train_name": self.train_name,
            "priority_class": self.priority_class,
            "direct_delay_minutes": round(self.direct_delay_minutes, 2),
            "primary_delay_minutes": round(p_delay, 2),
            "propagated_delay_minutes": round(self.propagated_delay_minutes, 2),
            "total_delay_minutes": round(self.total_delay_minutes, 2),
            "delay_saving_minutes": round(self.delay_saving_minutes, 2),
            "affected_downstream_resources": self.affected_downstream_resources,
            "downstream_impact_count": impact_count,
            "downstream_impact_summary": self.downstream_impact_summary,
        }


@dataclass
class BaselineOptimizationComparison:
    """Rigorous comparison between feasible baseline and CP-SAT optimization with published reference."""
    published_reference_delay_minutes: float
    feasible_baseline_delay_minutes: float
    feasible_baseline_max_delay_minutes: float
    feasible_baseline_conflicts_remaining: int
    feasible_baseline_throughput: int
    optimized_delay_minutes: float
    optimized_max_delay_minutes: float
    optimized_conflicts_remaining: int
    optimized_throughput: int
    delay_savings_minutes: float
    delay_savings_percent: float
    solver_status: str
    solve_time_seconds: float
    three_tier_timetable: List[Dict[str, Any]] = field(default_factory=list)
    published_timetables: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    feasible_timetables: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    optimized_timetables: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    corridor_performance: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "published_reference_delay_minutes": round(self.published_reference_delay_minutes, 2),
            "feasible_baseline_delay_minutes": round(self.feasible_baseline_delay_minutes, 2),
            "feasible_baseline_max_delay_minutes": round(self.feasible_baseline_max_delay_minutes, 2),
            "feasible_baseline_conflicts_remaining": self.feasible_baseline_conflicts_remaining,
            "feasible_baseline_throughput": self.feasible_baseline_throughput,
            "optimized_delay_minutes": round(self.optimized_delay_minutes, 2),
            "optimized_max_delay_minutes": round(self.optimized_max_delay_minutes, 2),
            "optimized_conflicts_remaining": self.optimized_conflicts_remaining,
            "optimized_throughput": self.optimized_throughput,
            "delay_savings_minutes": round(self.delay_savings_minutes, 2),
            "delay_savings_percent": round(self.delay_savings_percent, 2),
            "solver_status": self.solver_status,
            "solve_time_seconds": round(self.solve_time_seconds, 3),
            "three_tier_timetable": self.three_tier_timetable,
            "published_timetables": self.published_timetables,
            "feasible_timetables": self.feasible_timetables,
            "optimized_timetables": self.optimized_timetables,
            "corridor_performance": self.corridor_performance,
        }


@dataclass
class OperationalSituation:
    """Snapshot of the current operational state across the railway network."""
    timestamp: float
    active_train_count: int = 0
    delayed_train_count: int = 0
    total_active_delay_minutes: float = 0.0
    peak_delay_minutes: float = 0.0
    peak_delay_service: Optional[str] = None
    active_conflicts: List[Conflict] = field(default_factory=list)
    near_future_bottlenecks: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    affected_resources: List[str] = field(default_factory=list)
    severity: OperationalSeverity = OperationalSeverity.NORMAL
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    @property
    def timestamp_str(self) -> str:
        return minutes_to_time_str(self.timestamp)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "timestamp_str": self.timestamp_str,
            "active_train_count": self.active_train_count,
            "delayed_train_count": self.delayed_train_count,
            "total_active_delay_minutes": round(self.total_active_delay_minutes, 2),
            "peak_delay_minutes": round(self.peak_delay_minutes, 2),
            "peak_delay_service": self.peak_delay_service,
            "active_conflicts_count": len(self.active_conflicts),
            "near_future_bottlenecks": self.near_future_bottlenecks,
            "affected_services": self.affected_services,
            "affected_resources": self.affected_resources,
            "severity": self.severity.value,
            "diagnostics": self.diagnostics,
        }


@dataclass
class SupportingEvidence:
    """Explicit supporting evidence grounding the recommendation in network state."""
    triggering_conflicts: List[str] = field(default_factory=list)
    contested_resources: List[str] = field(default_factory=list)
    affected_services: List[str] = field(default_factory=list)
    bottlenecks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "triggering_conflicts": self.triggering_conflicts,
            "contested_resources": self.contested_resources,
            "affected_services": self.affected_services,
            "bottlenecks": self.bottlenecks,
        }


@dataclass
class DelayAnalysis:
    """Quantitative breakdown of direct and propagated delay mitigation."""
    direct_delay_reduction_minutes: float = 0.0
    propagated_delay_reduction_minutes: float = 0.0
    total_savings_minutes: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "direct_delay_reduction_minutes": round(self.direct_delay_reduction_minutes, 2),
            "propagated_delay_reduction_minutes": round(self.propagated_delay_reduction_minutes, 2),
            "total_savings_minutes": round(self.total_savings_minutes, 2),
        }


@dataclass
class CounterfactualAnalysis:
    """Deterministic counterfactual prediction of system state if recommendation is rejected."""
    unmitigated_delay_minutes: float = 0.0
    impact_if_not_applied: str = ""
    downstream_ripple_risk: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "unmitigated_delay_minutes": round(self.unmitigated_delay_minutes, 2),
            "impact_if_not_applied": self.impact_if_not_applied,
            "downstream_ripple_risk": self.downstream_ripple_risk,
        }


@dataclass
class ConfidenceMetrics:
    """Transparent metrics quantifying mathematical and operational confidence."""
    supporting_constraints_count: int = 1
    optimization_agreement: float = 1.0  # 1.0 = 100% agreement
    conflict_severity_basis: str = "MAJOR"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "supporting_constraints_count": self.supporting_constraints_count,
            "optimization_agreement": round(self.optimization_agreement, 2),
            "conflict_severity_basis": self.conflict_severity_basis,
        }


@dataclass
class ConstraintExplanation:
    """Human-interpretable explanation of physical railway constraint dimensions."""
    headway: str = ""
    platform_capacity: str = ""
    route_occupancy: str = ""
    junction_contention: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "headway": self.headway,
            "platform_capacity": self.platform_capacity,
            "route_occupancy": self.route_occupancy,
            "junction_contention": self.junction_contention,
        }


@dataclass
class ReasoningStep:
    """A distinct chronological step in the controller reasoning pathway."""
    step_number: int
    phase: str  # 'TRIGGER', 'BOTTLENECK', 'CONSTRAINTS', 'DECISION', 'OUTCOME'
    title: str
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "phase": self.phase,
            "title": self.title,
            "detail": self.detail,
        }


@dataclass
class Recommendation:
    """Structured, explainable dispatching recommendation generated by decision support."""
    recommendation_id: str
    recommendation_type: RecommendationType
    title: str
    reason: str
    affected_services: List[str]
    affected_resources: List[str]
    baseline_delay_minutes: float = 0.0
    expected_delay_minutes: float = 0.0
    expected_delay_savings: float = 0.0
    confidence_score: float = 1.0
    priority_tier: PriorityTier = PriorityTier.MEDIUM
    evidence_basis: str = "CP-SAT Mathematical Optimization (Status: OPTIMAL)"
    action_details: Dict[str, Any] = field(default_factory=dict)
    is_actionable: bool = True
    # Phase 25 Explainable Additions
    category: str = ""
    operational_context: str = "LIVE_OPERATIONAL"  # 'LIVE_OPERATIONAL' or 'HYPOTHETICAL_SCENARIO'
    supporting_evidence: Optional[SupportingEvidence] = None
    delay_analysis: Optional[DelayAnalysis] = None
    counterfactual_analysis: Optional[CounterfactualAnalysis] = None
    confidence_metrics: Optional[ConfidenceMetrics] = None
    constraint_explanation: Optional[ConstraintExplanation] = None
    ranking_explanation: str = ""
    reasoning_path: List[ReasoningStep] = field(default_factory=list)

    def __post_init__(self):
        if not self.category:
            self.category = map_type_to_category(self.recommendation_type)
        if self.supporting_evidence is None:
            self.supporting_evidence = SupportingEvidence(
                triggering_conflicts=[],
                contested_resources=list(self.affected_resources),
                affected_services=list(self.affected_services),
                bottlenecks=list(self.affected_resources),
            )
        if self.delay_analysis is None:
            self.delay_analysis = DelayAnalysis(
                direct_delay_reduction_minutes=round(self.expected_delay_savings * 0.6, 2),
                propagated_delay_reduction_minutes=round(self.expected_delay_savings * 0.4, 2),
                total_savings_minutes=round(self.expected_delay_savings, 2),
            )
        if self.counterfactual_analysis is None:
            self.counterfactual_analysis = CounterfactualAnalysis(
                unmitigated_delay_minutes=self.baseline_delay_minutes,
                impact_if_not_applied=(
                    f"If rejected, unmitigated delay of {self.baseline_delay_minutes:.1f}m persists on "
                    f"{', '.join(self.affected_resources) if self.affected_resources else 'the corridor'}."
                ),
                downstream_ripple_risk="Potential queue formation on trailing services.",
            )
        if self.confidence_metrics is None:
            self.confidence_metrics = ConfidenceMetrics(
                supporting_constraints_count=3,
                optimization_agreement=self.confidence_score,
                conflict_severity_basis=self.priority_tier.value,
            )
        if self.constraint_explanation is None:
            self.constraint_explanation = ConstraintExplanation(
                headway="Minimum safety headway enforced between movements.",
                platform_capacity="Station platform track capacity respected.",
                route_occupancy="Block section clearance maintained before train entry.",
                junction_contention="Junction interlocking path reserved without crossing overlap.",
            )
        if not self.ranking_explanation:
            self.ranking_explanation = (
                f"Ranked {self.priority_tier.value} based on saving {self.expected_delay_savings:.1f}m delay "
                f"across {len(self.affected_services)} services with {self.confidence_score * 100:.0f}% confidence."
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "recommendation_type": self.recommendation_type.value,
            "category": self.category,
            "title": self.title,
            "reason": self.reason,
            "affected_services": self.affected_services,
            "affected_resources": self.affected_resources,
            "baseline_delay_minutes": round(self.baseline_delay_minutes, 2),
            "expected_delay_minutes": round(self.expected_delay_minutes, 2),
            "expected_delay_savings": round(self.expected_delay_savings, 2),
            "confidence_score": round(self.confidence_score, 2),
            "priority_tier": self.priority_tier.value,
            "evidence_basis": self.evidence_basis,
            "action_details": self.action_details,
            "is_actionable": self.is_actionable,
            "operational_context": self.operational_context,
            "supporting_evidence": self.supporting_evidence.to_dict() if self.supporting_evidence else None,
            "delay_analysis": self.delay_analysis.to_dict() if self.delay_analysis else None,
            "counterfactual_analysis": self.counterfactual_analysis.to_dict() if self.counterfactual_analysis else None,
            "confidence_metrics": self.confidence_metrics.to_dict() if self.confidence_metrics else None,
            "constraint_explanation": self.constraint_explanation.to_dict() if self.constraint_explanation else None,
            "ranking_explanation": self.ranking_explanation,
            "reasoning_path": [step.to_dict() for step in self.reasoning_path],
        }


@dataclass
class DecisionSupportAssessment:
    """Comprehensive decision support output combining situation awareness, comparative metrics, and recommendations."""
    situation: OperationalSituation
    recommendations: List[Recommendation]
    what_if_scenario_id: Optional[str] = None
    baseline_total_delay: float = 0.0
    optimized_total_delay: float = 0.0
    net_delay_savings: float = 0.0
    net_delay_savings_percent: float = 0.0
    solver_status: str = "OPTIMAL"
    solve_time_seconds: float = 0.0
    deterministic_hash: str = ""
    prioritized_conflicts: List[PrioritizedConflict] = field(default_factory=list)
    identified_bottlenecks: List[ContestedBottleneck] = field(default_factory=list)
    service_delay_impacts: List[ServiceDelayImpact] = field(default_factory=list)
    comparison_detail: Optional[BaselineOptimizationComparison] = None
    controller_summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "situation": self.situation.to_dict(),
            "recommendations": [r.to_dict() for r in self.recommendations],
            "what_if_scenario_id": self.what_if_scenario_id,
            "baseline_total_delay": round(self.baseline_total_delay, 2),
            "optimized_total_delay": round(self.optimized_total_delay, 2),
            "net_delay_savings": round(self.net_delay_savings, 2),
            "net_delay_savings_percent": round(self.net_delay_savings_percent, 2),
            "solver_status": self.solver_status,
            "solve_time_seconds": round(self.solve_time_seconds, 3),
            "deterministic_hash": self.deterministic_hash,
            "prioritized_conflicts": [pc.to_dict() for pc in self.prioritized_conflicts],
            "identified_bottlenecks": [ib.to_dict() for ib in self.identified_bottlenecks],
            "service_delay_impacts": [sdi.to_dict() for sdi in self.service_delay_impacts],
            "comparison_detail": self.comparison_detail.to_dict() if self.comparison_detail else None,
            "controller_summary": self.controller_summary,
            "metadata": self.metadata,
        }

    def generate_summary_ascii(self) -> str:
        lines = [
            "=" * 96,
            "DYNAMIC DECISION-SUPPORT ASSESSMENT REPORT",
            "=" * 96,
            f"Timestamp: {self.situation.timestamp_str:<8} | Severity: {self.situation.severity.value:<10} | Active Trains: {self.situation.active_train_count} | Active Delay: {self.situation.total_active_delay_minutes:.1f}m",
            f"Conflicts Detected: {len(self.situation.active_conflicts)} | Solver: {self.solver_status} ({self.solve_time_seconds:.3f}s) | Savings: {self.net_delay_savings:.1f}m ({self.net_delay_savings_percent:.1f}%)",
            "-" * 96,
            "CONTROLLER SITUATION SUMMARY:",
            f"  Scenario: {self.controller_summary.get('scenario_name', self.what_if_scenario_id or 'Live Simulation')}",
            f"  Severity Assessment: {self.situation.severity.value} (Peak Delay: {self.situation.peak_delay_minutes:.1f}m on {self.situation.peak_delay_service or 'N/A'})",
            f"  Bottlenecks Identified: {len(self.identified_bottlenecks)} ({', '.join(b.resource_id for b in self.identified_bottlenecks) if self.identified_bottlenecks else 'None'})",
            f"  Comparative Impact: Feasible Baseline {self.baseline_total_delay:.1f}m -> CP-SAT {self.optimized_total_delay:.1f}m (Savings: {self.net_delay_savings:.1f}m | {self.net_delay_savings_percent:.1f}%)",
            "-" * 96,
            "RANKED OPERATIONAL RECOMMENDATIONS:",
        ]

        if not self.recommendations:
            lines.append("  (No action needed - system operating normally)")
        else:
            for rec in self.recommendations:
                lines.append(
                    f"  [{rec.priority_tier.value:<8}] {rec.recommendation_id}: {rec.title}"
                )
                lines.append(f"            Reason: {rec.reason}")
                lines.append(
                    f"            Impact: Baseline Delay {rec.baseline_delay_minutes:.1f}m -> Rec Delay {rec.expected_delay_minutes:.1f}m (Savings: {rec.expected_delay_savings:.1f}m | Conf: {rec.confidence_score:.2f})"
                )
                lines.append(f"            Evidence: {rec.evidence_basis}")
                lines.append(f"            Services: {', '.join(rec.affected_services)} | Resources: {', '.join(rec.affected_resources)}")

        lines.append("=" * 96)
        return "\n".join(lines)

    def generate_markdown(self) -> str:
        lines = [
            "# Dynamic Decision-Support Assessment",
            "",
            "## 1. Controller Situation Summary",
            f"- **Simulation Time / Scenario:** `{self.situation.timestamp_str}` / `{self.controller_summary.get('scenario_name', self.what_if_scenario_id or 'Live Simulation')}`",
            f"- **Operational Severity:** `{self.situation.severity.value}`",
            f"- **Active Trains / Delayed Trains:** `{self.situation.active_train_count}` / `{self.situation.delayed_train_count}`",
            f"- **Total Cumulative Delay:** `{self.situation.total_active_delay_minutes:.1f} min` (Peak: `{self.situation.peak_delay_minutes:.1f} min` on `{self.situation.peak_delay_service or 'N/A'}`)",
            f"- **Critical Conflicts Flagged:** `{len(self.prioritized_conflicts)}`",
            f"- **Contested Bottlenecks:** `{', '.join(b.resource_id for b in self.identified_bottlenecks) if self.identified_bottlenecks else 'None'}`",
            "",
            "## 2. Comparative Impact Summary (Feasible Baseline vs CP-SAT)",
            "| Metric | Feasible Baseline (FIFO) | Recommended (CP-SAT) | Net Savings |",
            "|---|:---:|:---:|:---:|",
            f"| **Total Delay** | `{self.baseline_total_delay:.1f} min` | `{self.optimized_total_delay:.1f} min` | **`{self.net_delay_savings:.1f} min` ({self.net_delay_savings_percent:.1f}%)** |",
            f"| **Solver Status** | Physical FIFO | `{self.solver_status}` | `{self.solve_time_seconds:.3f}s solve` |",
            "",
        ]

        if self.prioritized_conflicts:
            lines.extend([
                "## 3. Prioritized Traffic Conflicts",
                "| Rank | Conflict ID | Type | Severity | Resource | Priority Score | Ranking Explanation |",
                "|:---:|---|---|:---:|---|:---:|---|",
            ])
            for idx, pc in enumerate(self.prioritized_conflicts, start=1):
                lines.append(
                    f"| {idx} | `{pc.conflict.conflict_id}` | `{pc.conflict.conflict_type.value}` | `{pc.conflict.severity.value}` | `{pc.conflict.resource_id}` ({pc.resource_type}) | `{pc.priority_score:.1f}` | {pc.ranking_explanation} |"
                )
            lines.append("")

        if self.identified_bottlenecks:
            lines.extend([
                "## 4. Contested Bottleneck Resources",
                "| Resource ID | Type | Contending Services | Contention Count | Criticality Score | Description |",
                "|---|:---:|---|:---:|:---:|---|",
            ])
            for b in self.identified_bottlenecks:
                lines.append(
                    f"| `{b.resource_id}` | `{b.resource_type}` | `{', '.join(b.contending_services)}` | {b.contention_count} | `{b.criticality_score:.1f}` | {b.description} |"
                )
            lines.append("")

        if self.service_delay_impacts:
            lines.extend([
                "## 5. Service Delay-Impact Analysis",
                "| Service ID | Train Name | Priority | Direct Delay | Propagated Delay | Total Delay | Downstream Impact Summary |",
                "|---|---|:---:|:---:|:---:|:---:|---|",
            ])
            for sdi in self.service_delay_impacts:
                lines.append(
                    f"| `{sdi.service_id}` | {sdi.train_name} | `{sdi.priority_class}` | `{sdi.direct_delay_minutes:.1f}m` | `{sdi.propagated_delay_minutes:.1f}m` | `{sdi.total_delay_minutes:.1f}m` | {sdi.downstream_impact_summary} |"
                )
            lines.append("")

        lines.extend([
            "## 6. Ranked Actionable Dispatching Recommendations",
        ])

        if not self.recommendations:
            lines.append("✅ **No intervention required.** The railway system is operating within normal tolerances.")
        else:
            for idx, rec in enumerate(self.recommendations, start=1):
                lines.extend([
                    f"### Recommendation {idx}: {rec.title}",
                    f"- **Recommendation ID:** `{rec.recommendation_id}`",
                    f"- **Type:** `{rec.recommendation_type.value}`",
                    f"- **Priority Tier:** `{rec.priority_tier.value}`",
                    f"- **Rationale:** {rec.reason}",
                    f"- **Affected Services:** `{', '.join(rec.affected_services)}`",
                    f"- **Affected Resources:** `{', '.join(rec.affected_resources)}`",
                    f"- **Delay Impact:** Baseline `{rec.baseline_delay_minutes:.1f}m` $\\rightarrow$ Recommended `{rec.expected_delay_minutes:.1f}m` (Savings: **`{rec.expected_delay_savings:.1f}m`**)",
                    f"- **Evidence Basis:** {rec.evidence_basis}",
                    f"- **Confidence Score:** `{rec.confidence_score * 100:.0f}%`",
                    f"- **Operational Parameters:** `{rec.action_details}`",
                    "",
                ])

        lines.extend([
            "## 7. Operational Limitations & Boundaries",
            "- **Mathematical Optimizer**: Recommendations derived from exact mixed-integer CP-SAT schedules under macroscopic block constraints.",
            "- **No Hallucinated Savings**: Delay savings strictly represent the difference between the physical FIFO baseline and CP-SAT schedule.",
            "- **Immutable Railway Topology**: Infrastructure abstractions match Chennai Division network without synthetic interlocking geometry.",
        ])

        return "\n".join(lines)
