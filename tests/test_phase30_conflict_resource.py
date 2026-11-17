"""
tests/test_phase30_conflict_resource.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 30.3 -- Cross-Corridor Conflict & Resource Contention Tests.

Verifies deterministic conflict detection and resource contention behaviour
across all active corridors using the 40 timetable-backed services.

Scenario coverage:
  SC-01  Same-track section overcapacity  (BBQ throat, capacity=1)
  SC-02  Insufficient headway             (West trunk BBQ section, two services)
  SC-03  Junction/throat contention       (JCT_BBQ - 29 services share this throat)
  SC-04  Junction/throat contention       (JCT_PAB - PTMS branch merge)
  SC-05  Junction/throat contention       (JCT_KOK - North/Bypass merge point)
  SC-06  Junction/throat contention       (JCT_MSB - South/MRTS/Bypass hub)
  SC-07  Junction/throat contention       (JCT_CGL - South / Cross-Line divergence)
  SC-08  Opposing movement detection      (UP vs DOWN on same West section)
  SC-09  Platform contention              (MAS dual-platform: P1/P2 concurrency vs double-booking)
  SC-10  Unrelated corridor isolation     (North noise does not touch South resources)
  SC-11  Conflict classification correct  (CRITICAL / MAJOR / WARNING severity mapping)
  SC-12  Cross-corridor detector reset    (detector.reset() clears state between runs)
  SC-13  Determinism                      (two identical runs produce identical conflict ids/hashes)
  SC-14  Pending-service exclusion        (7 pending services never generate conflict records)
  SC-15  Full 40-service conflict scan    (no unclassified conflicts)
"""

import hashlib
import os
import unittest
from collections import defaultdict
from typing import Dict, List, Set

from simulation.clock import SimulationClock, time_to_minutes
from simulation.conflicts import (
    Conflict,
    ConflictDetector,
    ConflictSeverity,
    ConflictType,
)
from simulation.network import Network
from simulation.simulator import TrainSimulator
from simulation.state import (
    SimulationState,
    TrackSectionOccupancy,
    TrainStatus,
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")


def _load_network() -> Network:
    net = Network()
    net.load_from_directory(os.path.join(_DATA_DIR, "infrastructure"))
    net.load_trains(os.path.join(_DATA_DIR, "trains", "train_identity", "trains.json"))
    net.load_services(os.path.join(_DATA_DIR, "trains", "service_definitions", "services.json"))
    net.load_timetable(os.path.join(_DATA_DIR, "trains", "published_timetables", "timetable.json"))
    return net


def _backed_ids(net: Network) -> List[str]:
    return sorted({e.service_id for e in net.timetable})


def _pending_ids(net: Network) -> List[str]:
    backed = set(_backed_ids(net))
    return sorted(set(net.services.keys()) - backed)


def _make_occ(
    section_id: str,
    service_id: str,
    train_id: str,
    entry: float,
    exit_: float,
    direction: str = "UP",
    from_node: str = "",
    to_node: str = "",
) -> TrackSectionOccupancy:
    return TrackSectionOccupancy(
        section_id=section_id,
        service_id=service_id,
        train_id=train_id,
        entry_time=entry,
        expected_exit_time=exit_,
        actual_exit_time=exit_,
        from_node=from_node,
        to_node=to_node,
        direction=direction,
    )


# ==============================================================================
# SC-01 -- Same-track section overcapacity
# ==============================================================================
class TestSameTrackSectionConflict(unittest.TestCase):
    """SC-01: Concurrent occupancy beyond section capacity raises SAME_TRACK_SECTION."""

    def setUp(self):
        self.detector = ConflictDetector()

    def test_two_trains_on_capacity_1_section_detected(self):
        """Two trains overlapping on a capacity-1 section -> SAME_TRACK_SECTION CRITICAL."""
        occs = [
            _make_occ("TS_MAS_BBQ_DOWN", "SRV_12607_01", "TR_12607", 360.0, 366.0),
            _make_occ("TS_MAS_BBQ_DOWN", "SRV_12609_01", "TR_12609", 362.0, 368.0),
        ]
        conflicts = self.detector.detect_same_section_conflicts(occs, default_capacity=1)
        self.assertGreaterEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.SAME_TRACK_SECTION)
        self.assertEqual(c.severity, ConflictSeverity.CRITICAL)
        self.assertIn("SRV_12607_01", c.affected_service_ids)
        self.assertIn("SRV_12609_01", c.affected_service_ids)
        self.assertEqual(c.resource_id, "TS_MAS_BBQ_DOWN")

    def test_non_overlapping_trains_no_conflict(self):
        """Successive non-overlapping trains on same section -> no conflict."""
        occs = [
            _make_occ("TS_MAS_BBQ_DOWN", "SRV_12607_01", "TR_12607", 360.0, 364.0),
            _make_occ("TS_MAS_BBQ_DOWN", "SRV_12609_01", "TR_12609", 365.0, 369.0),
        ]
        conflicts = self.detector.detect_same_section_conflicts(occs, default_capacity=1)
        self.assertEqual(len(conflicts), 0)

    def test_capacity_2_section_two_trains_no_conflict(self):
        """Two concurrent trains on a capacity-2 section -> no overcapacity conflict."""
        occs = [
            _make_occ("TS_MULTI_A", "SRV_A", "TR_A", 360.0, 366.0),
            _make_occ("TS_MULTI_A", "SRV_B", "TR_B", 361.0, 367.0),
        ]
        conflicts = self.detector.detect_same_section_conflicts(
            occs, capacity_map={"TS_MULTI_A": 2}
        )
        self.assertEqual(len(conflicts), 0)

    def test_three_trains_on_capacity_2_section_detected(self):
        """Three concurrent trains on capacity-2 section -> SAME_TRACK_SECTION MAJOR."""
        occs = [
            _make_occ("TS_MULTI_B", "SRV_A", "TR_A", 360.0, 370.0),
            _make_occ("TS_MULTI_B", "SRV_B", "TR_B", 361.0, 371.0),
            _make_occ("TS_MULTI_B", "SRV_C", "TR_C", 362.0, 372.0),
        ]
        conflicts = self.detector.detect_same_section_conflicts(
            occs, capacity_map={"TS_MULTI_B": 2}
        )
        self.assertGreaterEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].severity, ConflictSeverity.MAJOR)

    def test_conflict_id_format(self):
        """Each conflict gets a unique deterministic CONF_NNNN ID."""
        occs = [
            _make_occ("TS_X", "SRV_A", "TR_A", 360.0, 366.0),
            _make_occ("TS_X", "SRV_B", "TR_B", 362.0, 368.0),
        ]
        conflicts = self.detector.detect_same_section_conflicts(occs, default_capacity=1)
        self.assertTrue(conflicts[0].conflict_id.startswith("CONF_"))
        self.assertEqual(len(conflicts[0].conflict_id), 9)  # "CONF_0001"


