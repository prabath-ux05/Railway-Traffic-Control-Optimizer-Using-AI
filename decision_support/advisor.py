"""
decision_support/advisor.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Deterministic Dynamic Decision-Support Advisor Engine.

Analyzes Digital Twin operational states, evaluates What-If scenarios,
prioritizes conflicts with deterministic scoring, identifies contested dynamic bottlenecks
(distinguishing track section, junction, platform, and station resources),
performs service delay-impact analysis (direct vs propagated delay),
compares feasible baseline against CP-SAT optimization,
and generates structured, explainable, and ranked dispatching recommendations.
"""

from collections import defaultdict
import copy
import hashlib
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictDetector, ConflictSeverity, ConflictType
from simulation.network import Network, Route, Service, TrackSection
from simulation.simulator import TrainSimulator
from simulation.state import SimulationState, TrackSectionOccupancy, TrainRuntimeState, TrainStatus
from optimization.model import PrecedenceDecision, ResourceAllocationDecision, ServiceTimetableAdjustment
from optimization.scenarios import Scenario, ScenarioComparison, ScenarioRunner
from optimization.scheduler import OptimizationResult
from optimization.solver import CPSATScheduler

from decision_support.models import (
    BaselineOptimizationComparison,
    ConfidenceMetrics,
    ConstraintExplanation,
    ContestedBottleneck,
    CounterfactualAnalysis,
    DecisionSupportAssessment,
    DelayAnalysis,
    OperationalSeverity,
    OperationalSituation,
    PrioritizedConflict,
    PriorityTier,
    ReasoningStep,
    Recommendation,
    RecommendationCategory,
    RecommendationType,
    ServiceDelayImpact,
    SupportingEvidence,
    map_type_to_category,
)


def _load_default_network() -> Network:
    net = Network()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    net.load_from_directory(os.path.join(base_dir, "data", "infrastructure"))
    net.load_trains(os.path.join(base_dir, "data", "trains", "train_identity", "trains.json"))
    net.load_services(os.path.join(base_dir, "data", "trains", "service_definitions", "services.json"))
    net.load_timetable(os.path.join(base_dir, "data", "trains", "published_timetables", "timetable.json"))
    return net


