"""
simulation/simulator.py
~~~~~~~~~~~~~~~~~~~~~~~
Train movement simulation engine for railway traffic optimizer.

Coordinates train movements along route ordered_nodes, performs directional
track section lookups, advances simulation time according to track section travel
times, generates discrete movement/arrival/departure events, and updates in-memory
runtime train states.

Pipeline:
    Service → Route → ordered_nodes → TrackSection → Event Generation → State Update
"""

from typing import Dict, List, Optional, Tuple, Union

from simulation.clock import SimulationClock, time_to_minutes
from simulation.events import EventQueue, EventType, SimulationEvent
from simulation.network import Network, Route, Service, TimetableEntry, TrackSection
from simulation.state import SimulationState, TrainRuntimeState, TrainStatus


class SimulationError(Exception):
    """Base exception for simulation engine errors."""
    pass


class MissingTrackSectionError(SimulationError):
    """Raised when no track section connects consecutive route nodes."""

    def __init__(self, from_node: str, to_node: str, service_id: str, direction: Optional[str] = None):
        self.from_node = from_node
        self.to_node = to_node
        self.service_id = service_id
        self.direction = direction
        msg = (
            f"No track section found connecting '{from_node}' -> '{to_node}' "
            f"for service '{service_id}'"
        )
        if direction:
            msg += f" in direction '{direction}'"
        super().__init__(msg)


class ServiceNotFoundError(SimulationError):
    """Raised when a requested service ID is not found in network."""
    pass


class InvalidRouteError(SimulationError):
    """Raised when a service route is invalid or has fewer than 2 nodes."""
    pass


def find_track_section(
    network: Network,
    from_node: str,
    to_node: str,
    direction: Optional[str] = None,
) -> Optional[TrackSection]:
    """Find a directional track section between two nodes in the network.

    Args:
        network: Loaded Network instance.
        from_node: Source node (station or junction ID).
        to_node: Target node (station or junction ID).
        direction: Optional direction filter ('UP', 'DOWN', 'BOTH', 'BIDIRECTIONAL').

    Returns:
        TrackSection if a matching section exists, else None.
    """
    candidates = []
    for ts in network.track_sections.values():
        if ts.from_node == from_node and ts.to_node == to_node:
            candidates.append(ts)

    if not candidates:
        return None

    if direction is not None:
        target_dir = direction.upper()
        # Look for exact direction match or bidirectional section
        for ts in candidates:
            ts_dir = ts.direction.upper() if ts.direction else ""
            if ts_dir == target_dir or ts_dir in ("BOTH", "BIDIRECTIONAL"):
                return ts

    # If direction not specified or no exact directional match, return first candidate
    return candidates[0]


