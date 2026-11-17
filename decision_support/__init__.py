"""
decision_support
~~~~~~~~~~~~~~~~
Dynamic Decision-Support Layer package for railway traffic management.

Turns simulation states, conflict detections, and CP-SAT optimization results
into explainable, deterministic dispatching recommendations.
"""

from decision_support.models import (
    BaselineOptimizationComparison,
    ConfidenceMetrics,
    ConstraintExplanation,
    ContestedBottleneck,
    CounterfactualAnalysis,
    DecisionSupportAssessment,
    DelayAnalysis,
    OperationalSeverity,
    OperationalSituation,
    PrioritizedConflict,
    PriorityTier,
    ReasoningStep,
    Recommendation,
    RecommendationCategory,
    RecommendationType,
    ServiceDelayImpact,
    SupportingEvidence,
)
from decision_support.advisor import (
    DecisionSupportAdvisor,
)
from decision_support.recommendation_refinement import (
    RecommendationClassification,
    RecommendationEvidence,
    RecommendationRefiner,
    RefinedRecommendation,
    RefinementAnalyticsResult,
    RefinementSummary,
    TraceabilityChain,
    TraceabilityPhase,
    run_recommendation_refinement,
)
from decision_support.what_if_comparison import (
    MultiScenarioComparativeSummary,
    ScenarioType,
    WhatIfAnalyticsResult,
    WhatIfComparisonEngine,
    WhatIfScenarioMetrics,
    run_what_if_comparison,
)

__all__ = [
    "BaselineOptimizationComparison",
    "ConfidenceMetrics",
    "ConstraintExplanation",
    "ContestedBottleneck",
    "CounterfactualAnalysis",
    "DecisionSupportAssessment",
    "DecisionSupportAdvisor",
    "DelayAnalysis",
    "MultiScenarioComparativeSummary",
    "OperationalSeverity",
    "OperationalSituation",
    "PrioritizedConflict",
    "PriorityTier",
    "ReasoningStep",
    "Recommendation",
    "RecommendationCategory",
    "RecommendationClassification",
    "RecommendationEvidence",
    "RecommendationRefiner",
    "RecommendationType",
    "RefinedRecommendation",
    "RefinementAnalyticsResult",
    "RefinementSummary",
    "ScenarioType",
    "ServiceDelayImpact",
    "SupportingEvidence",
    "TraceabilityChain",
    "TraceabilityPhase",
    "WhatIfAnalyticsResult",
    "WhatIfComparisonEngine",
    "WhatIfScenarioMetrics",
    "run_recommendation_refinement",
    "run_what_if_comparison",
]
