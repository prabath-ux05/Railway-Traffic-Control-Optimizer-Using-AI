"""
optimization/objective.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Objective function specifications, weighting parameters, and cost evaluation
for railway traffic optimization.

Provides penalty weights for delay minimization, conflict avoidance,
dwell time adherence, and throughput maximization.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from simulation.clock import time_to_minutes
from simulation.conflicts import Conflict, ConflictSeverity
from simulation.network import Service, TimetableEntry


@dataclass
class ObjectiveWeights:
    """Weighting coefficients for the multi-objective optimization function.

    Attributes:
        delay_weight: Multiplier for total train delay in minutes.
        weighted_delay_weight: Multiplier for priority-weighted delay.
        max_delay_weight: Penalty multiplier for the peak individual train delay.
        conflict_penalty_critical: Penalty score for each unresolved CRITICAL conflict.
        conflict_penalty_major: Penalty score for each unresolved MAJOR conflict.
        conflict_penalty_warning: Penalty score for each unresolved WARNING conflict.
        dwell_violation_penalty: Penalty per minute of dwell time violation.
        schedule_deviation_weight: Penalty per minute of departure deviation from timetable.
        cancellation_penalty: Penalty if a service must be cancelled or truncated.
    """
    delay_weight: float = 1.0
    weighted_delay_weight: float = 2.0
    max_delay_weight: float = 0.5
    conflict_penalty_critical: float = 1000.0
    conflict_penalty_major: float = 200.0
    conflict_penalty_warning: float = 50.0
    dwell_violation_penalty: float = 30.0
    schedule_deviation_weight: float = 0.8
    cancellation_penalty: float = 5000.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "delay_weight": self.delay_weight,
            "weighted_delay_weight": self.weighted_delay_weight,
            "max_delay_weight": self.max_delay_weight,
            "conflict_penalty_critical": self.conflict_penalty_critical,
            "conflict_penalty_major": self.conflict_penalty_major,
            "conflict_penalty_warning": self.conflict_penalty_warning,
            "dwell_violation_penalty": self.dwell_violation_penalty,
            "schedule_deviation_weight": self.schedule_deviation_weight,
            "cancellation_penalty": self.cancellation_penalty,
        }


@dataclass
class ObjectiveCostBreakdown:
    """Itemized breakdown of optimization objective costs."""
    base_delay_cost: float = 0.0
    weighted_delay_cost: float = 0.0
    max_delay_cost: float = 0.0
    conflict_penalty_cost: float = 0.0
    dwell_penalty_cost: float = 0.0
    schedule_deviation_cost: float = 0.0
    total_cost: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "base_delay_cost": round(self.base_delay_cost, 2),
            "weighted_delay_cost": round(self.weighted_delay_cost, 2),
            "max_delay_cost": round(self.max_delay_cost, 2),
            "conflict_penalty_cost": round(self.conflict_penalty_cost, 2),
            "dwell_penalty_cost": round(self.dwell_penalty_cost, 2),
            "schedule_deviation_cost": round(self.schedule_deviation_cost, 2),
            "total_cost": round(self.total_cost, 2),
        }


class OptimizationObjective:
    """Evaluates optimization objectives and calculates cost breakdowns."""

    def __init__(self, weights: Optional[ObjectiveWeights] = None):
        self.weights = weights or ObjectiveWeights()

    def evaluate_conflict_penalty(self, conflicts: List[Conflict]) -> float:
        """Compute total penalty for a list of unresolved conflicts."""
        total = 0.0
        for c in conflicts:
            if c.severity == ConflictSeverity.CRITICAL:
                total += self.weights.conflict_penalty_critical
            elif c.severity == ConflictSeverity.MAJOR:
                total += self.weights.conflict_penalty_major
            elif c.severity == ConflictSeverity.WARNING:
                total += self.weights.conflict_penalty_warning
        return total

    def evaluate_cost(
        self,
        total_delay_minutes: float,
        total_weighted_delay: float,
        max_delay_minutes: float,
        conflicts: List[Conflict],
        dwell_violations_minutes: float = 0.0,
        schedule_deviation_minutes: float = 0.0,
    ) -> ObjectiveCostBreakdown:
        """Compute the full multi-objective cost breakdown."""
        base_delay_cost = total_delay_minutes * self.weights.delay_weight
        weighted_delay_cost = total_weighted_delay * self.weights.weighted_delay_weight
        max_delay_cost = max_delay_minutes * self.weights.max_delay_weight
        conflict_cost = self.evaluate_conflict_penalty(conflicts)
        dwell_cost = dwell_violations_minutes * self.weights.dwell_violation_penalty
        dev_cost = schedule_deviation_minutes * self.weights.schedule_deviation_weight

        total = (
            base_delay_cost
            + weighted_delay_cost
            + max_delay_cost
            + conflict_cost
            + dwell_cost
            + dev_cost
        )

        return ObjectiveCostBreakdown(
            base_delay_cost=base_delay_cost,
            weighted_delay_cost=weighted_delay_cost,
            max_delay_cost=max_delay_cost,
            conflict_penalty_cost=conflict_cost,
            dwell_penalty_cost=dwell_cost,
            schedule_deviation_cost=dev_cost,
            total_cost=total,
        )
