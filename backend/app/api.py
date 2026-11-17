"""
backend/app/api.py
~~~~~~~~~~~~~~~~~~
Operational FastAPI Router for the Railway Traffic Optimization & Digital Twin Engine.

Exposes controller-facing endpoints:
- GET  /api/v1/health       - Health check and network diagnostic status
- GET  /api/v1/network      - Infrastructure topology, stations, junctions, routes, and services
- POST /api/v1/simulate     - Discrete-event simulation, live positions, occupancies, and conflicts
- POST /api/v1/optimize     - CP-SAT mathematical timetable optimization and delay savings
- POST /api/v1/what-if      - End-to-end What-If disruption evaluation and decision support directives
"""

import os
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status

from simulation.clock import SimulationClock, minutes_to_time_str, time_to_minutes
from simulation.conflicts import ConflictDetector
from simulation.network import Network
from simulation.simulator import TrainSimulator
from simulation.state import SimulationState
from simulation.state_manager import (
    SimulationStateManager,
    get_simulation_manager,
    get_ist_now,
    get_ist_time_str,
    get_ist_date_str,
    get_corridor_name_for_route,
    find_track_section,
)
from optimization.scenarios import Scenario, ScenarioRunner
from backend.app.pipeline import PipelineOrchestrator, _load_default_network
from evaluation.consolidation import run_consolidated_research
from backend.app.schemas import (
    AnalyticsResponse,
    HealthResponse,
    JunctionSummary,
    NetworkResponse,
    OptimizeRequest,
    OptimizeResponse,
    PlatformSummary,
    RouteSummary,
    ServiceSummary,
    SimulationControlRequest,
    SimulationStateResponse,
    SimulateRequest,
    SimulateResponse,
    StationSummary,
    TimetableAdjustmentSummary,
    TrackSectionSummary,
    TrainPositionState,
    WhatIfRequest,
    WhatIfResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Operational Railway Engine"])

# Shared in-memory singletons initialized from immutable datasets
_network_cache: Optional[Network] = None
_orchestrator_cache: Optional[PipelineOrchestrator] = None
_scenario_runner_cache: Optional[ScenarioRunner] = None
_detector_cache: Optional[ConflictDetector] = None


def get_network() -> Network:
    global _network_cache
    if _network_cache is None:
        _network_cache = _load_default_network()
    return _network_cache


def get_orchestrator() -> PipelineOrchestrator:
    global _orchestrator_cache
    if _orchestrator_cache is None:
        net = get_network()
        _orchestrator_cache = PipelineOrchestrator(network=net)
    return _orchestrator_cache


def get_scenario_runner() -> ScenarioRunner:
    global _scenario_runner_cache
    if _scenario_runner_cache is None:
        net = get_network()
        _scenario_runner_cache = ScenarioRunner(network=net)
    return _scenario_runner_cache


def get_detector() -> ConflictDetector:
    global _detector_cache
    if _detector_cache is None:
        net = get_network()
        _detector_cache = ConflictDetector(network=net)
    return _detector_cache


# ---------------------------------------------------------------------------
# 1. Health & Diagnostics Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="System Health & Infrastructure Diagnostics",
    description="Verify backend operational state and confirm that all railway infrastructure and timetable datasets are intact.",
)
def get_health() -> HealthResponse:
    net = get_network()
    stations_count = len(net.stations)
    junctions_count = len(net.junctions)
    routes_count = len(net.routes)
    services_count = len(net.services)
    trains_count = len(net.trains)

    datasets_ok = all(
        c > 0
        for c in [stations_count, junctions_count, routes_count, services_count, trains_count]
    )

    current_t_str = get_ist_time_str(include_seconds=False)
    ist_time_str = get_ist_time_str(include_seconds=True)
    ist_date_str = get_ist_date_str()

    return HealthResponse(
        status="healthy" if datasets_ok else "degraded",
        version="1.0.0",
        timestamp_str=current_t_str,
        ist_time_str=ist_time_str,
        ist_date_str=ist_date_str,
        timezone="Asia/Kolkata (IST)",
        network_status={
            "loaded_stations": stations_count,
            "loaded_junctions": junctions_count,
            "loaded_routes": routes_count,
            "loaded_services": services_count,
            "loaded_trains": trains_count,
            "datasets_intact": datasets_ok,
        },
    )