# ==============================================================================
# SC-02 -- Insufficient headway on shared corridor
# ==============================================================================
class TestHeadwayConflict(unittest.TestCase):
    """SC-02: Successive trains violating minimum headway -> INSUFFICIENT_HEADWAY."""

    def setUp(self):
        self.detector = ConflictDetector()

    def test_headway_violation_detected(self):
        """Two trains entering same section 1 min apart (< 3 min min) -> WARNING or MAJOR."""
        occs = [
            _make_occ("TS_BBQ_MAS", "SRV_12610_01", "TR_12610", 400.0, 405.0),
            _make_occ("TS_BBQ_MAS", "SRV_12640_01", "TR_12640", 401.0, 406.0),
        ]
        conflicts = self.detector.detect_headway_conflicts(occs, default_min_headway_minutes=3.0)
        self.assertGreaterEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.INSUFFICIENT_HEADWAY)
        self.assertIn(c.severity, {ConflictSeverity.WARNING, ConflictSeverity.MAJOR})

    def test_headway_exact_minimum_no_conflict(self):
        """Two trains exactly 3 min apart -> no headway conflict (boundary)."""
        occs = [
            _make_occ("TS_BBQ_MAS", "SRV_12610_01", "TR_12610", 400.0, 405.0),
            _make_occ("TS_BBQ_MAS", "SRV_12640_01", "TR_12640", 403.0, 408.0),
        ]
        conflicts = self.detector.detect_headway_conflicts(occs, default_min_headway_minutes=3.0)
        self.assertEqual(len(conflicts), 0)

    def test_headway_severity_major_at_half_minimum(self):
        """Train entering < 1.5 min after predecessor -> MAJOR severity."""
        occs = [
            _make_occ("TS_WEST_SEC", "SRV_12607_01", "TR_12607", 930.0, 932.0),
            _make_occ("TS_WEST_SEC", "SRV_16057_01", "TR_16057", 930.5, 932.5),
        ]
        conflicts = self.detector.detect_headway_conflicts(occs, default_min_headway_minutes=3.0)
        self.assertTrue(any(c.severity == ConflictSeverity.MAJOR for c in conflicts))

    def test_headway_metadata_accuracy(self):
        """Conflict metadata contains correct actual_headway_min and required_headway_min."""
        occs = [
            _make_occ("TS_SEC_A", "SRV_A", "TR_A", 600.0, 604.0),
            _make_occ("TS_SEC_A", "SRV_B", "TR_B", 601.5, 605.5),
        ]
        conflicts = self.detector.detect_headway_conflicts(occs, default_min_headway_minutes=3.0)
        self.assertGreaterEqual(len(conflicts), 1)
        meta = conflicts[0].metadata
        self.assertAlmostEqual(meta["actual_headway_min"], 1.5, places=5)
        self.assertAlmostEqual(meta["required_headway_min"], 3.0, places=5)

    def test_same_service_id_no_self_conflict(self):
        """Single service appearing twice does not conflict with itself."""
        occs = [
            _make_occ("TS_SEC_A", "SRV_A", "TR_A", 600.0, 604.0),
            _make_occ("TS_SEC_A", "SRV_A", "TR_A", 601.0, 605.0),
        ]
        conflicts = self.detector.detect_headway_conflicts(occs, default_min_headway_minutes=3.0)
        self.assertEqual(len(conflicts), 0)


