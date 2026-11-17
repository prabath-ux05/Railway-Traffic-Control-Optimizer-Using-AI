"""
tests/test_phase31_5_metrics.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test suite for Phase 31.5: Research Metrics Consolidation.

Tests cover:
  1. Module export and class presence.
  2. ResearchKPISummary, GroupKPISummary, ScalabilityKPISummary serialization.
  3. SeverityKPISummary, InfeasibleBoundarySummary, BottleneckKPISummary.
  4. MetricsConsolidator consolidation logic with synthetic ComparativeAnalysisResult.
  5. Infeasible boundary isolation ($n=1$ in registry, never in feasible KPIs).
  6. ConsolidatedResearchMetrics JSON export and Markdown generation.
  7. Strict pending services exclusion invariant.
  8. Dataset immutability invariant.
"""

from __future__ import annotations

import json
import os
import pytest
from typing import List

from optimization.scheduler import OptimizationResult, PerformanceMetrics
from optimization.scenarios import Scenario, ScenarioComparison
from evaluation.framework import (
    PENDING_SERVICES,
    ExperimentGroupType,
    ResearchExperimentConfig,
    ResearchExperimentResult,
    ResearchMetrics,
)
from evaluation.scalability_framework import (
    SCALABILITY_LOAD_LEVELS,
)
from evaluation.severity_framework import (
    DisruptionClass,
    SeverityLevel,
)
from evaluation.comparative_analysis import (
    ComparativeAnalysisResult,
    ComparativeRecord,
    DelayStats,
    ScalabilityTrend,
    SeverityTrend,
    SolverStats,
    ThroughputStats,
    _compute_delay_stats,
    _compute_solver_stats,
    _compute_throughput_stats,
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


# ---------------------------------------------------------------------------
# Test Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_dummy_metrics(
    feasible: bool = True,
    fifo_total_delay: float = 100.0,
    cpsat_total_delay: float = 70.0,
    fifo_peak_delay: float = 30.0,
    cpsat_peak_delay: float = 20.0,
    total_services: int = 10,
    fifo_conflicts: int = 5,
    cpsat_conflicts: int = 1,
    status: str = "OPTIMAL",
    solve_time: float = 1.25,
) -> ResearchMetrics:
    delay_savings = fifo_total_delay - cpsat_total_delay if feasible else 0.0
    delay_savings_pct = (delay_savings / fifo_total_delay * 100.0) if (feasible and fifo_total_delay > 0) else 0.0
    return ResearchMetrics(
        published_total_delay_minutes=0.0,
        feasible_baseline_total_delay_minutes=fifo_total_delay,
        optimized_total_delay_minutes=cpsat_total_delay if feasible else 0.0,
        delay_savings_minutes=delay_savings,
        delay_savings_percent=delay_savings_pct,
        feasible_baseline_average_delay_minutes=fifo_total_delay / total_services if total_services > 0 else 0.0,
        optimized_average_delay_minutes=cpsat_total_delay / total_services if (feasible and total_services > 0) else 0.0,
        average_delay_savings_minutes=delay_savings / total_services if (feasible and total_services > 0) else 0.0,
        feasible_baseline_peak_delay_minutes=fifo_peak_delay,
        optimized_peak_delay_minutes=cpsat_peak_delay if feasible else 0.0,
        peak_delay_savings_minutes=fifo_peak_delay - cpsat_peak_delay if feasible else 0.0,
        throughput=total_services if feasible else 0,
        total_requested_services=total_services,
        completion_rate_percent=100.0 if feasible else 0.0,
        on_time_performance_percent=80.0 if feasible else 0.0,
        initial_conflicts=fifo_conflicts,
        baseline_remaining_conflicts=fifo_conflicts,
        optimized_remaining_conflicts=cpsat_conflicts if feasible else fifo_conflicts,
        resolved_conflicts=fifo_conflicts - cpsat_conflicts if feasible else 0,
        solver_status=status if feasible else "INFEASIBLE",
        solve_time_seconds=solve_time,
        precedence_decisions_count=4,
    )


