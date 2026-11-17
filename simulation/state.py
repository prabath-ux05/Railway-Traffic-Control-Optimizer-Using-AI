"""
simulation/state.py
~~~~~~~~~~~~~~~~~~~
In-memory runtime simulation state management for railway traffic optimizer.

Tracks runtime states of trains, services, positions, station/track section
occupancies, resource locks, delays, and event histories.

IMPORTANT: Runtime state is strictly kept in memory and is NOT stored in JSON.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union

from simulation.clock import SimulationClock, time_to_minutes
from simulation.network import Network, Service, Train, TimetableEntry, Route


class TrainStatus(str, Enum):
    """Runtime status of a train service."""
    NOT_STARTED = "NOT_STARTED"   # Scheduled, not yet departed origin
    IN_TRANSIT  = "IN_TRANSIT"    # Moving between nodes / on a track section
    AT_STATION  = "AT_STATION"    # Stopped at station / dwelling on platform
    HELD        = "HELD"          # Stopped due to conflict / signal / dispatch hold
    COMPLETED   = "COMPLETED"     # Terminated at destination


class CapacityViolationError(Exception):
    """Raised when a track section's capacity limit is violated."""

    def __init__(
        self,
        section_id: str,
        service_id: str,
        train_id: str,
        current_occupancy: int,
        capacity: int,
        active_services: List[str],
    ):
        self.section_id = section_id
        self.service_id = service_id
        self.train_id = train_id
        self.current_occupancy = current_occupancy
        self.capacity = capacity
        self.active_services = active_services
        super().__init__(
            f"Capacity violation on track section '{section_id}': "
            f"capacity is {capacity}, but currently occupied by {current_occupancy} trains "
            f"{active_services}. Service '{service_id}' (Train '{train_id}') cannot enter."
        )