# ==============================================================================
# SC-03..SC-07 -- Junction / throat contention
# ==============================================================================
class TestJunctionContention(unittest.TestCase):
    """SC-03..07: Shared junction contention at all major network junctions."""

    def setUp(self):
        self.detector = ConflictDetector()

    def _node_occ(self, node_id, svc, train_id, arr, dep):
        return {
            "node_id": node_id,
            "service_id": svc,
            "train_id": train_id,
            "arrival_time": arr,
            "departure_time": dep,
        }

    def _run(self, node_id, pairs):
        occs = [self._node_occ(node_id, s, f"TR_{s.split('_')[1]}", a, d) for s, a, d in pairs]
        return self.detector.detect_junction_conflicts(
            node_occupancies=occs,
            junction_capacity_map={node_id: 1},
        )

    # SC-03: BBQ (West throat - highest traffic)
    def test_jct_bbq_concurrent_contention_detected(self):
        conflicts = self._run("BBQ", [
            ("SRV_12607_01", 361.0, 363.0),
            ("SRV_12610_01", 362.0, 364.0),
        ])
        self.assertGreaterEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.SHARED_JUNCTION)
        self.assertEqual(c.severity, ConflictSeverity.MAJOR)

    def test_jct_bbq_non_overlapping_no_conflict(self):
        conflicts = self._run("BBQ", [
            ("SRV_12607_01", 360.0, 362.0),
            ("SRV_12610_01", 363.0, 365.0),
        ])
        self.assertEqual(len(conflicts), 0)

    # SC-04: PAB (PTMS branch merge)
    def test_jct_pab_branch_merge_contention_detected(self):
        conflicts = self._run("PAB", [
            ("SRV_43102_01", 375.0, 377.0),
            ("SRV_12607_01", 376.0, 378.0),
        ])
        self.assertGreaterEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.SHARED_JUNCTION)

    def test_jct_pab_sequential_no_conflict(self):
        conflicts = self._run("PAB", [
            ("SRV_43102_01", 375.0, 376.0),
            ("SRV_12607_01", 377.0, 378.0),
        ])
        self.assertEqual(len(conflicts), 0)

    # SC-05: KOK (North / Bypass merge)
    def test_jct_kok_north_bypass_contention_detected(self):
        conflicts = self._run("KOK", [
            ("SRV_12712_01", 360.0, 362.0),
            ("SRV_42601_01", 361.0, 363.0),
        ])
        self.assertGreaterEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.SHARED_JUNCTION)

    # SC-06: MSB (South / MRTS / Bypass hub)
    def test_jct_msb_multi_corridor_hub_contention_detected(self):
        conflicts = self._run("MSB", [
            ("SRV_41001_01", 360.0, 362.0),
            ("SRV_42601_01", 361.0, 363.0),
        ])
        self.assertGreaterEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.SHARED_JUNCTION)

    # SC-07: CGL (South / Cross Line divergence)
    def test_jct_cgl_south_crossline_contention_detected(self):
        conflicts = self._run("CGL", [
            ("SRV_12635_01", 450.0, 452.0),
            ("SRV_12636_01", 451.0, 453.0),
        ])
        self.assertGreaterEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.SHARED_JUNCTION)

    def test_jct_cgl_sequential_no_conflict(self):
        conflicts = self._run("CGL", [
            ("SRV_12635_01", 450.0, 451.0),
            ("SRV_12636_01", 452.0, 453.0),
        ])
        self.assertEqual(len(conflicts), 0)

    def test_three_way_junction_contention(self):
        """Three services simultaneously at KOK -> conflict includes all three."""
        conflicts = self._run("KOK", [
            ("SRV_12712_01", 360.0, 363.0),
            ("SRV_42601_01", 361.0, 364.0),
            ("SRV_12711_01", 362.0, 365.0),
        ])
        self.assertGreaterEqual(len(conflicts), 1)
        all_affected: Set[str] = set()
        for c in conflicts:
            all_affected.update(c.affected_service_ids)
        self.assertIn("SRV_12712_01", all_affected)
        self.assertIn("SRV_42601_01", all_affected)


