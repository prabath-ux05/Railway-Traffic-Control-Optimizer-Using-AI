"use client";

import React, { Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import { Accessibility, Info, LogIn, LogOut, SlidersHorizontal, UserRound } from "lucide-react";
import { FieldLabel, Panel, SectionHead, Segmented, Switch } from "@/components/glass/ui";
import { Avatar } from "@/components/glass/Shell";
import { useTour } from "@/components/glass/Tour";
import { useSettings, type Settings } from "@/lib/glass/settings";
import { useNetwork } from "@/lib/glass/live";
import { SPEEDS, cx } from "@/lib/glass/format";

const TABS = [
  { id: "about", label: "About", icon: Info },
  { id: "profile", label: "Profile", icon: UserRound },
  { id: "general", label: "General", icon: SlidersHorizontal },
  { id: "accessibility", label: "Accessibility", icon: Accessibility },
] as const;
type TabId = (typeof TABS)[number]["id"];

function SettingsInner() {
  const params = useSearchParams();
  const router = useRouter();
  const tab = (TABS.find((t) => t.id === params.get("tab"))?.id ?? "about") as TabId;
  const setTab = (id: TabId) => router.replace(`/settings?tab=${id}`, { scroll: false });

  return (
    <div className="flex flex-col gap-6">
      <SectionHead level={1} className="rise px-1" title="Settings" description="About this system, your profile, general preferences and accessibility. Preferences are saved in this browser." />
      <div className="grid gap-6 lg:grid-cols-[240px_minmax(0,1fr)]">
        <nav aria-label="Settings sections" className="glass h-max p-2">
          <ul className="flex gap-1 overflow-x-auto lg:flex-col">
            {TABS.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  aria-current={tab === t.id ? "page" : undefined}
                  onClick={() => setTab(t.id)}
                  className={cx("flex w-full items-center gap-3 whitespace-nowrap rounded-[12px] px-3 py-2.5 text-[0.875rem] transition-colors", tab === t.id ? "bg-[var(--glass-strong)] text-champagne" : "text-fg-2 hover:bg-[var(--glass)] hover:text-fg-1")}
                >
                  <t.icon className="h-4 w-4" strokeWidth={1.75} aria-hidden /> {t.label}
                </button>
              </li>
            ))}
          </ul>
        </nav>
        <Panel className="p-6 sm:p-8">{tab === "about" ? <About /> : tab === "profile" ? <Profile /> : tab === "general" ? <General /> : <Access />}</Panel>
      </div>
    </div>
  );
}

function About() {
  const { network } = useNetwork();
  const sources = network?.data_provenance?.timetable_sources ?? {};
  const hashes = Object.keys(network?.data_provenance?.dataset_sha256_hashes ?? {}).length;
  return (
    <div className="max-w-[70ch]">
      <h2 className="text-[1.375rem] font-semibold tracking-[-0.02em] text-fg-1">About this system</h2>
      <p className="mt-3 text-[0.9375rem] leading-relaxed text-fg-2">
        The Chennai Division Traffic Optimizer is an AI-assisted decision-support prototype. It combines a railway digital twin, discrete-event simulation, conflict detection, a physically feasible FIFO baseline and Google OR-Tools CP-SAT scheduling. A human controller approves every change.
      </p>
      <dl className="mt-6 divide-y divide-[var(--line)] border-y border-line text-[0.875rem]">
        {[
          ["Research", "Accepted at CICT 2026, IIITDM Kurnool (18–20 December 2026)."],
          ["Status", "Simulation-based prototype. Not deployed on Indian Railways; exports are not official records."],
          ["Network", network ? `${network.track_section_count} track sections · ${network.station_count} stations · ${network.route_count} routes · ${network.junction_count} junctions · ${network.active_service_count ?? "—"} active services` : "Loading…"],
          ["Timetable sources", Object.keys(sources).length ? Object.entries(sources).map(([k, v]) => `${k} (${v})`).join(", ") : "—"],
          ["Data integrity", hashes ? `${hashes} master datasets tracked by SHA-256 hash` : "—"],
          ["Stack", "Next.js 15 · React 19 · FastAPI · Google OR-Tools CP-SAT 9.15"],
        ].map(([k, v]) => (
          <div key={k} className="grid gap-1 py-3 sm:grid-cols-[180px_1fr]">
            <dt className="text-fg-3">{k}</dt>
            <dd className="text-fg-1">{v}</dd>
          </div>
        ))}
      </dl>
      <p className="mt-6 text-[0.8125rem] leading-relaxed text-fg-2">
        Google and Microsoft sign-in need OAuth credentials from the project owner: add <code className="font-mono text-fg-1">GOOGLE_CLIENT_ID</code> and <code className="font-mono text-fg-1">GOOGLE_CLIENT_SECRET</code>, or <code className="font-mono text-fg-1">AZURE_AD_CLIENT_ID</code> and{" "}
        <code className="font-mono text-fg-1">AZURE_AD_CLIENT_SECRET</code>, to <code className="font-mono text-fg-1">frontend/.env.local</code> and restart. The previous interface remains available as the{" "}
        <Link href="/classic" className="text-champagne underline">
          classic dashboard
        </Link>
        .
      </p>
    </div>
  );
}