class DecisionSupportAdvisor:
    """Core decision support engine for railway traffic management."""

    # Priority weight mapping for service priority classes and train categories
    PRIORITY_WEIGHTS: Dict[str, float] = {
        "HIGH": 2.0,
        "PREMIUM": 2.0,
        "SUPERFAST": 1.8,
        "MEDIUM": 1.5,
        "EXPRESS": 1.5,
        "SUBURBAN": 1.2,
        "LOW": 1.0,
        "PASSENGER": 1.0,
        "FREIGHT": 0.8,
        "NORMAL": 1.0,
    }

    def __init__(
        self,
        network: Optional[Network] = None,
        detector: Optional[ConflictDetector] = None,
        solver: Optional[CPSATScheduler] = None,
    ):
        self.network = network or _load_default_network()
        self.detector = detector or ConflictDetector(network=self.network)
        self.solver = solver or CPSATScheduler()
        self.scenario_runner = ScenarioRunner(network=self.network)
        self._rec_counter = 0

    def _next_rec_id(self) -> str:
        self._rec_counter += 1
        return f"REC_{self._rec_counter:04d}"

    def reset_counter(self):
        self._rec_counter = 0

    # -----------------------------------------------------------------------
    # Resource Classification Helper
    # -----------------------------------------------------------------------
    def classify_resource(self, resource_id: str) -> str:
        """Classify a physical resource into JUNCTION, PLATFORM, TRACK_SECTION, or STATION."""
        if not resource_id:
            return "UNKNOWN"
        res_upper = resource_id.upper()
        if res_upper.startswith("JCT_") or resource_id in self.network.junctions:
            return "JUNCTION"
        if (
            res_upper.startswith("SEC_")
            or "_UP" in res_upper
            or "_DOWN" in res_upper
            or "_SUBURBAN" in res_upper
            or "_MAIN" in res_upper
            or resource_id in self.network.track_sections
        ):
            return "TRACK_SECTION"
        if (
            "PLAT_" in res_upper
            or "_PLAT_" in res_upper
            or any(res_upper.endswith(f"_P{i}") for i in range(1, 25))
        ):
            return "PLATFORM"
        if resource_id in self.network.stations:
            return "STATION"
        return "TRACK_SECTION"

    # -----------------------------------------------------------------------
    # 1. Conflict Prioritization Logic
    # -----------------------------------------------------------------------
    def prioritize_conflicts(
        self,
        conflicts: List[Conflict],
        state: Optional[SimulationState] = None,
    ) -> List[PrioritizedConflict]:
        """Rank detected conflicts using deterministic operational factors."""
        prioritized: List[PrioritizedConflict] = []

        for c in conflicts:
            res_type = self.classify_resource(c.resource_id)

            # 1. Base severity component
            sev_base = {
                ConflictSeverity.CRITICAL: 50.0,
                ConflictSeverity.MAJOR: 30.0,
                ConflictSeverity.MINOR: 15.0,
            }.get(c.severity, 10.0)

            # 2. Resource type criticality bonus
            res_bonus = {
                "JUNCTION": 25.0,
                "PLATFORM": 15.0,
                "TRACK_SECTION": 10.0,
                "STATION": 10.0,
            }.get(res_type, 5.0)

            # 3. Train priority multiplier & delay factors
            max_prio_weight = 1.0
            total_service_delay = 0.0
            train_priorities: Dict[str, str] = {}

            for s_id in c.affected_service_ids:
                svc = self.network.services.get(s_id)
                prio_class = svc.priority_class if svc else "NORMAL"
                train_priorities[s_id] = prio_class
                weight = self.PRIORITY_WEIGHTS.get(prio_class.upper(), 1.0)
                if weight > max_prio_weight:
                    max_prio_weight = weight

                if state and s_id in state.train_states:
                    total_service_delay += state.train_states[s_id].delay_minutes

            # Downstream volume factor
            volume_factor = min(20.0, len(c.affected_service_ids) * 5.0)
            delay_factor = min(20.0, total_service_delay * 0.5)

            final_score = (sev_base + res_bonus + volume_factor + delay_factor) * max_prio_weight

            lead_svc = c.affected_service_ids[0] if c.affected_service_ids else None
            foll_svc = c.affected_service_ids[1] if len(c.affected_service_ids) > 1 else None

            explanation = (
                f"Conflict on {res_type} '{c.resource_id}' ({c.severity.value}): "
                f"{len(c.affected_service_ids)} services involved (max priority weight {max_prio_weight:.1f}x, "
                f"delay impact +{total_service_delay:.1f}m)."
            )

            prioritized.append(
                PrioritizedConflict(
                    conflict=c,
                    priority_score=final_score,
                    resource_type=res_type,
                    ranking_explanation=explanation,
                    involved_train_priorities=train_priorities,
                    lead_service_id=lead_svc,
                    following_service_id=foll_svc,
                )
            )

        # Sort strictly deterministic: highest priority_score descending, tie-breaker conflict_id
        prioritized.sort(key=lambda pc: (-pc.priority_score, pc.conflict.conflict_id))
        return prioritized

    # -----------------------------------------------------------------------
    # 2. Bottleneck Identification Logic
    # -----------------------------------------------------------------------
    def identify_contested_bottlenecks(
        self,
        state: Optional[SimulationState] = None,
        conflicts: Optional[List[Conflict]] = None,
        optimization_result: Optional[OptimizationResult] = None,
    ) -> List[ContestedBottleneck]:
        """Identify and distinguish contested dynamic resources (junction vs platform vs track section)."""
        contention_map: Dict[str, Set[str]] = defaultdict(set)
        conflict_types_map: Dict[str, Set[str]] = defaultdict(set)
        max_delay_map: Dict[str, float] = defaultdict(float)

        # Pre-calculate service delays from optimization result if available
        service_delays: Dict[str, float] = {}
        if optimization_result:
            for s_id, adjs in optimization_result.adjusted_timetables.items():
                for a in adjs:
                    if a.delay_minutes > 0.0:
                        service_delays[s_id] = max(service_delays.get(s_id, 0.0), a.delay_minutes)

        # 1. Collect from active simulation state station occupancy
        if state:
            for node_id, svcs in state.station_occupancy.items():
                if len(svcs) > 1:
                    contention_map[node_id].update(svcs)
                    conflict_types_map[node_id].add("STATION_OCCUPANCY")
                    for s in svcs:
                        if s in state.train_states:
                            max_delay_map[node_id] = max(max_delay_map[node_id], state.train_states[s].delay_minutes)

        # 2. Collect from conflicts
        if conflicts:
            for c in conflicts:
                contention_map[c.resource_id].update(c.affected_service_ids)
                c_type = c.conflict_type.value if hasattr(c.conflict_type, "value") else str(c.conflict_type)
                conflict_types_map[c.resource_id].add(c_type)
                for s in c.affected_service_ids:
                    if s in service_delays:
                        max_delay_map[c.resource_id] = max(max_delay_map[c.resource_id], service_delays[s])
                    elif state and s in state.train_states:
                        max_delay_map[c.resource_id] = max(max_delay_map[c.resource_id], state.train_states[s].delay_minutes)

        # 3. Collect from CP-SAT precedence decisions where temporal closeness or order swap exists
        if optimization_result:
            dep_lookup: Dict[Tuple[str, str], float] = {}
            for s_id, adjs in optimization_result.adjusted_timetables.items():
                for a in adjs:
                    if a.adjusted_departure is not None:
                        dep_lookup[(s_id, a.station_id)] = a.adjusted_departure

            for p in optimization_result.precedence_decisions:
                t1 = dep_lookup.get((p.first_service_id, p.resource_id))
                t2 = dep_lookup.get((p.second_service_id, p.resource_id))
                # Only mark as contested bottleneck if trains interact in close temporal window (<= 15 min)
                if t1 is not None and t2 is not None and abs(t1 - t2) <= 15.0:
                    contention_map[p.resource_id].add(p.first_service_id)
                    contention_map[p.resource_id].add(p.second_service_id)
                    res_type_hint = self.classify_resource(p.resource_id)
                    c_type = "INSUFFICIENT_HEADWAY" if res_type_hint == "TRACK_SECTION" else "SHARED_JUNCTION" if res_type_hint == "JUNCTION" else "PRECEDENCE_ORDER"
                    conflict_types_map[p.resource_id].add(c_type)
                    max_delay_map[p.resource_id] = max(
                        max_delay_map[p.resource_id],
                        service_delays.get(p.first_service_id, 0.0),
                        service_delays.get(p.second_service_id, 0.0),
                    )
                elif "JCT" in p.resource_id and t1 is not None and t2 is not None and abs(t1 - t2) <= 30.0:
                    contention_map[p.resource_id].add(p.first_service_id)
                    contention_map[p.resource_id].add(p.second_service_id)
                    conflict_types_map[p.resource_id].add("SHARED_JUNCTION")
                    max_delay_map[p.resource_id] = max(
                        max_delay_map[p.resource_id],
                        service_delays.get(p.first_service_id, 0.0),
                        service_delays.get(p.second_service_id, 0.0),
                    )

            # Platform allocations where multiple services share the same station
            station_pf_map: Dict[str, Set[str]] = defaultdict(set)
            for r in optimization_result.resource_decisions:
                if r.resource_type == "PLATFORM":
                    station_pf_map[r.node_or_section_id].add(r.service_id)
            for stn, svcs in station_pf_map.items():
                if len(svcs) > 1:
                    contention_map[stn].update(svcs)
                    conflict_types_map[stn].add("PLATFORM_OCCUPANCY")
                    for s in svcs:
                        max_delay_map[stn] = max(max_delay_map[stn], service_delays.get(s, 0.0))

        bottlenecks: List[ContestedBottleneck] = []
        for res_id, svcs in contention_map.items():
            res_type = self.classify_resource(res_id)
            c_count = len(svcs)

            type_weight = {
                "JUNCTION": 2.0,
                "PLATFORM": 1.5,
                "TRACK_SECTION": 1.2,
                "STATION": 1.0,
            }.get(res_type, 1.0)

            crit_score = c_count * 10.0 * type_weight
            desc = (
                f"Dynamic {res_type.lower()} bottleneck '{res_id}' contested by "
                f"{c_count} services: {', '.join(sorted(list(svcs)))}."
            )

            c_types = sorted(list(conflict_types_map[res_id])) if conflict_types_map[res_id] else [
                "SHARED_JUNCTION" if res_type == "JUNCTION" else "PLATFORM_OCCUPANCY" if res_type == "PLATFORM" else "INSUFFICIENT_HEADWAY"
            ]
            max_d = max_delay_map[res_id]
            if max_d == 0.0 and service_delays:
                max_d = max((service_delays.get(s, 0.0) for s in svcs), default=0.0)

            bottlenecks.append(
                ContestedBottleneck(
                    resource_id=res_id,
                    resource_type=res_type,
                    contention_count=c_count,
                    contending_services=sorted(list(svcs)),
                    criticality_score=crit_score,
                    description=desc,
                    conflict_types=c_types,
                    max_delay_observed=round(max_d, 2),
                )
            )

        # Sort deterministic: highest criticality_score descending, tie-breaker resource_id
        bottlenecks.sort(key=lambda b: (-b.criticality_score, b.resource_id))
        return bottlenecks

    # -----------------------------------------------------------------------
    # 3. Delay-Impact Analysis Logic
    # -----------------------------------------------------------------------
    def analyze_service_delay_impacts(
        self,
        service_ids: List[str],
        state: Optional[SimulationState] = None,
        direct_delays: Optional[Dict[str, float]] = None,
        optimization_result: Optional[OptimizationResult] = None,
        baseline_result: Optional[OptimizationResult] = None,
    ) -> List[ServiceDelayImpact]:
        """Compute direct vs propagated delay, delay savings, and downstream impact counts per service."""
        impacts: List[ServiceDelayImpact] = []
        direct_map = direct_delays or {}

        raw_metrics: Dict[str, Dict[str, Any]] = {}
        for s_id in sorted(service_ids):
            svc = self.network.services.get(s_id)
            t_id = svc.train_id if svc else s_id
            train_obj = self.network.trains.get(t_id) if (svc and t_id in self.network.trains) else None
            t_name = train_obj.name if train_obj else t_id
            p_class = svc.priority_class if svc else "NORMAL"

            dir_delay = float(direct_map.get(s_id, 0.0))

            # Baseline unmitigated delay
            base_delay = dir_delay
            if baseline_result and s_id in baseline_result.adjusted_timetables:
                b_adjs = baseline_result.adjusted_timetables[s_id]
                if b_adjs:
                    base_delay = max(base_delay, max(a.delay_minutes for a in b_adjs))
            elif state and s_id in state.train_states:
                base_delay = max(base_delay, state.train_states[s_id].delay_minutes)

            # Optimized schedule delay & downstream resources
            opt_delay = base_delay
            downstream_res: List[str] = []
            if optimization_result and s_id in optimization_result.adjusted_timetables:
                o_adjs = optimization_result.adjusted_timetables[s_id]
                if o_adjs:
                    opt_delay = max(0.0, max(a.delay_minutes for a in o_adjs))
                    downstream_res = [a.station_id for a in o_adjs if a.delay_minutes > 0.0]
            elif state and s_id in state.train_states:
                if state.train_states[s_id].current_station:
                    downstream_res.append(state.train_states[s_id].current_station)
                if state.train_states[s_id].current_track_section:
                    downstream_res.append(state.train_states[s_id].current_track_section)

            tot_delay = max(dir_delay, base_delay)
            prop_delay = max(0.0, tot_delay - dir_delay)
            delay_savings = max(0.0, tot_delay - opt_delay)

            raw_metrics[s_id] = {
                "t_id": t_id,
                "t_name": t_name,
                "p_class": p_class,
                "dir_delay": dir_delay,
                "tot_delay": tot_delay,
                "prop_delay": prop_delay,
                "opt_delay": opt_delay,
                "savings": delay_savings,
                "downstream_res": downstream_res,
            }

        # Identify all services with secondary propagated delay
        services_with_propagation = [s for s, m in raw_metrics.items() if m["prop_delay"] > 0.0]

        # Second pass: compute downstream impact counts and summaries
        for s_id in sorted(service_ids):
            m = raw_metrics[s_id]
            dir_delay = m["dir_delay"]
            prop_delay = m["prop_delay"]
            tot_delay = m["tot_delay"]
            savings = m["savings"]
            downstream_res = m["downstream_res"]

            if dir_delay > 0.0:
                other_propagated = [s for s in services_with_propagation if s != s_id]
                impact_count = len(other_propagated)
                if impact_count == 0 and downstream_res:
                    impact_count = len(downstream_res)
            elif prop_delay > 0.0:
                impact_count = len(downstream_res) if downstream_res else 1
            else:
                impact_count = 0

            if prop_delay > 0.0 and dir_delay > 0.0:
                summary = (
                    f"Direct primary delay: {dir_delay:.1f}m, Secondary propagated delay: +{prop_delay:.1f}m "
                    f"from downstream queueing (impacting {impact_count} downstream trains/nodes)."
                )
            elif prop_delay > 0.0:
                summary = f"Secondary propagated delay: +{prop_delay:.1f}m absorbed from upstream network congestion."
            elif dir_delay > 0.0:
                summary = f"Direct primary delay: {dir_delay:.1f}m contained without secondary propagation."
            else:
                summary = "On-time operation within published schedule tolerance."

            impacts.append(
                ServiceDelayImpact(
                    service_id=s_id,
                    train_name=m["t_name"],
                    priority_class=m["p_class"],
                    direct_delay_minutes=dir_delay,
                    propagated_delay_minutes=prop_delay,
                    total_delay_minutes=tot_delay,
                    affected_downstream_resources=downstream_res,
                    downstream_impact_summary=summary,
                    delay_saving_minutes=savings,
                    downstream_impact_count=impact_count,
                    train_id=m["t_id"],
                    primary_delay_minutes=dir_delay,
                )
            )

        return impacts

    # -----------------------------------------------------------------------
    # 4. Operational Situation Awareness
    # -----------------------------------------------------------------------
    def assess_current_state(
        self,
        state: SimulationState,
        lookahead_minutes: float = 30.0,
    ) -> OperationalSituation:
        """Inspect simulation state, compute delay statistics, detect conflicts, and identify bottlenecks."""
        t_now = state.clock.current_time

        active_trains = [st for st in state.train_states.values() if st.is_active or st.status == TrainStatus.IN_TRANSIT]
        all_trains = list(state.train_states.values())

        active_count = len(active_trains)
        delayed_trains = [st for st in all_trains if st.delay_minutes > 0.0]
        delayed_count = len(delayed_trains)

        total_delay = sum(st.delay_minutes for st in all_trains)
        peak_delay = 0.0
        peak_svc: Optional[str] = None

        for st in all_trains:
            if st.delay_minutes > peak_delay:
                peak_delay = st.delay_minutes
                peak_svc = st.service_id

        conflicts = self.detector.detect_all(state=state)
        bottlenecks_obj = self.identify_contested_bottlenecks(state=state, conflicts=conflicts)
        bottleneck_ids = [b.resource_id for b in bottlenecks_obj]

        affected_services: Set[str] = set()
        affected_resources: Set[str] = set(bottleneck_ids)

        for c in conflicts:
            affected_services.update(c.affected_service_ids)
            affected_resources.add(c.resource_id)

        for st in delayed_trains:
            affected_services.add(st.service_id)
            if st.current_station:
                affected_resources.add(st.current_station)
            if st.current_track_section:
                affected_resources.add(st.current_track_section)

        # Severity determination
        has_critical_conflict = any(c.severity == ConflictSeverity.CRITICAL for c in conflicts)
        has_major_conflict = any(c.severity == ConflictSeverity.MAJOR for c in conflicts)

        if total_delay > 120.0 or (has_critical_conflict and len(affected_services) >= 4):
            severity = OperationalSeverity.EMERGENCY
        elif total_delay > 60.0 or has_critical_conflict:
            severity = OperationalSeverity.CRITICAL
        elif total_delay > 20.0 or has_major_conflict or len(conflicts) > 0:
            severity = OperationalSeverity.WARNING
        elif total_delay > 5.0:
            severity = OperationalSeverity.ADVISORY
        else:
            severity = OperationalSeverity.NORMAL

        return OperationalSituation(
            timestamp=t_now,
            active_train_count=active_count,
            delayed_train_count=delayed_count,
            total_active_delay_minutes=total_delay,
            peak_delay_minutes=peak_delay,
            peak_delay_service=peak_svc,
            active_conflicts=conflicts,
            near_future_bottlenecks=bottleneck_ids,
            affected_services=sorted(list(affected_services)),
            affected_resources=sorted(list(affected_resources)),
            severity=severity,
            diagnostics={
                "conflict_count": len(conflicts),
                "active_services_count": active_count,
                "delayed_services_count": delayed_count,
            },
        )

    # -----------------------------------------------------------------------
    # 5. Recommendation Synthesis & Ranking Logic
    # -----------------------------------------------------------------------
    def _build_explainability(
        self,
        rec_type: RecommendationType,
        title: str,
        reason: str,
        affected_services: List[str],
        affected_resources: List[str],
        baseline_delay_minutes: float,
        expected_delay_minutes: float,
        expected_delay_savings: float,
        confidence_score: float,
        priority_tier: PriorityTier,
        situation: OperationalSituation,
        operational_context: str = "LIVE_OPERATIONAL",
        action_details: Optional[Dict[str, Any]] = None,
        optimization_result: Optional[OptimizationResult] = None,
    ) -> Tuple[
        str,
        SupportingEvidence,
        DelayAnalysis,
        CounterfactualAnalysis,
        ConfidenceMetrics,
        ConstraintExplanation,
        str,
        List[ReasoningStep],
    ]:
        category = map_type_to_category(rec_type)

        # 1. Supporting Evidence
        conf_strs: List[str] = []
        for c in situation.active_conflicts:
            if c.resource_id in affected_resources or any(s in affected_services for s in c.affected_service_ids):
                conf_strs.append(f"[{c.conflict_type.value}] on {c.resource_id} ({c.severity.value}): {c.description}")

        if not conf_strs:
            if category == "maintain schedule":
                conf_strs = ["Zero conflicts detected. Timetable operating within published safety bounds."]
            elif category == "holding":
                conf_strs = [f"Downstream bottleneck queue avoidance before admitting {', '.join(affected_services)} to mainline."]
            elif category == "platform reassignment":
                conf_strs = [f"Concurrent dwelling contention at platform/station {', '.join(affected_resources)}."]
            elif category == "speed management":
                conf_strs = [f"Track section geometry / speed caution zone active on {', '.join(affected_resources)}."]
            else:
                conf_strs = [f"Potential headway or junction slot conflict on {', '.join(affected_resources)}."]

        bottleneck_strs = [f"{r} ({self.classify_resource(r)})" for r in affected_resources] if affected_resources else ["Corridor Line Section"]

        evidence = SupportingEvidence(
            triggering_conflicts=conf_strs,
            contested_resources=list(affected_resources),
            affected_services=list(affected_services),
            bottlenecks=bottleneck_strs,
        )

        # 2. Delay Analysis
        tot_savings = round(max(0.0, expected_delay_savings), 2)
        dir_savings = round(tot_savings * 0.65, 2) if tot_savings > 0.0 else 0.0
        prop_savings = round(max(0.0, tot_savings - dir_savings), 2)

        delay_analysis = DelayAnalysis(
            direct_delay_reduction_minutes=dir_savings,
            propagated_delay_reduction_minutes=prop_savings,
            total_savings_minutes=tot_savings,
        )

        # 3. Counterfactual Analysis
        unmitigated_delay = max(baseline_delay_minutes, round(expected_delay_minutes + tot_savings, 2))
        if category == "precedence change":
            cf_impact = (
                f"If not applied, lower-priority service occupies bottleneck '{affected_resources[0] if affected_resources else 'throat'}', "
                f"forcing higher-priority service to queue upstream with up to {unmitigated_delay:.1f}m accumulated delay."
            )
            ripple_risk = "Severe queue propagation across following mainline and suburban services."
        elif category == "holding":
            cf_impact = (
                f"If not applied, service '{affected_services[0] if affected_services else 'train'}' departs into occupied downstream blocks, "
                f"resulting in unplanned en-route signal stops and {unmitigated_delay:.1f}m delay."
            )
            ripple_risk = "Mainline junction gridlock and headway compression behind delayed lead train."
        elif category == "platform reassignment":
            cf_impact = (
                f"If not applied, simultaneous occupation conflict occurs at {affected_resources[0] if affected_resources else 'platform'}, "
                f"holding arriving train outside home signals and blocking station throat lines."
            )
            ripple_risk = "Inbound corridor paralysis blocking all arriving Chennai services."
        elif category == "dispatch sequencing":
            cf_impact = (
                f"If not applied, unsynchronized junction arrival causes crossing interlocking deadlocks, "
                f"escalating total delay to {unmitigated_delay:.1f}m."
            )
            ripple_risk = "Dual-track throat conflict blocking reverse-direction traffic."
        elif category == "speed management":
            cf_impact = (
                f"If not applied, emergency deceleration at caution boundary triggers severe dynamic headway braking waves."
            )
            ripple_risk = "Compressive braking shockwaves affecting following train headways."
        else:
            cf_impact = "If unnecessary dispatch interventions are imposed, timetable stability would degrade and create artificial buffer delays."
            ripple_risk = "None under current on-time schedule."

        counterfactual = CounterfactualAnalysis(
            unmitigated_delay_minutes=unmitigated_delay,
            impact_if_not_applied=cf_impact,
            downstream_ripple_risk=ripple_risk,
        )

        # 4. Confidence Metrics
        constraints_count = (
            5 if category in ("precedence change", "dispatch sequencing")
            else 4 if category in ("holding", "platform reassignment")
            else 2
        )
        opt_agreement = (
            1.0 if (optimization_result and optimization_result.status == "OPTIMAL")
            else 0.95 if (optimization_result and optimization_result.status == "FEASIBLE")
            else 0.90
        )
        conf_metrics = ConfidenceMetrics(
            supporting_constraints_count=constraints_count,
            optimization_agreement=opt_agreement,
            conflict_severity_basis=priority_tier.value,
        )

        # 5. Constraint Explanation
        c_expl = ConstraintExplanation(
            headway="Enforces minimum 3.0 min safety headway buffer between consecutive movements along the block section.",
            platform_capacity="Restricts concurrent platform track occupancy to maximum 1 train per platform track.",
            route_occupancy="Guarantees absolute block section mutual exclusion: trailing service cannot enter until lead service exits.",
            junction_contention="Interlocking route reservation prevents simultaneous conflicting movements through shared crossing throat.",
        )

        # 6. Ranking Explanation
        ranking_expl = (
            f"Ranked Tier {priority_tier.value} based on resolving {self.classify_resource(affected_resources[0] if affected_resources else '')} contention, "
            f"recovering {tot_savings:.1f}m delay across {len(affected_services)} services with {int(confidence_score * 100)}% solver confidence."
        )

        # 7. Reasoning Path (5 distinct steps)
        steps = [
            ReasoningStep(
                step_number=1,
                phase="TRIGGER",
                title="Operational Disturbance Detected",
                detail=f"Detected disturbance on {', '.join(affected_services) if affected_services else 'network'} with {baseline_delay_minutes:.1f}m baseline delay.",
            ),
            ReasoningStep(
                step_number=2,
                phase="BOTTLENECK",
                title="Contested Bottleneck Isolated",
                detail=f"Identified choke-point on {', '.join(affected_resources) if affected_resources else 'corridor'} ({self.classify_resource(affected_resources[0] if affected_resources else '')}).",
            ),
            ReasoningStep(
                step_number=3,
                phase="CONSTRAINTS",
                title="Physical Safety Boundaries Evaluated",
                detail="Evaluated 3-min headway buffers, single-block occupancy rules, and train class priority weighting.",
            ),
            ReasoningStep(
                step_number=4,
                phase="DECISION",
                title=f"Optimal Directive: {category.title()}",
                detail=f"{title}. {reason}",
            ),
            ReasoningStep(
                step_number=5,
                phase="OUTCOME",
                title="Impact & Counterfactual Assurance",
                detail=f"Yields {tot_savings:.1f}m total delay savings. Counterfactual prevents unmitigated {unmitigated_delay:.1f}m ripple delay.",
            ),
        ]

        return category, evidence, delay_analysis, counterfactual, conf_metrics, c_expl, ranking_expl, steps

    def generate_recommendations(
        self,
        situation: OperationalSituation,
        optimization_result: Optional[OptimizationResult] = None,
        baseline_result: Optional[OptimizationResult] = None,
        scenario_comparison: Optional[ScenarioComparison] = None,
        operational_context: str = "LIVE_OPERATIONAL",
        track_speed_restrictions: Optional[Dict[str, float]] = None,
        blocked_sections: Optional[List[str]] = None,
    ) -> List[Recommendation]:
        """Synthesize explainable recommendations from situation analysis and optimization comparisons."""
        recommendations: List[Recommendation] = []

        # Case INFEASIBLE: When solver proves no feasible schedule can be constructed
        if optimization_result is not None and optimization_result.status not in ("OPTIMAL", "FEASIBLE"):
            situation.severity = OperationalSeverity.EMERGENCY
            blocked_list = []
            if blocked_sections:
                blocked_list.extend(blocked_sections)
            if scenario_comparison and hasattr(scenario_comparison, "scenario") and scenario_comparison.scenario:
                scen = scenario_comparison.scenario
                if scen.blocked_sections:
                    for b in scen.blocked_sections:
                        if b not in blocked_list:
                            blocked_list.append(b)
                if scen.track_speed_restrictions:
                    for sec_id, tt in scen.track_speed_restrictions.items():
                        if tt >= 9000.0 and sec_id not in blocked_list:
                            blocked_list.append(sec_id)
            if not blocked_list and situation.affected_resources:
                blocked_list = list(situation.affected_resources)
            blocked_str = ", ".join(sorted(blocked_list)) if blocked_list else "None"

            title = f"No feasible schedule with the blocked resources: {blocked_str}"
            reason = f"The mathematical optimization solver proved INFEASIBLE: no conflict-free timetable can be constructed with blocked resources ({blocked_str}). Physical track capacity is 0."
            cat, ev, da, cf, cm, ce, re, st = self._build_explainability(
                rec_type=RecommendationType.NO_FEASIBLE_SCHEDULE,
                title=title,
                reason=reason,
                affected_services=situation.affected_services,
                affected_resources=sorted(blocked_list),
                baseline_delay_minutes=situation.total_active_delay_minutes,
                expected_delay_minutes=situation.total_active_delay_minutes,
                expected_delay_savings=0.0,
                confidence_score=1.0,
                priority_tier=PriorityTier.CRITICAL,
                situation=situation,
                operational_context=operational_context,
                optimization_result=optimization_result,
            )
            re = f"Ranked #1 (CRITICAL) - Emergency Directive: {title}"
            rec = Recommendation(
                recommendation_id=self._next_rec_id(),
                recommendation_type=RecommendationType.NO_FEASIBLE_SCHEDULE,
                category=cat,
                title=title,
                reason=reason,
                affected_services=situation.affected_services,
                affected_resources=sorted(blocked_list),
                baseline_delay_minutes=situation.total_active_delay_minutes,
                expected_delay_minutes=situation.total_active_delay_minutes,
                expected_delay_savings=0.0,
                confidence_score=1.0,
                priority_tier=PriorityTier.CRITICAL,
                evidence_basis="Mathematical Solver Feasibility Proof (INFEASIBLE)",
                is_actionable=True,
                operational_context=operational_context,
                supporting_evidence=ev,
                delay_analysis=da,
                counterfactual_analysis=cf,
                confidence_metrics=cm,
                constraint_explanation=ce,
                ranking_explanation=re,
                reasoning_path=st,
            )
            return [rec]

        # Case A: Normal operation with no active conflicts or significant delay
        if (
            situation.severity == OperationalSeverity.NORMAL
            and not situation.active_conflicts
            and situation.total_active_delay_minutes <= 5.0
            and not track_speed_restrictions
        ):
            title = "Maintain Current Published Timetable"
            reason = "All active services are running within scheduled tolerance (total delay < 5m, 0 conflicts detected). No intervention required."
            cat, ev, da, cf, cm, ce, re, st = self._build_explainability(
                rec_type=RecommendationType.MAINTAIN_CURRENT_SCHEDULE,
                title=title,
                reason=reason,
                affected_services=situation.affected_services,
                affected_resources=[],
                baseline_delay_minutes=situation.total_active_delay_minutes,
                expected_delay_minutes=situation.total_active_delay_minutes,
                expected_delay_savings=0.0,
                confidence_score=1.0,
                priority_tier=PriorityTier.LOW,
                situation=situation,
                operational_context=operational_context,
                optimization_result=optimization_result,
            )
            re = "Ranked #1 (LOW) based on zero conflicts and preserving timetable integrity with 100% confidence."
            recommendations.append(
                Recommendation(
                    recommendation_id=self._next_rec_id(),
                    recommendation_type=RecommendationType.MAINTAIN_CURRENT_SCHEDULE,
                    category=cat,
                    title=title,
                    reason=reason,
                    affected_services=situation.affected_services,
                    affected_resources=[],
                    baseline_delay_minutes=situation.total_active_delay_minutes,
                    expected_delay_minutes=situation.total_active_delay_minutes,
                    expected_delay_savings=0.0,
                    confidence_score=1.0,
                    priority_tier=PriorityTier.LOW,
                    evidence_basis="Simulation State Engine (0 active conflicts, schedule on-time)",
                    is_actionable=False,
                    operational_context=operational_context,
                    supporting_evidence=ev,
                    delay_analysis=da,
                    counterfactual_analysis=cf,
                    confidence_metrics=cm,
                    constraint_explanation=ce,
                    ranking_explanation=re,
                    reasoning_path=st,
                )
            )
            return recommendations

        # Case B: Synthesize recommendations from CP-SAT optimization results
        if optimization_result is not None:
            dep_lookup: Dict[Tuple[str, str], float] = {}
            orig_dep_lookup: Dict[Tuple[str, str], float] = {}
            for s_id, adjs in optimization_result.adjusted_timetables.items():
                for a in adjs:
                    if a.adjusted_departure is not None:
                        dep_lookup[(s_id, a.station_id)] = a.adjusted_departure
                    if a.original_departure is not None:
                        orig_dep_lookup[(s_id, a.station_id)] = a.original_departure

            seen_pair_precedence: Set[Tuple[str, str]] = set()

            # 1. Meaningful Precedence decisions (swapping train order, overtaking, or close headway conflict at junctions)
            for prec in optimization_result.precedence_decisions:
                pair_key = (min(prec.first_service_id, prec.second_service_id), max(prec.first_service_id, prec.second_service_id))
                if pair_key in seen_pair_precedence:
                    continue

                t1 = dep_lookup.get((prec.first_service_id, prec.resource_id))
                t2 = dep_lookup.get((prec.second_service_id, prec.resource_id))
                orig_t1 = orig_dep_lookup.get((prec.first_service_id, prec.resource_id))
                orig_t2 = orig_dep_lookup.get((prec.second_service_id, prec.resource_id))

                is_swap = (orig_t1 is not None and orig_t2 is not None and orig_t1 > orig_t2 and t1 is not None and t2 is not None and t1 < t2)
                is_close_headway = (t1 is not None and t2 is not None and abs(t1 - t2) <= 10.0 and ("JCT" in prec.resource_id or situation.total_active_delay_minutes > 5.0))

                if is_swap or is_close_headway:
                    seen_pair_precedence.add(pair_key)
                    svc_a = self.network.services.get(prec.first_service_id)
                    svc_b = self.network.services.get(prec.second_service_id)

                    prio_a = svc_a.priority_class if svc_a else "NORMAL"
                    prio_b = svc_b.priority_class if svc_b else "NORMAL"

                    prio_tier = PriorityTier.CRITICAL if ("HIGH" in (prio_a, prio_b) or is_swap) else PriorityTier.HIGH
                    reason_narrative = (
                        f"Prioritize higher-weight service '{prec.first_service_id}' ({prio_a}) over "
                        f"'{prec.second_service_id}' ({prio_b}) at key resource '{prec.resource_id}'. "
                        f"{'Active train overtaking / priority swap enforced.' if is_swap else 'Maintains safety headway separation and prevents queue formation.'}"
                    )

                    savings = max(0.0, (baseline_result.total_delay - optimization_result.total_delay)) if baseline_result else 0.0
                    title = f"Precedence Priority at {prec.resource_id}: {prec.first_service_id} before {prec.second_service_id}"
                    action_details = {
                        "resource_id": prec.resource_id,
                        "lead_service": prec.first_service_id,
                        "following_service": prec.second_service_id,
                        "is_order_swap": is_swap,
                    }

                    cat, ev, da, cf, cm, ce, re, st = self._build_explainability(
                        rec_type=RecommendationType.PRECEDENCE_OVERRIDE,
                        title=title,
                        reason=reason_narrative,
                        affected_services=[prec.first_service_id, prec.second_service_id],
                        affected_resources=[prec.resource_id],
                        baseline_delay_minutes=baseline_result.total_delay if baseline_result else situation.total_active_delay_minutes,
                        expected_delay_minutes=optimization_result.total_delay,
                        expected_delay_savings=savings,
                        confidence_score=1.0 if optimization_result.status == "OPTIMAL" else 0.9,
                        priority_tier=prio_tier,
                        situation=situation,
                        operational_context=operational_context,
                        action_details=action_details,
                        optimization_result=optimization_result,
                    )

                    recommendations.append(
                        Recommendation(
                            recommendation_id=self._next_rec_id(),
                            recommendation_type=RecommendationType.PRECEDENCE_OVERRIDE,
                            category=cat,
                            title=title,
                            reason=reason_narrative,
                            affected_services=[prec.first_service_id, prec.second_service_id],
                            affected_resources=[prec.resource_id],
                            baseline_delay_minutes=baseline_result.total_delay if baseline_result else situation.total_active_delay_minutes,
                            expected_delay_minutes=optimization_result.total_delay,
                            expected_delay_savings=savings,
                            confidence_score=1.0 if optimization_result.status == "OPTIMAL" else 0.9,
                            priority_tier=prio_tier,
                            evidence_basis=f"CP-SAT Integer Solver (Status: {optimization_result.status}, Solve time: {optimization_result.computation_time_seconds:.3f}s)",
                            action_details=action_details,
                            is_actionable=True,
                            operational_context=operational_context,
                            supporting_evidence=ev,
                            delay_analysis=da,
                            counterfactual_analysis=cf,
                            confidence_metrics=cm,
                            constraint_explanation=ce,
                            ranking_explanation=re,
                            reasoning_path=st,
                        )
                    )

            # 2. Platform resource allocations: only for multi-service contention
            station_services: Dict[str, Set[str]] = defaultdict(set)
            for r in optimization_result.resource_decisions:
                if r.resource_type == "PLATFORM":
                    station_services[r.node_or_section_id].add(r.service_id)

            for alloc in optimization_result.resource_decisions:
                if alloc.resource_type == "PLATFORM" and len(station_services[alloc.node_or_section_id]) > 1:
                    title = f"Platform Assignment at {alloc.node_or_section_id}: {alloc.service_id} -> {alloc.allocated_resource_id}"
                    reason = f"Assign service '{alloc.service_id}' to platform '{alloc.allocated_resource_id}' at station '{alloc.node_or_section_id}' to eliminate concurrent dwelling conflict."
                    action_details = {
                        "service_id": alloc.service_id,
                        "station_id": alloc.node_or_section_id,
                        "platform_id": alloc.allocated_resource_id,
                    }

                    cat, ev, da, cf, cm, ce, re, st = self._build_explainability(
                        rec_type=RecommendationType.PLATFORM_REASSIGNMENT,
                        title=title,
                        reason=reason,
                        affected_services=[alloc.service_id],
                        affected_resources=[alloc.allocated_resource_id, alloc.node_or_section_id],
                        baseline_delay_minutes=0.0,
                        expected_delay_minutes=0.0,
                        expected_delay_savings=0.0,
                        confidence_score=1.0,
                        priority_tier=PriorityTier.MEDIUM,
                        situation=situation,
                        operational_context=operational_context,
                        action_details=action_details,
                        optimization_result=optimization_result,
                    )

                    recommendations.append(
                        Recommendation(
                            recommendation_id=self._next_rec_id(),
                            recommendation_type=RecommendationType.PLATFORM_REASSIGNMENT,
                            category=cat,
                            title=title,
                            reason=reason,
                            affected_services=[alloc.service_id],
                            affected_resources=[alloc.allocated_resource_id, alloc.node_or_section_id],
                            baseline_delay_minutes=0.0,
                            expected_delay_minutes=0.0,
                            expected_delay_savings=0.0,
                            confidence_score=1.0,
                            priority_tier=PriorityTier.MEDIUM,
                            evidence_basis="CP-SAT Discrete Platform Variable",
                            action_details=action_details,
                            is_actionable=True,
                            operational_context=operational_context,
                            supporting_evidence=ev,
                            delay_analysis=da,
                            counterfactual_analysis=cf,
                            confidence_metrics=cm,
                            constraint_explanation=ce,
                            ranking_explanation=re,
                            reasoning_path=st,
                        )
                    )

            # 3. Schedule timing adjustments & holding actions (holds >= 5.0m at dispatching origin)
            for adj_list in optimization_result.adjusted_timetables.values():
                for adj in adj_list:
                    if adj.delay_minutes >= 5.0 and adj.stop_sequence == 1:
                        title = f"Regulated Dispatch Hold: {adj.service_id} at {adj.station_id} (+{adj.delay_minutes:.1f}m)"
                        reason = (
                            f"Regulate departure of service '{adj.service_id}' at '{adj.station_id}' to "
                            f"{adj.adjusted_departure_str or 'adjusted time'} (held +{adj.delay_minutes:.1f}m) "
                            f"to preserve safety headway separation and allow preceding mainline corridor clearance."
                        )
                        action_details = {
                            "service_id": adj.service_id,
                            "station_id": adj.station_id,
                            "holding_duration_minutes": adj.delay_minutes,
                            "scheduled_departure": adj.original_departure,
                            "recommended_departure": adj.adjusted_departure,
                        }

                        cat, ev, da, cf, cm, ce, re, st = self._build_explainability(
                            rec_type=RecommendationType.HOLD_AT_STATION,
                            title=title,
                            reason=reason,
                            affected_services=[adj.service_id],
                            affected_resources=[adj.station_id],
                            baseline_delay_minutes=adj.delay_minutes,
                            expected_delay_minutes=adj.delay_minutes,
                            expected_delay_savings=0.0,
                            confidence_score=1.0 if optimization_result.status == "OPTIMAL" else 0.9,
                            priority_tier=PriorityTier.HIGH,
                            situation=situation,
                            operational_context=operational_context,
                            action_details=action_details,
                            optimization_result=optimization_result,
                        )

                        recommendations.append(
                            Recommendation(
                                recommendation_id=self._next_rec_id(),
                                recommendation_type=RecommendationType.HOLD_AT_STATION,
                                category=cat,
                                title=title,
                                reason=reason,
                                affected_services=[adj.service_id],
                                affected_resources=[adj.station_id],
                                baseline_delay_minutes=adj.delay_minutes,
                                expected_delay_minutes=adj.delay_minutes,
                                expected_delay_savings=0.0,
                                confidence_score=1.0 if optimization_result.status == "OPTIMAL" else 0.9,
                                priority_tier=PriorityTier.HIGH,
                                evidence_basis=f"CP-SAT Timetable Adjustment Interval (Departure shifted to {adj.adjusted_departure_str})",
                                action_details=action_details,
                                is_actionable=True,
                                operational_context=operational_context,
                                supporting_evidence=ev,
                                delay_analysis=da,
                                counterfactual_analysis=cf,
                                confidence_metrics=cm,
                                constraint_explanation=ce,
                                ranking_explanation=re,
                                reasoning_path=st,
                            )
                        )

            # 4. Speed restriction caution order recommendations
            tsr_map = track_speed_restrictions or (
                scenario_comparison.scenario.track_speed_restrictions
                if (scenario_comparison and hasattr(scenario_comparison, "scenario") and scenario_comparison.scenario and scenario_comparison.scenario.track_speed_restrictions)
                else {}
            )
            if tsr_map:
                for sec_id, extra_t in tsr_map.items():
                    title = f"Speed Management Caution Order: {sec_id} (+{extra_t:.1f}m)"
                    reason = (
                        f"Impose regulated speed caution on track section '{sec_id}' (+{extra_t:.1f}m traversal time) "
                        f"to guarantee stopping sight distance and safe corridor block clearance."
                    )
                    action_details = {"track_section_id": sec_id, "extra_travel_time_minutes": extra_t}
                    cat, ev, da, cf, cm, ce, re, st = self._build_explainability(
                        rec_type=RecommendationType.SPEED_RESTRICTION_ADJUSTMENT,
                        title=title,
                        reason=reason,
                        affected_services=situation.affected_services,
                        affected_resources=[sec_id],
                        baseline_delay_minutes=extra_t,
                        expected_delay_minutes=extra_t,
                        expected_delay_savings=0.0,
                        confidence_score=1.0,
                        priority_tier=PriorityTier.HIGH,
                        situation=situation,
                        operational_context=operational_context,
                        action_details=action_details,
                        optimization_result=optimization_result,
                    )
                    recommendations.append(
                        Recommendation(
                            recommendation_id=self._next_rec_id(),
                            recommendation_type=RecommendationType.SPEED_RESTRICTION_ADJUSTMENT,
                            category=cat,
                            title=title,
                            reason=reason,
                            affected_services=situation.affected_services,
                            affected_resources=[sec_id],
                            baseline_delay_minutes=extra_t,
                            expected_delay_minutes=extra_t,
                            expected_delay_savings=0.0,
                            confidence_score=1.0,
                            priority_tier=PriorityTier.HIGH,
                            evidence_basis="Civil Engineering Temporary Speed Restriction (TSR)",
                            action_details=action_details,
                            is_actionable=True,
                            operational_context=operational_context,
                            supporting_evidence=ev,
                            delay_analysis=da,
                            counterfactual_analysis=cf,
                            confidence_metrics=cm,
                            constraint_explanation=ce,
                            ranking_explanation=re,
                            reasoning_path=st,
                        )
                    )

        # Case C: Fallback / Conflict-driven recommendations when optimizer result is not directly passed
        if not recommendations and situation.active_conflicts:
            prioritized_conflicts = self.prioritize_conflicts(situation.active_conflicts)
            for pc in prioritized_conflicts:
                c = pc.conflict
                prio_tier = PriorityTier.CRITICAL if c.severity == ConflictSeverity.CRITICAL else PriorityTier.HIGH
                rec_type = RecommendationType.JUNCTION_SLOT_RESCHEDULING if pc.resource_type == "JUNCTION" else RecommendationType.HOLD_AT_STATION
                title = f"Conflict Resolution at {c.resource_id}: {c.conflict_type.value}"
                reason = f"Active conflict detected on {pc.resource_type} '{c.resource_id}': {c.description}. Enforce slot separation between contending trains."
                action_details = {"conflict_id": c.conflict_id, "resource_id": c.resource_id, "priority_score": pc.priority_score}

                cat, ev, da, cf, cm, ce, re, st = self._build_explainability(
                    rec_type=rec_type,
                    title=title,
                    reason=reason,
                    affected_services=c.affected_service_ids,
                    affected_resources=[c.resource_id],
                    baseline_delay_minutes=situation.total_active_delay_minutes,
                    expected_delay_minutes=situation.total_active_delay_minutes,
                    expected_delay_savings=0.0,
                    confidence_score=0.95,
                    priority_tier=prio_tier,
                    situation=situation,
                    operational_context=operational_context,
                    action_details=action_details,
                    optimization_result=optimization_result,
                )

                recommendations.append(
                    Recommendation(
                        recommendation_id=self._next_rec_id(),
                        recommendation_type=rec_type,
                        category=cat,
                        title=title,
                        reason=reason,
                        affected_services=c.affected_service_ids,
                        affected_resources=[c.resource_id],
                        baseline_delay_minutes=situation.total_active_delay_minutes,
                        expected_delay_minutes=situation.total_active_delay_minutes,
                        expected_delay_savings=0.0,
                        confidence_score=0.95,
                        priority_tier=prio_tier,
                        evidence_basis="Deterministic Conflict Detection Engine",
                        action_details=action_details,
                        is_actionable=True,
                        operational_context=operational_context,
                        supporting_evidence=ev,
                        delay_analysis=da,
                        counterfactual_analysis=cf,
                        confidence_metrics=cm,
                        constraint_explanation=ce,
                        ranking_explanation=re,
                        reasoning_path=st,
                    )
                )

        # Deterministic recommendation ranking: Priority Tier -> expected_delay_savings -> confidence_score -> ID
        tier_order = {PriorityTier.CRITICAL: 0, PriorityTier.HIGH: 1, PriorityTier.MEDIUM: 2, PriorityTier.LOW: 3}
        recommendations.sort(
            key=lambda r: (
                tier_order.get(r.priority_tier, 99),
                -r.expected_delay_savings,
                -r.confidence_score,
                r.recommendation_id,
            )
        )

        # Deterministic ranking explanation assignment reflecting final sorted positions
        for rank, rec in enumerate(recommendations, start=1):
            rec.ranking_explanation = (
                f"Ranked #{rank} ({rec.priority_tier.value}) based on resolving "
                f"{self.classify_resource(rec.affected_resources[0] if rec.affected_resources else '')} contention, "
                f"recovering {rec.expected_delay_savings:.1f}m delay across "
                f"{len(rec.affected_services)} services with {int(rec.confidence_score * 100)}% solver confidence."
            )

        return recommendations

    # -----------------------------------------------------------------------
    # 6. What-If Scenario Decision Support
    # -----------------------------------------------------------------------
    def evaluate_what_if_scenario(
        self,
        scenario: Scenario,
        service_ids: Optional[List[str]] = None,
    ) -> DecisionSupportAssessment:
        """Run What-If scenario through baseline + CP-SAT optimizer and synthesize explainable decisions."""
        scen_copy = copy.deepcopy(scenario)
        if service_ids:
            scen_copy.affected_service_ids = list(service_ids)

        comparison = self.scenario_runner.run_scenario(
            scenario=scen_copy,
        )

        solve_time = comparison.computation_time_seconds
        solver_status = comparison.optimization_status

        affected_svcs = (
            list(comparison.optimized_result.adjusted_timetables.keys())
            if (comparison.optimized_result and comparison.optimized_result.adjusted_timetables)
            else scenario.affected_service_ids
        )

        conflicts_list = (
            getattr(comparison, "detected_conflicts", None)
            or (comparison.baseline_result.unresolved_conflicts if comparison.baseline_result and comparison.baseline_result.unresolved_conflicts else None)
            or scenario.injected_conflicts
            or []
        )

        # 1. Prioritize conflicts
        prioritized_conflicts = self.prioritize_conflicts(conflicts_list)

        # 2. Identify bottlenecks
        bottlenecks_obj = self.identify_contested_bottlenecks(
            conflicts=conflicts_list,
            optimization_result=comparison.optimized_result,
        )
        bottleneck_ids = [b.resource_id for b in bottlenecks_obj]

        # 3. Analyze service delay impacts
        direct_delay_map = dict(scenario.departure_delays)
        for s, d in scenario.station_delays.items():
            val = sum(d.values()) if isinstance(d, dict) else float(d)
            direct_delay_map[s] = max(direct_delay_map.get(s, 0.0), val)

        service_delay_impacts = self.analyze_service_delay_impacts(
            service_ids=affected_svcs,
            direct_delays=direct_delay_map,
            optimization_result=comparison.optimized_result,
            baseline_result=comparison.baseline_result,
        )

        is_sol = comparison.optimization_status in ("OPTIMAL", "FEASIBLE")

        # 4. Formulate OperationalSituation
        situation = OperationalSituation(
            timestamp=0.0,
            active_train_count=len(service_ids) if service_ids else len(affected_svcs) if affected_svcs else 4,
            delayed_train_count=len(scenario.departure_delays) + len(scenario.station_delays),
            total_active_delay_minutes=comparison.baseline_total_delay,
            peak_delay_minutes=comparison.baseline_max_delay,
            peak_delay_service=next(iter(scenario.departure_delays.keys())) if scenario.departure_delays else None,
            active_conflicts=conflicts_list,
            near_future_bottlenecks=bottleneck_ids,
            affected_services=affected_svcs,
            affected_resources=bottleneck_ids,
            severity=(
                OperationalSeverity.EMERGENCY if not is_sol
                else OperationalSeverity.CRITICAL if comparison.baseline_total_delay > 60.0
                else OperationalSeverity.WARNING if comparison.baseline_total_delay > 20.0
                else OperationalSeverity.ADVISORY if comparison.baseline_total_delay > 5.0
                else OperationalSeverity.NORMAL
            ),
            diagnostics={
                "scenario_id": scenario.scenario_id,
                "name": scenario.name,
                "initial_conflicts_count": comparison.initial_conflicts,
            },
        )

        # 5. Generate and rank recommendations
        ctx = "LIVE_OPERATIONAL" if (scenario.scenario_id and "LIVE" in scenario.scenario_id.upper()) else "HYPOTHETICAL_SCENARIO"
        recommendations = self.generate_recommendations(
            situation=situation,
            optimization_result=comparison.optimized_result,
            baseline_result=comparison.feasible_baseline_result or comparison.baseline_result,
            scenario_comparison=comparison,
            operational_context=ctx,
            track_speed_restrictions=scenario.track_speed_restrictions,
            blocked_sections=scenario.blocked_sections,
        )

        # 6. Build BaselineOptimizationComparison
        pub_ref_delay = getattr(comparison, "published_total_delay", None)
        if pub_ref_delay is None:
            pub_ref_delay = getattr(comparison, "published_baseline_total_delay", 0.0)

        three_tier_tt = comparison.build_three_tier_timetable(self.network) if is_sol else []
        pub_tt = {
            s_id: [a.to_dict() for a in adjs]
            for s_id, adjs in comparison.published_baseline_result.adjusted_timetables.items()
        } if comparison.published_baseline_result else {}
        feasible_tt = {
            s_id: [a.to_dict() for a in adjs]
            for s_id, adjs in comparison.baseline_result.adjusted_timetables.items()
        } if comparison.baseline_result else {}
        optimized_tt = {
            s_id: [a.to_dict() for a in adjs]
            for s_id, adjs in comparison.optimized_result.adjusted_timetables.items()
        } if (comparison.optimized_result and is_sol) else {}

        comp_detail = BaselineOptimizationComparison(
            published_reference_delay_minutes=pub_ref_delay,
            feasible_baseline_delay_minutes=comparison.baseline_total_delay,
            feasible_baseline_max_delay_minutes=comparison.baseline_max_delay,
            feasible_baseline_conflicts_remaining=comparison.baseline_unresolved_conflicts if hasattr(comparison, "baseline_unresolved_conflicts") else len(conflicts_list),
            feasible_baseline_throughput=comparison.baseline_throughput if hasattr(comparison, "baseline_throughput") else len(affected_svcs),
            optimized_delay_minutes=comparison.optimized_total_delay if is_sol else None,
            optimized_max_delay_minutes=comparison.optimized_max_delay if is_sol else None,
            optimized_conflicts_remaining=comparison.optimized_unresolved_conflicts if (hasattr(comparison, "optimized_unresolved_conflicts") and is_sol) else 0,
            optimized_throughput=comparison.optimized_throughput if (hasattr(comparison, "optimized_throughput") and is_sol) else len(affected_svcs),
            delay_savings_minutes=comparison.delay_savings_minutes if is_sol else None,
            delay_savings_percent=comparison.delay_savings_percent if is_sol else None,
            solver_status=solver_status,
            solution_available=is_sol,
            solve_time_seconds=solve_time,
            three_tier_timetable=three_tier_tt,
            published_timetables=pub_tt,
            feasible_timetables=feasible_tt,
            optimized_timetables=optimized_tt,
            corridor_performance=comparison.build_corridor_performance_summary(self.network) if is_sol else [],
        )

        # 7. Build Controller Summary
        controller_summary = {
            "scenario_id": scenario.scenario_id,
            "scenario_name": scenario.name,
            "operational_severity": situation.severity.value,
            "affected_train_count": len(affected_svcs),
            "critical_conflicts_count": len(prioritized_conflicts),
            "bottlenecks_count": len(bottlenecks_obj),
            "baseline_delay_minutes": round(comparison.baseline_total_delay, 2),
            "optimized_delay_minutes": round(comparison.optimized_total_delay, 2) if (is_sol and comparison.optimized_total_delay is not None) else None,
            "delay_savings_minutes": round(comparison.delay_savings_minutes, 2) if (is_sol and comparison.delay_savings_minutes is not None) else None,
            "delay_savings_percent": round(comparison.delay_savings_percent, 2) if (is_sol and comparison.delay_savings_percent is not None) else None,
            "solver_status": solver_status,
            "solution_available": is_sol,
        }

        h = hashlib.sha256(
            f"{scenario.scenario_id}_{comparison.baseline_total_delay}_{comparison.optimized_total_delay}_{len(recommendations)}_{solver_status}".encode()
        ).hexdigest()[:12]

        return DecisionSupportAssessment(
            situation=situation,
            recommendations=recommendations,
            what_if_scenario_id=scenario.scenario_id,
            baseline_total_delay=comparison.baseline_total_delay,
            optimized_total_delay=comparison.optimized_total_delay if is_sol else None,
            net_delay_savings=comparison.delay_savings_minutes if is_sol else None,
            net_delay_savings_percent=comparison.delay_savings_percent if is_sol else None,
            solver_status=solver_status,
            solution_available=is_sol,
            solve_time_seconds=solve_time,
            deterministic_hash=h,
            prioritized_conflicts=prioritized_conflicts,
            identified_bottlenecks=bottlenecks_obj,
            service_delay_impacts=service_delay_impacts,
            comparison_detail=comp_detail,
            controller_summary=controller_summary,
            metadata={"scenario_name": scenario.name, "scenario_desc": scenario.description},
        )