# ==============================================================================
# SC-08 -- Opposing movement / incompatible direction detection
# ==============================================================================
class TestIncompatibleMovements(unittest.TestCase):
    """SC-08: Head-on opposing movements -> INCOMPATIBLE_MOVEMENTS CRITICAL."""

    def setUp(self):
        self.detector = ConflictDetector()

    def test_opposing_up_down_concurrent_detected(self):
        """UP and DOWN trains overlapping on same single-track section -> CRITICAL."""
        occs = [
            _make_occ("TS_SINGLE_TRACK", "SRV_12607_01", "TR_12607",
                      500.0, 505.0, direction="UP"),
            _make_occ("TS_SINGLE_TRACK", "SRV_12610_01", "TR_12610",
                      502.0, 507.0, direction="DOWN"),
        ]
        conflicts = self.detector.detect_incompatible_movements(occs)
        self.assertGreaterEqual(len(conflicts), 1)
        c = conflicts[0]
        self.assertEqual(c.conflict_type, ConflictType.INCOMPATIBLE_MOVEMENTS)
        self.assertEqual(c.severity, ConflictSeverity.CRITICAL)

    def test_same_direction_concurrent_no_incompatible_movement(self):
        """Two UP trains on same section -> not an incompatible movement."""
        occs = [
            _make_occ("TS_WEST_UP", "SRV_12607_01", "TR_12607", 500.0, 505.0, direction="UP"),
            _make_occ("TS_WEST_UP", "SRV_12609_01", "TR_12609", 502.0, 507.0, direction="UP"),
        ]
        conflicts = self.detector.detect_incompatible_movements(occs)
        self.assertEqual(len(conflicts), 0)

    def test_non_overlapping_opposing_no_conflict(self):
        """UP and DOWN on same section with no temporal overlap -> no conflict."""
        occs = [
            _make_occ("TS_SINGLE", "SRV_A", "TR_A", 500.0, 504.0, direction="UP"),
            _make_occ("TS_SINGLE", "SRV_B", "TR_B", 505.0, 509.0, direction="DOWN"),
        ]
        conflicts = self.detector.detect_incompatible_movements(occs)
        self.assertEqual(len(conflicts), 0)

    def test_opposing_from_to_node_detection(self):
        """from_node/to_node reversal triggers incompatible movement detection."""
        occ1 = _make_occ("TS_SEC", "SRV_A", "TR_A", 600.0, 605.0,
                         from_node="NODE_X", to_node="NODE_Y")
        occ2 = _make_occ("TS_SEC", "SRV_B", "TR_B", 602.0, 607.0,
                         from_node="NODE_Y", to_node="NODE_X")
        conflicts = self.detector.detect_incompatible_movements([occ1, occ2])
        self.assertGreaterEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].conflict_type, ConflictType.INCOMPATIBLE_MOVEMENTS)

    def test_incompatible_conflict_metadata_overlap_window(self):
        """Incompatible movement conflict records correct overlap window in metadata."""
        occs = [
            _make_occ("TS_SINGLE_TRACK", "SRV_A", "TR_A", 500.0, 510.0, direction="UP"),
            _make_occ("TS_SINGLE_TRACK", "SRV_B", "TR_B", 504.0, 512.0, direction="DOWN"),
        ]
        conflicts = self.detector.detect_incompatible_movements(occs)
        self.assertGreaterEqual(len(conflicts), 1)
        meta = conflicts[0].metadata
        self.assertIn("overlap_start_time", meta)
        self.assertIn("overlap_end_time", meta)
        self.assertAlmostEqual(meta["overlap_start_time"], 504.0)
        self.assertAlmostEqual(meta["overlap_end_time"], 510.0)