# ---------------------------------------------------------------------------
# 2. Network Topology & Service Catalogue Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/network",
    response_model=NetworkResponse,
    summary="Railway Network Topology & Service Catalogue",
    description="Retrieve stations, platforms, junctions, routes, track sections, and train service definitions.",
)
def get_network_topology() -> NetworkResponse:
    net = get_network()

    stations = [
        StationSummary(
            id=stn.id,
            name=stn.name,
            station_type=stn.station_type,
            platform_count=stn.platform_count,
        )
        for stn in net.stations.values()
    ]

    junctions = [
        JunctionSummary(
            id=jct.id,
            name=jct.name,
            station_id=getattr(jct, "station_id", None),
            junction_type=getattr(jct, "junction_type", "CROSSING"),
            capacity=getattr(jct, "capacity", 1),
            connected_routes=getattr(jct, "connected_routes", []),
            description=getattr(jct, "description", None),
        )
        for jct in net.junctions.values()
    ]

    routes = [
        RouteSummary(
            id=r.id,
            name=r.name,
            origin=r.origin,
            destination=r.destination,
            service_type=r.service_type,
            node_count=len(r.ordered_nodes),
            ordered_nodes=r.ordered_nodes,
        )
        for r in net.routes.values()
    ]

    timetable_by_svc: Dict[str, Dict[str, Optional[str]]] = {}
    for e in net.timetable:
        if e.service_id not in timetable_by_svc:
            timetable_by_svc[e.service_id] = {}
        if e.departure:
            timetable_by_svc[e.service_id].setdefault("first_dep", e.departure)
        if e.arrival:
            timetable_by_svc[e.service_id]["last_arr"] = e.arrival

    services = []
    for s in net.services.values():
        dep_str = timetable_by_svc.get(s.id, {}).get("first_dep")
        arr_str = timetable_by_svc.get(s.id, {}).get("last_arr")
        route = net.routes.get(s.route_id)
        if not dep_str:
            dep_str = "06:00"
        if not arr_str and route:
            direction_hint = "UP" if "UP" in route.id else ("DOWN" if "DOWN" in route.id else None)
            nom_runtime = 0.0
            nodes = route.ordered_nodes
            for k in range(len(nodes) - 1):
                u_k, v_k = nodes[k], nodes[k + 1]
                ts_k = find_track_section(net, u_k, v_k, direction_hint)
                nom_runtime += (ts_k.travel_time_minutes if ts_k else 3.0)
                if k + 1 < len(nodes) - 1:
                    nom_runtime += 2.0
            arr_str = minutes_to_time_str((time_to_minutes(dep_str) + nom_runtime) % 1440.0)
        elif not arr_str:
            arr_str = minutes_to_time_str((time_to_minutes(dep_str) + 60.0) % 1440.0)

        services.append(
            ServiceSummary(
                id=s.id,
                service_id=s.id,
                train_id=s.train_id,
                train_name=net.trains[s.train_id].name if s.train_id in net.trains else s.train_id,
                service_type=net.trains[s.train_id].train_type if s.train_id in net.trains else "STANDARD",
                train_type=net.trains[s.train_id].train_type if s.train_id in net.trains else "STANDARD",
                origin=s.origin,
                destination=s.destination,
                route_id=s.route_id,
                priority_class=s.priority_class,
                delay_penalty_weight=s.delay_penalty_weight,
                corridor=get_corridor_name_for_route(s.route_id),
                corridor_name=get_corridor_name_for_route(s.route_id),
                scheduled_departure=dep_str,
                scheduled_arrival=arr_str,
            )
        )

    timetable = [
        {
            "service_id": e.service_id,
            "station_id": e.station_id,
            "train_type": net.trains[net.services[e.service_id].train_id].train_type if (e.service_id in net.services and net.services[e.service_id].train_id in net.trains) else "STANDARD",
            "arrival": e.arrival,
            "departure": e.departure,
            "stop_sequence": e.stop_sequence,
        }
        for e in net.timetable
    ]

    platforms = [
        PlatformSummary(
            id=p.id,
            station_id=p.station_id,
            platform_number=p.platform_number,
            platform_type=p.platform_type,
            capacity=p.capacity,
        )
        for p in net.platforms.values()
    ]

    track_sections = [
        TrackSectionSummary(
            id=ts.id,
            from_node=ts.from_node,
            to_node=ts.to_node,
            direction=ts.direction,
            track_type=ts.track_type,
            number_of_tracks=ts.number_of_tracks,
            travel_time_minutes=ts.travel_time_minutes,
            capacity=ts.capacity,
            minimum_headway_minutes=ts.minimum_headway_minutes,
        )
        for ts in net.track_sections.values()
    ]

    return NetworkResponse(
        station_count=len(stations),
        junction_count=len(junctions),
        route_count=len(routes),
        service_count=len(services),
        train_count=len(net.trains),
        track_section_count=len(net.track_sections),
        stations=stations,
        junctions=junctions,
        routes=routes,
        services=services,
        timetable=timetable,
        platforms=platforms,
        track_sections=track_sections,
    )


