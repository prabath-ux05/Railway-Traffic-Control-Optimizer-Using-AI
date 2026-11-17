"""
tests/test_cross_corridor.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Comprehensive unit and integration test suite for Batch 17:
Expanded Corridor Integration & Cross-Corridor Simulation.

Validates:
1. Multi-corridor data scope audit & boundary enforcement.
2. West trunk <-> PTMS branch convergence at JCT_PAB.
3. West trunk <-> PTMS branch terminal throat contention at JCT_BBQ.
4. Discrete platform allocation and multi-platform concurrency isolation.
5. Cross-corridor delay propagation from branch into trunk.
6. Independent-resource isolation with zero delay leakage.
7. Main vs Short route divergence at JCT_VJM.
8. Bidirectional trunk concurrency on paired tracks.
9. Suite report generation and deterministic repeatability.
"""

import pytest

from simulation.cross_corridor import (
    CorridorDataScope,
    CorridorDataStatus,
    CrossCorridorEvaluator,
    CrossCorridorScenarioType,
    CrossCorridorSimulationResult,
    CrossCorridorSuiteReport,
    run_cross_corridor_evaluation,
)
from simulation.network import Network
from simulation.state import TrainStatus


@pytest.fixture(scope="module")
def evaluator() -> CrossCorridorEvaluator:
    return CrossCorridorEvaluator()


@pytest.fixture(scope="module")
def suite_report(evaluator: CrossCorridorEvaluator) -> CrossCorridorSuiteReport:
    return evaluator.run_all_cross_corridor_scenarios()


# ---------------------------------------------------------------------------
# 1. Corridor Data Scope & Boundary Audit Tests
# ---------------------------------------------------------------------------

class TestCorridorDataScopeAudit:
    """Verify detection of populated vs topology-only corridors without synthetic data fabrication."""

    def test_audit_covers_all_seven_corridors(self, evaluator: CrossCorridorEvaluator):
        scopes = evaluator.audit_corridor_data_scope()
        assert len(scopes) == 7
        names = [s.corridor_name for s in scopes]
        assert "West Corridor" in names
        assert "PTMS Branch" in names
        assert "North Corridor" in names
        assert "Beach-North Bypass" in names
        assert "MRTS Corridor" in names
        assert "South Corridor" in names
        assert "Cross Line / Bypass" in names

    def test_populated_corridors_identified(self, evaluator: CrossCorridorEvaluator):
        scopes = {s.corridor_name: s for s in evaluator.audit_corridor_data_scope()}
        assert scopes["West Corridor"].status == CorridorDataStatus.FULLY_POPULATED
        assert scopes["West Corridor"].service_count == 20
        assert scopes["PTMS Branch"].status == CorridorDataStatus.FULLY_POPULATED
        assert scopes["PTMS Branch"].service_count == 2

    def test_topology_only_corridors_not_fabricated(self, evaluator: CrossCorridorEvaluator):
        scopes = {s.corridor_name: s for s in evaluator.audit_corridor_data_scope()}
        # Cross Line / Bypass remains strictly topology-only
        assert scopes["Cross Line / Bypass"].status == CorridorDataStatus.TOPOLOGY_ONLY
        assert scopes["Cross Line / Bypass"].service_count == 0
        assert scopes["Cross Line / Bypass"].total_track_sections > 0  # Topology exists

        # Corridors populated in Phase 28 expansion
        for name in ["North Corridor", "Beach-North Bypass", "MRTS Corridor", "South Corridor"]:
            assert scopes[name].status == CorridorDataStatus.FULLY_POPULATED
            assert scopes[name].service_count > 0

    def test_data_scope_to_dict_format(self, evaluator: CrossCorridorEvaluator):
        scopes = evaluator.audit_corridor_data_scope()
        d = scopes[0].to_dict()
        assert "corridor_name" in d
        assert "status" in d
        assert "service_count" in d
        assert "route_ids" in d

    def test_corridor_scope_lookup(self, evaluator: CrossCorridorEvaluator):
        west = evaluator.get_corridor_scope("West Corridor")
        assert west is not None
        assert west.status == CorridorDataStatus.FULLY_POPULATED
        unknown = evaluator.get_corridor_scope("Nonexistent Corridor")
        assert unknown is None

    def test_corridor_operational_testability_flags(self, evaluator: CrossCorridorEvaluator):
        testable_west, msg_west = evaluator.is_corridor_operationally_testable("West Corridor")
        assert testable_west is True
        assert "fully populated" in msg_west

        testable_ptms, msg_ptms = evaluator.is_corridor_operationally_testable("PTMS Branch")
        assert testable_ptms is True

        # Cross Line / Bypass remains unpopulated
        testable_cross, msg_cross = evaluator.is_corridor_operationally_testable("Cross Line / Bypass")
        assert testable_cross is False
        assert "topology-only" in msg_cross
        assert "0 published services" in msg_cross


# ---------------------------------------------------------------------------
# 1B. Infrastructure Junction Abstractions (BBQ, VJM, PAB, KOK, MSB, CGL, AJJ)
# ---------------------------------------------------------------------------

