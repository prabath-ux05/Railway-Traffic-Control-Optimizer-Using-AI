/**
 * Typed client for the Glass Spatial dashboard. Reuses the backend contract from lib/types.ts and adds the
 * live-engine endpoints (events, proposals) the classic client never called.
 */
import type {
  NetworkResponse,
  OptimizeRequest,
  OptimizeResponse,
  SimulationControlRequest,
  SimulationStateResponse,
  WhatIfRequest,
  WhatIfResponse,
  HealthResponse,
} from "@/lib/types";

export interface NetworkService {
  id: string;
  service_id?: string;
  train_id: string;
  train_name?: string | null;
  train_type?: string | null;
  service_type?: string | null;
  origin: string;
  destination: string;
  route_id: string;
  priority_class: string;
  corridor?: string | null;
  scheduled_departure?: string | null;
  scheduled_arrival?: string | null;
  active?: boolean;
  exclusion_reason?: string | null;
}

export type FullNetwork = Omit<NetworkResponse, "services"> & {
  services: NetworkService[];
  active_service_count?: number;
  excluded_service_count?: number;
  nodes?: number;
  data_provenance?: {
    dataset_sha256_hashes?: Record<string, string>;
    timetable_sources?: Record<string, number>;
  };
};

export type FullOptimize = OptimizeResponse & {
  fifo_weighted_objective?: number | null;
  optimized_weighted_objective?: number | null;
  objective_mode?: string;
  solution_available?: boolean;
  time_resolution?: number;
};

export type FullWhatIf = WhatIfResponse & {
  fifo_weighted_objective?: number | null;
  optimized_weighted_objective?: number | null;
  solution_available?: boolean;
};

export interface HealthFull extends HealthResponse {
  status: string;
}

export type SimEventType = "DEPARTURE_DELAY" | "DWELL_DELAY" | "SPEED_RESTRICTION" | "BLOCKED_SECTION";

export interface SimEventCreate {
  event_type: SimEventType;
  service_id?: string;
  station_id?: string;
  section_id?: string;
  delay_minutes?: number;
  speed_factor?: number;
  from_minute?: number;
  to_minute?: number;
  description?: string;
}

export interface SimEventRecord extends SimEventCreate {
  id: string;
  from_minute: number;
  to_minute: number;
  created_at_sim_minute: number;
  created_at_wall_clock: string;
}

export interface Proposal {
  proposal_id: string;
  created_at_sim_minute: number;
  created_at_wall_clock: string;
  solver_status: string;
  solution_available: boolean;
  total_baseline_delay_minutes: number;
  total_optimized_delay_minutes: number | null;
  net_delay_savings_minutes: number | null;
  net_delay_savings_percent: number | null;
  operational_severity: string;
  recommendations: Record<string, any>[];
  adjusted_timetables: Record<string, any>;
  precedence_decisions: { resource_id: string; first_service_id: string; second_service_id: string; reason: string }[];
  status: "PENDING" | "ACCEPTED" | "REJECTED" | string;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/v1${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", Accept: "application/json", ...(init?.headers || {}) },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("The railway backend isn't reachable. Start it on port 8000, then retry.", 0);
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep status text */
    }
    if (res.status === 500 || res.status === 502 || res.status === 503 || res.status === 504) {
      detail = "The railway backend isn't responding. Start it on port 8000, then retry.";
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

const post = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body ?? {}) });

export const Api = {
  health: () => call<HealthFull>("/health"),
  network: () => call<FullNetwork>("/network"),
  state: () => call<SimulationStateResponse>("/simulation/state"),
  control: (req: SimulationControlRequest) => call<SimulationStateResponse>("/simulation/control", post(req)),
  reset: (clearDelays = false) => call<SimulationStateResponse>(`/simulation/reset?clear_delays=${clearDelays}`, { method: "POST" }),
  events: () => call<SimEventRecord[]>("/simulation/events"),
  injectEvent: (req: SimEventCreate) => call<SimEventRecord>("/simulation/events", post(req)),
  removeEvent: (id: string) => call<{ status: string }>(`/simulation/events/${encodeURIComponent(id)}`, { method: "DELETE" }),
  reoptimize: () => call<Proposal>("/simulation/reoptimize", { method: "POST" }),
  acceptProposal: (id: string) => call<{ status: string; message: string }>(`/simulation/proposals/${encodeURIComponent(id)}/accept`, { method: "POST" }),
  rejectProposal: (id: string) => call<{ status: string; message: string }>(`/simulation/proposals/${encodeURIComponent(id)}/reject`, { method: "POST" }),
  optimize: (req: OptimizeRequest) => call<FullOptimize>("/optimize", post(req)),
  whatIf: (req: WhatIfRequest) => call<FullWhatIf>("/what-if", post(req)),
};
