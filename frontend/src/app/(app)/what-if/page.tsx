"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { Ban, FlaskConical, Plus, Radio, Trash2 } from "lucide-react";
import { DeltaChip, EmptyState, ErrorState, FieldLabel, Numeral, Panel, SectionHead, Segmented, Spinner, StatusChip } from "@/components/glass/ui";
import { servicesInWindow, useLive, useNetwork } from "@/lib/glass/live";
import { Api, type FullWhatIf, type SimEventCreate } from "@/lib/glass/api";
import { NODES } from "@/lib/glass/topology";
import { SHIFTS, cx, fmtNum, serviceShort, shiftForMinute, trainNumber, type ShiftId } from "@/lib/glass/format";
import { useLocalState } from "@/lib/glass/settings";

type Kind = "DEPARTURE_DELAY" | "DWELL_DELAY" | "SPEED_RESTRICTION" | "BLOCKED_SECTION";
interface Disruption {
  id: string;
  kind: Kind;
  service?: string;
  station?: string;
  section?: string;
  minutes?: number;
}
interface SavedRun {
  id: string;
  name: string;
  disruptions: number;
  fifo: number;
  cpsat: number;
  savingPct: number;
  status: string;
  severity: string;
  at: string;
}

const KIND_LABEL: Record<Kind, string> = {
  DEPARTURE_DELAY: "Departure delay",
  DWELL_DELAY: "Dwell spike",
  SPEED_RESTRICTION: "Speed restriction",
  BLOCKED_SECTION: "Blocked section",
};

const PRESETS: { id: string; name: string; services: string[]; disruptions: Omit<Disruption, "id">[] }[] = [
  { id: "peak", name: "West corridor peak", services: ["SRV_12607_01", "SRV_22639_01", "SRV_12675_01"], disruptions: [{ kind: "DEPARTURE_DELAY", service: "SRV_12607_01", minutes: 15 }, { kind: "DEPARTURE_DELAY", service: "SRV_22639_01", minutes: 10 }] },
  { id: "tsr", name: "Basin Bridge speed restriction", services: ["SRV_12607_01", "SRV_12675_01"], disruptions: [{ kind: "SPEED_RESTRICTION", section: "MAS_BBQ_THROAT_SEGMENT_DOWN", minutes: 8 }] },
  { id: "dwell", name: "Perambur dwell spike", services: ["SRV_12675_01", "SRV_16057_01"], disruptions: [{ kind: "DWELL_DELAY", service: "SRV_12675_01", station: "PER", minutes: 12 }] },
  { id: "block", name: "MAS – BBQ throat blocked", services: ["SRV_12607_01", "SRV_12675_01"], disruptions: [{ kind: "BLOCKED_SECTION", section: "MAS_BBQ_THROAT_SEGMENT_DOWN" }, { kind: "BLOCKED_SECTION", section: "BBQ_MAS_THROAT_SEGMENT_UP" }] },
];

const uid = () => Math.random().toString(36).slice(2, 9);

function severityKind(s?: string): "clear" | "info" | "caution" | "conflict" {
  const v = (s || "").toUpperCase();
  if (v === "NORMAL") return "clear";
  if (v === "ADVISORY") return "info";
  if (v === "WARNING") return "caution";
  return "conflict";
}

