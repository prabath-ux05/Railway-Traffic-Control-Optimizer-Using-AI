"""
simulation/state_manager.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~
Authoritative Railway Simulation State Manager and Discrete Concurrent Engine.

Provides:
1. Operational IST (Asia/Kolkata, UTC+05:30) time synchronization.
2. Concurrent multi-service movement simulation across shared track sections.
3. Idle window handling: simulation advances smoothly even when 0 trains are active.
4. Authoritative state persistence across browser refreshes and server reloads.
"""

from datetime import datetime, timedelta, timezone
import json
import os
import threading
from typing import Any, Dict, List, Optional, Set, Tuple

from simulation.clock import SimulationClock, minutes_to_time_str, time_to_minutes
from simulation.conflicts import Conflict, ConflictDetector
from simulation.network import Network, Route, Service, TrackSection
from simulation.simulator import find_track_section
from simulation.state import SimulationState, TrackSectionOccupancy, TrainRuntimeState, TrainStatus
from backend.app.schemas import (
    SimulateResponse,
    TrainPositionState,
)

# Operational Railway Timezone: Indian Standard Time (Asia/Kolkata = UTC+05:30)
IST_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def get_ist_now() -> datetime:
    """Return current datetime in Asia/Kolkata timezone."""
    return datetime.now(IST_TIMEZONE)


def get_ist_time_str(include_seconds: bool = True) -> str:
    """Return formatted current time string in Asia/Kolkata (e.g. '14:35:00')."""
    fmt = "%H:%M:%S" if include_seconds else "%H:%M"
    return get_ist_now().strftime(fmt)


def get_ist_date_str() -> str:
    """Return formatted current date string in Asia/Kolkata (e.g. '2026-09-26')."""
    return get_ist_now().strftime("%Y-%m-%d")


def get_ist_minutes() -> float:
    """Return current IST time in minutes from midnight (0.0 to 1439.9)."""
    now = get_ist_now()
    return now.hour * 60.0 + now.minute + (now.second / 60.0)


def get_corridor_name_for_route(route_id: str) -> str:
    """Resolve human-readable corridor name from route identifier."""
    r = (route_id or "").upper()
    if "WEST" in r:
        return "West"
    if "NORTH_BYPASS" in r or "BEACH_NORTH" in r:
        return "Beach–North Bypass"
    if "NORTH" in r:
        return "North"
    if "SOUTH" in r:
        return "South"
    if "MRTS" in r:
        return "MRTS"
    if "CROSS" in r or "BYPASS" in r:
        return "Cross/Bypass"
    if "PTMS" in r:
        return "PTMS"
    return "West"


