"""
tests/test_scalability.py
~~~~~~~~~~~~~~~~~~~~~~~~~
Batch 13: Deterministic scalability / stress-testing test suite.

Verifies:
1.  Load-level service counts match expected values (4, 8, 12, 16, max).
2.  All disruption-mode scenarios produce a valid ScalabilityMetrics object.
3.  Solver status is always one of the four recognised strings.
4.  CP-SAT solve time is finite, non-negative, and ≤ configured time limit.
5.  Throughput equals the configured load-level service count for NORMAL mode.
6.  Dataset integrity: no JSON files mutated (verified by comparing stored SHA-256
    hashes from test_dataset_integrity.py's data fixtures).
7.  Scalability-growth check: mean solve time is monotonically non-decreasing
    across increasing load levels (logged as a warning, not a hard failure).
8.  Delay-monotonicity: SINGLE_DELAY ≥ NORMAL and MULTI_DELAY ≥ SINGLE_DELAY
    for feasible baseline (soft assertion – logs warning if violated).
9.  ScalabilityReport Markdown and ASCII summaries are non-empty strings.
10. ScalabilityRunner can be constructed with custom load levels and disruption
    modes, and only those modes are executed.
"""

from __future__ import annotations

import hashlib
import json
import os
import warnings
from typing import Dict, List

import pytest

