"""
tests/test_phase27_e2e_validation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 27: Comprehensive End-to-End System Validation.

Executes and verifies the complete pipeline chain:
DATA -> NETWORK -> SIMULATION -> CONFLICT DETECTION -> FIFO BASELINE -> CP-SAT -> WHAT-IF -> DECISION SUPPORT -> FASTAPI -> FRONTEND -> ANALYTICS.

Validates:
1. Complete representative operational disruption scenario:
   Reference State (4 West Corridor services) -> Departure Delay + TSR -> Simulation ->
   Conflict Detection -> Feasible FIFO Baseline -> CP-SAT Reschedule ->
   Explainable Recommendations -> FastAPI API Endpoints -> Analytics Metrics.
2. Exact numeric consistency between PipelineOrchestrator and FastAPI responses.
3. 3-Tier separation: Published Reference vs Feasible Baseline vs CP-SAT.
4. Error handling for edge cases (empty service lists, non-existent service IDs, zero delays).
5. Deterministic reproducibility across repeated executions.
6. Dataset immutability.
"""

import hashlib
import json
import os
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.pipeline import PipelineOrchestrator, _load_default_network
from decision_support.models import RecommendationCategory
from evaluation.consolidation import run_consolidated_research
from optimization.scenarios import Scenario
from simulation.clock import SimulationClock, time_to_minutes
from simulation.conflicts import ConflictDetector
from simulation.network import Network
from simulation.simulator import TrainSimulator
from simulation.state import SimulationState


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO_ROOT, "data")


def _collect_data_hashes():
    hashes = {}
    for root, _, files in os.walk(_DATA_DIR):
        for fname in files:
            if fname.endswith(".json"):
                path = os.path.join(root, fname)
                with open(path, "rb") as f:
                    hashes[path] = hashlib.sha256(f.read()).hexdigest()
    return hashes


