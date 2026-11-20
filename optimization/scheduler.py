"""
optimization/scheduler.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Optimization output contracts, performance metrics reporting, and scheduler interfaces.

Defines the output data structures produced by the optimization engine:
- OptimizationResult: Final proposed schedule, decisions, and metrics.
- PerformanceMetrics: Quantitative evaluation (total delay, max delay, conflicts, throughput).
- BaseScheduler / BaselineScheduler: Interface and deterministic baseline scheduler.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictDetector
from simulation.network import Service, TimetableEntry, TrackSection
from optimization.model import (
    OptimizationRequest,
    PrecedenceDecision,
    ResourceAllocationDecision,
    ServiceTimetableAdjustment,
)
from optimization.objective import (
    ObjectiveCostBreakdown,
    OptimizationObjective,
    ObjectiveWeights,
)


@dataclass
class PerformanceMetrics:
    """Quantitative performance and quality metrics of an optimized schedule.

    Attributes:
        total_delay_minutes: Cumulative delay across all scheduled stops.
        max_delay_minutes: Peak delay for any individual train.
        total_weighted_delay: Delay weighted by train priority penalty weights.
        initial_conflict_count: Number of conflicts detected in input schedule.
        resolved_conflict_count: Number of conflicts successfully resolved.
        remaining_conflict_count: Conflicts remaining unresolved (0 for feasible solution).
        throughput_trains_completed: Total number of train services successfully scheduled.
        total_travel_time_minutes: Cumulative active run time of all services.
        on_time_performance_percent: Percentage of stops arriving within 5.0 min of timetable.
    """
    total_delay_minutes: float = 0.0
    max_delay_minutes: float = 0.0
    total_weighted_delay: float = 0.0
    initial_conflict_count: int = 0
    resolved_conflict_count: int = 0
    remaining_conflict_count: int = 0
    throughput_trains_completed: int = 0
    total_travel_time_minutes: float = 0.0
    on_time_performance_percent: float = 100.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_delay_minutes": round(self.total_delay_minutes, 2),
            "max_delay_minutes": round(self.max_delay_minutes, 2),
            "total_weighted_delay": round(self.total_weighted_delay, 2),
            "initial_conflict_count": self.initial_conflict_count,
            "resolved_conflict_count": self.resolved_conflict_count,
            "remaining_conflict_count": self.remaining_conflict_count,
            "throughput_trains_completed": self.throughput_trains_completed,
            "total_travel_time_minutes": round(self.total_travel_time_minutes, 2),
            "on_time_performance_percent": round(self.on_time_performance_percent, 2),
        }


@dataclass
class OptimizationResult:
    """Complete runtime output contract returned by the optimization engine.

    Attributes:
        status: Solver termination status ("OPTIMAL", "FEASIBLE", "BASELINE", "INFEASIBLE").
        adjusted_timetables: Map of service_id -> list of ServiceTimetableAdjustment stop timings.
        precedence_decisions: List of precedence ordering decisions at shared bottlenecks.
        resource_decisions: List of platform and track section allocation decisions.
        metrics: Quantitative performance metrics.
        cost_breakdown: Detailed objective cost breakdown.
        unresolved_conflicts: Any remaining conflicts that could not be resolved.
        computation_time_seconds: Elapsed solver execution duration in seconds.
    """
    status: str = "BASELINE"
    adjusted_timetables: Dict[str, List[ServiceTimetableAdjustment]] = field(default_factory=dict)
    precedence_decisions: List[PrecedenceDecision] = field(default_factory=list)
    resource_decisions: List[ResourceAllocationDecision] = field(default_factory=list)
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    cost_breakdown: ObjectiveCostBreakdown = field(default_factory=ObjectiveCostBreakdown)
    unresolved_conflicts: List[Conflict] = field(default_factory=list)
    computation_time_seconds: float = 0.0

    @property
    def total_delay(self) -> float:
        return self.metrics.total_delay_minutes

    @property
    def conflict_count(self) -> int:
        return self.metrics.remaining_conflict_count

    @property
    def throughput(self) -> int:
        return self.metrics.throughput_trains_completed

    def summary(self) -> str:
        """Generate human-readable summary of optimization results."""
        lines = [
            f"=== Railway Optimization Result ({self.status}) ===",
            f"Total Delay:        {self.metrics.total_delay_minutes:.1f} min (Max: {self.metrics.max_delay_minutes:.1f} min)",
            f"Weighted Delay:     {self.metrics.total_weighted_delay:.1f} min",
            f"Conflicts:          {self.metrics.remaining_conflict_count} remaining ({self.metrics.resolved_conflict_count} resolved of {self.metrics.initial_conflict_count})",
            f"Throughput:         {self.metrics.throughput_trains_completed} services scheduled",
            f"On-Time Perf:       {self.metrics.on_time_performance_percent:.1f}%",
            f"Precedence Decs:    {len(self.precedence_decisions)}",
            f"Resource Decs:      {len(self.resource_decisions)}",
            f"Objective Cost:     {self.cost_breakdown.total_cost:.2f}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize complete optimization output to dictionary."""
        return {
            "status": self.status,
            "metrics": self.metrics.to_dict(),
            "cost_breakdown": self.cost_breakdown.to_dict(),
            "precedence_decisions": [d.to_dict() for d in self.precedence_decisions],
            "resource_decisions": [d.to_dict() for d in self.resource_decisions],
            "adjusted_timetables": {
                s_id: [a.to_dict() for a in adj_list]
                for s_id, adj_list in self.adjusted_timetables.items()
            },
            "unresolved_conflicts": [c.to_dict() for c in self.unresolved_conflicts],
            "computation_time_seconds": round(self.computation_time_seconds, 3),
        }


