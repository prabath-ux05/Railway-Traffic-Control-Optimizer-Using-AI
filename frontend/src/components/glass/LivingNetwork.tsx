"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import type { DetectedConflict, TrackSectionSummary, TrainPositionState } from "@/lib/types";
import { CORRIDOR_BY_ID, EDGES, NODES, NODE_MAP, type CorridorId } from "@/lib/glass/topology";
import { resourcePoint } from "@/lib/glass/live";
import { TRAIN_TYPE_COLOR, trainNumber } from "@/lib/glass/format";
import type { SimEventRecord } from "@/lib/glass/api";

const FULL_VIEW = { x: 20, y: -40, w: 1210, h: 790 };

interface Props {
  sections: Record<string, TrackSectionSummary>;
  positions?: TrainPositionState[];
  conflicts?: DetectedConflict[];
  events?: SimEventRecord[];
  selectedNode?: string | null;
  onSelectNode?: (id: string | null) => void;
  selectedTrain?: string | null;
  onSelectTrain?: (id: string | null) => void;
  focusCorridor?: CorridorId | "ALL";
  tilt?: boolean;
  reducedMotion?: boolean;
  compact?: boolean;
  className?: string;
  ariaLabel?: string;
}

type View = typeof FULL_VIEW;

function useAnimatedView(target: View, reduced: boolean): View {
  const [view, setView] = useState<View>(target);
  const from = useRef<View>(target);
  const raf = useRef(0);
  useEffect(() => {
    if (reduced) {
      setView(target);
      from.current = target;
      return;
    }
    const start = performance.now();
    const origin = { ...from.current };
    const dur = 650;
    const ease = (t: number) => 1 - Math.pow(1 - t, 4);
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      const k = ease(t);
      const next = {
        x: origin.x + (target.x - origin.x) * k,
        y: origin.y + (target.y - origin.y) * k,
        w: origin.w + (target.w - origin.w) * k,
        h: origin.h + (target.h - origin.h) * k,
      };
      setView(next);
      from.current = next;
      if (t < 1) raf.current = requestAnimationFrame(step);
    };
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf.current);
  }, [target.x, target.y, target.w, target.h, reduced]); // eslint-disable-line react-hooks/exhaustive-deps
  return view;
}

