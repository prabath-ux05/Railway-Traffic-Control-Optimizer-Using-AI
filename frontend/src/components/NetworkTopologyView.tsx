"use client";

/**
 * NetworkTopologyView.tsx
 * ───────────────────────
 * Schematic SVG visualization of the Chennai Division railway network.
 *
 * SOURCE OF TRUTH: data/infrastructure/routes.json + stations.json + junctions.json
 * VISUAL REFERENCE: Chennai Suburban Railway Network map (provided reference image)
 *
 * Key topology facts (from junctions.json):
 *  - JCT_BBQ  → CRITICAL_THROAT: West + North corridors diverge here
 *  - JCT_VJM  → CORRIDOR_DIVERGENCE: West ↔ Chennai Beach-side routing diverge here
 *  - JCT_KOK  → CORRIDOR_MERGE: North (from MAS) + Bypass (from MSB) merge here
 *  - JCT_PAB  → BRANCH: PTMS siding branches off here
 *  - JCT_MSB  → MULTI_CORRIDOR_HUB: South + MRTS + Bypass
 *  - JCT_CGL  → CORRIDOR_DIVERGENCE: South ↔ Cross Line
 *  - JCT_AJJ  → MULTI_CORRIDOR_HUB: West trunk + Cross Line
 *
 * CRITICAL TOPOLOGY CORRECTION:
 *  VJM connects to MSB via the Beach-side routing path (through KOK→WST→RPM→MSB).
 *  There is NO direct MAS→MSB segment; the beach-side divergence happens at VJM/BBQ/KOK.
 */