class SimulationStateManager:
    """Authoritative singleton managing persistent railway simulation state."""

    def __init__(
        self,
        network: Network,
        state_file_path: Optional[str] = None,
    ):
        self.network = network
        self.detector = ConflictDetector(network=network)
        self._lock = threading.RLock()

        if state_file_path is None:
            runtime_dir = os.environ.get("RAILWAY_RUNTIME_DIR")
            if runtime_dir:
                self.state_file_path = os.path.join(runtime_dir, "runtime_simulation_state.json")
            else:
                base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                self.state_file_path = os.path.join(base_dir, "runtime", "runtime_simulation_state.json")
        else:
            self.state_file_path = state_file_path

        # If the new file is absent, read the legacy data/ file once (copy it, do not delete it)
        legacy_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data",
            "runtime_simulation_state.json",
        )
        if not os.path.exists(self.state_file_path) and os.path.exists(legacy_path):
            try:
                os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
                import shutil
                shutil.copyfile(legacy_path, self.state_file_path)
            except Exception:
                pass

        # Defaults
        self.start_minute: float = 360.0   # 06:00
        self.end_minute: float = 540.0     # 09:00
        self.current_minute: float = 360.0 # 06:00
        self.is_playing: bool = False
        self.playback_speed: int = 1
        # Defaults to all active network services across all train types
        self.selected_service_ids: List[str] = (
            list(self.network.active_services.keys())
            if self.network and hasattr(self.network, "active_services") and self.network.active_services
            else list(self.network.services.keys())
            if self.network and self.network.services
            else [
                "SRV_43501_01",  # Suburban MAS -> AJJ
                "SRV_12675_01",  # Kovai Express MAS -> AJJ
                "SRV_16057_01",  # Sapthagiri Express MAS -> AJJ
                "SRV_12607_01",  # Lalbagh Express MAS -> AJJ
            ]
        )
        self.departure_delays: Dict[str, float] = {}
        self.last_snapshot: Optional[Dict[str, Any]] = None
        self.last_updated_ist: str = get_ist_time_str()

        # Load persisted state from disk if available
        self._load_from_disk()

        # Generate initial snapshot if missing
        if self.last_snapshot is None:
            self._execute_and_cache_snapshot()

    def _load_from_disk(self):
        """Restore state from disk if available."""
        if not os.path.exists(self.state_file_path):
            return

        try:
            with open(self.state_file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.start_minute = float(data.get("start_minute", self.start_minute))
            self.end_minute = float(data.get("end_minute", self.end_minute))
            self.current_minute = float(data.get("current_minute", self.current_minute))
            if self.current_minute > self.end_minute or self.current_minute < self.start_minute:
                self.current_minute = self.start_minute
            # Always start paused; a persisted is_playing=true must never auto-run after restart
            self.is_playing = False
            self.playback_speed = int(data.get("playback_speed", 1))

            svcs = data.get("selected_service_ids")
            if svcs and isinstance(svcs, list):
                # Ensure all services exist in network
                valid_svcs = [s for s in svcs if s in self.network.services]
                if valid_svcs:
                    self.selected_service_ids = valid_svcs

            delays = data.get("departure_delays")
            if isinstance(delays, dict):
                self.departure_delays = {
                    s: float(d) for s, d in delays.items() if s in self.network.services and float(d) >= 0.0
                }

            if "last_snapshot" in data and isinstance(data["last_snapshot"], dict):
                self.last_snapshot = data["last_snapshot"]
        except Exception:
            # If corrupted, start with in-memory defaults
            pass

    def save_to_disk(self):
        """Save authoritative state to disk."""
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.state_file_path), exist_ok=True)
                payload = {
                    "start_minute": self.start_minute,
                    "end_minute": self.end_minute,
                    "current_minute": self.current_minute,
                    "current_time_str": minutes_to_time_str(self.current_minute),
                    "is_playing": self.is_playing,
                    "playback_speed": self.playback_speed,
                    "selected_service_ids": self.selected_service_ids,
                    "departure_delays": self.departure_delays,
                    "last_updated_ist": get_ist_time_str(),
                    "last_snapshot": self.last_snapshot,
                }
                temp_path = self.state_file_path + ".tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                if os.path.exists(self.state_file_path):
                    os.replace(temp_path, self.state_file_path)
                else:
                    os.rename(temp_path, self.state_file_path)
            except Exception:
                pass

    def _execute_and_cache_snapshot(self) -> SimulateResponse:
        """Run multi-service simulation for current state and cache snapshot."""
        resp = self.simulate_epoch(
            target_time_m=self.current_minute,
            service_ids=self.selected_service_ids,
            departure_delays=self.departure_delays,
            start_time_m=self.start_minute,
        )
        self.last_snapshot = resp.model_dump() if hasattr(resp, "model_dump") else resp.dict()
        self.last_updated_ist = get_ist_time_str()
        return resp

    def get_authoritative_state(self) -> Dict[str, Any]:
        """Return complete authoritative state representation."""
        with self._lock:
            if self.last_snapshot is None:
                self._execute_and_cache_snapshot()

            return {
                "current_minute": round(self.current_minute, 2),
                "current_time_str": minutes_to_time_str(self.current_minute),
                "start_minute": round(self.start_minute, 2),
                "end_minute": round(self.end_minute, 2),
                "is_playing": self.is_playing,
                "playback_speed": self.playback_speed,
                "selected_service_ids": list(self.selected_service_ids),
                "departure_delays": dict(self.departure_delays),
                "ist_time_str": get_ist_time_str(),
                "ist_date_str": get_ist_date_str(),
                "timezone": "Asia/Kolkata (IST)",
                "snapshot": self.last_snapshot,
            }

    def update_control(
        self,
        current_minute: Optional[float] = None,
        current_time_str: Optional[str] = None,
        start_minute: Optional[float] = None,
        end_minute: Optional[float] = None,
        is_playing: Optional[bool] = None,
        playback_speed: Optional[int] = None,
        service_ids: Optional[List[str]] = None,
        departure_delays: Optional[Dict[str, float]] = None,
        seek_minute: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Update controller parameters, recalculate snapshot, and persist."""
        with self._lock:
            if start_minute is not None:
                self.start_minute = float(start_minute)
            if end_minute is not None:
                self.end_minute = float(end_minute)

            if seek_minute is not None:
                self.current_minute = max(self.start_minute, min(self.end_minute, float(seek_minute)))
            elif current_time_str is not None:
                self.current_minute = max(self.start_minute, min(self.end_minute, time_to_minutes(current_time_str)))
            elif current_minute is not None:
                self.current_minute = max(self.start_minute, min(self.end_minute, float(current_minute)))

            if is_playing is not None:
                self.is_playing = bool(is_playing)
                if self.is_playing and self.current_minute >= self.end_minute:
                    self.is_playing = False

            if playback_speed is not None:
                self.playback_speed = int(playback_speed)

            if service_ids is not None:
                valid_svcs = [s for s in service_ids if s in self.network.services]
                if valid_svcs:
                    self.selected_service_ids = valid_svcs

            if departure_delays is not None:
                self.departure_delays = {
                    s: float(d) for s, d in departure_delays.items() if s in self.network.services and float(d) >= 0.0
                }

            self._execute_and_cache_snapshot()
            self.save_to_disk()
            return self.get_authoritative_state()

    def reset_state(self, clear_delays: bool = False) -> Dict[str, Any]:
        """Reset simulation clock to start_minute and optionally clear delays."""
        with self._lock:
            self.current_minute = self.start_minute
            self.is_playing = False
            if clear_delays:
                self.departure_delays.clear()
            self._execute_and_cache_snapshot()
            self.save_to_disk()
            return self.get_authoritative_state()

    def simulate_epoch(
        self,
        target_time_m: float,
        service_ids: Optional[List[str]] = None,
        departure_delays: Optional[Dict[str, float]] = None,
        start_time_m: Optional[float] = None,
    ) -> SimulateResponse:
        """Run concurrent multi-service train progression at target_time_m.

        Evaluates simultaneous physical locations, track section occupancies,
        station dwell states, and conflicts across all selected services.
        Works smoothly even when 0 trains are active at target_time_m.
        """
        svcs_to_run = service_ids if service_ids else self.selected_service_ids
        # Ensure all services exist in network
        selected_svcs = [s for s in svcs_to_run if s in self.network.services]
        if not selected_svcs:
            selected_svcs = (
                list(self.network.active_services.keys())
                if hasattr(self.network, "active_services") and self.network.active_services
                else list(self.network.services.keys())
            )

        delays = departure_delays if departure_delays is not None else self.departure_delays

        sim_clock = SimulationClock(start_time=start_time_m or self.start_minute)
        sim_clock.advance_to(target_time_m)

        state = SimulationState(clock=sim_clock)
        state.initialize_from_network(self.network)

        train_positions: List[TrainPositionState] = []
        total_delay = 0.0
        delayed_count = 0

        for s_id in selected_svcs:
            svc = self.network.services[s_id]
            train_info = self.network.trains.get(svc.train_id)
            train_name = train_info.name if train_info else svc.train_id
            train_type = train_info.train_type if train_info else "STANDARD"
            route = self.network.routes[svc.route_id]
            corridor_name = get_corridor_name_for_route(svc.route_id)
            dep_delay = float(delays.get(s_id, 0.0))

            # Timetable departure at origin and arrival at destination
            tt_origin = next(
                (e for e in self.network.timetable if e.service_id == s_id and e.station_id == svc.origin),
                None,
            )
            tt_dest = next(
                (e for e in self.network.timetable if e.service_id == s_id and e.station_id == svc.destination),
                None,
            )
            nodes = route.ordered_nodes
            direction_hint = "UP" if "UP" in route.id else ("DOWN" if "DOWN" in route.id else None)

            # Compute nominal traversal time along route if destination arrival missing
            nom_runtime = 0.0
            for k in range(len(nodes) - 1):
                u_k, v_k = nodes[k], nodes[k + 1]
                ts_k = find_track_section(self.network, u_k, v_k, direction_hint)
                nom_runtime += (ts_k.travel_time_minutes if ts_k else 3.0)
                if k + 1 < len(nodes) - 1:
                    nom_runtime += 2.0

            base_dep = time_to_minutes(tt_origin.departure) if (tt_origin and tt_origin.departure) else 360.0
            actual_dep = base_dep + dep_delay
            sched_dep_str = tt_origin.departure if (tt_origin and tt_origin.departure) else minutes_to_time_str(base_dep)
            if tt_dest and tt_dest.arrival:
                sched_arr_str = tt_dest.arrival
            else:
                sched_arr_str = minutes_to_time_str((base_dep + nom_runtime) % 1440.0)

            t_state = state.get_train_state(s_id)
            t_state.delay_minutes = dep_delay

            # Determine where the train is at target_time_m
            cur_node: Optional[str] = nodes[0]
            cur_station: Optional[str] = nodes[0] if nodes[0] in self.network.stations else None
            cur_section: Optional[str] = None
            status_str: str = "SCHEDULED"
            occupied_res: List[str] = []
            service_delay: float = dep_delay

            if target_time_m < actual_dep:
                # 1. Not started yet / Scheduled
                status_str = "SCHEDULED"
                t_state.status = TrainStatus.NOT_STARTED
                t_state.current_node = nodes[0]
                t_state.current_station = nodes[0] if nodes[0] in self.network.stations else None
                t_state.current_track_section = None
                service_delay = dep_delay
            else:
                # Simulate trajectory along ordered nodes
                curr_t = actual_dep
                traversed_all = False

                for i in range(len(nodes) - 1):
                    u = nodes[i]
                    v = nodes[i + 1]
                    ts = find_track_section(self.network, u, v, direction_hint)
                    travel_t = ts.travel_time_minutes if ts else 3.0
                    sec_id = ts.id if ts else f"FALLBACK_{u}_{v}"
                    sec_cap = ts.capacity if ts else 1
                    sec_dir = ts.direction if ts else direction_hint

                    entry_t = curr_t
                    exit_t = entry_t + travel_t

                    if entry_t <= target_time_m < exit_t:
                        # Currently traversing this section!
                        status_str = "RUNNING"
                        cur_node = u
                        cur_station = None
                        cur_section = sec_id
                        occupied_res = [sec_id]

                        t_state.status = TrainStatus.IN_TRANSIT
                        t_state.current_node = u
                        t_state.current_station = None
                        t_state.current_track_section = sec_id
                        t_state.occupied_resources = {sec_id}

                        # Register active track occupancy
                        state.enter_track_section(
                            s_id,
                            sec_id,
                            u,
                            v,
                            entry_t,
                            expected_exit_time=exit_t,
                            capacity=sec_cap,
                            enforce_capacity=False,
                            direction=sec_dir,
                        )
                        break

                    curr_t = exit_t

                    if i + 1 < len(nodes) - 1:
                        # Intermediate station / junction
                        tt_v = next(
                            (e for e in self.network.timetable if e.service_id == s_id and e.station_id == v),
                            None,
                        )
                        dwell = 1.0
                        if tt_v and tt_v.departure and tt_v.arrival:
                            dwell = max(1.0, time_to_minutes(tt_v.departure) - time_to_minutes(tt_v.arrival))
                        dep_v = curr_t + dwell

                        if curr_t <= target_time_m < dep_v:
                            # Currently dwelling at station
                            status_str = "RUNNING"
                            cur_node = v
                            cur_station = v if v in self.network.stations else None
                            cur_section = None
                            occupied_res = [v]

                            t_state.status = TrainStatus.AT_STATION
                            t_state.current_node = v
                            t_state.current_station = cur_station
                            t_state.current_track_section = None
                            t_state.occupied_resources = {v}
                            state.station_occupancy[v].add(s_id)
                            break

                        curr_t = dep_v
                    else:
                        # Terminus arrival
                        if target_time_m >= exit_t:
                            traversed_all = True
                            status_str = "ARRIVED"
                            cur_node = v
                            cur_station = v if v in self.network.stations else None
                            cur_section = None
                            occupied_res = []

                            t_state.status = TrainStatus.COMPLETED
                            t_state.current_node = v
                            t_state.current_station = cur_station
                            t_state.current_track_section = None
                            t_state.occupied_resources = set()

                if traversed_all:
                    status_str = "ARRIVED"

            if service_delay > 0.0:
                delayed_count += 1
            total_delay += service_delay

            train_positions.append(
                TrainPositionState(
                    service_id=s_id,
                    train_id=svc.train_id,
                    train_name=train_name,
                    service_type=train_type,
                    train_type=train_type,
                    corridor=corridor_name,
                    corridor_name=corridor_name,
                    origin=svc.origin,
                    destination=svc.destination,
                    scheduled_departure=sched_dep_str,
                    scheduled_arrival=sched_arr_str,
                    priority_class=svc.priority_class,
                    status=status_str,
                    current_node=cur_node,
                    current_station=cur_station,
                    current_track_section=cur_section,
                    delay_minutes=round(service_delay, 2),
                    occupied_resources=occupied_res,
                )
            )

        # Detect conflicts in final simulated state
        detected_conflicts = self.detector.detect_all(state=state)
        active_occupancies = [occ.to_dict() for occ in state.get_active_occupancies()]

        return SimulateResponse(
            simulation_time_str=minutes_to_time_str(target_time_m),
            total_services_simulated=len(selected_svcs),
            delayed_services_count=delayed_count,
            total_network_delay_minutes=round(total_delay, 2),
            active_occupancies_count=len(active_occupancies),
            train_positions=train_positions,
            active_occupancies=active_occupancies,
            detected_conflicts=[c.to_dict() for c in detected_conflicts],
        )


# Singleton instance
_sim_manager_cache: Optional[SimulationStateManager] = None


def get_simulation_manager(
    network: Network,
    state_file_path: Optional[str] = None,
) -> SimulationStateManager:
    """Return shared singleton of the SimulationStateManager."""
    global _sim_manager_cache
    if _sim_manager_cache is None:
        _sim_manager_cache = SimulationStateManager(network=network, state_file_path=state_file_path)
    elif state_file_path is not None and _sim_manager_cache.state_file_path != state_file_path:
        _sim_manager_cache = SimulationStateManager(network=network, state_file_path=state_file_path)
    return _sim_manager_cache