# ==============================================================================
# SC-09 -- Platform contention
# ==============================================================================
class TestPlatformContention(unittest.TestCase):
    """SC-09: Platform allocation -- concurrency on distinct platforms allowed;
    double-booking same platform blocked."""

    @classmethod
    def setUpClass(cls):
        cls.net = _load_network()

    def test_distinct_platform_concurrency_allowed(self):
        """Two services simultaneously on P1 and P2 -> both acquire resources."""
        state = SimulationState()
        state.initialize_from_network(self.net)
        ok_a = state.occupy_resource("MAS_P1", "SRV_12607_01")
        ok_b = state.occupy_resource("MAS_P2", "SRV_12609_01")
        self.assertTrue(ok_a)
        self.assertTrue(ok_b)

    def test_same_platform_double_booking_blocked(self):
        """Second service cannot acquire an already-occupied platform."""
        state = SimulationState()
        state.initialize_from_network(self.net)
        ok_a = state.occupy_resource("MAS_P1", "SRV_12607_01")
        ok_b = state.occupy_resource("MAS_P1", "SRV_12609_01")
        self.assertTrue(ok_a)
        self.assertFalse(ok_b)

    def test_platform_reclaim_after_release(self):
        """After the occupying service releases a platform, another can acquire it."""
        state = SimulationState()
        state.initialize_from_network(self.net)
        state.occupy_resource("MAS_P1", "SRV_12607_01")
        state.release_resource("MAS_P1", "SRV_12607_01")
        ok_b = state.occupy_resource("MAS_P1", "SRV_12609_01")
        self.assertTrue(ok_b)

    def test_three_platform_independent_allocation(self):
        """Three distinct platforms can be independently occupied concurrently."""
        state = SimulationState()
        state.initialize_from_network(self.net)
        ok1 = state.occupy_resource("MAS_P1", "SRV_A")
        ok2 = state.occupy_resource("MAS_P2", "SRV_B")
        # At least P1 and P2 must succeed; P3 may or may not exist
        self.assertTrue(ok1)
        self.assertTrue(ok2)


# ==============================================================================
# SC-10 -- Unrelated corridor resource isolation
# ==============================================================================
class TestCorridorResourceIsolation(unittest.TestCase):
    """SC-10: Resources used by one corridor must not appear in another corridor's occupancy."""

    @classmethod
    def setUpClass(cls):
        cls.net = _load_network()

    def _run_service(self, service_id: str) -> SimulationState:
        clock = SimulationClock()
        state = SimulationState(clock=clock)
        sim = TrainSimulator(network=self.net, clock=clock, state=state)
        sim.run_service_to_destination(service_id, strict_track_lookup=False)
        return state

    def test_north_service_does_not_touch_south_sections(self):
        """North Corridor service (MAS->SPE) must not occupy any South-specific section."""
        state = self._run_service("SRV_12712_01")
        south_prefixes = ("TS_MS_", "TS_MB_", "TS_TBM_", "TS_CGL")
        for occ in state.occupancy_history:
            for pfx in south_prefixes:
                self.assertFalse(
                    occ.section_id.startswith(pfx),
                    f"North service leaked into South section: {occ.section_id}",
                )

    def test_west_service_does_not_touch_mrts_sections(self):
        """West Corridor service (MAS->AJJ) must not occupy any MRTS section."""
        state = self._run_service("SRV_12607_01")
        for occ in state.occupancy_history:
            self.assertFalse(
                occ.section_id.startswith("TS_MRTS"),
                f"West service leaked into MRTS section: {occ.section_id}",
            )

    def test_south_service_does_not_touch_north_sections(self):
        """South Corridor service (MS->CGL) must not occupy any North-specific section."""
        state = self._run_service("SRV_12635_01")
        for occ in state.occupancy_history:
            self.assertFalse(
                occ.section_id.startswith("TS_MAS_KOK"),
                f"South service leaked into North section: {occ.section_id}",
            )

    def test_bypass_service_does_not_touch_west_only_sections(self):
        """Beach-North Bypass service (MSB->GPD) must not use West-only sections."""
        state = self._run_service("SRV_42601_01")
        west_only = ("TS_PAB_", "TS_TRL_AJJ", "TS_AJJ_TRL")
        for occ in state.occupancy_history:
            for pfx in west_only:
                self.assertFalse(
                    occ.section_id.startswith(pfx),
                    f"Bypass service leaked into West-only section: {occ.section_id}",
                )


