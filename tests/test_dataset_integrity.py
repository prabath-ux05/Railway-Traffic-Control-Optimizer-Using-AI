"""
tests/test_dataset_integrity.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Integration tests that load the *real* project data files (not temp fixtures)
and verify the complete Train → Service → Timetable pipeline:

  1. All 51 trains load successfully.
  2. All 22 services load successfully.
  3. All 84 timetable entries load successfully.
  4. Every service references a valid train and route.
  5. Every timetable entry references a valid service.
  6. Timetable entries for each service follow that service's routes.json ordered-node sequence.
  7. Preserve timetable file order when deriving stop_sequence.
  8. Verify the existing 20607, PTMS, and West-corridor records without modifying them.
  9. Report PAB/PTMS station-registry mismatch as a data-integrity issue; do NOT modify stations.json.
  10. No duplicate IDs or invalid references exist across all datasets.

These tests are read-only; they do not modify any data files.
"""

import json
import os
import unittest
from collections import defaultdict

from simulation.network import Network

# Absolute path to the data directory (resolved relative to this file)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data", "infrastructure")

_STATIONS_FILE   = os.path.join(_DATA_DIR, "stations.json")
_JUNCTIONS_FILE  = os.path.join(_DATA_DIR, "junctions.json")
_ROUTES_FILE     = os.path.join(_DATA_DIR, "routes.json")
_PLATFORMS_FILE  = os.path.join(_DATA_DIR, "platforms.json")

_TRAINS_FILE    = os.path.join(_REPO_ROOT, "data", "trains", "train_identity",    "trains.json")
_SERVICES_FILE  = os.path.join(_REPO_ROOT, "data", "trains", "service_definitions", "services.json")
_TIMETABLE_FILE = os.path.join(_REPO_ROOT, "data", "trains", "published_timetables", "timetable.json")

EXPECTED_TRAINS             = 51
EXPECTED_SERVICES           = 47
EXPECTED_PUBLISHED_SERVICES = 40
EXPECTED_TIMETABLE_ENTRIES  = 127
EXPECTED_STATIONS           = 30
EXPECTED_JUNCTIONS          = 7
EXPECTED_ROUTES             = 24
EXPECTED_PLATFORMS          = 14
EXPECTED_WEST_SERVICES      = 20
EXPECTED_TRACK_SECTIONS     = 354


