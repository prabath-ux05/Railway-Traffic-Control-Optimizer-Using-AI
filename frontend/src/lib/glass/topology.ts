/**
 * Spatial geometry of the Chennai Division network for the Glass Spatial dashboard.
 * Node coordinates and corridor sequences are copied verbatim from components/NetworkTopologyView.tsx
 * (which the test suite pins), so both maps draw the same division.
 */

export type CorridorId = "WEST" | "NORTH" | "SOUTH" | "MRTS" | "BYPASS" | "PTMS" | "CROSS";

export interface NodeDef {
  id: string;
  name: string;
  x: number;
  y: number;
  type: "TERMINUS" | "JUNCTION" | "MAJOR" | "STATION";
  corridors: string[];
}

export const NODES: NodeDef[] = [
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

export const NODE_MAP: Record<string, NodeDef> = Object.fromEntries(NODES.map((n) => [n.id, n]));

/** Ordered station sequences per corridor (from routes.json). */
export const CORRIDOR_SEQUENCES: { corridor: CorridorId; nodes: string[] }[] = [
  { corridor: "WEST", nodes: ["MAS","BBQ","VJM","PER","PCW","PEW","VLK","KOTR","PVM","ABU","TMVL","ANNR","AVD","HC","PAB","NEC","TI","VEU","SVR","PTLR","TRL","EGT","KBT","SPAM","MAF","TO","MSU","PLMG","AJJ"] },
  { corridor: "PTMS", nodes: ["PAB","PTMS"] },
  { corridor: "NORTH", nodes: ["BBQ","KOK","TNPM","VOCN","TVT","WCN","KAVM","ENR","AIP","ATU","NPKM","MJR","APB","PON","KVP","GPD","ELR","AKM","TADA","AKAT","SPE"] },
  { corridor: "BYPASS", nodes: ["MSB","RPM","WST","KOK"] },
  { corridor: "SOUTH", nodes: ["MSB","MSF","MPK","MS","MSC","NBK","MKK","MBM","SP","GDY","STM","PZA","MN","TLM","PV","CMP","TBMS","TBM","PRGL","VDR","UPM","GI","POT","CTM","MMNK","SKL","PWU","CGL"] },
  { corridor: "MRTS", nodes: ["MSB","MSF","MPKT","MCPT","MCPK","MTCN","MLHS","MKAK","MTMY","MYND","MNDY","GWYR","KTPM","KTBR","INDR","TYMR","TRMN","PRGD","VLCY"] },
  { corridor: "CROSS", nodes: ["CGL","RDY","VAM","PALR","PJS","WJ","NTT","CJE","CJ","TMLP","TKO","AJJ"] },
];

export const CORRIDORS: { id: CorridorId; label: string; full: string; color: string; serviceKey: string }[] = [
  { id: "WEST", label: "West", full: "West Mainline · MAS – AJJ", color: "#E8C79E", serviceKey: "West" },
  { id: "NORTH", label: "North", full: "North Corridor · BBQ – SPE", color: "#8FB2FF", serviceKey: "North" },
  { id: "SOUTH", label: "South", full: "South Mainline · MSB – CGL", color: "#63D7A8", serviceKey: "South" },
  { id: "MRTS", label: "MRTS", full: "MRTS Elevated · MSB – VLCY", color: "#B79BFF", serviceKey: "MRTS" },
  { id: "BYPASS", label: "Bypass", full: "Beach–North Bypass · MSB – KOK", color: "#F2B45A", serviceKey: "Beach–North Bypass" },
  { id: "PTMS", label: "PTMS", full: "PTMS Branch · PAB – PTMS", color: "#F59AB5", serviceKey: "PTMS" },
  { id: "CROSS", label: "Cross", full: "Cross Line · CGL – AJJ", color: "#7FD6E6", serviceKey: "Cross" },
];

export const CORRIDOR_BY_ID: Record<string, (typeof CORRIDORS)[number]> = Object.fromEntries(CORRIDORS.map((c) => [c.id, c]));

/** Map a service's corridor label (e.g. "Beach–North Bypass") to a corridor id. */
export function corridorIdFromLabel(label?: string | null): CorridorId | null {
  if (!label) return null;
  const hit = CORRIDORS.find((c) => c.serviceKey.toLowerCase() === label.toLowerCase() || c.label.toLowerCase() === label.toLowerCase());
  return hit ? hit.id : null;
}

export interface EdgeDef {
  from: string;
  to: string;
  corridor: CorridorId;
  dashed?: boolean;
}

function buildEdges(): EdgeDef[] {
  const seen = new Set<string>();
  const edges: EdgeDef[] = [];
  for (const { corridor, nodes } of CORRIDOR_SEQUENCES) {
    for (let i = 0; i < nodes.length - 1; i++) {
      const a = nodes[i];
      const b = nodes[i + 1];
      const key = [a, b].sort().join(":");
      if (seen.has(key)) continue;
      seen.add(key);
      edges.push({ from: a, to: b, corridor });
    }
  }
  // Beach-side divergence at VJM (junction description, not an explicit route sequence).
  if (!seen.has(["VJM", "WST"].sort().join(":"))) edges.push({ from: "VJM", to: "WST", corridor: "BYPASS", dashed: true });
  return edges;
}

export const EDGES: EdgeDef[] = buildEdges();

export const MAP_BOUNDS = (() => {
  const xs = NODES.map((n) => n.x);
  const ys = NODES.map((n) => n.y);
  return { minX: Math.min(...xs), maxX: Math.max(...xs), minY: Math.min(...ys), maxY: Math.max(...ys) };
})();

/** Corridor a node primarily belongs to (first listed). */
export function primaryCorridor(nodeId: string): CorridorId | null {
  const n = NODE_MAP[nodeId];
  return n ? (n.corridors[0] as CorridorId) : null;
}