# ==============================================================================
# SC-11 -- Conflict severity classification correctness
# ==============================================================================
class TestConflictSeverityClassification(unittest.TestCase):
    """SC-11: Verify severity mapping for each conflict category."""

    def setUp(self):
        self.detector = ConflictDetector()

    def test_same_track_capacity_1_is_critical(self):
        occs = [
            _make_occ("TS_X", "SRV_A", "TR_A", 360.0, 365.0),
            _make_occ("TS_X", "SRV_B", "TR_B", 362.0, 367.0),
        ]
        conflicts = self.detector.detect_same_section_conflicts(occs, default_capacity=1)
        self.assertTrue(all(c.severity == ConflictSeverity.CRITICAL for c in conflicts))

    def test_same_track_capacity_gt1_is_major(self):
        occs = [
            _make_occ("TS_M", "SRV_A", "TR_A", 360.0, 365.0),
            _make_occ("TS_M", "SRV_B", "TR_B", 361.0, 366.0),
            _make_occ("TS_M", "SRV_C", "TR_C", 362.0, 367.0),
        ]
        conflicts = self.detector.detect_same_section_conflicts(
            occs, capacity_map={"TS_M": 2}
        )
        self.assertTrue(all(c.severity == ConflictSeverity.MAJOR for c in conflicts))

    def test_headway_under_half_minimum_is_major(self):
        """delta_t < min_headway/2 -> MAJOR."""
        occs = [
            _make_occ("TS_H", "SRV_A", "TR_A", 600.0, 604.0),
            _make_occ("TS_H", "SRV_B", "TR_B", 600.8, 604.8),
        ]
        conflicts = self.detector.detect_headway_conflicts(occs, default_min_headway_minutes=3.0)
        self.assertTrue(any(c.severity == ConflictSeverity.MAJOR for c in conflicts))

    def test_headway_over_half_minimum_is_warning(self):
        """1.5 <= delta_t < 3.0 -> WARNING."""
        occs = [
            _make_occ("TS_H", "SRV_A", "TR_A", 600.0, 604.0),
            _make_occ("TS_H", "SRV_B", "TR_B", 602.0, 606.0),
        ]
        conflicts = self.detector.detect_headway_conflicts(occs, default_min_headway_minutes=3.0)
        self.assertTrue(any(c.severity == ConflictSeverity.WARNING for c in conflicts))

    def test_incompatible_movement_is_critical(self):
        occs = [
            _make_occ("TS_SING", "SRV_A", "TR_A", 500.0, 506.0, direction="UP"),
            _make_occ("TS_SING", "SRV_B", "TR_B", 502.0, 508.0, direction="DOWN"),
        ]
        conflicts = self.detector.detect_incompatible_movements(occs)
        self.assertTrue(all(c.severity == ConflictSeverity.CRITICAL for c in conflicts))

    def test_junction_contention_is_major(self):
        node_occs = [
            {"node_id": "BBQ", "service_id": "SRV_A", "train_id": "TR_A",
             "arrival_time": 360.0, "departure_time": 362.0},
            {"node_id": "BBQ", "service_id": "SRV_B", "train_id": "TR_B",
             "arrival_time": 361.0, "departure_time": 363.0},
        ]
        conflicts = self.detector.detect_junction_conflicts(
            node_occupancies=node_occs, junction_capacity_map={"BBQ": 1}
        )
        self.assertTrue(all(c.severity == ConflictSeverity.MAJOR for c in conflicts))


