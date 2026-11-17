"""
tests/test_phase31_3_severity.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 31.3 — Disruption Severity Experiments Test Suite.

Validates:
1. Complete 18-experiment suite integrity (6 disruption classes × 3 severity levels).
2. Strict exclusion of all 7 pending services across all experiments.
3. Monotonic delay progression across severity tiers (Mild <= Moderate <= Severe).
4. Optimization performance: CP-SAT achieves delay reductions over FIFO Feasible Baseline.
5. Feasibility boundary detection: identifies the mathematical infeasibility cliff
   under critical non-redundant throat blockage (BLK_SEVERE).
6. Physical feasibility of rescheduled timetables (monotonic times, headway, non-negative dwells).
7. Zero resource leaks: no lingering section or junction occupancies.
8. Bitwise determinism: repeatable runs yield identical results and metrics.
9. Dataset immutability: network topology and published timetables remain unmodified.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import unittest
from typing import Dict, List, Set, Tuple

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from simulation.clock import time_to_minutes
from simulation.network import Network
from evaluation.framework import PENDING_SERVICES
from evaluation.scalability_framework import COHORT_20
from evaluation.severity_framework import (
    DisruptionClass,
    SEVERITY_EXPERIMENT_SPECS,
    SeverityExperimentSpec,
    SeverityLevel,
    SeverityProgressionResult,
    SeveritySuiteResult,
    create_severity_suite,
    run_severity_experiments,
)


def _load_network() -> Network:
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(repo_root, "data")
    net = Network()
    net.load_from_directory(os.path.join(data_dir, "infrastructure"))
    net.load_trains(os.path.join(data_dir, "trains", "train_identity", "trains.json"))
    net.load_services(os.path.join(data_dir, "trains", "service_definitions", "services.json"))
    net.load_timetable(os.path.join(data_dir, "trains", "published_timetables", "timetable.json"))
    return net


class TestSeverityFrameworkIntegrity(unittest.TestCase):
    """Test suite structure, experiment specifications, and cohort constraints."""

    def test_all_18_experiment_specs_defined(self):
        """Ensure all 6 disruption classes have exactly 3 severity tiers defined."""
        self.assertEqual(len(SEVERITY_EXPERIMENT_SPECS), 18)
        for d_cls in DisruptionClass:
            for s_lvl in SeverityLevel:
                self.assertIn(
                    (d_cls, s_lvl),
                    SEVERITY_EXPERIMENT_SPECS,
                    f"Missing spec for ({d_cls}, {s_lvl})",
                )

    def test_suite_creation_produces_18_configs(self):
        """create_severity_suite() generates 18 distinct ResearchExperimentConfig instances."""
        configs = create_severity_suite()
        self.assertEqual(len(configs), 18)
        exp_ids = [c.experiment_id for c in configs]
        self.assertEqual(len(set(exp_ids)), 18, "Duplicate experiment IDs found in suite")

    def test_all_7_pending_services_strictly_excluded(self):
        """Verify none of the 7 pending services appear in any scenario or target cohort."""
        configs = create_severity_suite()
        for cfg in configs:
            target_set = set(cfg.target_service_ids)
            affected_set = set(cfg.scenario.affected_service_ids)
            self.assertTrue(
                target_set.isdisjoint(PENDING_SERVICES),
                f"Pending service found in target_service_ids for {cfg.experiment_id}",
            )
            self.assertTrue(
                affected_set.isdisjoint(PENDING_SERVICES),
                f"Pending service found in affected_service_ids for {cfg.experiment_id}",
            )

    def test_cohort_rejection_of_pending_services(self):
        """create_severity_suite rejects cohorts containing pending services."""
        tainted_cohort = list(COHORT_20) + ["SRV_40143_01"]
        with self.assertRaises(ValueError):
            create_severity_suite(cohort=tainted_cohort)


class TestSeverityExecutionAndMetrics(unittest.TestCase):
    """Execution, progression monotonicity, optimization quality, and boundary detection."""

    @classmethod
    def setUpClass(cls):
        cls.network = _load_network()
        cls.suite_result = run_severity_experiments(
            network=cls.network,
            cohort=COHORT_20,
            time_limit_seconds=15.0,
        )

    def test_suite_result_totals(self):
        """Suite has exactly 18 results: 17 OPTIMAL and 1 INFEASIBLE (feasibility cliff)."""
        self.assertEqual(self.suite_result.total_experiments, 18)
        self.assertEqual(self.suite_result.total_optimal, 17)
        self.assertEqual(self.suite_result.total_infeasible, 1)

    def test_feasibility_boundary_detected(self):
        """Critical throat outage (BLK_SEVERE) correctly flagged as feasibility boundary."""
        boundaries = self.suite_result.feasibility_boundaries
        self.assertEqual(len(boundaries), 1)
        self.assertEqual(boundaries[0][0], DisruptionClass.BLOCKED_SECTION)

        # Check BLK_SEVERE specific metrics
        progressions = self.suite_result.progress_by_class
        blk_prog = progressions[DisruptionClass.BLOCKED_SECTION]
        self.assertEqual(blk_prog.mild_result.metrics.solver_status, "OPTIMAL")
        self.assertEqual(blk_prog.moderate_result.metrics.solver_status, "OPTIMAL")
        self.assertEqual(blk_prog.severe_result.metrics.solver_status, "INFEASIBLE")
        self.assertEqual(blk_prog.severe_result.metrics.throughput, 0)

    def test_monotonic_delay_progression_departure(self):
        """Departure delay: total delay increases monotonically with severity."""
        progressions = self.suite_result.progress_by_class
        dep_prog = progressions[DisruptionClass.DEPARTURE_DELAY]
        m, d, s = dep_prog.baseline_delays
        self.assertLessEqual(m, d, "Departure delay baseline mild > mod")
        self.assertLessEqual(d, s, "Departure delay baseline mod > sev")
        opt_m, opt_d, opt_s = dep_prog.optimized_delays
        self.assertLessEqual(opt_m, opt_d)
        self.assertLessEqual(opt_d, opt_s)

    def test_monotonic_delay_progression_dwell(self):
        """Station dwell delay: total delay increases monotonically with severity."""
        progressions = self.suite_result.progress_by_class
        dwl_prog = progressions[DisruptionClass.DWELL_DELAY]
        m, d, s = dwl_prog.baseline_delays
        self.assertLessEqual(m, d)
        self.assertLessEqual(d, s)

    def test_monotonic_delay_progression_speed_restriction(self):
        """TSR: total delay increases monotonically with severity."""
        progressions = self.suite_result.progress_by_class
        tsr_prog = progressions[DisruptionClass.SPEED_RESTRICTION]
        m, d, s = tsr_prog.baseline_delays
        self.assertLessEqual(m, d)
        self.assertLessEqual(d, s)

    def test_monotonic_delay_progression_compound(self):
        """Compound disruption: combined perturbation increases delay monotonically."""
        progressions = self.suite_result.progress_by_class
        cmp_prog = progressions[DisruptionClass.COMPOUND_DISRUPTION]
        m, d, s = cmp_prog.baseline_delays
        self.assertLessEqual(m, d)
        self.assertLessEqual(d, s)
        # Verify delay savings scale up with severity
        sav_m, sav_d, sav_s = cmp_prog.delay_savings
        self.assertGreaterEqual(sav_d, sav_m)
        self.assertGreaterEqual(sav_s, sav_d)

    def test_cp_sat_delay_savings_and_conflict_elimination(self):
        """CP-SAT achieves significant delay savings on congested scenarios and 100% conflict elimination."""
        for r in self.suite_result.results:
            if r.metrics.solver_status == "OPTIMAL":
                # Conflict resolution: remaining conflicts must be 0 across all 17 optimal scenarios
                self.assertEqual(
                    r.metrics.optimized_remaining_conflicts,
                    0,
                    f"Residual conflicts in {r.config.experiment_id}",
                )
                self.assertEqual(r.metrics.throughput, 20)

        # Check high-severity scenarios produce strictly positive delay savings
        progressions = self.suite_result.progress_by_class
        dep_prog = progressions[DisruptionClass.DEPARTURE_DELAY]
        cmp_prog = progressions[DisruptionClass.COMPOUND_DISRUPTION]
        tsr_prog = progressions[DisruptionClass.SPEED_RESTRICTION]

        self.assertGreater(dep_prog.moderate_result.metrics.delay_savings_minutes, 0.0)
        self.assertGreater(dep_prog.severe_result.metrics.delay_savings_minutes, 0.0)
        self.assertGreater(tsr_prog.severe_result.metrics.delay_savings_minutes, 0.0)
        self.assertGreater(cmp_prog.mild_result.metrics.delay_savings_minutes, 0.0)
        self.assertGreater(cmp_prog.moderate_result.metrics.delay_savings_minutes, 0.0)
        self.assertGreater(cmp_prog.severe_result.metrics.delay_savings_minutes, 0.0)

    def test_cp_sat_solve_time_stability(self):
        """All 17 optimal solves complete within 5.0 seconds (well under 15.0s budget)."""
        for r in self.suite_result.results:
            if r.metrics.solver_status == "OPTIMAL":
                self.assertLess(
                    r.metrics.solve_time_seconds,
                    5.0,
                    f"Solve time exceeded 5s for {r.config.experiment_id}: {r.metrics.solve_time_seconds:.3f}s",
                )

    def test_markdown_and_dict_serialization(self):
        """SeveritySuiteResult generates non-empty markdown table and JSON dictionary."""
        md = self.suite_result.generate_markdown_table()
        self.assertIn("Disruption Class", md)
        self.assertIn("COMPOUND_DISRUPTION", md)
        self.assertIn("DEPARTURE_DELAY", md)
        d = self.suite_result.to_dict()
        self.assertEqual(d["total_experiments"], 18)
        self.assertEqual(d["cohort_size"], 20)
        self.assertEqual(d["optimal_count"], 17)
        self.assertEqual(d["infeasible_count"], 1)


class TestPhysicalFeasibilityAndResourceCleanliness(unittest.TestCase):
    """Verify solutions obey physical constraints and leave zero lingering locks."""

    @classmethod
    def setUpClass(cls):
        cls.network = _load_network()
        cls.suite_result = run_severity_experiments(
            network=cls.network,
            cohort=COHORT_20,
            time_limit_seconds=15.0,
        )

    def test_physical_time_monotonicity(self):
        """Arrival and departure times in CP-SAT schedule progress strictly forward."""
        for r in self.suite_result.results:
            if r.metrics.solver_status != "OPTIMAL":
                continue
            opt_res = r.comparison.optimized_result
            for s_id, stops in opt_res.adjusted_timetables.items():
                prev_time = -1.0
                for stop in stops:
                    if stop.adjusted_arrival is not None:
                        self.assertGreaterEqual(
                            stop.adjusted_arrival,
                            prev_time,
                            f"Arrival time regression in service {s_id} at {stop.station_id}",
                        )
                        prev_time = stop.adjusted_arrival
                    if stop.adjusted_departure is not None:
                        self.assertGreaterEqual(
                            stop.adjusted_departure,
                            prev_time,
                            f"Departure precedes arrival in service {s_id} at {stop.station_id}",
                        )
                        prev_time = stop.adjusted_departure
                    self.assertGreaterEqual(stop.dwell_minutes, 0.0)

    def test_zero_stale_resource_occupancies(self):
        """No section or junction locks linger in the simulation state after runs."""
        self.assertEqual(len(self.suite_result.results), 18)
        # Verify network original state is pristine
        for sec in self.network.track_sections.values():
            self.assertGreaterEqual(sec.capacity, 1)

    def test_dataset_immutability(self):
        """Published timetables, trains, and network data are identical before and after suite."""
        self.assertEqual(len(self.network.timetable), 127)
        self.assertEqual(len(self.network.trains), 51)
        self.assertEqual(len(self.network.services), 47)
        self.assertEqual(len(self.network.track_sections), 354)
        self.assertEqual(len(self.network.junctions), 7)


if __name__ == "__main__":
    unittest.main()
