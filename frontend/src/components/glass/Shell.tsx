"use client";

import React, { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { CircleHelp, Cpu, FileDown, FlaskConical, Home, LogOut, Pause, Play, Settings2, UserRound, Waypoints } from "lucide-react";
import { useLive } from "@/lib/glass/live";
import { cx, fmtClock, istNow } from "@/lib/glass/format";
import { useTour } from "./Tour";

export const DESTINATIONS = [
  { href: "/", label: "Home", icon: Home },
  { href: "/network", label: "Network", icon: Waypoints },
  { href: "/optimizer", label: "Optimizer", icon: Cpu },
  { href: "/what-if", label: "What-If", icon: FlaskConical },
  { href: "/export", label: "Export", icon: FileDown },
] as const;

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export function BrandMark({ className }: { className?: string }) {
  // Two rails converging on a junction node: the division's network reduced to its mark.
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden>
      <defs>
        <linearGradient id="bm-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#C04BD8" />
          <stop offset="1" stopColor="#4F5BFF" />
        </linearGradient>
      </defs>
      <rect x="1" y="1" width="30" height="30" rx="9" fill="url(#bm-g)" opacity="0.18" />
      <rect x="1.5" y="1.5" width="29" height="29" rx="8.5" fill="none" stroke="rgba(255,240,224,0.22)" />
      <path d="M6 24 L16 14 L26 24" fill="none" stroke="#E8C79E" strokeWidth="2" strokeLinecap="round" />
      <path d="M16 14 L16 6" fill="none" stroke="#8FB2FF" strokeWidth="2" strokeLinecap="round" />
      <circle cx="16" cy="14" r="3.2" fill="#0A090C" stroke="#F4EFE8" strokeWidth="1.6" />
    </svg>
  );
}

export function Avatar({ name, image, size = 32 }: { name?: string | null; image?: string | null; size?: number }) {
  const initials = (name || "Guest")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
  if (image) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={image} alt="" width={size} height={size} referrerPolicy="no-referrer" className="rounded-full border border-line-strong object-cover" style={{ width: size, height: size }} />;
  }
  return (
    <span
      className="grid place-items-center rounded-full border border-line-strong bg-[linear-gradient(135deg,rgba(192,75,216,0.55),rgba(79,91,255,0.55))] font-semibold text-white"
      style={{ width: size, height: size, fontSize: size * 0.38 }}
      aria-hidden
    >
      {initials || "G"}
    </span>
  );
}

function LiveClock() {
  const { state } = useLive();
  const [ist, setIst] = useState<string>("");
  useEffect(() => {
    const tick = () => {
      const d = istNow();
      setIst(`${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`);
    };
    tick();
    const id = window.setInterval(tick, 15000);
    return () => window.clearInterval(id);
  }, []);
  const playing = state?.is_playing;
  return (
    <div data-tour="live-clock" className="hidden items-center gap-3 rounded-full border border-line px-3 py-1.5 lg:flex" aria-live="off">
      <span className="flex items-center gap-1.5 text-[0.75rem] text-fg-2">
        {playing ? <Play className="h-3 w-3 fill-clear text-clear" aria-hidden /> : <Pause className="h-3 w-3 text-fg-3" aria-hidden />}
        <span className="text-fg-3">Sim</span>
        <span className="font-mono text-[0.8125rem] text-fg-1">{state ? fmtClock(state.current_minute) : "—:—"}</span>
        {state ? <span className="text-fg-3">{state.playback_speed}×</span> : null}
      </span>
      <span className="h-3.5 w-px bg-line" aria-hidden />
      <span className="flex items-center gap-1.5 text-[0.75rem]">
        <span className="text-fg-3">IST</span>
        <span className="font-mono text-[0.8125rem] text-fg-1">{ist || "—:—"}</span>
      </span>
    </div>
  );
}

