"use client";

import React, { createContext, useCallback, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, X } from "lucide-react";

interface Step {
  route: string;
  selector: string | null;
  title: string;
  body: string;
}

const STEPS: Step[] = [
  {
    route: "/",
    selector: null,
    title: "Welcome to the Chennai Division traffic optimizer",
    body: "A live digital twin of 7 corridors and 40 active services. The AI proposes conflict-free schedules; you, the controller, decide. This tour takes about a minute.",
  },
  {
    route: "/",
    selector: '[data-tour="nav"]',
    title: "Five destinations",
    body: "Home explains the system. Network shows trains running. Optimizer compares FIFO with CP-SAT. What-If tests disruptions. Export produces your shift chart for handover.",
  },
  {
    route: "/",
    selector: '[data-tour="live-clock"]',
    title: "Two clocks",
    body: "Sim is the digital twin's clock and playback speed. IST is the wall clock in Chennai. They are deliberately separate.",
  },
  {
    route: "/network",
    selector: '[data-tour="map"]',
    title: "The living network",
    body: "Every train sits on the section it occupies. Bigger halos mean bigger delays; hatched coral marks a conflict. Select any station to fly in and inspect it.",
  },
  {
    route: "/network",
    selector: '[data-tour="playback"]',
    title: "Run the shift",
    body: "Play, pause, change speed or scrub through the shift window. The backend advances the simulation; every open screen follows the same clock.",
  },
  {
    route: "/optimizer",
    selector: '[data-tour="run-optimizer"]',
    title: "FIFO versus CP-SAT",
    body: "Solve the shift and compare the feasible FIFO baseline with the CP-SAT schedule, train by train, then accept or reject the AI's live proposal.",
  },
  {
    route: "/what-if",
    selector: '[data-tour="studio"]',
    title: "Ask what if",
    body: "Add delays, dwell spikes, speed restrictions or blocked sections. Evaluate them safely, compare scenarios, and push a disruption to the live network when you mean it.",
  },
  {
    route: "/export",
    selector: '[data-tour="export"]',
    title: "Hand over the shift",
    body: "Generate the 6-hour control chart with the train register and your remarks, then download it as PDF or CSV for the next controller in charge.",
  },
  {
    route: "/",
    selector: '[data-tour="account"]',
    title: "Sign in only if you want to",
    body: "Everything works as a guest. Signing in puts your name on exported charts. Replay this tour any time from the help button or Settings.",
  },
];

const DONE_KEY = "cdto.tour.done.v1";

interface TourCtx {
  start: () => void;
  active: boolean;
}
const Ctx = createContext<TourCtx>({ start: () => undefined, active: false });
export const useTour = () => useContext(Ctx);

export function TourProvider({ children }: { children: React.ReactNode }) {
  const [index, setIndex] = useState<number | null>(null);
  const router = useRouter();
  const pathname = usePathname();

  const start = useCallback(() => {
    setIndex(0);
    if (pathname !== "/") router.push("/");
  }, [pathname, router]);

  const finish = useCallback(() => {
    setIndex(null);
    try {
      window.localStorage.setItem(DONE_KEY, "1");
    } catch {
      /* ignore */
    }
  }, []);

  // First visit: offer the tour once on Home.
  useEffect(() => {
    if (pathname !== "/") return;
    let seen = "1";
    try {
      seen = window.localStorage.getItem(DONE_KEY) || "";
    } catch {
      /* ignore */
    }
    if (seen) return;
    const t = window.setTimeout(() => setIndex((i) => (i === null ? 0 : i)), 1200);
    return () => window.clearTimeout(t);
  }, [pathname]);

  const value = useMemo(() => ({ start, active: index !== null }), [start, index]);
  return (
    <Ctx.Provider value={value}>
      {children}
      {index !== null ? <TourOverlay index={index} setIndex={setIndex} onClose={finish} /> : null}
    </Ctx.Provider>
  );
}

