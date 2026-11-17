"""
tests/test_conflicts.py
~~~~~~~~~~~~~~~~~~~~~~~
Unit and integration tests for Batch 6 railway conflict detection:
1. Same-track-section conflicts (capacity breach)
2. Insufficient headway (separation < minimum headway)
3. Shared junction/resource conflicts (multiple trains competing at junction)
4. Incompatible movements using the same resource (opposing UP/DOWN movements)
5. Conflict model validation (attributes, severity, formatting, serialization)
6. Comprehensive multi-conflict detection.
"""

import os
import unittest

from simulation.clock import SimulationClock, time_to_minutes
from simulation.conflicts import (
    Conflict,
    ConflictDetector,
    ConflictSeverity,
    ConflictType,
)
from simulation.network import Network, Route, Service, TrackSection, Junction
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


class TestConflictModel(unittest.TestCase):
    """Unit tests for the Conflict dataclass attributes and serialization."""

    def test_conflict_model_attributes_and_types(self):
        conf = Conflict(
            conflict_id="CONF_0001",
            conflict_type=ConflictType.SAME_TRACK_SECTION,
            affected_service_ids=["SRV_12607_01", "SRV_12608_01"],
            affected_train_ids=["TR_12607", "TR_12608"],
            resource_id="TS_MAS_BBQ_DOWN",
            conflict_time="06:05",
            severity=ConflictSeverity.CRITICAL,
            description="Concurrent overcapacity on TS_MAS_BBQ_DOWN",
            metadata={"capacity": 1, "occupants": 2},
        )

        self.assertEqual(conf.conflict_id, "CONF_0001")
        self.assertEqual(conf.conflict_type, ConflictType.SAME_TRACK_SECTION)
        self.assertEqual(conf.affected_service_ids, ["SRV_12607_01", "SRV_12608_01"])
        self.assertEqual(conf.affected_services, ["SRV_12607_01", "SRV_12608_01"])
        self.assertEqual(conf.affected_train_ids, ["TR_12607", "TR_12608"])
        self.assertEqual(conf.affected_trains, ["TR_12607", "TR_12608"])
        self.assertEqual(conf.resource_id, "TS_MAS_BBQ_DOWN")
        self.assertEqual(conf.conflict_time, 365.0)
        self.assertEqual(conf.conflict_time_str, "06:05")
        self.assertEqual(conf.severity, ConflictSeverity.CRITICAL)
        self.assertIn("TS_MAS_BBQ_DOWN", conf.description)
        self.assertEqual(conf.metadata["capacity"], 1)

    def test_conflict_to_dict_serialization(self):
        conf = Conflict(
            conflict_id="CONF_0002",
            conflict_type="INSUFFICIENT_HEADWAY",
            affected_service_ids=["SRV_A", "SRV_B"],
            affected_train_ids=["TR_A", "TR_B"],
            resource_id="SEC_01",
            conflict_time=370.0,
            severity="MAJOR",
            description="Headway violation",
        )
        d = conf.to_dict()
        self.assertEqual(d["conflict_id"], "CONF_0002")
        self.assertEqual(d["conflict_type"], "INSUFFICIENT_HEADWAY")
        self.assertEqual(d["severity"], "MAJOR")
        self.assertEqual(d["conflict_time"], 370.0)
        self.assertEqual(d["conflict_time_str"], "06:10")
        self.assertIsInstance(d, dict)


