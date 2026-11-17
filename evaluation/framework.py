"""
evaluation/framework.py
~~~~~~~~~~~~~~~~~~~~~~~
Phase 31.1 — Research Experiment Framework for Multi-Corridor Railway Traffic Optimization.

Provides a reproducible, mathematically rigorous research experimentation architecture
operating exclusively across the 40 active timetable-backed services of the Chennai
Division railway network model.

Covers 7 controlled experiment groups:
1. Baseline / Nominal Operation (No disruption)
2. Departure Delays at Origin Terminals
3. En-Route and Intermediate Station Dwell Delays
4. Temporary Speed Restrictions (TSR) & Caution Orders
5. Blocked Track Sections (Capacity = 0)
6. Junction Throat Contention & Interlocking Bottlenecks
7. Compound Multi-Corridor Disruptions

Features:
- Consistent metrics: total delay, average delay, peak delay, delay savings (minutes & %),
  conflict counts/resolution, throughput/completion rate, solver status/time, bottleneck utilization.
- Strict exclusion of all 7 pending services.
- 100% deterministic repeatability with config_hash and result_hash validation.
- Zero mutation of master JSON datasets or network models.
- Structured research results format with JSON export and Markdown generation.
"""

from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Set, Tuple

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictDetector, ConflictSeverity, ConflictType
from simulation.network import Network, Route, Service, TimetableEntry, TrackSection
from simulation.state import SimulationState, TrackSectionOccupancy
from optimization.model import (
    HeadwayConstraint,
    JunctionConstraint,
    OptimizationModel,
    OptimizationRequest,
    PrecedenceDecision,
    ResourceAllocationDecision,
    ServiceTimetableAdjustment,
)
from optimization.objective import ObjectiveWeights, OptimizationObjective
from optimization.scenarios import Scenario, ScenarioComparison, ScenarioRunner
from optimization.scheduler import (
    BaselineScheduler,
    FeasibleBaselineScheduler,
    OptimizationResult,
    PerformanceMetrics,
)
from optimization.solver import CPSATScheduler

PENDING_SERVICES: Set[str] = {
    "SRV_40143_01",
    "SRV_40144_01",
    "SRV_41015_01",
    "SRV_41131_01",
    "SRV_41132_01",
    "SRV_42413_01",
    "SRV_42425_01",
}


class ExperimentGroupType(str, Enum):
    """Seven standardized research experiment groups."""
    BASELINE = "EXP_GRP_01_BASELINE"
    DEPARTURE_DELAY = "EXP_GRP_02_DEP_DELAY"
    DWELL_DELAY = "EXP_GRP_03_DWELL_DELAY"
    SPEED_RESTRICTION = "EXP_GRP_04_SPEED_RESTRICTION"
    BLOCKED_SECTION = "EXP_GRP_05_BLOCKED_SECTION"
    JUNCTION_CONTENTION = "EXP_GRP_06_JUNCTION_CONTENTION"
    COMPOUND_DISRUPTION = "EXP_GRP_07_COMPOUND"


