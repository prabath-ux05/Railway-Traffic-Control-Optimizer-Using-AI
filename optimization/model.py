"""
optimization/model.py
~~~~~~~~~~~~~~~~~~~~~
Optimization problem formulations, input contracts, constraint specifications,
and decision representations for railway traffic management.

Defines the complete input contract (OptimizationRequest), constraint domain models,
and decision variable abstractions needed before mathematical solving.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictType
from simulation.network import (
    Junction,
    Network,
    Platform,
    Route,
    Service,
    Station,
    TimetableEntry,
    TrackSection,
    Train,
)
from simulation.state import SimulationState
from optimization.objective import ObjectiveWeights


def validate_data_time_resolution(network: Any, time_resolution: int) -> None:
    """Validate that every running time, headway, clearance, and dwell in the data is a multiple of 1/time_resolution.

    Raises ValueError with a clear explanation if any value is not an exact integer multiple of 1/R.
    """
    R = time_resolution
    if R <= 1:
        return

    # 1. Track sections: running time and minimum headway
    if hasattr(network, "track_sections") and network.track_sections:
        for ts_id, ts in sorted(network.track_sections.items()):
            rt = getattr(ts, "travel_time_minutes", None)
            if rt is not None:
                scaled = rt * R
                if abs(scaled - round(scaled)) > 1e-4:
                    raise ValueError(
                        f"Track section '{ts_id}' running time {rt} min is not an exact multiple of 1/time_resolution (1/{R} = {1.0/R:.4f} min)."
                    )
            hw = getattr(ts, "minimum_headway_minutes", None)
            if hw is not None and hw > 0:
                scaled = hw * R
                if abs(scaled - round(scaled)) > 1e-4:
                    raise ValueError(
                        f"Track section '{ts_id}' headway {hw} min is not an exact multiple of 1/time_resolution (1/{R} = {1.0/R:.4f} min)."
                    )

    # 2. Junction clearance times
    if hasattr(network, "junctions") and network.junctions:
        for jct_id, jct in sorted(network.junctions.items()):
            clr = getattr(jct, "clearance_time_minutes", 2.0)
            scaled = clr * R
            if abs(scaled - round(scaled)) > 1e-4:
                raise ValueError(
                    f"Junction '{jct_id}' clearance time {clr} min is not an exact multiple of 1/time_resolution (1/{R} = {1.0/R:.4f} min)."
                )

    # 3. Scheduled station dwell times
    if hasattr(network, "timetable") and network.timetable:
        for entry in network.timetable:
            if getattr(entry, "arrival", None) and getattr(entry, "departure", None):
                arr_m = time_to_minutes(entry.arrival)
                dep_m = time_to_minutes(entry.departure)
                dwell = (dep_m - arr_m) % 1440.0
                if dwell > 0:
                    scaled = dwell * R
                    if abs(scaled - round(scaled)) > 1e-4:
                        raise ValueError(
                            f"Timetable dwell for service '{entry.service_id}' at station '{entry.station_id}' ({dwell} min) is not an exact multiple of 1/time_resolution (1/{R} = {1.0/R:.4f} min)."
                        )


# ---------------------------------------------------------------------------
# Constraint Domain Models
# ---------------------------------------------------------------------------

@dataclass
class HeadwayConstraint:
    """Minimum safety temporal separation between consecutive trains on a track section."""
    section_id: str
    preceding_service_id: str
    following_service_id: str
    minimum_headway_minutes: float
    direction: Optional[str] = None


@dataclass
class JunctionConstraint:
    """Capacity and interlocking clearance constraint at a shared junction or throat."""
    junction_id: str
    node_id: str
    competing_service_ids: List[str]
    capacity: int = 1
    clearance_time_minutes: float = 2.0


@dataclass
class PlatformConstraint:
    """Platform capacity and station dwell duration bounds."""
    station_id: str
    platform_id: Optional[str]
    service_id: str
    min_dwell_minutes: float = 2.0
    max_dwell_minutes: float = 15.0


@dataclass
class PrecedenceConstraint:
    """Enforced dispatching sequence between two services at a shared bottleneck resource."""
    resource_id: str
    earlier_service_id: str
    later_service_id: str
    separation_minutes: float = 3.0
    reason: str = ""


# ---------------------------------------------------------------------------
# Decision Variable / Adjustment Domain Models
# ---------------------------------------------------------------------------

@dataclass
class ServiceTimetableAdjustment:
    """Proposed scheduled vs adjusted timings for a service stop.

    Attributes:
        service_id: Target service.
        station_id: Stop station or junction node ID.
        stop_sequence: 1-indexed stop sequence number.
        original_arrival: Original timetable arrival in minutes from midnight.
        original_departure: Original timetable departure in minutes.
        adjusted_arrival: Proposed optimized arrival time in minutes.
        adjusted_departure: Proposed optimized departure time in minutes.
        assigned_platform: Optional assigned platform ID.
        assigned_track_section: Optional assigned section ID.
        delay_minutes: Resulting delay (adjusted_arrival - original_arrival).
        dwell_minutes: Dwell time at station (adjusted_departure - adjusted_arrival).
    """
    service_id: str
    station_id: str
    stop_sequence: int
    original_arrival: Optional[float] = None
    original_departure: Optional[float] = None
    adjusted_arrival: Optional[float] = None
    adjusted_departure: Optional[float] = None
    assigned_platform: Optional[str] = None
    assigned_track_section: Optional[str] = None

    @property
    def delay_minutes(self) -> float:
        """Computed delay relative to original schedule."""
        if self.original_arrival is not None and self.adjusted_arrival is not None:
            return max(0.0, self.adjusted_arrival - self.original_arrival)
        if self.original_departure is not None and self.adjusted_departure is not None:
            return max(0.0, self.adjusted_departure - self.original_departure)
        return 0.0

    @property
    def dwell_minutes(self) -> float:
        """Computed station dwell time."""
        if self.adjusted_departure is not None and self.adjusted_arrival is not None:
            return max(0.0, self.adjusted_departure - self.adjusted_arrival)
        return 0.0

    @property
    def adjusted_arrival_str(self) -> Optional[str]:
        return minutes_to_time_str(self.adjusted_arrival) if self.adjusted_arrival is not None else None

    @property
    def adjusted_departure_str(self) -> Optional[str]:
        return minutes_to_time_str(self.adjusted_departure) if self.adjusted_departure is not None else None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "station_id": self.station_id,
            "stop_sequence": self.stop_sequence,
            "original_arrival": minutes_to_time_str(self.original_arrival) if self.original_arrival is not None else None,
            "original_departure": minutes_to_time_str(self.original_departure) if self.original_departure is not None else None,
            "adjusted_arrival": self.adjusted_arrival_str,
            "adjusted_departure": self.adjusted_departure_str,
            "assigned_platform": self.assigned_platform,
            "assigned_track_section": self.assigned_track_section,
            "delay_minutes": round(self.delay_minutes, 2),
            "dwell_minutes": round(self.dwell_minutes, 2),
        }


@dataclass
class PrecedenceDecision:
    """Dispatching decision establishing priority between two trains on a resource."""
    resource_id: str
    first_service_id: str
    second_service_id: str
    reason: str = "Priority / Headway resolution"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "first_service_id": self.first_service_id,
            "second_service_id": self.second_service_id,
            "reason": self.reason,
        }


@dataclass
class ResourceAllocationDecision:
    """Allocation decision assigning a specific physical resource to a service."""
    service_id: str
    node_or_section_id: str
    allocated_resource_id: str
    resource_type: str = "PLATFORM"  # PLATFORM, TRACK_SECTION, ROUTE

    def to_dict(self) -> Dict[str, Any]:
        return {
            "service_id": self.service_id,
            "node_or_section_id": self.node_or_section_id,
            "allocated_resource_id": self.allocated_resource_id,
            "resource_type": self.resource_type,
        }


# ---------------------------------------------------------------------------
# Optimization Input Contract
# ---------------------------------------------------------------------------

@dataclass
class OptimizationRequest:
    """Complete runtime input contract provided to the optimization layer.

    Contains all static network data, active simulation state, conflicts,
    constraints, and optimization parameters.
    """
    services: Dict[str, Service] = field(default_factory=dict)
    trains: Dict[str, Train] = field(default_factory=dict)
    timetable: List[TimetableEntry] = field(default_factory=list)
    routes: Dict[str, Route] = field(default_factory=dict)
    track_sections: Dict[str, TrackSection] = field(default_factory=dict)
    junctions: Dict[str, Junction] = field(default_factory=dict)
    platforms: Dict[str, Platform] = field(default_factory=dict)
    active_conflicts: List[Conflict] = field(default_factory=list)
    current_delays: Dict[str, float] = field(default_factory=dict)
    headway_constraints: List[HeadwayConstraint] = field(default_factory=list)
    junction_constraints: List[JunctionConstraint] = field(default_factory=list)
    platform_constraints: List[PlatformConstraint] = field(default_factory=list)
    precedence_constraints: List[PrecedenceConstraint] = field(default_factory=list)
    time_horizon: Tuple[float, float] = (0.0, 1440.0)  # (start_min, end_min)
    time_step_minutes: float = 1.0
    weights: ObjectiveWeights = field(default_factory=ObjectiveWeights)
    objective_mode: str = "WEIGHTED"
    fifo_timetables: Optional[Dict[str, List[ServiceTimetableAdjustment]]] = None
    enable_platform_conflicts: bool = False
    apply_midnight_wrap: bool = False
    time_resolution: int = 1

    @classmethod
    def from_network_and_state(
        cls,
        network: Network,
        state: Optional[SimulationState] = None,
        conflicts: Optional[List[Conflict]] = None,
        service_ids: Optional[List[str]] = None,
        time_horizon: Optional[Tuple[float, float]] = None,
        weights: Optional[ObjectiveWeights] = None,
        apply_midnight_wrap: bool = False,
        time_resolution: int = 1,
    ) -> "OptimizationRequest":
        """Factory constructor that builds an OptimizationRequest from network and state."""
        validate_data_time_resolution(network, time_resolution)

        # Filter services if subset requested
        svcs = network.services
        if service_ids is not None:
            svcs = {s_id: network.services[s_id] for s_id in service_ids if s_id in network.services}

        # Collect relevant trains, routes, timetables
        rel_trains = {s.train_id: network.trains[s.train_id] for s in svcs.values() if s.train_id in network.trains}
        rel_routes = {s.route_id: network.routes[s.route_id] for s in svcs.values() if s.route_id in network.routes}
        rel_tt = [e for e in network.timetable if e.service_id in svcs]

        # Extract current delays from state
        delays: Dict[str, float] = {}
        if state is not None:
            for s_id in svcs:
                if s_id in state.train_states:
                    delays[s_id] = state.train_states[s_id].delay_minutes

        # Build initial constraints from infrastructure
        headways: List[HeadwayConstraint] = []
        for sec in network.track_sections.values():
            if sec.minimum_headway_minutes > 0:
                headways.append(
                    HeadwayConstraint(
                        section_id=sec.id,
                        preceding_service_id="*",
                        following_service_id="*",
                        minimum_headway_minutes=sec.minimum_headway_minutes,
                        direction=sec.direction,
                    )
                )

        junctions_const: List[JunctionConstraint] = []
        for jct in network.junctions.values():
            junctions_const.append(
                JunctionConstraint(
                    junction_id=jct.id,
                    node_id=getattr(jct, "station_id", None) or jct.id,
                    competing_service_ids=list(svcs.keys()),
                    capacity=getattr(jct, "capacity", 1),
                )
            )

        horizon = time_horizon or (0.0, 1440.0)

        return cls(
            services=svcs,
            trains=rel_trains,
            timetable=rel_tt,
            routes=rel_routes,
            track_sections=network.track_sections,
            junctions=network.junctions,
            platforms=network.platforms,
            active_conflicts=conflicts or [],
            current_delays=delays,
            headway_constraints=headways,
            junction_constraints=junctions_const,
            time_horizon=horizon,
            apply_midnight_wrap=apply_midnight_wrap,
            time_resolution=time_resolution,
            weights=weights or ObjectiveWeights(),
        )


# ---------------------------------------------------------------------------
# Optimization Model Builder / Validator
# ---------------------------------------------------------------------------

class OptimizationModel:
    """Prepares and validates the optimization model structure before solving."""

    def __init__(self, request: OptimizationRequest):
        self.request = request
        self.validated: bool = False

    def validate(self) -> List[str]:
        """Verify model completeness and consistency. Returns list of warning/error messages."""
        issues: List[str] = []

        # 1. Verify all services have valid train and route
        for svc_id, svc in self.request.services.items():
            if svc.train_id not in self.request.trains:
                issues.append(f"Service '{svc_id}' references missing train '{svc.train_id}'")
            if svc.route_id not in self.request.routes:
                issues.append(f"Service '{svc_id}' references missing route '{svc.route_id}'")

        # 2. Verify all timetable entries map to valid services
        for entry in self.request.timetable:
            if entry.service_id not in self.request.services:
                issues.append(f"Timetable entry references missing service '{entry.service_id}'")

        self.validated = (len(issues) == 0)
        return issues

    def get_service_route_sections(self, service_id: str) -> List[TrackSection]:
        """Compute the sequence of track sections required by a service route."""
        if service_id not in self.request.services:
            return []
        svc = self.request.services[service_id]
        if svc.route_id not in self.request.routes:
            return []
        route = self.request.routes[svc.route_id]
        sections: List[TrackSection] = []

        for i in range(len(route.ordered_nodes) - 1):
            u, v = route.ordered_nodes[i], route.ordered_nodes[i + 1]
            for ts in self.request.track_sections.values():
                if ts.from_node == u and ts.to_node == v:
                    sections.append(ts)
                    break
        return sections
