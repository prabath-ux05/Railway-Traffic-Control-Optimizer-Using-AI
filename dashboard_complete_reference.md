# Railway Traffic Optimization Dashboard — Complete Page-by-Page Reference

> **How to read this:** Every page is documented with its purpose, every section, every button, what happens when you click it, and exactly what API call is made behind the scenes.

---

## System Architecture (How Everything Connects)

```
Your Browser (Next.js on localhost:3000 or 3001)
        │
        │  All API calls go to /api/v1/...
        │  (Next.js proxies them — no CORS issues)
        ▼
FastAPI Backend (Python on localhost:8000)
        │
        ├── /api/v1/health      → system diagnostics
        ├── /api/v1/network     → all stations, routes, junctions, services
        ├── /api/v1/simulate    → run discrete-event train simulation
        ├── /api/v1/optimize    → run CP-SAT mathematical solver
        ├── /api/v1/what-if     → run full disruption evaluation + recommendations
        └── /api/v1/analytics   → research benchmarks and scalability tests
```

**On every page load**, the frontend automatically calls:
1. `GET /api/v1/health` — checks the backend is alive
2. `GET /api/v1/network` — loads all 30 stations, 7 junctions, 24 routes, 40 services
3. `POST /api/v1/simulate` — runs the baseline simulation (no delays)
4. `POST /api/v1/what-if` — runs the baseline assessment (scenario: "Live Operational Corridor Baseline")
5. `POST /api/v1/optimize` — runs the baseline optimization

This pre-loading means **all pages have data** immediately when you switch tabs, without waiting.

---

## Header (Always Visible)

The sticky bar at the top of every page.

| Element | What it shows | What it does |
|---|---|---|
| **Train icon + title** | "Railway Traffic Optimization & Decision Support System" | Branding only |
| **Clock / time display** | The current simulation time (e.g., "07:45") — updates as simulation runs | Display only |
| **SYNC button** | Re-fetches all 5 API calls above from scratch | Refreshes everything |
| **Tab row** | 8 tabs: Operations Hub, Division Topology, Live Simulation, CP-SAT Optimizer, What-If Studio, Scenario Comparator, Timetable Comparator, Research Analytics | Switches the active page |

---

## Page 1 — Operations Hub (`/` → tab: `overview`)

**Purpose:** The command centre. Gives the controller an instant situational picture — what is the network status right now, what is the single most important action to take, and how to quickly fire test scenarios.

### Section 1: Operational Status Banner (top coloured bar)

This bar shows the result of the last **What-If evaluation**. Its colour changes:
- 🔴 **CRITICAL / EMERGENCY** → rose/red — serious disruption detected or high-risk conflicts present
- 🟡 **WARNING** → amber — moderate impact
- 🟡 **ADVISORY** → yellow — minor risk
- 🟢 **NORMAL** → green — all services on time, no conflicts

| Element | Meaning |
|---|---|
| **Status label** (e.g., "CRITICAL") | `operational_severity` field from the what-if API response |
| **Scenario name** (e.g., "Live Operational Corridor Baseline") | The name of the what-if scenario that was last evaluated |
| **DELAY SAVINGS** | How many minutes of delay the CP-SAT optimizer saved vs doing nothing (FIFO) |
| **ACTIVE CONFLICTS** | Number of conflicts (junction blocks, headway violations) the system detected |

> ⚠️ **Why is it CRITICAL in the baseline?** The baseline what-if runs with no delays. CRITICAL means the optimizer found a **preventive conflict** — two trains scheduled to reach the same junction (KOTR) at the same time. It's a warning, not an emergency. The system is doing its job correctly.

### Section 2: Primary Actionable Dispatch Directive

This box only appears when the what-if response has at least one recommendation. It shows the **single most important action** for the controller to take.