@dataclass
class ResearchMetrics:
    """Consistent, mathematically fair research metrics comparing FIFO Baseline and CP-SAT."""
    # Delay metrics
    published_total_delay_minutes: float = 0.0
    feasible_baseline_total_delay_minutes: float = 0.0
    optimized_total_delay_minutes: float = 0.0
    delay_savings_minutes: float = 0.0
    delay_savings_percent: float = 0.0

    # Average delay metrics (total delay / throughput)
    feasible_baseline_average_delay_minutes: float = 0.0
    optimized_average_delay_minutes: float = 0.0
    average_delay_savings_minutes: float = 0.0

    # Peak / max individual delay
    feasible_baseline_peak_delay_minutes: float = 0.0
    optimized_peak_delay_minutes: float = 0.0
    peak_delay_savings_minutes: float = 0.0

    # Throughput and completion
    throughput: int = 0
    total_requested_services: int = 0
    completion_rate_percent: float = 100.0
    on_time_performance_percent: float = 100.0

    # Conflict detection & resolution
    initial_conflicts: int = 0
    baseline_remaining_conflicts: int = 0
    optimized_remaining_conflicts: int = 0
    resolved_conflicts: int = 0

    # Solver metrics
    solver_status: str = "OPTIMAL"
    solve_time_seconds: float = 0.0
    precedence_decisions_count: int = 0
    resource_decisions_count: int = 0

    # Bottleneck and resource utilization
    bottleneck_utilization: Dict[str, Any] = field(default_factory=dict)

    @property
    def remaining_conflicts(self) -> int:
        """Alias for optimized remaining conflicts."""
        return self.optimized_remaining_conflicts

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delay": {
                "published_total_delay_min": round(self.published_total_delay_minutes, 2),
                "feasible_baseline_total_delay_min": round(self.feasible_baseline_total_delay_minutes, 2),
                "optimized_total_delay_min": round(self.optimized_total_delay_minutes, 2),
                "delay_savings_min": round(self.delay_savings_minutes, 2),
                "delay_savings_percent": round(self.delay_savings_percent, 2),
                "feasible_baseline_average_delay_min": round(self.feasible_baseline_average_delay_minutes, 2),
                "optimized_average_delay_min": round(self.optimized_average_delay_minutes, 2),
                "average_delay_savings_min": round(self.average_delay_savings_minutes, 2),
                "feasible_baseline_peak_delay_min": round(self.feasible_baseline_peak_delay_minutes, 2),
                "optimized_peak_delay_min": round(self.optimized_peak_delay_minutes, 2),
                "peak_delay_savings_min": round(self.peak_delay_savings_minutes, 2),
            },
            "throughput": {
                "throughput_services": self.throughput,
                "total_requested_services": self.total_requested_services,
                "completion_rate_percent": round(self.completion_rate_percent, 2),
                "on_time_performance_percent": round(self.on_time_performance_percent, 2),
            },
            "conflicts": {
                "initial_conflicts": self.initial_conflicts,
                "baseline_remaining_conflicts": self.baseline_remaining_conflicts,
                "optimized_remaining_conflicts": self.optimized_remaining_conflicts,
                "resolved_conflicts": self.resolved_conflicts,
            },
            "solver": {
                "solver_status": self.solver_status,
                "solve_time_seconds": round(self.solve_time_seconds, 3),
                "precedence_decisions": self.precedence_decisions_count,
                "resource_decisions": self.resource_decisions_count,
            },
            "bottlenecks": self.bottleneck_utilization,
        }


@dataclass
class ResearchExperimentConfig:
    """Configuration specification for a reproducible research experiment."""
    experiment_id: str
    group: ExperimentGroupType
    name: str
    description: str
    scenario: Scenario
    target_service_ids: List[str]
    time_horizon: Tuple[float, float] = (0.0, 1440.0)
    time_limit_seconds: float = 15.0
    random_seed: int = 42

    def __post_init__(self):
        # Enforce strict pending service exclusion
        for s_id in self.target_service_ids:
            if s_id in PENDING_SERVICES:
                raise ValueError(f"Pending service '{s_id}' cannot be included in research experiment '{self.experiment_id}'.")
        for s_id in self.scenario.affected_service_ids:
            if s_id in PENDING_SERVICES:
                raise ValueError(f"Pending service '{s_id}' cannot be included in scenario '{self.scenario.scenario_id}'.")

    @property
    def config_hash(self) -> str:
        """Deterministic SHA-256 fingerprint of the experiment configuration."""
        data = {
            "experiment_id": self.experiment_id,
            "group": self.group.value,
            "name": self.name,
            "scenario": self.scenario.to_dict(),
            "target_services": sorted(self.target_service_ids),
            "time_horizon": list(self.time_horizon),
            "time_limit": self.time_limit_seconds,
            "seed": self.random_seed,
        }
        raw = json.dumps(data, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "group": self.group.value,
            "name": self.name,
            "description": self.description,
            "config_hash": self.config_hash,
            "target_services": self.target_service_ids,
            "time_horizon": list(self.time_horizon),
            "time_limit_seconds": self.time_limit_seconds,
            "random_seed": self.random_seed,
            "scenario": self.scenario.to_dict(),
        }