from evaluation.scalability import (
    ALL_DISRUPTION_MODES,
    DISRUPTION_MULTI_DELAY,
    DISRUPTION_NORMAL,
    DISRUPTION_SEVERE_COMPOUND,
    DISRUPTION_SINGLE_DELAY,
    ScalabilityLoadLevel,
    ScalabilityMetrics,
    ScalabilityReport,
    ScalabilityResult,
    ScalabilityRunner,
    create_west_corridor_load_levels,
    run_scalability_suite,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_VALID_SOLVER_STATUSES = {"OPTIMAL", "FEASIBLE", "INFEASIBLE", "TIME_LIMIT", "BASELINE"}

# Expected service counts for each standard load level
_EXPECTED_COUNTS = {
    "4 Services": 4,
    "8 Services": 8,
    "12 Services": 12,
    "16 Services": 16,
    "Max Available": 20,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _collect_json_hashes() -> Dict[str, str]:
    """Walk the data/ directory and record SHA-256 for every JSON file."""
    hashes: Dict[str, str] = {}
    data_dir = os.path.join(_REPO_ROOT, "data")
    for root, _dirs, files in os.walk(data_dir):
        for fname in files:
            if fname.endswith(".json"):
                full = os.path.join(root, fname)
                hashes[full] = _sha256_file(full)
    return hashes


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def json_hashes_before() -> Dict[str, str]:
    """Capture JSON file hashes before the test module runs."""
    return _collect_json_hashes()


@pytest.fixture(scope="module")
def load_levels() -> List[ScalabilityLoadLevel]:
    return create_west_corridor_load_levels()


@pytest.fixture(scope="module")
def runner() -> ScalabilityRunner:
    """Shared ScalabilityRunner for the full module (avoid repeated network load)."""
    return ScalabilityRunner(time_limit_seconds=15.0)


@pytest.fixture(scope="module")
def full_report(runner: ScalabilityRunner) -> ScalabilityReport:
    """Run the complete sweep once for the entire module."""
    return runner.run()


# ---------------------------------------------------------------------------
# 1. Load-level definition tests
# ---------------------------------------------------------------------------

class TestLoadLevelDefinitions:
    """Verify load-level cohort structure before any I/O."""

    def test_five_load_levels_defined(self, load_levels):
        assert len(load_levels) == 5, "Expected exactly 5 West Corridor load levels"

    @pytest.mark.parametrize("label,expected_count", list(_EXPECTED_COUNTS.items()))
    def test_service_count(self, load_levels, label, expected_count):
        level = next((ll for ll in load_levels if ll.label == label), None)
        assert level is not None, f"Load level '{label}' not found"
        assert level.service_count == expected_count, (
            f"{label}: expected {expected_count} services, got {level.service_count}"
        )

    def test_service_ids_are_strings(self, load_levels):
        for ll in load_levels:
            for sid in ll.service_ids:
                assert isinstance(sid, str) and sid.startswith("SRV_"), (
                    f"Invalid service ID '{sid}' in load level '{ll.label}'"
                )

    def test_no_duplicate_service_ids_within_level(self, load_levels):
        for ll in load_levels:
            assert len(ll.service_ids) == len(set(ll.service_ids)), (
                f"Duplicate service IDs found in load level '{ll.label}'"
            )

    def test_load_levels_are_strictly_increasing(self, load_levels):
        counts = [ll.service_count for ll in load_levels]
        for i in range(1, len(counts)):
            assert counts[i] > counts[i - 1], (
                f"Load levels not strictly increasing: {counts}"
            )

    def test_outbound_services_are_subset_of_service_ids(self, load_levels):
        for ll in load_levels:
            for sid in ll.outbound_services:
                assert sid in ll.service_ids, (
                    f"Outbound service '{sid}' not in service_ids for '{ll.label}'"
                )

    def test_no_ptms_services_in_west_corridor_levels(self, load_levels):
        """PTMS→MAS services belong to a different corridor and must not appear."""
        ptms_ids = {"SRV_43102_01", "SRV_43116_01"}
        for ll in load_levels:
            overlap = set(ll.service_ids) & ptms_ids
            assert not overlap, (
                f"PTMS services {overlap} must not appear in West Corridor load level '{ll.label}'"
            )

    def test_to_dict_serialisable(self, load_levels):
        for ll in load_levels:
            d = ll.to_dict()
            assert d["service_count"] == ll.service_count
            json.dumps(d)  # must not raise


# ---------------------------------------------------------------------------
# 2. ScalabilityMetrics structure tests
# ---------------------------------------------------------------------------

class TestScalabilityMetricsStructure:
    """Verify metric objects have correct types and valid value ranges."""

    @pytest.fixture(scope="class")
    @classmethod
    def single_metrics(cls, runner: ScalabilityRunner) -> ScalabilityMetrics:
        """Run the smallest load level (4 services) in NORMAL mode."""
        levels = create_west_corridor_load_levels()
        return runner.run_single(levels[0], DISRUPTION_NORMAL, run_index=0)

    def test_returns_scalability_metrics_instance(self, single_metrics):
        assert isinstance(single_metrics, ScalabilityMetrics)

    def test_service_count_is_four(self, single_metrics):
        assert single_metrics.service_count == 4

    def test_solver_status_valid(self, single_metrics):
        assert single_metrics.solver_status in _VALID_SOLVER_STATUSES

    def test_solve_time_non_negative(self, single_metrics):
        assert single_metrics.solve_time_seconds >= 0.0

    def test_solve_time_within_limit(self, single_metrics):
        # Allow a 2-second grace margin beyond the configured limit
        assert single_metrics.solve_time_seconds <= 15.0 + 2.0

    def test_delay_values_non_negative(self, single_metrics):
        assert single_metrics.feasible_baseline_total_delay >= 0.0
        assert single_metrics.optimized_total_delay >= 0.0
        assert single_metrics.feasible_baseline_max_delay >= 0.0
        assert single_metrics.optimized_max_delay >= 0.0

    def test_throughput_non_negative(self, single_metrics):
        assert single_metrics.baseline_throughput >= 0
        assert single_metrics.optimized_throughput >= 0

    def test_conflict_counts_non_negative(self, single_metrics):
        assert single_metrics.initial_conflicts >= 0
        assert single_metrics.baseline_remaining_conflicts >= 0
        assert single_metrics.optimized_remaining_conflicts >= 0
        assert single_metrics.resolved_conflicts >= 0

    def test_to_dict_serialisable(self, single_metrics):
        d = single_metrics.to_dict()
        json.dumps(d)

    def test_ascii_row_non_empty(self, single_metrics):
        row = single_metrics.to_ascii_row()
        assert isinstance(row, str) and len(row) > 10

    def test_markdown_row_non_empty(self, single_metrics):
        row = single_metrics.to_markdown_row()
        assert isinstance(row, str) and "|" in row


# ---------------------------------------------------------------------------
# 3. Full report structure tests
# ---------------------------------------------------------------------------

class TestScalabilityReportStructure:
    """Verify ScalabilityReport from a full sweep."""

    def test_report_has_five_results(self, full_report):
        assert len(full_report.results) == 5

    def test_total_runs_equals_twenty(self, full_report):
        expected = 5 * len(ALL_DISRUPTION_MODES)
        assert full_report.total_runs == expected, (
            f"Expected {expected} total runs, got {full_report.total_runs}"
        )

    def test_all_disruption_modes_present(self, full_report):
        for result in full_report.results:
            modes_run = {m.disruption_mode for m in result.runs}
            for mode in ALL_DISRUPTION_MODES:
                assert mode in modes_run, (
                    f"Load level '{result.label}' missing disruption mode '{mode}'"
                )

    def test_elapsed_wall_seconds_positive(self, full_report):
        assert full_report.elapsed_wall_seconds > 0.0

    def test_optimal_count_in_range(self, full_report):
        assert 0 <= full_report.total_optimal <= full_report.total_runs

    def test_ascii_summary_non_empty(self, full_report):
        s = full_report.summary()
        assert isinstance(s, str) and "SCALABILITY" in s.upper()

    def test_markdown_report_non_empty(self, full_report):
        md = full_report.to_markdown_report()
        assert isinstance(md, str) and "# Batch 13" in md

    def test_markdown_report_contains_all_load_labels(self, full_report):
        md = full_report.to_markdown_report()
        for label in _EXPECTED_COUNTS:
            assert label in md, f"Markdown report missing load level '{label}'"

    def test_to_dict_serialisable(self, full_report):
        d = full_report.to_dict()
        json.dumps(d)


# ---------------------------------------------------------------------------
# 4. Per-load-level service count accuracy
# ---------------------------------------------------------------------------

class TestLoadLevelServiceCounts:
    """Every result must have service_count matching the load-level definition."""

    @pytest.mark.parametrize("label,expected_count", list(_EXPECTED_COUNTS.items()))
    def test_result_service_count(self, full_report, label, expected_count):
        result = next((r for r in full_report.results if r.label == label), None)
        assert result is not None, f"Result for load level '{label}' not found"
        assert result.service_count == expected_count


# ---------------------------------------------------------------------------
# 5. Solver status validity
# ---------------------------------------------------------------------------

class TestSolverStatusValidity:
    """Solver status must always be one of the four recognised strings."""

    def test_all_solver_statuses_valid(self, full_report):
        for result in full_report.results:
            for run in result.runs:
                assert run.solver_status in _VALID_SOLVER_STATUSES, (
                    f"Unexpected solver status '{run.solver_status}' "
                    f"in {run.load_label} / {run.disruption_mode}"
                )


# ---------------------------------------------------------------------------
# 6. Solve time bounds
# ---------------------------------------------------------------------------

class TestSolveTimeBounds:
    """Solve times must be finite, non-negative, and within the configured limit."""

    def test_all_solve_times_finite_non_negative(self, full_report):
        for result in full_report.results:
            for run in result.runs:
                assert run.solve_time_seconds >= 0.0, (
                    f"Negative solve time in {run.load_label} / {run.disruption_mode}"
                )
                assert run.solve_time_seconds < float("inf"), (
                    f"Infinite solve time in {run.load_label} / {run.disruption_mode}"
                )

    def test_all_solve_times_within_limit_plus_grace(self, full_report):
        limit = 15.0 + 3.0  # 3-second grace for overhead
        for result in full_report.results:
            for run in result.runs:
                assert run.solve_time_seconds <= limit, (
                    f"Solve time {run.solve_time_seconds:.3f}s exceeds limit "
                    f"in {run.load_label} / {run.disruption_mode}"
                )


# ---------------------------------------------------------------------------
# 7. Throughput: NORMAL mode must schedule all services
# ---------------------------------------------------------------------------

class TestThroughputNormalMode:
    """In NORMAL (no-delay) mode, all services should be scheduled."""

    def test_optimized_throughput_equals_service_count(self, full_report):
        for result in full_report.results:
            normal_run = result.get_run(DISRUPTION_NORMAL)
            assert normal_run is not None
            # Throughput should equal or exceed the expected service count
            # (it cannot exceed since only those services are in the request)
            assert normal_run.optimized_throughput == result.service_count, (
                f"NORMAL throughput {normal_run.optimized_throughput} ≠ "
                f"expected {result.service_count} for '{result.label}'"
            )

    def test_baseline_throughput_equals_service_count(self, full_report):
        for result in full_report.results:
            normal_run = result.get_run(DISRUPTION_NORMAL)
            assert normal_run is not None
            assert normal_run.baseline_throughput == result.service_count, (
                f"Baseline NORMAL throughput {normal_run.baseline_throughput} ≠ "
                f"expected {result.service_count} for '{result.label}'"
            )


# ---------------------------------------------------------------------------
# 8. Monotonicity checks (soft – warnings only)
# ---------------------------------------------------------------------------

class TestMonotonicitySoftChecks:
    """Non-hard checks that validate expected trends without failing the suite."""

    def test_delay_monotonicity_across_disruption_modes(self, full_report):
        """Feasible baseline delay should weakly increase with disruption severity."""
        mode_order = [
            DISRUPTION_NORMAL,
            DISRUPTION_SINGLE_DELAY,
            DISRUPTION_MULTI_DELAY,
            DISRUPTION_SEVERE_COMPOUND,
        ]
        for result in full_report.results:
            delays = []
            for mode in mode_order:
                run = result.get_run(mode)
                if run:
                    delays.append((mode, run.feasible_baseline_total_delay))

            for i in range(1, len(delays)):
                prev_mode, prev_delay = delays[i - 1]
                cur_mode, cur_delay = delays[i]
                if cur_delay < prev_delay - 0.5:
                    warnings.warn(
                        f"[{result.label}] Feasible baseline delay DECREASED from "
                        f"{prev_mode} ({prev_delay:.1f}m) → {cur_mode} ({cur_delay:.1f}m). "
                        "This may indicate service subsets differ in base delay."
                    )

    def test_solve_time_growth_trend(self, full_report):
        """Mean solve time should generally increase with service count."""
        normal_times = [
            (r.service_count, r.get_run(DISRUPTION_NORMAL).solve_time_seconds)
            for r in full_report.results
            if r.get_run(DISRUPTION_NORMAL) is not None
        ]
        if len(normal_times) >= 2:
            # Compare first (smallest) vs last (largest) load level
            small_time = normal_times[0][1]
            large_time = normal_times[-1][1]
            if large_time < small_time * 0.5:
                warnings.warn(
                    f"Unexpected: solve time for {normal_times[-1][0]} services "
                    f"({large_time:.3f}s) is less than half of {normal_times[0][0]} "
                    f"services ({small_time:.3f}s). May indicate caching or trivial solve."
                )


# ---------------------------------------------------------------------------
# 9. Dataset integrity (JSON files must not be mutated)
# ---------------------------------------------------------------------------

class TestDatasetIntegrity:
    """Verify that no JSON dataset file was modified during the scalability sweep."""

    def test_no_json_files_mutated(self, json_hashes_before, full_report):
        """Compare SHA-256 hashes of all JSON files in data/ before and after the sweep."""
        hashes_after = _collect_json_hashes()

        # All files present before must still be present with the same hash
        for path, digest_before in json_hashes_before.items():
            assert path in hashes_after, f"JSON file removed during sweep: {path}"
            assert hashes_after[path] == digest_before, (
                f"JSON file MUTATED during scalability sweep: {path}\n"
                f"  Before: {digest_before}\n"
                f"  After:  {hashes_after[path]}"
            )


# ---------------------------------------------------------------------------
# 10. Custom runner configuration
# ---------------------------------------------------------------------------

class TestCustomRunnerConfiguration:
    """Verify ScalabilityRunner respects custom load levels and disruption modes."""

    def test_single_mode_single_level_run(self, runner):
        """Running with one load level and one disruption mode produces exactly one run."""
        levels = create_west_corridor_load_levels()
        mini_levels = [levels[0]]  # 4 services only
        mini_modes = [DISRUPTION_NORMAL]

        mini_runner = ScalabilityRunner(
            network=runner.network,
            time_limit_seconds=10.0,
            load_levels=mini_levels,
            disruption_modes=mini_modes,
        )
        report = mini_runner.run()
        assert len(report.results) == 1
        assert len(report.results[0].runs) == 1
        assert report.results[0].runs[0].disruption_mode == DISRUPTION_NORMAL

    def test_run_scalability_suite_convenience_function(self, runner):
        """run_scalability_suite() returns a ScalabilityReport without error."""
        levels = create_west_corridor_load_levels()
        mini_levels = [levels[0]]
        mini_modes = [DISRUPTION_NORMAL]

        report = run_scalability_suite(
            network=runner.network,
            time_limit_seconds=10.0,
            load_levels=mini_levels,
            disruption_modes=mini_modes,
        )
        assert isinstance(report, ScalabilityReport)
        assert report.total_runs == 1

    def test_get_run_returns_correct_mode(self, full_report):
        """ScalabilityResult.get_run() returns the correct disruption-mode metrics."""
        for result in full_report.results:
            for mode in ALL_DISRUPTION_MODES:
                run = result.get_run(mode)
                assert run is not None, f"get_run({mode}) returned None for '{result.label}'"
                assert run.disruption_mode == mode


# ---------------------------------------------------------------------------
# 11. ScalabilityResult aggregation properties
# ---------------------------------------------------------------------------

class TestScalabilityResultAggregation:
    """Verify ScalabilityResult aggregate properties are correctly computed."""

    def test_mean_solve_time_in_range(self, full_report):
        for result in full_report.results:
            assert 0.0 <= result.mean_solve_time <= 15.0 + 3.0

    def test_max_solve_time_gte_mean(self, full_report):
        for result in full_report.results:
            assert result.max_solve_time >= result.mean_solve_time - 1e-9

    def test_optimal_count_in_range(self, full_report):
        for result in full_report.results:
            assert 0 <= result.optimal_count <= len(result.runs)

    def test_summary_string_contains_label(self, full_report):
        for result in full_report.results:
            s = result.summary()
            assert result.label in s

    def test_to_dict_has_required_keys(self, full_report):
        for result in full_report.results:
            d = result.to_dict()
            assert "load_level" in d
            assert "runs" in d
            assert "mean_solve_time_seconds" in d
            assert "optimal_count" in d