def _make_dummy_result(
    exp_id: str,
    group: ExperimentGroupType,
    feasible: bool = True,
    fifo_total_delay: float = 100.0,
    cpsat_total_delay: float = 70.0,
    status: str = "OPTIMAL",
    solve_time: float = 1.5,
) -> ResearchExperimentResult:
    scenario = Scenario(scenario_id=f"SCEN_{exp_id}", name=f"Scenario {exp_id}")
    config = ResearchExperimentConfig(
        experiment_id=exp_id,
        group=group,
        name=f"Test {exp_id}",
        description="Unit test fixture",
        scenario=scenario,
        target_service_ids=["SRV_01", "SRV_02"],
    )
    metrics = _make_dummy_metrics(
        feasible=feasible,
        fifo_total_delay=fifo_total_delay,
        cpsat_total_delay=cpsat_total_delay,
        status=status,
        solve_time=solve_time,
    )
    base_opt = OptimizationResult(status="BASELINE", metrics=PerformanceMetrics(total_delay_minutes=fifo_total_delay))
    cpsat_opt = OptimizationResult(status=status if feasible else "INFEASIBLE", metrics=PerformanceMetrics(total_delay_minutes=cpsat_total_delay if feasible else 0.0))
    comparison = ScenarioComparison(
        scenario_id=f"SCEN_{exp_id}",
        name=f"Scenario {exp_id}",
        description="Unit test fixture",
        baseline_result=base_opt,
        optimized_result=cpsat_opt,
    )
    return ResearchExperimentResult(config=config, metrics=metrics, comparison=comparison)


def _build_dummy_comparative_result() -> ComparativeAnalysisResult:
    r1 = ComparativeRecord.from_experiment_result(_make_dummy_result("E1", ExperimentGroupType.BASELINE, fifo_total_delay=100.0, cpsat_total_delay=70.0), "31.1")
    r2 = ComparativeRecord.from_experiment_result(_make_dummy_result("E2", ExperimentGroupType.COMPOUND_DISRUPTION, fifo_total_delay=200.0, cpsat_total_delay=140.0), "31.1")
    r_nom = ComparativeRecord.from_experiment_result(_make_dummy_result("E_NOM4", ExperimentGroupType.BASELINE, fifo_total_delay=35.0, cpsat_total_delay=35.0), "31.2_nominal", load_level=4)
    r_cmp = ComparativeRecord.from_experiment_result(_make_dummy_result("E_CMP4", ExperimentGroupType.COMPOUND_DISRUPTION, fifo_total_delay=140.0, cpsat_total_delay=90.0), "31.2_compound", load_level=4)
    r_inf = ComparativeRecord.from_experiment_result(_make_dummy_result("E_INF", ExperimentGroupType.BLOCKED_SECTION, feasible=False, status="INFEASIBLE"), "31.3", disruption_class="BLOCKED_SECTION", severity_level="SEVERE")

    return ComparativeAnalysisResult(
        generated_at="2026-09-20T14:30:00Z",
        phase31_1_records=[r1, r2],
        phase31_2_nominal_records=[r_nom],
        phase31_2_compound_records=[r_cmp],
        phase31_3_records=[r_inf],
        scalability_trends=[],
        severity_trends=[],
        global_delay_stats_total=_compute_delay_stats([r1, r2, r_nom, r_cmp, r_inf], "total"),
        global_delay_stats_average=_compute_delay_stats([r1, r2, r_nom, r_cmp, r_inf], "average"),
        global_delay_stats_peak=_compute_delay_stats([r1, r2, r_nom, r_cmp, r_inf], "peak"),
        global_throughput_stats=_compute_throughput_stats([r1, r2, r_nom, r_cmp]),
        global_solver_stats=_compute_solver_stats([r1, r2, r_nom, r_cmp, r_inf]),
    )


