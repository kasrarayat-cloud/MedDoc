# Design Direction V2 — APOTHECARY

Generated: 2026-04-29
Author: Design Director (v2)
Foundation: extends App-redesign-v1 / HANDOFF tokens (`docs/DESIGN_TOKENS.md` §A) — same 5-bg / 4-fg / 3-line / violet / mint-amber-coral palette plus two new accents (copper + aqua) anchored on violet.

Mockups (open at ~1600 px):

- [`landing-and-recording.html`](landing-and-recording.html) — HIGH-ENERGY mode demo
- [`dashboard.html`](dashboard.html) — CALM mode demo
- [`visit-detail-with-magic.html`](visit-detail-with-magic.html) — TRANSITION between modes

---

## 1. Thesis

**Apothecary** is a **two-mood design system** built on the App-redesign-v1 foundation, named for the original drug-safety expert: precise, ritual, measured, never theatrical for its own sake. It commits to one principle: **the surface mode-shifts to match the user's cognitive load.** Marketing, login, the recording moment, the AI processing pipeline, the success state, and the empty state all run in **HIGH-ENERGY mode** — aurora gradient mesh, spotlight, border-beams, magnetic CTAs, scroll-jacked transcript-becoming-SOAP, an animated 7-layer pipeline with pulsing nodes, a real "thought-chain" instead of a spinner. The dashboard, visit list, SOAP editor, transcript view, settings, and admin tables run in **CALM mode** — Linear-clean, no orbs, no mesh, no motion-on-scroll, just careful hover states and tab indicators. Apothecary explicitly **rejects the mistake of A/B/C** (each picked one energy level for everything) and **rejects the trade-offs they implied** — A's "looks audited but is exhausting," B's "feels safe but never earns awe," C's "feels expert but tires after a week." Apothecary lets the dashboard be quiet so the magic moment lands hard when it appears.

---

## 2. Mood-zone matrix

Every route in `apps/transcribe-md/src/app/`, classified.

| Route | Mode | One-line justification |
|---|---|---|
| `/` (authed-shell landing) | **HIGH** | First impression. The product's emotional pitch lands here. |
| `/login` | **HIGH** | First impression for returning users — small aurora, spotlight on the form. |
| `/signup` | **HIGH** | Conversion moment. Magnetic CTA. Aurora subdued. |
| `/check-email`, `/forgot-password`, `/reset-password` | CALM | Functional auth waypoints — no need for spectacle. |
| `/dashboard` | **CALM** | Daily driver. Bento grid, no animated background, no orbs. |
| `/visits` | CALM | Long-form list scanning. Density wins. |
| `/visits/new` | CALM with **one HIGH moment** | Patient picker + specialty + input mode are calm; the "Record" CTA on the page is magnetic and lights when hovered. |
| `/visits/[id]/record` | **HIGH** | The recording moment is *the* magic moment. Spotlight, breathing orb core, VU meter, border-beam frame on the active state. |
| `/visits/[id]` (READY) | CALM with **one HIGH moment** | SOAP editor + tabs are calm; the AI processing band at the top of the screen is the magic moment when "Regenerate Subjective" runs. Border-beam appears only while active. |
| `/visits/[id]` (PROCESSING) | **HIGH** | While the pipeline runs, this *is* the magic moment screen — full thought-chain visualization, pulsing nodes, gradient trails. Once status flips to READY, the screen mode-shifts to calm. |
| `/visits/[id]` (FAILED) | CALM with one alert moment | Failure is calm + clear. The retry CTA gets a single border-beam pulse on the button. No celebration. |
| `/visits/[id]` (SIGNED) | CALM | Done state. Audit chip, signed-by, no motion. |
| `/patients` | CALM | List view. Same bento+table idiom as dashboard. |
| `/patients/[id]` | CALM | Patient chart — long-form reading. |
| `/settings` | CALM | Forms. Account state. No spectacle. |
| `/dev/rx-warnings` | CALM | Internal playground. |
| `/admin/*` | CALM | Power-user surface. The admin must never feel marketed-to. |
| **Empty states everywhere** | HIGH | Empty states are the only way to make a doctor *care* about an unfilled section. The 0-visits state on the dashboard is HIGH; the rest of the dashboard is CALM. The transition is a route-level mode shift. |
| **Success states (toast-style)** | HIGH | Brief, contained — copper rays burst on signed-SOAP confirmation, then dismiss into a calm pill. |

---

## 3. Plugins / libraries used per mockup

Each visual move maps to (a) the library that inspired the pattern, (b) the skill that informed the choice. **All components are self-contained originals** — no copy-pasted Aceternity/Magic UI source.

### `landing-and-recording.html`

