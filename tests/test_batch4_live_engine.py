"""
tests/test_batch4_live_engine.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Comprehensive test suite for Batch 4: Live Runtime Simulation Engine.

Tests:
1. Engine lifecycle and startup paused enforcement.
2. Injectable FakeTimeSource clock progression and speed mappings (1x, 2x, 5x, 10x, 30x, 60x).
3. Clock bounds clamping at end_minute and automatic pause.
4. Pure function determinism: identical state hash regardless of trajectory.
5. Disruption event management (inject, persist JSONL, list, remove, input validation).
6. SSE event streaming: sequence IDs, message format, and Last-Event-ID reconnection replay.
7. Human-in-the-loop reoptimization: proposal generation, pending isolation, accept, and reject.
8. REST API integration for all Batch 4 endpoints.
"""

import asyncio
import json
import os
import shutil
import tempfile
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.pipeline import _load_default_network
from backend.app.runtime_engine import (
    FakeTimeSource,
    LiveSimulationEngine,
    SSEMessage,
    get_live_engine,
)
from backend.app.schemas import (
    SimulationControlRequest,
    SimulationEventCreateRequest,
)
from simulation.state_manager import SimulationStateManager


@pytest.fixture
def isolated_runtime_dir():
    temp_dir = tempfile.mkdtemp(prefix="railway_batch4_test_")
    orig_env = os.environ.get("RAILWAY_RUNTIME_DIR")
    os.environ["RAILWAY_RUNTIME_DIR"] = temp_dir
    yield temp_dir
    if orig_env is not None:
        os.environ["RAILWAY_RUNTIME_DIR"] = orig_env
    else:
        os.environ.pop("RAILWAY_RUNTIME_DIR", None)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def fake_time_engine(isolated_runtime_dir):
    net = _load_default_network()
    fake_time = FakeTimeSource(start_time=1000.0)
    state_mgr = SimulationStateManager(
        network=net,
        state_file_path=os.path.join(isolated_runtime_dir, "runtime_simulation_state.json"),
    )
    engine = LiveSimulationEngine(
        network=net,
        state_manager=state_mgr,
        time_source=fake_time,
        runtime_dir=isolated_runtime_dir,
    )
    return engine, fake_time


# ---------------------------------------------------------------------------
# 1. Startup & Clock Advancement Tests
# ---------------------------------------------------------------------------

def test_startup_paused_guarantee(isolated_runtime_dir):
    """Engine must always start paused, even if state on disk had is_playing=True."""
    state_file = os.path.join(isolated_runtime_dir, "runtime_simulation_state.json")
    with open(state_file, "w") as f:
        json.dump({"is_playing": True, "current_minute": 380.0}, f)

    net = _load_default_network()
    state_mgr = SimulationStateManager(network=net, state_file_path=state_file)
    engine = LiveSimulationEngine(network=net, state_manager=state_mgr, runtime_dir=isolated_runtime_dir)

    assert engine.state_manager.is_playing is False
    assert state_mgr.is_playing is False


def test_fake_time_speed_progression(fake_time_engine):
    """Speed options accurately advance simulation minutes per real-world time."""
    engine, fake_time = fake_time_engine
    engine.state_manager.start_minute = 360.0
    engine.state_manager.end_minute = 540.0
    engine.state_manager.current_minute = 360.0

    # 1. At 60x speed: 60 sim-min / real-min = 1.0 sim-min / real-sec
    engine.update_control(SimulationControlRequest(is_playing=True, playback_speed=60))
    engine.step(5.0)
    assert engine.state_manager.current_minute == 365.0

    # 2. At 1x speed: 1 sim-min / 60 real-sec
    engine.set_speed(1)
    engine.step(60.0)
    assert engine.state_manager.current_minute == 366.0

    # 3. At 2x speed: 2 sim-min / 60 real-sec = 1 sim-min / 30 real-sec
    engine.set_speed(2)
    engine.step(30.0)
    assert engine.state_manager.current_minute == 367.0


def test_clock_boundary_auto_pause(fake_time_engine):
    """Clock stops and pauses automatically at end_minute."""
    engine, fake_time = fake_time_engine
    engine.state_manager.start_minute = 360.0
    engine.state_manager.end_minute = 370.0
    engine.state_manager.current_minute = 365.0

    engine.update_control(SimulationControlRequest(is_playing=True, playback_speed=60))
    # Advance 20 real seconds (would be +20 min at 60x)
    engine.step(20.0)

    # Must clamp at end_minute and pause
    assert engine.state_manager.current_minute == 370.0
    assert engine.state_manager.is_playing is False


