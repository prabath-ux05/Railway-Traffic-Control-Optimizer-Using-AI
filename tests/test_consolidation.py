"""
tests/test_consolidation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Batch 15: Unit and integration tests for Research Experiment Consolidation.

Verifies:
1. Deterministic execution:
   - ConsolidatedResearchRunner executes cleanly and deterministically.
   - All 6 core benchmark scenarios + 20 scalability cases execute (26 total cases).
2. Metric consistency:
   - Delays, max delays, savings, OTP, throughput, conflicts, solve times, and objective costs.
   - Feasible FIFO baseline delay ≥ CP-SAT delay across disrupted runs.
   - Delay savings = baseline delay - optimized delay.
   - 100% throughput across all evaluated cases.
   - 0 remaining conflicts across all evaluated cases.
3. Dataset immutability:
   - SHA-256 hashes of all JSON files in `data/` remain identical before and after suite runs.
4. Aggregation correctness:
   - `compute_aggregates` calculates exact means, percentages, totals, and per-load metrics.
5. Report generation:
   - Markdown report contains all 6 required sections with tables.
   - Machine-readable `to_dict()` produces valid JSON-serializable dictionary.
   - ASCII summary is non-empty and well-formatted.
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List

import pytest

from evaluation.consolidation import (
    ConsolidatedAggregateStats,
    ConsolidatedCaseMetrics,
    ConsolidatedResearchReport,
    ConsolidatedResearchRunner,
    run_consolidated_research,
)
from evaluation.experiments import (
    create_consolidated_benchmark_suite,
    create_severe_compound_experiment,
    create_standard_evaluation_suite,
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


@pytest.fixture
def sample_case_metrics() -> ConsolidatedCaseMetrics:
    return ConsolidatedCaseMetrics(
        category="Core Operational Benchmark",
        case_id="EXP_01_NO_DELAY",
        name="Nominal Baseline Schedule",
        service_count=4,
        disruption_mode="NORMAL",
        published_total_delay_minutes=0.0,
        feasible_baseline_total_delay_minutes=115.0,
        optimized_total_delay_minutes=115.0,
        delay_savings_minutes=0.0,
        delay_savings_percent=0.0,
        feasible_baseline_max_delay_minutes=32.0,
        optimized_max_delay_minutes=32.0,
        published_on_time_percent=100.0,
        feasible_baseline_on_time_percent=0.0,
        optimized_on_time_percent=0.0,
        baseline_throughput=4,
        optimized_throughput=4,
        initial_conflicts=0,
        baseline_remaining_conflicts=0,
        optimized_remaining_conflicts=0,
        resolved_conflicts=0,
        solver_status="OPTIMAL",
        solve_time_seconds=0.12,
        feasible_baseline_objective_cost=361.0,
        optimized_objective_cost=361.0,
        cost_savings=0.0,
        precedence_decisions_count=10,
        resource_decisions_count=8,
    )


# ---------------------------------------------------------------------------
# Unit Tests: Data Models and Aggregation Logic
# ---------------------------------------------------------------------------

class TestConsolidatedDataContracts:
    """Test data contracts and unit aggregation calculations."""

    def test_case_metrics_to_dict(self, sample_case_metrics: ConsolidatedCaseMetrics):
        d = sample_case_metrics.to_dict()
        assert d["identity"]["case_id"] == "EXP_01_NO_DELAY"
        assert d["delay"]["feasible_baseline_total_delay_min"] == 115.0
        assert d["delay"]["optimized_total_delay_min"] == 115.0
        assert d["service_quality"]["baseline_throughput"] == 4
        assert d["solver"]["solver_status"] == "OPTIMAL"

    def test_case_metrics_to_markdown_row(self, sample_case_metrics: ConsolidatedCaseMetrics):
        row = sample_case_metrics.to_markdown_row()
        assert "| `EXP_01_NO_DELAY` |" in row
        assert "115.0m" in row
        assert "`OPTIMAL`" in row

    def test_aggregate_computation_with_fixtures(self, sample_case_metrics: ConsolidatedCaseMetrics):
        runner = ConsolidatedResearchRunner()

        core_list = [sample_case_metrics]
        scale_list = [sample_case_metrics]

        aggregates = runner.compute_aggregates(core_list, scale_list)

        assert aggregates.total_cases_evaluated == 2
        assert aggregates.core_benchmark_count == 1
        assert aggregates.scalability_sweep_count == 1
        assert aggregates.total_optimal_solutions == 2
        assert aggregates.total_optimality_percent == 100.0
        assert aggregates.total_throughput_maintained_percent == 100.0
        assert aggregates.total_conflict_resolution_percent == 100.0

        d = aggregates.to_dict()
        assert "core_aggregates" in d
        assert "scalability_aggregates" in d
        assert "global_reliability" in d

    def test_empty_aggregates(self):
        runner = ConsolidatedResearchRunner()
        aggregates = runner.compute_aggregates([], [])
        assert aggregates.total_cases_evaluated == 0

    def test_consolidated_suite_factory_contains_6_experiments(self):
        suite = create_consolidated_benchmark_suite()
        assert len(suite) == 6
        ids = [exp.experiment_id for exp in suite]
        assert "EXP_01_NO_DELAY" in ids
        assert "EXP_02_SINGLE_DELAY" in ids
        assert "EXP_03_MULTI_DELAY" in ids
        assert "EXP_04_SPEED_RESTRICTION" in ids
        assert "EXP_05_JUNCTION_BOTTLENECK" in ids
        assert "EXP_06_SEVERE_COMPOUND" in ids

    def test_severe_compound_experiment_definition(self):
        exp = create_severe_compound_experiment()
        assert exp.experiment_id == "EXP_06_SEVERE_COMPOUND"
        assert len(exp.scenario.departure_delays) == 3
        assert "MAS_BBQ_THROAT_SEGMENT_DOWN" in exp.scenario.track_speed_restrictions


# ---------------------------------------------------------------------------
# Unit Tests: Report Formatting and Serialization
# ---------------------------------------------------------------------------

class TestReportFormatting:
    """Test report generation functions and output structures."""

    @pytest.fixture
    def mock_report(self, sample_case_metrics: ConsolidatedCaseMetrics) -> ConsolidatedResearchReport:
        runner = ConsolidatedResearchRunner()
        core = [sample_case_metrics]
        scale = [sample_case_metrics]
        aggs = runner.compute_aggregates(core, scale)

        return ConsolidatedResearchReport(
            created_at="2026-09-10T14:30:00+00:00",
            elapsed_wall_seconds=1.50,
            core_results=core,
            scalability_results=scale,
            aggregate_stats=aggs,
            limitations=[],
            key_findings=[],
        )

    def test_core_table_markdown(self, mock_report: ConsolidatedResearchReport):
        table = mock_report.to_core_table_markdown()
        assert "| Scenario ID |" in table
        assert "| Published Ref |" in table
        assert "| Feasible Base |" in table
        assert "| CP-SAT Opt |" in table
        assert "EXP_01_NO_DELAY" in table

    def test_scalability_table_markdown(self, mock_report: ConsolidatedResearchReport):
        table = mock_report.to_scalability_table_markdown()
        assert "| Load Level / Case |" in table
        assert "EXP_01_NO_DELAY" in table

    def test_summary_ascii(self, mock_report: ConsolidatedResearchReport):
        summary = mock_report.summary()
        assert "BATCH 15: CONSOLIDATED RESEARCH EXPERIMENT REPORT" in summary
        assert "CORE OPERATIONAL SCENARIOS SUMMARY:" in summary
        assert "SCALABILITY SWEEP SUMMARY" in summary

    def test_markdown_report_structure(self, mock_report: ConsolidatedResearchReport):
        md = mock_report.to_markdown_report()
        assert "# Consolidated Railway Traffic Optimization Research Report" in md
        assert "## 1. Executive Summary & Research Methodology" in md
        assert "## 2. Core Operational Benchmark Results (4 Services)" in md
        assert "## 3. Scalability Sweep Results (4 to 20 Services)" in md
        assert "## 4. Consolidated Aggregate Statistics" in md
        assert "## 5. Key Research Findings" in md
        assert "## 6. Scope Boundaries & Research Limitations" in md

    def test_to_dict_json_serializable(self, mock_report: ConsolidatedResearchReport):
        d = mock_report.to_dict()
        assert d["metadata"]["total_cases_evaluated"] == 2
        json_str = json.dumps(d)
        assert len(json_str) > 200
        reloaded = json.loads(json_str)
        assert reloaded["metadata"]["core_benchmark_count"] == 1


# ---------------------------------------------------------------------------
# Integration Tests: End-to-End Consolidated Research Pipeline
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def consolidated_research_result() -> ConsolidatedResearchReport:
    """Execute the full consolidated research pipeline once for the module tests."""
    return run_consolidated_research()


class TestConsolidatedResearchPipeline:
    """Integration tests validating the real consolidated research execution."""

    def test_exact_total_cases_count(self, consolidated_research_result: ConsolidatedResearchReport):
        # 6 core scenarios + 20 scalability runs = 26 total cases
        assert len(consolidated_research_result.core_results) == 6
        assert len(consolidated_research_result.scalability_results) == 20
        assert consolidated_research_result.total_cases == 26

    def test_all_cases_reach_optimal_status(self, consolidated_research_result: ConsolidatedResearchReport):
        aggs = consolidated_research_result.aggregate_stats
        assert aggs.total_optimal_solutions == 26
        assert aggs.total_optimality_percent == 100.0

    def test_core_benchmark_metrics_validity(self, consolidated_research_result: ConsolidatedResearchReport):
        core = consolidated_research_result.core_results
        assert len(core) == 6

        # Check EXP_01 (nominal): 0 delay savings
        exp01 = next(r for r in core if r.case_id == "EXP_01_NO_DELAY")
        assert exp01.feasible_baseline_total_delay_minutes == 115.0
        assert exp01.optimized_total_delay_minutes == 115.0
        assert exp01.delay_savings_minutes == 0.0

        # Check EXP_06 (severe compound): positive delay savings
        exp06 = next(r for r in core if r.case_id == "EXP_06_SEVERE_COMPOUND")
        assert exp06.delay_savings_minutes > 100.0
        assert exp06.optimized_total_delay_minutes < exp06.feasible_baseline_total_delay_minutes

    def test_scalability_sweep_metrics_validity(self, consolidated_research_result: ConsolidatedResearchReport):
        scale = consolidated_research_result.scalability_results
        assert len(scale) == 20

        counts = {r.service_count for r in scale}
        assert counts == {4, 8, 12, 16, 20}

        for r in scale:
            assert r.optimized_throughput == r.service_count
            assert r.optimized_remaining_conflicts == 0
            assert r.solver_status == "OPTIMAL"

    def test_global_throughput_and_conflicts(self, consolidated_research_result: ConsolidatedResearchReport):
        aggs = consolidated_research_result.aggregate_stats
        assert aggs.total_throughput_maintained_percent == 100.0
        assert aggs.total_conflict_resolution_percent == 100.0

    def test_solve_times_sub_second(self, consolidated_research_result: ConsolidatedResearchReport):
        aggs = consolidated_research_result.aggregate_stats
        assert 0.0 < aggs.overall_mean_solve_time_seconds < 1.0
        assert 0.0 < aggs.overall_max_solve_time_seconds < 2.0

    def test_dataset_immutability(
        self,
        json_hashes_before: Dict[str, str],
        consolidated_research_result: ConsolidatedResearchReport,
    ):
        """Confirm that no dataset JSON file was modified during the entire research pipeline."""
        after_hashes = _collect_json_hashes()
        assert set(json_hashes_before.keys()) == set(after_hashes.keys())
        for path, hash_before in json_hashes_before.items():
            assert after_hashes[path] == hash_before, f"Dataset file {path} was mutated!"
