# Live Runtime Simulation Engine Contract & API Specification

**Authoritative Interface Documentation for Chennai Division Railway Traffic Digital Twin**  
**Document Revision:** 1.0.0 (Batch 4: Live Runtime Engine)  
**Scope:** Backend `LiveSimulationEngine`, Server-Sent Events (SSE) Stream, Disruption Events Lifecycle, and Human-in-the-Loop Reoptimization Proposals.

---

## 1. Architectural Overview & Determinism Guarantees

The `LiveSimulationEngine` manages authoritative live state transitions for the Chennai Central (MAS) – Arakkonam (AJJ) and suburban corridor digital twin.

### 1.1 State Determinism Equation
The simulation state at any target simulation minute $m$ is a strictly pure function:

$$\text{State}(m) = \mathcal{F}(\mathcal{D}_{\text{master}}, \mathcal{S}_{\text{active}}, \mathcal{E}_{\text{log}}, m)$$

where:
- $\mathcal{D}_{\text{master}}$ is the immutable Chennai Division network topology (stations, junctions, track sections, speed limits).
- $\mathcal{S}_{\text{active}}$ is the set of active services scheduled in the operational window.
- $\mathcal{E}_{\text{log}}$ is the ordered log of validated operational events (departure delays, dwell delays, speed restrictions, blocked sections).
- $m$ is the target simulation minute (e.g. $360.0 = \text{06:00 IST}$).

Wall-clock time governs only the **progression rate** of $m$; it never affects the underlying physical outcomes or conflict evaluations. Scrubbing or seeking backwards and forwards to any minute $m$ yields byte-identical state hashes.

### 1.2 Startup & Concurrency Guarantees
- **Always Starts Paused:** On process startup or restart, the engine initializes with `is_playing = False`. The clock never advances until an explicit `POST /simulation/control` with `is_playing: true` is received.
- **Single-Process Concurrency:** Thread-safe state progression and SSE dispatching are synchronized via `asyncio.Lock`.
- **Clock Boundaries:** Configurable operational window defaults to `start_minute = 360.0` (06:00 IST) and `end_minute = 540.0` (09:00 IST) or full 24-hour day ($0.0 - 1440.0$). Time advance automatically halts and sets `is_playing = False` upon reaching `end_minute`.

---

## 2. Playback Speed & Clock Progression Semantics

The engine defines playback speed as **simulation-minutes advanced per real-world minute**:

$$\frac{dm_{\text{sim}}}{dt_{\text{real}}} = \frac{\text{playback\_speed}}{60.0}$$

| Speed Option | Sim-Minutes per Real Minute | Sim-Minutes per Real Second | Real Seconds per Sim-Minute | Operational Description |
|:---:|:---:|:---:|:---:|:---|
| **1x** | $1.0\text{ min/min}$ | $0.0167\text{ min/s}$ | $60.0\text{ s}$ | Real-time 1:1 playback |
| **2x** | $2.0\text{ min/min}$ | $0.0333\text{ min/s}$ | $30.0\text{ s}$ | $2\times$ accelerated monitoring |
| **5x** | $5.0\text{ min/min}$ | $0.0833\text{ min/s}$ | $12.0\text{ s}$ | Accelerated peak window review |
| **10x** | $10.0\text{ min/min}$ | $0.1667\text{ min/s}$ | $6.0\text{ s}$ | Fast batch transition |
| **30x** | $30.0\text{ min/min}$ | $0.5000\text{ min/s}$ | $2.0\text{ s}$ | Rapid timeline scan |
| **60x** | $60.0\text{ min/min}$ | $1.0000\text{ min/s}$ | $1.0\text{ s}$ | 1 sim-minute per real-second scrub |

*Frontend Legacy Interval Mapping:* In the Next.js client, speed options previously mapped to interval delay `max(300, 1500 / speed)` with a fixed $+5\text{ min}$ step. In the new architecture, client polling is eliminated in favor of real-time server ticks over SSE.

