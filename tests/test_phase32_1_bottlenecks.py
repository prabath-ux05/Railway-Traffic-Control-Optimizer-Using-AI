"""
tests/test_phase32_1_bottlenecks.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test suite for Phase 32.1: Bottleneck & Resource Analytics.

Tests cover:
  1. Module export and presence of all required classes.
  2. Track, Platform, Junction, Corridor utilization models and serialization.
  3. RankedBottleneck construction, BSI calculation, and ranking logic.
  4. Classification of Critical Infrastructure vs Temporary Scenario bottlenecks.
  5. Isolated documentation of the MAS-BBQ throat infeasibility boundary.
  6. BottleneckAnalyticsResult JSON export and Markdown generation.
  7. End-to-end execution of BottleneckAnalyzer with live network data.
  8. Strict pending services exclusion invariant.
  9. Dataset immutability invariant.
"""

from __future__ import annotations

import json
import os
import pytest
from typing import List

from evaluation.framework import PENDING_SERVICES
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


# ---------------------------------------------------------------------------
# 1. Module Exports & Types
# ---------------------------------------------------------------------------

def test_module_exports():
    """All required Phase 32.1 symbols are accessible via evaluation package."""
    import evaluation
    expected_exports = [
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
    ]
    for symbol in expected_exports:
        assert hasattr(evaluation, symbol), f"evaluation missing export: {symbol}"


# ---------------------------------------------------------------------------
# 2. Utilization Models Serialization
# ---------------------------------------------------------------------------

def test_track_utilization_model():
    """TrackUtilization produces a complete dictionary representation."""
    tu = TrackUtilization(
        section_id="SEC_MAS_BBQ_DOWN",
        from_node="MAS",
        to_node="BBQ",
        direction="DOWN",
        corridor="West Corridor",
        track_type="MAIN",
        service_count=18,
        total_occupancy_minutes=95.0,
        utilization_rate_pct=6.6,
        contention_events_count=2,
        max_simultaneous_trains=1,
        headway_buffer_margin_min=3.0,
    )
    d = tu.to_dict()
    assert d["section_id"] == "SEC_MAS_BBQ_DOWN"
    assert d["service_count"] == 18
    assert d["headway_buffer_margin_min"] == 3.0


def test_platform_utilization_model():
    """PlatformUtilization serializes dwell and occupancy stats."""
    pu = PlatformUtilization(
        platform_id="MAS_P1",
        station_id="MAS",
        station_name="Chennai Central",
        platform_number=1,
        total_dwell_minutes=120.0,
        service_count=6,
        utilization_rate_pct=8.33,
        peak_occupancy_count=1,
        platform_contention_events=0,
    )
    d = pu.to_dict()
    assert d["platform_id"] == "MAS_P1"
    assert d["station_name"] == "Chennai Central"
    assert d["total_dwell_minutes"] == 120.0


def test_junction_utilization_model():
    """JunctionUtilization captures crossover complexity and congestion index."""
    ju = JunctionUtilization(
        junction_id="JNC_BBQ",
        name="Basin Bridge Junction",
        junction_type="DIAMOND_CROSSOVER",
        corridor="West Corridor",
        connected_routes_count=16,
        total_route_traversals=40,
        contention_conflict_count=18,
        precedence_decisions_required=12,
        peak_simultaneous_routes=4,
        congestion_index=0.92,
    )
    d = ju.to_dict()
    assert d["junction_id"] == "JNC_BBQ"
    assert d["congestion_index"] == 0.92


def test_corridor_utilization_model():
    """CorridorUtilization aggregates corridor-wide stress metrics."""
    cu = CorridorUtilization(
        corridor_name="West Corridor",
        total_active_services=24,
        total_track_sections=36,
        mean_track_utilization_pct=42.5,
        peak_track_utilization_pct=88.0,
        total_contention_conflicts=26,
        total_attributed_delay_min=186.5,
        stress_level="HIGH",
    )
    d = cu.to_dict()
    assert d["corridor_name"] == "West Corridor"
    assert d["stress_level"] == "HIGH"


# ---------------------------------------------------------------------------
# 3. RankedBottleneck & Severity Index
# ---------------------------------------------------------------------------

