"use client";

import React, { useEffect, useRef, useState } from "react";
import { 
  Activity,
  AlertTriangle, 
  BarChart3,
  CheckCircle2, 
  ChevronLeft, 
  ChevronRight, 
  Clock, 
  Compass, 
  Filter,
  Layers, 
  MapPin,
  Pause, 
  Play, 
  Plus,
  RefreshCw, 
  RotateCcw, 
  Sliders, 
  Train, 
  Trash2,
  X,
  Zap 
} from "lucide-react";
import { 
  NetworkResponse, 
  SimulateRequest, 
  SimulateResponse,
  SimulationControlRequest,
  SimulationStateResponse,
  TrackSectionOccupancyRecord 
} from "@/lib/types";

interface SimulationMonitorProps {
  network: NetworkResponse | null;
  simulationData: SimulateResponse | null;
  onRunSimulation: (req: SimulateRequest) => void;
  isLoading: boolean;
  authoritativeState?: SimulationStateResponse | null;
  onUpdateControl?: (req: SimulationControlRequest) => void;
}

export const SimulationMonitor: React.FC<SimulationMonitorProps> = ({
  network,
  simulationData,
  onRunSimulation,
  isLoading,
  authoritativeState,
  onUpdateControl,
}) => {
  // Simulation Window Presets (Including Standard 6-Hour Operational Work Windows)
  const WINDOW_PRESETS = [
    { id: "SHIFT_1", label: "Shift 1: Morning Operations (06:00 – 12:00) [6 Hours]", start: 360, end: 720 },
    { id: "SHIFT_2", label: "Shift 2: Afternoon Operations (12:00 – 18:00) [6 Hours]", start: 720, end: 1080 },
    { id: "SHIFT_3", label: "Shift 3: Evening Operations (18:00 – 24:00) [6 Hours]", start: 1080, end: 1440 },
    { id: "SHIFT_4", label: "Shift 4: Night Operations (00:00 – 06:00) [6 Hours]", start: 0, end: 360 },
    { id: "FULL_DAY", label: "Full Operational Day (05:00 – 23:00)", start: 300, end: 1380 },
  ];

  const [activeWindowPreset, setActiveWindowPreset] = useState<string>("SHIFT_1");
  const [startMinute, setStartMinute] = useState<number>(360);
  const [endMinute, setEndMinute] = useState<number>(720);
  const [currentMinute, setCurrentMinute] = useState<number>(360);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [playbackSpeed, setPlaybackSpeed] = useState<number>(1); // 1x, 2x, 5x

  // 6-Hour Operational Control-Room Chart Filters
  const [chartTrainTypeFilter, setChartTrainTypeFilter] = useState<string>("ALL");
  const [chartCorridorFilter, setChartCorridorFilter] = useState<string>("ALL");
  const [chartSearchQuery, setChartSearchQuery] = useState<string>("");

  // Multi-Service Fleet Selection & Injected Departure Delays
  const [selectedServiceIds, setSelectedServiceIds] = useState<string[]>([
    "SRV_43501_01",
    "SRV_12675_01",
    "SRV_16057_01",
    "SRV_12607_01",
  ]);
  const [departureDelays, setDepartureDelays] = useState<Record<string, number>>({});

  // Delay Injection Form Inputs
  const [delayInputSvc, setDelayInputSvc] = useState<string>("SRV_12607_01");
  const [delayInputMinutes, setDelayInputMinutes] = useState<number>(15);

  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const currentMinuteRef = useRef<number>(360);

  // Sync state from backend authoritative state on load/update
  useEffect(() => {
    if (authoritativeState) {
      if (authoritativeState.current_minute !== undefined) {
        setCurrentMinute(authoritativeState.current_minute);
        currentMinuteRef.current = authoritativeState.current_minute;
      }
      if (authoritativeState.start_minute !== undefined) {
        setStartMinute(authoritativeState.start_minute);
      }
      if (authoritativeState.end_minute !== undefined) {
        setEndMinute(authoritativeState.end_minute);
      }
      if (authoritativeState.playback_speed !== undefined) {
        setPlaybackSpeed(authoritativeState.playback_speed);
      }
      if (authoritativeState.selected_service_ids && authoritativeState.selected_service_ids.length > 0) {
        setSelectedServiceIds(authoritativeState.selected_service_ids);
      }
      if (authoritativeState.departure_delays) {
        setDepartureDelays(authoritativeState.departure_delays);
      }
    }
  }, [authoritativeState]);

  const formatMinutesToTime = (totalMinutes: number): string => {
    const hours = Math.floor(totalMinutes / 60) % 24;
    const mins = Math.floor(totalMinutes % 60);
    return `${hours.toString().padStart(2, "0")}:${mins.toString().padStart(2, "0")}`;
  };

  // Corridor resolution helper
  const getCorridorName = (routeId?: string | null, corridor?: string | null): string => {
    if (corridor) return corridor;
    const r = (routeId || "").toUpperCase();
    if (r.includes("WEST")) return "West";
    if (r.includes("NORTH_BYPASS") || r.includes("BEACH_NORTH")) return "Beach–North Bypass";
    if (r.includes("NORTH")) return "North";
    if (r.includes("SOUTH")) return "South";
    if (r.includes("MRTS")) return "MRTS";
    if (r.includes("CROSS") || r.includes("BYPASS")) return "Cross/Bypass";
    if (r.includes("PTMS")) return "PTMS";
    return "West";
  };

  // Train type badge helper
  const getTrainTypeBadge = (serviceType?: string | null, trainType?: string | null) => {
    const raw = (serviceType || trainType || "").toUpperCase();
    if (raw === "SUBURBAN_EMU" || raw.includes("EMU") || raw.includes("SUBURBAN") || raw.includes("LOCAL")) {
      return { label: "EMU / SUBURBAN", shortLabel: "EMU", bg: "bg-emerald-950/80 text-emerald-300 border-emerald-500/50" };
    }
    if (raw === "INTERCITY") {
      return { label: "INTERCITY", shortLabel: "INT", bg: "bg-cyan-950/80 text-cyan-300 border-cyan-500/50" };
    }
    if (raw === "LONG_DISTANCE") {
      return { label: "LONG DISTANCE", shortLabel: "LD", bg: "bg-amber-950/80 text-amber-300 border-amber-500/50" };
    }
    return { label: "EXPRESS / SF", shortLabel: "EXP", bg: "bg-indigo-950/80 text-indigo-300 border-indigo-500/50" };
  };

  // Helper to parse HH:MM string into minutes
  const parseTimeToMinutes = (tStr?: string | null): number | null => {
    if (!tStr) return null;
    const parts = tStr.split(":");
    if (parts.length < 2) return null;
    return parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
  };

  // Window span in minutes
  const windowSpan = Math.max(1, endMinute - startMinute);

  // Generate hourly time ticks across the window span
  const timeTicks = React.useMemo(() => {
    const ticks: number[] = [];
    const step = 60; // 1-hour increments
    for (let m = startMinute; m <= endMinute; m += step) {
      ticks.push(m);
    }
    if (ticks[ticks.length - 1] !== endMinute) {
      ticks.push(endMinute);
    }
    return ticks;
  }, [startMinute, endMinute]);

  // Services active in the 6-hour work window
  const activeShiftServices = React.useMemo(() => {
    if (!network?.services) return [];
    return network.services.map((s) => {
      const pos = simulationData?.train_positions.find((p) => p.service_id === s.id);
      const depM = parseTimeToMinutes(s.scheduled_departure || pos?.scheduled_departure) ?? 360;
      const arrM = parseTimeToMinutes(s.scheduled_arrival || pos?.scheduled_arrival) ?? (depM + 75);
      const depDelay = departureDelays[s.id] ?? (pos?.delay_minutes || 0);
      const actualDepM = depM + depDelay;
      const actualArrM = arrM + depDelay;

      // Check conflict involvement
      const involvedConflict = simulationData?.detected_conflicts.find(
        (c) =>
          (c.affected_service_ids && c.affected_service_ids.includes(s.id)) ||
          (c.resource_id && (pos?.occupied_resources || []).includes(c.resource_id)) ||
          (c.description && c.description.includes(s.id))
      );

      const resolvedCorridor = getCorridorName(s.route_id, s.corridor || pos?.corridor_name);
      const resolvedType = s.service_type || s.train_type || pos?.service_type || pos?.train_type || (s.id.startsWith("SRV_4") ? "SUBURBAN_EMU" : "EXPRESS");

      const isInWindow =
        (actualDepM <= endMinute && actualArrM >= startMinute) ||
        selectedServiceIds.includes(s.id);

      return {
        service: s,
        position: pos,
        depMinutes: depM,
        arrMinutes: arrM,
        actualDepMinutes: actualDepM,
        actualArrMinutes: actualArrM,
        delayMinutes: depDelay,
        conflict: involvedConflict,
        corridor: resolvedCorridor,
        trainType: resolvedType,
        isInWindow,
      };
    });
  }, [network, simulationData, departureDelays, selectedServiceIds, startMinute, endMinute]);

  // Filtered services for the 6-hour chart
  const filteredChartServices = React.useMemo(() => {
    return activeShiftServices.filter((item) => {
      if (!item.isInWindow) return false;

      // Train type filter
      if (chartTrainTypeFilter !== "ALL") {
        const badge = getTrainTypeBadge(item.trainType, null);
        if (chartTrainTypeFilter === "SUBURBAN_EMU" && badge.shortLabel !== "EMU") return false;
        if (chartTrainTypeFilter === "EXPRESS" && badge.shortLabel !== "EXP" && badge.shortLabel !== "LD") return false;
        if (chartTrainTypeFilter === "INTERCITY" && badge.shortLabel !== "INT") return false;
        if (chartTrainTypeFilter === "LONG_DISTANCE" && badge.shortLabel !== "LD") return false;
      }

      // Corridor filter
      if (chartCorridorFilter !== "ALL") {
        if (!item.corridor.toLowerCase().includes(chartCorridorFilter.toLowerCase())) return false;
      }

      // Search query filter
      if (chartSearchQuery.trim()) {
        const q = chartSearchQuery.toLowerCase();
        const s = item.service;
        const match =
          s.id.toLowerCase().includes(q) ||
          (s.train_name && s.train_name.toLowerCase().includes(q)) ||
          s.train_id.toLowerCase().includes(q) ||
          s.origin.toLowerCase().includes(q) ||
          s.destination.toLowerCase().includes(q) ||
          item.corridor.toLowerCase().includes(q);
        if (!match) return false;
      }

      return true;
    });
  }, [activeShiftServices, chartTrainTypeFilter, chartCorridorFilter, chartSearchQuery]);


  const executeSimulationStep = (
    targetMin: number,
    customDelays?: Record<string, number>,
    customSvcs?: string[]
  ) => {
    const timeStr = formatMinutesToTime(targetMin);
    const delaysToUse = customDelays !== undefined ? customDelays : departureDelays;
    const svcsToUse = customSvcs !== undefined ? customSvcs : selectedServiceIds;

    onRunSimulation({
      start_time: formatMinutesToTime(startMinute),
      current_time: timeStr,
      time_limit_minutes: targetMin,
      service_ids: svcsToUse,
      departure_delays: delaysToUse,
    });

    if (onUpdateControl) {
      onUpdateControl({
        current_minute: targetMin,
        current_time_str: timeStr,
        service_ids: svcsToUse,
        departure_delays: delaysToUse,
      });
    }
  };

  // Play / Pause Ticker Loop (continues advancing even when 0 trains active)
  useEffect(() => {
    if (isPlaying) {
      const intervalMs = Math.max(300, Math.floor(1500 / playbackSpeed));
      timerRef.current = setInterval(() => {
        const prev = currentMinuteRef.current;
        if (prev >= endMinute) {
          setIsPlaying(false);
          return;
        }
        const next = Math.min(endMinute, prev + 5);
        currentMinuteRef.current = next;
        setCurrentMinute(next);
        executeSimulationStep(next);
      }, intervalMs);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, playbackSpeed, endMinute, departureDelays, selectedServiceIds, startMinute]);

  const handlePlayPause = () => {
    if (!isPlaying && currentMinute >= endMinute) {
      currentMinuteRef.current = startMinute;
      setCurrentMinute(startMinute);
      executeSimulationStep(startMinute);
    }
    const nextPlayState = !isPlaying;
    setIsPlaying(nextPlayState);
    if (onUpdateControl) {
      onUpdateControl({ is_playing: nextPlayState, current_minute: currentMinuteRef.current });
    }
  };

  const handleStepForward = () => {
    setIsPlaying(false);
    const next = Math.min(endMinute, currentMinute + 5);
    currentMinuteRef.current = next;
    setCurrentMinute(next);
    executeSimulationStep(next);
  };

  const handleStepBackward = () => {
    setIsPlaying(false);
    const prev = Math.max(startMinute, currentMinute - 5);
    currentMinuteRef.current = prev;
    setCurrentMinute(prev);
    executeSimulationStep(prev);
  };

  const handleReset = () => {
    setIsPlaying(false);
    currentMinuteRef.current = startMinute;
    setCurrentMinute(startMinute);
    executeSimulationStep(startMinute);
  };

  const handleScrub = (value: number) => {
    setIsPlaying(false);
    currentMinuteRef.current = value;
    setCurrentMinute(value);
    executeSimulationStep(value);
  };

  const handleSelectWindowPreset = (presetId: string) => {
    const preset = WINDOW_PRESETS.find((p) => p.id === presetId);
    if (!preset) return;
    setActiveWindowPreset(presetId);
    setStartMinute(preset.start);
    setEndMinute(preset.end);
    currentMinuteRef.current = preset.start;
    setCurrentMinute(preset.start);
    setIsPlaying(false);
    executeSimulationStep(preset.start);
  };

  // Fleet Service Selection Toggles
  const handleToggleService = (sId: string) => {
    let nextSvcs: string[];
    if (selectedServiceIds.includes(sId)) {
      if (selectedServiceIds.length <= 1) return; // keep at least 1 service
      nextSvcs = selectedServiceIds.filter((id) => id !== sId);
    } else {
      nextSvcs = [...selectedServiceIds, sId];
    }
    setSelectedServiceIds(nextSvcs);
    executeSimulationStep(currentMinute, departureDelays, nextSvcs);
  };

  const handleSelectAllServices = () => {
    if (!network) return;
    const allIds = network.services.map((s) => s.id);
    setSelectedServiceIds(allIds);
    executeSimulationStep(currentMinute, departureDelays, allIds);
  };

  const handleSelectMorningFleet = () => {
    const morning = ["SRV_43501_01", "SRV_12675_01", "SRV_16057_01", "SRV_12842_01", "SRV_22625_01"];
    setSelectedServiceIds(morning);
    executeSimulationStep(currentMinute, departureDelays, morning);
  };

  const handleSelectSuburbanFleet = () => {
    if (!network) return;
    const suburban = network.services
      .filter((s) => {
        const t = (s.service_type || s.train_type || "").toUpperCase();
        return t === "SUBURBAN_EMU" || t.includes("EMU") || t.includes("LOCAL") || s.id.startsWith("SRV_4");
      })
      .map((s) => s.id);
    const chosen = suburban.length > 0 ? suburban : selectedServiceIds;
    setSelectedServiceIds(chosen);
    executeSimulationStep(currentMinute, departureDelays, chosen);
  };

  const handleSelectExpressFleet = () => {
    if (!network) return;
    const express = network.services
      .filter((s) => {
        const t = (s.service_type || s.train_type || "").toUpperCase();
        return (
          t === "EXPRESS" ||
          t === "LONG_DISTANCE" ||
          (!t.includes("EMU") && !t.includes("LOCAL") && !s.id.startsWith("SRV_4"))
        );
      })
      .map((s) => s.id);
    const chosen = express.length > 0 ? express : selectedServiceIds;
    setSelectedServiceIds(chosen);
    executeSimulationStep(currentMinute, departureDelays, chosen);
  };

  const handleSelectIntercityFleet = () => {
    if (!network) return;
    const intercity = network.services
      .filter((s) => {
        const t = (s.service_type || s.train_type || "").toUpperCase();
        return t === "INTERCITY" || s.id.includes("160") || s.id.includes("162") || s.id.includes("127");
      })
      .map((s) => s.id);
    const chosen = intercity.length > 0 ? intercity : selectedServiceIds;
    setSelectedServiceIds(chosen);
    executeSimulationStep(currentMinute, departureDelays, chosen);
  };

  const handleSelectShiftFleet = () => {
    if (!network) return;
    const shiftSvcs = network.services
      .filter((s) => {
        const depStr = s.scheduled_departure;
        if (!depStr) return true;
        const depParts = depStr.split(":");
        const depM = parseInt(depParts[0], 10) * 60 + parseInt(depParts[1], 10);
        return depM >= startMinute - 60 && depM <= endMinute + 60;
      })
      .map((s) => s.id);
    const chosen = shiftSvcs.length > 0 ? shiftSvcs : network.services.map((s) => s.id);
    setSelectedServiceIds(chosen);
    executeSimulationStep(currentMinute, departureDelays, chosen);
  };

  // Multiple Disruption Management
  const handleAddOrUpdateDelay = () => {
    if (!delayInputSvc || delayInputMinutes <= 0) return;
    const nextDelays = {
      ...departureDelays,
      [delayInputSvc]: delayInputMinutes,
    };
    setDepartureDelays(nextDelays);
    executeSimulationStep(currentMinute, nextDelays);
  };

  const handleRemoveDelay = (sId: string) => {
    const nextDelays = { ...departureDelays };
    delete nextDelays[sId];
    setDepartureDelays(nextDelays);
    executeSimulationStep(currentMinute, nextDelays);
  };

  const handleClearAllDelays = () => {
    setDepartureDelays({});
    executeSimulationStep(currentMinute, {});
  };

  const handlePresetDisruption = (type: "DUAL_EXPRESS" | "TRIPLE_MORNING") => {
    let nextDelays: Record<string, number> = {};
    if (type === "DUAL_EXPRESS") {
      nextDelays = {
        "SRV_12607_01": 25,
        "SRV_12609_01": 20,
      };
    } else if (type === "TRIPLE_MORNING") {
      nextDelays = {
        "SRV_43501_01": 15,
        "SRV_12675_01": 10,
        "SRV_16057_01": 20,
      };
    }
    setDepartureDelays(nextDelays);
    executeSimulationStep(currentMinute, nextDelays);
  };

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
      case "MAJOR":
        return "bg-amber-500/20 text-amber-300 border-amber-500/40";
      case "WARNING":
        return "bg-yellow-500/20 text-yellow-300 border-yellow-500/40";
      default:
        return "bg-blue-500/20 text-blue-300 border-blue-500/40";
    }
  };

  // Inspect active vs waiting vs arrived services in current epoch
  const activeTrainsCount = simulationData?.train_positions.filter(
    (t) => t.status === "RUNNING" || t.status === "IN_TRANSIT" || t.status === "AT_STATION"
  ).length || 0;

  return (
    <div className="space-y-6">
      {/* 1. Live Simulation Engine Cockpit & Time Controls */}
      <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-4 font-mono">
        <div className="flex flex-wrap items-center justify-between gap-4 border-b border-railway-800 pb-4">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-cyan-950/80 border border-cyan-500/30 text-cyan-400">
              <Compass className="w-5 h-5 animate-spin-slow" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-sm font-bold text-white uppercase tracking-wider">
                  Live Train Movement Simulation Engine
                </h2>
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  isPlaying 
                    ? "bg-emerald-500/20 text-emerald-300 border-emerald-500/40 animate-pulse" 
                    : currentMinute >= endMinute
                    ? "bg-indigo-500/20 text-indigo-300 border-indigo-500/40"
                    : "bg-amber-500/20 text-amber-300 border-amber-500/40"
                }`}>
                  {isPlaying ? "LIVE RUNNING" : currentMinute >= endMinute ? "COMPLETED" : "PAUSED"}
                </span>
                <span className="px-2 py-0.5 rounded text-[10px] font-bold border bg-cyan-950/60 text-cyan-300 border-cyan-500/30">
                  {selectedServiceIds.length} SERVICES CONCURRENT
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Authoritative backend simulation advancing concurrent multi-train progression across Chennai Division at 5-minute epochs.
              </p>
            </div>
          </div>

          {/* Clock Display & Playback Speed */}
          <div className="flex items-center space-x-3">
            <div className="bg-railway-950 px-4 py-2 rounded-xl border border-cyan-500/30 flex items-center space-x-3">
              <Clock className="w-4 h-4 text-cyan-400" />
              <div>
                <span className="text-[10px] text-slate-500 block">SIMULATION CLOCK</span>
                <span className="text-lg font-bold text-cyan-300">
                  {formatMinutesToTime(currentMinute)}
                </span>
              </div>
              <span className="text-xs text-slate-500 pl-2 border-l border-railway-800">
                +{currentMinute - startMinute}m elapsed
              </span>
            </div>

            {/* Speed Selector */}
            <div className="flex items-center space-x-1 bg-railway-950 p-1 rounded-lg border border-railway-800 text-xs">
              {[1, 2, 5].map((speed) => (
                <button
                  key={speed}
                  onClick={() => setPlaybackSpeed(speed)}
                  className={`px-2 py-1 rounded font-bold transition-colors ${
                    playbackSpeed === speed
                      ? "bg-cyan-950 text-cyan-300 border border-cyan-500/40"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {speed}x
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Window Preset Selector */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-xs">
          <span className="text-slate-400 text-[11px] font-bold">OPERATIONAL SIMULATION WINDOW:</span>
          <div className="flex flex-wrap items-center gap-1.5">
            {WINDOW_PRESETS.map((preset) => (
              <button
                key={preset.id}
                onClick={() => handleSelectWindowPreset(preset.id)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition-all ${
                  activeWindowPreset === preset.id
                    ? "bg-cyan-900/80 text-cyan-200 border border-cyan-500/50 shadow-[0_0_8px_rgba(6,182,212,0.2)]"
                    : "bg-railway-950 text-slate-400 border border-railway-800 hover:text-slate-200"
                }`}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* Transport Controls & Timeline Scrubber */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-center pt-2">
          {/* Transport Buttons */}
          <div className="flex items-center space-x-2">
            <button
              onClick={handleReset}
              className="p-2.5 rounded-lg bg-railway-950 hover:bg-railway-800 border border-railway-800 text-slate-300 transition-colors"
              title={`Reset Simulation (${formatMinutesToTime(startMinute)})`}
            >
              <RotateCcw className="w-4 h-4" />
            </button>

            <button
              onClick={handleStepBackward}
              className="p-2.5 rounded-lg bg-railway-950 hover:bg-railway-800 border border-railway-800 text-slate-300 transition-colors"
              title="Step Backward 5m"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>

            <button
              onClick={handlePlayPause}
              disabled={isLoading}
              className={`flex-1 flex items-center justify-center space-x-2 py-2.5 px-4 rounded-lg font-bold text-xs shadow-lg transition-all ${
                isPlaying
                  ? "bg-amber-600 hover:bg-amber-500 text-white shadow-amber-900/30"
                  : "bg-emerald-600 hover:bg-emerald-500 text-white shadow-emerald-900/30"
              }`}
            >
              {isPlaying ? (
                <>
                  <Pause className="w-4 h-4 fill-white" />
                  <span>PAUSE SIMULATION</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-white" />
                  <span>START LIVE SIMULATION</span>
                </>
              )}
            </button>

            <button
              onClick={handleStepForward}
              className="p-2.5 rounded-lg bg-railway-950 hover:bg-railway-800 border border-railway-800 text-slate-300 transition-colors"
              title="Step Forward 5m"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Timeline Scrubber Slider */}
          <div className="lg:col-span-2 space-y-1.5">
            <div className="flex justify-between text-slate-400 text-[11px]">
              <span>{formatMinutesToTime(startMinute)} (Window Start)</span>
              <span className="text-cyan-300 font-bold">Current: {formatMinutesToTime(currentMinute)}</span>
              <span>{formatMinutesToTime(endMinute)} (Window End)</span>
            </div>
            <input
              type="range"
              min={startMinute}
              max={endMinute}
              step={5}
              value={currentMinute}
              onChange={(e) => handleScrub(Number(e.target.value))}
              className="w-full accent-cyan-400 h-2 bg-railway-950 rounded-lg cursor-pointer"
            />
          </div>
        </div>

        {/* Status banner when no trains currently on track */}
        {activeTrainsCount === 0 && (
          <div className="p-2.5 rounded-lg bg-indigo-950/30 border border-indigo-500/30 text-indigo-300 text-[11px] flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-indigo-400 shrink-0" />
              <span>
                Simulation advancing smoothly: Selected services are either awaiting scheduled departure slot or completed traversal.
              </span>
            </div>
            <span className="text-[10px] text-indigo-400/80 font-bold uppercase">Ready for Next Departure</span>
          </div>
        )}

        {/* Multi-Service Disruption Injection */}
        <div className="pt-3 border-t border-railway-800/60 space-y-3 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-slate-300 font-bold flex items-center space-x-1.5">
              <Sliders className="w-3.5 h-3.5 text-cyan-400" />
              <span>MULTI-SERVICE DISRUPTION INJECTION &amp; SCENARIOS</span>
            </span>

            {/* Quick Preset Buttons */}
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => handlePresetDisruption("DUAL_EXPRESS")}
                className="px-2 py-0.5 rounded bg-amber-950/60 hover:bg-amber-900 border border-amber-500/40 text-amber-300 text-[10px] font-bold"
              >
                + Dual Express Contention (+25m, +20m)
              </button>
              <button
                onClick={() => handlePresetDisruption("TRIPLE_MORNING")}
                className="px-2 py-0.5 rounded bg-cyan-950/60 hover:bg-cyan-900 border border-cyan-500/40 text-cyan-300 text-[10px] font-bold"
              >
                + Triple Morning Delay (+15m, +10m, +20m)
              </button>
              {Object.keys(departureDelays).length > 0 && (
                <button
                  onClick={handleClearAllDelays}
                  className="px-2 py-0.5 rounded bg-rose-950/60 hover:bg-rose-900 border border-rose-500/40 text-rose-300 text-[10px] font-bold flex items-center space-x-1"
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Clear Delays</span>
                </button>
              )}
            </div>
          </div>

          {/* Form to inject delay into any service */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end bg-railway-950 p-3 rounded-lg border border-railway-800">
            <div className="md:col-span-6">
              <label className="text-slate-400 block mb-1 text-[11px]">SELECT SERVICE TO DISRUPT</label>
              <select
                value={delayInputSvc}
                onChange={(e) => setDelayInputSvc(e.target.value)}
                className="w-full bg-railway-900 border border-railway-800 rounded-lg px-3 py-1.5 text-slate-200 text-xs focus:border-cyan-500 focus:outline-none"
              >
                {network?.services.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.id} — {s.train_name || s.train_id} ({s.origin} ➔ {s.destination})
                  </option>
                ))}
              </select>
            </div>

            <div className="md:col-span-4">
              <div className="flex justify-between items-center mb-1 text-[11px]">
                <label className="text-slate-400">DELAY MAGNITUDE</label>
                <span className="text-cyan-300 font-bold">+{delayInputMinutes} min</span>
              </div>
              <input
                type="range"
                min="0"
                max="60"
                step="1"
                value={delayInputMinutes}
                onChange={(e) => setDelayInputMinutes(Number(e.target.value))}
                className="w-full accent-cyan-400 h-2 bg-railway-900 rounded"
              />
            </div>

            <div className="md:col-span-2">
              <button
                onClick={handleAddOrUpdateDelay}
                className="w-full py-1.5 px-3 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-bold text-xs flex items-center justify-center space-x-1 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>INJECT</span>
              </button>
            </div>
          </div>

          {/* Active injected disruptions list */}
          {Object.keys(departureDelays).length > 0 && (
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <span className="text-slate-400 text-[11px] font-bold">ACTIVE INJECTED DELAYS:</span>
              {Object.entries(departureDelays).map(([sId, delay]) => (
                <div
                  key={sId}
                  className="flex items-center space-x-2 px-2.5 py-1 rounded-md bg-amber-950/40 border border-amber-500/40 text-amber-300 text-[11px]"
                >
                  <span className="font-bold">{sId}: +{delay}m delay</span>
                  <button
                    onClick={() => handleRemoveDelay(sId)}
                    className="text-amber-400 hover:text-white transition-colors"
                    title="Remove disruption"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Multi-Service Active Fleet Selection */}
        <div className="pt-3 border-t border-railway-800/60 space-y-2 text-xs">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-slate-300 font-bold flex items-center space-x-1.5">
              <Train className="w-3.5 h-3.5 text-cyan-400" />
              <span>ACTIVE CORRIDOR FLEET ({selectedServiceIds.length} OF {network?.services.length || 0} SERVICES SELECTED)</span>
            </span>

            <div className="flex flex-wrap items-center gap-1.5">
              <button
                onClick={handleSelectAllServices}
                className="px-2 py-0.5 rounded bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-500/50 text-cyan-300 text-[10px] font-bold"
              >
                All Fleet ({network?.services.length || 0})
              </button>
              <button
                onClick={handleSelectSuburbanFleet}
                className="px-2 py-0.5 rounded bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-500/50 text-emerald-300 text-[10px] font-bold"
              >
                Suburban EMU ({(network?.services || []).filter((s) => (s.service_type || s.train_type || "").includes("EMU") || s.id.startsWith("SRV_4")).length})
              </button>
              <button
                onClick={handleSelectExpressFleet}
                className="px-2 py-0.5 rounded bg-indigo-950/80 hover:bg-indigo-900 border border-indigo-500/50 text-indigo-300 text-[10px] font-bold"
              >
                Express ({(network?.services || []).filter((s) => (s.service_type || s.train_type || "") === "EXPRESS" || (s.service_type || s.train_type || "") === "LONG_DISTANCE" || (!((s.service_type || s.train_type || "").includes("EMU")) && !s.id.startsWith("SRV_4"))).length})
              </button>
              <button
                onClick={handleSelectIntercityFleet}
                className="px-2 py-0.5 rounded bg-blue-950/80 hover:bg-blue-900 border border-blue-500/50 text-blue-300 text-[10px] font-bold"
              >
                Intercity ({(network?.services || []).filter((s) => (s.service_type || s.train_type || "") === "INTERCITY" || s.id.includes("160") || s.id.includes("162")).length})
              </button>
              <button
                onClick={handleSelectShiftFleet}
                className="px-2 py-0.5 rounded bg-amber-950/80 hover:bg-amber-900 border border-amber-500/50 text-amber-300 text-[10px] font-bold"
              >
                Shift Fleet (6h)
              </button>
            </div>
          </div>

          <div className="flex flex-wrap gap-1.5 max-h-[100px] overflow-y-auto p-2 bg-railway-950 rounded-lg border border-railway-800">
            {network?.services.map((s) => {
              const isSelected = selectedServiceIds.includes(s.id);
              const hasDelay = departureDelays[s.id] !== undefined;
              const typeBadge = getTrainTypeBadge(s.service_type, s.train_type);
              return (
                <button
                  key={s.id}
                  onClick={() => handleToggleService(s.id)}
                  className={`px-2 py-1 rounded text-[10px] font-bold flex items-center space-x-1.5 transition-all ${
                    isSelected
                      ? hasDelay
                        ? "bg-amber-950/80 text-amber-200 border border-amber-500/60"
                        : "bg-cyan-950/80 text-cyan-200 border border-cyan-500/50"
                      : "bg-railway-900 text-slate-500 border border-railway-800 hover:text-slate-300"
                  }`}
                  title={`${s.train_name || s.train_id} (${s.origin} -> ${s.destination}) [${typeBadge.label}]`}
                >
                  <span className={`w-2 h-2 rounded-full ${isSelected ? (hasDelay ? "bg-amber-400" : "bg-cyan-400") : "bg-slate-600"}`} />
                  <span>{s.id}</span>
                  <span className={`text-[8px] px-1 py-0.2 rounded border ${typeBadge.bg}`}>
                    {typeBadge.shortLabel}
                  </span>
                  {hasDelay && <span className="text-amber-400">+{departureDelays[s.id]}m</span>}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 2. Telemetry Summary Cards */}
      {simulationData && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 font-mono text-xs">
          <div className="bg-railway-900 border border-railway-800 p-4 rounded-xl">
            <span className="text-slate-500 block text-[10px]">ACTIVE / TOTAL FLEET</span>
            <span className="text-xl font-bold text-white mt-1 block">
              {activeTrainsCount} / {simulationData.total_services_simulated}
            </span>
            <span className="text-slate-500 text-[10px]">Simulated concurrently</span>
          </div>

          <div className="bg-railway-900 border border-railway-800 p-4 rounded-xl">
            <span className="text-slate-500 block text-[10px]">DELAYED SERVICES</span>
            <span className="text-xl font-bold text-amber-400 mt-1 block">
              {simulationData.delayed_services_count}
            </span>
            <span className="text-slate-500 text-[10px]">Experiencing delay</span>
          </div>

          <div className="bg-railway-900 border border-railway-800 p-4 rounded-xl">
            <span className="text-slate-500 block text-[10px]">NETWORK DELAY ACCUMULATED</span>
            <span className="text-xl font-bold text-rose-400 mt-1 block">
              {simulationData.total_network_delay_minutes.toFixed(1)} min
            </span>
            <span className="text-slate-500 text-[10px]">At {formatMinutesToTime(currentMinute)}</span>
          </div>

          <div className="bg-railway-900 border border-railway-800 p-4 rounded-xl">
            <span className="text-slate-500 block text-[10px]">ACTIVE CONFLICTS AT EPOCH</span>
            <span className={`text-xl font-bold mt-1 block ${
              simulationData.detected_conflicts.length > 0 ? "text-rose-400" : "text-emerald-400"
            }`}>
              {simulationData.detected_conflicts.length}
            </span>
            <span className="text-slate-500 text-[10px]">Safety / headway breaches</span>
          </div>
        </div>
      )}

      {/* 2.5 6-HOUR OPERATIONAL CONTROL-ROOM DISPATCH CHART */}
      <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-4 font-mono text-xs shadow-lg">
        {/* Header & Filter Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-railway-800 pb-3">
          <div className="flex items-center space-x-2.5">
            <div className="p-1.5 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-300">
              <BarChart3 className="w-4 h-4 text-cyan-400" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="font-bold text-white uppercase tracking-wider text-xs">
                  6-Hour Operational Control-Room Dispatch Chart
                </h3>
                <span className="px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-500/50 text-cyan-300 font-bold text-[10px]">
                  WORK WINDOW: {formatMinutesToTime(startMinute)} ➔ {formatMinutesToTime(endMinute)} ({(windowSpan / 60).toFixed(1)}h)
                </span>
              </div>
              <p className="text-[10px] text-slate-400 mt-0.5">
                Real-time multi-train dispatch progression, delays, conflicts, and corridor movements across the selected work window.
              </p>
            </div>
          </div>

          {/* Quick Filters */}
          <div className="flex flex-wrap items-center gap-2">
            {/* Train Type Filter */}
            <div className="flex items-center bg-railway-950 rounded-lg border border-railway-800 p-0.5 text-[10px]">
              {(["ALL", "SUBURBAN_EMU", "EXPRESS", "INTERCITY"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setChartTrainTypeFilter(t)}
                  className={`px-2 py-1 rounded transition-colors ${
                    chartTrainTypeFilter === t
                      ? "bg-cyan-600 text-white font-bold"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  {t === "ALL" ? "All Types" : t === "SUBURBAN_EMU" ? "Suburban" : t}
                </button>
              ))}
            </div>

            {/* Corridor Filter */}
            <select
              value={chartCorridorFilter}
              onChange={(e) => setChartCorridorFilter(e.target.value)}
              className="bg-railway-950 border border-railway-800 rounded-lg px-2 py-1 text-slate-200 text-[10px] focus:border-cyan-500 focus:outline-none"
            >
              <option value="ALL">All Corridors</option>
              <option value="West">West</option>
              <option value="North">North</option>
              <option value="South">South</option>
              <option value="MRTS">MRTS</option>
              <option value="Beach–North Bypass">Beach–North Bypass</option>
              <option value="PTMS">PTMS</option>
            </select>

            <span className="text-[10px] text-slate-400 bg-railway-950 px-2 py-1 rounded border border-railway-800">
              {filteredChartServices.length} Active Services
            </span>
          </div>
        </div>

        {/* 6-Hour Time Scale Grid Header */}
        <div className="pt-1">
          <div className="grid grid-cols-12 gap-2 text-[10px] text-slate-400 font-bold border-b border-railway-800/80 pb-1.5 mb-2 items-center">
            <div className="col-span-4 lg:col-span-3">TRAIN / SERVICE IDENTITY</div>
            <div className="col-span-3 lg:col-span-2">LOCATION &amp; SECTION</div>
            <div className="col-span-5 lg:col-span-7">
              <div className="flex justify-between text-[10px] text-slate-400 px-1 relative">
                {timeTicks.map((tick, i) => (
                  <span key={i} className="text-center font-mono">
                    {formatMinutesToTime(tick)}
                  </span>
                ))}
                {/* Epoch Indicator Needle in Header */}
                <div
                  className="absolute top-0 bottom-0 w-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.8)] z-10"
                  style={{ left: `${Math.max(0, Math.min(100, ((currentMinute - startMinute) / windowSpan) * 100))}%` }}
                />
              </div>
            </div>
          </div>

          {/* Service Rows */}
          <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
            {filteredChartServices.length === 0 ? (
              <div className="text-center py-6 text-slate-500 text-xs italic bg-railway-950 rounded-lg border border-railway-800">
                No active services matching selected filters in work window ({formatMinutesToTime(startMinute)} ➔ {formatMinutesToTime(endMinute)}).
              </div>
            ) : (
              filteredChartServices.map((item) => {
                const s = item.service;
                const pos = item.position;
                const typeBadge = getTrainTypeBadge(item.trainType, null);
                const isRunning = pos?.status === "RUNNING" || pos?.status === "IN_TRANSIT" || pos?.status === "AT_STATION";
                const isArrived = pos?.status === "ARRIVED" || pos?.status === "COMPLETED";
                const hasConflict = item.conflict !== undefined;

                // Timeline percentages
                const leftPct = Math.max(0, Math.min(100, ((item.actualDepMinutes - startMinute) / windowSpan) * 100));
                const rightPct = Math.max(0, Math.min(100, ((item.actualArrMinutes - startMinute) / windowSpan) * 100));
                const barWidth = Math.max(4, rightPct - leftPct);
                const epochPct = Math.max(0, Math.min(100, ((currentMinute - startMinute) / windowSpan) * 100));

                return (
                  <div
                    key={s.id}
                    className="grid grid-cols-12 gap-2 items-center p-2 rounded-lg bg-railway-950/70 border border-railway-800/80 hover:border-slate-700 transition-colors"
                  >
                    {/* Identity Column */}
                    <div className="col-span-4 lg:col-span-3">
                      <div className="flex items-center space-x-1.5">
                        <span className="font-bold text-slate-200 truncate">{s.train_name || s.train_id}</span>
                        <span className={`text-[8px] px-1 py-0.2 rounded border font-bold ${typeBadge.bg}`}>
                          {typeBadge.shortLabel}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-500 truncate mt-0.5">
                        <span className="text-slate-400 font-semibold">{s.id}</span> • {item.corridor} ({s.origin} ➔ {s.destination})
                      </div>
                    </div>

                    {/* Location & Status Column */}
                    <div className="col-span-3 lg:col-span-2">
                      <div className="text-cyan-300 font-bold truncate text-[11px]">
                        {pos?.current_station || pos?.current_node || "EN ROUTE"}
                      </div>
                      <div className="flex items-center space-x-1.5 mt-0.5 text-[10px]">
                        <span className={item.delayMinutes > 0 ? "text-amber-400 font-bold" : "text-emerald-400"}>
                          {item.delayMinutes > 0 ? `+${item.delayMinutes}m` : "ON-TIME"}
                        </span>
                        {hasConflict && (
                          <span className="px-1 py-0.2 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 text-[9px] font-bold">
                            CONFLICT
                          </span>
                        )}
                      </div>
                    </div>

                    {/* 6-Hour Timeline Bar Column */}
                    <div className="col-span-5 lg:col-span-7 relative h-7 bg-railway-950 rounded-md border border-railway-800/80 overflow-hidden flex items-center px-1">
                      {/* Hourly background tick lines */}
                      {timeTicks.slice(1, -1).map((tick, idx) => {
                        const tickPct = ((tick - startMinute) / windowSpan) * 100;
                        return (
                          <div
                            key={idx}
                            className="absolute top-0 bottom-0 border-r border-railway-800/40"
                            style={{ left: `${tickPct}%` }}
                          />
                        );
                      })}

                      {/* Current epoch needle */}
                      <div
                        className="absolute top-0 bottom-0 w-0.5 bg-cyan-400 shadow-[0_0_8px_rgba(6,182,212,0.9)] z-20"
                        style={{ left: `${epochPct}%` }}
                        title={`Current Epoch: ${formatMinutesToTime(currentMinute)}`}
                      />

                      {/* Movement Trajectory Span */}
                      <div
                        className={`absolute h-4 rounded px-1.5 flex items-center justify-between text-[9px] font-bold shadow-sm z-10 transition-all ${
                          hasConflict
                            ? "bg-rose-600/90 text-white border border-rose-400 animate-pulse"
                            : isRunning
                            ? "bg-emerald-600/90 text-white border border-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.4)]"
                            : isArrived
                            ? "bg-indigo-700/80 text-indigo-200 border border-indigo-500/50"
                            : "bg-slate-700 text-slate-300 border border-slate-600"
                        }`}
                        style={{ left: `${leftPct}%`, width: `${barWidth}%` }}
                        title={`${s.train_name}: Dep ${formatMinutesToTime(item.actualDepMinutes)} -> Arr ${formatMinutesToTime(item.actualArrMinutes)}`}
                      >
                        <span className="truncate">{formatMinutesToTime(item.actualDepMinutes)}</span>
                        {barWidth > 18 && (
                          <span className="truncate">{formatMinutesToTime(item.actualArrMinutes)}</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>

      {/* 3. Live Train Tracker Table & Track Section Occupancy Matrix */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 font-mono text-xs">
        {/* Train Positions Table */}
        <div className="lg:col-span-2 bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-railway-800 pb-3">
            <div className="flex items-center space-x-2">
              <Train className="w-4 h-4 text-cyan-400" />
              <h3 className="font-bold text-white uppercase tracking-wider">
                Live Train Runtime Tracker (Epoch: {formatMinutesToTime(currentMinute)})
              </h3>
            </div>
            <span className="text-slate-500 text-[11px]">Authoritative Dynamic State</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-railway-800 text-slate-400 text-[11px]">
                  <th className="py-2.5 px-3">TRAIN / SERVICE</th>
                  <th className="py-2.5 px-3">CURRENT LOCATION</th>
                  <th className="py-2.5 px-3">SECTION / RESOURCE</th>
                  <th className="py-2.5 px-3">STATUS</th>
                  <th className="py-2.5 px-3">LIVE DELAY</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-railway-800/60">
                {simulationData?.train_positions.map((train) => {
                  const isRunning = train.status === "RUNNING" || train.status === "IN_TRANSIT" || train.status === "AT_STATION";
                  const isArrived = train.status === "ARRIVED" || train.status === "COMPLETED";
                  return (
                    <tr key={train.service_id} className="hover:bg-railway-800/40 transition-colors">
                      <td className="py-3 px-3">
                        <div className="flex items-center space-x-1.5">
                          <span className="font-bold text-slate-200">{train.train_name}</span>
                          <span className={`px-1 py-0.2 rounded text-[8px] font-bold border ${getTrainTypeBadge(train.train_type || train.service_type).bg}`}>
                            {getTrainTypeBadge(train.train_type || train.service_type).shortLabel}
                          </span>
                        </div>
                        <div className="text-[10px] text-slate-500">
                          {train.service_id} • {train.corridor_name || "West"} ({train.priority_class})
                        </div>
                      </td>
                      <td className="py-3 px-3 text-cyan-300 font-bold">
                        {train.current_station || train.current_node || "EN ROUTE"}
                      </td>
                      <td className="py-3 px-3 text-slate-400 text-[11px]">
                        {train.current_track_section || train.occupied_resources[0] || "--"}
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          isRunning
                            ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                            : isArrived
                            ? "bg-indigo-500/20 text-indigo-300 border border-indigo-500/30"
                            : train.status === "HELD"
                            ? "bg-rose-500/20 text-rose-300 border border-rose-500/30"
                            : "bg-slate-800 text-slate-400 border border-slate-700"
                        }`}>
                          {isRunning ? "RUNNING" : isArrived ? "ARRIVED" : "SCHEDULED"}
                        </span>
                      </td>
                      <td className="py-3 px-3">
                        <span className={`font-bold ${train.delay_minutes > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                          {train.delay_minutes > 0 ? `+${train.delay_minutes.toFixed(1)}m` : "ON-TIME"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Dynamic Occupancy & Conflict Alerts */}
        <div className="bg-railway-900 border border-railway-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-railway-800 pb-3">
            <div className="flex items-center space-x-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              <h3 className="font-bold text-white uppercase tracking-wider">
                Track Occupancies ({simulationData?.active_occupancies.length || 0})
              </h3>
            </div>
          </div>

          <div className="space-y-2 overflow-y-auto max-h-[180px]">
            {(!simulationData || simulationData.active_occupancies.length === 0) ? (
              <p className="text-slate-500 text-xs italic py-2 text-center">
                All track sections clear at current epoch.
              </p>
            ) : (
              simulationData.active_occupancies.map((occ, idx) => (
                <div key={idx} className="p-2.5 rounded-lg bg-railway-950 border border-railway-800 flex justify-between items-center text-xs">
                  <div>
                    <span className="text-cyan-300 font-bold block">{occ.section_id}</span>
                    <span className="text-[10px] text-slate-500">Service: {occ.service_id}</span>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 text-[10px]">
                    OCCUPIED
                  </span>
                </div>
              ))
            )}
          </div>

          <div className="border-t border-railway-800 pt-3">
            <div className="flex items-center justify-between pb-2">
              <div className="flex items-center space-x-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h3 className="font-bold text-white uppercase tracking-wider">
                  Epoch Conflicts ({simulationData?.detected_conflicts.length || 0})
                </h3>
              </div>
            </div>

            <div className="space-y-2 overflow-y-auto max-h-[160px]">
              {(!simulationData || simulationData.detected_conflicts.length === 0) ? (
                <div className="p-3 rounded-lg bg-emerald-950/20 border border-emerald-500/30 text-emerald-400 text-[11px] flex items-center space-x-2">
                  <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
                  <span>Zero conflicts at {formatMinutesToTime(currentMinute)}.</span>
                </div>
              ) : (
                simulationData.detected_conflicts.map((conflict) => (
                  <div
                    key={conflict.conflict_id}
                    className="p-3 rounded-lg bg-railway-950 border border-railway-800 space-y-1 text-xs"
                  >
                    <div className="flex justify-between items-center">
                      <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${getSeverityBadge(conflict.severity)}`}>
                        {conflict.severity}
                      </span>
                      <span className="text-slate-500 text-[10px]">Resource: {conflict.resource_id}</span>
                    </div>
                    <p className="text-[11px] text-slate-300">{conflict.description}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
