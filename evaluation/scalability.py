"""
evaluation/scalability.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Batch 13: CP-SAT Stress Testing & Scalability Evaluation.

Provides a deterministic scalability / stress-testing framework that measures
how the CP-SAT optimizer and Feasible Baseline scheduler perform as the number
of simultaneously-scheduled West Corridor services grows.

Load levels are built exclusively from existing real service records in
data/trains/service_definitions/services.json — no synthetic trains are created.

Each load level is tested under four disruption modes:
  NORMAL          – nominal operation with no injected delay
  SINGLE_DELAY    – highest-priority outbound service delayed +15 min
  MULTI_DELAY     – two services delayed (+20 m / +10 m) + one station dwell
  SEVERE_COMPOUND – three services delayed + throat-track speed restriction

Usage
-----
    from evaluation.scalability import ScalabilityRunner, create_west_corridor_load_levels

    runner = ScalabilityRunner()
    report = runner.run()
    print(report.summary())
    print(report.to_markdown_report())
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from optimization.objective import ObjectiveWeights
from optimization.scenarios import Scenario, ScenarioComparison, ScenarioRunner
from simulation.network import Network


# ---------------------------------------------------------------------------
# Disruption mode constants
# ---------------------------------------------------------------------------

DISRUPTION_NORMAL = "NORMAL"
DISRUPTION_SINGLE_DELAY = "SINGLE_DELAY"
DISRUPTION_MULTI_DELAY = "MULTI_DELAY"
DISRUPTION_SEVERE_COMPOUND = "SEVERE_COMPOUND"

ALL_DISRUPTION_MODES: List[str] = [
    DISRUPTION_NORMAL,
    DISRUPTION_SINGLE_DELAY,
    DISRUPTION_MULTI_DELAY,
    DISRUPTION_SEVERE_COMPOUND,
]


# ---------------------------------------------------------------------------
# Load-level definition
# ---------------------------------------------------------------------------

@dataclass
class ScalabilityLoadLevel:
    """Defines a cohort of real existing services for one scalability load point.

    Attributes:
        label:         Human-readable label (e.g. "4 Services").
        service_ids:   Ordered list of existing service IDs included in this level.
        rationale:     Brief explanation of why this set was chosen.
        outbound_services: Subset of service_ids travelling outbound (MAS → AJJ / TRL).
                           Used when injecting directional delays.
    """
    label: str
    service_ids: List[str]
    rationale: str
    outbound_services: List[str] = field(default_factory=list)

    @property
    def service_count(self) -> int:
        return len(self.service_ids)

    def to_dict(self) -> Dict:
        return {
            "label": self.label,
            "service_count": self.service_count,
            "service_ids": self.service_ids,
            "outbound_services": self.outbound_services,
            "rationale": self.rationale,
        }


# ---------------------------------------------------------------------------
# Per-run metric capture
# ---------------------------------------------------------------------------

@dataclass
class ScalabilityMetrics:
    """Captured performance metrics for a single (load_level × disruption_mode) run.

    Attributes:
        load_label:              Human-readable load level label.
        service_count:           Number of services scheduled in this run.
        disruption_mode:         One of NORMAL / SINGLE_DELAY / MULTI_DELAY / SEVERE_COMPOUND.
        feasible_baseline_total_delay:   Total delay (min) from FIFO feasible baseline.
        optimized_total_delay:   Total delay (min) from CP-SAT.
        delay_savings:           feasible_baseline_total_delay − optimized_total_delay.
        delay_savings_percent:   Percentage delay reduction vs. feasible baseline.
        feasible_baseline_max_delay:     Peak individual delay in feasible baseline (min).
        optimized_max_delay:     Peak individual delay in CP-SAT solution (min).
        feasible_baseline_weighted_delay: Priority-weighted delay for feasible baseline.
        optimized_weighted_delay: Priority-weighted delay for CP-SAT.
        baseline_throughput:     Services scheduled by feasible baseline.
        optimized_throughput:    Services scheduled by CP-SAT.
        initial_conflicts:       Conflicts detected in the scenario state.
        baseline_remaining_conflicts: Conflicts remaining after feasible baseline.
        optimized_remaining_conflicts: Conflicts remaining after CP-SAT.
        resolved_conflicts:      initial_conflicts − optimized_remaining_conflicts.
        feasible_baseline_objective_cost: Objective cost for feasible baseline.
        optimized_objective_cost: Objective cost for CP-SAT.
        solver_status:           CP-SAT termination status string.
        solve_time_seconds:      CP-SAT wall-clock solve duration.
        precedence_decisions_count: Number of precedence decisions in CP-SAT result.
        resource_decisions_count: Number of resource-allocation decisions in CP-SAT result.
    """
    load_label: str = ""
    service_count: int = 0
    disruption_mode: str = DISRUPTION_NORMAL

    # Delay
    feasible_baseline_total_delay: float = 0.0
    optimized_total_delay: float = 0.0
    delay_savings: float = 0.0
    delay_savings_percent: float = 0.0
    feasible_baseline_max_delay: float = 0.0
    optimized_max_delay: float = 0.0
    feasible_baseline_weighted_delay: float = 0.0
    optimized_weighted_delay: float = 0.0

    # Throughput & Punctuality
    baseline_throughput: int = 0
    optimized_throughput: int = 0
    feasible_baseline_on_time_percent: float = 100.0
    optimized_on_time_percent: float = 100.0

    # Conflicts
    initial_conflicts: int = 0
    baseline_remaining_conflicts: int = 0
    optimized_remaining_conflicts: int = 0
    resolved_conflicts: int = 0

    # Solver
    feasible_baseline_objective_cost: float = 0.0
    optimized_objective_cost: float = 0.0
    solver_status: str = "OPTIMAL"
    solve_time_seconds: float = 0.0
    precedence_decisions_count: int = 0
    resource_decisions_count: int = 0

    @property
    def cost_savings(self) -> float:
        return self.feasible_baseline_objective_cost - self.optimized_objective_cost

    def to_dict(self) -> Dict:
        return {
            "load_label": self.load_label,
            "service_count": self.service_count,
            "disruption_mode": self.disruption_mode,
            "delay": {
                "feasible_baseline_total_delay_min": round(self.feasible_baseline_total_delay, 2),
                "optimized_total_delay_min": round(self.optimized_total_delay, 2),
                "delay_savings_min": round(self.delay_savings, 2),
                "delay_savings_percent": round(self.delay_savings_percent, 2),
                "feasible_baseline_max_delay_min": round(self.feasible_baseline_max_delay, 2),
                "optimized_max_delay_min": round(self.optimized_max_delay, 2),
                "feasible_baseline_weighted_delay": round(self.feasible_baseline_weighted_delay, 2),
                "optimized_weighted_delay": round(self.optimized_weighted_delay, 2),
            },
            "throughput": {
                "baseline": self.baseline_throughput,
                "optimized": self.optimized_throughput,
            },
            "conflicts": {
                "initial": self.initial_conflicts,
                "baseline_remaining": self.baseline_remaining_conflicts,
                "optimized_remaining": self.optimized_remaining_conflicts,
                "resolved": self.resolved_conflicts,
            },
            "solver": {
                "status": self.solver_status,
                "solve_time_seconds": round(self.solve_time_seconds, 3),
                "feasible_baseline_objective_cost": round(self.feasible_baseline_objective_cost, 2),
                "optimized_objective_cost": round(self.optimized_objective_cost, 2),
                "cost_savings": round(self.cost_savings, 2),
                "precedence_decisions": self.precedence_decisions_count,
                "resource_decisions": self.resource_decisions_count,
            },
        }

    def to_ascii_row(self) -> str:
        """One-line ASCII table row for console reporting."""
        savings_str = f"{self.delay_savings:+.1f}m ({self.delay_savings_percent:.1f}%)"
        return (
            f"  {self.disruption_mode:<20} "
            f"{self.feasible_baseline_total_delay:<10.1f} "
            f"{self.optimized_total_delay:<10.1f} "
            f"{savings_str:<20} "
            f"{self.optimized_remaining_conflicts:<8} "
            f"{self.solver_status:<14} "
            f"{self.solve_time_seconds:<8.3f}"
        )

    def to_markdown_row(self) -> str:
        """One-line Markdown table row."""
        savings_str = (
            f"**{self.delay_savings:+.1f}m ({self.delay_savings_percent:.1f}%)**"
            if abs(self.delay_savings) > 0.01
            else "0.0m (0.0%)"
        )
        return (
            f"| `{self.load_label}` | {self.service_count} | {self.disruption_mode} | "
            f"{self.feasible_baseline_total_delay:.1f}m | **{self.optimized_total_delay:.1f}m** | "
            f"{savings_str} | "
            f"{self.optimized_remaining_conflicts} | "
            f"`{self.solver_status}` ({self.solve_time_seconds:.3f}s) |"
        )


# ---------------------------------------------------------------------------
# Per-load-level aggregated result
# ---------------------------------------------------------------------------

@dataclass
class ScalabilityResult:
    """Aggregated outcomes for one load level across all disruption modes.

    Attributes:
        load_level: The ScalabilityLoadLevel definition for this result.
        runs:       Individual ScalabilityMetrics per disruption mode.
    """
    load_level: ScalabilityLoadLevel
    runs: List[ScalabilityMetrics] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.load_level.label

    @property
    def service_count(self) -> int:
        return self.load_level.service_count

    @property
    def mean_solve_time(self) -> float:
        if not self.runs:
            return 0.0
        return sum(r.solve_time_seconds for r in self.runs) / len(self.runs)

    @property
    def max_solve_time(self) -> float:
        return max((r.solve_time_seconds for r in self.runs), default=0.0)

    @property
    def mean_delay_savings(self) -> float:
        if not self.runs:
            return 0.0
        return sum(r.delay_savings for r in self.runs) / len(self.runs)

    @property
    def optimal_count(self) -> int:
        return sum(1 for r in self.runs if r.solver_status == "OPTIMAL")

    def get_run(self, disruption_mode: str) -> Optional[ScalabilityMetrics]:
        """Retrieve metrics for a specific disruption mode."""
        for r in self.runs:
            if r.disruption_mode == disruption_mode:
                return r
        return None

    def summary(self) -> str:
        header = (
            f"\n{'=' * 100}\n"
            f"LOAD LEVEL: {self.label}  ({self.service_count} services)  "
            f"| Optimal: {self.optimal_count}/{len(self.runs)} runs "
            f"| Mean solve: {self.mean_solve_time:.3f}s "
            f"| Max solve: {self.max_solve_time:.3f}s\n"
            f"{'=' * 100}\n"
            f"  {'Disruption Mode':<20} {'Base Del':<10} {'Opt Del':<10} "
            f"{'Savings':<20} {'Rem Conf':<8} {'Status':<14} {'SolveT(s)':<8}\n"
            f"  {'-' * 90}"
        )
        rows = "\n".join(r.to_ascii_row() for r in self.runs)
        return f"{header}\n{rows}"

    def to_dict(self) -> Dict:
        return {
            "load_level": self.load_level.to_dict(),
            "mean_solve_time_seconds": round(self.mean_solve_time, 3),
            "max_solve_time_seconds": round(self.max_solve_time, 3),
            "mean_delay_savings_minutes": round(self.mean_delay_savings, 2),
            "optimal_count": self.optimal_count,
            "runs": [r.to_dict() for r in self.runs],
        }


# ---------------------------------------------------------------------------
# Full scalability report
# ---------------------------------------------------------------------------

@dataclass
class ScalabilityReport:
    """Complete scalability sweep report across all load levels and disruption modes.

    Attributes:
        results:    One ScalabilityResult per load level.
        created_at: ISO-8601 UTC timestamp.
        elapsed_wall_seconds: Total real time taken for the whole sweep.
    """
    results: List[ScalabilityResult] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    elapsed_wall_seconds: float = 0.0

    @property
    def total_runs(self) -> int:
        return sum(len(r.runs) for r in self.results)

    @property
    def total_optimal(self) -> int:
        return sum(r.optimal_count for r in self.results)

    @property
    def overall_mean_solve_time(self) -> float:
        all_runs = [m for res in self.results for m in res.runs]
        if not all_runs:
            return 0.0
        return sum(m.solve_time_seconds for m in all_runs) / len(all_runs)

    def summary(self) -> str:
        """Multi-section ASCII report for all load levels."""
        lines = [
            "=" * 100,
            "BATCH 13 SCALABILITY REPORT: CP-SAT Stress Testing & Scalability Evaluation",
            f"Generated: {self.created_at}",
            f"Total Runs: {self.total_runs} "
            f"({len(self.results)} load levels × {len(ALL_DISRUPTION_MODES)} disruption modes)",
            f"Optimal Solutions: {self.total_optimal}/{self.total_runs}",
            f"Mean CP-SAT Solve Time: {self.overall_mean_solve_time:.3f}s",
            f"Total Elapsed Wall Time: {self.elapsed_wall_seconds:.2f}s",
            "=" * 100,
        ]
        for res in self.results:
            lines.append(res.summary())
        lines.append("=" * 100)
        return "\n".join(lines)

    def to_markdown_report(self) -> str:
        """Full Markdown report suitable for Jupyter notebooks or README export."""
        lines = [
            "# Batch 13 Scalability Report: CP-SAT Stress Testing & Scalability Evaluation",
            "",
            f"**Generated**: `{self.created_at}`  ",
            f"**Total Runs**: {self.total_runs} "
            f"({len(self.results)} load levels × {len(ALL_DISRUPTION_MODES)} disruption modes)  ",
            f"**Optimal Solutions**: {self.total_optimal} / {self.total_runs}  ",
            f"**Mean CP-SAT Solve Time**: {self.overall_mean_solve_time:.3f}s  ",
            f"**Total Elapsed Wall Time**: {self.elapsed_wall_seconds:.2f}s  ",
            "",
            "## Results by Load Level",
            "",
            "| Load Level | Services | Disruption Mode | Feasible Base | CP-SAT Opt | Delay Savings | Rem Conflicts | Solver Status (Time) |",
            "| :--- | :---: | :--- | :--- | :--- | :--- | :---: | :--- |",
        ]
        for res in self.results:
            for run in res.runs:
                lines.append(run.to_markdown_row())
        lines.append("")

        # Scalability summary table: one row per load level, showing NORMAL mode
        lines += [
            "## Scalability Scaling Summary (NORMAL disruption mode)",
            "",
            "| Load Level | Services | Base Del (m) | Opt Del (m) | Savings | Opt Status | Solve Time (s) |",
            "| :--- | :---: | :---: | :---: | :---: | :--- | :---: |",
        ]
        for res in self.results:
            normal_run = res.get_run(DISRUPTION_NORMAL)
            if normal_run:
                savings_str = (
                    f"{normal_run.delay_savings:+.1f}m ({normal_run.delay_savings_percent:.1f}%)"
                )
                lines.append(
                    f"| {res.label} | {res.service_count} | "
                    f"{normal_run.feasible_baseline_total_delay:.1f} | "
                    f"**{normal_run.optimized_total_delay:.1f}** | "
                    f"{savings_str} | "
                    f"`{normal_run.solver_status}` | "
                    f"{normal_run.solve_time_seconds:.3f} |"
                )
        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "created_at": self.created_at,
            "total_runs": self.total_runs,
            "total_optimal": self.total_optimal,
            "overall_mean_solve_time_seconds": round(self.overall_mean_solve_time, 3),
            "elapsed_wall_seconds": round(self.elapsed_wall_seconds, 2),
            "load_levels": [r.to_dict() for r in self.results],
        }


# ---------------------------------------------------------------------------
# Load-level factory (existing services only)
# ---------------------------------------------------------------------------

def create_west_corridor_load_levels() -> List[ScalabilityLoadLevel]:
    """Return the 5 standard scalability load levels built from existing West Corridor services.

    All service IDs are drawn from data/trains/service_definitions/services.json.
    No synthetic or fabricated train identities are introduced.
    """
    return [
        ScalabilityLoadLevel(
            label="4 Services",
            service_ids=[
                "SRV_12607_01",  # Lalbagh SF Express MAS→AJJ (HIGH)
                "SRV_12609_01",  # Chennai-Mysuru SF Express MAS→AJJ (HIGH)
                "SRV_12610_01",  # Mysuru-Chennai SF Express AJJ→MAS (HIGH)
                "SRV_43219_01",  # Suburban EMU MAS→TRL (NORMAL)
            ],
            outbound_services=["SRV_12607_01", "SRV_12609_01", "SRV_43219_01"],
            rationale=(
                "Core 4-service set matching the existing Exp01–05 benchmark: "
                "two outbound Superfast expresses, one return express, one suburban EMU."
            ),
        ),
        ScalabilityLoadLevel(
            label="8 Services",
            service_ids=[
                "SRV_12607_01",
                "SRV_12609_01",
                "SRV_12610_01",
                "SRV_43219_01",
                "SRV_43411_01",  # EMU MAS→AJJ (NORMAL)
                "SRV_43412_01",  # EMU AJJ→MAS (NORMAL)
                "SRV_16057_01",  # Express MAS→AJJ (HIGH)
                "SRV_16203_01",  # Express MAS→AJJ (HIGH)
            ],
            outbound_services=[
                "SRV_12607_01", "SRV_12609_01", "SRV_43219_01",
                "SRV_43411_01", "SRV_16057_01", "SRV_16203_01",
            ],
            rationale=(
                "Doubles the load with 2 additional EMU pairs and 2 extra express services, "
                "increasing throat-track contention."
            ),
        ),
        ScalabilityLoadLevel(
            label="12 Services",
            service_ids=[
                "SRV_12607_01",
                "SRV_12609_01",
                "SRV_12610_01",
                "SRV_43219_01",
                "SRV_43411_01",
                "SRV_43412_01",
                "SRV_16057_01",
                "SRV_16203_01",
                "SRV_12639_01",  # Express MAS→AJJ (HIGH)
                "SRV_12640_01",  # Express AJJ→MAS (HIGH)
                "SRV_43507_01",  # EMU MAS→AJJ (NORMAL)
                "SRV_43223_01",  # EMU MAS→TRL (NORMAL)
            ],
            outbound_services=[
                "SRV_12607_01", "SRV_12609_01", "SRV_43219_01",
                "SRV_43411_01", "SRV_16057_01", "SRV_16203_01",
                "SRV_12639_01", "SRV_43507_01", "SRV_43223_01",
            ],
            rationale=(
                "Adds two more express pairs (12639/12640) and additional suburban EMUs "
                "to push the scheduler into moderate contention."
            ),
        ),
        ScalabilityLoadLevel(
            label="16 Services",
            service_ids=[
                "SRV_12607_01",
                "SRV_12609_01",
                "SRV_12610_01",
                "SRV_43219_01",
                "SRV_43411_01",
                "SRV_43412_01",
                "SRV_16057_01",
                "SRV_16203_01",
                "SRV_12639_01",
                "SRV_12640_01",
                "SRV_43507_01",
                "SRV_43223_01",
                "SRV_12675_01",  # Express MAS→AJJ (HIGH)
                "SRV_12676_01",  # Express AJJ→MAS (HIGH)
                "SRV_13351_01",  # Express AJJ→MAS (HIGH)
                "SRV_43501_01",  # EMU MAS→AJJ (NORMAL)
            ],
            outbound_services=[
                "SRV_12607_01", "SRV_12609_01", "SRV_43219_01",
                "SRV_43411_01", "SRV_16057_01", "SRV_16203_01",
                "SRV_12639_01", "SRV_43507_01", "SRV_43223_01",
                "SRV_12675_01", "SRV_43501_01",
            ],
            rationale=(
                "Near-maximum West Corridor set; adds 12675/12676 pair, 13351 return, "
                "and 43501 EMU – significant resource contention for CP-SAT scalability probe."
            ),
        ),
        ScalabilityLoadLevel(
            label="Max Available",
            service_ids=[
                "SRV_12607_01",
                "SRV_12609_01",
                "SRV_12610_01",
                "SRV_43219_01",
                "SRV_43411_01",
                "SRV_43412_01",
                "SRV_16057_01",
                "SRV_16203_01",
                "SRV_12639_01",
                "SRV_12640_01",
                "SRV_43507_01",
                "SRV_43223_01",
                "SRV_12675_01",
                "SRV_12676_01",
                "SRV_13351_01",
                "SRV_43501_01",
                "SRV_22625_01",  # Express MAS→AJJ (HIGH)
                "SRV_43413_01",  # EMU MAS→AJJ (NORMAL)
                "SRV_20607_01",  # Express MAS→AJJ (HIGH)
                "SRV_12657_01",  # Express MAS→AJJ (HIGH)
            ],
            outbound_services=[
                "SRV_12607_01", "SRV_12609_01", "SRV_43219_01",
                "SRV_43411_01", "SRV_16057_01", "SRV_16203_01",
                "SRV_12639_01", "SRV_43507_01", "SRV_43223_01",
                "SRV_12675_01", "SRV_43501_01",
                "SRV_22625_01", "SRV_43413_01", "SRV_20607_01", "SRV_12657_01",
            ],
            rationale=(
                "Full stress test using all West Corridor services that share the "
                "MAS/AJJ/TRL routes. Excludes PTMS→MAS services (different corridor)."
            ),
        ),
    ]


# ---------------------------------------------------------------------------
# Scenario construction helpers
# ---------------------------------------------------------------------------

def _build_scenario(
    load_level: ScalabilityLoadLevel,
    disruption_mode: str,
    run_index: int,
) -> Scenario:
    """Construct a Scenario for the given load level and disruption mode.

    Only in-memory parameter changes are applied; no JSON files are modified.
    """
    service_ids = load_level.service_ids
    outbound = load_level.outbound_services
    # Pick the first two HIGH-priority outbound services for injected delays
    high_priority_out = [s for s in outbound if s in {
        "SRV_12607_01", "SRV_12609_01", "SRV_16057_01", "SRV_16203_01",
        "SRV_12639_01", "SRV_12675_01", "SRV_22625_01", "SRV_20607_01",
        "SRV_12657_01",
    }]
    primary = high_priority_out[0] if len(high_priority_out) >= 1 else (outbound[0] if outbound else service_ids[0])
    secondary = high_priority_out[1] if len(high_priority_out) >= 2 else primary
    tertiary = high_priority_out[2] if len(high_priority_out) >= 3 else secondary

    scen_id = f"SCEN_SCALE_{load_level.service_count:02d}_{disruption_mode}_{run_index:02d}"

    if disruption_mode == DISRUPTION_NORMAL:
        return Scenario(
            scenario_id=scen_id,
            name=f"{load_level.label} – Nominal",
            description=(
                f"Nominal operation for {load_level.service_count} services: "
                "no injected delays, all services dispatched on published timetable."
            ),
            affected_service_ids=list(service_ids),
            departure_delays={},
            station_delays={},
            track_speed_restrictions={},
        )

    elif disruption_mode == DISRUPTION_SINGLE_DELAY:
        return Scenario(
            scenario_id=scen_id,
            name=f"{load_level.label} – Single Delay (+15m on {primary})",
            description=(
                f"Single departure delay of +15 min on {primary}. "
                f"{load_level.service_count} total services competing for shared corridor resources."
            ),
            affected_service_ids=list(service_ids),
            departure_delays={primary: 15.0},
            station_delays={},
            track_speed_restrictions={},
        )

    elif disruption_mode == DISRUPTION_MULTI_DELAY:
        return Scenario(
            scenario_id=scen_id,
            name=f"{load_level.label} – Multi Delay ({primary} +20m, {secondary} +10m)",
            description=(
                f"Simultaneous departure delays: {primary} +20m, {secondary} +10m, "
                f"plus +5m extra dwell at PER for {primary}. "
                f"{load_level.service_count} services."
            ),
            affected_service_ids=list(service_ids),
            departure_delays={primary: 20.0, secondary: 10.0},
            station_delays={primary: {"PER": 5.0}},
            track_speed_restrictions={},
        )

    else:  # SEVERE_COMPOUND
        return Scenario(
            scenario_id=scen_id,
            name=f"{load_level.label} – Severe Compound",
            description=(
                f"Severe compound disruption: {primary} +30m, {secondary} +20m, "
                f"{tertiary} +10m departure delays, "
                "plus throat-track speed restriction on MAS_BBQ_THROAT_SEGMENT_DOWN (+4m). "
                f"{load_level.service_count} services."
            ),
            affected_service_ids=list(service_ids),
            departure_delays={primary: 30.0, secondary: 20.0, tertiary: 10.0},
            station_delays={},
            track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 6.0},
        )


# ---------------------------------------------------------------------------
# ScalabilityRunner
# ---------------------------------------------------------------------------

class ScalabilityRunner:
    """Orchestrates the complete scalability sweep across load levels and disruption modes.

    Never mutates the original Network or any JSON dataset.  All scenario
    perturbations are applied exclusively to in-memory clones inside ScenarioRunner.

    Attributes:
        network:              Optional pre-loaded Network; loaded automatically if None.
        time_limit_seconds:   Per-run CP-SAT solve time budget.
        objective_weights:    Objective penalty weights (uses defaults if None).
        load_levels:          Load-level cohorts to sweep (uses West Corridor defaults if None).
        disruption_modes:     Disruption modes to test per load level.
    """

    def __init__(
        self,
        network: Optional[Network] = None,
        time_limit_seconds: float = 20.0,
        objective_weights: Optional[ObjectiveWeights] = None,
        load_levels: Optional[List[ScalabilityLoadLevel]] = None,
        disruption_modes: Optional[List[str]] = None,
    ) -> None:
        self.scenario_runner = ScenarioRunner(
            network=network,
            time_limit_seconds=time_limit_seconds,
            objective_weights=objective_weights,
        )
        self.network = self.scenario_runner.network
        self.time_limit_seconds = time_limit_seconds
        self.load_levels = load_levels or create_west_corridor_load_levels()
        self.disruption_modes = disruption_modes or ALL_DISRUPTION_MODES

    def _extract_metrics(
        self,
        load_level: ScalabilityLoadLevel,
        disruption_mode: str,
        comparison: ScenarioComparison,
    ) -> ScalabilityMetrics:
        """Extract ScalabilityMetrics from a ScenarioComparison result."""
        base_res = comparison.feasible_baseline_result or comparison.baseline_result
        opt_res = comparison.optimized_result

        base_delay = base_res.metrics.total_delay_minutes
        opt_delay = opt_res.metrics.total_delay_minutes
        savings = base_delay - opt_delay
        savings_pct = (savings / base_delay * 100.0) if base_delay > 1e-9 else 0.0

        init_conflicts = comparison.initial_conflicts
        opt_remaining = opt_res.metrics.remaining_conflict_count
        resolved = max(0, init_conflicts - opt_remaining)

        return ScalabilityMetrics(
            load_label=load_level.label,
            service_count=load_level.service_count,
            disruption_mode=disruption_mode,
            feasible_baseline_total_delay=base_delay,
            optimized_total_delay=opt_delay,
            delay_savings=savings,
            delay_savings_percent=savings_pct,
            feasible_baseline_max_delay=base_res.metrics.max_delay_minutes,
            optimized_max_delay=opt_res.metrics.max_delay_minutes,
            feasible_baseline_weighted_delay=base_res.metrics.total_weighted_delay,
            optimized_weighted_delay=opt_res.metrics.total_weighted_delay,
            baseline_throughput=base_res.metrics.throughput_trains_completed,
            optimized_throughput=opt_res.metrics.throughput_trains_completed,
            feasible_baseline_on_time_percent=base_res.metrics.on_time_performance_percent,
            optimized_on_time_percent=opt_res.metrics.on_time_performance_percent,
            initial_conflicts=init_conflicts,
            baseline_remaining_conflicts=base_res.metrics.remaining_conflict_count,
            optimized_remaining_conflicts=opt_remaining,
            resolved_conflicts=resolved,
            feasible_baseline_objective_cost=base_res.cost_breakdown.total_cost,
            optimized_objective_cost=opt_res.cost_breakdown.total_cost,
            solver_status=opt_res.status,
            solve_time_seconds=opt_res.computation_time_seconds,
            precedence_decisions_count=len(opt_res.precedence_decisions),
            resource_decisions_count=len(opt_res.resource_decisions),
        )

    def run_single(
        self,
        load_level: ScalabilityLoadLevel,
        disruption_mode: str,
        run_index: int = 0,
    ) -> ScalabilityMetrics:
        """Run a single (load_level × disruption_mode) scenario and return metrics."""
        scenario = _build_scenario(load_level, disruption_mode, run_index)
        comparison = self.scenario_runner.run_scenario(scenario=scenario)
        return self._extract_metrics(load_level, disruption_mode, comparison)

    def run_load_level(
        self,
        load_level: ScalabilityLoadLevel,
    ) -> ScalabilityResult:
        """Run all disruption modes for a single load level."""
        result = ScalabilityResult(load_level=load_level)
        for mode in self.disruption_modes:
            metrics = self.run_single(load_level, mode, run_index=0)
            result.runs.append(metrics)
        return result

    def run(self) -> ScalabilityReport:
        """Execute the full scalability sweep: all load levels × all disruption modes.

        Returns a ScalabilityReport summarising every data point collected.
        """
        wall_start = time.perf_counter()
        report = ScalabilityReport()

        for load_level in self.load_levels:
            result = self.run_load_level(load_level)
            report.results.append(result)

        report.elapsed_wall_seconds = time.perf_counter() - wall_start
        return report


# ---------------------------------------------------------------------------
# Convenience top-level function
# ---------------------------------------------------------------------------

def run_scalability_suite(
    network: Optional[Network] = None,
    time_limit_seconds: float = 20.0,
    objective_weights: Optional[ObjectiveWeights] = None,
    load_levels: Optional[List[ScalabilityLoadLevel]] = None,
    disruption_modes: Optional[List[str]] = None,
) -> ScalabilityReport:
    """Convenience function: create and run a ScalabilityRunner with one call.

    Args:
        network:              Pre-loaded Network, or None to auto-load from disk.
        time_limit_seconds:   Per-run CP-SAT time budget.
        objective_weights:    Custom objective penalty weights.
        load_levels:          Override default West Corridor load levels.
        disruption_modes:     Override default disruption modes.

    Returns:
        ScalabilityReport with results for every (load_level × disruption_mode) combination.
    """
    runner = ScalabilityRunner(
        network=network,
        time_limit_seconds=time_limit_seconds,
        objective_weights=objective_weights,
        load_levels=load_levels,
        disruption_modes=disruption_modes,
    )
    return runner.run()
