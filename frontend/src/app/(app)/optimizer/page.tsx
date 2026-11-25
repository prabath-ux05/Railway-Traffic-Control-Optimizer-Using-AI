"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Check, ChevronDown, Cpu, Sparkles, X } from "lucide-react";
import { DeltaChip, EmptyState, ErrorState, Numeral, Panel, SectionHead, Segmented, Skeleton, Spinner, StatusChip, Switch } from "@/components/glass/ui";
import { servicesInWindow, useLive, useNetwork } from "@/lib/glass/live";
import { Api, type FullOptimize, type FullWhatIf, type Proposal } from "@/lib/glass/api";
import { CORRIDORS, corridorIdFromLabel } from "@/lib/glass/topology";
import { SHIFTS, cx, fmtClock, fmtNum, serviceShort, shiftForMinute, trainNumber, type ShiftId } from "@/lib/glass/format";
import type { Recommendation } from "@/lib/types";

const CHANGE_KIND: Record<string, { kind: "clear" | "caution" | "violet" | "info" | "muted"; label: string }> = {
  ON_TIME: { kind: "clear", label: "On time" },
  RESCHEDULED: { kind: "violet", label: "Rescheduled" },
  DELAY_RECOVERED: { kind: "clear", label: "Delay recovered" },
  PLATFORM_SWAP: { kind: "info", label: "Platform swap" },
  DELAYED: { kind: "caution", label: "Delayed" },
};

function tierKind(tier?: string): "conflict" | "caution" | "info" | "muted" {
  const t = (tier || "").toUpperCase();
  if (t === "CRITICAL" || t === "URGENT") return "conflict";
  if (t === "HIGH") return "caution";
  if (t === "MEDIUM") return "info";
  return "muted";
}

