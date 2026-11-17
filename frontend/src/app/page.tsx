"use client";

import React, { useEffect, useState } from "react";
import { Header } from "@/components/Header";
import { DashboardOverview } from "@/components/DashboardOverview";
import { NetworkTopologyView } from "@/components/NetworkTopologyView";
import { SimulationMonitor } from "@/components/SimulationMonitor";
import { OptimizationPanel } from "@/components/OptimizationPanel";
import { WhatIfStudio } from "@/components/WhatIfStudio";
import { ScenarioComparisonView } from "@/components/ScenarioComparisonView";
import { TimetableComparisonView } from "@/components/TimetableComparisonView";
import { ResearchAnalyticsView } from "@/components/ResearchAnalyticsView";
import { RailwayApi } from "@/lib/api";
import { 
  AnalyticsResponse,
  HealthResponse, 
  NetworkResponse, 
  OptimizeRequest, 
  OptimizeResponse, 
  SimulationControlRequest,
  SimulationStateResponse,
  SimulateRequest, 
  SimulateResponse, 
  WhatIfRequest, 
  WhatIfResponse 
} from "@/lib/types";
import { AlertCircle } from "lucide-react";

export default function ControllerDashboard() {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [network, setNetwork] = useState<NetworkResponse | null>(null);
  const [simulationData, setSimulationData] = useState<SimulateResponse | null>(null);
  const [authoritativeState, setAuthoritativeState] = useState<SimulationStateResponse | null>(null);
  const [optimizationData, setOptimizationData] = useState<OptimizeResponse | null>(null);
  const [whatIfData, setWhatIfData] = useState<WhatIfResponse | null>(null);
  const [analyticsData, setAnalyticsData] = useState<AnalyticsResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [serverTime, setServerTime] = useState<string>("");

  // Initial Load from real backend APIs with authoritative simulation state persistence
  const loadInitialData = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const [hRes, netRes, simStateRes] = await Promise.all([
        RailwayApi.getHealth(),
        RailwayApi.getNetwork(),
        RailwayApi.getSimulationState().catch(() => null),
      ]);
      setHealth(hRes);
      setNetwork(netRes);
      setServerTime(hRes.ist_time_str || hRes.timestamp_str);

      if (simStateRes) {
        setAuthoritativeState(simStateRes);
        setSimulationData(simStateRes.snapshot);
      }

      // Run default simulation and what-if assessment
      const [simRes, whatIfRes, optRes] = await Promise.all([
        simStateRes ? Promise.resolve(simStateRes.snapshot) : RailwayApi.simulate(),
        RailwayApi.evaluateWhatIf({
          scenario_id: "SCEN_LIVE_BASE",
          scenario_name: "Live Operational Corridor Baseline",
          description: "Active timetable monitoring across West Mainline.",
        }),
        RailwayApi.optimize(),
      ]);

      if (!simStateRes) {
        setSimulationData(simRes);
      }
      setWhatIfData(whatIfRes);
      setOptimizationData(optRes);

      // Asynchronously pre-fetch research analytics without blocking
      RailwayApi.getAnalytics()
        .then((aRes) => setAnalyticsData(aRes))
        .catch((aErr) => console.warn("Background analytics prefetch deferred:", aErr));
    } catch (err: any) {
      console.error("Failed to load railway operations data:", err);
      setErrorMessage(err.message || "Failed to communicate with Railway API backend.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadInitialData();
  }, []);

  // Automatic background synchronization (no repeated SYNC clicks required)
  useEffect(() => {
    const syncInterval = setInterval(async () => {
      try {
        const [hRes, simState] = await Promise.all([
          RailwayApi.getHealth(),
          RailwayApi.getSimulationState(),
        ]);
        setHealth(hRes);
        setServerTime(hRes.ist_time_str || hRes.timestamp_str);
        if (simState) {
          setAuthoritativeState(simState);
          setSimulationData(simState.snapshot);
        }
      } catch {
        // silent fail on transient network hiccups
      }
    }, 8000);

    return () => clearInterval(syncInterval);
  }, []);

  // Handlers for specific modules
  const handleRunSimulation = async (req: SimulateRequest) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await RailwayApi.simulate(req);
      setSimulationData(res);
      setServerTime(res.simulation_time_str);

      // Immediate What-If decision support propagation when delays exist
      if (req.departure_delays && Object.keys(req.departure_delays).length > 0) {
        RailwayApi.evaluateWhatIf({
          scenario_id: "SCEN_SIM_PROPAGATION",
          scenario_name: "Active Simulation Disruption Assessment",
          description: "Real-time decision support for active simulation disruptions.",
          departure_delays: req.departure_delays,
          service_ids: req.service_ids || undefined,
        })
          .then((wiRes) => setWhatIfData(wiRes))
          .catch((wiErr) => console.warn("Background What-If update deferred:", wiErr));
      }
    } catch (err: any) {
      setErrorMessage(err.message || "Simulation execution failed.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateControl = async (req: SimulationControlRequest) => {
    try {
      const stateRes = await RailwayApi.controlSimulation(req);
      setAuthoritativeState(stateRes);
      setSimulationData(stateRes.snapshot);

      // Immediate What-If decision support propagation when delays exist
      if (req.departure_delays && Object.keys(req.departure_delays).length > 0) {
        RailwayApi.evaluateWhatIf({
          scenario_id: "SCEN_SIM_PROPAGATION",
          scenario_name: "Active Simulation Disruption Assessment",
          description: "Real-time decision support for active simulation disruptions.",
          departure_delays: req.departure_delays,
          service_ids: req.service_ids || undefined,
        })
          .then((wiRes) => setWhatIfData(wiRes))
          .catch((wiErr) => console.warn("Background What-If update deferred:", wiErr));
      }
    } catch (err) {
      console.warn("Background control update deferred:", err);
    }
  };

  const handleRunOptimization = async (req: OptimizeRequest) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await RailwayApi.optimize(req);
      setOptimizationData(res);
    } catch (err: any) {
      setErrorMessage(err.message || "CP-SAT optimization solver failed.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleEvaluateWhatIf = async (req: WhatIfRequest) => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await RailwayApi.evaluateWhatIf(req);
      setWhatIfData(res);
      setServerTime(res.simulation_timestamp_str);
    } catch (err: any) {
      setErrorMessage(err.message || "What-If evaluation failed.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefreshAnalytics = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const res = await RailwayApi.getAnalytics(true);
      setAnalyticsData(res);
    } catch (err: any) {
      setErrorMessage(err.message || "Failed to re-run research analytics suite.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleTriggerScenario = async (scenarioType: "SINGLE" | "MULTI" | "TSR" | "COMPOUND") => {
    let req: WhatIfRequest = {};
    switch (scenarioType) {
      case "SINGLE":
        req = {
          scenario_id: "SCEN_SINGLE_DELAY",
          scenario_name: "Lalbagh Express 25m Origin Delay",
          departure_delays: { "SRV_12607_01": 25.0 },
        };
        break;
      case "MULTI":
        req = {
          scenario_id: "SCEN_MULTI_DELAY",
          scenario_name: "Simultaneous Dual Express Departure Delays",
          departure_delays: { "SRV_12607_01": 25.0, "SRV_12609_01": 20.0 },
        };
        break;
      case "TSR":
        req = {
          scenario_id: "SCEN_TSR_THROAT",
          scenario_name: "MAS-BBQ Throat Temporary Speed Restriction",
          speed_restrictions: { "MAS_BBQ_THROAT_SEGMENT_DOWN": 10.0 },
        };
        break;
      case "COMPOUND":
        req = {
          scenario_id: "SCEN_SEVERE_COMPOUND",
          scenario_name: "Severe Compound Peak-Hour Disruption",
          departure_delays: { "SRV_12607_01": 35.0, "SRV_12609_01": 25.0 },
          speed_restrictions: { "MAS_BBQ_THROAT_SEGMENT_DOWN": 12.0 },
        };
        break;
    }

    await handleEvaluateWhatIf(req);
    setActiveTab("what-if");
  };

  return (
    /* Root: min-h-screen so the page is at least full height, but NOT overflow:hidden — 
       that was blocking scroll on every page. */
    <div className="min-h-screen bg-railway-950 flex flex-col font-mono text-slate-100">
      {/* Sticky top header */}
      <Header
        health={health}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onRefresh={loadInitialData}
        isLoading={isLoading}
        serverTime={serverTime}
      />

      {/* ── Topology page: fixed-height, no scroll (pan/zoom inside SVG) ── */}
      {activeTab === "topology" && (
        <div style={{ height: "calc(100dvh - 96px)", overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {errorMessage && (
            <div className="mx-4 mt-3 p-3 rounded-xl bg-rose-950/40 border border-rose-500/50 text-rose-300 text-xs flex items-center gap-3">
              <AlertCircle className="w-4 h-4 flex-shrink-0 text-rose-400" />
              <span className="flex-1">{errorMessage}</span>
              <button onClick={loadInitialData} className="px-2 py-0.5 rounded bg-rose-900/60 hover:bg-rose-800 text-rose-200 border border-rose-500/40 text-xs font-bold">RETRY</button>
            </div>
          )}
          <NetworkTopologyView
            network={network}
            trainPositions={simulationData?.train_positions || []}
            detectedConflicts={simulationData?.detected_conflicts || []}
            activeOccupancies={simulationData?.active_occupancies || []}
            simulationTime={simulationData?.simulation_time_str}
          />
        </div>
      )}

      {/* ── All other pages: scrollable main content ── */}
      {activeTab !== "topology" && (
        <main className="flex-1 overflow-y-auto">
          <div className="p-6 max-w-7xl mx-auto space-y-6 pb-10">
            {/* Error Alert Bar */}
            {errorMessage && (
              <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/50 text-rose-300 text-xs flex items-center space-x-3">
                <AlertCircle className="w-5 h-5 flex-shrink-0 text-rose-400" />
                <div className="flex-1">
                  <strong className="block font-bold">API Connection / Evaluation Notice:</strong>
                  <span>{errorMessage}</span>
                </div>
                <button
                  onClick={loadInitialData}
                  className="px-3 py-1 rounded bg-rose-900/60 hover:bg-rose-800 text-rose-200 border border-rose-500/40 font-bold"
                >
                  RETRY
                </button>
              </div>
            )}

            {activeTab === "overview" && (
              <DashboardOverview
                network={network}
                simulationData={simulationData}
                whatIfData={whatIfData}
                onNavigateTab={setActiveTab}
                onTriggerScenario={handleTriggerScenario}
              />
            )}

            {activeTab === "simulation" && (
              <SimulationMonitor
                network={network}
                simulationData={simulationData}
                onRunSimulation={handleRunSimulation}
                isLoading={isLoading}
                authoritativeState={authoritativeState}
                onUpdateControl={handleUpdateControl}
              />
            )}

            {activeTab === "optimization" && (
              <OptimizationPanel
                network={network}
                optimizationData={optimizationData}
                simulationData={simulationData}
                onRunOptimization={handleRunOptimization}
                isLoading={isLoading}
              />
            )}

            {activeTab === "what-if" && (
              <WhatIfStudio
                network={network}
                whatIfData={whatIfData}
                onEvaluateWhatIf={handleEvaluateWhatIf}
                isLoading={isLoading}
              />
            )}

            {activeTab === "scenarios" && (
              <ScenarioComparisonView
                whatIfData={whatIfData}
              />
            )}

            {activeTab === "timetable" && (
              <TimetableComparisonView
                whatIfData={whatIfData}
                optimizationData={optimizationData}
                network={network}
              />
            )}

            {activeTab === "analytics" && (
              <ResearchAnalyticsView
                analyticsData={analyticsData}
                isLoading={isLoading}
                onRefresh={handleRefreshAnalytics}
                corridorPerformance={
                  whatIfData?.corridor_performance ||
                  whatIfData?.baseline_comparison?.corridor_performance ||
                  optimizationData?.corridor_performance
                }
                whatIfData={whatIfData}
                optimizationData={optimizationData}
              />
            )}
          </div>
        </main>
      )}

      {/* Footer — only shown on non-topology pages */}
      {activeTab !== "topology" && (
        <footer className="border-t border-railway-800 bg-railway-900/60 py-3 px-6 text-[11px] font-mono text-slate-500 flex flex-wrap justify-between items-center">
          <span>Southern Railway Chennai Division • Advanced Traffic Optimization Cockpit</span>
          <span>Connected to FastAPI Operational Engine v1.0.0 • Pure Stateless Architecture</span>
        </footer>
      )}
    </div>
  );
}
