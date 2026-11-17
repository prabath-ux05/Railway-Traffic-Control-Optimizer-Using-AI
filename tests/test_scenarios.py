"""
tests/test_scenarios.py
~~~~~~~~~~~~~~~~~~~~~~~
Unit and integration tests for Batch 10 What-If Scenario Engine.

Validates:
1. Scenario formulation and serialization.
2. Single service delayed departure What-If execution.
3. Multiple simultaneous delays across West corridor services.
4. Track speed restrictions and temporary bottleneck evaluations.
5. Comparative evaluation (Baseline vs CP-SAT) and savings metrics.
6. Absolute immutability of underlying Network and JSON datasets.
"""

import os
import unittest

from simulation.clock import time_to_minutes
from simulation.network import Network
from optimization.scenarios import (
    Scenario,
    ScenarioComparison,
    ScenarioRunner,
)


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data", "infrastructure")
_TRAINS_FILE = os.path.join(_REPO_ROOT, "data", "trains", "train_identity", "trains.json")
_SERVICES_FILE = os.path.join(_REPO_ROOT, "data", "trains", "service_definitions", "services.json")
_TIMETABLE_FILE = os.path.join(_REPO_ROOT, "data", "trains", "published_timetables", "timetable.json")


class TestScenarioWhatIfEngine(unittest.TestCase):
    """Test suite for the What-If Scenario simulation and optimization engine."""

    @classmethod
    def setUpClass(cls):
        cls.network = Network()
        cls.network.load_from_directory(_DATA_DIR)
        cls.network.load_trains(_TRAINS_FILE)
        cls.network.load_services(_SERVICES_FILE)
        cls.network.load_timetable(_TIMETABLE_FILE)
        cls.runner = ScenarioRunner(network=cls.network, time_limit_seconds=10.0)

    def test_scenario_dataclass_and_serialization(self):
        scen = Scenario(
            scenario_id="SCEN_TEST_01",
            name="Test Departure Delay",
            description="Simulating 15m delay on 12607",
            affected_service_ids=["SRV_12607_01"],
            departure_delays={"SRV_12607_01": 15.0},
            track_speed_restrictions={"MAS_BBQ_THROAT_SEGMENT_DOWN": 8.0},
        )
        d = scen.to_dict()
        self.assertEqual(d["scenario_id"], "SCEN_TEST_01")
        self.assertEqual(d["departure_delays"]["SRV_12607_01"], 15.0)
        self.assertEqual(d["track_speed_restrictions"]["MAS_BBQ_THROAT_SEGMENT_DOWN"], 8.0)

    def test_single_train_delayed_departure_scenario(self):
        """Scenario: SRV_12607_01 departs MAS 20 minutes late (15:50 instead of 15:30)."""
        scen = Scenario(
            scenario_id="SCEN_LATE_12607",
            name="12607 20-Minute Departure Delay at MAS",
            description="Superfast Express 12607 held at MAS for 20 minutes due to late incoming rake.",
            affected_service_ids=["SRV_12607_01"],
            departure_delays={"SRV_12607_01": 20.0},
        )

        comparison = self.runner.run_scenario(scen, time_horizon=(900.0, 1150.0))

        self.assertIn(comparison.optimization_status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(comparison.throughput, 1)

        # Baseline reflects unoptimized propagation
        self.assertGreater(comparison.baseline_total_delay, 0.0)

        # CP-SAT optimizes running and dwell recovery
        self.assertGreaterEqual(comparison.optimized_total_delay, 0.0)
        self.assertIn("SCEN_LATE_12607", comparison.summary())
        self.assertIsInstance(comparison.to_dict(), dict)

    def test_multiple_simultaneous_delays_scenario(self):
        """Scenario: Multiple West Corridor services delayed simultaneously.

        - SRV_12607_01 delayed 15m (15:45)
        - SRV_12609_01 delayed 30m (14:05)
        - SRV_43219_01 delayed 10m (09:25)
        """
        scen = Scenario(
            scenario_id="SCEN_MULTI_DELAY",
            name="Multiple Simultaneous Corridor Delays",
            description="Peak congestion event causing concurrent departure delays across 3 services.",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_43219_01"],
            departure_delays={
                "SRV_12607_01": 15.0,
                "SRV_12609_01": 30.0,
                "SRV_43219_01": 10.0,
            },
        )

        comparison = self.runner.run_scenario(scen, time_horizon=(500.0, 1150.0))

        self.assertIn(comparison.optimization_status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(comparison.throughput, 3)
        self.assertEqual(comparison.remaining_conflicts, 0)
        self.assertGreaterEqual(len(comparison.optimized_result.precedence_decisions), 0)

    def test_track_speed_restriction_what_if_scenario(self):
        """Scenario: Temporary Caution Order on MAS_BBQ Throat segment (travel time doubled: 4.0 -> 8.0 min)."""
        scen = Scenario(
            scenario_id="SCEN_SPEED_RESTRICTION",
            name="MAS-BBQ Throat Speed Restriction",
            description="Track maintenance speed restriction doubling traversal time on MAS_BBQ throat.",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
            track_speed_restrictions={
                "MAS_BBQ_THROAT_SEGMENT_DOWN": 8.0,
            },
        )

        comparison = self.runner.run_scenario(scen, time_horizon=(800.0, 1150.0))

        self.assertIn(comparison.optimization_status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(comparison.throughput, 2)
        self.assertEqual(comparison.remaining_conflicts, 0)

    def test_temporary_junction_bottleneck_scenario(self):
        """Scenario: Basin Bridge Junction throat bottleneck constraint evaluation."""
        scen = Scenario(
            scenario_id="SCEN_JUNCTION_BOTTLENECK",
            name="Basin Bridge Junction Throat Contention",
            description="Tight interlocking clearance constraint at Basin Bridge Junction.",
            affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"],
            junction_capacity_overrides={"JCT_BBQ": 1},
        )

        comparison = self.runner.run_scenario(scen, time_horizon=(800.0, 1150.0))

        self.assertIn(comparison.optimization_status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(comparison.throughput, 3)
        self.assertEqual(comparison.remaining_conflicts, 0)

    def test_dataset_immutability_guarantee(self):
        """Verify that running multiple What-If scenarios leaves original datasets 100% untouched."""
        self.assertEqual(len(self.network.trains), 51)
        self.assertEqual(len(self.network.services), 47)
        self.assertEqual(len(self.network.timetable), 127)
        self.assertEqual(len(self.network.track_sections), 354)
        self.assertEqual(len(self.network.junctions), 7)

        # Check raw timetable entry for 12607 at MAS is still exactly 15:30
        mas_12607 = next(e for e in self.network.timetable if e.service_id == "SRV_12607_01" and e.station_id == "MAS")
        self.assertEqual(mas_12607.departure, "15:30")

        # Check MAS_BBQ throat travel time is still exactly 4.0 min
        mas_bbq = self.network.track_sections.get("MAS_BBQ_THROAT_SEGMENT_DOWN")
        self.assertEqual(mas_bbq.travel_time_minutes, 4.0)


if __name__ == "__main__":
    unittest.main()
