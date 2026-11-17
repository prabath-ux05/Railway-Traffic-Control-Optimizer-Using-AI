"""
tests/test_phase30_simulation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 30.2: Expanded Digital Twin Multi-Corridor Simulation & Determinism.

Verifies:
1. Multi-corridor concurrent stepped simulation across 5 operational corridors:
   - West, North, South, MRTS, Beach-North Bypass.
2. Dynamic train state progression:
   NOT_STARTED -> AT_STATION -> IN_TRANSIT -> AT_STATION -> ... -> COMPLETED.
3. Resource acquisition and release lifecycle with zero stale track section locks.
4. Bitwise deterministic reproducibility of event streams and final states across repeated runs.
5. Strict exclusion of the 7 pending services from simulation event generation.
"""

import hashlib
import os
import unittest
from typing import List

from simulation.clock import SimulationClock, time_to_minutes
from simulation.network import Network
from simulation.simulator import TrainSimulator
from simulation.state import SimulationState, TrainStatus

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")


class TestPhase30Simulation(unittest.TestCase):
    """Expanded multi-corridor simulation and determinism tests."""

    @classmethod
    def setUpClass(cls):
        cls.net = Network()
        cls.net.load_from_directory(os.path.join(_DATA_DIR, "infrastructure"))
        cls.net.load_trains(os.path.join(_DATA_DIR, "trains", "train_identity", "trains.json"))
        cls.net.load_services(os.path.join(_DATA_DIR, "trains", "service_definitions", "services.json"))
        cls.net.load_timetable(os.path.join(_DATA_DIR, "trains", "published_timetables", "timetable.json"))

        cls.backed_service_ids = sorted({e.service_id for e in cls.net.timetable})
        cls.pending_service_ids = sorted(set(cls.net.services.keys()) - set(cls.backed_service_ids))

        cls.representative_corridor_services = [
            "SRV_12607_01",  # West Corridor (MAS -> AJJ)
            "SRV_12712_01",  # North Corridor (MAS -> SPE)
            "SRV_12635_01",  # South Corridor (MS -> CGL)
            "SRV_41001_01",  # MRTS Corridor (MSB -> VLCY)
            "SRV_42601_01",  # Beach-North Bypass (MSB -> GPD)
        ]

    def test_all_40_services_resource_lifecycle_clean(self):
        """Verify that every backed service releases all track locks upon completion."""
        for s_id in self.backed_service_ids:
            clock = SimulationClock()
            state = SimulationState(clock=clock)
            sim = TrainSimulator(network=self.net, clock=clock, state=state)

            sim.run_service_to_destination(s_id, strict_track_lookup=False)
            ts = state.get_train_state(s_id)

            self.assertEqual(ts.status, TrainStatus.COMPLETED)
            self.assertIsNone(ts.current_track_section)

            active_for_svc = [occ for occ in state.get_active_occupancies() if occ.service_id == s_id]
            self.assertEqual(len(active_for_svc), 0, f"Stale active occupancy for {s_id}")

            for track_id, svc_set in state.track_occupancy.items():
                self.assertNotIn(s_id, svc_set, f"Stale track_occupancy in {track_id} for {s_id}")

    def test_concurrent_stepped_simulation_across_all_corridors(self):
        """Run simultaneous stepped simulation of 5 services across 5 distinct corridors."""
        clock = SimulationClock(start_time="05:00")
        state = SimulationState(clock=clock)
        sim = TrainSimulator(network=self.net, clock=clock, state=state)

        for s_id in self.representative_corridor_services:
            sim.initialize_service(s_id)
            ts = state.get_train_state(s_id)
            self.assertEqual(ts.status, TrainStatus.AT_STATION)

        cycles = 0
        while not all(state.get_train_state(s).is_completed for s in self.representative_corridor_services):
            cycles += 1
            self.assertLess(cycles, 300, "Simulation exceeded maximum expected cycle count")
            for s_id in self.representative_corridor_services:
                if not state.get_train_state(s_id).is_completed:
                    sim.step_service(s_id, strict_track_lookup=False)

        for s_id in self.representative_corridor_services:
            ts = state.get_train_state(s_id)
            self.assertEqual(ts.status, TrainStatus.COMPLETED)
            self.assertIsNone(ts.current_track_section)

        self.assertEqual(len(state.get_active_occupancies()), 0)

    def test_simulation_determinism_across_identical_runs(self):
        """Verify identical multi-service simulations produce identical event logs and hashes."""
        def run_sim():
            clock = SimulationClock(start_time="05:00")
            state = SimulationState(clock=clock)
            sim = TrainSimulator(network=self.net, clock=clock, state=state)

            for s_id in self.representative_corridor_services:
                sim.initialize_service(s_id)

            while not all(state.get_train_state(s).is_completed for s in self.representative_corridor_services):
                for s_id in self.representative_corridor_services:
                    if not state.get_train_state(s_id).is_completed:
                        sim.step_service(s_id, strict_track_lookup=False)

            events = [
                f"{e.time:.2f}:{e.event_type.value}:{e.service_id}:{e.node_id}:{e.track_section_id}"
                for e in sim.event_history
            ]
            event_hash = hashlib.sha256("\n".join(events).encode()).hexdigest()
            return event_hash, events, state

        hash1, events1, state1 = run_sim()
        hash2, events2, state2 = run_sim()

        self.assertEqual(hash1, hash2, "Event history hash mismatch across identical runs")
        self.assertEqual(len(events1), len(events2))
        self.assertEqual(events1, events2)

        for s_id in self.representative_corridor_services:
            st1 = state1.get_train_state(s_id)
            st2 = state2.get_train_state(s_id)
            self.assertEqual(st1.status, st2.status)
            self.assertEqual(st1.last_event_time, st2.last_event_time)
            self.assertEqual(st1.delay_minutes, st2.delay_minutes)
            self.assertEqual(st1.actual_arrivals, st2.actual_arrivals)
            self.assertEqual(st1.actual_departures, st2.actual_departures)

    def test_pending_services_remain_unactivated_during_simulation(self):
        """Confirm the 7 pending services are never touched during operational simulation."""
        clock = SimulationClock(start_time="05:00")
        state = SimulationState(clock=clock)
        sim = TrainSimulator(network=self.net, clock=clock, state=state)

        for s_id in self.representative_corridor_services:
            sim.run_service_to_destination(s_id, strict_track_lookup=False)

        for p_id in self.pending_service_ids:
            ts = state.get_train_state(p_id)
            self.assertEqual(ts.status, TrainStatus.NOT_STARTED)
            self.assertEqual(len(ts.actual_arrivals), 0)
            self.assertEqual(len(ts.actual_departures), 0)
            self.assertIsNone(ts.current_node)


if __name__ == "__main__":
    unittest.main()
