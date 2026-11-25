/**
 * Shift handover report: builds the 6-hour control chart data and train register from the backend's
 * three-tier timetable, and exports it as PDF (vector chart + tables) or CSV.
 */
import type { FullNetwork, FullOptimize, SimEventRecord } from "./api";
import { CORRIDOR_SEQUENCES, NODE_MAP, type CorridorId } from "./topology";
import { TRAIN_TYPE_LABEL, fmtClock, toMinutes, trainNumber } from "./format";

export interface ChartPoint {
  station: string;
  y: number; // index on the station axis
  t: number; // minutes from midnight
}

export interface ChartTrain {
  serviceId: string;
  number: string;
  name: string;
  type: string;
  planned: ChartPoint[];
  controlled: ChartPoint[];
}

export interface RegisterRow {
  serviceId: string;
  number: string;
  name: string;
  type: string;
  route: string;
  schedDep: string;
  ctrlDep: string;
  schedArr: string;
  ctrlArr: string;
  delay: number;
  remark: string;
}

export interface ShiftReport {
  shiftLabel: string;
  window: string;
  start: number;
  end: number;
  date: string;
  corridor: CorridorId;
  axis: string[];
  trains: ChartTrain[];
  register: RegisterRow[];
  totals: { services: number; fifo: number; cpsat: number; conflictsInitial: number; conflictsResolved: number; decisions: number; onTimePct: number; solver: string; solveSeconds: number };
  decisions: { resource: string; first: string; second: string; reason: string }[];
  events: SimEventRecord[];
}

export interface Handover {
  handedBy: string;
  designation: string;
  takenBy: string;
  remarks: string;
}

function unwrap(t: number, start: number): number {
  // Times after midnight in a late shift come back as small numbers; keep the line continuous.
  return t < start - 120 ? t + 1440 : t;
}

export function buildReport(opts: {
  network: FullNetwork;
  opt: FullOptimize;
  events: SimEventRecord[];
  shift: { label: string; window: string; start: number; end: number };
  corridor: CorridorId;
  serviceIds: string[];
  date: string;
}): ShiftReport {
  const { network, opt, events, shift, corridor, serviceIds, date } = opts;
  const axis = CORRIDOR_SEQUENCES.find((c) => c.corridor === corridor)?.nodes ?? [];
  const axisIndex = new Map(axis.map((n, i) => [n, i]));
  const services = new Map(network.services.map((s) => [s.id, s]));
  const tt = network.timetable ?? [];

  const trains: ChartTrain[] = [];
  const register: RegisterRow[] = [];

  for (const sid of serviceIds) {
    const svc = services.get(sid);
    if (!svc) continue;
    const rows = (opt.three_tier_timetable ?? []).filter((r) => r.service_id === sid).sort((a, b) => a.stop_sequence - b.stop_sequence);
    const stops = tt.filter((t) => t.service_id === sid).sort((a, b) => a.stop_sequence - b.stop_sequence);

    const planned: ChartPoint[] = [];
    for (const s of stops) {
      const y = axisIndex.get(s.station_id);
      if (y === undefined) continue;
      const a = toMinutes(s.arrival);
      const d = toMinutes(s.departure);
      if (a !== null) planned.push({ station: s.station_id, y, t: unwrap(a, shift.start) });
      if (d !== null && d !== a) planned.push({ station: s.station_id, y, t: unwrap(d, shift.start) });
    }
    const controlled: ChartPoint[] = [];
    for (const r of rows) {
      const y = axisIndex.get(r.station_id);
      if (y === undefined) continue;
      const a = r.optimized_arrival ?? null;
      const d = r.optimized_departure ?? null;
      if (a !== null) controlled.push({ station: r.station_id, y, t: unwrap(a, shift.start) });
      if (d !== null && d !== a) controlled.push({ station: r.station_id, y, t: unwrap(d, shift.start) });
    }
    if (planned.length + controlled.length >= 2) {
      trains.push({ serviceId: sid, number: trainNumber(svc.train_id), name: svc.train_name || sid, type: svc.train_type || "", planned, controlled });
    }

    const first = rows.find((r) => r.optimized_departure !== null && r.optimized_departure !== undefined);
    const last = [...rows].reverse().find((r) => r.optimized_arrival !== null && r.optimized_arrival !== undefined);
    const schedArr = toMinutes(svc.scheduled_arrival);
    const ctrlArr = last?.optimized_arrival ?? null;
    const delay = schedArr !== null && ctrlArr !== null ? Math.max(0, unwrap(ctrlArr, schedArr) - schedArr) : 0;
    register.push({
      serviceId: sid,
      number: trainNumber(svc.train_id),
      name: svc.train_name || sid,
      type: TRAIN_TYPE_LABEL[svc.train_type || ""] ?? svc.train_type ?? "",
      route: `${svc.origin}–${svc.destination}`,
      schedDep: svc.scheduled_departure || "—",
      ctrlDep: first?.optimized_departure_str || fmtClock(first?.optimized_departure ?? null),
      schedArr: svc.scheduled_arrival || "—",
      ctrlArr: last?.optimized_arrival_str || fmtClock(ctrlArr),
      delay: Math.round(delay),
      remark: delay >= 5 ? `Late +${Math.round(delay)} min` : "Right time",
    });
  }

  register.sort((a, b) => (toMinutes(a.schedDep) ?? 0) - (toMinutes(b.schedDep) ?? 0));
  const perf = (opt.corridor_performance ?? []).filter((c) => !c.is_topology_only);
  const onTime = register.length ? (register.filter((r) => r.delay < 5).length / register.length) * 100 : 0;

  return {
    shiftLabel: shift.label,
    window: shift.window,
    start: shift.start,
    end: shift.end,
    date,
    corridor,
    axis,
    trains,
    register,
    totals: {
      services: serviceIds.length,
      fifo: opt.feasible_baseline_delay_minutes,
      cpsat: opt.optimized_total_delay_minutes,
      conflictsInitial: perf.reduce((a, c) => a + c.initial_conflicts, 0),
      conflictsResolved: perf.reduce((a, c) => a + c.resolved_conflicts, 0),
      decisions: opt.precedence_decisions.length,
      onTimePct: onTime,
      solver: opt.solver_status,
      solveSeconds: opt.computation_time_seconds,
    },
    decisions: opt.precedence_decisions.map((d) => ({ resource: d.resource_id, first: d.first_service_id, second: d.second_service_id, reason: d.reason })),
    events: events.filter((e) => e.from_minute < shift.end && e.to_minute > shift.start),
  };
}

