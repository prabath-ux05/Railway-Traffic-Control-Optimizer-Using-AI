"use client";

import React, { useState, useMemo } from "react";
import { 
  ArrowRight, 
  Check, 
  CheckCircle2, 
  Clock, 
  Cpu, 
  FileText, 
  Flame, 
  GitCommit, 
  Layers, 
  ListFilter, 
  Play, 
  RefreshCw, 
  RotateCcw, 
  ShieldAlert, 
  ShieldCheck, 
  Sliders, 
  Sparkles, 
  Train, 
  TrendingDown, 
  Undo2, 
  Zap 
} from "lucide-react";
import { 
  NetworkResponse, 
  OptimizeRequest, 
  OptimizeResponse, 
  SimulateResponse 
} from "@/lib/types";

interface OptimizationPanelProps {
  network: NetworkResponse | null;
  optimizationData: OptimizeResponse | null;
  simulationData?: SimulateResponse | null;
  onRunOptimization: (req: OptimizeRequest) => void;
  isLoading: boolean;
}

export const OptimizationPanel: React.FC<OptimizationPanelProps> = ({
  network,
  optimizationData,
  simulationData,
  onRunOptimization,
  isLoading,
}) => {
  // Service Selection State
  const defaultServices = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"];
  const [selectedServices, setSelectedServices] = useState<string[]>(defaultServices);

  // Disruption Context States
  const [activeTab, setActiveTab] = useState<"TIMETABLE" | "DIFF" | "PRECEDENCE" | "PLATFORMS">("TIMETABLE");
  const [injectedDelaySvc, setInjectedDelaySvc] = useState<string>("SRV_12607_01");
  const [injectedDelayMinutes, setInjectedDelayMinutes] = useState<number>(20);
  
  // Per-service customized departure delays
  const [departureDelays, setDepartureDelays] = useState<Record<string, number>>({
    "SRV_12607_01": 20,
  });

  // Station dwell delay injection state
  const [selectedStationSvc, setSelectedStationSvc] = useState<string>("SRV_12607_01");
  const [selectedStationId, setSelectedStationId] = useState<string>("KOK");
  const [stationDwellDelay, setStationDwellDelay] = useState<number>(0);
  const [stationDelays, setStationDelays] = useState<Record<string, Record<string, number>>>({});

  // Proposed Controller Decision State (Non-destructive workspace state)
  const [isProposedDecisionApplied, setIsProposedDecisionApplied] = useState<boolean>(false);
  const [proposedDecisionTimestamp, setProposedDecisionTimestamp] = useState<string | null>(null);

  // Toggle single service selection
  const handleToggleService = (sId: string) => {
    setSelectedServices((prev) =>
      prev.includes(sId) ? prev.filter((id) => id !== sId) : [...prev, sId]
    );
  };

  // Quick service selection presets
  const handleSelectAll = () => {
    if (network) {
      setSelectedServices(network.services.map((s) => s.id));
    }
  };

  const handleDeselectAll = () => {
    setSelectedServices([]);
  };

  const handleSelectExpressOnly = () => {
    if (network) {
      const express = network.services
        .filter((s) => s.priority_class === "SUPERFAST" || s.priority_class === "EXPRESS" || s.priority_class === "PASSENGER")
        .map((s) => s.id);
      setSelectedServices(express);
    }
  };

  const handleSelectSuburbanOnly = () => {
    if (network) {
      const suburban = network.services
        .filter((s) => s.priority_class === "SUBURBAN_EMU" || s.priority_class === "SUBURBAN")
        .map((s) => s.id);
      setSelectedServices(suburban);
    }
  };

  const handleResetDefaultServices = () => {
    setSelectedServices(defaultServices);
  };

  // Add or update departure delay
  const handleSetDepartureDelay = (sId: string, delayMin: number) => {
    setDepartureDelays((prev) => {
      const updated = { ...prev };
      if (delayMin > 0) {
        updated[sId] = delayMin;
      } else {
        delete updated[sId];
      }
      return updated;
    });
  };

  // Add station dwell delay
  const handleAddStationDelay = () => {
    if (stationDwellDelay <= 0) return;
    setStationDelays((prev) => {
      const updated = { ...prev };
      if (!updated[selectedStationSvc]) {
        updated[selectedStationSvc] = {};
      }
      updated[selectedStationSvc][selectedStationId] = stationDwellDelay;
      return updated;
    });
  };

  const handleRemoveStationDelay = (sId: string, stnId: string) => {
    setStationDelays((prev) => {
      const updated = { ...prev };
      if (updated[sId]) {
        delete updated[sId][stnId];
        if (Object.keys(updated[sId]).length === 0) {
          delete updated[sId];
        }
      }
      return updated;
    });
  };

  // Sync with current simulation state
  const handleSyncWithSimulation = () => {
    if (!simulationData) return;
    const simDelays: Record<string, number> = {};
    const delayedSvcs: string[] = [];
    
    simulationData.train_positions.forEach((pos) => {
      if (pos.delay_minutes > 0) {
        simDelays[pos.service_id] = Math.round(pos.delay_minutes);
        delayedSvcs.push(pos.service_id);
      }
    });

    if (delayedSvcs.length > 0) {
      setSelectedServices((prev) => Array.from(new Set([...prev, ...delayedSvcs])));
      setDepartureDelays(simDelays);
    }
  };

  // Execute optimization
  const handleExecuteOptimization = () => {
    if (selectedServices.length === 0) {
      return;
    }
    onRunOptimization({
      service_ids: selectedServices,
      departure_delays: departureDelays,
      station_delays: Object.keys(stationDelays).length > 0 ? stationDelays : undefined,
    });
    // Reset proposed state until user explicitly approves
    setIsProposedDecisionApplied(false);
  };

  // Apply as Proposed Decision
  const handleApplyProposedDecision = () => {
    setIsProposedDecisionApplied(true);
    setProposedDecisionTimestamp(new Date().toLocaleTimeString());
  };

  const handleRevertProposedDecision = () => {
    setIsProposedDecisionApplied(false);
    setProposedDecisionTimestamp(null);
  };

  // Identify affected services
  const affectedServiceIds = useMemo(() => {
    const affected = new Set<string>();
    Object.keys(departureDelays).forEach((id) => affected.add(id));
    Object.keys(stationDelays).forEach((id) => affected.add(id));
    
    if (optimizationData) {
      Object.entries(optimizationData.adjusted_timetables).forEach(([sId, adjs]) => {
        if (adjs.some((a) => a.delay_minutes > 0)) {
          affected.add(sId);
        }
      });
      optimizationData.precedence_decisions.forEach((p) => {
        affected.add(p.first_service_id);
        affected.add(p.second_service_id);
      });
    }
    return affected;
  }, [departureDelays, stationDelays, optimizationData]);

  // Selected service objects
  const availableServices = network?.services || [];

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* 1. Proposed Controller Decision Status Banner */}
      {isProposedDecisionApplied && optimizationData && (
        <div className="p-4 rounded-xl bg-cyan-950/40 border border-cyan-500/50 shadow-[0_0_20px_rgba(6,182,212,0.15)] flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-lg bg-cyan-500/20 border border-cyan-400 text-cyan-300">
              <ShieldCheck className="w-5 h-5 text-cyan-400" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="text-xs font-bold text-cyan-200 uppercase tracking-wider">
                  PROPOSED RESCHEDULE DECISION ACTIVE:
                </span>
                <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-bold text-[10px]">
                  REF: PROP-CP-SAT-{proposedDecisionTimestamp?.replace(/:/g, "") || "01"}
                </span>
                <span className="text-[10px] text-slate-400">
                  (Prepared at {proposedDecisionTimestamp})
                </span>
              </div>
              <p className="text-[11px] text-slate-300 mt-0.5">
                Controller action queued: {optimizationData.precedence_decisions.length} precedence overrides & {optimizationData.platform_assignments.length} platform allocations ready for dispatch lock.
              </p>
              <span className="text-[10px] text-slate-400 italic">
                * Note: Reference published timetable remains unmodified and intact.
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={handleRevertProposedDecision}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-railway-900 hover:bg-railway-800 text-slate-300 border border-railway-700 text-xs font-semibold transition-all"
            >
              <Undo2 className="w-3.5 h-3.5 text-slate-400" />
              <span>REVERT TO PUBLISHED VIEW</span>
            </button>
            <div className="px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 font-bold text-xs flex items-center space-x-1">
              <Check className="w-3.5 h-3.5" />
              <span>SAVINGS +{optimizationData.net_delay_savings_minutes.toFixed(1)}m</span>
            </div>
          </div>
        </div>
      )}

      {/* 2. Main CP-SAT Optimizer Configuration Console */}
      <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-5">
        {/* Console Header */}
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-railway-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-lg bg-indigo-950/70 border border-indigo-500/30 text-indigo-400">
              <Cpu className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                Mixed-Integer CP-SAT Rescheduling & Optimization Engine
              </h2>
              <p className="text-xs text-slate-400">
                Solves global headway separation, platform occupancies, and junction throat locks to eliminate conflicts and minimize delay.
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            {simulationData && (
              <button
                onClick={handleSyncWithSimulation}
                className="flex items-center space-x-1.5 px-3 py-2 rounded-lg bg-railway-950 hover:bg-railway-800 text-cyan-300 border border-cyan-500/30 font-semibold transition-all"
                title="Sync delayed trains from active live simulation"
              >
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <span>SYNC LIVE SIM STATE</span>
              </button>
            )}

            <button
              onClick={handleExecuteOptimization}
              disabled={isLoading || selectedServices.length === 0}
              className="flex items-center space-x-2 px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-mono text-xs font-semibold shadow-[0_0_16px_rgba(99,102,241,0.35)] transition-all disabled:opacity-50"
            >
              {isLoading ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4 fill-white" />
              )}
              <span>EXECUTE CP-SAT SOLVER</span>
            </button>
          </div>
        </div>

        {/* Multi-Train / Service Selector */}
        <div className="space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center space-x-2">
              <Train className="w-4 h-4 text-indigo-400" />
              <span className="font-bold text-slate-200">
                SERVICE SELECTION FOR RESCHEDULING ({selectedServices.length} of {availableServices.length} Selected)
              </span>
            </div>
            <div className="flex items-center space-x-2 text-[11px]">
              <button
                onClick={handleSelectAll}
                className="px-2 py-1 rounded bg-railway-950 hover:bg-railway-800 text-slate-300 border border-railway-700"
              >
                ALL
              </button>
              <button
                onClick={handleSelectExpressOnly}
                className="px-2 py-1 rounded bg-railway-950 hover:bg-railway-800 text-indigo-300 border border-indigo-900"
              >
                EXPRESS ONLY
              </button>
              <button
                onClick={handleSelectSuburbanOnly}
                className="px-2 py-1 rounded bg-railway-950 hover:bg-railway-800 text-cyan-300 border border-cyan-900"
              >
                SUBURBAN ONLY
              </button>
              <button
                onClick={handleResetDefaultServices}
                className="px-2 py-1 rounded bg-railway-950 hover:bg-railway-800 text-slate-300 border border-railway-700"
              >
                DEFAULT (4)
              </button>
              <button
                onClick={handleDeselectAll}
                className="px-2 py-1 rounded bg-railway-950 hover:bg-railway-800 text-rose-300 border border-rose-900"
              >
                CLEAR
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2.5 max-h-48 overflow-y-auto p-2 bg-railway-950 rounded-xl border border-railway-800">
            {availableServices.map((svc) => {
              const isSelected = selectedServices.includes(svc.id);
              const isAffected = affectedServiceIds.has(svc.id);
              const depDelay = departureDelays[svc.id] || 0;

              return (
                <div
                  key={svc.id}
                  onClick={() => handleToggleService(svc.id)}
                  className={`p-2.5 rounded-lg border transition-all cursor-pointer flex items-center justify-between space-x-2 ${
                    isSelected
                      ? "bg-indigo-950/30 border-indigo-500/50 text-slate-200 shadow-sm"
                      : "bg-railway-900/50 border-railway-800/80 text-slate-400 hover:border-slate-700"
                  }`}
                >
                  <div className="flex items-center space-x-2.5 overflow-hidden">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => {}} // Handled by container onClick
                      className="accent-indigo-500 rounded cursor-pointer"
                    />
                    <div className="truncate">
                      <div className="flex items-center space-x-1.5">
                        <span className="font-bold text-white text-xs truncate">
                          {svc.train_name || svc.train_id}
                        </span>
                        {isAffected && (
                          <span className="px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-300 text-[9px] font-bold border border-amber-500/30">
                            AFFECTED
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-slate-400 block truncate">
                        {svc.id} • {svc.origin} ➔ {svc.destination} ({svc.priority_class})
                      </span>
                    </div>
                  </div>

                  {depDelay > 0 && (
                    <span className="flex-shrink-0 px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 font-bold text-[10px] border border-rose-500/30">
                      +{depDelay}m
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Disruption Context Configuration (Departure Delays & Station Dwells) */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2 border-t border-railway-800/80">
          {/* Departure Delay Configurator */}
          <div className="bg-railway-950 p-4 rounded-xl border border-railway-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-slate-300 font-bold flex items-center space-x-1.5">
                <Sliders className="w-3.5 h-3.5 text-indigo-400" />
                <span>INJECT ORIGIN DEPARTURE DELAY</span>
              </label>
              {departureDelays[injectedDelaySvc] && (
                <span className="text-indigo-300 font-bold">
                  +{departureDelays[injectedDelaySvc]}m configured
                </span>
              )}
            </div>

            <div className="space-y-2">
              <select
                value={injectedDelaySvc}
                onChange={(e) => {
                  setInjectedDelaySvc(e.target.value);
                  setInjectedDelayMinutes(departureDelays[e.target.value] || 0);
                }}
                className="w-full bg-railway-900 border border-railway-800 rounded-lg px-3 py-1.5 text-slate-200 focus:border-indigo-500 focus:outline-none"
              >
                {selectedServices.map((sId) => {
                  const s = network?.services.find((svc) => svc.id === sId);
                  return (
                    <option key={sId} value={sId}>
                      {sId} — {s?.train_name || s?.train_id} ({s?.origin} ➔ {s?.destination})
                    </option>
                  );
                })}
              </select>

              <div className="flex items-center space-x-3 pt-1">
                <input
                  type="range"
                  min="0"
                  max="60"
                  step="1"
                  value={injectedDelayMinutes}
                  onChange={(e) => {
                    const val = Number(e.target.value);
                    setInjectedDelayMinutes(val);
                    handleSetDepartureDelay(injectedDelaySvc, val);
                  }}
                  className="w-full accent-indigo-400"
                />
                <span className="text-indigo-300 font-bold w-12 text-right">
                  +{injectedDelayMinutes}m
                </span>
              </div>

              <div className="flex items-center space-x-1.5 text-[10px]">
                {[0, 10, 20, 30, 45].map((d) => (
                  <button
                    key={d}
                    onClick={() => {
                      setInjectedDelayMinutes(d);
                      handleSetDepartureDelay(injectedDelaySvc, d);
                    }}
                    className={`px-2 py-0.5 rounded border transition-all ${
                      injectedDelayMinutes === d
                        ? "bg-indigo-600 text-white border-indigo-500"
                        : "bg-railway-900 text-slate-400 border-railway-800 hover:border-slate-700"
                    }`}
                  >
                    +{d}m
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Intermediate Station Dwell Delay Configurator */}
          <div className="bg-railway-950 p-4 rounded-xl border border-railway-800 space-y-3">
            <div className="flex items-center justify-between">
              <label className="text-slate-300 font-bold flex items-center space-x-1.5">
                <Clock className="w-3.5 h-3.5 text-cyan-400" />
                <span>INJECT STATION DWELL DELAY</span>
              </label>
              <span className="text-slate-500 text-[10px]">
                {Object.keys(stationDelays).length} active station delays
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <select
                value={selectedStationSvc}
                onChange={(e) => setSelectedStationSvc(e.target.value)}
                className="bg-railway-900 border border-railway-800 rounded-lg px-2 py-1.5 text-slate-200 text-[11px]"
              >
                {selectedServices.map((sId) => (
                  <option key={sId} value={sId}>
                    {sId}
                  </option>
                ))}
              </select>

              <select
                value={selectedStationId}
                onChange={(e) => setSelectedStationId(e.target.value)}
                className="bg-railway-900 border border-railway-800 rounded-lg px-2 py-1.5 text-slate-200 text-[11px]"
              >
                {(network?.stations || []).map((stn) => (
                  <option key={stn.id} value={stn.id}>
                    {stn.id} ({stn.name})
                  </option>
                ))}
              </select>

              <div className="flex items-center space-x-1">
                <input
                  type="number"
                  min="0"
                  max="60"
                  step="1"
                  placeholder="Min"
                  value={stationDwellDelay || ""}
                  onChange={(e) => setStationDwellDelay(Number(e.target.value))}
                  className="w-full bg-railway-900 border border-railway-800 rounded-lg px-2 py-1.5 text-slate-200 text-[11px]"
                />
                <button
                  onClick={handleAddStationDelay}
                  disabled={stationDwellDelay <= 0}
                  className="px-2 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-[10px] disabled:opacity-40"
                >
                  ADD
                </button>
              </div>
            </div>

            {/* List of active station dwell delays */}
            <div className="flex flex-wrap gap-1.5 max-h-16 overflow-y-auto">
              {Object.entries(stationDelays).flatMap(([sId, stns]) =>
                Object.entries(stns).map(([stnId, delayMin]) => (
                  <span
                    key={`${sId}-${stnId}`}
                    className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-500/30 text-cyan-300 text-[10px]"
                  >
                    <span>{sId} @ {stnId}: +{delayMin}m</span>
                    <button
                      onClick={() => handleRemoveStationDelay(sId, stnId)}
                      className="text-rose-400 hover:text-rose-200 font-bold ml-1"
                    >
                      ×
                    </button>
                  </span>
                ))
              )}
              {Object.keys(stationDelays).length === 0 && (
                <span className="text-slate-500 text-[10px] italic">No intermediate station delays injected.</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* 3. Solver Outcome KPI Cards */}
      {optimizationData && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="bg-railway-900 border border-railway-800 p-4 rounded-xl">
            <span className="text-slate-500 block text-[10px]">SOLVER STATUS</span>
            <div className="flex items-center space-x-2 mt-1">
              <span className={`px-2 py-0.5 rounded font-bold border ${
                optimizationData.solver_status === "OPTIMAL"
                  ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                  : optimizationData.solver_status === "FEASIBLE"
                  ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                  : "bg-rose-500/20 text-rose-300 border-rose-500/30"
              }`}>
                {optimizationData.solver_status}
              </span>
            </div>
            <span className="text-slate-500 text-[10px] block mt-1">
              Solve Time: {optimizationData.computation_time_seconds.toFixed(3)}s
            </span>
          </div>

          <div className="bg-railway-900 border border-railway-800 p-4 rounded-xl">
            <span className="text-slate-500 block text-[10px]">FEASIBLE BASELINE (FIFO)</span>
            <span className="text-xl font-bold text-amber-400 mt-1 block">
              {optimizationData.feasible_baseline_delay_minutes.toFixed(1)}m
            </span>
            <span className="text-slate-500 text-[10px] block mt-1">Un-optimized FIFO delay</span>
          </div>

          <div className="bg-railway-900 border border-railway-800 p-4 rounded-xl">
            <span className="text-slate-500 block text-[10px]">CP-SAT OPTIMIZED DELAY</span>
            <span className="text-xl font-bold text-cyan-400 mt-1 block">
              {optimizationData.optimized_total_delay_minutes.toFixed(1)}m
            </span>
            <span className="text-slate-500 text-[10px] block mt-1">Global mathematical optimum</span>
          </div>

          <div className="bg-railway-900 border border-indigo-500/40 p-4 rounded-xl bg-indigo-950/20">
            <span className="text-indigo-300 block text-[10px] font-bold">NET DELAY SAVINGS</span>
            <span className="text-xl font-bold text-emerald-400 mt-1 block">
              +{optimizationData.net_delay_savings_minutes.toFixed(1)}m ({optimizationData.net_delay_savings_percent.toFixed(1)}%)
            </span>
            <span className="text-slate-400 text-[10px] block mt-1">Gains over FIFO dispatch</span>
          </div>

          <div className="bg-railway-900 border border-railway-800 p-4 rounded-xl">
            <span className="text-slate-500 block text-[10px]">UNRESOLVED CONFLICTS</span>
            <span className="text-xl font-bold text-emerald-400 mt-1 block">
              {optimizationData.unresolved_conflicts_count}
            </span>
            <span className="text-slate-500 text-[10px] block mt-1">100% Conflict Free</span>
          </div>
        </div>
      )}

      {/* 4. Reschedule Inspection Workspace with Tabs */}
      <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-4">
        {/* Navigation Tab Header & Proposed Decision Action */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-railway-800 pb-3">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setActiveTab("TIMETABLE")}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === "TIMETABLE"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-railway-950 text-slate-400 hover:text-white"
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
              <span>OPTIMIZED TIMETABLE</span>
            </button>

            <button
              onClick={() => setActiveTab("DIFF")}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === "DIFF"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-railway-950 text-slate-400 hover:text-white"
              }`}
            >
              <GitCommit className="w-3.5 h-3.5" />
              <span>BEFORE / AFTER DIFF</span>
            </button>

            <button
              onClick={() => setActiveTab("PRECEDENCE")}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === "PRECEDENCE"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-railway-950 text-slate-400 hover:text-white"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>PRECEDENCE DECISIONS ({optimizationData?.precedence_decisions.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("PLATFORMS")}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === "PLATFORMS"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-railway-950 text-slate-400 hover:text-white"
              }`}
            >
              <Train className="w-3.5 h-3.5" />
              <span>PLATFORM ALLOCATIONS ({optimizationData?.platform_assignments.length || 0})</span>
            </button>
          </div>

          {/* Action to Apply Reschedule as Controller Proposed Decision */}
          {optimizationData && (
            <div className="flex items-center space-x-2">
              {!isProposedDecisionApplied ? (
                <button
                  onClick={handleApplyProposedDecision}
                  className="flex items-center space-x-1.5 px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-bold shadow-[0_0_12px_rgba(16,185,129,0.3)] transition-all"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>APPLY AS PROPOSED DECISION</span>
                </button>
              ) : (
                <button
                  onClick={handleRevertProposedDecision}
                  className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-railway-950 hover:bg-railway-800 text-rose-300 border border-rose-900 font-bold transition-all"
                >
                  <RotateCcw className="w-3.5 h-3.5" />
                  <span>CLEAR PROPOSED DECISION</span>
                </button>
              )}
            </div>
          )}
        </div>

        {/* Tab 1: Optimized Timetable Table */}
        {activeTab === "TIMETABLE" && (
          <div className="overflow-x-auto max-h-[460px]">
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-railway-900 border-b border-railway-800 text-slate-400 text-[11px]">
                <tr>
                  <th className="py-2.5 px-3">SERVICE / TRAIN</th>
                  <th className="py-2.5 px-3">STATION</th>
                  <th className="py-2.5 px-3">ORIGINAL ARR / DEP</th>
                  <th className="py-2.5 px-3">OPTIMIZED ARR / DEP</th>
                  <th className="py-2.5 px-3">DELAY</th>
                  <th className="py-2.5 px-3">PLATFORM</th>
                  <th className="py-2.5 px-3">STATUS</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-railway-800/60">
                {optimizationData ? (
                  Object.entries(optimizationData.adjusted_timetables).flatMap(([sId, adjs]) => {
                    const svc = network?.services.find((s) => s.id === sId);
                    return adjs.map((adj) => {
                      const isDelayed = adj.delay_minutes > 0;
                      return (
                        <tr key={`${sId}-${adj.station_id}`} className="hover:bg-railway-800/40">
                          <td className="py-2.5 px-3">
                            <span className="font-semibold text-slate-200 block">{sId}</span>
                            <span className="text-[10px] text-slate-500">
                              {svc?.train_name || svc?.train_id}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 font-bold text-cyan-300">{adj.station_id}</td>
                          <td className="py-2.5 px-3 text-slate-400">
                            {adj.original_arrival != null ? `${adj.original_arrival.toFixed(0)}m` : "--"} /{" "}
                            {adj.original_departure != null ? `${adj.original_departure.toFixed(0)}m` : "--"}
                          </td>
                          <td className="py-2.5 px-3 text-emerald-300 font-semibold">
                            {adj.adjusted_arrival_str || "--"} ➔ {adj.adjusted_departure_str || "--"}
                          </td>
                          <td className="py-2.5 px-3">
                            <span className={isDelayed ? "text-amber-400 font-bold" : "text-emerald-400"}>
                              {isDelayed ? `+${adj.delay_minutes.toFixed(1)}m` : "0.0m"}
                            </span>
                          </td>
                          <td className="py-2.5 px-3">
                            <span className="px-1.5 py-0.5 rounded bg-railway-950 border border-railway-700 text-slate-200 text-[10px] font-bold">
                              {adj.assigned_platform || "PF-1"}
                            </span>
                          </td>
                          <td className="py-2.5 px-3">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                              isDelayed
                                ? "bg-amber-500/20 text-amber-300 border-amber-500/30"
                                : "bg-emerald-500/20 text-emerald-300 border-emerald-500/30"
                            }`}>
                              {isDelayed ? "RESCHEDULED" : "ON TIME"}
                            </span>
                          </td>
                        </tr>
                      );
                    });
                  })
                ) : (
                  <tr>
                    <td colSpan={7} className="py-12 text-center text-slate-500 italic">
                      Click "EXECUTE CP-SAT SOLVER" to compute mathematical timetable adjustments.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 2: Before vs After Reschedule Visual Differential */}
        {activeTab === "DIFF" && (
          <div className="space-y-4">
            <div className="p-3 bg-railway-950 rounded-xl border border-railway-800 text-xs text-slate-300 flex items-center justify-between">
              <span>
                Comparing <strong>Published Timetable Reference</strong> against <strong>CP-SAT Optimized Reschedule</strong>.
              </span>
              <span className="text-emerald-400 font-bold">
                {affectedServiceIds.size} Services Affected / {selectedServices.length} Selected
              </span>
            </div>

            <div className="space-y-3 max-h-[460px] overflow-y-auto">
              {optimizationData ? (
                Object.entries(optimizationData.adjusted_timetables).map(([sId, adjs]) => {
                  const svc = network?.services.find((s) => s.id === sId);
                  const totalDelay = adjs.reduce((acc, a) => Math.max(acc, a.delay_minutes), 0);
                  const isAffected = affectedServiceIds.has(sId);

                  return (
                    <div
                      key={sId}
                      className={`p-4 rounded-xl border space-y-3 ${
                        isAffected
                          ? "bg-railway-950 border-amber-500/40 shadow-sm"
                          : "bg-railway-950/60 border-railway-800"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-railway-800 pb-2">
                        <div className="flex items-center space-x-2">
                          <span className="font-bold text-white text-sm">{sId}</span>
                          <span className="text-slate-400">— {svc?.train_name || svc?.train_id}</span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-railway-900 border border-slate-700 text-slate-300">
                            {svc?.origin} ➔ {svc?.destination}
                          </span>
                        </div>
                        <div className="flex items-center space-x-2">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                            totalDelay > 0
                              ? "bg-amber-500/20 text-amber-300 border-amber-500/40"
                              : "bg-emerald-500/20 text-emerald-300 border-emerald-500/40"
                          }`}>
                            {totalDelay > 0 ? `Max Delay +${totalDelay.toFixed(1)}m` : "On Schedule"}
                          </span>
                        </div>
                      </div>

                      {/* Stops timeline diff cards */}
                      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-2">
                        {adjs.map((a) => (
                          <div
                            key={a.station_id}
                            className="p-2.5 rounded-lg bg-railway-900/80 border border-railway-800 space-y-1"
                          >
                            <div className="flex items-center justify-between text-slate-300">
                              <span className="font-bold text-cyan-300">{a.station_id}</span>
                              <span className="text-[10px] px-1.5 py-0.2 rounded bg-railway-950 border border-slate-700 text-slate-400">
                                {a.assigned_platform || "PF-1"}
                              </span>
                            </div>
                            <div className="text-[11px] text-slate-400">
                              <span>Orig: {a.original_departure != null ? `${a.original_departure.toFixed(0)}m` : "--"}</span>
                            </div>
                            <div className="text-[11px] font-bold text-emerald-300 flex items-center justify-between">
                              <span>Resched: {a.adjusted_departure_str || "--"}</span>
                              {a.delay_minutes > 0 ? (
                                <span className="text-amber-400">+{a.delay_minutes.toFixed(0)}m</span>
                              ) : (
                                <span className="text-emerald-400 text-[10px]">OK</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })
              ) : (
                <p className="text-center text-slate-500 py-10 italic">
                  Run CP-SAT optimization to generate before/after schedule diff.
                </p>
              )}
            </div>
          </div>
        )}

        {/* Tab 3: Precedence & Overtaking Decisions */}
        {activeTab === "PRECEDENCE" && (
          <div className="space-y-4">
            <div className="p-3 bg-railway-950 rounded-xl border border-railway-800 text-xs text-slate-300 flex items-center justify-between">
              <span>
                Mathematical CP-SAT Ordering & Overtaking Directives along Shared Tracks and Junction Throats.
              </span>
              <span className="text-indigo-400 font-bold">
                {optimizationData?.precedence_decisions.length || 0} Decisions
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[440px] overflow-y-auto">
              {(!optimizationData || optimizationData.precedence_decisions.length === 0) ? (
                <div className="col-span-2 py-10 text-center text-slate-500 italic">
                  No active precedence overrides required; trains maintain standard headway separation.
                </div>
              ) : (
                optimizationData.precedence_decisions.map((dec, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl bg-railway-950 border border-railway-800 space-y-2 hover:border-indigo-500/40 transition-all"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-cyan-300 text-xs">{dec.resource_id}</span>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-bold">
                        ORDER DECISION
                      </span>
                    </div>

                    <div className="p-2.5 rounded-lg bg-railway-900 border border-railway-800/80 flex items-center justify-between">
                      <div className="space-y-0.5">
                        <span className="text-[10px] text-slate-500 block">PRECEDENCE 1 (FIRST)</span>
                        <span className="font-bold text-emerald-400 text-xs">{dec.first_service_id}</span>
                      </div>
                      <ArrowRight className="w-4 h-4 text-indigo-400" />
                      <div className="space-y-0.5 text-right">
                        <span className="text-[10px] text-slate-500 block">PRECEDENCE 2 (FOLLOWS)</span>
                        <span className="font-bold text-amber-400 text-xs">{dec.second_service_id}</span>
                      </div>
                    </div>

                    <p className="text-[11px] text-slate-300 leading-relaxed italic">
                      {dec.reason}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Tab 4: Platform Allocations Matrix */}
        {activeTab === "PLATFORMS" && (
          <div className="space-y-4">
            <div className="p-3 bg-railway-950 rounded-xl border border-railway-800 text-xs text-slate-300 flex items-center justify-between">
              <span>
                Dynamic Platform Slot Assignments computed by CP-SAT to avoid station platform starvation.
              </span>
              <span className="text-cyan-400 font-bold">
                {optimizationData?.platform_assignments.length || 0} Allocations
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 max-h-[440px] overflow-y-auto">
              {(!optimizationData || optimizationData.platform_assignments.length === 0) ? (
                <div className="col-span-3 py-10 text-center text-slate-500 italic">
                  Standard platform allocation mapping active across stations.
                </div>
              ) : (
                optimizationData.platform_assignments.map((alloc, idx) => {
                  const svc = network?.services.find((s) => s.id === alloc.service_id);
                  return (
                    <div
                      key={idx}
                      className="p-3.5 rounded-xl bg-railway-950 border border-railway-800 space-y-2 hover:border-cyan-500/40 transition-all"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-200">{alloc.service_id}</span>
                        <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[10px] font-bold">
                          {alloc.allocated_resource_id}
                        </span>
                      </div>

                      <div className="text-[11px] text-slate-400">
                        <span className="text-slate-300 font-semibold">{svc?.train_name || svc?.train_id}</span>
                        <span className="block text-[10px] text-slate-500 mt-0.5">
                          Station / Node: {alloc.node_or_section_id}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