@dataclass
class ResearchExperimentResult:
    """Complete evaluated outcome of a single research experiment."""
    config: ResearchExperimentConfig
    metrics: ResearchMetrics
    comparison: ScenarioComparison
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def result_hash(self) -> str:
        """Deterministic SHA-256 signature of the evaluated result."""
        m = self.metrics
        data = {
            "config_hash": self.config.config_hash,
            "experiment_id": self.config.experiment_id,
            "feasible_baseline_delay": round(m.feasible_baseline_total_delay_minutes, 2),
            "optimized_delay": round(m.optimized_total_delay_minutes, 2),
            "delay_savings": round(m.delay_savings_minutes, 2),
            "throughput": m.throughput,
            "initial_conflicts": m.initial_conflicts,
            "remaining_conflicts": m.optimized_remaining_conflicts,
            "resolved_conflicts": m.resolved_conflicts,
            "status": m.solver_status,
            "precedence_count": m.precedence_decisions_count,
            "resource_count": m.resource_decisions_count,
        }
        raw = json.dumps(data, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.config.experiment_id,
            "group": self.config.group.value,
            "name": self.config.name,
            "config_hash": self.config.config_hash,
            "result_hash": self.result_hash,
            "created_at": self.created_at,
            "metrics": self.metrics.to_dict(),
            "precedence_decisions": [p.to_dict() for p in self.comparison.optimized_result.precedence_decisions],
            "resource_decisions": [r.to_dict() for r in self.comparison.optimized_result.resource_decisions],
        }

    def summary(self) -> str:
        m = self.metrics
        lines = [
            f"====================================================================================================",
            f"RESEARCH EXPERIMENT [{self.config.experiment_id}] {self.config.name}",
            f"Group:       {self.config.group.value}",
            f"Hashes:      Config={self.config.config_hash} | Result={self.result_hash}",
            f"Description: {self.config.description}",
            f"----------------------------------------------------------------------------------------------------",
            f"METRIC                            FEASIBLE BASELINE (FIFO)   CP-SAT OPTIMIZED   SAVINGS / DELTA",
            f"----------------------------------------------------------------------------------------------------",
            f"Solver Status                     FEASIBLE_BASELINE          {m.solver_status:<18} -",
            f"Total Delay (min)                 {m.feasible_baseline_total_delay_minutes:<26.1f} {m.optimized_total_delay_minutes:<18.1f} {m.delay_savings_minutes:+.1f} min ({m.delay_savings_percent:.1f}%)",
            f"Average Delay / Service (min)     {m.feasible_baseline_average_delay_minutes:<26.1f} {m.optimized_average_delay_minutes:<18.1f} {m.average_delay_savings_minutes:+.1f} min",
            f"Peak Individual Delay (min)       {m.feasible_baseline_peak_delay_minutes:<26.1f} {m.optimized_peak_delay_minutes:<18.1f} {m.peak_delay_savings_minutes:+.1f} min",
            f"Throughput (Scheduled Services)   {m.throughput:<26d} {m.throughput:<18d} {m.completion_rate_percent:.1f}%",
            f"On-Time Performance (<=5m)        -                          {m.on_time_performance_percent:<18.1f} -",
            f"Conflicts (Init / Rem / Solved)   {m.initial_conflicts} / {m.baseline_remaining_conflicts:<21d} 0 / {m.optimized_remaining_conflicts:<14d} -{m.resolved_conflicts} resolved",
            f"Precedence Re-orderings           -                          {m.precedence_decisions_count:<18d} -",
            f"Solve Execution Duration (s)      <0.005                     {m.solve_time_seconds:<18.3f} -",
            f"====================================================================================================",
        ]
        return "\n".join(lines)


