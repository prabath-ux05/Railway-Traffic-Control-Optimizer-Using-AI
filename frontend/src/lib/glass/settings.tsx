"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

export interface Settings {
  reduceMotion: boolean;
  reduceTransparency: boolean;
  highContrast: boolean;
  colorBlindSafe: boolean;
  textScale: 100 | 112 | 125;
  mapTilt: boolean;
  landing: "/" | "/network" | "/optimizer" | "/what-if" | "/export";
  defaultSpeed: number;
  clock24h: boolean;
}

export interface Profile {
  displayName: string;
  designation: string;
  controllerId: string;
  division: string;
}

const DEFAULT_SETTINGS: Settings = {
  reduceMotion: false,
  reduceTransparency: false,
  highContrast: false,
  colorBlindSafe: false,
  textScale: 100,
  mapTilt: true,
  landing: "/",
  defaultSpeed: 30,
  clock24h: true,
};

const DEFAULT_PROFILE: Profile = {
  displayName: "",
  designation: "Section Controller",
  controllerId: "",
  division: "Chennai Division · Southern Railway",
};

const SETTINGS_KEY = "cdto.settings.v1";
const PROFILE_KEY = "cdto.profile.v1";

function readJson<T>(key: string, fallback: T): T {
  try {
    const raw = window.localStorage.getItem(key);
    return raw ? { ...fallback, ...JSON.parse(raw) } : fallback;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* storage unavailable: settings stay for this visit only */
  }
}

interface Ctx {
  settings: Settings;
  profile: Profile;
  update: (patch: Partial<Settings>) => void;
  updateProfile: (patch: Partial<Profile>) => void;
  resetAll: () => void;
  ready: boolean;
}

const SettingsContext = createContext<Ctx | null>(null);

export function SettingsProvider({ children }: { children: React.ReactNode }) {
  const [settings, setSettings] = useState<Settings>(DEFAULT_SETTINGS);
  const [profile, setProfile] = useState<Profile>(DEFAULT_PROFILE);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setSettings(readJson(SETTINGS_KEY, DEFAULT_SETTINGS));
    setProfile(readJson(PROFILE_KEY, DEFAULT_PROFILE));
    setReady(true);
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    const systemReduced = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    root.dataset.motion = settings.reduceMotion || systemReduced ? "reduced" : "full";
    root.dataset.transparency = settings.reduceTransparency ? "reduced" : "full";
    root.dataset.contrast = settings.highContrast ? "high" : "normal";
    root.dataset.signals = settings.colorBlindSafe ? "cb" : "default";
    root.style.fontSize = `${settings.textScale}%`;
  }, [settings]);

  const update = useCallback((patch: Partial<Settings>) => {
    setSettings((prev) => {
      const next = { ...prev, ...patch };
      writeJson(SETTINGS_KEY, next);
      return next;
    });
  }, []);

  const updateProfile = useCallback((patch: Partial<Profile>) => {
    setProfile((prev) => {
      const next = { ...prev, ...patch };
      writeJson(PROFILE_KEY, next);
      return next;
    });
  }, []);

  const resetAll = useCallback(() => {
    try {
      Object.keys(window.localStorage)
        .filter((k) => k.startsWith("cdto."))
        .forEach((k) => window.localStorage.removeItem(k));
    } catch {
      /* ignore */
    }
    setSettings(DEFAULT_SETTINGS);
    setProfile(DEFAULT_PROFILE);
  }, []);

  const value = useMemo(() => ({ settings, profile, update, updateProfile, resetAll, ready }), [settings, profile, update, updateProfile, resetAll, ready]);
  return <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>;
}

export function useSettings(): Ctx {
  const ctx = useContext(SettingsContext);
  if (!ctx) throw new Error("useSettings must be used inside SettingsProvider");
  return ctx;
}

/** Local persistence helper for small per-browser state (scenarios, tour progress). */
export function useLocalState<T>(key: string, initial: T): [T, (v: T | ((p: T) => T)) => void] {
  const [value, setValue] = useState<T>(initial);
  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(key);
      if (raw) setValue(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, [key]);
  const set = useCallback(
    (v: T | ((p: T) => T)) => {
      setValue((prev) => {
        const next = typeof v === "function" ? (v as (p: T) => T)(prev) : v;
        try {
          window.localStorage.setItem(key, JSON.stringify(next));
        } catch {
          /* ignore */
        }
        return next;
      });
    },
    [key],
  );
  return [value, set];
}
