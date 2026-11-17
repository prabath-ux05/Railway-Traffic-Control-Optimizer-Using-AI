"""
evaluation/runner.py
~~~~~~~~~~~~~~~~~~~~
Testbench execution runner for the research evaluation framework.

Executes single experiments or batch evaluation suites, extracts comparative metrics,
and generates structured research summaries.
"""

from typing import List, Optional

from evaluation.experiments import create_standard_evaluation_suite
from evaluation.models import (
    EvaluationSuiteResult,
    ExperimentConfig,
    ExperimentMetrics,
    ExperimentResult,
)
from optimization.objective import ObjectiveWeights
from optimization.scenarios import ScenarioRunner
from simulation.network import Network


class EvaluationRunner:
    """Orchestrates controlled research experiments and comparative metric extraction."""

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

    def run_experiment(self, config: ExperimentConfig) -> ExperimentResult:
        """Executes a single ExperimentConfig and returns a structured ExperimentResult."""
        # Execute scenario via ScenarioRunner
        comparison = self.scenario_runner.run_scenario(
            scenario=config.scenario,
        )

        base_res = comparison.feasible_baseline_result or comparison.baseline_result
        pub_res = comparison.published_baseline_result
        opt_res = comparison.optimized_result

        # Build clean separated metrics
        metrics = ExperimentMetrics(
            # Delay
            published_total_delay_minutes=pub_res.metrics.total_delay_minutes if pub_res else 0.0,
            feasible_baseline_total_delay_minutes=base_res.metrics.total_delay_minutes,
            optimized_total_delay_minutes=opt_res.metrics.total_delay_minutes,
            baseline_total_delay_minutes=base_res.metrics.total_delay_minutes,
            feasible_baseline_max_delay_minutes=base_res.metrics.max_delay_minutes,
            optimized_max_delay_minutes=opt_res.metrics.max_delay_minutes,
            baseline_max_delay_minutes=base_res.metrics.max_delay_minutes,
            feasible_baseline_weighted_delay=base_res.metrics.total_weighted_delay,
            optimized_weighted_delay=opt_res.metrics.total_weighted_delay,
            baseline_weighted_delay=base_res.metrics.total_weighted_delay,
            # Throughput & Punctuality
            baseline_throughput=base_res.throughput,
            optimized_throughput=opt_res.throughput,
            published_on_time_percent=pub_res.metrics.on_time_performance_percent if pub_res else 100.0,
            feasible_baseline_on_time_percent=base_res.metrics.on_time_performance_percent,
            optimized_on_time_percent=opt_res.metrics.on_time_performance_percent,
            baseline_on_time_percent=base_res.metrics.on_time_performance_percent,
            # Conflicts
            initial_conflicts=comparison.initial_conflicts,
            baseline_remaining_conflicts=base_res.metrics.remaining_conflict_count,
            optimized_remaining_conflicts=opt_res.metrics.remaining_conflict_count,
            resolved_conflicts=comparison.resolved_conflicts,
            # Solver & Cost
            feasible_baseline_objective_cost=base_res.cost_breakdown.total_cost,
            optimized_objective_cost=opt_res.cost_breakdown.total_cost,
            baseline_objective_cost=base_res.cost_breakdown.total_cost,
            solver_status=opt_res.status,
            solve_time_seconds=opt_res.computation_time_seconds,
            precedence_decisions_count=len(opt_res.precedence_decisions),
            resource_decisions_count=len(opt_res.resource_decisions),
        )

        return ExperimentResult(
            config=config,
            metrics=metrics,
            comparison=comparison,
        )

    def run_suite(
        self,
        experiments: Optional[List[ExperimentConfig]] = None,
        suite_name: str = "Railway Traffic Optimizer Evaluation Suite",
        description: str = "Comparative evaluation of Baseline Heuristic vs. Google OR-Tools CP-SAT Dispatcher.",
    ) -> EvaluationSuiteResult:
        """Executes a list of experiments and aggregates results into an EvaluationSuiteResult."""
        target_experiments = experiments or create_standard_evaluation_suite()
        results: List[ExperimentResult] = []

        for exp in target_experiments:
            res = self.run_experiment(exp)
            results.append(res)

        return EvaluationSuiteResult(
            suite_name=suite_name,
            description=description,
            results=results,
        )

    def run_standard_suite(self) -> EvaluationSuiteResult:
        """Executes the standard 5-scenario evaluation suite."""
        return self.run_suite(
            experiments=create_standard_evaluation_suite(),
            suite_name="Standard 5-Scenario Operational Benchmark",
            description="Benchmark covering nominal operations, single delays, multiple disruptions, TSRs, and junction bottlenecks.",
        )