# ---------------------------------------------------------------------------
# 3. Dynamic Simulation Endpoint
# ---------------------------------------------------------------------------

@router.get(
    "/simulation/state",
    response_model=SimulationStateResponse,
    summary="Get Authoritative Real-Time Simulation State",
    description="Retrieve the current persistent simulation state, active fleet, injected delays, and latest snapshot.",
)
def get_simulation_state() -> SimulationStateResponse:
    net = get_network()
    sim_mgr = get_simulation_manager(net)
    return SimulationStateResponse(**sim_mgr.get_authoritative_state())


@router.post(
    "/simulation/control",
    response_model=SimulationStateResponse,
    summary="Update Simulation Playback and Operational Parameters",
    description="Controls playback (play/pause/speed), timeline scrubbing, selected fleet services, and departure delays.",
)
def control_simulation(req: SimulationControlRequest) -> SimulationStateResponse:
    net = get_network()
    sim_mgr = get_simulation_manager(net)

    if req.service_ids:
        for s_id in req.service_ids:
            if s_id not in net.services:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid service_id '{s_id}' not found in network service catalogue.",
                )

    if req.departure_delays:
        for s_id in req.departure_delays:
            if s_id not in net.services:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid departure_delays key '{s_id}' not found in network service catalogue.",
                )

    updated = sim_mgr.update_control(
        current_minute=req.current_minute,
        current_time_str=req.current_time_str,
        start_minute=req.start_minute,
        end_minute=req.end_minute,
        is_playing=req.is_playing,
        playback_speed=req.playback_speed,
        service_ids=req.service_ids,
        departure_delays=req.departure_delays,
    )
    return SimulationStateResponse(**updated)


@router.post(
    "/simulation/reset",
    response_model=SimulationStateResponse,
    summary="Reset Simulation to Initial State",
    description="Resets simulation clock to start time and optionally clears injected disruptions.",
)
def reset_simulation(clear_delays: bool = False) -> SimulationStateResponse:
    net = get_network()
    sim_mgr = get_simulation_manager(net)
    res = sim_mgr.reset_state(clear_delays=clear_delays)
    return SimulationStateResponse(**res)