class TrainSimulator:
    """Deterministic railway movement simulator.

    Simulates train progression along route nodes, advances the simulation clock,
    records discrete events, and maintains runtime states.
    """

    def __init__(
        self,
        network: Network,
        clock: Optional[SimulationClock] = None,
        state: Optional[SimulationState] = None,
        event_queue: Optional[EventQueue] = None,
    ):
        self.network = network
        self.clock = clock or SimulationClock()
        self.state = state or SimulationState(clock=self.clock)
        self.event_queue = event_queue or EventQueue()
        self.event_history: List[SimulationEvent] = []

        # Ensure state is initialized from network if not already populated
        if not self.state.train_states and self.network.services:
            self.state.initialize_from_network(self.network)

        # Track route progression: service_id -> current index in route.ordered_nodes
        self._route_node_index: Dict[str, int] = {}

    def find_track_section(
        self,
        from_node: str,
        to_node: str,
        direction: Optional[str] = None,
    ) -> Optional[TrackSection]:
        """Look up track section in simulator's network."""
        return find_track_section(self.network, from_node, to_node, direction)

    def get_service(self, service_id: str) -> Service:
        """Retrieve service from network or raise ServiceNotFoundError."""
        if service_id not in self.network.services:
            raise ServiceNotFoundError(f"Service '{service_id}' not found in network")
        return self.network.services[service_id]

    def get_route(self, route_id: str) -> Route:
        """Retrieve route from network or raise InvalidRouteError."""
        if route_id not in self.network.routes:
            raise InvalidRouteError(f"Route '{route_id}' not found in network")
        return self.network.routes[route_id]

    def get_timetable_entries(self, service_id: str) -> List[TimetableEntry]:
        """Return timetable entries for a service sorted by stop_sequence."""
        entries = [e for e in self.network.timetable if e.service_id == service_id]
        return sorted(entries, key=lambda e: e.stop_sequence)

    def get_timetable_entry(self, service_id: str, station_id: str) -> Optional[TimetableEntry]:
        """Return timetable entry for service at a specific station, if any."""
        for e in self.network.timetable:
            if e.service_id == service_id and e.station_id == station_id:
                return e
        return None

    def initialize_service(
        self,
        service_id: str,
        start_time: Optional[Union[str, float, int]] = None,
    ) -> SimulationEvent:
        """Initialize a service at its route origin node.

        If start_time is not provided, uses the scheduled departure from timetable,
        or current clock time.
        """
        service = self.get_service(service_id)
        route = self.get_route(service.route_id)

        if not route.ordered_nodes:
            raise InvalidRouteError(f"Route '{route.id}' has no ordered_nodes")

        origin_node = route.ordered_nodes[0]
        self._route_node_index[service_id] = 0

        # Determine start time
        if start_time is not None:
            t = time_to_minutes(start_time)
        else:
            tt_origin = self.get_timetable_entry(service_id, origin_node)
            if tt_origin and tt_origin.departure:
                t = time_to_minutes(tt_origin.departure)
            else:
                t = self.clock.current_time

        # Advance clock to start time if start time is later
        if t > self.clock.current_time:
            self.clock.advance_to(t)

        # Update runtime state
        self.state.start_service(service_id, start_node=origin_node, time=t)

        # Generate SERVICE_START event
        start_event = SimulationEvent(
            time=t,
            event_type=EventType.SERVICE_START,
            service_id=service_id,
            node_id=origin_node,
            details={"origin": origin_node, "destination": service.destination, "route": route.id},
        )
        self.event_history.append(start_event)
        return start_event

    def step_service(
        self,
        service_id: str,
        strict_track_lookup: bool = True,
        fallback_travel_time_minutes: float = 3.0,
    ) -> List[SimulationEvent]:
        """Advance a single service by one segment along its route's ordered_nodes.

        Args:
            service_id: ID of the service to advance.
            strict_track_lookup: If True, raises MissingTrackSectionError when no track
                                section is found. If False, uses fallback travel time.
            fallback_travel_time_minutes: Travel time used if strict_track_lookup is False.

        Returns:
            List of generated SimulationEvents for this step (DEPARTURE, SECTION_ENTER,
            SECTION_EXIT, ARRIVAL, and optionally SERVICE_COMPLETE).
        """
        service = self.get_service(service_id)
        route = self.get_route(service.route_id)
        train_state = self.state.get_train_state(service_id)

        if train_state.is_completed:
            return []

        # Ensure service is started
        if service_id not in self._route_node_index or train_state.status == TrainStatus.NOT_STARTED:
            self.initialize_service(service_id)

        curr_idx = self._route_node_index[service_id]
        if curr_idx >= len(route.ordered_nodes) - 1:
            # Already at the final node in route
            if not train_state.is_completed:
                dest_node = route.ordered_nodes[curr_idx]
                complete_event = SimulationEvent(
                    time=self.clock.current_time,
                    event_type=EventType.SERVICE_COMPLETE,
                    service_id=service_id,
                    node_id=dest_node,
                    details={"destination": dest_node},
                )
                self.state.complete_service(service_id, final_station=dest_node, time=self.clock.current_time)
                self.event_history.append(complete_event)
                return [complete_event]
            return []

        from_node = route.ordered_nodes[curr_idx]
        to_node = route.ordered_nodes[curr_idx + 1]

        # Determine directional track section
        # Infer direction from route ID or endpoints if possible (e.g. _UP / _DOWN)
        direction_hint = None
        if "UP" in route.id:
            direction_hint = "UP"
        elif "DOWN" in route.id or "AJJ" in route.destination or "MAS" in route.origin:
            direction_hint = "DOWN"

        track_section = self.find_track_section(from_node, to_node, direction_hint)

        if track_section is None:
            if strict_track_lookup:
                raise MissingTrackSectionError(
                    from_node=from_node,
                    to_node=to_node,
                    service_id=service_id,
                    direction=direction_hint,
                )
            travel_time = fallback_travel_time_minutes
            track_id = f"FALLBACK_{from_node}_{to_node}"
        else:
            travel_time = track_section.travel_time_minutes
            track_id = track_section.id

        dep_time = self.clock.current_time
        arr_time = dep_time + travel_time

        step_events: List[SimulationEvent] = []

        # 1. DEPARTURE event from current node
        dep_tt = self.get_timetable_entry(service_id, from_node)
        sched_dep = dep_tt.departure if dep_tt else None
        self.state.depart_from_station(service_id, from_node, dep_time, scheduled_departure=sched_dep)

        dep_event = SimulationEvent(
            time=dep_time,
            event_type=EventType.DEPARTURE,
            service_id=service_id,
            node_id=from_node,
            track_section_id=track_id,
            details={"from_node": from_node, "to_node": to_node},
        )
        step_events.append(dep_event)

        # 2. SECTION_ENTER event
        enter_event = SimulationEvent(
            time=dep_time,
            event_type=EventType.SECTION_ENTER,
            service_id=service_id,
            node_id=from_node,
            track_section_id=track_id,
            details={"travel_time_minutes": travel_time, "expected_exit_time": arr_time},
        )
        step_events.append(enter_event)

        sec_capacity = track_section.capacity if track_section else 1
        self.state.enter_track_section(
            service_id,
            track_id,
            from_node,
            to_node,
            dep_time,
            expected_exit_time=arr_time,
            capacity=sec_capacity,
            enforce_capacity=True,
        )

        # 3. Advance simulation clock to arrival time
        self.clock.advance_to(arr_time)

        # 4. SECTION_EXIT event
        exit_event = SimulationEvent(
            time=arr_time,
            event_type=EventType.SECTION_EXIT,
            service_id=service_id,
            node_id=to_node,
            track_section_id=track_id,
        )
        step_events.append(exit_event)


        # 5. ARRIVAL event at next node
        arr_tt = self.get_timetable_entry(service_id, to_node)
        sched_arr = arr_tt.arrival if arr_tt else None
        stop_seq = arr_tt.stop_sequence if arr_tt else None

        self.state.arrive_at_station(
            service_id,
            to_node,
            arr_time,
            scheduled_arrival=sched_arr,
            stop_sequence=stop_seq,
        )

        arr_event = SimulationEvent(
            time=arr_time,
            event_type=EventType.ARRIVAL,
            service_id=service_id,
            node_id=to_node,
            track_section_id=track_id,
            details={
                "scheduled_arrival": sched_arr,
                "delay_minutes": train_state.delay_minutes,
            },
        )
        step_events.append(arr_event)

        # Update route node index
        self._route_node_index[service_id] = curr_idx + 1

        # 6. Check if destination or end of route reached
        is_destination = (to_node == service.destination) or (curr_idx + 1 == len(route.ordered_nodes) - 1)
        if is_destination:
            complete_event = SimulationEvent(
                time=arr_time,
                event_type=EventType.SERVICE_COMPLETE,
                service_id=service_id,
                node_id=to_node,
                details={"destination": to_node, "final_delay_minutes": train_state.delay_minutes},
            )
            self.state.complete_service(service_id, final_station=to_node, time=arr_time)
            step_events.append(complete_event)

        self.event_history.extend(step_events)
        return step_events

    def run_service_to_destination(
        self,
        service_id: str,
        start_time: Optional[Union[str, float, int]] = None,
        strict_track_lookup: bool = True,
        fallback_travel_time_minutes: float = 3.0,
    ) -> List[SimulationEvent]:
        """Run a service from its origin to destination through all ordered_nodes.

        Returns all generated SimulationEvents in chronological order.
        """
        all_events: List[SimulationEvent] = []

        # Initialize
        start_event = self.initialize_service(service_id, start_time=start_time)
        all_events.append(start_event)

        train_state = self.state.get_train_state(service_id)
        while not train_state.is_completed:
            step_events = self.step_service(
                service_id,
                strict_track_lookup=strict_track_lookup,
                fallback_travel_time_minutes=fallback_travel_time_minutes,
            )
            if not step_events:
                break
            all_events.extend(step_events)

        return all_events
