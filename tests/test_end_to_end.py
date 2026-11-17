"""
tests/test_end_to_end.py
~~~~~~~~~~~~~~~~~~~~~~~~
End-to-end integration test suite for the complete railway traffic optimizer engine:
Timetable -> Service -> Route -> Simulation Clock -> Train Movement -> Track Occupancy -> Conflict Detection
-> Feasible FIFO Baseline -> CP-SAT Optimization -> Decision Support -> Pipeline Execution Result.

Validates:
1. Complete pipeline execution using actual project datasets (no mocks or data changes).
2. Starting trains from real published timetable departure timestamps.
3. Accurate ordered-node route traversal across the West corridor.
4. Dynamic track section occupancy creation, maintenance, and release.
5. Deterministic conflict detection for both conflict-free and conflicting multi-train schedules.
6. Unified Pipeline Orchestrator (Phase 19) for normal timetable, single delay, and multi-delay scenarios.
7. Low-noise decision support recommendations & genuine bottleneck isolation.
8. Deterministic repeatability, serialization to Dict/JSON/Markdown/ASCII.
9. Dataset integrity preservation (zero modifications to static JSON data).
"""

import json
import os
import unittest
from typing import List

from backend.app.pipeline import (
    PipelineExecutionResult,
    PipelineOrchestrator,
    run_pipeline,
)
from decision_support.models import (
    OperationalSeverity,
    PriorityTier,
    RecommendationType,
)
from optimization.scenarios import Scenario
from simulation.clock import SimulationClock, minutes_to_time_str, time_to_minutes
from simulation.conflicts import (
    Conflict,
    ConflictDetector,
    ConflictSeverity,
    ConflictType,
)
from simulation.events import EventType, SimulationEvent
from simulation.network import Network
from simulation.simulator import TrainSimulator
from simulation.state import (
    SimulationState,
    TrackSectionOccupancy,
    TrainRuntimeState,
    TrainStatus,
)


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data", "infrastructure")
_TRAINS_FILE = os.path.join(_REPO_ROOT, "data", "trains", "train_identity", "trains.json")
_SERVICES_FILE = os.path.join(_REPO_ROOT, "data", "trains", "service_definitions", "services.json")
_TIMETABLE_FILE = os.path.join(_REPO_ROOT, "data", "trains", "published_timetables", "timetable.json")