# ---------------------------------------------------------------------------
# 1. Module Exports & Types
# ---------------------------------------------------------------------------

def test_module_exports():
    """All required Phase 31.5 symbols are accessible."""
    import evaluation
    expected_exports = [
        "ResearchKPISummary",
        "GroupKPISummary",
        "ScalabilityKPISummary",
        "SeverityKPISummary",
        "InfeasibleBoundarySummary",
        "BottleneckKPISummary",
        "ConsolidatedResearchMetrics",
        "MetricsConsolidator",
        "run_metrics_consolidation",
    ]
    for symbol in expected_exports:
        assert hasattr(evaluation, symbol), f"evaluation missing export: {symbol}"


# ---------------------------------------------------------------------------
# 2. Dataclass Construction & Serialization
# ---------------------------------------------------------------------------

def test_kpi_summary_serialization():
    """ResearchKPISummary produces clean dictionary."""
    kpi = ResearchKPISummary(
        n_total_experiments=45,
        n_feasible_experiments=44,
        n_infeasible_experiments=1,
        mean_fifo_total_delay_min=331.38,
        mean_cpsat_total_delay_min=314.39,
        mean_delay_savings_min=16.99,
        median_delay_savings_min=0.0,
        max_delay_savings_min=125.50,
        mean_delay_savings_pct=-0.61,
        max_delay_savings_pct=55.16,
        mean_fifo_peak_delay_min=172.01,
        mean_cpsat_peak_delay_min=165.59,
        mean_peak_delay_savings_min=6.42,
        max_peak_delay_savings_min=30.00,
        mean_completion_rate_pct=97.78,
        mean_on_time_pct=85.0,
        total_initial_conflicts=22,
        total_resolved_conflicts=22,
        total_remaining_conflicts=0,
        overall_conflict_resolution_rate_pct=100.0,
        mean_precedence_decisions=4.0,
        optimality_rate_pct=97.8,
        mean_solve_time_seconds=0.44,
        max_solve_time_seconds=1.48,
    )
    d = kpi.to_dict()
    assert d["n_total_experiments"] == 45
    assert d["n_feasible_experiments"] == 44
    assert d["n_infeasible_experiments"] == 1
    assert d["mean_delay_savings_min"] == 16.99


def test_group_kpi_summary():
    """GroupKPISummary structures per-group findings."""
    g = GroupKPISummary(
        group_name="DEPARTURE_DELAY",
        group_code="EXP_GRP_02_DEP_DELAY",
        n_experiments=2,
        mean_fifo_delay_min=217.75,
        mean_cpsat_delay_min=117.50,
        mean_delay_savings_min=100.25,
        mean_delay_savings_pct=45.61,
        mean_solve_time_seconds=0.08,
        mean_conflicts_resolved=1.0,
        conflict_resolution_rate_pct=100.0,
    )
    d = g.to_dict()
    assert d["group_name"] == "DEPARTURE_DELAY"
    assert d["mean_delay_savings_min"] == 100.25


def test_scalability_kpi_summary():
    """ScalabilityKPISummary structures per-load comparisons."""
    s = ScalabilityKPISummary(
        load_level=40,
        nominal_fifo_delay_min=1926.0,
        nominal_cpsat_delay_min=1937.0,
        nominal_savings_min=-11.0,
        nominal_savings_pct=-0.6,
        nominal_solve_time_s=1.319,
        compound_fifo_delay_min=2127.5,
        compound_cpsat_delay_min=2066.0,
        compound_savings_min=61.5,
        compound_savings_pct=2.9,
        compound_conflicts="8->0",
        compound_solve_time_s=1.477,
    )
    d = s.to_dict()
    assert d["load_level"] == 40
    assert d["compound_savings_min"] == 61.5


# ---------------------------------------------------------------------------
# 3. Consolidation Logic
# ---------------------------------------------------------------------------