| Element | Meaning |
|---|---|
| **Title** (e.g., "Precedence Priority at KOTR") | The recommended action title |
| **Priority tier badge** (e.g., "CRITICAL") | How urgent this action is |
| **Operational context badge** (e.g., "LIVE_OPERATIONAL") | Whether this applies to live operations or a simulation test |
| **Category badge** (e.g., "precedence change") | The type of intervention |
| **Expected Savings** | `+X.Xm (Opt Y.Ym)` — X = delay currently saved, Y = the amount the optimizer had to work around internally |
| **Dispatcher Rationale** | Plain-English explanation of why this action is needed |
| **Counterfactual Impact** | What happens if you do NOT follow this directive |
| **Target** | Which train service the directive applies to |
| **Confidence** | How certain the optimizer is (usually 100% for CP-SAT) |
| **Resources** | Which junctions/stations are involved |
| **"Explain Reasoning Pathway" →** | Clicking this navigates to the **What-If Studio** page for full detail |

### Section 3: One-Click Disruption Scenario Buttons

Four scenario launcher buttons. **Clicking any of them** does two things:
1. Calls `POST /api/v1/what-if` with the scenario parameters (delays + speed restrictions)
2. Automatically switches you to the **What-If Studio** tab to see results

| Button | What it simulates | API parameters sent |
|---|---|---|
| **Single Train Delay** | Lalbagh Express (train 12607) departs 25 min late from Chennai Central | `departure_delays: { "SRV_12607_01": 25.0 }` |
| **Multi-Train Contention** | Both 12607 AND 12609 depart late (25m + 20m), competing for Basin Bridge throat | `departure_delays: { "SRV_12607_01": 25.0, "SRV_12609_01": 20.0 }` |
| **Speed Restriction** | A temporary speed restriction (TSR) is imposed on the MAS-BBQ mainline throat at 10 km/h | `speed_restrictions: { "MAS_BBQ_THROAT_SEGMENT_DOWN": 10.0 }` |
| **Severe Compound** | Worst-case: both expresses delayed AND a throat speed restriction simultaneously | `departure_delays: {...}, speed_restrictions: {...}` |

### Section 4: Division Corridor Cards (3 panels)

Static information panels showing the three main operating zones.

| Panel | Corridor | Key junctions | Services |
|---|---|---|---|
| WEST MAINLINE | MAS → AJJ | BBQ, VJM, PAB, AJJ | 12607, 12609, 12610, 43411 |
| NORTH MAINLINE | MAS → GPD | BBQ, KOK | North suburban services |
| SOUTH & BYPASS | MSB → CGL | MSB, MS, TBM, CGL, PTMS | South/MRTS services |

Each panel has a **"View Corridor Topology" button** — clicking it navigates directly to the **Division Topology** page.

---

## Page 2 — Division Topology (`tab: topology`)

**Purpose:** Interactive schematic map of the entire Chennai Division railway network — all 107 stations across 7 corridors. This page is **display-only** (no API calls when you interact with it — all data was loaded at startup from `GET /api/v1/network`).

### Corridor Filter Buttons (top bar)

| Button | What it shows | Stations visible |
|---|---|---|
| **All** | Every station on every corridor | ~107 |
| **West** | MAS → AJJ trunk route | 29 stations |
| **North** | BBQ → SPE coastal route | 21 stations |
| **South** | MSB → CGL suburban south | 28 stations |
| **MRTS** | MSB → VLCY elevated rail | 19 stations |
| **Bypass** | MSB → RPM → WST → KOK | 5 stations |
| **PTMS** | PAB → PTMS (military siding) | 2 stations |
| **Cross** | CGL → Kanchipuram → AJJ | 11 stations |

**When you click a filter button:** The map automatically zooms and pans to fit that corridor's stations on screen. Station labels become visible.

### Zoom / Pan Controls

| Control | Action |
|---|---|
| **+ button** | Zoom in 1.2× |
| **− button** | Zoom out (÷1.2) |
| **⌖ Reset** | Returns to default zoom/pan |
| **Mouse wheel** | Zoom in/out at cursor position |
| **Click and drag** | Pan the map |

### Station Nodes (circles on the map)

| Circle size/colour | Station type |
|---|---|
| Large, white ring | **Terminus** (e.g., MAS, MSB, TBM, AJJ) |
| Medium, amber ring | **Junction** (e.g., BBQ, VJM, KOK, CGL) |
| Medium, grey ring | **Major station** (e.g., AVD, ABU, TBM) |
| Small, dark | **Regular station** |
| Pulsing yellow ring | **Has a live train on it** (from simulation data) |
| Blue ring | Currently selected station |

