"""
scripts/smoke_test_api.py
~~~~~~~~~~~~~~~~~~~~~~~~~
End-to-end API smoke test exercising every endpoint in the Railway Traffic Optimizer backend.
"""

import sys
import os
import json

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from starlette.testclient import TestClient
from backend.app.main import app


def run_smoke_test():
    print("=" * 80)
    print("RAILWAY TRAFFIC OPTIMIZER - API SMOKE TEST")
    print("=" * 80)

    client = TestClient(app)
    results = []

    def check(name, status, condition, details=""):
        res = "PASS" if condition else "FAIL"
        print(f"[{res}] {name:<48} (Status: {status}) {details}")
        results.append((name, condition))

    # 1. Root
    resp = client.get("/")
    check("GET / (Root Metadata)", resp.status_code, resp.status_code == 200 and "version" in resp.json())

    # 2. Health
    resp = client.get("/api/v1/health")
    data = resp.json()
    net_status = data.get("network_status", {})
    check(
        "GET /api/v1/health",
        resp.status_code,
        resp.status_code == 200 and data.get("status") == "healthy" and net_status.get("datasets_intact") is True,
        f"status={data.get('status')}, datasets_intact={net_status.get('datasets_intact')}"
    )

    # 3. Network
    resp = client.get("/api/v1/network")
    net = resp.json()
    check(
        "GET /api/v1/network",
        resp.status_code,
        resp.status_code == 200 and net.get("active_service_count") == 40 and net.get("excluded_service_count") == 7,
        f"active={net.get('active_service_count')}, excluded={net.get('excluded_service_count')}, nodes={len(net.get('nodes', []))}"
    )

    # 4. Simulation State
    resp = client.get("/api/v1/simulation/state")
    state = resp.json()
    check(
        "GET /api/v1/simulation/state",
        resp.status_code,
        resp.status_code == 200 and "current_minute" in state,
        f"minute={state.get('current_minute')}, is_playing={state.get('is_playing')}"
    )

    # 5. Simulation Control (Pause & Seek)
    resp = client.post("/api/v1/simulation/control", json={"is_playing": False, "seek_minute": 380.0, "playback_speed": 2})
    check(
        "POST /api/v1/simulation/control",
        resp.status_code,
        resp.status_code == 200 and resp.json().get("current_minute") == 380.0,
        f"minute={resp.json().get('current_minute')}"
    )

    # 6. Disruption Event Injection
    event_payload = {
        "event_type": "SPEED_RESTRICTION",
        "track_section_id": "PER_PCW_MAIN_DOWN",
        "speed_limit_kmh": 20.0,
        "start_minute": 370.0,
        "end_minute": 420.0,
        "severity": "MAJOR",
        "description": "Smoke test speed restriction"
    }
    resp = client.post("/api/v1/simulation/events", json=event_payload)
    injected_event = resp.json()
    event_id = injected_event.get("id")
    check(
        "POST /api/v1/simulation/events (Inject)",
        resp.status_code,
        resp.status_code == 201 and event_id is not None,
        f"id={event_id}"
    )

    # 7. List Events
    resp = client.get("/api/v1/simulation/events")
    events = resp.json() if isinstance(resp.json(), list) else resp.json().get("events", [])
    check(
        "GET /api/v1/simulation/events",
        resp.status_code,
        resp.status_code == 200 and any(e.get("id") == event_id for e in events),
        f"count={len(events)}"
    )

    # 8. Re-optimization Proposal Generation
    resp = client.post("/api/v1/simulation/reoptimize")
    proposal_data = resp.json()
    proposal_id = proposal_data.get("proposal_id")
    check(
        "POST /api/v1/simulation/reoptimize",
        resp.status_code,
        resp.status_code == 200 and proposal_id is not None,
        f"proposal_id={proposal_id}, status={proposal_data.get('status')}"
    )

    # 9. Reject Proposal
    if proposal_id:
        resp = client.post(f"/api/v1/simulation/proposals/{proposal_id}/reject")
        check(
            "POST /api/v1/simulation/proposals/{id}/reject",
            resp.status_code,
            resp.status_code == 200 and resp.json().get("status") == "REJECTED",
            f"status={resp.json().get('status')}"
        )

    # 10. Delete Disruption Event
    if event_id:
        resp = client.delete(f"/api/v1/simulation/events/{event_id}")
        check(
            "DELETE /api/v1/simulation/events/{id}",
            resp.status_code,
            resp.status_code == 200,
            f"deleted={event_id}"
        )

    # 11. Simulation Reset
    resp = client.post("/api/v1/simulation/reset")
    reset_state = resp.json()
    check(
        "POST /api/v1/simulation/reset",
        resp.status_code,
        resp.status_code == 200 and reset_state.get("current_minute") == 360.0,
        f"reset_minute={reset_state.get('current_minute')}"
    )

    # 12. Ad-Hoc Simulation
    resp = client.post("/api/v1/simulate", json={"service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]})
    sim_data = resp.json()
    check(
        "POST /api/v1/simulate",
        resp.status_code,
        resp.status_code == 200 and sim_data.get("total_services_simulated") == 4 and "train_positions" in sim_data,
        f"simulated={sim_data.get('total_services_simulated')}, delay={sim_data.get('total_network_delay_minutes')}m"
    )

    # 13. CP-SAT Timetable Optimization
    resp = client.post("/api/v1/optimize", json={"service_ids": ["SRV_12607_01", "SRV_12609_01"]})
    opt_data = resp.json()
    check(
        "POST /api/v1/optimize",
        resp.status_code,
        resp.status_code == 200 and opt_data.get("solution_available") is True,
        f"solver_status={opt_data.get('solver_status')}, solve_time={opt_data.get('solve_time_seconds')}s"
    )

    # 14. What-If Disruption Scenario (Feasible)
    resp = client.post("/api/v1/what-if", json={
        "service_ids": ["SRV_12607_01", "SRV_12609_01"],
        "departure_delays": {"SRV_12607_01": 15.0}
    })
    what_if_data = resp.json()
    check(
        "POST /api/v1/what-if (Feasible)",
        resp.status_code,
        resp.status_code == 200 and what_if_data.get("solution_available") is True,
        f"baseline={what_if_data.get('total_baseline_delay_minutes')}m, opt={what_if_data.get('total_optimized_delay_minutes')}m"
    )

    # 15. What-If Disruption Scenario (Infeasible Fallback)
    resp = client.post("/api/v1/what-if", json={
        "service_ids": ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01"],
        "blocked_sections": ["PER_PCW_SUBURBAN_DOWN", "PER_PCW_MAIN_DOWN"]
    })
    infeas_data = resp.json()
    check(
        "POST /api/v1/what-if (Infeasible Fallback)",
        resp.status_code,
        resp.status_code == 200 and infeas_data.get("solution_available") is False and infeas_data.get("total_optimized_delay_minutes") is None,
        f"solution_available={infeas_data.get('solution_available')}, opt_delay={infeas_data.get('total_optimized_delay_minutes')}"
    )

    # 16. SSE Stream Check (Async Generator Verification)
    try:
        import asyncio
        from backend.app.runtime_engine import get_live_engine

        async def test_sse():
            engine = get_live_engine()
            gen = engine.sse_event_stream()
            frame = await gen.__anext__()
            await gen.aclose()
            return frame

        frame = asyncio.run(test_sse())
        sse_ok = "event: connected" in frame and "data:" in frame
        check(
            "GET /api/v1/simulation/stream (SSE Generator)",
            200,
            sse_ok,
            f"frame: {repr(frame.strip()[:60])}"
        )
    except Exception as e:
        check("GET /api/v1/simulation/stream (SSE Generator)", 500, False, str(e))

    print("=" * 80)
    passed_count = sum(1 for _, ok in results if ok)
    total_count = len(results)
    print(f"RESULTS: {passed_count}/{total_count} checks passed.")
    print("=" * 80)

    if passed_count != total_count:
        sys.exit(1)


if __name__ == "__main__":
    run_smoke_test()
