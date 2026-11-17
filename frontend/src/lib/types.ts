/**
 * frontend/src/lib/types.ts
 * ~~~~~~~~~~~~~~~~~~~~~~~~~
 * Strict TypeScript models and response schemas matching Phase 20 FastAPI operational APIs.
 */

// 1. Health & System Diagnostics
export interface HealthResponse {
  status: string;
  version: string;
  timestamp_str: string;
  ist_time_str?: string;
  ist_date_str?: string;
  timezone?: string;
  network_status: {
    loaded_stations: number;
    loaded_junctions: number;
    loaded_routes: number;
    loaded_services: number;
    loaded_trains: number;
    datasets_intact: boolean;
  };
}

// 2. Network Topology & Service Catalogue
export interface StationSummary {
  id: string;
  name: string;
  station_type: string;
  platform_count: number;
}

export interface JunctionSummary {
  id: string;
  name: string;
  station_id?: string | null;
  junction_type: string;
  capacity: number;
  connected_routes: string[];
  description?: string | null;
}

export interface RouteSummary {
  id: string;
  name: string;
  origin: string;
  destination: string;
  service_type: string;
  node_count: number;
  ordered_nodes: string[];
}

export interface ServiceSummary {
  id: string;
  train_id: string;
  train_name?: string | null;
  service_type?: string | null;
  train_type?: string | null;
  origin: string;
  destination: string;
  route_id: string;
  priority_class: string;
  delay_penalty_weight: number;
  corridor?: string | null;
  scheduled_departure?: string | null;
  scheduled_arrival?: string | null;
}

export interface TimetableRecord {
  service_id: string;
  station_id: string;
  arrival?: string | null;
  departure?: string | null;
  stop_sequence: number;
}

export interface PlatformSummary {
  id: string;
  station_id: string;
  platform_number: number;
  platform_type: string;
  capacity: number;
}

export interface TrackSectionSummary {
  id: string;
  from_node: string;
  to_node: string;
  direction: string;
  track_type: string;
  number_of_tracks: number;
  travel_time_minutes: number;
  capacity: number;
  minimum_headway_minutes: number;
}

export interface NetworkResponse {
  station_count: number;
  junction_count: number;
  route_count: number;
  service_count: number;
  train_count: number;
  track_section_count: number;
  stations: StationSummary[];
  junctions: JunctionSummary[];
  routes: RouteSummary[];
  services: ServiceSummary[];
  timetable?: TimetableRecord[] | null;
  platforms?: PlatformSummary[] | null;
  track_sections?: TrackSectionSummary[] | null;
}

// 3. Dynamic Simulation Request & Response
export interface SimulateRequest {
  service_ids?: string[] | null;
  departure_delays?: Record<string, number>;
  start_time?: string;
  current_time?: string | null;
  time_limit_minutes?: number | null;
}

export interface TrainPositionState {
  service_id: string;
  train_id: string;
  train_name: string;
  service_type?: string | null;
  train_type?: string | null;
  corridor_name?: string | null;
  origin?: string | null;
  destination?: string | null;
  scheduled_departure?: string | null;
  scheduled_arrival?: string | null;
  priority_class: string;
  status: "SCHEDULED" | "RUNNING" | "DWELLING" | "HELD" | "ARRIVED" | "IN_TRANSIT" | "AT_STATION" | "NOT_STARTED" | "COMPLETED" | string;
  current_node?: string | null;
  current_station?: string | null;
  current_track_section?: string | null;
  delay_minutes: number;
  occupied_resources: string[];
}

export interface TrackSectionOccupancyRecord {
  section_id: string;
  service_id: string;
  train_id: string;
  entry_time: number;
  expected_exit_time?: number | null;
  actual_exit_time?: number | null;
  direction?: string | null;
}

export interface DetectedConflict {
  conflict_id: string;
  conflict_type: "SAME_TRACK_SECTION" | "INSUFFICIENT_HEADWAY" | "SHARED_JUNCTION" | "INCOMPATIBLE_MOVEMENTS";
  affected_service_ids: string[];
  affected_train_ids: string[];
  resource_id: string;
  conflict_time: number;
  severity: "CRITICAL" | "MAJOR" | "WARNING" | "MINOR";
  description: string;
  metadata?: Record<string, any>;
}

export interface SimulateResponse {
  simulation_time_str: string;
  total_services_simulated: number;
  delayed_services_count: number;
  total_network_delay_minutes: number;
  active_occupancies_count: number;
  train_positions: TrainPositionState[];
  active_occupancies: TrackSectionOccupancyRecord[];
  detected_conflicts: DetectedConflict[];
}

