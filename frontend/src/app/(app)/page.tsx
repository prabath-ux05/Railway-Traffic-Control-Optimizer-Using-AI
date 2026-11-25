"use client";

import React, { useMemo } from "react";
import Link from "next/link";
import { ArrowRight, CircleHelp, Cpu, FileDown, FlaskConical, Waypoints } from "lucide-react";
import { LivingNetwork } from "@/components/glass/LivingNetwork";
import { Numeral, Panel, Skeleton } from "@/components/glass/ui";
import { useTour } from "@/components/glass/Tour";
import { activeServices, sectionIndex, useLive, useNetwork } from "@/lib/glass/live";
import { CORRIDORS, corridorIdFromLabel } from "@/lib/glass/topology";
import { fmtClock, fmtNum } from "@/lib/glass/format";
import { useSettings } from "@/lib/glass/settings";

const LOOP = [
  { title: "Digital twin", body: "Stations, platforms, 354 track sections, junctions and timetables become one simulated division.", href: "/network" },
  { title: "Conflict detection", body: "Track, headway, junction and incompatible-movement conflicts are found as trains move.", href: "/network" },
  { title: "Feasible FIFO", body: "A physically feasible first-in, first-out schedule is the honest baseline to beat.", href: "/optimizer" },
  { title: "CP-SAT optimiser", body: "Google OR-Tools solves a priority-weighted, conflict-free schedule in well under a second.", href: "/optimizer" },
  { title: "Controller decides", body: "Every change arrives as an explained proposal you accept or reject. Nothing applies itself.", href: "/optimizer" },
];

const DOING = [
  { icon: Waypoints, title: "Watch the division run", body: "Trains on the map, conflicts where they happen, playback through any shift.", href: "/network" },
  { icon: Cpu, title: "Compare FIFO with CP-SAT", body: "Train-by-train timetables, the weighted objective, and the AI's reasoning.", href: "/optimizer" },
  { icon: FlaskConical, title: "Test a disruption first", body: "Delays, dwell spikes, speed restrictions and blockages, evaluated safely.", href: "/what-if" },
  { icon: FileDown, title: "Hand over the shift", body: "A 6-hour control chart and train register as PDF or CSV.", href: "/export" },
];

