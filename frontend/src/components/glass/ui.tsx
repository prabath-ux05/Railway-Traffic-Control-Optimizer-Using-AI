"use client";

import React from "react";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, ChevronRight, Loader2, Minus, RefreshCw } from "lucide-react";
import { cx } from "@/lib/glass/format";

/* ───────── Surfaces ───────── */

export function Panel({
  children,
  className,
  as: Tag = "section",
  ...rest
}: { children: React.ReactNode; className?: string; as?: React.ElementType } & React.HTMLAttributes<HTMLElement>) {
  return (
    <Tag className={cx("glass relative", className)} {...rest}>
      {children}
    </Tag>
  );
}

export function SectionHead({ title, description, actions, level = 2, className }: { title: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode; level?: 1 | 2 | 3; className?: string }) {
  const H = (level === 1 ? "h1" : level === 2 ? "h2" : "h3") as React.ElementType;
  const size = level === 1 ? "text-[2rem] sm:text-[2.5rem] leading-[1.08] tracking-[-0.03em]" : level === 2 ? "text-[1.375rem] sm:text-[1.75rem] leading-[1.15] tracking-[-0.02em]" : "text-[1.1875rem] leading-[1.3] tracking-[-0.01em]";
  return (
    <div className={cx("flex flex-wrap items-end justify-between gap-x-6 gap-y-3", className)}>
      <div className="min-w-0 max-w-[68ch]">
        <H className={cx("font-semibold text-fg-1 text-balance", size)}>{title}</H>
        {description ? <p className="mt-2 text-[0.9375rem] leading-relaxed text-fg-2">{description}</p> : null}
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

/* ───────── Numbers ───────── */

export function Numeral({ value, unit, size = "l", className, tone }: { value: React.ReactNode; unit?: string; size?: "xl" | "l" | "m" | "s"; className?: string; tone?: "default" | "clear" | "caution" | "conflict" | "violet" | "bronze" | "champagne" }) {
  const sz = size === "xl" ? "text-[2.75rem] sm:text-[3.5rem]" : size === "l" ? "text-[2.125rem] sm:text-[2.5rem]" : size === "m" ? "text-[1.75rem]" : "text-[1.25rem]";
  const color =
    tone === "clear" ? "text-clear" : tone === "caution" ? "text-caution" : tone === "conflict" ? "text-conflict" : tone === "violet" ? "text-[#b3a2ff]" : tone === "bronze" ? "text-[#dcae84]" : tone === "champagne" ? "text-champagne" : "text-fg-1";
  return (
    <span className={cx("numeral", sz, color, className)}>
      {value}
      {unit ? <span className="unit">{unit}</span> : null}
    </span>
  );
}

export function Stat({ label, value, unit, hint, tone, size = "m", className }: { label: string; value: React.ReactNode; unit?: string; hint?: React.ReactNode; tone?: React.ComponentProps<typeof Numeral>["tone"]; size?: React.ComponentProps<typeof Numeral>["size"]; className?: string }) {
  return (
    <div className={cx("flex min-w-0 flex-col gap-2", className)}>
      <span className="label">{label}</span>
      <Numeral value={value} unit={unit} size={size} tone={tone} />
      {hint ? <span className="text-[0.8125rem] leading-snug text-fg-2">{hint}</span> : null}
    </div>
  );
}

/** Delta chip coloured by meaning (good/bad), not by sign. */
export function DeltaChip({ value, unit = "", good, digits = 0, title }: { value: number | null | undefined; unit?: string; good?: boolean | null; digits?: number; title?: string }) {
  if (value === null || value === undefined || Number.isNaN(value)) return <span className="chip">—</span>;
  const zero = Math.abs(value) < 1e-9;
  const Icon = zero ? Minus : value > 0 ? ArrowUpRight : ArrowDownRight;
  const color = zero || good === null || good === undefined ? "text-fg-2" : good ? "text-clear border-[rgba(99,215,168,0.32)]" : "text-conflict border-[rgba(242,106,91,0.35)]";
  const abs = Math.abs(value).toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
  return (
    <span className={cx("chip", color)} title={title}>
      <Icon className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
      {value > 0 ? "+" : value < 0 ? "−" : ""}
      {abs}
      {unit}
    </span>
  );
}

type StatusKind = "clear" | "caution" | "conflict" | "info" | "muted" | "violet";
const STATUS_STYLE: Record<StatusKind, { dot: string; text: string; border: string }> = {
  clear: { dot: "bg-clear", text: "text-clear", border: "border-[rgba(99,215,168,0.3)]" },
  caution: { dot: "bg-caution", text: "text-caution", border: "border-[rgba(242,180,90,0.32)]" },
  conflict: { dot: "bg-conflict", text: "text-conflict", border: "border-[rgba(242,106,91,0.38)]" },
  info: { dot: "bg-info", text: "text-info", border: "border-[rgba(143,178,255,0.3)]" },
  violet: { dot: "bg-violet", text: "text-[#b3a2ff]", border: "border-[rgba(139,108,255,0.35)]" },
  muted: { dot: "bg-fg-3", text: "text-fg-2", border: "border-line" },
};

export function StatusChip({ kind, children, className }: { kind: StatusKind; children: React.ReactNode; className?: string }) {
  const s = STATUS_STYLE[kind];
  return (
    <span className={cx("chip", s.text, s.border, kind === "conflict" && "hatch", className)}>
      <span className={cx("h-1.5 w-1.5 rounded-full", s.dot)} aria-hidden />
      {children}
    </span>
  );
}

export function trainStatusKind(status?: string | null, delay = 0): StatusKind {
  const st = (status || "").toUpperCase();
  if (st === "HELD") return "caution";
  if (st === "ARRIVED" || st === "COMPLETED") return "muted";
  if (st === "SCHEDULED" || st === "NOT_STARTED") return delay > 0 ? "caution" : "info";
  return delay >= 5 ? "caution" : "clear";
}

export function trainStatusLabel(status?: string | null, delay = 0): string {
  const st = (status || "").toUpperCase();
  if (st === "HELD") return "Held";
  if (st === "ARRIVED" || st === "COMPLETED") return "Arrived";
  if (st === "SCHEDULED" || st === "NOT_STARTED") return delay > 0 ? `Due +${Math.round(delay)}m` : "Scheduled";
  if (st === "DWELLING" || st === "AT_STATION") return delay >= 5 ? `At platform +${Math.round(delay)}m` : "At platform";
  return delay >= 5 ? `Running +${Math.round(delay)}m` : "On time";
}

/* ───────── Navigation & controls ───────── */

export function Breadcrumb({ items }: { items: { label: string; onClick?: () => void }[] }) {
  return (
    <nav aria-label="Location" className="flex min-w-0 items-center gap-1.5 text-[0.9375rem]">
      {items.map((it, i) => {
        const last = i === items.length - 1;
        return (
          <React.Fragment key={`${it.label}-${i}`}>
            {i > 0 ? <ChevronRight className="h-4 w-4 shrink-0 text-fg-3" aria-hidden /> : null}
            {last || !it.onClick ? (
              <span className={cx("truncate", last ? "font-medium text-fg-1" : "font-light text-fg-3")} aria-current={last ? "location" : undefined}>
                {it.label}
              </span>
            ) : (
              <button type="button" onClick={it.onClick} className="truncate font-light text-fg-3 transition-colors hover:text-fg-1">
                {it.label}
              </button>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}

export function Segmented<T extends string | number>({ options, value, onChange, label, size = "md", className }: { options: { value: T; label: React.ReactNode; title?: string }[]; value: T; onChange: (v: T) => void; label: string; size?: "sm" | "md"; className?: string }) {
  return (
    <div role="group" aria-label={label} className={cx("seg max-w-full overflow-x-auto", className)}>
      {options.map((o) => (
        <button key={String(o.value)} type="button" title={o.title} aria-pressed={o.value === value} onClick={() => onChange(o.value)} className={cx("seg-item", size === "sm" && "!px-3 !py-1.5 !text-[0.75rem]")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Switch({ checked, onChange, label, description, id }: { checked: boolean; onChange: (v: boolean) => void; label: string; description?: string; id: string }) {
  return (
    <div className="flex items-start justify-between gap-6 py-4">
      <div className="min-w-0">
        <label htmlFor={id} className="text-[0.9375rem] font-medium text-fg-1">
          {label}
        </label>
        {description ? <p className="mt-1 max-w-[60ch] text-[0.8125rem] leading-relaxed text-fg-2">{description}</p> : null}
      </div>
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cx(
          "relative mt-0.5 inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors duration-200",
          checked ? "border-transparent bg-[linear-gradient(100deg,var(--magenta),var(--indigo))]" : "border-line-strong bg-ink-2",
        )}
      >
        <span className={cx("inline-block h-4 w-4 rounded-full bg-white shadow transition-transform duration-200 [transition-timing-function:var(--ease-out)]", checked ? "translate-x-[22px]" : "translate-x-[3px]")} />
      </button>
    </div>
  );
}

export function FieldLabel({ htmlFor, children, hint }: { htmlFor?: string; children: React.ReactNode; hint?: React.ReactNode }) {
  return (
    <div className="mb-1.5 flex items-baseline justify-between gap-3">
      <label htmlFor={htmlFor} className="text-[0.8125rem] font-medium text-fg-2">
        {children}
      </label>
      {hint ? <span className="text-[0.75rem] text-fg-3">{hint}</span> : null}
    </div>
  );
}

/* ───────── States ───────── */

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cx("spin h-4 w-4", className)} aria-hidden />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} aria-hidden />;
}

export function ErrorState({ message, onRetry, compact }: { message: string; onRetry?: () => void; compact?: boolean }) {
  return (
    <div role="alert" className={cx("flex items-start gap-3 rounded-[14px] border border-[rgba(242,106,91,0.35)] bg-[rgba(242,106,91,0.07)]", compact ? "p-3" : "p-4")}>
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-conflict" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="text-[0.875rem] leading-relaxed text-fg-1">{message}</p>
      </div>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="btn btn-quiet btn-sm shrink-0">
          <RefreshCw className="h-3.5 w-3.5" aria-hidden /> Retry
        </button>
      ) : null}
    </div>
  );
}

export function EmptyState({ title, body, action, icon }: { title: string; body?: React.ReactNode; action?: React.ReactNode; icon?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 px-6 py-12 text-center">
      {icon ? <div className="grid h-12 w-12 place-items-center rounded-full border border-line text-fg-2">{icon}</div> : null}
      <p className="text-[1rem] font-medium text-fg-1">{title}</p>
      {body ? <p className="max-w-[48ch] text-[0.875rem] leading-relaxed text-fg-2">{body}</p> : null}
      {action}
    </div>
  );
}

export function Legend({ items }: { items: { color: string; label: string; dashed?: boolean; hatch?: boolean }[] }) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-2">
      {items.map((it) => (
        <li key={it.label} className="flex items-center gap-2 text-[0.75rem] text-fg-2">
          {it.hatch ? (
            <span className="hatch inline-block h-2.5 w-4 rounded-[3px] border border-[rgba(242,106,91,0.5)]" aria-hidden />
          ) : (
            <span className="inline-block h-0 w-4" style={{ borderTop: `2px ${it.dashed ? "dashed" : "solid"} ${it.color}` }} aria-hidden />
          )}
          {it.label}
        </li>
      ))}
    </ul>
  );
}