---

## 3. REST API Specifications

### 3.1 Simulation Control
`POST /api/v1/simulation/control`

Updates playback parameters, scrubs timeline, or configures the operational fleet.

**Request Body (`SimulationControlRequest`):**
```json
{
  "current_minute": 375.0,
  "is_playing": true,
  "playback_speed": 5,
  "seek_minute": 380.0,
  "start_minute": 360.0,
  "end_minute": 540.0,
  "service_ids": ["SRV_12607_01", "SRV_12609_01"],
  "departure_delays": {
    "SRV_12607_01": 15.0
  }
}
```

**Response (`SimulationStateResponse`):**
```json
{
  "current_minute": 380.0,
  "current_time_str": "06:20",
  "start_minute": 360.0,
  "end_minute": 540.0,
  "is_playing": true,
  "playback_speed": 5,
  "selected_service_ids": ["SRV_12607_01", "SRV_12609_01"],
  "departure_delays": {"SRV_12607_01": 15.0},
  "last_updated_ist": "06:20:00",
  "active_services_count": 2,
  "delayed_services_count": 1,
  "total_departure_delay_minutes": 15.0
}
```

---

### 3.2 Simulation Reset
`POST /api/v1/simulation/reset?clear_delays=false`

Resets the simulation clock back to `start_minute` (06:00 IST), halts playback, and cleans runtime state.

**Query Parameters:**
- `clear_delays` (boolean, default: `false`): If `true`, clears injected departure delays.

---

### 3.3 Disruption Events Management

#### (a) List Disruption Events
`GET /api/v1/simulation/events`

Returns the active JSONL-persisted log of disruption events.

**Response:**
```json
[
  {
    "id": "EVT_0001",
    "event_type": "DEPARTURE_DELAY",
    "service_id": "SRV_12607_01",
    "station_id": null,
    "section_id": null,
    "delay_minutes": 20.0,
    "speed_kmh": null,
    "speed_factor": null,
    "from_minute": 360.0,
    "to_minute": 540.0,
    "description": "Signal failure at MAS platform 1",
    "created_at_sim_minute": 360.0,
    "created_at_wall_clock": "2026-11-18T13:00:00.000Z"
  }
]
```

#### (b) Inject Disruption Event
`POST /api/v1/simulation/events`

Injects a new operational event, appends it to `runtime/runtime_simulation_events.jsonl`, re-evaluates the simulation state from scratch, and broadcasts `event_injected` over SSE.

**Request Body (`SimulationEventCreateRequest`):**
```json
{
  "event_type": "BLOCKED_SECTION",
  "section_id": "PER_PCW_SUBURBAN_DOWN",
  "from_minute": 370.0,
  "to_minute": 420.0,
  "description": "Emergency track maintenance between Perambur and Carriage Works"
}
```

*Supported `event_type` values:*
- `DEPARTURE_DELAY`: Requires `service_id` and `delay_minutes`.
- `DWELL_DELAY`: Requires `service_id`, `station_id`, and `delay_minutes`.
- `SPEED_RESTRICTION`: Requires `section_id` and `speed_kmh` or `speed_factor`.
- `BLOCKED_SECTION`: Requires `section_id`.

**Response Status:** `201 Created`  
**Response Body:** `SimulationEventRecord`

#### (c) Remove Disruption Event
`DELETE /api/v1/simulation/events/{event_id}`

Deletes the specified event from the JSONL log, re-evaluates state deterministically, and broadcasts `event_removed` over SSE.

**Response Body:**
```json
{
  "status": "success",
  "message": "Event 'EVT_0001' successfully removed."
}
```

---

### 3.4 Human-in-the-Loop Reoptimization Proposals

#### (a) Trigger Live Reoptimization
`POST /api/v1/simulation/reoptimize`

Triggers CP-SAT mathematical optimization on the current simulation snapshot and active disruptions. Returns a proposal stored in `runtime/runtime_simulation_proposals.json` in status `PENDING`. **Never automatically alters the running train plan.**

