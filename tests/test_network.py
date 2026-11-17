import unittest
import tempfile
import json
import os
import shutil
from simulation.network import Network

class TestNetworkLoader(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def write_json(self, filename, data):
        with open(os.path.join(self.test_dir, filename), 'w') as f:
            json.dump(data, f)

    def test_load_valid_network(self):
        self.write_json('stations.json', [
            {"id": "MAS", "name": "Chennai Central", "station_type": "Terminal", "platform_count": 15},
            {"id": "BBQ", "name": "Basin Bridge", "station_type": "Junction", "platform_count": 6}
        ])
        self.write_json('platforms.json', [
            {"id": "MAS_P1", "station_id": "MAS", "platform_number": 1, "platform_type": "Mainline", "capacity": 24}
        ])
        self.write_json('track_sections.json', [
            {"id": "MAS_BBQ_UP", "from_node": "MAS", "to_node": "BBQ", "direction": "UP", "track_type": "Main", "number_of_tracks": 2, "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0}
        ])
        self.write_json('junctions.json', [])
        self.write_json('routes.json', [
            {"id": "RT_MAS_BBQ", "name": "MAS to BBQ", "origin": "MAS", "destination": "BBQ", "service_type": "Suburban", "ordered_nodes": ["MAS", "BBQ"]}
        ])

        net = Network()
        net.load_from_directory(self.test_dir)
        
        self.assertEqual(len(net.stations), 2)
        self.assertEqual(len(net.platforms), 1)
        self.assertEqual(len(net.track_sections), 1)
        self.assertEqual(len(net.routes), 1)

    def test_duplicate_station_id(self):
        self.write_json('stations.json', [
            {"id": "MAS", "name": "Chennai Central", "station_type": "Terminal", "platform_count": 15},
            {"id": "MAS", "name": "Chennai Central Duplicate", "station_type": "Terminal", "platform_count": 15}
        ])
        net = Network()
        with self.assertRaisesRegex(ValueError, "Duplicate node ID detected: MAS"):
            net.load_from_directory(self.test_dir)

    def test_invalid_platform_reference(self):
        self.write_json('stations.json', [])
        self.write_json('platforms.json', [
            {"id": "INVALID_P1", "station_id": "NONEXISTENT", "platform_number": 1, "platform_type": "Mainline", "capacity": 12}
        ])
        net = Network()
        with self.assertRaisesRegex(ValueError, "references non-existent station: NONEXISTENT"):
            net.load_from_directory(self.test_dir)

    def test_invalid_track_node_reference(self):
        self.write_json('stations.json', [
            {"id": "MAS", "name": "Chennai Central", "station_type": "Terminal", "platform_count": 15}
        ])
        self.write_json('track_sections.json', [
            {"id": "TRK_1", "from_node": "MAS", "to_node": "NONEXISTENT", "direction": "UP", "track_type": "Main", "number_of_tracks": 1, "travel_time_minutes": 5.0, "capacity": 10, "minimum_headway_minutes": 3.0}
        ])
        net = Network()
        with self.assertRaisesRegex(ValueError, "references non-existent to_node: NONEXISTENT"):
            net.load_from_directory(self.test_dir)

class TestTrackSectionSubdirectoryLoader(unittest.TestCase):
    """Tests for the corridor-file (subdirectory) track-section loading path."""

    # Minimal topology reused across tests
    _STATIONS = [
        {"id": "MAS", "name": "Chennai Central", "station_type": "Terminal", "platform_count": 15},
        {"id": "BBQ", "name": "Basin Bridge",    "station_type": "Junction Station", "platform_count": 6},
        {"id": "KOK", "name": "Korukkupet",      "station_type": "Junction Station", "platform_count": 3},
    ]

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ts_dir = os.path.join(self.test_dir, "track_sections")
        os.makedirs(self.ts_dir)

        # Write shared topology files
        self._write(self.test_dir, "stations.json",  self._STATIONS)
        self._write(self.test_dir, "platforms.json", [])
        self._write(self.test_dir, "junctions.json", [])
        self._write(self.test_dir, "routes.json",    [])

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write(self, directory, filename, data):
        with open(os.path.join(directory, filename), 'w') as f:
            json.dump(data, f)

    def _write_ts(self, filename, data):
        """Write a corridor file into the track_sections subdirectory."""
        self._write(self.ts_dir, filename, data)

    # ------------------------------------------------------------------
    # 1. Subdirectory files load successfully
    # ------------------------------------------------------------------
    def test_subdirectory_files_load(self):
        self._write_ts("north_track_sections.json", [
            {"id": "MAS_BBQ_UP",   "from_node": "MAS", "to_node": "BBQ",
             "direction": "UP",   "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0},
            {"id": "BBQ_MAS_DOWN", "from_node": "BBQ", "to_node": "MAS",
             "direction": "DOWN", "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0},
        ])

        net = Network()
        net.load_from_directory(self.test_dir)
        self.assertEqual(len(net.track_sections), 2)
        self.assertIn("MAS_BBQ_UP",   net.track_sections)
        self.assertIn("BBQ_MAS_DOWN", net.track_sections)

    # ------------------------------------------------------------------
    # 2. Global track-section IDs are unique across corridor files
    # ------------------------------------------------------------------
    def test_global_id_uniqueness(self):
        self._write_ts("north_track_sections.json", [
            {"id": "MAS_BBQ_UP", "from_node": "MAS", "to_node": "BBQ",
             "direction": "UP", "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0},
        ])
        # Same ID appearing in a second corridor file must be rejected
        self._write_ts("west_track_sections.json", [
            {"id": "MAS_BBQ_UP", "from_node": "MAS", "to_node": "BBQ",
             "direction": "UP", "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0},
        ])

        net = Network()
        with self.assertRaisesRegex(ValueError, "Duplicate track section ID detected: MAS_BBQ_UP"):
            net.load_from_directory(self.test_dir)

    # ------------------------------------------------------------------
    # 3. Both UP and DOWN directions are preserved (not deduplicated)
    # ------------------------------------------------------------------
    def test_both_directions_preserved(self):
        self._write_ts("north_track_sections.json", [
            {"id": "MAS_BBQ_UP",   "from_node": "MAS", "to_node": "BBQ",
             "direction": "UP",   "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0},
            {"id": "BBQ_MAS_DOWN", "from_node": "BBQ", "to_node": "MAS",
             "direction": "DOWN", "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0},
        ])

        net = Network()
        net.load_from_directory(self.test_dir)

        up   = net.track_sections["MAS_BBQ_UP"]
        down = net.track_sections["BBQ_MAS_DOWN"]
        self.assertEqual(up.direction,   "UP")
        self.assertEqual(down.direction, "DOWN")
        self.assertEqual(up.from_node,   "MAS")
        self.assertEqual(down.from_node, "BBQ")

    # ------------------------------------------------------------------
    # 4. Empty corridor files are tolerated silently
    # ------------------------------------------------------------------
    def test_empty_corridor_files_skipped(self):
        # Create a genuinely empty file (0 bytes)
        open(os.path.join(self.ts_dir, "west_track_sections.json"), 'w').close()
        # And a populated one
        self._write_ts("north_track_sections.json", [
            {"id": "MAS_BBQ_UP", "from_node": "MAS", "to_node": "BBQ",
             "direction": "UP", "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0},
        ])

        net = Network()
        net.load_from_directory(self.test_dir)   # must not raise
        self.assertEqual(len(net.track_sections), 1)

    # ------------------------------------------------------------------
    # 5. Multiple corridor files merge correctly
    # ------------------------------------------------------------------
    def test_multiple_corridor_files_merge(self):
        self._write_ts("north_track_sections.json", [
            {"id": "MAS_BBQ_UP",   "from_node": "MAS", "to_node": "BBQ",
             "direction": "UP",   "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0},
        ])
        self._write_ts("west_track_sections.json", [
            {"id": "BBQ_KOK_UP",   "from_node": "BBQ", "to_node": "KOK",
             "direction": "UP",   "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 4.0, "capacity": 8,  "minimum_headway_minutes": 3.0},
            {"id": "KOK_BBQ_DOWN", "from_node": "KOK", "to_node": "BBQ",
             "direction": "DOWN", "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 4.0, "capacity": 8,  "minimum_headway_minutes": 3.0},
        ])

        net = Network()
        net.load_from_directory(self.test_dir)
        self.assertEqual(len(net.track_sections), 3)
        self.assertIn("MAS_BBQ_UP",   net.track_sections)
        self.assertIn("BBQ_KOK_UP",   net.track_sections)
        self.assertIn("KOK_BBQ_DOWN", net.track_sections)

    # ------------------------------------------------------------------
    # 6. Empty junctions.json (current state of real data) is valid
    # ------------------------------------------------------------------
    def test_empty_junctions_valid(self):
        # junctions.json is already written as [] in setUp
        self._write_ts("north_track_sections.json", [
            {"id": "MAS_BBQ_UP", "from_node": "MAS", "to_node": "BBQ",
             "direction": "UP", "track_type": "Main", "number_of_tracks": 2,
             "travel_time_minutes": 3.5, "capacity": 10, "minimum_headway_minutes": 3.0},
        ])

        net = Network()
        net.load_from_directory(self.test_dir)
        self.assertEqual(len(net.junctions), 0)


if __name__ == '__main__':
    unittest.main()
