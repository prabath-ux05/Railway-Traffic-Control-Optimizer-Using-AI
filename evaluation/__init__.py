"""
evaluation/__init__.py
~~~~~~~~~~~~~~~~~~~~~~
Batch 11–13: Research Evaluation, Experiment Framework & Scalability Testing.

Exports:
- EvaluationRunner: Core testbench orchestrator.
- ExperimentConfig: Configuration dataclass for controlled experiments.
- ExperimentMetrics: Quantitative metrics separating Baseline and CP-SAT outcomes.
- ExperimentResult: Complete evaluated result of a single experiment.
- EvaluationSuiteResult: Aggregated testbench result with Markdown reporting.
- MetricComparison: Pairwise metric delta and percentage change tracker.
- create_standard_evaluation_suite: Factory for 5 standard benchmark experiments.
- create_no_delay_baseline_experiment
- create_single_train_delay_experiment
- create_multiple_simultaneous_delays_experiment
- create_speed_restriction_experiment
- create_junction_bottleneck_experiment

Batch 13 Scalability:
- ScalabilityLoadLevel: Load-level cohort definition.
- ScalabilityMetrics: Per-run captured metrics.
- ScalabilityResult: Aggregated per-load-level outcome.
- ScalabilityReport: Full sweep report across all load levels.
- ScalabilityRunner: Orchestrator for the scalability sweep.
- create_west_corridor_load_levels: Factory for 5 standard West Corridor load levels.
- run_scalability_suite: Convenience top-level function.
"""

from evaluation.experiments import (
    create_consolidated_benchmark_suite,
    create_junction_bottleneck_experiment,
    create_multiple_simultaneous_delays_experiment,
    create_no_delay_baseline_experiment,
    create_severe_compound_experiment,
    create_single_train_delay_experiment,
    create_speed_restriction_experiment,
    create_standard_evaluation_suite,
)
from evaluation.models import (
    EvaluationSuiteResult,
    ExperimentConfig,
    ExperimentMetrics,
    ExperimentResult,
    MetricComparison,
)
from evaluation.runner import EvaluationRunner
from evaluation.scalability import (
    ScalabilityLoadLevel,
    ScalabilityMetrics,
    ScalabilityReport,
    ScalabilityResult,
    ScalabilityRunner,
    create_west_corridor_load_levels,
    run_scalability_suite,
)
from evaluation.analysis import (
    BottleneckFinding,
    ConflictSummary,
    ExperimentLimitation,
    SavingsScaling,
    ScalabilityAnalysis,
    ScalabilityAnalyzer,
    ScalabilityFinding,
    SolveTimeScaling,
    StatusSummary,
    ThroughputSummary,
    run_scalability_analysis,
)
from evaluation.consolidation import (
    ConsolidatedAggregateStats,
    ConsolidatedCaseMetrics,
    ConsolidatedResearchReport,
    ConsolidatedResearchRunner,
    run_consolidated_research,
)
from evaluation.framework import (
    ExperimentGroupType,
    ResearchExperimentConfig,
    ResearchExperimentResult,
    ResearchExperimentRunner,
    ResearchMetrics,
    ResearchSuiteResult,
    create_phase31_research_suite,
)
from evaluation.scalability_framework import (
    COHORT_4,
    COHORT_8,
    COHORT_12,
    COHORT_16,
    COHORT_20,
    COHORT_30,
    COHORT_40,
    SCALABILITY_COHORTS,
    SCALABILITY_LOAD_LEVELS,
    ScalabilitySuiteResult,
    create_scalability_experiment_config,
    create_scalability_scenario,
    create_scalability_suite,
    run_scalability_experiments,
)
from evaluation.severity_framework import (
    DisruptionClass,
    SEVERITY_EXPERIMENT_SPECS,
    SeverityExperimentSpec,
    SeverityLevel,
    SeverityProgressionResult,
    SeveritySuiteResult,
    create_severity_suite,
    run_severity_experiments,
)
from evaluation.comparative_analysis import (
    ComparativeAnalysisResult,
    ComparativeAnalyzer,
    ComparativeRecord,
    DelayStats,
    ScalabilityTrend,
    SeverityTrend,
    SolverStats,
    ThroughputStats,
    run_comparative_analysis,
)
from evaluation.metrics_consolidation import (
    BottleneckKPISummary,
    ConsolidatedResearchMetrics,
    GroupKPISummary,
    InfeasibleBoundarySummary,
    MetricsConsolidator,
    ResearchKPISummary,
    ScalabilityKPISummary,
    SeverityKPISummary,
    run_metrics_consolidation,
)
from evaluation.bottleneck_analytics import (
    BottleneckAnalyticsResult,
    BottleneckAnalyzer,
    BottleneckCategory,
    CorridorUtilization,
    InfeasibleBottleneckDetail,
    JunctionUtilization,
    PlatformUtilization,
    RankedBottleneck,
    TrackUtilization,
    run_bottleneck_analytics,
)
from evaluation.delay_propagation_analytics import (
    CorridorPropagationProfile,
    DelayDecomposition,
    DelayPropagationAnalyticsResult,
    DelayPropagationAnalyzer,
    PropagationChain,
    PropagationChainNode,
    PropagationTriggerType,
    run_delay_propagation_analytics,
)