export function LivingNetwork({
  sections,
  positions = [],
  conflicts = [],
  events = [],
  selectedNode = null,
  onSelectNode,
  selectedTrain = null,
  onSelectTrain,
  focusCorridor = "ALL",
  tilt = true,
  reducedMotion = false,
  compact = false,
  className,
  ariaLabel = "Chennai Division network map",
}: Props) {
  const target = useMemo<View>(() => {
    if (selectedNode && NODE_MAP[selectedNode]) {
      const n = NODE_MAP[selectedNode];
      const w = 440;
      const h = w * (FULL_VIEW.h / FULL_VIEW.w);
      return { x: n.x - w / 2, y: n.y - h / 2, w, h };
    }
    return FULL_VIEW;
  }, [selectedNode]);
  const view = useAnimatedView(target, reducedMotion);
  const zoom = FULL_VIEW.w / view.w;

  const trains = useMemo(() => {
    return positions
      .filter((p) => !["ARRIVED", "COMPLETED"].includes((p.status || "").toUpperCase()))
      .map((p) => {
        const pt = resourcePoint(p.current_track_section, sections) || resourcePoint(p.current_node, sections) || resourcePoint(p.current_station, sections) || resourcePoint(p.origin, sections);
        return pt ? { p, pt } : null;
      })
      .filter(Boolean) as { p: TrainPositionState; pt: { x: number; y: number } }[];
  }, [positions, sections]);

  const conflictPoints = useMemo(() => {
    const seen = new Set<string>();
    return conflicts
      .map((c) => ({ c, pt: resourcePoint(c.resource_id, sections) }))
      .filter((x) => {
        if (!x.pt) return false;
        const key = `${Math.round(x.pt.x)}:${Math.round(x.pt.y)}`;
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }) as { c: DetectedConflict; pt: { x: number; y: number } }[];
  }, [conflicts, sections]);

  const eventSegments = useMemo(() => {
    return events
      .filter((e) => e.section_id && (e.event_type === "BLOCKED_SECTION" || e.event_type === "SPEED_RESTRICTION"))
      .map((e) => {
        const sec = sections[e.section_id as string];
        const a = sec ? NODE_MAP[sec.from_node] : null;
        const b = sec ? NODE_MAP[sec.to_node] : null;
        if (!a || !b) {
          const pt = resourcePoint(e.section_id, sections);
          return pt ? { e, a: { x: pt.x - 8, y: pt.y }, b: { x: pt.x + 8, y: pt.y } } : null;
        }
        return { e, a, b };
      })
      .filter(Boolean) as { e: SimEventRecord; a: { x: number; y: number }; b: { x: number; y: number } }[];
  }, [events, sections]);

  const dim = (corridors: string[]) => focusCorridor !== "ALL" && !corridors.includes(focusCorridor);
  const labelScale = 1 / Math.max(1, zoom * 0.75);
  const showMinorLabels = zoom > 1.8;

  return (
    <div className={className} style={{ perspective: tilt ? "1600px" : undefined }}>
      <svg
        viewBox={`${view.x} ${view.y} ${view.w} ${view.h}`}
        role="img"
        aria-label={ariaLabel}
        className="h-full w-full select-none"
        style={{
          transform: tilt ? "rotateX(24deg) scale(1.06)" : "none",
          transformOrigin: "50% 60%",
          transition: reducedMotion ? undefined : "transform 650ms var(--ease-out)",
        }}
        onClick={(e) => {
          if (e.target === e.currentTarget) onSelectNode?.(null);
        }}
      >
        <defs>
          <filter id="ln-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="4" />
          </filter>
          <pattern id="ln-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <rect width="6" height="6" fill="rgba(242,106,91,0.18)" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--conflict)" strokeWidth="2.4" />
          </pattern>
          {Object.entries(TRAIN_TYPE_COLOR).map(([type, color]) => (
            <radialGradient key={type} id={`halo-${type}`}>
              <stop offset="0" stopColor={color} stopOpacity="0.55" />
              <stop offset="1" stopColor={color} stopOpacity="0" />
            </radialGradient>
          ))}
        </defs>

        {/* corridor glow + line */}
        <g>
          {EDGES.map((ed) => {
            const a = NODE_MAP[ed.from];
            const b = NODE_MAP[ed.to];
            if (!a || !b) return null;
            const color = CORRIDOR_BY_ID[ed.corridor]?.color ?? "#8E877C";
            const faded = focusCorridor !== "ALL" && ed.corridor !== focusCorridor;
            return (
              <line key={`g-${ed.from}-${ed.to}`} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={color} strokeWidth={7} strokeLinecap="round" opacity={faded ? 0.03 : compact ? 0.16 : 0.22} filter="url(#ln-glow)" />
            );
          })}
          {EDGES.map((ed) => {
            const a = NODE_MAP[ed.from];
            const b = NODE_MAP[ed.to];
            if (!a || !b) return null;
            const color = CORRIDOR_BY_ID[ed.corridor]?.color ?? "#8E877C";
            const faded = focusCorridor !== "ALL" && ed.corridor !== focusCorridor;
            return (
              <line
                key={`l-${ed.from}-${ed.to}`}
                x1={a.x}
                y1={a.y}
                x2={b.x}
                y2={b.y}
                stroke={color}
                strokeWidth={2.6 / Math.max(1, zoom * 0.6)}
                strokeLinecap="round"
                strokeDasharray={ed.dashed ? "6 5" : undefined}
                opacity={faded ? 0.12 : 0.85}
              />
            );
          })}
        </g>

        {/* live disruptions on the track */}
        <g>
          {eventSegments.map(({ e, a, b }) =>
            e.event_type === "BLOCKED_SECTION" ? (
              <line key={e.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="url(#ln-hatch)" strokeWidth={10} strokeLinecap="round">
                <title>{`Blocked: ${e.section_id}`}</title>
              </line>
            ) : (
              <line key={e.id} x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="var(--caution)" strokeWidth={6} strokeDasharray="3 4" strokeLinecap="round" opacity={0.9}>
                <title>{`Speed restriction: ${e.section_id}`}</title>
              </line>
            ),
          )}
        </g>

        {/* stations */}
        <g>
          {NODES.map((n) => {
            const faded = dim(n.corridors);
            const sel = selectedNode === n.id;
            const major = n.type !== "STATION";
            const color = CORRIDOR_BY_ID[n.corridors[0]]?.color ?? "#F4EFE8";
            const r = (n.type === "TERMINUS" ? 6.5 : n.type === "JUNCTION" ? 5.8 : n.type === "MAJOR" ? 4.4 : 2.6) / Math.max(1, zoom * 0.55);
            return (
              <g
                key={n.id}
                data-testid={`glass-station-${n.id}`}
                opacity={faded ? 0.25 : 1}
                style={{ cursor: onSelectNode ? "pointer" : undefined }}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectNode?.(sel ? null : n.id);
                }}
              >
                <circle cx={n.x} cy={n.y} r={11 / Math.max(1, zoom * 0.55)} fill="transparent" />
                {sel ? <circle cx={n.x} cy={n.y} r={r + 6 / zoom} fill="none" stroke="var(--champagne)" strokeWidth={1.4 / zoom} /> : null}
                <circle
                  cx={n.x}
                  cy={n.y}
                  r={r}
                  fill={major ? "#0A090C" : color}
                  stroke={n.type === "JUNCTION" ? "var(--champagne)" : major ? "#F4EFE8" : "none"}
                  strokeWidth={major ? 1.4 / Math.max(1, zoom * 0.6) : 0}
                  opacity={major ? 1 : 0.75}
                />
                {(!compact && (major || showMinorLabels)) || sel ? (
                  <text
                    x={n.x}
                    y={n.y - (r + 5 / zoom)}
                    textAnchor="middle"
                    fontSize={(major ? 14 : 11) * labelScale}
                    fill={sel ? "var(--champagne)" : major ? "#D8D1C7" : "#8E877C"}
                    fontWeight={sel || n.type === "TERMINUS" ? 600 : 500}
                    style={{ paintOrder: "stroke", stroke: "#0A090C", strokeWidth: 3 * labelScale, strokeLinejoin: "round" }}
                  >
                    {showMinorLabels || sel ? n.name : n.id}
                  </text>
                ) : null}
                <title>{`${n.name} (${n.id})`}</title>
              </g>
            );
          })}
        </g>

        {/* conflicts */}
        <g>
          {conflictPoints.map(({ c, pt }) => (
            <g key={c.conflict_id} transform={`translate(${pt.x} ${pt.y})`}>
              {!reducedMotion ? <circle r={9} fill="none" stroke="var(--conflict)" strokeWidth={1.5} className="conflict-ring" /> : null}
              <circle r={10 / Math.max(1, zoom * 0.6)} fill="url(#ln-hatch)" stroke="var(--conflict)" strokeWidth={1.2 / Math.max(1, zoom * 0.6)} />
              <title>{`${c.conflict_type.replace(/_/g, " ").toLowerCase()} at ${c.resource_id}: ${c.affected_service_ids.join(", ")}`}</title>
            </g>
          ))}
        </g>

        {/* trains */}
        <g>
          {trains.map(({ p, pt }) => {
            const type = p.train_type || "SUBURBAN_EMU";
            const color = TRAIN_TYPE_COLOR[type] || "#F4EFE8";
            const sel = selectedTrain === p.service_id;
            const haloR = (15 + Math.min(p.delay_minutes || 0, 40) / 1.6) / Math.max(1, zoom * 0.55);
            return (
              <g
                key={p.service_id}
                style={{ transform: `translate(${pt.x}px, ${pt.y}px)`, transition: reducedMotion ? undefined : "transform 900ms var(--ease-in-out)", cursor: onSelectTrain ? "pointer" : undefined }}
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectTrain?.(sel ? null : p.service_id);
                }}
              >
                <circle r={haloR} fill={`url(#halo-${type})`} />
                <circle r={(sel ? 7.5 : 5.6) / Math.max(1, zoom * 0.55)} fill={color} stroke="#0A090C" strokeWidth={1.6 / Math.max(1, zoom * 0.55)} />
                {sel || (zoom > 1.8 && !compact) ? (
                  <text y={-(haloR + 2)} textAnchor="middle" fontSize={13 * labelScale} fill="#F4EFE8" fontWeight={600} style={{ paintOrder: "stroke", stroke: "#0A090C", strokeWidth: 3 * labelScale }}>
                    {trainNumber(p.train_id)}
                  </text>
                ) : null}
                <title>{`${p.train_name} · ${trainNumber(p.train_id)}${p.delay_minutes ? ` · +${Math.round(p.delay_minutes)} min` : ""}`}</title>
              </g>
            );
          })}
        </g>
      </svg>
    </div>
  );
}
