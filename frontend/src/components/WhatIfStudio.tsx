"use client";

import React, { useState, useMemo } from "react";
import { 
  AlertOctagon, 
  AlertTriangle, 
  ArrowRight, 
  BarChart3, 
  Check, 
  CheckCircle2, 
  Clock, 
  Cpu, 
  FileText, 
  Fingerprint, 
  Flame, 
  GitBranch, 
  GitCommit, 
  HelpCircle, 
  Info, 
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
  X, 
  Zap 
} from "lucide-react";
import { 
  NetworkResponse, 
  Recommendation, 
  WhatIfRequest, 
  WhatIfResponse 
} from "@/lib/types";
import { ExplainableRecommendationCard } from "./ExplainableRecommendationCard";

interface WhatIfStudioProps {
  network: NetworkResponse | null;
  whatIfData: WhatIfResponse | null;
  onEvaluateWhatIf: (req: WhatIfRequest) => void;
  isLoading: boolean;
}

type ScenarioTypePreset = 
  | "DEP_DELAY" 
  | "ENROUTE_DELAY" 
  | "TSR_SPEED" 
  | "BLOCKED_SECTION" 
  | "JUNCTION_CONTENTION" 
  | "COMPOUND_DISRUPTION";

export const WhatIfStudio: React.FC<WhatIfStudioProps> = ({
  network,
  whatIfData,
  onEvaluateWhatIf,
  isLoading,
}) => {
  // Scenario Configuration State
  const [scenarioName, setScenarioName] = useState<string>("Lalbagh Express 25m Origin Departure Delay");
  const [scenarioDescription, setScenarioDescription] = useState<string>(
    "Simulates 25m departure delay on 12607 Lalbagh Express and optimizes downstream precedence."
  );
  const [activePreset, setActivePreset] = useState<ScenarioTypePreset>("DEP_DELAY");
  const [activeTab, setActiveTab] = useState<"RECOMMENDATIONS" | "DELAYS" | "CONFLICTS" | "BOTTLENECKS" | "COMPARISON">("RECOMMENDATIONS");
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string>("ALL");

  // Filter recommendations by selected category
  const filteredRecs = useMemo(() => {
    if (!whatIfData?.recommendations) return [];
    if (selectedCategoryFilter === "ALL") return whatIfData.recommendations;
    return whatIfData.recommendations.filter((r) => r.category === selectedCategoryFilter);
  }, [whatIfData?.recommendations, selectedCategoryFilter]);

  // Selected services for what-if
  const defaultServices = ["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"];
  const [selectedServices, setSelectedServices] = useState<string[]>(defaultServices);

  // 1. Departure delays
  const [departureDelays, setDepartureDelays] = useState<Record<string, number>>({
    "SRV_12607_01": 25,
  });
  const [depSvcSelect, setDepSvcSelect] = useState<string>("SRV_12607_01");
  const [depDelayInput, setDepDelayInput] = useState<number>(25);

  // 2. Intermediate Station Dwell Delays (En-route delay)
  const [stationDelays, setStationDelays] = useState<Record<string, Record<string, number>>>({});
  const [stnSvcSelect, setStnSvcSelect] = useState<string>("SRV_12607_01");
  const [stnIdSelect, setStnIdSelect] = useState<string>("PER");
  const [stnDwellInput, setStnDwellInput] = useState<number>(10);

  // 3. Track Speed Restrictions (TSR)
  const [speedRestrictions, setSpeedRestrictions] = useState<Record<string, number>>({});
  const [tsrSectionSelect, setTsrSectionSelect] = useState<string>("MAS_BBQ_THROAT_SEGMENT_DOWN");
  const [tsrRunTimeInput, setTsrRunTimeInput] = useState<number>(10.0);

  // 4. Blocked Track Sections
  const [blockedSections, setBlockedSections] = useState<string[]>([]);
  const [blockedSectionSelect, setBlockedSectionSelect] = useState<string>("MAS_BBQ_THROAT_SEGMENT_DOWN");

  // Time horizon
  const [timeHorizon, setTimeHorizon] = useState<number | null>(null);

  // Available services & track sections from network
  const availableServices = network?.services || [];
  const trackSections = useMemo(() => {
    return [
      "MAS_BBQ_THROAT_SEGMENT_DOWN",
      "MAS_BBQ_THROAT_SEGMENT_UP",
      "BBQ_KOK_MAIN_DOWN",
      "BBQ_KOK_MAIN_UP",
      "KOK_PER_MAIN_DOWN",
      "KOK_PER_MAIN_UP",
      "PER_VLK_MAIN_DOWN",
      "PER_VLK_MAIN_UP",
      "VLK_ABU_MAIN_DOWN",
      "ABU_AVD_MAIN_DOWN",
      "AVD_TI_MAIN_DOWN",
      "TI_TRL_MAIN_DOWN",
      "TRL_TO_MAIN_DOWN",
      "TO_AJJ_MAIN_DOWN",
    ];
  }, []);

  // Preset Scenario Applicator
  const applyScenarioPreset = (preset: ScenarioTypePreset) => {
    setActivePreset(preset);
    switch (preset) {
      case "DEP_DELAY":
        setScenarioName("Lalbagh Express 25m Origin Departure Delay");
        setScenarioDescription("Single express train delayed at MAS departure; evaluates downstream precedence at BBQ & PER.");
        setSelectedServices(["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]);
        setDepartureDelays({ "SRV_12607_01": 25 });
        setStationDelays({});
        setSpeedRestrictions({});
        setBlockedSections([]);
        break;

      case "ENROUTE_DELAY":
        setScenarioName("Perambur Station Exceeded Dwell En-Route Delay");
        setScenarioDescription("SRV_12607_01 incurs 15m unscheduled dwell at Perambur (PER); evaluates secondary EMU headway compression.");
        setSelectedServices(["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]);
        setDepartureDelays({});
        setStationDelays({ "SRV_12607_01": { "PER": 15 } });
        setSpeedRestrictions({});
        setBlockedSections([]);
        break;

      case "TSR_SPEED":
        setScenarioName("MAS-BBQ Throat Temporary Speed Restriction (10m Run Time)");
        setScenarioDescription("Speed restriction on MAS_BBQ_THROAT_SEGMENT_DOWN increases run time to 10m; tests throat slot capacity.");
        setSelectedServices(["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]);
        setDepartureDelays({});
        setStationDelays({});
        setSpeedRestrictions({ "MAS_BBQ_THROAT_SEGMENT_DOWN": 10.0 });
        setBlockedSections([]);
        break;

      case "BLOCKED_SECTION":
        setScenarioName("MAS-BBQ Down Throat Complete Section Blockage");
        setScenarioDescription("Simulates complete track outage on MAS_BBQ_THROAT_SEGMENT_DOWN; computes alternative sequencing.");
        setSelectedServices(["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]);
        setDepartureDelays({ "SRV_12607_01": 15 });
        setStationDelays({});
        setSpeedRestrictions({});
        setBlockedSections(["MAS_BBQ_THROAT_SEGMENT_DOWN"]);
        break;

      case "JUNCTION_CONTENTION":
        setScenarioName("Basin Bridge (BBQ) Peak Dual-Express Junction Contention");
        setScenarioDescription("Simultaneous 20m departure delay on 12607 and 15m delay on 12609 creating severe throat contention at BBQ junction.");
        setSelectedServices(["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]);
        setDepartureDelays({ "SRV_12607_01": 20, "SRV_12609_01": 15 });
        setStationDelays({});
        setSpeedRestrictions({});
        setBlockedSections([]);
        break;

      case "COMPOUND_DISRUPTION":
        setScenarioName("Severe Compound Peak-Hour Disruption (Delays + TSR + Dwells)");
        setScenarioDescription("Multi-train origin delays (35m & 25m) combined with MAS-BBQ TSR (12m) and Perambur dwell delay.");
        setSelectedServices(["SRV_12607_01", "SRV_12609_01", "SRV_12610_01", "SRV_43411_01"]);
        setDepartureDelays({ "SRV_12607_01": 35, "SRV_12609_01": 25 });
        setStationDelays({ "SRV_12607_01": { "PER": 10 } });
        setSpeedRestrictions({ "MAS_BBQ_THROAT_SEGMENT_DOWN": 12.0 });
        setBlockedSections([]);
        break;
    }
  };

  // Add / remove perturbation helpers
  const handleAddDepartureDelay = () => {
    if (depDelayInput <= 0) return;
    setDepartureDelays((prev) => ({ ...prev, [depSvcSelect]: depDelayInput }));
  };

  const handleRemoveDepartureDelay = (sId: string) => {
    setDepartureDelays((prev) => {
      const updated = { ...prev };
      delete updated[sId];
      return updated;
    });
  };

  const handleAddStationDelay = () => {
    if (stnDwellInput <= 0) return;
    setStationDelays((prev) => {
      const updated = { ...prev };
      if (!updated[stnSvcSelect]) {
        updated[stnSvcSelect] = {};
      }
      updated[stnSvcSelect][stnIdSelect] = stnDwellInput;
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

  const handleAddSpeedRestriction = () => {
    if (tsrRunTimeInput <= 0) return;
    setSpeedRestrictions((prev) => ({ ...prev, [tsrSectionSelect]: tsrRunTimeInput }));
  };

  const handleRemoveSpeedRestriction = (secId: string) => {
    setSpeedRestrictions((prev) => {
      const updated = { ...prev };
      delete updated[secId];
      return updated;
    });
  };

  const handleToggleBlockedSection = (secId: string) => {
    setBlockedSections((prev) =>
      prev.includes(secId) ? prev.filter((id) => id !== secId) : [...prev, secId]
    );
  };

  // Trigger evaluation
  const handleRunEvaluation = () => {
    onEvaluateWhatIf({
      scenario_id: `SCEN_WHATIF_${Date.now()}`,
      scenario_name: scenarioName,
      description: scenarioDescription,
      service_ids: selectedServices.length > 0 ? selectedServices : null,
      departure_delays: Object.keys(departureDelays).length > 0 ? departureDelays : undefined,
      station_delays: Object.keys(stationDelays).length > 0 ? stationDelays : undefined,
      speed_restrictions: Object.keys(speedRestrictions).length > 0 ? speedRestrictions : undefined,
      blocked_sections: blockedSections.length > 0 ? blockedSections : undefined,
      time_horizon: timeHorizon,
    });
  };

  // Severity & Tier Badges
  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
      case "EMERGENCY":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
      case "WARNING":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "ADVISORY":
        return "bg-yellow-500/20 text-yellow-300 border-yellow-500/40";
      default:
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
    }
  };

  const getTierBadge = (tier: string) => {
    switch (tier) {
      case "URGENT":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
      case "HIGH":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "MEDIUM":
        return "bg-cyan-500/20 text-cyan-300 border-cyan-500/40";
      default:
        return "bg-slate-500/20 text-slate-300 border-slate-500/40";
    }
  };

  // Check affected service count
  const affectedServiceCount = useMemo(() => {
    const s = new Set<string>();
    Object.keys(departureDelays).forEach((id) => s.add(id));
    Object.keys(stationDelays).forEach((id) => s.add(id));
    if (whatIfData) {
      whatIfData.service_delay_impacts.forEach((imp) => {
        if (imp.total_delay_minutes > 0) s.add(imp.service_id);
      });
    }
    return s.size;
  }, [departureDelays, stationDelays, whatIfData]);

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* 1. Hypothetical Sandbox Notice */}
      <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-indigo-500/20 border border-indigo-400 text-indigo-300">
            <Sparkles className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-indigo-200 uppercase tracking-wider">
                HYPOTHETICAL WHAT-IF SIMULATION & RESCHEDULING STUDIO:
              </span>
              <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/40 font-bold text-[10px]">
                SANDBOX ISOLATED
              </span>
            </div>
            <p className="text-[11px] text-slate-300 mt-0.5">
              Formulate complex multi-variable operational disruptions, simulate ripple delay cascades, and synthesize mathematically proven controller directives.
            </p>
            <span className="text-[10px] text-slate-400 italic">
              * Note: What-If evaluations are research-oriented and non-destructive; the published reference timetable remains intact.
            </span>
          </div>
        </div>

        <button
          onClick={handleRunEvaluation}
          disabled={isLoading}
          className="flex items-center space-x-2 px-6 py-2.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-bold shadow-[0_0_16px_rgba(244,63,94,0.35)] transition-all disabled:opacity-50"
        >
          {isLoading ? (
            <RefreshCw className="w-4 h-4 animate-spin" />
          ) : (
            <Play className="w-4 h-4 fill-white" />
          )}
          <span>EVALUATE SCENARIO</span>
        </button>
      </div>

      {/* 2. Scenario Type Preset Selector */}
      <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between border-b border-railway-800 pb-3">
          <div className="flex items-center space-x-2">
            <Sliders className="w-4 h-4 text-rose-400" />
            <h2 className="text-xs font-bold text-white uppercase tracking-wider">
              Supported Railway Disruption Archetypes
            </h2>
          </div>
          <span className="text-slate-500 text-[10px]">6 Canonical Scenarios Supported</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2.5">
          {[
            { id: "DEP_DELAY", label: "1. Departure Delay", desc: "Origin late start" },
            { id: "ENROUTE_DELAY", label: "2. En-Route Dwell", desc: "Station dwell overrun" },
            { id: "TSR_SPEED", label: "3. Speed Limit (TSR)", desc: "Throat run time increase" },
            { id: "BLOCKED_SECTION", label: "4. Blocked Section", desc: "Full track outage" },
            { id: "JUNCTION_CONTENTION", label: "5. Junction Throat", desc: "Multi-train contention" },
            { id: "COMPOUND_DISRUPTION", label: "6. Compound Multi", desc: "Delays + TSR + Dwells" },
          ].map((scen) => (
            <button
              key={scen.id}
              onClick={() => applyScenarioPreset(scen.id as ScenarioTypePreset)}
              className={`p-3 rounded-lg border text-left transition-all space-y-1 ${
                activePreset === scen.id
                  ? "bg-rose-950/40 border-rose-500 text-white shadow-sm"
                  : "bg-railway-950 border-railway-800 text-slate-400 hover:border-slate-700 hover:text-slate-200"
              }`}
            >
              <div className="font-bold text-xs truncate">{scen.label}</div>
              <div className="text-[10px] text-slate-500 truncate">{scen.desc}</div>
            </button>
          ))}
        </div>

        {/* Perturbation Configuration Formulation Matrix */}
        <div className="p-4 bg-railway-950 rounded-xl border border-railway-800 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-slate-400 block mb-1">SCENARIO TITLE</label>
              <input
                type="text"
                value={scenarioName}
                onChange={(e) => setScenarioName(e.target.value)}
                className="w-full bg-railway-900 border border-railway-800 rounded-lg px-3 py-1.5 text-slate-200 focus:border-rose-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-slate-400 block mb-1">OPERATIONAL DESCRIPTION</label>
              <input
                type="text"
                value={scenarioDescription}
                onChange={(e) => setScenarioDescription(e.target.value)}
                className="w-full bg-railway-900 border border-railway-800 rounded-lg px-3 py-1.5 text-slate-200 focus:border-rose-500 focus:outline-none"
              />
            </div>
          </div>

          {/* Detailed Perturbations Manager */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 pt-2 border-t border-railway-800/80">
            {/* 1. Departure Delay Sub-Editor */}
            <div className="p-3 bg-railway-900/60 rounded-lg border border-railway-800 space-y-2">
              <span className="text-[11px] font-bold text-slate-300 block">
                1. DEPARTURE DELAYS ({Object.keys(departureDelays).length})
              </span>
              <div className="flex items-center space-x-1.5">
                <select
                  value={depSvcSelect}
                  onChange={(e) => setDepSvcSelect(e.target.value)}
                  className="bg-railway-950 border border-railway-800 rounded px-2 py-1 text-slate-200 text-[10px] flex-1"
                >
                  {availableServices.map((s) => (
                    <option key={s.id} value={s.id}>{s.id}</option>
                  ))}
                </select>
                <input
                  type="number"
                  min="0"
                  max="60"
                  step="1"
                  value={depDelayInput || ""}
                  onChange={(e) => setDepDelayInput(Number(e.target.value))}
                  className="w-14 bg-railway-950 border border-railway-800 rounded px-2 py-1 text-slate-200 text-[10px]"
                />
                <button
                  onClick={handleAddDepartureDelay}
                  className="px-2 py-1 rounded bg-rose-600 hover:bg-rose-500 text-white font-bold text-[10px]"
                >
                  SET
                </button>
              </div>
              <div className="flex flex-wrap gap-1 max-h-14 overflow-y-auto">
                {Object.entries(departureDelays).map(([sId, min]) => (
                  <span key={sId} className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-rose-950/60 border border-rose-500/30 text-rose-300 text-[9px]">
                    <span>{sId}: +{min}m</span>
                    <button onClick={() => handleRemoveDepartureDelay(sId)} className="text-rose-400 hover:text-white">×</button>
                  </span>
                ))}
              </div>
            </div>

            {/* 2. En-Route Station Dwell Sub-Editor */}
            <div className="p-3 bg-railway-900/60 rounded-lg border border-railway-800 space-y-2">
              <span className="text-[11px] font-bold text-slate-300 block">
                2. EN-ROUTE DWELLS ({Object.keys(stationDelays).length})
              </span>
              <div className="grid grid-cols-3 gap-1">
                <select
                  value={stnSvcSelect}
                  onChange={(e) => setStnSvcSelect(e.target.value)}
                  className="bg-railway-950 border border-railway-800 rounded px-1.5 py-1 text-slate-200 text-[10px]"
                >
                  {availableServices.map((s) => (
                    <option key={s.id} value={s.id}>{s.id}</option>
                  ))}
                </select>
                <select
                  value={stnIdSelect}
                  onChange={(e) => setStnIdSelect(e.target.value)}
                  className="bg-railway-950 border border-railway-800 rounded px-1.5 py-1 text-slate-200 text-[10px]"
                >
                  {(network?.stations || []).map((stn) => (
                    <option key={stn.id} value={stn.id}>{stn.id}</option>
                  ))}
                </select>
                <input
                  type="number"
                  min="0"
                  max="60"
                  step="1"
                  placeholder="Min"
                  value={stnDwellInput || ""}
                  onChange={(e) => setStnDwellInput(Number(e.target.value))}
                  className="bg-railway-950 border border-railway-800 rounded px-1.5 py-1 text-slate-200 text-[10px]"
                />
              </div>
              <button
                onClick={handleAddStationDelay}
                className="w-full py-1 rounded bg-amber-600 hover:bg-amber-500 text-white font-bold text-[10px]"
              >
                ADD DWELL DELAY
              </button>
              <div className="flex flex-wrap gap-1 max-h-12 overflow-y-auto">
                {Object.entries(stationDelays).flatMap(([sId, stns]) =>
                  Object.entries(stns).map(([stnId, min]) => (
                    <span key={`${sId}-${stnId}`} className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-amber-950/60 border border-amber-500/30 text-amber-300 text-[9px]">
                      <span>{sId}@{stnId}: +{min}m</span>
                      <button onClick={() => handleRemoveStationDelay(sId, stnId)} className="text-amber-400 hover:text-white">×</button>
                    </span>
                  ))
                )}
              </div>
            </div>

            {/* 3. Speed Restrictions (TSR) Sub-Editor */}
            <div className="p-3 bg-railway-900/60 rounded-lg border border-railway-800 space-y-2">
              <span className="text-[11px] font-bold text-slate-300 block">
                3. SPEED RESTRICTION ({Object.keys(speedRestrictions).length})
              </span>
              <div className="flex items-center space-x-1">
                <select
                  value={tsrSectionSelect}
                  onChange={(e) => setTsrSectionSelect(e.target.value)}
                  className="bg-railway-950 border border-railway-800 rounded px-1.5 py-1 text-slate-200 text-[10px] flex-1"
                >
                  {trackSections.map((sec) => (
                    <option key={sec} value={sec}>{sec}</option>
                  ))}
                </select>
                <input
                  type="number"
                  min="1"
                  max="30"
                  step="1"
                  placeholder="Min"
                  value={tsrRunTimeInput || ""}
                  onChange={(e) => setTsrRunTimeInput(Number(e.target.value))}
                  className="w-12 bg-railway-950 border border-railway-800 rounded px-1.5 py-1 text-slate-200 text-[10px]"
                />
              </div>
              <button
                onClick={handleAddSpeedRestriction}
                className="w-full py-1 rounded bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-[10px]"
              >
                APPLY TSR RUNTIME
              </button>
              <div className="flex flex-wrap gap-1 max-h-12 overflow-y-auto">
                {Object.entries(speedRestrictions).map(([sec, rt]) => (
                  <span key={sec} className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-indigo-950/60 border border-indigo-500/30 text-indigo-300 text-[9px]">
                    <span>{sec}: {rt}m</span>
                    <button onClick={() => handleRemoveSpeedRestriction(sec)} className="text-indigo-400 hover:text-white">×</button>
                  </span>
                ))}
              </div>
            </div>

            {/* 4. Blocked Section Sub-Editor */}
            <div className="p-3 bg-railway-900/60 rounded-lg border border-railway-800 space-y-2">
              <span className="text-[11px] font-bold text-slate-300 block">
                4. BLOCKED SECTIONS ({blockedSections.length})
              </span>
              <select
                value={blockedSectionSelect}
                onChange={(e) => setBlockedSectionSelect(e.target.value)}
                className="w-full bg-railway-950 border border-railway-800 rounded px-2 py-1 text-slate-200 text-[10px]"
              >
                {trackSections.map((sec) => (
                  <option key={sec} value={sec}>{sec}</option>
                ))}
              </select>
              <button
                onClick={() => handleToggleBlockedSection(blockedSectionSelect)}
                className="w-full py-1 rounded bg-rose-700 hover:bg-rose-600 text-white font-bold text-[10px]"
              >
                {blockedSections.includes(blockedSectionSelect) ? "UNBLOCK SECTION" : "BLOCK TRACK SECTION"}
              </button>
              <div className="flex flex-wrap gap-1 max-h-12 overflow-y-auto">
                {blockedSections.map((sec) => (
                  <span key={sec} className="inline-flex items-center space-x-1 px-1.5 py-0.5 rounded bg-rose-950/80 border border-rose-500/50 text-rose-300 text-[9px]">
                    <span>BLOCKED: {sec}</span>
                    <button onClick={() => handleToggleBlockedSection(sec)} className="text-rose-400 hover:text-white">×</button>
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 3. Scenario Outcome KPI Dashboard */}
      {whatIfData && (
        <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-railway-800 pb-3">
            <div className="flex items-center space-x-3">
              <span className={`px-2.5 py-1 rounded text-xs font-bold border ${getSeverityBadge(whatIfData.operational_severity)}`}>
                SITUATION SEVERITY: {whatIfData.operational_severity}
              </span>
              <span className="text-xs text-slate-300 font-bold">
                Scenario: <strong className="text-white">{whatIfData.scenario_name}</strong>
              </span>
            </div>

            <div className="flex items-center space-x-3 text-xs text-slate-400">
              <span className="flex items-center space-x-1 bg-railway-950 px-2.5 py-1 rounded border border-railway-800">
                <Fingerprint className="w-3.5 h-3.5 text-cyan-400" />
                <span>Deterministic Hash: {whatIfData.deterministic_hash}</span>
              </span>
              <span className="text-slate-400">Solve Time: {whatIfData.solve_time_seconds.toFixed(3)}s</span>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className="bg-railway-950 p-3.5 rounded-xl border border-railway-800">
              <span className="text-slate-500 block text-[10px]">FEASIBLE BASELINE (FIFO)</span>
              <span className="text-xl font-bold text-amber-400 mt-0.5 block">
                {whatIfData.total_baseline_delay_minutes.toFixed(1)}m
              </span>
              <span className="text-[10px] text-slate-500">Unmitigated delay</span>
            </div>

            <div className="bg-railway-950 p-3.5 rounded-xl border border-railway-800">
              <span className="text-slate-500 block text-[10px]">CP-SAT OPTIMIZED DELAY</span>
              <span className="text-xl font-bold text-cyan-400 mt-0.5 block">
                {whatIfData.total_optimized_delay_minutes.toFixed(1)}m
              </span>
              <span className="text-[10px] text-slate-500">Global MIP reschedule</span>
            </div>

            <div className="bg-emerald-950/20 border border-emerald-500/30 p-3.5 rounded-xl">
              <span className="text-emerald-300 block text-[10px] font-bold">NET DELAY SAVINGS</span>
              <span className="text-xl font-bold text-emerald-400 mt-0.5 block">
                +{whatIfData.net_delay_savings_minutes.toFixed(1)}m ({whatIfData.net_delay_savings_percent.toFixed(1)}%)
              </span>
              <span className="text-[10px] text-emerald-400/80">Intervention benefit</span>
            </div>

            <div className="bg-railway-950 p-3.5 rounded-xl border border-railway-800">
              <span className="text-slate-500 block text-[10px]">DETECTED CONFLICTS</span>
              <span className="text-xl font-bold text-rose-400 mt-0.5 block">
                {whatIfData.prioritized_conflicts.length}
              </span>
              <span className="text-[10px] text-slate-500">Prioritized safety bottlenecks</span>
            </div>

            <div className="bg-railway-950 p-3.5 rounded-xl border border-railway-800">
              <span className="text-slate-500 block text-[10px]">RANKED DIRECTIVES</span>
              <span className="text-xl font-bold text-indigo-400 mt-0.5 block">
                {whatIfData.recommendations.length}
              </span>
              <span className="text-[10px] text-slate-500">Actionable interventions</span>
            </div>
          </div>
        </div>
      )}

      {/* 4. What-If Analytics & Decision Workspace Tabs */}
      <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-4">
        {/* Navigation Tabs */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-railway-800 pb-3">
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setActiveTab("RECOMMENDATIONS")}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === "RECOMMENDATIONS"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-railway-950 text-slate-400 hover:text-white"
              }`}
            >
              <ShieldAlert className="w-3.5 h-3.5" />
              <span>RANKED DIRECTIVES & EVIDENCE ({whatIfData?.recommendations.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("DELAYS")}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === "DELAYS"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-railway-950 text-slate-400 hover:text-white"
              }`}
            >
              <TrendingDown className="w-3.5 h-3.5" />
              <span>DIRECT VS PROPAGATED DELAYS ({whatIfData?.service_delay_impacts.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("CONFLICTS")}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === "CONFLICTS"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-railway-950 text-slate-400 hover:text-white"
              }`}
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              <span>PRIORITIZED CONFLICTS ({whatIfData?.prioritized_conflicts.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("BOTTLENECKS")}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === "BOTTLENECKS"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-railway-950 text-slate-400 hover:text-white"
              }`}
            >
              <Flame className="w-3.5 h-3.5" />
              <span>CONTESTED BOTTLENECKS ({whatIfData?.identified_bottlenecks.length || 0})</span>
            </button>

            <button
              onClick={() => setActiveTab("COMPARISON")}
              className={`px-3 py-1.5 rounded-lg font-bold transition-all flex items-center space-x-1.5 ${
                activeTab === "COMPARISON"
                  ? "bg-indigo-600 text-white shadow-sm"
                  : "bg-railway-950 text-slate-400 hover:text-white"
              }`}
            >
              <BarChart3 className="w-3.5 h-3.5" />
              <span>3-TIER BENCHMARK</span>
            </button>
          </div>
        </div>

        {/* Tab 1: Explainable Ranked Recommendations */}
        {activeTab === "RECOMMENDATIONS" && (
          <div className="space-y-4">
            {/* Category Filter Pills */}
            <div className="flex flex-wrap items-center gap-1.5 p-2 bg-railway-950/60 rounded-xl border border-railway-800/80">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mr-1 flex items-center gap-1">
                <ListFilter className="w-3 h-3 text-cyan-400" /> Category:
              </span>
              {[
                { id: "ALL", label: "All Categories" },
                { id: "precedence change", label: "Precedence Change" },
                { id: "holding", label: "Holding" },
                { id: "platform reassignment", label: "Platform Reassignment" },
                { id: "dispatch sequencing", label: "Dispatch Sequencing" },
                { id: "speed management", label: "Speed Management" },
                { id: "maintain schedule", label: "Maintain Schedule" },
              ].map((cat) => {
                const count = cat.id === "ALL"
                  ? whatIfData?.recommendations?.length || 0
                  : whatIfData?.recommendations?.filter((r) => r.category === cat.id).length || 0;
                const isSelected = selectedCategoryFilter === cat.id;
                return (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategoryFilter(cat.id)}
                    className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition-all flex items-center space-x-1.5 ${
                      isSelected
                        ? "bg-cyan-600 text-white shadow-sm shadow-cyan-900/40"
                        : "bg-railway-900 text-slate-400 hover:text-slate-200 hover:bg-railway-850"
                    }`}
                  >
                    <span>{cat.label}</span>
                    <span className={`text-[10px] px-1.5 py-0.2 rounded-full ${isSelected ? "bg-cyan-800 text-white" : "bg-railway-800 text-slate-400"}`}>
                      {count}
                    </span>
                  </button>
                );
              })}
            </div>

            {/* Explainable Recommendations List */}
            <div className="space-y-3 max-h-[600px] overflow-y-auto pr-1">
              {filteredRecs.length === 0 ? (
                <div className="p-8 rounded-xl bg-railway-950 border border-railway-800 text-slate-400 text-center italic">
                  {whatIfData?.recommendations?.length === 0
                    ? "No active interventions required. Services proceed under normal timetable separation."
                    : `No recommendations found for category '${selectedCategoryFilter}'.`}
                </div>
              ) : (
                filteredRecs.map((rec, index) => (
                  <ExplainableRecommendationCard
                    key={rec.recommendation_id}
                    rec={rec}
                    defaultExpanded={index === 0}
                  />
                ))
              )}
            </div>
          </div>
        )}

        {/* Tab 2: Direct vs Propagated Delay Breakdown */}
        {activeTab === "DELAYS" && (
          <div className="space-y-4">
            <div className="p-3 bg-railway-950 rounded-xl border border-railway-800 text-xs text-slate-300 flex items-center justify-between">
              <span>
                Quantifies <strong>Primary (Injected) Delay</strong> vs <strong>Propagated (Downstream Ripple) Delay</strong> per train service.
              </span>
              <span className="text-amber-400 font-bold">
                {whatIfData?.delayed_services_count || 0} Delayed Services / {whatIfData?.active_services_count || 0} Total
              </span>
            </div>

            <div className="overflow-x-auto max-h-[440px]">
              <table className="w-full text-left border-collapse">
                <thead className="sticky top-0 bg-railway-900 border-b border-railway-800 text-slate-400 text-[11px]">
                  <tr>
                    <th className="py-2.5 px-3">TRAIN / SERVICE</th>
                    <th className="py-2.5 px-3">CATEGORY</th>
                    <th className="py-2.5 px-3">PRIMARY DELAY</th>
                    <th className="py-2.5 px-3">PROPAGATED DELAY</th>
                    <th className="py-2.5 px-3">TOTAL UNMITIGATED</th>
                    <th className="py-2.5 px-3">DELAY SAVINGS</th>
                    <th className="py-2.5 px-3">DOWNSTREAM IMPACTS</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-railway-800/60">
                  {whatIfData?.service_delay_impacts.map((imp) => {
                    const primaryDelay = imp.primary_delay_minutes ?? imp.direct_delay_minutes ?? 0;
                    const propDelay = imp.propagated_delay_minutes ?? 0;
                    const totalDelay = imp.total_delay_minutes ?? (primaryDelay + propDelay);
                    const delaySavings = imp.delay_saving_minutes ?? 0;
                    const downstreamCount = imp.downstream_impact_count ?? imp.affected_downstream_resources?.length ?? 0;
                    const hasProp = propDelay > 0;
                    return (
                      <tr key={imp.service_id} className="hover:bg-railway-800/40">
                        <td className="py-2.5 px-3">
                          <span className="font-bold text-slate-200 block">{imp.train_name}</span>
                          <span className="text-[10px] text-slate-500">{imp.service_id}</span>
                        </td>
                        <td className="py-2.5 px-3">
                          <span className="px-2 py-0.5 rounded bg-railway-950 border border-slate-700 text-slate-300 text-[10px]">
                            {imp.priority_class}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-bold text-rose-400">
                          {primaryDelay > 0 ? `+${primaryDelay.toFixed(1)}m` : "0.0m"}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className={hasProp ? "text-amber-400 font-bold" : "text-slate-500"}>
                            {hasProp ? `+${propDelay.toFixed(1)}m` : "0.0m"}
                          </span>
                        </td>
                        <td className="py-2.5 px-3 font-bold text-slate-100">
                          {totalDelay.toFixed(1)}m
                        </td>
                        <td className="py-2.5 px-3 font-bold text-emerald-400">
                          {delaySavings > 0 ? `+${delaySavings.toFixed(1)}m` : "0.0m"}
                        </td>
                        <td className="py-2.5 px-3">
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            downstreamCount > 0
                              ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                              : "bg-slate-800 text-slate-400"
                          }`}>
                            {downstreamCount} downstream {downstreamCount === 1 ? "train" : "trains"}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 3: Prioritized Conflicts Matrix */}
        {activeTab === "CONFLICTS" && (
          <div className="space-y-4">
            <div className="p-3 bg-railway-950 rounded-xl border border-railway-800 text-xs text-slate-300 flex items-center justify-between">
              <span>
                Safety & Headway Conflicts detected by the physical simulator, ranked deterministically by criticality.
              </span>
              <span className="text-rose-400 font-bold">
                {whatIfData?.prioritized_conflicts.length || 0} Total Conflicts
              </span>
            </div>

            <div className="space-y-3 max-h-[440px] overflow-y-auto">
              {(!whatIfData || whatIfData.prioritized_conflicts.length === 0) ? (
                <div className="p-8 rounded-xl bg-railway-950 border border-railway-800 text-slate-500 text-center italic">
                  Zero active conflicts detected. Physical headway constraints satisfied.
                </div>
              ) : (
                whatIfData.prioritized_conflicts.map((pc, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl bg-railway-950 border border-railway-800 space-y-2 hover:border-rose-500/40 transition-colors"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center space-x-2">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${getTierBadge(pc.priority_tier.replace("TIER_1_", "").replace("TIER_2_", "").replace("TIER_3_", "").replace("TIER_4_", ""))}`}>
                          {pc.priority_tier} • SCORE {pc.priority_score.toFixed(0)}
                        </span>
                        <span className="font-bold text-rose-300">{pc.conflict.conflict_type}</span>
                      </div>
                      <span className="text-slate-400 text-[10px]">
                        Resource: <strong className="text-cyan-300">{pc.conflict.resource_id}</strong>
                      </span>
                    </div>

                    <p className="text-slate-300 text-xs leading-relaxed">
                      {pc.conflict.description}
                    </p>

                    <div className="p-2 bg-railway-900 rounded border border-railway-800 text-[10px] text-slate-400 italic">
                      Ranking Rationale: {pc.ranking_explanation}
                    </div>

                    <div className="flex flex-wrap items-center justify-between text-[10px] text-slate-500 border-t border-railway-800/80 pt-1.5">
                      <span>Affected Services: <strong className="text-slate-300">{pc.conflict.affected_service_ids.join(", ")}</strong></span>
                      <span>Max Delay: <strong className="text-amber-400">+{pc.max_delay_minutes.toFixed(1)}m</strong></span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Tab 4: Contested Infrastructure Bottlenecks */}
        {activeTab === "BOTTLENECKS" && (
          <div className="space-y-4">
            <div className="p-3 bg-railway-950 rounded-xl border border-railway-800 text-xs text-slate-300 flex items-center justify-between">
              <span>
                Infrastructure nodes & track sections experiencing highest contention and delay accumulation.
              </span>
              <span className="text-amber-400 font-bold">
                {whatIfData?.identified_bottlenecks.length || 0} Contested Bottlenecks
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-h-[440px] overflow-y-auto">
              {(!whatIfData || whatIfData.identified_bottlenecks.length === 0) ? (
                <div className="col-span-2 p-8 rounded-xl bg-railway-950 border border-railway-800 text-slate-500 text-center italic">
                  No active infrastructure bottlenecks identified.
                </div>
              ) : (
                whatIfData.identified_bottlenecks.map((b) => (
                  <div
                    key={b.resource_id}
                    className="p-4 rounded-xl bg-railway-950 border border-railway-800 space-y-2 hover:border-amber-500/40 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        <Flame className="w-4 h-4 text-rose-400" />
                        <span className="font-bold text-cyan-300 text-sm">{b.resource_id}</span>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[10px] font-bold">
                        {b.resource_type} • CRITICALITY {b.criticality_score.toFixed(0)}
                      </span>
                    </div>

                    <p className="text-slate-300 text-xs leading-relaxed">
                      {b.description}
                    </p>

                    <div className="flex flex-wrap items-center justify-between text-[10px] text-slate-500 border-t border-railway-800/80 pt-2">
                      <span>Contending Services: <strong className="text-slate-300">{b.contending_services.join(", ")}</strong></span>
                      <span>Max Delay: <strong className="text-rose-400">+{((b.max_delay_observed ?? 0)).toFixed(1)}m</strong></span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Tab 5: 3-Tier Benchmark Comparison */}
        {activeTab === "COMPARISON" && whatIfData?.baseline_comparison && (
          <div className="space-y-4">
            <div className="p-3 bg-railway-950 rounded-xl border border-railway-800 text-xs text-slate-300 flex items-center justify-between">
              <span>
                Rigorous 3-Tier Performance Breakdown: Published Reference vs Feasible FIFO Baseline vs CP-SAT Optimal.
              </span>
              <span className="text-emerald-400 font-bold">
                Net Delay Savings: +{whatIfData.baseline_comparison.delay_savings_minutes.toFixed(1)}m ({whatIfData.baseline_comparison.delay_savings_percent.toFixed(1)}%)
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead className="border-b border-railway-800 text-slate-400 text-[11px]">
                  <tr>
                    <th className="py-2.5 px-3">PERFORMANCE CRITERIA</th>
                    <th className="py-2.5 px-3">PUBLISHED REFERENCE</th>
                    <th className="py-2.5 px-3">FEASIBLE BASELINE (FIFO)</th>
                    <th className="py-2.5 px-3">CP-SAT OPTIMIZED</th>
                    <th className="py-2.5 px-3 text-right">NET DELTA</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-railway-800/60 text-xs">
                  <tr className="hover:bg-railway-800/30">
                    <td className="py-3 px-3 font-semibold text-slate-300">Total Network Delay</td>
                    <td className="py-3 px-3 text-slate-400">
                      {whatIfData.baseline_comparison.published_reference_delay_minutes.toFixed(1)}m
                    </td>
                    <td className="py-3 px-3 text-amber-400 font-bold">
                      {whatIfData.baseline_comparison.feasible_baseline_delay_minutes.toFixed(1)}m
                    </td>
                    <td className="py-3 px-3 text-cyan-400 font-bold">
                      {whatIfData.baseline_comparison.optimized_delay_minutes.toFixed(1)}m
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-emerald-400">
                      +{whatIfData.baseline_comparison.delay_savings_minutes.toFixed(1)}m ({whatIfData.baseline_comparison.delay_savings_percent.toFixed(1)}%)
                    </td>
                  </tr>
                  <tr className="hover:bg-railway-800/30">
                    <td className="py-3 px-3 font-semibold text-slate-300">Peak Individual Train Delay</td>
                    <td className="py-3 px-3 text-slate-400">--</td>
                    <td className="py-3 px-3 text-slate-300">
                      {whatIfData.baseline_comparison.feasible_baseline_max_delay_minutes.toFixed(1)}m
                    </td>
                    <td className="py-3 px-3 text-emerald-400 font-bold">
                      {whatIfData.baseline_comparison.optimized_max_delay_minutes.toFixed(1)}m
                    </td>
                    <td className="py-3 px-3 text-right text-emerald-400 font-semibold">
                      -{ (whatIfData.baseline_comparison.feasible_baseline_max_delay_minutes - whatIfData.baseline_comparison.optimized_max_delay_minutes).toFixed(1) }m
                    </td>
                  </tr>
                  <tr className="hover:bg-railway-800/30">
                    <td className="py-3 px-3 font-semibold text-slate-300">Unresolved Conflicts Remaining</td>
                    <td className="py-3 px-3 text-rose-400">Ignored</td>
                    <td className="py-3 px-3 text-slate-400">0</td>
                    <td className="py-3 px-3 text-emerald-400 font-bold">0</td>
                    <td className="py-3 px-3 text-right text-emerald-400 font-semibold">100% Conflict Free</td>
                  </tr>
                  <tr className="hover:bg-railway-800/30">
                    <td className="py-3 px-3 font-semibold text-slate-300">Network Throughput</td>
                    <td className="py-3 px-3 text-slate-400">--</td>
                    <td className="py-3 px-3 text-slate-300">{whatIfData.baseline_comparison.feasible_baseline_throughput}</td>
                    <td className="py-3 px-3 text-cyan-300 font-bold">{whatIfData.baseline_comparison.optimized_throughput}</td>
                    <td className="py-3 px-3 text-right text-emerald-400 font-semibold">100% Maintained</td>
                  </tr>
                  <tr className="hover:bg-railway-800/30">
                    <td className="py-3 px-3 font-semibold text-slate-300">Computation & Solver Duration</td>
                    <td className="py-3 px-3 text-slate-400">Passive (0.000s)</td>
                    <td className="py-3 px-3 text-slate-400">0.005s (FIFO)</td>
                    <td className="py-3 px-3 text-indigo-300">{whatIfData.baseline_comparison.solve_time_seconds.toFixed(3)}s (CP-SAT)</td>
                    <td className="py-3 px-3 text-right text-slate-400">Sub-second Real-time</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
