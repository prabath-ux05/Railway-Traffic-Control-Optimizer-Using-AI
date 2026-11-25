import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Classic Controller Dashboard — Railway Traffic Optimization",
};

/** The previous 8-tab controller dashboard, kept intact on its original navy theme. */
export default function ClassicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-railway-950 text-slate-100" style={{ fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif" }}>
      {children}
    </div>
  );
}
