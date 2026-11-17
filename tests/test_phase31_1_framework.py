"""
tests/test_phase31_1_framework.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 31.1 — Research Experiment Framework Test Suite.

Validates:
1. Seven controlled experiment groups (Taxonomy) across 40 backed services.
2. Strict exclusion of all 7 pending services (validation and error raising).
3. Consistent metrics: total, average, peak delays, delay savings, conflicts, throughput, solver status, bottleneck utilization.
4. Deterministic repeatability: config_hash and result_hash stability across runs.
5. Execution of all 7 groups via ResearchExperimentRunner.
6. Absolute immutability of underlying timetable and network datasets.
7. Result serialization (JSON export schema) and Markdown reporting.
"""

import copy
import json
import os
import sys
import unittest
from typing import Dict, List, Set

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from simulation.network import Network
from optimization.scenarios import Scenario
from evaluation.framework import (
    ExperimentGroupType,
    ResearchExperimentConfig,
    ResearchExperimentResult,
    ResearchExperimentRunner,
    ResearchMetrics,
    ResearchSuiteResult,
    create_phase31_research_suite,
    PENDING_SERVICES,
)

_DATA_DIR = os.path.join(_REPO_ROOT, "data", "infrastructure")
_TRAINS_FILE = os.path.join(_REPO_ROOT, "data", "trains", "train_identity", "trains.json")
_SERVICES_FILE = os.path.join(_REPO_ROOT, "data", "trains", "service_definitions", "services.json")
_TIMETABLE_FILE = os.path.join(_REPO_ROOT, "data", "trains", "published_timetables", "timetable.json")


def _load_network() -> Network:
    net = Network()
    net.load_from_directory(_DATA_DIR)
    net.load_trains(_TRAINS_FILE)
    net.load_services(_SERVICES_FILE)
    net.load_timetable(_TIMETABLE_FILE)
    return net


class TestExperimentTaxonomyAndSuite(unittest.TestCase):
    """Verify taxonomy structure and suite completeness."""

    def test_all_seven_groups_defined_in_enum(self):
        expected_groups = {
            "EXP_GRP_01_BASELINE",
            "EXP_GRP_02_DEP_DELAY",
            "EXP_GRP_03_DWELL_DELAY",
            "EXP_GRP_04_SPEED_RESTRICTION",
            "EXP_GRP_05_BLOCKED_SECTION",
            "EXP_GRP_06_JUNCTION_CONTENTION",
            "EXP_GRP_07_COMPOUND",
        }
        actual_groups = {g.value for g in ExperimentGroupType}
        self.assertEqual(actual_groups, expected_groups)

    def test_standard_suite_contains_all_seven_groups(self):
        suite = create_phase31_research_suite()
        self.assertGreaterEqual(len(suite), 7)
        covered_groups = {cfg.group for cfg in suite}
        self.assertEqual(len(covered_groups), 7)
        for g in ExperimentGroupType:
            self.assertIn(g, covered_groups, f"Group {g.value} missing from standard suite.")

    def test_experiment_ids_are_unique(self):
        suite = create_phase31_research_suite()
        ids = [cfg.experiment_id for cfg in suite]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate experiment IDs found in suite.")


class TestStrictPendingServicesExclusion(unittest.TestCase):
    """Verify that none of the 7 pending services can be evaluated."""

    def test_pending_services_list_matches_phase29_and_30(self):
        expected = {
            "SRV_40143_01",
            "SRV_40144_01",
            "SRV_41015_01",
            "SRV_41131_01",
            "SRV_41132_01",
            "SRV_42413_01",
            "SRV_42425_01",
        }
        self.assertEqual(PENDING_SERVICES, expected)

    def test_target_services_reject_pending_service(self):
        for p_svc in PENDING_SERVICES:
            with self.assertRaises(ValueError):
                ResearchExperimentConfig(
                    experiment_id="TEST_REJECT",
                    group=ExperimentGroupType.BASELINE,
                    name="Test Reject",
                    description="Should raise",
                    scenario=Scenario("SCEN_REJECT", "Reject"),
                    target_service_ids=["SRV_12607_01", p_svc],
                )

    def test_scenario_affected_services_reject_pending_service(self):
        for p_svc in PENDING_SERVICES:
            with self.assertRaises(ValueError):
                ResearchExperimentConfig(
                    experiment_id="TEST_REJECT",
                    group=ExperimentGroupType.BASELINE,
                    name="Test Reject",
                    description="Should raise",
                    scenario=Scenario(
                        "SCEN_REJECT",
                        "Reject",
                        affected_service_ids=[p_svc],
                    ),
                    target_service_ids=["SRV_12607_01"],
                )

    def test_standard_suite_contains_zero_pending_services(self):
        suite = create_phase31_research_suite()
        for exp in suite:
            for s_id in exp.target_service_ids:
                self.assertNotIn(s_id, PENDING_SERVICES)
            for s_id in exp.scenario.affected_service_ids:
                self.assertNotIn(s_id, PENDING_SERVICES)


