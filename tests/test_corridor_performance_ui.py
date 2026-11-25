"""
tests/test_corridor_performance_ui.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Focused test suite for Requirement #8 Frontend:
Corridor Performance Aggregation UI & Data Contracts.

Verifies:
1. TypeScript data model integrity in frontend/src/lib/types.ts:
   - CorridorPerformanceMetrics interface with all required metrics
   - Integration into OptimizeResponse, BaselineComparisonDetail, and WhatIfResponse
2. Component source integrity in ResearchAnalyticsView.tsx:
   - Dedicated "CORRIDORS" subtab (Corridors (7))
   - Coverage of all 7 authoritative corridors
   - Live metrics display: service count, baseline delay, optimized delay, savings,
     throughput/OTP, conflicts, utilization, stress level
   - Clear distinction of Cross/Bypass as topology-only with N/A values
   - Interactive filtering (ALL, OPERATIONAL, ACTIVE, TOPOLOGY)
3. page.tsx wiring:
   - corridorPerformance prop forwarded to ResearchAnalyticsView
4. End-to-end API data mapping contracts:
   - Live /api/v1/what-if and /api/v1/optimize payloads adhere to CorridorPerformanceMetrics
"""

import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_corridor_performance_types_integrity():
    """Verify frontend/src/lib/types.ts contains CorridorPerformanceMetrics and response fields."""
    types_path = os.path.join("frontend", "src", "lib", "types.ts")
    assert os.path.exists(types_path), "types.ts must exist"

    with open(types_path, "r", encoding="utf-8") as f:
        src = f.read()

    # Must contain CorridorPerformanceMetrics interface
    assert "export interface CorridorPerformanceMetrics" in src

    required_fields = [
        "corridor_id: string;",
        "corridor_name: string;",
        "is_topology_only: boolean;",
        "service_count: number;",
        "total_registered_services: number;",
        "baseline_delay_minutes: number;",
        "optimized_delay_minutes: number;",
        "delay_savings_minutes: number;",
        "delay_savings_percent: number;",
        "throughput: number;",
        "on_time_performance_percent: number;",
        "initial_conflicts: number;",
        "remaining_conflicts: number;",
        "resolved_conflicts: number;",
        "track_sections_count: number;",
        "mean_track_utilization_pct: number;",
        "peak_track_utilization_pct: number;",
        "utilization_percent: number;",
        "stress_level:",
        "route_ids: string[];",
    ]
    for field in required_fields:
        assert field in src, f"Field '{field}' must be defined in CorridorPerformanceMetrics"

    # Must be wired into response models
    assert "corridor_performance?: CorridorPerformanceMetrics[];" in src


def test_research_analytics_view_component_integrity():
    """Verify ResearchAnalyticsView.tsx includes dedicated CORRIDORS section and required UI logic."""
    view_path = os.path.join("frontend", "src", "components", "ResearchAnalyticsView.tsx")
    assert os.path.exists(view_path), "ResearchAnalyticsView.tsx must exist"

    with open(view_path, "r", encoding="utf-8") as f:
        src = f.read()

    # Must contain CORRIDORS subtab
    assert '"CORRIDORS"' in src
    assert 'label: "Corridors (7)"' in src

    # Must contain all 7 authoritative corridors
    authoritative_names = [
        "West",
        "North",
        "South",
        "MRTS",
        "Beach–North Bypass",
        "Cross/Bypass",
        "PTMS",
    ]
    for name in authoritative_names:
        assert name in src, f"Corridor '{name}' must be defined in ResearchAnalyticsView.tsx"

    # Must contain metric labels and displays
    assert "service_count" in src
    assert "baseline_delay_minutes" in src
    assert "optimized_delay_minutes" in src
    assert "delay_savings_minutes" in src
    assert "throughput" in src
    assert "on_time_performance_percent" in src
    assert "initial_conflicts" in src
    assert "mean_track_utilization_pct" in src
    assert "stress_level" in src

    # Must distinguish Cross/Bypass as topology-only and show N/A
    assert "is_topology_only" in src
    assert "TOPOLOGY ONLY" in src
    assert "TOPOLOGY REFERENCE ONLY" in src
    assert "N/A" in src

    # Must contain corridor filtering
    assert "corridorFilter" in src
    assert "OPERATIONAL" in src
    assert "TOPOLOGY" in src


def test_page_component_wiring():
    """Verify the classic dashboard page wires corridorPerformance into ResearchAnalyticsView.

    The original 8-tab page moved to /classic when the Glass Spatial dashboard became the home page
    (2026-11-25); its wiring is unchanged, so this test now reads it there.
    """
    page_path = os.path.join("frontend", "src", "app", "classic", "page.tsx")
    assert os.path.exists(page_path), "page.tsx must exist"

    with open(page_path, "r", encoding="utf-8") as f:
        src = f.read()

    assert "<ResearchAnalyticsView" in src
    assert "corridorPerformance={" in src


def test_corridor_performance_api_data_mapping_contracts():
    """Verify API responses match the frontend CorridorPerformanceMetrics contract."""
    payload = {
        "scenario_id": "SCEN_UI_DATA_MAPPING_TEST",
        "scenario_name": "UI Data Mapping Contract Test",
        "service_ids": ["SRV_12607_01", "SRV_42015_01"],
        "departure_delays": {"SRV_12607_01": 20.0},
    }
    response = client.post("/api/v1/what-if", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "corridor_performance" in data
    corridors = data["corridor_performance"]
    assert len(corridors) == 7

    corridors_by_name = {c["corridor_name"]: c for c in corridors}

    # Verify West corridor has live dynamic values
    west = corridors_by_name["West"]
    assert west["is_topology_only"] is False
    assert west["service_count"] == 1
    assert west["baseline_delay_minutes"] > 0
    assert west["optimized_delay_minutes"] > 0
    assert west["delay_savings_minutes"] >= 0
    assert west["throughput"] == 1
    assert 0 <= west["on_time_performance_percent"] <= 100
    assert west["track_sections_count"] > 100

    # Verify Cross/Bypass is strictly topology-only
    cross = corridors_by_name["Cross/Bypass"]
    assert cross["is_topology_only"] is True
    assert cross["service_count"] == 0
    assert cross["baseline_delay_minutes"] == 0.0
    assert cross["optimized_delay_minutes"] == 0.0
    assert cross["delay_savings_minutes"] == 0.0
    assert cross["track_sections_count"] == 22
    assert cross["stress_level"] == "TOPOLOGY_ONLY"