# ---------------------------------------------------------------------------
# Scheduler Interface & Baseline Implementation
# ---------------------------------------------------------------------------

class BaseScheduler(ABC):
    """Abstract interface for railway dispatching and timetable optimization schedulers."""

    @abstractmethod
    def schedule(self, request: OptimizationRequest) -> OptimizationResult:
        """Compute an optimized schedule fulfilling the input OptimizationRequest."""
        pass


class BaselineScheduler(BaseScheduler):
    """Deterministic passive baseline scheduler (unconstrained timetable shift).

    Constructs initial timetable adjustments directly from input timetable
    and computes baseline delay, conflict, and throughput metrics without
    solving constraints. Serves as published timetable reference comparator.
    """

    def __init__(self, objective: Optional[OptimizationObjective] = None):
        self.objective = objective or OptimizationObjective()

    def schedule(self, request: OptimizationRequest) -> OptimizationResult:
        """Generate passive baseline schedule from published timetable."""
        adjusted_timetables: Dict[str, List[ServiceTimetableAdjustment]] = {}
        total_delay = 0.0
        max_delay = 0.0
        total_weighted_delay = 0.0
        on_time_count = 0
        total_stops = 0

        # Group timetable entries by service
        for s_id, service in request.services.items():
            entries = [e for e in request.timetable if e.service_id == s_id]
            entries.sort(key=lambda e: e.stop_sequence)
            adj_list: List[ServiceTimetableAdjustment] = []

            last_t = -1.0
            day_offset = 0.0
            for entry in entries:
                total_stops += 1
                arr_min = time_to_minutes(entry.arrival) if entry.arrival is not None else None
                dep_min = time_to_minutes(entry.departure) if entry.departure is not None else None

                if getattr(request, "apply_midnight_wrap", False):
                    if arr_min is not None:
                        calc_a = arr_min + day_offset
                        if calc_a < last_t and (calc_a + 1440.0) >= last_t:
                            day_offset += 1440.0
                            calc_a += 1440.0
                        last_t = max(last_t, calc_a)
                        arr_min = calc_a
                    if dep_min is not None:
                        calc_d = dep_min + day_offset
                        if calc_d < last_t and (calc_d + 1440.0) >= last_t:
                            day_offset += 1440.0
                            calc_d += 1440.0
                        last_t = max(last_t, calc_d)
                        dep_min = calc_d

                current_delay = request.current_delays.get(s_id, 0.0)
                adj_arr = (arr_min + current_delay) if arr_min is not None else None
                adj_dep = (dep_min + current_delay) if dep_min is not None else None

                adj = ServiceTimetableAdjustment(
                    service_id=s_id,
                    station_id=entry.station_id,
                    stop_sequence=entry.stop_sequence,
                    original_arrival=arr_min,
                    original_departure=dep_min,
                    adjusted_arrival=adj_arr,
                    adjusted_departure=adj_dep,
                )
                adj_list.append(adj)

                delay = adj.delay_minutes
                total_delay += delay
                if delay > max_delay:
                    max_delay = delay
                total_weighted_delay += delay * service.delay_penalty_weight
                if delay <= 5.0:
                    on_time_count += 1

            adjusted_timetables[s_id] = adj_list

        on_time_pct = (on_time_count / total_stops * 100.0) if total_stops > 0 else 100.0
        init_conflicts = len(request.active_conflicts)

        metrics = PerformanceMetrics(
            total_delay_minutes=total_delay,
            max_delay_minutes=max_delay,
            total_weighted_delay=total_weighted_delay,
            initial_conflict_count=init_conflicts,
            resolved_conflict_count=0,
            remaining_conflict_count=init_conflicts,
            throughput_trains_completed=len(request.services),
            on_time_performance_percent=on_time_pct,
        )

        cost_breakdown = self.objective.evaluate_cost(
            total_delay_minutes=total_delay,
            total_weighted_delay=total_weighted_delay,
            max_delay_minutes=max_delay,
            conflicts=request.active_conflicts,
        )

        return OptimizationResult(
            status="BASELINE",
            adjusted_timetables=adjusted_timetables,
            precedence_decisions=[],
            resource_decisions=[],
            metrics=metrics,
            cost_breakdown=cost_breakdown,
            unresolved_conflicts=list(request.active_conflicts),
            computation_time_seconds=0.001,
        )


