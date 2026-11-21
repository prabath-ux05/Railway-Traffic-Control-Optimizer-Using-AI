# Frontend UI/UX Hand-off Specification

This document is prepared for the frontend designer/developer. It provides a complete map of all additive backend contract changes, identifies existing hard-coded data in UI components, and outlines the exact backend fields to connect for dynamic rendering—without altering existing UI layouts, styling, or design tokens.

---

## 1. Summary of API Contract Changes (Batches 1–4)

All changes made to the FastAPI backend are strictly additive and backward-compatible.

### 1.1 Infeasible Disruption & Objective Reporting (`/api/v1/optimize`, `/api/v1/what-if`)
* **`solution_available` (boolean):** Indicates if CP-SAT found a valid schedule (`true` for `OPTIMAL` or `FEASIBLE`, `false` for `INFEASIBLE`).
* **`optimized_total_delay_minutes` / `total_optimized_delay_minutes` (float or null):** Returns `null` when `solution_available=false`. **Do not treat 0 as default!**
* **`net_delay_savings_minutes` / `net_delay_savings_percent` (float or null):** Returns `null` when `solution_available=false`.
* **`objective_mode` (string, request & response):** `"WEIGHTED"` (default multi-objective with priority weights) or `"TOTAL_DELAY"` (plain delay minimization).
* **`fifo_weighted_objective` / `optimized_weighted_objective` (float or null):** Multi-objective penalty metrics for baseline vs. optimized plan.
* **Emergency Directive:** When `solution_available=false`, the top recommendation has category `"EMERGENCY"` and title `"No feasible schedule with the blocked resources: [...]"`.

### 1.2 Active Service Registry & Provenance (`/api/v1/network`, `/api/v1/health`)
* **`active_service_count` (int, default 40):** Count of scheduled services with published timetable evidence.
* **`excluded_service_count` (int, default 7):** Count of unscheduled services.
* **`services[].active` (boolean):** `false` for the 7 excluded services (`SRV_40143_01`, `SRV_40144_01`, `SRV_41015_01`, `SRV_41131_01`, `SRV_41132_01`, `SRV_42413_01`, `SRV_42425_01`).
* **`services[].exclusion_reason` (string or null):** `"No published timetable evidence"` for excluded services.
* **`nodes` (array of objects):** Complete list of 107 route nodes with `id`, `name`, `has_station_record`, `node_type`, `corridors`, and `platform_count`.
* **`data_provenance` (object):** Public timetable sources, snapshot date (`null` by default or configured via `DATASET_SNAPSHOT_DATE` env var), and SHA-256 integrity hashes.
* **`integrity_warning_count` / `datasets_integrity_status` (`/api/v1/health`):** Operational dataset health indicators.

### 1.3 Live Runtime Simulation & SSE Streaming (`/api/v1/simulation/*`)
* **`GET /api/v1/simulation/stream` (Server-Sent Events):** Real-time stream with event types:
  - `tick`: Broadcasts updated `current_minute`, `trains`, `conflicts`, `active_occupancies`.
  - `conflict_detected` / `conflict_cleared`: Immediate conflict transition alerts.
  - `event_injected` / `event_removed`: Injected disruption updates.
  - `proposal_ready`: Notifies that a re-optimization proposal is pending controller review.
  - `heartbeat`: Keep-alive event.
* **`POST /api/v1/simulation/control`:** Supports playback control (`is_playing`, `playback_speed` in `[1, 2, 5, 10, 30, 60]`, `seek_minute`). Note speed semantics: `playback_speed = N` means N simulation minutes advance per 60 real-world seconds (e.g. at 60x, 1 real second = 1 simulation minute).
* **`GET / POST / DELETE /api/v1/simulation/events`:** Full lifecycle for dynamic track blockages and speed restrictions.
* **`POST /api/v1/simulation/reoptimize`:** Triggers proposal generation without modifying active plan.
* **`POST /api/v1/simulation/proposals/{id}/accept` / `reject`:** Controller approval actions.

---

## 2. Hard-Coded Frontend Data & Replacement Map

The table below lists every component where hard-coded mock data or static fallbacks exist, and the corresponding dynamic backend field to wire in.

