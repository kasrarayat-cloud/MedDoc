# Design Direction V3 — NOCTURNE

Generated: 2026-04-29
Author: Design Director (v3 / Nocturne)
Foundation: a dark-mode-first cinematic re-skin that **replaces** App-redesign-v1's bg/fg layers with a deeper blue-black canvas and **collapses** the multi-accent palette to a single saturated electric-blue.

Mockups (open at ~1600px wide):

- [`landing-and-recording.html`](landing-and-recording.html) — landing → recording moment → success → empty-state → AI typewriter
- [`dashboard.html`](dashboard.html) — calm zone, dense visit table, status pills as desaturated mono
- [`visit-detail.html`](visit-detail.html) — patient header + tabs + SOAP editor + transcript + Rx warning re-skin

---

## 1. Thesis

**Nocturne** is the design direction for a doctor who finishes their notes at 11:42 pm, in a dark study, with a glass of something. It is **dark-mode-first** — not "we offer a dark theme," but the canvas IS dark, the chrome IS dark, and a light theme is an alternate, never the source of truth. It rejects medical-cosplay (no mint, no sky-blue, no soft "trust" gradients) in favor of the cinematic vocabulary of a high-end DAW: 1px borders that catch a single saturated accent, inset shadows that sit, dense type at small sizes, mono numerals, generous black space.

Nocturne commits to three loud opinions. **One:** there is exactly one accent — `#3B82F6` electric-blue — and every CTA, focus ring, recording dot, and active-row indicator uses it. Status colors are grayscale or desaturated (a desaturated red `#A83244` for danger, a desaturated amber `#B07A29` for review-needed) so the "noir mood" is never broken by a Christmas-tree of saturated severity pills. **Two:** the recording moment is the showpiece — a full-screen spotlight, a conic-gradient border-beam in the accent traveling around the recording widget, a ~5% opacity SVG film-grain overlay drifting behind everything, and the rest of the interface dimmed to ~30% lightness. Cinematic, never festive — closer to a Christopher Nolan title sequence than a Vercel celebration. **Three:** the AI processing moment is **a single mono line with a blinking typewriter cursor**, replaced in place as each pipeline stage advances. No nodes. No connecting beams. No thought-chain. The cursor is the visualization.

Apothecary (v2) and Nocturne are both dark, but they share almost nothing else. Apothecary is **violet, aurora-mesh, two-mood, multi-accent (violet + copper + aqua), thought-chain-with-pulsing-nodes, festive on success**. Nocturne is **blue, no-mesh, one-mood (always-cinematic, intensity-modulated), single-accent, typewriter-cursor, reveal-on-success**. They are close in temperature and far apart in grammar.

---

## 2. The chosen accent

**Electric-blue `#3B82F6`** — Tailwind blue-500, the "signal" hue.

Why it (and not the other two we considered):

- **`#F5A524` signal-amber** was tempting — feels like a tape deck's record LED — but at the saturation needed to read on a near-black canvas, it pulls toward "warning" semantics, which conflicts with using the same hue on every CTA.
- **`#D946EF` magenta** is owned by Apothecary's secondary palette already (`--color-accent-b` in `DESIGN_TOKENS.md`); using it here would fight Apothecary in side-by-side reviews.
- **`#3B82F6` electric-blue** reads as **technical confidence** at every size: 1px on a focus ring, 2px on the active-row left edge, 8px on the recording border-beam. It also has the highest contrast against `#0A0E1A` of the three candidates (AAA at 14px+).

Nocturne defines two satellites of the accent for state:

| Token | Hex | Use |
|---|---|---|
| `--accent` | `#3B82F6` | All CTAs, focus rings, active-row edge, recording dot |
| `--accent-bright` | `#60A5FA` | Hover state on the accent — 1 step lighter |
| `--accent-deep` | `#1D4ED8` | Pressed / inset shadow color |
| `--accent-glow` | `rgba(59, 130, 246, 0.18)` | Inner-glow of buttons on hover, severity-critical card glow |

