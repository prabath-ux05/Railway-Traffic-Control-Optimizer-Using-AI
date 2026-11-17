/**
 * frontend/src/lib/api.ts
 * ~~~~~~~~~~~~~~~~~~~~~~~
 * Typed REST API client for the Railway Traffic Optimization Backend.
 */

import {
  AnalyticsResponse,
  HealthResponse,
  NetworkResponse,
  OptimizeRequest,
  OptimizeResponse,
  SimulationControlRequest,
  SimulationStateResponse,
  SimulateRequest,
  SimulateResponse,
  WhatIfRequest,
  WhatIfResponse,
} from "./types";

// Use Next.js proxy (rewrites in next.config.ts) so requests stay same-origin → no CORS
const API_BASE_URL = "";

async function fetchJson<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        ...options.headers,
      },
    });

    if (!res.ok) {
      let errorDetail = `HTTP ${res.status}: ${res.statusText}`;
      try {
        const errorJson = await res.json();
        if (errorJson.detail) {
          errorDetail = typeof errorJson.detail === "string" 
            ? errorJson.detail 
            : JSON.stringify(errorJson.detail);
        }
      } catch {
        // use default statusText
      }
      throw new Error(errorDetail);
    }

    return (await res.json()) as T;
  } catch (err: any) {
    if (err.name === "TypeError" && err.message?.includes("fetch")) {
      throw new Error(
        `Unable to reach Railway Backend API at ${API_BASE_URL}. Ensure FastAPI is running on port 8000.`
      );
    }
    throw err;
  }
}

export const RailwayApi = {
  /**
   * Check backend system diagnostics & dataset integrity.
   */
  async getHealth(): Promise<HealthResponse> {
    return fetchJson<HealthResponse>("/api/v1/health");
  },

  /**
   * Retrieve complete Chennai Division network topology, stations, junctions, routes, and services.
   */
  async getNetwork(): Promise<NetworkResponse> {
    return fetchJson<NetworkResponse>("/api/v1/network");
  },

  /**
   * Execute discrete-event train movement simulation and get live positions, occupancies, and conflicts.
   */
  async simulate(req: SimulateRequest = {}): Promise<SimulateResponse> {
    return fetchJson<SimulateResponse>("/api/v1/simulate", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /**
   * Trigger CP-SAT mathematical schedule optimization.
   */
  async optimize(req: OptimizeRequest = {}): Promise<OptimizeResponse> {
    return fetchJson<OptimizeResponse>("/api/v1/optimize", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /**
   * Run full end-to-end What-If disruption evaluation and get decision support recommendations.
   */
  async evaluateWhatIf(req: WhatIfRequest = {}): Promise<WhatIfResponse> {
    return fetchJson<WhatIfResponse>("/api/v1/what-if", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /**
   * Fetch research evaluation analytics, benchmark comparisons, and scalability sweep.
   */
  async getAnalytics(refresh: boolean = false): Promise<AnalyticsResponse> {
    const query = refresh ? "?refresh=true" : "";
    return fetchJson<AnalyticsResponse>(`/api/v1/analytics${query}`);
  },

  /**
   * Retrieve authoritative persistent simulation state across browser refreshes.
   */
  async getSimulationState(): Promise<SimulationStateResponse> {
    return fetchJson<SimulationStateResponse>("/api/v1/simulation/state");
  },

  /**
   * Update authoritative simulation control parameters (playback, scrub, active fleet, delays).
   */
  async controlSimulation(req: SimulationControlRequest): Promise<SimulationStateResponse> {
    return fetchJson<SimulationStateResponse>("/api/v1/simulation/control", {
      method: "POST",
      body: JSON.stringify(req),
    });
  },

  /**
   * Reset simulation state to start of window.
   */
  async resetSimulation(clearDelays: boolean = false): Promise<SimulationStateResponse> {
    return fetchJson<SimulationStateResponse>(`/api/v1/simulation/reset?clear_delays=${clearDelays}`, {
      method: "POST",
    });
  },
};

