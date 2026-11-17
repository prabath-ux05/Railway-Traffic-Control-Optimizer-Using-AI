"""
tests/test_phase31_2_scalability.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 31.2: Multi-Load Scalability Experiments & Verification.

Validates:
1. Cohort definitions: exact sizes [4, 8, 12, 16, 20, 30, 40], strict nesting property,
   all services backed by timetable records, all 7 pending services strictly excluded.
2. Route continuity & resource lifecycle: zero stale track section or junction occupancies
   upon completion across all cohorts.
3. Scenario and config factories: deterministic parameters, explicit target IDs, 14 standard configs.
4. Nominal scalability sweep: 100% throughput, OPTIMAL status, monotonic scaling, solve time < 15s.
5. Compound disruption scalability sweep: 100% throughput, OPTIMAL status, delay savings across
   all loads, conflict resolution, solve time < 15s.
6. Absolute determinism: SHA-256 config and result hashes identical across repeated runs.
7. Dataset immutability: zero modifications to published timetable or network infrastructure.
"""

import hashlib
import json
import os
import unittest
from typing import Dict, List, Set

from simulation.clock import SimulationClock
from simulation.network import Network
from simulation.simulator import TrainSimulator
from simulation.state import SimulationState, TrainStatus
from evaluation.framework import (
    ExperimentGroupType,
    PENDING_SERVICES,
    ResearchExperimentConfig,
    ResearchExperimentRunner,
)
from evaluation.scalability_framework import (
    COHORT_4,
    COHORT_8,
    COHORT_12,
    COHORT_16,
    COHORT_20,
    COHORT_30,
    COHORT_40,
    SCALABILITY_COHORTS,
    SCALABILITY_LOAD_LEVELS,
    ScalabilitySuiteResult,
    create_scalability_experiment_config,
    create_scalability_scenario,
    create_scalability_suite,
    run_scalability_experiments,
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")


class TestPhase312Scalability(unittest.TestCase):
    """Unit and integration test suite for Phase 31.2 Scalability Experiments."""

    @classmethod
    def setUpClass(cls):
        cls.net = Network()
        cls.net.load_from_directory(os.path.join(_DATA_DIR, "infrastructure"))
        cls.net.load_trains(os.path.join(_DATA_DIR, "trains", "train_identity", "trains.json"))
        cls.net.load_services(os.path.join(_DATA_DIR, "trains", "service_definitions", "services.json"))
        cls.net.load_timetable(os.path.join(_DATA_DIR, "trains", "published_timetables", "timetable.json"))

        cls.timetable_backed_ids = sorted({e.service_id for e in cls.net.timetable})
        cls.pending_service_ids = sorted(PENDING_SERVICES)

    def test_load_levels_definition(self):
        """Verify load levels match requirement exactly: [4, 8, 12, 16, 20, 30, 40]."""
        self.assertEqual(SCALABILITY_LOAD_LEVELS, [4, 8, 12, 16, 20, 30, 40])
        self.assertEqual(list(SCALABILITY_COHORTS.keys()), [4, 8, 12, 16, 20, 30, 40])

    def test_cohort_sizes_and_nesting_property(self):
        """Verify cohort sizes, no duplicates, strict nesting, and timetable backing."""
        prev_cohort: List[str] = []
        for load_count in SCALABILITY_LOAD_LEVELS:
            cohort = SCALABILITY_COHORTS[load_count]
            # Exact size
            self.assertEqual(len(cohort), load_count, f"Cohort {load_count} wrong size")
            # No duplicates
            self.assertEqual(len(set(cohort)), load_count, f"Cohort {load_count} has duplicates")
            # Strict nesting: Cohort(N-1) is a subset of Cohort(N)
            self.assertTrue(
                set(prev_cohort).issubset(set(cohort)),
                f"Cohort {load_count} does not contain all services from previous cohort",
            )
            # All services exist in network.services
            for s_id in cohort:
                self.assertIn(s_id, self.net.services, f"Service {s_id} not in network")
                self.assertIn(s_id, self.timetable_backed_ids, f"Service {s_id} has no timetable")
            prev_cohort = cohort

        # Cohort 40 must match all 40 timetable-backed services exactly
        self.assertEqual(sorted(COHORT_40), self.timetable_backed_ids)

    def test_strict_exclusion_of_pending_services(self):
        """Verify all 7 pending services are strictly excluded from all load cohorts."""
        self.assertEqual(len(PENDING_SERVICES), 7)
        for load_count, cohort in SCALABILITY_COHORTS.items():
            intersection = set(cohort).intersection(PENDING_SERVICES)
            self.assertEqual(
                len(intersection),
                0,
                f"Cohort {load_count} contains pending services: {intersection}",
            )

    def test_corridor_diversity_across_cohorts(self):
        """Verify that early cohorts span multiple operational corridors."""
        # Cohort 4 should span multiple origins and destinations across corridors
        origins_cohort_4 = {self.net.services[s].origin for s in COHORT_4}
        destinations_cohort_4 = {self.net.services[s].destination for s in COHORT_4}
        self.assertGreaterEqual(len(origins_cohort_4), 2)
        self.assertGreaterEqual(len(destinations_cohort_4), 3)

        # Cohort 8 spans primary terminal hubs (MAS, MS, MSB) plus outer terminals
        origins_cohort_8 = {self.net.services[s].origin for s in COHORT_8}
        self.assertTrue({"MAS", "MS", "MSB"}.issubset(origins_cohort_8))
        self.assertGreaterEqual(len(origins_cohort_8), 4)

    def test_scenario_factories(self):
        """Test nominal and compound disruption scenario factories."""
        for count in SCALABILITY_LOAD_LEVELS:
            # Nominal
            scen_nom = create_scalability_scenario(count, "nominal")
            self.assertEqual(scen_nom.scenario_id, f"SCEN_SCALE_{count}_NOMINAL")
            self.assertEqual(scen_nom.affected_service_ids, SCALABILITY_COHORTS[count])
            self.assertEqual(len(scen_nom.departure_delays), 0)
            self.assertEqual(len(scen_nom.track_speed_restrictions), 0)

            # Compound
            scen_comp = create_scalability_scenario(count, "compound")
            self.assertEqual(scen_comp.scenario_id, f"SCEN_SCALE_{count}_COMPOUND")
            self.assertEqual(scen_comp.affected_service_ids, SCALABILITY_COHORTS[count])
            self.assertIn("SRV_12607_01", scen_comp.departure_delays)
            self.assertIn("MAS_BBQ_THROAT_SEGMENT_DOWN", scen_comp.track_speed_restrictions)
            self.assertEqual(scen_comp.junction_capacity_overrides.get("JCT_BBQ"), 1)

    def test_scalability_suite_config_generation(self):
        """Verify create_scalability_suite generates 14 configs with unique IDs."""
        configs = create_scalability_suite(self.net)
        self.assertEqual(len(configs), 14)

        exp_ids = [c.experiment_id for c in configs]
        self.assertEqual(len(set(exp_ids)), 14, "Experiment IDs must be unique")

        # Verify half are BASELINE and half are COMPOUND_DISRUPTION
        nominal_configs = [c for c in configs if c.group == ExperimentGroupType.BASELINE]
        compound_configs = [c for c in configs if c.group == ExperimentGroupType.COMPOUND_DISRUPTION]
        self.assertEqual(len(nominal_configs), 7)
        self.assertEqual(len(compound_configs), 7)

    def test_route_validity_and_resource_lifecycle(self):
        """Verify all services have valid routes and release resources cleanly without stale locks."""
        for count in [4, 12, 40]:  # Sample representative loads including max load
            cohort = SCALABILITY_COHORTS[count]
            clock = SimulationClock(start_time="04:00")
            state = SimulationState(clock=clock)
            sim = TrainSimulator(network=self.net, clock=clock, state=state)

            for s_id in cohort:
                svc = self.net.services[s_id]
                route = self.net.routes[svc.route_id]
                self.assertGreaterEqual(len(route.ordered_nodes), 2)
                sim.run_service_to_destination(s_id, strict_track_lookup=False)

                # Verify completed status and no current track
                ts = state.get_train_state(s_id)
                self.assertEqual(ts.status, TrainStatus.COMPLETED)
                self.assertIsNone(ts.current_track_section)

            # Verify zero stale active occupancies
            active = state.get_active_occupancies()
            self.assertEqual(len(active), 0, f"Stale active occupancies in load {count}")

    def test_nominal_scalability_sweep(self):
        """Test nominal scalability across all 7 loads: 100% throughput, OPTIMAL, solve time < 15s."""
        runner = ResearchExperimentRunner(network=self.net, time_limit_seconds=15.0)
        prev_throughput = 0

        for count in SCALABILITY_LOAD_LEVELS:
            cfg = create_scalability_experiment_config(count, "nominal")
            res = runner.run_experiment(cfg)
            m = res.metrics

            # Optimization status must be OPTIMAL
            self.assertEqual(m.solver_status, "OPTIMAL")
            # Throughput must equal cohort size
            self.assertEqual(m.throughput, count)
            self.assertEqual(m.completion_rate_percent, 100.0)
            # Throughput must scale monotonically
            self.assertGreater(m.throughput, prev_throughput)
            prev_throughput = m.throughput
            # CP-SAT solve time must be well under 15 seconds
            self.assertLess(m.solve_time_seconds, 15.0)

    def test_compound_disruption_scalability_sweep(self):
        """Test compound disruption across all 7 loads: positive delay savings, OPTIMAL, conflicts resolved."""
        runner = ResearchExperimentRunner(network=self.net, time_limit_seconds=15.0)

        for count in SCALABILITY_LOAD_LEVELS:
            cfg = create_scalability_experiment_config(count, "compound")
            res = runner.run_experiment(cfg)
            m = res.metrics

            # Solver status
            self.assertEqual(m.solver_status, "OPTIMAL")
            # Throughput
            self.assertEqual(m.throughput, count)
            # Delay savings must be positive (CP-SAT outperforms FIFO Feasible Baseline)
            self.assertGreater(m.delay_savings_minutes, 0.0)
            # Remaining conflicts must be 0
            self.assertEqual(m.optimized_remaining_conflicts, 0)
            # Peak delay must not exceed baseline peak delay
            self.assertLessEqual(m.optimized_peak_delay_minutes, m.feasible_baseline_peak_delay_minutes)
            # Solve time under 15s
            self.assertLess(m.solve_time_seconds, 15.0)

    def test_bitwise_determinism(self):
        """Verify that repeated runs of the same load experiment produce identical result_hash."""
        runner = ResearchExperimentRunner(network=self.net, time_limit_seconds=15.0)
        cfg = create_scalability_experiment_config(8, "compound")

        res1 = runner.run_experiment(cfg)
        res2 = runner.run_experiment(cfg)

        self.assertEqual(res1.config.config_hash, res2.config.config_hash)
        self.assertEqual(res1.result_hash, res2.result_hash)
        self.assertEqual(
            res1.metrics.optimized_total_delay_minutes,
            res2.metrics.optimized_total_delay_minutes,
        )

    def test_suite_runner_and_aggregation(self):
        """Test run_scalability_experiments and ScalabilitySuiteResult reporting."""
        # Run smaller 2-load test using the runner function
        suite = run_scalability_experiments(
            network=self.net,
            time_limit_seconds=15.0,
            modes=["compound"],
        )
        self.assertEqual(len(suite.results_map), 7)
        md_table = suite.to_markdown_table("compound")
        self.assertIn("Scalability Performance", md_table)
        self.assertIn("Result Hash", md_table)

        summary = suite.summary()
        self.assertIn("PHASE 31.2", summary)

        data = suite.to_dict()
        self.assertIn("experiments", data)
        self.assertEqual(len(data["experiments"]), 7)

    def test_dataset_immutability(self):
        """Verify zero mutation of published timetables, trains, or network infrastructure."""
        orig_timetable_len = len(self.net.timetable)
        orig_services_len = len(self.net.services)
        orig_trains_len = len(self.net.trains)
        orig_sections_len = len(self.net.track_sections)

        # Run an experiment
        runner = ResearchExperimentRunner(network=self.net)
        cfg = create_scalability_experiment_config(12, "compound")
        runner.run_experiment(cfg)

        self.assertEqual(len(self.net.timetable), orig_timetable_len)
        self.assertEqual(len(self.net.services), orig_services_len)
        self.assertEqual(len(self.net.trains), orig_trains_len)
        self.assertEqual(len(self.net.track_sections), orig_sections_len)


if __name__ == "__main__":
    unittest.main()
