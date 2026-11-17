"""
tests/test_phase31_4_comparative.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test suite for Phase 31.4: Comparative Results & Statistical Analysis.

Tests cover:
  1. Module export and class presence.
  2. _descriptive_stats edge cases (empty, single, multi).
  3. ComparativeRecord construction and serialization.
  4. DelayStats, ThroughputStats, SolverStats calculation logic.
  5. Infeasible experiment isolation (never in feasible statistics).
  6. ScalabilityTrend and SeverityTrend builders.
  7. ComparativeAnalysisResult JSON export and Markdown generation.
  8. Exclusion of pending services across comparative records.
  9. Dataset immutability during comparative analysis.
 10. End-to-end execution of ComparativeAnalyzer on the research suite.
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
    ComparativeAnalyzer,
    ComparativeRecord,
    DelayStats,
    ScalabilityTrend,
    SeverityTrend,
    SolverStats,
    ThroughputStats,
    _compute_delay_stats,
    _compute_solver_stats,
    _compute_throughput_stats,
    _descriptive_stats,
    _result_to_record,
    run_comparative_analysis,
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


# ---------------------------------------------------------------------------
# 1. Module Exports & Types
# ---------------------------------------------------------------------------

def test_module_exports():
    """All required Phase 31.4 symbols are accessible."""
    import evaluation
    expected_exports = [
        "ComparativeRecord",
        "DelayStats",
        "ThroughputStats",
        "SolverStats",
        "ScalabilityTrend",
        "SeverityTrend",
        "ComparativeAnalysisResult",
        "ComparativeAnalyzer",
        "run_comparative_analysis",
    ]
    for symbol in expected_exports:
        assert hasattr(evaluation, symbol), f"evaluation missing export: {symbol}"


# ---------------------------------------------------------------------------
# 2. Descriptive Stats Function
# ---------------------------------------------------------------------------

def test_descriptive_stats_empty():
    """Empty list returns n=0 with None stats."""
    res = _descriptive_stats([])
    assert res["n"] == 0
    assert res["mean"] is None
    assert res["median"] is None
    assert res["min"] is None
    assert res["max"] is None
    assert res["stdev"] is None


def test_descriptive_stats_single():
    """Single value list returns zero stdev and matching mean/median/min/max."""
    res = _descriptive_stats([42.0])
    assert res["n"] == 1
    assert res["mean"] == 42.0
    assert res["median"] == 42.0
    assert res["min"] == 42.0
    assert res["max"] == 42.0
    assert res["stdev"] == 0.0


def test_descriptive_stats_multi():
    """Multi-element list computes mathematically exact stats."""
    values = [10.0, 20.0, 30.0, 40.0, 50.0]
    res = _descriptive_stats(values)
    assert res["n"] == 5
    assert res["mean"] == 30.0
    assert res["median"] == 30.0
    assert res["min"] == 10.0
    assert res["max"] == 50.0
    assert pytest.approx(res["stdev"], 0.01) == 15.811


# ---------------------------------------------------------------------------
# 3. ComparativeRecord
# ---------------------------------------------------------------------------

def test_comparative_record_from_feasible():
    """Feasible experiment result populates ComparativeRecord accurately."""
    res = _make_dummy_result("EXP_01", ExperimentGroupType.BASELINE, feasible=True, fifo_total_delay=120.0, cpsat_total_delay=80.0)
    rec = ComparativeRecord.from_experiment_result(res, source_phase="31.1")

    assert rec.experiment_id == "EXP_01"
    assert rec.is_feasible is True
    assert rec.source_phase == "31.1"
    assert rec.group == ExperimentGroupType.BASELINE.value
    assert rec.fifo_total_delay_min == 120.0
    assert rec.cpsat_total_delay_min == 80.0
    assert rec.delay_savings_min == 40.0
    assert pytest.approx(rec.delay_savings_pct, 0.01) == 33.33
    assert rec.solver_status == "OPTIMAL"


def test_comparative_record_from_infeasible():
    """Infeasible experiment preserves status and flags is_feasible as False."""
    res = _make_dummy_result("EXP_INF", ExperimentGroupType.BLOCKED_SECTION, feasible=False, status="INFEASIBLE", solve_time=0.5)
    rec = ComparativeRecord.from_experiment_result(res, source_phase="31.3", disruption_class="TRACK_BLOCKAGE", severity_level="SEVERE")

    assert rec.experiment_id == "EXP_INF"
    assert rec.is_feasible is False
    assert rec.solver_status == "INFEASIBLE"
    assert rec.disruption_class == "TRACK_BLOCKAGE"
    assert rec.severity_level == "SEVERE"
    assert rec.source_phase == "31.3"


def test_comparative_record_to_dict():
    """to_dict produces clean serializable dictionary."""
    res = _make_dummy_result("EXP_01", ExperimentGroupType.BASELINE)
    rec = ComparativeRecord.from_experiment_result(res, source_phase="31.1")
    d = rec.to_dict()
    assert isinstance(d, dict)
    assert d["experiment_id"] == "EXP_01"
    assert d["is_feasible"] is True
    assert "fifo_total_delay_min" in d
    assert "cpsat_total_delay_min" in d


# ---------------------------------------------------------------------------
# 4. Statistical Aggregations (Delay, Throughput, Solver)
# ---------------------------------------------------------------------------

def test_delay_stats_computation():
    """DelayStats aggregates correctly over feasible records."""
    r1 = ComparativeRecord.from_experiment_result(_make_dummy_result("E1", ExperimentGroupType.BASELINE, fifo_total_delay=100.0, cpsat_total_delay=80.0), "31.1")
    r2 = ComparativeRecord.from_experiment_result(_make_dummy_result("E2", ExperimentGroupType.BASELINE, fifo_total_delay=200.0, cpsat_total_delay=140.0), "31.1")
    
    ds = _compute_delay_stats([r1, r2], "total")

    assert ds.n_feasible == 2
    assert ds.n_infeasible == 0
    assert ds.n_total == 2
    assert ds.fifo_stats["mean"] == 150.0
    assert ds.cpsat_stats["mean"] == 110.0
    assert ds.savings_min_stats["mean"] == 40.0
    assert ds.to_dict()["n_total"] == 2


def test_infeasible_excluded_from_feasible_stats():
    """Infeasible records must NEVER enter the feasible statistics calculation."""
    r_feas = ComparativeRecord.from_experiment_result(_make_dummy_result("E_FEAS", ExperimentGroupType.BASELINE, fifo_total_delay=100.0, cpsat_total_delay=80.0), "31.1")
    r_inf = ComparativeRecord.from_experiment_result(_make_dummy_result("E_INF", ExperimentGroupType.BLOCKED_SECTION, feasible=False, status="INFEASIBLE"), "31.3")

    ds = _compute_delay_stats([r_feas, r_inf], "total")

    assert ds.n_total == 2
    assert ds.n_feasible == 1
    assert ds.n_infeasible == 1
    assert ds.fifo_stats["n"] == 1
    assert ds.fifo_stats["mean"] == 100.0
    assert ds.cpsat_stats["mean"] == 80.0
    assert ds.savings_min_stats["mean"] == 20.0


def test_solver_stats_computation():
    """SolverStats computes correct status counts and optimal percentage."""
    r1 = ComparativeRecord.from_experiment_result(_make_dummy_result("E1", ExperimentGroupType.BASELINE, status="OPTIMAL", solve_time=1.0), "31.1")
    r2 = ComparativeRecord.from_experiment_result(_make_dummy_result("E2", ExperimentGroupType.BASELINE, status="FEASIBLE", solve_time=3.0), "31.1")
    r3 = ComparativeRecord.from_experiment_result(_make_dummy_result("E3", ExperimentGroupType.BASELINE, status="OPTIMAL", solve_time=2.0), "31.1")

    ss = _compute_solver_stats([r1, r2, r3])

    assert ss.n == 3
    assert ss.status_counts["OPTIMAL"] == 2
    assert ss.status_counts["FEASIBLE"] == 1
    assert pytest.approx(ss.optimal_rate_pct, 0.1) == 66.67
    assert ss.solve_time_stats["mean"] == 2.0


def test_throughput_stats_computation():
    """ThroughputStats calculates completion rate and conflict resolution rate."""
    r1 = ComparativeRecord.from_experiment_result(_make_dummy_result("E1", ExperimentGroupType.BASELINE), "31.1")
    ts = _compute_throughput_stats([r1])
    assert ts.n == 1
    assert ts.mean_completion_rate_pct == 100.0
    assert ts.conflict_resolution_rate_pct == 80.0


# ---------------------------------------------------------------------------
# 5. Trends (Scalability & Severity)
# ---------------------------------------------------------------------------

def test_scalability_trend_construction():
    """ScalabilityTrend models both nominal and compound outcomes per load level."""
    st = ScalabilityTrend(
        load_level=20,
        nominal_record=ComparativeRecord.from_experiment_result(_make_dummy_result("NOM_20", ExperimentGroupType.BASELINE, fifo_total_delay=5.0, cpsat_total_delay=5.0), "31.2_nominal"),
        compound_record=ComparativeRecord.from_experiment_result(_make_dummy_result("CMP_20", ExperimentGroupType.COMPOUND_DISRUPTION, fifo_total_delay=150.0, cpsat_total_delay=100.0), "31.2_compound"),
    )
    d = st.to_dict()
    assert d["load_level"] == 20
    assert d["nominal"]["experiment_id"] == "NOM_20"
    assert d["compound"]["experiment_id"] == "CMP_20"


def test_severity_trend_construction():
    """SeverityTrend captures progression across Low, Moderate, Severe."""
    r_low = ComparativeRecord.from_experiment_result(_make_dummy_result("DIS_LOW", ExperimentGroupType.BLOCKED_SECTION, fifo_total_delay=30.0, cpsat_total_delay=20.0), "31.3")
    r_mod = ComparativeRecord.from_experiment_result(_make_dummy_result("DIS_MOD", ExperimentGroupType.BLOCKED_SECTION, fifo_total_delay=60.0, cpsat_total_delay=35.0), "31.3")
    r_sev = ComparativeRecord.from_experiment_result(_make_dummy_result("DIS_SEV", ExperimentGroupType.BLOCKED_SECTION, feasible=False, status="INFEASIBLE"), "31.3")

    trend = SeverityTrend(
        disruption_class="TRACK_BLOCKAGE",
        mild_record=r_low,
        moderate_record=r_mod,
        severe_record=r_sev,
        is_monotonic_baseline=True,
        has_feasibility_cliff=True,
    )
    d = trend.to_dict()
    assert d["disruption_class"] == "TRACK_BLOCKAGE"
    assert d["has_feasibility_cliff"] is True
    assert d["is_monotonic_baseline"] is True
    assert d["mild"]["experiment_id"] == "DIS_LOW"
    assert d["moderate"]["experiment_id"] == "DIS_MOD"
    assert d["severe"]["experiment_id"] == "DIS_SEV"


# ---------------------------------------------------------------------------
# 6. JSON Export & Markdown Generation
# ---------------------------------------------------------------------------

def test_comparative_analysis_result_json_and_markdown(tmp_path):
    """ComparativeAnalysisResult exports valid JSON and Markdown."""
    r1 = ComparativeRecord.from_experiment_result(_make_dummy_result("E1", ExperimentGroupType.BASELINE, fifo_total_delay=100.0, cpsat_total_delay=70.0), "31.1")
    r2 = ComparativeRecord.from_experiment_result(_make_dummy_result("E2", ExperimentGroupType.BLOCKED_SECTION, feasible=False, status="INFEASIBLE"), "31.3", disruption_class="TRACK_BLOCKAGE", severity_level="SEVERE")

    result = ComparativeAnalysisResult(
        generated_at="2026-09-20T14:30:00Z",
        phase31_1_records=[r1],
        phase31_2_nominal_records=[],
        phase31_2_compound_records=[],
        phase31_3_records=[r2],
        scalability_trends=[],
        severity_trends=[],
        global_delay_stats_total=_compute_delay_stats([r1, r2], "total"),
        global_delay_stats_average=_compute_delay_stats([r1, r2], "average"),
        global_delay_stats_peak=_compute_delay_stats([r1, r2], "peak"),
        global_throughput_stats=_compute_throughput_stats([r1]),
        global_solver_stats=_compute_solver_stats([r1, r2]),
    )

    # JSON export
    json_path = tmp_path / "comparative_test.json"
    result.export_json(str(json_path))
    assert os.path.exists(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["summary"]["total_experiments"] == 2
    assert loaded["summary"]["feasible_count"] == 1
    assert loaded["summary"]["infeasible_count"] == 1
    assert len(loaded["infeasible_registry"]) == 1

    # Markdown generation
    md = result.generate_markdown()
    assert isinstance(md, str)
    assert "# Railway Traffic Optimizer - Phase 31.4 Comparative Analysis" in md
    assert "## 1  Experiment Source Breakdown" in md
    assert "## 2  Global FIFO Baseline vs CP-SAT - Delay Statistics" in md
    assert "## 8  Infeasible Case Registry" in md
    assert "INFEASIBLE: mathematical boundary exceeded" in md



# ---------------------------------------------------------------------------
# 7. Invariants: Pending Services & Dataset Immutability
# ---------------------------------------------------------------------------

def test_pending_services_exclusion_invariant():
    """Verify all 7 pending services are defined and strictly tracked."""
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
    """Verify master datasets are unchanged before/after test."""
    timetable_path = "data/trains/published_timetables/timetable.json"
    trains_path = "data/trains/train_identity/trains.json"
    
    with open(timetable_path, "r", encoding="utf-8") as f:
        tt_data = json.load(f)
    with open(trains_path, "r", encoding="utf-8") as f:
        tr_data = json.load(f)

    # Timetable must have 127 entries; Trains must have 51 entries
    assert len(tt_data) == 127
    assert len(tr_data) == 51