class TestSameTrackSectionConflicts(unittest.TestCase):
    """Tests for conflict detection when track section capacity is exceeded."""

    def setUp(self):
        self.detector = ConflictDetector()

    def test_single_capacity_section_concurrent_occupancy(self):
        """Two trains concurrently on a section of capacity 1 triggers SAME_TRACK_SECTION."""
        occ1 = TrackSectionOccupancy(
            section_id="SEC_MAS_BBQ",
            service_id="SRV_1",
            train_id="TR_1",
            entry_time=360.0,   # 06:00
            actual_exit_time=365.0, # 06:05
        )
        occ2 = TrackSectionOccupancy(
            section_id="SEC_MAS_BBQ",
            service_id="SRV_2",
            train_id="TR_2",
            entry_time=362.0,   # 06:02 (overlaps 06:02 - 06:05)
            actual_exit_time=367.0, # 06:07
        )

        conflicts = self.detector.detect_same_section_conflicts(
            occupancies=[occ1, occ2],
            capacity_map={"SEC_MAS_BBQ": 1},
        )

        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.SAME_TRACK_SECTION)
        self.assertEqual(c.resource_id, "SEC_MAS_BBQ")
        self.assertEqual(sorted(c.affected_service_ids), ["SRV_1", "SRV_2"])
        self.assertEqual(c.conflict_time, 362.0)
        self.assertEqual(c.severity, ConflictSeverity.CRITICAL)

    def test_multi_capacity_section_allows_up_to_capacity(self):
        """Two trains on a capacity-2 section is valid, but a third triggers overcapacity."""
        occ1 = TrackSectionOccupancy(
            section_id="SEC_THROAT",
            service_id="SRV_1",
            train_id="TR_1",
            entry_time=360.0,
            actual_exit_time=370.0,
        )
        occ2 = TrackSectionOccupancy(
            section_id="SEC_THROAT",
            service_id="SRV_2",
            train_id="TR_2",
            entry_time=362.0,
            actual_exit_time=372.0,
        )

        # 2 trains on capacity 2 -> 0 conflicts
        conflicts = self.detector.detect_same_section_conflicts(
            occupancies=[occ1, occ2],
            capacity_map={"SEC_THROAT": 2},
        )
        self.assertEqual(len(conflicts), 0)

        # Add 3rd train overlapping -> 1 conflict
        occ3 = TrackSectionOccupancy(
            section_id="SEC_THROAT",
            service_id="SRV_3",
            train_id="TR_3",
            entry_time=364.0,
            actual_exit_time=374.0,
        )
        conflicts = self.detector.detect_same_section_conflicts(
            occupancies=[occ1, occ2, occ3],
            capacity_map={"SEC_THROAT": 2},
        )
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.SAME_TRACK_SECTION)
        self.assertEqual(len(conflicts[0].affected_service_ids), 3)

    def test_non_overlapping_occupancies_cause_no_conflict(self):
        """Sequential occupancies on the same section do not trigger capacity conflict."""
        occ1 = TrackSectionOccupancy(
            section_id="SEC_MAS_BBQ",
            service_id="SRV_1",
            train_id="TR_1",
            entry_time=360.0,
            actual_exit_time=364.0,
        )
        occ2 = TrackSectionOccupancy(
            section_id="SEC_MAS_BBQ",
            service_id="SRV_2",
            train_id="TR_2",
            entry_time=365.0,  # Enters after occ1 left
            actual_exit_time=370.0,
        )
        conflicts = self.detector.detect_same_section_conflicts(
            occupancies=[occ1, occ2],
            capacity_map={"SEC_MAS_BBQ": 1},
        )
        self.assertEqual(len(conflicts), 0)


class TestInsufficientHeadwayConflicts(unittest.TestCase):
    """Tests for conflict detection when trains follow too closely."""

    def setUp(self):
        self.detector = ConflictDetector()

    def test_insufficient_headway_detected(self):
        """Train 2 entering 1.5 min after Train 1 violates 3.0 min minimum headway."""
        occ1 = TrackSectionOccupancy(
            section_id="SEC_PER_VLK",
            service_id="SRV_12607",
            train_id="TR_12607",
            entry_time=370.0,   # 06:10
            actual_exit_time=374.0,
        )
        occ2 = TrackSectionOccupancy(
            section_id="SEC_PER_VLK",
            service_id="SRV_EMU_01",
            train_id="TR_EMU_01",
            entry_time=371.5,   # 06:11:30 (delta = 1.5 min < 3.0 min headway)
            actual_exit_time=375.5,
        )

        conflicts = self.detector.detect_headway_conflicts(
            occupancies=[occ1, occ2],
            min_headway_map={"SEC_PER_VLK": 3.0},
        )

        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.INSUFFICIENT_HEADWAY)
        self.assertEqual(c.resource_id, "SEC_PER_VLK")
        self.assertEqual(c.conflict_time, 371.5)
        self.assertEqual(c.affected_service_ids, ["SRV_12607", "SRV_EMU_01"])
        self.assertEqual(c.metadata["actual_headway_min"], 1.5)
        self.assertEqual(c.metadata["required_headway_min"], 3.0)

    def test_sufficient_headway_causes_no_conflict(self):
        """Train 2 entering 5.0 min after Train 1 satisfies 3.0 min minimum headway."""
        occ1 = TrackSectionOccupancy(
            section_id="SEC_PER_VLK",
            service_id="SRV_12607",
            train_id="TR_12607",
            entry_time=370.0,
            actual_exit_time=374.0,
        )
        occ2 = TrackSectionOccupancy(
            section_id="SEC_PER_VLK",
            service_id="SRV_EMU_01",
            train_id="TR_EMU_01",
            entry_time=375.0,  # delta = 5.0 min >= 3.0 min
            actual_exit_time=379.0,
        )

        conflicts = self.detector.detect_headway_conflicts(
            occupancies=[occ1, occ2],
            min_headway_map={"SEC_PER_VLK": 3.0},
        )
        self.assertEqual(len(conflicts), 0)