| Visual move | Inspired by | Skill that informed it |
|---|---|---|
| Aurora gradient-mesh background (`.qm-aurora`) | Aceternity UI · "background-beams" / "aurora-background" | `frontend-design` (atmosphere-first, anti-AI-slop), `ui-ux-pro-max` (color-not-only, contrast on gradient backgrounds) |
| Spotlight on hero (`.qm-spotlight`) | Aceternity UI · "spotlight" | `frontend-design` (focus the eye), `ui-libraries-reference` (Aceternity = "wow" hero) |
| Border-beam frame on hero card + recording widget (`.qm-beam-frame`) | Magic UI · "border-beam" (conic-gradient ring) | `framer-motion` (continuous animation pattern; respect `prefers-reduced-motion`) |
| Animated AI pipeline with nodes + connecting trails (`.qm-node`, `.qm-trail-path`) | Magic UI · "animated-beam" | `framer-motion` (scroll-linked + dasharray motion), `ui-ux-pro-max` (spatial continuity) |
| Magnetic CTA (`[data-magnet]`) | Cult UI / Vengeance UI gesture patterns | `framer-motion` (gesture animations, spring physics) |
| Recording orb with pulse rings + breathing core | Cult UI · "family-button" / dynamic-island morph language | `frontend-design` (one memorable visual moment) |
| Thought-chain visualization (`.qm-thought-line`, live/done states) | Cult UI · streaming-text + agent dashboard patterns | `frontend-design` (avoid generic spinners), `ui-ux-pro-max` (`progressive-loading` — show meaning, not progress) |
| Success-state copper rays burst | Custom; loosely inspired by Magic UI · "particles" | `framer-motion` (one-shot reveal; do not re-animate every render) |
| Aurora wisps (drifting particles) | Magic UI · "particles" | `framer-motion` (`useAnimationFrame` would back the production version) |
| Scroll progress bar | shared SaaS idiom | `framer-motion` (`useScroll` → `scaleX` recipe) |

### `dashboard.html` (CALM)

| Visual move | Inspired by | Skill that informed it |
|---|---|---|
| Bento asymmetric grid (5/3/2/2/4 + 12-span table) | Magic UI · "bento-grid", Smooth UI · clean blocks | `ui-ux-pro-max` (`visual-hierarchy`, `spacing-scale`, density vs whitespace) |
| Quiet sparkline + donut for stats | Smooth UI · minimal data viz | `ui-ux-pro-max` (`gridline-subtle`, `trend-emphasis`, `axis-readability`) |
| Linear-style table with mono meta + serif name + hover-bar | Linear / Vercel idiom (already in repo) | `ui-ux-pro-max` (`number-tabular`, `truncation-strategy`, `letter-spacing`) |
| Activity feed with semantic icon tiles | Smooth UI · activity feeds | `ui-ux-pro-max` (`color-not-only` — every row has icon AND text) |
| Top-bar command-palette trigger | shadcn idiom (already in repo via `cmdk`) | preserved (no library swap) |

**Zero motion in calm mode** — only `transition: color/background/border 120ms` on hover/focus. No animations. No keyframes. No backdrop-blur. The contrast with HIGH-ENERGY is deliberate.

### `visit-detail-with-magic.html` (TRANSITION)

