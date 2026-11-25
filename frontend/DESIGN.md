# DESIGN.md — Chennai Division Traffic Optimizer ("Glass Spatial")

Single source of truth for every page. If a skill or habit conflicts with this file, this file wins.
References: Dribbble "Hero Section – Glass Effect" (Dwinawan / Paperpillar) for material and type;
Dribbble "A Live Intelligence Interface for Stadium Operations" (George Railean) for spatial model, numerals, drill-down.

## 1. World in one line
A warm-black control room seen through frosted glass: the Chennai Division network glows as the
working canvas, and every number sits on the place it describes.

Use scene: controllers in a dim control room at night and a projector in a conference hall — dark ground,
luminous data, high contrast. Dark is chosen by scene, not by category.

## 2. Colour (CSS variables in `src/app/globals.css`)
| Token | Value | Role |
|---|---|---|
| `--ink-0` | `#0A090C` | page ground (warm black) |
| `--ink-1` | `#131219` | solid surface (used when transparency is reduced) |
| `--ink-2` | `#1B1922` | raised solid surface, inputs |
| `--glass` | `rgba(255,246,236,0.045)` | glass panel fill |
| `--glass-strong` | `rgba(255,246,236,0.08)` | hover / selected glass |
| `--line` | `rgba(255,240,224,0.10)` | hairline borders, grid dividers |
| `--line-strong` | `rgba(255,240,224,0.18)` | focused/active borders |
| `--fg-1` | `#F4EFE8` | primary text (17.6:1 on ink-0) |
| `--fg-2` | `#B9B2A8` | secondary text (9.3:1) |
| `--fg-3` | `#8E877C` | labels, axis text (5.4:1, never below 11px) |
| `--champagne` | `#E8C79E` | primary data highlight, active nav, West corridor |
| `--bronze` | `#C08A57` | FIFO baseline series |
| `--violet` | `#8B6CFF` | CP-SAT / AI series |
| `--indigo` | `#4F5BFF` | CTA gradient end, focus ring |
| `--magenta` | `#C04BD8` | CTA gradient start |
| `--clear` | `#63D7A8` | on time / resolved / clear block |
| `--caution` | `#F2B45A` | delay, speed restriction |
| `--conflict` | `#F26A5B` | conflict, blockage (always paired with hatching) |
| `--info` | `#8FB2FF` | neutral info, North corridor |

Glow field (page background only): violet `#5B3DF5` and blue `#2C45FF` top-right, amber `#D9822B` bottom-left,
each a blurred radial at 22–35 % opacity, overlaid with the dot-matrix texture.

Corridor palette (map lines, legend, chart series): West `#E8C79E`, North `#8FB2FF`, South `#63D7A8`,
MRTS `#B79BFF`, Beach–North Bypass `#F2B45A`, PTMS `#F59AB5`, Cross `#7FD6E6`.

Colour-blind-safe signal set (Settings → Accessibility): clear `#56B4E9`, caution `#E69F00`, conflict `#D55E00`.
State is never colour alone: conflicts carry hatching, delays carry a "+n" value, status chips carry a word.

Colour strategy: Full palette with fixed roles — champagne = data, bronze = FIFO, violet = CP-SAT/AI,
signal colours = state, corridor colours = the map. No other hues.

## 3. Type
- Faces: **Inter** (UI, headings, numerals; pinned by the glass reference) and **JetBrains Mono**
  (only times, train numbers, IDs, coordinates). Loaded with `next/font`, self-hosted at build.
- Scale (px / weight / line-height / tracking):
  - `display` 64 / 600 / 1.02 / -0.035em (Home only)
  - `h1` 40 / 600 / 1.08 / -0.03em
  - `h2` 28 / 600 / 1.15 / -0.02em
  - `h3` 19 / 600 / 1.3 / -0.01em
  - `body` 15 / 400 / 1.55
  - `body-sm` 13 / 400 / 1.5
  - `label` 11 / 500 / 1.3 / +0.12em, uppercase — field and axis labels only, never above a heading
  - `numeral-xl` 56 / 300 / 1 / -0.04em · `numeral-l` 40 / 300 · `numeral-m` 28 / 300 — tabular, unit as a
    superscript at 0.42em, `--fg-2`