function TourOverlay({ index, setIndex, onClose }: { index: number; setIndex: (i: number) => void; onClose: () => void }) {
  const step = STEPS[index];
  const router = useRouter();
  const pathname = usePathname();
  const [rect, setRect] = useState<DOMRect | null>(null);
  const cardRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (pathname !== step.route) router.push(step.route);
  }, [step.route, pathname, router]);

  useLayoutEffect(() => {
    setRect(null);
    if (!step.selector) return;
    let tries = 0;
    let raf = 0;
    const find = () => {
      const el = document.querySelector(step.selector as string) as HTMLElement | null;
      if (el && el.getBoundingClientRect().width > 0) {
        el.scrollIntoView({ block: "center", behavior: "smooth" });
        window.setTimeout(() => setRect(el.getBoundingClientRect()), 260);
        return;
      }
      if (tries++ < 90) raf = window.requestAnimationFrame(find);
    };
    find();
    const onResize = () => {
      const el = document.querySelector(step.selector as string) as HTMLElement | null;
      if (el) setRect(el.getBoundingClientRect());
    };
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onResize, true);
    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onResize, true);
    };
  }, [step.selector, pathname]);

  useEffect(() => {
    cardRef.current?.focus();
  }, [index]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "ArrowRight") index < STEPS.length - 1 ? setIndex(index + 1) : onClose();
      if (e.key === "ArrowLeft" && index > 0) setIndex(index - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, setIndex, onClose]);

  const pad = 8;
  const hole = rect ? { left: rect.left - pad, top: rect.top - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 } : null;
  const vw = typeof window !== "undefined" ? window.innerWidth : 1200;
  const vh = typeof window !== "undefined" ? window.innerHeight : 800;
  const cardW = Math.min(380, vw - 32);
  let cardStyle: React.CSSProperties = { left: (vw - cardW) / 2, top: Math.max(96, vh / 2 - 120), width: cardW };
  if (hole) {
    const below = hole.top + hole.height + 16;
    const fitsBelow = below + 230 < vh;
    const top = fitsBelow ? below : Math.max(16, hole.top - 246);
    const left = Math.min(Math.max(16, hole.left + hole.width / 2 - cardW / 2), vw - cardW - 16);
    cardStyle = { left, top, width: cardW };
  }

  return (
    <div className="fixed inset-0 z-[100]" role="dialog" aria-modal="true" aria-labelledby="tour-title">
      {hole ? (
        <div
          className="pointer-events-none absolute rounded-[16px] transition-all duration-300 [transition-timing-function:var(--ease-out)]"
          style={{ ...hole, boxShadow: "0 0 0 9999px rgba(6,5,9,0.68), 0 0 0 1px rgba(232,199,158,0.55), 0 0 32px 4px rgba(139,108,255,0.35)" }}
        />
      ) : (
        <div className="absolute inset-0 bg-[rgba(6,5,9,0.68)]" />
      )}
      <div ref={cardRef} tabIndex={-1} className="glass rise absolute p-5 outline-none" style={cardStyle}>
        <div className="flex items-start justify-between gap-4">
          <h2 id="tour-title" className="text-[1.0625rem] font-semibold leading-snug tracking-[-0.01em] text-fg-1">
            {step.title}
          </h2>
          <button type="button" className="icon-btn -mr-2 -mt-2 !h-8 !w-8" onClick={onClose} aria-label="Close the tour">
            <X className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-2 text-[0.875rem] leading-relaxed text-fg-2">{step.body}</p>
        <div className="mt-5 flex items-center justify-between gap-3">
          <div className="flex gap-1.5" aria-label={`Step ${index + 1} of ${STEPS.length}`}>
            {STEPS.map((_, i) => (
              <span key={i} className={`h-1.5 rounded-full transition-all duration-300 ${i === index ? "w-5 bg-champagne" : "w-1.5 bg-[var(--line-strong)]"}`} />
            ))}
          </div>
          <div className="flex items-center gap-2">
            {index > 0 ? (
              <button type="button" className="btn btn-quiet btn-sm" onClick={() => setIndex(index - 1)}>
                <ArrowLeft className="h-3.5 w-3.5" /> Back
              </button>
            ) : (
              <button type="button" className="btn btn-quiet btn-sm" onClick={onClose}>
                Skip tour
              </button>
            )}
            <button type="button" className="btn btn-primary btn-sm" onClick={() => (index < STEPS.length - 1 ? setIndex(index + 1) : onClose())}>
              {index < STEPS.length - 1 ? (
                <>
                  Next <ArrowRight className="h-3.5 w-3.5" />
                </>
              ) : (
                "Finish"
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