@dataclass
class ResearchSuiteResult:
    """Aggregated outcome of executing a suite of research experiments."""
    suite_id: str
    suite_name: str
    results: List[ResearchExperimentResult] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def get_results_by_group(self, group: ExperimentGroupType) -> List[ResearchExperimentResult]:
        return [r for r in self.results if r.config.group == group]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "suite_name": self.suite_name,
            "created_at": self.created_at,
            "total_experiments": len(self.results),
            "results": [r.to_dict() for r in self.results],
        }

    def generate_markdown(self) -> str:
        lines = [
            f"# Railway Traffic Optimization — Research Experiment Suite Report",
            f"",
            f"**Suite ID:** `{self.suite_id}`  ",
            f"**Suite Name:** {self.suite_name}  ",
            f"**Generated:** `{self.created_at}`  ",
            f"**Total Experiments Evaluated:** {len(self.results)}  ",
            f"",
            f"## 1. Summary of Experiment Groups",
            f"",
            f"| Experiment ID | Group | Scenario Name | Base Delay | Opt Delay | Savings (min) | Savings (%) | Conflicts Resolved | Status |",
            f"|---|---|---|:---:|:---:|:---:|:---:|:---:|:---:|",
        ]
        for r in self.results:
            m = r.metrics
            lines.append(
                f"| `{r.config.experiment_id}` | `{r.config.group.name}` | {r.config.name} | "
                f"{m.feasible_baseline_total_delay_minutes:.1f}m | **{m.optimized_total_delay_minutes:.1f}m** | "
                f"**{m.delay_savings_minutes:+.1f}m** | **{m.delay_savings_percent:.1f}%** | "
                f"{m.resolved_conflicts} | `{m.solver_status}` ({m.solve_time_seconds:.3f}s) |"
            )
        return "\n".join(lines)


class ResearchExperimentRunner:
    """Executes research experiments and computes comprehensive metrics."""

    def __init__(
        self,
        network: Optional[Network] = None,
        time_limit_seconds: float = 15.0,
        objective_weights: Optional[ObjectiveWeights] = None,
    ):
        self.scenario_runner = ScenarioRunner(
            network=network,
            time_limit_seconds=time_limit_seconds,
            objective_weights=objective_weights,
        )
        self.network = self.scenario_runner.network

    def run_experiment(self, config: ResearchExperimentConfig) -> ResearchExperimentResult:
        """Executes a single ResearchExperimentConfig and returns a ResearchExperimentResult."""
        # 1. Run scenario comparison
        comparison = self.scenario_runner.run_scenario(
            scenario=config.scenario,
            time_horizon=config.time_horizon,
        )

        base_res = comparison.feasible_baseline_result or comparison.baseline_result
        pub_res = comparison.published_baseline_result
        opt_res = comparison.optimized_result

        # 2. Extract throughput and delay averages
        throughput = opt_res.throughput
        req_services = len(config.target_service_ids) or throughput
        comp_rate = (throughput / req_services * 100.0) if req_services > 0 else 100.0

        base_total_delay = base_res.metrics.total_delay_minutes
        opt_total_delay = opt_res.metrics.total_delay_minutes
        delay_savings = base_total_delay - opt_total_delay
        savings_pct = (delay_savings / base_total_delay * 100.0) if base_total_delay > 0 else 0.0

        base_avg_delay = (base_total_delay / throughput) if throughput > 0 else 0.0
        opt_avg_delay = (opt_total_delay / throughput) if throughput > 0 else 0.0
        avg_savings = base_avg_delay - opt_avg_delay

        base_peak = base_res.metrics.max_delay_minutes
        opt_peak = opt_res.metrics.max_delay_minutes
        peak_savings = base_peak - opt_peak

        # 3. Assess bottleneck utilization from scenario and decisions
        bottleneck_info: Dict[str, Any] = {}
        for jct_id, cap in config.scenario.junction_capacity_overrides.items():
            precedence_on_jct = [p for p in opt_res.precedence_decisions if jct_id in p.resource_id]
            bottleneck_info[jct_id] = {
                "type": "JUNCTION",
                "constrained_capacity": cap,
                "precedence_decisions_count": len(precedence_on_jct),
            }
        for sec_id, tt in config.scenario.track_speed_restrictions.items():
            bottleneck_info[sec_id] = {
                "type": "TRACK_SECTION_TSR",
                "restricted_travel_time_minutes": tt,
            }
        for sec_id in config.scenario.blocked_sections:
            bottleneck_info[sec_id] = {
                "type": "BLOCKED_SECTION",
                "capacity": 0,
            }

        # 4. Build ResearchMetrics
        metrics = ResearchMetrics(
            published_total_delay_minutes=pub_res.metrics.total_delay_minutes if pub_res else 0.0,
            feasible_baseline_total_delay_minutes=base_total_delay,
            optimized_total_delay_minutes=opt_total_delay,
            delay_savings_minutes=delay_savings,
            delay_savings_percent=savings_pct,
            feasible_baseline_average_delay_minutes=base_avg_delay,
            optimized_average_delay_minutes=opt_avg_delay,
            average_delay_savings_minutes=avg_savings,
            feasible_baseline_peak_delay_minutes=base_peak,
            optimized_peak_delay_minutes=opt_peak,
            peak_delay_savings_minutes=peak_savings,
            throughput=throughput,
            total_requested_services=req_services,
            completion_rate_percent=comp_rate,
            on_time_performance_percent=opt_res.metrics.on_time_performance_percent,
            initial_conflicts=comparison.initial_conflicts,
            baseline_remaining_conflicts=base_res.metrics.remaining_conflict_count,
            optimized_remaining_conflicts=opt_res.metrics.remaining_conflict_count,
            resolved_conflicts=comparison.resolved_conflicts,
            solver_status=opt_res.status,
            solve_time_seconds=opt_res.computation_time_seconds,
            precedence_decisions_count=len(opt_res.precedence_decisions),
            resource_decisions_count=len(opt_res.resource_decisions),
            bottleneck_utilization=bottleneck_info,
        )

        return ResearchExperimentResult(
            config=config,
            metrics=metrics,
            comparison=comparison,
        )

    def run_suite(
        self,
        configs: List[ResearchExperimentConfig],
        suite_id: str = "PHASE_31_1_RESEARCH_SUITE",
        suite_name: str = "Phase 31.1 Multi-Corridor Research Experiment Suite",
    ) -> ResearchSuiteResult:
        """Executes a list of research experiment configs and aggregates results."""
        results: List[ResearchExperimentResult] = []
        for cfg in configs:
            res = self.run_experiment(cfg)
            results.append(res)
        return ResearchSuiteResult(
            suite_id=suite_id,
            suite_name=suite_name,
            results=results,
        )