// 4. Mathematical CP-SAT Optimization
export interface OptimizeRequest {
  service_ids?: string[] | null;
  departure_delays?: Record<string, number>;
  station_delays?: Record<string, Record<string, number>>;
  time_horizon?: number | null;
}

export interface TimetableAdjustmentSummary {
  service_id: string;
  station_id: string;
  stop_sequence: number;
  original_arrival?: number | null;
  original_departure?: number | null;
  adjusted_arrival?: number | null;
  adjusted_departure?: number | null;
  adjusted_arrival_str?: string | null;
  adjusted_departure_str?: string | null;
  delay_minutes: number;
  dwell_minutes?: number;
  assigned_platform?: string | null;
  assigned_track_section?: string | null;
}

export interface PrecedenceDecision {
  resource_id: string;
  first_service_id: string;
  second_service_id: string;
  reason: string;
}

export interface ResourceAllocationDecision {
  service_id: string;
  node_or_section_id: string;
  allocated_resource_id: string;
  resource_type: string;
}

export interface OptimizeResponse {
  solver_status: "OPTIMAL" | "FEASIBLE" | "BASELINE" | "INFEASIBLE";
  computation_time_seconds: number;
  feasible_baseline_delay_minutes: number;
  optimized_total_delay_minutes: number;
  net_delay_savings_minutes: number;
  net_delay_savings_percent: number;
  unresolved_conflicts_count: number;
  adjusted_timetables: Record<string, TimetableAdjustmentSummary[]>;
  precedence_decisions: PrecedenceDecision[];
  platform_assignments: ResourceAllocationDecision[];
  published_reference_delay_minutes?: number;
  feasible_adjusted_timetables?: Record<string, TimetableAdjustmentSummary[]>;
  published_adjusted_timetables?: Record<string, TimetableAdjustmentSummary[]>;
  three_tier_timetable?: ThreeTierTimetableEntry[];
  corridor_performance?: CorridorPerformanceMetrics[];
}

export interface CorridorPerformanceMetrics {
  corridor_id: string;
  corridor_name: string;
  is_topology_only: boolean;
  service_count: number;
  total_registered_services: number;
  baseline_delay_minutes: number;
  optimized_delay_minutes: number;
  published_delay_minutes?: number;
  delay_savings_minutes: number;
  net_delay_savings_minutes?: number;
  delay_savings_percent: number;
  throughput: number;
  on_time_performance_percent: number;
  initial_conflicts: number;
  remaining_conflicts: number;
  resolved_conflicts: number;
  track_sections_count: number;
  mean_track_utilization_pct: number;
  peak_track_utilization_pct: number;
  utilization_percent: number;
  stress_level: "TOPOLOGY_ONLY" | "UNCONTESTED" | "LOW" | "MODERATE" | "HIGH" | "CRITICAL" | string;
  route_ids: string[];
  active_service_ids?: string[];
}

// 5. What-If Scenario & Decision Support Directives
export interface WhatIfRequest {
  scenario_id?: string;
  scenario_name?: string;
  description?: string;
  service_ids?: string[] | null;
  departure_delays?: Record<string, number>;
  station_delays?: Record<string, Record<string, number>>;
  speed_restrictions?: Record<string, number>;
  blocked_sections?: string[];
  time_horizon?: number | null;
}

export interface PrioritizedConflict {
  conflict: DetectedConflict;
  priority_score: number;
  affected_train_count: number;
  max_delay_minutes: number;
  is_junction_or_platform: boolean;
  priority_tier: "TIER_1_CRITICAL" | "TIER_2_HIGH" | "TIER_3_MEDIUM" | "TIER_4_ADVISORY";
  ranking_explanation: string;
}

export interface ContestedBottleneck {
  resource_id: string;
  resource_type: "JUNCTION" | "PLATFORM" | "TRACK_SECTION" | "STATION" | string;
  contending_services: string[];
  contention_count: number;
  conflict_types?: string[];
  max_delay_observed?: number;
  criticality_score: number;
  description: string;
}

export interface ServiceDelayImpact {
  service_id: string;
  train_id?: string;
  train_name: string;
  priority_class: string;
  primary_delay_minutes?: number;
  direct_delay_minutes?: number;
  propagated_delay_minutes: number;
  total_delay_minutes: number;
  delay_saving_minutes?: number;
  downstream_impact_count?: number;
  affected_downstream_resources?: string[];
  downstream_impact_summary?: string;
}