@router.post(
    "/simulate",
    response_model=SimulateResponse,
    summary="Execute Discrete-Event Train Movement Simulation",
    description="Simulates chronological train progression and returns live positions, track occupancies, and detected conflicts.",
)
def run_simulation(req: SimulateRequest) -> SimulateResponse:
    net = get_network()
    sim_mgr = get_simulation_manager(net)

    # Validate requested service IDs
    if req.service_ids:
        for s_id in req.service_ids:
            if s_id not in net.services:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid service_id '{s_id}' not found in network service catalogue.",
                )
        selected_svcs = list(req.service_ids)
    else:
        selected_svcs = list(net.services.keys())

    # Validate departure delay service keys
    if req.departure_delays:
        for s_id in req.departure_delays:
            if s_id not in net.services:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid departure_delays key '{s_id}' not found in network service catalogue.",
                )

    target_time_m = None
    if req.time_limit_minutes is not None:
        target_time_m = float(req.time_limit_minutes)
    elif req.current_time:
        target_time_m = time_to_minutes(req.current_time)
    else:
        # Default to current authoritative minute or start time
        target_time_m = sim_mgr.current_minute

    start_time_m = time_to_minutes(req.start_time) if req.start_time else sim_mgr.start_minute

    resp = sim_mgr.simulate_epoch(
        target_time_m=target_time_m,
        service_ids=selected_svcs,
        departure_delays=req.departure_delays,
        start_time_m=start_time_m,
    )

    # Update authoritative persistent state with current simulation progress
    sim_mgr.current_minute = target_time_m
    sim_mgr.selected_service_ids = selected_svcs
    if req.departure_delays:
        sim_mgr.departure_delays.update(req.departure_delays)
    sim_mgr.last_snapshot = resp.model_dump() if hasattr(resp, "model_dump") else resp.dict()
    sim_mgr.last_updated_ist = get_ist_time_str()
    sim_mgr.save_to_disk()

    return resp


# ---------------------------------------------------------------------------
# 4. CP-SAT Mathematical Optimization Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/optimize",
    response_model=OptimizeResponse,
    summary="Compute CP-SAT Optimal Railway Timetable Schedule",
    description="Optimizes train ordering, dwells, and platform assignments to eliminate headway and junction bottlenecks while minimizing total delay.",
)
def run_optimization(req: OptimizeRequest) -> OptimizeResponse:
    net = get_network()
    runner = get_scenario_runner()

    if req.service_ids:
        for s_id in req.service_ids:
            if s_id not in net.services:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid service_id '{s_id}' not found in network service catalogue.",
                )
        selected_svcs = list(req.service_ids)
    else:
        selected_svcs = sorted(list(net.services.keys()))[:4]

    scenario = Scenario(
        scenario_id="SCEN_API_OPTIMIZE",
        name="API Timetable Optimization",
        description="CP-SAT mathematical timetable optimization request.",
        affected_service_ids=selected_svcs,
        departure_delays=req.departure_delays or {},
        station_delays=req.station_delays or {},
        track_speed_restrictions=req.speed_restrictions or {},
    )

    comparison = runner.run_scenario(scenario=scenario, time_horizon=req.time_horizon)
    opt_result = comparison.optimized_result

    adjusted_timetables: Dict[str, List[TimetableAdjustmentSummary]] = {}
    for s_id, adjs in opt_result.adjusted_timetables.items():
        adjusted_timetables[s_id] = [
            TimetableAdjustmentSummary(
                service_id=a.service_id,
                station_id=a.station_id,
                stop_sequence=a.stop_sequence,
                original_arrival=a.original_arrival,
                original_departure=a.original_departure,
                adjusted_arrival=a.adjusted_arrival,
                adjusted_departure=a.adjusted_departure,
                adjusted_arrival_str=a.adjusted_arrival_str,
                adjusted_departure_str=a.adjusted_departure_str,
                delay_minutes=round(a.delay_minutes, 2),
                assigned_platform=a.assigned_platform,
            )
            for a in adjs
        ]

    platform_allocations = [
        d.to_dict() for d in opt_result.resource_decisions if d.resource_type == "PLATFORM"
    ]

    feasible_timetables: Dict[str, List[TimetableAdjustmentSummary]] = {}
    if comparison.baseline_result and comparison.baseline_result.adjusted_timetables:
        for s_id, adjs in comparison.baseline_result.adjusted_timetables.items():
            feasible_timetables[s_id] = [
                TimetableAdjustmentSummary(
                    service_id=a.service_id,
                    station_id=a.station_id,
                    stop_sequence=a.stop_sequence,
                    original_arrival=a.original_arrival,
                    original_departure=a.original_departure,
                    adjusted_arrival=a.adjusted_arrival,
                    adjusted_departure=a.adjusted_departure,
                    adjusted_arrival_str=a.adjusted_arrival_str,
                    adjusted_departure_str=a.adjusted_departure_str,
                    delay_minutes=round(a.delay_minutes, 2),
                    assigned_platform=a.assigned_platform,
                )
                for a in adjs
            ]

    published_timetables: Dict[str, List[TimetableAdjustmentSummary]] = {}
    if comparison.published_baseline_result and comparison.published_baseline_result.adjusted_timetables:
        for s_id, adjs in comparison.published_baseline_result.adjusted_timetables.items():
            published_timetables[s_id] = [
                TimetableAdjustmentSummary(
                    service_id=a.service_id,
                    station_id=a.station_id,
                    stop_sequence=a.stop_sequence,
                    original_arrival=a.original_arrival,
                    original_departure=a.original_departure,
                    adjusted_arrival=a.adjusted_arrival,
                    adjusted_departure=a.adjusted_departure,
                    adjusted_arrival_str=a.adjusted_arrival_str,
                    adjusted_departure_str=a.adjusted_departure_str,
                    delay_minutes=round(a.delay_minutes, 2),
                    assigned_platform=a.assigned_platform,
                )
                for a in adjs
            ]

    three_tier_tt = comparison.build_three_tier_timetable(net)

    return OptimizeResponse(
        solver_status=opt_result.status,
        computation_time_seconds=round(opt_result.computation_time_seconds, 3),
        feasible_baseline_delay_minutes=round(comparison.baseline_total_delay, 2),
        optimized_total_delay_minutes=round(comparison.optimized_total_delay, 2),
        net_delay_savings_minutes=round(comparison.delay_savings_minutes, 2),
        net_delay_savings_percent=round(comparison.delay_savings_percent, 2),
        unresolved_conflicts_count=opt_result.metrics.remaining_conflict_count,
        adjusted_timetables=adjusted_timetables,
        precedence_decisions=[d.to_dict() for d in opt_result.precedence_decisions],
        platform_assignments=platform_allocations,
        published_reference_delay_minutes=round(getattr(comparison, "published_total_delay", 0.0), 2),
        feasible_adjusted_timetables=feasible_timetables,
        published_adjusted_timetables=published_timetables,
        three_tier_timetable=three_tier_tt,
        corridor_performance=comparison.build_corridor_performance_summary(net),
    )