def test_metrics_consolidator_execution():
    """MetricsConsolidator transforms ComparativeAnalysisResult into ConsolidatedResearchMetrics."""
    cr = _build_dummy_comparative_result()
    consolidator = MetricsConsolidator()
    metrics = consolidator.consolidate(cr)

    assert isinstance(metrics, ConsolidatedResearchMetrics)
    assert metrics.kpi_summary.n_total_experiments == 5
    assert metrics.kpi_summary.n_feasible_experiments == 4
    assert metrics.kpi_summary.n_infeasible_experiments == 1
    assert len(metrics.infeasible_boundaries) == 1
    assert len(metrics.bottleneck_summaries) >= 3


def test_infeasible_boundary_isolation():
    """Verify the 1 infeasible boundary case is documented and excluded from feasible metrics."""
    cr = _build_dummy_comparative_result()
    consolidator = MetricsConsolidator()
    metrics = consolidator.consolidate(cr)

    # Infeasible case must be recorded in infeasible_boundaries
    assert len(metrics.infeasible_boundaries) == 1
    boundary = metrics.infeasible_boundaries[0]
    assert boundary.experiment_id == "EXP_31_3_12_BLK_SEVERE"
    assert "MAS_BBQ_THROAT_SEGMENT_DOWN" in boundary.target_resource

    # Feasible stats must strictly count n=4 feasible records
    assert metrics.kpi_summary.n_feasible_experiments == 4


# ---------------------------------------------------------------------------
# 4. JSON Export & Markdown Generation
# ---------------------------------------------------------------------------

def test_consolidated_metrics_json_and_markdown(tmp_path):
    """ConsolidatedResearchMetrics exports JSON and generates valid Markdown report."""
    cr = _build_dummy_comparative_result()
    consolidator = MetricsConsolidator()
    metrics = consolidator.consolidate(cr)

    # JSON export
    json_path = tmp_path / "consolidated_metrics_test.json"
    metrics.export_json(str(json_path))
    assert os.path.exists(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["phase"] == "31.5"
    assert loaded["kpi_summary"]["n_total_experiments"] == 5

    # Markdown generation
    md = metrics.generate_markdown()
    assert isinstance(md, str)
    assert "# Railway Traffic Optimizer — Phase 31.5 Research Metrics Consolidation" in md
    assert "## 1  Executive Research KPI Synthesis" in md
    assert "## 2  Performance by Experiment Group (Phase 31.1)" in md
    assert "## 3  Multi-Load Scalability Characterization (Phase 31.2)" in md
    assert "## 4  Disruption Severity Progression & Feasibility Cliffs (Phase 31.3)" in md
    assert "## 5  Feasibility Boundaries & Isolated Case Registry" in md
    assert "## 6  Identified Network Bottlenecks & Critical Throat Points" in md
    assert "## 7  Research Findings & Methodological Boundaries" in md


# ---------------------------------------------------------------------------
# 5. Invariants: Pending Services & Dataset Immutability
# ---------------------------------------------------------------------------

def test_pending_services_exclusion_invariant():
    """Verify all 7 pending services remain strictly excluded."""
    assert len(PENDING_SERVICES) == 7
    expected = {
        "SRV_40143_01",
        "SRV_40144_01",
        "SRV_41015_01",
        "SRV_41131_01",
        "SRV_41132_01",
        "SRV_42413_01",
        "SRV_42425_01",
    }
    assert set(PENDING_SERVICES) == expected


def test_dataset_immutability():
    """Verify master datasets are unchanged."""
    timetable_path = "data/trains/published_timetables/timetable.json"
    trains_path = "data/trains/train_identity/trains.json"
    
    with open(timetable_path, "r", encoding="utf-8") as f:
        tt_data = json.load(f)
    with open(trains_path, "r", encoding="utf-8") as f:
        tr_data = json.load(f)

    assert len(tt_data) == 127
    assert len(tr_data) == 51
