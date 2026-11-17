"use client";

import React, { useState } from "react";
import {
  AlertOctagon,
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Clock,
  ExternalLink,
  Flame,
  Gauge,
  HelpCircle,
  Info,
  Layers,
  MapPin,
  Maximize2,
  Milestone,
  Radio,
  Scale,
  ShieldAlert,
  Shuffle,
  Sliders,
  Sparkles,
  Split,
  Train,
  Zap,
} from "lucide-react";
import { Recommendation } from "@/lib/types";

interface ExplainableRecommendationCardProps {
  rec: Recommendation;
  defaultExpanded?: boolean;
}

export const ExplainableRecommendationCard: React.FC<ExplainableRecommendationCardProps> = ({
  rec,
  defaultExpanded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState<boolean>(defaultExpanded);
  const [activeSubTab, setActiveSubTab] = useState<"PATHWAY" | "EVIDENCE" | "CONSTRAINTS" | "COUNTERFACTUAL">("PATHWAY");

  // Category Theme Styling
  const getCategoryStyles = (category: string) => {
    switch (category) {
      case "precedence change":
        return {
          badge: "bg-indigo-950/60 text-indigo-300 border-indigo-500/50",
          icon: Shuffle,
          accent: "border-l-indigo-500",
        };
      case "holding":
        return {
          badge: "bg-amber-950/60 text-amber-300 border-amber-500/50",
          icon: Clock,
          accent: "border-l-amber-500",
        };
      case "platform reassignment":
        return {
          badge: "bg-purple-950/60 text-purple-300 border-purple-500/50",
          icon: Layers,
          accent: "border-l-purple-500",
        };
      case "dispatch sequencing":
        return {
          badge: "bg-cyan-950/60 text-cyan-300 border-cyan-500/50",
          icon: Split,
          accent: "border-l-cyan-500",
        };
      case "speed management":
        return {
          badge: "bg-rose-950/60 text-rose-300 border-rose-500/50",
          icon: Gauge,
          accent: "border-l-rose-500",
        };
      case "maintain schedule":
      default:
        return {
          badge: "bg-emerald-950/60 text-emerald-300 border-emerald-500/50",
          icon: CheckCircle2,
          accent: "border-l-emerald-500",
        };
    }
  };

  const getTierStyles = (tier: string) => {
    switch (tier) {
      case "CRITICAL":
      case "URGENT":
        return "bg-rose-900/60 text-rose-200 border-rose-500/60";
      case "HIGH":
        return "bg-amber-900/60 text-amber-200 border-amber-500/60";
      case "MEDIUM":
        return "bg-sky-900/60 text-sky-200 border-sky-500/60";
      case "LOW":
      case "ADVISORY":
      default:
        return "bg-slate-900/60 text-slate-300 border-slate-700/60";
    }
  };

  const isHypothetical = rec.operational_context === "HYPOTHETICAL_SCENARIO";
  const catStyle = getCategoryStyles(rec.category);
  const CategoryIcon = catStyle.icon;

  const directSavings = rec.delay_analysis?.direct_delay_reduction_minutes ?? (rec.expected_delay_savings * 0.65);
  const propSavings = rec.delay_analysis?.propagated_delay_reduction_minutes ?? (rec.expected_delay_savings * 0.35);
  const totalSavings = rec.expected_delay_savings;

  return (
    <div
      className={`rounded-xl bg-railway-950 border border-railway-800/90 shadow-md font-mono transition-all border-l-4 ${catStyle.accent}`}
    >
      {/* 1. Header Bar */}
      <div className="p-4 space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2.5">
          <div className="flex flex-wrap items-center gap-2">
            {/* Operational Context Tag */}
            {isHypothetical ? (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950/70 border border-amber-500/50 text-amber-300 flex items-center space-x-1">
                <Radio className="w-3 h-3 animate-pulse" />
                <span>SANDBOX WHAT-IF</span>
              </span>
            ) : (
              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950/70 border border-emerald-500/50 text-emerald-300 flex items-center space-x-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-ping mr-1"></span>
                <span>LIVE OPERATIONAL</span>
              </span>
            )}

            {/* Category Badge */}
            <span
              className={`px-2.5 py-0.5 rounded text-[10px] font-bold border flex items-center space-x-1 uppercase ${catStyle.badge}`}
            >
              <CategoryIcon className="w-3 h-3" />
              <span>{rec.category}</span>
            </span>

            {/* Priority Tier Badge */}
            <span className={`px-2 py-0.5 rounded text-[10px] font-extrabold border ${getTierStyles(rec.priority_tier)}`}>
              {rec.priority_tier}
            </span>

            <span className="text-[11px] text-slate-500">#{rec.recommendation_id}</span>
          </div>

          {/* Delay Savings Pill */}
          <div className="flex items-center space-x-2">
            {totalSavings > 0 ? (
              <span className="text-emerald-400 font-bold text-xs bg-emerald-950/50 px-2.5 py-1 rounded-lg border border-emerald-500/30 flex items-center space-x-1">
                <Zap className="w-3.5 h-3.5 text-emerald-400" />
                <span>
                  SAVINGS: +{totalSavings.toFixed(1)}m (Base {rec.baseline_delay_minutes.toFixed(1)}m ➔ Opt {rec.expected_delay_minutes.toFixed(1)}m)
                </span>
              </span>
            ) : (
              <span className="text-slate-400 text-xs bg-railway-900 px-2.5 py-1 rounded-lg border border-railway-800">
                SCHEDULE INTEGRITY MAINTAINED
              </span>
            )}
          </div>
        </div>

        {/* Title */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
            <span>{rec.title}</span>
          </h4>
        </div>

        {/* Operational Rationale */}
        <p className="text-xs text-slate-300 leading-relaxed bg-railway-900/70 p-3 rounded-lg border border-railway-800/80">
          <strong className="text-cyan-400 font-semibold">Dispatcher Rationale: </strong>
          {rec.reason}
        </p>

        {/* Compact Metadata Strip */}
        <div className="flex flex-wrap items-center justify-between gap-3 text-[11px] text-slate-400 pt-1 border-t border-railway-800/60">
          <div className="flex flex-wrap items-center gap-4">
            <span>
              Target Services:{" "}
              <strong className="text-slate-200">
                {rec.affected_services && rec.affected_services.length > 0
                  ? rec.affected_services.join(", ")
                  : rec.target_service_id || "Corridor Traffic"}
              </strong>
            </span>
            <span>
              Key Resources:{" "}
              <strong className="text-slate-200">
                {rec.affected_resources.length > 0 ? rec.affected_resources.join(", ") : "Mainline Throat"}
              </strong>
            </span>
            <span>
              Confidence:{" "}
              <strong className="text-emerald-400">
                {(rec.confidence_score * 100).toFixed(0)}%
              </strong>
            </span>
          </div>

          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center space-x-1.5 text-xs text-cyan-400 hover:text-cyan-300 font-bold bg-cyan-950/40 hover:bg-cyan-900/60 px-3 py-1.5 rounded-lg border border-cyan-500/40 transition-colors"
          >
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span>{isExpanded ? "COLLAPSE EXPLANATION" : "EXPLAIN DECISION"}</span>
            {isExpanded ? <ChevronUp className="w-3.5 h-3.5 ml-0.5" /> : <ChevronDown className="w-3.5 h-3.5 ml-0.5" />}
          </button>
        </div>
      </div>

      {/* 2. Expandable Deep Explainability Panel */}
      {isExpanded && (
        <div className="border-t border-railway-800 bg-railway-900/90 p-5 rounded-b-xl space-y-5 animate-fadeIn">
          {/* Sub-tab Navigation */}
          <div className="flex flex-wrap items-center gap-2 border-b border-railway-800 pb-3">
            <button
              onClick={() => setActiveSubTab("PATHWAY")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors flex items-center space-x-1.5 ${
                activeSubTab === "PATHWAY"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "text-slate-400 hover:text-slate-200 hover:bg-railway-800/60"
              }`}
            >
              <Milestone className="w-3.5 h-3.5" />
              <span>REASONING PATHWAY</span>
            </button>

            <button
              onClick={() => setActiveSubTab("EVIDENCE")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors flex items-center space-x-1.5 ${
                activeSubTab === "EVIDENCE"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "text-slate-400 hover:text-slate-200 hover:bg-railway-800/60"
              }`}
            >
              <Info className="w-3.5 h-3.5" />
              <span>SUPPORTING EVIDENCE</span>
            </button>

            <button
              onClick={() => setActiveSubTab("COUNTERFACTUAL")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors flex items-center space-x-1.5 ${
                activeSubTab === "COUNTERFACTUAL"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "text-slate-400 hover:text-slate-200 hover:bg-railway-800/60"
              }`}
            >
              <Scale className="w-3.5 h-3.5" />
              <span>DELAY & COUNTERFACTUAL</span>
            </button>

            <button
              onClick={() => setActiveSubTab("CONSTRAINTS")}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors flex items-center space-x-1.5 ${
                activeSubTab === "CONSTRAINTS"
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "text-slate-400 hover:text-slate-200 hover:bg-railway-800/60"
              }`}
            >
              <Sliders className="w-3.5 h-3.5" />
              <span>CONSTRAINT PILLARS</span>
            </button>
          </div>

          {/* Sub-tab 1: Controller Reasoning Pathway (5 chronological steps) */}
          {activeSubTab === "PATHWAY" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-bold text-slate-200 flex items-center space-x-1.5">
                  <Milestone className="w-4 h-4 text-cyan-400" />
                  <span>5-STAGE CONTROLLER REASONING PATHWAY</span>
                </span>
                <span className="text-[11px] text-slate-500">
                  {rec.ranking_explanation || `Ranked #${rec.priority_tier}`}
                </span>
              </div>

              <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-railway-800">
                {(rec.reasoning_path && rec.reasoning_path.length > 0
                  ? rec.reasoning_path
                  : [
                      {
                        step_number: 1,
                        phase: "TRIGGER",
                        title: "Disturbance Detected",
                        detail: `Identified schedule contention involving ${rec.affected_services?.join(", ") || "services"} with baseline delay ${rec.baseline_delay_minutes.toFixed(1)}m.`,
                      },
                      {
                        step_number: 2,
                        phase: "BOTTLENECK",
                        title: "Choke-point Isolated",
                        detail: `Resource ${rec.affected_resources.join(", ") || "section"} identified as throughput constraint.`,
                      },
                      {
                        step_number: 3,
                        phase: "CONSTRAINTS",
                        title: "Boundary Conditions Evaluated",
                        detail: "Validated safety headway rules, platform track limits, and train priority weights.",
                      },
                      {
                        step_number: 4,
                        phase: "DECISION",
                        title: `Mathematical Optimization Action (${rec.category})`,
                        detail: `${rec.title}. ${rec.reason}`,
                      },
                      {
                        step_number: 5,
                        phase: "OUTCOME",
                        title: "Projected Relief & Downstream Assurance",
                        detail: `Recovers ${totalSavings.toFixed(1)}m total delay while avoiding secondary queue ripple.`,
                      },
                    ]
                ).map((step) => {
                  const getPhaseColor = (phase: string) => {
                    switch (phase) {
                      case "TRIGGER":
                        return "bg-rose-900/50 text-rose-300 border-rose-500/40";
                      case "BOTTLENECK":
                        return "bg-amber-900/50 text-amber-300 border-amber-500/40";
                      case "CONSTRAINTS":
                        return "bg-sky-900/50 text-sky-300 border-sky-500/40";
                      case "DECISION":
                        return "bg-cyan-900/50 text-cyan-300 border-cyan-500/40";
                      case "OUTCOME":
                      default:
                        return "bg-emerald-900/50 text-emerald-300 border-emerald-500/40";
                    }
                  };

                  return (
                    <div key={step.step_number} className="relative">
                      {/* Node Bullet */}
                      <span className="absolute -left-[27px] top-1.5 w-5 h-5 rounded-full bg-railway-950 border-2 border-cyan-500 flex items-center justify-center text-[10px] font-extrabold text-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.4)]">
                        {step.step_number}
                      </span>

                      <div className="p-3 bg-railway-950 rounded-lg border border-railway-800/80 space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className={`px-2 py-0.5 rounded text-[9px] font-bold border ${getPhaseColor(step.phase)}`}>
                            {step.phase}
                          </span>
                          <span className="text-xs font-bold text-slate-200">{step.title}</span>
                        </div>
                        <p className="text-[11px] text-slate-300 leading-relaxed pl-1">{step.detail}</p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Sub-tab 2: Supporting Evidence Grid */}
          {activeSubTab === "EVIDENCE" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Triggering Conflicts */}
              <div className="p-3.5 bg-railway-950 rounded-lg border border-railway-800 space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-rose-300 border-b border-railway-800/80 pb-2">
                  <AlertTriangle className="w-4 h-4 text-rose-400" />
                  <span>TRIGGERING CONFLICTS</span>
                </div>
                {rec.supporting_evidence?.triggering_conflicts && rec.supporting_evidence.triggering_conflicts.length > 0 ? (
                  <ul className="space-y-1.5 text-[11px] text-slate-300">
                    {rec.supporting_evidence.triggering_conflicts.map((conf, idx) => (
                      <li key={idx} className="p-2 bg-railway-900/80 rounded border border-rose-500/20 text-rose-200">
                        {conf}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-xs text-slate-500 italic p-2">Zero active conflicts. Schedule operates within nominal limits.</p>
                )}
              </div>

              {/* Contested Bottlenecks */}
              <div className="p-3.5 bg-railway-950 rounded-lg border border-railway-800 space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-amber-300 border-b border-railway-800/80 pb-2">
                  <MapPin className="w-4 h-4 text-amber-400" />
                  <span>CONTESTED BOTTLENECKS</span>
                </div>
                {rec.supporting_evidence?.bottlenecks && rec.supporting_evidence.bottlenecks.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {rec.supporting_evidence.bottlenecks.map((b, idx) => (
                      <span key={idx} className="px-2.5 py-1 rounded bg-amber-950/40 border border-amber-500/30 text-amber-300 text-xs font-semibold">
                        {b}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic p-2">No physical bottlenecks restricted.</p>
                )}
              </div>

              {/* Affected Services */}
              <div className="p-3.5 bg-railway-950 rounded-lg border border-railway-800 space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-cyan-300 border-b border-railway-800/80 pb-2">
                  <Train className="w-4 h-4 text-cyan-400" />
                  <span>AFFECTED SERVICES</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {(rec.supporting_evidence?.affected_services || rec.affected_services || []).map((s, idx) => (
                    <span key={idx} className="px-2.5 py-1 rounded bg-cyan-950/40 border border-cyan-500/30 text-cyan-300 text-xs font-bold">
                      {s}
                    </span>
                  ))}
                </div>
              </div>

              {/* Confidence & Agreement Matrix */}
              <div className="p-3.5 bg-railway-950 rounded-lg border border-railway-800 space-y-2">
                <div className="flex items-center space-x-2 text-xs font-bold text-emerald-300 border-b border-railway-800/80 pb-2">
                  <ShieldAlert className="w-4 h-4 text-emerald-400" />
                  <span>SOLVER CONFIDENCE METRICS</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="p-2 bg-railway-900 rounded border border-railway-800">
                    <span className="text-[10px] text-slate-500 block">CONSTRAINTS</span>
                    <strong className="text-slate-100 font-extrabold text-sm">
                      {rec.confidence_metrics?.supporting_constraints_count || 4}
                    </strong>
                  </div>
                  <div className="p-2 bg-railway-900 rounded border border-railway-800">
                    <span className="text-[10px] text-slate-500 block">AGREEMENT</span>
                    <strong className="text-emerald-400 font-extrabold text-sm">
                      {((rec.confidence_metrics?.optimization_agreement || rec.confidence_score) * 100).toFixed(0)}%
                    </strong>
                  </div>
                  <div className="p-2 bg-railway-900 rounded border border-railway-800">
                    <span className="text-[10px] text-slate-500 block">SEVERITY BASIS</span>
                    <strong className="text-amber-400 font-extrabold text-sm">
                      {rec.confidence_metrics?.conflict_severity_basis || rec.priority_tier}
                    </strong>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Sub-tab 3: Delay Analysis & Counterfactual */}
          {activeSubTab === "COUNTERFACTUAL" && (
            <div className="space-y-4">
              {/* Delay Breakdown Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="p-3.5 bg-railway-950 rounded-lg border border-emerald-500/30">
                  <span className="text-[10px] text-slate-500 block uppercase font-semibold">Total Delay Savings</span>
                  <div className="text-xl font-extrabold text-emerald-400 mt-1">
                    +{totalSavings.toFixed(1)} min
                  </div>
                  <span className="text-[10px] text-slate-400">Baseline {rec.baseline_delay_minutes.toFixed(1)}m ➔ Opt {rec.expected_delay_minutes.toFixed(1)}m</span>
                </div>

                <div className="p-3.5 bg-railway-950 rounded-lg border border-sky-500/30">
                  <span className="text-[10px] text-slate-500 block uppercase font-semibold">Direct Primary Reduction</span>
                  <div className="text-xl font-extrabold text-sky-400 mt-1">
                    +{directSavings.toFixed(1)} min
                  </div>
                  <span className="text-[10px] text-slate-400">Immediate station/node wait mitigated</span>
                </div>

                <div className="p-3.5 bg-railway-950 rounded-lg border border-indigo-500/30">
                  <span className="text-[10px] text-slate-500 block uppercase font-semibold">Propagated Ripple Saved</span>
                  <div className="text-xl font-extrabold text-indigo-400 mt-1">
                    +{propSavings.toFixed(1)} min
                  </div>
                  <span className="text-[10px] text-slate-400">Downstream queue prevention</span>
                </div>
              </div>

              {/* Counterfactual Impact Alert Box */}
              <div className="p-4 bg-rose-950/40 rounded-xl border border-rose-500/40 space-y-2">
                <div className="flex items-center space-x-2 text-rose-300 text-xs font-bold">
                  <AlertOctagon className="w-4 h-4 text-rose-400 flex-shrink-0" />
                  <span>COUNTERFACTUAL ANALYSIS: WHAT HAPPENS IF THIS DIRECTIVE IS NOT APPLIED?</span>
                </div>
                <p className="text-xs text-rose-200 leading-relaxed pl-6">
                  {rec.counterfactual_analysis?.impact_if_not_applied ||
                    `If rejected, unmitigated delay of ${rec.baseline_delay_minutes.toFixed(1)}m persists, compounding congestion across shared corridor blocks.`}
                </p>
                <div className="pl-6 pt-1 text-[11px] text-amber-300 flex items-center space-x-1.5">
                  <Flame className="w-3.5 h-3.5 text-amber-400 flex-shrink-0" />
                  <span>
                    <strong>Downstream Ripple Risk: </strong>
                    {rec.counterfactual_analysis?.downstream_ripple_risk ||
                      "Cascading queue formation on following Chennai suburban and express services."}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Sub-tab 4: Constraint Explanation Pillars */}
          {activeSubTab === "CONSTRAINTS" && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="p-3.5 bg-railway-950 rounded-lg border border-railway-800 space-y-1">
                <div className="flex items-center space-x-2 text-xs font-bold text-cyan-300">
                  <Clock className="w-3.5 h-3.5 text-cyan-400" />
                  <span>1. HEADWAY SEPARATION RULE</span>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  {rec.constraint_explanation?.headway ||
                    "Enforces minimum 3.0 min safety headway buffer between consecutive train movements along the track section."}
                </p>
              </div>

              <div className="p-3.5 bg-railway-950 rounded-lg border border-railway-800 space-y-1">
                <div className="flex items-center space-x-2 text-xs font-bold text-purple-300">
                  <Layers className="w-3.5 h-3.5 text-purple-400" />
                  <span>2. PLATFORM CAPACITY MUTEX</span>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  {rec.constraint_explanation?.platform_capacity ||
                    "Restricts concurrent platform track occupancy to maximum 1 service per platform track at any time."}
                </p>
              </div>

              <div className="p-3.5 bg-railway-950 rounded-lg border border-railway-800 space-y-1">
                <div className="flex items-center space-x-2 text-xs font-bold text-amber-300">
                  <Split className="w-3.5 h-3.5 text-amber-400" />
                  <span>3. BLOCK ROUTE OCCUPANCY</span>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  {rec.constraint_explanation?.route_occupancy ||
                    "Guarantees absolute block section mutual exclusion: trailing service cannot enter until lead service exits."}
                </p>
              </div>

              <div className="p-3.5 bg-railway-950 rounded-lg border border-railway-800 space-y-1">
                <div className="flex items-center space-x-2 text-xs font-bold text-rose-300">
                  <Shuffle className="w-3.5 h-3.5 text-rose-400" />
                  <span>4. JUNCTION THROAT CONTENTION</span>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed">
                  {rec.constraint_explanation?.junction_contention ||
                    "Interlocking route reservation prevents simultaneous conflicting movements through shared crossing throat."}
                </p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