# ---------------------------------------------------------------------------
# 5. What-If Scenario Evaluation & Decision Support Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/what-if",
    response_model=WhatIfResponse,
    summary="Evaluate What-If Scenario with End-to-End Decision Support",
    description="Evaluates custom operational disruptions and returns baseline vs CP-SAT comparison, prioritized conflicts, bottlenecks, and actionable recommendations.",
)
def run_what_if(req: WhatIfRequest) -> WhatIfResponse:
    net = get_network()
    orchestrator = get_orchestrator()

    if req.service_ids:
        for s_id in req.service_ids:
            if s_id not in net.services:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid service_id '{s_id}' not found in network service catalogue.",
                )
        selected_svcs = list(req.service_ids)
    else:
        selected_svcs = sorted(list(net.services.keys()))[:4]

    scenario = Scenario(
        scenario_id=req.scenario_id or "SCEN_CUSTOM",
        name=req.scenario_name or "Custom What-If Disruption",
        description=req.description or "What-If disruption scenario evaluation.",
        affected_service_ids=selected_svcs,
        departure_delays=req.departure_delays or {},
        station_delays=req.station_delays or {},
        track_speed_restrictions=req.speed_restrictions or {},
        blocked_sections=req.blocked_sections or [],
    )

    result = orchestrator.run_pipeline(
        scenario=scenario,
        service_ids=selected_svcs,
        time_horizon=req.time_horizon,
    )

    top_action = (
        result.recommendations[0].title
        if result.recommendations
        else "Maintain published timetable"
    )

    controller_summary = {
        "solver_status": result.solver_status,
        "operational_severity": result.assessment.situation.severity.value,
        "net_delay_savings_minutes": round(result.net_delay_savings_minutes, 2),
        "recommendation_count": len(result.recommendations),
        "top_recommendation": top_action,
    }

    return WhatIfResponse(
        scenario_id=result.scenario_id,
        scenario_name=result.scenario_name,
        simulation_timestamp_str=result.simulation_timestamp_str,
        operational_severity=result.assessment.situation.severity.value,
        active_services_count=result.active_services_count,
        delayed_services_count=result.delayed_services_count,
        total_baseline_delay_minutes=round(result.total_baseline_delay_minutes, 2),
        total_optimized_delay_minutes=round(result.total_optimized_delay_minutes, 2),
        net_delay_savings_minutes=round(result.net_delay_savings_minutes, 2),
        net_delay_savings_percent=round(result.net_delay_savings_percent, 2),
        solver_status=result.solver_status,
        solve_time_seconds=round(result.solve_time_seconds, 3),
        execution_time_seconds=round(result.execution_time_seconds, 3),
        deterministic_hash=result.deterministic_hash,
        prioritized_conflicts=[pc.to_dict() for pc in result.prioritized_conflicts],
        identified_bottlenecks=[ib.to_dict() for ib in result.identified_bottlenecks],
        service_delay_impacts=[sdi.to_dict() for sdi in result.service_delay_impacts],
        recommendations=[r.to_dict() for r in result.recommendations],
        baseline_comparison=result.baseline_comparison.to_dict(),
        controller_summary=controller_summary,
        metadata=result.metadata,
        corridor_performance=result.baseline_comparison.corridor_performance if hasattr(result.baseline_comparison, "corridor_performance") else None,
    )