**Response Body (`ReoptimizationProposal`):**
```json
{
  "proposal_id": "PROP_0001",
  "created_at_sim_minute": 375.0,
  "created_at_wall_clock": "2026-11-18T13:05:00.000Z",
  "solver_status": "OPTIMAL",
  "solution_available": true,
  "total_baseline_delay_minutes": 114.0,
  "total_optimized_delay_minutes": 42.5,
  "net_delay_savings_minutes": 71.5,
  "net_delay_savings_percent": 62.72,
  "operational_severity": "WARNING",
  "recommendations": [
    {
      "directive_id": "REC_01",
      "text": "Hold SRV_12609_01 at PER loop 1 to give precedence to express SRV_12607_01.",
      "severity": "WARNING"
    }
  ],
  "adjusted_timetables": {},
  "precedence_decisions": [],
  "status": "PENDING"
}
```

#### (b) Accept Proposal
`POST /api/v1/simulation/proposals/{proposal_id}/accept`

Controller decision: marks proposal `ACCEPTED`, applies it to `runtime/runtime_simulation_applied_plan.json`.

**Response Body (`ProposalActionResponse`):**
```json
{
  "proposal_id": "PROP_0001",
  "action": "ACCEPT",
  "status": "ACCEPTED",
  "message": "Proposal 'PROP_0001' successfully applied to runtime plan."
}
```

#### (c) Reject Proposal
`POST /api/v1/simulation/proposals/{proposal_id}/reject`

Controller decision: marks proposal `REJECTED` and preserves existing baseline schedule.

**Response Body (`ProposalActionResponse`):**
```json
{
  "proposal_id": "PROP_0001",
  "action": "REJECT",
  "status": "REJECTED",
  "message": "Proposal 'PROP_0001' rejected."
}
```

---

## 4. Server-Sent Events (SSE) Specification

### 4.1 Endpoint
`GET /api/v1/simulation/stream`

### 4.2 Stream Protocol
- **Media Type:** `text/event-stream`
- **Headers:** `Cache-Control: no-cache`, `Connection: keep-alive`
- **Monotonic Sequence IDs:** Each event frame includes `id: <integer>`.
- **Reconnection Replay:** When a client reconnects providing the `Last-Event-ID: <id>` request header, the engine replays all buffered historical messages with `seq_id > id` before continuing real-time stream.

### 4.3 SSE Event Types & Payloads

#### 1. `tick`
Emitted every clock advance step or timeline scrub.
```
id: 101
event: tick
data: {"sim_minute":375.0,"sim_time_str":"06:15","ist_time_str":"06:15:00","is_playing":true,"playback_speed":5,"running_count":12,"scheduled_count":26,"arrived_count":2,"delayed_count":3,"active_conflict_count":1,"total_delay_minutes":45.0}
```

#### 2. `conflict_detected`
Emitted when a new conflict appears in the epoch simulation that was not present in the previous tick.
```
id: 102
event: conflict_detected
data: {"signature":"HEADWAY_CONFLICT:PER_PCW_SUBURBAN_DOWN:SRV_12607_01,SRV_12609_01"}
```

#### 3. `conflict_cleared`
Emitted when a previously active conflict is resolved or passed.
```
id: 103
event: conflict_cleared
data: {"signature":"HEADWAY_CONFLICT:PER_PCW_SUBURBAN_DOWN:SRV_12607_01,SRV_12609_01"}
```

#### 4. `event_injected`
Emitted immediately when a controller or external system injects a disruption.
```
id: 104
event: event_injected
data: {"id":"EVT_0002","event_type":"BLOCKED_SECTION","section_id":"PER_PCW_SUBURBAN_DOWN","from_minute":370.0,"to_minute":420.0,"description":"Track obstruction"}
```

#### 5. `event_removed`
Emitted immediately when an injected disruption is deleted.
```
id: 105
event: event_removed
data: {"id":"EVT_0002","event_type":"BLOCKED_SECTION"}
```

