"""
tests/test_paper_reproduction.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Unit and regression test suite verifying that paper reproducibility checks pass.
"""

from __future__ import annotations

import os
import pytest

from scripts.reproduce_paper import audit_stored_results


def test_paper_reproduction_checks_pass():
    """Verify that all reproducible paper claims match stored evaluation datasets within tolerance."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    results = audit_stored_results(base_dir)

    assert results["status"] == "PASSED", f"Paper reproduction failed: {results['failed_checks']} checks failed"
    assert results["total_checks"] == 10
    assert results["passed_checks"] == 10
    assert results["failed_checks"] == 0

    # Verify that all 10 checks passed individually
    for check in results["checks"]:
        assert check["passed"] is True, f"Check {check['id']} failed: expected {check['expected']}, got {check['actual']}"

    # Verify that the 3 unverified claims are classified as RECONSTRUCTED or NOT FOUND
    unverified = {u["claim"]: u["status"] for u in results["unverified_paper_values"]}
    assert len(unverified) == 3
    assert unverified["Compound Disruption 183 to 123 (saving 60.0 min, 32.8%)"] == "RECONSTRUCTED"
    assert unverified["20.5% mean reduction over '6 core experiments'"] == "NOT FOUND"
    assert unverified["44.3% for the most aggressive compound scenario"] == "RECONSTRUCTED"
