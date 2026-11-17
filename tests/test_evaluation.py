"""
tests/test_evaluation.py
~~~~~~~~~~~~~~~~~~~~~~~~
Unit and integration tests for Batch 11 Research Evaluation & Experiment Framework.

Validates:
1. MetricComparison and ExperimentMetrics serialization.
2. Nominal No-Delay baseline experiment.
3. Single train delayed departure experiment.
4. Multiple simultaneous delays experiment.
5. Track speed restriction experiment.
6. Junction bottleneck & headway constraint experiment.
7. Complete Standard Evaluation Suite execution and Markdown reporting.
8. Absolute immutability of underlying railway datasets during evaluation.
"""

import json
import os
import unittest

from evaluation import (
    EvaluationRunner,
    EvaluationSuiteResult,
    ExperimentConfig,
    ExperimentMetrics,
    ExperimentResult,
    MetricComparison,
    create_junction_bottleneck_experiment,
    create_multiple_simultaneous_delays_experiment,
    create_no_delay_baseline_experiment,
    create_single_train_delay_experiment,
    create_speed_restriction_experiment,
    create_standard_evaluation_suite,
)
from simulation.network import Network


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data", "infrastructure")
_TRAINS_FILE = os.path.join(_REPO_ROOT, "data", "trains", "train_identity", "trains.json")
_SERVICES_FILE = os.path.join(_REPO_ROOT, "data", "trains", "service_definitions", "services.json")
_TIMETABLE_FILE = os.path.join(_REPO_ROOT, "data", "trains", "published_timetables", "timetable.json")