export default function OptimizerPage() {
  const { network } = useNetwork();
  const { state } = useLive();
  const [shiftId, setShiftId] = useState<ShiftId | null>(null);
  const [opt, setOpt] = useState<FullOptimize | null>(null);
  const [analysis, setAnalysis] = useState<FullWhatIf | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [onlyChanged, setOnlyChanged] = useState(true);
  const [trainFilter, setTrainFilter] = useState<string>("ALL");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [proposalBusy, setProposalBusy] = useState<"create" | "accept" | "reject" | null>(null);
  const [proposalMsg, setProposalMsg] = useState<string | null>(null);
  const [proposalError, setProposalError] = useState<string | null>(null);

  const shift = SHIFTS.find((s) => s.id === shiftId) ?? (state ? shiftForMinute(state.start_minute) : SHIFTS[0]);
  const scope = useMemo(() => servicesInWindow(network, shift.start, shift.end), [network, shift.start, shift.end]);

  const solve = useCallback(async () => {
    if (!scope.length) return;
    setLoading(true);
    setError(null);
    const ids = scope.map((s) => s.id);
    const delays = Object.fromEntries(Object.entries(state?.departure_delays ?? {}).filter(([k]) => ids.includes(k)));
    try {
      const [o, w] = await Promise.all([
        Api.optimize({ service_ids: ids, departure_delays: delays }),
        Api.whatIf({ scenario_id: `OPT_${shift.id}`, scenario_name: `${shift.label} analysis`, service_ids: ids, departure_delays: delays }).catch(() => null),
      ]);
      setOpt(o);
      setAnalysis(w);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "The optimiser didn't respond.");
    } finally {
      setLoading(false);
    }
  }, [scope, state?.departure_delays, shift.id, shift.label]);

  useEffect(() => {
    if (network && scope.length && !opt && !loading && !error) solve();
  }, [network, scope.length, opt]); // eslint-disable-line react-hooks/exhaustive-deps

  const rawSaving = opt ? opt.feasible_baseline_delay_minutes - opt.optimized_total_delay_minutes : null;
  const wF = opt?.fifo_weighted_objective ?? null;
  const wC = opt?.optimized_weighted_objective ?? null;
  const wSavingPct = wF && wC !== null && wC !== undefined ? ((wF - wC) / wF) * 100 : null;
  const corridorRows = (opt?.corridor_performance ?? []).filter((c) => !c.is_topology_only && c.service_count > 0);
  const maxCorr = Math.max(1, ...corridorRows.map((c) => Math.max(c.baseline_delay_minutes, c.optimized_delay_minutes)));
  const initialConflicts = corridorRows.reduce((a, c) => a + c.initial_conflicts, 0);
  const resolvedConflicts = corridorRows.reduce((a, c) => a + c.resolved_conflicts, 0);

  const rows = useMemo(() => {
    const tt = opt?.three_tier_timetable ?? [];
    return tt
      .filter((r) => r.published_arrival_str || r.published_departure_str || r.has_rescheduling_change)
      .filter((r) => (trainFilter === "ALL" ? true : r.service_id === trainFilter))
      .filter((r) => (onlyChanged ? r.has_rescheduling_change || (r.optimized_delay_minutes ?? 0) !== (r.feasible_delay_minutes ?? 0) : true));
  }, [opt, onlyChanged, trainFilter]);

  const trainsInResult = useMemo(() => {
    const m = new Map<string, string>();
    for (const r of opt?.three_tier_timetable ?? []) if (!m.has(r.service_id)) m.set(r.service_id, `${trainNumber(r.train_id)} ${r.train_name ?? ""}`);
    return [...m.entries()];
  }, [opt]);

  const createProposal = async () => {
    setProposalBusy("create");
    setProposalError(null);
    setProposalMsg(null);
    try {
      setProposal(await Api.reoptimize());
    } catch (e: unknown) {
      setProposalError(e instanceof Error ? e.message : "Couldn't create a proposal.");
    } finally {
      setProposalBusy(null);
    }
  };
  const actOnProposal = async (accept: boolean) => {
    if (!proposal) return;
    setProposalBusy(accept ? "accept" : "reject");
    setProposalError(null);
    try {
      const r = accept ? await Api.acceptProposal(proposal.proposal_id) : await Api.rejectProposal(proposal.proposal_id);
      setProposal({ ...proposal, status: r.status });
      setProposalMsg(r.message);
    } catch (e: unknown) {
      setProposalError(e instanceof Error ? e.message : "The decision wasn't recorded.");
    } finally {
      setProposalBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <SectionHead
        level={1}
        className="rise px-1"
        title="FIFO versus CP-SAT"
        description="Solve a shift with Google OR-Tools CP-SAT and compare it, train by train, with the physically feasible first-in, first-out baseline. Then decide on the live proposal."
        actions={
          <>
            <Segmented
              label="Shift"
              value={shift.id}
              onChange={(v) => {
                setShiftId(v);
                setOpt(null);
                setAnalysis(null);
                setError(null);
              }}
              options={SHIFTS.map((s) => ({ value: s.id, label: s.window, title: s.label }))}
            />
            <button type="button" data-tour="run-optimizer" className="btn btn-primary" disabled={loading || !scope.length} onClick={solve}>
              {loading ? <Spinner /> : <Cpu className="h-4 w-4" aria-hidden />} Solve {scope.length || ""} services
            </button>
          </>
        }
      />

      {error ? <ErrorState message={error} onRetry={solve} /> : null}

      {/* Result slab */}
      <Panel className="overflow-hidden">
        <div className="grid divide-y divide-[var(--line)] md:grid-cols-2 md:divide-x md:divide-y-0 xl:grid-cols-4">
          <div className="flex flex-col gap-3 p-6">
            <span className="label">Solver</span>
            {opt ? (
              <>
                <StatusChip kind={opt.solver_status === "OPTIMAL" ? "clear" : opt.solver_status === "FEASIBLE" ? "info" : "conflict"} className="self-start">
                  {opt.solver_status}
                </StatusChip>
                <Numeral value={fmtNum(opt.computation_time_seconds, 3)} unit="s" size="l" />
                <span className="text-[0.8125rem] text-fg-2">
                  {scope.length} services · {shift.window}
                </span>
              </>
            ) : (
              <Skeleton className="h-20 w-32" />
            )}
          </div>
          <div className="flex flex-col gap-3 p-6">
            <span className="label">Total delay, unweighted</span>
            {opt ? (
              <>
                <div className="flex items-end gap-5">
                  <div>
                    <span className="block text-[0.75rem] text-[#dcae84]">FIFO</span>
                    <Numeral value={fmtNum(opt.feasible_baseline_delay_minutes, 1)} unit="min" size="m" tone="bronze" />
                  </div>
                  <div>
                    <span className="block text-[0.75rem] text-[#b3a2ff]">CP-SAT</span>
                    <Numeral value={fmtNum(opt.optimized_total_delay_minutes, 1)} unit="min" size="m" tone="violet" />
                  </div>
                </div>
                <DeltaChip value={-(rawSaving ?? 0)} unit=" min" good={(rawSaving ?? 0) >= 0} digits={1} title="CP-SAT minus FIFO" />
              </>
            ) : (
              <Skeleton className="h-20 w-40" />
            )}
          </div>
          <div className="flex flex-col gap-3 p-6">
            <span className="label">Weighted objective Z</span>
            {opt && wF !== null ? (
              <>
                <div className="flex items-end gap-5">
                  <div>
                    <span className="block text-[0.75rem] text-[#dcae84]">FIFO</span>
                    <Numeral value={fmtNum(wF)} size="m" tone="bronze" />
                  </div>
                  <div>
                    <span className="block text-[0.75rem] text-[#b3a2ff]">CP-SAT</span>
                    <Numeral value={fmtNum(wC)} size="m" tone="violet" />
                  </div>
                </div>
                <DeltaChip value={wSavingPct === null ? null : -wSavingPct} unit="%" good={(wSavingPct ?? 0) >= 0} digits={1} title="Change in the weighted objective" />
              </>
            ) : opt ? (
              <p className="text-[0.8125rem] text-fg-2">Not reported for this run.</p>
            ) : (
              <Skeleton className="h-20 w-40" />
            )}
          </div>
          <div className="flex flex-col gap-3 p-6">
            <span className="label">Conflicts resolved</span>
            {opt ? (
              <>
                <Numeral value={resolvedConflicts} unit={`/${initialConflicts}`} size="l" tone={resolvedConflicts === initialConflicts ? "clear" : "caution"} />
                <span className="text-[0.8125rem] text-fg-2">
                  {opt.unresolved_conflicts_count} unresolved · {opt.precedence_decisions.length} precedence decisions
                </span>
              </>
            ) : (
              <Skeleton className="h-20 w-32" />
            )}
          </div>
        </div>
        {opt && rawSaving !== null && rawSaving < 0 && wSavingPct !== null && wSavingPct > 0 ? (
          <p className="border-t border-line px-6 py-4 text-[0.875rem] leading-relaxed text-fg-2">
            CP-SAT accepted <span className="text-fg-1">{fmtNum(-rawSaving, 1)} more raw minutes</span> to lower the weighted objective by <span className="text-fg-1">{fmtNum(wSavingPct, 1)}%</span>. High-priority express and intercity trains count 5 per delay-minute against 3 for suburban EMUs, so protecting them can cost a little elsewhere.
          </p>
        ) : null}
      </Panel>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.35fr)]">
        {/* Corridor bars */}
        <Panel className="p-6">
          <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">By corridor</h2>
          <p className="mt-1 text-[0.8125rem] text-fg-2">Delay minutes under each schedule, with conflicts resolved.</p>
          {opt ? (
            corridorRows.length ? (
              <ul className="mt-5 flex flex-col gap-5">
                {corridorRows.map((c) => {
                  const cid = corridorIdFromLabel(c.corridor_name);
                  const color = CORRIDORS.find((x) => x.id === cid)?.color ?? "var(--fg-2)";
                  return (
                    <li key={c.corridor_id}>
                      <div className="flex items-center justify-between gap-3 text-[0.8125rem]">
                        <span className="flex items-center gap-2 font-medium text-fg-1">
                          <span className="h-[3px] w-5 rounded-full" style={{ background: color }} aria-hidden />
                          {c.corridor_name}
                          <span className="font-normal text-fg-3">{c.service_count} services</span>
                        </span>
                        <span className="text-fg-2 tnum">
                          {c.resolved_conflicts}/{c.initial_conflicts} resolved
                        </span>
                      </div>
                      <div className="mt-2 flex flex-col gap-1.5" role="img" aria-label={`${c.corridor_name}: FIFO ${c.baseline_delay_minutes} minutes, CP-SAT ${c.optimized_delay_minutes} minutes`}>
                        <div className="flex items-center gap-3">
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-[rgba(255,240,224,0.06)]">
                            <div className="h-full rounded-full bg-bronze transition-[width] duration-500" style={{ width: `${(c.baseline_delay_minutes / maxCorr) * 100}%` }} />
                          </div>
                          <span className="w-14 text-right font-mono text-[0.75rem] text-[#dcae84] tnum">{fmtNum(c.baseline_delay_minutes, 0)}</span>
                        </div>
                        <div className="flex items-center gap-3">
                          <div className="h-2 flex-1 overflow-hidden rounded-full bg-[rgba(255,240,224,0.06)]">
                            <div className="h-full rounded-full bg-violet transition-[width] duration-500" style={{ width: `${(c.optimized_delay_minutes / maxCorr) * 100}%` }} />
                          </div>
                          <span className="w-14 text-right font-mono text-[0.75rem] text-[#b3a2ff] tnum">{fmtNum(c.optimized_delay_minutes, 0)}</span>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            ) : (
              <EmptyState title="No corridor carried traffic in this shift" />
            )
          ) : (
            <div className="mt-5 flex flex-col gap-4">
              {[0, 1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-10" />
              ))}
            </div>
          )}
          <div className="mt-6 flex items-center gap-5 text-[0.75rem] text-fg-2">
            <span className="flex items-center gap-2">
              <span className="h-2 w-5 rounded-full bg-bronze" aria-hidden /> FIFO baseline
            </span>
            <span className="flex items-center gap-2">
              <span className="h-2 w-5 rounded-full bg-violet" aria-hidden /> CP-SAT
            </span>
          </div>
        </Panel>

        {/* Live proposal: human in the loop */}
        <Panel className="p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="max-w-[52ch]">
              <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">Live proposal</h2>
              <p className="mt-1 text-[0.8125rem] leading-relaxed text-fg-2">CP-SAT re-plans the live network from its current state. Nothing changes until you accept.</p>
            </div>
            <button type="button" className="btn btn-secondary btn-sm" disabled={proposalBusy !== null} onClick={createProposal}>
              {proposalBusy === "create" ? <Spinner /> : <Sparkles className="h-4 w-4" aria-hidden />} {proposal ? "New proposal" : "Generate proposal"}
            </button>
          </div>
          {proposalError ? (
            <div className="mt-4">
              <ErrorState message={proposalError} compact />
            </div>
          ) : null}
          {proposal ? (
            <div className="mt-5 flex flex-col gap-4">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[0.8125rem] text-fg-1">{proposal.proposal_id}</span>
                <StatusChip kind={proposal.status === "ACCEPTED" ? "clear" : proposal.status === "REJECTED" ? "muted" : "violet"}>{proposal.status.toLowerCase().replace(/^\w/, (m) => m.toUpperCase())}</StatusChip>
                <StatusChip kind={proposal.solution_available ? "clear" : "conflict"}>{proposal.solver_status}</StatusChip>
                <span className="text-[0.75rem] text-fg-3">at sim {fmtClock(proposal.created_at_sim_minute)}</span>
              </div>
              <dl className="grid grid-cols-3 gap-4 rounded-[14px] border border-line p-4">
                <div>
                  <dt className="label">Now</dt>
                  <dd className="mt-1.5">
                    <Numeral value={fmtNum(proposal.total_baseline_delay_minutes, 0)} unit="min" size="s" tone="bronze" />
                  </dd>
                </div>
                <div>
                  <dt className="label">Proposed</dt>
                  <dd className="mt-1.5">{proposal.total_optimized_delay_minutes === null ? <span className="text-fg-2">—</span> : <Numeral value={fmtNum(proposal.total_optimized_delay_minutes, 0)} unit="min" size="s" tone="violet" />}</dd>
                </div>
                <div>
                  <dt className="label">Change</dt>
                  <dd className="mt-2">
                    <DeltaChip value={proposal.net_delay_savings_minutes === null ? null : -proposal.net_delay_savings_minutes} unit=" min" good={(proposal.net_delay_savings_minutes ?? 0) >= 0} />
                  </dd>
                </div>
              </dl>
              {proposal.precedence_decisions.length ? (
                <ul className="flex flex-col gap-2 text-[0.8125rem]">
                  {proposal.precedence_decisions.slice(0, 4).map((d, i) => (
                    <li key={i} className="flex gap-2 text-fg-2">
                      <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-violet" aria-hidden />
                      <span>
                        <span className="text-fg-1">
                          {serviceShort(d.first_service_id)} before {serviceShort(d.second_service_id)}
                        </span>{" "}
                        at {d.resource_id}. {d.reason}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[0.8125rem] text-fg-2">No precedence changes are needed: the live plan is already conflict-free.</p>
              )}
              {proposal.status === "PENDING" ? (
                <div className="flex flex-wrap gap-2">
                  <button type="button" className="btn btn-primary btn-sm" disabled={proposalBusy !== null || !proposal.solution_available} onClick={() => actOnProposal(true)}>
                    {proposalBusy === "accept" ? <Spinner /> : <Check className="h-4 w-4" aria-hidden />} Accept and apply
                  </button>
                  <button type="button" className="btn btn-secondary btn-sm" disabled={proposalBusy !== null} onClick={() => actOnProposal(false)}>
                    {proposalBusy === "reject" ? <Spinner /> : <X className="h-4 w-4" aria-hidden />} Reject
                  </button>
                </div>
              ) : null}
              {proposalMsg ? <p className="text-[0.8125rem] text-fg-2">{proposalMsg}</p> : null}
            </div>
          ) : (
            <EmptyState title="No proposal yet" body="Generate one from the live network. You'll see what CP-SAT would change and why before anything is applied." />
          )}
        </Panel>
      </div>

      {/* Timetable */}
      <Panel className="overflow-hidden">
        <div className="flex flex-wrap items-end justify-between gap-4 p-6 pb-2">
          <div>
            <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">Timetable, three ways</h2>
            <p className="mt-1 text-[0.8125rem] text-fg-2">Published timetable, the feasible FIFO run, and the CP-SAT schedule at every timetabled call.</p>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            <select aria-label="Filter by train" className="field !w-auto !rounded-full !py-2 text-[0.8125rem]" value={trainFilter} onChange={(e) => setTrainFilter(e.target.value)}>
              <option value="ALL">All trains</option>
              {trainsInResult.map(([id, label]) => (
                <option key={id} value={id}>
                  {label}
                </option>
              ))}
            </select>
            <div className="w-56">
              <Switch id="only-changed" checked={onlyChanged} onChange={setOnlyChanged} label="Changed calls only" />
            </div>
          </div>
        </div>
        {opt ? (
          rows.length ? (
            <div className="max-h-[520px] overflow-auto">
              <table className="table-glass">
                <thead>
                  <tr>
                    <th>Train</th>
                    <th>Station</th>
                    <th>Published</th>
                    <th>FIFO</th>
                    <th>CP-SAT</th>
                    <th className="!text-right">Saving</th>
                    <th>Change</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 400).map((r) => {
                    const ck = CHANGE_KIND[r.change_status || ""] ?? { kind: "muted" as const, label: (r.change_status || "—").replace(/_/g, " ").toLowerCase() };
                    const t = (a?: string | null, d?: string | null) => (a && d && a !== d ? `${a} / ${d}` : d || a || "—");
                    const saving = r.delay_savings_minutes ?? 0;
                    return (
                      <tr key={`${r.service_id}-${r.stop_sequence}-${r.station_id}`}>
                        <td className="text-fg-1">
                          <span className="font-mono">{trainNumber(r.train_id)}</span> <span className="text-fg-2">{r.train_name}</span>
                        </td>
                        <td className="font-mono">{r.station_id}</td>
                        <td className="font-mono">{t(r.published_arrival_str, r.published_departure_str)}</td>
                        <td className="font-mono text-[#dcae84]">{t(r.feasible_arrival_str, r.feasible_departure_str)}</td>
                        <td className="font-mono text-[#b3a2ff]">{t(r.optimized_arrival_str, r.optimized_departure_str)}</td>
                        <td className={cx("!text-right font-mono", saving > 0 ? "text-clear" : saving < 0 ? "text-conflict" : "text-fg-2")}>{saving === 0 ? "0" : `${saving > 0 ? "+" : "−"}${fmtNum(Math.abs(saving), 0)}`}</td>
                        <td>
                          <StatusChip kind={ck.kind}>{ck.label}</StatusChip>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title={onlyChanged ? "CP-SAT kept every call as FIFO had it" : "No timetabled calls in this shift"} body={onlyChanged ? "Turn off “Changed calls only” to see the full timetable." : undefined} />
          )
        ) : (
          <div className="flex flex-col gap-2 p-6">
            {[0, 1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-9" />
            ))}
          </div>
        )}
      </Panel>

      {/* Explainable recommendations */}
      <Panel className="p-6">
        <h2 className="text-[1.1875rem] font-semibold tracking-[-0.01em] text-fg-1">AI recommendations</h2>
        <p className="mt-1 max-w-[70ch] text-[0.8125rem] leading-relaxed text-fg-2">
          The decision-support layer ranks what to do about this shift and shows its reasoning: what triggered it, the bottleneck, the binding constraints, the decision, and the expected outcome.
        </p>
        {analysis ? (
          analysis.recommendations.length ? (
            <ul className="mt-5 divide-y divide-[var(--line)] border-y border-line">
              {analysis.recommendations.map((r) => (
                <RecommendationRow key={r.recommendation_id} rec={r} />
              ))}
            </ul>
          ) : (
            <EmptyState title="Nothing to recommend" body="No conflicts or bottlenecks need action in this shift." />
          )
        ) : loading ? (
          <div className="mt-5 flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-16" />
            ))}
          </div>
        ) : (
          <p className="mt-4 text-[0.875rem] text-fg-2">Solve the shift to see recommendations.</p>
        )}
      </Panel>
    </div>
  );
}

function RecommendationRow({ rec }: { rec: Recommendation }) {
  const [open, setOpen] = useState(false);
  return (
    <li className="py-4">
      <button type="button" className="flex w-full items-start gap-4 text-left" aria-expanded={open} onClick={() => setOpen((v) => !v)}>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <StatusChip kind={tierKind(rec.priority_tier)}>{(rec.priority_tier || "").toLowerCase().replace(/^\w/, (m) => m.toUpperCase())}</StatusChip>
            <span className="chip">{rec.category}</span>
            <span className="text-[0.75rem] text-fg-3">confidence {Math.round((rec.confidence_score ?? 0) * 100)}%</span>
          </div>
          <p className="mt-2 text-[0.9375rem] font-medium text-fg-1">{rec.title}</p>
          <p className="mt-1 max-w-[80ch] text-[0.8125rem] leading-relaxed text-fg-2">{rec.reason}</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <DeltaChip value={-(rec.expected_delay_savings ?? 0)} unit=" min" good={(rec.expected_delay_savings ?? 0) >= 0} />
          <ChevronDown className={cx("h-4 w-4 text-fg-3 transition-transform duration-200", open && "rotate-180")} aria-hidden />
        </div>
      </button>
      {open ? (
        <div className="rise mt-4 grid gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          {rec.reasoning_path?.length ? (
            <ol className="relative flex flex-col gap-4 pl-6">
              <span className="absolute bottom-2 left-[5px] top-2 w-px bg-[linear-gradient(var(--champagne),var(--violet))]" aria-hidden />
              {rec.reasoning_path.map((s) => (
                <li key={s.step_number} className="relative">
                  <span className="absolute -left-6 top-1 h-[11px] w-[11px] rounded-full border-2 border-ink-0 bg-champagne" aria-hidden />
                  <p className="text-[0.8125rem] font-medium text-fg-1">{s.title}</p>
                  <p className="mt-0.5 text-[0.8125rem] leading-relaxed text-fg-2">{s.detail}</p>
                </li>
              ))}
            </ol>
          ) : null}
          <dl className="flex flex-col gap-3 text-[0.8125rem]">
            {rec.counterfactual_analysis ? (
              <div>
                <dt className="label">If not applied</dt>
                <dd className="mt-1 leading-relaxed text-fg-2">{rec.counterfactual_analysis.impact_if_not_applied}</dd>
              </div>
            ) : null}
            {rec.constraint_explanation ? (
              <div>
                <dt className="label">Binding constraint</dt>
                <dd className="mt-1 leading-relaxed text-fg-2">{rec.constraint_explanation.headway || rec.constraint_explanation.junction_contention}</dd>
              </div>
            ) : null}
            <div>
              <dt className="label">Affects</dt>
              <dd className="mt-1 text-fg-2">
                {(rec.affected_services ?? []).map(serviceShort).join(", ") || "—"} · {rec.affected_resources.join(", ")}
              </dd>
            </div>
            <div>
              <dt className="label">Evidence</dt>
              <dd className="mt-1 leading-relaxed text-fg-2">{rec.evidence_basis}</dd>
            </div>
          </dl>
        </div>
      ) : null}
    </li>
  );
}
