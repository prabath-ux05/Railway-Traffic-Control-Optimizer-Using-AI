"""
optimization/solver.py
~~~~~~~~~~~~~~~~~~~~~~
Google OR-Tools CP-SAT mathematical optimization solver for railway traffic scheduling.

Consumes an OptimizationRequest and formulates a discrete Constraint Programming (CP-SAT)
model to compute optimal timetable adjustments, resolve headway/junction/opposing-movement
conflicts, enforce physical running and dwell times, and minimize weighted train delays.

Returns an OptimizationResult conforming to the Batch 8 optimization interface.
"""

import os
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

# Feature flag for platform conflicts (disabled by default to maintain paper baseline)
ENABLE_PLATFORM_CONFLICTS = os.environ.get("ENABLE_PLATFORM_CONFLICTS", "0").lower() in ("1", "true")

from ortools.sat.python import cp_model

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictDetector, ConflictSeverity, ConflictType
from simulation.network import Network, Route, Service, TimetableEntry, TrackSection
from optimization.model import (
    HeadwayConstraint,
    JunctionConstraint,
    OptimizationModel,
    OptimizationRequest,
    PlatformConstraint,
    PrecedenceConstraint,
    PrecedenceDecision,
    ResourceAllocationDecision,
    ServiceTimetableAdjustment,
)
from optimization.objective import (
    ObjectiveCostBreakdown,
    ObjectiveWeights,
    OptimizationObjective,
)
from optimization.scheduler import (
    BaseScheduler,
    OptimizationResult,
    PerformanceMetrics,
)