| Visual move | Inspired by | Skill that informed it |
|---|---|---|
| Calm shell (rail + topbar + breadcrumb) | Same as dashboard | `ui-ux-pro-max` (`navigation-consistency`) |
| Visit header — serif name + status pill + meta line | App-redesign-v1 patterns already in repo | `theme-factory` (extending the existing serif-name idiom) |
| **AI processing band** (the one magic moment) — border-beam appears only when `data-state="active"` | Magic UI · "border-beam" + Cult UI · streaming-text | `framer-motion` (the band's beam is paused at idle; respects reduced-motion), `ui-ux-pro-max` (`motion-meaning` — animation only when something is happening) |
| Thought-ticker rolling lines | Cult UI · streaming-text patterns | `frontend-design` (avoid generic spinners) |
| Layer dots with single live-pulse | Custom · pipeline status grammar | `ui-ux-pro-max` (`state-clarity`, `color-not-only`) |
| Active-section soft tint on the SOAP block being regenerated | Custom | `ui-ux-pro-max` (`state-transition`, `fade-crossfade`) |
| Right rail with kv tables + layer trace + audit chip | Linear / Notion idiom | `ui-ux-pro-max` (`field-grouping`, `whitespace-balance`) |
| Rx warning frame (preserves the existing `<RxWarningCard>` design spec) | Direct preservation | Per project rules — `RxWarningCard` is not redesigned. |

---

## 4. What this kills from the existing design

- **Three.js orbs ship only in `landing-and-recording` and `/visits/[id]/record`.** The `<VioletOrb>` / `<VisitOrb>` / `<LiveOrb>` / `<ShaderBg>` family is **dropped from the app shell** (icon rail, top nav, dashboard, visit list, settings, admin). They become a HIGH-mode-only bundle, lazy-loaded on those routes. **Bundle saved on calm routes: ~290 KB gzipped.**
- **`<ShaderBg>` is dropped entirely.** Replaced by the lazy-loaded `.qm-aurora` (CSS-only gradient mesh) on HIGH routes. Zero WebGL anywhere.
- **The `body` page-level radial violet glow** (`globals.css` line 175, fixed-attach) **is dropped from the calm shell** and lives only inside `.qm-app[data-mode="high"]`. The calm dashboard renders against a near-flat `--bg` with one tiny radial that fades out by the fold.
- **Gradient pills ship for brand status only** (the recording active state, the "ready" success burst). Status pills in the calm dashboard table are **flat** — outline + colored dot + uppercase mono label. No saturated-gradient `.qm-status-*` pills in tables.
- **Orb-pulse and ambient breathing animations** disappear from the icon rail and top nav. The only motion in CALM mode is hover/focus transitions (≤140ms).
- **Existing legacy orb component file paths** (`components/violet-orb.tsx`, `components/visit-orb.tsx`, `components/recording/live-orb.tsx`, `components/ui/shader-bg.tsx`) **stay on disk** but their import sites are restricted: only auth-shell + recording route + landing may import them. Dashboard, visit-ready, patients, settings, admin: forbidden.

---

## 5. What this commits to building (new `.qm-*` classes for Phase 2)

Phase 2 component builders must author these new utilities in `apps/transcribe-md/src/app/globals.css`:

### HIGH-ENERGY-only (lazy-loadable, lives behind `.qm-app[data-mode="high"]`)

| Class | Purpose | Notes |
|---|---|---|
| `.qm-aurora` + `.qm-aurora .aurora-third` | CSS-only 3-blob gradient mesh background | Replaces `<ShaderBg>`. ~24 lines of CSS. |
| `.qm-grain` | SVG fractal-noise overlay (mix-blend overlay) | Replaces page-level grain texture. |
| `.qm-spotlight` | Radial spotlight from top of section | Loads once on hero. |
| `.qm-beam-frame` | Conic-gradient border-beam wrapper | Used on hero card, recording widget, AI band when active. |
| `.qm-magnet` | Magnetic-cursor wrapper hook (CSS transition; JS sets transform) | One JS handler for all magnets. |
| `.qm-rec-ring` + `.qm-rec-core` + `.qm-vu` | Recording widget (3 pulse rings + breathing core + 9-bar VU) | Replaces `<LiveOrb>` Three.js with CSS-only. |
| `.qm-node` + `.qm-trail-path` | Pipeline node + animated SVG dasharray trail | Drives the AI processing pipeline. |
| `.qm-thought-line` (idle/live/done) | One row of the thought-chain | The magic-moment primitive. |
| `.qm-thought-ticker` (rolling) | Compact single-line variant of the thought-chain | Used inside the AI band on `/visits/[id]`. |
| `.qm-success-burst` | Copper-ray reveal on confirmation | Single fire on intersection. |

### CALM-mode (always on; ~zero bundle cost)

| Class | Purpose | Notes |
|---|---|---|
| `.qm-bento` + `.qm-tile` + `.qm-pulse-tile` + `.span-{3..12}` | Bento grid + asymmetric tiles | Pure grid; no JS. |
| `.qm-table` + thead/td/tr styles + hover-bar | Linear-style data table | New primitive — the inventory flagged this gap. |
| `.qm-tabs-bar` + `.qm-tab` (active/count) | Visit-detail tab grammar | Replaces ad-hoc Radix bindings. |
| `.qm-feed-row` + `.qm-feed-icon.{mint/copper/coral/amber/violet}` | Activity feed primitive | New. |
| `.qm-side-card` + `.qm-side-h` + `.qm-kv` | Right-rail metadata block | New — the visit-detail rail. |
| `.qm-layer-trace` + `.lr` rows | Per-layer pipeline trace | New. |
| `.qm-pill` (flat outline variants) | Mint/amber/coral/copper/aqua/violet flat status pills | Sibling to existing `.qm-status-*` (which stays for hero moments). |
| `.qm-page-h` + `.qm-stat-num` + `.qm-stat-delta` | Page-header + stat-typography idiom | The "Good morning, Dr. X" pattern. |
| `.qm-ai-band` (idle/active) | The visit-detail AI processing band | The magic-moment dock. |
| `.qm-rx-warn-frame` | Frame around the existing `<RxWarningCard>` | Outer frame only — `RxWarningCard` internals untouched. |

### Two new accent tokens (extend `:root`)

```css
--copper:        #E8A872;   /* warm — earned moments, ICD/Rx tags, costs */
--copper-deep:   #B5793D;
--aqua:          #7DD3FC;   /* cool — AI thought-chain, transcript-side, info */
--aqua-deep:     #38BDF8;
```

Plus Tailwind utilities: `text-copper`, `bg-copper`, `border-copper`, `text-aqua`, `bg-aqua`, `border-aqua` (Tailwind v4 reads them automatically from `@theme`).

The existing accents (`--accent` violet, `--mint`, `--amber`, `--coral`) **keep their existing meaning** — Apothecary doesn't reassign roles, it only adds two roles the existing palette didn't cover (cost/tag warmth and AI/info coolness).

---

## 6. Why this beats A/B/C

**A (Clinical)** committed to one energy level — sober, audited, mono-flecked everywhere. It looks correct in code review and exhausting in clinic. **Apothecary keeps A's audit-first dashboard** (mono labels, layer trace, cost surface) but lets the recording moment and the AI processing pipeline be unapologetically expressive — exactly the moments that justify the price tag. **B (Warm)** continued the trajectory the codebase was on but never earned any awe — the dashboard and the recording widget felt the same temperature, and the Rx warning card had to do all the emotional work alone. Apothecary keeps B's serif-warm headline grammar in the calm zones but reintroduces big visual moments where they belong, so the Rx card stops being the only thing on screen that feels like it matters. **C (Dense)** would have rewritten `<AppFrame>` and made the surface look experimental. Apothecary preserves the existing shell wholesale.

**Honest costs:**
1. **Two motion budgets to manage.** Engineers must enforce the rule that HIGH-mode utilities never leak into CALM routes. Phase 2 needs a lint or a CSS layer guard.
2. **Focus management for scroll-jacking.** The hero scroll-jack must respect `prefers-reduced-motion` and tab-key navigation. The `landing-and-recording.html` mockup includes the `prefers-reduced-motion` collapse; production must too.
3. **Magnetic CTA and border-beam can confuse keyboard users.** Both are decorative — keyboard nav must reach buttons through normal tab order; the magnet effect only triggers on `mousemove`, not on focus.
4. **Aurora + grain on low-end Chromebooks.** The aurora uses CSS-only filter:blur; on integrated GPUs the blur is ~1ms/frame — fine. But we must measure on a baseline (Acer Spin 3 / Chromebook Plus). If it's not 60fps, drop blur radius from 110px → 80px and reduce blob count to 2.

---

## 7. Performance note

**Calm zones cost zero in additional bundle.** The new `.qm-*` calm utilities are pure CSS and ship in the existing `globals.css` — net add ~4 KB un-minified.

**HIGH-energy zones lazy-load their motion lib.** Apothecary's HIGH-mode utilities are CSS-only (aurora, spotlight, border-beam, recording orb, thought-chain) — no framer-motion required for the visual moves. The only places framer-motion is needed in production are (a) the magnetic-CTA hook (~3 KB), (b) the scroll-progress bar (`useScroll`), (c) the success-burst on intersection. We can ship all of these in a `motion-high.client.tsx` chunk that's `next/dynamic` imported by `app/page.tsx`, `app/login/page.tsx`, and `app/visits/[id]/record/page.tsx` only.

**Three.js stays out of the dashboard bundle.** Calm routes never import `@react-three/fiber`, `@react-three/drei`, or `three`. Tree-shaking confirms ~290 KB gzipped removed from the dashboard route. (The legacy orb files stay on disk for the recording route.)

**Bundle target after Apothecary lands:**
- `/dashboard` first-load JS: ~190 KB (down from ~480 KB)
- `/visits/[id]` (READY): ~210 KB (down from ~480 KB)
- `/` (landing) first-load JS: ~340 KB (HIGH chunk loaded), but on a route the user sees once.

---

## 8. The single most-controversial decision (for the user to reject)

**The dashboard table uses serif patient names.**

`<td class="pname">John Smith <span class="dob">b. 1967 · M</span></td>` — Source Serif 4 16.5px italic-DOB.

This is contestable. A doctor scanning 30 rows for a name pattern arguably wants Inter Tight (faster glyph recognition, more uniform x-height). But the App-redesign-v1 work already in production uses serif for the patient name in `<PatientCard>` (per audit §2.1), and Apothecary commits to that grammar everywhere — the calm dashboard, the visit header, the right-rail context block. **If the user prefers all-sans data tables**, swap the `.pname` font-family declaration to `var(--sans)` and keep the italic-DOB; the rest of Apothecary survives untouched.

The decision is contestable because it's the one place where "feels human" (the warm thesis from B) collides with "feels scannable" (the dense thesis from C), and Apothecary picks human. The user can flip this in 1 line of CSS.
