# Design Direction V3 — PRISM

Generated: 2026-04-29
Author: Design Director (Phase 1 — exploration v3)
Foundation: extends App-redesign-v1 / HANDOFF tokens (`docs/DESIGN_TOKENS.md` §A) — same 5-bg / 4-fg / 3-line / mint-amber-coral status palette, but **replaces the violet+copper+aqua brand layer with a Cosmic tri-tone (magenta → violet → cyan)** and pushes saturation everywhere, even into calm zones.

Mockups (open at ~1600 px):

- [`landing-and-recording.html`](landing-and-recording.html) — gradient-mesh hero, the AI pipeline showpiece, recording orb, success reveal, empty state
- [`dashboard.html`](dashboard.html) — bento grid; calm-but-still-Prism: gradient pills, gradient sparklines, gradient hover stripes, AI-activity tile with mini-pipeline
- [`visit-detail.html`](visit-detail.html) — calm SOAP body with gradient accents; "Regenerate Subjective" triggers the FULL pipeline showpiece in-context

---

## 1. Thesis

**Prism is an AI-first product that's PROUD of being AI.** It looks like the toolchain a 2026 doctor *wants* to be seen using — saturated, gradient-everywhere-but-tasteful, the AI is the protagonist not the assistant. The recording moment is a gradient-meshed orb breathing under a border-beam. The processing pipeline is a SHOWPIECE — a five-node beam with particle trails on animated SVG paths, gradient mesh breathing in the background, node halos pulsing to a 1.4-second rhythm. When the SOAP is ready the success card gets a gradient sweep and the check-mark draws on. Nothing about this product apologizes for being computational.

**Prism rejects the two-mood "calm zones get NO accents" framing** that Apothecary commits to. In Prism, even the dashboard table — the most tabular surface in the app — has gradient status pills, a gradient-edge hover stripe, gradient focus rings on inputs, a gradient-clipped logo, and a tile-corner mini-pipeline pulse on the "AI Activity" bento card. Calm in Prism doesn't mean gradients-banished; it means gradients-quieter (lower opacity, smaller surfaces, slower motion). The dashboard is functional and dense, but at a glance you cannot mistake it for a generic admin panel — it reads as *AI product* the moment it loads.

**Saturation is earned, not sprinkled.** Every gradient in Prism encodes something: brand identity (logo, primary CTA), AI activity (pipeline beams, processing band, regenerate moment), confidence (ICD pill), severity (Rx warn pill), or trend (sparkline this-week-vs-last-week). A gradient that doesn't earn its place gets demoted to flat. The stat numbers themselves stay unembellished; the *trend chart* underneath them carries the gradient. Body copy stays plain; the *section bullet* carries the gradient. This discipline is what separates Prism from generic gradient slop: gradients here are **functional pigment**, not decoration.

---

## 2. The chosen tri-tone — COSMIC

