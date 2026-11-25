"use client";

import React from "react";
import { LiveProvider } from "@/lib/glass/live";
import { useSettings } from "@/lib/glass/settings";
import { Atmosphere, BottomNav, TopBar, useLandingRedirect } from "@/components/glass/Shell";
import { TourProvider } from "@/components/glass/Tour";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { settings, ready } = useSettings();
  useLandingRedirect(settings.landing, ready);
  return (
    <LiveProvider>
      <TourProvider>
        <Atmosphere />
        <div className="relative z-10 flex min-h-screen flex-col">
          <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-ink-2 focus:px-4 focus:py-2">
            Skip to content
          </a>
          <TopBar />
          <main id="main" className="mx-auto w-full max-w-[1520px] flex-1 px-3 pb-28 pt-5 sm:px-5 md:pb-12">
            {children}
          </main>
          <BottomNav />
        </div>
      </TourProvider>
    </LiveProvider>
  );
}
