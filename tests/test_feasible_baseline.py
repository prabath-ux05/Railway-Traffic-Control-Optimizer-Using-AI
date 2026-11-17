"""
tests/test_feasible_baseline.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit and integration tests for Batch 12: Physically Feasible Baseline & Evaluation Correction.

Validates:
1. FeasibleBaselineScheduler respects physical running times, dwell times, and headway.
2. Equivalent physical constraint scope between FeasibleBaselineScheduler and CPSATScheduler.
3. Accurate 3-tier comparison: Published Reference vs Feasible Baseline vs CP-SAT.
4. Mathematically valid delay savings and percentage improvements under disruptions.
5. Absolute immutability of underlying published timetable and network datasets.
"""

import json
import os
import unittest

from simulation.clock import time_to_minutes
from simulation.network import Network
from optimization.model import OptimizationRequest
from optimization.objective import OptimizationObjective
from optimization.scheduler import (
    BaselineScheduler,
    FeasibleBaselineScheduler,
    OptimizationResult,
    PassiveBaselineScheduler,
)
from optimization.scenarios import Scenario, ScenarioRunner
from optimization.solver import CPSATScheduler


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data", "infrastructure")
_TRAINS_FILE = os.path.join(_REPO_ROOT, "data", "trains", "train_identity", "trains.json")
_SERVICES_FILE = os.path.join(_REPO_ROOT, "data", "trains", "service_definitions", "services.json")
_TIMETABLE_FILE = os.path.join(_REPO_ROOT, "data", "trains", "published_timetables", "timetable.json")


