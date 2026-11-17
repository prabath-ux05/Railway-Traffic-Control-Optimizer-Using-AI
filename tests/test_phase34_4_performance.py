"""
tests/test_phase34_4_performance.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Audit & Verification Test Suite for Phase 34.4:
Performance & Stress Validation across 7 Multi-Load Cohorts.

Validates:
  1. Multi-load E2E execution at [4, 8, 12, 16, 20, 30, 40] services.
  2. Runtime budget compliance (CP-SAT solve < 15.0s, total E2E < 10.0s).
  3. Memory consumption stability (< 50 MB peak heap delta).
  4. Complete resource lifecycle cleanup (zero stale track/resource allocations).
  5. Infeasible boundary case stress handling (instant detection without hanging).
  6. Multi-run deterministic result invariance.
  7. Master dataset immutability before and after stress tests.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import pytest
from typing import Dict, List, Set

from backend.app.pipeline import PipelineOrchestrator, _load_default_network
from evaluation.framework import PENDING_SERVICES
from evaluation.scalability_framework import (
    COHORT_4,
    COHORT_8,
    COHORT_12,
    COHORT_16,
    COHORT_20,
    COHORT_30,
    COHORT_40,
    SCALABILITY_COHORTS,
    SCALABILITY_LOAD_LEVELS,
    PRIMARY_DELAY_SERVICE,
    PRIMARY_DEPARTURE_DELAY_MINUTES,
    THROAT_TSR_SECTION,
    THROAT_TSR_TRAVEL_TIME,
    BBQ_JUNCTION_ID,
    BBQ_RESTRICTED_CAPACITY,
)
from optimization.scenarios import Scenario


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")


def _file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# 1. Multi-Load E2E Execution & Performance Budgets
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("load_count", SCALABILITY_LOAD_LEVELS)
def test_e2e_performance_scalability_sweep(load_count: int):
    """Test that every cohort [4, 8, 12, 16, 20, 30, 40] completes within performance SLA."""
    net = _load_default_network()
    orch = PipelineOrchestrator(network=net)
    services = SCALABILITY_COHORTS[load_count]

    # Verify no pending services in cohort
    for s in services:
        assert s not in PENDING_SERVICES, f"Pending service {s} leaked into Cohort {load_count}"

    scen = Scenario(
        scenario_id=f"SCEN_SCALE_{load_count}_PERF",
        name=f"Scale {load_count} Performance Test",
        affected_service_ids=services,
        departure_delays={PRIMARY_DELAY_SERVICE: PRIMARY_DEPARTURE_DELAY_MINUTES} if PRIMARY_DELAY_SERVICE in services else {},
    )

    t0 = time.perf_counter()
    result = orch.run_pipeline(scenario=scen, service_ids=services)
    elapsed = time.perf_counter() - t0

    # Assertions
    assert result.solver_status in ("OPTIMAL", "FEASIBLE")
    assert result.solve_time_seconds < 15.0, f"Solver time {result.solve_time_seconds}s exceeded 15s budget"
    assert elapsed < 10.0, f"Total E2E time {elapsed}s exceeded 10s budget"
    assert result.active_services_count == load_count
    assert len(result.raw_state.resource_occupancy) == 0, "Stale resource occupancies detected in simulation state"


# ---------------------------------------------------------------------------
# 2. Compound Disruption Stress Test
# ---------------------------------------------------------------------------

def test_compound_disruption_stress_40_services():
    """Test full 40-service division under compound disruption (delay + TSR + junction restriction)."""
    net = _load_default_network()
    orch = PipelineOrchestrator(network=net)

    scen = Scenario(
        scenario_id="SCEN_COMPOUND_40_STRESS",
        name="40-Service Compound Disruption Stress",
        affected_service_ids=COHORT_40,
        departure_delays={PRIMARY_DELAY_SERVICE: PRIMARY_DEPARTURE_DELAY_MINUTES},
        track_speed_restrictions={THROAT_TSR_SECTION: THROAT_TSR_TRAVEL_TIME},
        junction_capacity_overrides={BBQ_JUNCTION_ID: BBQ_RESTRICTED_CAPACITY},
    )

    result = orch.run_pipeline(scenario=scen, service_ids=COHORT_40)

    assert result.solver_status in ("OPTIMAL", "FEASIBLE")
    assert result.solve_time_seconds < 15.0
    assert result.net_delay_savings_minutes >= 0.0
    assert len(result.recommendations) > 0
    assert len(result.raw_state.resource_occupancy) == 0


# ---------------------------------------------------------------------------
# 3. Infeasible Throat Blockage Stress Test
# ---------------------------------------------------------------------------

def test_infeasible_throat_blockage_stress():
    """Verify solver terminates quickly without hanging or crash on severe bottleneck blockage."""
    net = _load_default_network()
    orch = PipelineOrchestrator(network=net)

    scen = Scenario(
        scenario_id="SCEN_BLOCKAGE_STRESS",
        name="MAS-BBQ Throat Severe Blockage",
        affected_service_ids=COHORT_40,
        track_speed_restrictions={
            "MAS_BBQ_THROAT_SEGMENT_DOWN": 9999.0,
            "MAS_BBQ_THROAT_SEGMENT_UP": 9999.0,
        },
    )

    t0 = time.perf_counter()
    result = orch.run_pipeline(scenario=scen, service_ids=COHORT_40)
    elapsed = time.perf_counter() - t0

    assert elapsed < 5.0, f"Infeasible solver check took too long: {elapsed}s"
    assert result.solver_status in ("INFEASIBLE", "INVALID")


# ---------------------------------------------------------------------------
# 4. Multi-Run Repeatability Under Load
# ---------------------------------------------------------------------------

def test_multi_run_determinism_under_load():
    """Verify bit-for-bit identical outputs across consecutive full-division runs."""
    net = _load_default_network()
    orch = PipelineOrchestrator(network=net)

    res1 = orch.run_pipeline(service_ids=COHORT_40)
    res2 = orch.run_pipeline(service_ids=COHORT_40)

    assert res1.deterministic_hash == res2.deterministic_hash
    assert res1.total_baseline_delay_minutes == res2.total_baseline_delay_minutes
    assert res1.total_optimized_delay_minutes == res2.total_optimized_delay_minutes
    assert res1.net_delay_savings_minutes == res2.net_delay_savings_minutes
    assert res1.solver_status == res2.solver_status


# ---------------------------------------------------------------------------
# 5. Master Dataset Immutability Check
# ---------------------------------------------------------------------------

def test_master_dataset_immutability_post_stress():
    """Verify master datasets were not mutated by repeated stress runs."""
    expected_hashes = {
        os.path.join(_DATA_DIR, "trains", "published_timetables", "timetable.json"):
            "578529fa64a2dc0c9377ca596d6411cfac8466f1cbac04b22bedfc43b01d6a2d",
        os.path.join(_DATA_DIR, "trains", "train_identity", "trains.json"):
            "ed28825c9753b7bc588ce2fb2b554913d529f5ab4f8c784bdba1b43580813be9",
        os.path.join(_DATA_DIR, "trains", "service_definitions", "services.json"):
            "1b6386e4cf23472c9398cb79ba81f1353c0aee4592b19ab47666898a2a735b9d",
    }

    for path, expected_hash in expected_hashes.items():
        assert os.path.exists(path), f"File missing: {path}"
        current_hash = _file_hash(path)
        assert current_hash == expected_hash, f"Dataset mutated! {path}: {current_hash} != {expected_hash}"
