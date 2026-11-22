"""
tests/test_paper_reconstruction.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit tests verifying the reconstructed CICT 2026 paper claims.

Verifies:
1. Reconstructed Claim (a): SRV_12607_01 + SRV_12609_01 with delay +20m yields FIFO 183.0, CP-SAT 123.0.
2. Reconstructed Claim (b): SRV_12607_01 + SRV_12609_01 + SRV_12635_01 with dual +20m delays yields 221.0 -> 123.0 (44.34%).
3. Generated artifacts in data/evaluation/paper_reconstruction/ exist and carry search grid metadata.
"""

import json
import os
import pytest

from optimization.scenarios import Scenario, ScenarioRunner
from scripts.reconstruct_paper_claims import run_reconstruction, SEARCH_GRID_SIZE


def test_reconstructed_claim_183_to_123():
    """Verify reconstructed claim (a): FIFO 183.0, CP-SAT 123.0 (60.0 min savings)."""
    runner = ScenarioRunner()
    scen = Scenario(
        scenario_id="TEST_RECON_CLAIM_183_123",
        name="Test Reconstructed 183 to 123",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01"],
        departure_delays={"SRV_12607_01": 20.0},
    )
    res = runner.run_scenario(scen)

    assert res.optimization_status == "OPTIMAL"
    assert round(res.baseline_total_delay, 1) == 183.0
    assert round(res.optimized_total_delay, 1) == 123.0
    savings = res.baseline_total_delay - res.optimized_total_delay
    assert round(savings, 1) == 60.0


def test_reconstructed_claim_44_34_percent():
    """Verify reconstructed claim (b): 221.0 -> 123.0 (44.34% savings)."""
    runner = ScenarioRunner()
    scen = Scenario(
        scenario_id="TEST_RECON_CLAIM_44_34_PCT",
        name="Test Reconstructed 44.34%",
        affected_service_ids=["SRV_12607_01", "SRV_12609_01", "SRV_12635_01"],
        departure_delays={"SRV_12607_01": 20.0, "SRV_12635_01": 20.0},
    )
    res = runner.run_scenario(scen)

    assert res.optimization_status == "OPTIMAL"
    assert round(res.baseline_total_delay, 1) == 221.0
    assert round(res.optimized_total_delay, 1) == 123.0
    savings = res.baseline_total_delay - res.optimized_total_delay
    pct = (savings / res.baseline_total_delay) * 100.0
    assert round(pct, 2) == 44.34


def test_reconstruction_runner_and_artifacts():
    """Verify run_reconstruction generates artifacts and labels them RECONSTRUCTED / NOT FOUND."""
    results = run_reconstruction()

    assert results["search_grid"]["size"] == SEARCH_GRID_SIZE
    claims = {c["claim_id"]: c for c in results["claims"]}

    assert claims["CLAIM_183_123"]["status"] == "RECONSTRUCTED"
    assert claims["CLAIM_183_123"]["verification_passed"] is True
    assert "not an original stored record" in claims["CLAIM_183_123"]["provenance_note"]

    assert claims["CLAIM_44_34_PCT"]["status"] == "RECONSTRUCTED"
    assert claims["CLAIM_44_34_PCT"]["verification_passed"] is True

    assert claims["CLAIM_20_5_PCT"]["status"] == "NOT FOUND"
    assert claims["CLAIM_20_5_PCT"]["verification_passed"] is True

    # Artifact files must exist
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "data", "evaluation", "paper_reconstruction", "reconstructed_claims.json")
    md_path = os.path.join(base_dir, "data", "evaluation", "paper_reconstruction", "reconstructed_claims.md")
    assert os.path.isfile(json_path)
    assert os.path.isfile(md_path)