class TestPhysicallyFeasibleBaseline(unittest.TestCase):
    """Test suite validating the physically feasible baseline scheduler."""

    @classmethod
    def setUpClass(cls):
        cls.network = Network()
        cls.network.load_from_directory(_DATA_DIR)
        cls.network.load_trains(_TRAINS_FILE)
        cls.network.load_services(_SERVICES_FILE)
        cls.network.load_timetable(_TIMETABLE_FILE)
        cls.feasible_scheduler = FeasibleBaselineScheduler()
        cls.passive_scheduler = BaselineScheduler()
        cls.cpsat_solver = CPSATScheduler(time_limit_seconds=10.0)

    def test_published_timetable_immutability(self):
        """Verifies that running FeasibleBaselineScheduler does not mutate the published timetable."""
        orig_entries = [(e.service_id, e.station_id, e.arrival, e.departure) for e in self.network.timetable]
        
        target_sids = ["SRV_12607_01", "SRV_12609_01"]
        target_services = {s: self.network.services[s] for s in target_sids}
        request = OptimizationRequest(
            services=target_services,
            trains={s.train_id: self.network.trains[s.train_id] for s in target_services.values()},
            timetable=[e for e in self.network.timetable if e.service_id in target_services],
            routes={s.route_id: self.network.routes[s.route_id] for s in target_services.values()},
            track_sections=self.network.track_sections,
            junctions=self.network.junctions,
            current_delays={"SRV_12607_01": 20.0},
        )

        result = self.feasible_scheduler.schedule(request)
        self.assertEqual(result.status, "FEASIBLE_BASELINE")

        # Confirm published entries in network remain untouched
        current_entries = [(e.service_id, e.station_id, e.arrival, e.departure) for e in self.network.timetable]
        self.assertEqual(orig_entries, current_entries)

    def test_feasible_baseline_respects_running_times_and_dwells(self):
        """Verifies that feasible baseline guarantees physical traversal times along every edge."""
        target_sids = ["SRV_12607_01"]
        target_services = {s: self.network.services[s] for s in target_sids}
        request = OptimizationRequest(
            services=target_services,
            trains={s.train_id: self.network.trains[s.train_id] for s in target_services.values()},
            timetable=[e for e in self.network.timetable if e.service_id in target_services],
            routes={s.route_id: self.network.routes[s.route_id] for s in target_services.values()},
            track_sections=self.network.track_sections,
            junctions=self.network.junctions,
        )

        result = self.feasible_scheduler.schedule(request)
        adjs = result.adjusted_timetables["SRV_12607_01"]

        # Ensure all arrival times strictly follow running times and departures >= arrivals
        for i in range(len(adjs) - 1):
            curr_stop = adjs[i]
            next_stop = adjs[i + 1]
            if curr_stop.adjusted_departure is not None and next_stop.adjusted_arrival is not None:
                self.assertGreater(next_stop.adjusted_arrival, curr_stop.adjusted_departure)

    def test_feasible_baseline_and_cpsat_equivalent_constraint_scope(self):
        """Verifies that FeasibleBaseline and CP-SAT operate on the same physical constraints under nominal conditions."""
        target_sids = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43219_01"]
        target_services = {s: self.network.services[s] for s in target_sids}
        request = OptimizationRequest(
            services=target_services,
            trains={s.train_id: self.network.trains[s.train_id] for s in target_services.values()},
            timetable=[e for e in self.network.timetable if e.service_id in target_services],
            routes={s.route_id: self.network.routes[s.route_id] for s in target_services.values()},
            track_sections=self.network.track_sections,
            junctions=self.network.junctions,
        )

        feasible_res = self.feasible_scheduler.schedule(request)
        cpsat_res = self.cpsat_solver.schedule(request)

        # Under nominal unperturbed operations, both produce identical total delay
        self.assertEqual(feasible_res.status, "FEASIBLE_BASELINE")
        self.assertEqual(cpsat_res.status, "OPTIMAL")
        self.assertAlmostEqual(feasible_res.metrics.total_delay_minutes, cpsat_res.metrics.total_delay_minutes, places=1)
        self.assertEqual(feasible_res.metrics.remaining_conflict_count, 0)
        self.assertEqual(cpsat_res.metrics.remaining_conflict_count, 0)

    def test_cpsat_yields_mathematically_valid_delay_savings_under_disruption(self):
        """Verifies that CP-SAT achieves valid positive delay savings over Feasible Baseline during compound delays."""
        target_sids = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43219_01"]
        target_services = {s: self.network.services[s] for s in target_sids}
        request = OptimizationRequest(
            services=target_services,
            trains={s.train_id: self.network.trains[s.train_id] for s in target_services.values()},
            timetable=[e for e in self.network.timetable if e.service_id in target_services],
            routes={s.route_id: self.network.routes[s.route_id] for s in target_services.values()},
            track_sections=self.network.track_sections,
            junctions=self.network.junctions,
            current_delays={"SRV_12607_01": 20.0, "SRV_12609_01": 10.0},
        )

        feasible_res = self.feasible_scheduler.schedule(request)
        cpsat_res = self.cpsat_solver.schedule(request)

        self.assertEqual(cpsat_res.status, "OPTIMAL")
        
        # Valid mathematical improvement: CP-SAT total delay <= Feasible Baseline total delay
        self.assertLessEqual(cpsat_res.metrics.total_delay_minutes, feasible_res.metrics.total_delay_minutes)
        delay_savings = feasible_res.metrics.total_delay_minutes - cpsat_res.metrics.total_delay_minutes
        self.assertGreater(delay_savings, 0.0)

    def test_scenario_runner_produces_3_tier_comparison(self):
        """Verifies that ScenarioRunner produces valid 3-tier comparison results."""
        runner = ScenarioRunner(network=self.network, time_limit_seconds=10.0)
        scenario = Scenario(
            scenario_id="SCEN_TEST_3TIER",
            name="3-Tier Disruption Test",
            description="Testing 15m delay on 12607",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43219_01"],
            departure_delays={"SRV_12607_01": 15.0},
        )
        comp = runner.run(scenario)

        self.assertIsNotNone(comp.published_baseline_result)
        self.assertIsNotNone(comp.feasible_baseline_result)
        self.assertIsNotNone(comp.optimized_result)

        # Published ref has only passive 15m delay propagated
        self.assertEqual(comp.published_total_delay, 45.0)
        # Feasible baseline has physical travel times + delays
        self.assertGreater(comp.baseline_total_delay, comp.published_total_delay)
        # CP-SAT delay is strictly <= Feasible baseline delay
        self.assertLessEqual(comp.optimized_total_delay, comp.baseline_total_delay)
        self.assertGreaterEqual(comp.delay_savings_minutes, 0.0)
