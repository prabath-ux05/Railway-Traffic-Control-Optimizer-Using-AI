"""
backend/app/schemas.py
~~~~~~~~~~~~~~~~~~~~~~
Pydantic data schemas and contracts for Phase 20 FastAPI operational endpoints.

Defines controller-facing request and response models:
- Health and dataset diagnostics
- Network topology and service definitions
- Real-time / step-by-step simulation states
- CP-SAT optimization schedules and metrics
- What-If disruption analysis and decision-support recommendations
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# 1. Health & System Status Schemas
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """System health and operational status response."""
    status: str = Field(..., json_schema_extra={"example": "healthy"})
    version: str = Field(..., json_schema_extra={"example": "1.0.0"})
    timestamp_str: str = Field(..., json_schema_extra={"example": "15:30"})
    ist_time_str: Optional[str] = Field(None, json_schema_extra={"example": "15:30:00"})
    ist_date_str: Optional[str] = Field(None, json_schema_extra={"example": "2026-09-26"})
    timezone: Optional[str] = Field("Asia/Kolkata (IST)", json_schema_extra={"example": "Asia/Kolkata (IST)"})
    integrity_warning_count: int = Field(0, description="Total count of data integrity warnings logged during network loading.")
    integrity_summary: Dict[str, int] = Field(default_factory=dict, description="Breakdown of data integrity warnings by category.")
    datasets_integrity_status: str = Field("WARNINGS", description="Overall data integrity health: CLEAN or WARNINGS.")
    network_status: Dict[str, Any] = Field(
        ...,
        json_schema_extra={
            "example": {
                "loaded_stations": 30,
                "loaded_junctions": 7,
                "loaded_routes": 16,
                "loaded_services": 22,
                "loaded_trains": 51,
                "datasets_intact": True,
            }
        },
    )


# ---------------------------------------------------------------------------
# 2. Network Topology & Service Metadata Schemas
# ---------------------------------------------------------------------------

class StationSummary(BaseModel):
    id: str
    name: str
    station_type: str
    platform_count: int


class PlatformSummary(BaseModel):
    id: str
    station_id: str
    platform_number: int
    platform_type: str
    capacity: int


class TrackSectionSummary(BaseModel):
    id: str
    from_node: str
    to_node: str
    direction: str
    track_type: str
    number_of_tracks: int
    travel_time_minutes: float
    capacity: int
    minimum_headway_minutes: float


class JunctionSummary(BaseModel):
    id: str
    name: str
    station_id: Optional[str] = None
    junction_type: str
    capacity: int
    connected_routes: List[str]
    description: Optional[str] = None


class RouteSummary(BaseModel):
    id: str
    name: str
    origin: str
    destination: str
    service_type: str
    node_count: int
    ordered_nodes: List[str]


class ServiceSummary(BaseModel):
    id: str
    service_id: Optional[str] = None
    train_id: str
    train_name: Optional[str] = None
    service_type: Optional[str] = None
    train_type: Optional[str] = None
    origin: str
    destination: str
    route_id: str
    priority_class: str
    delay_penalty_weight: float
    corridor: Optional[str] = None
    corridor_name: Optional[str] = None
    scheduled_departure: Optional[str] = None
    scheduled_arrival: Optional[str] = None
    active: bool = Field(True, description="Whether the service has published timetable evidence.")
    exclusion_reason: Optional[str] = Field(None, description="Reason if service is excluded from operational scheduling.")


class RouteNodeSummary(BaseModel):
    """Authoritative node registry entry across corridor routes."""
    id: str = Field(..., description="Unique node identifier.")
    name: Optional[str] = Field(None, description="Station or junction name from existing datasets; null when unknown.")
    has_station_record: bool = Field(..., description="True if node has a record in stations.json.")
    node_type: str = Field(..., description="Node classification: STATION, JUNCTION, or WAYPOINT.")
    corridors: List[str] = Field(default_factory=list, description="List of railway corridors traversing this node.")
    platform_count: int = Field(0, description="Platform count from platforms.json.")


class NetworkResponse(BaseModel):
    """Complete railway network infrastructure and service catalogue response."""
    station_count: int
    junction_count: int
    route_count: int
    service_count: int
    active_service_count: int = Field(40, description="Count of active services with timetable evidence.")
    excluded_service_count: int = Field(7, description="Count of excluded services without published timetable evidence.")
    train_count: int
    track_section_count: int
    stations: List[StationSummary]
    junctions: List[JunctionSummary]
    routes: List[RouteSummary]
    services: List[ServiceSummary]
    nodes: List[RouteNodeSummary] = Field(default_factory=list, description="Registry of all 107 route nodes across corridor routes.")
    timetable: Optional[List[Dict[str, Any]]] = None
    platforms: Optional[List[PlatformSummary]] = None
    track_sections: Optional[List[TrackSectionSummary]] = None
    data_provenance: Optional[Dict[str, Any]] = Field(None, description="Dataset provenance metadata.")


# ---------------------------------------------------------------------------
# 3. Dynamic Simulation Request & Response Schemas
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    """Parameters to execute discrete-event train movement simulation."""
    service_ids: Optional[List[str]] = Field(
        None,
        description="Optional list of specific service IDs to simulate. Defaults to all active corridor services.",
        json_schema_extra={"example": ["SRV_12607_01", "SRV_12609_01"]},
    )
    departure_delays: Optional[Dict[str, float]] = Field(
        default_factory=dict,
        description="Initial departure delay injected at service origin (in minutes).",
        json_schema_extra={"example": {"SRV_12607_01": 15.0}},
    )
    start_time: Optional[str] = Field(
        "00:00",
        description="Simulation clock start time (HH:MM format).",
        json_schema_extra={"example": "06:00"},
    )
    current_time: Optional[str] = Field(
        None,
        description="Optional simulation clock timestamp to advance train states up to (HH:MM format).",
        json_schema_extra={"example": "06:30"},
    )
    time_limit_minutes: Optional[float] = Field(
        None,
        description="Optional simulation clock limit in minutes from midnight.",
        json_schema_extra={"example": 390.0},
    )


class TrainPositionState(BaseModel):
    service_id: str
    train_id: str
    train_name: str
    service_type: Optional[str] = None
    train_type: Optional[str] = None
    corridor: Optional[str] = None
    corridor_name: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    scheduled_departure: Optional[str] = None
    scheduled_arrival: Optional[str] = None
    priority_class: str
    status: str
    current_node: Optional[str] = None
    current_station: Optional[str] = None
    current_track_section: Optional[str] = None
    delay_minutes: float
    occupied_resources: List[str]


class SimulateResponse(BaseModel):
    """Dynamic simulation state snapshot containing positions, occupancies, and conflicts."""
    simulation_time_str: str
    total_services_simulated: int
    delayed_services_count: int
    total_network_delay_minutes: float
    active_occupancies_count: int
    train_positions: List[TrainPositionState]
    active_occupancies: List[Dict[str, Any]]
    detected_conflicts: List[Dict[str, Any]]


class SimulationControlRequest(BaseModel):
    """Parameters to update authoritative simulation playback or active services."""
    current_minute: Optional[float] = Field(None, description="Simulation minute from midnight.")
    current_time_str: Optional[str] = Field(None, description="Simulation time string (HH:MM).")
    start_minute: Optional[float] = Field(None, description="Simulation window start minute.")
    end_minute: Optional[float] = Field(None, description="Simulation window end minute.")
    is_playing: Optional[bool] = Field(None, description="Playback running status.")
    playback_speed: Optional[int] = Field(None, description="Playback speed multiplier (1, 2, 5, 10, 30, 60).")
    service_ids: Optional[List[str]] = Field(None, description="Active fleet service IDs to simulate.")
    departure_delays: Optional[Dict[str, float]] = Field(None, description="Injected origin departure delays.")
    seek_minute: Optional[float] = Field(None, description="Directly seek to simulation minute, clamped within start_minute and end_minute.")


class SimulationStateResponse(BaseModel):
    """Authoritative real-time simulation state response."""
    current_minute: float
    current_time_str: str
    start_minute: float
    end_minute: float
    is_playing: bool
    playback_speed: int
    selected_service_ids: List[str]
    departure_delays: Dict[str, float]
    ist_time_str: str
    ist_date_str: str
    timezone: str = "Asia/Kolkata (IST)"
    snapshot: SimulateResponse


# ---------------------------------------------------------------------------
# 4. Mathematical CP-SAT Optimization Request & Response Schemas
# ---------------------------------------------------------------------------

class OptimizeRequest(BaseModel):
    """Parameters to trigger mathematical CP-SAT timetable optimization."""
    service_ids: Optional[List[str]] = Field(
        None,
        description="List of service IDs to optimize. Defaults to active corridor services.",
        json_schema_extra={"example": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]},
    )
    departure_delays: Optional[Dict[str, float]] = Field(
        default_factory=dict,
        description="Injected primary departure delays at origin (minutes).",
        json_schema_extra={"example": {"SRV_12607_01": 20.0}},
    )
    station_delays: Optional[Dict[str, Dict[str, float]]] = Field(
        default_factory=dict,
        description="Extra station dwell/delays {service_id: {station_id: minutes}}.",
    )
    speed_restrictions: Optional[Dict[str, float]] = Field(
        default_factory=dict,
        description="Track section speed restrictions {section_id: traversal_minutes}.",
    )
    blocked_sections: Optional[List[str]] = Field(
        default_factory=list,
        description="List of completely blocked track section IDs.",
    )
    time_horizon: Optional[float] = Field(
        None,
        description="Optimization lookahead horizon in minutes from midnight.",
    )
    objective_mode: Optional[str] = Field(
        "WEIGHTED",
        description="Optimization objective mode: WEIGHTED (default, minimizing weighted penalty) or TOTAL_DELAY (minimizing plain sum of delays).",
        json_schema_extra={"example": "WEIGHTED"},
    )
    apply_midnight_wrap: Optional[bool] = Field(
        False,
        description="Opt-in flag (default False). When True, applies +1440 minute day wrap to services crossing midnight.",
    )
    time_resolution: Optional[int] = Field(
        1,
        description="Opt-in time resolution multiplier (1=1 min, 2=0.5 min/30s). Defaults to 1.",
        json_schema_extra={"example": 1},
    )

    @field_validator("time_resolution")
    @classmethod
    def validate_time_resolution(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError(f"time_resolution must be an integer >= 1, got {v}")
        return v

    @field_validator("departure_delays")
    @classmethod
    def validate_departure_delays(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if v:
            for s_id, delay in v.items():
                if delay < 0:
                    raise ValueError(f"Departure delay for service '{s_id}' cannot be negative ({delay} < 0).")
        return v

    @field_validator("station_delays")
    @classmethod
    def validate_station_delays(cls, v: Optional[Dict[str, Dict[str, float]]]) -> Optional[Dict[str, Dict[str, float]]]:
        if v:
            for s_id, stn_map in v.items():
                for stn_id, delay in stn_map.items():
                    if delay < 0:
                        raise ValueError(f"Station dwell delay for service '{s_id}' at station '{stn_id}' cannot be negative ({delay} < 0).")
        return v


class TimetableAdjustmentSummary(BaseModel):
    service_id: str
    station_id: str
    stop_sequence: int
    original_arrival: Optional[float] = None
    original_departure: Optional[float] = None
    adjusted_arrival: Optional[float] = None
    adjusted_departure: Optional[float] = None
    adjusted_arrival_str: Optional[str] = None
    adjusted_departure_str: Optional[str] = None
    delay_minutes: float = 0.0
    assigned_platform: Optional[str] = None


class OptimizeResponse(BaseModel):
    """CP-SAT optimization results with schedule adjustments and delay savings."""
    solver_status: str
    solution_available: bool = True
    computation_time_seconds: float
    feasible_baseline_delay_minutes: float
    optimized_total_delay_minutes: Optional[float] = None
    net_delay_savings_minutes: Optional[float] = None
    net_delay_savings_percent: Optional[float] = None
    fifo_weighted_objective: Optional[float] = None
    optimized_weighted_objective: Optional[float] = None
    objective_mode: str = "WEIGHTED"
    unresolved_conflicts_count: int
    adjusted_timetables: Dict[str, List[TimetableAdjustmentSummary]]
    precedence_decisions: List[Dict[str, Any]]
    platform_assignments: List[Dict[str, Any]]
    published_reference_delay_minutes: float = 0.0
    feasible_adjusted_timetables: Optional[Dict[str, List[TimetableAdjustmentSummary]]] = None
    published_adjusted_timetables: Optional[Dict[str, List[TimetableAdjustmentSummary]]] = None
    three_tier_timetable: Optional[List[Dict[str, Any]]] = None
    corridor_performance: Optional[List[Dict[str, Any]]] = None
    time_resolution: int = Field(1, description="Time resolution multiplier (1 = 1-min units, 2 = 30-sec units)")


# ---------------------------------------------------------------------------
# 5. What-If Scenario & Decision Support Schemas
# ---------------------------------------------------------------------------

class WhatIfRequest(BaseModel):
    """Parameters for evaluating operational What-If disruption scenarios."""
    scenario_id: Optional[str] = Field("SCEN_CUSTOM", json_schema_extra={"example": "SCEN_LATE_12607"})
    scenario_name: Optional[str] = Field("Custom What-If Disruption", json_schema_extra={"example": "Lalbagh Express Late Departure"})
    description: Optional[str] = Field("What-If disruption scenario evaluation.", json_schema_extra={"example": "15 min late departure at MAS."})
    service_ids: Optional[List[str]] = Field(
        None,
        json_schema_extra={"example": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]},
    )
    departure_delays: Optional[Dict[str, float]] = Field(
        default_factory=dict,
        json_schema_extra={"example": {"SRV_12607_01": 15.0}},
    )
    station_delays: Optional[Dict[str, Dict[str, float]]] = Field(default_factory=dict)
    speed_restrictions: Optional[Dict[str, float]] = Field(default_factory=dict)
    blocked_sections: Optional[List[str]] = Field(default_factory=list)
    time_horizon: Optional[float] = None
    objective_mode: Optional[str] = Field(
        "WEIGHTED",
        description="Optimization objective mode: WEIGHTED (default, minimizing weighted penalty) or TOTAL_DELAY (minimizing plain sum of delays).",
        json_schema_extra={"example": "WEIGHTED"},
    )
    apply_midnight_wrap: Optional[bool] = Field(
        False,
        description="Opt-in flag (default False). When True, applies +1440 minute day wrap to services crossing midnight.",
    )
    time_resolution: Optional[int] = Field(
        1,
        description="Opt-in time resolution multiplier (1=1 min, 2=0.5 min/30s). Defaults to 1.",
        json_schema_extra={"example": 1},
    )

    @field_validator("time_resolution")
    @classmethod
    def validate_time_resolution(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 1:
            raise ValueError(f"time_resolution must be an integer >= 1, got {v}")
        return v

    @field_validator("departure_delays")
    @classmethod
    def validate_departure_delays(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if v:
            for s_id, delay in v.items():
                if delay < 0:
                    raise ValueError(f"Departure delay for service '{s_id}' cannot be negative ({delay} < 0).")
        return v

    @field_validator("station_delays")
    @classmethod
    def validate_station_delays(cls, v: Optional[Dict[str, Dict[str, float]]]) -> Optional[Dict[str, Dict[str, float]]]:
        if v:
            for s_id, stn_map in v.items():
                for stn_id, delay in stn_map.items():
                    if delay < 0:
                        raise ValueError(f"Station dwell delay for service '{s_id}' at station '{stn_id}' cannot be negative ({delay} < 0).")
        return v


class SupportingEvidenceSchema(BaseModel):
    triggering_conflicts: List[str] = Field(default_factory=list)
    contested_resources: List[str] = Field(default_factory=list)
    affected_services: List[str] = Field(default_factory=list)
    bottlenecks: List[str] = Field(default_factory=list)


class DelayAnalysisSchema(BaseModel):
    direct_delay_reduction_minutes: float = 0.0
    propagated_delay_reduction_minutes: float = 0.0
    total_savings_minutes: float = 0.0


class CounterfactualAnalysisSchema(BaseModel):
    unmitigated_delay_minutes: float = 0.0
    impact_if_not_applied: str = ""
    downstream_ripple_risk: str = ""


class ConfidenceMetricsSchema(BaseModel):
    supporting_constraints_count: int = 1
    optimization_agreement: float = 1.0
    conflict_severity_basis: str = "MAJOR"


class ConstraintExplanationSchema(BaseModel):
    headway: str = ""
    platform_capacity: str = ""
    route_occupancy: str = ""
    junction_contention: str = ""


class ReasoningStepSchema(BaseModel):
    step_number: int
    phase: str
    title: str
    detail: str


class ExplainableRecommendationSchema(BaseModel):
    """Detailed explainable dispatch directive containing all 8 operational facets."""
    recommendation_id: str
    recommendation_type: str
    category: str
    title: str
    reason: str
    affected_services: List[str]
    affected_resources: List[str]
    baseline_delay_minutes: float
    expected_delay_minutes: float
    expected_delay_savings: float
    confidence_score: float
    priority_tier: str
    evidence_basis: str
    is_actionable: bool
    operational_context: str = "LIVE_OPERATIONAL"
    action_details: Optional[Dict[str, Any]] = None
    supporting_evidence: Optional[SupportingEvidenceSchema] = None
    delay_analysis: Optional[DelayAnalysisSchema] = None
    counterfactual_analysis: Optional[CounterfactualAnalysisSchema] = None
    confidence_metrics: Optional[ConfidenceMetricsSchema] = None
    constraint_explanation: Optional[ConstraintExplanationSchema] = None
    ranking_explanation: str = ""
    reasoning_path: List[ReasoningStepSchema] = Field(default_factory=list)


class WhatIfResponse(BaseModel):
    """Comprehensive end-to-end What-If evaluation and decision-support response."""
    scenario_id: Optional[str]
    scenario_name: str
    simulation_timestamp_str: str = Field(
        ...,
        description="Authoritative simulation clock timestamp (HH:MM) corresponding to the arrival time of the final simulated service in the evaluated cohort. Deterministic model time, not wall-clock based.",
    )
    operational_severity: str
    active_services_count: int
    delayed_services_count: int
    total_baseline_delay_minutes: float
    total_optimized_delay_minutes: Optional[float] = None
    net_delay_savings_minutes: Optional[float] = None
    net_delay_savings_percent: Optional[float] = None
    solver_status: str
    solution_available: bool = True
    fifo_weighted_objective: Optional[float] = None
    optimized_weighted_objective: Optional[float] = None
    objective_mode: str = "WEIGHTED"
    solve_time_seconds: float
    execution_time_seconds: float
    deterministic_hash: str
    prioritized_conflicts: List[Dict[str, Any]]
    identified_bottlenecks: List[Dict[str, Any]]
    service_delay_impacts: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    baseline_comparison: Dict[str, Any]
    controller_summary: Dict[str, Any]
    metadata: Dict[str, Any]
    corridor_performance: Optional[List[Dict[str, Any]]] = None
    time_resolution: int = Field(1, description="Time resolution multiplier (1 = 1-min units, 2 = 30-sec units)")


# ---------------------------------------------------------------------------
# Research Analytics & Evaluation Schemas (Phase 26)
# ---------------------------------------------------------------------------

class AnalyticsCaseIdentitySchema(BaseModel):
    category: str
    case_id: str
    name: str
    service_count: int
    disruption_mode: str


class AnalyticsCaseDelaySchema(BaseModel):
    published_total_delay_min: float
    feasible_baseline_total_delay_min: float
    optimized_total_delay_min: float
    delay_savings_min: float
    delay_savings_percent: float
    feasible_baseline_avg_delay_min: float
    optimized_avg_delay_min: float
    avg_delay_savings_min: float
    feasible_baseline_max_delay_min: float
    optimized_max_delay_min: float


class AnalyticsCaseServiceQualitySchema(BaseModel):
    published_on_time_percent: float
    feasible_baseline_on_time_percent: float
    optimized_on_time_percent: float
    baseline_throughput: int
    optimized_throughput: int


class AnalyticsCaseConflictSchema(BaseModel):
    initial_conflicts: int
    baseline_remaining_conflicts: int
    optimized_remaining_conflicts: int
    resolved_conflicts: int


class AnalyticsCaseSolverSchema(BaseModel):
    solver_status: str
    solve_time_seconds: float
    feasible_baseline_objective_cost: float
    optimized_objective_cost: float
    cost_savings: float
    precedence_decisions: int
    resource_decisions: int


class AnalyticsCaseMetricsSchema(BaseModel):
    identity: AnalyticsCaseIdentitySchema
    delay: AnalyticsCaseDelaySchema
    service_quality: AnalyticsCaseServiceQualitySchema
    conflicts: AnalyticsCaseConflictSchema
    solver: AnalyticsCaseSolverSchema


class AnalyticsCoreAggregatesSchema(BaseModel):
    mean_baseline_delay_min: float
    mean_optimized_delay_min: float
    mean_delay_savings_min: float
    mean_delay_savings_percent: float
    mean_baseline_avg_delay_min: float
    mean_optimized_avg_delay_min: float
    mean_solve_time_seconds: float


class AnalyticsScalabilityAggregatesSchema(BaseModel):
    mean_baseline_delay_min: float
    mean_optimized_delay_min: float
    mean_delay_savings_min: float
    mean_delay_savings_percent: float
    mean_baseline_avg_delay_min: float
    mean_optimized_avg_delay_min: float
    mean_solve_time_seconds: float
    per_load_mean_solve_times: Dict[str, float]


class AnalyticsGlobalReliabilitySchema(BaseModel):
    overall_mean_solve_time_seconds: float
    overall_max_solve_time_seconds: float
    total_optimal_solutions: int
    total_optimality_percent: float
    total_throughput_maintained_percent: float
    total_conflict_resolution_percent: float
    total_initial_conflicts: int
    total_resolved_conflicts: int


class AnalyticsAggregateStatsSchema(BaseModel):
    total_cases_evaluated: int
    core_benchmark_count: int
    scalability_sweep_count: int
    core_aggregates: AnalyticsCoreAggregatesSchema
    scalability_aggregates: AnalyticsScalabilityAggregatesSchema
    global_reliability: AnalyticsGlobalReliabilitySchema


class AnalyticsSolveTimeScalingSchema(BaseModel):
    load_label: str
    service_count: int
    mean_solve_time_seconds: float
    min_solve_time_seconds: float
    max_solve_time_seconds: float
    normal_solve_time_seconds: float
    solve_time_per_service_ms: float


class AnalyticsSavingsScalingSchema(BaseModel):
    load_label: str
    service_count: int
    mean_delay_savings_minutes: float
    mean_delay_savings_percent: float
    disrupted_mean_savings_minutes: float
    disrupted_mean_savings_percent: float
    max_delay_savings_minutes: float
    mean_cost_savings: float


class AnalyticsStatusSummarySchema(BaseModel):
    total_runs: int
    optimal_count: int
    feasible_count: int
    infeasible_count: int
    time_limit_count: int
    unknown_count: int
    all_optimal: bool
    status_by_load: Dict[str, Dict[str, int]]


class AnalyticsThroughputSummarySchema(BaseModel):
    load_label: str
    service_count: int
    baseline_throughput: int
    optimized_throughput: int
    throughput_maintained_ratio: float
    is_fully_maintained: bool


class AnalyticsConflictSummarySchema(BaseModel):
    load_label: str
    service_count: int
    initial_conflicts_total: int
    initial_conflicts_mean: float
    optimized_remaining_conflicts_total: int
    optimized_remaining_conflicts_mean: float
    resolved_conflicts_total: int
    resolution_rate: float
    has_unresolved_conflicts: bool


class AnalyticsBottleneckSchema(BaseModel):
    has_bottleneck: bool
    bottleneck_load_level: Optional[str] = None
    bottleneck_service_count: Optional[int] = None
    description: str
    evidence: List[str] = Field(default_factory=list)
    impact_level: str = "NONE"


class AnalyticsFindingSchema(BaseModel):
    category: str
    headline: str
    detail: str


class AnalyticsLimitationSchema(BaseModel):
    category: str
    title: str
    description: str


class AnalyticsScalabilityAnalysisSchema(BaseModel):
    solve_time_scaling: List[AnalyticsSolveTimeScalingSchema]
    savings_scaling: List[AnalyticsSavingsScalingSchema]
    status_summary: AnalyticsStatusSummarySchema
    throughput_summary: List[AnalyticsThroughputSummarySchema]
    conflict_summary: List[AnalyticsConflictSummarySchema]
    bottleneck: AnalyticsBottleneckSchema


class AnalyticsMethodologySchema(BaseModel):
    published_reference: str
    feasible_baseline: str
    cpsat_optimum: str
    delay_savings_formula: str
    savings_percent_formula: str
    research_disclaimer: str


class AnalyticsResponse(BaseModel):
    """Complete research analytics and evaluation dataset across all benchmarks and scalability runs."""
    metadata: Dict[str, Any]
    methodology: AnalyticsMethodologySchema
    aggregate_statistics: AnalyticsAggregateStatsSchema
    core_benchmark_results: List[AnalyticsCaseMetricsSchema]
    scalability_results: List[AnalyticsCaseMetricsSchema]
    scalability_analysis: AnalyticsScalabilityAnalysisSchema
    key_findings: List[AnalyticsFindingSchema]
    limitations: List[AnalyticsLimitationSchema]


# ---------------------------------------------------------------------------
# 8. Live Runtime Engine Event & Proposal Schemas
# ---------------------------------------------------------------------------

class SimulationEventCreateRequest(BaseModel):
    """Payload to inject an operational disruption at the current or scheduled simulation time."""
    event_type: str = Field(..., description="DEPARTURE_DELAY, DWELL_DELAY, SPEED_RESTRICTION, or BLOCKED_SECTION")
    service_id: Optional[str] = Field(None, description="Target service ID for departure/dwell delay")
    station_id: Optional[str] = Field(None, description="Station ID for dwell delay")
    section_id: Optional[str] = Field(None, description="Track section ID for speed restriction or blockage")
    delay_minutes: Optional[float] = Field(None, ge=0.0, description="Delay magnitude in minutes")
    speed_kmh: Optional[float] = Field(None, ge=0.0, description="Speed restriction in km/h")
    speed_factor: Optional[float] = Field(None, ge=1.0, description="Runtime multiplier (e.g. 2.0 = double runtime)")
    from_minute: Optional[float] = Field(None, description="Disruption effective start minute (default: current sim minute)")
    to_minute: Optional[float] = Field(None, description="Disruption effective end minute (default: horizon)")
    description: Optional[str] = Field(None, description="Contextual description of operational disturbance")


class SimulationEventRecord(BaseModel):
    """Authoritative persistent record of an operational disruption event."""
    id: str = Field(..., description="Unique event identifier (e.g. EVT_0001)")
    event_type: str
    service_id: Optional[str] = None
    station_id: Optional[str] = None
    section_id: Optional[str] = None
    delay_minutes: Optional[float] = None
    speed_kmh: Optional[float] = None
    speed_factor: Optional[float] = None
    from_minute: float
    to_minute: float
    description: Optional[str] = None
    created_at_sim_minute: float
    created_at_wall_clock: str


class ReoptimizationProposal(BaseModel):
    """Human-in-the-loop candidate reoptimization proposal produced by CP-SAT."""
    proposal_id: str = Field(..., description="Unique proposal identifier (e.g. PROP_0001)")
    created_at_sim_minute: float
    created_at_wall_clock: str
    solver_status: str
    solution_available: bool = True
    total_baseline_delay_minutes: float
    total_optimized_delay_minutes: Optional[float] = None
    net_delay_savings_minutes: Optional[float] = None
    net_delay_savings_percent: Optional[float] = None
    operational_severity: str
    recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    adjusted_timetables: Dict[str, Any] = Field(default_factory=dict)
    precedence_decisions: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = Field("PENDING", description="PENDING, ACCEPTED, or REJECTED")


class ProposalActionResponse(BaseModel):
    """Response returned upon accepting or rejecting a reoptimization proposal."""
    proposal_id: str
    action: str  # ACCEPT or REJECT
    status: str  # ACCEPTED or REJECTED
    message: str


class SSETickData(BaseModel):
    """Lightweight real-time tick payload streamed via Server-Sent Events."""
    sim_minute: float
    sim_time_str: str
    ist_time_str: str
    is_playing: bool
    playback_speed: int
    running_count: int
    scheduled_count: int
    arrived_count: int
    delayed_count: int
    active_conflict_count: int
    total_delay_minutes: float


