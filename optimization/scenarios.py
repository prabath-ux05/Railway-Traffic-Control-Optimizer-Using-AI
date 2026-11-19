"""
optimization/scenarios.py
~~~~~~~~~~~~~~~~~~~~~~~~~
What-If Scenario Simulation & Comparative Optimization Engine.

Enables operational dispatchers and planners to evaluate "What-If" scenarios:
- Primary train delays (e.g. late origin departures, en-route delays)
- Multiple simultaneous delays across corridors
- Temporary track section speed restrictions & capacity blocks
- Junction throat contention & capacity constraints

Orchestrates:
Scenario Formulation -> Conflict Detection -> BaselineScheduler -> CPSATScheduler -> ScenarioComparison

Guarantees 100% immutability of underlying JSON datasets and Network models.
"""

import copy
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictDetector, ConflictSeverity, ConflictType
from simulation.network import Network, Route, Service, TimetableEntry, TrackSection
from simulation.state import SimulationState, TrackSectionOccupancy
from optimization.model import (
    HeadwayConstraint,
    JunctionConstraint,
    OptimizationModel,
    OptimizationRequest,
    PlatformConstraint,
    PrecedenceConstraint,
    ServiceTimetableAdjustment,
)
from optimization.objective import ObjectiveWeights, OptimizationObjective
from optimization.scheduler import (
    BaselineScheduler,
    FeasibleBaselineScheduler,
    OptimizationResult,
    PassiveBaselineScheduler,
    PerformanceMetrics,
)
from optimization.solver import CPSATScheduler


AUTHORITATIVE_CORRIDORS: List[Dict[str, Any]] = [
    {
        "corridor_id": "WEST",
        "corridor_name": "West",
        "route_ids": [
            "RT_WEST_MAS_AJJ",
            "RT_WEST_AJJ_MAS",
            "RT_WEST_MAS_TRL_SHORT",
            "RT_WEST_TRL_MAIN_UP",
        ],
        "is_topology_only": False,
    },
    {
        "corridor_id": "NORTH",
        "corridor_name": "North",
        "route_ids": [
            "RT_NORTH_MAS_SPE",
            "RT_NORTH_SPE_MAS",
            "RT_NORTH_MAS_GPD_SHORT",
        ],
        "is_topology_only": False,
    },
    {
        "corridor_id": "SOUTH",
        "corridor_name": "South",
        "route_ids": [
            "RT_SOUTH_MSB_CGL",
            "RT_SOUTH_CGL_MSB",
            "RT_SOUTH_MSB_TBM_SHORT",
            "RT_SOUTH_MAINLINE_REVERSE",
            "RT_SOUTH_MS_CGL_EXPRESS",
            "RT_SOUTH_CGL_MS_EXPRESS",
        ],
        "is_topology_only": False,
    },
    {
        "corridor_id": "MRTS",
        "corridor_name": "MRTS",
        "route_ids": [
            "RT_MRTS_MSB_VLCY",
            "RT_MRTS_VLCY_MSB",
            "RT_MRTS_ELEVATED_REV",
        ],
        "is_topology_only": False,
    },
    {
        "corridor_id": "BEACH_NORTH_BYPASS",
        "corridor_name": "Beach–North Bypass",
        "route_ids": [
            "RT_BEACH_NORTH_BYPASS",
            "RT_BEACH_NORTH_BYPASS_REV",
            "RT_WEST_NORTH_BYPASS_MSB_SPE",
            "RT_WEST_NORTH_BYPASS_SPE_MSB",
        ],
        "is_topology_only": False,
    },
    {
        "corridor_id": "CROSS_BYPASS",
        "corridor_name": "Cross/Bypass",
        "route_ids": [
            "RT_CROSS_CGL_AJJ",
            "RT_CROSS_AJJ_CGL",
        ],
        "is_topology_only": True,
    },
    {
        "corridor_id": "PTMS",
        "corridor_name": "PTMS",
        "route_ids": [
            "RT_PTMS_MAS",
            "RT_MAS_PTMS",
        ],
        "is_topology_only": False,
    },
]


@dataclass
class Scenario:
    """Defines an operational What-If scenario perturbation.

    Attributes:
        scenario_id: Unique scenario identifier (e.g. 'SCEN_LATE_12607').
        name: Short descriptive title.
        description: Detailed narrative of the simulated operational event.
        affected_service_ids: Specific services targeted (empty list applies to all).
        departure_delays: Map of service_id -> minutes of departure delay added at origin.
        station_delays: Map of service_id -> {station_id: extra dwell / arrival delay minutes}.
        track_speed_restrictions: Map of section_id -> new/increased travel_time_minutes.
        blocked_sections: List of section_ids temporarily blocked (capacity set to 0 or unavailable).
        junction_capacity_overrides: Map of junction_id -> modified junction capacity.
        custom_headway_overrides: Map of section_id -> modified minimum_headway_minutes.
        injected_conflicts: Optional explicitly injected Conflict instances.
    """
    scenario_id: str
    name: str
    description: str = ""
    affected_service_ids: List[str] = field(default_factory=list)
    departure_delays: Dict[str, float] = field(default_factory=dict)
    station_delays: Dict[str, Dict[str, float]] = field(default_factory=dict)
    track_speed_restrictions: Dict[str, float] = field(default_factory=dict)
    blocked_sections: List[str] = field(default_factory=list)
    junction_capacity_overrides: Dict[str, int] = field(default_factory=dict)
    custom_headway_overrides: Dict[str, float] = field(default_factory=dict)
    injected_conflicts: List[Conflict] = field(default_factory=list)
    objective_mode: str = "WEIGHTED"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "affected_service_ids": self.affected_service_ids,
            "departure_delays": self.departure_delays,
            "station_delays": self.station_delays,
            "track_speed_restrictions": self.track_speed_restrictions,
            "blocked_sections": self.blocked_sections,
            "junction_capacity_overrides": self.junction_capacity_overrides,
            "custom_headway_overrides": self.custom_headway_overrides,
            "injected_conflicts": [c.to_dict() for c in self.injected_conflicts],
            "objective_mode": self.objective_mode,
        }


