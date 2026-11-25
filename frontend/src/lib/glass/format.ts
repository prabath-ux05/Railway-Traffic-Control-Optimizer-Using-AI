export const SHIFTS = [
  { id: "S1", label: "Shift 1", window: "06:00 – 12:00", start: 360, end: 720 },
  { id: "S2", label: "Shift 2", window: "12:00 – 18:00", start: 720, end: 1080 },
  { id: "S3", label: "Shift 3", window: "18:00 – 24:00", start: 1080, end: 1440 },
  { id: "S4", label: "Shift 4", window: "00:00 – 06:00", start: 0, end: 360 },
] as const;

export type ShiftId = (typeof SHIFTS)[number]["id"];

export const SPEEDS = [1, 2, 5, 10, 30, 60] as const;

export function toMinutes(hhmm?: string | null): number | null {
  if (!hhmm) return null;
  const m = /^(\d{1,2}):(\d{2})/.exec(hhmm);
  if (!m) return null;
  return Number(m[1]) * 60 + Number(m[2]);
}

export function fmtClock(minutes: number | null | undefined, withSeconds = false): string {
  if (minutes === null || minutes === undefined || Number.isNaN(minutes)) return "—";
  const total = ((minutes % 1440) + 1440) % 1440;
  const h = Math.floor(total / 60);
  const m = Math.floor(total % 60);
  const base = `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  if (!withSeconds) return base;
  const s = Math.round((total - Math.floor(total)) * 60);
  return `${base}:${String(s).padStart(2, "0")}`;
}

export function fmtNum(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function fmtSigned(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  const s = fmtNum(Math.abs(value), digits);
  if (value > 0) return `+${s}`;
  if (value < 0) return `−${s}`;
  return s;
}

export function pct(part: number, whole: number): number {
  if (!whole) return 0;
  return (part / whole) * 100;
}

export function trainNumber(trainId?: string | null): string {
  if (!trainId) return "—";
  return trainId.replace(/^TR_/, "");
}

export function serviceShort(serviceId?: string | null): string {
  if (!serviceId) return "—";
  return serviceId.replace(/^SRV_/, "").replace(/_01$/, "");
}

export const TRAIN_TYPE_LABEL: Record<string, string> = {
  SUBURBAN_EMU: "Suburban EMU",
  EXPRESS: "Express",
  INTERCITY: "Intercity",
  LONG_DISTANCE: "Long distance",
};

export const TRAIN_TYPE_COLOR: Record<string, string> = {
  SUBURBAN_EMU: "#63D7A8",
  EXPRESS: "#E8C79E",
  INTERCITY: "#8FB2FF",
  LONG_DISTANCE: "#B79BFF",
};

export function shiftForMinute(minute: number) {
  return SHIFTS.find((s) => minute >= s.start && minute < s.end) ?? SHIFTS[0];
}

export function istNow(): Date {
  const now = new Date();
  const utc = now.getTime() + now.getTimezoneOffset() * 60000;
  return new Date(utc + 330 * 60000);
}

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}
