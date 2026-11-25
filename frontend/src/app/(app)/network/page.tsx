"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Ban, Gauge, Layers, MapPin, Pause, Play, RotateCcw, TrainFront, Trash2, X } from "lucide-react";
import { LivingNetwork } from "@/components/glass/LivingNetwork";
import { Breadcrumb, EmptyState, ErrorState, Legend, Numeral, Panel, Segmented, Spinner, StatusChip, trainStatusKind, trainStatusLabel } from "@/components/glass/ui";
import { activeServices, sectionIndex, useLive, useNetwork } from "@/lib/glass/live";
import { Api, type SimEventRecord } from "@/lib/glass/api";
import { CORRIDORS, CORRIDOR_BY_ID, NODES, NODE_MAP, type CorridorId } from "@/lib/glass/topology";
import { SHIFTS, SPEEDS, TRAIN_TYPE_COLOR, TRAIN_TYPE_LABEL, cx, fmtClock, fmtNum, serviceShort, shiftForMinute, trainNumber } from "@/lib/glass/format";
import { useSettings } from "@/lib/glass/settings";

const RUNNING = ["RUNNING", "IN_TRANSIT", "DWELLING", "AT_STATION", "HELD"];

export default function NetworkPage() {
  const { network, error: netError, retry } = useNetwork();
  const { state, error: liveError, control, busy } = useLive();
  const { settings } = useSettings();
  const [focus, setFocus] = useState<CorridorId | "ALL">("ALL");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedTrain, setSelectedTrain] = useState<string | null>(null);
  const [events, setEvents] = useState<SimEventRecord[]>([]);
  const [scrub, setScrub] = useState<number | null>(null);
  const [eventError, setEventError] = useState<string | null>(null);

  const sections = useMemo(() => sectionIndex(network), [network]);
  const snap = state?.snapshot;
  const positions = snap?.train_positions ?? [];
  const conflicts = snap?.detected_conflicts ?? [];
  const active = activeServices(network);

  const loadEvents = useCallback(() => {
    Api.events()
      .then((e) => {
        setEvents(e);
        setEventError(null);
      })
      .catch((e: Error) => setEventError(e.message));
  }, []);
  useEffect(() => {
    loadEvents();
    const id = globalThis.setInterval(loadEvents, 6000);
    return () => globalThis.clearInterval(id);
  }, [loadEvents]);

  const running = positions.filter((p) => RUNNING.includes((p.status || "").toUpperCase()));
  const moved = positions.filter((p) => !["SCHEDULED", "NOT_STARTED"].includes((p.status || "").toUpperCase()));
  const onTime = moved.length ? (moved.filter((p) => (p.delay_minutes || 0) < 5).length / moved.length) * 100 : null;
  const shift = state ? shiftForMinute(state.start_minute) : SHIFTS[0];
  const fleetSmall = state && active.length > 0 && state.selected_service_ids.length < Math.min(10, active.length);

  const loadFleet = (s: (typeof SHIFTS)[number] = shift) =>
    control({ service_ids: active.map((a) => a.id), start_minute: s.start, end_minute: s.end, current_minute: s.start, playback_speed: settings.defaultSpeed });

  const node = selectedNode ? NODE_MAP[selectedNode] : null;
  const train = selectedTrain ? positions.find((p) => p.service_id === selectedTrain) ?? null : null;
  const clearSelection = () => {
    setSelectedNode(null);
    setSelectedTrain(null);
  };
  const crumbs = [
    { label: "Chennai Division", onClick: () => { clearSelection(); setFocus("ALL"); } },
    ...(focus !== "ALL" ? [{ label: CORRIDOR_BY_ID[focus].label, onClick: clearSelection }] : []),
    ...(node ? [{ label: node.name }] : []),
    ...(train && !node ? [{ label: `${trainNumber(train.train_id)} ${train.train_name}` }] : []),
  ];

  const stationTrains = node
    ? positions.filter((p) => p.current_node === node.id || p.current_station === node.id || (p.current_track_section && (sections[p.current_track_section]?.from_node === node.id || sections[p.current_track_section]?.to_node === node.id)))
    : [];
  const stationCalls = node
    ? (network?.timetable ?? [])
        .filter((t) => t.station_id === node.id)
        .map((t) => ({ t, s: network?.services.find((s) => s.id === t.service_id) }))
        .filter((x) => x.s && x.s.active !== false)
        .sort((a, b) => (a.t.departure || a.t.arrival || "").localeCompare(b.t.departure || b.t.arrival || ""))
        .slice(0, 8)
    : [];
  const nodeConflicts = node ? conflicts.filter((c) => c.resource_id === node.id || c.resource_id.includes(node.id)) : [];

  const win = state ? { start: state.start_minute, end: state.end_minute } : { start: 360, end: 720 };
  const curMin = scrub ?? state?.current_minute ?? win.start;
  const progress = Math.min(100, Math.max(0, ((curMin - win.start) / Math.max(1, win.end - win.start)) * 100));
  const commitScrub = () => {
    if (scrub !== null) control({ current_minute: scrub }).finally(() => setScrub(null));
  };

  if (netError) return <ErrorState message={netError} onRetry={retry} />;

  return (
    <div className="flex flex-col gap-6">
      <Panel className="rise overflow-hidden !rounded-[24px]">
        <div className="relative h-[min(78vh,820px)] min-h-[940px] sm:min-h-[600px]" data-tour="map">
          <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_75%_20%,rgba(91,61,245,0.14),transparent_55%),radial-gradient(ellipse_at_15%_90%,rgba(217,130,43,0.1),transparent_50%)]" aria-hidden />
          <div className="dots pointer-events-none absolute inset-0" aria-hidden />
          <LivingNetwork
            sections={sections}
            positions={positions}
            conflicts={conflicts}
            events={events}
            selectedNode={selectedNode}
            onSelectNode={(id) => {
              setSelectedNode(id);
              if (id) setSelectedTrain(null);
            }}
            selectedTrain={selectedTrain}
            onSelectTrain={(id) => {
              setSelectedTrain(id);
              if (id) setSelectedNode(null);
            }}
            focusCorridor={focus}
            tilt={settings.mapTilt && !selectedNode}
            reducedMotion={settings.reduceMotion}
            className="absolute inset-0 px-1 pb-[15rem] pt-[18rem] sm:px-4 sm:pb-24 sm:pt-6"
          />

          {/* top-left: breadcrumb + health slab */}
          <div className="pointer-events-none absolute left-3 right-3 top-3 flex flex-col gap-3 sm:left-4 sm:right-auto sm:top-4 sm:w-[560px] sm:max-w-[calc(100%-2rem)]">
            <div className="glass pointer-events-auto !rounded-[16px] px-4 py-3">
              <Breadcrumb items={crumbs} />
            </div>
            <div className="glass pointer-events-auto grid grid-cols-2 !rounded-[16px] sm:grid-cols-4">
              {[
                { label: "Running", value: state ? running.length : null, unit: `/${positions.length}`, tone: "default" as const },
                { label: "On time", value: onTime === null ? "—" : Math.round(onTime), unit: onTime === null ? "" : "%", tone: onTime !== null && onTime < 80 ? ("caution" as const) : ("clear" as const) },
                { label: "Conflicts", value: state ? conflicts.length : null, unit: "", tone: conflicts.length ? ("conflict" as const) : ("clear" as const) },
                { label: "Network delay", value: state ? fmtNum(snap?.total_network_delay_minutes ?? 0) : null, unit: "min", tone: (snap?.total_network_delay_minutes ?? 0) > 0 ? ("caution" as const) : ("default" as const) },
              ].map((m, i) => (
                <div key={m.label} className={cx("px-4 py-3", i > 0 && "sm:border-l sm:border-line", i % 2 === 1 && "border-l border-line", i > 1 && "border-t border-line sm:border-t-0")}>
                  <span className="label">{m.label}</span>
                  <div className="mt-1.5">{m.value === null ? <span className="skeleton inline-block h-6 w-10" /> : <Numeral value={m.value} unit={m.unit} size="s" tone={m.tone} className="!text-[1.5rem]" />}</div>
                </div>
              ))}
            </div>
            {fleetSmall ? (
              <div className="glass pointer-events-auto flex flex-wrap items-center justify-between gap-3 !rounded-[16px] px-4 py-3">
                <p className="text-[0.8125rem] text-fg-2">
                  Only {state?.selected_service_ids.length} of {active.length} active services are in the live window.
                </p>
                <button type="button" className="btn btn-primary btn-sm" disabled={busy} onClick={() => loadFleet()}>
                  {busy ? <Spinner /> : <TrainFront className="h-4 w-4" aria-hidden />} Load all {active.length}
                </button>
              </div>
            ) : null}
            {liveError ? (
              <div className="pointer-events-auto">
                <ErrorState message={liveError} compact />
              </div>
            ) : null}
          </div>

          {/* top-right: focus & station jump (wide screens) */}
          <div className="absolute right-4 top-4 hidden flex-col items-end gap-2 2xl:flex">
            <Segmented
              label="Corridor focus"
              size="sm"
              value={focus}
              onChange={(v) => {
                setFocus(v);
                setSelectedNode(null);
              }}
              options={[{ value: "ALL" as const, label: "All" }, ...CORRIDORS.map((c) => ({ value: c.id, label: c.label }))]}
              className="glass !rounded-full"
            />
            <select aria-label="Jump to station" className="field glass !w-56 !rounded-full !py-2 text-[0.8125rem]" value={selectedNode ?? ""} onChange={(e) => setSelectedNode(e.target.value || null)}>
              <option value="">Jump to station…</option>
              {NODES.filter((n) => n.type !== "STATION")
                .sort((a, b) => a.name.localeCompare(b.name))
                .map((n) => (
                  <option key={n.id} value={n.id}>
                    {n.name} ({n.id})
                  </option>
                ))}
            </select>
          </div>

          {/* bottom: playback */}
          <div data-tour="playback" className="glass absolute bottom-3 left-3 right-3 flex flex-col gap-3 !rounded-[18px] p-3 sm:bottom-4 sm:left-1/2 sm:right-auto sm:w-[min(880px,calc(100%-2rem))] sm:-translate-x-1/2 sm:p-4">
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                className="btn btn-primary !h-11 !w-11 !p-0"
                disabled={!state || busy}
                onClick={() => control({ is_playing: !state?.is_playing })}
                aria-label={state?.is_playing ? "Pause the simulation" : "Play the simulation"}
              >
                {state?.is_playing ? <Pause className="h-4 w-4 fill-white" /> : <Play className="h-4 w-4 fill-white" />}
              </button>
              <div className="min-w-[5.5rem]">
                <span className="label">Sim time</span>
                <p className="font-mono text-[1.125rem] text-fg-1 tnum">{state ? fmtClock(curMin) : "—:—"}</p>
              </div>
              <Segmented
                label="Playback speed"
                size="sm"
                value={state?.playback_speed ?? 1}
                onChange={(v) => control({ playback_speed: v })}
                options={SPEEDS.map((s) => ({ value: s, label: `${s}×`, title: `${s} simulated minutes per real minute` }))}
              />
              <div className="ml-auto flex items-center gap-2">
                <select
                  aria-label="Shift window"
                  className="field !w-auto !rounded-full !py-2 text-[0.8125rem]"
                  value={shift.id}
                  onChange={(e) => {
                    const s = SHIFTS.find((x) => x.id === e.target.value) ?? SHIFTS[0];
                    control({ start_minute: s.start, end_minute: s.end, current_minute: s.start });
                  }}
                >
                  {SHIFTS.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label} · {s.window}
                    </option>
                  ))}
                </select>
                <button type="button" className="icon-btn" title="Back to the start of the window" aria-label="Back to the start of the window" onClick={() => control({ current_minute: win.start, is_playing: false })}>
                  <RotateCcw className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <span className="font-mono text-[0.75rem] text-fg-3 tnum">{fmtClock(win.start)}</span>
              <div className="relative flex-1">
                <div className="pointer-events-none absolute left-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-[linear-gradient(90deg,var(--champagne),var(--violet))]" style={{ width: `${progress}%` }} aria-hidden />
                <input
                  type="range"
                  aria-label="Scrub simulation time"
                  min={win.start}
                  max={win.end}
                  step={1}
                  value={curMin}
                  onChange={(e) => setScrub(Number(e.target.value))}
                  onPointerUp={commitScrub}
                  onKeyUp={commitScrub}
                  className="glass-range relative w-full"
                />
              </div>
              <span className="font-mono text-[0.75rem] text-fg-3 tnum">{fmtClock(win.end)}</span>
            </div>
          </div>

          {/* inspector */}
          {node || train ? (
            <aside className="glass rise absolute bottom-[11rem] right-3 z-10 max-h-[52%] w-[min(360px,calc(100%-1.5rem))] overflow-y-auto !rounded-[18px] p-5 sm:bottom-auto sm:right-4 sm:top-4 sm:max-h-[60%] 2xl:top-[6.5rem]" aria-label="Inspector">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  {node ? (
                    <>
                      <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">{node.name}</h2>
                      <p className="mt-1 text-[0.8125rem] text-fg-2">
                        <span className="font-mono">{node.id}</span> · {node.type.charAt(0) + node.type.slice(1).toLowerCase()} · {node.corridors.map((c) => CORRIDOR_BY_ID[c]?.label ?? c).join(", ")}
                      </p>
                    </>
                  ) : train ? (
                    <>
                      <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">{train.train_name}</h2>
                      <p className="mt-1 text-[0.8125rem] text-fg-2">
                        <span className="font-mono">{trainNumber(train.train_id)}</span> · {TRAIN_TYPE_LABEL[train.train_type || ""] ?? train.train_type} · {train.corridor_name}
                      </p>
                    </>
                  ) : null}
                </div>
                <button type="button" className="icon-btn -mr-2 -mt-2 !h-8 !w-8" aria-label="Close the inspector" onClick={clearSelection}>
                  <X className="h-4 w-4" />
                </button>
              </div>

              {train ? (
                <dl className="mt-5 grid grid-cols-2 gap-x-4 gap-y-4 border-t border-line pt-4 text-[0.8125rem]">
                  <div>
                    <dt className="label">Status</dt>
                    <dd className="mt-1.5">
                      <StatusChip kind={trainStatusKind(train.status, train.delay_minutes)}>{trainStatusLabel(train.status, train.delay_minutes)}</StatusChip>
                    </dd>
                  </div>
                  <div>
                    <dt className="label">Delay</dt>
                    <dd className="mt-1.5">
                      <Numeral value={Math.round(train.delay_minutes || 0)} unit="min" size="s" tone={(train.delay_minutes || 0) >= 5 ? "caution" : "clear"} />
                    </dd>
                  </div>
                  <div>
                    <dt className="label">Route</dt>
                    <dd className="mt-1.5 text-fg-1">
                      {train.origin} → {train.destination}
                    </dd>
                  </div>
                  <div>
                    <dt className="label">Timetable</dt>
                    <dd className="mt-1.5 font-mono text-fg-1">
                      {train.scheduled_departure} – {train.scheduled_arrival}
                    </dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="label">Now at</dt>
                    <dd className="mt-1.5 text-fg-1">{train.current_track_section ? `Section ${train.current_track_section}` : NODE_MAP[train.current_node || ""]?.name ?? train.current_node ?? "Not yet departed"}</dd>
                  </div>
                </dl>
              ) : null}

              {node ? (
                <div className="mt-5 flex flex-col gap-5 border-t border-line pt-4">
                  {nodeConflicts.length ? (
                    <div className="hatch rounded-[12px] border border-[rgba(242,106,91,0.4)] p-3">
                      <p className="text-[0.8125rem] font-medium text-conflict">
                        {nodeConflicts.length} conflict{nodeConflicts.length > 1 ? "s" : ""} here
                      </p>
                      <p className="mt-1 text-[0.75rem] text-fg-1">{nodeConflicts[0].description}</p>
                    </div>
                  ) : null}
                  <div>
                    <h3 className="label">Trains here now</h3>
                    {stationTrains.length ? (
                      <ul className="mt-2 flex flex-col gap-2">
                        {stationTrains.map((p) => (
                          <li key={p.service_id} className="flex items-center justify-between gap-2 text-[0.8125rem]">
                            <button type="button" className="truncate text-left text-fg-1 hover:text-champagne" onClick={() => { setSelectedTrain(p.service_id); setSelectedNode(null); }}>
                              <span className="font-mono">{trainNumber(p.train_id)}</span> {p.train_name}
                            </button>
                            <StatusChip kind={trainStatusKind(p.status, p.delay_minutes)}>{trainStatusLabel(p.status, p.delay_minutes)}</StatusChip>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-[0.8125rem] text-fg-2">No train is at or next to this station right now.</p>
                    )}
                  </div>
                  <div>
                    <h3 className="label">Scheduled calls</h3>
                    {stationCalls.length ? (
                      <ul className="mt-2 flex flex-col gap-1.5">
                        {stationCalls.map(({ t, s }) => (
                          <li key={`${t.service_id}-${t.stop_sequence}`} className="flex items-center justify-between gap-3 text-[0.8125rem]">
                            <span className="truncate text-fg-2">
                              <span className="font-mono text-fg-1">{trainNumber(s?.train_id)}</span> {s?.train_name}
                            </span>
                            <span className="font-mono text-fg-1 tnum">{t.departure || t.arrival}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-[0.8125rem] text-fg-2">No timetabled stops recorded here; trains pass through.</p>
                    )}
                  </div>
                </div>
              ) : null}
            </aside>
          ) : null}
        </div>
      </Panel>

      {/* below the map: legend, compact focus controls, trains, disruptions */}
      <div className="flex flex-wrap items-center justify-between gap-4 px-1">
        <Legend
          items={[
            ...Object.entries(TRAIN_TYPE_COLOR).map(([k, c]) => ({ color: c, label: TRAIN_TYPE_LABEL[k] })),
            { color: "var(--caution)", label: "Speed restriction", dashed: true },
            { color: "var(--conflict)", label: "Conflict / blockage", hatch: true },
          ]}
        />
        <div className="flex flex-wrap items-center gap-2 2xl:hidden">
          <Layers className="h-4 w-4 text-fg-3" aria-hidden />
          <select aria-label="Corridor focus" className="field !w-auto !rounded-full !py-2 text-[0.8125rem]" value={focus} onChange={(e) => setFocus(e.target.value as CorridorId | "ALL")}>
            <option value="ALL">All corridors</option>
            {CORRIDORS.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <select aria-label="Jump to station" className="field !w-auto !rounded-full !py-2 text-[0.8125rem]" value={selectedNode ?? ""} onChange={(e) => setSelectedNode(e.target.value || null)}>
            <option value="">Station…</option>
            {NODES.filter((n) => n.type !== "STATION")
              .sort((a, b) => a.name.localeCompare(b.name))
              .map((n) => (
                <option key={n.id} value={n.id}>
                  {n.name}
                </option>
              ))}
          </select>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <Panel className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 p-5 pb-3">
            <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">Trains in this window</h2>
            <span className="text-[0.8125rem] text-fg-2">
              {positions.length} services · {shift.label} {shift.window}
            </span>
          </div>
          {positions.length ? (
            <div className="max-h-[420px] overflow-auto">
              <table className="table-glass">
                <thead>
                  <tr>
                    <th>Train</th>
                    <th>Type</th>
                    <th>Route</th>
                    <th>Location</th>
                    <th className="!text-right">Delay</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {[...positions]
                    .sort((a, b) => (b.delay_minutes || 0) - (a.delay_minutes || 0))
                    .map((p) => (
                      <tr key={p.service_id} className={cx("cursor-pointer", selectedTrain === p.service_id && "bg-[var(--glass-strong)]")} onClick={() => { setSelectedTrain(p.service_id); setSelectedNode(null); }}>
                        <td className="text-fg-1">
                          <span className="font-mono">{trainNumber(p.train_id)}</span> <span className="text-fg-2">{p.train_name}</span>
                        </td>
                        <td>
                          <span className="flex items-center gap-2">
                            <span className="h-2 w-2 rounded-full" style={{ background: TRAIN_TYPE_COLOR[p.train_type || ""] }} aria-hidden />
                            {TRAIN_TYPE_LABEL[p.train_type || ""] ?? p.train_type}
                          </span>
                        </td>
                        <td className="font-mono">
                          {p.origin}→{p.destination}
                        </td>
                        <td>{p.current_track_section ? <span className="font-mono text-[0.75rem]">{p.current_track_section}</span> : NODE_MAP[p.current_node || ""]?.name ?? p.current_node ?? "—"}</td>
                        <td className={cx("!text-right font-mono", (p.delay_minutes || 0) >= 5 ? "text-caution" : "text-fg-1")}>{(p.delay_minutes || 0) > 0 ? `+${Math.round(p.delay_minutes)}` : "0"}</td>
                        <td>
                          <StatusChip kind={trainStatusKind(p.status, p.delay_minutes)}>{trainStatusLabel(p.status, p.delay_minutes)}</StatusChip>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              icon={<TrainFront className="h-5 w-5" />}
              title={state ? "No trains in the live window" : "Connecting to the live engine…"}
              body={state ? "Load the active fleet to watch every service in this shift." : undefined}
              action={
                state ? (
                  <button type="button" className="btn btn-primary btn-sm" onClick={() => loadFleet()}>
                    Load all {active.length} services
                  </button>
                ) : (
                  <Spinner />
                )
              }
            />
          )}
        </Panel>

        <div className="flex flex-col gap-6">
          <Panel className="p-5">
            <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">Conflicts now</h2>
            {conflicts.length ? (
              <ul className="mt-3 flex flex-col gap-2">
                {conflicts.slice(0, 8).map((c) => (
                  <li key={c.conflict_id} className="hatch rounded-[12px] border border-[rgba(242,106,91,0.35)] p-3">
                    <p className="flex items-center justify-between gap-2 text-[0.8125rem]">
                      <span className="font-medium text-fg-1">{c.conflict_type.replace(/_/g, " ").toLowerCase().replace(/^\w/, (m) => m.toUpperCase())}</span>
                      <span className="font-mono text-fg-2">{fmtClock(c.conflict_time)}</span>
                    </p>
                    <p className="mt-1 text-[0.75rem] text-fg-1">
                      {c.resource_id} · {c.affected_service_ids.map(serviceShort).join(" vs ")}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 flex items-center gap-2 text-[0.875rem] text-fg-2">
                <span className="h-2 w-2 rounded-full bg-clear" aria-hidden /> No conflicts on the network at {state ? fmtClock(state.current_minute) : "—"}.
              </p>
            )}
            <Link href="/optimizer" className="btn btn-secondary btn-sm mt-4">
              <Gauge className="h-4 w-4" aria-hidden /> Ask CP-SAT for a proposal
            </Link>
          </Panel>

          <Panel className="p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">Disruptions on the network</h2>
              <Link href="/what-if" className="text-[0.8125rem] text-champagne hover:underline">
                Add in What-If
              </Link>
            </div>
            {eventError ? (
              <div className="mt-3">
                <ErrorState message={eventError} compact onRetry={loadEvents} />
              </div>
            ) : null}
            {events.length ? (
              <ul className="mt-3 divide-y divide-[var(--line)]">
                {events.map((e) => (
                  <li key={e.id} className="flex items-start justify-between gap-3 py-3">
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 text-[0.8125rem] font-medium text-fg-1">
                        {e.event_type === "BLOCKED_SECTION" ? <Ban className="h-4 w-4 text-conflict" aria-hidden /> : <MapPin className="h-4 w-4 text-caution" aria-hidden />}
                        {e.event_type.replace(/_/g, " ").toLowerCase().replace(/^\w/, (m) => m.toUpperCase())}
                      </p>
                      <p className="mt-1 truncate text-[0.75rem] text-fg-2">
                        {e.service_id ? serviceShort(e.service_id) : e.section_id}
                        {e.station_id ? ` at ${e.station_id}` : ""}
                        {e.delay_minutes ? ` · +${e.delay_minutes} min` : ""} · from {fmtClock(e.from_minute)}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="icon-btn !h-8 !w-8"
                      aria-label={`Remove ${e.id}`}
                      title="Remove this disruption"
                      onClick={() =>
                        Api.removeEvent(e.id)
                          .then(loadEvents)
                          .catch((err: Error) => setEventError(err.message))
                      }
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-3 text-[0.875rem] text-fg-2">None injected. The network is running to timetable.</p>
            )}
          </Panel>
        </div>
      </div>
    </div>
  );
}