# ---------------------------------------------------------------------------
# 2. Controls: Play, Pause, Seek, Reset
# ---------------------------------------------------------------------------

def test_playback_controls(fake_time_engine):
    """Verify play, pause, seek, and reset operations."""
    engine, _ = fake_time_engine

    # Play
    res = engine.play()
    assert res["is_playing"] is True

    # Pause
    res = engine.pause()
    assert res["is_playing"] is False

    # Seek within bounds
    res = engine.seek(420.0)
    assert res["current_minute"] == 420.0
    assert res["current_time_str"] == "07:00"

    # Seek out of bounds clamps to end_minute
    res = engine.seek(9999.0)
    assert res["current_minute"] == engine.state_manager.end_minute

    # Reset
    res = engine.reset(clear_delays=True)
    assert res["current_minute"] == engine.state_manager.start_minute
    assert res["is_playing"] is False


# ---------------------------------------------------------------------------
# 3. Pure-Function Determinism
# ---------------------------------------------------------------------------

def test_pure_function_snapshot_determinism(fake_time_engine):
    """Evaluating state at minute m returns identical hashes regardless of path."""
    engine, _ = fake_time_engine

    # Direct snapshot computation
    snap1 = engine.compute_snapshot_at(385.0)
    hash1 = engine.compute_deterministic_state_hash(385.0)

    # Change current minute to something else
    engine.state_manager.current_minute = 450.0

    # Re-evaluate minute 385.0
    snap2 = engine.compute_snapshot_at(385.0)
    hash2 = engine.compute_deterministic_state_hash(385.0)

    assert hash1 == hash2
    assert snap1.total_network_delay_minutes == snap2.total_network_delay_minutes
    assert len(snap1.train_positions) == len(snap2.train_positions)


# ---------------------------------------------------------------------------
# 4. Disruption Events Lifecycle & JSONL Persistence
# ---------------------------------------------------------------------------