# ---------------------------------------------------------------------------
# 6. Research Analytics & Evaluation Endpoint (Phase 26)
# ---------------------------------------------------------------------------

_analytics_cache: Optional[Dict[str, Any]] = None


@router.get(
    "/analytics",
    response_model=AnalyticsResponse,
    summary="Research Analytics & Consolidated Evaluation Results",
    description="Retrieve comprehensive empirical benchmark metrics, 3-tier comparisons, scalability curves, and bottleneck analysis from deterministic testbench runs.",
)
def get_analytics(refresh: bool = False) -> AnalyticsResponse:
    global _analytics_cache
    if _analytics_cache is None or refresh:
        net = get_network()
        report = run_consolidated_research(network=net)
        d = report.to_dict()

        methodology = {
            "published_reference": (
                "Published Timetable Reference: Unconstrained timetable baseline that shifts service times "
                "according to injected disruptions without resolving physical headway, station dwell, or block occupancy constraints."
            ),
            "feasible_baseline": (
                "Physically Feasible FIFO Baseline: Discrete-event First-In-First-Out (FIFO) dynamic simulation that "
                "resolves conflicts sequentially at the moment they arise, enforcing safety headways and resource exclusivity without multi-train optimization."
            ),
            "cpsat_optimum": (
                "CP-SAT Global Optimum: Exact integer programming model (Google OR-Tools CP-SAT) performing simultaneous "
                "global optimization over precedence orderings, platform tracks, and station departures to minimize weighted total corridor delay."
            ),
            "delay_savings_formula": "Delay Savings = Total Delay (Feasible Baseline) - Total Delay (CP-SAT Optimized)",
            "savings_percent_formula": "Savings % = [Delay Savings / Total Delay (Feasible Baseline)] * 100%",
            "research_disclaimer": (
                "All results are derived deterministically from the offline simulation testbench and mathematical solver "
                "operating on Chennai Division topological datasets. These metrics represent controlled research benchmarks "
                "and do not constitute certified live field trial validation or unverified reinforcement learning claims."
            ),
        }

        d["methodology"] = methodology
        _analytics_cache = d

    return AnalyticsResponse(**_analytics_cache)

