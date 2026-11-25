"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { SimulationControlRequest, SimulationStateResponse, TrackSectionSummary } from "@/lib/types";
import { Api, ApiError, type FullNetwork, type NetworkService } from "./api";
import { NODE_MAP } from "./topology";
import { toMinutes } from "./format";

/* ───────────── Network (fetched once per tab, shared) ───────────── */

let networkPromise: Promise<FullNetwork> | null = null;

export function useNetwork() {
  const [network, setNetwork] = useState<FullNetwork | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    setError(null);
    if (!networkPromise) networkPromise = Api.network();
    networkPromise
      .then(setNetwork)
      .catch((e: unknown) => {
        networkPromise = null;
        setError(e instanceof Error ? e.message : "Couldn't load the network.");
      });
  }, []);
  useEffect(load, [load]);
  return { network, error, retry: load };
}

export function activeServices(network: FullNetwork | null): NetworkService[] {
  if (!network) return [];
  return network.services.filter((s) => s.active !== false);
}

/** Services whose scheduled run overlaps a minute window. */
export function servicesInWindow(network: FullNetwork | null, start: number, end: number): NetworkService[] {
  return activeServices(network).filter((s) => {
    const dep = toMinutes(s.scheduled_departure);
    let arr = toMinutes(s.scheduled_arrival);
    if (dep === null) return false;
    if (arr === null) arr = dep + 60;
    if (arr < dep) arr += 1440; // runs past midnight
    return dep < end && arr > start;
  });
}

/* ───────────── Live simulation state (one poller for the whole app) ───────────── */

interface LiveCtx {
  state: SimulationStateResponse | null;
  error: string | null;
  lastUpdated: number | null;
  busy: boolean;
  refresh: () => Promise<void>;
  control: (req: SimulationControlRequest) => Promise<void>;
}

const LiveContext = createContext<LiveCtx | null>(null);

export function LiveProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<SimulationStateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const playing = state?.is_playing ?? false;
  const inflight = useRef(false);

  const refresh = useCallback(async () => {
    if (inflight.current) return;
    inflight.current = true;
    try {
      const s = await Api.state();
      setState(s);
      setError(null);
      setLastUpdated(Date.now());
    } catch (e: unknown) {
      setError(e instanceof ApiError || e instanceof Error ? e.message : "Live state unavailable.");
    } finally {
      inflight.current = false;
    }
  }, []);

  const control = useCallback(async (req: SimulationControlRequest) => {
    setBusy(true);
    try {
      const s = await Api.control(req);
      setState(s);
      setError(null);
      setLastUpdated(Date.now());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Couldn't update the simulation.");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = window.setInterval(() => {
      if (document.visibilityState === "visible") refresh();
    }, playing ? 1000 : 4000);
    return () => window.clearInterval(id);
  }, [refresh, playing]);

  const value = useMemo(() => ({ state, error, lastUpdated, busy, refresh, control }), [state, error, lastUpdated, busy, refresh, control]);
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>;
}

export function useLive(): LiveCtx {
  const ctx = useContext(LiveContext);
  if (!ctx) throw new Error("useLive must be used inside LiveProvider");
  return ctx;
}

/* ───────────── Placement helpers ───────────── */

export function sectionIndex(network: FullNetwork | null): Record<string, TrackSectionSummary> {
  const out: Record<string, TrackSectionSummary> = {};
  for (const s of network?.track_sections ?? []) out[s.id] = s;
  return out;
}

/** Point on the map for a resource id: a node, or the midpoint of a track section. */
export function resourcePoint(resourceId: string | null | undefined, sections: Record<string, TrackSectionSummary>): { x: number; y: number } | null {
  if (!resourceId) return null;
  const node = NODE_MAP[resourceId];
  if (node) return { x: node.x, y: node.y };
  const sec = sections[resourceId];
  if (sec) {
    const a = NODE_MAP[sec.from_node];
    const b = NODE_MAP[sec.to_node];
    if (a && b) return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    if (a) return { x: a.x, y: a.y };
    if (b) return { x: b.x, y: b.y };
  }
  // Junction ids look like JCT_BBQ; throat segments name their nodes.
  const jct = /^JCT_(\w+)$/.exec(resourceId);
  if (jct && NODE_MAP[jct[1]]) return { x: NODE_MAP[jct[1]].x, y: NODE_MAP[jct[1]].y };
  const parts = resourceId.split("_").filter((p) => NODE_MAP[p]);
  if (parts.length >= 2) {
    const a = NODE_MAP[parts[0]];
    const b = NODE_MAP[parts[1]];
    return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
  }
  if (parts.length === 1) return { x: NODE_MAP[parts[0]].x, y: NODE_MAP[parts[0]].y };
  return null;
}
