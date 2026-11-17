"""
tests/test_validation.py
~~~~~~~~~~~~~~~~~~~~~~~~
Batch 16: Unit and integration tests for Digital Twin Operational Validation.

Verifies:
1. Train movement validation (route order, travel times, chronological progression, reverse movement).
2. Timetable consistency (train identity linkage, route alignment, time monotonicity, non-fabrication).
3. Track occupancy lifecycle (acquire, release, opposing protection, directional pairing).
4. Station/platform behavior (state transitions, dwell times, platform count limits).
5. Junction abstractions (BBQ, VJM, PAB, KOK, MSB, CGL, AJJ, connected routes, capacity).
6. Conflict detection & resolution (headway, junction, platform, clean state invariance).
7. Deterministic delay propagation (downstream ripple effect, timetable immutability).
8. Multi-corridor integrity (West, North, South, Bypass, MRTS, Cross, PTMS route continuity).
9. Report generation and serialization.
10. Complete dataset immutability (SHA-256 verification before vs after).
"""

from __future__ import annotations

import hashlib
import json
import os
from typing import Dict, List

import pytest

from simulation.network import Network
from simulation.validation import (
    DigitalTwinValidationReport,
    DigitalTwinValidator,
    ValidationCategoryResult,
    ValidationCheck,
    run_digital_twin_validation,
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# Helpers & SHA-256 Verification Fixture
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_json_hashes() -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    data_dir = os.path.join(_REPO_ROOT, "data")
    for root, _dirs, files in os.walk(data_dir):
        for fname in files:
            if fname.endswith(".json"):
                full = os.path.join(root, fname)
                hashes[full] = _sha256_file(full)
    return hashes


@pytest.fixture(scope="module")
def json_hashes_before() -> Dict[str, str]:
    return _collect_json_hashes()


@pytest.fixture(scope="module")
def validation_report() -> DigitalTwinValidationReport:
    """Execute the full validation suite once for this test module."""
    return run_digital_twin_validation()


# ---------------------------------------------------------------------------
# Domain 1 Tests: Train Movement Validation
# ---------------------------------------------------------------------------

class TestTrainMovementValidation:
    """Verify route order, travel times, chronological progression, and reverse movement."""

    def test_movement_validation_category_passes(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Train Movement Validation")
        assert cat.all_passed is True
        assert cat.passed_count >= 4

    def test_outbound_express_reaches_terminus(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Train Movement Validation")
        chk = next(c for c in cat.checks if "Outbound Express Movement" in c.name)
        assert chk.passed is True

    def test_reverse_direction_reaches_terminus(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Train Movement Validation")
        chk = next(c for c in cat.checks if "Return Express Movement" in c.name)
        assert chk.passed is True

    def test_travel_times_are_positive(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Train Movement Validation")
        chk = next(c for c in cat.checks if "Travel Time Fidelity" in c.name)
        assert chk.passed is True


# ---------------------------------------------------------------------------
# Domain 2 Tests: Timetable Consistency Validation
# ---------------------------------------------------------------------------

class TestTimetableConsistencyValidation:
    """Verify train identity resolution, route alignment, time monotonicity, and commercial stops."""

    def test_timetable_consistency_category_passes(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Timetable Consistency Validation")
        assert cat.all_passed is True
        assert cat.passed_count >= 5

    def test_services_resolve_to_trains(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Timetable Consistency Validation")
        chk = next(c for c in cat.checks if "Service Train Identity Resolution" in c.name)
        assert chk.passed is True

    def test_timetable_stops_match_route_nodes(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Timetable Consistency Validation")
        chk = next(c for c in cat.checks if "Timetable Station Route Alignment" in c.name)
        assert chk.passed is True

    def test_timetable_times_monotonic(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Timetable Consistency Validation")
        chk = next(c for c in cat.checks if "Chronological Timetable Monotonicity" in c.name)
        assert chk.passed is True


# ---------------------------------------------------------------------------
# Domain 3 Tests: Track Occupancy Validation
# ---------------------------------------------------------------------------

class TestTrackOccupancyValidation:
    """Verify section acquire/release lifecycle, opposing movement protection, and directional pairing."""

    def test_occupancy_category_passes(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Track Occupancy Validation")
        assert cat.all_passed is True
        assert cat.passed_count >= 3

    def test_acquire_and_release_lifecycle(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Track Occupancy Validation")
        chk = next(c for c in cat.checks if "Track Occupancy Acquire/Release Lifecycle" in c.name)
        assert chk.passed is True
        assert chk.metrics["active_during"] == 1
        assert chk.metrics["active_after"] == 0

    def test_directional_pairing(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Track Occupancy Validation")
        chk = next(c for c in cat.checks if "Directional Track Section Mapping" in c.name)
        assert chk.passed is True
        assert chk.metrics["down_sections"] > 0
        assert chk.metrics["up_sections"] > 0


# ---------------------------------------------------------------------------
# Domain 4 Tests: Station and Platform Behavior Validation
# ---------------------------------------------------------------------------

class TestStationAndPlatformValidation:
    """Verify platform bounds, state progression, and dwell times."""

    def test_station_platform_category_passes(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Station & Platform Validation")
        assert cat.all_passed is True
        assert cat.passed_count >= 3

    def test_platform_bounds_valid(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Station & Platform Validation")
        chk = next(c for c in cat.checks if "Platform Count & Indexing Bounds" in c.name)
        assert chk.passed is True

    def test_dwell_times_non_negative(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Station & Platform Validation")
        chk = next(c for c in cat.checks if "Station Dwell Time Validity" in c.name)
        assert chk.passed is True


# ---------------------------------------------------------------------------
# Domain 5 Tests: Junction Behavior Validation
# ---------------------------------------------------------------------------

class TestJunctionBehaviorValidation:
    """Verify BBQ, VJM, PAB, KOK, MSB, CGL, AJJ junction abstractions and connected routes."""

    def test_junction_category_passes(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Junction Behavior Validation")
        assert cat.all_passed is True
        assert cat.passed_count >= 3

    def test_core_junctions_present(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Junction Behavior Validation")
        chk = next(c for c in cat.checks if "Core Junction Presence" in c.name)
        assert chk.passed is True

    def test_junction_routes_valid(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Junction Behavior Validation")
        chk = next(c for c in cat.checks if "Junction Connected Routes Integrity" in c.name)
        assert chk.passed is True


# ---------------------------------------------------------------------------
# Domain 6 Tests: Conflict Detection Validation
# ---------------------------------------------------------------------------

class TestConflictDetectionValidation:
    """Verify detection of headway, opposing, and junction conflicts."""

    def test_conflict_detection_category_passes(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Conflict Detection Validation")
        assert cat.all_passed is True
        assert cat.passed_count >= 3

    def test_headway_conflict_detected(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Conflict Detection Validation")
        chk = next(c for c in cat.checks if "Headway & Shared Resource Conflict Detection" in c.name)
        assert chk.passed is True

    def test_junction_contention_detected(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Conflict Detection Validation")
        chk = next(c for c in cat.checks if "Junction Capacity Contention Detection" in c.name)
        assert chk.passed is True


# ---------------------------------------------------------------------------
# Domain 7 Tests: Delay Propagation Validation
# ---------------------------------------------------------------------------

class TestDelayPropagationValidation:
    """Verify deterministic downstream delay propagation and dataset immutability."""

    def test_delay_propagation_category_passes(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Delay Propagation Validation")
        assert cat.all_passed is True
        assert cat.passed_count >= 2

    def test_downstream_ripple_effect(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Delay Propagation Validation")
        chk = next(c for c in cat.checks if "Downstream Delay Ripple Effect" in c.name)
        assert chk.passed is True

    def test_timetable_not_mutated_by_simulation(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Delay Propagation Validation")
        chk = next(c for c in cat.checks if "Static Timetable Immutability Guarantee" in c.name)
        assert chk.passed is True


# ---------------------------------------------------------------------------
# Domain 8 Tests: Multi-Corridor Integrity Validation
# ---------------------------------------------------------------------------

class TestMultiCorridorIntegrityValidation:
    """Verify route existence and complete track-section continuity across all 7 corridors."""

    def test_multi_corridor_category_passes(self, validation_report: DigitalTwinValidationReport):
        cat = next(c for c in validation_report.category_results if c.category == "Multi-Corridor Integrity Validation")
        assert cat.all_passed is True
        assert cat.passed_count == 7

    @pytest.mark.parametrize("corridor_name", [
        "West Corridor",
        "North Corridor",
        "South Corridor",
        "Beach-North Bypass",
        "MRTS Corridor",
        "Cross Line / Bypass",
        "PTMS Branch",
    ])
    def test_individual_corridor_continuity(
        self,
        validation_report: DigitalTwinValidationReport,
        corridor_name: str,
    ):
        cat = next(c for c in validation_report.category_results if c.category == "Multi-Corridor Integrity Validation")
        chk = next(c for c in cat.checks if corridor_name in c.name)
        assert chk.passed is True
        assert chk.metrics["missing_segments"] == 0


# ---------------------------------------------------------------------------
# Report Formatting & Dataset Immutability Tests
# ---------------------------------------------------------------------------

class TestValidationReportAndIntegrity:
    """Verify report formatting, JSON serialization, and dataset immutability."""

    def test_overall_report_validity(self, validation_report: DigitalTwinValidationReport):
        assert validation_report.is_valid is True
        assert validation_report.total_failed == 0
        assert validation_report.total_passed == validation_report.total_checks
        assert len(validation_report.category_results) == 8

    def test_markdown_report_generation(self, validation_report: DigitalTwinValidationReport):
        md = validation_report.to_markdown_report()
        assert "# Batch 16: Digital Twin Operational Validation Report" in md
        assert "## Summary Table by Operational Domain" in md
        assert "## Detailed Check Results by Category" in md
        assert "## Modeling Observations & Scope Boundaries" in md

    def test_summary_ascii_generation(self, validation_report: DigitalTwinValidationReport):
        txt = validation_report.summary()
        assert "BATCH 16: DIGITAL TWIN OPERATIONAL VALIDATION REPORT" in txt
        assert "Validation Status: PASSED" in txt

    def test_to_dict_json_serializable(self, validation_report: DigitalTwinValidationReport):
        d = validation_report.to_dict()
        assert d["is_valid"] is True
        json_str = json.dumps(d)
        assert len(json_str) > 1000
        reloaded = json.loads(json_str)
        assert len(reloaded["categories"]) == 8

    def test_dataset_immutability(
        self,
        json_hashes_before: Dict[str, str],
        validation_report: DigitalTwinValidationReport,
    ):
        """Confirm that no dataset JSON file was modified during the validation suite."""
        after_hashes = _collect_json_hashes()
        assert set(json_hashes_before.keys()) == set(after_hashes.keys())
        for path, hash_before in json_hashes_before.items():
            assert after_hashes[path] == hash_before, f"Dataset file {path} was mutated!"
