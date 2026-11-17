"use client";

import React from "react";
import { 
  Activity, 
  AlertOctagon, 
  AlertTriangle, 
  ArrowRight, 
  CheckCircle2, 
  Clock, 
  Cpu, 
  Flame, 
  Layers, 
  Play, 
  ShieldAlert, 
  Sparkles, 
  Train, 
  TrendingDown, 
  Zap 
} from "lucide-react";
import { 
  NetworkResponse, 
  SimulateResponse, 
  WhatIfResponse 
} from "@/lib/types";

interface DashboardOverviewProps {
  network: NetworkResponse | null;
  simulationData: SimulateResponse | null;
  whatIfData: WhatIfResponse | null;
  onNavigateTab: (tab: string) => void;
  onTriggerScenario: (scenarioType: "SINGLE" | "MULTI" | "TSR" | "COMPOUND") => void;
}

export const DashboardOverview: React.FC<DashboardOverviewProps> = ({
  network,
  simulationData,
  whatIfData,
  onNavigateTab,
  onTriggerScenario,
}) => {
  const severity = whatIfData?.operational_severity || "NORMAL";
  const topRec = whatIfData?.recommendations && whatIfData.recommendations.length > 0
    ? whatIfData.recommendations[0]
    : null;

  const getSeverityBg = (sev: string) => {
    switch (sev) {
      case "CRITICAL":
      case "EMERGENCY":
        return "bg-rose-950/40 border-rose-500/50 text-rose-300";
      case "WARNING":
        return "bg-amber-950/40 border-amber-500/50 text-amber-300";
      case "ADVISORY":
        return "bg-yellow-950/40 border-yellow-500/50 text-yellow-300";
      default:
        return "bg-emerald-950/40 border-emerald-500/50 text-emerald-300";
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. Operational Situational Severity Banner */}
      <div className={`p-5 rounded-xl border ${getSeverityBg(severity)} flex flex-wrap items-center justify-between gap-4 font-mono`}>
        <div className="flex items-center space-x-4">
          <div className="p-3 rounded-xl bg-railway-950/80 border border-current shadow-[0_0_16px_currentColor]">
            {severity === "CRITICAL" || severity === "EMERGENCY" ? (
              <AlertOctagon className="w-6 h-6 animate-pulse" />
            ) : severity === "WARNING" ? (
              <AlertTriangle className="w-6 h-6" />
            ) : (
              <CheckCircle2 className="w-6 h-6 text-emerald-400" />
            )}
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold uppercase tracking-wider">
                CHENNAI DIVISION OPERATIONAL STATUS:
              </span>
              <span className="text-sm font-extrabold uppercase underline">
                {severity}
              </span>
            </div>
            <p className="text-xs opacity-80 mt-0.5">
              {whatIfData?.scenario_name || "Normal timetable operations active. Continuous digital twin state monitoring."}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-4 text-xs">
          <div className="bg-railway-950/80 px-3 py-1.5 rounded-lg border border-current/30">
            <span className="opacity-70 text-[10px] block">DELAY SAVINGS</span>
            <span className="text-emerald-400 font-bold text-sm">
              +{whatIfData?.net_delay_savings_minutes.toFixed(1) || "0.0"}m ({whatIfData?.net_delay_savings_percent.toFixed(1) || "0.0"}%)
            </span>
          </div>

          <div className="bg-railway-950/80 px-3 py-1.5 rounded-lg border border-current/30">
            <span className="opacity-70 text-[10px] block">ACTIVE CONFLICTS</span>
            <span className="font-bold text-sm">
              {whatIfData?.prioritized_conflicts.length ?? simulationData?.detected_conflicts.length ?? 0}
            </span>
          </div>
        </div>
      </div>

      {/* 2. Top Actionable Controller Directive Alert Box */}
      {topRec && (
        <div className="bg-railway-900 border border-cyan-500/40 p-5 rounded-xl shadow-[0_0_20px_rgba(6,182,212,0.15)] font-mono text-xs space-y-3">
          <div className="flex items-center justify-between border-b border-railway-800 pb-2.5">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span className="font-bold text-cyan-300 uppercase tracking-wider">
                PRIMARY ACTIONABLE DISPATCH DIRECTIVE ({topRec.priority_tier})
              </span>
            </div>
            <div className="flex items-center space-x-2">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                topRec.operational_context === "LIVE_OPERATIONAL"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "bg-purple-500/20 text-purple-300 border border-purple-500/40"
              }`}>
                {topRec.operational_context || "OPERATIONAL"}
              </span>
              <span className="px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 text-[10px] font-bold uppercase">
                {topRec.category || topRec.recommendation_type}
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-2">
            <h4 className="text-base font-bold text-white">{topRec.title}</h4>
            <span className="text-emerald-400 font-bold">
              Expected Savings: +{topRec.expected_delay_savings.toFixed(1)}m (Opt {topRec.expected_delay_minutes.toFixed(1)}m)
            </span>
          </div>

          <p className="text-slate-300 text-xs leading-relaxed bg-railway-950 p-3 rounded-lg border border-railway-800">
            <strong className="text-cyan-400">Dispatcher Rationale:</strong> {topRec.reason}
          </p>

          {topRec.counterfactual_analysis?.impact_if_not_applied && (
            <div className="p-2.5 rounded-lg bg-rose-950/30 border border-rose-500/30 text-[11px] text-rose-300 flex items-start space-x-2">
              <AlertTriangle className="w-3.5 h-3.5 text-rose-400 mt-0.5 flex-shrink-0" />
              <div>
                <span className="font-bold">Counterfactual Impact if Unapplied: </span>
                <span className="text-slate-300">{topRec.counterfactual_analysis.impact_if_not_applied}</span>
              </div>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between text-[11px] text-slate-400 pt-1">
            <span>Target: <strong className="text-slate-200">{topRec.target_service_id}</strong></span>
            <span>Confidence: <strong className="text-emerald-400">{Math.round((topRec.confidence_metrics?.optimization_agreement ?? topRec.confidence_score) * 100)}%</strong></span>
            <span>Resources: <strong className="text-slate-200">{topRec.affected_resources.join(", ") || "Mainline"}</strong></span>
            <button
              onClick={() => onNavigateTab("what-if")}
              className="flex items-center space-x-1 text-cyan-400 hover:text-cyan-300 underline font-semibold"
            >
              <span>Explain Reasoning Pathway</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* 3. Quick Disruption Scenario Simulation Launchers */}
      <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-4 font-mono text-xs">
        <div className="flex items-center justify-between border-b border-railway-800 pb-3">
          <div className="flex items-center space-x-2">
            <Zap className="w-4 h-4 text-rose-400" />
            <h3 className="font-bold text-white uppercase tracking-wider">
              One-Click Operational Disruption Scenarios
            </h3>
          </div>
          <span className="text-slate-500 text-[11px]">Instant What-If & Decision Support Evaluation</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <button
            onClick={() => onTriggerScenario("SINGLE")}
            className="p-3.5 rounded-xl bg-railway-950 border border-railway-800 hover:border-amber-500/50 text-left space-y-2 group transition-all"
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-amber-300">Single Train Delay</span>
              <Play className="w-3.5 h-3.5 text-amber-400 opacity-60 group-hover:opacity-100" />
            </div>
            <p className="text-slate-400 text-[11px] line-clamp-2">
              Lalbagh Express (12607) +25 min origin delay at Chennai Central.
            </p>
          </button>

          <button
            onClick={() => onTriggerScenario("MULTI")}
            className="p-3.5 rounded-xl bg-railway-950 border border-railway-800 hover:border-amber-500/50 text-left space-y-2 group transition-all"
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-amber-300">Multi-Train Contention</span>
              <Play className="w-3.5 h-3.5 text-amber-400 opacity-60 group-hover:opacity-100" />
            </div>
            <p className="text-slate-400 text-[11px] line-clamp-2">
              Dual late departures (12607 + 12609) contending for Basin Bridge throat.
            </p>
          </button>

          <button
            onClick={() => onTriggerScenario("TSR")}
            className="p-3.5 rounded-xl bg-railway-950 border border-railway-800 hover:border-cyan-500/50 text-left space-y-2 group transition-all"
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-cyan-300">Speed Restriction</span>
              <Play className="w-3.5 h-3.5 text-cyan-400 opacity-60 group-hover:opacity-100" />
            </div>
            <p className="text-slate-400 text-[11px] line-clamp-2">
              Temporary speed restriction on MAS-BBQ mainline throat segment.
            </p>
          </button>

          <button
            onClick={() => onTriggerScenario("COMPOUND")}
            className="p-3.5 rounded-xl bg-rose-950/30 border border-rose-500/40 hover:border-rose-500 text-left space-y-2 group transition-all"
          >
            <div className="flex items-center justify-between">
              <span className="font-bold text-rose-300">Severe Compound</span>
              <Play className="w-3.5 h-3.5 text-rose-400 opacity-60 group-hover:opacity-100" />
            </div>
            <p className="text-slate-400 text-[11px] line-clamp-2">
              Simultaneous express delays + suburban peak ripple + throat bottleneck.
            </p>
          </button>
        </div>
      </div>

      {/* 4. Division Corridor Telemetry & Core KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 font-mono text-xs">
        {/* West Mainline Corridor */}
        <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-railway-800 pb-2">
            <span className="font-bold text-cyan-300">WEST MAINLINE CORRIDOR</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300">MAS ➔ AJJ</span>
          </div>
          <div className="space-y-1.5 text-slate-300 text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-500">Key Junctions:</span>
              <span>BBQ, VJM, PAB, AJJ</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Scheduled Services:</span>
              <span>12607, 12609, 12610, 43411</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Physical Feasibility:</span>
              <span className="text-emerald-400 font-bold">100% Verified</span>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab("topology")}
            className="w-full mt-2 py-1.5 rounded bg-railway-950 hover:bg-railway-800 border border-railway-800 text-cyan-300 text-center block"
          >
            View Corridor Topology
          </button>
        </div>

        {/* North Corridor */}
        <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-railway-800 pb-2">
            <span className="font-bold text-amber-300">NORTH MAINLINE CORRIDOR</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300">MAS ➔ GDR</span>
          </div>
          <div className="space-y-1.5 text-slate-300 text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-500">Key Junctions:</span>
              <span>BBQ, KOK, GDR</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Intermediate Stations:</span>
              <span>TVT, ENR, PON</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Status:</span>
              <span className="text-slate-400">Topology Integrated</span>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab("topology")}
            className="w-full mt-2 py-1.5 rounded bg-railway-950 hover:bg-railway-800 border border-railway-800 text-amber-300 text-center block"
          >
            View Corridor Topology
          </button>
        </div>

        {/* South & Bypass Corridors */}
        <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between border-b border-railway-800 pb-2">
            <span className="font-bold text-emerald-300">SOUTH & BYPASS CORRIDORS</span>
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300">MSB ➔ CGL</span>
          </div>
          <div className="space-y-1.5 text-slate-300 text-[11px]">
            <div className="flex justify-between">
              <span className="text-slate-500">Key Nodes:</span>
              <span>MSB, MS, TBM, CGL, PTMS</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Cross Bypass:</span>
              <span>MSB ↔ VJM ↔ BBQ</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Status:</span>
              <span className="text-slate-400">Topology Integrated</span>
            </div>
          </div>
          <button
            onClick={() => onNavigateTab("topology")}
            className="w-full mt-2 py-1.5 rounded bg-railway-950 hover:bg-railway-800 border border-railway-800 text-emerald-300 text-center block"
          >
            View Corridor Topology
          </button>
        </div>
      </div>
    </div>
  );
};
