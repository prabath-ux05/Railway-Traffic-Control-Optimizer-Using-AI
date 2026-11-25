# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Two audiences, weighted equally (confirmed by the user, 2026-11-25):

- **Section controllers / controller-in-charge** of Southern Railway's Chennai Division, working a 6-hour shift: watch live traffic on the network, resolve conflicts, accept or reject AI re-optimisation proposals, and hand the shift's control chart to the next in-charge.
- **Conference audience and reviewers at CICT 2026** (Dec 18–20, IIITDM Kurnool), who need to understand within minutes what the system does and see it working live.

## Product Purpose

An AI-assisted decision-support digital twin for railway traffic control. It simulates the Chennai Division network, detects resource conflicts, builds a physically feasible FIFO baseline, and uses Google OR-Tools CP-SAT to propose conflict-free, priority-weighted schedules that a human controller approves. Success: a controller can see the network's state, test a disruption, compare FIFO against CP-SAT, act on an explained recommendation, and export a shift record, without leaving the dashboard.

## Positioning

The whole loop (digital twin → conflict detection → feasible FIFO baseline → CP-SAT optimisation → explainable, human-approved recommendation) runs end to end on a real division's topology, rather than any single scheduling technique in isolation.

## Operating Context

- Controllers work in fixed 6-hour shifts (00–06, 06–12, 12–18, 18–24) and hand over at shift change with a control chart (time–distance train graph) and a written handover. The dashboard's Export destination reproduces that ritual as PDF/CSV.
- Live operation runs through the FastAPI backend (`/api/v1/*`): SSE ticks, disruption events, proposals that need explicit Accept/Reject.
- Demos run locally (backend :8000, Next.js :3000).

## Capabilities and Constraints

- Navigation (confirmed): **Home** (explains the project), **Network** (health snapshot + live spatial map with train playback), **Optimizer** (FIFO vs CP-SAT timetables, AI recommendations), **What-If** (disruption studio + scenario comparison), **Export** (6-hour shift chart, PDF/CSV). Plus **Settings** (About, Profile, General, Accessibility), a first-run **tutorial**, and an **optional** login/sign-up (username + password, Continue with Google, Continue with Microsoft; avatar shown when signed in; guests can use everything).
- No research/paper-results page (user decision).
- Network facts: 7 corridors (West, North, South, MRTS, Beach–North Bypass, Cross/Bypass, PTMS), 354 track sections, 30 station records, 24 routes, 7 junctions, 107 route nodes, 47 services of which 40 active and 7 excluded for missing timetable evidence.
- The solver minimises a priority-weighted objective (high-priority 5, suburban 3 per delay-minute, +0.5 × peak delay, +0.8 × late origin departure); reported delays are unweighted. Raw delay can rise while the weighted objective falls; the UI must show both rather than hide it.
- Google/Microsoft sign-in requires OAuth client credentials the project owner creates; until then the buttons must say so plainly rather than fake a sign-in.
- Existing component files under `frontend/src/components/` are checked by the test suite and must stay; the previous dashboard remains reachable at `/classic`.

## Evidence on Hand

- Live backend data (network, timetable of 127 stops from erail.in / railyatri.in / confirmtkt.com, simulation state, optimiser, what-if, proposals).
- Accepted paper CICT647 and its verified values (`docs/PAPER_ALIGNMENT.md`). The dashboard does not present paper results.
- No customer testimonials, deployment, or field-trial evidence exist; never imply live deployment on Indian Railways.

## Product Principles

1. The human controller decides; the AI proposes and explains.
2. Show the network where things happen: state lives on the map before it lives in a table.
3. Never hide a trade-off: raw versus weighted delay, infeasible cases, excluded services.
4. Every shift leaves a record the next in-charge can trust.
5. Guests can do everything; signing in only personalises.

## Accessibility & Inclusion

Settings must offer reduced motion, reduced transparency (solid surfaces instead of glass), higher contrast, larger text, and a colour-blind-safe signal palette. WCAG 2.2 AA contrast for text.