That's it. Three values + one alpha. No gradient stops, no analogous secondary.

---

## 3. The chosen base

**Deep blue-black `#0A0E1A`** — not pure black, not Apothecary's `#07060C` violet-tinted dark.

Why deep blue-black over warm-charcoal:

- Pairs with the electric-blue accent without feeling tonally clashed (a warm `#16151A` charcoal would "dirty" a cool blue accent).
- Carries a slight blue cast that reads as "cinema 2.4:1 letterbox" rather than "tar."
- At 5% white-noise film-grain overlay (mix-blend-mode: overlay, opacity 0.05), the canvas takes on the texture of a 35mm print — exactly the mood we want.

Nocturne's surface stack is intentionally narrow (5 → 4 layers; one fewer than Apothecary's), because Nocturne uses **borders, not fills**, to express elevation:

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#0A0E1A` | App-shell base |
| `--bg-1` | `#0E1320` | Top nav, sidebar, calm-zone tables |
| `--bg-2` | `#121828` | Card surfaces, panels |
| `--bg-3` | `#171E30` | Hovered cards, popovers |

Borders do the rest of the work:

| Token | Hex | Use |
|---|---|---|
| `--line-soft` | `#1A2235` | Almost-invisible dense-list separator |
| `--line` | `#212B42` | Default card / input border |
| `--line-strong` | `#2F3B57` | Hovered / focused border |

Foreground is a 4-step cool-gray:

| Token | Hex | Use |
|---|---|---|
| `--fg` | `#E8ECF3` | Primary text (slight cool cast, not pure white) |
| `--fg-2` | `#A3ADC2` | Body copy, paragraph |
| `--fg-3` | `#6B7388` | Labels, captions, meta |
| `--fg-4` | `#3F4659` | Disabled, placeholders |

---

## 4. Skills + libraries used

Skills invoked during authoring:

- **`frontend-design`** — to push past the "generic AI dark mode" trope and earn each animation's existence (only the recording moment + the typewriter cursor + the success sweep are animated; everything else is static).
- **`ui-ux-pro-max`** — palette restraint (one accent, grayscale status), AAA contrast on `#0A0E1A`, dense-table density rules, mono numerals on stats.
- **`theme-factory`** — extracting an 8-step grayscale + 1 accent + 2 satellites; committing to one base hex.
- **`framer-motion`** — slow eases (`cubic-bezier(0.32, 0.72, 0.18, 1)` for ~600ms reveals), single-property transitions, `prefers-reduced-motion` collapse on the spotlight + grain.
- **`ui-libraries-reference`** — referenced (not copied) for spotlight + border-beam patterns.

Libraries WebFetched for inspiration only:

| Library | Component | What Nocturne took |
|---|---|---|
| Aceternity UI | Spotlight | The `transform: scale + opacity` reveal pattern; the `translate(-50%, -40%)` off-center anchor that gives the cone of light a "slightly above center" cinematic feel. **Original CSS** authored in-mockup. |
| Magic UI | Border Beam | The conic-gradient `from 0deg, transparent → accent → transparent` rotation pattern, with `inset: 0` masked to a 1px-thick ring. **Original CSS** authored in-mockup, no React. |

Other inspirations (no fetch — references only): Arc browser chrome (centered command bar + slim rail), Linear in dark mode (1px-bordered dense tables), Ableton Live (mono numerals + tiny labels at scale), Logic Pro (dark gray + one signal color), A24 / Criterion film websites (italic serif over grain).

---

## 5. Five differences from Apothecary

Both directions are dark + serif-leaning. Here is what makes Nocturne distinctly different.

