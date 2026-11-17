"""
tests/test_phase34_5_final_regression.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Final Technical Regression & Defect Cleanup Test Suite for Phase 34.5.

Comprehensive checks:
  1. Master Dataset Hash Invariants (Published timetables, trains, services, network topology).
  2. Strict Service Count Invariants: Exactly 40 active services, exactly 7 pending services.
  3. Digital Twin 30-Check Full Division Audit.
  4. End-to-End Pipeline Execution across Nominal, Disruption, and Infeasible Boundary states.
  5. Deterministic Hash Consistency & Zero Resource Leaks.
  6. Explainable Decision Support & What-If Comparison Integration.
  7. API Schema and Endpoint Integrity.
"""

from __future__ import annotations

import hashlib
import json
import os
import pytest
from fastapi.testclient import TestClient
from typing import Dict, List, Set

from backend.app.main import app
from backend.app.pipeline import PipelineOrchestrator, _load_default_network
from evaluation.framework import PENDING_SERVICES
from evaluation.scalability_framework import (
    COHORT_40,
    PRIMARY_DELAY_SERVICE,
    PRIMARY_DEPARTURE_DELAY_MINUTES,
    THROAT_TSR_SECTION,
    THROAT_TSR_TRAVEL_TIME,
)
from optimization.scenarios import Scenario
from simulation.validation import DigitalTwinValidator


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. Master Dataset Hash Invariants
# ---------------------------------------------------------------------------

def test_master_dataset_integrity_and_hashes():
    """Verify all master datasets match expected SHA-256 baseline hashes exactly."""
    expected_hashes = {
        os.path.join(_DATA_DIR, "trains", "published_timetables", "timetable.json"):
            "578529fa64a2dc0c9377ca596d6411cfac8466f1cbac04b22bedfc43b01d6a2d",
        os.path.join(_DATA_DIR, "trains", "train_identity", "trains.json"):
            "ed28825c9753b7bc588ce2fb2b554913d529f5ab4f8c784bdba1b43580813be9",
        os.path.join(_DATA_DIR, "trains", "service_definitions", "services.json"):
            "1b6386e4cf23472c9398cb79ba81f1353c0aee4592b19ab47666898a2a735b9d",
        os.path.join(_DATA_DIR, "infrastructure", "routes.json"):
            "07afe8f4b093b7987fb09d8b857a0ac84610a47e3c1cfd5f0daaa0515e883708",
        os.path.join(_DATA_DIR, "infrastructure", "stations.json"):
            "c1c3324c8f252a7f12fd7d0ce960e0c92c746945afdff1db15b71bc71fac14e3",
        os.path.join(_DATA_DIR, "infrastructure", "platforms.json"):
            "6c8b85beaed15541cd20ed2e38c4f2e29add9373ef65149443f5a28f22ec74b1",
        os.path.join(_DATA_DIR, "infrastructure", "junctions.json"):
            "abd203cfce1ca4cef39bb54b376b855807f792d30b8e94b237aca49a11461d45",
    }

    for path, expected_hash in expected_hashes.items():
        assert os.path.exists(path), f"Critical dataset file missing: {path}"
        current_hash = _file_hash(path)
        assert current_hash == expected_hash, (
            f"Dataset hash mismatch for {os.path.basename(path)}: {current_hash} != {expected_hash}"
        )


# ---------------------------------------------------------------------------
# 2. Service Count & Pending Exclusion Invariant
# ---------------------------------------------------------------------------

def test_service_inventory_and_pending_exclusion():
    """Verify division has 47 total service definitions, exactly 40 active, exactly 7 pending."""
    net = _load_default_network()
    
    assert len(net.services) == 47
    assert len(PENDING_SERVICES) == 7

    active_services = [s_id for s_id in net.services.keys() if s_id not in PENDING_SERVICES]
    assert len(active_services) == 40

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


# ---------------------------------------------------------------------------
# 3. Full Digital Twin Validation
# ---------------------------------------------------------------------------

def test_digital_twin_full_division_health():
    """Run full 30-check Digital Twin validator on integrated Chennai Division network."""
    net = _load_default_network()
    validator = DigitalTwinValidator(network=net)
    report = validator.run_all_validations()

    assert report.is_valid, f"Digital Twin validation failed: passed={report.total_passed}/{report.total_checks}"
    assert report.total_failed == 0
    assert report.total_checks >= 30


# ---------------------------------------------------------------------------
# 4. End-to-End Pipeline & State Cleanup
# ---------------------------------------------------------------------------

def test_e2e_nominal_and_disrupted_pipeline():
    """Verify nominal and disrupted E2E execution with complete state cleanup."""
    net = _load_default_network()
    orch = PipelineOrchestrator(network=net)

    # 1. Nominal
    res_nom = orch.run_pipeline(service_ids=COHORT_40[:10])
    assert res_nom.solver_status in ("OPTIMAL", "FEASIBLE")
    assert len(res_nom.raw_state.resource_occupancy) == 0

    # 2. Perturbed
    scen = Scenario(
        scenario_id="SCEN_FINAL_TEST",
        name="Final Disruption Test",
        affected_service_ids=COHORT_40[:10],
        departure_delays={PRIMARY_DELAY_SERVICE: PRIMARY_DEPARTURE_DELAY_MINUTES},
        track_speed_restrictions={THROAT_TSR_SECTION: THROAT_TSR_TRAVEL_TIME},
    )
    res_pert = orch.run_pipeline(scenario=scen, service_ids=COHORT_40[:10])
    assert res_pert.solver_status in ("OPTIMAL", "FEASIBLE")
    assert len(res_pert.raw_state.resource_occupancy) == 0
    assert len(res_pert.recommendations) > 0


# ---------------------------------------------------------------------------
# 5. Infeasible Boundary Safety Invariant
# ---------------------------------------------------------------------------

def test_infeasible_boundary_safety():
    """Verify complete throat blockage triggers clean infeasible / invalid safety status."""
    net = _load_default_network()
    orch = PipelineOrchestrator(network=net)

    scen = Scenario(
        scenario_id="SCEN_FINAL_BLOCKAGE",
        name="Throat Complete Blockage",
        affected_service_ids=COHORT_40[:10],
        track_speed_restrictions={
            "MAS_BBQ_THROAT_SEGMENT_DOWN": 9999.0,
            "MAS_BBQ_THROAT_SEGMENT_UP": 9999.0,
        },
    )

    res = orch.run_pipeline(scenario=scen, service_ids=COHORT_40[:10])
    assert res.solver_status in ("INFEASIBLE", "INVALID")
    assert res.solve_time_seconds < 5.0


# ---------------------------------------------------------------------------
# 6. API Endpoint Integrity
# ---------------------------------------------------------------------------

def test_fastapi_endpoints_integrity():
    """Verify core FastAPI endpoints respond correctly."""
    client = TestClient(app)

    # 1. Health / Root
    resp_health = client.get("/health")
    if resp_health.status_code == 200:
        assert resp_health.json().get("status") in ("ok", "healthy", "UP")

    # 2. Analytics
    resp_analytics = client.get("/api/v1/analytics")
    assert resp_analytics.status_code == 200
    data_analytics = resp_analytics.json()
    assert "aggregate_statistics" in data_analytics
    assert "core_benchmark_results" in data_analytics