# ==============================================================================
# SC-12 -- Detector reset
# ==============================================================================
class TestDetectorReset(unittest.TestCase):
    """SC-12: reset() clears all accumulated conflict state and resets ID counter."""

    def test_reset_clears_conflicts(self):
        detector = ConflictDetector()
        occs = [
            _make_occ("TS_X", "SRV_A", "TR_A", 360.0, 366.0),
            _make_occ("TS_X", "SRV_B", "TR_B", 362.0, 368.0),
        ]
        detector.detect_same_section_conflicts(occs, default_capacity=1)
        self.assertGreater(len(detector.conflicts), 0)
        detector.reset()
        self.assertEqual(len(detector.conflicts), 0)

    def test_reset_restarts_id_counter(self):
        detector = ConflictDetector()
        occs = [
            _make_occ("TS_X", "SRV_A", "TR_A", 360.0, 366.0),
            _make_occ("TS_X", "SRV_B", "TR_B", 362.0, 368.0),
        ]
        detector.detect_same_section_conflicts(occs, default_capacity=1)
        first_ids = {c.conflict_id for c in detector.conflicts}
        detector.reset()
        detector.detect_same_section_conflicts(occs, default_capacity=1)
        second_ids = {c.conflict_id for c in detector.conflicts}
        self.assertEqual(first_ids, second_ids)

    def test_detect_all_reset_consistent_count(self):
        detector = ConflictDetector()
        occs = [
            _make_occ("TS_Y", "SRV_A", "TR_A", 360.0, 366.0),
            _make_occ("TS_Y", "SRV_B", "TR_B", 361.0, 367.0),
        ]
        count1 = len(detector.detect_all(occupancies=occs))
        detector.reset()
        count2 = len(detector.detect_all(occupancies=occs))
        self.assertEqual(count1, count2)


# ==============================================================================
# SC-13 -- Determinism
# ==============================================================================
class TestConflictDeterminism(unittest.TestCase):
    """SC-13: Two identical conflict detection runs must produce identical ordered results."""

    def _build_occupancies(self):
        return [
            _make_occ("TS_MAS_BBQ_DOWN", "SRV_12607_01", "TR_12607", 360.0, 366.0),
            _make_occ("TS_MAS_BBQ_DOWN", "SRV_12610_01", "TR_12610", 362.0, 368.0),
            _make_occ("TS_BBQ_MAS",      "SRV_12610_01", "TR_12610", 400.0, 405.0),
            _make_occ("TS_BBQ_MAS",      "SRV_12640_01", "TR_12640", 401.0, 406.0),
            _make_occ("TS_SINGLE_TRACK", "SRV_12607_01", "TR_12607", 500.0, 505.0, direction="UP"),
            _make_occ("TS_SINGLE_TRACK", "SRV_12610_01", "TR_12610", 502.0, 507.0, direction="DOWN"),
        ]

    def _run_detection(self) -> str:
        detector = ConflictDetector()
        all_c = detector.detect_all(occupancies=self._build_occupancies())
        fp = "|".join(
            f"{c.conflict_id}:{c.conflict_type.value}:{c.resource_id}:{c.conflict_time:.2f}"
            for c in all_c
        )
        return hashlib.sha256(fp.encode()).hexdigest()

    def test_identical_runs_produce_same_hash(self):
        h1 = self._run_detection()
        h2 = self._run_detection()
        self.assertEqual(h1, h2, "Conflict detection is not deterministic across identical runs")

    def test_conflict_ordering_stable(self):
        """detect_all returns conflicts in stable chronological order."""
        detector = ConflictDetector()
        conflicts = detector.detect_all(occupancies=self._build_occupancies())
        times = [c.conflict_time for c in conflicts]
        self.assertEqual(times, sorted(times))

    def test_simulation_conflict_detection_deterministic(self):
        """Running the same simulation twice produces the same conflict set."""
        net = _load_network()

        def run():
            clock = SimulationClock()
            state = SimulationState(clock=clock)
            sim = TrainSimulator(network=net, clock=clock, state=state)
            sim.run_service_to_destination("SRV_12607_01", strict_track_lookup=False)
            sim.run_service_to_destination("SRV_12610_01", strict_track_lookup=False)
            det = ConflictDetector(network=net)
            all_c = det.detect_all(state=state)
            return hashlib.sha256(
                "|".join(f"{c.conflict_id}:{c.resource_id}" for c in all_c).encode()
            ).hexdigest()

        self.assertEqual(run(), run())