export default function HomePage() {
  const { network } = useNetwork();
  const { state } = useLive();
  const { settings } = useSettings();
  const tour = useTour();
  const sections = useMemo(() => sectionIndex(network), [network]);
  const snap = state?.snapshot;
  const running = snap?.train_positions.filter((p) => !["ARRIVED", "COMPLETED", "SCHEDULED", "NOT_STARTED"].includes((p.status || "").toUpperCase())).length ?? 0;
  const active = activeServices(network);
  const perCorridor = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of active) {
      const id = corridorIdFromLabel(s.corridor);
      if (id) counts[id] = (counts[id] || 0) + 1;
    }
    return counts;
  }, [active]);

  return (
    <div className="flex flex-col gap-6">
      {/* Hero slab: explanation left, the live network right */}
      <Panel className="rise overflow-hidden !rounded-[24px]">
        <div className="dots pointer-events-none absolute inset-0" aria-hidden />
        <div className="relative grid lg:grid-cols-[minmax(0,1.05fr)_minmax(0,1fr)]">
          <div className="flex flex-col justify-between gap-10 p-6 sm:p-10 lg:p-12">
            <div>
              <h1 className="max-w-[16ch] text-[2.5rem] font-semibold leading-[1.02] tracking-[-0.035em] text-fg-1 sm:text-[3.25rem] xl:text-[4rem]">
                AI-Assisted Railway Traffic Optimization
              </h1>
              <p className="mt-5 max-w-[56ch] text-[1rem] leading-relaxed text-fg-2 sm:text-[1.0625rem]">
                A live digital twin of Southern Railway&apos;s Chennai Division. It detects conflicts as trains move, builds a physically feasible FIFO baseline, and asks Google OR-Tools CP-SAT for a better, conflict-free schedule. The section controller stays in charge: every change is a proposal with its reasoning attached.
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <Link href="/network" className="btn btn-primary">
                  Open the live network <ArrowRight className="h-4 w-4" aria-hidden />
                </Link>
                <button type="button" onClick={tour.start} className="btn btn-secondary">
                  <CircleHelp className="h-4 w-4" aria-hidden /> Take the 1-minute tour
                </button>
              </div>
            </div>
            <dl className="grid grid-cols-3 gap-6 border-t border-line pt-6">
              <div>
                <dt className="label">Running now</dt>
                <dd className="mt-2">{state ? <Numeral value={running} size="m" /> : <Skeleton className="h-7 w-12" />}</dd>
              </div>
              <div>
                <dt className="label">Conflicts</dt>
                <dd className="mt-2">{state ? <Numeral value={snap?.detected_conflicts.length ?? 0} size="m" tone={(snap?.detected_conflicts.length ?? 0) > 0 ? "conflict" : "clear"} /> : <Skeleton className="h-7 w-12" />}</dd>
              </div>
              <div>
                <dt className="label">Sim clock</dt>
                <dd className="mt-2">{state ? <Numeral value={fmtClock(state.current_minute)} size="m" /> : <Skeleton className="h-7 w-16" />}</dd>
              </div>
            </dl>
          </div>
          <div className="relative min-h-[300px] border-t border-line lg:border-l lg:border-t-0">
            <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_70%_30%,rgba(91,61,245,0.16),transparent_60%)]" aria-hidden />
            <LivingNetwork
              sections={sections}
              positions={snap?.train_positions}
              conflicts={snap?.detected_conflicts}
              tilt={settings.mapTilt}
              reducedMotion={settings.reduceMotion}
              compact
              className="relative h-full min-h-[300px] w-full p-4 sm:min-h-[420px]"
              ariaLabel="Live preview of the Chennai Division network with running trains"
            />
            <Link href="/network" className="glass absolute bottom-4 left-4 flex items-center gap-2 !rounded-full px-4 py-2 text-[0.8125rem] text-fg-1 transition-colors hover:bg-[var(--glass-strong)]">
              <span className="h-2 w-2 rounded-full bg-clear" aria-hidden /> Live · {snap?.train_positions.length ?? 0} trains in this window
            </Link>
          </div>
        </div>
      </Panel>

      {/* The loop, drawn as a line with stations */}
      <Panel className="p-6 sm:p-8">
        <h2 className="text-[1.375rem] font-semibold tracking-[-0.02em] text-fg-1 sm:text-[1.75rem]">How a decision is made</h2>
        <p className="mt-2 max-w-[64ch] text-[0.9375rem] leading-relaxed text-fg-2">Five stages run in order on every disruption. The line below is the order they run in.</p>
        <ol className="relative mt-8 grid gap-8 md:grid-cols-5 md:gap-4">
          <span className="absolute left-[7px] top-2 h-[calc(100%-1rem)] w-px bg-[linear-gradient(var(--champagne),var(--violet))] md:left-0 md:top-[7px] md:h-px md:w-full md:bg-[linear-gradient(90deg,var(--champagne),var(--violet))]" aria-hidden />
          {LOOP.map((s, i) => (
            <li key={s.title} className="relative pl-8 md:pl-0 md:pt-8">
              <span className="absolute left-0 top-0.5 grid h-[15px] w-[15px] place-items-center rounded-full border-2 border-ink-0 bg-champagne md:top-0" style={{ background: i === 4 ? "var(--violet)" : undefined }} aria-hidden />
              <Link href={s.href} className="group block">
                <h3 className="text-[1rem] font-semibold text-fg-1 transition-colors group-hover:text-champagne">{s.title}</h3>
                <p className="mt-1.5 text-[0.8125rem] leading-relaxed text-fg-2">{s.body}</p>
              </Link>
            </li>
          ))}
        </ol>
      </Panel>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        {/* The division in numbers */}
        <Panel className="p-6 sm:p-8">
          <h2 className="text-[1.375rem] font-semibold tracking-[-0.02em] text-fg-1">The division, as modelled</h2>
          <dl className="mt-6 grid grid-cols-2 gap-x-6 gap-y-6 sm:grid-cols-3">
            {[
              { label: "Corridors", value: 7 },
              { label: "Track sections", value: network?.track_section_count },
              { label: "Station records", value: network?.station_count },
              { label: "Routes", value: network?.route_count },
              { label: "Junctions", value: network?.junction_count },
              { label: "Active services", value: network?.active_service_count ?? active.length, hint: network ? `${network.excluded_service_count ?? 0} excluded: no timetable evidence` : undefined },
            ].map((m) => (
              <div key={m.label}>
                <dt className="label">{m.label}</dt>
                <dd className="mt-2">{m.value !== undefined && m.value !== null ? <Numeral value={fmtNum(m.value)} size="m" /> : <Skeleton className="h-7 w-14" />}</dd>
                {m.hint ? <dd className="mt-1 text-[0.75rem] leading-snug text-fg-3">{m.hint}</dd> : null}
              </div>
            ))}
          </dl>
          <ul className="mt-8 divide-y divide-[var(--line)] border-t border-line">
            {CORRIDORS.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-4 py-3">
                <span className="flex min-w-0 items-center gap-3">
                  <span className="h-[3px] w-6 shrink-0 rounded-full" style={{ background: c.color }} aria-hidden />
                  <span className="truncate text-[0.875rem] text-fg-1">{c.full}</span>
                </span>
                <span className="shrink-0 text-[0.8125rem] text-fg-2 tnum">{perCorridor[c.id] ? `${perCorridor[c.id]} services` : "Topology only"}</span>
              </li>
            ))}
          </ul>
        </Panel>

        {/* What you can do */}
        <Panel className="p-6 sm:p-8">
          <h2 className="text-[1.375rem] font-semibold tracking-[-0.02em] text-fg-1">What you can do here</h2>
          <ul className="mt-4 divide-y divide-[var(--line)]">
            {DOING.map((d) => (
              <li key={d.title}>
                <Link href={d.href} className="group flex items-start gap-4 py-4">
                  <d.icon className="mt-0.5 h-5 w-5 shrink-0 text-champagne" strokeWidth={1.75} aria-hidden />
                  <span className="min-w-0 flex-1">
                    <span className="block text-[0.9375rem] font-medium text-fg-1">{d.title}</span>
                    <span className="mt-1 block text-[0.8125rem] leading-relaxed text-fg-2">{d.body}</span>
                  </span>
                  <ArrowRight className="mt-1 h-4 w-4 shrink-0 text-fg-3 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:text-fg-1" aria-hidden />
                </Link>
              </li>
            ))}
          </ul>
          <p className="mt-6 rounded-[14px] border border-line p-4 text-[0.8125rem] leading-relaxed text-fg-2">
            A simulation-based decision-support prototype, accepted at CICT 2026. It runs on public timetable data and has not been deployed on Indian Railways. The previous dashboard is still available as the{" "}
            <Link href="/classic" className="text-champagne underline">
              classic view
            </Link>
            .
          </p>
        </Panel>
      </div>
    </div>
  );
}