1. **Cooler canvas.** Apothecary's `--bg` is `#07060C` (violet-tinted dark). Nocturne's `--bg` is `#0A0E1A` (blue-tinted dark). Side-by-side, Nocturne reads **cinema**; Apothecary reads **alchemy**.
2. **Single accent, not three.** Apothecary uses violet + copper + aqua. Nocturne uses electric-blue and only electric-blue. Status colors in Nocturne are grayscale or desaturated severity tints — a ready-pill is `[READY]` in flat mono, not a mint gradient.
3. **Grain, not aurora.** Apothecary uses a CSS gradient mesh (`.qm-aurora`) on HIGH-mode routes. Nocturne uses a 5% opacity SVG film-grain overlay **everywhere, always-on**. The grain is the texture; there is no mesh, no blob, no glow shader.
4. **Border-beam only on the recording widget — never elsewhere.** Apothecary applies its border-beam to the hero card, the recording widget, and the AI band when active. Nocturne reserves the beam exclusively for the recording widget. The visit-detail "regenerate" moment uses the typewriter cursor instead — a different visual primitive entirely.
5. **AI processing is a typewriter cursor, not a thought-chain.** Apothecary's pipeline is animated nodes connected by SVG dasharray trails, with rolling thought-text. Nocturne's pipeline is one mono line that types itself, replaces itself, and types the next stage. "Reviewing transcript…|" → "Identifying speakers…|" → "Drafting subjective…|". Single line. One spotlight. The cursor is the entire visualization.

---

## 6. Best for

A design-conscious solo physician doing late-night chart catch-up — the kind who runs Arc browser, edits in Logic Pro on weekends, watches Criterion. Hospital procurement officers will not love Nocturne. The user who picks Nocturne picks it on purpose.

---

## 7. Honest costs

- **Dark-mode-first means light-theme users are second-class.** A light theme can be derived (the foreground/background pairings invert cleanly) but it will not feel like the canonical Nocturne — it will feel like a courtesy.
- **The grain overlay can clash with screen-share, projector, and very-old-monitor viewing.** The mockups use `mix-blend-mode: overlay` at 5% opacity; on a beamer at 800 lumens this can read as a faulty signal. Production should expose a "disable grain" preference and auto-disable when the user is presenting (`navigator.mediaDevices.getDisplayMedia` polled flag).
- **The moody aesthetic may feel "indie" to a hospital procurement office.** Nocturne is unambiguously consumer-software-grade. Selling into a 200-bed hospital IT department, the aesthetic is a liability. This is the price of committing.
- **Reduced status-color saturation costs medical-trust signaling.** A flat `[CRITICAL]` pill in `#A83244` reads as "elegant" to a designer and as "is that a button or a label?" to a clinician under cognitive load. Nocturne accepts this trade in service of the unified mood. The Rx warning card retains the `<RxWarningCard>` design-spec internal layout (per `PROTECTED_CONTRACTS.md`); only the outer frame is reskinned.
- **Single-accent commitment is brittle.** If a future feature needs a *second* signal color (e.g., a billing module that competes with clinical signals for attention), Nocturne has no second hue to give. Phase 2 must hold the line — or break the system on purpose, with intent.

---

## 8. The single most-controversial decision

**Status pills are flat desaturated mono — no green.**

A `READY` visit in Nocturne renders as `[READY]` in mono, with `letter-spacing: 0.12em`, color `#7E8AA4` (a cool gray), on a 1px `#212B42` border, no fill. A `SIGNED` visit is the same chip with `[SIGNED]` and a tiny accent dot. There is **no mint pill**, anywhere. The desaturated red `#A83244` shows up only on the Rx warning card outer frame, and even there it sits behind the existing `<RxWarningCard>` design-spec internals, which keep their full-saturation severity colors (the protected contract).

This is contestable because every healthcare app the doctor has ever used signals "good" with green and "bad" with red. Nocturne deliberately suppresses those signals to preserve the cinematic mood, betting that **a doctor reading their own chart at 11pm prefers stillness over signal**. If the user rejects this trade, swap `.qm-pill-ready { color: #7E8AA4 }` to `color: var(--mint)` and the rest of Nocturne survives untouched.