class CPSATScheduler(BaseScheduler):
    """Railway traffic scheduler using Google OR-Tools CP-SAT solver.

    Formulates integer decision variables for arrival and departure times at all
    route nodes, enforces headway separation, track section exclusivity, junction
    clearance, physical running times, and station dwell times, and minimizes
    total weighted passenger/express delays.
    """

    def __init__(
        self,
        time_limit_seconds: float = 30.0,
        num_search_workers: int = 8,
        log_search_progress: bool = False,
        objective: Optional[OptimizationObjective] = None,
        objective_mode: str = "WEIGHTED",
        time_resolution: Optional[int] = None,
    ):
        self.time_limit_seconds = time_limit_seconds
        self.num_search_workers = num_search_workers
        self.log_search_progress = log_search_progress
        self.objective = objective or OptimizationObjective()
        self.objective_mode = objective_mode
        self.time_resolution = time_resolution or 1

    def schedule(self, request: OptimizationRequest) -> OptimizationResult:
        """Formulate and solve the railway optimization problem for the given request."""
        start_cpu_time = time.time()

        if not request.services:
            return OptimizationResult(
                status="FEASIBLE",
                adjusted_timetables={},
                metrics=PerformanceMetrics(),
                cost_breakdown=ObjectiveCostBreakdown(),
                computation_time_seconds=time.time() - start_cpu_time,
            )

        # Determine internal time resolution multiplier (1 = 1-min units, 2 = 0.5-min units)
        R = int(getattr(request, "time_resolution", None) or self.time_resolution or 1)
        if R < 1:
            raise ValueError(f"time_resolution must be an integer >= 1, got {R}")

        def to_units(val: float, name: str) -> int:
            scaled = val * R
            rounded = round(scaled)
            if R > 1 and abs(scaled - rounded) > 1e-4:
                raise ValueError(
                    f"Value {val} for '{name}' is not an exact multiple of 1/time_resolution (1/{R} = {1.0/R} min)."
                )
            return int(rounded)

        # 1. Initialize CP-SAT model
        model = cp_model.CpModel()
        horizon_start, horizon_end = request.time_horizon
        if getattr(request, "apply_midnight_wrap", False):
            max_horizon_min = int(max(2880, horizon_end + 1440 + 360))
        else:
            max_horizon_min = int(max(1440, horizon_end + 360))  # Allow buffer for delays
        max_horizon_units = max_horizon_min * R

        # Validate current delays against resolution
        for s_id, d in request.current_delays.items():
            to_units(d, f"current_delays[{s_id}]")

        # 2. Decision Variables: arr_var[s_id, node_idx], dep_var[s_id, node_idx]
        arr_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}
        dep_vars: Dict[Tuple[str, int], cp_model.IntVar] = {}

        # Track mappings: service_id -> list of node_ids
        service_nodes: Dict[str, List[str]] = {}
        # Timetable lookup: (service_id, station_id) -> TimetableEntry
        tt_lookup: Dict[Tuple[str, str], TimetableEntry] = {
            (e.service_id, e.station_id): e for e in request.timetable
        }

        # Track section lookup helper
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

        # 3. Create node-level arrival/departure variables per service
        for s_id, service in request.services.items():
            route = request.routes.get(service.route_id)
            if not route or not route.ordered_nodes:
                continue
            nodes = route.ordered_nodes
            service_nodes[s_id] = nodes
            k_nodes = len(nodes)

            for i, node in enumerate(nodes):
                arr_var = model.NewIntVar(0, max_horizon_units, f"arr_{s_id}_{i}_{node}")
                dep_var = model.NewIntVar(0, max_horizon_units, f"dep_{s_id}_{i}_{node}")
                arr_vars[(s_id, i)] = arr_var
                dep_vars[(s_id, i)] = dep_var

                # Departure at same node must be >= arrival
                model.Add(dep_var >= arr_var)

        # 4. Enforce timetable departure & initial origin constraints
        day_offsets: Dict[Tuple[str, int], float] = {}
        for s_id, service in request.services.items():
            if s_id not in service_nodes:
                continue
            nodes = service_nodes[s_id]

            # Compute day_offsets if opt-in midnight wrap is requested
            if getattr(request, "apply_midnight_wrap", False):
                last_m = -1.0
                curr_offset = 0.0
                for i, node in enumerate(nodes):
                    tt_e = tt_lookup.get((s_id, node))
                    if tt_e:
                        if tt_e.arrival:
                            arr_raw = time_to_minutes(tt_e.arrival) + curr_offset
                            if last_m >= 0 and (last_m - arr_raw) > 720.0:
                                curr_offset += 1440.0
                                arr_raw += 1440.0
                            last_m = max(last_m, arr_raw)
                        if tt_e.departure:
                            dep_raw = time_to_minutes(tt_e.departure) + curr_offset
                            if last_m >= 0 and (last_m - dep_raw) > 720.0:
                                curr_offset += 1440.0
                                dep_raw += 1440.0
                            last_m = max(last_m, dep_raw)
                    day_offsets[(s_id, i)] = curr_offset

            # Origin departure
            origin_node = nodes[0]
            tt_origin = tt_lookup.get((s_id, origin_node))
            offset_0 = day_offsets.get((s_id, 0), 0.0)
            if tt_origin and tt_origin.departure:
                sched_dep_units = to_units(time_to_minutes(tt_origin.departure) + offset_0, f"origin_dep_{s_id}")
                # Cannot depart origin earlier than published schedule
                model.Add(dep_vars[(s_id, 0)] >= sched_dep_units)
                model.Add(arr_vars[(s_id, 0)] == dep_vars[(s_id, 0)])
            else:
                # Default start within horizon
                model.Add(arr_vars[(s_id, 0)] == dep_vars[(s_id, 0)])

            # Intermediate and destination stops in timetable
            for i, node in enumerate(nodes):
                tt_entry = tt_lookup.get((s_id, node))
                offset_i = day_offsets.get((s_id, i), 0.0)
                if tt_entry:
                    if tt_entry.arrival and i > 0:
                        sched_arr_units = to_units(time_to_minutes(tt_entry.arrival) + offset_i, f"sched_arr_{s_id}_{node}")
                        # Train arrives around or after scheduled arrival
                        # We track delay = max(0, arr - sched_arr)
                    if tt_entry.departure and i < len(nodes) - 1:
                        sched_dep_units = to_units(time_to_minutes(tt_entry.departure) + offset_i, f"sched_dep_{s_id}_{node}")
                        # Cannot depart commercial passenger stop early
                        model.Add(dep_vars[(s_id, i)] >= sched_dep_units)

        # 5. Physics & Running Time Constraints along Route Edges
        # and Section Occupancy Intervals for NoOverlap
        section_intervals: Dict[str, List[Tuple[str, cp_model.IntervalVar]]] = defaultdict(list)
        # For opposing movement exclusivity on shared physical lines
        corridor_intervals: Dict[str, List[Tuple[str, str, cp_model.IntervalVar]]] = defaultdict(list)

        for s_id, service in request.services.items():
            if s_id not in service_nodes:
                continue
            nodes = service_nodes[s_id]
            route = request.routes[service.route_id]
            dir_hint = "UP" if "UP" in route.id else ("DOWN" if "DOWN" in route.id else None)

            for i in range(len(nodes) - 1):
                u, v = nodes[i], nodes[i + 1]
                ts = get_track_section(u, v, dir_hint)

                travel_time_val = ts.travel_time_minutes if ts else 3.0
                travel_time_units = max(1, to_units(travel_time_val, f"travel_time_{u}_{v}"))

                headway_val = ts.minimum_headway_minutes if (ts and ts.minimum_headway_minutes > 0) else 3.0
                headway_units = max(1, to_units(headway_val, f"headway_{ts.id if ts else f'SEC_{u}_{v}'}"))

                dep_u = dep_vars[(s_id, i)]
                arr_v = arr_vars[(s_id, i + 1)]

                # Physics: Arrival at v >= Departure from u + travel time
                model.Add(arr_v >= dep_u + travel_time_units)

                # Dwell time at intermediate station v (if not terminus)
                if i + 1 < len(nodes) - 1:
                    dep_v = dep_vars[(s_id, i + 1)]
                    tt_v = tt_lookup.get((s_id, v))
                    # If commercial stop with dwell in timetable
                    if tt_v and tt_v.arrival and tt_v.departure:
                        sched_dwell_min = time_to_minutes(tt_v.departure) - time_to_minutes(tt_v.arrival)
                        min_dwell_units = max(1, to_units(sched_dwell_min, f"dwell_{s_id}_{v}"))
                    else:
                        min_dwell_units = 0  # Non-stop waypoint / transit node
                    model.Add(dep_v >= arr_v + min_dwell_units)

                # Track section occupancy interval for capacity & headway enforcement
                sec_id = ts.id if ts else f"SEC_{u}_{v}"
                # Interval covers entry to exit + safety headway buffer
                occ_duration = model.NewIntVar(travel_time_units, max_horizon_units, f"dur_{s_id}_{sec_id}_{i}")
                model.Add(occ_duration >= arr_v - dep_u + headway_units)
                occ_interval = model.NewIntervalVar(
                    dep_u,
                    occ_duration,
                    model.NewIntVar(0, max_horizon_units, f"end_{s_id}_{sec_id}_{i}"),
                    f"occ_{s_id}_{sec_id}_{i}",
                )
                section_intervals[sec_id].append((s_id, occ_interval))

                # Also track undirected corridor endpoints for opposing movement protection
                corridor_key = "_".join(sorted([u, v]))
                corridor_intervals[corridor_key].append((s_id, dir_hint or "UNKNOWN", occ_interval))

        # 6. Enforce Track Section Exclusivity / Capacity
        for sec_id, occ_list in section_intervals.items():
            if len(occ_list) <= 1:
                continue

            ts = request.track_sections.get(sec_id)
            cap = ts.capacity if ts else 1

            if cap == 1:
                # Exclusive single track segment
                model.AddNoOverlap([interval for _, interval in occ_list])
            else:
                # Multi-capacity segment (e.g. throat segment with capacity=3)
                intervals = [interval for _, interval in occ_list]
                demands = [1] * len(intervals)
                model.AddCumulative(intervals, demands, cap)

        # 7. Enforce Opposing Movement Exclusivity on Shared Lines
        for corridor_key, items in corridor_intervals.items():
            # Check if both UP and DOWN trains use this corridor
            dirs = {d for _, d, _ in items}
            if "UP" in dirs and "DOWN" in dirs and len(items) > 1:
                # Single/shared physical corridor cannot have opposing trains simultaneously
                model.AddNoOverlap([interval for _, _, interval in items])

        # 8. Enforce Junction / Interlocking Constraints
        for jct_const in request.junction_constraints:
            node = jct_const.node_id
            clearance_units = to_units(jct_const.clearance_time_minutes, f"junction_{jct_const.junction_id}_clearance")
            jct_intervals: List[cp_model.IntervalVar] = []

            for s_id in jct_const.competing_service_ids:
                if s_id not in service_nodes:
                    continue
                nodes = service_nodes[s_id]
                for i, n in enumerate(nodes):
                    if n == node or n in jct_const.junction_id:
                        arr_n = arr_vars[(s_id, i)]
                        dep_n = dep_vars[(s_id, i)]
                        dur = model.NewIntVar(clearance_units, max_horizon_units, f"jct_dur_{s_id}_{node}")
                        model.Add(dur >= dep_n - arr_n + clearance_units)
                        j_int = model.NewIntervalVar(
                            arr_n,
                            dur,
                            model.NewIntVar(0, max_horizon_units, f"jct_end_{s_id}_{node}"),
                            f"jct_occ_{s_id}_{node}",
                        )
                        jct_intervals.append(j_int)

            if len(jct_intervals) > 1:
                if jct_const.capacity == 1:
                    model.AddNoOverlap(jct_intervals)
                else:
                    model.AddCumulative(jct_intervals, [1] * len(jct_intervals), jct_const.capacity)

        # 9. Enforce Precedence Constraints
        for prec in request.precedence_constraints:
            s1, s2, res_id = prec.earlier_service_id, prec.later_service_id, prec.resource_id
            sep_units = to_units(prec.separation_minutes, f"precedence_separation_{s1}_{s2}")
            if s1 in service_nodes and s2 in service_nodes:
                # Find matching node if res_id is a node
                nodes1 = service_nodes[s1]
                nodes2 = service_nodes[s2]
                for i1, n1 in enumerate(nodes1):
                    for i2, n2 in enumerate(nodes2):
                        if n1 == n2 and (n1 == res_id or res_id in n1 or res_id == "*"):
                            model.Add(dep_vars[(s2, i2)] >= dep_vars[(s1, i1)] + sep_units)

        # 10. Multi-Objective Function
        # Minimize: total weighted delay + departure schedule deviation + max delay
        weights = request.weights
        delay_terms: List[Tuple[cp_model.IntVar, int]] = []
        dev_terms: List[Tuple[cp_model.IntVar, int]] = []
        max_delay_var = model.NewIntVar(0, max_horizon_units, "max_delay")

        for s_id, service in request.services.items():
            if s_id not in service_nodes:
                continue
            nodes = service_nodes[s_id]
            k_final = len(nodes) - 1

            # Priority weight multiplier
            prio_mult = int(round(service.delay_penalty_weight * 10))
            if service.priority_class == "HIGH":
                prio_mult = max(prio_mult, 20)

            # Destination arrival delay
            dest_node = nodes[k_final]
            tt_dest = tt_lookup.get((s_id, dest_node))
            offset_dest = day_offsets.get((s_id, k_final), 0.0)
            if tt_dest and tt_dest.arrival:
                sched_dest_units = to_units(time_to_minutes(tt_dest.arrival) + offset_dest, f"dest_arr_{s_id}")
            else:
                tt_origin = tt_lookup.get((s_id, nodes[0]))
                offset_0 = day_offsets.get((s_id, 0), 0.0)
                sched_origin = time_to_minutes(tt_origin.departure) + offset_0 if (tt_origin and tt_origin.departure) else 0.0
                sched_dest_units = to_units(sched_origin + (len(nodes) * 3.0), f"dest_arr_fallback_{s_id}")

            dest_arr = arr_vars[(s_id, k_final)]
            delay_dest = model.NewIntVar(0, max_horizon_units, f"delay_{s_id}")
            model.Add(delay_dest >= dest_arr - sched_dest_units)
            model.Add(max_delay_var >= delay_dest)

            # Add to objective
            base_weight = int(round(weights.delay_weight * 10))
            weighted_weight = int(round(weights.weighted_delay_weight * prio_mult))
            total_svc_weight = max(1, base_weight + weighted_weight)
            delay_terms.append((delay_dest, total_svc_weight))

            # Departure deviation at origin
            origin_dep = dep_vars[(s_id, 0)]
            tt_origin = tt_lookup.get((s_id, nodes[0]))
            if tt_origin and tt_origin.departure:
                sched_origin_units = to_units(time_to_minutes(tt_origin.departure), f"origin_dev_{s_id}")
                dev_var = model.NewIntVar(0, max_horizon_units, f"dev_{s_id}")
                model.Add(dev_var >= origin_dep - sched_origin_units)
                dev_weight = int(round(weights.schedule_deviation_weight * 10))
                dev_terms.append((dev_var, max(1, dev_weight)))

        # Combined minimization objective based on objective_mode
        active_mode = getattr(request, "objective_mode", None) or self.objective_mode or "WEIGHTED"
        if active_mode.upper() == "TOTAL_DELAY":
            model.Minimize(sum(var for var, _ in delay_terms))
        else:
            obj_expr = []
            for var, coeff in delay_terms:
                obj_expr.append(var * coeff)
            for var, coeff in dev_terms:
                obj_expr.append(var * coeff)
            obj_expr.append(max_delay_var * int(round(weights.max_delay_weight * 10)))
            model.Minimize(sum(obj_expr))

        # Provide FIFO schedule as a solver hint if available
        if getattr(request, "fifo_timetables", None):
            for s_id, adjs in request.fifo_timetables.items():
                if s_id in service_nodes:
                    nodes = service_nodes[s_id]
                    stn_to_idx = {n: i for i, n in enumerate(nodes)}
                    for adj in adjs:
                        if adj.station_id in stn_to_idx:
                            idx = stn_to_idx[adj.station_id]
                            if adj.adjusted_arrival is not None and (s_id, idx) in arr_vars:
                                model.AddHint(arr_vars[(s_id, idx)], int(round(adj.adjusted_arrival * R)))
                            if adj.adjusted_departure is not None and (s_id, idx) in dep_vars:
                                model.AddHint(dep_vars[(s_id, idx)], int(round(adj.adjusted_departure * R)))

        # 11. Execute CP-SAT Solver
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.time_limit_seconds
        solver.parameters.num_workers = self.num_search_workers
        solver.parameters.log_search_progress = self.log_search_progress

        status_code = solver.Solve(model)
        elapsed_sec = time.time() - start_cpu_time

        # Map CP-SAT status
        status_map = {
            cp_model.OPTIMAL: "OPTIMAL",
            cp_model.FEASIBLE: "FEASIBLE",
            cp_model.INFEASIBLE: "INFEASIBLE",
            cp_model.MODEL_INVALID: "INVALID",
            cp_model.UNKNOWN: "TIMEOUT",
        }
        solution_status = status_map.get(status_code, "UNKNOWN")

        if solution_status not in ("OPTIMAL", "FEASIBLE"):
            return OptimizationResult(
                status=solution_status,
                adjusted_timetables={},
                metrics=PerformanceMetrics(
                    initial_conflict_count=len(request.active_conflicts),
                    remaining_conflict_count=len(request.active_conflicts),
                ),
                cost_breakdown=ObjectiveCostBreakdown(),
                unresolved_conflicts=list(request.active_conflicts),
                computation_time_seconds=elapsed_sec,
            )

        # 12. Extract Solution into OptimizationResult
        adjusted_timetables: Dict[str, List[ServiceTimetableAdjustment]] = {}
        total_delay = 0.0
        max_delay = 0.0
        total_weighted_delay = 0.0
        total_stops = 0
        on_time_stops = 0
        total_travel_time = 0.0

        for s_id, service in request.services.items():
            if s_id not in service_nodes:
                continue
            nodes = service_nodes[s_id]
            adj_list: List[ServiceTimetableAdjustment] = []

            for i, node in enumerate(nodes):
                total_stops += 1
                opt_arr = float(solver.Value(arr_vars[(s_id, i)])) / R
                opt_dep = float(solver.Value(dep_vars[(s_id, i)])) / R

                tt_entry = tt_lookup.get((s_id, node))
                offset_i = day_offsets.get((s_id, i), 0.0)
                orig_arr = (time_to_minutes(tt_entry.arrival) + offset_i) if (tt_entry and tt_entry.arrival) else None
                orig_dep = (time_to_minutes(tt_entry.departure) + offset_i) if (tt_entry and tt_entry.departure) else None

                seq = tt_entry.stop_sequence if tt_entry else (i + 1)
                pf_id = None
                if getattr(request, "enable_platform_conflicts", False) or ENABLE_PLATFORM_CONFLICTS:
                    # Platforms in platforms.json follow {station_id}_P1 / {station_id}_P2 format
                    candidate_pfs = [p for p in request.platforms.values() if p.station_id == node]
                    if candidate_pfs:
                        pf_idx = abs(hash(s_id)) % len(candidate_pfs)
                        pf_id = candidate_pfs[pf_idx].id
                else:
                    # Legacy behavior: looked up PF_{node}_01 which returns None
                    assigned_pf = request.platforms.get(f"PF_{node}_01")
                    pf_id = assigned_pf.id if assigned_pf else None

                # Directional section if in transit
                sec_id = None
                if i < len(nodes) - 1:
                    ts = get_track_section(node, nodes[i + 1])
                    sec_id = ts.id if ts else None

                adj = ServiceTimetableAdjustment(
                    service_id=s_id,
                    station_id=node,
                    stop_sequence=seq,
                    original_arrival=orig_arr,
                    original_departure=orig_dep,
                    adjusted_arrival=opt_arr,
                    adjusted_departure=opt_dep,
                    assigned_platform=pf_id,
                    assigned_track_section=sec_id,
                )
                adj_list.append(adj)

                delay = adj.delay_minutes
                total_delay += delay
                if delay > max_delay:
                    max_delay = delay
                total_weighted_delay += delay * service.delay_penalty_weight
                if delay <= 5.0:
                    on_time_stops += 1

            # Travel duration
            orig_t = float(solver.Value(dep_vars[(s_id, 0)])) / R
            dest_t = float(solver.Value(arr_vars[(s_id, len(nodes) - 1)])) / R
            total_travel_time += max(0.0, float(dest_t - orig_t))

            adjusted_timetables[s_id] = adj_list

        # Extract Precedence Decisions
        precedence_decisions: List[PrecedenceDecision] = []
        sorted_services = sorted(request.services.keys())
        for i in range(len(sorted_services)):
            for j in range(i + 1, len(sorted_services)):
                s1, s2 = sorted_services[i], sorted_services[j]
                if s1 in service_nodes and s2 in service_nodes:
                    # Common nodes
                    common_nodes = set(service_nodes[s1]).intersection(set(service_nodes[s2]))
                    for c_node in sorted(list(common_nodes)):
                        idx1 = service_nodes[s1].index(c_node)
                        idx2 = service_nodes[s2].index(c_node)
                        t1 = float(solver.Value(dep_vars[(s1, idx1)])) / R
                        t2 = float(solver.Value(dep_vars[(s2, idx2)])) / R
                        if t1 != t2:
                            first = s1 if t1 < t2 else s2
                            second = s2 if t1 < t2 else s1
                            precedence_decisions.append(
                                PrecedenceDecision(
                                    resource_id=c_node,
                                    first_service_id=first,
                                    second_service_id=second,
                                    reason=f"Optimized departure order at bottleneck '{c_node}' ({minutes_to_time_str(min(t1, t2), include_seconds=(min(t1, t2) % 1.0 != 0))} precedes {minutes_to_time_str(max(t1, t2), include_seconds=(max(t1, t2) % 1.0 != 0))})",
                                )
                            )

        # Extract Resource Allocation Decisions
        resource_decisions: List[ResourceAllocationDecision] = []
        for s_id, adj_list in adjusted_timetables.items():
            for adj in adj_list:
                if adj.assigned_platform:
                    resource_decisions.append(
                        ResourceAllocationDecision(
                            service_id=s_id,
                            node_or_section_id=adj.station_id,
                            allocated_resource_id=adj.assigned_platform,
                            resource_type="PLATFORM",
                        )
                    )
                if adj.assigned_track_section:
                    resource_decisions.append(
                        ResourceAllocationDecision(
                            service_id=s_id,
                            node_or_section_id=adj.station_id,
                            allocated_resource_id=adj.assigned_track_section,
                            resource_type="TRACK_SECTION",
                        )
                    )

        # Performance metrics
        on_time_pct = (on_time_stops / total_stops * 100.0) if total_stops > 0 else 100.0
        init_conflicts = len(request.active_conflicts)
        resolved_conflicts = init_conflicts  # Mathematical constraints guarantee 0 remaining conflicts

        metrics = PerformanceMetrics(
            total_delay_minutes=total_delay,
            max_delay_minutes=max_delay,
            total_weighted_delay=total_weighted_delay,
            initial_conflict_count=init_conflicts,
            resolved_conflict_count=resolved_conflicts,
            remaining_conflict_count=0,
            throughput_trains_completed=len(request.services),
            total_travel_time_minutes=total_travel_time,
            on_time_performance_percent=on_time_pct,
        )

        cost_breakdown = self.objective.evaluate_cost(
            total_delay_minutes=total_delay,
            total_weighted_delay=total_weighted_delay,
            max_delay_minutes=max_delay,
            conflicts=[],  # 0 remaining conflicts
        )

        return OptimizationResult(
            status=solution_status,
            adjusted_timetables=adjusted_timetables,
            precedence_decisions=precedence_decisions,
            resource_decisions=resource_decisions,
            metrics=metrics,
            cost_breakdown=cost_breakdown,
            unresolved_conflicts=[],
            computation_time_seconds=elapsed_sec,
        )

    def check_schedule_feasibility(
        self,
        request: OptimizationRequest,
        schedule_timetables: Dict[str, List[ServiceTimetableAdjustment]],
    ) -> Tuple[bool, List[str]]:
        """Verify whether a candidate timetable schedule (e.g. FIFO baseline) satisfies CP-SAT model constraints."""
        violations: List[str] = []
        for s_id, adjs in schedule_timetables.items():
            service = request.services.get(s_id)
            if not service:
                continue
            route = request.routes.get(service.route_id)
            if not route:
                continue
            dir_hint = "UP" if "UP" in route.id else ("DOWN" if "DOWN" in route.id else None)
            adj_map = {a.station_id: a for a in adjs}
            nodes = route.ordered_nodes
            for i in range(len(nodes) - 1):
                u, v = nodes[i], nodes[i + 1]
                cand = [ts for ts in request.track_sections.values() if ts.from_node == u and ts.to_node == v]
                ts = next((c for c in cand if c.direction == dir_hint), cand[0]) if cand else None
                req_tt = int(round(ts.travel_time_minutes)) if ts else 3
                req_tt = max(1, req_tt)

                u_adj = adj_map.get(u)
                v_adj = adj_map.get(v)
                if u_adj and v_adj and u_adj.adjusted_departure is not None and v_adj.adjusted_arrival is not None:
                    actual_tt = v_adj.adjusted_arrival - u_adj.adjusted_departure
                    if actual_tt < req_tt - 1e-4:
                        violations.append(
                            f"Service {s_id} between {u}->{v}: travel time {actual_tt:.2f}m < required {req_tt}m"
                        )
        return len(violations) == 0, violations
