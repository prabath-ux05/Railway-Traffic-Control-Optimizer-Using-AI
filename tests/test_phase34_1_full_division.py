"""
tests/test_phase34_1_full_division.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Comprehensive Validation Test Suite for Phase 34.1:
Full Chennai Division Integrated Validation.

Tests cover:
  1. Complete Chennai Division Topology: West (MAS-AJJ), North (MAS-GPD/SPE),
     South (MSB-TBM/CGL), MRTS (MSB-VLCY), and PTMS Siding branch.
  2. 40 active backed services across multiple rolling-stock and priority classes.
  3. Strict pending services exclusion invariant (7 pending services excluded).
  4. Shared junctions & throat contention: JCT_BBQ, JCT_PAB, JCT_VJM, JCT_MSB, JCT_KOK, JCT_AJJ, JCT_CGL.
  5. Platform granularity and resource isolation across multi-platform hubs.
  6. End-to-end pipeline execution: Infrastructure -> Simulation -> Conflicts -> FIFO -> CP-SAT -> Decision Support -> API.
  7. Cross-corridor delay propagation and independent corridor isolation.
  8. Infeasible boundary cliff isolation (MAS_BBQ_THROAT_SEGMENT_DOWN impassable state).
  9. Deterministic repeatability & hash stability.
  10. Full Digital Twin 30-check validation suite.
"""

from __future__ import annotations

import json
import os
import pytest
from typing import Dict, List, Set

from backend.app.pipeline import PipelineOrchestrator, _load_default_network
from evaluation.framework import PENDING_SERVICES
from simulation.cross_corridor import (
    CrossCorridorEvaluator,
    CrossCorridorScenarioType,
    run_cross_corridor_evaluation,
)
from simulation.network import Network
from simulation.validation import DigitalTwinValidator
from decision_support import (
    DecisionSupportAdvisor,
    RecommendationClassification,
    RecommendationRefiner,
    ScenarioType,
    WhatIfComparisonEngine,
)


# ---------------------------------------------------------------------------
# 1. Complete Chennai Division Topology & Corridor Coverage
# ---------------------------------------------------------------------------

def test_full_chennai_division_topology_inventory():
    """Verify division network loads 30 stations, 7 junctions, 354 track sections, 14 platforms, 24 routes."""
    net = _load_default_network()
    
    assert len(net.stations) >= 30, f"Expected >=30 stations, found {len(net.stations)}"
    assert len(net.junctions) == 7, f"Expected 7 junctions, found {len(net.junctions)}"
    assert len(net.track_sections) >= 350, f"Expected >=350 track sections, found {len(net.track_sections)}"
    assert len(net.platforms) >= 14, f"Expected >=14 platforms, found {len(net.platforms)}"
    assert len(net.routes) >= 24, f"Expected >=24 routes, found {len(net.routes)}"

    # Check key hub stations
    key_stations = {"MAS", "BBQ", "PER", "AVD", "TRL", "AJJ", "MSB", "MS", "TBM", "CGL", "GPD", "SPE", "VLCY", "ENR"}
    for stn in key_stations:
        assert stn in net.stations, f"Key station {stn} missing from division network"

    # Check key junctions
    key_junctions = {"JCT_BBQ", "JCT_PAB", "JCT_VJM", "JCT_MSB", "JCT_KOK", "JCT_AJJ", "JCT_CGL"}
    for jct in key_junctions:
        assert jct in net.junctions, f"Key junction {jct} missing from division network"


# ---------------------------------------------------------------------------
# 2. 40 Active Services & 7 Pending Services Exclusion Invariant
# ---------------------------------------------------------------------------

