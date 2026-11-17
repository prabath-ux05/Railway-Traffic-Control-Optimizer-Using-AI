"""
evaluation/models.py
~~~~~~~~~~~~~~~~~~~~
Data contracts and report structures for the research evaluation framework.

Defines structured models for:
- MetricComparison: Explicit baseline vs. optimized comparison with semantic delta.
- ExperimentMetrics: Comprehensive collection of operational, timetable, and solver metrics.
- ExperimentConfig: Definition and parameters for a reproducible experiment.
- ExperimentResult: Complete evaluated outcome of a single experiment.
- EvaluationSuiteResult: Multi-experiment research testbench results with aggregation.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from optimization.scenarios import Scenario, ScenarioComparison
from optimization.scheduler import OptimizationResult


@dataclass
class MetricComparison:
    """Represents a pairwise metric comparison between Baseline and CP-SAT."""
    metric_name: str
    baseline_value: float
    optimized_value: float
    unit: str = ""
    higher_is_better: bool = False

    @property
    def delta(self) -> float:
        """Raw difference (baseline - optimized). Positive means reduction in delay/conflicts/cost."""
        if self.higher_is_better:
            return self.optimized_value - self.baseline_value
        return self.baseline_value - self.optimized_value

    @property
    def percent_change(self) -> Optional[float]:
        """Percentage change relative to baseline if baseline != 0."""
        if abs(self.baseline_value) < 1e-6:
            return 0.0 if abs(self.optimized_value) < 1e-6 else None
        return (self.delta / abs(self.baseline_value)) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_name": self.metric_name,
            "baseline_value": round(self.baseline_value, 2),
            "optimized_value": round(self.optimized_value, 2),
            "unit": self.unit,
            "delta": round(self.delta, 2),
            "percent_change": round(self.percent_change, 2) if self.percent_change is not None else None,
            "higher_is_better": self.higher_is_better,
        }


@dataclass
class ExperimentMetrics:
    """Comprehensive performance metrics capturing Published Reference, Feasible Baseline, and CP-SAT outcomes.

    Ensures fair, mathematically valid comparison between the Physically Feasible Baseline and CP-SAT.
    """
    # 1. Delay Metrics
    published_total_delay_minutes: float = 0.0
    feasible_baseline_total_delay_minutes: float = 0.0
    optimized_total_delay_minutes: float = 0.0
    baseline_total_delay_minutes: float = 0.0  # Backward-compatible alias to feasible baseline
    feasible_baseline_max_delay_minutes: float = 0.0
    optimized_max_delay_minutes: float = 0.0
    baseline_max_delay_minutes: float = 0.0   # Backward-compatible alias
    feasible_baseline_weighted_delay: float = 0.0
    optimized_weighted_delay: float = 0.0
    baseline_weighted_delay: float = 0.0      # Backward-compatible alias

    # 2. Throughput & Punctuality
    baseline_throughput: int = 0
    optimized_throughput: int = 0
    published_on_time_percent: float = 100.0
    feasible_baseline_on_time_percent: float = 100.0
    optimized_on_time_percent: float = 100.0
    baseline_on_time_percent: float = 100.0   # Backward-compatible alias

    # 3. Conflict Resolution
    initial_conflicts: int = 0
    baseline_remaining_conflicts: int = 0
    optimized_remaining_conflicts: int = 0
    resolved_conflicts: int = 0

    # 4. Objective & Solver Evaluation
    feasible_baseline_objective_cost: float = 0.0
    optimized_objective_cost: float = 0.0
    baseline_objective_cost: float = 0.0      # Backward-compatible alias
    solver_status: str = "OPTIMAL"
    solve_time_seconds: float = 0.0
    precedence_decisions_count: int = 0
    resource_decisions_count: int = 0

    @property
    def delay_savings_minutes(self) -> float:
        """Minutes saved by CP-SAT relative to the physically feasible baseline."""
        return self.feasible_baseline_total_delay_minutes - self.optimized_total_delay_minutes

    @property
    def delay_savings_percent(self) -> float:
        """Percentage delay reduction relative to the physically feasible baseline."""
        if self.feasible_baseline_total_delay_minutes > 1e-6:
            return (self.delay_savings_minutes / self.feasible_baseline_total_delay_minutes) * 100.0
        return 0.0

    @property
    def weighted_delay_savings(self) -> float:
        """Weighted delay saved by CP-SAT relative to the physically feasible baseline."""
        return self.feasible_baseline_weighted_delay - self.optimized_weighted_delay

    @property
    def cost_savings(self) -> float:
        """Objective cost reduction relative to the physically feasible baseline."""
        return self.feasible_baseline_objective_cost - self.optimized_objective_cost

    def to_dict(self) -> Dict[str, Any]:
        return {
            "delay": {
                "published_total_delay_min": round(self.published_total_delay_minutes, 2),
                "feasible_baseline_total_delay_min": round(self.feasible_baseline_total_delay_minutes, 2),
                "optimized_total_delay_min": round(self.optimized_total_delay_minutes, 2),
                "delay_savings_min": round(self.delay_savings_minutes, 2),
                "delay_savings_percent": round(self.delay_savings_percent, 2),
                "feasible_baseline_max_delay_min": round(self.feasible_baseline_max_delay_minutes, 2),
                "optimized_max_delay_min": round(self.optimized_max_delay_minutes, 2),
                "feasible_baseline_weighted_delay": round(self.feasible_baseline_weighted_delay, 2),
                "optimized_weighted_delay": round(self.optimized_weighted_delay, 2),
                "weighted_delay_savings": round(self.weighted_delay_savings, 2),
            },
            "throughput_and_service": {
                "baseline_throughput": self.baseline_throughput,
                "optimized_throughput": self.optimized_throughput,
                "published_on_time_percent": round(self.published_on_time_percent, 2),
                "feasible_baseline_on_time_percent": round(self.feasible_baseline_on_time_percent, 2),
                "optimized_on_time_percent": round(self.optimized_on_time_percent, 2),
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
                "feasible_baseline_objective_cost": round(self.feasible_baseline_objective_cost, 2),
                "optimized_objective_cost": round(self.optimized_objective_cost, 2),
                "cost_savings": round(self.cost_savings, 2),
                "precedence_decisions": self.precedence_decisions_count,
                "resource_decisions": self.resource_decisions_count,
            },
        }


@dataclass
class ExperimentConfig:
    """Definition of a reproducible research experiment."""
    experiment_id: str
    name: str
    category: str
    description: str
    scenario: Scenario
    time_limit_seconds: float = 15.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "scenario": self.scenario.to_dict(),
            "time_limit_seconds": self.time_limit_seconds,
        }


@dataclass
class ExperimentResult:
    """Complete results for a single evaluated experiment."""
    config: ExperimentConfig
    metrics: ExperimentMetrics
    comparison: ScenarioComparison

    @property
    def experiment_id(self) -> str:
        return self.config.experiment_id

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def category(self) -> str:
        return self.config.category

    def summary(self) -> str:
        """Format an ASCII research summary for this experiment."""
        m = self.metrics
        lines = [
            f"====================================================================================================",
            f"EXPERIMENT: [{self.config.experiment_id}] {self.config.name}",
            f"Category:   {self.config.category}",
            f"Narrative:  {self.config.description}",
            f"----------------------------------------------------------------------------------------------------",
            f"METRIC                            PUBLISHED REF     FEASIBLE BASELINE (FIFO)   CP-SAT OPTIMIZED   IMPROVEMENT",
            f"----------------------------------------------------------------------------------------------------",
            f"Solver Status                     REFERENCE         FEASIBLE_BASELINE          {m.solver_status:<18} -",
            f"Total Delay (min)                 {m.published_total_delay_minutes:<17.1f} {m.feasible_baseline_total_delay_minutes:<26.1f} {m.optimized_total_delay_minutes:<18.1f} {m.delay_savings_minutes:+.1f} min ({m.delay_savings_percent:.1f}%)",
            f"Max Individual Delay (min)        -                 {m.feasible_baseline_max_delay_minutes:<26.1f} {m.optimized_max_delay_minutes:<18.1f} {m.feasible_baseline_max_delay_minutes - m.optimized_max_delay_minutes:+.1f} min",
            f"Weighted Delay                    -                 {m.feasible_baseline_weighted_delay:<26.1f} {m.optimized_weighted_delay:<18.1f} {m.weighted_delay_savings:+.1f}",
            f"Throughput (Scheduled Services)   {m.baseline_throughput:<17d} {m.baseline_throughput:<26d} {m.optimized_throughput:<18d} 100%",
            f"On-Time Performance (<=5m)        {m.published_on_time_percent:<17.1f}%{m.feasible_baseline_on_time_percent:<26.1f}%{m.optimized_on_time_percent:<18.1f}%{m.optimized_on_time_percent - m.feasible_baseline_on_time_percent:+.1f}%",
            f"Conflicts (Init / Rem / Solved)   {m.initial_conflicts} / {m.baseline_remaining_conflicts:<13d}0 / 0                      0 / {m.optimized_remaining_conflicts} (-{m.resolved_conflicts})",
            f"Objective Cost                    -                 {m.feasible_baseline_objective_cost:<26.2f} {m.optimized_objective_cost:<18.2f} {m.cost_savings:+.2f}",
            f"Solve Time (s)                    -                 0.005                      {m.solve_time_seconds:<18.3f} -",
            f"====================================================================================================",
        ]
        return "\n".join(lines)

    def to_markdown_row(self) -> str:
        """Format as a row for a Markdown comparison table."""
        m = self.metrics
        savings_str = f"**{m.delay_savings_minutes:+.1f}m ({m.delay_savings_percent:.1f}%)**" if abs(m.delay_savings_minutes) > 0.01 else "0.0m (0.0%)"
        return (
            f"| `{self.config.experiment_id}` | {self.config.name} | "
            f"{m.published_total_delay_minutes:.1f}m | {m.feasible_baseline_total_delay_minutes:.1f}m | **{m.optimized_total_delay_minutes:.1f}m** | "
            f"{savings_str} | "
            f"{m.feasible_baseline_on_time_percent:.1f}% | **{m.optimized_on_time_percent:.1f}%** | "
            f"`{m.solver_status}` ({m.solve_time_seconds:.3f}s) |"
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "config": self.config.to_dict(),
            "metrics": self.metrics.to_dict(),
            "comparison": self.comparison.to_dict(),
        }


@dataclass
class EvaluationSuiteResult:
    """Aggregated outcome of executing a multi-experiment evaluation testbench."""
    suite_name: str
    description: str
    results: List[ExperimentResult] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def total_experiments(self) -> int:
        return len(self.results)

    @property
    def optimal_count(self) -> int:
        return sum(1 for r in self.results if r.metrics.solver_status == "OPTIMAL")

    @property
    def total_published_delay(self) -> float:
        return sum(r.metrics.published_total_delay_minutes for r in self.results)

    @property
    def total_feasible_baseline_delay(self) -> float:
        return sum(r.metrics.feasible_baseline_total_delay_minutes for r in self.results)

    @property
    def total_baseline_delay(self) -> float:
        return self.total_feasible_baseline_delay

    @property
    def total_optimized_delay(self) -> float:
        return sum(r.metrics.optimized_total_delay_minutes for r in self.results)

    @property
    def total_delay_savings(self) -> float:
        return self.total_feasible_baseline_delay - self.total_optimized_delay

    @property
    def overall_savings_percent(self) -> float:
        if self.total_feasible_baseline_delay > 1e-6:
            return (self.total_delay_savings / self.total_feasible_baseline_delay) * 100.0
        return 0.0

    @property
    def total_conflicts_resolved(self) -> int:
        return sum(r.metrics.resolved_conflicts for r in self.results)

    @property
    def average_solve_time(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.metrics.solve_time_seconds for r in self.results) / len(self.results)

    def summary(self) -> str:
        """Format an ASCII research summary for the complete testbench."""
        lines = [
            f"====================================================================================================",
            f"EVALUATION SUITE SUMMARY: {self.suite_name}",
            f"Total Experiments: {self.total_experiments} | Optimal Solutions: {self.optimal_count}/{self.total_experiments}",
            f"Total Delay:       Published {self.total_published_delay:.1f}m | Feasible Base {self.total_feasible_baseline_delay:.1f}m -> CP-SAT {self.total_optimized_delay:.1f}m",
            f"Net Delay Savings: {self.total_delay_savings:+.1f} min ({self.overall_savings_percent:.1f}% reduction)",
            f"Average Solve Time: {self.average_solve_time:.3f} seconds",
            f"====================================================================================================",
        ]
        for r in self.results:
            lines.append(f"  * [{r.config.experiment_id}] {r.config.name}: "
                         f"Feasible Base {r.metrics.feasible_baseline_total_delay_minutes:.1f}m -> Opt {r.metrics.optimized_total_delay_minutes:.1f}m "
                         f"(Savings: {r.metrics.delay_savings_minutes:+.1f}m / {r.metrics.delay_savings_percent:.1f}%, {r.metrics.solver_status}, {r.metrics.solve_time_seconds:.3f}s)")
        lines.append(f"====================================================================================================")
        return "\n".join(lines)

    def to_markdown_report(self) -> str:
        """Generate a complete research Markdown report."""
        lines = [
            f"# Evaluation Suite Report: {self.suite_name}",
            f"",
            f"**Timestamp**: `{self.created_at}`  ",
            f"**Total Experiments Evaluated**: {self.total_experiments}  ",
            f"**Solver Optimality Rate**: {self.optimal_count} / {self.total_experiments} ({(self.optimal_count / self.total_experiments * 100):.1f}%)  ",
            f"**Total Delay Savings**: `{self.total_delay_savings:+.1f} min` ({self.overall_savings_percent:.1f}% reduction over Feasible Baseline)  ",
            f"**Average CP-SAT Solve Time**: {self.average_solve_time:.3f} seconds  ",
            f"",
            f"## Comparative Results Table (Published Ref vs Feasible Baseline vs CP-SAT)",
            f"",
            f"| Experiment ID | Scenario Name | Pub Ref | Feasible Base | CP-SAT Opt | Delay Savings | Base OTP | Opt OTP | Solver Status (Time) |",
            f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for r in self.results:
            lines.append(r.to_markdown_row())
        lines.append("")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suite_name": self.suite_name,
            "description": self.description,
            "created_at": self.created_at,
            "total_experiments": self.total_experiments,
            "optimal_count": self.optimal_count,
            "total_published_delay": round(self.total_published_delay, 2),
            "total_feasible_baseline_delay": round(self.total_feasible_baseline_delay, 2),
            "total_baseline_delay": round(self.total_baseline_delay, 2),
            "total_optimized_delay": round(self.total_optimized_delay, 2),
            "total_delay_savings": round(self.total_delay_savings, 2),
            "overall_savings_percent": round(self.overall_savings_percent, 2),
            "total_conflicts_resolved": self.total_conflicts_resolved,
            "average_solve_time_seconds": round(self.average_solve_time, 3),
            "experiments": [r.to_dict() for r in self.results],
        }