export default function WhatIfPage() {
  const { network } = useNetwork();
  const { state, refresh } = useLive();
  const [shiftId, setShiftId] = useState<ShiftId | null>(null);
  const [name, setName] = useState("Custom disruption");
  const [presetServices, setPresetServices] = useState<string[] | null>(null);
  const [list, setList] = useState<Disruption[]>([]);
  const [draft, setDraft] = useState<Omit<Disruption, "id">>({ kind: "DEPARTURE_DELAY", minutes: 15 });
  const [result, setResult] = useState<FullWhatIf | null>(null);
  const [busy, setBusy] = useState<"eval" | "apply" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [applied, setApplied] = useState<string | null>(null);
  const [saved, setSaved] = useLocalState<SavedRun[]>("cdto.scenarios.v1", []);

  const shift = SHIFTS.find((s) => s.id === shiftId) ?? (state ? shiftForMinute(state.start_minute) : SHIFTS[0]);
  const scope = useMemo(() => servicesInWindow(network, shift.start, shift.end), [network, shift.start, shift.end]);
  const allActive = useMemo(() => (network?.services ?? []).filter((s) => s.active !== false), [network]);
  const serviceOptions = presetServices ? allActive.filter((s) => presetServices.includes(s.id)) : scope;
  const sections = useMemo(() => [...(network?.track_sections ?? [])].sort((a, b) => a.id.localeCompare(b.id)), [network]);
  const sectionTime = (id?: string) => sections.find((s) => s.id === id)?.travel_time_minutes;
  const stations = useMemo(() => NODES.filter((n) => n.type !== "STATION").sort((a, b) => a.name.localeCompare(b.name)), []);

  const valid = Boolean(
    (draft.kind === "DEPARTURE_DELAY" && draft.service && (draft.minutes ?? 0) > 0) ||
      (draft.kind === "DWELL_DELAY" && draft.service && draft.station && (draft.minutes ?? 0) > 0) ||
      (draft.kind === "SPEED_RESTRICTION" && draft.section && (draft.minutes ?? 0) > 0) ||
      (draft.kind === "BLOCKED_SECTION" && draft.section),
  );

  const applyPreset = (id: string) => {
    const p = PRESETS.find((x) => x.id === id);
    if (!p) return;
    // Keep only services and sections that exist in this network's catalogue.
    const known = new Set(allActive.map((s) => s.id));
    const knownSections = new Set(sections.map((s) => s.id));
    const svcs = p.services.filter((s) => known.has(s));
    setName(p.name);
    setPresetServices(svcs.length ? svcs : null);
    setList(
      p.disruptions
        .filter((d) => (!d.service || known.has(d.service)) && (!d.section || knownSections.has(d.section)))
        .map((d) => ({ ...d, id: uid() })),
    );
    setResult(null);
    setApplied(null);
  };

  const request = () => {
    const known = new Set(allActive.map((s) => s.id));
    const ids = (presetServices ?? scope.map((s) => s.id)).filter((id) => known.has(id));
    const departure_delays: Record<string, number> = {};
    const station_delays: Record<string, Record<string, number>> = {};
    const speed_restrictions: Record<string, number> = {};
    const blocked_sections: string[] = [];
    for (const d of list) {
      if (d.kind === "DEPARTURE_DELAY" && d.service) departure_delays[d.service] = d.minutes ?? 0;
      if (d.kind === "DWELL_DELAY" && d.service && d.station) station_delays[d.service] = { ...(station_delays[d.service] || {}), [d.station]: d.minutes ?? 0 };
      if (d.kind === "SPEED_RESTRICTION" && d.section) speed_restrictions[d.section] = d.minutes ?? 0;
      if (d.kind === "BLOCKED_SECTION" && d.section) blocked_sections.push(d.section);
    }
    return { scenario_id: `WHATIF_${uid()}`, scenario_name: name || "What-if scenario", service_ids: ids, departure_delays, station_delays, speed_restrictions, blocked_sections };
  };

  const evaluate = async () => {
    setBusy("eval");
    setError(null);
    setApplied(null);
    try {
      const r = await Api.whatIf(request());
      setResult(r);
      setSaved((prev) =>
        [
          {
            id: uid(),
            name: name || "What-if scenario",
            disruptions: list.length,
            fifo: r.total_baseline_delay_minutes,
            cpsat: r.total_optimized_delay_minutes,
            savingPct: r.net_delay_savings_percent,
            status: r.solver_status,
            severity: r.operational_severity,
            at: new Date().toISOString(),
          },
          ...prev,
        ].slice(0, 12),
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "The evaluation didn't complete.");
    } finally {
      setBusy(null);
    }
  };

  const applyLive = async () => {
    setBusy("apply");
    setError(null);
    setApplied(null);
    try {
      const from = state?.current_minute;
      const events: SimEventCreate[] = list.map((d) => {
        if (d.kind === "DEPARTURE_DELAY") return { event_type: d.kind, service_id: d.service, delay_minutes: d.minutes, from_minute: from, description: name };
        if (d.kind === "DWELL_DELAY") return { event_type: d.kind, service_id: d.service, station_id: d.station, delay_minutes: d.minutes, from_minute: from, description: name };
        if (d.kind === "SPEED_RESTRICTION") {
          const base = sectionTime(d.section) || 1;
          return { event_type: d.kind, section_id: d.section, speed_factor: Math.max(1, (d.minutes ?? base) / base), from_minute: from, description: name };
        }
        return { event_type: d.kind, section_id: d.section, from_minute: from, description: name };
      });
      const created: string[] = [];
      for (const ev of events) created.push((await Api.injectEvent(ev)).id);
      setApplied(`${created.length} disruption${created.length > 1 ? "s" : ""} injected into the live network (${created.join(", ")}).`);
      refresh();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "The live network didn't accept the disruption.");
    } finally {
      setBusy(null);
    }
  };

  const infeasible = Boolean(result && (result.solution_available === false || ["INFEASIBLE", "MODEL_INVALID", "UNKNOWN"].includes((result.solver_status || "").toUpperCase())));
  const maxSaved = Math.max(1, ...saved.map((s) => Math.max(s.fifo, s.cpsat || 0)));

  return (
    <div className="flex flex-col gap-6">
      <SectionHead level={1} className="rise px-1" title="Ask what if" description="Build a disruption, evaluate it safely against FIFO and CP-SAT, compare it with earlier scenarios, and push it to the live network only when you mean to." />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.25fr)]">
        <Panel className="p-6" data-tour="studio">
          <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">Disruption studio</h2>
          <div className="mt-4">
            <FieldLabel>Start from a known case</FieldLabel>
            <div className="flex flex-wrap gap-2">
              {PRESETS.map((p) => (
                <button key={p.id} type="button" className="btn btn-secondary btn-sm" onClick={() => applyPreset(p.id)}>
                  {p.name}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-6 grid gap-4">
            <div>
              <FieldLabel htmlFor="wi-name">Scenario name</FieldLabel>
              <input id="wi-name" className="field" value={name} onChange={(e) => setName(e.target.value)} maxLength={80} />
            </div>
            <div>
              <FieldLabel hint={presetServices ? `${presetServices.length} services from the preset` : `${scope.length} services`}>Scope</FieldLabel>
              {presetServices ? (
                <div className="flex flex-wrap items-center gap-2">
                  {presetServices.map((s) => (
                    <span key={s} className="chip font-mono">
                      {serviceShort(s)}
                    </span>
                  ))}
                  <button type="button" className="btn btn-quiet btn-sm" onClick={() => setPresetServices(null)}>
                    Use a shift instead
                  </button>
                </div>
              ) : (
                <Segmented label="Shift scope" value={shift.id} onChange={(v) => setShiftId(v)} options={SHIFTS.map((s) => ({ value: s.id, label: s.window, title: s.label }))} />
              )}
            </div>
          </div>

          <div className="mt-6 rounded-[14px] border border-line p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="sm:col-span-2">
                <FieldLabel htmlFor="wi-kind">Add a disruption</FieldLabel>
                <select id="wi-kind" className="field" value={draft.kind} onChange={(e) => setDraft({ kind: e.target.value as Kind, minutes: e.target.value === "SPEED_RESTRICTION" ? 8 : 15 })}>
                  {Object.entries(KIND_LABEL).map(([k, l]) => (
                    <option key={k} value={k}>
                      {l}
                    </option>
                  ))}
                </select>
              </div>
              {draft.kind === "DEPARTURE_DELAY" || draft.kind === "DWELL_DELAY" ? (
                <div className={draft.kind === "DWELL_DELAY" ? "" : "sm:col-span-2"}>
                  <FieldLabel htmlFor="wi-svc">Train</FieldLabel>
                  <select id="wi-svc" className="field" value={draft.service ?? ""} onChange={(e) => setDraft({ ...draft, service: e.target.value || undefined })}>
                    <option value="">Choose a train…</option>
                    {serviceOptions.map((s) => (
                      <option key={s.id} value={s.id}>
                        {trainNumber(s.train_id)} {s.train_name} · {s.scheduled_departure}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
              {draft.kind === "DWELL_DELAY" ? (
                <div>
                  <FieldLabel htmlFor="wi-stn">Station</FieldLabel>
                  <select id="wi-stn" className="field" value={draft.station ?? ""} onChange={(e) => setDraft({ ...draft, station: e.target.value || undefined })}>
                    <option value="">Choose a station…</option>
                    {stations.map((n) => (
                      <option key={n.id} value={n.id}>
                        {n.name} ({n.id})
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
              {draft.kind === "SPEED_RESTRICTION" || draft.kind === "BLOCKED_SECTION" ? (
                <div className={draft.kind === "BLOCKED_SECTION" ? "sm:col-span-2" : ""}>
                  <FieldLabel htmlFor="wi-sec">Track section</FieldLabel>
                  <select id="wi-sec" className="field font-mono !text-[0.8125rem]" value={draft.section ?? ""} onChange={(e) => setDraft({ ...draft, section: e.target.value || undefined })}>
                    <option value="">Choose a section…</option>
                    {sections.map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.id}
                      </option>
                    ))}
                  </select>
                </div>
              ) : null}
              {draft.kind !== "BLOCKED_SECTION" ? (
                <div>
                  <FieldLabel htmlFor="wi-min" hint={draft.kind === "SPEED_RESTRICTION" && draft.section ? `normally ${sectionTime(draft.section) ?? "—"} min` : undefined}>
                    {draft.kind === "SPEED_RESTRICTION" ? "Restricted run time (min)" : "Delay (min)"}
                  </FieldLabel>
                  <input id="wi-min" type="number" min={1} max={240} className="field tnum" value={draft.minutes ?? ""} onChange={(e) => setDraft({ ...draft, minutes: Number(e.target.value) })} />
                </div>
              ) : null}
            </div>
            <button
              type="button"
              className="btn btn-secondary btn-sm mt-4"
              disabled={!valid}
              onClick={() => {
                setList((l) => [...l, { ...draft, id: uid() }]);
                setResult(null);
              }}
            >
              <Plus className="h-4 w-4" aria-hidden /> Add to scenario
            </button>
          </div>

          <div className="mt-5">
            <span className="label">In this scenario</span>
            {list.length ? (
              <ul className="mt-2 flex flex-col gap-2">
                {list.map((d) => (
                  <li key={d.id} className={cx("flex items-center justify-between gap-3 rounded-[12px] border px-3 py-2 text-[0.8125rem]", d.kind === "BLOCKED_SECTION" ? "hatch border-[rgba(242,106,91,0.4)]" : "border-line")}>
                    <span className="min-w-0 truncate text-fg-1">
                      <span className="font-medium">{KIND_LABEL[d.kind]}</span>{" "}
                      <span className="text-fg-2">
                        {d.service ? serviceShort(d.service) : d.section}
                        {d.station ? ` at ${d.station}` : ""}
                        {d.minutes && d.kind !== "BLOCKED_SECTION" ? (d.kind === "SPEED_RESTRICTION" ? ` · ${d.minutes} min run` : ` · +${d.minutes} min`) : ""}
                      </span>
                    </span>
                    <button type="button" className="icon-btn !h-8 !w-8 shrink-0" aria-label="Remove this disruption" onClick={() => setList((l) => l.filter((x) => x.id !== d.id))}>
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-2 text-[0.8125rem] text-fg-2">Nothing yet. With no disruptions, the evaluation shows the shift as timetabled.</p>
            )}
          </div>

          <div className="mt-6 flex flex-wrap gap-3">
            <button type="button" className="btn btn-primary" disabled={busy !== null || (!presetServices && !scope.length)} onClick={evaluate}>
              {busy === "eval" ? <Spinner /> : <FlaskConical className="h-4 w-4" aria-hidden />} Evaluate safely
            </button>
            <button type="button" className="btn btn-secondary" disabled={busy !== null || !list.length} onClick={applyLive} title="Inject these disruptions into the live simulation">
              {busy === "apply" ? <Spinner /> : <Radio className="h-4 w-4" aria-hidden />} Apply to live network
            </button>
          </div>
          {applied ? (
            <p className="mt-3 text-[0.8125rem] text-clear">
              {applied}{" "}
              <Link href="/network" className="text-champagne underline">
                See it on the map
              </Link>
            </p>
          ) : null}
          {error ? (
            <div className="mt-4">
              <ErrorState message={error} compact />
            </div>
          ) : null}
        </Panel>

        <Panel className="p-6">
          <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">Result</h2>
          {result ? (
            <div className="mt-4 flex flex-col gap-6">
              <div className="flex flex-wrap items-center gap-2">
                <StatusChip kind={severityKind(result.operational_severity)}>{result.operational_severity.toLowerCase().replace(/^\w/, (m) => m.toUpperCase())}</StatusChip>
                <StatusChip kind={infeasible ? "conflict" : "clear"}>{result.solver_status}</StatusChip>
                <span className="text-[0.75rem] text-fg-3">
                  {fmtNum(result.solve_time_seconds, 3)} s · {result.active_services_count} services · {result.delayed_services_count} delayed
                </span>
              </div>
              {infeasible ? (
                <div className="hatch rounded-[14px] border border-[rgba(242,106,91,0.45)] p-5">
                  <p className="flex items-center gap-2 text-[1rem] font-medium text-fg-1">
                    <Ban className="h-5 w-5 text-conflict" aria-hidden /> No conflict-free schedule exists
                  </p>
                  <p className="mt-2 max-w-[60ch] text-[0.875rem] leading-relaxed text-fg-1">
                    With these disruptions the modelled topology has no alternative path, so CP-SAT proves the case infeasible instead of returning a schedule. Remove a blockage, widen the window, or plan a manual diversion.
                  </p>
                </div>
              ) : (
                <dl className="grid grid-cols-3 gap-4 border-y border-line py-5">
                  <div>
                    <dt className="label">FIFO</dt>
                    <dd className="mt-2">
                      <Numeral value={fmtNum(result.total_baseline_delay_minutes, 0)} unit="min" size="m" tone="bronze" />
                    </dd>
                  </div>
                  <div>
                    <dt className="label">CP-SAT</dt>
                    <dd className="mt-2">
                      <Numeral value={fmtNum(result.total_optimized_delay_minutes, 0)} unit="min" size="m" tone="violet" />
                    </dd>
                  </div>
                  <div>
                    <dt className="label">Change</dt>
                    <dd className="mt-3">
                      <DeltaChip value={-result.net_delay_savings_percent} unit="%" digits={1} good={result.net_delay_savings_percent >= 0} />
                    </dd>
                  </div>
                </dl>
              )}
              <div className="grid gap-6 lg:grid-cols-2">
                <div>
                  <h3 className="label">Conflicts, by priority</h3>
                  {result.prioritized_conflicts.length ? (
                    <ul className="mt-2 flex flex-col gap-2">
                      {result.prioritized_conflicts.slice(0, 5).map((pc) => (
                        <li key={pc.conflict.conflict_id} className="rounded-[12px] border border-line p-3 text-[0.8125rem]">
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate font-medium text-fg-1">{pc.conflict.resource_id}</span>
                            <StatusChip kind={pc.priority_tier.startsWith("TIER_1") ? "conflict" : pc.priority_tier.startsWith("TIER_2") ? "caution" : "info"}>{pc.priority_tier.replace(/^TIER_\d_/, "").toLowerCase()}</StatusChip>
                          </div>
                          <p className="mt-1 text-fg-2">
                            {pc.conflict.affected_service_ids.map(serviceShort).join(" vs ")} · up to {fmtNum(pc.max_delay_minutes)} min
                          </p>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-[0.8125rem] text-fg-2">None detected.</p>
                  )}
                </div>
                <div>
                  <h3 className="label">Bottlenecks</h3>
                  {result.identified_bottlenecks.length ? (
                    <ul className="mt-2 flex flex-col gap-2">
                      {result.identified_bottlenecks.slice(0, 5).map((b) => (
                        <li key={b.resource_id} className="rounded-[12px] border border-line p-3 text-[0.8125rem]">
                          <div className="flex items-center justify-between gap-2">
                            <span className="truncate font-medium text-fg-1">{b.resource_id}</span>
                            <span className="text-fg-2 tnum">{b.contention_count} trains</span>
                          </div>
                          <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[rgba(255,240,224,0.06)]">
                            <div className="h-full rounded-full bg-caution" style={{ width: `${Math.min(100, b.criticality_score)}%` }} />
                          </div>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-[0.8125rem] text-fg-2">No contested resources.</p>
                  )}
                </div>
              </div>
              {result.recommendations[0] ? (
                <div className="rounded-[14px] border border-[rgba(139,108,255,0.35)] bg-[rgba(139,108,255,0.06)] p-4">
                  <span className="label !text-[#b3a2ff]">Top recommendation</span>
                  <p className="mt-2 text-[0.9375rem] font-medium text-fg-1">{result.recommendations[0].title}</p>
                  <p className="mt-1 text-[0.8125rem] leading-relaxed text-fg-2">{result.recommendations[0].reason}</p>
                  <Link href="/optimizer" className="mt-3 inline-block text-[0.8125rem] text-champagne underline">
                    See every recommendation and its reasoning
                  </Link>
                </div>
              ) : null}
            </div>
          ) : (
            <EmptyState icon={<FlaskConical className="h-5 w-5" />} title="Evaluate a scenario to see its impact" body="Pick a known case or add your own disruptions, then evaluate. The live network is untouched until you apply." />
          )}
        </Panel>
      </div>

      <Panel className="p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">Scenario comparison</h2>
            <p className="mt-1 text-[0.8125rem] text-fg-2">Every scenario you evaluate in this browser, newest first.</p>
          </div>
          {saved.length ? (
            <button type="button" className="btn btn-quiet btn-sm" onClick={() => setSaved([])}>
              Clear all
            </button>
          ) : null}
        </div>
        {saved.length ? (
          <div className="mt-4 overflow-x-auto">
            <table className="table-glass">
              <thead>
                <tr>
                  <th>Scenario</th>
                  <th>Disruptions</th>
                  <th className="w-[32%]">FIFO vs CP-SAT (min)</th>
                  <th className="!text-right">Change</th>
                  <th>Severity</th>
                  <th>Solver</th>
                  <th>
                    <span className="sr-only">Remove</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {saved.map((s) => (
                  <tr key={s.id}>
                    <td className="text-fg-1">{s.name}</td>
                    <td className="tnum">{s.disruptions}</td>
                    <td>
                      <div className="flex flex-col gap-1" role="img" aria-label={`FIFO ${s.fifo} minutes, CP-SAT ${s.cpsat} minutes`}>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[rgba(255,240,224,0.06)]">
                            <div className="h-full rounded-full bg-bronze" style={{ width: `${(s.fifo / maxSaved) * 100}%` }} />
                          </div>
                          <span className="w-12 text-right font-mono text-[0.75rem] text-[#dcae84]">{fmtNum(s.fifo)}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[rgba(255,240,224,0.06)]">
                            <div className="h-full rounded-full bg-violet" style={{ width: `${((s.cpsat || 0) / maxSaved) * 100}%` }} />
                          </div>
                          <span className="w-12 text-right font-mono text-[0.75rem] text-[#b3a2ff]">{fmtNum(s.cpsat)}</span>
                        </div>
                      </div>
                    </td>
                    <td className="!text-right">
                      <DeltaChip value={-s.savingPct} unit="%" digits={1} good={s.savingPct >= 0} />
                    </td>
                    <td>
                      <StatusChip kind={severityKind(s.severity)}>{s.severity.toLowerCase()}</StatusChip>
                    </td>
                    <td className="font-mono text-[0.75rem]">{s.status}</td>
                    <td>
                      <button type="button" className="icon-btn !h-8 !w-8" aria-label={`Remove ${s.name}`} onClick={() => setSaved((p) => p.filter((x) => x.id !== s.id))}>
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No scenarios yet" body="Each evaluation lands here so you can compare disruptions side by side." />
        )}
      </Panel>
    </div>
  );
}