# Backward compatibility alias
PassiveBaselineScheduler = BaselineScheduler


class FeasibleBaselineScheduler(BaseScheduler):
    """Deterministic, physically feasible baseline scheduler (FIFO / FCFS rule-based dispatching).

    Enforces the exact same physical and operational constraints as CP-SAT:
    - Route preservation & sequential node traversal
    - Minimum track section running times from TrackSection infrastructure data
    - Minimum commercial station dwell times
    - Non-early departure from timetable stops
    - Minimum headway intervals between consecutive trains on the same track section
    - Section capacity limits (single-track exclusivity & multi-track throats)
    - Opposing movement exclusivity on shared bidirectional corridors
    - Junction capacity constraints and interlocking clearance

    Applies a standard operational First-In-First-Out (FIFO) greedy dispatching policy
    WITHOUT mathematical optimization or MIP search. Provides a true physically valid
    benchmark for evaluating optimization gains.
    """

    def __init__(self, objective: Optional[OptimizationObjective] = None):
        self.objective = objective or OptimizationObjective()

    def schedule(self, request: OptimizationRequest) -> OptimizationResult:
        """Generate a physically feasible schedule using deterministic FIFO dispatching."""
        if not request.services:
            return OptimizationResult(
                status="FEASIBLE_BASELINE",
                adjusted_timetables={},
                metrics=PerformanceMetrics(),
                cost_breakdown=ObjectiveCostBreakdown(),
                computation_time_seconds=0.001,
            )

        # 1. Timetable & Track Lookup Helpers
        tt_lookup: Dict[Tuple[str, str], TimetableEntry] = {
            (e.service_id, e.station_id): e for e in request.timetable
        }

        def get_track_section(u: str, v: str, preferred_dir: Optional[str] = None) -> Optional[TrackSection]:
            candidates = [ts for ts in request.track_sections.values() if ts.from_node == u and ts.to_node == v]
            if not candidates:
                return None
            if preferred_dir:
                p_dir = preferred_dir.upper()
                for ts in candidates:
                    if ts.direction and (ts.direction.upper() == p_dir or ts.direction.upper() in ("BOTH", "BIDIRECTIONAL")):
                        return ts
            return candidates[0]

        # 2. Determine initial ready times at origin
        # Sort services by initial ready departure time for deterministic FIFO processing
        service_initial_times: List[Tuple[float, str]] = []
        service_routes: Dict[str, List[str]] = {}

        for s_id, service in request.services.items():
            route = request.routes.get(service.route_id)
            if not route or not route.ordered_nodes:
                continue
            service_routes[s_id] = route.ordered_nodes
            origin_node = route.ordered_nodes[0]
            tt_origin = tt_lookup.get((s_id, origin_node))

            sched_dep = time_to_minutes(tt_origin.departure) if (tt_origin and tt_origin.departure) else 0.0
            cur_delay = request.current_delays.get(s_id, 0.0)
            ready_dep = max(0.0, sched_dep + cur_delay)
            service_initial_times.append((ready_dep, s_id))

        # Sort FIFO: earliest ready departure first, break ties by service_id
        service_initial_times.sort(key=lambda x: (x[0], x[1]))

        # 3. Global Resource Reservation Maps
        section_occupancies: Dict[str, List[Tuple[float, float, float, str]]] = {}
        corridor_occupancies: Dict[str, List[Tuple[float, float, str, str]]] = {}
        junction_occupancies: Dict[str, List[Tuple[float, float, str]]] = {}

        # Track results
        node_timings: Dict[str, Dict[int, Tuple[float, float]]] = {}
        precedence_decisions: List[PrecedenceDecision] = []
        resource_decisions: List[ResourceAllocationDecision] = []

        # 4. Simulate each train sequentially in FIFO order
        for ready_dep_0, s_id in service_initial_times:
            nodes = service_routes[s_id]
            service = request.services[s_id]
            route = request.routes[service.route_id]
            dir_hint = "UP" if "UP" in route.id else ("DOWN" if "DOWN" in route.id else "BOTH")

            timings: Dict[int, Tuple[float, float]] = {}
            curr_ready_time = ready_dep_0
            timings[0] = (curr_ready_time, curr_ready_time)

            for i in range(len(nodes) - 1):
                u, v = nodes[i], nodes[i + 1]
                ts = get_track_section(u, v, dir_hint)

                travel_time = float(ts.travel_time_minutes) if ts else 3.0
                travel_time = max(1.0, travel_time)
                headway = float(ts.minimum_headway_minutes) if (ts and ts.minimum_headway_minutes > 0) else 3.0
                headway = max(1.0, headway)
                capacity = ts.capacity if ts else 1
                sec_id = ts.id if ts else f"SEC_{u}_{v}"
                corridor_key = "_".join(sorted([u, v]))

                dep_u = curr_ready_time

                while True:
                    bumped = False
                    entry_t = dep_u
                    exit_t = entry_t + travel_time

                    # A. Headway & Capacity constraint on section
                    sec_list = section_occupancies.get(sec_id, [])
                    if sec_list:
                        for prev_entry, prev_exit, prev_clear, prev_sid in sec_list:
                            if prev_sid != s_id:
                                if entry_t < prev_entry + headway:
                                    dep_u = max(dep_u, prev_entry + headway)
                                    bumped = True
                                    precedence_decisions.append(
                                        PrecedenceDecision(
                                            resource_id=sec_id,
                                            first_service_id=prev_sid,
                                            second_service_id=s_id,
                                            reason=f"HEADWAY_FIFO (min {headway}m)",
                                        )
                                    )

                        if capacity > 0:
                            overlap_count = sum(
                                1 for prev_entry, prev_exit, _, prev_sid in sec_list
                                if prev_sid != s_id and not (exit_t <= prev_entry or entry_t >= prev_exit)
                            )
                            if overlap_count >= capacity:
                                earliest_exit = min(
                                    prev_exit for prev_entry, prev_exit, _, prev_sid in sec_list
                                    if prev_sid != s_id and not (exit_t <= prev_entry or entry_t >= prev_exit)
                                )
                                dep_u = max(dep_u, earliest_exit)
                                bumped = True

                    # B. Opposing movement exclusivity on shared line
                    corr_list = corridor_occupancies.get(corridor_key, [])
                    if corr_list:
                        for prev_entry, prev_exit, prev_dir, prev_sid in corr_list:
                            if prev_sid != s_id and prev_dir != dir_hint and prev_dir != "BOTH" and dir_hint != "BOTH":
                                if not (exit_t <= prev_entry or entry_t >= prev_exit):
                                    dep_u = max(dep_u, prev_exit)
                                    bumped = True
                                    precedence_decisions.append(
                                        PrecedenceDecision(
                                            resource_id=corridor_key,
                                            first_service_id=prev_sid,
                                            second_service_id=s_id,
                                            reason="OPPOSING_MOVEMENT_FIFO",
                                        )
                                    )

                    # C. Junction constraints
                    for jct_const in request.junction_constraints:
                        node_match = (u == jct_const.node_id or u in jct_const.junction_id or v == jct_const.node_id)
                        if node_match:
                            j_cap = jct_const.capacity
                            j_clear = float(jct_const.clearance_time_minutes)
                            j_list = junction_occupancies.get(jct_const.junction_id, [])
                            overlap_j = sum(
                                1 for j_entry, j_exit, j_sid in j_list
                                if j_sid != s_id and not (entry_t + j_clear <= j_entry or entry_t >= j_exit)
                            )
                            if overlap_j >= j_cap:
                                earliest_j_exit = min(
                                    j_exit for j_entry, j_exit, j_sid in j_list
                                    if j_sid != s_id and not (entry_t + j_clear <= j_entry or entry_t >= j_exit)
                                )
                                dep_u = max(dep_u, earliest_j_exit)
                                bumped = True

                    if not bumped:
                        break

                # Confirm departure at u and arrival at v
                timings[i] = (timings[i][0], dep_u)
                arr_v = dep_u + travel_time
                safety_clear = arr_v + headway

                # Record reservations
                if sec_id not in section_occupancies:
                    section_occupancies[sec_id] = []
                section_occupancies[sec_id].append((dep_u, arr_v, safety_clear, s_id))

                if corridor_key not in corridor_occupancies:
                    corridor_occupancies[corridor_key] = []
                corridor_occupancies[corridor_key].append((dep_u, arr_v, dir_hint, s_id))

                resource_decisions.append(
                    ResourceAllocationDecision(
                        service_id=s_id,
                        node_or_section_id=sec_id,
                        allocated_resource_id=sec_id,
                        resource_type="TRACK_SECTION",
                    )
                )

                for jct_const in request.junction_constraints:
                    if u == jct_const.node_id or u in jct_const.junction_id or v == jct_const.node_id:
                        j_clear = float(jct_const.clearance_time_minutes)
                        if jct_const.junction_id not in junction_occupancies:
                            junction_occupancies[jct_const.junction_id] = []
                        junction_occupancies[jct_const.junction_id].append((dep_u, dep_u + j_clear, s_id))

                # Intermediate dwell at node i+1 (station v)
                if i + 1 < len(nodes) - 1:
                    tt_v = tt_lookup.get((s_id, v))
                    if tt_v and tt_v.arrival and tt_v.departure:
                        sched_arr = time_to_minutes(tt_v.arrival)
                        sched_dep = time_to_minutes(tt_v.departure)
                        if getattr(request, "apply_midnight_wrap", False):
                            if sched_arr < curr_ready_time and (sched_arr + 1440.0) >= curr_ready_time:
                                sched_arr += 1440.0
                            if sched_dep < sched_arr and (sched_dep + 1440.0) >= sched_arr:
                                sched_dep += 1440.0
                        sched_dwell = max(1.0, sched_dep - sched_arr)
                    elif tt_v and tt_v.is_commercial_stop:
                        sched_dwell = 1.0
                        sched_dep = None
                    else:
                        sched_dwell = 0.0
                        sched_dep = None

                    dep_v = arr_v + sched_dwell
                    if sched_dep is not None:
                        dep_v = max(dep_v, sched_dep)

                    timings[i + 1] = (arr_v, dep_v)
                    curr_ready_time = dep_v
                else:
                    # Terminus
                    timings[i + 1] = (arr_v, arr_v)

            node_timings[s_id] = timings

        # 5. Extract ServiceTimetableAdjustment, Calculate Metrics & Cost
        adjusted_timetables: Dict[str, List[ServiceTimetableAdjustment]] = {}
        total_delay = 0.0
        max_delay = 0.0
        total_weighted_delay = 0.0
        on_time_count = 0
        total_stops = 0

        for s_id, service in request.services.items():
            if s_id not in service_routes or s_id not in node_timings:
                continue
            nodes = service_routes[s_id]
            timings = node_timings[s_id]
            entries = [e for e in request.timetable if e.service_id == s_id]
            entries.sort(key=lambda e: e.stop_sequence)
            adj_list: List[ServiceTimetableAdjustment] = []

            last_t = -1.0
            day_offset = 0.0
            for entry in entries:
                total_stops += 1
                orig_arr_min = time_to_minutes(entry.arrival) if entry.arrival else None
                orig_dep_min = time_to_minutes(entry.departure) if entry.departure else None

                if getattr(request, "apply_midnight_wrap", False):
                    if orig_arr_min is not None:
                        calc_a = orig_arr_min + day_offset
                        if calc_a < last_t and (calc_a + 1440.0) >= last_t:
                            day_offset += 1440.0
                            calc_a += 1440.0
                        last_t = max(last_t, calc_a)
                        orig_arr_min = calc_a
                    if orig_dep_min is not None:
                        calc_d = orig_dep_min + day_offset
                        if calc_d < last_t and (calc_d + 1440.0) >= last_t:
                            day_offset += 1440.0
                            calc_d += 1440.0
                        last_t = max(last_t, calc_d)
                        orig_dep_min = calc_d

                node_idx = None
                for idx, n in enumerate(nodes):
                    if n == entry.station_id:
                        node_idx = idx
                        break

                if node_idx is not None and node_idx in timings:
                    adj_arr_min, adj_dep_min = timings[node_idx]
                else:
                    adj_arr_min = orig_arr_min
                    adj_dep_min = orig_dep_min

                adj = ServiceTimetableAdjustment(
                    service_id=s_id,
                    station_id=entry.station_id,
                    stop_sequence=entry.stop_sequence,
                    original_arrival=orig_arr_min,
                    original_departure=orig_dep_min,
                    adjusted_arrival=adj_arr_min,
                    adjusted_departure=adj_dep_min,
                )
                adj_list.append(adj)

                delay = adj.delay_minutes
                total_delay += delay
                if delay > max_delay:
                    max_delay = delay
                total_weighted_delay += delay * service.delay_penalty_weight
                if delay <= 5.0:
                    on_time_count += 1

            adjusted_timetables[s_id] = adj_list

        on_time_pct = (on_time_count / total_stops * 100.0) if total_stops > 0 else 100.0
        init_conflicts = len(request.active_conflicts)

        metrics = PerformanceMetrics(
            total_delay_minutes=total_delay,
            max_delay_minutes=max_delay,
            total_weighted_delay=total_weighted_delay,
            initial_conflict_count=init_conflicts,
            resolved_conflict_count=init_conflicts,
            remaining_conflict_count=0,
            throughput_trains_completed=len(request.services),
            on_time_performance_percent=on_time_pct,
        )

        cost_breakdown = self.objective.evaluate_cost(
            total_delay_minutes=total_delay,
            total_weighted_delay=total_weighted_delay,
            max_delay_minutes=max_delay,
            conflicts=[],
        )

        return OptimizationResult(
            status="FEASIBLE_BASELINE",
            adjusted_timetables=adjusted_timetables,
            precedence_decisions=precedence_decisions,
            resource_decisions=resource_decisions,
            metrics=metrics,
            cost_breakdown=cost_breakdown,
            unresolved_conflicts=[],
            computation_time_seconds=0.005,
        )