class TestSharedJunctionConflicts(unittest.TestCase):
    """Tests for conflict detection at junctions and shared throats."""

    def setUp(self):
        self.detector = ConflictDetector()

    def test_shared_junction_live_state_conflict(self):
        """Two trains simultaneously at junction BBQ in live SimulationState triggers SHARED_JUNCTION."""
        clock = SimulationClock(start_time="06:00")
        state = SimulationState(clock=clock)

        # Mock train runtime states
        state.train_states["SRV_EXP_01"] = TrainRuntimeState(
            service_id="SRV_EXP_01",
            train_id="TR_EXP_01",
            route_id="RT_WEST_MAS_AJJ",
            status=TrainStatus.AT_STATION,
            current_station="BBQ",
            current_node="BBQ",
        )
        state.train_states["SRV_SUB_01"] = TrainRuntimeState(
            service_id="SRV_SUB_01",
            train_id="TR_SUB_01",
            route_id="RT_NORTH_MAS_SPE",
            status=TrainStatus.AT_STATION,
            current_station="BBQ",
            current_node="BBQ",
        )
        state.station_occupancy["BBQ"].add("SRV_EXP_01")
        state.station_occupancy["BBQ"].add("SRV_SUB_01")

        conflicts = self.detector.detect_junction_conflicts(state=state, default_junction_capacity=1)
        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.SHARED_JUNCTION)
        self.assertEqual(sorted(c.affected_service_ids), ["SRV_EXP_01", "SRV_SUB_01"])
        self.assertIn("BBQ", c.resource_id)

    def test_shared_junction_temporal_interval_conflict(self):
        """Overlapping arrival/departure windows at a junction node detect conflict."""
        node_records = [
            {
                "node_id": "JCT_BBQ",
                "service_id": "SRV_W_01",
                "train_id": "TR_W_01",
                "arrival_time": 360.0,   # 06:00
                "departure_time": 364.0, # 06:04
            },
            {
                "node_id": "JCT_BBQ",
                "service_id": "SRV_N_01",
                "train_id": "TR_N_01",
                "arrival_time": 362.0,   # 06:02 (overlaps 06:02 - 06:04)
                "departure_time": 366.0, # 06:06
            },
        ]

        conflicts = self.detector.detect_junction_conflicts(
            node_occupancies=node_records,
            junction_capacity_map={"JCT_BBQ": 1},
        )
        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.SHARED_JUNCTION)
        self.assertEqual(c.resource_id, "JCT_BBQ")
        self.assertEqual(c.conflict_time, 362.0)
        self.assertEqual(sorted(c.affected_service_ids), ["SRV_N_01", "SRV_W_01"])