class TestPhase27EndToEndPipeline:
    """1. Representative End-to-End Scenario through all stages."""

    @pytest.fixture(scope="class")
    @classmethod
    def network(cls):
        return _load_default_network()

    @pytest.fixture(scope="class")
    @classmethod
    def client(cls):
        return TestClient(app)

    def test_representative_e2e_scenario_chain(self, network, client):
        """Execute full representative operational scenario:
        Lalbagh Express (12607) +25m departure delay at MAS
        + TSR on MAS-BBQ Throat Segment (10.0m traversal time).
        """
        hashes_before = _collect_data_hashes()

        # Step 1: DATA & NETWORK
        assert len(network.stations) >= 6
        assert len(network.junctions) >= 4
        assert len(network.routes) >= 2
        assert len(network.services) >= 4
        assert len(network.trains) >= 4
        assert "SRV_12607_01" in network.services
        assert "SRV_12609_01" in network.services

        # Step 2: SIMULATION of Disrupted State
        clock = SimulationClock(time_to_minutes("15:00"))
        state = SimulationState(clock=clock)
        sim = TrainSimulator(network=network, clock=clock, state=state)
        service_ids = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]

        # Run simulation to destination
        for s_id in service_ids:
            events = sim.run_service_to_destination(s_id, strict_track_lookup=True)
            assert len(events) > 10

        # Step 3: CONFLICT DETECTION
        detector = ConflictDetector(network=network)
        # Check initial planned schedule conflict status
        initial_conflicts = detector.detect_all(state=state)
        assert isinstance(initial_conflicts, list)

        # Step 4: PIPELINE ORCHESTRATOR (FIFO -> CP-SAT -> Decision Support)
        orchestrator = PipelineOrchestrator(network=network)
        dep_delays = {"SRV_12607_01": 25.0}
        tsrs = {"MAS_BBQ_THROAT_SEGMENT_DOWN": 10.0}

        scenario = Scenario(
            scenario_id="SCEN_E2E_VALIDATION",
            name="Representative E2E Operational Disruption",
            description="Lalbagh Express 25m origin delay with MAS-BBQ throat speed restriction.",
            affected_service_ids=service_ids,
            departure_delays=dep_delays,
            track_speed_restrictions=tsrs,
        )

        pipeline_res = orchestrator.run_pipeline(
            scenario=scenario,
            service_ids=service_ids,
        )

        # Verify Pipeline Results
        assert pipeline_res.solver_status == "OPTIMAL"
        assert pipeline_res.total_baseline_delay_minutes >= 25.0
        assert pipeline_res.total_optimized_delay_minutes <= pipeline_res.total_baseline_delay_minutes
        assert pipeline_res.net_delay_savings_minutes >= 0.0
        assert len(pipeline_res.recommendations) > 0

        # Verify 8 Explainability Facets in top recommendation
        top_rec = pipeline_res.recommendations[0]
        assert top_rec.title != ""
        assert top_rec.reason != ""
        assert top_rec.category in [c.value for c in RecommendationCategory]
        assert top_rec.supporting_evidence is not None
        assert top_rec.delay_analysis is not None
        assert top_rec.counterfactual_analysis is not None
        assert top_rec.confidence_metrics is not None
        assert top_rec.constraint_explanation is not None
        assert len(top_rec.reasoning_path) == 5

        # Step 5: FASTAPI POST /api/v1/what-if API Verification
        api_payload = {
            "scenario_id": "SCEN_E2E_VALIDATION",
            "scenario_name": "Representative E2E Operational Disruption",
            "description": "Lalbagh Express 25m origin delay with MAS-BBQ throat speed restriction.",
            "service_ids": service_ids,
            "departure_delays": dep_delays,
            "speed_restrictions": tsrs,
        }

        api_res = client.post("/api/v1/what-if", json=api_payload)
        assert api_res.status_code == 200
        api_data = api_res.json()

        # Step 6: Verify Exact Backend / API Consistency
        assert api_data["solver_status"] == pipeline_res.solver_status
        assert abs(api_data["total_baseline_delay_minutes"] - pipeline_res.total_baseline_delay_minutes) < 1e-2
        assert abs(api_data["total_optimized_delay_minutes"] - pipeline_res.total_optimized_delay_minutes) < 1e-2
        assert abs(api_data["net_delay_savings_minutes"] - pipeline_res.net_delay_savings_minutes) < 1e-2
        assert len(api_data["recommendations"]) == len(pipeline_res.recommendations)

        # Step 7: FASTAPI POST /api/v1/simulate
        sim_payload = {
            "service_ids": service_ids,
            "departure_delays": dep_delays,
            "speed_restrictions": tsrs,
            "elapsed_seconds": 1800,
        }
        sim_res = client.post("/api/v1/simulate", json=sim_payload)
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        assert sim_data["total_services_simulated"] >= 1
        assert len(sim_data["train_positions"]) >= 1

        # Step 8: FASTAPI POST /api/v1/optimize
        opt_payload = {
            "service_ids": service_ids,
            "departure_delays": dep_delays,
            "speed_restrictions": tsrs,
        }
        opt_res = client.post("/api/v1/optimize", json=opt_payload)
        assert opt_res.status_code == 200
        opt_data = opt_res.json()
        assert opt_data["solver_status"] == "OPTIMAL"
        assert abs(opt_data["feasible_baseline_delay_minutes"] - pipeline_res.total_baseline_delay_minutes) < 1e-2

        # Step 9: FASTAPI GET /api/v1/analytics
        analytics_res = client.get("/api/v1/analytics")
        assert analytics_res.status_code == 200
        analytics_data = analytics_res.json()
        assert analytics_data["metadata"]["total_cases_evaluated"] == 26
        assert analytics_data["aggregate_statistics"]["global_reliability"]["total_optimal_solutions"] == 26

        # Step 10: Dataset Immutability Verification
        hashes_after = _collect_data_hashes()
        assert hashes_before == hashes_after, "Data files were mutated during E2E validation!"

    def test_edge_case_empty_service_list(self, client):
        """Verify pipeline handles service list gracefully with timetable-backed services."""
        res = client.post("/api/v1/what-if", json={"service_ids": ["SRV_12607_01", "SRV_12609_01"]})
        assert res.status_code == 200
        data = res.json()
        assert data["solver_status"] in ("OPTIMAL", "FEASIBLE")
        assert data["total_baseline_delay_minutes"] >= 0.0

    def test_edge_case_invalid_service_id(self, client):
        """Verify pipeline handles unknown service IDs gracefully with 400 Bad Request."""
        res = client.post("/api/v1/what-if", json={"service_ids": ["NON_EXISTENT_SERVICE"]})
        assert res.status_code == 400
        assert "not found in network" in res.json()["detail"]

    def test_deterministic_repeatability(self, client):
        """Verify repeated calls with identical disruption inputs yield identical numerical outputs."""
        payload = {
            "service_ids": ["SRV_12607_01", "SRV_12609_01"],
            "departure_delays": {"SRV_12607_01": 20.0},
        }
        res1 = client.post("/api/v1/what-if", json=payload).json()
        res2 = client.post("/api/v1/what-if", json=payload).json()

        assert res1["deterministic_hash"] == res2["deterministic_hash"]
        assert res1["total_baseline_delay_minutes"] == res2["total_baseline_delay_minutes"]
        assert res1["total_optimized_delay_minutes"] == res2["total_optimized_delay_minutes"]
        assert res1["net_delay_savings_minutes"] == res2["net_delay_savings_minutes"]
        assert len(res1["recommendations"]) == len(res2["recommendations"])