| Component File | Location | Hard-Coded Entity | Dynamic Backend Replacement |
|---|---|---|---|
| `src/components/ScenarioComparisonView.tsx` | Lines 39–140 | `defaultCatalog`: 5 static scenarios (`SCEN_NOMINAL_STATE`, `SCEN_PEAK_CONCURRENCY`, `SCEN_CORRIDOR_BOTTLENECK`, `SCEN_SPEED_RESTRICTION`, `SCEN_COMPOUND_DISRUPTION`) | Wire to `GET /api/v1/analytics/summary` or dynamic calls to `POST /api/v1/what-if`. If `solution_available === false`, display `EMERGENCY` badge and disable net savings bar. |
| `src/components/ResearchAnalyticsView.tsx` | Lines 53–95 | `DEFAULT_AUTHORITATIVE_CORRIDORS`: Fallback array with static service counts and zero delays | Replace with unique corridor names derived from `network.nodes[].corridors` (or `network.services[].corridor`) from `GET /api/v1/network` combined with `corridor_performance` from `GET /api/v1/analytics/summary`. |
| `src/components/ResearchAnalyticsView.tsx` | Lines 300–450 | Static academic comparison tables (Tables I & II from paper draft) | Keep visual table format, but bind dynamic cells to `analyticsData.benchmark_cases` and report values from `/data/evaluation/paper_reproduction/report.json`. |
| `src/components/SimulationMonitor.tsx` | Lines 45–60 | `WINDOW_PRESETS`: Hard-coded time windows (06:00–08:30) | Use `start_minute` and `end_minute` from `GET /api/v1/simulation/state`. |
| `src/components/SimulationMonitor.tsx` | Lines 120–180 | Client-side playback loop via `setInterval` calling `executeSimulationStep` | **Major upgrade opportunity:** Replace client-side interval with SSE subscription: `const evtSource = new EventSource('/api/v1/simulation/stream')`. Set `onmessage` / event listeners to consume `tick` events directly from server. Speed semantics: `playback_speed = N` means N simulation minutes per 60 real seconds. |
| `src/components/NetworkTopologyView.tsx` | Lines 57–75 | `CORRIDORS`: Static array of corridor names and colors | Map to unique corridor names derived from `network.nodes[].corridors` (or `network.services[].corridor`) from `GET /api/v1/network`. (Keep custom SVG coordinate layout `X, Y` as physical schematic layout). |
| `src/components/NetworkTopologyView.tsx` | Lines 410–480 | Node inspection panel station details | Bind directly to `network.nodes[selectedNode]` (populated with `platform_count`, `corridors`, `has_station_record`, `node_type`). |
| `src/components/OptimizationPanel.tsx` | Lines 110–140 | Static service checkbox list | Filter using `network.services.filter(s => s.active)`. Show disabled/grayed-out chip for excluded services with tooltip: `s.exclusion_reason`. |
| `src/components/OptimizationPanel.tsx` | Lines 450–480 | Fixed objective weights display ($w_{\text{delay}}=1.0$, $w_{\text{dev}}=0.5$, etc.) | Display verified weights: $w_{\text{delay}}=1.0$, $w_{\text{weighted}}=2.0$, $w_{\text{max}}=0.5$, $w_{\text{dev}}=0.8$. Provide dropdown to switch `objective_mode` between `"WEIGHTED"` and `"TOTAL_DELAY"`. |
| `src/components/ExplainableRecommendationCard.tsx` (in `DashboardOverview.tsx` / `WhatIfStudio.tsx`) | Lines 80–120 | Static fallback recommendation cards | Note: `DecisionSupportView.tsx` does not exist; recommendations are rendered in `ExplainableRecommendationCard.tsx`. Bind to `whatIfData.recommendations`. Highlight `EMERGENCY` severity in red with warning icon when `whatIfData.solution_available === false`. |

---

## 3. Recommended Frontend Integration Steps

1. **Server-Sent Events (SSE) Adoption in `SimulationMonitor.tsx`:**
   - Instead of driving clock progression via client-side timers, connect to `/api/v1/simulation/stream`.
   - Send playback commands (`play`, `pause`, `speed`, `seek`) to `POST /api/v1/simulation/control`.
   - Update UI state whenever a `tick` SSE event arrives. Notice speed semantics: `playback_speed = N` means N simulation minutes per 60 real seconds (e.g., at 60x, 1 real second = 1 simulation minute).

2. **Infeasible Handling in `OptimizationPanel.tsx` & `WhatIfStudio.tsx`:**
   - Check `data.solution_available === false`.
   - When false:
     - Render delay savings as `"—"` or `"N/A"` (do not display `"0.0 min"` or `"-100%"`).
     - Render red alert banner: *"Infrastructure Capacity Infeasible — Rerouting or Departure Hold Required"*.
     - Render primary directive: `"EMERGENCY: Infrastructure capacity exhausted. Hold departures and verify alternate routing."*

3. **Active Service Filtering in Service Selectors:**
   - Only select from `services.filter(s => s.active)`.
   - Excluded services (e.g. `SRV_40143_01`) should display an info badge: *"Excluded: No published timetable evidence"*.