export interface SupportingEvidence {
  triggering_conflicts: string[];
  contested_resources: string[];
  affected_services: string[];
  bottlenecks: string[];
}

export interface DelayAnalysis {
  direct_delay_reduction_minutes: number;
  propagated_delay_reduction_minutes: number;
  total_savings_minutes: number;
}

export interface CounterfactualAnalysis {
  unmitigated_delay_minutes: number;
  impact_if_not_applied: string;
  downstream_ripple_risk: string;
}

export interface ConfidenceMetrics {
  supporting_constraints_count: number;
  optimization_agreement: number;
  conflict_severity_basis: string;
}

export interface ConstraintExplanation {
  headway: string;
  platform_capacity: string;
  route_occupancy: string;
  junction_contention: string;
}

export interface ReasoningStep {
  step_number: number;
  phase: "TRIGGER" | "BOTTLENECK" | "CONSTRAINTS" | "DECISION" | "OUTCOME" | string;
  title: string;
  detail: string;
}

export interface Recommendation {
  recommendation_id: string;
  recommendation_type: string;
  category: "precedence change" | "holding" | "platform reassignment" | "dispatch sequencing" | "speed management" | "maintain schedule" | string;
  priority_tier: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "URGENT" | "ADVISORY" | string;
  target_service_id?: string;
  title: string;
  reason: string;
  affected_services?: string[];
  affected_resources: string[];
  baseline_delay_minutes: number;
  expected_delay_minutes: number;
  expected_delay_savings: number;
  confidence_score: number;
  evidence_basis: string;
  is_actionable?: boolean;
  operational_context?: "LIVE_OPERATIONAL" | "HYPOTHETICAL_SCENARIO" | string;
  action_details?: Record<string, any>;
  supporting_evidence?: SupportingEvidence;
  delay_analysis?: DelayAnalysis;
  counterfactual_analysis?: CounterfactualAnalysis;
  confidence_metrics?: ConfidenceMetrics;
  constraint_explanation?: ConstraintExplanation;
  ranking_explanation?: string;
  reasoning_path?: ReasoningStep[];
}

export interface ThreeTierTimetableEntry {
  service_id: string;
  train_id?: string;
  train_name?: string;
  corridor_id?: string;
  station_id: string;
  stop_sequence: number;
  section_id?: string | null;

  published_arrival?: number | null;
  published_departure?: number | null;
  published_arrival_str?: string | null;
  published_departure_str?: string | null;
  published_platform?: string | null;
  published_delay_minutes?: number;

  feasible_arrival?: number | null;
  feasible_departure?: number | null;
  feasible_arrival_str?: string | null;
  feasible_departure_str?: string | null;
  feasible_platform?: string | null;
  feasible_delay_minutes?: number;

  optimized_arrival?: number | null;
  optimized_departure?: number | null;
  optimized_arrival_str?: string | null;
  optimized_departure_str?: string | null;
  optimized_platform?: string | null;
  optimized_delay_minutes?: number;
  optimized_dwell_minutes?: number;

  delay_savings_minutes?: number;
  has_rescheduling_change?: boolean;
  is_corridor_relevant?: boolean;
  change_status?: string;

  tier1_published?: Record<string, any>;
  tier2_feasible?: Record<string, any>;
  tier3_optimized?: Record<string, any>;
}

export interface BaselineComparisonDetail {
  published_reference_delay_minutes: number;
  feasible_baseline_delay_minutes: number;
  feasible_baseline_max_delay_minutes: number;
  feasible_baseline_conflicts_remaining: number;
  feasible_baseline_throughput: number;
  optimized_delay_minutes: number;
  optimized_max_delay_minutes: number;
  optimized_conflicts_remaining: number;
  optimized_throughput: number;
  delay_savings_minutes: number;
  delay_savings_percent: number;
  solver_status: string;
  solve_time_seconds: number;
  three_tier_timetable?: ThreeTierTimetableEntry[];
  published_timetables?: Record<string, any[]>;
  feasible_timetables?: Record<string, any[]>;
  optimized_timetables?: Record<string, any[]>;
  corridor_performance?: CorridorPerformanceMetrics[];
}

export interface ControllerSummary {
  solver_status?: string;
  operational_severity: "NORMAL" | "ADVISORY" | "WARNING" | "CRITICAL" | "EMERGENCY";
  net_delay_savings_minutes: number;
  recommendation_count: number;
  top_recommendation: string;
}