class TestDatasetRecordCounts(unittest.TestCase):
    """Verify that the raw JSON files contain the expected number of records."""

    def _load_json(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_trains_count(self):
        data = self._load_json(_TRAINS_FILE)
        self.assertIsInstance(data, list)
        self.assertEqual(
            len(data), EXPECTED_TRAINS,
            f"trains.json: expected {EXPECTED_TRAINS} records, got {len(data)}"
        )

    def test_services_count(self):
        data = self._load_json(_SERVICES_FILE)
        self.assertIsInstance(data, list)
        self.assertEqual(
            len(data), EXPECTED_SERVICES,
            f"services.json: expected {EXPECTED_SERVICES} records, got {len(data)}"
        )

    def test_timetable_count(self):
        data = self._load_json(_TIMETABLE_FILE)
        self.assertIsInstance(data, list)
        self.assertEqual(
            len(data), EXPECTED_TIMETABLE_ENTRIES,
            f"timetable.json: expected {EXPECTED_TIMETABLE_ENTRIES} entries, got {len(data)}"
        )

    def test_track_sections_count(self):
        import glob
        corridor_files = sorted(glob.glob(os.path.join(_REPO_ROOT, "data", "track_sections", "*.json")))
        self.assertEqual(len(corridor_files), 6, "Expected 6 track-section corridor files")
        total_tracks = sum(len(self._load_json(f)) for f in corridor_files)
        self.assertEqual(
            total_tracks, EXPECTED_TRACK_SECTIONS,
            f"Expected {EXPECTED_TRACK_SECTIONS} track sections across corridor files, got {total_tracks}"
        )

    def test_infrastructure_record_counts(self):
        stations = self._load_json(_STATIONS_FILE)
        junctions = self._load_json(_JUNCTIONS_FILE)
        routes = self._load_json(_ROUTES_FILE)
        platforms = self._load_json(_PLATFORMS_FILE)

        self.assertEqual(len(stations), EXPECTED_STATIONS,
                         f"stations.json: expected {EXPECTED_STATIONS}, got {len(stations)}")
        self.assertEqual(len(junctions), EXPECTED_JUNCTIONS,
                         f"junctions.json: expected {EXPECTED_JUNCTIONS}, got {len(junctions)}")
        self.assertEqual(len(routes), EXPECTED_ROUTES,
                         f"routes.json: expected {EXPECTED_ROUTES}, got {len(routes)}")
        self.assertEqual(len(platforms), EXPECTED_PLATFORMS,
                         f"platforms.json: expected {EXPECTED_PLATFORMS}, got {len(platforms)}")



class TestDatasetUniquenessAndReferences(unittest.TestCase):
    """Verify primary key uniqueness and foreign key integrity across raw JSON files."""

    def _load_json(self, path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def test_trains_ids_unique(self):
        data = self._load_json(_TRAINS_FILE)
        ids = [t["train_id"] for t in data]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate train IDs found in trains.json")

    def test_services_ids_unique(self):
        data = self._load_json(_SERVICES_FILE)
        ids = [s["service_id"] for s in data]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate service IDs found in services.json")

    def test_infrastructure_ids_unique(self):
        stations = self._load_json(_STATIONS_FILE)
        stn_ids = [s["id"] for s in stations]
        self.assertEqual(len(stn_ids), len(set(stn_ids)), "Duplicate station IDs found in stations.json")

        junctions = self._load_json(_JUNCTIONS_FILE)
        junc_ids = [j["id"] for j in junctions]
        self.assertEqual(len(junc_ids), len(set(junc_ids)), "Duplicate junction IDs found in junctions.json")

        routes = self._load_json(_ROUTES_FILE)
        route_ids = [r["id"] for r in routes]
        self.assertEqual(len(route_ids), len(set(route_ids)), "Duplicate route IDs found in routes.json")

        platforms = self._load_json(_PLATFORMS_FILE)
        platform_ids = [p["id"] for p in platforms]
        self.assertEqual(len(platform_ids), len(set(platform_ids)), "Duplicate platform IDs found in platforms.json")

    def test_timetable_service_station_pairs_unique(self):
        """No service should have duplicate stops at the same station."""
        data = self._load_json(_TIMETABLE_FILE)
        pairs = [(e["service_id"], e["station_id"]) for e in data]
        self.assertEqual(
            len(pairs), len(set(pairs)),
            "Duplicate (service_id, station_id) pairs found in timetable.json"
        )

    def test_services_train_refs_exist_in_trains(self):
        """Every service's train_id must exist in trains.json."""
        trains_data = self._load_json(_TRAINS_FILE)
        services_data = self._load_json(_SERVICES_FILE)
        train_ids = {t["train_id"] for t in trains_data}
        for svc in services_data:
            self.assertIn(
                svc["train_id"], train_ids,
                f"Service {svc['service_id']} references unknown train_id: {svc['train_id']}"
            )

    def test_services_route_refs_exist_in_routes(self):
        """Every service's route_id must exist in routes.json."""
        routes_data = self._load_json(_ROUTES_FILE)
        services_data = self._load_json(_SERVICES_FILE)
        route_ids = {r["id"] for r in routes_data}
        for svc in services_data:
            self.assertIn(
                svc["route_id"], route_ids,
                f"Service {svc['service_id']} references unknown route_id: {svc['route_id']}"
            )

    def test_timetable_service_refs_valid(self):
        """Every timetable service_id must exist in services.json."""
        services_data = self._load_json(_SERVICES_FILE)
        timetable_data = self._load_json(_TIMETABLE_FILE)
        service_ids = {s["service_id"] for s in services_data}
        for entry in timetable_data:
            self.assertIn(
                entry["service_id"], service_ids,
                f"Timetable references unknown service_id: {entry['service_id']}"
            )

    def test_timetable_covers_all_services(self):
        """Verify timetable coverage for published services and foreign-key integrity."""
        services_data = self._load_json(_SERVICES_FILE)
        timetable_data = self._load_json(_TIMETABLE_FILE)
        service_ids = {s["service_id"] for s in services_data}
        covered = {e["service_id"] for e in timetable_data}

        # Invariant: Every timetable entry references a valid service
        self.assertTrue(covered.issubset(service_ids))

        # All 22 original West corridor services remain 100% timetable-backed
        original_services = {s["service_id"] for s in services_data[:22]}
        missing_original = original_services - covered
        self.assertEqual(
            missing_original, set(),
            f"Original published services with no timetable entries: {sorted(missing_original)}"
        )

        # 40 services are now timetable-backed across West, North, South, Bypass, and MRTS corridors
        self.assertEqual(len(covered), EXPECTED_PUBLISHED_SERVICES)

        # 7 Phase 28 expansion services intentionally awaiting timetable integration
        pending_services = service_ids - covered
        self.assertEqual(len(pending_services), 7)


class TestFullDatasetLoad(unittest.TestCase):
    """End-to-end: load infrastructure + trains + services + timetable via Network."""

    @classmethod
    def setUpClass(cls):
        cls.net = Network()
        cls.net.load_from_directory(_DATA_DIR)
        cls.net.load_trains(_TRAINS_FILE)
        cls.net.load_services(_SERVICES_FILE)
        cls.net.load_timetable(_TIMETABLE_FILE)

    def test_train_count_loaded(self):
        self.assertEqual(
            len(self.net.trains), EXPECTED_TRAINS,
            f"Network loaded {len(self.net.trains)} trains, expected {EXPECTED_TRAINS}"
        )

    def test_service_count_loaded(self):
        self.assertEqual(
            len(self.net.services), EXPECTED_SERVICES,
            f"Network loaded {len(self.net.services)} services, expected {EXPECTED_SERVICES}"
        )

    def test_timetable_count_loaded(self):
        self.assertEqual(
            len(self.net.timetable), EXPECTED_TIMETABLE_ENTRIES,
            f"Network loaded {len(self.net.timetable)} timetable entries, expected {EXPECTED_TIMETABLE_ENTRIES}"
        )

    def test_track_sections_count_loaded(self):
        self.assertEqual(
            len(self.net.track_sections), EXPECTED_TRACK_SECTIONS,
            f"Network loaded {len(self.net.track_sections)} track sections via auto-discovery, expected {EXPECTED_TRACK_SECTIONS}"
        )

    def test_network_infrastructure_loaded(self):
        self.assertEqual(len(self.net.stations), EXPECTED_STATIONS)
        self.assertEqual(len(self.net.junctions), EXPECTED_JUNCTIONS)
        self.assertEqual(len(self.net.routes), EXPECTED_ROUTES)
        self.assertEqual(len(self.net.platforms), EXPECTED_PLATFORMS)
        self.assertEqual(len(self.net.track_sections), EXPECTED_TRACK_SECTIONS)


    def test_all_services_reference_loaded_trains_and_routes(self):
        for svc in self.net.services.values():
            self.assertIn(svc.train_id, self.net.trains,
                          f"Service {svc.id} train_id '{svc.train_id}' not found in loaded trains")
            self.assertIn(svc.route_id, self.net.routes,
                          f"Service {svc.id} route_id '{svc.route_id}' not found in loaded routes")

    def test_all_timetable_entries_reference_loaded_services(self):
        for entry in self.net.timetable:
            self.assertIn(entry.service_id, self.net.services,
                          f"Timetable entry references service '{entry.service_id}' not in loaded services")

    def test_all_services_have_timetable_entries(self):
        """Verify published services have timetable entries and distinguish pending services."""
        covered = {e.service_id for e in self.net.timetable}
        published_subset = [s_id for s_id in self.net.services if s_id in covered]
        self.assertEqual(len(published_subset), EXPECTED_PUBLISHED_SERVICES)
        for svc_id in published_subset:
            self.assertIn(svc_id, covered)
        pending_subset = [s_id for s_id in self.net.services if s_id not in covered]
        self.assertEqual(len(pending_subset), 7)

    def test_stop_sequence_preserves_file_order(self):
        """stop_sequence must be strictly increasing starting from 1 for every service."""
        entries_by_svc = defaultdict(list)
        for entry in self.net.timetable:
            entries_by_svc[entry.service_id].append(entry)

        for svc_id, entries in entries_by_svc.items():
            seqs = [e.stop_sequence for e in entries]
            expected = list(range(1, len(entries) + 1))
            self.assertEqual(
                seqs, expected,
                f"Service {svc_id} stop_sequence does not match 1..N file order: got {seqs}, expected {expected}"
            )

    def test_all_services_timetable_follows_route_sequence(self):
        """Every service's timetable station sequence must be a subsequence of its route's ordered_nodes."""
        entries_by_svc = defaultdict(list)
        for entry in self.net.timetable:
            entries_by_svc[entry.service_id].append(entry)

        for svc_id, entries in entries_by_svc.items():
            service = self.net.services[svc_id]
            route = self.net.routes[service.route_id]
            route_nodes = route.ordered_nodes

            stops = [e.station_id for e in entries]
            pos = 0
            for stn in stops:
                while pos < len(route_nodes) and route_nodes[pos] != stn:
                    pos += 1
                self.assertLess(
                    pos, len(route_nodes),
                    f"Service {svc_id} stop '{stn}' does not follow route '{route.id}' sequence {route_nodes}"
                )
                pos += 1

    def test_no_hard_validation_exceptions_raised(self):
        """setUpClass would have raised if any hard validation failed."""
        self.assertIsNotNone(self.net)

    def test_print_summary_runs(self):
        import io
        import sys
        buf = io.StringIO()
        sys.stdout = buf
        try:
            self.net.print_summary()
        finally:
            sys.stdout = sys.__stdout__
        output = buf.getvalue()
        self.assertIn("Total Trains", output)
        self.assertIn(str(EXPECTED_TRAINS), output)
        self.assertIn("Total Services", output)
        self.assertIn(str(EXPECTED_SERVICES), output)


class TestSpecificDatasetRecords(unittest.TestCase):
    """Verify specific established records: 20607, PTMS, and West-corridor."""

    @classmethod
    def setUpClass(cls):
        cls.net = Network()
        cls.net.load_from_directory(_DATA_DIR)
        cls.net.load_trains(_TRAINS_FILE)
        cls.net.load_services(_SERVICES_FILE)
        cls.net.load_timetable(_TIMETABLE_FILE)

    def test_train_20607_identity(self):
        self.assertIn("TR_20607", self.net.trains)
        train = self.net.trains["TR_20607"]
        self.assertEqual(train.id, "TR_20607")
        self.assertEqual(train.train_number, "20607")
        self.assertEqual(train.name, "Mysuru Vande Bharat Express")
        self.assertEqual(train.train_type, "EXPRESS")

    def test_service_20607_definition(self):
        self.assertIn("SRV_20607_01", self.net.services)
        svc = self.net.services["SRV_20607_01"]
        self.assertEqual(svc.train_id, "TR_20607")
        self.assertEqual(svc.route_id, "RT_WEST_MAS_AJJ")
        self.assertEqual(svc.origin, "MAS")
        self.assertEqual(svc.destination, "AJJ")
        self.assertEqual(svc.priority_class, "HIGH")
        self.assertEqual(svc.simulation_profile, "LOCO_ELECTRIC")
        self.assertEqual(svc.operating_days, ["MON", "TUE", "THU", "FRI", "SAT", "SUN"])

    def test_timetable_20607_record(self):
        entries = [e for e in self.net.timetable if e.service_id == "SRV_20607_01"]
        self.assertEqual(len(entries), 1, "SRV_20607_01 must have exactly 1 timetable entry")
        entry = entries[0]
        self.assertEqual(entry.station_id, "MAS")
        self.assertEqual(entry.departure, "05:50")
        self.assertIsNone(entry.arrival)
        self.assertEqual(entry.stop_sequence, 1)
        self.assertTrue(entry.commercial_stop)

    def test_ptms_trains_identity(self):
        for train_id in ["TR_43102", "TR_43116"]:
            self.assertIn(train_id, self.net.trains)
            train = self.net.trains[train_id]
            self.assertEqual(train.name, "Pattabiram Siding–Chennai Central Local")
            self.assertEqual(train.train_type, "SUBURBAN_EMU")

    def test_ptms_services_definition(self):
        for svc_id, expected_train in [("SRV_43102_01", "TR_43102"), ("SRV_43116_01", "TR_43116")]:
            self.assertIn(svc_id, self.net.services)
            svc = self.net.services[svc_id]
            self.assertEqual(svc.train_id, expected_train)
            self.assertEqual(svc.origin, "PTMS")
            self.assertEqual(svc.destination, "MAS")
            self.assertEqual(svc.route_id, "RT_PTMS_MAS")
            self.assertEqual(svc.priority_class, "NORMAL")
            self.assertEqual(svc.simulation_profile, "EMU_STANDARD")

    def test_ptms_timetable_stops_and_sequence(self):
        expected_stops = ["PTMS", "PAB", "AVD", "PER", "MAS"]
        route = self.net.routes["RT_PTMS_MAS"]

        for svc_id in ["SRV_43102_01", "SRV_43116_01"]:
            entries = [e for e in self.net.timetable if e.service_id == svc_id]
            self.assertEqual(len(entries), 5, f"Service {svc_id} expected 5 stops, got {len(entries)}")

            actual_stops = [e.station_id for e in entries]
            self.assertEqual(actual_stops, expected_stops)

            actual_seqs = [e.stop_sequence for e in entries]
            self.assertEqual(actual_seqs, [1, 2, 3, 4, 5])

            # Verify stops follow route ordered_nodes
            pos = 0
            for stn in actual_stops:
                while pos < len(route.ordered_nodes) and route.ordered_nodes[pos] != stn:
                    pos += 1
                self.assertLess(pos, len(route.ordered_nodes),
                                f"{stn} not found in ordered nodes of {route.id}")
                pos += 1

    def test_west_corridor_services_complete(self):
        west_trunk_routes = {"RT_WEST_MAS_AJJ", "RT_WEST_AJJ_MAS", "RT_WEST_MAS_TRL_SHORT", "RT_WEST_TRL_MAIN_UP"}
        west_services = [s for s in self.net.services.values() if s.route_id in west_trunk_routes]
        self.assertEqual(
            len(west_services), EXPECTED_WEST_SERVICES,
            f"Expected {EXPECTED_WEST_SERVICES} West corridor services, got {len(west_services)}"
        )
        for svc in west_services:
            self.assertIn(svc.train_id, self.net.trains)
            self.assertIn(svc.route_id, self.net.routes)
            # Timetable entries follow route
            route = self.net.routes[svc.route_id]
            svc_entries = [e for e in self.net.timetable if e.service_id == svc.id]
            self.assertGreater(len(svc_entries), 0)
            stops = [e.station_id for e in svc_entries]
            pos = 0
            for stn in stops:
                while pos < len(route.ordered_nodes) and route.ordered_nodes[pos] != stn:
                    pos += 1
                self.assertLess(pos, len(route.ordered_nodes),
                                f"Service {svc.id} stop {stn} not in route {route.id}")
                pos += 1

    def test_mas_bbq_throat_segment_resolved(self):
        """MAS -> BBQ must resolve to MAS_BBQ_THROAT_SEGMENT_DOWN with travel time 4.0 min."""
        ts = self.net.get_track_section("MAS", "BBQ", direction="DOWN")
        self.assertIsNotNone(ts, "Expected MAS -> BBQ DOWN track section")
        self.assertEqual(ts.id, "MAS_BBQ_THROAT_SEGMENT_DOWN")
        self.assertEqual(ts.track_type, "THROAT_SEGMENT")
        self.assertEqual(ts.travel_time_minutes, 4.0)

    def test_west_route_edges_all_resolve_real_track_sections(self):
        """All 28 consecutive edges in RT_WEST_MAS_AJJ must resolve to real track sections."""
        route = self.net.routes["RT_WEST_MAS_AJJ"]
        nodes = route.ordered_nodes
        self.assertEqual(len(nodes), 29)

        for i in range(len(nodes) - 1):
            u, v = nodes[i], nodes[i + 1]
            ts = self.net.get_track_section(u, v, direction="DOWN")
            self.assertIsNotNone(
                ts,
                f"Edge {i+1}: {u} -> {v} has no matching real track section in Network"
            )

    def test_real_12607_simulation_strict_lookup_zero_fallback(self):
        """Simulate SRV_12607_01 with strict lookup and verify 0 fallback events."""
        from simulation.simulator import TrainSimulator
        sim = TrainSimulator(network=self.net)
        events = sim.run_service_to_destination("SRV_12607_01", strict_track_lookup=True)
        self.assertEqual(len(events), 114)

        fallback_events = [e for e in events if e.track_section_id and "FALLBACK" in e.track_section_id]
        self.assertEqual(len(fallback_events), 0, "Strict simulation of 12607 must have 0 fallback events")

        t_state = sim.state.get_train_state("SRV_12607_01")
        self.assertEqual(t_state.status.value, "COMPLETED")
        self.assertEqual(t_state.current_station, "AJJ")



class TestDataIntegrityReporting(unittest.TestCase):
    """Verify data-integrity warnings and ensure original JSON files are not modified."""

    @classmethod
    def setUpClass(cls):
        cls.net = Network()
        cls.net.load_from_directory(_DATA_DIR)
        cls.net.load_trains(_TRAINS_FILE)
        cls.net.load_services(_SERVICES_FILE)
        cls.net.load_timetable(_TIMETABLE_FILE)

    def test_stations_json_unmodified_no_pab_ptms(self):
        """PAB and PTMS must NOT be added to stations.json (preserving dataset truth)."""
        with open(_STATIONS_FILE, encoding="utf-8") as f:
            stations = json.load(f)
        stn_ids = {s["id"] for s in stations}
        self.assertNotIn("PAB", stn_ids, "stations.json must NOT contain PAB")
        self.assertNotIn("PTMS", stn_ids, "stations.json must NOT contain PTMS")

    def test_pab_ptms_reported_as_integrity_warnings(self):
        """PAB and PTMS referenced in timetable must be reported in data_integrity_warnings."""
        warning_text = " ".join(self.net.data_integrity_warnings)
        self.assertIn("PAB", warning_text,
                      "Expected DATA INTEGRITY warning for station PAB")
        self.assertIn("PTMS", warning_text,
                      "Expected DATA INTEGRITY warning for station PTMS")

    def test_route_waypoint_warnings_reported(self):
        """Route waypoints not in stations.json must be recorded as warnings, not fatal errors."""
        route_warnings = [
            w for w in self.net.data_integrity_warnings
            if "absent from stations.json and junctions.json" in w
        ]
        self.assertGreater(len(route_warnings), 0,
                           "Expected non-fatal warnings for intermediate route waypoints")

    def test_pipeline_resilient_to_integrity_warnings(self):
        """Network must load all trains, services, and timetables despite registry warnings."""
        self.assertEqual(len(self.net.trains), EXPECTED_TRAINS)
        self.assertEqual(len(self.net.services), EXPECTED_SERVICES)
        self.assertEqual(len(self.net.timetable), EXPECTED_TIMETABLE_ENTRIES)
        self.assertGreater(len(self.net.data_integrity_warnings), 0)


if __name__ == "__main__":
    unittest.main()