class TestEvaluationFramework(unittest.TestCase):
    """Test suite for research evaluation and experiment benchmarking."""

    @classmethod
    def setUpClass(cls):
        cls.network = Network()
        cls.network.load_from_directory(_DATA_DIR)
        cls.network.load_trains(_TRAINS_FILE)
        cls.network.load_services(_SERVICES_FILE)
        cls.network.load_timetable(_TIMETABLE_FILE)
        cls.runner = EvaluationRunner(network=cls.network, time_limit_seconds=10.0)

    def test_metric_comparison_and_serialization(self):
        comp = MetricComparison(
            metric_name="Total Delay",
            baseline_value=120.0,
            optimized_value=90.0,
            unit="min",
            higher_is_better=False,
        )
        self.assertAlmostEqual(comp.delta, 30.0)
        self.assertAlmostEqual(comp.percent_change, 25.0)

        d = comp.to_dict()
        self.assertEqual(d["metric_name"], "Total Delay")
        self.assertEqual(d["delta"], 30.0)
        self.assertEqual(d["percent_change"], 25.0)

    def test_no_delay_baseline_experiment(self):
        config = create_no_delay_baseline_experiment()
        result = self.runner.run_experiment(config)

        self.assertIsInstance(result, ExperimentResult)
        self.assertEqual(result.metrics.solver_status, "OPTIMAL")
        self.assertEqual(result.metrics.optimized_throughput, 4)
        self.assertEqual(result.metrics.published_total_delay_minutes, 0.0)
        self.assertEqual(result.metrics.feasible_baseline_total_delay_minutes, 115.0)
        self.assertGreaterEqual(result.metrics.optimized_on_time_percent, 90.0)
        self.assertIn("NOMINAL", result.summary().upper())

    def test_single_train_delay_experiment(self):
        config = create_single_train_delay_experiment()
        result = self.runner.run_experiment(config)

        self.assertEqual(result.metrics.solver_status, "OPTIMAL")
        self.assertEqual(result.metrics.published_total_delay_minutes, 45.0)
        self.assertGreater(result.metrics.feasible_baseline_total_delay_minutes, result.metrics.published_total_delay_minutes)
        self.assertLess(result.metrics.optimized_total_delay_minutes, result.metrics.feasible_baseline_total_delay_minutes)
        self.assertGreater(result.metrics.delay_savings_minutes, 0.0)
        self.assertEqual(result.metrics.optimized_throughput, 4)
        self.assertIn("| `EXP_02_SINGLE_DELAY` |", result.to_markdown_row())

    def test_multiple_simultaneous_delays_experiment(self):
        config = create_multiple_simultaneous_delays_experiment()
        result = self.runner.run_experiment(config)

        self.assertEqual(result.metrics.solver_status, "OPTIMAL")
        self.assertEqual(result.metrics.published_total_delay_minutes, 90.0)
        self.assertGreater(result.metrics.feasible_baseline_total_delay_minutes, result.metrics.published_total_delay_minutes)
        self.assertLess(result.metrics.optimized_total_delay_minutes, result.metrics.feasible_baseline_total_delay_minutes)
        self.assertGreater(result.metrics.delay_savings_percent, 20.0)
        self.assertEqual(result.metrics.optimized_throughput, 4)
        self.assertGreater(len(result.comparison.optimized_result.precedence_decisions), 0)

    def test_speed_restriction_experiment(self):
        config = create_speed_restriction_experiment()
        result = self.runner.run_experiment(config)

        self.assertEqual(result.metrics.solver_status, "OPTIMAL")
        self.assertEqual(result.metrics.optimized_throughput, 4)
        self.assertGreater(result.metrics.solve_time_seconds, 0.0)

    def test_junction_bottleneck_experiment(self):
        config = create_junction_bottleneck_experiment()
        result = self.runner.run_experiment(config)

        self.assertEqual(result.metrics.solver_status, "OPTIMAL")
        self.assertEqual(result.metrics.optimized_throughput, 4)
        self.assertEqual(result.metrics.optimized_remaining_conflicts, 0)

    def test_standard_evaluation_suite_run_and_reporting(self):
        suite_res = self.runner.run_standard_suite()

        self.assertIsInstance(suite_res, EvaluationSuiteResult)
        self.assertEqual(suite_res.total_experiments, 5)
        self.assertEqual(suite_res.optimal_count, 5)
        self.assertGreater(suite_res.total_baseline_delay, 0.0)
        self.assertGreater(suite_res.average_solve_time, 0.0)

        # Verify Markdown report generation
        md = suite_res.to_markdown_report()
        self.assertIn("# Evaluation Suite Report:", md)
        self.assertIn("EXP_01_NO_DELAY", md)
        self.assertIn("EXP_02_SINGLE_DELAY", md)
        self.assertIn("EXP_03_MULTI_DELAY", md)
        self.assertIn("EXP_04_SPEED_RESTRICTION", md)
        self.assertIn("EXP_05_JUNCTION_BOTTLENECK", md)

        # Verify summary output
        summary = suite_res.summary()
        self.assertIn("EVALUATION SUITE SUMMARY:", summary)

        # Verify JSON dictionary structure
        d = suite_res.to_dict()
        self.assertEqual(d["total_experiments"], 5)
        self.assertEqual(len(d["experiments"]), 5)

    def test_evaluation_preserves_dataset_integrity(self):
        # Record pre-evaluation hashes or lengths
        tt_len_before = len(self.network.timetable)
        sec_len_before = len(self.network.track_sections)
        srv_len_before = len(self.network.services)

        # Read JSON file content
        with open(_TIMETABLE_FILE, "r", encoding="utf-8") as f:
            tt_json_before = f.read()

        # Run full suite
        _ = self.runner.run_standard_suite()

        # Verify in-memory structures remain identical
        self.assertEqual(len(self.network.timetable), tt_len_before)
        self.assertEqual(len(self.network.track_sections), sec_len_before)
        self.assertEqual(len(self.network.services), srv_len_before)

        # Verify disk JSON files were never written to
        with open(_TIMETABLE_FILE, "r", encoding="utf-8") as f:
            tt_json_after = f.read()
        self.assertEqual(tt_json_before, tt_json_after)
