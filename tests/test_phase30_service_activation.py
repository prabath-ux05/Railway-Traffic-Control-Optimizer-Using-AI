"""
tests/test_phase30_service_activation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 30.1: Multi-Corridor Service Activation & Load Verification.

Verifies:
1. Audit of all 40 timetable-backed services across the Chennai Division.
2. Complete exclusion of the 7 pending services from timetable entries.
3. Safe loading and simulation traversal across all operational corridors:
   - West / PTMS (22 services)
   - North (7 services)
   - South (6 services)
   - MRTS (3 services)
   - Beach-North Bypass (2 services)
4. Safe handling of partial timetable services (SRV_12842_01 Coromandel Express).
5. Safe handling of multi-day midnight rollover services (SRV_16159_01).
6. Concurrent multi-corridor service activation.
"""

import os
import unittest
from collections import defaultdict

from simulation.clock import SimulationClock, time_to_minutes
from simulation.network import Network
from simulation.simulator import TrainSimulator
from simulation.state import SimulationState, TrainStatus

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")


class TestPhase30ServiceActivation(unittest.TestCase):
    """Deterministic activation and load verification for all 40 backed services."""

    @classmethod
    def setUpClass(cls):
        cls.net = Network()
        cls.net.load_from_directory(os.path.join(_DATA_DIR, "infrastructure"))
        cls.net.load_trains(os.path.join(_DATA_DIR, "trains", "train_identity", "trains.json"))
        cls.net.load_services(os.path.join(_DATA_DIR, "trains", "service_definitions", "services.json"))
        cls.net.load_timetable(os.path.join(_DATA_DIR, "trains", "published_timetables", "timetable.json"))

        cls.backed_service_ids = {e.service_id for e in cls.net.timetable}
        cls.all_service_ids = set(cls.net.services.keys())
        cls.pending_service_ids = cls.all_service_ids - cls.backed_service_ids

    def test_backed_and_pending_service_counts(self):
        """Verify exactly 40 backed services and 7 pending services."""
        self.assertEqual(len(self.backed_service_ids), 40)
        self.assertEqual(len(self.pending_service_ids), 7)
        self.assertEqual(len(self.all_service_ids), 47)

        # Expected 7 pending services
        expected_pending = {
            "SRV_40143_01", "SRV_40144_01", "SRV_41015_01",
            "SRV_41131_01", "SRV_41132_01", "SRV_42413_01", "SRV_42425_01",
        }
        self.assertEqual(self.pending_service_ids, expected_pending)

    def test_pending_services_have_no_timetable_entries(self):
        """Confirm all 7 pending services have strictly 0 timetable records."""
        for p_id in self.pending_service_ids:
            entries = [e for e in self.net.timetable if e.service_id == p_id]
            self.assertEqual(
                len(entries), 0,
                f"Pending service {p_id} unexpectedly has {len(entries)} timetable entries"
            )

    def test_all_backed_services_initialize_in_simulator(self):
        """Verify all 40 backed services initialize cleanly at their origin station."""
        for s_id in sorted(self.backed_service_ids):
            sim = TrainSimulator(network=self.net)
            ev = sim.initialize_service(s_id)
            state = sim.state.get_train_state(s_id)

            self.assertEqual(state.status, TrainStatus.AT_STATION)
            svc = self.net.services[s_id]
            route = self.net.routes[svc.route_id]
            self.assertEqual(state.current_node, route.ordered_nodes[0])
            self.assertEqual(ev.service_id, s_id)

    def test_all_backed_services_traverse_to_completion(self):
        """Verify all 40 backed services traverse their full route to COMPLETED status."""
        for s_id in sorted(self.backed_service_ids):
            sim = TrainSimulator(network=self.net)
            events = sim.run_service_to_destination(s_id, strict_track_lookup=False)
            state = sim.state.get_train_state(s_id)

            self.assertEqual(
                state.status, TrainStatus.COMPLETED,
                f"Service {s_id} did not reach COMPLETED status (status={state.status})"
            )
            self.assertGreater(len(events), 0)

    def test_partial_service_12842_simulation(self):
        """Verify SRV_12842_01 (Coromandel Express, origin-only partial) simulates without errors."""
        self.assertIn("SRV_12842_01", self.backed_service_ids)
        entries = [e for e in self.net.timetable if e.service_id == "SRV_12842_01"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].station_id, "MAS")
        self.assertEqual(entries[0].departure, "07:00")

        # Full route has 22 nodes (MAS -> SPE)
        route = self.net.routes[self.net.services["SRV_12842_01"].route_id]
        self.assertEqual(len(route.ordered_nodes), 22)

        # Runs with strict track lookup since North mainline has all contiguous sections
        sim = TrainSimulator(network=self.net)
        events = sim.run_service_to_destination("SRV_12842_01", strict_track_lookup=True)
        state = sim.state.get_train_state("SRV_12842_01")
        self.assertEqual(state.status, TrainStatus.COMPLETED)
        self.assertEqual(state.current_station, "SPE")

    def test_midnight_rollover_16159_simulation(self):
        """Verify SRV_16159_01 handles midnight rollover cleanly."""
        self.assertIn("SRV_16159_01", self.backed_service_ids)
        entries = sorted(
            [e for e in self.net.timetable if e.service_id == "SRV_16159_01"],
            key=lambda e: e.stop_sequence
        )
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0].station_id, "MS")
        self.assertEqual(entries[0].departure, "23:10")
        self.assertEqual(entries[1].station_id, "TBM")
        self.assertEqual(entries[1].departure, "23:40")
        self.assertEqual(entries[2].station_id, "CGL")
        self.assertEqual(entries[2].arrival, "00:08")

        sim = TrainSimulator(network=self.net)
        events = sim.run_service_to_destination("SRV_16159_01", strict_track_lookup=False)
        state = sim.state.get_train_state("SRV_16159_01")
        self.assertEqual(state.status, TrainStatus.COMPLETED)

    def test_multi_corridor_concurrent_activation(self):
        """Simulate concurrent initialization of services across 5 operational corridors."""
        sample_services = [
            "SRV_12607_01",  # West
            "SRV_12712_01",  # North
            "SRV_12635_01",  # South
            "SRV_41001_01",  # MRTS
            "SRV_42601_01",  # Beach-North Bypass
        ]

        clock = SimulationClock("05:00")
        state = SimulationState(clock=clock)
        sim = TrainSimulator(network=self.net, clock=clock, state=state)

        for s_id in sample_services:
            ev = sim.initialize_service(s_id)
            self.assertEqual(ev.service_id, s_id)

        for s_id in sample_services:
            ts = sim.state.get_train_state(s_id)
            self.assertEqual(ts.status, TrainStatus.AT_STATION)


if __name__ == "__main__":
    unittest.main()