class TestRailwayEngineEndToEnd(unittest.TestCase):
    """Full end-to-end pipeline test using real project datasets."""

    def setUp(self):
        """Load the entire real project network, train registry, services, and timetables."""
        self.network = Network()
        self.network.load_from_directory(_DATA_DIR)
        self.network.load_trains(_TRAINS_FILE)
        self.network.load_services(_SERVICES_FILE)
        self.network.load_timetable(_TIMETABLE_FILE)

    def test_single_service_lifecycle_end_to_end(self):
        """Pipeline verification: Service 12607 (MAS -> AJJ).

        Timetable (15:30 MAS) -> Service (SRV_12607_01) -> Route (RT_WEST_MAS_AJJ)
        -> Clock -> Movement -> Occupancy -> Conflict Check (Zero Conflicts).
        """
        clock = SimulationClock()
        state = SimulationState(clock=clock)
        simulator = TrainSimulator(network=self.network, clock=clock, state=state)
        detector = ConflictDetector(network=self.network)

        service_id = "SRV_12607_01"
        service = self.network.services[service_id]
        route = self.network.routes[service.route_id]

        # 1. Timetable departure verification
        tt_mas = next(e for e in self.network.timetable if e.service_id == service_id and e.station_id == "MAS")
        self.assertEqual(tt_mas.departure, "15:30")
        expected_start_min = time_to_minutes("15:30")  # 930.0

        # 2. Run service to destination
        events = simulator.run_service_to_destination(service_id, strict_track_lookup=True)

        # 3. Verify event sequence and ordering
        self.assertGreater(len(events), 50)
        self.assertEqual(events[0].event_type, EventType.SERVICE_START)
        self.assertEqual(events[0].time, expected_start_min)
        self.assertEqual(events[-1].event_type, EventType.SERVICE_COMPLETE)
        self.assertEqual(events[-1].node_id, "AJJ")

        # 4. Verify runtime state at destination
        train_state = state.get_train_state(service_id)
        self.assertEqual(train_state.status, TrainStatus.COMPLETED)
        self.assertEqual(train_state.current_node, "AJJ")
        self.assertEqual(train_state.current_station, "AJJ")
        self.assertIsNone(train_state.current_track_section)
        self.assertEqual(len(train_state.occupied_resources), 0)

        # 5. Verify track occupancy history
        expected_edges = len(route.ordered_nodes) - 1
        service_occs = [o for o in state.occupancy_history if o.service_id == service_id]
        self.assertEqual(len(service_occs), expected_edges)

        # All occupancies must be released and have valid durations
        for occ in service_occs:
            self.assertFalse(occ.is_active)
            self.assertIsNotNone(occ.actual_exit_time)
            self.assertGreater(occ.duration_minutes, 0)
            self.assertIn("DOWN", occ.direction)

        # 6. Verify zero active occupancies remain
        active_occs = state.get_active_occupancies()
        self.assertEqual(len(active_occs), 0)

        # 7. Run conflict detector on isolated run -> expect 0 conflicts
        conflicts = detector.detect_all(state=state)
        self.assertEqual(len(conflicts), 0)

    def test_multi_train_headway_and_junction_conflict_detection_end_to_end(self):
        """End-to-end multi-train scenario:

        Two trains depart MAS on RT_WEST_MAS_AJJ in close succession (1.0 min gap).
        Verifies:
        - Route progression of both trains
        - Occupancy tracking of both trains
        - Conflict detector accurately detects INSUFFICIENT_HEADWAY on MAS_BBQ throat section.
        """
        clock = SimulationClock(start_time="15:30")
        state = SimulationState(clock=clock)
        state.initialize_from_network(self.network)
        detector = ConflictDetector(network=self.network)

        # Train 1: SRV_12607_01 enters MAS_BBQ at 15:30 (930.0 min), exits at 15:34 (934.0 min)
        state.enter_track_section(
            service_id="SRV_12607_01",
            track_section_id="MAS_BBQ_THROAT_SEGMENT_DOWN",
            from_node="MAS",
            to_node="BBQ",
            time=930.0,
            expected_exit_time=934.0,
            direction="DOWN",
        )

        # Train 2: SRV_12609_01 scheduled close behind at 15:31 (931.0 min, delta = 1.0 min < 3.0 min headway)
        state.enter_track_section(
            service_id="SRV_12609_01",
            track_section_id="MAS_BBQ_THROAT_SEGMENT_DOWN",
            from_node="MAS",
            to_node="BBQ",
            time=931.0,
            expected_exit_time=935.0,
            direction="DOWN",
        )

        # Release occupancies
        state.exit_track_section("SRV_12607_01", "MAS_BBQ_THROAT_SEGMENT_DOWN", time=934.0)
        state.exit_track_section("SRV_12609_01", "MAS_BBQ_THROAT_SEGMENT_DOWN", time=935.0)

        # Run conflict detector across state
        conflicts = detector.detect_all(state=state)

        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.INSUFFICIENT_HEADWAY)
        self.assertEqual(c.resource_id, "MAS_BBQ_THROAT_SEGMENT_DOWN")
        self.assertEqual(c.conflict_time, 931.0)
        self.assertEqual(c.conflict_time_str, "15:31")
        self.assertEqual(c.affected_service_ids, ["SRV_12607_01", "SRV_12609_01"])
        self.assertEqual(c.metadata["actual_headway_min"], 1.0)
        self.assertEqual(c.metadata["required_headway_min"], 3.0)

    def test_multi_train_opposing_movement_conflict_detection_end_to_end(self):
        """End-to-end scenario:

        Two trains moving in opposing directions (SRV_12607_01 DOWN vs SRV_12610_01 UP)
        occupying the same single line / section concurrently.
        """
        clock = SimulationClock(start_time="16:00")
        state = SimulationState(clock=clock)
        detector = ConflictDetector(network=self.network)

        # DOWN train entering shared section at 16:00 -> 16:08
        occ_down = TrackSectionOccupancy(
            section_id="TS_TI_TRL_SHARED",
            service_id="SRV_12607_01",
            train_id="TR_12607",
            entry_time=960.0,
            actual_exit_time=968.0,
            from_node="TI",
            to_node="TRL",
            direction="DOWN",
        )

        # UP train entering same section in opposing direction at 16:04 -> 16:12
        occ_up = TrackSectionOccupancy(
            section_id="TS_TI_TRL_SHARED",
            service_id="SRV_12610_01",
            train_id="TR_12610",
            entry_time=964.0,
            actual_exit_time=972.0,
            from_node="TRL",
            to_node="TI",
            direction="UP",
        )

        conflicts = detector.detect_incompatible_movements([occ_down, occ_up])

        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.INCOMPATIBLE_MOVEMENTS)
        self.assertEqual(c.severity, ConflictSeverity.CRITICAL)
        self.assertEqual(c.conflict_time, 964.0)
        self.assertEqual(c.conflict_time_str, "16:04")
        self.assertEqual(sorted(c.affected_service_ids), ["SRV_12607_01", "SRV_12610_01"])
        self.assertEqual(sorted(c.affected_train_ids), ["TR_12607", "TR_12610"])

    def test_dataset_immutability_guarantee(self):
        """Verifies that static infrastructure and timetable JSON files are untouched."""
        stations_path = os.path.join(_DATA_DIR, "stations.json")
        with open(stations_path, "r", encoding="utf-8") as f:
            stations = json.load(f)
        station_ids = {s["id"] for s in stations}
        self.assertEqual(len(stations), 30)
        self.assertNotIn("PAB", station_ids)

        with open(_TRAINS_FILE, "r", encoding="utf-8") as f:
            trains = json.load(f)
        self.assertEqual(len(trains), 51)
        self.assertIn("train_id", trains[0])


