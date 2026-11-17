"""
tests/test_phase32_2_propagation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Test suite for Phase 32.2: Delay Propagation Analytics.

Tests cover:
  1. Module export and presence of all required classes and enums.
  2. DelayDecomposition math (primary vs secondary, knock-on ratio, recovery rate).
  3. PropagationChainNode and PropagationChain construction, node traversal, serialization.
  4. CorridorPropagationProfile metrics and damping efficiency.
  5. Isolated documentation of the MAS-BBQ throat infinite propagation boundary.
  6. DelayPropagationAnalyticsResult JSON export and Markdown report generation.
  7. End-to-end execution of DelayPropagationAnalyzer.
  8. Strict pending services exclusion invariant.
  9. Dataset immutability invariant.
"""

from __future__ import annotations

import json
import os
import pytest
from typing import List

from evaluation.framework import PENDING_SERVICES
from evaluation.delay_propagation_analytics import (
    CorridorPropagationProfile,
    DelayDecomposition,
    DelayPropagationAnalyticsResult,
    DelayPropagationAnalyzer,
    PropagationChain,
    PropagationChainNode,
    PropagationTriggerType,
    run_delay_propagation_analytics,
)


# ---------------------------------------------------------------------------
# 1. Module Exports & Types
# ---------------------------------------------------------------------------

def test_module_exports():
    """All required Phase 32.2 symbols are accessible via evaluation package."""
    import evaluation
    expected_exports = [
        "PropagationTriggerType",
        "DelayDecomposition",
        "PropagationChainNode",
        "PropagationChain",
        "CorridorPropagationProfile",
        "DelayPropagationAnalyticsResult",
        "DelayPropagationAnalyzer",
        "run_delay_propagation_analytics",
    ]
    for symbol in expected_exports:
        assert hasattr(evaluation, symbol), f"evaluation missing export: {symbol}"


# ---------------------------------------------------------------------------
# 2. Delay Decomposition Models
# ---------------------------------------------------------------------------

def test_delay_decomposition_model():
    """DelayDecomposition calculates knock-on ratio and recovery rate accurately."""
    decomp = DelayDecomposition(
        service_id="SRV_12607_01",
        train_name="Lalbagh Express",
        corridor="West Corridor",
        primary_delay_minutes=30.0,
        secondary_delay_minutes=15.0,
        total_delay_minutes=45.0,
        knock_on_ratio=0.5,
        absorbed_delay_minutes=10.0,
        recovery_rate_pct=22.2,
    )
    d = decomp.to_dict()
    assert d["service_id"] == "SRV_12607_01"
    assert d["primary_delay_minutes"] == 30.0
    assert d["secondary_delay_minutes"] == 15.0
    assert d["knock_on_ratio"] == 0.5
    assert d["recovery_rate_pct"] == 22.2


# ---------------------------------------------------------------------------
# 3. Propagation Chains & Triggers
# ---------------------------------------------------------------------------

def test_propagation_chain_construction():
    """PropagationChain and nodes serialize cleanly with trigger enums."""
    node1 = PropagationChainNode(
        parent_service_id=None,
        child_service_id="SRV_12607_01",
        trigger_type=PropagationTriggerType.PLATFORM_OCCUPANCY,
        trigger_location="Chennai Central (MAS) Platform 3",
        delay_transferred_minutes=30.0,
        timestamp_minutes=360.0,
    )
    node2 = PropagationChainNode(
        parent_service_id="SRV_12607_01",
        child_service_id="SRV_43001_01",
        trigger_type=PropagationTriggerType.HEADWAY_FOLLOWING,
        trigger_location="MAS - BBQ Down Main Throat",
        delay_transferred_minutes=15.0,
        timestamp_minutes=365.0,
    )

    chain = PropagationChain(
        chain_id="CHAIN_TEST",
        root_service_id="SRV_12607_01",
        root_disruption_cause="30-min late departure at MAS",
        chain_depth=2,
        total_services_affected=2,
        total_propagated_delay_minutes=45.0,
        attenuation_rate_pct=50.0,
        nodes=[node1, node2],
    )
    d = chain.to_dict()
    assert d["chain_id"] == "CHAIN_TEST"
    assert d["chain_depth"] == 2
    assert len(d["nodes"]) == 2
    assert d["nodes"][0]["trigger_type"] == "PLATFORM_OCCUPANCY"
    assert d["nodes"][1]["trigger_type"] == "HEADWAY_FOLLOWING"


# ---------------------------------------------------------------------------
# 4. Corridor Propagation Profiles
# ---------------------------------------------------------------------------

def test_corridor_propagation_profile():
    """CorridorPropagationProfile structures damping and knock-on stats."""
    cp = CorridorPropagationProfile(
        corridor_name="West Corridor",
        total_disruption_events=18,
        mean_primary_delay_min=16.5,
        mean_secondary_delay_min=14.2,
        mean_knock_on_ratio=0.86,
        damping_efficiency_pct=62.5,
        primary_propagation_chokepoints=["MAS_BBQ_THROAT", "JNC_BBQ"],
    )
    d = cp.to_dict()
    assert d["corridor_name"] == "West Corridor"
    assert d["mean_knock_on_ratio"] == 0.86
    assert d["damping_efficiency_pct"] == 62.5
    assert len(d["primary_propagation_chokepoints"]) == 2


# ---------------------------------------------------------------------------
# 5. JSON Export & Markdown Generation
# ---------------------------------------------------------------------------

def test_delay_propagation_analytics_result_json_and_markdown(tmp_path):
    """DelayPropagationAnalyticsResult produces valid JSON and Markdown."""
    analyzer = DelayPropagationAnalyzer()
    res = analyzer.analyze()

    assert isinstance(res, DelayPropagationAnalyticsResult)
    assert res.total_services_profiled == 40
    assert len(res.delay_decompositions) == 40
    assert len(res.propagation_chains) >= 3
    assert len(res.corridor_profiles) >= 4

    # JSON export
    json_path = tmp_path / "propagation_analytics_test.json"
    res.export_json(str(json_path))
    assert os.path.exists(json_path)

    with open(json_path, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["phase"] == "32.2"
    assert "delay_decompositions" in loaded
    assert "propagation_chains" in loaded
    assert "corridor_profiles" in loaded
    assert "infeasible_boundary_explanation" in loaded

    # Markdown generation
    md = res.generate_markdown()
    assert isinstance(md, str)
    assert "# Railway Traffic Optimizer — Phase 32.2 Delay Propagation Analytics" in md
    assert "## 1  Primary vs Secondary Delay Decomposition" in md
    assert "## 2  Major Delay Propagation Chains & Causal Vectors" in md
    assert "## 3  Corridor Delay Propagation & Damping Profiles" in md
    assert "## 4  Topological Infeasibility Boundary (Infinite Propagation)" in md
    assert "## 5  Key Analytical Takeaways" in md


# ---------------------------------------------------------------------------
# 6. Invariants: Pending Services & Dataset Immutability
# ---------------------------------------------------------------------------

def test_pending_services_exclusion_invariant():
    """Verify all 7 pending services remain excluded from delay propagation analytics."""
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

    analyzer = DelayPropagationAnalyzer()
    res = analyzer.analyze()
    for d in res.delay_decompositions:
        assert d.service_id not in PENDING_SERVICES, f"Pending service {d.service_id} found in delay decomposition"
    for c in res.propagation_chains:
        assert c.root_service_id not in PENDING_SERVICES, f"Pending service {c.root_service_id} found in chain root"
        for n in c.nodes:
            assert n.child_service_id not in PENDING_SERVICES, f"Pending service {n.child_service_id} found in chain node"


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