__all__ = [
    # Batch 11: Evaluation Runner & Experiments
    "EvaluationRunner",
    "ExperimentConfig",
    "ExperimentMetrics",
    "ExperimentResult",
    "EvaluationSuiteResult",
    "MetricComparison",
    "create_standard_evaluation_suite",
    "create_consolidated_benchmark_suite",
    "create_no_delay_baseline_experiment",
    "create_single_train_delay_experiment",
    "create_multiple_simultaneous_delays_experiment",
    "create_speed_restriction_experiment",
    "create_junction_bottleneck_experiment",
    "create_severe_compound_experiment",
    # Batch 13: Scalability
    "ScalabilityLoadLevel",
    "ScalabilityMetrics",
    "ScalabilityResult",
    "ScalabilityReport",
    "ScalabilityRunner",
    "create_west_corridor_load_levels",
    "run_scalability_suite",
    # Batch 14: Analysis & Validation
    "ScalabilityAnalysis",
    "ScalabilityAnalyzer",
    "ScalabilityFinding",
    "SolveTimeScaling",
    "SavingsScaling",
    "StatusSummary",
    "ThroughputSummary",
    "ConflictSummary",
    "BottleneckFinding",
    "ExperimentLimitation",
    "run_scalability_analysis",
    # Batch 15: Research Experiment Consolidation
    "ConsolidatedCaseMetrics",
    "ConsolidatedAggregateStats",
    "ConsolidatedResearchReport",
    "ConsolidatedResearchRunner",
    "run_consolidated_research",
    # Phase 31.1: Multi-Corridor Research Framework
    "ExperimentGroupType",
    "ResearchExperimentConfig",
    "ResearchExperimentResult",
    "ResearchExperimentRunner",
    "ResearchMetrics",
    "ResearchSuiteResult",
    "create_phase31_research_suite",
    # Phase 31.2: Multi-Load Scalability Framework
    "COHORT_4",
    "COHORT_8",
    "COHORT_12",
    "COHORT_16",
    "COHORT_20",
    "COHORT_30",
    "COHORT_40",
    "SCALABILITY_COHORTS",
    "SCALABILITY_LOAD_LEVELS",
    "ScalabilitySuiteResult",
    "create_scalability_experiment_config",
    "create_scalability_scenario",
    "create_scalability_suite",
    "run_scalability_experiments",
    # Phase 31.3: Disruption Severity Framework
    "DisruptionClass",
    "SeverityLevel",
    "SeverityExperimentSpec",
    "SEVERITY_EXPERIMENT_SPECS",
    "SeverityProgressionResult",
    "SeveritySuiteResult",
    "create_severity_suite",
    "run_severity_experiments",
    # Phase 31.4: Comparative Analysis & Statistics
    "ComparativeRecord",
    "DelayStats",
    "ThroughputStats",
    "SolverStats",
    "ScalabilityTrend",
    "SeverityTrend",
    "ComparativeAnalysisResult",
    "ComparativeAnalyzer",
    "run_comparative_analysis",
    # Phase 31.5: Research Metrics Consolidation
    "ResearchKPISummary",
    "GroupKPISummary",
    "ScalabilityKPISummary",
    "SeverityKPISummary",
    "InfeasibleBoundarySummary",
    "BottleneckKPISummary",
    "ConsolidatedResearchMetrics",
    "MetricsConsolidator",
    "run_metrics_consolidation",
    # Phase 32.1: Bottleneck & Resource Analytics
    "TrackUtilization",
    "PlatformUtilization",
    "JunctionUtilization",
    "CorridorUtilization",
    "BottleneckCategory",
    "RankedBottleneck",
    "InfeasibleBottleneckDetail",
    "BottleneckAnalyticsResult",
    "BottleneckAnalyzer",
    "run_bottleneck_analytics",
    # Phase 32.2: Delay Propagation Analytics
    "PropagationTriggerType",
    "DelayDecomposition",
    "PropagationChainNode",
    "PropagationChain",
    "CorridorPropagationProfile",
    "DelayPropagationAnalyticsResult",
    "DelayPropagationAnalyzer",
    "run_delay_propagation_analytics",
]