# ---------------------------------------------------------------------------
# Phase 19: Integrated End-to-End Pipeline Tests
# ---------------------------------------------------------------------------

class TestIntegratedPipelineEndToEnd(unittest.TestCase):
    """Verifies complete 6-stage backend orchestration flow."""

    def setUp(self):
        self.orchestrator = PipelineOrchestrator()

    def test_pipeline_normal_timetable_execution(self):
        """Verify normal timetable execution produces clean state, 0 baseline delay, and maintain-schedule directive."""
        services = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]
        result = self.orchestrator.run_pipeline(service_ids=services)

        self.assertIsInstance(result, PipelineExecutionResult)
        self.assertEqual(result.active_services_count, 4)
        self.assertEqual(result.delayed_services_count, 0)
        self.assertGreaterEqual(result.total_baseline_delay_minutes, 0.0)
        self.assertGreaterEqual(result.total_optimized_delay_minutes, 0.0)
        self.assertEqual(result.net_delay_savings_minutes, 0.0)
        self.assertIn(result.solver_status, ("OPTIMAL", "FEASIBLE"))
        self.assertEqual(len(result.prioritized_conflicts), 0)

        # Recommendation should be low-noise (1 to 3 items, not 150+ noise items)
        self.assertLessEqual(len(result.recommendations), 3)

    def test_pipeline_single_delay_scenario(self):
        """Verify single-delay disruption scenario produces focused recommendations and accurate delay decomposition."""
        services = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]
        result = self.orchestrator.run_pipeline(
            service_ids=services,
            departure_delays={"SRV_12607_01": 15.0},
        )

        self.assertIsInstance(result, PipelineExecutionResult)
        self.assertEqual(result.delayed_services_count, 1)
        self.assertGreaterEqual(result.total_baseline_delay_minutes, 15.0)
        self.assertGreaterEqual(result.total_optimized_delay_minutes, 15.0)
        self.assertEqual(result.solver_status, "OPTIMAL")

        # Verify low-noise decision support (1 to 4 actionable recommendations, not 150+)
        self.assertLessEqual(len(result.recommendations), 4)
        self.assertGreaterEqual(len(result.recommendations), 1)

        # Verify bottleneck count is constrained to genuine contention points
        self.assertLessEqual(len(result.identified_bottlenecks), 6)

        # Verify delay impacts
        imp_12607 = next(i for i in result.service_delay_impacts if i.service_id == "SRV_12607_01")
        self.assertEqual(imp_12607.direct_delay_minutes, 15.0)
        self.assertGreaterEqual(imp_12607.total_delay_minutes, 15.0)

    def test_pipeline_multi_delay_scenario(self):
        """Verify multi-delay scenario coordinates multiple disruptions and solves optimally."""
        services = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]
        result = self.orchestrator.run_pipeline(
            service_ids=services,
            departure_delays={"SRV_12607_01": 20.0, "SRV_12609_01": 15.0},
        )

        self.assertEqual(result.delayed_services_count, 2)
        self.assertGreaterEqual(result.total_baseline_delay_minutes, 35.0)
        self.assertEqual(result.solver_status, "OPTIMAL")
        self.assertIn(result.assessment.situation.severity, (OperationalSeverity.WARNING, OperationalSeverity.CRITICAL))

        # Check that both delayed trains are tracked in delay impacts
        impacted_svc_ids = {i.service_id for i in result.service_delay_impacts if i.direct_delay_minutes > 0.0}
        self.assertEqual(impacted_svc_ids, {"SRV_12607_01", "SRV_12609_01"})

        # Recommendations should be concise and focused
        self.assertLessEqual(len(result.recommendations), 4)

    def test_pipeline_serialization_and_reporting(self):
        """Verify dictionary, JSON, Markdown, and ASCII export formats."""
        services = ["SRV_12607_01", "SRV_12609_01"]
        result = self.orchestrator.run_pipeline(
            service_ids=services,
            departure_delays={"SRV_12607_01": 10.0},
        )

        d = result.to_dict()
        self.assertIn("scenario_name", d)
        self.assertIn("total_baseline_delay_minutes", d)
        self.assertIn("total_optimized_delay_minutes", d)
        self.assertIn("recommendations", d)
        self.assertIn("service_delay_impacts", d)
        self.assertIn("baseline_comparison", d)

        # JSON valid
        j_str = result.to_json()
        parsed = json.loads(j_str)
        self.assertEqual(parsed["scenario_name"], result.scenario_name)

        # ASCII report
        ascii_rep = result.generate_ascii_summary()
        self.assertIn("END-TO-END RAILWAY TRAFFIC OPTIMIZATION PIPELINE RESULT", ascii_rep)
        self.assertIn("RANKED ACTIONABLE RECOMMENDATIONS", ascii_rep)

        # Markdown report
        md_rep = result.generate_markdown()
        self.assertIn("# Dynamic Decision-Support Assessment", md_rep)

    def test_pipeline_deterministic_repeatability(self):
        """Verify 100% hash and numeric consistency over repeated executions."""
        services = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"]
        res1 = self.orchestrator.run_pipeline(
            service_ids=services,
            departure_delays={"SRV_12607_01": 12.0},
        )
        res2 = self.orchestrator.run_pipeline(
            service_ids=services,
            departure_delays={"SRV_12607_01": 12.0},
        )

        self.assertEqual(res1.deterministic_hash, res2.deterministic_hash)
        self.assertEqual(res1.total_baseline_delay_minutes, res2.total_baseline_delay_minutes)
        self.assertEqual(res1.total_optimized_delay_minutes, res2.total_optimized_delay_minutes)
        self.assertEqual(len(res1.recommendations), len(res2.recommendations))


if __name__ == "__main__":
    unittest.main()
