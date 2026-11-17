"""
simulation/conflicts.py
~~~~~~~~~~~~~~~~~~~~~~~
Railway conflict detection module for railway traffic optimizer.

Identifies traffic conflicts and safety/operational violations across the network:
1. SAME_TRACK_SECTION: Concurrent section occupancy exceeding section capacity.
2. INSUFFICIENT_HEADWAY: Successive trains on the same section violating minimum headway separation.
3. SHARED_JUNCTION: Multiple trains concurrently contending for the same junction/throat resource.
4. INCOMPATIBLE_MOVEMENTS: Opposing or intersecting conflicting movements attempting to use the same resource.

All conflicts are represented deterministically using the Conflict model.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.network import Junction, Network, Route, TrackSection
from simulation.state import SimulationState, TrackSectionOccupancy, TrainRuntimeState


class ConflictType(str, Enum):
    """Categories of detected railway traffic conflicts."""
    SAME_TRACK_SECTION     = "SAME_TRACK_SECTION"       # Exceeded track section capacity
    INSUFFICIENT_HEADWAY   = "INSUFFICIENT_HEADWAY"     # Temporal headway separation violation
    SHARED_JUNCTION        = "SHARED_JUNCTION"          # Contention at shared junction/throat
    INCOMPATIBLE_MOVEMENTS = "INCOMPATIBLE_MOVEMENTS"   # Opposing/intersecting conflicting moves


class ConflictSeverity(str, Enum):
    """Severity classification for railway conflicts."""
    CRITICAL = "CRITICAL"   # Imminent collision / head-on opposing movement / severe safety violation
    MAJOR    = "MAJOR"      # Capacity breach / junction contention / severe delay propagation
    WARNING  = "WARNING"    # Headway infringement / non-blocking resource contention
    MINOR    = "MINOR"      # Informational conflict


@dataclass
class Conflict:
    """Represents a single detected railway traffic conflict.

    Attributes:
        conflict_id: Unique deterministic identifier (e.g. 'CONF_0001').
        conflict_type: Category (ConflictType or string).
        affected_service_ids: List of service IDs involved in the conflict.
        affected_train_ids: List of physical train IDs involved.
        resource_id: Identifier of the disputed infrastructure resource (section, junction, node).
        conflict_time: Timestamp of conflict occurrence in minutes from midnight.
        severity: ConflictSeverity tier (CRITICAL, MAJOR, WARNING, MINOR).
        description: Human-readable narrative detailing the conflict condition.
        metadata: Contextual diagnostic data (e.g., observed vs minimum headway, directions, capacities).
    """
    conflict_id: str
    conflict_type: ConflictType
    affected_service_ids: List[str]
    affected_train_ids: List[str]
    resource_id: str
    conflict_time: float
    severity: ConflictSeverity
    description: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if isinstance(self.conflict_type, str) and not isinstance(self.conflict_type, ConflictType):
            self.conflict_type = ConflictType(self.conflict_type)
        if isinstance(self.severity, str) and not isinstance(self.severity, ConflictSeverity):
            self.severity = ConflictSeverity(self.severity)
        if isinstance(self.conflict_time, (str, int)):
            self.conflict_time = time_to_minutes(self.conflict_time)

    @property
    def conflict_time_str(self) -> str:
        """Formatted timestamp 'HH:MM' of the conflict."""
        return minutes_to_time_str(self.conflict_time)

    @property
    def affected_services(self) -> List[str]:
        return self.affected_service_ids

    @property
    def affected_trains(self) -> List[str]:
        return self.affected_train_ids

    def to_dict(self) -> Dict[str, Any]:
        """Convert conflict record to a clean dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "affected_service_ids": self.affected_service_ids,
            "affected_train_ids": self.affected_train_ids,
            "resource_id": self.resource_id,
            "conflict_time": self.conflict_time,
            "conflict_time_str": self.conflict_time_str,
            "severity": self.severity.value,
            "description": self.description,
            "metadata": self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"Conflict(id='{self.conflict_id}', type={self.conflict_type.value}, "
            f"resource='{self.resource_id}', t={self.conflict_time_str}, "
            f"severity={self.severity.value}, services={self.affected_service_ids})"
        )