/* ───────── CSV ───────── */

function csvCell(v: unknown): string {
  const s = v === null || v === undefined ? "" : String(v);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function reportToCsv(r: ShiftReport, h: Handover): string {
  const lines: string[][] = [];
  lines.push(["record_type", "train_no", "train_name", "type", "route", "sched_dep", "controlled_dep", "sched_arr", "controlled_arr", "delay_min", "remark"]);
  for (const t of r.register) lines.push(["TRAIN", t.number, t.name, t.type, t.route, t.schedDep, t.ctrlDep, t.schedArr, t.ctrlArr, String(t.delay), t.remark]);
  for (const d of r.decisions) lines.push(["DECISION", "", "", "", d.resource, "", "", "", "", "", `${d.first} before ${d.second}: ${d.reason}`]);
  for (const e of r.events) lines.push(["EVENT", e.service_id ?? "", "", e.event_type, e.section_id ?? e.station_id ?? "", fmtClock(e.from_minute), "", fmtClock(e.to_minute), "", e.delay_minutes ? String(e.delay_minutes) : "", e.description ?? ""]);
  lines.push(["SUMMARY", "", "", "", `${r.shiftLabel} ${r.window} · ${r.date}`, "", "", "", "", "", `services=${r.totals.services}; fifo_delay=${r.totals.fifo}; cpsat_delay=${r.totals.cpsat}; conflicts_resolved=${r.totals.conflictsResolved}/${r.totals.conflictsInitial}; solver=${r.totals.solver}`]);
  lines.push(["HANDOVER", "", h.handedBy, h.designation, "", "", "", "", "", "", `taken over by: ${h.takenBy}; remarks: ${h.remarks}`]);
  return lines.map((row) => row.map(csvCell).join(",")).join("\n");
}

export function download(filename: string, content: Blob) {
  const url = URL.createObjectURL(content);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

/* ───────── PDF ───────── */

const TYPE_RGB: Record<string, [number, number, number]> = {
  SUBURBAN_EMU: [34, 150, 110],
  EXPRESS: [176, 120, 48],
  INTERCITY: [62, 102, 196],
  LONG_DISTANCE: [120, 84, 200],
};

export async function reportToPdf(r: ShiftReport, h: Handover, corridorName: string): Promise<Blob> {
  const { jsPDF } = await import("jspdf");
  const autoTable = (await import("jspdf-autotable")).default;
  const doc = new jsPDF({ orientation: "landscape", unit: "mm", format: "a4" });
  const W = doc.internal.pageSize.getWidth();
  const H = doc.internal.pageSize.getHeight();

  const header = (title: string) => {
    doc.setFont("helvetica", "bold");
    doc.setFontSize(14);
    doc.setTextColor(20, 18, 24);
    doc.text(title, 14, 15);
    doc.setFont("helvetica", "normal");
    doc.setFontSize(9);
    doc.setTextColor(90, 86, 80);
    doc.text(`Chennai Division · Southern Railway   |   ${r.shiftLabel} ${r.window}   |   ${r.date}   |   ${corridorName}`, 14, 21);
    doc.setDrawColor(200, 196, 190);
    doc.line(14, 24, W - 14, 24);
  };

  // Page 1: control chart
  header("Shift control chart");
  const left = 46;
  const top = 32;
  const right = W - 14;
  const bottom = H - 26;
  const t0 = r.start;
  const t1 = r.end;
  const x = (t: number) => left + ((t - t0) / (t1 - t0)) * (right - left);
  const yStep = r.axis.length > 1 ? (bottom - top) / (r.axis.length - 1) : 0;
  const y = (i: number) => top + i * yStep;

  doc.setFontSize(6.5);
  for (let m = t0; m <= t1; m += 30) {
    const xx = x(m);
    doc.setDrawColor(m % 60 === 0 ? 205 : 230, m % 60 === 0 ? 200 : 226, m % 60 === 0 ? 194 : 220);
    doc.line(xx, top, xx, bottom);
    if (m % 60 === 0) {
      doc.setTextColor(90, 86, 80);
      doc.text(fmtClock(m), xx, top - 2, { align: "center" });
      doc.text(fmtClock(m), xx, bottom + 4, { align: "center" });
    }
  }
  r.axis.forEach((n, i) => {
    doc.setDrawColor(236, 232, 226);
    doc.line(left, y(i), right, y(i));
    doc.setTextColor(60, 56, 52);
    const node = NODE_MAP[n];
    const major = node && node.type !== "STATION";
    if (major || r.axis.length <= 24 || i % 2 === 0) doc.text(`${n}${major ? `  ${node.name}` : ""}`.slice(0, 26), left - 2, y(i) + 1, { align: "right" });
  });

  const clip = (pts: ChartPoint[]) => pts.filter((p) => p.t >= t0 - 5 && p.t <= t1 + 5).sort((a, b) => a.t - b.t);
  for (const tr of r.trains) {
    const [cr, cg, cb] = TYPE_RGB[tr.type] ?? [80, 80, 80];
    const plan = clip(tr.planned);
    doc.setLineWidth(0.25);
    doc.setDrawColor(150, 146, 140);
    doc.setLineDashPattern([1.2, 1.2], 0);
    for (let i = 1; i < plan.length; i++) doc.line(x(plan[i - 1].t), y(plan[i - 1].y), x(plan[i].t), y(plan[i].y));
    doc.setLineDashPattern([], 0);
    const ctrl = clip(tr.controlled);
    doc.setLineWidth(0.55);
    doc.setDrawColor(cr, cg, cb);
    for (let i = 1; i < ctrl.length; i++) doc.line(x(ctrl[i - 1].t), y(ctrl[i - 1].y), x(ctrl[i].t), y(ctrl[i].y));
    const label = ctrl[0] ?? plan[0];
    if (label) {
      doc.setTextColor(cr, cg, cb);
      doc.setFontSize(6);
      doc.text(tr.number, x(label.t) + 0.8, y(label.y) - 1);
    }
  }
  doc.setFontSize(7);
  doc.setTextColor(90, 86, 80);
  doc.text("Dashed grey: published timetable.  Solid: controlled run (CP-SAT dispatch, simulated).  Colour: EMU green · Express amber · Intercity blue · Long distance violet.", 14, H - 12);

  // Page 2: register, totals, decisions, handover
  doc.addPage();
  header("Shift register and handover");
  const t = r.totals;
  doc.setFontSize(9);
  doc.setTextColor(30, 28, 34);
  const kv = [
    ["Services in shift", String(t.services)],
    ["Delay, FIFO baseline", `${t.fifo.toFixed(1)} min`],
    ["Delay, CP-SAT dispatch", `${t.cpsat.toFixed(1)} min`],
    ["Conflicts resolved", `${t.conflictsResolved} of ${t.conflictsInitial}`],
    ["Precedence decisions", String(t.decisions)],
    ["Right-time arrivals", `${t.onTimePct.toFixed(0)}%`],
    ["Solver", `${t.solver} in ${t.solveSeconds.toFixed(3)} s`],
  ];
  kv.forEach(([k, v], i) => {
    const col = i % 4;
    const row = Math.floor(i / 4);
    doc.setTextColor(110, 106, 100);
    doc.text(k, 14 + col * 68, 32 + row * 11);
    doc.setTextColor(20, 18, 24);
    doc.setFont("helvetica", "bold");
    doc.text(v, 14 + col * 68, 37 + row * 11);
    doc.setFont("helvetica", "normal");
  });

  autoTable(doc, {
    startY: 56,
    head: [["Train", "Name", "Type", "Route", "Sched dep", "Ctrl dep", "Sched arr", "Ctrl arr", "Delay", "Remark"]],
    body: r.register.map((x) => [x.number, x.name, x.type, x.route, x.schedDep, x.ctrlDep, x.schedArr, x.ctrlArr, x.delay ? `+${x.delay}` : "0", x.remark]),
    styles: { fontSize: 7.5, cellPadding: 1.6, textColor: [30, 28, 34] },
    headStyles: { fillColor: [36, 32, 44], textColor: [244, 239, 232], fontStyle: "bold" },
    alternateRowStyles: { fillColor: [247, 245, 242] },
    margin: { left: 14, right: 14 },
  });

  let yPos = ((doc as any).lastAutoTable?.finalY ?? 120) + 6;
  if (r.decisions.length || r.events.length) {
    autoTable(doc, {
      startY: yPos,
      head: [["Kind", "Where", "Detail"]],
      body: [
        ...r.events.map((e) => ["Disruption", e.section_id || e.station_id || e.service_id || "", `${e.event_type.replace(/_/g, " ").toLowerCase()} from ${fmtClock(e.from_minute)}${e.delay_minutes ? `, +${e.delay_minutes} min` : ""}${e.description ? ` (${e.description})` : ""}`]),
        ...r.decisions.slice(0, 30).map((d) => ["CP-SAT decision", d.resource, `${d.first} before ${d.second}. ${d.reason}`]),
      ],
      styles: { fontSize: 7.5, cellPadding: 1.6, textColor: [30, 28, 34] },
      headStyles: { fillColor: [36, 32, 44], textColor: [244, 239, 232] },
      margin: { left: 14, right: 14 },
    });
    yPos = ((doc as any).lastAutoTable?.finalY ?? yPos) + 6;
  }

  if (yPos > H - 52) {
    doc.addPage();
    header("Handover");
    yPos = 32;
  }
  doc.setFont("helvetica", "bold");
  doc.setFontSize(10);
  doc.setTextColor(20, 18, 24);
  doc.text("Charge handed over", 14, yPos);
  doc.setFont("helvetica", "normal");
  doc.setFontSize(8.5);
  const remarks = doc.splitTextToSize(h.remarks || "No remarks.", W - 28);
  doc.text(remarks, 14, yPos + 6);
  const sigY = Math.min(H - 18, yPos + 12 + remarks.length * 4 + 8);
  doc.setDrawColor(120, 116, 110);
  doc.line(14, sigY, 110, sigY);
  doc.line(W - 110, sigY, W - 14, sigY);
  doc.text(`Handed over by: ${h.handedBy || "—"}${h.designation ? `, ${h.designation}` : ""}  at ${fmtClock(r.end)}`, 14, sigY + 4.5);
  doc.text(`Taken over by: ${h.takenBy || "—"}`, W - 110, sigY + 4.5);

  const pages = doc.getNumberOfPages();
  for (let i = 1; i <= pages; i++) {
    doc.setPage(i);
    doc.setFontSize(7);
    doc.setTextColor(130, 126, 120);
    doc.text("Generated by the Chennai Division Traffic Optimizer: simulation-based decision support, not an official Indian Railways record.", 14, H - 6);
    doc.text(`${i} / ${pages}`, W - 14, H - 6, { align: "right" });
  }
  return doc.output("blob");
}