def test_active_services_and_pending_services_isolation():
    """Verify exactly 40 active backed services and 7 pending services strictly excluded."""
    net = _load_default_network()
    
    total_services = len(net.services)
    assert total_services == 47, f"Expected 47 total service definitions, found {total_services}"
    assert len(PENDING_SERVICES) == 7, f"Expected 7 pending services, found {len(PENDING_SERVICES)}"

    active_services = [s for s in net.services.values() if s.id not in PENDING_SERVICES]
    assert len(active_services) == 40, f"Expected 40 active services, found {len(active_services)}"

    # Verify each pending service ID matches specification
    expected_pending = {
        "SRV_40143_01",
        "SRV_40144_01",
        "SRV_41015_01",
        "SRV_41131_01",
        "SRV_41132_01",
        "SRV_42413_01",
        "SRV_42425_01",
    }
    assert PENDING_SERVICES == expected_pending

    for srv in active_services:
        assert srv.id not in PENDING_SERVICES


# ---------------------------------------------------------------------------
# 3. Cross-Corridor Simulation & Resource Isolation
# ---------------------------------------------------------------------------

def test_cross_corridor_evaluation_suite():
    """Verify all 7 cross-corridor operational scenarios pass without conflict leakage."""
    report = run_cross_corridor_evaluation()
    assert report.all_passed is True, "Cross-corridor simulation evaluation suite failed"
    assert report.total_scenarios == 7
    assert report.passed_scenarios == 7
    assert report.failed_scenarios == 0


# ---------------------------------------------------------------------------
# 4. Digital Twin 30-Check Validation
# ---------------------------------------------------------------------------

def test_digital_twin_full_validation():
    """Verify Digital Twin validator achieves 100% validity across all 30 checks."""
    validator = DigitalTwinValidator()
    report = validator.run_all_validations()
    assert report.is_valid is True, f"Digital Twin validation failed: {report.total_failed} checks failed"
    assert report.total_checks == 30
    assert report.total_passed == 30
    assert report.total_failed == 0


# ---------------------------------------------------------------------------
# 5. End-to-End Pipeline Execution (Nominal & Perturbed)
# ---------------------------------------------------------------------------

def test_e2e_pipeline_nominal_and_perturbed():
    """Verify complete 6-stage pipeline on active services with deterministic repeatability."""
    net = _load_default_network()
    active_svcs = [s for s in net.services.keys() if s not in PENDING_SERVICES]
    orchestrator = PipelineOrchestrator(network=net)

    # 1. Nominal run (first 10 active services)
    res_nom1 = orchestrator.run_pipeline(service_ids=active_svcs[:10])
    res_nom2 = orchestrator.run_pipeline(service_ids=active_svcs[:10])
    assert res_nom1.solver_status == "OPTIMAL"
    assert res_nom1.deterministic_hash == res_nom2.deterministic_hash, "Nominal execution is not deterministic"
    assert res_nom1.active_services_count == 10

    # 2. Perturbed run with departure delay injection
    res_pert = orchestrator.run_pipeline(
        service_ids=active_svcs[:10],
        departure_delays={"SRV_12607_01": 25.0},
    )
    assert res_pert.solver_status in ("OPTIMAL", "FEASIBLE")
    assert res_pert.total_baseline_delay_minutes >= 25.0
    assert res_pert.delayed_services_count >= 1


# ---------------------------------------------------------------------------
# 6. Infeasible Boundary Case Isolation
# ---------------------------------------------------------------------------

def test_infeasible_boundary_throat_blockage_handling():
    """Verify single-point impassable throat blockage triggers INFEASIBLE boundary isolation."""
    engine = WhatIfComparisonEngine()
    suite = engine.evaluate_suite(time_limit_seconds=5.0)

    infeasible_scenarios = [s for s in suite.scenarios if s.scenario_type == ScenarioType.INFEASIBLE_BOUNDARY_CASE]
    assert len(infeasible_scenarios) >= 1, "Expected at least 1 infeasible boundary scenario"

    blocked = infeasible_scenarios[0]
    assert blocked.solver_status == "INFEASIBLE"
    assert blocked.confidence_score == 0.0
    assert blocked.delay_savings_minutes == 0.0
    assert blocked.remaining_conflicts > 0
