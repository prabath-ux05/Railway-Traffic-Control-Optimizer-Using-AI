"""
backend/app/pipeline.py
~~~~~~~~~~~~~~~~~~~~~~~
End-to-End Integrated Railway Traffic Optimization Pipeline.

Coordinates the complete 6-stage lifecycle:
1. Simulation & Digital Twin State
2. Real-time Conflict Detection & Prioritization
3. Physical Feasible FIFO Baseline Scheduling
4. Mixed-Integer CP-SAT Optimization
5. Direct vs Propagated Delay-Impact Analysis & Bottleneck Identification
6. Decision Support Diagnosis, Ranked Recommendations, & Multi-Format Reporting

Provides a single synchronous orchestration entrypoint for backend API services and CLI tools.
"""

from dataclasses import dataclass, field
import hashlib
import json
import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from simulation.clock import SimulationClock, minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictDetector, ConflictSeverity, ConflictType
from simulation.network import Network, Route, Service, TrackSection
from simulation.simulator import TrainSimulator
from simulation.state import SimulationState, TrackSectionOccupancy, TrainRuntimeState, TrainStatus
from optimization.scheduler import BaselineScheduler, FeasibleBaselineScheduler, OptimizationResult
from optimization.model import (
    OptimizationModel,
    OptimizationRequest,
    ServiceTimetableAdjustment,
)
from optimization.scenarios import Scenario, ScenarioComparison, ScenarioRunner
from optimization.solver import CPSATScheduler
from decision_support.advisor import DecisionSupportAdvisor
from decision_support.models import (
    BaselineOptimizationComparison,
    ContestedBottleneck,
    DecisionSupportAssessment,
    OperationalSeverity,
    OperationalSituation,
    PrioritizedConflict,
    PriorityTier,
    Recommendation,
    RecommendationType,
    ServiceDelayImpact,
)


def _load_default_network() -> Network:
    net = Network()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    net.load_from_directory(os.path.join(base_dir, "data", "infrastructure"))
    net.load_trains(os.path.join(base_dir, "data", "trains", "train_identity", "trains.json"))
    net.load_services(os.path.join(base_dir, "data", "trains", "service_definitions", "services.json"))
    net.load_timetable(os.path.join(base_dir, "data", "trains", "published_timetables", "timetable.json"))
    return net


