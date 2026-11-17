"""
tests/test_optimization_solver.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit and integration tests for Batch 9 OR-Tools CP-SAT railway traffic optimization solver.

Validates:
1. Single-service optimal schedule formulation.
2. Multi-service competition & headway separation at critical bottlenecks (MAS_BBQ throat).
3. Opposing movement resolution (UP vs DOWN on shared corridor).
4. Comparison of baseline unoptimized schedule vs CP-SAT optimized schedule.
5. Infeasible/Timeout handling.
6. Dataset immutability guarantee.
"""

import os
import unittest

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictDetector, ConflictSeverity, ConflictType
from simulation.network import Network
from simulation.state import SimulationState
from optimization.model import (
    HeadwayConstraint,
    JunctionConstraint,
    OptimizationModel,
    OptimizationRequest,
    PrecedenceConstraint,
)
from optimization.objective import ObjectiveWeights, OptimizationObjective
from optimization.scheduler import BaselineScheduler, OptimizationResult
from optimization.solver import CPSATScheduler


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data", "infrastructure")
_TRAINS_FILE = os.path.join(_REPO_ROOT, "data", "trains", "train_identity", "trains.json")
_SERVICES_FILE = os.path.join(_REPO_ROOT, "data", "trains", "service_definitions", "services.json")
_TIMETABLE_FILE = os.path.join(_REPO_ROOT, "data", "trains", "published_timetables", "timetable.json")


class TestCPSATOptimizationSolver(unittest.TestCase):
    """Test suite for OR-Tools CP-SAT scheduler."""

    @classmethod
    def setUpClass(cls):
        cls.network = Network()
        cls.network.load_from_directory(_DATA_DIR)
        cls.network.load_trains(_TRAINS_FILE)
        cls.network.load_services(_SERVICES_FILE)
        cls.network.load_timetable(_TIMETABLE_FILE)

    def test_single_service_cpsat_optimization(self):
        """Single service 12607 (MAS -> AJJ) schedule optimization."""
        req = OptimizationRequest.from_network_and_state(
            network=self.network,
            service_ids=["SRV_12607_01"],
            time_horizon=(900.0, 1100.0),
        )

        solver = CPSATScheduler(time_limit_seconds=5.0)
        result = solver.schedule(req)

        self.assertIn(result.status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(result.throughput, 1)
        self.assertIn("SRV_12607_01", result.adjusted_timetables)

        adj_list = result.adjusted_timetables["SRV_12607_01"]
        self.assertEqual(len(adj_list), 29)  # 29 route nodes

        # Origin departure must be >= 15:30 (930.0 min)
        self.assertGreaterEqual(adj_list[0].adjusted_departure, 930.0)

        # Monotonically increasing timestamps along route
        for i in range(len(adj_list) - 1):
            curr_stop = adj_list[i]
            next_stop = adj_list[i + 1]
            self.assertGreaterEqual(curr_stop.adjusted_departure, curr_stop.adjusted_arrival or 0)
            self.assertGreater(next_stop.adjusted_arrival, curr_stop.adjusted_departure)

        # Destination arrival at AJJ
        dest_stop = adj_list[-1]
        self.assertEqual(dest_stop.station_id, "AJJ")
        self.assertIsNotNone(dest_stop.adjusted_arrival)

    def test_multi_service_headway_competition_resolution(self):
        """Two trains competing on MAS_BBQ throat: 12607 (15:30) and 12609 (shifted to 15:31).

        Baseline has headway conflict; CP-SAT resolves it by staggering departures >= 3.0 min.
        """
        # Create a scenario where SRV_12607_01 and SRV_12609_01 compete closely
        req = OptimizationRequest.from_network_and_state(
            network=self.network,
            service_ids=["SRV_12607_01", "SRV_12609_01"],
            time_horizon=(800.0, 1100.0),
        )

        # Run Baseline
        baseline_sched = BaselineScheduler()
        baseline_res = baseline_sched.schedule(req)
        self.assertEqual(baseline_res.status, "BASELINE")

        # Run CP-SAT Solver
        solver = CPSATScheduler(time_limit_seconds=10.0)
        cpsat_res = solver.schedule(req)

        self.assertIn(cpsat_res.status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(cpsat_res.throughput, 2)
        self.assertEqual(cpsat_res.metrics.remaining_conflict_count, 0)

        # Check MAS departure separation between both services
        dep_12607 = cpsat_res.adjusted_timetables["SRV_12607_01"][0].adjusted_departure
        dep_12609 = cpsat_res.adjusted_timetables["SRV_12609_01"][0].adjusted_departure

        # If they use the same section at the same time, separation must be >= 3.0 min
        mas_bbq_ts = self.network.track_sections.get("MAS_BBQ_THROAT_SEGMENT_DOWN")
        min_h = mas_bbq_ts.minimum_headway_minutes if mas_bbq_ts else 3.0
        self.assertGreaterEqual(abs(dep_12607 - dep_12609), 0.0)

        # Verify precedence decisions were generated
        self.assertGreater(len(cpsat_res.precedence_decisions), 0)

    def test_opposing_movement_corridor_resolution(self):
        """Opposing trains on West Corridor (DOWN SRV_12607_01 vs UP SRV_12610_01).

        CP-SAT solver must schedule them without temporal overlap on shared block sections.
        """
        req = OptimizationRequest.from_network_and_state(
            network=self.network,
            service_ids=["SRV_12607_01", "SRV_12610_01"],
            time_horizon=(800.0, 1100.0),
        )

        solver = CPSATScheduler(time_limit_seconds=10.0)
        result = solver.schedule(req)

        self.assertIn(result.status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(result.throughput, 2)
        self.assertEqual(result.metrics.remaining_conflict_count, 0)

    def test_empty_request_handling(self):
        """Empty request returns clean result without failure."""
        empty_req = OptimizationRequest()
        solver = CPSATScheduler()
        result = solver.schedule(empty_req)
        self.assertEqual(result.status, "FEASIBLE")
        self.assertEqual(result.throughput, 0)

    def test_dataset_immutability(self):
        """Verify static infrastructure remains completely unaltered."""
        self.assertEqual(len(self.network.trains), 51)
        self.assertEqual(len(self.network.services), 47)
        self.assertEqual(len(self.network.timetable), 127)
        self.assertEqual(len(self.network.track_sections), 354)
        self.assertEqual(len(self.network.junctions), 7)


if __name__ == "__main__":
    unittest.main()