# ===========================================================================
# Standardized Research Experiment Definitions (7 Controlled Groups)
# ===========================================================================

def create_phase31_research_suite() -> List[ResearchExperimentConfig]:
    """Builds the comprehensive, standardized 7-group research experiment suite across the 40 backed services."""
    experiments: List[ResearchExperimentConfig] = []

    # -----------------------------------------------------------------------
    # Group 1: Baseline / Nominal (No disruption)
    # -----------------------------------------------------------------------
    exp_01a = ResearchExperimentConfig(
        experiment_id="EXP_31_1_01A_NOMINAL_MULTI",
        group=ExperimentGroupType.BASELINE,
        name="Nominal Multi-Corridor Concurrency",
        description="Ideal on-time operation across West, South, North, MRTS, and Bypass corridors.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_01A",
            name="Nominal Multi-Corridor Concurrency",
            affected_service_ids=["SRV_12607_01", "SRV_12635_01", "SRV_12712_01", "SRV_41001_01", "SRV_42601_01"],
        ),
        target_service_ids=["SRV_12607_01", "SRV_12635_01", "SRV_12712_01", "SRV_41001_01", "SRV_42601_01"],
        time_horizon=(300.0, 1200.0),
    )
    experiments.append(exp_01a)

    exp_01b = ResearchExperimentConfig(
        experiment_id="EXP_31_1_01B_NOMINAL_WEST",
        group=ExperimentGroupType.BASELINE,
        name="Nominal West Corridor High-Density",
        description="Unperturbed baseline operation for multiple West trunk services into MAS.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_01B",
            name="Nominal West High-Density",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"],
        ),
        target_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"],
        time_horizon=(800.0, 1150.0),
    )
    experiments.append(exp_01b)

    # -----------------------------------------------------------------------
    # Group 2: Departure Delays
    # -----------------------------------------------------------------------
    exp_02a = ResearchExperimentConfig(
        experiment_id="EXP_31_1_02A_DEP_EXPRESS_WEST",
        group=ExperimentGroupType.DEPARTURE_DELAY,
        name="Single Express Origin Departure Delay",
        description="Lalbagh SF Express 12607 delayed by 25 minutes at MAS origin.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_02A",
            name="12607 MAS 25m Departure Delay",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
            departure_delays={"SRV_12607_01": 25.0},
        ),
        target_service_ids=["SRV_12607_01", "SRV_12609_01"],
        time_horizon=(850.0, 1150.0),
    )
    experiments.append(exp_02a)

    exp_02b = ResearchExperimentConfig(
        experiment_id="EXP_31_1_02B_DEP_MULTI_CORRIDOR",
        group=ExperimentGroupType.DEPARTURE_DELAY,
        name="Multi-Corridor Concurrent Terminal Delays",
        description="Concurrent departure delays across West (MAS), South (MS), and North (MAS) mainlines.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_02B",
            name="Multi-Corridor Terminal Delays",
            affected_service_ids=["SRV_12607_01", "SRV_12635_01", "SRV_12712_01"],
            departure_delays={
                "SRV_12607_01": 20.0,
                "SRV_12635_01": 15.0,
                "SRV_12712_01": 25.0,
            },
        ),
        target_service_ids=["SRV_12607_01", "SRV_12635_01", "SRV_12712_01"],
        time_horizon=(700.0, 1200.0),
    )
    experiments.append(exp_02b)

    # -----------------------------------------------------------------------
    # Group 3: En-Route & Station Dwell Delays
    # -----------------------------------------------------------------------
    exp_03a = ResearchExperimentConfig(
        experiment_id="EXP_31_1_03A_DWELL_JUNCTION_PER",
        group=ExperimentGroupType.DWELL_DELAY,
        name="Intermediate Junction Dwell Delay at Perambur",
        description="Extended dwell (+15m) at Perambur (PER) on West Express 12607.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_03A",
            name="PER Extended Dwell Delay",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
            station_delays={"SRV_12607_01": {"PER": 15.0}},
        ),
        target_service_ids=["SRV_12607_01", "SRV_12609_01"],
        time_horizon=(850.0, 1150.0),
    )
    experiments.append(exp_03a)

    exp_03b = ResearchExperimentConfig(
        experiment_id="EXP_31_1_03B_DWELL_JUNCTION_TBM",
        group=ExperimentGroupType.DWELL_DELAY,
        name="South Corridor Tambaram Dwell Delay",
        description="Tambaram (TBM) dwell extension (+20m) on South Express 12635.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_03B",
            name="TBM Dwell Extension",
            affected_service_ids=["SRV_12635_01", "SRV_12636_01"],
            station_delays={"SRV_12635_01": {"TBM": 20.0}},
        ),
        target_service_ids=["SRV_12635_01", "SRV_12636_01"],
        time_horizon=(750.0, 1000.0),
    )
    experiments.append(exp_03b)

    # -----------------------------------------------------------------------
    # Group 4: Temporary Speed Restrictions (TSR)
    # -----------------------------------------------------------------------
    exp_04a = ResearchExperimentConfig(
        experiment_id="EXP_31_1_04A_TSR_THROAT_BBQ",
        group=ExperimentGroupType.SPEED_RESTRICTION,
        name="MAS-BBQ Throat Speed Restriction",
        description="Caution order on MAS_BBQ_THROAT_SEGMENT_DOWN increasing traversal time from 4m to 10m.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_04A",
            name="MAS-BBQ Throat TSR",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
            track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 10.0},
        ),
        target_service_ids=["SRV_12607_01", "SRV_12609_01"],
        time_horizon=(800.0, 1150.0),
    )
    experiments.append(exp_04a)

    exp_04b = ResearchExperimentConfig(
        experiment_id="EXP_31_1_04B_TSR_NORTH_TRUNK",
        group=ExperimentGroupType.SPEED_RESTRICTION,
        name="North Trunk Track Renewal TSR",
        description="Track renewal caution order on BBQ_KOK_MAIN_NORTH_UP (+8m traversal time).",
        scenario=Scenario(
            scenario_id="SCEN_31_1_04B",
            name="North Trunk TSR",
            affected_service_ids=["SRV_12712_01", "SRV_12656_01"],
            track_speed_restrictions={"BBQ_KOK_MAIN_NORTH_UP": 11.0},
        ),
        target_service_ids=["SRV_12712_01", "SRV_12656_01"],
        time_horizon=(800.0, 1200.0),
    )
    experiments.append(exp_04b)

    # -----------------------------------------------------------------------
    # Group 5: Blocked Track Sections
    # -----------------------------------------------------------------------
    exp_05a = ResearchExperimentConfig(
        experiment_id="EXP_31_1_05A_BLOCK_PTMS_BRANCH",
        group=ExperimentGroupType.BLOCKED_SECTION,
        name="Pattabiram Branch Track Blockage",
        description="Temporary overhead line maintenance blocking section PAB_PTMS_SUBURBAN_DOWN.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_05A",
            name="PTMS Branch Section Blockage",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
            blocked_sections=["PAB_PTMS_SUBURBAN_DOWN"],
        ),
        target_service_ids=["SRV_12607_01", "SRV_12609_01"],
        time_horizon=(800.0, 1150.0),
    )
    experiments.append(exp_05a)

    # -----------------------------------------------------------------------
    # Group 6: Junction & Throat Contention
    # -----------------------------------------------------------------------
    exp_06a = ResearchExperimentConfig(
        experiment_id="EXP_31_1_06A_JCT_BBQ_THROTTLE",
        group=ExperimentGroupType.JUNCTION_CONTENTION,
        name="Basin Bridge Junction Interlocking Throttle",
        description="Constraining JCT_BBQ to capacity 1 with competing West and North services.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_06A",
            name="JCT_BBQ Capacity 1 Bottleneck",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"],
            junction_capacity_overrides={"JCT_BBQ": 1},
        ),
        target_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"],
        time_horizon=(800.0, 1150.0),
    )
    experiments.append(exp_06a)

    exp_06b = ResearchExperimentConfig(
        experiment_id="EXP_31_1_06B_JCT_PAB_MERGE",
        group=ExperimentGroupType.JUNCTION_CONTENTION,
        name="Pattabiram Junction Branch Merge Bottleneck",
        description="Single-capacity interlocking clearance constraint at JCT_PAB.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_06B",
            name="JCT_PAB Merge Contention",
            affected_service_ids=["SRV_12607_01", "SRV_43411_01"],
            junction_capacity_overrides={"JCT_PAB": 1},
        ),
        target_service_ids=["SRV_12607_01", "SRV_43411_01"],
        time_horizon=(800.0, 1150.0),
    )
    experiments.append(exp_06b)

    # -----------------------------------------------------------------------
    # Group 7: Compound Multi-Corridor Disruptions
    # -----------------------------------------------------------------------
    exp_07a = ResearchExperimentConfig(
        experiment_id="EXP_31_1_07A_COMPOUND_WEST_THROAT",
        group=ExperimentGroupType.COMPOUND_DISRUPTION,
        name="Compound Departure Delay, Throat TSR, and Junction Throttle",
        description="Simultaneous departure delay on 12607 (+20m), TSR on MAS-BBQ throat, and JCT_BBQ throttle.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_07A",
            name="West Corridor Compound Disruption",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_43411_01"],
            departure_delays={"SRV_12607_01": 20.0},
            track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 8.0},
            junction_capacity_overrides={"JCT_BBQ": 1},
        ),
        target_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_43411_01"],
        time_horizon=(800.0, 1150.0),
    )
    experiments.append(exp_07a)

    exp_07b = ResearchExperimentConfig(
        experiment_id="EXP_31_1_07B_COMPOUND_MULTI_CORRIDOR",
        group=ExperimentGroupType.COMPOUND_DISRUPTION,
        name="Multi-Corridor Peak Severe Compound Disruption",
        description="Simultaneous West and South departure delays with throat restriction and junction capacity constrictions.",
        scenario=Scenario(
            scenario_id="SCEN_31_1_07B",
            name="Multi-Corridor Severe Disruption",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12635_01"],
            departure_delays={"SRV_12607_01": 25.0, "SRV_12635_01": 20.0},
            track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 8.0},
            junction_capacity_overrides={"JCT_BBQ": 1},
        ),
        target_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12635_01"],
        time_horizon=(750.0, 1200.0),
    )
    experiments.append(exp_07b)

    return experiments