export interface WhatIfResponse {
  scenario_id?: string | null;
  scenario_name: string;
  simulation_timestamp_str: string;
  operational_severity: "NORMAL" | "ADVISORY" | "WARNING" | "CRITICAL" | "EMERGENCY";
  active_services_count: number;
  delayed_services_count: number;
  total_baseline_delay_minutes: number;
  total_optimized_delay_minutes: number;
  net_delay_savings_minutes: number;
  net_delay_savings_percent: number;
  solver_status: string;
  solve_time_seconds: number;
  execution_time_seconds: number;
  deterministic_hash: string;
  prioritized_conflicts: PrioritizedConflict[];
  identified_bottlenecks: ContestedBottleneck[];
  service_delay_impacts: ServiceDelayImpact[];
  recommendations: Recommendation[];
  baseline_comparison: BaselineComparisonDetail;
  controller_summary: ControllerSummary;
  metadata: Record<string, any>;
  corridor_performance?: CorridorPerformanceMetrics[];
}

// ---------------------------------------------------------------------------
// Phase 26: Research Analytics & Evaluation Contracts
// ---------------------------------------------------------------------------

export interface AnalyticsCaseIdentity {
  category: string;
  case_id: string;
  name: string;
  service_count: number;
  disruption_mode: string;
}

export interface AnalyticsCaseDelay {
  published_total_delay_min: number;
  feasible_baseline_total_delay_min: number;
  optimized_total_delay_min: number;
  delay_savings_min: number;
  delay_savings_percent: number;
  feasible_baseline_avg_delay_min: number;
  optimized_avg_delay_min: number;
  avg_delay_savings_min: number;
  feasible_baseline_max_delay_min: number;
  optimized_max_delay_min: number;
}

export interface AnalyticsCaseServiceQuality {
  published_on_time_percent: number;
  feasible_baseline_on_time_percent: number;
  optimized_on_time_percent: number;
  baseline_throughput: number;
  optimized_throughput: number;
}

export interface AnalyticsCaseConflict {
  initial_conflicts: number;
  baseline_remaining_conflicts: number;
  optimized_remaining_conflicts: number;
  resolved_conflicts: number;
}

export interface AnalyticsCaseSolver {
  solver_status: string;
  solve_time_seconds: number;
  feasible_baseline_objective_cost: number;
  optimized_objective_cost: number;
  cost_savings: number;
  precedence_decisions: number;
  resource_decisions: number;
}

export interface AnalyticsCaseMetrics {
  identity: AnalyticsCaseIdentity;
  delay: AnalyticsCaseDelay;
  service_quality: AnalyticsCaseServiceQuality;
  conflicts: AnalyticsCaseConflict;
  solver: AnalyticsCaseSolver;
}

export interface AnalyticsCoreAggregates {
  mean_baseline_delay_min: number;
  mean_optimized_delay_min: number;
  mean_delay_savings_min: number;
  mean_delay_savings_percent: number;
  mean_baseline_avg_delay_min: number;
  mean_optimized_avg_delay_min: number;
  mean_solve_time_seconds: number;
}

export interface AnalyticsScalabilityAggregates {
  mean_baseline_delay_min: number;
  mean_optimized_delay_min: number;
  mean_delay_savings_min: number;
  mean_delay_savings_percent: number;
  mean_baseline_avg_delay_min: number;
  mean_optimized_avg_delay_min: number;
  mean_solve_time_seconds: number;
  per_load_mean_solve_times: Record<string, number>;
}

export interface AnalyticsGlobalReliability {
  overall_mean_solve_time_seconds: number;
  overall_max_solve_time_seconds: number;
  total_optimal_solutions: number;
  total_optimality_percent: number;
  total_throughput_maintained_percent: number;
  total_conflict_resolution_percent: number;
  total_initial_conflicts: number;
  total_resolved_conflicts: number;
}

export interface AnalyticsAggregateStats {
  total_cases_evaluated: number;
  core_benchmark_count: number;
  scalability_sweep_count: number;
  core_aggregates: AnalyticsCoreAggregates;
  scalability_aggregates: AnalyticsScalabilityAggregates;
  global_reliability: AnalyticsGlobalReliability;
}

export interface AnalyticsSolveTimeScaling {
  load_label: string;
  service_count: number;
  mean_solve_time_seconds: number;
  min_solve_time_seconds: number;
  max_solve_time_seconds: number;
  normal_solve_time_seconds: number;
  solve_time_per_service_ms: number;
}

export interface AnalyticsSavingsScaling {
  load_label: string;
  service_count: number;
  mean_delay_savings_minutes: number;
  mean_delay_savings_percent: number;
  disrupted_mean_savings_minutes: number;
  disrupted_mean_savings_percent: number;
  max_delay_savings_minutes: number;
  mean_cost_savings: number;
}

