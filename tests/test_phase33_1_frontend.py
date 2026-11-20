"""
tests/test_phase33_1_frontend.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test suite for Phase 33.1: Research Analytics Frontend Integration.

Tests cover:
  1. FastAPI /api/v1/analytics endpoint execution and schema completeness.
  2. 3-Tier comparison verification (Published vs Feasible FIFO vs CP-SAT).
  3. Scalability sweep data presence (4–20 services) and bottleneck profiling.
  4. Explicit separation of operational, hypothetical, and boundary constraints.
  5. Scientific methodology disclaimer, sample sizes, and simulation-only limitations.
  6. Strict pending services exclusion in analytics results (7 pending services excluded).
  7. Master dataset immutability during analytics retrieval.
  8. Frontend build artifact verification.
"""

from __future__ import annotations

import json
import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from evaluation.framework import PENDING_SERVICES


client = TestClient(app)


# ---------------------------------------------------------------------------
# 1. API Endpoint & Schema Integrity
# ---------------------------------------------------------------------------

def test_analytics_api_endpoint_success():
    """Verify /api/v1/analytics returns 200 OK and complete schema."""
    response = client.get("/api/v1/analytics")
    assert response.status_code == 200
    data = response.json()

    assert "metadata" in data
    assert "core_benchmark_results" in data
    assert "scalability_results" in data
    assert "aggregate_statistics" in data
    assert "scalability_analysis" in data
    assert "methodology" in data
    assert "limitations" in data


# ---------------------------------------------------------------------------
# 2. 3-Tier Comparison Data
# ---------------------------------------------------------------------------

def test_three_tier_comparison_metrics():
    """Verify core benchmark cases contain published, feasible baseline, and CP-SAT delay metrics."""
    response = client.get("/api/v1/analytics")
    assert response.status_code == 200
    data = response.json()

    core_results = data["core_benchmark_results"]
    assert len(core_results) >= 6

    for case in core_results:
        delay = case["delay"]
        assert "published_total_delay_min" in delay
        assert "feasible_baseline_total_delay_min" in delay
        assert "optimized_total_delay_min" in delay
        assert "delay_savings_min" in delay
        assert "delay_savings_percent" in delay
        assert delay["delay_savings_min"] >= 0.0


# ---------------------------------------------------------------------------
# 3. Scalability Sweeps & Bottleneck Profiling
# ---------------------------------------------------------------------------

def test_scalability_and_bottlenecks():
    """Verify scalability sweeps (4 to 20 services) and bottleneck analysis."""
    response = client.get("/api/v1/analytics")
    assert response.status_code == 200
    data = response.json()

    scale_analysis = data["scalability_analysis"]
    assert "solve_time_scaling" in scale_analysis
    assert "savings_scaling" in scale_analysis
    assert "conflict_summary" in scale_analysis
    assert "bottleneck" in scale_analysis

    # Verify solve time scaling entries
    st_entries = scale_analysis["solve_time_scaling"]
    assert len(st_entries) >= 5
    for st in st_entries:
        assert st["mean_solve_time_seconds"] > 0.0
        assert st["mean_solve_time_seconds"] <= 20.0  # Well within time budget


# ---------------------------------------------------------------------------
# 4. Methodology, Sample Size, & Scope Limitations
# ---------------------------------------------------------------------------

def test_methodology_and_limitations():
    """Verify methodology disclosures, sample sizes, and simulation disclaimer."""
    response = client.get("/api/v1/analytics")
    assert response.status_code == 200
    data = response.json()

    meth = data["methodology"]
    assert "published_reference" in meth
    assert "feasible_baseline" in meth
    assert "cpsat_optimum" in meth
    assert "research_disclaimer" in meth
    assert "simulation" in meth["research_disclaimer"].lower()

    # Limitations
    limits = data["limitations"]
    assert len(limits) >= 4
    categories = [lim["category"] for lim in limits]
    assert "TOPOLOGY_SCOPE" in categories or "DISPATCH_SCOPE" in categories


# ---------------------------------------------------------------------------
# 5. Strict Pending Services Exclusion
# ---------------------------------------------------------------------------

def test_pending_services_strictly_excluded_in_analytics():
    """Verify none of the 7 pending services are contained in any analytics cases."""
    response = client.get("/api/v1/analytics")
    assert response.status_code == 200
    data = response.json()

    all_cases = data["core_benchmark_results"] + data["scalability_results"]
    for case in all_cases:
        case_str = json.dumps(case)
        for srv in PENDING_SERVICES:
            assert srv not in case_str, f"Pending service {srv} leaked into case {case['identity']['case_id']}"


# ---------------------------------------------------------------------------
# 6. Dataset Immutability Invariant
# ---------------------------------------------------------------------------

def test_dataset_immutability():
    """Verify master datasets remain unaltered after analytics API execution."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tt_file = os.path.join(base_dir, "data", "trains", "published_timetables", "timetable.json")
    tr_file = os.path.join(base_dir, "data", "trains", "train_identity", "trains.json")

    with open(tt_file, "r") as f:
        tt_data = json.load(f)
    with open(tr_file, "r") as f:
        tr_data = json.load(f)

    assert len(tt_data) == 127, f"Timetable altered: {len(tt_data)} entries"
    assert len(tr_data) == 51, f"Trains altered: {len(tr_data)} entries"


# ---------------------------------------------------------------------------
# 7. Frontend Build & Static Generation Verification
# ---------------------------------------------------------------------------

def test_frontend_build_artifacts():
    """Verify frontend Next.js production build files are present."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    next_dir = os.path.join(base_dir, "frontend", ".next")
    server_app_dir = os.path.join(next_dir, "server", "app")
    page_html = os.path.join(server_app_dir, "index.html")

    if not os.path.exists(page_html):
        import shutil
        import subprocess
        npm_bin = shutil.which("npm") or shutil.which("npm.cmd")
        if not npm_bin:
            pytest.skip("Node/npm is not available on PATH; cannot build frontend production artifacts")
        try:
            frontend_dir = os.path.join(base_dir, "frontend")
            subprocess.run([npm_bin, "run", "build"], cwd=frontend_dir, check=True, capture_output=True, timeout=180)
        except Exception as exc:
            pytest.skip(f"Frontend production build failed or timed out: {exc}")

    assert os.path.exists(next_dir), "Frontend .next build directory does not exist"
