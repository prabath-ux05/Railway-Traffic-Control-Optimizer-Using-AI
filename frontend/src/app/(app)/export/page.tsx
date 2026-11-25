"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSession } from "next-auth/react";
import { FileSpreadsheet, FileText, RefreshCw } from "lucide-react";
import { EmptyState, ErrorState, FieldLabel, Legend, Numeral, Panel, SectionHead, Segmented, Skeleton, Spinner, StatusChip } from "@/components/glass/ui";
import { servicesInWindow, useLive, useNetwork } from "@/lib/glass/live";
import { Api } from "@/lib/glass/api";
import { CORRIDORS, CORRIDOR_BY_ID, CORRIDOR_SEQUENCES, NODE_MAP, corridorIdFromLabel, type CorridorId } from "@/lib/glass/topology";
import { SHIFTS, TRAIN_TYPE_COLOR, TRAIN_TYPE_LABEL, cx, fmtClock, fmtNum, istNow, shiftForMinute, type ShiftId } from "@/lib/glass/format";
import { buildReport, download, reportToCsv, reportToPdf, type ShiftReport } from "@/lib/glass/shift";
import { useSettings } from "@/lib/glass/settings";

function ControlChart({ report }: { report: ShiftReport }) {
  const W = 1100;
  const rowH = report.axis.length > 22 ? 18 : 24;
  const H = Math.max(260, report.axis.length * rowH + 48);
  const left = 150;
  const right = W - 16;
  const top = 26;
  const bottom = H - 22;
  const x = (t: number) => left + ((t - report.start) / (report.end - report.start)) * (right - left);
  const y = (i: number) => top + (report.axis.length > 1 ? (i * (bottom - top)) / (report.axis.length - 1) : 0);
  const ticks: number[] = [];
  for (let m = report.start; m <= report.end; m += 30) ticks.push(m);
  const inWin = (t: number) => t >= report.start - 5 && t <= report.end + 5;

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-auto w-full min-w-[760px]" role="img" aria-label={`Control chart for ${report.shiftLabel}, ${report.window}`}>
      {ticks.map((m) => (
        <g key={m}>
          <line x1={x(m)} x2={x(m)} y1={top} y2={bottom} stroke="rgba(255,240,224,0.08)" strokeWidth={m % 60 === 0 ? 1 : 0.5} />
          {m % 60 === 0 ? (
            <text x={x(m)} y={top - 9} textAnchor="middle" fontSize={11} fill="#8E877C" fontFamily="var(--font-mono)">
              {fmtClock(m)}
            </text>
          ) : null}
        </g>
      ))}
      {report.axis.map((n, i) => {
        const node = NODE_MAP[n];
        const major = node && node.type !== "STATION";
        return (
          <g key={n}>
            <line x1={left} x2={right} y1={y(i)} y2={y(i)} stroke="rgba(255,240,224,0.05)" />
            <text x={left - 10} y={y(i) + 4} textAnchor="end" fontSize={major ? 11.5 : 10.5} fill={major ? "#D8D1C7" : "#8E877C"} fontWeight={major ? 600 : 400}>
              {major ? node.name : n}
            </text>
          </g>
        );
      })}
      {report.trains.map((tr) => {
        const color = TRAIN_TYPE_COLOR[tr.type] ?? "#F4EFE8";
        const plan = tr.planned.filter((p) => inWin(p.t)).sort((a, b) => a.t - b.t);
        const ctrl = tr.controlled.filter((p) => inWin(p.t)).sort((a, b) => a.t - b.t);
        const path = (pts: typeof plan) => pts.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.y).toFixed(1)}`).join(" ");
        const lab = ctrl[0] ?? plan[0];
        return (
          <g key={tr.serviceId}>
            {plan.length > 1 ? <path d={path(plan)} fill="none" stroke="rgba(185,178,168,0.55)" strokeWidth={1} strokeDasharray="4 4" /> : null}
            {ctrl.length > 1 ? <path d={path(ctrl)} fill="none" stroke={color} strokeWidth={1.8} strokeLinejoin="round" /> : null}
            {lab ? (
              <text x={x(lab.t) + 4} y={y(lab.y) - 5} fontSize={10} fill={color} fontFamily="var(--font-mono)">
                {tr.number}
              </text>
            ) : null}
            <title>{`${tr.number} ${tr.name}`}</title>
          </g>
        );
      })}
    </svg>
  );
}

export default function ExportPage() {
  const { network } = useNetwork();
  const { state } = useLive();
  const { data: session } = useSession();
  const { profile } = useSettings();
  const [shiftId, setShiftId] = useState<ShiftId | null>(null);
  const [corridor, setCorridor] = useState<CorridorId>("WEST");
  const [date, setDate] = useState<string>(() => {
    const d = istNow();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  });
  const [report, setReport] = useState<ShiftReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"pdf" | "csv" | null>(null);
  const [takenBy, setTakenBy] = useState("");
  const [remarks, setRemarks] = useState("");
  const [handedBy, setHandedBy] = useState("");

  useEffect(() => {
    if (!handedBy) setHandedBy(profile.displayName || session?.user?.name || "");
  }, [profile.displayName, session?.user?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  const shift = SHIFTS.find((s) => s.id === shiftId) ?? (state ? shiftForMinute(state.start_minute) : SHIFTS[0]);
  const scope = useMemo(() => servicesInWindow(network, shift.start, shift.end), [network, shift.start, shift.end]);
  const corridorsWithTraffic = useMemo(() => new Set(scope.map((s) => corridorIdFromLabel(s.corridor)).filter(Boolean)), [scope]);

  const generate = useCallback(async () => {
    if (!network) return;
    setLoading(true);
    setError(null);
    try {
      const ids = scope.map((s) => s.id);
      if (!ids.length) {
        setReport(null);
        setError(`No active services run in ${shift.label} (${shift.window}). Pick another shift.`);
        return;
      }
      const [opt, events] = await Promise.all([Api.optimize({ service_ids: ids }), Api.events().catch(() => [])]);
      const onCorridor = ids.filter((id) => corridorIdFromLabel(network.services.find((s) => s.id === id)?.corridor) === corridor);
      setReport(buildReport({ network, opt, events, shift, corridor, serviceIds: onCorridor.length ? onCorridor : ids, date }));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Couldn't build the shift chart.");
    } finally {
      setLoading(false);
    }
  }, [network, scope, shift, corridor, date]);

  useEffect(() => {
    if (network) generate();
  }, [network, shift.id, corridor]); // eslint-disable-line react-hooks/exhaustive-deps

  const handover = { handedBy, designation: profile.designation, takenBy, remarks };
  const fileBase = `chennai-division_${date}_${shift.id}_${corridor.toLowerCase()}`;
  const corridorName = CORRIDOR_BY_ID[corridor]?.full ?? corridor;

  const exportPdf = async () => {
    if (!report) return;
    setBusy("pdf");
    try {
      download(`${fileBase}_control-chart.pdf`, await reportToPdf({ ...report, date }, handover, corridorName));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "The PDF couldn't be created.");
    } finally {
      setBusy(null);
    }
  };
  const exportCsv = () => {
    if (!report) return;
    setBusy("csv");
    download(`${fileBase}_register.csv`, new Blob([reportToCsv({ ...report, date }, handover)], { type: "text/csv;charset=utf-8" }));
    setBusy(null);
  };

  return (
    <div className="flex flex-col gap-6">
      <SectionHead
        level={1}
        className="rise px-1"
        title="Hand over the shift"
        description="The 6-hour control chart for the next controller in charge: every train's planned and controlled run, the register, the decisions taken, and your remarks. Download it as PDF or CSV."
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_380px]">
        <Panel className="overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 p-5">
            <div className="flex flex-wrap items-center gap-3">
              <Segmented label="Shift" value={shift.id} onChange={(v) => setShiftId(v)} options={SHIFTS.map((s) => ({ value: s.id, label: s.window, title: s.label }))} />
              <select aria-label="Corridor on the chart" className="field !w-auto !rounded-full !py-2 text-[0.8125rem]" value={corridor} onChange={(e) => setCorridor(e.target.value as CorridorId)}>
                {CORRIDORS.filter((c) => CORRIDOR_SEQUENCES.some((s) => s.corridor === c.id)).map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.full}
                    {corridorsWithTraffic.has(c.id) ? "" : " (no traffic this shift)"}
                  </option>
                ))}
              </select>
            </div>
            <button type="button" className="btn btn-quiet btn-sm" onClick={generate} disabled={loading}>
              {loading ? <Spinner /> : <RefreshCw className="h-4 w-4" aria-hidden />} Refresh
            </button>
          </div>
          <div className="border-t border-line px-2 py-4 sm:px-5">
            {error ? (
              <div className="p-3">
                <ErrorState message={error} onRetry={generate} />
              </div>
            ) : report && !loading ? (
              report.trains.length ? (
                <div className="overflow-x-auto">
                  <ControlChart report={report} />
                </div>
              ) : (
                <EmptyState title={`No trains cross ${CORRIDOR_BY_ID[corridor].label} in this shift`} body="Pick another corridor or shift. The register below still lists the shift's services." />
              )
            ) : (
              <Skeleton className="h-[420px]" />
            )}
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-4">
            <Legend
              items={[
                { color: "rgba(185,178,168,0.7)", label: "Published timetable", dashed: true },
                ...Object.entries(TRAIN_TYPE_COLOR).map(([k, c]) => ({ color: c, label: `${TRAIN_TYPE_LABEL[k]}, controlled` })),
              ]}
            />
          </div>
        </Panel>

        <Panel className="flex flex-col gap-5 p-6" data-tour="export">
          <div>
            <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">This shift</h2>
            {report ? (
              <dl className="mt-4 grid grid-cols-2 gap-4">
                <div>
                  <dt className="label">Services</dt>
                  <dd className="mt-1.5">
                    <Numeral value={report.totals.services} size="s" />
                  </dd>
                </div>
                <div>
                  <dt className="label">Right time</dt>
                  <dd className="mt-1.5">
                    <Numeral value={Math.round(report.totals.onTimePct)} unit="%" size="s" tone={report.totals.onTimePct >= 80 ? "clear" : "caution"} />
                  </dd>
                </div>
                <div>
                  <dt className="label">CP-SAT delay</dt>
                  <dd className="mt-1.5">
                    <Numeral value={fmtNum(report.totals.cpsat, 0)} unit="min" size="s" tone="violet" />
                  </dd>
                </div>
                <div>
                  <dt className="label">Conflicts</dt>
                  <dd className="mt-1.5">
                    <Numeral value={report.totals.conflictsResolved} unit={`/${report.totals.conflictsInitial}`} size="s" tone="clear" />
                  </dd>
                </div>
              </dl>
            ) : (
              <Skeleton className="mt-4 h-24" />
            )}
          </div>

          <div className="grid gap-4 border-t border-line pt-5">
            <div>
              <FieldLabel htmlFor="ex-date">Date</FieldLabel>
              <input id="ex-date" type="date" className="field" value={date} onChange={(e) => setDate(e.target.value)} />
            </div>
            <div>
              <FieldLabel htmlFor="ex-by" hint={profile.designation}>
                Handed over by
              </FieldLabel>
              <input id="ex-by" className="field" value={handedBy} onChange={(e) => setHandedBy(e.target.value)} placeholder="Your name" maxLength={80} />
            </div>
            <div>
              <FieldLabel htmlFor="ex-to">Taken over by</FieldLabel>
              <input id="ex-to" className="field" value={takenBy} onChange={(e) => setTakenBy(e.target.value)} placeholder="Relieving controller" maxLength={80} />
            </div>
            <div>
              <FieldLabel htmlFor="ex-remarks" hint={`${remarks.length}/600`}>
                Remarks for the next in-charge
              </FieldLabel>
              <textarea id="ex-remarks" rows={4} maxLength={600} className="field resize-y" value={remarks} onChange={(e) => setRemarks(e.target.value)} placeholder="Restrictions in force, trains to watch, pending decisions…" />
            </div>
          </div>

          <div className="mt-auto flex flex-wrap gap-3 border-t border-line pt-5">
            <button type="button" className="btn btn-primary flex-1" disabled={!report || busy !== null} onClick={exportPdf}>
              {busy === "pdf" ? <Spinner /> : <FileText className="h-4 w-4" aria-hidden />} Download PDF
            </button>
            <button type="button" className="btn btn-secondary flex-1" disabled={!report || busy !== null} onClick={exportCsv}>
              <FileSpreadsheet className="h-4 w-4" aria-hidden /> Download CSV
            </button>
          </div>
        </Panel>
      </div>

      <Panel className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 p-5 pb-3">
          <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">Train register</h2>
          {report ? (
            <span className="text-[0.8125rem] text-fg-2">
              {report.register.length} trains · {report.events.length} disruptions · {report.decisions.length} CP-SAT decisions
            </span>
          ) : null}
        </div>
        {report ? (
          <div className="max-h-[460px] overflow-auto">
            <table className="table-glass">
              <thead>
                <tr>
                  <th>Train</th>
                  <th>Type</th>
                  <th>Route</th>
                  <th>Sched dep</th>
                  <th>Ctrl dep</th>
                  <th>Sched arr</th>
                  <th>Ctrl arr</th>
                  <th className="!text-right">Delay</th>
                  <th>Remark</th>
                </tr>
              </thead>
              <tbody>
                {report.register.map((r) => (
                  <tr key={r.serviceId}>
                    <td className="text-fg-1">
                      <span className="font-mono">{r.number}</span> <span className="text-fg-2">{r.name}</span>
                    </td>
                    <td>{r.type}</td>
                    <td className="font-mono">{r.route}</td>
                    <td className="font-mono">{r.schedDep}</td>
                    <td className="font-mono text-[#b3a2ff]">{r.ctrlDep}</td>
                    <td className="font-mono">{r.schedArr}</td>
                    <td className="font-mono text-[#b3a2ff]">{r.ctrlArr}</td>
                    <td className={cx("!text-right font-mono", r.delay >= 5 ? "text-caution" : "text-fg-1")}>{r.delay ? `+${r.delay}` : "0"}</td>
                    <td>
                      <StatusChip kind={r.delay >= 5 ? "caution" : "clear"}>{r.remark}</StatusChip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex flex-col gap-2 p-5">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-9" />
            ))}
          </div>
        )}
      </Panel>
    </div>
  );
}
