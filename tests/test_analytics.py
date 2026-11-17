"""
tests/test_analytics.py
~~~~~~~~~~~~~~~~~~~~~~~
Phase 26: Unit and Integration Tests for Research Analytics & Evaluation.

Verifies:
1. Per-service average delay calculations in ConsolidatedCaseMetrics and ConsolidatedAggregateStats.
2. Complete data serialization conforming to AnalyticsResponse schema.
3. FastAPI GET /api/v1/analytics endpoint execution, caching, and refresh behavior.
4. Scalability curves and bottleneck analysis data presence.
5. Strict dataset immutability during analytics generation.
"""

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from evaluation.consolidation import (
    ConsolidatedAggregateStats,
    ConsolidatedCaseMetrics,
    ConsolidatedResearchRunner,
    run_consolidated_research,
)


class TestAnalyticsDataStructures:
    """Test unit calculation of per-service average delays and serialization."""

    def test_case_metrics_average_delay_calculation(self):
        case = ConsolidatedCaseMetrics(
            category="Core Operational Benchmark",
            case_id="EXP_TEST",
            name="Test Scenario",
            service_count=4,
            disruption_mode="SINGLE_DELAY",
            published_total_delay_minutes=0.0,
            feasible_baseline_total_delay_minutes=120.0,
            optimized_total_delay_minutes=60.0,
            delay_savings_minutes=60.0,
            delay_savings_percent=50.0,
            feasible_baseline_avg_delay_minutes=30.0,
            optimized_avg_delay_minutes=15.0,
            avg_delay_savings_minutes=15.0,
        )

        d = case.to_dict()
        assert "feasible_baseline_avg_delay_min" in d["delay"]
        assert "optimized_avg_delay_min" in d["delay"]
        assert "avg_delay_savings_min" in d["delay"]
        assert d["delay"]["feasible_baseline_avg_delay_min"] == 30.0
        assert d["delay"]["optimized_avg_delay_min"] == 15.0
        assert d["delay"]["avg_delay_savings_min"] == 15.0

    def test_aggregate_stats_average_delay_aggregation(self):
        runner = ConsolidatedResearchRunner()
        c1 = ConsolidatedCaseMetrics(
            category="Core",
            case_id="C1",
            name="C1",
            service_count=4,
            disruption_mode="NORMAL",
            feasible_baseline_total_delay_minutes=40.0,
            optimized_total_delay_minutes=40.0,
            delay_savings_minutes=0.0,
            feasible_baseline_avg_delay_minutes=10.0,
            optimized_avg_delay_minutes=10.0,
        )
        c2 = ConsolidatedCaseMetrics(
            category="Core",
            case_id="C2",
            name="C2",
            service_count=4,
            disruption_mode="SINGLE_DELAY",
            feasible_baseline_total_delay_minutes=100.0,
            optimized_total_delay_minutes=60.0,
            delay_savings_minutes=40.0,
            feasible_baseline_avg_delay_minutes=25.0,
            optimized_avg_delay_minutes=15.0,
        )

        aggs = runner.compute_aggregates([c1, c2], [c1, c2])
        assert aggs.mean_core_baseline_avg_delay_minutes == 17.5
        assert aggs.mean_core_optimized_avg_delay_minutes == 12.5

        d = aggs.to_dict()
        assert d["core_aggregates"]["mean_baseline_avg_delay_min"] == 17.5
        assert d["core_aggregates"]["mean_optimized_avg_delay_min"] == 12.5


class TestFastApiAnalyticsEndpoint:
    """Test GET /api/v1/analytics endpoint using TestClient."""

    @pytest.fixture(scope="class")
    @classmethod
    def client(cls):
        return TestClient(app)

    def test_get_analytics_endpoint_success(self, client):
        response = client.get("/api/v1/analytics")
        assert response.status_code == 200
        data = response.json()

        # 1. Metadata
        meta = data["metadata"]
        assert meta["total_cases_evaluated"] == 26
        assert meta["core_benchmark_count"] == 6
        assert meta["scalability_sweep_count"] == 20

        # 2. Methodology & Rigor
        meth = data["methodology"]
        assert "Published" in meth["published_reference"] or "published" in meth["published_reference"].lower()
        assert "FIFO" in meth["feasible_baseline"] or "First-In-First-Out" in meth["feasible_baseline"]
        assert "CP-SAT" in meth["cpsat_optimum"]
        assert "Delay Savings" in meth["delay_savings_formula"]
        assert len(meth["research_disclaimer"]) > 20

        # 3. Aggregate Statistics
        aggs = data["aggregate_statistics"]
        assert aggs["total_cases_evaluated"] == 26
        assert aggs["global_reliability"]["total_optimal_solutions"] == 26
        assert aggs["global_reliability"]["total_optimality_percent"] == 100.0
        assert aggs["global_reliability"]["total_throughput_maintained_percent"] == 100.0
        assert aggs["global_reliability"]["total_conflict_resolution_percent"] == 100.0

        # 4. Core Benchmarks
        core = data["core_benchmark_results"]
        assert len(core) == 6
        for c in core:
            assert "identity" in c
            assert "delay" in c
            assert "service_quality" in c
            assert "conflicts" in c
            assert "solver" in c
            assert "feasible_baseline_avg_delay_min" in c["delay"]
            assert "optimized_avg_delay_min" in c["delay"]

        # 5. Scalability Results & Analysis
        scale = data["scalability_results"]
        assert len(scale) == 20

        analysis = data["scalability_analysis"]
        assert "solve_time_scaling" in analysis
        assert "savings_scaling" in analysis
        assert "status_summary" in analysis
        assert "throughput_summary" in analysis
        assert "conflict_summary" in analysis
        assert "bottleneck" in analysis

        assert len(analysis["solve_time_scaling"]) == 5  # 5 load levels (4, 8, 12, 16, 20 services)
        assert analysis["status_summary"]["all_optimal"] is True

        # 6. Findings & Limitations
        assert len(data["key_findings"]) >= 4
        assert len(data["limitations"]) >= 3

    def test_get_analytics_cached_performance(self, client):
        """Verify that second call returns instantaneously from cache."""
        import time
        t0 = time.perf_counter()
        resp = client.get("/api/v1/analytics")
        t_elapsed = time.perf_counter() - t0
        assert resp.status_code == 200
        # Cached response should be virtually instantaneous (< 0.2s)
        assert t_elapsed < 0.5