class TestMetricsCalculationAndConsistency(unittest.TestCase):
    """Verify metric calculations, mathematical consistency, and bottleneck utilization."""

    @classmethod
    def setUpClass(cls):
        cls.network = _load_network()
        cls.runner = ResearchExperimentRunner(network=cls.network, time_limit_seconds=10.0)

    def test_consistent_metrics_in_departure_delay_experiment(self):
        cfg = ResearchExperimentConfig(
            experiment_id="EXP_TEST_METRICS",
            group=ExperimentGroupType.DEPARTURE_DELAY,
            name="Metrics Calculation Test",
            description="Testing mathematical consistency of metrics.",
            scenario=Scenario(
                scenario_id="SCEN_TEST_METRICS",
                name="Test Metrics",
                affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
                departure_delays={"SRV_12607_01": 20.0},
            ),
            target_service_ids=["SRV_12607_01", "SRV_12609_01"],
            time_horizon=(800.0, 1150.0),
        )
        res = self.runner.run_experiment(cfg)
        m = res.metrics

        # 1. Total and savings consistency
        self.assertAlmostEqual(m.delay_savings_minutes, m.feasible_baseline_total_delay_minutes - m.optimized_total_delay_minutes, places=2)
        if m.feasible_baseline_total_delay_minutes > 0:
            expected_pct = (m.delay_savings_minutes / m.feasible_baseline_total_delay_minutes) * 100.0
            self.assertAlmostEqual(m.delay_savings_percent, expected_pct, places=2)

        # 2. Average delay consistency
        self.assertEqual(m.throughput, 2)
        self.assertAlmostEqual(m.feasible_baseline_average_delay_minutes, m.feasible_baseline_total_delay_minutes / 2.0, places=2)
        self.assertAlmostEqual(m.optimized_average_delay_minutes, m.optimized_total_delay_minutes / 2.0, places=2)
        self.assertAlmostEqual(m.average_delay_savings_minutes, m.feasible_baseline_average_delay_minutes - m.optimized_average_delay_minutes, places=2)

        # 3. Peak delay consistency
        self.assertAlmostEqual(m.peak_delay_savings_minutes, m.feasible_baseline_peak_delay_minutes - m.optimized_peak_delay_minutes, places=2)

        # 4. Completion rate
        self.assertEqual(m.completion_rate_percent, 100.0)
        self.assertIn(m.solver_status, ("OPTIMAL", "FEASIBLE"))


class TestDeterministicRepeatability(unittest.TestCase):
    """Verify config_hash and result_hash stability."""

    @classmethod
    def setUpClass(cls):
        cls.network = _load_network()
        cls.runner = ResearchExperimentRunner(network=cls.network, time_limit_seconds=10.0)

    def test_config_hash_is_deterministic(self):
        cfg1 = ResearchExperimentConfig(
            experiment_id="EXP_TEST_HASH",
            group=ExperimentGroupType.SPEED_RESTRICTION,
            name="Hash Test",
            description="Testing config hash.",
            scenario=Scenario("SCEN_H", "Hash", track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 8.0}),
            target_service_ids=["SRV_12607_01", "SRV_12609_01"],
            time_horizon=(800.0, 1150.0),
        )
        cfg2 = ResearchExperimentConfig(
            experiment_id="EXP_TEST_HASH",
            group=ExperimentGroupType.SPEED_RESTRICTION,
            name="Hash Test",
            description="Testing config hash.",
            scenario=Scenario("SCEN_H", "Hash", track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 8.0}),
            target_service_ids=["SRV_12607_01", "SRV_12609_01"],
            time_horizon=(800.0, 1150.0),
        )
        self.assertEqual(cfg1.config_hash, cfg2.config_hash)

    def test_identical_runs_produce_identical_result_hash_and_metrics(self):
        cfg = ResearchExperimentConfig(
            experiment_id="EXP_TEST_REPEAT",
            group=ExperimentGroupType.DEPARTURE_DELAY,
            name="Repeatability Test",
            description="Testing identical runs.",
            scenario=Scenario("SCEN_R", "Repeat", departure_delays={"SRV_12607_01": 15.0}),
            target_service_ids=["SRV_12607_01", "SRV_12609_01"],
            time_horizon=(800.0, 1150.0),
        )
        res1 = self.runner.run_experiment(cfg)
        res2 = self.runner.run_experiment(cfg)

        self.assertEqual(res1.result_hash, res2.result_hash)
        self.assertEqual(res1.metrics.feasible_baseline_total_delay_minutes, res2.metrics.feasible_baseline_total_delay_minutes)
        self.assertEqual(res1.metrics.optimized_total_delay_minutes, res2.metrics.optimized_total_delay_minutes)
        self.assertEqual(res1.metrics.delay_savings_minutes, res2.metrics.delay_savings_minutes)
        self.assertEqual(len(res1.comparison.optimized_result.precedence_decisions), len(res2.comparison.optimized_result.precedence_decisions))


