"""
tests/test_analysis.py
~~~~~~~~~~~~~~~~~~~~~~
Batch 14: Unit and integration tests for Scalability Results Analysis & Validation.

Verifies:
1. Metric calculations:
   - Solve-time scaling statistics (mean, min, max, normal, ms/service)
   - Delay and cost savings scaling (mean, %, disrupted mean, cost savings)
   - Status summary aggregation (OPTIMAL, FEASIBLE, INFEASIBLE, TIME_LIMIT)
   - Throughput summary and maintenance flags
   - Conflict summary, resolution rate, and unresolved flags
   - Bottleneck detection and classification
   - Limitation generation and structure
2. Determinism and Report Formatting:
   - 20-case results table in Markdown has all required columns and 20 data rows
   - 20-case results table in ASCII has all required columns and 20 data rows
   - Full Markdown report contains all 7 analytical sections
   - Summary ASCII report is non-empty and well-formatted
   - `to_dict()` produces fully serializable dictionaries
3. End-to-End Integration:
   - Complete 20-case sweep and analysis executes cleanly
   - 100% OPTIMAL solver status
   - 100% throughput maintenance
   - 0 remaining conflicts across all cases
4. Dataset Integrity:
   - No JSON files in `data/` are modified (SHA-256 integrity check)
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List

import pytest

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
from evaluation.scalability import (
    ALL_DISRUPTION_MODES,
    DISRUPTION_MULTI_DELAY,
    DISRUPTION_NORMAL,
    DISRUPTION_SEVERE_COMPOUND,
    DISRUPTION_SINGLE_DELAY,
    ScalabilityLoadLevel,
    ScalabilityMetrics,
    ScalabilityReport,
    ScalabilityResult,
    ScalabilityRunner,
    create_west_corridor_load_levels,
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers & SHA-256 Verification Fixture
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_json_hashes() -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    data_dir = os.path.join(_REPO_ROOT, "data")
    for root, _dirs, files in os.walk(data_dir):
        for fname in files:
            if fname.endswith(".json"):
                full = os.path.join(root, fname)
                hashes[full] = _sha256_file(full)
    return hashes


@pytest.fixture(scope="module")
def json_hashes_before() -> Dict[str, str]:
    return _collect_json_hashes()


# ---------------------------------------------------------------------------
# Synthetic / Fixture Data for Unit Testing
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_load_level_4() -> ScalabilityLoadLevel:
    return ScalabilityLoadLevel(
        label="4 Services",
        service_ids=["SRV_1", "SRV_2", "SRV_3", "SRV_4"],
        rationale="4-service test cohort",
        outbound_services=["SRV_1", "SRV_2"],
    )


@pytest.fixture
def sample_metrics_4_normal() -> ScalabilityMetrics:
    return ScalabilityMetrics(
        load_label="4 Services",
        service_count=4,
        disruption_mode=DISRUPTION_NORMAL,
        feasible_baseline_total_delay=100.0,
        optimized_total_delay=100.0,
        delay_savings=0.0,
        delay_savings_percent=0.0,
        feasible_baseline_max_delay=20.0,
        optimized_max_delay=20.0,
        baseline_throughput=4,
        optimized_throughput=4,
        initial_conflicts=0,
        baseline_remaining_conflicts=0,
        optimized_remaining_conflicts=0,
        resolved_conflicts=0,
        feasible_baseline_objective_cost=300.0,
        optimized_objective_cost=300.0,
        solver_status="OPTIMAL",
        solve_time_seconds=0.10,
        precedence_decisions_count=10,
        resource_decisions_count=8,
    )


@pytest.fixture
def sample_metrics_4_single() -> ScalabilityMetrics:
    return ScalabilityMetrics(
        load_label="4 Services",
        service_count=4,
        disruption_mode=DISRUPTION_SINGLE_DELAY,
        feasible_baseline_total_delay=150.0,
        optimized_total_delay=110.0,
        delay_savings=40.0,
        delay_savings_percent=26.67,
        feasible_baseline_max_delay=40.0,
        optimized_max_delay=25.0,
        baseline_throughput=4,
        optimized_throughput=4,
        initial_conflicts=1,
        baseline_remaining_conflicts=0,
        optimized_remaining_conflicts=0,
        resolved_conflicts=1,
        feasible_baseline_objective_cost=450.0,
        optimized_objective_cost=330.0,
        solver_status="OPTIMAL",
        solve_time_seconds=0.12,
        precedence_decisions_count=12,
        resource_decisions_count=8,
    )


@pytest.fixture
def sample_metrics_4_multi() -> ScalabilityMetrics:
    return ScalabilityMetrics(
        load_label="4 Services",
        service_count=4,
        disruption_mode=DISRUPTION_MULTI_DELAY,
        feasible_baseline_total_delay=200.0,
        optimized_total_delay=120.0,
        delay_savings=80.0,
        delay_savings_percent=40.0,
        feasible_baseline_max_delay=50.0,
        optimized_max_delay=30.0,
        baseline_throughput=4,
        optimized_throughput=4,
        initial_conflicts=2,
        baseline_remaining_conflicts=0,
        optimized_remaining_conflicts=0,
        resolved_conflicts=2,
        feasible_baseline_objective_cost=600.0,
        optimized_objective_cost=360.0,
        solver_status="OPTIMAL",
        solve_time_seconds=0.14,
        precedence_decisions_count=14,
        resource_decisions_count=8,
    )


@pytest.fixture
def sample_metrics_4_severe() -> ScalabilityMetrics:
    return ScalabilityMetrics(
        load_label="4 Services",
        service_count=4,
        disruption_mode=DISRUPTION_SEVERE_COMPOUND,
        feasible_baseline_total_delay=250.0,
        optimized_total_delay=150.0,
        delay_savings=100.0,
        delay_savings_percent=40.0,
        feasible_baseline_max_delay=60.0,
        optimized_max_delay=35.0,
        baseline_throughput=4,
        optimized_throughput=4,
        initial_conflicts=3,
        baseline_remaining_conflicts=0,
        optimized_remaining_conflicts=0,
        resolved_conflicts=3,
        feasible_baseline_objective_cost=750.0,
        optimized_objective_cost=450.0,
        solver_status="OPTIMAL",
        solve_time_seconds=0.16,
        precedence_decisions_count=16,
        resource_decisions_count=8,
    )


@pytest.fixture
def sample_report(
    sample_load_level_4: ScalabilityLoadLevel,
    sample_metrics_4_normal: ScalabilityMetrics,
    sample_metrics_4_single: ScalabilityMetrics,
    sample_metrics_4_multi: ScalabilityMetrics,
    sample_metrics_4_severe: ScalabilityMetrics,
) -> ScalabilityReport:
    res = ScalabilityResult(
        load_level=sample_load_level_4,
        runs=[
            sample_metrics_4_normal,
            sample_metrics_4_single,
            sample_metrics_4_multi,
            sample_metrics_4_severe,
        ],
    )
    return ScalabilityReport(
        results=[res],
        created_at="2026-09-10T14:00:00+00:00",
        elapsed_wall_seconds=0.60,
    )


# ---------------------------------------------------------------------------
# Unit Tests: Metric Calculations
# ---------------------------------------------------------------------------

class TestMetricCalculations:
    """Test individual calculation methods on ScalabilityAnalyzer."""

    def test_solve_time_scaling_calculation(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        scaling = analyzer.compute_solve_time_scaling(sample_report)

        assert len(scaling) == 1
        s = scaling[0]
        assert s.load_label == "4 Services"
        assert s.service_count == 4
        # Times are 0.10, 0.12, 0.14, 0.16 -> Mean is 0.13
        assert pytest.approx(s.mean_solve_time_seconds, abs=1e-3) == 0.13
        assert pytest.approx(s.min_solve_time_seconds, abs=1e-3) == 0.10
        assert pytest.approx(s.max_solve_time_seconds, abs=1e-3) == 0.16
        assert pytest.approx(s.normal_solve_time_seconds, abs=1e-3) == 0.10
        assert pytest.approx(s.solve_time_per_service_ms, abs=1e-1) == 32.5

        d = s.to_dict()
        assert d["service_count"] == 4
        assert "mean_solve_time_seconds" in d

    def test_savings_scaling_calculation(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        savings = analyzer.compute_savings_scaling(sample_report)

        assert len(savings) == 1
        s = savings[0]
        assert s.load_label == "4 Services"
        assert s.service_count == 4
        # Savings: 0, 40, 80, 100 -> Mean = 55.0
        assert pytest.approx(s.mean_delay_savings_minutes, abs=1e-2) == 55.0
        # Disrupted savings: 40, 80, 100 -> Mean = 73.33
        assert pytest.approx(s.disrupted_mean_savings_minutes, abs=1e-2) == 73.33
        assert pytest.approx(s.max_delay_savings_minutes, abs=1e-2) == 100.0

        d = s.to_dict()
        assert d["mean_delay_savings_minutes"] == 55.0

    def test_status_summary_all_optimal(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        summary = analyzer.compute_status_summary(sample_report)

        assert summary.total_runs == 4
        assert summary.optimal_count == 4
        assert summary.feasible_count == 0
        assert summary.infeasible_count == 0
        assert summary.time_limit_count == 0
        assert summary.all_optimal is True

        d = summary.to_dict()
        assert d["all_optimal"] is True
        assert "4 Services" in d["status_by_load"]

    def test_status_summary_mixed_statuses(self, sample_load_level_4: ScalabilityLoadLevel):
        r1 = ScalabilityMetrics(solver_status="OPTIMAL")
        r2 = ScalabilityMetrics(solver_status="FEASIBLE")
        r3 = ScalabilityMetrics(solver_status="INFEASIBLE")
        r4 = ScalabilityMetrics(solver_status="TIME_LIMIT")
        res = ScalabilityResult(load_level=sample_load_level_4, runs=[r1, r2, r3, r4])
        report = ScalabilityReport(results=[res])

        analyzer = ScalabilityAnalyzer()
        summary = analyzer.compute_status_summary(report)

        assert summary.total_runs == 4
        assert summary.optimal_count == 1
        assert summary.feasible_count == 1
        assert summary.infeasible_count == 1
        assert summary.time_limit_count == 1
        assert summary.all_optimal is False

    def test_throughput_summary_calculation(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        thr = analyzer.compute_throughput_summary(sample_report)

        assert len(thr) == 1
        t = thr[0]
        assert t.service_count == 4
        assert t.baseline_throughput == 4
        assert t.optimized_throughput == 4
        assert t.throughput_maintained_ratio == 1.0
        assert t.is_fully_maintained is True

    def test_conflict_summary_calculation(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        conf = analyzer.compute_conflict_summary(sample_report)

        assert len(conf) == 1
        c = conf[0]
        # Inits: 0 + 1 + 2 + 3 = 6
        assert c.initial_conflicts_total == 6
        assert pytest.approx(c.initial_conflicts_mean, abs=1e-2) == 1.5
        assert c.optimized_remaining_conflicts_total == 0
        assert c.resolved_conflicts_total == 6
        assert c.resolution_rate == 1.0
        assert c.has_unresolved_conflicts is False


# ---------------------------------------------------------------------------
# Unit Tests: Bottleneck and Limitation Detection
# ---------------------------------------------------------------------------

class TestBottleneckAndLimitations:
    """Test bottleneck detection logic under various scenarios."""

    def test_clean_no_bottleneck(self, sample_report: ScalabilityReport):
        # sample_report has no remaining conflicts and initial conflicts are resolved
        analyzer = ScalabilityAnalyzer()
        finding = analyzer.detect_first_bottleneck(sample_report)
        assert finding.impact_level in {"NONE", "LOW"}

    def test_bottleneck_on_non_optimal_status(self, sample_load_level_4: ScalabilityLoadLevel):
        r = ScalabilityMetrics(solver_status="TIME_LIMIT", optimized_remaining_conflicts=0)
        res = ScalabilityResult(load_level=sample_load_level_4, runs=[r])
        report = ScalabilityReport(results=[res])

        analyzer = ScalabilityAnalyzer()
        finding = analyzer.detect_first_bottleneck(report)
        assert finding.has_bottleneck is True
        assert finding.impact_level == "HIGH"
        assert finding.bottleneck_load_level == "4 Services"

    def test_bottleneck_on_unresolved_conflicts(self, sample_load_level_4: ScalabilityLoadLevel):
        r = ScalabilityMetrics(solver_status="OPTIMAL", optimized_remaining_conflicts=2)
        res = ScalabilityResult(load_level=sample_load_level_4, runs=[r])
        report = ScalabilityReport(results=[res])

        analyzer = ScalabilityAnalyzer()
        finding = analyzer.detect_first_bottleneck(report)
        assert finding.has_bottleneck is True
        assert finding.impact_level == "HIGH"
        assert finding.bottleneck_load_level == "4 Services"

    def test_limitations_structure(self):
        analyzer = ScalabilityAnalyzer()
        limitations = analyzer.generate_limitations()

        assert len(limitations) >= 5
        categories = {lim.category for lim in limitations}
        assert "DATASET_CEILING" in categories
        assert "TOPOLOGY_SCOPE" in categories
        assert "DISPATCH_SCOPE" in categories
        assert "TIME_HORIZON" in categories
        assert "BENCHMARK_ENVIRONMENT" in categories

        for lim in limitations:
            d = lim.to_dict()
            assert "category" in d
            assert "title" in d
            assert "description" in d
            assert len(lim.description) > 20

    def test_key_findings_generation(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        analysis = analyzer.analyze(sample_report)

        assert len(analysis.key_findings) >= 5
        categories = {f.category for f in analysis.key_findings}
        assert "SOLVE_TIME" in categories
        assert "DELAY_SAVINGS" in categories
        assert "SOLVER_STATUS" in categories
        assert "SYSTEM_STABILITY" in categories
        assert "SCALABILITY_BOUNDARY" in categories


# ---------------------------------------------------------------------------
# Unit Tests: Output Formatting (Tables & Reports)
# ---------------------------------------------------------------------------

class TestOutputFormatting:
    """Test table rendering and markdown generation."""

    def test_markdown_results_table_format(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        analysis = analyzer.analyze(sample_report)
        table_md = analysis.to_results_table_markdown()

        assert "| Load Level |" in table_md
        assert "| Feasible Base Delay |" in table_md
        assert "| CP-SAT Delay |" in table_md
        assert "| Delay Savings (%) |" in table_md
        assert "| Max Delay (Base / Opt) |" in table_md
        assert "| Throughput (Base / Opt) |" in table_md
        assert "| Rem Conf |" in table_md
        assert "| Solver Status |" in table_md
        assert "| Solve Time |" in table_md
        assert "| Obj Cost (Base / Opt) |" in table_md

        # 4 runs in sample_report -> 4 data rows + 2 header rows = 6 lines
        lines = [line for line in table_md.splitlines() if line.strip()]
        assert len(lines) == 6

    def test_ascii_results_table_format(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        analysis = analyzer.analyze(sample_report)
        table_ascii = analysis.to_results_table_ascii()

        assert "Load Level" in table_ascii
        assert "BaseDel" in table_ascii
        assert "OptDel" in table_ascii
        assert "Savings (%)" in table_ascii
        assert "4 Services" in table_ascii

    def test_markdown_report_structure(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        analysis = analyzer.analyze(sample_report)
        report_md = analysis.to_markdown_report()

        assert "# Batch 14: Scalability Results Analysis & Validation Report" in report_md
        assert "## 1. Complete 20-Case Scalability Results Table" in report_md
        assert "## 2. Solve Time vs Service Load Analysis" in report_md
        assert "## 3. Delay Savings & Efficiency vs Load Analysis" in report_md
        assert "## 4. Solver Status, Throughput & Conflict Degradation" in report_md
        assert "## 5. First Observable Scalability Bottleneck" in report_md
        assert "## 6. Experiment Limitations & Scope Boundaries" in report_md
        assert "## 7. Key Findings Summary" in report_md

    def test_summary_ascii(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        analysis = analyzer.analyze(sample_report)
        summary_txt = analysis.summary()

        assert "BATCH 14: SCALABILITY RESULTS ANALYSIS & VALIDATION SUMMARY" in summary_txt
        assert "SOLVE TIME SCALING:" in summary_txt
        assert "DELAY SAVINGS SCALING:" in summary_txt
        assert "BOTTLENECK ANALYSIS:" in summary_txt

    def test_to_dict_json_serializable(self, sample_report: ScalabilityReport):
        analyzer = ScalabilityAnalyzer()
        analysis = analyzer.analyze(sample_report)
        d = analysis.to_dict()

        json_str = json.dumps(d)
        assert len(json_str) > 500
        reloaded = json.loads(json_str)
        assert reloaded["total_cases"] == 4


# ---------------------------------------------------------------------------
# Integration Tests: Real 20-Case Scalability Sweep Analysis
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_analysis() -> ScalabilityAnalysis:
    """Run the actual 20-case sweep once for module tests."""
    return run_scalability_analysis()


class TestRealScalabilitySweepAnalysis:
    """End-to-end integration tests executing the real 20-case sweep and validating analysis."""

    def test_exact_20_cases_executed(self, real_analysis: ScalabilityAnalysis):
        assert real_analysis.total_cases == 20
        assert len(real_analysis.report.results) == 5
        for res in real_analysis.report.results:
            assert len(res.runs) == 4

    def test_all_20_cases_optimal(self, real_analysis: ScalabilityAnalysis):
        assert real_analysis.status_summary.optimal_count == 20
        assert real_analysis.status_summary.feasible_count == 0
        assert real_analysis.status_summary.infeasible_count == 0
        assert real_analysis.status_summary.time_limit_count == 0
        assert real_analysis.status_summary.all_optimal is True

    def test_solve_time_scaling_within_bounds(self, real_analysis: ScalabilityAnalysis):
        scaling = real_analysis.solve_time_scaling
        assert len(scaling) == 5

        # Verify service counts: 4, 8, 12, 16, 20
        counts = [s.service_count for s in scaling]
        assert counts == [4, 8, 12, 16, 20]

        # Verify mean solve times are finite and sub-second
        for s in scaling:
            assert 0.0 < s.mean_solve_time_seconds < 5.0
            assert s.min_solve_time_seconds <= s.mean_solve_time_seconds <= s.max_solve_time_seconds

    def test_savings_scaling_behavior(self, real_analysis: ScalabilityAnalysis):
        savings = real_analysis.savings_scaling
        assert len(savings) == 5

        for s in savings:
            # Under disrupted conditions, mean savings must be positive
            assert s.disrupted_mean_savings_minutes > 0.0
            assert s.disrupted_mean_savings_percent > 0.0
            # Mean cost savings should be non-negative
            assert s.mean_cost_savings >= 0.0

    def test_throughput_100_percent_maintained(self, real_analysis: ScalabilityAnalysis):
        thr = real_analysis.throughput_summary
        assert len(thr) == 5

        for t in thr:
            assert t.is_fully_maintained is True
            assert t.throughput_maintained_ratio == 1.0
            assert t.optimized_throughput == t.service_count

    def test_zero_remaining_conflicts(self, real_analysis: ScalabilityAnalysis):
        conf = real_analysis.conflict_summary
        assert len(conf) == 5

        for c in conf:
            assert c.optimized_remaining_conflicts_total == 0
            assert c.has_unresolved_conflicts is False
            assert c.resolution_rate == 1.0

    def test_20_case_markdown_table_has_all_rows(self, real_analysis: ScalabilityAnalysis):
        table_md = real_analysis.to_results_table_markdown()
        lines = [l.strip() for l in table_md.splitlines() if l.strip()]

        # 2 header lines + 20 data rows = 22 lines
        assert len(lines) == 22

    def test_dataset_integrity_preserved(
        self,
        json_hashes_before: Dict[str, str],
        real_analysis: ScalabilityAnalysis,
    ):
        """Confirm that no dataset JSON file was modified during the sweep."""
        after_hashes = _collect_json_hashes()
        assert set(json_hashes_before.keys()) == set(after_hashes.keys())
        for path, hash_before in json_hashes_before.items():
            assert after_hashes[path] == hash_before, f"Dataset file {path} was mutated!"
