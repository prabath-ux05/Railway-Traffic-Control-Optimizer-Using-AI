import json
import os
import glob
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


# ---------------------------------------------------------------------------
# Infrastructure domain models
# ---------------------------------------------------------------------------

@dataclass
class Station:
    id: str
    name: str
    station_type: str
    platform_count: int


@dataclass
class Platform:
    id: str
    station_id: str
    platform_number: int
    platform_type: str
    capacity: int


@dataclass
class TrackSection:
    id: str
    from_node: str
    to_node: str
    direction: str
    track_type: str
    number_of_tracks: int
    travel_time_minutes: float
    capacity: int
    minimum_headway_minutes: float


@dataclass
class Junction:
    id: str
    name: str
    junction_type: str
    connected_routes: List[str]   # route IDs served by this junction (from JSON connected_routes)
    station_id: Optional[str] = None
    capacity: int = 1


@dataclass
class Route:
    id: str
    name: str
    origin: str
    destination: str
    service_type: str
    ordered_nodes: List[str]


# ---------------------------------------------------------------------------
# Train / Service / Timetable domain models
# ---------------------------------------------------------------------------

@dataclass
class Train:
    """Physical rolling-stock unit."""
    id: str           # normalized from train_id in JSON
    name: str         # normalized from train_name in JSON
    train_number: str # e.g. "12607"
    train_type: str   # normalized from service_type in JSON; e.g. "SUBURBAN_EMU", "EXPRESS"


@dataclass
class Service:
    """A scheduled operating pattern: a specific train on a specific route."""
    id: str               # Mapped from service_id
    train_id: str         # → trains registry
    origin: str
    destination: str
    route_id: str         # → routes registry
    operating_days: List[str]
    priority_class: str
    delay_penalty_weight: float
    simulation_profile: str
    active: bool = True
    exclusion_reason: Optional[str] = None


@dataclass
class TimetableEntry:
    """One stop in a service's timetable."""
    service_id: str            # → services registry
    station_id: str            # → stations registry
    arrival: Optional[str]     # "HH:MM", null at origin; normalized from scheduled_arrival
    departure: Optional[str]   # "HH:MM", null at terminus; normalized from scheduled_departure
    stop_sequence: int         # derived from file-order position per service (1-indexed)
    commercial_stop: bool = True  # preserved from dataset


# ---------------------------------------------------------------------------
# Network: loader + validator
# ---------------------------------------------------------------------------