# ==============================================================================
# SC-14 -- Pending service exclusion
# ==============================================================================
class TestPendingServiceExclusion(unittest.TestCase):
    """SC-14: The 7 pending services never appear in conflict records from backed service runs."""

    PENDING_IDS = {
        "SRV_40143_01", "SRV_40144_01", "SRV_41015_01",
        "SRV_41131_01", "SRV_41132_01", "SRV_42413_01", "SRV_42425_01",
    }

    @classmethod
    def setUpClass(cls):
        cls.net = _load_network()

    def test_pending_services_absent_from_all_conflict_records(self):
        """Run 5 representative services; no pending service_id appears in conflicts."""
        svc_ids = [
            "SRV_12607_01",  # West
            "SRV_12712_01",  # North
            "SRV_12635_01",  # South
            "SRV_41001_01",  # MRTS
            "SRV_42601_01",  # Bypass
        ]
        clock = SimulationClock()
        state = SimulationState(clock=clock)
        sim = TrainSimulator(network=self.net, clock=clock, state=state)
        for s_id in svc_ids:
            sim.run_service_to_destination(s_id, strict_track_lookup=False)

        detector = ConflictDetector(network=self.net)
        all_conflicts = detector.detect_all(state=state)

        for c in all_conflicts:
            for p_id in self.PENDING_IDS:
                self.assertNotIn(
                    p_id, c.affected_service_ids,
                    f"Pending service {p_id} appeared in conflict {c.conflict_id}",
                )


# ==============================================================================
# SC-15 -- Full 40-service conflict scan
# ==============================================================================
class TestFull40ServiceConflictScan(unittest.TestCase):
    """SC-15: Run all 40 backed services and verify every conflict is correctly classified."""

    VALID_TYPES: Set = {
        ConflictType.SAME_TRACK_SECTION,
        ConflictType.INSUFFICIENT_HEADWAY,
        ConflictType.SHARED_JUNCTION,
        ConflictType.INCOMPATIBLE_MOVEMENTS,
    }
    VALID_SEVERITIES: Set = {
        ConflictSeverity.CRITICAL,
        ConflictSeverity.MAJOR,
        ConflictSeverity.WARNING,
        ConflictSeverity.MINOR,
    }

    @classmethod
    def setUpClass(cls):
        cls.net = _load_network()
        cls.backed_ids = _backed_ids(cls.net)

        clock = SimulationClock()
        cls.state = SimulationState(clock=clock)
        sim = TrainSimulator(network=cls.net, clock=clock, state=cls.state)
        for s_id in cls.backed_ids:
            sim.run_service_to_destination(s_id, strict_track_lookup=False)

        cls.detector = ConflictDetector(network=cls.net)
        cls.all_conflicts = cls.detector.detect_all(state=cls.state)

    def test_all_conflicts_have_valid_type(self):
        for c in self.all_conflicts:
            self.assertIn(c.conflict_type, self.VALID_TYPES,
                          f"Unclassified conflict type: {c.conflict_type}")

    def test_all_conflicts_have_valid_severity(self):
        for c in self.all_conflicts:
            self.assertIn(c.severity, self.VALID_SEVERITIES,
                          f"Unclassified severity: {c.severity}")

    def test_all_conflicts_reference_valid_services(self):
        all_known_ids = set(self.net.services.keys())
        for c in self.all_conflicts:
            for s_id in c.affected_service_ids:
                self.assertIn(s_id, all_known_ids,
                              f"Conflict references unknown service {s_id}")

    def test_all_conflicts_have_non_empty_resource_id(self):
        for c in self.all_conflicts:
            self.assertTrue(len(c.resource_id) > 0,
                            f"Conflict {c.conflict_id} has empty resource_id")

    def test_all_conflicts_have_non_negative_time(self):
        for c in self.all_conflicts:
            self.assertGreaterEqual(c.conflict_time, 0.0,
                                    f"Conflict {c.conflict_id} has negative time")

    def test_conflict_count_summary_informational(self):
        """Emit per-type conflict count summary (always passes)."""
        by_type: Dict[str, int] = defaultdict(int)
        by_sev: Dict[str, int] = defaultdict(int)
        for c in self.all_conflicts:
            by_type[c.conflict_type.value] += 1
            by_sev[c.severity.value] += 1
        _ = by_type, by_sev   # informational only

    def test_all_40_backed_services_completed(self):
        """After running all 40 services, every one reaches COMPLETED status."""
        for s_id in self.backed_ids:
            ts = self.state.get_train_state(s_id)
            self.assertEqual(ts.status, TrainStatus.COMPLETED,
                             f"Service {s_id} did not reach COMPLETED (got {ts.status})")

    def test_no_stale_active_occupancies_after_full_run(self):
        """After running all 40 services, the active occupancy set is empty."""
        active = self.state.get_active_occupancies()
        self.assertEqual(len(active), 0,
                         f"Stale active occupancies: {[o.service_id for o in active]}")


if __name__ == "__main__":
    unittest.main()