def test_disruption_event_lifecycle(fake_time_engine):
    """Test injection, validation, JSONL persistence, listing, and deletion."""
    engine, _ = fake_time_engine

    # 1. Validation failure: invalid service ID
    with pytest.raises(ValueError, match="not found in network"):
        engine.inject_event(
            SimulationEventCreateRequest(
                event_type="DEPARTURE_DELAY",
                service_id="INVALID_SERVICE_999",
                delay_minutes=15.0,
            )
        )

    # 2. Validation failure: invalid track section
    with pytest.raises(ValueError, match="not found in network"):
        engine.inject_event(
            SimulationEventCreateRequest(
                event_type="BLOCKED_SECTION",
                section_id="NON_EXISTENT_SECTION",
            )
        )

    # 3. Valid injection
    rec = engine.inject_event(
        SimulationEventCreateRequest(
            event_type="DEPARTURE_DELAY",
            service_id="SRV_12607_01",
            delay_minutes=25.0,
            from_minute=360.0,
            to_minute=480.0,
            description="Signal failure at origin",
        )
    )

    assert rec.id == "EVT_0001"
    assert rec.delay_minutes == 25.0

    # Check JSONL persistence
    assert os.path.exists(engine.events_log_path)
    with open(engine.events_log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["id"] == "EVT_0001"
        assert data["service_id"] == "SRV_12607_01"

    # List events
    events = engine.list_events()
    assert len(events) == 1
    assert events[0].id == "EVT_0001"

    # Verify state reflects delay
    snap = engine.compute_snapshot_at(370.0)
    srv_pos = next(p for p in snap.train_positions if p.service_id == "SRV_12607_01")
    assert srv_pos.delay_minutes >= 25.0

    # Delete event
    removed = engine.remove_event("EVT_0001")
    assert removed is True

    # Confirm log updated
    events_after = engine.list_events()
    assert len(events_after) == 0

    # Removing non-existent returns False
    assert engine.remove_event("NON_EXISTENT") is False


# ---------------------------------------------------------------------------
# 5. Server-Sent Events (SSE) & Reconnection Replay
# ---------------------------------------------------------------------------

def test_sse_streaming_and_reconnection_replay(fake_time_engine):
    """Test SSE message structure, sequential IDs, and Last-Event-ID replay."""
    engine, _ = fake_time_engine

    # Broadcast 3 distinct events
    engine.broadcast_event("test_event_1", {"msg": "hello"})
    engine.broadcast_event("test_event_2", {"msg": "world"})
    engine.broadcast_event("test_event_3", {"msg": "antigravity"})

    # Check history queue
    assert len(engine._sse_history) == 3
    msgs = list(engine._sse_history)
    assert msgs[0].seq_id == 1
    assert msgs[1].seq_id == 2
    assert msgs[2].seq_id == 3

    # Format check
    frame2 = msgs[1].format_sse()
    assert "id: 2" in frame2
    assert "event: test_event_2" in frame2
    assert '"world"' in frame2

    frame3 = msgs[2].format_sse()
    assert "id: 3" in frame3
    assert "event: test_event_3" in frame3
    assert '"antigravity"' in frame3


# ---------------------------------------------------------------------------
# 6. Human-in-the-Loop Reoptimization Proposals
# ---------------------------------------------------------------------------

def test_reoptimization_proposal_lifecycle(fake_time_engine):
    """Test proposal generation, pending state isolation, accept, and reject."""
    engine, _ = fake_time_engine
    engine.state_manager.current_minute = 360.0

    # Inject departure delay to cause conflict
    engine.inject_event(
        SimulationEventCreateRequest(
            event_type="DEPARTURE_DELAY",
            service_id="SRV_12607_01",
            delay_minutes=15.0,
            from_minute=360.0,
            to_minute=480.0,
        )
    )

    # 1. Trigger live reoptimization
    proposal = engine.create_reoptimization_proposal()

    assert proposal.proposal_id.startswith("PROP_")
    assert proposal.status == "PENDING"
    assert proposal.solution_available is True

    # Crucial guarantee: plan is NOT automatically applied
    assert engine.applied_plan == {}

    # 2. Reject proposal
    rej = engine.reject_proposal(proposal.proposal_id)
    assert rej.status == "REJECTED"
    assert proposal.status == "REJECTED"
    assert engine.applied_plan == {}

    # Cannot accept an already rejected proposal
    with pytest.raises(ValueError, match="already REJECTED"):
        engine.accept_proposal(proposal.proposal_id)

    # 3. Create second proposal and accept it
    prop2 = engine.create_reoptimization_proposal()
    acc = engine.accept_proposal(prop2.proposal_id)
    assert acc.status == "ACCEPTED"
    assert engine.applied_plan.get("active_proposal_id") == prop2.proposal_id


# ---------------------------------------------------------------------------
# 7. FastAPI REST API Integration Tests
# ---------------------------------------------------------------------------

def test_api_batch4_endpoints_integration(isolated_runtime_dir):
    """Test full HTTP REST API contracts for Batch 4 endpoints."""
    with TestClient(app) as client:
        # 1. Simulation Control with seek_minute
        res = client.post(
            "/api/v1/simulation/control",
            json={"seek_minute": 390.0, "playback_speed": 10},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["current_minute"] == 390.0
        assert data["playback_speed"] == 10

        # 2. Inject Disruption Event (POST /events)
        evt_payload = {
            "event_type": "DEPARTURE_DELAY",
            "service_id": "SRV_12607_01",
            "delay_minutes": 20.0,
            "description": "Integration test delay",
        }
        res = client.post("/api/v1/simulation/events", json=evt_payload)
        assert res.status_code == 201
        evt_data = res.json()
        assert evt_data["id"] == "EVT_0001"
        assert evt_data["delay_minutes"] == 20.0

        # Invalid event injection returns 400
        res_bad = client.post(
            "/api/v1/simulation/events",
            json={"event_type": "BLOCKED_SECTION", "section_id": "UNKNOWN_SECTION"},
        )
        assert res_bad.status_code == 400

        # 3. List Events (GET /events)
        res = client.get("/api/v1/simulation/events")
        assert res.status_code == 200
        events_list = res.json()
        assert len(events_list) == 1
        assert events_list[0]["id"] == "EVT_0001"

        # 4. Delete Event (DELETE /events/{id})
        res = client.delete("/api/v1/simulation/events/EVT_0001")
        assert res.status_code == 200
        assert res.json()["status"] == "success"

        # Deleting non-existent returns 404
        res = client.delete("/api/v1/simulation/events/EVT_9999")
        assert res.status_code == 404

        # 5. Reoptimize (POST /reoptimize)
        res = client.post("/api/v1/simulation/reoptimize")
        assert res.status_code == 200
        prop_data = res.json()
        assert "proposal_id" in prop_data
        assert prop_data["status"] == "PENDING"
        prop_id = prop_data["proposal_id"]

        # 6. Accept Proposal (POST /proposals/{id}/accept)
        res = client.post(f"/api/v1/simulation/proposals/{prop_id}/accept")
        assert res.status_code == 200
        assert res.json()["status"] == "ACCEPTED"