export interface AnalyticsStatusSummary {
  total_runs: number;
  optimal_count: number;
  feasible_count: number;
  infeasible_count: number;
  time_limit_count: number;
  unknown_count: number;
  all_optimal: boolean;
  status_by_load: Record<string, Record<string, number>>;
}

export interface AnalyticsThroughputSummary {
  load_label: string;
  service_count: number;
  baseline_throughput: number;
  optimized_throughput: number;
  throughput_maintained_ratio: number;
  is_fully_maintained: boolean;
}

export interface AnalyticsConflictSummary {
  load_label: string;
  service_count: number;
  initial_conflicts_total: number;
  initial_conflicts_mean: number;
  optimized_remaining_conflicts_total: number;
  optimized_remaining_conflicts_mean: number;
  resolved_conflicts_total: number;
  resolution_rate: number;
  has_unresolved_conflicts: boolean;
}

export interface AnalyticsBottleneck {
  has_bottleneck: boolean;
  bottleneck_load_level: string | null;
  bottleneck_service_count: number | null;
  description: string;
  evidence: string[];
  impact_level: string;
}

export interface AnalyticsFinding {
  category: string;
  headline: string;
  detail: string;
}

export interface AnalyticsLimitation {
  category: string;
  title: string;
  description: string;
}

export interface AnalyticsScalabilityAnalysis {
  solve_time_scaling: AnalyticsSolveTimeScaling[];
  savings_scaling: AnalyticsSavingsScaling[];
  status_summary: AnalyticsStatusSummary;
  throughput_summary: AnalyticsThroughputSummary[];
  conflict_summary: AnalyticsConflictSummary[];
  bottleneck: AnalyticsBottleneck;
}

export interface AnalyticsMethodology {
  published_reference: string;
  feasible_baseline: string;
  cpsat_optimum: string;
  delay_savings_formula: string;
  savings_percent_formula: string;
  research_disclaimer: string;
}

export interface AnalyticsResponse {
  metadata: Record<string, any>;
  methodology: AnalyticsMethodology;
  aggregate_statistics: AnalyticsAggregateStats;
  core_benchmark_results: AnalyticsCaseMetrics[];
  scalability_results: AnalyticsCaseMetrics[];
  scalability_analysis: AnalyticsScalabilityAnalysis;
  key_findings: AnalyticsFinding[];
  limitations: AnalyticsLimitation[];
}

// 7. Phase 33.3 Scenario & Result Comparison Models
export type ScenarioType = "OPERATIONAL_STATE" | "HYPOTHETICAL_SCENARIO" | "INFEASIBLE_BOUNDARY_CASE";

export interface WhatIfScenarioMetrics {
  scenario_id: string;
  name: string;
  scenario_type: ScenarioType;
  baseline_delay_minutes: number;
  optimized_delay_minutes: number;
  delay_savings_minutes: number;
  delay_savings_percent: number;
  primary_delay_minutes: number;
  secondary_delay_minutes: number;
  knock_on_multiplier: number;
  recovery_rate_pct: number;
  initial_conflicts: number;
  remaining_conflicts: number;
  resolved_conflicts: number;
  affected_services_count: number;
  affected_service_ids: string[];
  primary_bottleneck_id: string;
  bottleneck_utilization_pct: number;
  solver_status: string;
  solve_time_seconds: number;
  recommendations_count: number;
  top_recommendation_title: string;
  top_recommendation_tier: string;
  confidence_score: number;
}

export interface MultiScenarioComparativeSummary {
  total_scenarios_evaluated: number;
  operational_state_count: number;
  hypothetical_scenario_count: number;
  infeasible_boundary_count: number;
  mean_delay_savings_minutes: number;
  mean_delay_savings_percent: number;
  mean_solve_time_seconds: number;
  total_conflicts_resolved: number;
  mean_knock_on_multiplier: number;
  mean_confidence_score: number;
}

export interface SimulationControlRequest {
  current_minute?: number;
  current_time_str?: string;
  start_minute?: number;
  end_minute?: number;
  is_playing?: boolean;
  playback_speed?: number;
  service_ids?: string[];
  departure_delays?: Record<string, number>;
}

export interface SimulationStateResponse {
  current_minute: number;
  current_time_str: string;
  start_minute: number;
  end_minute: number;
  is_playing: boolean;
  playback_speed: number;
  selected_service_ids: string[];
  departure_delays: Record<string, number>;
  ist_time_str: string;
  ist_date_str: string;
  timezone: string;
  snapshot: SimulateResponse;
}


