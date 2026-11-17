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
from pydantic import BaseModel, Field


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


class NetworkResponse(BaseModel):
    """Complete railway network infrastructure and service catalogue response."""
    station_count: int
    junction_count: int
    route_count: int
    service_count: int
    train_count: int
    track_section_count: int
    stations: List[StationSummary]
    junctions: List[JunctionSummary]
    routes: List[RouteSummary]
    services: List[ServiceSummary]
    timetable: Optional[List[Dict[str, Any]]] = None
    platforms: Optional[List[PlatformSummary]] = None
    track_sections: Optional[List[TrackSectionSummary]] = None


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
    playback_speed: Optional[int] = Field(None, description="Playback speed multiplier (1, 2, 5).")
    service_ids: Optional[List[str]] = Field(None, description="Active fleet service IDs to simulate.")
    departure_delays: Optional[Dict[str, float]] = Field(None, description="Injected origin departure delays.")


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
    time_horizon: Optional[float] = Field(
        None,
        description="Optimization lookahead horizon in minutes from midnight.",
    )


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
    computation_time_seconds: float
    feasible_baseline_delay_minutes: float
    optimized_total_delay_minutes: float
    net_delay_savings_minutes: float
    net_delay_savings_percent: float
    unresolved_conflicts_count: int
    adjusted_timetables: Dict[str, List[TimetableAdjustmentSummary]]
    precedence_decisions: List[Dict[str, Any]]
    platform_assignments: List[Dict[str, Any]]
    published_reference_delay_minutes: float = 0.0
    feasible_adjusted_timetables: Optional[Dict[str, List[TimetableAdjustmentSummary]]] = None
    published_adjusted_timetables: Optional[Dict[str, List[TimetableAdjustmentSummary]]] = None
    three_tier_timetable: Optional[List[Dict[str, Any]]] = None
    corridor_performance: Optional[List[Dict[str, Any]]] = None


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
    simulation_timestamp_str: str
    operational_severity: str
    active_services_count: int
    delayed_services_count: int
    total_baseline_delay_minutes: float
    total_optimized_delay_minutes: float
    net_delay_savings_minutes: float
    net_delay_savings_percent: float
    solver_status: str
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

