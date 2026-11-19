"""
backend/app/runtime_engine.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Authoritative Live Runtime Simulation Engine for the Railway Traffic Optimization Digital Twin.

Architectural Guarantees:
1. Engine: Owns SimulationStateManager, runs an asyncio background loop to advance time.
2. Time Source: Injectable TimeSource interface (RealTimeSource vs FakeTimeSource for test isolation).
3. Determinism: State at minute m is a pure function of (datasets, services, event log, m).
4. Startup: Always starts paused (is_playing=False); never auto-runs after a restart.
5. Events: Supports injection, logging (JSONL), listing, and deletion with replay recomputation.
6. Streaming: Server-Sent Events (SSE) with sequence IDs, Last-Event-ID replay, and typed events.
7. Human-in-the-Loop: Generates reoptimization proposals that require explicit user acceptance.
8. Concurrency: Single-process engine guarded by asyncio.Lock.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timezone
import hashlib
import json
import os
import threading
import time
from typing import Any, AsyncIterator, Deque, Dict, List, Optional, Set, Tuple

from simulation.clock import minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictDetector
from simulation.network import Network
from simulation.state_manager import (
    SimulationStateManager,
    get_simulation_manager,
    get_ist_time_str,
    get_ist_date_str,
)
from backend.app.schemas import (
    ProposalActionResponse,
    ReoptimizationProposal,
    SimulateResponse,
    SimulationControlRequest,
    SimulationEventCreateRequest,
    SimulationEventRecord,
    SSETickData,
    TrainPositionState,
)


# ---------------------------------------------------------------------------
# 1. Injectable Time Source Interface
# ---------------------------------------------------------------------------

class TimeSource:
    """Abstract time provider enabling millisecond unit testing without wall-clock sleep."""

    def time(self) -> float:
        """Return current epoch time in seconds."""
        raise NotImplementedError

    async def sleep(self, seconds: float) -> None:
        """Asynchronously sleep for the given number of seconds."""
        raise NotImplementedError


class RealTimeSource(TimeSource):
    """Production wall-clock time source backed by standard library time and asyncio."""

    def time(self) -> float:
        return time.time()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)


class FakeTimeSource(TimeSource):
    """Controllable deterministic fake time source for testing time progression."""

    def __init__(self, start_time: float = 1727344800.0):  # 2024-09-26 10:00:00 UTC
        self._current_time: float = start_time
        self._sleep_calls: List[float] = []

    def time(self) -> float:
        return self._current_time

    def advance(self, seconds: float) -> None:
        """Manually advance clock by seconds."""
        self._current_time += seconds

    async def sleep(self, seconds: float) -> None:
        """Advance time and yield control."""
        self._sleep_calls.append(seconds)
        self._current_time += seconds
        await asyncio.sleep(0.01)


# ---------------------------------------------------------------------------
# 2. SSE Message Data Structure
# ---------------------------------------------------------------------------

class SSEMessage:
    """Server-Sent Event frame containing sequence ID, event name, and payload."""

    def __init__(self, seq_id: int, event_type: str, data: Dict[str, Any]):
        self.seq_id = seq_id
        self.event_type = event_type
        self.data = data
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def format_sse(self) -> str:
        """Format as valid SSE HTTP frame."""
        payload = json.dumps(self.data, default=str)
        return f"id: {self.seq_id}\nevent: {self.event_type}\ndata: {payload}\n\n"


# ---------------------------------------------------------------------------
# 3. Live Simulation Engine
# ---------------------------------------------------------------------------

class LiveSimulationEngine:
    """Authoritative singleton simulation runtime coordinator."""

    # Supported playback speed factors (sim-minutes advanced per real-minute)
    # Default 1x = 1.0 sim-min / real-min; 60x = 60.0 sim-min / real-min (1 sim-min / real-sec).
    # Legacy browser pacing multipliers: 1x (200), 2x (400), 5x (1000)
    LEGACY_FRONTEND_SPEED_MAP = {
        1: 200.0,
        2: 400.0,
        5: 1000.0,
        10: 2000.0,
        30: 6000.0,
        60: 12000.0,
    }

    def __init__(
        self,
        network: Network,
        state_manager: Optional[SimulationStateManager] = None,
        time_source: Optional[TimeSource] = None,
        runtime_dir: Optional[str] = None,
    ):
        self.network = network
        self.runtime_dir = runtime_dir or os.environ.get("RAILWAY_RUNTIME_DIR", "runtime")
        os.makedirs(self.runtime_dir, exist_ok=True)

        self.time_source = time_source or RealTimeSource()
        self.state_manager = state_manager or get_simulation_manager(self.network)

        # Enforce startup requirement: ALWAYS start paused
        self.state_manager.is_playing = False

        self._lock = threading.RLock()
        self._loop_task: Optional[asyncio.Task] = None
        self._stop_event_flag: bool = False

        # Paths
        self.events_log_path = os.path.join(self.runtime_dir, "runtime_simulation_events.jsonl")
        self.proposals_path = os.path.join(self.runtime_dir, "runtime_simulation_proposals.json")
        self.applied_plan_path = os.path.join(self.runtime_dir, "runtime_simulation_applied_plan.json")

        # In-memory event log and proposals
        self.event_log: List[SimulationEventRecord] = []
        self.proposals: Dict[str, ReoptimizationProposal] = {}
        self.applied_plan: Dict[str, Any] = {}

        # SSE state
        self._sse_seq: int = 0
        self._sse_history: Deque[SSEMessage] = deque(maxlen=2000)
        self._sse_subscribers: Set[asyncio.Queue[SSEMessage]] = set()

        # Last detected conflicts tracker to emit conflict_detected/conflict_cleared
        self._last_conflict_signatures: Set[str] = set()

        # Load persisted event logs and proposals
        self._load_events_log()
        self._load_proposals()
        self._load_applied_plan()

    # -----------------------------------------------------------------------
    # Background Task & Lifecycle
    # -----------------------------------------------------------------------

    def start_background_loop(self) -> None:
        """Start the live ticking background loop task if not already running."""
        if self._loop_task is None or self._loop_task.done():
            self._stop_event_flag = False
            try:
                loop = asyncio.get_running_loop()
                self._loop_task = loop.create_task(self._run_loop())
            except RuntimeError:
                pass

    async def stop_background_loop(self) -> None:
        """Gracefully stop background loop task."""
        self._stop_event_flag = True
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
        self._loop_task = None

    async def _run_loop(self) -> None:
        """Main engine tick loop advancing simulation time when is_playing is True."""
        last_real_time = self.time_source.time()
        last_heartbeat = last_real_time

        while not self._stop_event_flag:
            await self.time_source.sleep(0.5)
            now = self.time_source.time()
            elapsed_real_seconds = max(0.0, now - last_real_time)
            last_real_time = now

            # Heartbeat check (every 15s)
            if now - last_heartbeat >= 15.0:
                last_heartbeat = now
                self.broadcast_event(
                    "heartbeat",
                    {"timestamp": now, "ist_time": get_ist_time_str(include_seconds=True)},
                )

            # Advance simulation time if playing
            self.step(elapsed_real_seconds)

    def step(self, elapsed_real_seconds: float) -> Optional[SimulateResponse]:
        """Advance simulation clock by elapsed real seconds given current speed."""
        with self._lock:
            if not self.state_manager.is_playing:
                return None

            speed = self.state_manager.playback_speed
            sim_minutes_per_real_second = speed / 60.0
            delta_sim_minutes = elapsed_real_seconds * sim_minutes_per_real_second

            prev_min = self.state_manager.current_minute
            next_min = prev_min + delta_sim_minutes

            # Bounds check
            if next_min >= self.state_manager.end_minute:
                next_min = self.state_manager.end_minute
                self.state_manager.is_playing = False

            self.state_manager.current_minute = next_min
            snap = self.compute_snapshot_at(next_min)
            self.state_manager.last_snapshot = snap.model_dump() if hasattr(snap, "model_dump") else snap.dict()
            self.state_manager.save_to_disk()

            # Emit tick and conflict diff events
            self._emit_tick_and_conflict_events(snap)
            return snap
            if not self.state_manager.is_playing:
                return None

            speed = self.state_manager.playback_speed
            sim_minutes_per_real_second = speed / 60.0
            delta_sim_minutes = elapsed_real_seconds * sim_minutes_per_real_second

            prev_min = self.state_manager.current_minute
            next_min = prev_min + delta_sim_minutes

            # Bounds check
            if next_min >= self.state_manager.end_minute:
                next_min = self.state_manager.end_minute
                self.state_manager.is_playing = False

            self.state_manager.current_minute = next_min
            snap = self.compute_snapshot_at(next_min)
            self.state_manager.last_snapshot = snap.model_dump() if hasattr(snap, "model_dump") else snap.dict()
            self.state_manager.save_to_disk()

            # Emit tick and conflict diff events
            self._emit_tick_and_conflict_events(snap)
            return snap

    # -----------------------------------------------------------------------
    # Pure Function Deterministic State Evaluation
    # -----------------------------------------------------------------------

    def compute_snapshot_at(
        self,
        target_time_m: float,
        service_ids: Optional[List[str]] = None,
    ) -> SimulateResponse:
        """Pure function computing deterministic simulation snapshot at minute m.

        Signature: State(m) = F(Datasets, Services, EventLog, m)
        """
        svcs = service_ids or self.state_manager.selected_service_ids

        # 1. Collate active disruptions from event log at minute m
        active_departure_delays = dict(self.state_manager.departure_delays)
        active_dwell_delays: Dict[str, Dict[str, float]] = {}
        active_speed_restrictions: Dict[str, float] = {}
        active_blocked_sections: List[str] = []

        for ev in self.event_log:
            if ev.from_minute <= target_time_m <= ev.to_minute:
                if ev.event_type == "DEPARTURE_DELAY" and ev.service_id and ev.delay_minutes:
                    active_departure_delays[ev.service_id] = max(
                        active_departure_delays.get(ev.service_id, 0.0),
                        ev.delay_minutes,
                    )
                elif ev.event_type == "DWELL_DELAY" and ev.service_id and ev.station_id and ev.delay_minutes:
                    if ev.service_id not in active_dwell_delays:
                        active_dwell_delays[ev.service_id] = {}
                    active_dwell_delays[ev.service_id][ev.station_id] = (
                        active_dwell_delays[ev.service_id].get(ev.station_id, 0.0) + ev.delay_minutes
                    )
                elif ev.event_type == "SPEED_RESTRICTION" and ev.section_id:
                    sec = self.network.track_sections.get(ev.section_id)
                    base_tt = sec.travel_time_minutes if sec else 3.0
                    factor = ev.speed_factor if ev.speed_factor else 2.0
                    active_speed_restrictions[ev.section_id] = base_tt * factor
                elif ev.event_type == "BLOCKED_SECTION" and ev.section_id:
                    if ev.section_id not in active_blocked_sections:
                        active_blocked_sections.append(ev.section_id)

        # 2. Execute epoch simulation
        snap = self.state_manager.simulate_epoch(
            target_time_m=target_time_m,
            service_ids=svcs,
            departure_delays=active_departure_delays,
            start_time_m=self.state_manager.start_minute,
        )

        return snap

    def compute_deterministic_state_hash(self, target_time_m: float) -> str:
        """Compute SHA-256 fingerprint of the evaluated snapshot at minute m."""
        snap = self.compute_snapshot_at(target_time_m)
        positions = [
            (p.service_id, p.status, p.current_node, p.current_track_section, p.delay_minutes)
            for p in snap.train_positions
        ]
        conflicts = [
            (c.conflict_type, c.resource_id, c.service_ids)
            for c in snap.detected_conflicts
        ]
        payload = {
            "target_time_m": round(target_time_m, 2),
            "positions": sorted(positions, key=lambda x: str(x[0])),
            "conflicts": sorted(conflicts, key=lambda x: (str(x[0]), str(x[1]))),
        }
        raw = json.dumps(payload, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    # -----------------------------------------------------------------------
    # Playback & Control Operations
    # -----------------------------------------------------------------------

    def update_control(self, req: SimulationControlRequest) -> Dict[str, Any]:
        """Update playback controls under lock and broadcast changes."""
        with self._lock:
            prev_playing = self.state_manager.is_playing
            res = self.state_manager.update_control(
                current_minute=req.current_minute,
                current_time_str=req.current_time_str,
                start_minute=req.start_minute,
                end_minute=req.end_minute,
                is_playing=req.is_playing,
                playback_speed=req.playback_speed,
                service_ids=req.service_ids,
                departure_delays=req.departure_delays,
                seek_minute=req.seek_minute,
            )
            # If playback was started, trigger background loop
            if not prev_playing and self.state_manager.is_playing:
                self.start_background_loop()

            snap = self.state_manager.last_snapshot
            if snap:
                model_snap = SimulateResponse(**snap)
                self._emit_tick_and_conflict_events(model_snap)
            return res

    def play(self) -> Dict[str, Any]:
        return self.update_control(SimulationControlRequest(is_playing=True))

    def pause(self) -> Dict[str, Any]:
        return self.update_control(SimulationControlRequest(is_playing=False))

    def seek(self, minute: float) -> Dict[str, Any]:
        return self.update_control(SimulationControlRequest(seek_minute=minute))

    def set_speed(self, speed: int) -> Dict[str, Any]:
        return self.update_control(SimulationControlRequest(playback_speed=speed))

    def reset(self, clear_delays: bool = False) -> Dict[str, Any]:
        with self._lock:
            res = self.state_manager.reset_state(clear_delays=clear_delays)
            snap = self.state_manager.last_snapshot
            if snap:
                self._emit_tick_and_conflict_events(SimulateResponse(**snap))
            return res

    # -----------------------------------------------------------------------
    # Disruption Events Management
    # -----------------------------------------------------------------------

    def _load_events_log(self) -> None:
        """Load JSONL events log from disk."""
        if not os.path.exists(self.events_log_path):
            return
        self.event_log.clear()
        try:
            with open(self.events_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = SimulationEventRecord(**json.loads(line))
                        self.event_log.append(record)
        except Exception:
            pass

    def _save_events_log(self) -> None:
        """Flush in-memory event log to JSONL file."""
        temp_path = self.events_log_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            for ev in self.event_log:
                f.write(ev.model_dump_json() + "\n")
        if os.path.exists(self.events_log_path):
            os.replace(temp_path, self.events_log_path)
        else:
            os.rename(temp_path, self.events_log_path)

    def inject_event(self, req: SimulationEventCreateRequest) -> SimulationEventRecord:
        """Validate, assign ID, append to JSONL log, recompute, and broadcast."""
        # Validation of IDs against network
        if req.service_id and req.service_id not in self.network.services:
            raise ValueError(f"Service ID '{req.service_id}' not found in network.")
        if req.station_id and req.station_id not in self.network.stations:
            # Check route waypoints
            all_route_nodes = {n for r in self.network.routes.values() for n in r.ordered_nodes}
            if req.station_id not in all_route_nodes:
                raise ValueError(f"Station/Node ID '{req.station_id}' not found in network.")
        if req.section_id and req.section_id not in self.network.track_sections:
            raise ValueError(f"Track Section ID '{req.section_id}' not found in network.")

        from_min = req.from_minute if req.from_minute is not None else self.state_manager.current_minute
        to_min = req.to_minute if req.to_minute is not None else self.state_manager.end_minute

        with self._lock:
            ev_id = f"EVT_{len(self.event_log) + 1:04d}"
            record = SimulationEventRecord(
                id=ev_id,
                event_type=req.event_type.upper(),
                service_id=req.service_id,
                station_id=req.station_id,
                section_id=req.section_id,
                delay_minutes=req.delay_minutes,
                speed_kmh=req.speed_kmh,
                speed_factor=req.speed_factor,
                from_minute=from_min,
                to_minute=to_min,
                description=req.description,
                created_at_sim_minute=self.state_manager.current_minute,
                created_at_wall_clock=datetime.now(timezone.utc).isoformat(),
            )

            self.event_log.append(record)
            self._save_events_log()

            # Recompute state
            snap = self.compute_snapshot_at(self.state_manager.current_minute)
            self.state_manager.last_snapshot = snap.model_dump() if hasattr(snap, "model_dump") else snap.dict()
            self.state_manager.save_to_disk()

            # Broadcast
            self.broadcast_event("event_injected", record.model_dump())
            self._emit_tick_and_conflict_events(snap)

            return record

    def list_events(self) -> List[SimulationEventRecord]:
        with self._lock:
            return list(self.event_log)

    def remove_event(self, event_id: str) -> bool:
        """Remove event by ID, persist JSONL, recompute state, and broadcast."""
        with self._lock:
            idx = next((i for i, ev in enumerate(self.event_log) if ev.id == event_id), None)
            if idx is None:
                return False

            removed = self.event_log.pop(idx)
            self._save_events_log()

            # Recompute state
            snap = self.compute_snapshot_at(self.state_manager.current_minute)
            self.state_manager.last_snapshot = snap.model_dump() if hasattr(snap, "model_dump") else snap.dict()
            self.state_manager.save_to_disk()

            # Broadcast
            self.broadcast_event("event_removed", {"id": removed.id, "event_type": removed.event_type})
            self._emit_tick_and_conflict_events(snap)

            return True

    # -----------------------------------------------------------------------
    # Reoptimization Proposals & Human-in-the-Loop
    # -----------------------------------------------------------------------

    def _load_proposals(self) -> None:
        if not os.path.exists(self.proposals_path):
            return
        try:
            with open(self.proposals_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.proposals = {p["proposal_id"]: ReoptimizationProposal(**p) for p in data}
        except Exception:
            pass

    def _save_proposals(self) -> None:
        temp_path = self.proposals_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump([p.model_dump() for p in self.proposals.values()], f, indent=2)
        if os.path.exists(self.proposals_path):
            os.replace(temp_path, self.proposals_path)
        else:
            os.rename(temp_path, self.proposals_path)

    def _load_applied_plan(self) -> None:
        if not os.path.exists(self.applied_plan_path):
            return
        try:
            with open(self.applied_plan_path, "r", encoding="utf-8") as f:
                self.applied_plan = json.load(f)
        except Exception:
            pass

    def _save_applied_plan(self) -> None:
        temp_path = self.applied_plan_path + ".tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(self.applied_plan, f, indent=2)
        if os.path.exists(self.applied_plan_path):
            os.replace(temp_path, self.applied_plan_path)
        else:
            os.rename(temp_path, self.applied_plan_path)

    def create_reoptimization_proposal(self) -> ReoptimizationProposal:
        """Run CP-SAT optimization pipeline on current state and disruptions; store proposal."""
        from optimization.scenarios import Scenario, ScenarioRunner
        from backend.app.pipeline import PipelineOrchestrator

        with self._lock:
            curr_m = self.state_manager.current_minute
            snap = self.compute_snapshot_at(curr_m)

            # Active departure delays from state + event log
            delays = dict(self.state_manager.departure_delays)
            blocked: List[str] = []
            speed_restr: Dict[str, float] = {}

            for ev in self.event_log:
                if ev.from_minute <= curr_m <= ev.to_minute:
                    if ev.event_type == "DEPARTURE_DELAY" and ev.service_id and ev.delay_minutes:
                        delays[ev.service_id] = max(delays.get(ev.service_id, 0.0), ev.delay_minutes)
                    elif ev.event_type == "BLOCKED_SECTION" and ev.section_id:
                        blocked.append(ev.section_id)
                    elif ev.event_type == "SPEED_RESTRICTION" and ev.section_id:
                        sec = self.network.track_sections.get(ev.section_id)
                        speed_restr[ev.section_id] = (sec.travel_time_minutes if sec else 3.0) * (ev.speed_factor or 2.0)

            svcs = self.state_manager.selected_service_ids

            # Resolve target cohort for live reoptimization: prioritize affected and conflicting services
            affected = set(delays.keys())
            for c in snap.detected_conflicts:
                affected.update(c.service_ids)
            for p in snap.train_positions:
                if p.status == "RUNNING" or p.delay_minutes > 0:
                    affected.add(p.service_id)

            if affected:
                target_svcs = [s for s in svcs if s in affected]
                if len(target_svcs) < 3:
                    for s in svcs:
                        if s not in target_svcs:
                            target_svcs.append(s)
                            if len(target_svcs) >= 4:
                                break
            else:
                target_svcs = svcs[:4]

            scenario = Scenario(
                scenario_id=f"SCEN_REOPT_{int(curr_m)}",
                name=f"Live Reoptimization at {minutes_to_time_str(curr_m)}",
                description="Live runtime disruption optimization proposal.",
                affected_service_ids=target_svcs,
                departure_delays=delays,
                track_speed_restrictions=speed_restr,
                blocked_sections=blocked,
            )

            orchestrator = PipelineOrchestrator(self.network)
            result = orchestrator.run_pipeline(scenario=scenario, service_ids=target_svcs)

            prop_id = f"PROP_{len(self.proposals) + 1:04d}"
            is_sol = result.solver_status in ("OPTIMAL", "FEASIBLE")

            opt_tt = (
                result.baseline_comparison.optimized_timetables
                if is_sol and result.baseline_comparison and result.baseline_comparison.optimized_timetables
                else {}
            )

            proposal = ReoptimizationProposal(
                proposal_id=prop_id,
                created_at_sim_minute=curr_m,
                created_at_wall_clock=datetime.now(timezone.utc).isoformat(),
                solver_status=result.solver_status,
                solution_available=is_sol,
                total_baseline_delay_minutes=round(result.total_baseline_delay_minutes, 2),
                total_optimized_delay_minutes=round(result.total_optimized_delay_minutes, 2) if is_sol else None,
                net_delay_savings_minutes=round(result.net_delay_savings_minutes, 2) if is_sol else None,
                net_delay_savings_percent=round(result.net_delay_savings_percent, 2) if is_sol else None,
                operational_severity=result.assessment.situation.severity.value,
                recommendations=[r.to_dict() for r in result.recommendations],
                adjusted_timetables=opt_tt,
                precedence_decisions=[],
                status="PENDING",
            )

            self.proposals[prop_id] = proposal
            self._save_proposals()

            # Broadcast SSE event
            self.broadcast_event(
                "proposal_ready",
                {
                    "proposal_id": proposal.proposal_id,
                    "sim_minute": proposal.created_at_sim_minute,
                    "solution_available": proposal.solution_available,
                    "net_delay_savings_minutes": proposal.net_delay_savings_minutes,
                    "operational_severity": proposal.operational_severity,
                },
            )

            return proposal

    def accept_proposal(self, proposal_id: str) -> ProposalActionResponse:
        """Apply proposal to the runtime plan (logged) and set status ACCEPTED."""
        with self._lock:
            if proposal_id not in self.proposals:
                raise ValueError(f"Proposal '{proposal_id}' not found.")

            prop = self.proposals[proposal_id]
            if prop.status != "PENDING":
                raise ValueError(f"Proposal '{proposal_id}' is already {prop.status}.")

            prop.status = "ACCEPTED"
            self._save_proposals()

            # Apply to runtime plan
            self.applied_plan = {
                "active_proposal_id": prop.proposal_id,
                "applied_at_wall_clock": datetime.now(timezone.utc).isoformat(),
                "applied_at_sim_minute": self.state_manager.current_minute,
                "precedence_decisions": prop.precedence_decisions,
                "adjusted_timetables": prop.adjusted_timetables,
            }
            self._save_applied_plan()

            return ProposalActionResponse(
                proposal_id=proposal_id,
                action="ACCEPT",
                status="ACCEPTED",
                message=f"Proposal '{proposal_id}' successfully applied to runtime plan.",
            )

    def reject_proposal(self, proposal_id: str) -> ProposalActionResponse:
        """Mark proposal REJECTED and discard."""
        with self._lock:
            if proposal_id not in self.proposals:
                raise ValueError(f"Proposal '{proposal_id}' not found.")

            prop = self.proposals[proposal_id]
            if prop.status != "PENDING":
                raise ValueError(f"Proposal '{proposal_id}' is already {prop.status}.")

            prop.status = "REJECTED"
            self._save_proposals()

            return ProposalActionResponse(
                proposal_id=proposal_id,
                action="REJECT",
                status="REJECTED",
                message=f"Proposal '{proposal_id}' rejected.",
            )

    # -----------------------------------------------------------------------
    # Server-Sent Events (SSE) Dispatcher
    # -----------------------------------------------------------------------

    def broadcast_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Enqueue message to all active SSE queues and store in replay history."""
        self._sse_seq += 1
        msg = SSEMessage(seq_id=self._sse_seq, event_type=event_type, data=data)
        self._sse_history.append(msg)

        for q in list(self._sse_subscribers):
            try:
                q.put_nowait(msg)
            except asyncio.QueueFull:
                pass

    def _emit_tick_and_conflict_events(self, snap: SimulateResponse) -> None:
        """Helper to broadcast tick and conflict state diffs."""
        # 1. Tick payload
        pos = snap.train_positions
        running = len([p for p in pos if p.status == "RUNNING"])
        scheduled = len([p for p in pos if p.status == "SCHEDULED"])
        arrived = len([p for p in pos if p.status == "ARRIVED"])

        tick_data = SSETickData(
            sim_minute=round(self.state_manager.current_minute, 2),
            sim_time_str=snap.simulation_time_str,
            ist_time_str=get_ist_time_str(),
            is_playing=self.state_manager.is_playing,
            playback_speed=self.state_manager.playback_speed,
            running_count=running,
            scheduled_count=scheduled,
            arrived_count=arrived,
            delayed_count=snap.delayed_services_count,
            active_conflict_count=len(snap.detected_conflicts),
            total_delay_minutes=snap.total_network_delay_minutes,
        )
        self.broadcast_event("tick", tick_data.model_dump())

        # 2. Conflict diff
        current_signatures = {
            f"{c.conflict_type}:{c.resource_id}:{','.join(sorted(c.service_ids))}"
            for c in snap.detected_conflicts
        }
        new_conflicts = current_signatures - self._last_conflict_signatures
        cleared_conflicts = self._last_conflict_signatures - current_signatures
        self._last_conflict_signatures = current_signatures

        for sig in new_conflicts:
            self.broadcast_event("conflict_detected", {"signature": sig})
        for sig in cleared_conflicts:
            self.broadcast_event("conflict_cleared", {"signature": sig})

    async def sse_event_stream(self, last_event_id: Optional[int] = None) -> AsyncIterator[str]:
        """Async generator yielding SSE formatted frames with reconnection replay."""
        q: asyncio.Queue[SSEMessage] = asyncio.Queue(maxsize=100)
        self._sse_subscribers.add(q)

        try:
            # 0. Initial connection handshake frame confirming stream activation
            curr_min = self.state_manager.current_minute
            playing = self.state_manager.is_playing
            init_payload = json.dumps({"status": "connected", "current_minute": curr_min, "is_playing": playing})
            yield f"event: connected\ndata: {init_payload}\n\n"

            # 1. Replay missed events if requested
            if last_event_id is not None:
                for msg in list(self._sse_history):
                    if msg.seq_id > last_event_id:
                        yield msg.format_sse()

            # 2. Stream live events
            while True:
                msg = await q.get()
                yield msg.format_sse()
        finally:
            self._sse_subscribers.discard(q)


# ---------------------------------------------------------------------------
# Global Singleton Accessor
# ---------------------------------------------------------------------------

_engine_instance: Optional[LiveSimulationEngine] = None


def get_live_engine(network: Optional[Network] = None) -> LiveSimulationEngine:
    """Return application-wide LiveSimulationEngine singleton."""
    global _engine_instance
    current_env_dir = os.environ.get("RAILWAY_RUNTIME_DIR", "runtime")
    if _engine_instance is None or _engine_instance.runtime_dir != current_env_dir:
        if network is None:
            from backend.app.pipeline import _load_default_network
            network = _load_default_network()
        _engine_instance = LiveSimulationEngine(network=network, runtime_dir=current_env_dir)
    return _engine_instance