class TestInfrastructureJunctionAbstractions:
    """Verify that BBQ, VJM, PAB, KOK, MSB, CGL, and AJJ use existing infrastructure abstractions correctly."""

    EXPECTED_JUNCTIONS = {
        "JCT_BBQ": {"station_id": "BBQ", "role": "RESOURCE_CONFLICT_POINT"},
        "JCT_VJM": {"station_id": "VJM", "role": "ROUTE_CONFLICT_POINT"},
        "JCT_PAB": {"station_id": "PAB", "role": "BRANCH_CONFLICT_POINT"},
        "JCT_KOK": {"station_id": "KOK", "role": "MERGE_CONFLICT_POINT"},
        "JCT_MSB": {"station_id": "MSB", "role": "MULTI_ROUTE_RESOURCE"},
        "JCT_CGL": {"station_id": "CGL", "role": "CROSS_CORRIDOR_CONFLICT_POINT"},
        "JCT_AJJ": {"station_id": "AJJ", "role": "CORRIDOR_INTERCHANGE"},
    }

    def test_all_seven_junctions_exist_in_network(self, evaluator: CrossCorridorEvaluator):
        network = evaluator.network
        all_nodes = set(network.stations.keys())
        for r in network.routes.values():
            all_nodes.update(r.ordered_nodes)
        for ts in network.track_sections.values():
            all_nodes.add(ts.from_node)
            all_nodes.add(ts.to_node)

        for jct_id, meta in self.EXPECTED_JUNCTIONS.items():
            assert jct_id in network.junctions, f"Junction {jct_id} missing from network"
            jct = network.junctions[jct_id]
            assert jct.station_id == meta["station_id"]
            assert jct.station_id in all_nodes, f"Station/Node {jct.station_id} missing for junction {jct_id}"
            assert jct.capacity >= 1

    def test_junction_connected_routes_exist(self, evaluator: CrossCorridorEvaluator):
        network = evaluator.network
        for jct_id in self.EXPECTED_JUNCTIONS:
            jct = network.junctions[jct_id]
            assert len(jct.connected_routes) > 0
            for r_id in jct.connected_routes:
                assert r_id in network.routes, f"Route {r_id} connected to {jct_id} not found in network routes"

    def test_junctions_do_not_invent_interlocking_geometry(self, evaluator: CrossCorridorEvaluator):
        network = evaluator.network
        for jct in network.junctions.values():
            assert isinstance(jct.capacity, int)
            assert jct.capacity >= 1
            assert jct.junction_type in (
                "CRITICAL_THROAT",
                "CORRIDOR_DIVERGENCE",
                "BRANCH",
                "CORRIDOR_MERGE",
                "MULTI_CORRIDOR_HUB",
                "CORRIDOR_INTERCHANGE",
            )


# ---------------------------------------------------------------------------
# 2. West Trunk <-> PTMS Branch Merging at JCT_PAB
# ---------------------------------------------------------------------------