class TestSevenControlledExperimentGroupsExecution(unittest.TestCase):
    """Execute one representative experiment from each of the 7 controlled groups."""

    @classmethod
    def setUpClass(cls):
        cls.network = _load_network()
        cls.runner = ResearchExperimentRunner(network=cls.network, time_limit_seconds=15.0)
        cls.suite = create_phase31_research_suite()

    def _find_first_in_group(self, group: ExperimentGroupType) -> ResearchExperimentConfig:
        for cfg in self.suite:
            if cfg.group == group:
                return cfg
        raise ValueError(f"No experiment in group {group}")

    def test_group1_baseline_execution(self):
        cfg = self._find_first_in_group(ExperimentGroupType.BASELINE)
        res = self.runner.run_experiment(cfg)
        self.assertIn(res.metrics.solver_status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(res.metrics.throughput, len(cfg.target_service_ids))

    def test_group2_departure_delay_execution(self):
        cfg = self._find_first_in_group(ExperimentGroupType.DEPARTURE_DELAY)
        res = self.runner.run_experiment(cfg)
        self.assertIn(res.metrics.solver_status, ("OPTIMAL", "FEASIBLE"))
        self.assertGreaterEqual(res.metrics.feasible_baseline_total_delay_minutes, 20.0)

    def test_group3_dwell_delay_execution(self):
        cfg = self._find_first_in_group(ExperimentGroupType.DWELL_DELAY)
        res = self.runner.run_experiment(cfg)
        self.assertIn(res.metrics.solver_status, ("OPTIMAL", "FEASIBLE"))

    def test_group4_speed_restriction_execution(self):
        cfg = self._find_first_in_group(ExperimentGroupType.SPEED_RESTRICTION)
        res = self.runner.run_experiment(cfg)
        self.assertIn(res.metrics.solver_status, ("OPTIMAL", "FEASIBLE"))
        self.assertIn("MAS_BBQ_THROAT_SEGMENT_DOWN", res.metrics.bottleneck_utilization)

    def test_group5_blocked_section_execution(self):
        cfg = self._find_first_in_group(ExperimentGroupType.BLOCKED_SECTION)
        res = self.runner.run_experiment(cfg)
        self.assertIn(res.metrics.solver_status, ("OPTIMAL", "FEASIBLE"))
        self.assertIn("PAB_PTMS_SUBURBAN_DOWN", res.metrics.bottleneck_utilization)

    def test_group6_junction_contention_execution(self):
        cfg = self._find_first_in_group(ExperimentGroupType.JUNCTION_CONTENTION)
        res = self.runner.run_experiment(cfg)
        self.assertIn(res.metrics.solver_status, ("OPTIMAL", "FEASIBLE"))
        self.assertIn("JCT_BBQ", res.metrics.bottleneck_utilization)

    def test_group7_compound_disruption_execution(self):
        cfg = self._find_first_in_group(ExperimentGroupType.COMPOUND_DISRUPTION)
        res = self.runner.run_experiment(cfg)
        self.assertIn(res.metrics.solver_status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(res.metrics.remaining_conflicts, 0)


class TestResultSerializationAndReporting(unittest.TestCase):
    """Verify result serialization to dict/JSON and Markdown summary generation."""

    @classmethod
    def setUpClass(cls):
        cls.network = _load_network()
        cls.runner = ResearchExperimentRunner(network=cls.network, time_limit_seconds=10.0)
        cls.suite = create_phase31_research_suite()

    def test_result_to_dict_and_json_serializable(self):
        cfg = self.suite[0]
        res = self.runner.run_experiment(cfg)
        d = res.to_dict()
        # Verify JSON serializability
        dumped = json.dumps(d, indent=2)
        self.assertIsInstance(dumped, str)
        self.assertIn("config_hash", d)
        self.assertIn("result_hash", d)
        self.assertIn("metrics", d)

    def test_suite_result_markdown_generation(self):
        subset = self.suite[:2]
        suite_res = self.runner.run_suite(subset, suite_id="TEST_SUITE", suite_name="Test Suite")
        md = suite_res.generate_markdown()
        self.assertIn("# Railway Traffic Optimization — Research Experiment Suite Report", md)
        self.assertIn("TEST_SUITE", md)
        self.assertIn("Summary of Experiment Groups", md)
        for exp in subset:
            self.assertIn(exp.experiment_id, md)

    def test_dataset_immutability_guarantee(self):
        # Verify raw published timetable unchanged
        self.assertEqual(len(self.network.timetable), 127)
        self.assertEqual(len(self.network.trains), 51)
        self.assertEqual(len(self.network.services), 47)
        mas_12607 = next(e for e in self.network.timetable if e.service_id == "SRV_12607_01" and e.station_id == "MAS")
        self.assertEqual(mas_12607.departure, "15:30")


if __name__ == "__main__":
    unittest.main()