- Body measure 60–72ch. Every numeric column uses `font-variant-numeric: tabular-nums`.

## 4. Space, shape, depth
- Spacing on a 4 px base: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 96. More space above a heading than below.
- Radii: panel 20, inner block 14, control 10, chip 6, pill 999.
- Glass panel: `--glass` fill + `backdrop-filter: blur(22px) saturate(140%)` + 1px `--line` border +
  inset top highlight `inset 0 1px 0 rgba(255,255,255,0.06)` + depth shadow `0 24px 60px -28px rgba(0,0,0,.65)`.
- Bento grid: panels share 1px hairline dividers inside a single glass slab (glass reference), not floating cards.
- Dot matrix: `radial-gradient(rgba(255,236,214,.16) 1px, transparent 1.3px)` at 7px, masked to fade out.
- Hatch (conflict/blockage): `repeating-linear-gradient(135deg, rgba(242,106,91,.30) 0 5px, transparent 5px 10px)`.
- Reduced transparency: glass becomes `--ink-1`/`--ink-2` solid, glows dim to 8 %.

## 5. Components
- **Top bar** (glass, sticky): brand mark + "Chennai Division" · five destinations as a segmented tab group ·
  IST clock and simulation clock · tutorial (?) · settings · account (avatar or "Sign in").
  Below 900px the destinations move to a bottom tab bar (icon + label, 44px targets).
- **Buttons**: primary = pill, gradient `--magenta → --indigo`, white text 15/600; secondary = pill outline `--line-strong`;
  quiet = text button. Press scale .97, 120 ms.
- **Segmented control / tabs**: glass track, selected segment `--glass-strong` + champagne text.
- **Delta chip**: 6px radius, 1px line, "+3 ▲" style using a drawn icon, coloured by sign meaning (not by sign).
- **Status chip**: word + dot (On time / Delayed / Conflict / Held / Arrived).
- **Breadcrumb**: parent levels `--fg-3` light, current level `--fg-1` medium — "Chennai Division / West / Basin Bridge".
- **Data table**: hairline rows, sticky header in `label` style, tabular numerals, hover row `--glass`.
- **Inputs**: `--ink-2` fill, 1px line, 10px radius, focus ring 2px `--indigo` at 70 %.
- Icons: lucide-react only, 1.75 stroke, 16/18/20 px.

## 6. Signature move — "The Living Network"
The Network destination renders the division's 107 nodes and 7 corridors as glowing lines on a softly tilted
spatial plane. Trains ride their sections as luminous points coloured by type; delays enlarge their halo;
conflicts pulse as hatched coral at the contested resource. Selecting a station eases the camera in,
deepens the breadcrumb, and opens the inspector beside it. Everything else on the page is standard UI.

## 7. Motion
- Easing: `--ease-out: cubic-bezier(0.16, 1, 0.3, 1)`; `--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1)`.
- Durations: press 120 ms, hover/state 200 ms, panel enter 320 ms, map camera 650 ms.
- One authored entrance per page (content rises 8px from a visible state with a 4px blur clearing);
  no per-card stagger cascades. Live values tween, never jump.
- `prefers-reduced-motion` or Settings → Reduce motion: no camera moves, no pulses, instant states.

## 8. Browser surfaces
Selection `rgba(139,108,255,.35)`, caret `--champagne`, thin scrollbars on `--line`, focus-visible ring 2px `--indigo`,
underline offset 3px, tabular numerals everywhere numbers align.

## 9. Bans (from the design notes and craft floor)
No eyebrow/kicker labels above headings, no gradient text, no glass as decoration where a solid surface would
read better, no same-size icon-card grids as page structure, no sparklines standing in for content,
no coloured side borders thicker than 1px, no emoji or unicode icons, no monospace outside data.