function AccountMenu() {
  const { data: session, status } = useSession();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const pathname = usePathname();
  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  if (status === "loading") return <span className="h-9 w-9 rounded-full skeleton" aria-hidden />;

  if (!session?.user) {
    return (
      <Link href={`/login?callbackUrl=${encodeURIComponent(pathname || "/")}`} className="btn btn-secondary btn-sm" data-tour="account">
        <UserRound className="h-4 w-4" aria-hidden />
        <span className="hidden sm:inline">Sign in</span>
      </Link>
    );
  }

  const provider = (session as any).provider as string | undefined;
  const providerLabel = provider === "google" ? "Google" : provider === "azure-ad" ? "Microsoft" : "Username";
  return (
    <div className="relative" ref={ref} data-tour="account">
      <button type="button" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((v) => !v)} className="rounded-full transition-transform active:scale-95" title={session.user.name || "Account"}>
        <Avatar name={session.user.name} image={session.user.image} size={36} />
      </button>
      {open ? (
        <div role="menu" className="glass rise absolute right-0 top-12 z-50 w-72 p-2">
          <div className="flex items-center gap-3 p-3">
            <Avatar name={session.user.name} image={session.user.image} size={40} />
            <div className="min-w-0">
              <p className="truncate text-[0.9375rem] font-medium text-fg-1">{session.user.name}</p>
              <p className="truncate text-[0.8125rem] text-fg-2">{session.user.email || `Signed in with ${providerLabel}`}</p>
            </div>
          </div>
          <div className="my-1 h-px bg-line" />
          <Link role="menuitem" href="/settings?tab=profile" className="flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-[0.875rem] text-fg-2 transition-colors hover:bg-[var(--glass-strong)] hover:text-fg-1">
            <UserRound className="h-4 w-4" aria-hidden /> Profile
          </Link>
          <Link role="menuitem" href="/settings" className="flex items-center gap-3 rounded-[10px] px-3 py-2.5 text-[0.875rem] text-fg-2 transition-colors hover:bg-[var(--glass-strong)] hover:text-fg-1">
            <Settings2 className="h-4 w-4" aria-hidden /> Settings
          </Link>
          <button role="menuitem" type="button" onClick={() => signOut({ callbackUrl: "/" })} className="flex w-full items-center gap-3 rounded-[10px] px-3 py-2.5 text-left text-[0.875rem] text-fg-2 transition-colors hover:bg-[var(--glass-strong)] hover:text-fg-1">
            <LogOut className="h-4 w-4" aria-hidden /> Sign out
          </button>
        </div>
      ) : null}
    </div>
  );
}

export function TopBar() {
  const pathname = usePathname() || "/";
  const tour = useTour();
  return (
    <header className="sticky top-0 z-40 px-3 pt-3 sm:px-5">
      <div className="glass mx-auto flex h-16 max-w-[1520px] items-center gap-3 !rounded-[18px] px-3 sm:px-4">
        <Link href="/" className="flex min-w-0 items-center gap-2.5 rounded-[12px] pr-2" aria-label="Chennai Division Traffic Optimizer, home">
          <BrandMark className="h-8 w-8 shrink-0" />
          <span className="hidden min-w-0 flex-col leading-tight sm:flex">
            <span className="truncate text-[0.9375rem] font-semibold tracking-[-0.01em] text-fg-1">Chennai Division</span>
            <span className="truncate text-[0.75rem] text-fg-3">Traffic Optimizer</span>
          </span>
        </Link>

        <nav aria-label="Destinations" data-tour="nav" className="mx-auto hidden md:block">
          <ul className="seg">
            {DESTINATIONS.map((d) => {
              const active = isActive(pathname, d.href);
              const Icon = d.icon;
              return (
                <li key={d.href}>
                  <Link href={d.href} aria-current={active ? "page" : undefined} className="seg-item flex items-center gap-2">
                    <Icon className="h-4 w-4" strokeWidth={1.75} aria-hidden />
                    {d.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="ml-auto flex items-center gap-1.5 md:ml-0">
          <LiveClock />
          <button type="button" className="icon-btn" onClick={() => tour.start()} aria-label="Start the guided tour" title="Guided tour">
            <CircleHelp className="h-[18px] w-[18px]" strokeWidth={1.75} />
          </button>
          <Link href="/settings" className={cx("icon-btn", pathname.startsWith("/settings") && "!text-champagne !border-line")} aria-label="Settings" title="Settings">
            <Settings2 className="h-[18px] w-[18px]" strokeWidth={1.75} />
          </Link>
          <AccountMenu />
        </div>
      </div>
    </header>
  );
}

export function BottomNav() {
  const pathname = usePathname() || "/";
  return (
    <nav aria-label="Destinations" className="fixed inset-x-0 bottom-0 z-40 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:hidden">
      <ul className="glass mx-auto grid max-w-md grid-cols-5 !rounded-[18px] p-1.5">
        {DESTINATIONS.map((d) => {
          const active = isActive(pathname, d.href);
          const Icon = d.icon;
          return (
            <li key={d.href}>
              <Link
                href={d.href}
                aria-current={active ? "page" : undefined}
                className={cx("flex min-h-[48px] flex-col items-center justify-center gap-1 rounded-[12px] text-[0.6875rem] font-medium transition-colors", active ? "bg-[var(--glass-strong)] text-champagne" : "text-fg-2 hover:text-fg-1")}
              >
                <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} aria-hidden />
                {d.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export function Atmosphere() {
  return (
    <div className="atmosphere" aria-hidden>
      <div className="dots" />
    </div>
  );
}

/** Redirect to the user's preferred landing destination on a fresh visit to "/". */
export function useLandingRedirect(landing: string, ready: boolean) {
  const router = useRouter();
  const pathname = usePathname();
  useEffect(() => {
    if (!ready || landing === "/" || pathname !== "/") return;
    try {
      if (window.sessionStorage.getItem("cdto.landed")) return;
      window.sessionStorage.setItem("cdto.landed", "1");
    } catch {
      return;
    }
    router.replace(landing);
  }, [landing, ready, pathname, router]);
}