@dataclass
class PipelineExecutionResult:
    """Comprehensive container aggregating the complete end-to-end railway optimization output."""
    scenario_id: Optional[str]
    scenario_name: str
    simulation_timestamp: float
    simulation_timestamp_str: str
    active_services_count: int
    delayed_services_count: int
    total_baseline_delay_minutes: float
    total_optimized_delay_minutes: Optional[float]
    net_delay_savings_minutes: Optional[float]
    net_delay_savings_percent: Optional[float]
    solver_status: str
    solve_time_seconds: float
    prioritized_conflicts: List[PrioritizedConflict]
    identified_bottlenecks: List[ContestedBottleneck]
    service_delay_impacts: List[ServiceDelayImpact]
    recommendations: List[Recommendation]
    baseline_comparison: BaselineOptimizationComparison
    assessment: DecisionSupportAssessment
    deterministic_hash: str
    solution_available: bool = True
    fifo_weighted_objective: Optional[float] = None
    optimized_weighted_objective: Optional[float] = None
    objective_mode: str = "WEIGHTED"
    execution_time_seconds: float = 0.0
    raw_state: Optional[SimulationState] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "simulation_timestamp": self.simulation_timestamp,
            "simulation_timestamp_str": self.simulation_timestamp_str,
            "active_services_count": self.active_services_count,
            "delayed_services_count": self.delayed_services_count,
            "total_baseline_delay_minutes": round(self.total_baseline_delay_minutes, 2),
            "total_optimized_delay_minutes": round(self.total_optimized_delay_minutes, 2) if self.total_optimized_delay_minutes is not None else None,
            "net_delay_savings_minutes": round(self.net_delay_savings_minutes, 2) if self.net_delay_savings_minutes is not None else None,
            "net_delay_savings_percent": round(self.net_delay_savings_percent, 2) if self.net_delay_savings_percent is not None else None,
            "solver_status": self.solver_status,
            "solution_available": self.solution_available,
            "fifo_weighted_objective": round(self.fifo_weighted_objective, 2) if self.fifo_weighted_objective is not None else None,
            "optimized_weighted_objective": round(self.optimized_weighted_objective, 2) if self.optimized_weighted_objective is not None else None,
            "objective_mode": self.objective_mode,
            "solve_time_seconds": round(self.solve_time_seconds, 3),
            "execution_time_seconds": round(self.execution_time_seconds, 3),
            "deterministic_hash": self.deterministic_hash,
            "prioritized_conflicts": [pc.to_dict() for pc in self.prioritized_conflicts],
            "identified_bottlenecks": [ib.to_dict() for ib in self.identified_bottlenecks],
            "service_delay_impacts": [sdi.to_dict() for sdi in self.service_delay_impacts],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "baseline_comparison": self.baseline_comparison.to_dict(),
            "assessment": self.assessment.to_dict(),
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def generate_ascii_summary(self) -> str:
        opt_d_str = f"{self.total_optimized_delay_minutes:.1f}m" if self.total_optimized_delay_minutes is not None else "N/A (Infeasible)"
        sav_m_str = f"{self.net_delay_savings_minutes:.1f}m" if self.net_delay_savings_minutes is not None else "N/A"
        sav_p_str = f"{self.net_delay_savings_percent:.1f}%" if self.net_delay_savings_percent is not None else "N/A"

        lines = [
            "=" * 96,
            "END-TO-END RAILWAY TRAFFIC OPTIMIZATION PIPELINE RESULT",
            "=" * 96,
            f"Scenario: {self.scenario_name:<30} | Timestamp: {self.simulation_timestamp_str:<8} | Solver: {self.solver_status} ({self.solve_time_seconds:.3f}s)",
            f"Active Services: {self.active_services_count:<4} | Delayed Services: {self.delayed_services_count:<4} | Severity: {self.assessment.situation.severity.value}",
            f"Feasible Baseline Delay: {self.total_baseline_delay_minutes:.1f}m -> Optimized Delay: {opt_d_str} (Savings: {sav_m_str} | {sav_p_str})",
            "-" * 96,
            f"PRIORITIZED CONFLICTS DETECTED ({len(self.prioritized_conflicts)}):",
        ]

        if not self.prioritized_conflicts:
            lines.append("  (Zero active conflicts detected)")
        else:
            for pc in self.prioritized_conflicts:
                lines.append(
                    f"  [{pc.conflict.severity.value:<8}] {pc.conflict.conflict_id}: {pc.conflict.conflict_type.value} at {pc.conflict.resource_id} (Score: {pc.priority_score:.1f})"
                )
                lines.append(f"            {pc.ranking_explanation}")

        lines.extend([
            "-" * 96,
            f"CONTESTED BOTTLENECKS IDENTIFIED ({len(self.identified_bottlenecks)}):",
        ])

        if not self.identified_bottlenecks:
            lines.append("  (No contested infrastructure bottlenecks)")
        else:
            for b in self.identified_bottlenecks:
                lines.append(
                    f"  [{b.resource_type:<13}] {b.resource_id:<18} | Contending Svcs: {b.contention_count} | Score: {b.criticality_score:.1f}"
                )

        lines.extend([
            "-" * 96,
            f"RANKED ACTIONABLE RECOMMENDATIONS ({len(self.recommendations)}):",
        ])

        if not self.recommendations:
            lines.append("  (No intervention required - maintain published timetable)")
        else:
            for r in self.recommendations:
                lines.append(
                    f"  [{r.priority_tier.value:<8}] {r.recommendation_id}: {r.title}"
                )
                lines.append(f"            Rationale: {r.reason}")
                lines.append(
                    f"            Impact: Baseline {r.baseline_delay_minutes:.1f}m -> Opt {r.expected_delay_minutes:.1f}m (Savings: {r.expected_delay_savings:.1f}m)"
                )
                lines.append(f"            Evidence: {r.evidence_basis}")

        lines.append("=" * 96)
        return "\n".join(lines)

    def generate_markdown(self) -> str:
        return self.assessment.generate_markdown()


