"use client";

import React from "react";
import { SessionProvider } from "next-auth/react";
import { SettingsProvider } from "@/lib/glass/settings";

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider refetchOnWindowFocus={false}>
      <SettingsProvider>{children}</SettingsProvider>
    </SessionProvider>
  );
}