class Network:
    def __init__(self):
        # Infrastructure
        self.stations: Dict[str, Station] = {}
        self.platforms: Dict[str, Platform] = {}
        self.track_sections: Dict[str, TrackSection] = {}
        self.junctions: Dict[str, Junction] = {}
        self.routes: Dict[str, Route] = {}

        # Train / service / timetable
        self.trains: Dict[str, Train] = {}
        self.services: Dict[str, Service] = {}
        self.timetable: List[TimetableEntry] = []

        # Internal: per-service stop counter used when deriving stop_sequence
        self._timetable_seq_counter: Dict[str, int] = {}

        # Data quality: non-fatal issues discovered during load/validation
        self.data_integrity_warnings: List[str] = []

        # Provenance: timetable row sources and dataset integrity
        self.timetable_raw_sources: Dict[str, int] = defaultdict(int)
        self.timetable_domain_sources: Dict[str, int] = defaultdict(int)
        self.timetable_data_sources: Dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # Public: infrastructure loader (unchanged behaviour)
    # ------------------------------------------------------------------

    def load_from_directory(self, data_dir: str):
        self._load_file(data_dir, "stations.json", self._parse_station)
        self._load_file(data_dir, "platforms.json", self._parse_platform)
        self._load_file(data_dir, "junctions.json", self._parse_junction)
        self._load_file(data_dir, "routes.json", self._parse_route)
        self.load_track_sections(data_dir)

        self._validate_network()

    # ------------------------------------------------------------------
    # Public: train / service / timetable loaders
    # ------------------------------------------------------------------

    def load_trains(self, filepath: str):
        """Load trains from *filepath*, validate uniqueness."""
        self._load_json_list(filepath, self._parse_train)

    def load_services(self, filepath: str):
        """Load services, validate train_id → trains and route_id → routes."""
        self._load_json_list(filepath, self._parse_service)
        self._validate_service_references()

    def load_timetable(self, filepath: str):
        """Load timetable entries, validate all cross-references and coverage."""
        self._load_json_list(filepath, self._parse_timetable_entry)
        self._validate_timetable()

    def get_track_section(
        self,
        from_node: str,
        to_node: str,
        direction: Optional[str] = None,
    ) -> Optional[TrackSection]:
        """Look up a directional track section between two nodes.

        Args:
            from_node: Starting station/junction ID.
            to_node: Ending station/junction ID.
            direction: Optional direction filter ('UP', 'DOWN', 'BOTH', 'BIDIRECTIONAL').

        Returns:
            Matching TrackSection if found, otherwise None.
        """
        candidates = [
            ts for ts in self.track_sections.values()
            if ts.from_node == from_node and ts.to_node == to_node
        ]
        if not candidates:
            return None

        if direction is not None:
            target_dir = direction.upper()
            for ts in candidates:
                ts_dir = ts.direction.upper() if ts.direction else ""
                if ts_dir == target_dir or ts_dir in ("BOTH", "BIDIRECTIONAL"):
                    return ts

        return candidates[0]

    # ------------------------------------------------------------------
    # Public & Internal: track-section loader
    # ------------------------------------------------------------------

    def load_track_sections(self, path_or_dir: str):
        """Load track sections from a corridor directory, flat file, or auto-discover.

        Discovery order:
        1. If path_or_dir is a file -> parse that single file.
        2. If path_or_dir/track_sections/ directory exists -> load all *.json within it.
        3. If path_or_dir is a track_sections directory containing corridor files -> load all *.json.
        4. If <parent_of_path_or_dir>/track_sections/ directory exists -> load all *.json within it.
        5. If path_or_dir/track_sections.json flat file exists -> load that file.
        """
        if os.path.isfile(path_or_dir):
            self._load_track_section_file(path_or_dir)
            return

        if os.path.isdir(path_or_dir):
            # 1. Direct subdirectory: <path_or_dir>/track_sections/
            subdir = os.path.join(path_or_dir, "track_sections")
            if os.path.isdir(subdir):
                corridor_files = sorted(glob.glob(os.path.join(subdir, "*.json")))
                if corridor_files:
                    for filepath in corridor_files:
                        self._load_track_section_file(filepath)
                    return

            # 2. Direct JSON corridor files in path_or_dir (e.g. 'data/track_sections')
            corridor_files = sorted(glob.glob(os.path.join(path_or_dir, "*.json")))
            if corridor_files and any(os.path.basename(f).endswith("_track_sections.json") for f in corridor_files):
                for filepath in corridor_files:
                    self._load_track_section_file(filepath)
                return

            # 3. Sibling track_sections directory (e.g. data/infrastructure -> data/track_sections)
            sibling_dir = os.path.join(os.path.dirname(os.path.abspath(path_or_dir)), "track_sections")
            if os.path.isdir(sibling_dir):
                corridor_files = sorted(glob.glob(os.path.join(sibling_dir, "*.json")))
                if corridor_files:
                    for filepath in corridor_files:
                        self._load_track_section_file(filepath)
                    return

            # 4. Flat file in path_or_dir (used by unit tests with temp directories)
            flat_file = os.path.join(path_or_dir, "track_sections.json")
            if os.path.isfile(flat_file):
                self._load_track_section_file(flat_file)
                return

        # Fallback if flat file exists without os.path.isdir
        flat_file = os.path.join(path_or_dir, "track_sections.json")
        if os.path.exists(flat_file):
            self._load_file(path_or_dir, "track_sections.json", self._parse_track_section)

    def _load_track_sections(self, data_dir: str):
        """Internal alias for backward compatibility."""
        self.load_track_sections(data_dir)


    def _load_track_section_file(self, filepath: str):
        """Parse a single corridor track-section file, skipping empty files."""
        if os.path.getsize(filepath) == 0:
            return  # Empty file — corridor not yet populated; skip silently

        filename = os.path.basename(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON file {filename}: {e}")

        if not isinstance(data, list):
            raise ValueError(f"Track-section file {filename} must contain a JSON array")

        for item in data:
            self._parse_track_section(item)

    # ------------------------------------------------------------------
    # Private: generic file helpers
    # ------------------------------------------------------------------

    def _load_file(self, data_dir: str, filename: str, parser_func):
        """Load a JSON array from data_dir/filename, calling parser_func per item."""
        filepath = os.path.join(data_dir, filename)
        if not os.path.exists(filepath):
            print(f"Warning: Data file not found - {filepath}")
            return

        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                for item in data:
                    parser_func(item)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON file {filename}: {e}")

    def _load_json_list(self, filepath: str, parser_func):
        """Load a JSON array from an explicit filepath, calling parser_func per item."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Data file not found: {filepath}")

        filename = os.path.basename(filepath)
        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse JSON file {filename}: {e}")

        if not isinstance(data, list):
            raise ValueError(f"{filename} must contain a JSON array")

        for item in data:
            parser_func(item)

    # ------------------------------------------------------------------
    # Private: infrastructure parsers
    # ------------------------------------------------------------------

    def _parse_station(self, data: dict):
        if data["id"] in self.stations or data["id"] in self.junctions:
            raise ValueError(f"Duplicate node ID detected: {data['id']}")
        self.stations[data["id"]] = Station(**data)

    def _parse_platform(self, data: dict):
        if data["id"] in self.platforms:
            raise ValueError(f"Duplicate platform ID detected: {data['id']}")
        self.platforms[data["id"]] = Platform(**data)

    def _parse_junction(self, data: dict):
        if data["id"] in self.junctions or data["id"] in self.stations:
            raise ValueError(f"Duplicate node ID detected: {data['id']}")
        # Normalize: keep only the fields in the Junction dataclass;
        # the real junctions.json has extra metadata (description,
        # simulation_role, data_source) that we safely handle.
        normalized = {
            "id":               data["id"],
            "name":             data["name"],
            "junction_type":    data["junction_type"],
            "connected_routes": data.get("connected_routes", []),
            "station_id":       data.get("station_id"),
            "capacity":         data.get("capacity", 1),
        }
        self.junctions[data["id"]] = Junction(**normalized)

    @staticmethod
    def _normalize_track_section_data(data: dict) -> dict:
        """Normalize the two field-name schemas used by track-section files.

        The canonical dataclass fields are:
            from_node, to_node, travel_time_minutes, minimum_headway_minutes,
            number_of_tracks

        The real corridor files use shorter aliases (and omit number_of_tracks):
            from, to, travel_time_min, headway_min
        """
        d = dict(data)
        if "from" in d and "from_node" not in d:
            d["from_node"] = d.pop("from")
        if "to" in d and "to_node" not in d:
            d["to_node"] = d.pop("to")
        if "travel_time_min" in d and "travel_time_minutes" not in d:
            d["travel_time_minutes"] = d.pop("travel_time_min")
        if "headway_min" in d and "minimum_headway_minutes" not in d:
            d["minimum_headway_minutes"] = d.pop("headway_min")
        d.setdefault("number_of_tracks", 1)
        return d

    def _parse_track_section(self, data: dict):
        d = self._normalize_track_section_data(data)
        if d["id"] in self.track_sections:
            raise ValueError(f"Duplicate track section ID detected: {d['id']}")
        self.track_sections[d["id"]] = TrackSection(**d)

    def _parse_route(self, data: dict):
        if data["id"] in self.routes:
            raise ValueError(f"Duplicate route ID detected: {data['id']}")
        self.routes[data["id"]] = Route(**data)

    # ------------------------------------------------------------------
    # Private: train / service / timetable parsers
    # ------------------------------------------------------------------

    def _parse_train(self, data: dict):
        d = dict(data)
        # Normalize JSON field names → runtime model field names
        # trains.json schema: train_id, train_name, train_number, service_type
        if "train_id" in d and "id" not in d:
            d["id"] = d.pop("train_id")
        if "train_name" in d and "name" not in d:
            d["name"] = d.pop("train_name")
        if "service_type" in d and "train_type" not in d:
            d["train_type"] = d.pop("service_type")
        if d["id"] in self.trains:
            raise ValueError(f"Duplicate train ID detected: {d['id']}")
        # Keep only the fields declared in the Train dataclass
        allowed = {"id", "name", "train_number", "train_type"}
        d = {k: v for k, v in d.items() if k in allowed}
        self.trains[d["id"]] = Train(**d)

    def _parse_service(self, data: dict):
        d = dict(data)
        if "service_id" in d and "id" not in d:
            d["id"] = d.pop("service_id")
        if d["id"] in self.services:
            raise ValueError(f"Duplicate service ID detected: {d['id']}")
        self.services[d["id"]] = Service(**d)

    def _parse_timetable_entry(self, data: dict):
        d = dict(data)
        # Capture raw data provenance before stripping
        if "source" in d and d["source"]:
            src = str(d["source"])
            self.timetable_raw_sources[src] += 1
            domain = src.replace("https://", "").replace("http://", "").split("/")[0]
            self.timetable_domain_sources[domain] += 1
        if "data_source" in d and d["data_source"]:
            self.timetable_data_sources[str(d["data_source"])] += 1

        # Normalize field names: timetable.json uses scheduled_arrival/departure
        if "scheduled_arrival" in d and "arrival" not in d:
            d["arrival"] = d.pop("scheduled_arrival")
        if "scheduled_departure" in d and "departure" not in d:
            d["departure"] = d.pop("scheduled_departure")
        # Derive stop_sequence from per-service file order (1-indexed)
        svc_id = d["service_id"]
        self._timetable_seq_counter[svc_id] = (
            self._timetable_seq_counter.get(svc_id, 0) + 1
        )
        d["stop_sequence"] = self._timetable_seq_counter[svc_id]
        # Strip data-provenance metadata not needed in the runtime model
        allowed = {"service_id", "station_id", "arrival", "departure",
                   "stop_sequence", "commercial_stop"}
        d = {k: v for k, v in d.items() if k in allowed}
        self.timetable.append(TimetableEntry(**d))

    # ------------------------------------------------------------------
    # Private: validators
    # ------------------------------------------------------------------

    def _validate_network(self):
        # Validate platforms reference valid stations
        for platform in self.platforms.values():
            if platform.station_id not in self.stations:
                raise ValueError(
                    f"Platform {platform.id} references non-existent station: "
                    f"{platform.station_id}"
                )

        # Validate track sections reference valid nodes (stations, junctions, or route waypoints)
        all_nodes = set(self.stations.keys()) | set(self.junctions.keys())
        all_route_nodes = set()
        for route in self.routes.values():
            all_route_nodes.update(route.ordered_nodes)
        all_valid_nodes = all_nodes | all_route_nodes

        for track in self.track_sections.values():
            if track.from_node not in all_valid_nodes:
                raise ValueError(
                    f"Track section {track.id} references non-existent from_node: "
                    f"{track.from_node}"
                )
            if track.to_node not in all_valid_nodes:
                raise ValueError(
                    f"Track section {track.id} references non-existent to_node: "
                    f"{track.to_node}"
                )
            if track.from_node not in all_nodes:
                self.data_integrity_warnings.append(
                    f"DATA INTEGRITY: track section '{track.id}' references from_node '{track.from_node}' "
                    f"absent from stations.json and junctions.json"
                )
            if track.to_node not in all_nodes:
                self.data_integrity_warnings.append(
                    f"DATA INTEGRITY: track section '{track.id}' references to_node '{track.to_node}' "
                    f"absent from stations.json and junctions.json"
                )


        # Validate junction connected_routes against the loaded route registry
        for junction in self.junctions.values():
            for route_id in junction.connected_routes:
                if route_id not in self.routes:
                    self.data_integrity_warnings.append(
                        f"Junction {junction.id} references route not in routes.json: "
                        f"{route_id}"
                    )

        # Validate routes reference valid nodes — waypoints absent from stations/junctions
        # are reported as data-integrity warnings (they are real intermediate halts
        # not yet registered in stations.json) rather than hard errors.
        for route in self.routes.values():
            for node in route.ordered_nodes:
                if node not in all_nodes:
                    self.data_integrity_warnings.append(
                        f"DATA INTEGRITY: route '{route.id}' references node '{node}' "
                        f"absent from stations.json and junctions.json"
                    )

    def _validate_service_references(self):
        """Check that each service's train_id and route_id exist."""
        for svc in self.services.values():
            if svc.train_id not in self.trains:
                raise ValueError(
                    f"Service {svc.id} references non-existent train_id: "
                    f"{svc.train_id}"
                )
            if svc.route_id not in self.routes:
                raise ValueError(
                    f"Service {svc.id} references non-existent route_id: "
                    f"{svc.route_id}"
                )

    def _validate_timetable(self):
        """Validate all timetable entries.

        Per-service checks:
        1. service_id exists in services.
        2. station_id exists in stations.
        3. stop_sequence is strictly increasing.
        4. All stops form a subsequence of the service's route.ordered_nodes.
        5. Each consecutive stop pair (A → B) is covered by at least one
           TrackSection with from_node=A and to_node=B (any track_type,
           including THROAT_SEGMENT).
        """
        # Pre-build edge set for O(1) coverage lookups
        track_edges = frozenset(
            (ts.from_node, ts.to_node) for ts in self.track_sections.values()
        )

        # Validate individual entries; collect station gaps as data-integrity warnings
        # rather than hard errors so that partial datasets remain loadable.
        unknown_station_keys: set = set()  # (service_id, station_id) pairs to skip
        for entry in self.timetable:
            if entry.service_id not in self.services:
                raise ValueError(
                    f"Timetable entry references non-existent service_id: "
                    f"{entry.service_id}"
                )
            if entry.station_id not in self.stations:
                key = (entry.service_id, entry.station_id)
                if key not in unknown_station_keys:
                    self.data_integrity_warnings.append(
                        f"DATA INTEGRITY: station '{entry.station_id}' referenced in "
                        f"timetable (service {entry.service_id}, "
                        f"stop_seq {entry.stop_sequence}) is absent from stations.json "
                        f"— entry excluded from route/track-coverage validation"
                    )
                    unknown_station_keys.add(key)

        # Group by service_id for per-service checks;
        # exclude entries whose station_id is not in the registry
        entries_by_service: Dict[str, List[TimetableEntry]] = defaultdict(list)
        for entry in self.timetable:
            if (entry.service_id, entry.station_id) not in unknown_station_keys:
                entries_by_service[entry.service_id].append(entry)

        for svc_id, entries in entries_by_service.items():
            service = self.services[svc_id]
            route = self.routes[service.route_id]

            # Sort by stop_sequence
            sorted_entries = sorted(entries, key=lambda e: e.stop_sequence)
            seqs = [e.stop_sequence for e in sorted_entries]
            station_ids = [e.station_id for e in sorted_entries]

            # 3. Strictly increasing stop_sequence
            for i in range(1, len(seqs)):
                if seqs[i] <= seqs[i - 1]:
                    raise ValueError(
                        f"Service {svc_id}: stop_sequence must be strictly "
                        f"increasing; got {seqs[i-1]} then {seqs[i]}"
                    )

            # 4. Stops must be a subsequence of route.ordered_nodes
            route_nodes = route.ordered_nodes
            pos = 0
            for stn in station_ids:
                while pos < len(route_nodes) and route_nodes[pos] != stn:
                    pos += 1
                if pos >= len(route_nodes):
                    raise ValueError(
                        f"Service {svc_id}: timetable station '{stn}' not found "
                        f"in route '{route.id}' ordered_nodes in the correct order"
                    )
                pos += 1

            # 5. Track-section coverage between consecutive stops.
            # Reported as a warning when no track-section data is loaded yet;
            # once track_sections/ is populated this can be promoted to a hard error.
            if track_edges:   # only enforce when we actually have track data
                for i in range(len(station_ids) - 1):
                    a, b = station_ids[i], station_ids[i + 1]
                    if (a, b) not in track_edges:
                        self.data_integrity_warnings.append(
                            f"DATA INTEGRITY: service {svc_id}: no track section covers "
                            f"'{a}' → '{b}'"
                        )
            else:
                pass  # no track data loaded — skip coverage check silently

        # Derive active / excluded status from published timetable evidence
        services_with_tt = {e.service_id for e in self.timetable}
        for svc in self.services.values():
            if svc.id in services_with_tt:
                svc.active = True
                svc.exclusion_reason = None
            else:
                svc.active = False
                svc.exclusion_reason = "No published timetable evidence"

    @property
    def active_services(self) -> Dict[str, Service]:
        """Services that have at least one published timetable entry."""
        return {s_id: s for s_id, s in self.services.items() if s.active}

    @property
    def excluded_services(self) -> Dict[str, Service]:
        """Services excluded due to lack of published timetable evidence."""
        return {s_id: s for s_id, s in self.services.items() if not s.active}

    def get_integrity_summary(self) -> Dict[str, int]:
        """Categorize and count data integrity warnings."""
        summary = {
            "station_record_missing_for_route_node": 0,
            "no_track_section_for_hop": 0,
            "timetable_references_unknown_station": 0,
            "junction_references_unknown_route": 0,
            "other": 0,
        }
        for w in self.data_integrity_warnings:
            if "absent from stations.json and junctions.json" in w:
                summary["station_record_missing_for_route_node"] += 1
            elif "no track section covers" in w:
                summary["no_track_section_for_hop"] += 1
            elif "absent from stations.json — entry excluded" in w:
                summary["timetable_references_unknown_station"] += 1
            elif "references route not in routes.json" in w:
                summary["junction_references_unknown_route"] += 1
            else:
                summary["other"] += 1
        return summary

    def get_data_provenance(self) -> Dict[str, Any]:
        """Return dataset provenance including timetable sources, snapshot date, and file hashes."""
        import hashlib, glob
        hashes = {}
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(repo_root, "data")
        for json_file in sorted(glob.glob(os.path.join(data_dir, "**", "*.json"), recursive=True)):
            rel_path = os.path.relpath(json_file, data_dir).replace("\\", "/")
            if "evaluation" in rel_path or "proposals" in rel_path or "runtime" in rel_path or ".system_generated" in rel_path:
                continue
            with open(json_file, "rb") as fp:
                hashes[rel_path] = hashlib.sha256(fp.read()).hexdigest()

        return {
            "snapshot_date": "2026-09-26",
            "timetable_sources": dict(self.timetable_domain_sources),
            "timetable_raw_sources": dict(self.timetable_raw_sources),
            "timetable_data_sources": dict(self.timetable_data_sources),
            "dataset_sha256_hashes": hashes,
        }

    # ------------------------------------------------------------------
    # Reporting
    # ------------------------------------------------------------------

    def print_summary(self):
        print("Railway Network Summary:")
        print("-" * 30)
        print(f"Total Stations:          {len(self.stations)}")
        print(f"Total Platforms:         {len(self.platforms)}")
        print(f"Total Junctions:         {len(self.junctions)}")
        print(f"Total Track Sections:    {len(self.track_sections)}")
        print(f"Total Routes:            {len(self.routes)}")
        print(f"Total Trains:            {len(self.trains)}")
        print(f"Total Services:          {len(self.services)}")
        print(f"Total Timetable Entries: {len(self.timetable)}")
        print("-" * 30)
        if self.data_integrity_warnings:
            print(f"Data Integrity Warnings: {len(self.data_integrity_warnings)}")
            for w in self.data_integrity_warnings:
                print(f"  ⚠  {w}")
        else:
            print("Data Integrity Warnings: 0")
