"use client";

import React from "react";
import { 
  Activity, 
  Cpu, 
  GitBranch, 
  Layers, 
  RefreshCw, 
  Train, 
  Zap, 
  Clock,
  BarChart3,
  Scale,
} from "lucide-react";
import { HealthResponse } from "@/lib/types";

interface HeaderProps {
  health: HealthResponse | null;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onRefresh: () => void;
  isLoading: boolean;
  serverTime: string;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  activeTab,
  setActiveTab,
  onRefresh,
  isLoading,
  serverTime,
}) => {
  // Automatic IST (Asia/Kolkata, UTC+05:30) real-time synchronized clock
  const [liveIstTime, setLiveIstTime] = React.useState<string>("");

  React.useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      const utc = now.getTime() + now.getTimezoneOffset() * 60000;
      const istDate = new Date(utc + 5.5 * 3600000);
      const hrs = istDate.getHours().toString().padStart(2, "0");
      const mins = istDate.getMinutes().toString().padStart(2, "0");
      const secs = istDate.getSeconds().toString().padStart(2, "0");
      setLiveIstTime(`${hrs}:${mins}:${secs} IST`);
    };

    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  const tabs = [
    { id: "overview", label: "Operations Hub", icon: Activity },
    { id: "topology", label: "Division Topology", icon: GitBranch },
    { id: "simulation", label: "Live Simulation", icon: Train },
    { id: "optimization", label: "CP-SAT Optimizer", icon: Cpu },
    { id: "what-if", label: "What-If Studio", icon: Zap },
    { id: "scenarios", label: "Scenario Comparator", icon: Scale },
    { id: "timetable", label: "Timetable Comparator", icon: Layers },
    { id: "analytics", label: "Research Analytics", icon: BarChart3 },
  ];

  return (
    <header className="border-b border-railway-800 bg-railway-900/90 backdrop-blur sticky top-0 z-50">
      {/* Main Title Bar */}
      <div className="flex items-center justify-between px-6 py-3 gap-4">
        {/* Branding */}
        <div className="flex items-center space-x-3 shrink-0">
          <div className="w-9 h-9 rounded-lg bg-cyan-950/70 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shadow-[0_0_12px_rgba(6,182,212,0.2)]">
            <Train className="w-5 h-5" />
          </div>
          <h1 className="text-base font-bold tracking-tight text-white">
            Railway Traffic Optimization &amp; Decision Support System
          </h1>
        </div>

        {/* Right: Automatic IST Clock + Manual Sync Option */}
        <div className="flex items-center space-x-4 shrink-0">
          <div className="flex items-center space-x-2 text-cyan-300 bg-railway-950 px-3 py-1 rounded border border-cyan-500/20 text-xs font-mono">
            <Clock className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
            <span className="font-semibold">{liveIstTime || health?.ist_time_str || "--:--:-- IST"}</span>
            <span className="text-[10px] text-cyan-400/70 border-l border-railway-800 pl-1.5 font-bold uppercase tracking-wider hidden sm:inline">
              Asia/Kolkata
            </span>
          </div>
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="flex items-center space-x-1 text-xs font-mono text-slate-300 hover:text-cyan-300 transition-colors disabled:opacity-50"
            title="Poll fresh data on-demand (background sync is automatic)"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-cyan-400" : ""}`} />
            <span>SYNC</span>
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="px-6 border-t border-railway-800/60">
        <nav className="flex items-center space-x-0.5 overflow-x-auto py-2" style={{ scrollbarWidth: 'none' }}>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all whitespace-nowrap ${
                  isActive
                    ? "bg-cyan-950 text-cyan-300 border border-cyan-500/40 shadow-[0_0_8px_rgba(6,182,212,0.25)]"
                    : "text-slate-400 hover:text-slate-200 hover:bg-railway-800/50"
                }`}
              >
                <Icon className={`w-3.5 h-3.5 ${isActive ? "text-cyan-400" : "text-slate-500"}`} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>
      </div>
    </header>
  );
};