Pick: **Cosmic** (the brief's middle option).

| Role | Token | Hex | Where it leads |
|---|---|---|---|
| **Primary** | `--prism-1` | `#D946EF` (deep magenta) | Logo gradient stop 0%, Rx critical pills, recording orb core, "live" / "active" / "now-recording" indicators, primary CTA gradient stop 0% |
| **Secondary** (anchor) | `--prism-2` | `#7C3AED` (electric violet) | Default brand violet — the gradient stop everything passes through; pipeline beam middle, focus rings, AI band trim, primary CTA gradient stop 50% |
| **Tertiary** | `--prism-3` | `#22D3EE` (electric cyan) | AI / info / "thinking" / transcript-side, code chips, pipeline beam tail, success-state mint pairs with cyan, primary CTA gradient stop 100% |

**The defended gradient.** `linear-gradient(135deg, #D946EF 0%, #7C3AED 50%, #22D3EE 100%)` is the Prism brand gradient. It's the magenta-end energy you'd see on Vercel AI's hero, with the violet anchor of Anthropic's gradient illustrations, landing in the cyan that says "AI / signal / data flow." The 135° angle is committed everywhere — logo, primary CTA, hero headline mask, pipeline beam, recording orb mesh, sparkline strokes — so the eye reads "Prism" as a single visual language across surfaces.

**Background washes.** The Prism dashboard uses `--bg: #07060C` like Apothecary, but applies a 1–2% magenta wash on the topmost background layer (`background-color: #07060C; background-image: radial-gradient(...rgba(217,70,239,0.04)...)`) — invisible on its own, but it tints the entire shell so the page reads ever-so-slightly purple-pink against pure black. This is the "gradients in calm zones" promise made concrete.

**Status accents (preserved from foundation):** mint `#6EE7B7`, amber `#FBBF24`, coral `#FB7185`. These keep their roles. Prism does not reassign success/warn/error to brand colors — clinical clarity demands they stay distinct from brand.

---

## 3. Plugins / libraries used per mockup

Each visual move maps to (a) the library that inspired the pattern, (b) the skill that informed the choice. **All components are self-contained originals** — no copy-pasted Aceternity / Magic UI / Cult UI source.

### `landing-and-recording.html`

| Visual move | Inspired by | Skill |
|---|---|---|
| Animated gradient-mesh hero background (3 blobs translate + opacity-pulse, 22–34s loops, the "Prism breathes" promise) | Aceternity UI · "background-beams" + Anthropic's gradient illustrations | `frontend-design` (atmosphere-first, no flat hero), `ui-ux-pro-max` (gradient contrast on dark) |
| Hero headline with gradient-clipped fill on the verb ("**Transcribe**, **diagnose**, **prescribe** — your voice does it all") | Magic UI · "gradient-text" | `theme-factory` (committing the 135° angle as brand identity) |
| Magnetic primary CTA wrapped in border-beam (conic gradient ring) | Magic UI · "border-beam" + Cult UI gesture patterns | `framer-motion` (spring `stiffness: 380, damping: 25`, magnet only on `mousemove` not focus) |
| **AI pipeline showpiece** — 5 nodes (voice → transcript → SOAP → ICD → Rx) with animated SVG dasharray beams and gradient particle trails | Magic UI · "animated-beam" + Cult UI agentic dashboards | `framer-motion` (scroll-triggered IntersectionObserver, particle stagger), `ui-ux-pro-max` (`spatial-continuity`, `progressive-loading`) |
| Gradient-meshed recording orb (CSS-only — radial gradients + filter:blur + slow rotate, layered three-ring pulse) | Cult UI · "family-button" / dynamic-island morph | `frontend-design` (one memorable visual moment, no Three.js), `ui-libraries-reference` (Cult UI for AI-native gestures) |
| Border-beam frame + spotlight COMBINED on the recording widget | Magic UI · "border-beam" + Aceternity · "spotlight" | `framer-motion` (continuous animation; reduced-motion guard) |
| Tabular-mono recording timer (`00:42` in JetBrains Mono, leading-digit color hops) | Linear / Stripe idiom | `ui-ux-pro-max` (`number-tabular`, monospace for scrubbing time) |
| Success card with gradient-sweep wipe + check-mark draw-on (no confetti) | Custom; gradient-sweep idiom from Linear's "deploy succeeded" cards | `framer-motion` (one-shot reveal, `pathLength: [0, 1]`) |
| Empty state — quiet gradient mesh + gradient-bordered CTA "Record your first visit" | Aceternity UI · gradient-border idiom | `frontend-design` (empty states earn a moment too) |

### `dashboard.html`

| Visual move | Inspired by | Skill |
|---|---|---|
| Bento grid: 1 large AI-Activity tile + 3 stat cards + visit list table | Magic UI · "bento-grid" | `ui-ux-pro-max` (`visual-hierarchy`, `spacing-scale`) |
| Top-nav with **gradient-clipped logo** + gradient focus rings | Anthropic / Vercel AI brand pattern | `theme-factory` (logo gradient = brand commitment) |
| AI-Activity tile: mini gradient pipeline (4 nodes pulsing 1.4s) | Distilled from the showpiece | `framer-motion` (`AnimatePresence` for live activity rows) |
| Stat-card gradient sparklines (functional — gradient encodes this-week-vs-last-week direction) | Cult UI · sparkline pattern | `ui-ux-pro-max` (`color-not-only` — direction is in shape AND color), `framer-motion` (path draws on mount) |
| **Gradient status pills** (queued / processing / ready / signed / failed) | Magic UI · gradient-text + bento color theory | `theme-factory` (each status owns its gradient: processing = magenta→cyan animated, ready = mint→cyan static, signed = violet→cyan static, failed = magenta→coral) |
| Visit list table — quiet density, but row hover shows a 2px **gradient stripe** sliding in from the left edge | Linear / Vercel idiom + Prism gradient discipline | `framer-motion` (transform-only animation, GPU cheap) |
| Empty state for the table — quiet gradient mesh (low opacity) + gradient-bordered CTA | Aceternity UI · gradient-border | `frontend-design` (calm empty state still feels Prism) |

### `visit-detail.html`

| Visual move | Inspired by | Skill |
|---|---|---|
| Patient name large with **gradient underline** that draws on mount | Magic UI · "border-beam" applied to a path | `framer-motion` (`pathLength` on mount only) |
| Gradient-underlined active tab (Subjective / Objective / Assessment / Plan / Transcript) | Linear tab idiom + Prism gradient layer | `ui-ux-pro-max` (`focus-visible`, `keyboard-nav`) |
| SOAP body — calm 16px serif/sans, but each section header has a **gradient bullet** (•) and ICD candidates carry **gradient confidence pills** | Custom; gradient applied to functional state | `theme-factory` (gradient encodes confidence: 95% = full saturation, 60% = partial) |
| Transcript with speaker names in gradient-clipped mono | Magic UI · gradient-text | `ui-ux-pro-max` (`role-clarity`, `tabular-spacing`) |
| **In-context regenerate moment** — clicking "Regenerate Subjective" expands the FULL pipeline showpiece (animated beams, particles, mesh) inline above the SOAP section, then the new text fades in | The showpiece from landing, brought into the work surface | `framer-motion` (layout animation, `AnimatePresence`, `useInView`) |
| Rx warning frame — preserves existing `<RxWarningCard>` internals; only the severity pill becomes gradient (critical = magenta→coral, warning = amber→cyan, info = violet→cyan) | Direct preservation per project rules | Per `docs/design/rx_warning_handoff/` — internals untouched |

---

## 4. Five differences from Apothecary

1. **Tri-tone is Cosmic, not violet+copper+aqua.** Magenta `#D946EF` primary, electric violet `#7C3AED` anchor, electric cyan `#22D3EE` tertiary. No copper warmth anywhere — Prism is electric-cool throughout. This makes the brand feel younger, more "Vercel AI demo" than "antique pharmacy."
2. **Calm zones keep gradients.** Apothecary's dashboard has flat outline pills, no animation, no backdrop-blur. Prism's dashboard has gradient pills, gradient sparklines, gradient hover stripes, a gradient-clipped logo, and a 1.4s pulse on the AI-activity tile's mini-pipeline. The calm vs. high distinction is **intensity**, not **presence**.
3. **AI is the protagonist, not the assistant.** Apothecary's processing pipeline is a "magic moment" tucked into a band on `/visits/[id]` (PROCESSING). Prism's pipeline is a **showpiece on the landing page** — it's the thing the marketing site brags about, and the same component shows up inline in `/visits/[id]` when you regenerate. Same showpiece, two surfaces.
4. **Gradient-clipped typography on brand verbs.** The hero headline has 3 gradient-clipped verbs ("**Transcribe**, **diagnose**, **prescribe**"). Apothecary uses serif italic for emphasis but never paints the type. Prism commits to the verb-gradient as brand identity.
5. **Recording orb is a CSS-meshed gradient sphere.** Apothecary keeps the `<LiveOrb>` Three.js component on the recording route. Prism replaces it with a CSS-only gradient mesh (radial gradients + filter:blur + slow rotation under a border-beam frame). Cheaper bundle, just-as-strong moment, scales to mobile.

---

## 5. Best for

> **Best for:** the modern solo doctor or 2–10-person specialty group who wants their tools to *look* like the cutting-edge they paid for — physicians who'd rather feel they're using something on the level of Cursor / Linear / Anthropic Console than a mid-2010s EMR module. Strongest in DTC sales, weakest in hospital procurement.

---

## 6. Honest costs

1. **Gradient ages faster than monochrome.** A specific saturated tri-tone in 2026 may read as "of-its-time" in 2028 the way bright neon Memphis design now reads as "1985." Apothecary's earned-restraint will likely outlive Prism's saturation. Mitigation: the Cosmic palette is conservative (no fluorescent / Y2K extreme); refresh the gradient family every ~30 months on a brand cadence.
2. **Animation cost on lower-end hardware.** Three or four simultaneous gradient meshes with `filter: blur(110px)` plus an animated SVG dasharray beam plus a CSS rotate on the recording orb costs ~3–5ms/frame on integrated GPUs. The pipeline showpiece is heaviest. Mitigation: blur radius 110→80, blob count 3→2, and aggressive `prefers-reduced-motion` collapse (the mockups ship the media-query guard). Production needs a perf budget audit before launch.
3. **Hospital procurement may read it as consumer-app.** Saturated gradient brand on a clinical surface signals "modern" to a doctor browsing the website but can signal "unserious" to a CIO buying for 200 seats. Mitigation: the dashboard and visit detail are dense and tabular; the gradient is on accents only, not on data. The procurement-facing screenshot should be the dashboard, not the landing page.
4. **Accessibility on gradient text.** Gradient-clipped text on a dark background passes WCAG AA at the bright stops (cyan + magenta) but dips below at the violet middle. Mitigation: gradient-clipped text is reserved for **display-size** copy (≥40px) and for verb-emphasis only; body copy and labels stay solid `--fg` / `--fg-2`. The mockups follow this rule.
5. **Saturated brand on clinical content can be a credibility hit.** Pink-toward-magenta `#D946EF` is the most contestable color — it's the youngest stop on the gradient. Mitigation: magenta is reserved for brand surfaces (logo, hero headline, recording active state, Rx critical) — it does **not** appear on patient names, SOAP body, ICD codes, or transcript text. The clinical content stays in the calm `--fg` / `--fg-2` neutrals.
6. **Two motion budgets to manage** (shared with Apothecary). The pipeline showpiece + recording orb + hero mesh together can run >60fps on M-series Macs but degrade on Chromebook Plus. Phase 2 needs a `prefers-reduced-motion` lint and a perf budget that caps simultaneous animated layers at 4.

---

## 7. The single most-controversial decision

**The dashboard's status column shows GRADIENT pills, not flat outline pills.**

Apothecary's most defensible move is "the daily-driver dashboard table is calm — pills are flat, mono labels, no gradients." Prism explicitly rejects this. In Prism, every visit row's status column shows a small (28px tall) pill filled with a 135° gradient: `processing` is `magenta→cyan` and animates a slow 2s shimmer, `ready` is a static `mint→cyan`, `signed` is a static `violet→cyan`, `failed` is a static `magenta→coral`.

This is contestable because:
- A doctor scanning 30 rows for "which visits are ready to sign" arguably wants the highest-contrast signal, and a flat mint pill against a dark row achieves that more directly than a gradient mint→cyan pill.
- Gradient pills add ~12 fill colors to a single screen (4 statuses × 3 stops), which competes with the patient names for attention.
- Apothecary's flat pills are colorblind-friendlier (a single hue + dot is unambiguous; a gradient hue may be read as two hues).

**Prism picks gradient pills anyway** because the brand promise is *"calm zones still feel Prism."* If the table pills go flat, the dashboard reads identical to Apothecary's dashboard, and the Prism thesis collapses to "Apothecary with magenta-cyan instead of violet-copper." The pills are the load-bearing detail that proves Prism is a different direction, not a re-skin.

If the user prefers flat pills, the Prism thesis survives **only if** another calm-zone gradient surface compensates: gradient column-header underline on the table, or gradient-bordered active row, or gradient-clipped count chips in the bento. In one form or another, Prism must keep gradient ink in the calmest zone or it stops being Prism.