@dataclass
class ScenarioComparison:
    """Comprehensive comparative evaluation of Baseline vs. CP-SAT Optimized outcomes.

    Provides a 3-tier research evaluation:
    1. Published Timetable Reference (unconstrained passive shift)
    2. Physically Feasible Baseline (deterministic FIFO rule-based dispatching)
    3. CP-SAT Optimized (global multi-objective MIP optimal)

    Attributes:
        scenario_id: Scenario identifier.
        name: Scenario title.
        description: Scenario narrative.
        baseline_result: Output from FeasibleBaselineScheduler (physically feasible reference).
        optimized_result: Output from CPSATScheduler (CP-SAT optimal solution).
        published_baseline_result: Optional output from BaselineScheduler (passive unconstrained shift).
        feasible_baseline_result: Explicit output from FeasibleBaselineScheduler.
        baseline_total_delay: Total cumulative delay in feasible baseline schedule (min).
        optimized_total_delay: Total cumulative delay in CP-SAT schedule (min).
        published_total_delay: Total cumulative delay in published passive schedule (min).
        delay_savings_minutes: Net minutes saved by optimization (feasible baseline - optimized).
        delay_savings_percent: Percentage reduction in delay over feasible baseline.
        baseline_max_delay: Peak individual service delay in feasible baseline.
        optimized_max_delay: Peak individual service delay in optimized schedule.
        throughput: Number of services completed.
        initial_conflicts: Conflicts present before optimization.
        remaining_conflicts: Conflicts remaining after optimization (0 if solved).
        resolved_conflicts: Number of conflicts eliminated by optimization.
        on_time_performance_percent: Percentage of on-time stops in optimized schedule.
        optimization_status: CP-SAT solver status ("OPTIMAL", "FEASIBLE", etc.).
        optimization_cost: Evaluated multi-objective penalty score.
        computation_time_seconds: Solver execution time.
    """
    scenario_id: str
    name: str
    description: str
    baseline_result: OptimizationResult
    optimized_result: OptimizationResult
    published_baseline_result: Optional[OptimizationResult] = None
    feasible_baseline_result: Optional[OptimizationResult] = None
    baseline_total_delay: float = 0.0
    optimized_total_delay: Optional[float] = None
    published_total_delay: float = 0.0
    delay_savings_minutes: Optional[float] = None
    delay_savings_percent: Optional[float] = None
    baseline_max_delay: float = 0.0
    optimized_max_delay: Optional[float] = None
    throughput: int = 0
    initial_conflicts: int = 0
    remaining_conflicts: int = 0
    resolved_conflicts: int = 0
    on_time_performance_percent: float = 100.0
    optimization_status: str = "OPTIMAL"
    optimization_cost: Optional[float] = None
    computation_time_seconds: float = 0.0
    solution_available: bool = True
    fifo_weighted_objective: Optional[float] = None
    optimized_weighted_objective: Optional[float] = None
    objective_mode: str = "WEIGHTED"
    scenario: Optional[Any] = None
    detected_conflicts: List[Conflict] = field(default_factory=list)
    network: Optional[Any] = None

    def build_three_tier_timetable(self, network: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Construct structured per-service and per-station 3-tier comparative timetable entries."""
        net = network or getattr(self, "network", None)
        entries: List[Dict[str, Any]] = []

        all_service_ids = set()
        if self.optimized_result and self.optimized_result.adjusted_timetables:
            all_service_ids.update(self.optimized_result.adjusted_timetables.keys())
        if self.baseline_result and self.baseline_result.adjusted_timetables:
            all_service_ids.update(self.baseline_result.adjusted_timetables.keys())
        if self.published_baseline_result and self.published_baseline_result.adjusted_timetables:
            all_service_ids.update(self.published_baseline_result.adjusted_timetables.keys())

        # Identify corridors that experienced perturbations or operational changes
        affected_corridors: Set[str] = set()
        for s_id in all_service_ids:
            svc = net.services.get(s_id) if net and hasattr(net, "services") and s_id in net.services else None
            r_id = svc.route_id if svc else ""
            pub_adjs = self.published_baseline_result.adjusted_timetables.get(s_id, []) if self.published_baseline_result else []
            fifo_adjs = self.baseline_result.adjusted_timetables.get(s_id, []) if self.baseline_result else []
            opt_adjs = self.optimized_result.adjusted_timetables.get(s_id, []) if self.optimized_result else []
            has_delay_or_change = (
                any(getattr(a, "delay_minutes", 0.0) > 0.1 for a in pub_adjs + fifo_adjs + opt_adjs)
                or any(
                    abs(getattr(o, "delay_minutes", 0.0) - getattr(f, "delay_minutes", 0.0)) > 0.01
                    or getattr(o, "assigned_platform", None) != getattr(f, "assigned_platform", None)
                    for o, f in zip(opt_adjs, fifo_adjs)
                )
            )
            if has_delay_or_change and r_id:
                affected_corridors.add(r_id)

        # If no specific corridor was perturbed, all corridors in scenario are in scope
        all_active_corridors = {net.services[s].route_id for s in all_service_ids if net and s in net.services and hasattr(net.services[s], "route_id")} if net else set()
        active_affected_corridors = affected_corridors if affected_corridors else all_active_corridors

        for s_id in sorted(list(all_service_ids)):
            svc = net.services.get(s_id) if net and hasattr(net, "services") and s_id in net.services else None
            train = net.trains.get(svc.train_id) if net and svc and hasattr(net, "trains") and svc.train_id in net.trains else None
            train_id = svc.train_id if svc else ""
            train_name = train.name if train else train_id

            route = net.routes.get(svc.route_id) if net and svc and hasattr(net, "routes") and svc.route_id in net.routes else None
            corridor_id = route.id if route else (svc.route_id if svc else "MAINLINE")

            pub_adjs = self.published_baseline_result.adjusted_timetables.get(s_id, []) if self.published_baseline_result else []
            fifo_adjs = self.baseline_result.adjusted_timetables.get(s_id, []) if self.baseline_result else []
            opt_adjs = self.optimized_result.adjusted_timetables.get(s_id, []) if self.optimized_result else []

            pub_map = {a.station_id: a for a in pub_adjs}
            fifo_map = {a.station_id: a for a in fifo_adjs}
            opt_map = {a.station_id: a for a in opt_adjs}

            # Gather all station nodes in route or sequence order
            ordered_stations: List[str] = []
            if route and route.ordered_nodes:
                for n in route.ordered_nodes:
                    if n in opt_map or n in fifo_map or n in pub_map:
                        ordered_stations.append(n)
            if not ordered_stations:
                combined_adjs = opt_adjs or fifo_adjs or pub_adjs
                sorted_adjs = sorted(combined_adjs, key=lambda a: getattr(a, "stop_sequence", 0))
                ordered_stations = [a.station_id for a in sorted_adjs]

            prev_stn: Optional[str] = None
            for idx, stn_id in enumerate(ordered_stations):
                pub_a = pub_map.get(stn_id)
                fifo_a = fifo_map.get(stn_id)
                opt_a = opt_map.get(stn_id)

                seq = (
                    getattr(opt_a, "stop_sequence", None)
                    or getattr(fifo_a, "stop_sequence", None)
                    or getattr(pub_a, "stop_sequence", None)
                    or (idx + 1)
                )

                # Track section identification
                sec_id = getattr(opt_a, "assigned_track_section", None) or getattr(fifo_a, "assigned_track_section", None)
                if not sec_id and prev_stn and net and hasattr(net, "track_sections"):
                    for ts in net.track_sections.values():
                        if (ts.from_node == prev_stn and ts.to_node == stn_id) or (
                            ts.from_node == stn_id and ts.to_node == prev_stn and (ts.direction == "BIDIRECTIONAL" or getattr(ts, "is_bidirectional", False))
                        ):
                            sec_id = ts.id
                            break
                prev_stn = stn_id

                # Tier 1 Published
                pub_orig_arr = pub_a.original_arrival if pub_a and pub_a.original_arrival is not None else (opt_a.original_arrival if opt_a else None)
                pub_orig_dep = pub_a.original_departure if pub_a and pub_a.original_departure is not None else (opt_a.original_departure if opt_a else None)
                pub_delay = pub_a.delay_minutes if pub_a else 0.0
                pub_pf = getattr(pub_a, "assigned_platform", None) or "PF-1"

                # Tier 2 Feasible FIFO
                fifo_arr = fifo_a.adjusted_arrival if fifo_a else None
                fifo_dep = fifo_a.adjusted_departure if fifo_a else None
                fifo_arr_str = fifo_a.adjusted_arrival_str if fifo_a else None
                fifo_dep_str = fifo_a.adjusted_departure_str if fifo_a else None
                fifo_delay = fifo_a.delay_minutes if fifo_a else 0.0
                fifo_pf = getattr(fifo_a, "assigned_platform", None) or "PF-1"

                # Tier 3 CP-SAT Optimal
                opt_arr = opt_a.adjusted_arrival if opt_a else None
                opt_dep = opt_a.adjusted_departure if opt_a else None
                opt_arr_str = opt_a.adjusted_arrival_str if opt_a else None
                opt_dep_str = opt_a.adjusted_departure_str if opt_a else None
                opt_delay = opt_a.delay_minutes if opt_a else 0.0
                opt_dwell = opt_a.dwell_minutes if opt_a else 0.0
                opt_pf = getattr(opt_a, "assigned_platform", None) or "PF-1"

                # Delay savings & Rescheduling change tracking
                delay_savings = max(0.0, fifo_delay - opt_delay)
                has_change = (
                    abs(opt_delay - fifo_delay) > 0.01
                    or (opt_pf != fifo_pf)
                    or (opt_delay > 0.0)
                )

                if opt_pf != fifo_pf:
                    change_status = "PLATFORM_REASSIGNED"
                elif opt_delay > 0.0 and abs(opt_delay - fifo_delay) > 0.01:
                    change_status = "RESCHEDULED"
                elif delay_savings > 0.0:
                    change_status = "DELAY_RECOVERED"
                elif opt_delay <= 0.0:
                    change_status = "ON_TIME"
                else:
                    change_status = "MAINTAINED"

                is_corridor_in_scope = (corridor_id in active_affected_corridors) or (svc and svc.route_id in active_affected_corridors)
                is_relevant = (opt_a is not None) and (is_corridor_in_scope or has_change)

                entry = {
                    "service_id": s_id,
                    "train_id": train_id,
                    "train_name": train_name,
                    "corridor_id": corridor_id,
                    "station_id": stn_id,
                    "stop_sequence": seq,
                    "section_id": sec_id,

                    # Tier 1: Published Reference
                    "published_arrival": pub_orig_arr,
                    "published_departure": pub_orig_dep,
                    "published_arrival_str": minutes_to_time_str(pub_orig_arr) if pub_orig_arr is not None else None,
                    "published_departure_str": minutes_to_time_str(pub_orig_dep) if pub_orig_dep is not None else None,
                    "published_platform": pub_pf,
                    "published_delay_minutes": round(pub_delay, 2),

                    # Tier 2: Feasible Baseline (FIFO)
                    "feasible_arrival": fifo_arr,
                    "feasible_departure": fifo_dep,
                    "feasible_arrival_str": fifo_arr_str,
                    "feasible_departure_str": fifo_dep_str,
                    "feasible_platform": fifo_pf,
                    "feasible_delay_minutes": round(fifo_delay, 2),

                    # Tier 3: CP-SAT Optimal
                    "optimized_arrival": opt_arr,
                    "optimized_departure": opt_dep,
                    "optimized_arrival_str": opt_arr_str,
                    "optimized_departure_str": opt_dep_str,
                    "optimized_platform": opt_pf,
                    "optimized_delay_minutes": round(opt_delay, 2),
                    "optimized_dwell_minutes": round(opt_dwell, 2),

                    # Quantitative Improvement & Status
                    "delay_savings_minutes": round(delay_savings, 2) if is_relevant else 0.0,
                    "has_rescheduling_change": has_change if is_relevant else False,
                    "is_corridor_relevant": is_relevant,
                    "change_status": change_status if is_relevant else "N/A",

                    # Nested Tier Objects
                    "tier1_published": {
                        "arrival": pub_orig_arr,
                        "departure": pub_orig_dep,
                        "arrival_str": minutes_to_time_str(pub_orig_arr) if pub_orig_arr is not None else None,
                        "departure_str": minutes_to_time_str(pub_orig_dep) if pub_orig_dep is not None else None,
                        "platform": pub_pf,
                        "delay_minutes": round(pub_delay, 2),
                    },
                    "tier2_feasible": {
                        "arrival": fifo_arr,
                        "departure": fifo_dep,
                        "arrival_str": fifo_arr_str,
                        "departure_str": fifo_dep_str,
                        "platform": fifo_pf,
                        "delay_minutes": round(fifo_delay, 2),
                    },
                    "tier3_optimized": {
                        "arrival": opt_arr,
                        "departure": opt_dep,
                        "arrival_str": opt_arr_str,
                        "departure_str": opt_dep_str,
                        "platform": opt_pf,
                        "delay_minutes": round(opt_delay, 2),
                        "dwell_minutes": round(opt_dwell, 2),
                    },
                }
                entries.append(entry)

        return entries

    def build_corridor_performance_summary(self, network: Optional[Any] = None) -> List[Dict[str, Any]]:
        """Construct aggregated performance metrics for each of the 7 authoritative corridors.

        Corridors evaluated:
        1. West
        2. North
        3. South
        4. MRTS
        5. Beach–North Bypass
        6. Cross/Bypass (topology-only reference)
        7. PTMS (Pattabiram Siding branch)

        Computes real existing data metrics:
        - service_count (active in scenario)
        - total_registered_services (in catalogue)
        - baseline delay (feasible baseline delay minutes)
        - optimized delay (CP-SAT delay minutes)
        - delay savings / %
        - throughput / OTP
        - conflicts (initial, remaining, resolved)
        - track utilization (% occupancy over operational window)
        - stress level (TOPOLOGY_ONLY, UNCONTESTED, LOW, MODERATE, HIGH, CRITICAL)
        """
        net = network or getattr(self, "network", None)
        if net is None:
            try:
                from backend.app.api import get_network
                net = get_network()
            except Exception:
                net = None

        route_to_corridor: Dict[str, str] = {}
        for c in AUTHORITATIVE_CORRIDORS:
            for r in c["route_ids"]:
                route_to_corridor[r] = c["corridor_id"]

        # Track sections attribution across corridors
        sections_by_corridor: Dict[str, Set[str]] = {c["corridor_id"]: set() for c in AUTHORITATIVE_CORRIDORS}
        if net and hasattr(net, "track_sections"):
            for ts_id, ts in net.track_sections.items():
                if "CROSS_BYPASS" in ts_id:
                    sections_by_corridor["CROSS_BYPASS"].add(ts_id)
                elif "MRTS" in ts_id:
                    sections_by_corridor["MRTS"].add(ts_id)
                elif "BYPASS" in ts_id:
                    sections_by_corridor["BEACH_NORTH_BYPASS"].add(ts_id)
                elif "PTMS" in ts_id or getattr(ts, "from_node", "") == "PTMS" or getattr(ts, "to_node", "") == "PTMS":
                    sections_by_corridor["PTMS"].add(ts_id)
                elif "NORTH" in ts_id:
                    sections_by_corridor["NORTH"].add(ts_id)
                elif "SOUTH" in ts_id:
                    sections_by_corridor["SOUTH"].add(ts_id)
                else:
                    sections_by_corridor["WEST"].add(ts_id)

        # Registered services attribution
        registered_services_by_corridor: Dict[str, List[str]] = {c["corridor_id"]: [] for c in AUTHORITATIVE_CORRIDORS}
        if net and hasattr(net, "services"):
            for s_id, svc in net.services.items():
                cid = route_to_corridor.get(svc.route_id, "WEST")
                if cid in registered_services_by_corridor:
                    registered_services_by_corridor[cid].append(s_id)

        # Active scenario services attribution
        all_scenario_service_ids = set()
        if self.optimized_result and self.optimized_result.adjusted_timetables:
            all_scenario_service_ids.update(self.optimized_result.adjusted_timetables.keys())
        if self.baseline_result and self.baseline_result.adjusted_timetables:
            all_scenario_service_ids.update(self.baseline_result.adjusted_timetables.keys())
        if self.published_baseline_result and self.published_baseline_result.adjusted_timetables:
            all_scenario_service_ids.update(self.published_baseline_result.adjusted_timetables.keys())

        active_services_by_corridor: Dict[str, List[str]] = {c["corridor_id"]: [] for c in AUTHORITATIVE_CORRIDORS}
        for s_id in sorted(list(all_scenario_service_ids)):
            svc = net.services.get(s_id) if net and hasattr(net, "services") and s_id in net.services else None
            r_id = svc.route_id if svc else ""
            cid = route_to_corridor.get(r_id)
            if not cid:
                if "NORTH" in r_id: cid = "NORTH"
                elif "SOUTH" in r_id: cid = "SOUTH"
                elif "MRTS" in r_id: cid = "MRTS"
                elif "BYPASS" in r_id: cid = "BEACH_NORTH_BYPASS"
                elif "CROSS" in r_id: cid = "CROSS_BYPASS"
                elif "PTMS" in r_id: cid = "PTMS"
                else: cid = "WEST"
            if cid in active_services_by_corridor:
                active_services_by_corridor[cid].append(s_id)

        summaries: List[Dict[str, Any]] = []

        for c_def in AUTHORITATIVE_CORRIDORS:
            cid = c_def["corridor_id"]
            c_name = c_def["corridor_name"]
            is_topology_only = c_def["is_topology_only"]
            c_svcs = active_services_by_corridor.get(cid, [])
            c_svc_set = set(c_svcs)
            reg_svcs = registered_services_by_corridor.get(cid, [])
            c_sec_ids = sections_by_corridor.get(cid, set())

            base_delay = 0.0
            opt_delay = 0.0
            pub_delay = 0.0
            on_time_stops = 0
            total_stops = 0
            track_occ_mins: Dict[str, float] = defaultdict(float)

            for s_id in c_svcs:
                base_adjs = self.baseline_result.adjusted_timetables.get(s_id, []) if self.baseline_result else []
                opt_adjs = self.optimized_result.adjusted_timetables.get(s_id, []) if self.optimized_result else []
                pub_adjs = self.published_baseline_result.adjusted_timetables.get(s_id, []) if self.published_baseline_result else []

                for a in base_adjs:
                    base_delay += getattr(a, "delay_minutes", 0.0)
                for a in opt_adjs:
                    d = getattr(a, "delay_minutes", 0.0)
                    opt_delay += d
                    total_stops += 1
                    if d <= 5.0:
                        on_time_stops += 1
                for a in pub_adjs:
                    pub_delay += getattr(a, "delay_minutes", 0.0)

                adjs_for_occ = opt_adjs if opt_adjs else (base_adjs if base_adjs else pub_adjs)
                sorted_adjs = sorted(adjs_for_occ, key=lambda x: getattr(x, "stop_sequence", 0))
                for i in range(len(sorted_adjs) - 1):
                    cur = sorted_adjs[i]
                    nxt = sorted_adjs[i + 1]
                    dep_m = getattr(cur, "adjusted_departure", None) or getattr(cur, "original_departure", None) or 0.0
                    arr_m = getattr(nxt, "adjusted_arrival", None) or getattr(nxt, "original_arrival", None) or (dep_m + 3.0)
                    dur = max(1.0, arr_m - dep_m)
                    u = cur.station_id
                    v = nxt.station_id
                    sec_found = None
                    if net and hasattr(net, "track_sections"):
                        for ts in net.track_sections.values():
                            if (ts.from_node == u and ts.to_node == v) or (
                                ts.from_node == v and ts.to_node == u and (ts.direction == "BIDIRECTIONAL" or getattr(ts, "is_bidirectional", False))
                            ):
                                sec_found = ts.id
                                break
                    if sec_found and sec_found in c_sec_ids:
                        track_occ_mins[sec_found] += dur

            delay_savings = round(base_delay - opt_delay, 2)
            delay_savings_pct = round((delay_savings / base_delay * 100.0), 2) if base_delay > 0 else 0.0
            otp_pct = round((on_time_stops / total_stops * 100.0), 2) if total_stops > 0 else 100.0

            # Conflicts attribution
            c_confs = []
            for conf in self.detected_conflicts:
                aff = getattr(conf, "affected_service_ids", []) or []
                prim = getattr(conf, "primary_service_id", None)
                sec = getattr(conf, "conflicting_service_id", None)
                res = getattr(conf, "resource_id", "")
                is_corr = False
                if (prim and prim in c_svc_set) or (sec and sec in c_svc_set) or any(s in c_svc_set for s in aff):
                    is_corr = True
                elif res in c_sec_ids:
                    is_corr = True
                elif net and hasattr(net, "junctions") and res in net.junctions:
                    jct = net.junctions[res]
                    if any(r in c_def["route_ids"] for r in getattr(jct, "connected_routes", [])):
                        is_corr = True
                if is_corr:
                    c_confs.append(conf)

            init_conflicts = len(c_confs)
            if self.remaining_conflicts == 0:
                rem_conflicts = 0
            else:
                rem_conflicts = min(init_conflicts, self.remaining_conflicts)
            res_conflicts = max(0, init_conflicts - rem_conflicts)

            # Track utilization
            window_mins = 180.0
            util_rates: List[float] = []
            for sec_id in c_sec_ids:
                occ = track_occ_mins.get(sec_id, 0.0)
                sec_obj = net.track_sections.get(sec_id) if net and hasattr(net, "track_sections") and sec_id in net.track_sections else None
                cap = getattr(sec_obj, "capacity", 1) or 1
                u_rate = min(100.0, (occ / (window_mins * cap)) * 100.0)
                util_rates.append(u_rate)

            mean_util = round(sum(util_rates) / len(util_rates), 2) if util_rates else 0.0
            peak_util = round(max(util_rates), 2) if util_rates else 0.0

            # Operational stress level
            if is_topology_only:
                stress_level = "TOPOLOGY_ONLY"
            elif len(c_svcs) == 0:
                stress_level = "UNCONTESTED"
            elif init_conflicts >= 5 or base_delay >= 60.0 or mean_util >= 50.0:
                stress_level = "CRITICAL"
            elif init_conflicts >= 2 or base_delay >= 20.0 or mean_util >= 25.0:
                stress_level = "HIGH"
            elif init_conflicts >= 1 or base_delay >= 5.0 or mean_util >= 10.0:
                stress_level = "MODERATE"
            else:
                stress_level = "LOW"

            entry = {
                "corridor_id": cid,
                "corridor_name": c_name,
                "is_topology_only": is_topology_only,
                "service_count": len(c_svcs),
                "total_registered_services": len(reg_svcs),
                "baseline_delay_minutes": round(base_delay, 2),
                "optimized_delay_minutes": round(opt_delay, 2),
                "published_delay_minutes": round(pub_delay, 2),
                "delay_savings_minutes": delay_savings,
                "net_delay_savings_minutes": delay_savings,
                "delay_savings_percent": delay_savings_pct,
                "throughput": len(c_svcs),
                "on_time_performance_percent": otp_pct,
                "initial_conflicts": init_conflicts,
                "remaining_conflicts": rem_conflicts,
                "resolved_conflicts": res_conflicts,
                "track_sections_count": len(c_sec_ids),
                "mean_track_utilization_pct": mean_util,
                "peak_track_utilization_pct": peak_util,
                "utilization_percent": mean_util,
                "stress_level": stress_level,
                "route_ids": c_def["route_ids"],
                "active_service_ids": c_svcs,
            }
            summaries.append(entry)

        return summaries

    def summary(self) -> str:
        """Produce a human-readable 3-tier comparison summary."""
        pub_delay_str = f"{self.published_total_delay:.1f}" if self.published_baseline_result else "N/A"
        lines = [
            f"====================================================================================================",
            f"SCENARIO WHAT-IF COMPARISON: [{self.scenario_id}] {self.name}",
            f"====================================================================================================",
            f"Description: {self.description}",
            f"",
            f"METRIC                        PUBLISHED REF     FEASIBLE BASELINE (FIFO)   CP-SAT OPTIMIZED   IMPROVEMENT",
            f"----------------------------------------------------------------------------------------------------",
            f"Solver Status                 REFERENCE         {self.baseline_result.status:<26} {self.optimized_result.status:<18} -",
            f"Total Delay (min)             {pub_delay_str:<17} {self.baseline_total_delay:<26.1f} {self.optimized_total_delay:<18.1f} {self.delay_savings_minutes:+.1f} min ({self.delay_savings_percent:.1f}%)",
            f"Max Individual Delay (min)    -                 {self.baseline_max_delay:<26.1f} {self.optimized_max_delay:<18.1f} {self.baseline_max_delay - self.optimized_max_delay:+.1f} min",
            f"Active / Remaining Conflicts  {self.initial_conflicts:<17d} {self.baseline_result.metrics.remaining_conflict_count:<26d} {self.remaining_conflicts:<18d} -{self.resolved_conflicts} resolved",
            f"Throughput (Services)         {self.throughput:<17d} {self.throughput:<26d} {self.throughput:<18d} 100%",
            f"On-Time Performance (%)       {self.published_baseline_result.metrics.on_time_performance_percent if self.published_baseline_result else 100.0:<17.1f} {self.baseline_result.metrics.on_time_performance_percent:<26.1f} {self.on_time_performance_percent:<18.1f} {self.on_time_performance_percent - self.baseline_result.metrics.on_time_performance_percent:+.1f}%",
            f"Precedence Decisions          0                 {len(self.baseline_result.precedence_decisions):<26d} {len(self.optimized_result.precedence_decisions):<18d} -",
            f"Objective Cost                -                 {self.baseline_result.cost_breakdown.total_cost:<26.2f} {self.optimization_cost:<18.2f} {self.baseline_result.cost_breakdown.total_cost - self.optimization_cost:+.2f}",
            f"Solve Duration (s)            -                 {self.baseline_result.computation_time_seconds:<26.3f} {self.computation_time_seconds:<18.3f} -",
            f"====================================================================================================",
        ]
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        pub_tt = {
            s_id: [a.to_dict() for a in adjs]
            for s_id, adjs in self.published_baseline_result.adjusted_timetables.items()
        } if self.published_baseline_result else {}
        base_tt = {
            s_id: [a.to_dict() for a in adjs]
            for s_id, adjs in self.baseline_result.adjusted_timetables.items()
        } if self.baseline_result else {}
        opt_tt = {
            s_id: [a.to_dict() for a in adjs]
            for s_id, adjs in self.optimized_result.adjusted_timetables.items()
        } if self.optimized_result else {}

        return {
            "scenario_id": self.scenario_id,
            "name": self.name,
            "description": self.description,
            "published_total_delay": round(self.published_total_delay, 2),
            "baseline_total_delay": round(self.baseline_total_delay, 2),
            "optimized_total_delay": round(self.optimized_total_delay, 2),
            "delay_savings_minutes": round(self.delay_savings_minutes, 2),
            "delay_savings_percent": round(self.delay_savings_percent, 2),
            "baseline_max_delay": round(self.baseline_max_delay, 2),
            "optimized_max_delay": round(self.optimized_max_delay, 2),
            "throughput": self.throughput,
            "initial_conflicts": self.initial_conflicts,
            "remaining_conflicts": self.remaining_conflicts,
            "resolved_conflicts": self.resolved_conflicts,
            "on_time_performance_percent": round(self.on_time_performance_percent, 2),
            "optimization_status": self.optimization_status,
            "optimization_cost": round(self.optimization_cost, 2),
            "computation_time_seconds": round(self.computation_time_seconds, 3),
            "published_result": self.published_baseline_result.to_dict() if self.published_baseline_result else None,
            "baseline_result": self.baseline_result.to_dict(),
            "optimized_result": self.optimized_result.to_dict(),
            "detected_conflicts": [c.to_dict() for c in self.detected_conflicts],
            "published_timetables": pub_tt,
            "feasible_timetables": base_tt,
            "optimized_timetables": opt_tt,
            "three_tier_timetable": self.build_three_tier_timetable(getattr(self, "network", None)),
            "corridor_performance": self.build_corridor_performance_summary(getattr(self, "network", None)),
        }


class ScenarioRunner:
    """Executes What-If scenarios and performs comparative Baseline vs CP-SAT analysis.

    Never mutates original Network or JSON datasets; operates strictly on in-memory
    cloned request representations.
    """

    def __init__(
        self,
        network: Optional[Network] = None,
        time_limit_seconds: float = 15.0,
        objective_weights: Optional[ObjectiveWeights] = None,
    ):
        if network is None:
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(repo_root, "data", "infrastructure")
            trains_file = os.path.join(repo_root, "data", "trains", "train_identity", "trains.json")
            services_file = os.path.join(repo_root, "data", "trains", "service_definitions", "services.json")
            timetable_file = os.path.join(repo_root, "data", "trains", "published_timetables", "timetable.json")
            self.network = Network()
            self.network.load_from_directory(data_dir)
            self.network.load_trains(trains_file)
            self.network.load_services(services_file)
            self.network.load_timetable(timetable_file)
        else:
            self.network = network
        self.time_limit_seconds = time_limit_seconds
        self.objective_weights = objective_weights or ObjectiveWeights()
        self.detector = ConflictDetector(network=self.network)

    def run(
        self,
        scenario: Scenario,
        time_horizon: Optional[Tuple[float, float]] = None,
    ) -> ScenarioComparison:
        """Alias for run_scenario."""
        return self.run_scenario(scenario=scenario, time_horizon=time_horizon)

    def run_scenario(
        self,
        scenario: Scenario,
        time_horizon: Optional[Tuple[float, float]] = None,
    ) -> ScenarioComparison:
        """Execute a What-If scenario and compute comparative metrics."""
        # 1. Select target services
        target_service_ids = scenario.affected_service_ids or list(self.network.services.keys())
        target_services = {
            s_id: self.network.services[s_id]
            for s_id in target_service_ids
            if s_id in self.network.services
        }

        # 2. Build Base Request (using cloned objects)
        cloned_tt = copy.deepcopy(self.network.timetable)
        cloned_sections = copy.deepcopy(self.network.track_sections)
        cloned_junctions = copy.deepcopy(self.network.junctions)

        # Apply departure delays to timetable
        for s_id, dep_delay in scenario.departure_delays.items():
            if dep_delay <= 0:
                continue
            # Find origin stop
            svc_entries = [e for e in cloned_tt if e.service_id == s_id]
            svc_entries.sort(key=lambda e: e.stop_sequence)
            if svc_entries and svc_entries[0].departure:
                orig_dep_min = time_to_minutes(svc_entries[0].departure)
                new_dep_min = orig_dep_min + dep_delay
                svc_entries[0].departure = minutes_to_time_str(new_dep_min)

        # Apply intermediate station delays
        for s_id, stn_map in scenario.station_delays.items():
            for stn_id, extra_delay in stn_map.items():
                for entry in cloned_tt:
                    if entry.service_id == s_id and entry.station_id == stn_id:
                        if entry.arrival:
                            arr_m = time_to_minutes(entry.arrival) + extra_delay
                            entry.arrival = minutes_to_time_str(arr_m)
                        if entry.departure:
                            dep_m = time_to_minutes(entry.departure) + extra_delay
                            entry.departure = minutes_to_time_str(dep_m)

        # Apply speed restrictions
        for sec_id, new_tt in scenario.track_speed_restrictions.items():
            if sec_id in cloned_sections:
                cloned_sections[sec_id].travel_time_minutes = float(new_tt)

        # Apply blocked sections
        for sec_id in scenario.blocked_sections:
            if sec_id in cloned_sections:
                cloned_sections[sec_id].capacity = 0

        # Build Constraints
        headways: List[HeadwayConstraint] = []
        for sec_id, sec in cloned_sections.items():
            h_min = scenario.custom_headway_overrides.get(sec_id, sec.minimum_headway_minutes)
            if h_min > 0:
                headways.append(
                    HeadwayConstraint(
                        section_id=sec.id,
                        preceding_service_id="*",
                        following_service_id="*",
                        minimum_headway_minutes=h_min,
                        direction=sec.direction,
                    )
                )

        junctions_const: List[JunctionConstraint] = []
        for jct_id, jct in cloned_junctions.items():
            cap = scenario.junction_capacity_overrides.get(jct_id, getattr(jct, "capacity", 1))
            junctions_const.append(
                JunctionConstraint(
                    junction_id=jct.id,
                    node_id=getattr(jct, "station_id", None) or jct.id,
                    competing_service_ids=list(target_services.keys()),
                    capacity=cap,
                )
            )

        horizon = time_horizon or (0.0, 1440.0)

        # Initial delay map
        current_delays: Dict[str, float] = {}
        for s_id in target_services:
            d_delay = scenario.departure_delays.get(s_id, 0.0)
            if d_delay > 0:
                current_delays[s_id] = d_delay

        # Build OptimizationRequest
        request = OptimizationRequest(
            services=target_services,
            trains={s.train_id: self.network.trains[s.train_id] for s in target_services.values() if s.train_id in self.network.trains},
            timetable=[e for e in cloned_tt if e.service_id in target_services],
            routes={s.route_id: self.network.routes[s.route_id] for s in target_services.values() if s.route_id in self.network.routes},
            track_sections=cloned_sections,
            junctions=cloned_junctions,
            platforms=self.network.platforms,
            active_conflicts=list(scenario.injected_conflicts),
            current_delays=current_delays,
            headway_constraints=headways,
            junction_constraints=junctions_const,
            time_horizon=horizon,
            weights=self.objective_weights,
            objective_mode=getattr(scenario, "objective_mode", "WEIGHTED"),
        )

        # 3. Detect Conflicts on Scenario State (throat sections & corridor headway)
        throat_sections = ["MAS_BBQ_THROAT_SEGMENT_DOWN", "BBQ_MAS_THROAT_SEGMENT_UP"]
        for sec_id in throat_sections:
            sec_occs = []
            for s_id in target_services:
                entries = [e for e in request.timetable if e.service_id == s_id]
                if entries and entries[0].departure:
                    dep_m = time_to_minutes(entries[0].departure)
                    sec_occs.append(
                        TrackSectionOccupancy(
                            section_id=sec_id,
                            service_id=s_id,
                            train_id=target_services[s_id].train_id,
                            entry_time=dep_m,
                            expected_exit_time=dep_m + 4.0,
                            direction="DOWN" if "DOWN" in sec_id else "UP",
                        )
                    )
            detected_hw = self.detector.detect_headway_conflicts(sec_occs)
            for c in detected_hw:
                if c not in request.active_conflicts:
                    request.active_conflicts.append(c)

        # Detect headway and occupancy conflicts across shared corridor sections
        section_occs_by_sec: Dict[str, List[TrackSectionOccupancy]] = defaultdict(list)
        for s_id, svc in target_services.items():
            route = self.network.routes.get(svc.route_id)
            if not route:
                continue
            tt_map = {e.station_id: time_to_minutes(e.departure) for e in request.timetable if e.service_id == s_id and e.departure}
            if not tt_map:
                continue

            curr_t = min(tt_map.values())
            for i in range(len(route.ordered_nodes) - 1):
                u = route.ordered_nodes[i]
                v = route.ordered_nodes[i + 1]
                if u in tt_map:
                    curr_t = tt_map[u]
                ts = None
                for cand in self.network.track_sections.values():
                    if (cand.from_node == u and cand.to_node == v) or (
                        cand.from_node == v and cand.to_node == u and (cand.direction == "BIDIRECTIONAL" or getattr(cand, "is_bidirectional", False))
                    ):
                        ts = cand
                        break
                travel_t = ts.travel_time_minutes if ts else 3.0
                sec_id = ts.id if ts else f"FALLBACK_{u}_{v}"
                sec_dir = ts.direction if ts else ("UP" if "UP" in route.id else "DOWN")

                section_occs_by_sec[sec_id].append(
                    TrackSectionOccupancy(
                        section_id=sec_id,
                        service_id=s_id,
                        train_id=svc.train_id,
                        entry_time=curr_t,
                        expected_exit_time=curr_t + travel_t,
                        direction=sec_dir,
                    )
                )
                curr_t += travel_t

        for sec_id, occ_list in section_occs_by_sec.items():
            if len(occ_list) > 1:
                hw_confs = self.detector.detect_headway_conflicts(occ_list)
                for c in hw_confs:
                    if c not in request.active_conflicts:
                        request.active_conflicts.append(c)

        # 4. Execute Baseline Schedulers
        # A. Unconstrained Published Timetable Shift (Reference)
        passive_scheduler = BaselineScheduler(objective=OptimizationObjective(weights=self.objective_weights))
        passive_result = passive_scheduler.schedule(request)

        # B. Physically Feasible FIFO Baseline (Fair Reference)
        feasible_scheduler = FeasibleBaselineScheduler(objective=OptimizationObjective(weights=self.objective_weights))
        feasible_result = feasible_scheduler.schedule(request)

        # 5. Execute CP-SAT Solver with FIFO hints
        # request.fifo_timetables = feasible_result.adjusted_timetables
        cpsat_solver = CPSATScheduler(
            time_limit_seconds=self.time_limit_seconds,
            objective=OptimizationObjective(weights=self.objective_weights),
            objective_mode=getattr(scenario, "objective_mode", "WEIGHTED"),
        )
        opt_result = cpsat_solver.schedule(request)

        # 6. Compute Comparative Metrics
        is_feasible = opt_result.status in ("OPTIMAL", "FEASIBLE")
        pub_delay = passive_result.metrics.total_delay_minutes
        base_delay = feasible_result.metrics.total_delay_minutes

        if is_feasible:
            opt_delay = opt_result.metrics.total_delay_minutes
            savings = base_delay - opt_delay
            savings_pct = (savings / base_delay * 100.0) if base_delay > 0 else 0.0
            opt_max_delay = opt_result.metrics.max_delay_minutes
            opt_cost = opt_result.cost_breakdown.total_cost
            opt_weighted_obj = opt_result.cost_breakdown.total_cost
        else:
            opt_delay = None
            savings = None
            savings_pct = None
            opt_max_delay = None
            opt_cost = None
            opt_weighted_obj = None

        fifo_weighted_obj = feasible_result.cost_breakdown.total_cost
        init_conflicts = len(request.active_conflicts)
        rem_conflicts = opt_result.metrics.remaining_conflict_count
        res_conflicts = max(0, init_conflicts - rem_conflicts)

        return ScenarioComparison(
            scenario_id=scenario.scenario_id,
            name=scenario.name,
            description=scenario.description,
            baseline_result=feasible_result,
            published_baseline_result=passive_result,
            feasible_baseline_result=feasible_result,
            optimized_result=opt_result,
            published_total_delay=pub_delay,
            baseline_total_delay=base_delay,
            optimized_total_delay=opt_delay,
            delay_savings_minutes=savings,
            delay_savings_percent=savings_pct,
            baseline_max_delay=feasible_result.metrics.max_delay_minutes,
            optimized_max_delay=opt_max_delay,
            throughput=opt_result.throughput,
            initial_conflicts=init_conflicts,
            remaining_conflicts=rem_conflicts,
            resolved_conflicts=res_conflicts,
            on_time_performance_percent=opt_result.metrics.on_time_performance_percent,
            optimization_status=opt_result.status,
            optimization_cost=opt_cost,
            computation_time_seconds=opt_result.computation_time_seconds,
            solution_available=is_feasible,
            fifo_weighted_objective=fifo_weighted_obj,
            optimized_weighted_objective=opt_weighted_obj,
            objective_mode=getattr(scenario, "objective_mode", "WEIGHTED"),
            scenario=scenario,
            detected_conflicts=list(request.active_conflicts),
            network=self.network,
        )