function Profile() {
  const { data: session, status } = useSession();
  const { profile, updateProfile } = useSettings();
  const provider = (session as any)?.provider as string | undefined;
  return (
    <div className="max-w-[640px]">
      <h2 className="text-[1.375rem] font-semibold tracking-[-0.02em] text-fg-1">Profile</h2>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-4 rounded-[14px] border border-line p-4">
        <div className="flex items-center gap-4">
          <Avatar name={session?.user?.name || profile.displayName} image={session?.user?.image} size={52} />
          <div>
            <p className="text-[1rem] font-medium text-fg-1">{session?.user?.name || profile.displayName || "Guest controller"}</p>
            <p className="text-[0.8125rem] text-fg-2">
              {status === "authenticated" ? `${session?.user?.email ? `${session.user.email} · ` : ""}Signed in with ${provider === "google" ? "Google" : provider === "azure-ad" ? "Microsoft" : "username"}` : "Using the dashboard as a guest"}
            </p>
          </div>
        </div>
        {status === "authenticated" ? (
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => signOut({ callbackUrl: "/" })}>
            <LogOut className="h-4 w-4" aria-hidden /> Sign out
          </button>
        ) : (
          <Link href="/login?callbackUrl=%2Fsettings%3Ftab%3Dprofile" className="btn btn-primary btn-sm">
            <LogIn className="h-4 w-4" aria-hidden /> Sign in
          </Link>
        )}
      </div>
      <p className="mt-6 text-[0.875rem] text-fg-2">These details go on the shift charts you export.</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <FieldLabel htmlFor="pf-name">Name on exports</FieldLabel>
          <input id="pf-name" className="field" value={profile.displayName} placeholder={session?.user?.name || "Your name"} onChange={(e) => updateProfile({ displayName: e.target.value })} maxLength={80} />
        </div>
        <div>
          <FieldLabel htmlFor="pf-role">Designation</FieldLabel>
          <input id="pf-role" className="field" value={profile.designation} onChange={(e) => updateProfile({ designation: e.target.value })} maxLength={60} />
        </div>
        <div>
          <FieldLabel htmlFor="pf-id">Controller ID</FieldLabel>
          <input id="pf-id" className="field font-mono" value={profile.controllerId} placeholder="Optional" onChange={(e) => updateProfile({ controllerId: e.target.value })} maxLength={30} />
        </div>
        <div className="sm:col-span-2">
          <FieldLabel htmlFor="pf-div">Division</FieldLabel>
          <input id="pf-div" className="field" value={profile.division} onChange={(e) => updateProfile({ division: e.target.value })} maxLength={80} />
        </div>
      </div>
    </div>
  );
}

function General() {
  const { settings, update, resetAll } = useSettings();
  const tour = useTour();
  return (
    <div className="max-w-[640px]">
      <h2 className="text-[1.375rem] font-semibold tracking-[-0.02em] text-fg-1">General</h2>
      <div className="mt-5 grid gap-5">
        <div>
          <FieldLabel htmlFor="gn-landing">Open on</FieldLabel>
          <select id="gn-landing" className="field" value={settings.landing} onChange={(e) => update({ landing: e.target.value as Settings["landing"] })}>
            <option value="/">Home</option>
            <option value="/network">Network</option>
            <option value="/optimizer">Optimizer</option>
            <option value="/what-if">What-If</option>
            <option value="/export">Export</option>
          </select>
        </div>
        <div>
          <FieldLabel>Default playback speed when loading the fleet</FieldLabel>
          <Segmented label="Default playback speed" value={settings.defaultSpeed} onChange={(v) => update({ defaultSpeed: v })} options={SPEEDS.map((s) => ({ value: s, label: `${s}×` }))} />
        </div>
      </div>
      <div className="mt-8 flex flex-wrap gap-3 border-t border-line pt-6">
        <button type="button" className="btn btn-secondary" onClick={tour.start}>
          Replay the guided tour
        </button>
        <button
          type="button"
          className="btn btn-danger"
          onClick={() => {
            if (window.confirm("Clear saved preferences, profile, scenarios and tour progress in this browser? Your account is not affected.")) resetAll();
          }}
        >
          Clear local data
        </button>
      </div>
    </div>
  );
}

function Access() {
  const { settings, update } = useSettings();
  return (
    <div className="max-w-[680px]">
      <h2 className="text-[1.375rem] font-semibold tracking-[-0.02em] text-fg-1">Accessibility</h2>
      <div className="mt-2 divide-y divide-[var(--line)]">
        <Switch id="ax-motion" checked={settings.reduceMotion} onChange={(v) => update({ reduceMotion: v })} label="Reduce motion" description="No camera moves, pulses or entrances. Your system setting is also respected." />
        <Switch id="ax-glass" checked={settings.reduceTransparency} onChange={(v) => update({ reduceTransparency: v })} label="Reduce transparency" description="Replace frosted glass with solid surfaces and dim the background light." />
        <Switch id="ax-contrast" checked={settings.highContrast} onChange={(v) => update({ highContrast: v })} label="Higher contrast" description="Brighter secondary text and stronger dividers." />
        <Switch id="ax-cb" checked={settings.colorBlindSafe} onChange={(v) => update({ colorBlindSafe: v })} label="Colour-blind-safe signals" description="Blue, orange and vermilion for clear, caution and conflict. Conflicts keep their hatching either way." />
        <Switch id="ax-tilt" checked={!settings.mapTilt} onChange={(v) => update({ mapTilt: !v })} label="Flat network map" description="Draw the map flat instead of on a tilted plane." />
        <div className="py-4">
          <FieldLabel>Text size</FieldLabel>
          <Segmented
            label="Text size"
            value={settings.textScale}
            onChange={(v) => update({ textScale: v })}
            options={[
              { value: 100 as const, label: "Default" },
              { value: 112 as const, label: "Large" },
              { value: 125 as const, label: "Larger" },
            ]}
          />
        </div>
      </div>
    </div>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={null}>
      <SettingsInner />
    </Suspense>
  );
}