class PipelineOrchestrator:
    """End-to-end backend orchestrator for railway simulation, optimization, and decision support."""

    def __init__(
        self,
        network: Optional[Network] = None,
        detector: Optional[ConflictDetector] = None,
        solver: Optional[CPSATScheduler] = None,
        advisor: Optional[DecisionSupportAdvisor] = None,
    ):
        self.network = network or _load_default_network()
        self.detector = detector or ConflictDetector(network=self.network)
        self.solver = solver or CPSATScheduler()
        self.advisor = advisor or DecisionSupportAdvisor(
            network=self.network,
            detector=self.detector,
            solver=self.solver,
        )
        self.scenario_runner = ScenarioRunner(network=self.network)

    def run_pipeline(
        self,
        scenario: Optional[Scenario] = None,
        service_ids: Optional[List[str]] = None,
        departure_delays: Optional[Dict[str, float]] = None,
        time_horizon: Optional[float] = None,
        objective_mode: str = "WEIGHTED",
        apply_midnight_wrap: bool = False,
        time_resolution: int = 1,
    ) -> PipelineExecutionResult:
        """Execute complete 6-stage end-to-end optimization and decision-support pipeline."""
        t_start = time.perf_counter()

        # Step 1: Resolve services and scenario
        selected_svcs = list(service_ids) if service_ids else sorted(list(self.network.services.keys()))[:4]

        if scenario is None:
            # Build baseline operational scenario
            dep_delays = departure_delays or {}
            scenario = Scenario(
                scenario_id="SCEN_LIVE_BASE",
                name="Live Operational Baseline",
                description="Standard operational timetable execution with dynamic state evaluation.",
                affected_service_ids=selected_svcs,
                departure_delays=dep_delays,
                objective_mode=objective_mode,
            )
        else:
            if service_ids:
                scenario.affected_service_ids = list(service_ids)
            if departure_delays:
                for s, d in departure_delays.items():
                    scenario.departure_delays[s] = d
            if hasattr(scenario, "objective_mode") and objective_mode != "WEIGHTED":
                scenario.objective_mode = objective_mode

        # Step 2: Run simulation & dynamic state progression
        sim_clock = SimulationClock(start_time="00:00")
        state = SimulationState(clock=sim_clock)
        state.initialize_from_network(self.network)
        simulator = TrainSimulator(network=self.network, clock=sim_clock, state=state)

        for s_id in selected_svcs:
            dep_delay = scenario.departure_delays.get(s_id, 0.0)
            tt_entry = simulator.get_timetable_entry(s_id, self.network.services[s_id].origin)
            base_dep = time_to_minutes(tt_entry.departure) if tt_entry and tt_entry.departure else 360.0
            simulator.run_service_to_destination(
                s_id,
                start_time=base_dep + dep_delay,
                strict_track_lookup=False,
            )

        # Step 3: Run full scenario comparison (Feasible FIFO Baseline vs CP-SAT)
        comparison = self.scenario_runner.run_scenario(
            scenario=scenario,
            time_horizon=time_horizon,
            apply_midnight_wrap=apply_midnight_wrap,
            time_resolution=time_resolution,
        )

        # Step 4: Evaluate Decision Support Assessment
        assessment = self.advisor.evaluate_what_if_scenario(
            scenario=scenario,
            service_ids=selected_svcs,
        )

        t_end = time.perf_counter()
        exec_duration = t_end - t_start

        h = hashlib.sha256(
            f"{scenario.scenario_id}_{comparison.baseline_total_delay}_{comparison.optimized_total_delay}_{len(assessment.recommendations)}_{comparison.optimization_status}".encode()
        ).hexdigest()[:12]

        is_sol = comparison.optimization_status in ("OPTIMAL", "FEASIBLE")

        return PipelineExecutionResult(
            scenario_id=scenario.scenario_id,
            scenario_name=scenario.name,
            simulation_timestamp=state.clock.current_time,
            simulation_timestamp_str=state.clock.current_time_str,
            active_services_count=len(selected_svcs),
            delayed_services_count=len(scenario.departure_delays) + len(scenario.station_delays),
            total_baseline_delay_minutes=comparison.baseline_total_delay,
            total_optimized_delay_minutes=comparison.optimized_total_delay if is_sol else None,
            net_delay_savings_minutes=comparison.delay_savings_minutes if is_sol else None,
            net_delay_savings_percent=comparison.delay_savings_percent if is_sol else None,
            solver_status=comparison.optimization_status,
            solution_available=is_sol,
            fifo_weighted_objective=comparison.fifo_weighted_objective,
            optimized_weighted_objective=comparison.optimized_weighted_objective if is_sol else None,
            objective_mode=getattr(scenario, "objective_mode", "WEIGHTED"),
            solve_time_seconds=comparison.computation_time_seconds,
            prioritized_conflicts=assessment.prioritized_conflicts,
            identified_bottlenecks=assessment.identified_bottlenecks,
            service_delay_impacts=assessment.service_delay_impacts,
            recommendations=assessment.recommendations,
            baseline_comparison=assessment.comparison_detail or BaselineOptimizationComparison(
                published_reference_delay_minutes=getattr(comparison, "published_total_delay", 0.0),
                feasible_baseline_delay_minutes=comparison.baseline_total_delay,
                feasible_baseline_max_delay_minutes=comparison.baseline_max_delay,
                feasible_baseline_conflicts_remaining=comparison.baseline_unresolved_conflicts if hasattr(comparison, "baseline_unresolved_conflicts") else 0,
                feasible_baseline_throughput=len(selected_svcs),
                optimized_delay_minutes=comparison.optimized_total_delay if is_sol else None,
                optimized_max_delay_minutes=comparison.optimized_max_delay if is_sol else None,
                optimized_conflicts_remaining=0,
                optimized_throughput=len(selected_svcs) if is_sol else 0,
                delay_savings_minutes=comparison.delay_savings_minutes if is_sol else None,
                delay_savings_percent=comparison.delay_savings_percent if is_sol else None,
                solver_status=comparison.optimization_status,
                solution_available=is_sol,
                solve_time_seconds=comparison.computation_time_seconds,
                three_tier_timetable=comparison.build_three_tier_timetable(self.network) if is_sol else [],
                published_timetables={
                    s_id: [a.to_dict() for a in adjs]
                    for s_id, adjs in comparison.published_baseline_result.adjusted_timetables.items()
                } if comparison.published_baseline_result else {},
                feasible_timetables={
                    s_id: [a.to_dict() for a in adjs]
                    for s_id, adjs in comparison.baseline_result.adjusted_timetables.items()
                } if comparison.baseline_result else {},
                optimized_timetables={
                    s_id: [a.to_dict() for a in adjs]
                    for s_id, adjs in comparison.optimized_result.adjusted_timetables.items()
                } if (comparison.optimized_result and is_sol) else {},
                corridor_performance=comparison.build_corridor_performance_summary(self.network) if is_sol else [],
            ),
            assessment=assessment,
            deterministic_hash=h,
            execution_time_seconds=exec_duration,
            raw_state=state,
            metadata={
                "service_ids": selected_svcs,
                "departure_delays": scenario.departure_delays,
                "conflict_count": len(assessment.prioritized_conflicts),
                "recommendation_count": len(assessment.recommendations),
            },
        )


def run_pipeline(
    scenario: Optional[Scenario] = None,
    service_ids: Optional[List[str]] = None,
    departure_delays: Optional[Dict[str, float]] = None,
    time_horizon: Optional[float] = None,
    objective_mode: str = "WEIGHTED",
    apply_midnight_wrap: bool = False,
    time_resolution: int = 1,
    network: Optional[Network] = None,
) -> PipelineExecutionResult:
    """Convenience factory function to execute full end-to-end backend optimization pipeline."""
    orchestrator = PipelineOrchestrator(network=network)
    return orchestrator.run_pipeline(
        scenario=scenario,
        service_ids=service_ids,
        departure_delays=departure_delays,
        time_horizon=time_horizon,
        objective_mode=objective_mode,
        apply_midnight_wrap=apply_midnight_wrap,
        time_resolution=time_resolution,
    )