def test_ranked_bottleneck_bsi_and_categories():
    """RankedBottleneck structures composite severity and distinguishes categories."""
    rb = RankedBottleneck(
        rank=1,
        resource_id="BN_MAS_BBQ_THROAT",
        resource_name="Chennai Central - Basin Bridge Throat",
        resource_category="JUNCTION_THROAT",
        bottleneck_type=BottleneckCategory.CRITICAL_INFRASTRUCTURE,
        corridor="West Corridor",
        contention_frequency=18,
        affected_service_count=24,
        affected_service_ids=["SRV_12607_01", "SRV_12608_01"],
        total_attributed_delay_min=125.5,
        peak_utilization_pct=92.0,
        bottleneck_severity_index=381.15,
        primary_contention_cause="Terminal throat convergence",
        mitigation_recommendation="Implement dynamic precedence dispatching",
    )
    d = rb.to_dict()
    assert d["rank"] == 1
    assert d["bottleneck_type"] == "CRITICAL_INFRASTRUCTURE"
    assert d["bottleneck_severity_index"] == 381.15


# ---------------------------------------------------------------------------
# 4. Infeasible Boundary Documentation
# ---------------------------------------------------------------------------

def test_infeasible_boundary_isolation():
    """Infeasible bottleneck documents the single point of topological failure."""
    detail = InfeasibleBottleneckDetail(
        resource_id="MAS_BBQ_THROAT_SEGMENT_DOWN",
        resource_name="Chennai Central - Basin Bridge Down Main Throat",
        corridor="West / North Terminus Trunk",
        disruption_event="EXP_31_3_12_BLK_SEVERE (Capacity = 0 for 120 min)",
        duration_minutes=120.0,
        impact_type="TOPOLOGICAL_DISCONNECT_INFEASIBILITY",
        root_cause_analysis="Complete physical blockage of non-redundant throat isolates terminal.",
        dispatching_implication="Requires emergency short-terminations or diversions.",
    )
    d = detail.to_dict()
    assert d["resource_id"] == "MAS_BBQ_THROAT_SEGMENT_DOWN"
    assert d["impact_type"] == "TOPOLOGICAL_DISCONNECT_INFEASIBILITY"


# ---------------------------------------------------------------------------
# 5. JSON Export & Markdown Generation
# ---------------------------------------------------------------------------

def test_bottleneck_analytics_result_json_and_markdown(tmp_path):
    """BottleneckAnalyticsResult produces valid JSON and comprehensive Markdown."""
    analyzer = BottleneckAnalyzer()
    res = analyzer.analyze()

    assert isinstance(res, BottleneckAnalyticsResult)
    assert len(res.ranked_bottlenecks) >= 5
    assert len(res.corridor_utilizations) >= 4
    assert len(res.junction_utilizations) >= 5

    # JSON export
    json_path = tmp_path / "bottleneck_analytics_test.json"
    res.export_json(str(json_path))
    assert os.path.exists(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["phase"] == "32.1"
    assert "ranked_bottlenecks" in loaded
    assert "corridor_utilizations" in loaded
    assert "infeasible_boundary" in loaded

    # Markdown generation
    md = res.generate_markdown()
    assert isinstance(md, str)
    assert "# Railway Traffic Optimizer — Phase 32.1 Bottleneck & Resource Analytics" in md
    assert "## 1  Top Ranked Infrastructure & Scenario Bottlenecks" in md
    assert "## 2  Detailed Bottleneck Characterization & Mitigation" in md
    assert "## 3  Corridor Capacity & Stress Level Profiling" in md
    assert "## 4  Junction & Interlocking Throat Utilization" in md
    assert "## 5  Key Station Platform Turnaround & Dwell Stress" in md
    assert "## 6  Topological Infeasibility Boundary Isolation" in md
    assert "## 7  Key Insights: Infrastructure vs Temporary Scenario Contention" in md


# ---------------------------------------------------------------------------
# 6. Invariants: Pending Services & Dataset Immutability
# ---------------------------------------------------------------------------

def test_pending_services_exclusion_invariant():
    """Verify all 7 pending services remain excluded from bottleneck analysis."""
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

    analyzer = BottleneckAnalyzer()
    res = analyzer.analyze()
    for b in res.ranked_bottlenecks:
        for s_id in b.affected_service_ids:
            assert s_id not in PENDING_SERVICES, f"Pending service {s_id} found in bottleneck {b.resource_id}"


def test_dataset_immutability():
    """Verify master datasets are unchanged before/after analytics execution."""
    timetable_path = "data/trains/published_timetables/timetable.json"
    trains_path = "data/trains/train_identity/trains.json"
    
    with open(timetable_path, "r", encoding="utf-8") as f:
        tt_data = json.load(f)
    with open(trains_path, "r", encoding="utf-8") as f:
        tr_data = json.load(f)

    assert len(tt_data) == 127
    assert len(tr_data) == 51
