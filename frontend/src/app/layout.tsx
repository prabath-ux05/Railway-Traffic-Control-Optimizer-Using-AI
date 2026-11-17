import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Chennai Division — Railway Traffic Optimization & Digital Twin",
  description: "Real-time railway traffic simulation, CP-SAT timetable optimization, and operational decision support dashboard for Chennai Division controllers.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-railway-950 text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        {children}
      </body>
    </html>
  );
}