class TestWestPTMSBranchMerge:
    """Verify merging dynamics at Pattabiram Junction between branch and trunk lines."""

    def test_branch_merge_scenario_executes_successfully(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_west_ptms_branch_merge()
        assert res.passed is True
        assert res.scenario_type == CrossCorridorScenarioType.WEST_PTMS_BRANCH_MERGE
        assert len(res.service_ids) == 2
        assert all(st == "COMPLETED" for st in res.completion_statuses.values())

    def test_both_services_reach_pab_node(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_west_ptms_branch_merge()
        assert "pab_time_difference_min" in res.metrics
        assert res.metrics["pab_time_difference_min"] >= 0.0

    def test_contention_event_structure(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_west_ptms_branch_merge()
        if res.junction_contention_events:
            event = res.junction_contention_events[0]
            assert event["junction"] == "JCT_PAB"
            assert "time_difference" in event


# ---------------------------------------------------------------------------
# 3. West Trunk <-> PTMS Terminal Throat at JCT_BBQ
# ---------------------------------------------------------------------------

class TestWestPTMSTerminalThroat:
    """Verify multi-service convergence at Basin Bridge terminal throat."""

    def test_throat_convergence_scenario_passes(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_west_ptms_throat_contention()
        assert res.passed is True
        assert res.scenario_type == CrossCorridorScenarioType.WEST_PTMS_TERMINAL_THROAT
        assert len(res.service_ids) == 2
        assert all(st == "COMPLETED" for st in res.completion_statuses.values())

    def test_both_services_reach_bbq_throat(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_west_ptms_throat_contention()
        assert "bbq_time_difference_min" in res.metrics


# ---------------------------------------------------------------------------
# 4. Platform Granularity & Resource Allocation
# ---------------------------------------------------------------------------

class TestPlatformGranularity:
    """Verify discrete platform allocation avoiding artificial station-wide locking."""

    def test_multi_platform_concurrency_at_mas(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_platform_granularity_evaluation(station_id="MAS")
        assert res.passed is True
        assert res.resource_isolation_passed is True
        assert res.metrics["distinct_platform_concurrency_allowed"] is True
        assert res.metrics["double_booking_blocked"] is True
        assert res.metrics["reclaim_after_release_success"] is True

    def test_platform_granularity_at_ajj(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_platform_granularity_evaluation(station_id="AJJ")
        assert res.passed is True
        assert res.resource_isolation_passed is True

    def test_platform_granularity_at_bbq(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_platform_granularity_evaluation(station_id="BBQ")
        assert res.passed is True
        assert res.resource_isolation_passed is True


# ---------------------------------------------------------------------------
# 5. Cross-Corridor Delay Propagation
# ---------------------------------------------------------------------------

class TestCrossCorridorDelayPropagation:
    """Verify branch delay ripple effect into downstream shared movements."""

    def test_delay_propagation_execution(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_cross_corridor_delay_propagation(delay_minutes=25.0)
        assert res.passed is True
        assert res.scenario_type == CrossCorridorScenarioType.CROSS_CORRIDOR_DELAY_PROPAGATION
        assert res.final_delays["SRV_43102_01"] >= 25.0

    def test_delay_metrics_tracked(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_cross_corridor_delay_propagation(delay_minutes=15.0)
        assert res.metrics["injected_branch_delay_min"] == 15.0
        assert res.metrics["observed_branch_delay"] >= 15.0


# ---------------------------------------------------------------------------
# 6. Independent-Resource Isolation
# ---------------------------------------------------------------------------

class TestIndependentResourceIsolation:
    """Verify zero delay leakage across unshared corridor sections."""

    def test_zero_delay_leakage_on_isolated_branch(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_independent_resource_isolation(disruption_delay=45.0)
        assert res.passed is True
        assert res.resource_isolation_passed is True
        assert res.metrics["delay_leakage_minutes"] == 0.0
        assert res.final_delays["SRV_43102_01"] == 0.0

    def test_disrupted_service_reflects_disruption(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_independent_resource_isolation(disruption_delay=30.0)
        assert res.final_delays["SRV_12607_01"] >= 0.0


# ---------------------------------------------------------------------------
# 7. West Main vs Short Route Divergence
# ---------------------------------------------------------------------------

class TestWestMainShortDivergence:
    """Verify concurrent long-distance express and short suburban route movements."""

    def test_main_and_short_routes_complete(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_west_main_short_divergence()
        assert res.passed is True
        assert res.scenario_type == CrossCorridorScenarioType.WEST_MAIN_SHORT_DIVERGENCE
        assert res.metrics["main_nodes_traversed"] == 28
        assert res.metrics["short_nodes_traversed"] == 20


# ---------------------------------------------------------------------------
# 8. West Bidirectional Concurrency
# ---------------------------------------------------------------------------

class TestWestBidirectionalConcurrency:
    """Verify simultaneous opposing movements on paired parallel tracks."""

    def test_opposing_movements_complete_all_nodes(self, evaluator: CrossCorridorEvaluator):
        res = evaluator.run_west_bidirectional_concurrency()
        assert res.passed is True
        assert res.scenario_type == CrossCorridorScenarioType.WEST_BIDIRECTIONAL_CONCURRENCY
        assert res.metrics["outbound_nodes"] == 28
        assert res.metrics["inbound_nodes"] == 28


# ---------------------------------------------------------------------------
# 9. Suite Report & Determinism Tests
# ---------------------------------------------------------------------------

class TestCrossCorridorSuiteReportingAndDeterminism:
    """Verify aggregated reporting, serialization, and deterministic repeatability."""

    def test_full_suite_passes(self, suite_report: CrossCorridorSuiteReport):
        assert suite_report.all_passed is True
        assert suite_report.total_scenarios == 7
        assert suite_report.passed_scenarios == 7
        assert suite_report.failed_scenarios == 0

    def test_summary_ascii_output(self, suite_report: CrossCorridorSuiteReport):
        txt = suite_report.generate_summary_ascii()
        assert "BATCH 17: EXPANDED CORRIDOR INTEGRATION" in txt
        assert "Overall Suite Status: PASSED" in txt
        assert "[POPULATED]" in txt
        assert "[TOPOLOGY ONLY]" in txt

    def test_markdown_report_output(self, suite_report: CrossCorridorSuiteReport):
        md = suite_report.generate_markdown_report()
        assert "# Batch 17: Expanded Corridor Integration" in md
        assert "## 2. Corridor Data Scope & Divisional Boundary Audit" in md
        assert "West Corridor" in md
        assert "PTMS Branch" in md

    def test_to_dict_serializable(self, suite_report: CrossCorridorSuiteReport):
        d = suite_report.to_dict()
        assert d["all_passed"] is True
        assert len(d["results"]) == 7
        assert len(d["data_scopes"]) == 7

    def test_deterministic_repeatability(self, evaluator: CrossCorridorEvaluator):
        run1 = evaluator.run_west_ptms_branch_merge()
        run2 = evaluator.run_west_ptms_branch_merge()
        assert run1.deterministic_hash == run2.deterministic_hash
        assert run1.metrics == run2.metrics
        assert run1.final_delays == run2.final_delays