**Hover over a station:** Tooltip appears at the bottom left showing station code + name + train count.

**Click a station:** Opens the **Inspector Panel** on the right side showing:
- Station type and platform count
- Junction role (if it's a junction) — its type, capacity, and which routes pass through it
- List of all connected neighbouring stations — click any neighbour to jump to it
- Live train count (if simulation is running)

### Line colours (corridor coding)

| Colour | Corridor |
|---|---|
| Cyan | West |
| Amber | North |
| Green | South |
| Purple | MRTS |
| Blue | Bypass |
| Orange | PTMS |
| Pink | Cross |

---

## Page 3 — Live Simulation (`tab: simulation`)

**Purpose:** Step-by-step playback of train movements across the network from 06:00 to 08:30. You can inject delays and watch how they cascade through the timetable.

**API used:** `POST /api/v1/simulate` — called every time the simulation clock advances.

### Simulation Clock Controls

| Control | Action | What it does |
|---|---|---|
| **▶ Play / ⏸ Pause** | Starts/stops the automatic clock | Fires `POST /api/v1/simulate` every 1.5 seconds (at 1× speed) advancing 5 minutes per step |
| **◀ Step Backward** | Go back 5 minutes | Calls simulate with `current_time = now - 5` |
| **▶ Step Forward** | Advance 5 minutes | Calls simulate with `current_time = now + 5` |
| **↺ Reset** | Returns to 06:00 | Calls simulate at 06:00 |
| **Timeline scrubber** | Click/drag to any time | Calls simulate at the chosen time |
| **1× / 2× / 5× speed** | Playback speed | Changes interval: 1×=1500ms, 2×=750ms, 5×=300ms |

### Delay Injection Controls

Before pressing Play or stepping forward, you can inject a departure delay:

| Control | What it does |
|---|---|
| **Service dropdown** | Pick which train to delay (default: SRV_12607_01 = Lalbagh Express) |
| **Delay slider (0–60 min)** | How many minutes late the train departs from origin |

These delays are sent to the API with every simulation step as `departure_delays`.

### Simulation Results (displayed after each step)

| Section | What it shows |
|---|---|
| **Train Positions table** | Every active train: which station it's at, what time, delay in minutes, current status |
| **Track Occupancy** | Which sections of track are occupied (red = occupied, green = free) |
| **Detected Conflicts** | Any headway violations or junction blocks the simulator found |
| **Service Status** | Whether each train is ON TIME, DELAYED, or CANCELLED |

---

## Page 4 — CP-SAT Optimizer (`tab: optimization`)

**Purpose:** The mathematical scheduling engine. You tell it which trains to schedule and what disruptions exist, and it uses Google's OR-Tools CP-SAT solver to find the globally optimal conflict-free timetable. This is the core research contribution of the project.

**API used:** `POST /api/v1/optimize`

### Step 1 — Service Selection (top section)

A checklist of all available services. Click any service card to include/exclude it from optimization.

| Button | Action |
|---|---|
| **ALL** | Select every service in the network |
| **EXPRESS ONLY** | Select only SUPERFAST / EXPRESS / PASSENGER class services |
| **SUBURBAN ONLY** | Select only SUBURBAN_EMU / SUBURBAN class services |
| **DEFAULT (4)** | Reset to the 4 default services: 12607, 12609, 12610, 43411 |
| **CLEAR** | Deselect everything |

Services marked **AFFECTED** (amber badge) are ones that have delays injected or were rescheduled by the optimizer.

### Step 2 — Inject Departure Delay (left configurator)

| Control | Action |
|---|---|
| **Service dropdown** | Pick which train to delay |
| **Slider (0–60m)** | Set departure delay |
| **Quick preset buttons (+0m, +10m, +20m, +30m, +45m)** | One-click delay amounts |

### Step 3 — Inject Station Dwell Delay (right configurator)

Add extra dwell time at a specific intermediate station (e.g., a train stops 10 extra minutes at AVD because of a track inspection).

| Control | Action |
|---|---|
| **Service dropdown** | Which train |
| **Station dropdown** | Which station |
| **Minutes input** | How many extra minutes |
| **ADD button** | Adds the delay to the list |
| **× on a tag** | Removes that specific station delay |

### Step 4 — SYNC LIVE SIM STATE button

Reads the current simulation data and automatically imports all delayed trains from the Live Simulation into the departure delay configurator. Use this after running the simulation with delays to transfer that state into the optimizer.

### Step 5 — EXECUTE CP-SAT SOLVER (blue button)

Sends `POST /api/v1/optimize` with:
- `service_ids`: the selected services
- `departure_delays`: the delays you configured  
- `station_delays`: any station dwell delays

The solver runs Google OR-Tools CP-SAT and returns within 2–5 seconds.

### Solver Outcome KPI Cards (appear after solving)

| Card | What it means |
|---|---|
| **SOLVER STATUS** | OPTIMAL = best possible solution found; FEASIBLE = good but not provably optimal; INFEASIBLE = no valid schedule exists |
| **Solve Time** | How many seconds the solver took |
| **FEASIBLE BASELINE (FIFO)** | Total delay if trains are dispatched First-In-First-Out (no optimization) |
| **CP-SAT OPTIMIZED DELAY** | Total delay after optimization — always ≤ FIFO |
| **NET DELAY SAVINGS** | Difference: how many minutes the optimizer saved over FIFO dispatch |
| **UNRESOLVED CONFLICTS** | Should be 0 (CP-SAT always produces a conflict-free schedule) |

### Result Inspection Tabs

| Tab | What it shows |
|---|---|
| **OPTIMIZED TIMETABLE** | Full table: every station stop for every service, with original time vs. optimized time, delay, platform assignment, and ON TIME / RESCHEDULED status |
| **BEFORE / AFTER DIFF** | Per-service comparison: original schedule vs. optimized schedule, showing exactly which station arrivals changed and by how much |
| **PRECEDENCE DECISIONS (N)** | Which trains were given priority over others at each junction — e.g., "SRV_12610_01 before SRV_12609_01 at KOTR" |
| **PLATFORM ALLOCATIONS (N)** | Which platform number each train is assigned to at each stop |

### APPLY AS PROPOSED DECISION (green button)

Marks the current optimization result as the controller's proposed action. Shows a banner at the top confirming the proposal with a reference number (e.g., PROP-CP-SAT-075523).

**Important:** This does NOT modify any timetable files or send anything to real systems. It is a simulation workspace state only.

| Button | Action |
|---|---|
| **APPLY AS PROPOSED DECISION** | Sets "proposed decision active" banner with timestamp and reference |
| **REVERT TO PUBLISHED VIEW** | Clears the proposed decision banner |
| **CLEAR PROPOSED DECISION** | Same as Revert |

---

## Page 5 — What-If Studio (`tab: what-if`)

**Purpose:** The most powerful decision-support page. Design a disruption scenario (type, trains affected, delays, speed restrictions), run it through the full simulation + optimization pipeline, and get a detailed list of AI-generated dispatcher recommendations with confidence scores and counterfactual analysis.

**API used:** `POST /api/v1/what-if`

### Scenario Configuration Panel (left/top)

#### Scenario Name and Description fields
Free-text fields. Naming your scenario helps you track what you tested. No API calls on typing.

#### Scenario Type Presets (6 buttons)

| Preset | What it pre-fills |
|---|---|
| **Departure Delay** | Single train departure delay |
| **En-Route Delay** | Delay that occurs mid-journey at an intermediate station |
| **Temporary Speed Restriction** | Reduced speed on a track section |
| **Blocked Section** | A track section completely blocked |
| **Junction Contention** | Multiple trains competing for the same junction |
| **Compound Disruption** | Combination of delays + speed restrictions |

Clicking a preset automatically fills in sensible default values for the controls below.

#### Service selector, delay slider, station delay controls
Same as CP-SAT Optimizer page — select which trains, set departure delays 0–60m, add station dwell delays.

#### Speed Restriction configurator
Set a speed limit (km/h) on a specific track segment ID (e.g., `MAS_BBQ_THROAT_SEGMENT_DOWN`). Used for TSR scenarios.

#### EVALUATE WHAT-IF SCENARIO (purple button)
Sends `POST /api/v1/what-if` with all configured parameters. The backend runs:
1. Full discrete-event simulation with the injected disruptions
2. CP-SAT optimization to find the best recovery schedule
3. Generates ranked recommendations with rationale, confidence, and counterfactual analysis

### Results Area (right/bottom)

#### Severity Banner
Shows `operational_severity`: NORMAL / ADVISORY / WARNING / CRITICAL / EMERGENCY based on the scenario outcome.

Key metrics:
- `Active services simulated`
- `Net delay savings` (how much the optimizer recovered)
- `Conflicts detected`
- `Recommendations generated`

#### Result Inspection Tabs

| Tab | What it shows |
|---|---|
| **RECOMMENDATIONS** | Ranked list of dispatcher actions (see below) |
| **DELAYS** | Per-train delay breakdown — original vs. simulated delay, recovery percentage |
| **CONFLICTS** | All junction conflicts detected: which trains, which resource, what time |
| **BOTTLENECKS** | Network hotspots — stations/junctions with highest occupancy pressure |
| **COMPARISON** | Side-by-side: baseline (no disruption) vs. scenario metrics |

#### Recommendations Tab (the main output)

Each recommendation card shows:

| Field | Meaning |
|---|---|
| **Priority Tier** | CRITICAL > HIGH > MEDIUM > LOW |
| **Category** | Type of action: `precedence_change`, `speed_recovery`, `platform_reassignment`, `hold_and_release`, etc. |
| **Operational Context** | `LIVE_OPERATIONAL` (can be done now) or `SIMULATION_ADVISORY` (research only) |
| **Title** | Short action description |
| **Expected Savings** | Minutes of delay this action prevents |
| **Dispatcher Rationale** | Why this action is recommended |
| **Counterfactual Analysis** | What happens if you DON'T follow this recommendation |
| **Confidence Score** | 0–100% (CP-SAT agreement rate) |
| **Affected Resources** | Which junctions/stations/segments are involved |
| **Target Service** | Which train this action applies to |

#### Category filter buttons (ALL, precedence_change, speed_recovery, etc.)
Filter the recommendations list to show only a specific category.

---

## Page 6 — Scenario Comparator (`tab: scenarios`)

**Purpose:** Side-by-side comparison of multiple what-if scenarios. Shows how different disruption types compare against the baseline.

**No API call on this page** — it uses `whatIfData` already loaded.

Shows a structured comparison table of:
- Scenario name
- Severity level
- Services affected
- Delay savings vs. baseline
- Conflicts detected
- Recommendations count

Use this after running multiple scenarios from the What-If Studio or the Operations Hub scenario buttons to compare their impacts.

---

## Page 7 — Timetable Comparator (`tab: timetable`)

**Purpose:** Visual diff of the original published timetable vs. the CP-SAT optimized timetable. Shows exactly which arrival/departure times changed and by how much for each train.

**No API call on this page** — uses `whatIfData` and `optimizationData` already loaded.

| Section | What it shows |
|---|---|
| **Published Timetable** | The original scheduled times straight from the timetable data files |
| **Optimized Timetable** | The CP-SAT adjusted times |
| **Diff highlights** | Changed entries highlighted in amber; unchanged entries in green |
| **Per-service summary** | Max delay, total delay, stations rescheduled |

---

## Page 8 — Research Analytics (`tab: analytics`)

**Purpose:** Academic/research view. Runs the full experimental suite — scalability benchmarks, severity experiments, comparative analysis — and shows quantitative performance metrics. This is the research contribution evidence layer.

**API used:** `GET /api/v1/analytics` (called once at startup; can be refreshed)

### REFRESH ANALYTICS button
Sends `GET /api/v1/analytics?refresh=true` — re-runs the entire experimental suite on the backend (may take 30–60 seconds).

### Content sections

| Section | What it shows |
|---|---|
| **Solver Performance** | CP-SAT solve times across different numbers of services (scalability curve) |
| **Delay Recovery Rate** | How much delay the optimizer recovers across different severity levels (0m, 15m, 25m, 35m) |
| **Conflict Resolution Rate** | % of conflicts resolved at each severity level |
| **Comparative Analysis** | CP-SAT vs. FIFO baseline: delay savings, solve time, conflicts resolved |
| **Scalability Experiments** | Results of running the optimizer with 4, 8, 16, 24, 40 services |
| **Severity Experiments** | Results across NONE, MINOR, MODERATE, SEVERE, CRITICAL disruption levels |
| **Research Metrics** | Summary statistics for publication: mean solve time, mean savings, P95 delay, etc. |

---

## Data Flow Summary — End to End

```
User clicks "Single Train Delay" on Operations Hub
        │
        ▼
page.tsx: handleTriggerScenario("SINGLE")
        │
        ├── Calls: RailwayApi.evaluateWhatIf({
        │       scenario_id: "SCEN_SINGLE_DELAY",
        │       departure_delays: { "SRV_12607_01": 25.0 }
        │   })
        │
        ├── → POST /api/v1/what-if (via Next.js proxy)
        │
        ├── → FastAPI backend:
        │       1. Loads 40 services from data/trains/*.json
        │       2. Runs discrete-event simulation with SRV_12607_01 +25m late
        │       3. Detects cascade conflicts at BBQ, VJM, KOTR
        │       4. Runs CP-SAT solver for optimal recovery schedule
        │       5. Generates ranked recommendations
        │       6. Returns WhatIfResponse JSON
        │
        ├── setWhatIfData(response) → stored in React state
        │
        ├── setActiveTab("what-if") → navigates to What-If Studio
        │
        ▼
What-If Studio renders:
  - Severity banner (e.g., WARNING)
  - Recommendations list (precedence changes at BBQ, KOTR)
  - Delay table (SRV_12607_01: +25m, SRV_12609_01: +8m cascade)
  - Conflicts: 2 junction contention events
```

---

## Quick Reference — All API Endpoints

| Endpoint | Method | Called by | What it does |
|---|---|---|---|
| `/api/v1/health` | GET | Startup, SYNC button | System health check + dataset integrity |
| `/api/v1/network` | GET | Startup, SYNC button | All stations, junctions, routes, services |
| `/api/v1/simulate` | POST | Simulation page (every clock tick), Startup | Discrete-event train simulation |
| `/api/v1/optimize` | POST | CP-SAT page "EXECUTE" button, Startup | CP-SAT mathematical optimization |
| `/api/v1/what-if` | POST | What-If page, Operations Hub scenario buttons, Startup | Full disruption evaluation + recommendations |
| `/api/v1/analytics` | GET | Analytics page load, REFRESH button | Research benchmark suite |

---

## Glossary

| Term | Meaning |
|---|---|
| **CP-SAT** | Constraint Programming - Satisfiability solver from Google OR-Tools. Finds mathematically optimal schedules. |
| **FIFO** | First-In-First-Out. The naive baseline dispatch method (whoever arrives at a junction first gets priority). CP-SAT always beats FIFO. |
| **Precedence decision** | When two trains need the same track, the optimizer decides which one goes first. |
| **TSR** | Temporary Speed Restriction — a stretch of track where trains must slow down due to maintenance or safety. |
| **Headway** | The minimum time gap required between two consecutive trains on the same track. |
| **Junction throat** | A point where multiple routes converge (like BBQ, Basin Bridge) — the highest-contention point in the network. |
| **Counterfactual analysis** | "What happens if you DON'T apply this recommendation?" |
| **SRV_12607_01** | Internal service ID for the 12607 Lalbagh Express (Chennai → Bangalore). |
| **MAS** | Chennai Central station code |
| **MSB** | Chennai Beach station code |
| **AJJ** | Arakkonam Junction station code |
| **BBQ** | Basin Bridge Junction — the critical throat where West + North corridors share track |
| **KOK** | Korukkupet — junction where North corridor and Beach-Bypass corridor merge |
| **VJM** | Vyasarpadi Jeeva — the corridor divergence point for the Beach-side routing |
| **CGL** | Chengalpattu — southern junction connecting South corridor to the Cross Line |