import React, { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { 
  NetworkResponse, 
  TrainPositionState, 
  DetectedConflict, 
  TrackSectionOccupancyRecord 
} from "@/lib/types";
import { 
  Train, 
  MapPin, 
  Activity, 
  Clock, 
  AlertTriangle, 
  Layers, 
  GitBranch, 
  ArrowRight, 
  Search, 
  X, 
  CheckCircle2, 
  ShieldAlert, 
  Radio 
} from "lucide-react";

interface NetworkTopologyViewProps {
  network: NetworkResponse | null;
  trainPositions?: TrainPositionState[];
  detectedConflicts?: DetectedConflict[];
  activeOccupancies?: TrackSectionOccupancyRecord[];
  simulationTime?: string;
}

// ─── Corridor definitions ──────────────────────────────────────────────────────
const CORRIDORS = [
  { id: "ALL",    label: "All",       color: "#64748b" },
  { id: "WEST",   label: "West",      color: "#06b6d4" },
  { id: "NORTH",  label: "North",     color: "#f59e0b" },
  { id: "SOUTH",  label: "South",     color: "#22c55e" },
  { id: "MRTS",   label: "MRTS",      color: "#a855f7" },
  { id: "BYPASS", label: "Bypass",    color: "#3b82f6" },
  { id: "PTMS",   label: "PTMS",      color: "#f97316" },
  { id: "CROSS",  label: "Cross",     color: "#ec4899" },
];

const CORRIDOR_COLOR: Record<string, string> = Object.fromEntries(
  CORRIDORS.map((c) => [c.id, c.color])
);

const CORRIDOR_FULL_NAMES: Record<string, string> = {
  ALL: "All Chennai Division Corridors",
  WEST: "West Mainline (MAS - AJJ)",
  NORTH: "North Corridor (BBQ - SPE)",
  SOUTH: "South Mainline (MSB - CGL)",
  MRTS: "MRTS Elevated (MSB - VLCY)",
  BYPASS: "Beach–North Bypass (MSB - KOK)",
  CROSS: "Cross Line (CGL - AJJ)",
  PTMS: "PTMS Military Siding (PAB - PTMS)",
};

const TRAIN_TYPE_BADGES: Record<string, { bg: string; text: string; border: string; label: string }> = {
  SUBURBAN_EMU: { bg: "bg-emerald-950/60", text: "text-emerald-300", border: "border-emerald-500/40", label: "EMU" },
  EXPRESS: { bg: "bg-amber-950/60", text: "text-amber-300", border: "border-amber-500/40", label: "EXP" },
  INTERCITY: { bg: "bg-cyan-950/60", text: "text-cyan-300", border: "border-cyan-500/40", label: "INT" },
  LONG_DISTANCE: { bg: "bg-purple-950/60", text: "text-purple-300", border: "border-purple-500/40", label: "LD" },
};

// ─── Node type styles ──────────────────────────────────────────────────────────
const NODE_STYLES: Record<string, { r: number; fill: string; stroke: string; sw: number }> = {
  TERMINUS: { r: 8,  fill: "#0f172a", stroke: "#e2e8f0", sw: 2.5 },
  JUNCTION: { r: 6,  fill: "#1e293b", stroke: "#fbbf24", sw: 2 },
  MAJOR:    { r: 5,  fill: "#1e293b", stroke: "#94a3b8", sw: 1.5 },
  STATION:  { r: 3.5,fill: "#334155", stroke: "#475569", sw: 1 },
};

// ─── All nodes with SVG coordinates ───────────────────────────────────────────
// Layout follows the reference map spatial arrangement:
//   - West mainline:  y ≈ 330  (horizontal, left = AJJ, right = MAS)
//   - North corridor: diagonal from BBQ upper-right toward the coast (SPE)
//   - Bypass:         MSB → RPM → WST → KOK  (east side, connecting coast to North)
//   - South:          MSB → ... → CGL  (vertical, going south from MSB)
//   - MRTS:           MSB → ... → VLCY (coastal south, right of South line)
//   - Cross:          CGL → ... → AJJ  (diagonal connecting south to west)
//
// VJM (CORRIDOR_DIVERGENCE junction) is positioned between BBQ and the westbound
// PER, visually showing its role as the divergence point toward the Beach-side.
// The Beach-side path runs: VJM/BBQ → KOK → WST → RPM → MSB

interface NodeDef {
  id: string;
  name: string;
  x: number;
  y: number;
  type: "TERMINUS" | "JUNCTION" | "MAJOR" | "STATION";
  corridors: string[];
}

const NODES: NodeDef[] = [
  // ── WEST MAINLINE (y ≈ 330, going left AJJ→MAS) ────────────────────────────
  { id: "AJJ",  name: "Arakkonam",          x:  55, y: 332, type: "JUNCTION", corridors: ["WEST","CROSS"] },
  { id: "PLMG", name: "Poonamallee",        x:  80, y: 330, type: "STATION",  corridors: ["WEST"] },
  { id: "MSU",  name: "Mosur",              x: 103, y: 328, type: "STATION",  corridors: ["WEST"] },
  { id: "TO",   name: "Tiruvalangadu",      x: 127, y: 327, type: "STATION",  corridors: ["WEST"] },
  { id: "MAF",  name: "Minjur A",           x: 151, y: 326, type: "STATION",  corridors: ["WEST"] },
  { id: "SPAM", name: "Spandam",            x: 175, y: 325, type: "STATION",  corridors: ["WEST"] },
  { id: "KBT",  name: "Kadambattur",        x: 199, y: 325, type: "STATION",  corridors: ["WEST"] },
  { id: "EGT",  name: "Egattur",            x: 223, y: 325, type: "STATION",  corridors: ["WEST"] },
  { id: "TRL",  name: "Tiruvallur",         x: 248, y: 326, type: "TERMINUS", corridors: ["WEST"] },
  { id: "PTLR", name: "Putlur",             x: 273, y: 327, type: "STATION",  corridors: ["WEST"] },
  { id: "SVR",  name: "Sevvapet Road",      x: 297, y: 328, type: "STATION",  corridors: ["WEST"] },
  { id: "VEU",  name: "Veppampattu",        x: 321, y: 329, type: "STATION",  corridors: ["WEST"] },
  { id: "TI",   name: "Tiruninravur",       x: 345, y: 330, type: "STATION",  corridors: ["WEST"] },
  { id: "NEC",  name: "Nemilichery",        x: 369, y: 331, type: "STATION",  corridors: ["WEST"] },
  { id: "PAB",  name: "Pattabiram",         x: 393, y: 332, type: "JUNCTION", corridors: ["WEST","PTMS"] },
  { id: "HC",   name: "Hindu College",      x: 417, y: 332, type: "STATION",  corridors: ["WEST"] },
  { id: "AVD",  name: "Avadi",              x: 441, y: 333, type: "MAJOR",    corridors: ["WEST"] },
  { id: "ANNR", name: "Annanur",            x: 465, y: 333, type: "STATION",  corridors: ["WEST"] },
  { id: "TMVL", name: "Tirumazhisai",       x: 489, y: 333, type: "STATION",  corridors: ["WEST"] },
  { id: "ABU",  name: "Ambattur",           x: 513, y: 332, type: "MAJOR",    corridors: ["WEST"] },
  { id: "PVM",  name: "Pattaravakkam",      x: 537, y: 330, type: "STATION",  corridors: ["WEST"] },
  { id: "KOTR", name: "Korattur",           x: 561, y: 328, type: "STATION",  corridors: ["WEST"] },
  { id: "VLK",  name: "Villivakkam",        x: 585, y: 325, type: "MAJOR",    corridors: ["WEST"] },
  { id: "PEW",  name: "Pattabiram E Works", x: 609, y: 322, type: "STATION",  corridors: ["WEST"] },
  { id: "PCW",  name: "Pattabiram C Works", x: 633, y: 319, type: "STATION",  corridors: ["WEST"] },
  { id: "PER",  name: "Perambur",           x: 657, y: 315, type: "MAJOR",    corridors: ["WEST"] },
  // VJM is the CORRIDOR_DIVERGENCE junction – between BBQ(West) and the westbound PER;
  // visually it sits just east of PER, south of KOK, bridging toward the coastal routing
  { id: "VJM",  name: "Vyasarpadi Jeeva",   x: 682, y: 308, type: "JUNCTION", corridors: ["WEST"] },
  { id: "BBQ",  name: "Basin Bridge",       x: 706, y: 300, type: "JUNCTION", corridors: ["WEST","NORTH"] },
  { id: "MAS",  name: "Chennai Central",    x: 718, y: 330, type: "TERMINUS", corridors: ["WEST","NORTH"] },

  // ── PTMS BRANCH (north from PAB) ───────────────────────────────────────────
  { id: "PTMS", name: "Pattabiram Siding",  x: 393, y: 258, type: "TERMINUS", corridors: ["PTMS"] },

  // ── NORTH CORRIDOR (BBQ → KOK → ... → SPE) ────────────────────────────────
  // KOK is the CORRIDOR_MERGE point where North (from BBQ) and Bypass (from WST) meet
  { id: "KOK",  name: "Korukkupet",         x: 738, y: 258, type: "JUNCTION", corridors: ["NORTH","BYPASS"] },
  { id: "TNPM", name: "Tondiarpet",         x: 768, y: 232, type: "STATION",  corridors: ["NORTH"] },
  { id: "VOCN", name: "VOC Nagar",          x: 798, y: 210, type: "STATION",  corridors: ["NORTH"] },
  { id: "TVT",  name: "Tiruvottiyur",       x: 832, y: 188, type: "MAJOR",    corridors: ["NORTH","BYPASS"] },
  { id: "WCN",  name: "Wimco Nagar",        x: 864, y: 168, type: "STATION",  corridors: ["NORTH"] },
  { id: "KAVM", name: "Kathivakkam",        x: 895, y: 150, type: "STATION",  corridors: ["NORTH"] },
  { id: "ENR",  name: "Ennore",             x: 926, y: 133, type: "MAJOR",    corridors: ["NORTH","BYPASS"] },
  { id: "AIP",  name: "Attipattu Pudunagar",x: 955, y: 117, type: "STATION",  corridors: ["NORTH"] },
  { id: "ATU",  name: "Attipattu",          x: 982, y: 102, type: "STATION",  corridors: ["NORTH"] },
  { id: "NPKM", name: "Nandiambakkam",      x:1008, y:  88, type: "STATION",  corridors: ["NORTH"] },
  { id: "MJR",  name: "Minijur",            x:1032, y:  75, type: "STATION",  corridors: ["NORTH"] },
  { id: "APB",  name: "Anuppambattu",       x:1055, y:  63, type: "STATION",  corridors: ["NORTH"] },
  { id: "PON",  name: "Ponneri",            x:1076, y:  52, type: "MAJOR",    corridors: ["NORTH"] },
  { id: "KVP",  name: "Kavaraipettai",      x:1097, y:  41, type: "STATION",  corridors: ["NORTH"] },
  { id: "GPD",  name: "Gummidipoondi",      x:1117, y:  31, type: "TERMINUS", corridors: ["NORTH","BYPASS"] },
  { id: "ELR",  name: "Elavur",             x:1136, y:  21, type: "STATION",  corridors: ["NORTH"] },
  { id: "AKM",  name: "Arambakkam",         x:1153, y:  13, type: "STATION",  corridors: ["NORTH"] },
  { id: "TADA", name: "Tada",               x:1168, y:   6, type: "STATION",  corridors: ["NORTH"] },
  { id: "AKAT", name: "Akkampet",           x:1181, y:   1, type: "STATION",  corridors: ["NORTH"] },
  { id: "SPE",  name: "Sullurpeta",         x:1193, y:   0, type: "TERMINUS", corridors: ["NORTH"] },

  // ── BYPASS (MSB → RPM → WST → KOK) ────────────────────────────────────────
  // WST (Washermanpet) and RPM (Royapuram) form the coastal link from MSB to KOK
  { id: "WST",  name: "Washermanpet",       x: 790, y: 305, type: "STATION",  corridors: ["BYPASS"] },
  { id: "RPM",  name: "Royapuram",          x: 824, y: 330, type: "STATION",  corridors: ["BYPASS"] },
  { id: "MSB",  name: "Chennai Beach",      x: 860, y: 358, type: "JUNCTION", corridors: ["BYPASS","SOUTH","MRTS"] },

  // ── SOUTH CORRIDOR (MSB → ... → CGL) ─────────────────────────────────────
  // MSB branches: MSF is shared between SOUTH and MRTS
  { id: "MSF",  name: "Chennai Fort",       x: 840, y: 388, type: "MAJOR",    corridors: ["SOUTH","MRTS"] },
  { id: "MPK",  name: "Chennai Park",       x: 816, y: 416, type: "STATION",  corridors: ["SOUTH"] },
  { id: "MS",   name: "Chennai Egmore",     x: 793, y: 443, type: "TERMINUS", corridors: ["SOUTH"] },
  { id: "MCPT", name: "Park Town",          x: 868, y: 416, type: "STATION",  corridors: ["MRTS"] },
  { id: "MCPK", name: "Thousand Lights",    x: 882, y: 443, type: "STATION",  corridors: ["MRTS"] },
  { id: "MSC",  name: "Chetpet",            x: 770, y: 464, type: "STATION",  corridors: ["SOUTH"] },
  { id: "NBK",  name: "Nungambakkam",       x: 748, y: 483, type: "STATION",  corridors: ["SOUTH"] },
  { id: "MTCN", name: "Chepauk",            x: 895, y: 464, type: "STATION",  corridors: ["MRTS"] },
  { id: "MKK",  name: "Kodambakkam",        x: 726, y: 500, type: "STATION",  corridors: ["SOUTH"] },
  { id: "MPKT", name: "Chennai Park Town",  x: 856, y: 388, type: "STATION",  corridors: ["MRTS"] },
  { id: "MLHS", name: "Light House",        x: 906, y: 483, type: "STATION",  corridors: ["MRTS"] },
  { id: "MBM",  name: "Mambalam",           x: 704, y: 516, type: "MAJOR",    corridors: ["SOUTH"] },
  { id: "MKAK", name: "Tiruvanmiyur",       x: 915, y: 500, type: "STATION",  corridors: ["MRTS"] },
  { id: "SP",   name: "Saidapet",           x: 685, y: 532, type: "STATION",  corridors: ["SOUTH"] },
  { id: "MTMY", name: "Thiruvanmiyur",      x: 922, y: 516, type: "STATION",  corridors: ["MRTS"] },
  { id: "GDY",  name: "Guindy",             x: 667, y: 547, type: "MAJOR",    corridors: ["SOUTH"] },
  { id: "MYND", name: "Mylapore",           x: 928, y: 532, type: "STATION",  corridors: ["MRTS"] },
  { id: "STM",  name: "St. Thomas Mount",   x: 652, y: 562, type: "STATION",  corridors: ["SOUTH"] },
  { id: "MNDY", name: "Mandaveli",          x: 934, y: 547, type: "STATION",  corridors: ["MRTS"] },
  { id: "PZA",  name: "Pallavaram",         x: 638, y: 576, type: "STATION",  corridors: ["SOUTH"] },
  { id: "GWYR", name: "Greenways Road",     x: 940, y: 562, type: "STATION",  corridors: ["MRTS"] },
  { id: "MN",   name: "Meenambakkam",       x: 624, y: 589, type: "STATION",  corridors: ["SOUTH"] },
  { id: "KTPM", name: "Kasturba Nagar",     x: 946, y: 576, type: "STATION",  corridors: ["MRTS"] },
  { id: "TLM",  name: "Tirusulam",          x: 611, y: 602, type: "STATION",  corridors: ["SOUTH"] },
  { id: "KTBR", name: "Indira Nagar",       x: 950, y: 589, type: "STATION",  corridors: ["MRTS"] },
  { id: "PV",   name: "Chromepet",          x: 598, y: 614, type: "STATION",  corridors: ["SOUTH"] },
  { id: "INDR", name: "Indira Nagar Jn",    x: 953, y: 602, type: "STATION",  corridors: ["MRTS"] },
  { id: "CMP",  name: "Pallavaram Stn",     x: 585, y: 624, type: "STATION",  corridors: ["SOUTH"] },
  { id: "TYMR", name: "Taramani",           x: 954, y: 614, type: "STATION",  corridors: ["MRTS"] },
  { id: "TBMS", name: "Tambaram Sanatorium",x: 573, y: 634, type: "STATION",  corridors: ["SOUTH"] },
  { id: "TRMN", name: "Perungudi",          x: 954, y: 626, type: "STATION",  corridors: ["MRTS"] },
  { id: "TBM",  name: "Tambaram",           x: 561, y: 644, type: "TERMINUS", corridors: ["SOUTH"] },
  { id: "PRGD", name: "Sholinganallur",     x: 953, y: 638, type: "STATION",  corridors: ["MRTS"] },
  { id: "PRGL", name: "Vandalur",           x: 542, y: 654, type: "STATION",  corridors: ["SOUTH"] },
  { id: "VLCY", name: "Velachery",          x: 950, y: 652, type: "TERMINUS", corridors: ["MRTS"] },
  { id: "VDR",  name: "Perungalathur",      x: 524, y: 663, type: "STATION",  corridors: ["SOUTH"] },
  { id: "UPM",  name: "Urappakkam",         x: 507, y: 672, type: "STATION",  corridors: ["SOUTH"] },
  { id: "GI",   name: "Guduvancheri",       x: 490, y: 679, type: "STATION",  corridors: ["SOUTH"] },
  { id: "POT",  name: "Potheri",            x: 473, y: 685, type: "STATION",  corridors: ["SOUTH"] },
  { id: "CTM",  name: "Kattangulathur",     x: 456, y: 690, type: "STATION",  corridors: ["SOUTH"] },
  { id: "MMNK", name: "Maraimalai Nagar",   x: 439, y: 694, type: "STATION",  corridors: ["SOUTH"] },
  { id: "SKL",  name: "Singaperumal Koil",  x: 422, y: 697, type: "STATION",  corridors: ["SOUTH"] },
  { id: "PWU",  name: "Paranur",            x: 405, y: 700, type: "STATION",  corridors: ["SOUTH"] },
  { id: "CGL",  name: "Chengalpattu",       x: 388, y: 703, type: "JUNCTION", corridors: ["SOUTH","CROSS"] },

  // ── CROSS LINE (CGL → ... → AJJ) ──────────────────────────────────────────
  { id: "RDY",  name: "Reddypalayam",       x: 360, y: 696, type: "STATION",  corridors: ["CROSS"] },
  { id: "VAM",  name: "Villiambakkam",       x: 333, y: 687, type: "STATION",  corridors: ["CROSS"] },
  { id: "PALR", name: "Palur",              x: 307, y: 677, type: "STATION",  corridors: ["CROSS"] },
  { id: "PJS",  name: "Paiyur",             x: 281, y: 666, type: "STATION",  corridors: ["CROSS"] },
  { id: "WJ",   name: "Walajabad",          x: 256, y: 654, type: "STATION",  corridors: ["CROSS"] },
  { id: "NTT",  name: "Nathapettai",        x: 232, y: 641, type: "STATION",  corridors: ["CROSS"] },
  { id: "CJE",  name: "Kancheepuram Old",   x: 209, y: 627, type: "STATION",  corridors: ["CROSS"] },
  { id: "CJ",   name: "Kanchipuram",        x: 188, y: 612, type: "MAJOR",    corridors: ["CROSS"] },
  { id: "TMLP", name: "Tirumalpur",         x: 167, y: 595, type: "STATION",  corridors: ["CROSS"] },
  { id: "TKO",  name: "Takkolam",           x: 131, y: 540, type: "STATION",  corridors: ["CROSS"] },
  // AJJ already defined in WEST above
];

// Build fast node lookup
const NODE_MAP = Object.fromEntries(NODES.map((n) => [n.id, n]));

// ─── Edges ─────────────────────────────────────────────────────────────────────
// Derived from routes.json consecutive node pairs (undirected, deduplicated)
// PTMS branch: PAB→PTMS (from RT_MAS_PTMS)
// CRITICAL: VJM→WST represents the Beach-side divergence (JCT_VJM description).
//           This bridges the West corridor junction to the Bypass at Washermanpet.

interface EdgeDef {
  from: string;
  to: string;
  corridor: string;
  dashed?: boolean;
}

function buildEdges(): EdgeDef[] {
  const routeEdges: Array<{ pairs: string[][], corridor: string }> = [
    // WEST mainline
    {
      pairs: consecutive(["MAS","BBQ","VJM","PER","PCW","PEW","VLK","KOTR","PVM","ABU","TMVL","ANNR","AVD","HC","PAB","NEC","TI","VEU","SVR","PTLR","TRL","EGT","KBT","SPAM","MAF","TO","MSU","PLMG","AJJ"]),
      corridor: "WEST",
    },
    // PTMS branch
    {
      pairs: consecutive(["PAB","PTMS"]),
      corridor: "PTMS",
    },
    // NORTH corridor (MAS→BBQ→KOK branch; MAS→BBQ already in WEST)
    {
      pairs: consecutive(["BBQ","KOK","TNPM","VOCN","TVT","WCN","KAVM","ENR","AIP","ATU","NPKM","MJR","APB","PON","KVP","GPD","ELR","AKM","TADA","AKAT","SPE"]),
      corridor: "NORTH",
    },
    // BYPASS: MSB → RPM → WST → KOK (connects Beach to North at KOK)
    {
      pairs: consecutive(["MSB","RPM","WST","KOK"]),
      corridor: "BYPASS",
    },
    // SOUTH corridor
    {
      pairs: consecutive(["MSB","MSF","MPK","MS","MSC","NBK","MKK","MBM","SP","GDY","STM","PZA","MN","TLM","PV","CMP","TBMS","TBM","PRGL","VDR","UPM","GI","POT","CTM","MMNK","SKL","PWU","CGL"]),
      corridor: "SOUTH",
    },
    // MRTS elevated (MSB→VLCY)
    {
      pairs: consecutive(["MSB","MSF","MPKT","MCPT","MCPK","MTCN","MLHS","MKAK","MTMY","MYND","MNDY","GWYR","KTPM","KTBR","INDR","TYMR","TRMN","PRGD","VLCY"]),
      corridor: "MRTS",
    },
    // CROSS line
    {
      pairs: consecutive(["CGL","RDY","VAM","PALR","PJS","WJ","NTT","CJE","CJ","TMLP","TKO","AJJ"]),
      corridor: "CROSS",
    },
  ];

  const seen = new Set<string>();
  const edges: EdgeDef[] = [];

  for (const { pairs, corridor } of routeEdges) {
    for (const [a, b] of pairs) {
      const key = [a, b].sort().join(":");
      if (!seen.has(key)) {
        seen.add(key);
        edges.push({ from: a, to: b, corridor });
      }
    }
  }

  // VJM → WST: the Beach-side divergence from JCT_VJM (not in any explicit route
  // sequence, but expressed by the JCT_VJM junction description and geographic reality)
  const vjmWstKey = ["VJM","WST"].sort().join(":");
  if (!seen.has(vjmWstKey)) {
    edges.push({ from: "VJM", to: "WST", corridor: "BYPASS", dashed: true });
  }

  return edges;
}

function consecutive(nodes: string[]): string[][] {
  const pairs: string[][] = [];
  for (let i = 0; i < nodes.length - 1; i++) {
    pairs.push([nodes[i], nodes[i + 1]]);
  }
  return pairs;
}

const ALL_EDGES = buildEdges();

// ─── Corridor-to-node membership (for filtering) ──────────────────────────────
function getVisibleSet(filter: string): Set<string> {
  if (filter === "ALL") return new Set(NODES.map((n) => n.id));
  const corridorEdges = ALL_EDGES.filter((e) => e.corridor === filter);
  const ids = new Set<string>();
  for (const e of corridorEdges) {
    ids.add(e.from);
    ids.add(e.to);
  }
  return ids;
}

// ─── Component ────────────────────────────────────────────────────────────────
export const NetworkTopologyView: React.FC<NetworkTopologyViewProps> = ({
  network,
  trainPositions = [],
  detectedConflicts = [],
  activeOccupancies = [],
  simulationTime,
}) => {
  const [corridorFilter, setCorridorFilter] = useState<string>("ALL");
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [inspectorTab, setInspectorTab] = useState<"ALL" | "OVERVIEW" | "ROUTES" | "TIMETABLE" | "LIVE">("ALL");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [canvasSize, setCanvasSize] = useState({ w: 0, h: 0 });
  const isPanningRef = useRef(false);
  const panStartRef = useRef({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  // ResizeObserver: keep canvasSize in sync with the real DOM size
  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const ro = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      if (width > 0 && height > 0) {
        setCanvasSize({ w: width, h: height });
      }
    });
    ro.observe(el);
    const rect = el.getBoundingClientRect();
    if (rect.width > 0) setCanvasSize({ w: rect.width, h: rect.height });
    return () => ro.disconnect();
  }, []);

  // Auto-fit to the selected corridor bounds using real container dimensions
  useEffect(() => {
    const w = canvasSize.w || canvasRef.current?.getBoundingClientRect().width || 900;
    const h = canvasSize.h || canvasRef.current?.getBoundingClientRect().height || 500;
    if (w === 0 || h === 0) return;

    const visSet = getVisibleSet(corridorFilter);
    const visNodes = NODES.filter((n) => visSet.has(n.id));
    if (visNodes.length === 0) return;
    const xs = visNodes.map((n) => n.x);
    const ys = visNodes.map((n) => n.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const rangeX = maxX - minX || 1;
    const rangeY = maxY - minY || 1;
    const pad = 80;
    const newZoom = Math.min(2.5, Math.min((w - pad * 2) / rangeX, (h - pad * 2) / rangeY));
    const newPanX = w / 2 - (minX + rangeX / 2) * newZoom;
    const newPanY = h / 2 - (minY + rangeY / 2) * newZoom;
    setZoom(parseFloat(newZoom.toFixed(3)));
    setPan({ x: newPanX, y: newPanY });
    // Keep selectedNode if it's still visible
    if (selectedNode && !visSet.has(selectedNode) && corridorFilter !== "ALL") {
      setSelectedNode(null);
    }
  }, [corridorFilter, canvasSize]);

  // Pan handlers
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if ((e.target as SVGElement).dataset.nodeId) return;
    isPanningRef.current = true;
    panStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  }, [pan]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanningRef.current) return;
    setPan({ x: e.clientX - panStartRef.current.x, y: e.clientY - panStartRef.current.y });
  }, []);

  const handleMouseUp = useCallback(() => { isPanningRef.current = false; }, []);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    setZoom((z) => Math.max(0.3, Math.min(4, z * factor)));
  }, []);

  const visibleNodeIds = getVisibleSet(corridorFilter);

  // Authoritative queries for selected node
  const selNode = selectedNode ? NODE_MAP[selectedNode] : null;
  const selStation = selNode && network?.stations.find((s) => s.id === selNode.id);
  const selJunction = selNode && network?.junctions.find(
    (j) => j.station_id === selNode.id || j.id === `JCT_${selNode.id}` || j.id === selNode.id
  );

  // Platforms for this station
  const stationPlatforms = useMemo(() => {
    if (!selNode || !network?.platforms) return [];
    return network.platforms.filter((p) => p.station_id === selNode.id);
  }, [selNode, network]);

  const platformCount = selStation?.platform_count || (stationPlatforms.length > 0 ? stationPlatforms.length : (selNode?.type === "TERMINUS" ? 4 : selNode?.type === "JUNCTION" ? 4 : 2));

  // Connected routes passing through or serving this station
  const connectedRoutes = useMemo(() => {
    if (!selNode || !network?.routes) return [];
    return network.routes.filter((r) => r.ordered_nodes.includes(selNode.id));
  }, [selNode, network]);

  // Connected track sections (inbound and outbound)
  const connectedSections = useMemo(() => {
    if (!selNode || !network?.track_sections) return [];
    return network.track_sections.filter((ts) => ts.from_node === selNode.id || ts.to_node === selNode.id);
  }, [selNode, network]);

  // Associated services (calling or routing through this station)
  const associatedServices = useMemo(() => {
    if (!selNode || !network?.services) return [];
    return network.services.filter((s) => {
      const inTt = network.timetable?.some((t) => t.service_id === s.id && t.station_id === selNode.id);
      const onRoute = network.routes.some((r) => r.id === s.route_id && r.ordered_nodes.includes(selNode.id));
      return inTt || onRoute;
    });
  }, [selNode, network]);

  // Timetable entries for this station
  const stationTimetable = useMemo(() => {
    if (!selNode || !network?.timetable) return [];
    return network.timetable
      .filter((t) => t.station_id === selNode.id)
      .sort((a, b) => (a.departure || a.arrival || "").localeCompare(b.departure || b.arrival || ""));
  }, [selNode, network]);

  // Live trains at or approaching this station
  const liveTrainsAtStation = useMemo(() => {
    if (!selNode) return [];
    return trainPositions.filter(
      (t) =>
        t.current_station === selNode.id ||
        t.current_node === selNode.id ||
        t.occupied_resources?.some((r) => r.includes(selNode.id))
    );
  }, [selNode, trainPositions]);

  // Active conflicts at this station or affecting trains here
  const activeConflictsAtStation = useMemo(() => {
    if (!selNode || !detectedConflicts) return [];
    const trainServiceIds = new Set(liveTrainsAtStation.map((t) => t.service_id));
    return detectedConflicts.filter(
      (c) =>
        c.resource_id?.includes(selNode.id) ||
        c.affected_service_ids?.some((sid) => trainServiceIds.has(sid))
    );
  }, [selNode, detectedConflicts, liveTrainsAtStation]);

  // Train count lookup across all stations
  const trainCounts: Record<string, number> = useMemo(() => {
    const counts: Record<string, number> = {};
    trainPositions.forEach((t) => {
      if (t.current_station) {
        counts[t.current_station] = (counts[t.current_station] || 0) + 1;
      }
    });
    return counts;
  }, [trainPositions]);

  const corridorEdgeColor = (c: string) => CORRIDOR_COLOR[c] || "#475569";

  const stationCategory = selStation?.station_type
    ? selStation.station_type
    : selJunction
    ? "Junction Station"
    : selNode?.type === "TERMINUS"
    ? "Terminal"
    : selNode?.type === "MAJOR"
    ? "Major Station"
    : "Suburban Station";

  const operationalStatus = activeConflictsAtStation.length > 0
    ? { label: "CONFLICT ACTIVE", color: "text-rose-300", bg: "bg-rose-950/80 border-rose-500/50" }
    : liveTrainsAtStation.some((t) => t.delay_minutes > 0)
    ? { label: `DELAYED (${liveTrainsAtStation.filter((t) => t.delay_minutes > 0).length})`, color: "text-amber-300", bg: "bg-amber-950/80 border-amber-500/50" }
    : liveTrainsAtStation.length > 0
    ? { label: `ACTIVE (${liveTrainsAtStation.length})`, color: "text-emerald-300", bg: "bg-emerald-950/80 border-emerald-500/50" }
    : { label: "IDLE / CLEAR", color: "text-slate-400", bg: "bg-slate-800/80 border-slate-700/50" };

  if (!network) {
    return (
      <div className="flex items-center justify-center h-80 text-slate-500 text-sm font-mono">
        Loading Chennai Division topology...
      </div>
    );
  }

  return (
    <div className="flex flex-col" style={{ height: '100%', minHeight: 0 }}>
      {/* ── Corridor filter bar + Station Selector ── */}
      <div className="flex items-center gap-1.5 px-4 py-2 border-b border-slate-800 bg-slate-900/80 flex-wrap">
        {CORRIDORS.map((c) => (
          <button
            key={c.id}
            onClick={() => setCorridorFilter(c.id)}
            className="px-2.5 py-1 rounded-full text-[11px] font-semibold tracking-wide transition-all"
            style={{
              background: corridorFilter === c.id ? c.color : "transparent",
              color: corridorFilter === c.id ? "#0f172a" : c.color,
              border: `1.5px solid ${c.color}`,
              opacity: corridorFilter !== "ALL" && corridorFilter !== c.id ? 0.4 : 1,
            }}
          >
            {c.label}
          </button>
        ))}

        {/* Station Search / Quick Selector */}
        <div className="relative flex items-center ml-2">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 pointer-events-none" />
          <select
            value={selectedNode || ""}
            onChange={(e) => {
              const val = e.target.value;
              if (val) {
                setSelectedNode(val);
                const n = NODE_MAP[val];
                if (n && corridorFilter !== "ALL" && !n.corridors.includes(corridorFilter)) {
                  setCorridorFilter("ALL");
                }
              } else {
                setSelectedNode(null);
              }
            }}
            className="pl-8 pr-3 py-1 bg-slate-800 hover:bg-slate-700/80 border border-slate-700 rounded-lg text-xs text-slate-200 focus:outline-none focus:ring-1 focus:ring-sky-500 appearance-none font-medium cursor-pointer"
            title="Select any station to inspect"
            data-testid="station-selector-dropdown"
          >
            <option value="">Jump to Station... ({NODES.length})</option>
            {NODES.slice().sort((a, b) => a.name.localeCompare(b.name)).map((n) => (
              <option key={n.id} value={n.id}>
                {n.name} ({n.id}) — {n.corridors.join("/")}
              </option>
            ))}
          </select>
        </div>

        <div className="ml-auto flex items-center gap-1">
          <span className="text-[10px] text-slate-400 font-mono mr-2 hidden sm:inline">
            {NODES.length} Stations Modeled
          </span>
          <button
            onClick={() => setZoom((z) => Math.min(4, z * 1.2))}
            className="w-7 h-7 rounded bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 text-sm flex items-center justify-center transition-colors"
          >+</button>
          <button
            onClick={() => setZoom((z) => Math.max(0.3, z * 0.83))}
            className="w-7 h-7 rounded bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 text-sm flex items-center justify-center transition-colors"
          >−</button>
          <button
            onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}
            className="px-2 h-7 rounded bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 text-[10px] transition-colors"
          >⌖ Reset</button>
          <span className="text-[10px] text-slate-500 ml-1 font-mono">{Math.round(zoom * 100)}%</span>
        </div>
      </div>

      {/* ── Main canvas + inspector ── */}
      <div className="flex min-h-0 overflow-hidden" style={{ flex: '1 1 0', minHeight: 0 }}>
        {/* SVG canvas */}
        <div ref={canvasRef} className="flex-1 min-w-0 relative overflow-hidden bg-slate-950">
          <svg
            ref={svgRef}
            className="w-full h-full"
            style={{ cursor: isPanningRef.current ? "grabbing" : "grab" }}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            onWheel={handleWheel}
          >
            <defs>
              <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
                <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#1e293b" strokeWidth="0.5" />
              </pattern>
              <filter id="glow">
                <feGaussianBlur stdDeviation="2" result="coloredBlur" />
                <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            </defs>

            {/* Background grid */}
            <rect width="100%" height="100%" fill="url(#grid)" />

            <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
              {/* ── Edges ── */}
              {ALL_EDGES.map((edge) => {
                const a = NODE_MAP[edge.from];
                const b = NODE_MAP[edge.to];
                if (!a || !b) return null;
                const visible = corridorFilter === "ALL"
                  || edge.corridor === corridorFilter
                  || (visibleNodeIds.has(edge.from) && visibleNodeIds.has(edge.to));
                if (!visible) return null;
                const col = corridorEdgeColor(edge.corridor);
                const isHov = hoveredNode === edge.from || hoveredNode === edge.to;
                return (
                  <line
                    key={`${edge.from}-${edge.to}-${edge.corridor}`}
                    x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                    stroke={col}
                    strokeWidth={isHov ? 2.5 : 1.8}
                    strokeDasharray={edge.dashed ? "5 3" : undefined}
                    opacity={corridorFilter !== "ALL" && edge.corridor !== corridorFilter ? 0.12 : isHov ? 1 : 0.75}
                    strokeLinecap="round"
                  />
                );
              })}

              {/* ── Nodes (EVERY station is clickable) ── */}
              {NODES.map((node) => {
                const visible = visibleNodeIds.has(node.id);
                if (!visible && corridorFilter !== "ALL") return null;
                const style = NODE_STYLES[node.type];
                const isHov = hoveredNode === node.id;
                const isSel = selectedNode === node.id;
                const tc = trainCounts[node.id] || 0;
                const primaryCorridor = node.corridors[0];
                const nodeColor = CORRIDOR_COLOR[primaryCorridor] || "#94a3b8";
                const dim = corridorFilter !== "ALL" && !node.corridors.includes(corridorFilter);

                const isRight = node.x > 900;
                const labelDx = isRight ? -8 : node.type === "STATION" ? 0 : 8;
                const labelAnchor = isRight ? "end" : node.type === "STATION" ? "middle" : "start";
                const labelDy = node.type === "STATION" ? -6 : -9;
                const showLabel = node.type !== "STATION" || isHov || isSel || corridorFilter !== "ALL";

                return (
                  <g
                    key={node.id}
                    data-node-id={node.id}
                    data-testid={`station-node-${node.id}`}
                    style={{ cursor: "pointer" }}
                    onMouseEnter={() => setHoveredNode(node.id)}
                    onMouseLeave={() => setHoveredNode(null)}
                    onClick={() => setSelectedNode(isSel ? null : node.id)}
                  >
                    {/* Enlarged transparent hit area to guarantee effortless clicking on any station */}
                    <circle cx={node.x} cy={node.y} r={Math.max(style.r + 7, 13)} fill="transparent" />

                    {/* Train indicator ring */}
                    {tc > 0 && (
                      <circle
                        cx={node.x} cy={node.y}
                        r={style.r + 4}
                        fill="none"
                        stroke="#facc15"
                        strokeWidth={1.5}
                        opacity={0.7}
                      >
                        <animate attributeName="r" values={`${style.r + 3};${style.r + 6};${style.r + 3}`} dur="1.5s" repeatCount="indefinite" />
                        <animate attributeName="opacity" values="0.7;0.2;0.7" dur="1.5s" repeatCount="indefinite" />
                      </circle>
                    )}

                    {/* Selection ring */}
                    {isSel && (
                      <circle
                        cx={node.x} cy={node.y}
                        r={style.r + 5}
                        fill="none"
                        stroke="#38bdf8"
                        strokeWidth={2}
                        opacity={0.8}
                      />
                    )}

                    {/* Node circle */}
                    <circle
                      cx={node.x} cy={node.y}
                      r={isHov || isSel ? style.r + 1.5 : style.r}
                      fill={isSel ? nodeColor : style.fill}
                      stroke={isSel ? "#38bdf8" : isHov ? nodeColor : style.stroke}
                      strokeWidth={isHov || isSel ? style.sw + 0.5 : style.sw}
                      opacity={dim ? 0.2 : 1}
                      filter={isHov || isSel ? "url(#glow)" : undefined}
                    />

                    {/* Train count badge */}
                    {tc > 0 && (
                      <text
                        x={node.x + style.r + 2}
                        y={node.y - style.r - 1}
                        fontSize={7} fill="#facc15" fontWeight="bold" textAnchor="middle"
                      >
                        {tc}
                      </text>
                    )}

                    {/* Label */}
                    {showLabel && (
                      <text
                        x={node.x + (node.type === "STATION" ? 0 : labelDx)}
                        y={node.y + labelDy}
                        fontSize={node.type === "TERMINUS" ? 9 : node.type === "JUNCTION" ? 8 : node.type === "MAJOR" ? 7.5 : 6.5}
                        fontWeight={node.type === "TERMINUS" || node.type === "JUNCTION" ? "600" : "400"}
                        fill={dim ? "#374151" : isSel ? "#38bdf8" : isHov ? nodeColor : node.type === "STATION" ? "#64748b" : "#cbd5e1"}
                        textAnchor={labelAnchor}
                        style={{ userSelect: "none", pointerEvents: "none" }}
                        filter={isHov || isSel ? "url(#glow)" : undefined}
                      >
                        {node.id}
                      </text>
                    )}
                  </g>
                );
              })}
            </g>
          </svg>

          {/* Hover tooltip */}
          {hoveredNode && !selectedNode && (
            <div className="absolute bottom-3 left-3 pointer-events-none">
              <div className="px-2.5 py-1.5 rounded-lg bg-slate-800/95 border border-slate-700 text-xs text-slate-200 font-mono shadow-xl">
                <span className="text-slate-400 mr-1.5">{hoveredNode}</span>
                {NODE_MAP[hoveredNode]?.name}
                {trainCounts[hoveredNode] ? (
                  <span className="ml-2 text-yellow-400">🚆 {trainCounts[hoveredNode]}</span>
                ) : null}
              </div>
            </div>
          )}

          {/* Legend */}
          <div className="absolute top-2 right-2 bg-slate-900/90 border border-slate-800 rounded-lg p-2 pointer-events-none">
            <div className="text-[9px] text-slate-500 mb-1 font-semibold uppercase tracking-wider">Legend</div>
            {[
              { label: "Terminus",    fill: "#0f172a", stroke: "#e2e8f0" },
              { label: "Junction",    fill: "#1e293b", stroke: "#fbbf24" },
              { label: "Major Stn",   fill: "#1e293b", stroke: "#94a3b8" },
              { label: "Station",     fill: "#334155", stroke: "#475569" },
            ].map((l) => (
              <div key={l.label} className="flex items-center gap-1.5 mb-0.5">
                <svg width="10" height="10">
                  <circle cx="5" cy="5" r="4" fill={l.fill} stroke={l.stroke} strokeWidth="1.5" />
                </svg>
                <span className="text-[9px] text-slate-400">{l.label}</span>
              </div>
            ))}
            <div className="mt-1.5 border-t border-slate-800 pt-1.5">
              <div className="text-[9px] text-slate-500 mb-1 font-semibold uppercase tracking-wider">Corridors</div>
              {CORRIDORS.slice(1).map((c) => (
                <div key={c.id} className="flex items-center gap-1.5 mb-0.5">
                  <div className="w-5 h-1.5 rounded-full" style={{ background: c.color }} />
                  <span className="text-[9px] text-slate-400">{c.label}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Inspector panel (Authoritative station control view) ── */}
        <div 
          className="w-80 md:w-96 min-w-[20rem] md:min-w-[24rem] bg-slate-900 border-l border-slate-800 overflow-y-auto flex-shrink-0 flex flex-col"
          data-testid="station-inspector-panel"
        >
          {selNode ? (
            <div className="p-3.5 space-y-3.5 flex-1">
              {/* Header */}
              <div className="border-b border-slate-800 pb-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="px-2 py-0.5 rounded text-xs font-mono font-bold bg-sky-950 text-sky-400 border border-sky-500/40">
                      {selNode.id}
                    </span>
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${operationalStatus.bg} ${operationalStatus.color}`}>
                      {operationalStatus.label}
                    </span>
                  </div>
                  <button
                    onClick={() => setSelectedNode(null)}
                    className="text-slate-500 hover:text-slate-200 text-xl leading-none px-1 rounded transition-colors"
                    title="Close inspector"
                  >×</button>
                </div>
                <h2 className="text-sm font-bold text-slate-100 mt-1.5 leading-snug">
                  {selNode.name}
                </h2>
                <p className="text-[10px] text-slate-500 font-medium mt-0.5">
                  Chennai Division (MAS) • Southern Railway
                </p>

                {/* Corridor & Category Pills */}
                <div className="flex flex-wrap items-center gap-1.5 mt-2">
                  <span className="px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
                    {stationCategory}
                  </span>
                  {selNode.corridors.map((c) => (
                    <span
                      key={c}
                      className="px-2 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider border"
                      style={{ 
                        background: CORRIDOR_COLOR[c] + "22", 
                        color: CORRIDOR_COLOR[c],
                        borderColor: CORRIDOR_COLOR[c] + "55"
                      }}
                      title={CORRIDOR_FULL_NAMES[c] || c}
                    >
                      {c} Corridor
                    </span>
                  ))}
                </div>
              </div>

              {/* Sub-navigation tabs */}
              <div className="flex items-center gap-1 p-0.5 bg-slate-950 rounded-lg border border-slate-800 text-[10px] font-semibold">
                {(["ALL", "OVERVIEW", "ROUTES", "TIMETABLE", "LIVE"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setInspectorTab(tab)}
                    className={`flex-1 py-1 rounded transition-all text-center ${
                      inspectorTab === tab
                        ? "bg-sky-600 text-white shadow-sm"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/60"
                    }`}
                  >
                    {tab === "ALL" ? "All" : tab === "OVERVIEW" ? "Info" : tab === "ROUTES" ? "Tracks" : tab === "TIMETABLE" ? "Sched" : "Live"}
                  </button>
                ))}
              </div>

              {/* ── Section: Overview / Identity & Platforms ── */}
              {(inspectorTab === "ALL" || inspectorTab === "OVERVIEW") && (
                <div className="space-y-3">
                  {/* Platforms */}
                  <div className="bg-slate-950/60 rounded-xl p-2.5 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Layers className="w-3 h-3 text-sky-400" />
                        Platforms ({platformCount})
                      </span>
                      <span className="text-[9px] font-mono text-slate-500">
                        Total Count: {platformCount}
                      </span>
                    </div>

                    {stationPlatforms.length > 0 ? (
                      <div className="grid grid-cols-2 gap-1.5">
                        {stationPlatforms.map((p) => (
                          <div key={p.id} className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 text-[10px]">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-slate-200">PF {p.platform_number}</span>
                              <span className="text-[9px] text-sky-400 font-mono">{p.platform_type}</span>
                            </div>
                            <p className="text-[9px] text-slate-500 mt-0.5">Cap: {p.capacity} Rakes</p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-[10px] text-slate-400 italic">
                        {platformCount} Standard Multi-Track Platform Lines (Up & Down Suburban/Mainline)
                      </p>
                    )}
                  </div>

                  {/* Junction / Interlocking */}
                  {selJunction ? (
                    <div className="bg-amber-950/20 border border-amber-600/30 rounded-xl p-2.5 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
                          <GitBranch className="w-3 h-3 text-amber-400" />
                          Junction & Interlocking
                        </span>
                        <span className="px-1.5 py-0.2 rounded bg-amber-900/40 text-amber-300 text-[9px] font-mono">
                          {selJunction.id}
                        </span>
                      </div>
                      <div className="text-[11px] space-y-1">
                        <p className="text-slate-200 font-medium">{selJunction.name}</p>
                        <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[10px]">
                          <span className="text-slate-500">Throat Type:</span>
                          <span className="text-amber-300 font-semibold">{selJunction.junction_type}</span>
                          <span className="text-slate-500">Throat Capacity:</span>
                          <span className="text-slate-300">{selJunction.capacity} Block Limit</span>
                        </div>
                        {selJunction.description && (
                          <p className="text-[10px] text-slate-400 leading-relaxed border-t border-amber-800/30 pt-1.5 mt-1">
                            {selJunction.description}
                          </p>
                        )}
                        {selJunction.connected_routes && selJunction.connected_routes.length > 0 && (
                          <div className="border-t border-amber-800/30 pt-1.5 mt-1">
                            <span className="text-[9px] text-slate-500 font-medium">Interlocking Routes:</span>
                            <div className="flex flex-wrap gap-1 mt-1">
                              {selJunction.connected_routes.map((r) => (
                                <span key={r} className="px-1.5 py-0.5 rounded bg-amber-900/40 text-amber-300 text-[8px] font-mono">
                                  {r.replace("RT_", "")}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  ) : (
                    <div className="bg-slate-950/40 border border-slate-800 rounded-xl p-2.5 space-y-1">
                      <div className="flex items-center gap-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                        <CheckCircle2 className="w-3 h-3 text-slate-500" />
                        Interlocking Classification
                      </div>
                      <p className="text-[10px] text-slate-400">
                        Standard Intermediate Block Station • Automatic Block Territory with track-circuit detection.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {/* ── Section: Routes & Track Sections ── */}
              {(inspectorTab === "ALL" || inspectorTab === "ROUTES") && (
                <div className="space-y-3">
                  {/* Connected Routes */}
                  <div className="bg-slate-950/60 rounded-xl p-2.5 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <GitBranch className="w-3 h-3 text-cyan-400" />
                        Connected Routes ({connectedRoutes.length})
                      </span>
                    </div>

                    {connectedRoutes.length > 0 ? (
                      <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                        {connectedRoutes.map((r) => {
                          const stopIdx = r.ordered_nodes.indexOf(selNode.id);
                          const isOrigin = stopIdx === 0;
                          const isTerminus = stopIdx === r.ordered_nodes.length - 1;
                          return (
                            <div key={r.id} className="p-2 rounded-lg bg-slate-900 border border-slate-800/80 text-[10px]">
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-slate-200 truncate">{r.name}</span>
                                <span className="px-1.5 py-0.2 rounded bg-slate-800 text-[8px] text-slate-400 font-mono">
                                  {r.service_type}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-[9px] text-slate-400 mt-1">
                                <span>{r.origin} → {r.destination}</span>
                                <span className="font-semibold text-sky-400">
                                  {isOrigin ? "Origin" : isTerminus ? "Terminus" : `Stop ${stopIdx + 1} of ${r.ordered_nodes.length}`}
                                </span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-[10px] text-slate-500 italic">No direct corridor route registrations.</p>
                    )}
                  </div>

                  {/* Connected Track Sections */}
                  <div className="bg-slate-950/60 rounded-xl p-2.5 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Activity className="w-3 h-3 text-sky-400" />
                        Track Sections ({connectedSections.length})
                      </span>
                    </div>

                    {connectedSections.length > 0 ? (
                      <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                        {connectedSections.map((ts) => {
                          const otherNode = ts.from_node === selNode.id ? ts.to_node : ts.from_node;
                          return (
                            <div key={ts.id} className="p-2 rounded-lg bg-slate-900 border border-slate-800/80 text-[10px]">
                              <div className="flex items-center justify-between">
                                <span className="font-mono text-slate-300 truncate font-semibold">{ts.id}</span>
                                <span className="text-[9px] px-1 py-0.2 rounded bg-slate-800 text-slate-400">
                                  {ts.direction || "BIDIR"}
                                </span>
                              </div>
                              <div className="grid grid-cols-2 gap-x-2 gap-y-0.5 text-[9px] text-slate-400 mt-1">
                                <span>Link: {selNode.id} ↔ {otherNode}</span>
                                <span>Runtime: {ts.travel_time_minutes}m</span>
                                <span>Type: {ts.track_type}</span>
                                <span>Headway: {ts.minimum_headway_minutes}m</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-[10px] text-slate-500 italic">No individual track section objects registered.</p>
                    )}
                  </div>

                  {/* Adjacent Topological Stations */}
                  <div className="bg-slate-950/60 rounded-xl p-2.5 border border-slate-800 space-y-2">
                    <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                      <ArrowRight className="w-3 h-3 text-emerald-400" />
                      Adjacent Stations
                    </span>
                    <div className="space-y-1">
                      {ALL_EDGES
                        .filter((e) => e.from === selNode.id || e.to === selNode.id)
                        .map((e) => {
                          const other = e.from === selNode.id ? e.to : e.from;
                          const otherNode = NODE_MAP[other];
                          return (
                            <button
                              key={`${e.from}-${e.to}`}
                              onClick={() => setSelectedNode(other)}
                              className="w-full flex items-center justify-between px-2 py-1.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 transition-colors text-left"
                            >
                              <div className="flex items-center gap-2">
                                <div
                                  className="w-2 h-2 rounded-full flex-shrink-0"
                                  style={{ background: CORRIDOR_COLOR[e.corridor] }}
                                />
                                <span className="text-[10px] text-slate-200 font-mono font-bold">{other}</span>
                                <span className="text-[9px] text-slate-400 truncate max-w-[120px]">{otherNode?.name}</span>
                              </div>
                              <span className="text-[9px] text-sky-400 font-medium">Inspect ↗</span>
                            </button>
                          );
                        })}
                    </div>
                  </div>
                </div>
              )}

              {/* ── Section: Services & Timetable ── */}
              {(inspectorTab === "ALL" || inspectorTab === "TIMETABLE") && (
                <div className="space-y-3">
                  {/* Station Timetable */}
                  <div className="bg-slate-950/60 rounded-xl p-2.5 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Clock className="w-3 h-3 text-amber-400" />
                        Station Timetable ({stationTimetable.length} Stops)
                      </span>
                    </div>

                    {stationTimetable.length > 0 ? (
                      <div className="space-y-1.5 max-h-56 overflow-y-auto pr-1">
                        {stationTimetable.map((tt) => {
                          const svc = network.services.find((s) => s.id === tt.service_id);
                          const tType = svc?.train_type || "SUBURBAN_EMU";
                          const badge = TRAIN_TYPE_BADGES[tType] || { bg: "bg-slate-800", text: "text-slate-300", border: "border-slate-700", label: "TR" };
                          return (
                            <div key={`${tt.service_id}-${tt.stop_sequence}`} className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-[10px]">
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-200 truncate">
                                  {svc?.train_name || tt.service_id}
                                </span>
                                <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold border ${badge.bg} ${badge.text} ${badge.border}`}>
                                  {badge.label}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-[9px] text-slate-400 mt-1 font-mono">
                                <span>Arr: {tt.arrival || "--:--"}</span>
                                <span>Dep: {tt.departure || "--:--"}</span>
                                <span className="text-slate-500">Stop #{tt.stop_sequence}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-[10px] text-slate-500 italic">
                        No scheduled passenger dwells; trains transit continuously via block sections.
                      </p>
                    )}
                  </div>

                  {/* Associated Services */}
                  <div className="bg-slate-950/60 rounded-xl p-2.5 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Train className="w-3 h-3 text-purple-400" />
                        Associated Services ({associatedServices.length})
                      </span>
                    </div>

                    {associatedServices.length > 0 ? (
                      <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                        {associatedServices.map((svc) => {
                          const tType = svc.train_type || "SUBURBAN_EMU";
                          const badge = TRAIN_TYPE_BADGES[tType] || { bg: "bg-slate-800", text: "text-slate-300", border: "border-slate-700", label: "TR" };
                          return (
                            <div key={svc.id} className="p-2 rounded-lg bg-slate-900 border border-slate-800 text-[10px]">
                              <div className="flex items-center justify-between">
                                <span className="font-semibold text-slate-200 truncate">
                                  {svc.train_name || svc.id}
                                </span>
                                <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold border ${badge.bg} ${badge.text} ${badge.border}`}>
                                  {badge.label}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-[9px] text-slate-400 mt-1">
                                <span>{svc.origin} → {svc.destination}</span>
                                <span className="font-mono text-slate-500">Pri: {svc.priority_class}</span>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-[10px] text-slate-500 italic">No services routed through this node.</p>
                    )}
                  </div>
                </div>
              )}

              {/* ── Section: Live Operational State ── */}
              {(inspectorTab === "ALL" || inspectorTab === "LIVE") && (
                <div className="space-y-3">
                  {/* Active Conflicts */}
                  {activeConflictsAtStation.length > 0 && (
                    <div className="bg-rose-950/40 border border-rose-500/50 rounded-xl p-2.5 space-y-2">
                      <div className="flex items-center gap-1.5 text-[10px] font-bold text-rose-300 uppercase tracking-wider">
                        <ShieldAlert className="w-3.5 h-3.5 text-rose-400 animate-pulse" />
                        Active Station Conflicts ({activeConflictsAtStation.length})
                      </div>
                      <div className="space-y-1.5">
                        {activeConflictsAtStation.map((c) => (
                          <div key={c.conflict_id} className="p-2 rounded-lg bg-rose-900/30 border border-rose-500/30 text-[10px]">
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-rose-200">{c.conflict_type}</span>
                              <span className="px-1.5 py-0.2 rounded bg-rose-900/60 text-rose-300 text-[8px] font-bold">
                                {c.severity}
                              </span>
                            </div>
                            <p className="text-[9px] text-rose-300/80 mt-1">{c.description}</p>
                            <p className="text-[8px] font-mono text-rose-400 mt-0.5">
                              Trains: {c.affected_service_ids?.join(", ")}
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Live Trains */}
                  <div className="bg-slate-950/60 rounded-xl p-2.5 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                        <Activity className="w-3 h-3 text-yellow-400" />
                        Active Trains at Station ({liveTrainsAtStation.length})
                      </span>
                      {simulationTime && (
                        <span className="text-[9px] font-mono text-slate-500">Clock: {simulationTime}</span>
                      )}
                    </div>

                    {liveTrainsAtStation.length > 0 ? (
                      <div className="space-y-1.5">
                        {liveTrainsAtStation.map((t) => {
                          const badge = TRAIN_TYPE_BADGES[t.train_type || ""] || { bg: "bg-slate-800", text: "text-slate-300", border: "border-slate-700", label: "TR" };
                          return (
                            <div key={t.service_id} className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[10px] space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="font-bold text-slate-100">{t.train_name}</span>
                                <span className={`px-1.5 py-0.2 rounded text-[8px] font-bold border ${badge.bg} ${badge.text} ${badge.border}`}>
                                  {badge.label}
                                </span>
                              </div>
                              <div className="flex items-center justify-between text-[9px]">
                                <span className="text-slate-400">Status: <strong className="text-slate-200">{t.status}</strong></span>
                                <span className={`font-mono font-bold ${t.delay_minutes > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                                  {t.delay_minutes > 0 ? `+${t.delay_minutes}m delay` : "On-Time"}
                                </span>
                              </div>
                              {t.current_track_section && (
                                <p className="text-[8px] font-mono text-slate-500">
                                  Section: {t.current_track_section}
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="p-3 rounded-lg bg-slate-900/50 border border-slate-800/60 text-center">
                        <p className="text-[10px] text-slate-400">No active trains currently dwelling or held at this station.</p>
                        <p className="text-[9px] text-slate-600 mt-0.5 font-mono">Platform tracks clear</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div 
              className="p-6 flex flex-col items-center justify-center h-full gap-3 text-center"
              data-testid="inspector-empty-state"
            >
              <div className="w-10 h-10 rounded-full bg-slate-800/80 border border-slate-700 flex items-center justify-center text-sky-400 text-lg shadow-inner">
                <MapPin className="w-5 h-5 text-sky-400" />
              </div>
              <div>
                <p className="text-xs font-semibold text-slate-200">Division Station Inspector</p>
                <p className="text-[11px] text-slate-500 mt-1 max-w-[200px] leading-relaxed">
                  Click any station node on the map or select from the dropdown above to inspect authoritative topology, routes, timetable, platforms, and operational state.
                </p>
              </div>
              <div className="w-full border-t border-slate-800/80 pt-3 mt-2 grid grid-cols-2 gap-2 text-left">
                <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800 text-[10px]">
                  <span className="text-slate-500 block">Total Stations</span>
                  <span className="text-slate-200 font-bold font-mono">{NODES.length}</span>
                </div>
                <div className="p-2 rounded-lg bg-slate-950/60 border border-slate-800 text-[10px]">
                  <span className="text-slate-500 block">Visible</span>
                  <span className="text-sky-400 font-bold font-mono">{NODES.filter((n) => visibleNodeIds.has(n.id)).length}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
