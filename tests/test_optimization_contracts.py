"""
tests/test_optimization_contracts.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests for the Optimization Layer input/output contracts, constraint models,
objective specifications, and scheduling interfaces.
"""

import os
import unittest

from simulation.clock import time_to_minutes
from simulation.conflicts import Conflict, ConflictSeverity, ConflictType
from simulation.network import Network, Service, TimetableEntry, Train, Route, TrackSection
from simulation.state import SimulationState
from optimization.model import (
    HeadwayConstraint,
    JunctionConstraint,
    OptimizationModel,
    OptimizationRequest,
    PlatformConstraint,
    PrecedenceConstraint,
    PrecedenceDecision,
    ResourceAllocationDecision,
    ServiceTimetableAdjustment,
)
from optimization.objective import (
    ObjectiveCostBreakdown,
    ObjectiveWeights,
    OptimizationObjective,
)
from optimization.scheduler import (
    BaselineScheduler,
    OptimizationResult,
    PerformanceMetrics,
)


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data", "infrastructure")
_TRAINS_FILE = os.path.join(_REPO_ROOT, "data", "trains", "train_identity", "trains.json")
_SERVICES_FILE = os.path.join(_REPO_ROOT, "data", "trains", "service_definitions", "services.json")
_TIMETABLE_FILE = os.path.join(_REPO_ROOT, "data", "trains", "published_timetables", "timetable.json")


class TestOptimizationInputContracts(unittest.TestCase):
    """Tests for OptimizationRequest and constraint domain models."""

    def test_optimization_request_creation_and_factory(self):
        net = Network()
        net.load_from_directory(_DATA_DIR)
        net.load_trains(_TRAINS_FILE)
        net.load_services(_SERVICES_FILE)
        net.load_timetable(_TIMETABLE_FILE)

        req = OptimizationRequest.from_network_and_state(
            network=net,
            service_ids=["SRV_12607_01", "SRV_12609_01"],
            time_horizon=(720.0, 1080.0),
        )

        self.assertEqual(len(req.services), 2)
        self.assertIn("SRV_12607_01", req.services)
        self.assertIn("SRV_12609_01", req.services)
        self.assertGreaterEqual(len(req.timetable), 6)
        self.assertGreater(len(req.headway_constraints), 0)
        self.assertGreater(len(req.junction_constraints), 0)
        self.assertEqual(req.time_horizon, (720.0, 1080.0))

    def test_optimization_model_validation(self):
        net = Network()
        net.load_from_directory(_DATA_DIR)
        net.load_trains(_TRAINS_FILE)
        net.load_services(_SERVICES_FILE)
        net.load_timetable(_TIMETABLE_FILE)

        req = OptimizationRequest.from_network_and_state(network=net)
        model = OptimizationModel(request=req)
        issues = model.validate()
        self.assertEqual(len(issues), 0)
        self.assertTrue(model.validated)

        # Test route sections extraction
        sections = model.get_service_route_sections("SRV_12607_01")
        self.assertGreater(len(sections), 0)
        self.assertEqual(sections[0].from_node, "MAS")
        self.assertEqual(sections[0].to_node, "BBQ")

    def test_constraint_models(self):
        hw = HeadwayConstraint(
            section_id="SEC_MAS_BBQ",
            preceding_service_id="SRV_1",
            following_service_id="SRV_2",
            minimum_headway_minutes=3.0,
            direction="DOWN",
        )
        self.assertEqual(hw.minimum_headway_minutes, 3.0)

        jct = JunctionConstraint(
            junction_id="JCT_BBQ",
            node_id="BBQ",
            competing_service_ids=["SRV_1", "SRV_2"],
            capacity=1,
        )
        self.assertEqual(jct.capacity, 1)


class TestOptimizationObjectiveContracts(unittest.TestCase):
    """Tests for ObjectiveWeights and cost evaluation."""

    def test_objective_weights_and_cost_breakdown(self):
        weights = ObjectiveWeights(
            delay_weight=1.5,
            weighted_delay_weight=2.0,
            conflict_penalty_critical=1000.0,
        )
        objective = OptimizationObjective(weights=weights)

        conflict = Conflict(
            conflict_id="CONF_0001",
            conflict_type=ConflictType.SAME_TRACK_SECTION,
            affected_service_ids=["SRV_1", "SRV_2"],
            affected_train_ids=["TR_1", "TR_2"],
            resource_id="SEC_1",
            conflict_time=360.0,
            severity=ConflictSeverity.CRITICAL,
            description="Capacity violation",
        )

        cost = objective.evaluate_cost(
            total_delay_minutes=10.0,
            total_weighted_delay=20.0,
            max_delay_minutes=5.0,
            conflicts=[conflict],
        )

        self.assertEqual(cost.base_delay_cost, 15.0)       # 10 * 1.5
        self.assertEqual(cost.weighted_delay_cost, 40.0)   # 20 * 2.0
        self.assertEqual(cost.max_delay_cost, 2.5)         # 5 * 0.5
        self.assertEqual(cost.conflict_penalty_cost, 1000.0)
        self.assertEqual(cost.total_cost, 1057.5)


class TestOptimizationOutputContracts(unittest.TestCase):
    """Tests for PerformanceMetrics, OptimizationResult, and BaselineScheduler."""

    def test_decision_and_adjustment_dataclasses(self):
        adj = ServiceTimetableAdjustment(
            service_id="SRV_12607_01",
            station_id="PER",
            stop_sequence=2,
            original_arrival=943.0,
            original_departure=945.0,
            adjusted_arrival=948.0,
            adjusted_departure=950.0,
            assigned_platform="PF_PER_01",
        )
        self.assertEqual(adj.delay_minutes, 5.0)
        self.assertEqual(adj.dwell_minutes, 2.0)
        self.assertEqual(adj.adjusted_arrival_str, "15:48")
        d = adj.to_dict()
        self.assertEqual(d["delay_minutes"], 5.0)
        self.assertEqual(d["assigned_platform"], "PF_PER_01")

        prec = PrecedenceDecision(
            resource_id="JCT_BBQ",
            first_service_id="SRV_12607_01",
            second_service_id="SRV_43411_01",
        )
        self.assertEqual(prec.first_service_id, "SRV_12607_01")

        alloc = ResourceAllocationDecision(
            service_id="SRV_12607_01",
            node_or_section_id="MAS",
            allocated_resource_id="PF_MAS_01",
        )
        self.assertEqual(alloc.allocated_resource_id, "PF_MAS_01")

    def test_baseline_scheduler_execution(self):
        net = Network()
        net.load_from_directory(_DATA_DIR)
        net.load_trains(_TRAINS_FILE)
        net.load_services(_SERVICES_FILE)
        net.load_timetable(_TIMETABLE_FILE)

        req = OptimizationRequest.from_network_and_state(
            network=net,
            service_ids=["SRV_12607_01", "SRV_12609_01"],
        )

        scheduler = BaselineScheduler()
        result = scheduler.schedule(req)

        self.assertEqual(result.status, "BASELINE")
        self.assertEqual(result.throughput, 2)
        self.assertEqual(result.total_delay, 0.0)
        self.assertEqual(result.conflict_count, 0)
        self.assertIn("SRV_12607_01", result.adjusted_timetables)
        self.assertIn("SRV_12609_01", result.adjusted_timetables)

        # Check summary output
        summary = result.summary()
        self.assertIn("Throughput:         2 services scheduled", summary)

        # Check serialization
        res_dict = result.to_dict()
        self.assertEqual(res_dict["status"], "BASELINE")
        self.assertIn("metrics", res_dict)


if __name__ == "__main__":
    unittest.main()