class ConflictDetector:
    """Deterministic detector for railway traffic conflicts.

    Inspects simulation states, track section occupancies, headway intervals,
    junction contention points, and directional compatibility.
    """

    def __init__(self, network: Optional[Network] = None):
        self.network = network
        self.conflicts: List[Conflict] = []
        self._conflict_counter: int = 0

    def reset(self):
        """Clear detected conflicts and reset ID generator."""
        self.conflicts.clear()
        self._conflict_counter = 0

    def _next_conflict_id(self) -> str:
        self._conflict_counter += 1
        return f"CONF_{self._conflict_counter:04d}"

    # ------------------------------------------------------------------
    # 1. Same Track Section Conflicts (Overcapacity)
    # ------------------------------------------------------------------

    def detect_same_section_conflicts(
        self,
        occupancies: List[TrackSectionOccupancy],
        capacity_map: Optional[Dict[str, int]] = None,
        default_capacity: int = 1,
    ) -> List[Conflict]:
        """Detect concurrent occupancy on any track section exceeding its capacity.

        Args:
            occupancies: List of TrackSectionOccupancy records.
            capacity_map: Optional section_id -> capacity mapping override.
            default_capacity: Default capacity if section not in network or map.

        Returns:
            List of detected SAME_TRACK_SECTION Conflict objects.
        """
        detected: List[Conflict] = []
        by_section: Dict[str, List[TrackSectionOccupancy]] = defaultdict(list)
        for occ in occupancies:
            by_section[occ.section_id].append(occ)

        for sec_id, occ_list in sorted(by_section.items()):
            # Determine section capacity
            cap = default_capacity
            if capacity_map and sec_id in capacity_map:
                cap = capacity_map[sec_id]
            elif self.network and sec_id in self.network.track_sections:
                cap = self.network.track_sections[sec_id].capacity

            if len(occ_list) <= cap:
                continue

            # Sweep-line over entry and exit times to find concurrent overlaps > cap
            # Event format: (time, is_exit (-1 or 1), occ)
            time_points: List[Tuple[float, int, TrackSectionOccupancy]] = []
            for occ in occ_list:
                exit_t = occ.actual_exit_time if occ.actual_exit_time is not None else (
                    occ.expected_exit_time if occ.expected_exit_time is not None else occ.entry_time + 3.0
                )
                time_points.append((occ.entry_time, 1, occ))    # 1 = enter
                time_points.append((exit_t, -1, occ))           # -1 = exit

            # Sort time points: by timestamp; if simultaneous, process exits (-1) before entries (1)
            time_points.sort(key=lambda item: (item[0], item[1]))

            active_occs: Set[str] = set()
            reported_groups: Set[Tuple[str, ...]] = set()

            for t, kind, occ in time_points:
                if kind == 1:
                    active_occs.add(occ.service_id)
                    if len(active_occs) > cap:
                        group_key = tuple(sorted(active_occs))
                        if group_key not in reported_groups:
                            reported_groups.add(group_key)
                            # Collect train IDs
                            train_map = {o.service_id: o.train_id for o in occ_list if o.service_id in active_occs}
                            sev = ConflictSeverity.CRITICAL if cap == 1 else ConflictSeverity.MAJOR
                            desc = (
                                f"Same track section overcapacity on '{sec_id}': "
                                f"{len(active_occs)} trains present ({', '.join(sorted(active_occs))}), "
                                f"exceeding section capacity of {cap}."
                            )
                            c = Conflict(
                                conflict_id=self._next_conflict_id(),
                                conflict_type=ConflictType.SAME_TRACK_SECTION,
                                affected_service_ids=sorted(list(active_occs)),
                                affected_train_ids=[train_map.get(s, "") for s in sorted(list(active_occs))],
                                resource_id=sec_id,
                                conflict_time=t,
                                severity=sev,
                                description=desc,
                                metadata={
                                    "capacity": cap,
                                    "concurrent_trains": len(active_occs),
                                    "section_id": sec_id,
                                },
                            )
                            detected.append(c)
                            self.conflicts.append(c)
                else:
                    active_occs.discard(occ.service_id)

        return detected

    # ------------------------------------------------------------------
    # 2. Insufficient Headway Conflicts
    # ------------------------------------------------------------------

    def detect_headway_conflicts(
        self,
        occupancies: List[TrackSectionOccupancy],
        min_headway_map: Optional[Dict[str, float]] = None,
        default_min_headway_minutes: float = 3.0,
    ) -> List[Conflict]:
        """Detect successive trains on the same section violating minimum headway separation.

        Args:
            occupancies: List of TrackSectionOccupancy records.
            min_headway_map: Optional section_id -> minimum headway mapping override.
            default_min_headway_minutes: Default headway if not specified in network.

        Returns:
            List of detected INSUFFICIENT_HEADWAY Conflict objects.
        """
        detected: List[Conflict] = []
        by_section: Dict[str, List[TrackSectionOccupancy]] = defaultdict(list)
        for occ in occupancies:
            by_section[occ.section_id].append(occ)

        for sec_id, occ_list in sorted(by_section.items()):
            if len(occ_list) < 2:
                continue

            # Determine minimum headway for this section
            min_headway = default_min_headway_minutes
            if min_headway_map and sec_id in min_headway_map:
                min_headway = min_headway_map[sec_id]
            elif self.network and sec_id in self.network.track_sections:
                sec_headway = self.network.track_sections[sec_id].minimum_headway_minutes
                if sec_headway > 0:
                    min_headway = sec_headway

            # Sort by entry time
            sorted_occs = sorted(occ_list, key=lambda o: (o.entry_time, o.service_id))

            for i in range(len(sorted_occs) - 1):
                first = sorted_occs[i]
                second = sorted_occs[i + 1]

                # Skip if it's the exact same service instance
                if first.service_id == second.service_id:
                    continue

                # Check if movement is in the same direction / consecutive entry
                delta_t = second.entry_time - first.entry_time

                # Check headway violation: 0 <= delta_t < min_headway
                if 0.0 <= delta_t < min_headway:
                    sev = ConflictSeverity.MAJOR if delta_t < (min_headway / 2.0) else ConflictSeverity.WARNING
                    desc = (
                        f"Insufficient headway on track section '{sec_id}': "
                        f"service '{second.service_id}' entered at {minutes_to_time_str(second.entry_time)} "
                        f"only {delta_t:.1f} min after service '{first.service_id}' (entered {minutes_to_time_str(first.entry_time)}). "
                        f"Minimum required headway is {min_headway:.1f} min."
                    )
                    c = Conflict(
                        conflict_id=self._next_conflict_id(),
                        conflict_type=ConflictType.INSUFFICIENT_HEADWAY,
                        affected_service_ids=[first.service_id, second.service_id],
                        affected_train_ids=[first.train_id, second.train_id],
                        resource_id=sec_id,
                        conflict_time=second.entry_time,
                        severity=sev,
                        description=desc,
                        metadata={
                            "actual_headway_min": delta_t,
                            "required_headway_min": min_headway,
                            "preceding_service": first.service_id,
                            "following_service": second.service_id,
                            "section_id": sec_id,
                        },
                    )
                    detected.append(c)
                    self.conflicts.append(c)

        return detected

    # ------------------------------------------------------------------
    # 3. Shared Junction / Resource Conflicts
    # ------------------------------------------------------------------

    def detect_junction_conflicts(
        self,
        node_occupancies: Optional[List[Dict[str, Any]]] = None,
        state: Optional[SimulationState] = None,
        junction_capacity_map: Optional[Dict[str, int]] = None,
        default_junction_capacity: int = 1,
    ) -> List[Conflict]:
        """Detect contention and concurrent presence at shared junctions or throat nodes.

        Can evaluate either structured node occupancy intervals or the live SimulationState.

        Args:
            node_occupancies: List of records containing:
                              {"node_id": str, "service_id": str, "train_id": str,
                               "arrival_time": float, "departure_time": float}
            state: Optional live SimulationState to inspect active station/junction occupancies.
            junction_capacity_map: Optional junction_id -> capacity mapping.
            default_junction_capacity: Default capacity (typically 1 for junctions/throats).

        Returns:
            List of detected SHARED_JUNCTION Conflict objects.
        """
        detected: List[Conflict] = []
        junction_nodes: Set[str] = set()
        jct_id_map: Dict[str, str] = {}  # node/station_id -> junction_id

        # Register junctions from network
        if self.network:
            for jct in self.network.junctions.values():
                junction_nodes.add(jct.id)
                jct_id_map[jct.id] = jct.id
                # If junction defines station_id (e.g. BBQ, VJM)
                station_node = getattr(jct, "station_id", None)
                if station_node:
                    junction_nodes.add(station_node)
                    jct_id_map[station_node] = jct.id

        # Mode A: Evaluate live SimulationState
        if state is not None:
            # Check station/node occupancy
            for node, svcs in state.station_occupancy.items():
                active_svcs = list(svcs)
                if len(active_svcs) > 1:
                    # Check if this node is a recognized junction or throat
                    is_jct = node in junction_nodes or any(node in j.connected_routes for j in getattr(self.network, "junctions", {}).values() if hasattr(j, "connected_routes")) or "JCT" in node or "BBQ" in node
                    if is_jct or len(active_svcs) > default_junction_capacity:
                        jct_id = jct_id_map.get(node, node)
                        train_ids = [state.get_train_state(s).train_id for s in active_svcs if s in state.train_states]
                        desc = (
                            f"Shared junction contention at '{jct_id}' (node '{node}'): "
                            f"{len(active_svcs)} trains competing concurrently ({', '.join(sorted(active_svcs))})."
                        )
                        c = Conflict(
                            conflict_id=self._next_conflict_id(),
                            conflict_type=ConflictType.SHARED_JUNCTION,
                            affected_service_ids=sorted(active_svcs),
                            affected_train_ids=train_ids,
                            resource_id=jct_id,
                            conflict_time=state.clock.current_time,
                            severity=ConflictSeverity.MAJOR,
                            description=desc,
                            metadata={"node_id": node, "junction_id": jct_id, "active_count": len(active_svcs)},
                        )
                        detected.append(c)
                        self.conflicts.append(c)

        # Mode B: Evaluate temporal node interval records
        if node_occupancies:
            by_node: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for rec in node_occupancies:
                by_node[rec["node_id"]].append(rec)

            for node, rec_list in sorted(by_node.items()):
                if len(rec_list) < 2:
                    continue

                jct_id = jct_id_map.get(node, node)
                cap = default_junction_capacity
                if junction_capacity_map and jct_id in junction_capacity_map:
                    cap = junction_capacity_map[jct_id]

                # Sweep line over arrival and departure times
                events: List[Tuple[float, int, Dict[str, Any]]] = []
                for rec in rec_list:
                    events.append((rec["arrival_time"], 1, rec))
                    events.append((rec["departure_time"], -1, rec))

                events.sort(key=lambda x: (x[0], x[1]))
                active: Set[str] = set()
                reported: Set[Tuple[str, ...]] = set()

                for t, kind, rec in events:
                    if kind == 1:
                        active.add(rec["service_id"])
                        if len(active) > cap:
                            key = tuple(sorted(active))
                            if key not in reported:
                                reported.add(key)
                                train_map = {r["service_id"]: r.get("train_id", "") for r in rec_list}
                                desc = (
                                    f"Shared junction contention at '{jct_id}' (node '{node}'): "
                                    f"{len(active)} trains competing simultaneously ({', '.join(sorted(active))}) "
                                    f"exceeding junction capacity of {cap}."
                                )
                                c = Conflict(
                                    conflict_id=self._next_conflict_id(),
                                    conflict_type=ConflictType.SHARED_JUNCTION,
                                    affected_service_ids=sorted(list(active)),
                                    affected_train_ids=[train_map.get(s, "") for s in sorted(list(active))],
                                    resource_id=jct_id,
                                    conflict_time=t,
                                    severity=ConflictSeverity.MAJOR,
                                    description=desc,
                                    metadata={"node_id": node, "junction_id": jct_id, "capacity": cap},
                                )
                                detected.append(c)
                                self.conflicts.append(c)
                    else:
                        active.discard(rec["service_id"])

        return detected

    # ------------------------------------------------------------------
    # 4. Incompatible Movements (Opposing Moves on Shared Resource)
    # ------------------------------------------------------------------

    def detect_incompatible_movements(
        self,
        occupancies: List[TrackSectionOccupancy],
        routes_map: Optional[Dict[str, Route]] = None,
    ) -> List[Conflict]:
        """Detect opposing or intersecting movements competing for the same track section.

        Flags head-on / opposing direction movements (e.g. UP vs DOWN, or A->B vs B->A)
        occurring within overlapping time intervals.

        Args:
            occupancies: List of TrackSectionOccupancy records (optionally with from_node/to_node/direction).
            routes_map: Optional service_id/route_id -> Route mapping.

        Returns:
            List of detected INCOMPATIBLE_MOVEMENTS Conflict objects.
        """
        detected: List[Conflict] = []

        # Helper to determine movement direction
        def get_direction(occ: TrackSectionOccupancy) -> str:
            if hasattr(occ, "direction") and occ.direction:
                return occ.direction.upper()
            if self.network and occ.service_id in self.network.services:
                svc = self.network.services[occ.service_id]
                if routes_map and svc.route_id in routes_map:
                    r_id = routes_map[svc.route_id].id
                elif self.network and svc.route_id in self.network.routes:
                    r_id = self.network.routes[svc.route_id].id
                else:
                    r_id = svc.route_id
                if "UP" in r_id:
                    return "UP"
                if "DOWN" in r_id:
                    return "DOWN"
            return "UNKNOWN"

        # Group by section ID
        by_section: Dict[str, List[TrackSectionOccupancy]] = defaultdict(list)
        for occ in occupancies:
            by_section[occ.section_id].append(occ)

        for sec_id, occ_list in sorted(by_section.items()):
            if len(occ_list) < 2:
                continue

            # Compare all pairs for overlapping intervals with opposing directions
            for i in range(len(occ_list)):
                for j in range(i + 1, len(occ_list)):
                    occ1 = occ_list[i]
                    occ2 = occ_list[j]

                    if occ1.service_id == occ2.service_id:
                        continue

                    exit1 = occ1.actual_exit_time or occ1.expected_exit_time or (occ1.entry_time + 3.0)
                    exit2 = occ2.actual_exit_time or occ2.expected_exit_time or (occ2.entry_time + 3.0)

                    # Check temporal overlap: max(start1, start2) < min(end1, end2)
                    overlap_start = max(occ1.entry_time, occ2.entry_time)
                    overlap_end = min(exit1, exit2)

                    if overlap_start < overlap_end:
                        dir1 = get_direction(occ1)
                        dir2 = get_direction(occ2)

                        # Opposing directions condition: (UP vs DOWN) or opposing from_node/to_node
                        is_opposing = False
                        if (dir1 == "UP" and dir2 == "DOWN") or (dir1 == "DOWN" and dir2 == "UP"):
                            is_opposing = True
                        elif hasattr(occ1, "from_node") and hasattr(occ2, "from_node") and occ1.from_node and occ2.from_node:
                            if occ1.from_node == getattr(occ2, "to_node", None) and occ1.to_node == getattr(occ2, "from_node", None):
                                is_opposing = True

                        if is_opposing:
                            desc = (
                                f"Incompatible opposing movement on section '{sec_id}': "
                                f"service '{occ1.service_id}' ({dir1}) and service '{occ2.service_id}' ({dir2}) "
                                f"occupy the same track section concurrently from "
                                f"{minutes_to_time_str(overlap_start)} to {minutes_to_time_str(overlap_end)}."
                            )
                            c = Conflict(
                                conflict_id=self._next_conflict_id(),
                                conflict_type=ConflictType.INCOMPATIBLE_MOVEMENTS,
                                affected_service_ids=sorted([occ1.service_id, occ2.service_id]),
                                affected_train_ids=sorted([occ1.train_id, occ2.train_id]),
                                resource_id=sec_id,
                                conflict_time=overlap_start,
                                severity=ConflictSeverity.CRITICAL,
                                description=desc,
                                metadata={
                                    "direction_1": dir1,
                                    "direction_2": dir2,
                                    "overlap_start_time": overlap_start,
                                    "overlap_end_time": overlap_end,
                                    "section_id": sec_id,
                                },
                            )
                            detected.append(c)
                            self.conflicts.append(c)

        return detected

    # ------------------------------------------------------------------
    # Comprehensive Conflict Detection
    # ------------------------------------------------------------------

    def detect_all(
        self,
        state: Optional[SimulationState] = None,
        occupancies: Optional[List[TrackSectionOccupancy]] = None,
        node_occupancies: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Conflict]:
        """Run all conflict detection routines across given state and occupancies.

        Returns all detected conflicts in deterministic chronological order.
        """
        occs: List[TrackSectionOccupancy] = []
        if occupancies is not None:
            occs.extend(occupancies)
        if state is not None:
            occs.extend(state.occupancy_history)
            for active_map in state.active_occupancies.values():
                for act_occ in active_map.values():
                    if act_occ not in occs:
                        occs.append(act_occ)

        # Run individual detectors
        same_sec = self.detect_same_section_conflicts(occs)
        headway = self.detect_headway_conflicts(occs)
        jct = self.detect_junction_conflicts(node_occupancies=node_occupancies, state=state)
        incompat = self.detect_incompatible_movements(occs)

        # Sort all conflicts deterministically by (conflict_time, severity, conflict_id)
        severity_order = {
            ConflictSeverity.CRITICAL: 0,
            ConflictSeverity.MAJOR: 1,
            ConflictSeverity.WARNING: 2,
            ConflictSeverity.MINOR: 3,
        }
        all_detected = same_sec + headway + jct + incompat
        all_detected.sort(key=lambda c: (c.conflict_time, severity_order.get(c.severity, 99), c.conflict_id))
        return all_detected