#### 6. `proposal_ready`
Emitted when the CP-SAT reoptimization completes and an advisory plan is available for review.
```
id: 106
event: proposal_ready
data: {"proposal_id":"PROP_0001","sim_minute":375.0,"solution_available":true,"net_delay_savings_minutes":71.5,"operational_severity":"WARNING"}
```

#### 7. `heartbeat`
Emitted every 15 seconds during idle playback or pause to keep connection active across proxies.
```
id: 107
event: heartbeat
data: {"timestamp":1727344815.0,"ist_time":"15:30:15"}
```

---

## 5. Suggested TypeScript Client Interfaces

```typescript
// --- Simulation Control & State ---
export interface SimulationControlRequest {
  current_minute?: number;
  current_time_str?: string;
  start_minute?: number;
  end_minute?: number;
  is_playing?: boolean;
  playback_speed?: 1 | 2 | 5 | 10 | 30 | 60;
  seek_minute?: number;
  service_ids?: string[];
  departure_delays?: Record<string, number>;
}

export interface SimulationStateResponse {
  current_minute: number;
  current_time_str: string;
  start_minute: number;
  end_minute: number;
  is_playing: boolean;
  playback_speed: number;
  selected_service_ids: string[];
  departure_delays: Record<string, number>;
  last_updated_ist: string;
  active_services_count: number;
  delayed_services_count: number;
  total_departure_delay_minutes: number;
}

// --- Disruption Events ---
export type DisruptionEventType =
  | 'DEPARTURE_DELAY'
  | 'DWELL_DELAY'
  | 'SPEED_RESTRICTION'
  | 'BLOCKED_SECTION';

export interface SimulationEventCreateRequest {
  event_type: DisruptionEventType;
  service_id?: string;
  station_id?: string;
  section_id?: string;
  delay_minutes?: number;
  speed_kmh?: number;
  speed_factor?: number;
  from_minute?: number;
  to_minute?: number;
  description?: string;
}

export interface SimulationEventRecord extends SimulationEventCreateRequest {
  id: string;
  created_at_sim_minute: number;
  created_at_wall_clock: string;
}

// --- SSE Event Stream ---
export interface SSETickData {
  sim_minute: number;
  sim_time_str: string;
  ist_time_str: string;
  is_playing: boolean;
  playback_speed: number;
  running_count: number;
  scheduled_count: number;
  arrived_count: number;
  delayed_count: number;
  active_conflict_count: number;
  total_delay_minutes: number;
}

export interface SSEConflictData {
  signature: string;
}

export interface SSEProposalReadyData {
  proposal_id: string;
  sim_minute: number;
  solution_available: boolean;
  net_delay_savings_minutes: number | null;
  operational_severity: 'NORMAL' | 'ADVISORY' | 'WARNING' | 'CRITICAL' | 'EMERGENCY';
}

// --- Reoptimization Proposals ---
export interface ReoptimizationProposal {
  proposal_id: string;
  created_at_sim_minute: number;
  created_at_wall_clock: string;
  solver_status: string;
  solution_available: boolean;
  total_baseline_delay_minutes: number;
  total_optimized_delay_minutes: number | null;
  net_delay_savings_minutes: number | null;
  net_delay_savings_percent: number | null;
  operational_severity: 'NORMAL' | 'ADVISORY' | 'WARNING' | 'CRITICAL' | 'EMERGENCY';
  recommendations: Array<{
    directive_id: string;
    text: string;
    severity: string;
  }>;
  adjusted_timetables: Record<string, any[]>;
  precedence_decisions: any[];
  status: 'PENDING' | 'ACCEPTED' | 'REJECTED';
}

export interface ProposalActionResponse {
  proposal_id: string;
  action: 'ACCEPT' | 'REJECT';
  status: 'ACCEPTED' | 'REJECTED';
  message: string;
}
```
