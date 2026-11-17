"""
simulation/events.py
~~~~~~~~~~~~~~~~~~~~
Discrete event definitions and deterministic event queue for the simulation.

Events represent discrete occurrences such as service departures, arrivals,
track section entries/exits, dwelling completions, and hold/release actions.
All event ordering is strictly deterministic via timestamp, priority, and sequence ID.
"""

import heapq
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from simulation.clock import time_to_minutes


class EventType(str, Enum):
    """Types of discrete simulation events."""
    SERVICE_START   = "SERVICE_START"     # Train enters simulation / starts at origin
    DEPARTURE       = "DEPARTURE"         # Train departs station or node
    SECTION_ENTER   = "SECTION_ENTER"     # Train enters a track section
    SECTION_EXIT    = "SECTION_EXIT"      # Train clears a track section
    ARRIVAL         = "ARRIVAL"           # Train arrives at station or node
    DWELL_COMPLETE  = "DWELL_COMPLETE"    # Scheduled or minimum dwell time finished
    SERVICE_COMPLETE = "SERVICE_COMPLETE" # Train finishes route at terminus
    HOLD            = "HOLD"              # Train held (conflict/signal/dispatch decision)
    RESUME          = "RESUME"            # Train released from hold


@dataclass(order=False)
class SimulationEvent:
    """Represents a single discrete simulation event.

    Attributes:
        time: Event timestamp in minutes from midnight.
        event_type: Category of the event.
        service_id: ID of the service involved.
        node_id: Optional station or junction node ID.
        track_section_id: Optional track section ID involved.
        resource_id: Optional infrastructure resource ID (platform, section, route lock).
        details: Arbitrary contextual metadata.
        priority: Secondary sort key for simultaneous events (lower = higher priority).
        sequence_id: Monotonically increasing tie-breaker ensuring deterministic FIFO.
    """
    time: float
    event_type: EventType
    service_id: str
    node_id: Optional[str] = None
    track_section_id: Optional[str] = None
    resource_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    priority: int = 10
    sequence_id: int = 0

    def __post_init__(self):
        # Allow time to be passed as string "HH:MM"
        if isinstance(self.time, (str, int)):
            self.time = time_to_minutes(self.time)
        if isinstance(self.event_type, str) and not isinstance(self.event_type, EventType):
            self.event_type = EventType(self.event_type)

    def __lt__(self, other: "SimulationEvent") -> bool:
        """Deterministic event comparison: time -> priority -> sequence_id."""
        if not isinstance(other, SimulationEvent):
            return NotImplemented
        return (self.time, self.priority, self.sequence_id) < (other.time, other.priority, other.sequence_id)

    def __repr__(self) -> str:
        return (
            f"SimulationEvent(t={self.time:.2f}m, type={self.event_type.value}, "
            f"svc='{self.service_id}', node={self.node_id}, track={self.track_section_id})"
        )


class EventQueue:
    """Deterministic, priority-ordered event queue for simulation execution.

    Maintains events in chronological order with strict tie-breaking guarantees.
    """

    def __init__(self):
        self._heap: List[SimulationEvent] = []
        self._seq_counter: int = 0

    def schedule(
        self,
        event_or_time: Optional[Union[SimulationEvent, str, float, int]] = None,
        event_type: Optional[Union[EventType, str]] = None,
        service_id: Optional[str] = None,
        node_id: Optional[str] = None,
        track_section_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        priority: int = 10,
        time: Optional[Union[str, float, int]] = None,
        event: Optional[SimulationEvent] = None,
    ) -> SimulationEvent:
        """Schedule a new event. Accepts either a SimulationEvent or individual arguments."""
        actual_event = event or (event_or_time if isinstance(event_or_time, SimulationEvent) else None)
        if actual_event is not None:
            if actual_event.sequence_id == 0:
                self._seq_counter += 1
                actual_event.sequence_id = self._seq_counter
            heapq.heappush(self._heap, actual_event)
            return actual_event

        actual_time = time if time is not None else event_or_time
        if actual_time is None:
            raise ValueError("Must provide either a SimulationEvent or a time value")
        if event_type is None or service_id is None:
            raise ValueError("event_type and service_id are required when scheduling an event by parameters")

        self._seq_counter += 1
        ev = SimulationEvent(
            time=time_to_minutes(actual_time),
            event_type=EventType(event_type) if isinstance(event_type, str) else event_type,
            service_id=service_id,
            node_id=node_id,
            track_section_id=track_section_id,
            resource_id=resource_id,
            details=details or {},
            priority=priority,
            sequence_id=self._seq_counter,
        )

        heapq.heappush(self._heap, ev)
        return ev


    def pop(self) -> Optional[SimulationEvent]:
        """Remove and return the next earliest event, or None if queue is empty."""
        if not self._heap:
            return None
        return heapq.heappop(self._heap)

    def peek(self) -> Optional[SimulationEvent]:
        """Return the next earliest event without removing it, or None if empty."""
        if not self._heap:
            return None
        return self._heap[0]

    def pop_until(self, until_time: Union[str, float, int]) -> List[SimulationEvent]:
        """Pop and return all events occurring at or before until_time."""
        target_minutes = time_to_minutes(until_time)
        ready_events: List[SimulationEvent] = []
        while self._heap and self._heap[0].time <= target_minutes:
            ready_events.append(heapq.heappop(self._heap))
        return ready_events

    def cancel_events_for_service(
        self,
        service_id: str,
        event_type: Optional[Union[EventType, str]] = None
    ) -> int:
        """Cancel pending events for a service (and optionally a specific event type). Returns count canceled."""
        et = EventType(event_type) if isinstance(event_type, str) else event_type
        new_heap = []
        canceled = 0
        for ev in self._heap:
            match_svc = (ev.service_id == service_id)
            match_type = (et is None or ev.event_type == et)
            if match_svc and match_type:
                canceled += 1
            else:
                new_heap.append(ev)

        if canceled > 0:
            heapq.heapify(new_heap)
            self._heap = new_heap
        return canceled

    def is_empty(self) -> bool:
        return len(self._heap) == 0

    def __len__(self) -> int:
        return len(self._heap)

    def clear(self):
        """Clear all events and reset the sequence counter."""
        self._heap.clear()
        self._seq_counter = 0

    def all_events(self) -> List[SimulationEvent]:
        """Return a sorted copy of all pending events."""
        return sorted(self._heap)