class TestIncompatibleMovementConflicts(unittest.TestCase):
    """Tests for conflict detection when opposing movements use the same section."""

    def setUp(self):
        self.detector = ConflictDetector()

    def test_opposing_up_and_down_movements_on_same_section(self):
        """UP train and DOWN train occupying the same single/bidirectional section concurrently is CRITICAL."""
        occ_down = TrackSectionOccupancy(
            section_id="SEC_SINGLE_LINE",
            service_id="SRV_DOWN_01",
            train_id="TR_DOWN_01",
            entry_time=360.0,   # 06:00
            actual_exit_time=370.0, # 06:10
            from_node="STN_A",
            to_node="STN_B",
            direction="DOWN",
        )
        occ_up = TrackSectionOccupancy(
            section_id="SEC_SINGLE_LINE",
            service_id="SRV_UP_01",
            train_id="TR_UP_01",
            entry_time=365.0,   # 06:05 (overlaps 06:05 - 06:10)
            actual_exit_time=375.0, # 06:15
            from_node="STN_B",
            to_node="STN_A",
            direction="UP",
        )

        conflicts = self.detector.detect_incompatible_movements(
            occupancies=[occ_down, occ_up]
        )

        self.assertEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.INCOMPATIBLE_MOVEMENTS)
        self.assertEqual(c.severity, ConflictSeverity.CRITICAL)
        self.assertEqual(c.resource_id, "SEC_SINGLE_LINE")
        self.assertEqual(c.conflict_time, 365.0)
        self.assertIn("opposing", c.description.lower())
        self.assertEqual(sorted(c.affected_service_ids), ["SRV_DOWN_01", "SRV_UP_01"])

    def test_same_direction_trains_do_not_trigger_incompatible_movement(self):
        """Two DOWN trains on the same section do not trigger INCOMPATIBLE_MOVEMENTS (handled by headway/capacity)."""
        occ1 = TrackSectionOccupancy(
            section_id="SEC_DOUBLE_DOWN",
            service_id="SRV_DOWN_01",
            train_id="TR_DOWN_01",
            entry_time=360.0,
            actual_exit_time=370.0,
            direction="DOWN",
        )
        occ2 = TrackSectionOccupancy(
            section_id="SEC_DOUBLE_DOWN",
            service_id="SRV_DOWN_02",
            train_id="TR_DOWN_02",
            entry_time=365.0,
            actual_exit_time=375.0,
            direction="DOWN",
        )

        conflicts = self.detector.detect_incompatible_movements(
            occupancies=[occ1, occ2]
        )
        self.assertEqual(len(conflicts), 0)


class TestComprehensiveConflictDetection(unittest.TestCase):
    """Integration test verifying full conflict detection across realistic network datasets."""

    def test_full_dataset_integration_and_detect_all(self):
        net = Network()
        net.load_from_directory(_DATA_DIR)
        net.load_trains(_TRAINS_FILE)
        net.load_services(_SERVICES_FILE)
        net.load_timetable(_TIMETABLE_FILE)

        detector = ConflictDetector(network=net)

        # Scenario:
        # 1. Headway conflict between 12607 and a hypothetical following EMU on MAS_BBQ
        occ1 = TrackSectionOccupancy(
            section_id="MAS_BBQ_THROAT_SEGMENT_DOWN",
            service_id="SRV_12607_01",
            train_id="TR_12607",
            entry_time=360.0,
            actual_exit_time=364.0,
            direction="DOWN",
        )
        occ2 = TrackSectionOccupancy(
            section_id="MAS_BBQ_THROAT_SEGMENT_DOWN",
            service_id="SRV_EMU_FOLLOW",
            train_id="TR_EMU",
            entry_time=361.0,  # 1.0 min headway < minimum 3.0 min
            actual_exit_time=365.0,
            direction="DOWN",
        )

        # 2. Incompatible opposing movement on a shared track
        occ3 = TrackSectionOccupancy(
            section_id="SEC_SHARED_TEST",
            service_id="SRV_12607_01",
            train_id="TR_12607",
            entry_time=400.0,
            actual_exit_time=408.0,
            from_node="TI",
            to_node="TRL",
            direction="DOWN",
        )
        occ4 = TrackSectionOccupancy(
            section_id="SEC_SHARED_TEST",
            service_id="SRV_UP_TEST",
            train_id="TR_UP",
            entry_time=404.0,
            actual_exit_time=412.0,
            from_node="TRL",
            to_node="TI",
            direction="UP",
        )

        all_conflicts = detector.detect_all(occupancies=[occ1, occ2, occ3, occ4])

        # Expect headway conflict on MAS_BBQ and incompatible move conflict on SEC_SHARED_TEST
        types_found = {c.conflict_type for c in all_conflicts}
        self.assertIn(ConflictType.INSUFFICIENT_HEADWAY, types_found)
        self.assertIn(ConflictType.INCOMPATIBLE_MOVEMENTS, types_found)

        # Verify all conflict records conform to required schema
        for c in all_conflicts:
            self.assertTrue(c.conflict_id.startswith("CONF_"))
            self.assertIsInstance(c.conflict_type, ConflictType)
            self.assertIsInstance(c.affected_service_ids, list)
            self.assertGreater(len(c.affected_service_ids), 0)
            self.assertIsInstance(c.affected_train_ids, list)
            self.assertIsInstance(c.resource_id, str)
            self.assertIsInstance(c.conflict_time, float)
            self.assertIsInstance(c.severity, ConflictSeverity)
            self.assertIsInstance(c.description, str)
            self.assertGreater(len(c.description), 5)


if __name__ == "__main__":
    unittest.main()