@dataclass
class TrackSectionOccupancy:
    """Runtime dynamic record of a train occupying a track section.

    Attributes:
        section_id: TrackSection identifier.
        service_id: Service ID of the occupying train.
        train_id: Physical train identity.
        entry_time: Timestamp of section entry in minutes from midnight.
        expected_exit_time: Scheduled or calculated exit timestamp.
        actual_exit_time: Actual exit timestamp (None while active).
        from_node: Origin node of the traversal (station or junction).
        to_node: Destination node of the traversal (station or junction).
        direction: Direction of traversal ('UP', 'DOWN', etc.).
    """
    section_id: str
    service_id: str
    train_id: str
    entry_time: float
    expected_exit_time: Optional[float] = None
    actual_exit_time: Optional[float] = None
    from_node: Optional[str] = None
    to_node: Optional[str] = None
    direction: Optional[str] = None

    @property
    def is_active(self) -> bool:
        """True if the section is currently occupied by this train."""
        return self.actual_exit_time is None

    @property
    def duration_minutes(self) -> Optional[float]:
        """Total duration of occupancy in minutes once released."""
        if self.actual_exit_time is not None:
            return self.actual_exit_time - self.entry_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert occupancy record to dictionary."""
        return {
            "section_id": self.section_id,
            "service_id": self.service_id,
            "train_id": self.train_id,
            "entry_time": self.entry_time,
            "expected_exit_time": self.expected_exit_time,
            "actual_exit_time": self.actual_exit_time,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "direction": self.direction,
        }


@dataclass
class TrainRuntimeState:
    """Runtime dynamic state of a train service.

    Attributes:
        service_id: Unique service identifier (e.g. 'SRV_12607_01').
        train_id: Physical train identity (e.g. 'TR_12607').
        route_id: Assigned route ID.
        status: Current TrainStatus.
        current_station: ID of current station if stopped/dwelling at one.
        current_node: ID of current node (station or junction).
        current_track_section: ID of current track section if in transit.
        occupied_resources: Set of resource IDs currently held by this train.
        stop_sequence: Current or last completed stop sequence number (1-indexed).
        delay_minutes: Current delay relative to scheduled timetable in minutes (>= 0).
        max_delay_minutes: Peak delay encountered throughout service execution.
        actual_arrivals: Map of station_id -> actual arrival time (minutes from midnight).
        actual_departures: Map of station_id -> actual departure time (minutes from midnight).
        origin: Service origin station ID.
        destination: Service destination station ID.
        priority_class: Priority tier (e.g. 'HIGH', 'NORMAL').
        delay_penalty_weight: Cost multiplier for delay minutes.
        simulation_profile: Train rolling-stock performance profile.
        last_event_time: Timestamp of last recorded state change.
    """
    service_id: str
    train_id: str
    route_id: str
    status: TrainStatus = TrainStatus.NOT_STARTED
    current_station: Optional[str] = None
    current_node: Optional[str] = None
    current_track_section: Optional[str] = None
    occupied_resources: Set[str] = field(default_factory=set)
    stop_sequence: int = 0
    delay_minutes: float = 0.0
    max_delay_minutes: float = 0.0
    actual_arrivals: Dict[str, float] = field(default_factory=dict)
    actual_departures: Dict[str, float] = field(default_factory=dict)
    origin: str = ""
    destination: str = ""
    priority_class: str = "NORMAL"
    delay_penalty_weight: float = 1.0
    simulation_profile: str = ""
    last_event_time: Optional[float] = None

    @property
    def occupied_resource(self) -> Optional[str]:
        """Primary occupied resource (first in set, if any)."""
        if self.occupied_resources:
            return next(iter(self.occupied_resources))
        return None

    @property
    def is_active(self) -> bool:
        """True if train is currently running on the network."""
        return self.status in (TrainStatus.IN_TRANSIT, TrainStatus.AT_STATION, TrainStatus.HELD)

    @property
    def is_completed(self) -> bool:
        return self.status == TrainStatus.COMPLETED

    def record_delay(self, current_delay: float):
        """Update current and maximum observed delay."""
        self.delay_minutes = max(0.0, current_delay)
        if self.delay_minutes > self.max_delay_minutes:
            self.max_delay_minutes = self.delay_minutes


class SimulationState:
    """Central runtime state manager for the railway simulation.

    Maintains all train states, resource allocations, track section
    occupancies, capacity tracking, and delay statistics.
    """

    def __init__(self, clock: Optional[SimulationClock] = None):
        self.clock: SimulationClock = clock or SimulationClock()
        self.train_states: Dict[str, TrainRuntimeState] = {}
        self.resource_occupancy: Dict[str, str] = {}               # resource_id -> service_id
        self.station_occupancy: Dict[str, Set[str]] = defaultdict(set) # station_id -> set(service_ids)
        self.track_occupancy: Dict[str, Set[str]] = defaultdict(set)   # track_section_id -> set(service_ids)
        self.active_occupancies: Dict[str, Dict[str, TrackSectionOccupancy]] = defaultdict(dict) # section_id -> {service_id -> TrackSectionOccupancy}
        self.occupancy_history: List[TrackSectionOccupancy] = []
        self._network_ref: Optional[Network] = None

    def initialize_from_network(self, network: Network):
        """Initialize runtime state from a loaded Network model."""
        self._network_ref = network
        self.train_states.clear()
        self.resource_occupancy.clear()
        self.station_occupancy.clear()
        self.track_occupancy.clear()
        self.active_occupancies.clear()
        self.occupancy_history.clear()

        for svc_id, service in network.services.items():
            self.train_states[svc_id] = TrainRuntimeState(
                service_id=svc_id,
                train_id=service.train_id,
                route_id=service.route_id,
                status=TrainStatus.NOT_STARTED,
                origin=service.origin,
                destination=service.destination,
                priority_class=service.priority_class,
                delay_penalty_weight=service.delay_penalty_weight,
                simulation_profile=service.simulation_profile,
            )

    def get_train_state(self, service_id: str) -> TrainRuntimeState:
        """Retrieve the runtime state for a given service ID."""
        if service_id not in self.train_states:
            raise KeyError(f"Service '{service_id}' not found in runtime simulation state")
        return self.train_states[service_id]

    # ------------------------------------------------------------------
    # Resource Lock & Occupancy Management
    # ------------------------------------------------------------------

    def occupy_resource(self, resource_id: str, service_id: str) -> bool:
        """Attempt to claim a resource for a service. Returns True on success, False if already held by another."""
        current_holder = self.resource_occupancy.get(resource_id)
        if current_holder is not None and current_holder != service_id:
            return False

        self.resource_occupancy[resource_id] = service_id
        if service_id in self.train_states:
            self.train_states[service_id].occupied_resources.add(resource_id)
        return True

    def release_resource(self, resource_id: str, service_id: str) -> bool:
        """Release a resource held by service_id. Returns True if released."""
        if self.resource_occupancy.get(resource_id) == service_id:
            del self.resource_occupancy[resource_id]
            if service_id in self.train_states:
                self.train_states[service_id].occupied_resources.discard(resource_id)
            return True
        return False

    def release_all_resources_for_service(self, service_id: str):
        """Release all resources currently held by a service."""
        if service_id not in self.train_states:
            return
        state = self.train_states[service_id]
        for res_id in list(state.occupied_resources):
            if self.resource_occupancy.get(res_id) == service_id:
                del self.resource_occupancy[res_id]
            # If it was an active track section occupancy, release it
            if res_id in self.active_occupancies and service_id in self.active_occupancies[res_id]:
                self.exit_track_section(service_id, res_id, self.clock.current_time)
        state.occupied_resources.clear()

    def is_resource_occupied(self, resource_id: str) -> bool:
        return resource_id in self.resource_occupancy or len(self.active_occupancies.get(resource_id, {})) > 0

    def get_resource_holder(self, resource_id: str) -> Optional[str]:
        return self.resource_occupancy.get(resource_id)

    # ------------------------------------------------------------------
    # Track Section Occupancy Queries
    # ------------------------------------------------------------------

    def get_active_occupancies(self, section_id: Optional[str] = None) -> List[TrackSectionOccupancy]:
        """Return list of active track section occupancies (all or filtered by section_id)."""
        if section_id is not None:
            return list(self.active_occupancies.get(section_id, {}).values())
        result = []
        for occupancies in self.active_occupancies.values():
            result.extend(occupancies.values())
        return result

    def get_section_occupancy_count(self, section_id: str) -> int:
        """Return number of trains currently occupying a track section."""
        return len(self.active_occupancies.get(section_id, {}))

    def is_section_available(self, section_id: str, capacity: Optional[int] = None) -> bool:
        """Return True if track section has available capacity."""
        sec_cap = capacity
        if sec_cap is None and self._network_ref and section_id in self._network_ref.track_sections:
            sec_cap = self._network_ref.track_sections[section_id].capacity
        if sec_cap is None:
            sec_cap = 1
        return self.get_section_occupancy_count(section_id) < sec_cap

    # ------------------------------------------------------------------
    # State Transition Handlers
    # ------------------------------------------------------------------

    def start_service(
        self,
        service_id: str,
        start_node: str,
        time: Union[str, float, int],
    ):
        """Mark service as started / ready at its origin."""
        t = time_to_minutes(time)
        state = self.get_train_state(service_id)
        state.status = TrainStatus.AT_STATION
        state.current_station = start_node
        state.current_node = start_node
        state.current_track_section = None
        state.stop_sequence = 1
        state.last_event_time = t
        self.station_occupancy[start_node].add(service_id)

    def enter_track_section(
        self,
        service_id: str,
        track_section_id: str,
        from_node: str,
        to_node: str,
        time: Union[str, float, int],
        expected_exit_time: Optional[Union[str, float, int]] = None,
        capacity: Optional[int] = None,
        enforce_capacity: bool = True,
        direction: Optional[str] = None,
    ) -> TrackSectionOccupancy:
        """Transition train into a track section and record runtime occupancy.

        Raises:
            CapacityViolationError: If enforce_capacity is True and section capacity is exceeded.
        """
        t = time_to_minutes(time)
        exp_exit_t = time_to_minutes(expected_exit_time) if expected_exit_time is not None else None
        state = self.get_train_state(service_id)

        # Enforce capacity
        if enforce_capacity:
            sec_cap = capacity
            if sec_cap is None and self._network_ref and track_section_id in self._network_ref.track_sections:
                sec_cap = self._network_ref.track_sections[track_section_id].capacity
            if sec_cap is None:
                sec_cap = 1

            active_in_sec = self.active_occupancies[track_section_id]
            if service_id not in active_in_sec and len(active_in_sec) >= sec_cap:
                raise CapacityViolationError(
                    section_id=track_section_id,
                    service_id=service_id,
                    train_id=state.train_id,
                    current_occupancy=len(active_in_sec),
                    capacity=sec_cap,
                    active_services=list(active_in_sec.keys()),
                )

        # Remove from origin station if departing
        if state.current_station:
            self.station_occupancy[state.current_station].discard(service_id)

        # Clear previous track section occupancy if any
        if state.current_track_section and state.current_track_section != track_section_id:
            self.exit_track_section(service_id, state.current_track_section, t)

        # Infer direction if not explicitly supplied
        sec_dir = direction
        if sec_dir is None and self._network_ref and track_section_id in self._network_ref.track_sections:
            sec_dir = self._network_ref.track_sections[track_section_id].direction

        state.status = TrainStatus.IN_TRANSIT
        state.current_station = None
        state.current_node = from_node
        state.current_track_section = track_section_id
        state.last_event_time = t
        state.occupied_resources.add(track_section_id)

        self.track_occupancy[track_section_id].add(service_id)

        # Create active occupancy record
        rec = TrackSectionOccupancy(
            section_id=track_section_id,
            service_id=service_id,
            train_id=state.train_id,
            entry_time=t,
            expected_exit_time=exp_exit_t,
            from_node=from_node,
            to_node=to_node,
            direction=sec_dir,
        )
        self.active_occupancies[track_section_id][service_id] = rec
        self.occupancy_history.append(rec)

        return rec

    def exit_track_section(
        self,
        service_id: str,
        track_section_id: str,
        time: Union[str, float, int],
    ) -> Optional[TrackSectionOccupancy]:
        """Release track section occupancy when train clears the section."""
        t = time_to_minutes(time)
        rec = self.active_occupancies[track_section_id].pop(service_id, None)
        if rec is not None:
            rec.actual_exit_time = t

        self.track_occupancy[track_section_id].discard(service_id)
        if service_id in self.train_states:
            self.train_states[service_id].occupied_resources.discard(track_section_id)

        return rec

    def arrive_at_station(
        self,
        service_id: str,
        station_id: str,
        time: Union[str, float, int],
        scheduled_arrival: Optional[Union[str, float, int]] = None,
        stop_sequence: Optional[int] = None,
    ):
        """Transition train to arrival at station/node and release track section occupancy."""
        t = time_to_minutes(time)
        state = self.get_train_state(service_id)

        # Clear track section occupancy
        if state.current_track_section:
            self.exit_track_section(service_id, state.current_track_section, t)
            state.current_track_section = None

        state.status = TrainStatus.AT_STATION
        state.current_station = station_id
        state.current_node = station_id
        state.actual_arrivals[station_id] = t
        state.last_event_time = t
        if stop_sequence is not None:
            state.stop_sequence = stop_sequence

        self.station_occupancy[station_id].add(service_id)

        if scheduled_arrival is not None:
            sched_t = time_to_minutes(scheduled_arrival)
            state.record_delay(t - sched_t)


    def depart_from_station(
        self,
        service_id: str,
        station_id: str,
        time: Union[str, float, int],
        scheduled_departure: Optional[Union[str, float, int]] = None,
    ):
        """Record station departure."""
        t = time_to_minutes(time)
        state = self.get_train_state(service_id)
        state.actual_departures[station_id] = t
        state.last_event_time = t

        if scheduled_departure is not None:
            sched_t = time_to_minutes(scheduled_departure)
            state.record_delay(t - sched_t)

    def hold_service(self, service_id: str, reason: str = ""):
        """Mark service as held due to conflict or dispatching decision."""
        state = self.get_train_state(service_id)
        state.status = TrainStatus.HELD

    def resume_service(
        self,
        service_id: str,
        new_status: TrainStatus = TrainStatus.IN_TRANSIT,
    ):
        """Resume a held service."""
        state = self.get_train_state(service_id)
        state.status = new_status

    def complete_service(
        self,
        service_id: str,
        final_station: str,
        time: Union[str, float, int],
    ):
        """Mark service as completed at destination."""
        t = time_to_minutes(time)
        state = self.get_train_state(service_id)

        # Clean up all occupancies and resource holds
        if state.current_track_section:
            self.track_occupancy[state.current_track_section].discard(service_id)
        if state.current_station:
            self.station_occupancy[state.current_station].discard(service_id)
        self.release_all_resources_for_service(service_id)

        state.status = TrainStatus.COMPLETED
        state.current_station = final_station
        state.current_node = final_station
        state.current_track_section = None
        state.last_event_time = t

    # ------------------------------------------------------------------
    # Query & Analytics Helpers
    # ------------------------------------------------------------------

    def get_active_services(self) -> List[TrainRuntimeState]:
        """Return list of trains currently active on the network."""
        return [s for s in self.train_states.values() if s.is_active]

    def get_completed_services(self) -> List[TrainRuntimeState]:
        """Return list of completed services."""
        return [s for s in self.train_states.values() if s.is_completed]

    def get_delayed_services(self, threshold_minutes: float = 0.0) -> List[TrainRuntimeState]:
        """Return list of active or completed services with delay > threshold_minutes."""
        return [s for s in self.train_states.values() if s.delay_minutes > threshold_minutes]

    def get_total_delay_minutes(self) -> float:
        """Return sum of current delay minutes across all services."""
        return sum(s.delay_minutes for s in self.train_states.values())

    def get_total_weighted_delay(self) -> float:
        """Return sum of (delay_minutes * delay_penalty_weight) across all services."""
        return sum(s.delay_minutes * s.delay_penalty_weight for s in self.train_states.values())
