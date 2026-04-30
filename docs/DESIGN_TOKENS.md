# Transcribe-MD Design Tokens

Generated: 2026-04-29
Source of truth: `apps/transcribe-md/src/app/globals.css` (1,324 lines)
System: Tailwind v4 CSS-first config — `@theme` directive in `globals.css`, **no `tailwind.config.ts`**.

This file extracts every design token currently in use. Two systems coexist; both must keep working. **Phase 2 will migrate to the App-redesign-v1 token set; the legacy set stays alive until every consumer is migrated.**

---

## A. App-redesign-v1 / HANDOFF tokens (CANONICAL — use these for new work)

Source: `globals.css` lines 61–100 (`@theme` block) + lines 105–138 (`:root` aliases) + lines 148–160 (`.qm-app`-scoped radii/shadows).

The `--color-*` names give Tailwind utility classes out of the box (`bg-bg-1`, `text-fg-2`, `border-line`, `text-accent`, `text-mint`). The bare-name aliases (`--bg`, `--fg`, `--accent`) are for handwritten `.qm-*` CSS that pre-dates the Tailwind utilities.

### A.1 Color — backgrounds (5 layers, dark only)

| Token (Tailwind) | Bare alias | Hex | Use |
|---|---|---|---|
| `--color-bg` | `--bg` | `#07060C` | App-shell base (deepest) |
| `--color-bg-1` | `--bg-1` | `#0C0A16` | First elevation — sidebars, top nav |
| `--color-bg-2` | `--bg-2` | `#14111F` | Second — card surfaces, panels |
| `--color-bg-3` | `--bg-3` | `#1C1828` | Third — hovered cards, popovers |
| `--color-bg-4` | `--bg-4` | `#221C30` | Fourth — modal interiors, command palette |

Tailwind utilities: `bg-bg`, `bg-bg-1`, `bg-bg-2`, `bg-bg-3`, `bg-bg-4`.

### A.2 Color — borders / hairlines

| Token | Alias | Hex | Use |
|---|---|---|---|
| `--color-line-soft` | `--line-soft` | `#191524` | Almost-invisible separator (e.g. inside dense lists) |
| `--color-line` | `--line` | `#26222F` | **Default** card / input border |
| `--color-line-strong` | `--line-strong` | `#3A3445` | Hover / focused borders, prominent dividers |

Tailwind: `border-line`, `border-line-soft`, `border-line-strong`.

### A.3 Color — foreground (text + icons)

| Token | Alias | Hex | Use |
|---|---|---|---|
| `--color-fg` | `--fg` | `#F5F2FA` | Primary text |
| `--color-fg-2` | `--fg-2` | `#B9B2C9` | Secondary text — body copy, paragraph |
| `--color-fg-3` | `--fg-3` | `#7E7791` | Tertiary — labels, captions, section headers |
| `--color-fg-4` | `--fg-4` | `#4B4558` | Muted — placeholders, disabled |

Tailwind: `text-fg`, `text-fg-2`, `text-fg-3`, `text-fg-4`.

### A.4 Color — brand (violet) + accents

| Token | Alias | Hex | Use |
|---|---|---|---|
| `--color-accent` | `--accent` | `#8B5CFF` | **Primary brand violet** — buttons, focus, active state |
| `--color-accent-bright` | `--accent-bright` | `#A87CFF` | Hover / highlight on accent |
| `--color-accent-deep` | `--accent-deep` | `#6B3FD9` | Pressed / deep accent — gradient stops |
| `--color-accent-ink` | `--accent-ink` | `#2A1560` | Darkest accent — backgrounds, ink shadow |
| `--color-accent-a` | `--accent-a` | `#D1B5FF` | Soft accent — gradient bright stop, chips |
| `--color-accent-b` | `--accent-b` | `#D946EF` | Magenta secondary accent |
| `--color-accent-c` | `--accent-c` | `#60A5FA` | Blue secondary accent (info status) |

Tailwind: `text-accent`, `bg-accent`, `border-accent`, plus `-bright`, `-deep`, `-ink`, `-a`, `-b`, `-c` variants.

### A.5 Color — status

| Token | Alias | Hex | Use |
|---|---|---|---|
| `--color-mint` | `--mint` | `#6EE7B7` | Success / ready / signed-OK |
| `--color-amber` | `--amber` | `#FBBF24` | Warning / review-needed |
| `--color-coral` | `--coral` | `#FB7185` | Error / critical / Rx warn |

Tailwind: `text-mint`, `bg-mint`, `border-mint` (and amber/coral).

### A.6 Radii (`.qm-app`-scoped — does NOT override Tailwind globally)

These live inside `.qm-app` so Tailwind's `rounded-sm` / `rounded-lg` defaults stay intact for the marketing site, while the redesigned app gets handoff radii inside the scope.

| Var | Value | Use |
|---|---|---|
| `--radius-sm` | `6px` | Chips, kbd, tight inputs |
| `--radius` | `12px` | Cards, buttons (default) |
| `--radius-lg` | `20px` | Modals, large surfaces |
| `--radius-xl` | `28px` | Hero panels, full-bleed cards |

### A.7 Shadows + glow (`.qm-app`-scoped)

| Var | Use |
|---|---|
| `--shadow-1` | Subtle inset highlight + soft drop shadow — default card depth |
| `--shadow-2` | Stronger version — modals, popovers |
| `--glow-accent` | Violet halo + 1px ring — hover state on `.qm-glass.hover` |

### A.8 Motion / timing

| Var | Value | Use |
|---|---|---|
| `--ease-out-premium` | `cubic-bezier(0.4, 0, 0.2, 1)` | Default ease — buttons, hovers |
| `--ease-out-back` | `cubic-bezier(0.34, 1.56, 0.64, 1)` | Springy enter — modals, success ticks |
| `--ease-in-out-soft` | `cubic-bezier(0.65, 0, 0.35, 1)` | Long ambient — orb pulse |
| `--duration-fast` | `150ms` | Hover transitions |
| `--duration-base` | `300ms` | Card lift, focus ring |
| `--duration-slow` | `500ms` | Page transitions |
| `--duration-lazy` | `800ms` | Hero / orchestrated reveals |

### A.9 Typography

Fonts are loaded in `apps/transcribe-md/src/app/layout.tsx` and exposed as CSS variables:

| Var | Family | Use |
|---|---|---|
| `--serif` | Source Serif 4 | Section headlines, Rx warning headlines, body in details panels |
| `--sans` | Inter Tight | Default UI font (buttons, body, labels) |
| `--mono` | JetBrains Mono | Codes, kbd hints, tabular labels, transcribed values |

`.qm-serif`, `.qm-sans`, `.qm-mono` utility classes apply each one.

Inside `.qm-app`: `font-size: 14px`, `line-height: 1.5`, `letter-spacing: -0.01em`.

#### Typography helper classes (legacy / global — work outside `.qm-app` too)

| Class | Spec |
|---|---|
| `.type-display` | clamp(48px, 6vw, 88px), 800 weight, lh 0.95, tracking -0.04em |
| `.type-h1` | clamp(36px, 4vw, 48px), 600, lh 1.1, tracking -0.02em |
| `.type-h2` | clamp(28px, 3vw, 32px), 600, lh 1.2, tracking -0.015em |
| `.type-body` | 17px, 400, lh 1.6 |
| `.type-small` | 14px, 500, lh 1.5 |

These predate the App-redesign-v1 system but are still in use on the landing/auth-shell. Phase 2 may rationalize.

### A.10 Animations + utilities (`.qm-*`)

`globals.css` lines 405–878. The most-used:

| Class | Behavior |
|---|---|
| `.qm-pulse` | 2s pulsing halo — for status dots |
| `.qm-spin` | 1.2s linear rotate — loading spinners |
| `.qm-shimmer` | 1.6s violet-tinted skeleton shimmer |
| `.animate-in` + composables (`fade-in-0`, `zoom-in-95`, `slide-in-from-top-2`, etc.) | Drop-in tailwindcss-animate replacements (also defined as fallbacks) |
| `.orb-pulse` | 4s ambient breathing — used by `<VioletOrb>` halo |
| `.animate-accordion-{down,up}` | Radix-tied open/close — uses `--radix-accordion-content-height` |

Reduced motion: `@media (prefers-reduced-motion: reduce)` collapses all animation durations to 0.01ms (line 485).

---

## B. Legacy "Linear/Raycast/Vercel/Resend" tokens (PRESERVE — do not delete)

Source: `globals.css` lines 20–60 (`@theme` block, before the App-redesign-v1 block).

These tokens still resolve and are referenced by 15 unmigrated components (see `docs/COMPONENT_INVENTORY.md`). Phase 2 migrates components off these onto the App-redesign-v1 set, but **the tokens themselves stay in `globals.css` until every consumer migrates**.

### B.1 Color — backgrounds (legacy)

| Token | Hex |
|---|---|
| `--color-bg-base` | `#08090D` |
| `--color-bg-surface-1` | `#101119` |
| `--color-bg-surface-2` | `#161822` |
| `--color-bg-surface-3` | `#1E2030` |

(Used by `html, body` background at line 164. The page-level radial violet glow is also keyed off this layer.)

### B.2 Color — borders (legacy)

| Token | Hex |
|---|---|
| `--color-border-subtle` | `#1C1D28` |
| `--color-border-default` | `#2A2C3A` |
| `--color-border-emphasis` | `#3C3E50` |

### B.3 Color — text (legacy)

| Token | Hex |
|---|---|
| `--color-text-primary` | `#F8FAFC` |
| `--color-text-secondary` | `#CBD5E1` |
| `--color-text-tertiary` | `#94A3B8` |
| `--color-text-muted` | `#64748B` |

### B.4 Color — violet shades + accent (legacy)

| Token | Hex |
|---|---|
| `--color-violet-300` | `#C4B5FD` |
| `--color-violet-400` | `#A78BFA` |
| `--color-violet-500` | `#8B5CF6` |
| `--color-violet-600` | `#7C3AED` |
| `--color-violet-700` | `#6D28D9` |
| `--color-cyan-400` | `#22D3EE` |
| `--color-cyan-500` | `#06B6D4` |
| `--color-success` | `#10B981` |
| `--color-warning` | `#F59E0B` |
| `--color-danger` | `#EF4444` |

> Note: `--color-violet-500` (`#8B5CF6`) and the App-redesign-v1 `--color-accent` (`#8B5CFF`) are visually almost identical — but the new system uses `8B5CFF` (true purple) instead of `8B5CF6` (slight green tint). New components must use `--color-accent`.

---

## C. Components already on App-redesign-v1 (preserve identity in remodel)

9 files use `qm-*` classes today. Any visual remodel must keep them coherent.

| File | qm-* classes used |
|---|---|
| `src/components/ui/app-frame.tsx` | `qm-app`, page-shell wrapper |
| `src/components/ui/auth-shell.tsx` | Auth-page chrome |
| `src/components/ui/top-nav.tsx` | Top navigation bar |
| `src/components/ui/spec-chip.tsx` | Specialty pill (`qm-chip`-like) |
| `src/components/dashboard/patient-card.tsx` | Card grid item |
| `src/components/dashboard/stat-card.tsx` | Dashboard stat tile |
| `src/components/dashboard/visit-list.tsx` | Visit list rows |
| `src/components/rx/rx-warning-card.tsx` | Full Rx warn component (uses `qm-warn-*` family) |
| `src/components/rx/override-confirm-modal.tsx` | Rx override flow |

Plus the dashboard route itself: `src/app/dashboard/page.tsx` mounts `<AppFrame>` and is the canonical "new shell" implementation.

---

## D. Background effects in `globals.css` (visual chrome)

| Element | Source | Notes |
|---|---|---|
| Page-level radial glow | line 175 — `body` background-image | Violet ellipse anchored upper-centre, fixed attachment |
| `.qm-shader` | line 546 | Reserved space for the WebGL shader background |
| `.qm-noise` | line 559 | SVG fractal-noise overlay, 28% opacity, mix-blend overlay |
| `.grid-bg` | line 265 | 48px grid with radial-mask fade |
| `.gradient-border` | line 218 | Padding-box + border-box double-bg trick |
| `.specular-button` | line 234 | Hover light-sweep (Linear's "shine") |
| `.glow-violet` | line 293 | Violet radial halo on `:hover` or `[data-glow="on"]` |
| `.tilt-perspective` | line 276 | 1200px perspective + preserve-3d |
| `.text-gradient-violet` | line 282 | violet→light text gradient |

---

## E. Per-component `.qm-*` classes (for reference when authoring new components)

These already exist in `globals.css` and should be reused before authoring new utility classes.

### Cards
- `.qm-glass` (line 570) — translucent glass card with backdrop-blur, line border, hover-glow when `.qm-glass.hover`

### Buttons (line 588 onward)
- `.qm-btn` — base button reset
- `.qm-btn-primary` — violet gradient with inset highlight + soft shadow
- `.qm-btn-ghost` — line-bordered, fg-2 text
- `.qm-btn-icon` — 32×32 square
- `.qm-btn-sm` — smaller padding/font

### Inputs
- `.qm-input` (line 654) — translucent background, line border, accent ring on focus

### Chips (line 676 onward)
- `.qm-chip` — base chip
- `.qm-chip.dot` — adds a leading dot
- `.qm-chip-{accent,mint,amber,coral,blue}` — colored variants

### Status pills (line 723 onward — "LOUD")
- `.qm-status` — base
- `.qm-status-{queued,processing,ready,review,signed,error}` — full-saturation gradient pills
- `.qm-status-processing::before` — animated pulse dot

### Misc
- `.qm-kbd` — keyboard chip (mono, tiny)
- `.qm-divider` — 1px line divider
- `.qm-sectlabel` — "§ 01 / METHOD" idiom — mono, 10px, uppercase, letter-spaced

### Rx warning card (entire family, lines 880–1324)
- `.qm-warn` — root, severity-themed (3 variants: critical/warning/info)
- `.qm-warn-{head,body,actions,details-toggle,details-body}` — card regions
- `.qm-warn-{icon,badge,headline,dismiss}` — header pieces
- `.qm-warn-{action,action-icon}` — action tile
- `.qm-warn-{transcribed,field-block,field-label,field-value,confidence}` — heard-vs-guess section
- `.qm-warn-{risks,risk,risk-dot,risk-body,risk-primary,risk-outcome,outcome-bold,pill}` — risk list
- `.qm-warn-{next,next-icon,next-label}` — next-step strip
- `.qm-warn-{btn,btn-primary,kbd}` — actions

The Rx warning family is gated by an existing design spec in `docs/design/rx_warning_handoff/` and a Vitest test (`src/components/rx/__tests__/rx-warning-card.test.tsx`). **Phase 1 directions should not propose visual changes to this component.**

---

## F. What's missing (gaps the design directions can fill)

The following primitives don't have a `.qm-*` equivalent yet — directions in Stage C may propose them, and Phase 2 can author them:

- Tabs (currently the visit ready view uses ad-hoc Radix bindings)
- Tables (none in the app today)
- Stepper / progress indicator (visit pipeline status uses `.qm-status-processing` only)
- Avatar (file `ui/avatar.tsx` exists but isn't wired to qm tokens)
- Tooltip (no qm-tooltip; relies on Radix defaults)
- Empty-state (file `ui/empty-state.tsx` exists; not yet keyed to qm tokens)
- Form-group / fieldset / label
- Toast (sonner is wired through `components/toaster.tsx` but not styled to qm tokens)
- Command palette styling (cmdk is used but legacy-styled today)

---

## G. Migration policy (Phase 2)

When porting a legacy component to the App-redesign-v1 set:

1. Replace `bg-bg-base` → `bg-bg`. `bg-surface-1` → `bg-bg-1`. `bg-surface-2` → `bg-bg-2`. `bg-surface-3` → `bg-bg-3`.
2. Replace `border-subtle` → `border-line-soft`. `border-default` → `border-line`. `border-emphasis` → `border-line-strong`.
3. Replace `text-primary` → `text-fg`. `text-secondary` → `text-fg-2`. `text-tertiary` → `text-fg-3`. `text-muted` → `text-fg-4`.
4. Replace `text-violet-{500,600,700}` → `text-accent` / `text-accent-deep` / `text-accent-ink`. `bg-violet-*` similarly.
5. Replace `text-success` / `bg-warning` / `text-danger` → `text-mint` / `bg-amber` / `text-coral`.
6. Wrap the component's tree in `.qm-app` if it isn't already inside one (e.g. via `<AppFrame>`).
7. Remove direct `font-family` overrides — `.qm-app` provides Inter Tight by default; opt into serif/mono via `.qm-serif` / `.qm-mono` classes only.

This migration policy is also embedded in `docs/REMODEL_PHASE1_PLAN.md` as the operational rule for component builders.

---

## H. Clinician tokens (PHASE 2 — the chosen direction)

Added to `apps/transcribe-md/src/app/globals.css` on 2026-04-29 as the start of Phase 2. Source of truth: `docs/design-directions-v3/clinician/{landing-and-recording,dashboard,visit-detail}.html` — tokens ported 1:1 from the mockups' `:root` blocks.

### Architecture

- **`@theme` namespace `--color-clinician-*`** → exposed as Tailwind utilities (`bg-clinician-cream`, `text-clinician-sage`, `border-clinician-line`, etc.)
- **`.qm-cl-app` scope** → defines bare-name aliases (`--cream`, `--ink`, `--sage`, `--serif`, `--sans`, `--mono`, etc.) so handwritten `.qm-cl-*` CSS resolves the same way the mockups do — without polluting the global `:root` (where App-redesign-v1's `--bg`/`--fg`/`--accent` live)
- **`.qm-cl-*` utility classes** → only meaningful inside `.qm-cl-app`. Migrated routes wrap their tree in `.qm-cl-app` (mirror of how dark routes wrap in `.qm-app`)

A single page is wrapped in EITHER `.qm-app` (dark — App-redesign-v1) OR `.qm-cl-app` (light — Clinician). Never both. The two scopes don't overlap, so both token systems coexist during the migration.

### H.1 Color — surfaces (cream layers)

| Token (Tailwind) | Bare alias (`.qm-cl-app`) | Hex | Use |
|---|---|---|---|
| `--color-clinician-cream` | `--cream` | `#FAF7F2` | Canvas (lightest) |
| `--color-clinician-cream-card` | `--cream-card` | `#FFFCF5` | Card surface — slightly lighter than canvas |
| `--color-clinician-cream-2` | `--cream-2` | `#F2EDE3` | Hover / sidebar / active-tab base |
| `--color-clinician-cream-3` | `--cream-3` | `#E8E1D3` | Deeper elevation — scrollbar thumb, dividers |

Tailwind utilities: `bg-clinician-cream`, `bg-clinician-cream-card`, `bg-clinician-cream-2`, `bg-clinician-cream-3`.

### H.2 Color — hairlines

| Token | Alias | Value | Use |
|---|---|---|---|
| `--color-clinician-line` | `--line` | `rgba(43, 38, 32, 0.08)` | Default hairline |
| `--color-clinician-line-strong` | `--line-strong` | `rgba(43, 38, 32, 0.14)` | Stronger hairline (visible dividers) |

### H.3 Color — ink (warm-charcoal text)

| Token | Alias | Hex | Use |
|---|---|---|---|
| `--color-clinician-ink` | `--ink` | `#2B2620` | Primary text |
| `--color-clinician-ink-2` | `--ink-2` | `#5C544A` | Secondary text — body |
| `--color-clinician-ink-3` | `--ink-3` | `#8A8278` | Tertiary — labels / captions |
| `--color-clinician-ink-4` | `--ink-4` | `#B5AE9F` | Muted — placeholders / disabled |

### H.4 Color — sage (primary accent) + sage tints

| Token | Alias | Value |
|---|---|---|
| `--color-clinician-sage` | `--sage` | `#7AA68C` |
| `--color-clinician-sage-deep` | `--sage-deep` | `#2F5040` |
| `--color-clinician-sage-bright` | `--sage-bright` | `#95BCA4` |
| (scoped `.qm-cl-app`) | `--sage-tint` | `rgba(122, 166, 140, 0.14)` |
| (scoped `.qm-cl-app`) | `--sage-tint-strong` | `rgba(122, 166, 140, 0.22)` |

The tints are intentionally only inside `.qm-cl-app` scope — they're rgba expressions that don't fit Tailwind's color-token model cleanly.

### H.5 Color — secondary accent + status (teal / amber / coral / sky)

| Token | Alias | Hex |
|---|---|---|
| `--color-clinician-teal` | `--teal` | `#5BA3B4` |
| `--color-clinician-teal-deep` | `--teal-deep` | `#2C5A66` |
| `--color-clinician-amber` | `--amber` | `#D4A574` (warm warning) |
| `--color-clinician-amber-deep` | `--amber-deep` | `#7A4F1F` |
| `--color-clinician-coral` | `--coral` | `#C97B6E` (soft danger) |
| `--color-clinician-coral-deep` | `--coral-deep` | `#7A3329` |
| `--color-clinician-sky` | `--sky` | `#7BA8C4` (info) |
| `--color-clinician-sky-deep` | `--sky-deep` | `#2C4F66` |

Plus rgba tints (scoped to `.qm-cl-app`): `--teal-tint`, `--amber-tint`, `--amber-tint-strong`, `--coral-tint`, `--coral-tint-strong`, `--sky-tint`.

### H.6 Shadows (`.qm-cl-app`-scoped — paper-on-desk feel)

| Var | Value | Use |
|---|---|---|
| `--shadow-card` | `0 4px 14px rgba(43, 38, 32, 0.04)` | Resting card (looks like paper sitting on a warm desk) |
| `--shadow-card-hover` | `0 8px 24px rgba(43, 38, 32, 0.06)` | Hover lift |
| `--shadow-button` | `0 1px 2px rgba(43, 38, 32, 0.05), 0 1px 1px rgba(43, 38, 32, 0.03)` | Soft button surface |
| `--shadow-cta` | `0 6px 18px rgba(122, 166, 140, 0.28)` | Sage-tinted primary CTA shadow |

No glow rings. No inset highlights. No box-shadow with high opacity. Clinician shadows are intentionally subtle.

### H.7 Motion (`.qm-cl-app`-scoped)

| Var | Value | Use |
|---|---|---|
| `--ease-clinician` | `cubic-bezier(0.22, 1, 0.36, 1)` | The single ease curve. Slow, gentle, no overshoot. |

Default duration: **240 ms** for hover/transition, **360 ms** for card lift, **600 ms** for transcript slide-fade, **800–1600 ms** for the recording halo and AI crossfade.

**No springs.** No bounces. No `framer-motion` `spring` configs. Clinician's tonal commitment.

### H.8 Typography (`.qm-cl-app`-scoped)

| Var | Stack | Use |
|---|---|---|
| `--serif` | `"Source Serif 4", Georgia, "Times New Roman", serif` | Patient names (19–40 px), SOAP body (16 px / 1.7 lh), prose, big-num stats (38 px) |
| `--sans` | `"DM Sans", -apple-system, ..., system-ui, sans-serif` | Default UI body (15 px), buttons, labels, pills, kickers |
| `--mono` | `"JetBrains Mono", ui-monospace, ...` | IDs (MRN-77324), timestamps, kbd (rare in Clinician) |

DM Sans is loaded via `@import url('https://fonts.googleapis.com/css2?family=DM+Sans...')` near the top of `globals.css`. The other two faces are already loaded via `next/font` in `apps/transcribe-md/src/app/layout.tsx`.

The `--sans` override only happens inside `.qm-cl-app` — non-migrated routes continue to use Inter Tight (the App-redesign-v1 default).

### H.9 Class catalog (`.qm-cl-*` — utility classes)

All defined inside `.qm-cl-app` selector. Listed here so component builders can grep before authoring new utilities.

#### Layout chrome
- `.qm-cl-wordmark` — Source Serif 4 wordmark (top-nav)
- `.qm-cl-topbar` — sticky top-nav with cream-w-blur backdrop
- `.qm-cl-sidebar` — left sidebar (cream-2 surface, hairline right border)
- `.qm-cl-nav-item` — sidebar nav item (with `.qm-cl-active` modifier)
- `.qm-cl-nav-icon` — nav-item icon (color shifts on hover/active)

#### Atomic
- `.qm-cl-pill` — base pill (12 px, rounded-full)
- `.qm-cl-pill-sage`, `-teal`, `-amber`, `-coral`, `-sky`, `-soft` — color variants
- `.qm-cl-pill-dot` — leading 6 px dot
- `.qm-cl-btn` — base button (pill-shaped, 240 ms ease)
- `.qm-cl-btn-primary`, `-soft`, `-ghost` — button variants
- `.qm-cl-btn-lg` — larger size (landing CTA)
- `.qm-cl-card` — soft warm card (16 px radius)
- `.qm-cl-card-soft` — same with hover-lift
- `.qm-cl-input` — soft warm input with sage focus ring
- `.qm-cl-section-label` — small-caps sans label
- `.qm-cl-eyebrow` — small-caps sage-deep eyebrow (above headlines)
- `.qm-cl-big-num` — 38 px Source Serif 4 stat number
- `.qm-cl-tab-row` + `.qm-cl-tab` (with `.qm-cl-active`) — soft pill tabs
- `.qm-cl-meta-dot` — quiet meta separator
- `.qm-cl-lift` — hover-lift transition (apply to any container)
- `.qm-cl-gentle-rule` — 1 px hairline (warm-charcoal at 14%)
- `.qm-cl-sage-divider` — 1 px sage-tinted hairline (SOAP section breaks)

#### Feature — patient/visit listings
- `.qm-cl-patient-row` — 76 px-tall row (grid: 56 px avatar + name + meta + time + status + chevron)
- `.qm-cl-avatar` + `-sage`, `-teal`, `-amber`, `-coral`, `-sky` variants — rounded-square serif initial chip

#### Feature — visit detail
- `.qm-cl-prose` — Source Serif 4 16 px / 1.7 lh, max-width 720 px (SOAP body, transcript snippets)
- `.qm-cl-soap-section` — SOAP block (S / O / A / P)
- `.qm-cl-soap-letter` — the colored letter chip beside each section
- `.qm-cl-turn` + `.qm-cl-turn-dr`, `.qm-cl-turn-pt` — speaker turn cards (alternating left/right)
- `.qm-cl-speaker-label` — "DR." / "PT." caption
- `.qm-cl-turn-body` — speaker turn body text

#### Feature — AI processing moment
- `.qm-cl-ai-status` — italic-serif crossfade band (above SOAP when regenerating)
- `.qm-cl-ai-status-line` + `-s1` `-s2` `-s3` — three crossfading lines
- `.qm-cl-editing` — caret cursor for live SOAP streaming

#### Feature — recording state
- `.qm-cl-halo` + `.qm-cl-halo-delayed` — radial-gradient slow pulse (3.4 s)
- `.qm-cl-mic-dot` — sage-tinted breathing-shadow dot
- `.qm-cl-wave-bar` — 3 px sage VU-meter bar
- `.qm-cl-transcript-line` + `-l1` `-l2` `-l3` `-l4` — staggered slide-fade-in lines

#### Feature — illustrations (line-art)
- `.qm-cl-illus-stroke` — sage stroke 1.4 px
- `.qm-cl-illus-stroke-warm` — warm-charcoal stroke 1.2 px
- `.qm-cl-illus-fill-sage`, `-cream`, `-amber` — fills

#### Animations (global @keyframes — all `qm-cl-*` prefixed)
- `qm-cl-halo-pulse` (3.4 s)
- `qm-cl-mic-breath` (2.8 s)
- `qm-cl-slide-fade` (600 ms)
- `qm-cl-ai-crossfade` (4.8 s, looped)
- `qm-cl-caret` (1.1 s, looped)
- `qm-cl-wave-bar` (1.6 s, looped)

All collapse to a static frame under `prefers-reduced-motion: reduce`.

### H.10 Body grain (opt-in via `data-grain`)

`<div class="qm-cl-app" data-grain>...</div>` enables a gentle warm radial wash:

```css
background-image:
  radial-gradient(ellipse at 12% 8%, rgba(122, 166, 140, 0.06) 0%, transparent 42%),
  radial-gradient(ellipse at 88% 92%, rgba(91, 163, 180, 0.05) 0%, transparent 50%);
```

Used on the landing page only. Dashboard / visit-detail keep the canvas flat.

### H.11 Migration policy (Clinician-specific addendum to §G)

When porting a non-migrated component to Clinician:

1. **Wrap the page in `.qm-cl-app`.** Either at the route's `layout.tsx` boundary (preferred — adds the warm canvas + DM Sans body for the entire route family) or at the root component level if a layout doesn't exist.
2. **Replace `.qm-*` classes with `.qm-cl-*` equivalents.** A direct mapping exists for most:
   - `.qm-glass.hover` → `.qm-cl-card-soft`
   - `.qm-btn-primary` → `.qm-cl-btn-primary`
   - `.qm-input` → `.qm-cl-input`
   - `.qm-status-{ready,signed,processing,...}` → `.qm-cl-pill-{sage,sage,teal,...}` (use the soft pill family)
3. **Replace inline Tailwind referencing dark tokens** (`bg-bg-1`, `text-fg-2`, `border-line`, `text-accent`) **with Clinician utilities** (`bg-clinician-cream-card`, `text-clinician-ink-2`, `border-clinician-line`, `text-clinician-sage`).
4. **Keep TypeScript types, props, hooks, server-action signatures unchanged.** Visual swap only — the seam is preserved.
5. **Preserve every `data-testid`** — Playwright e2e tests rely on them.
6. **Run `npx tsc --noEmit` + `npx vitest run <component>` after each migration.** No commit lands without TS + tests green.

### H.12 What this does NOT change

- The legacy `--color-bg-base` / `--color-violet-500` / `--color-text-primary` token names (still used by 15 unmigrated components).
- The App-redesign-v1 tokens `--color-bg`, `--color-fg`, `--color-accent`, `--color-mint`, `--color-amber`, `--color-coral` (still used by 9 already-migrated dark components).
- The `.qm-warn-*` Rx warning family (its own design spec; the severity pills will be Clinician-toned in Batch D, but the structural CSS stays).
- The `tailwindcss-animate` plugin loading or any of the existing `.animate-*` classes.

This Clinician section is **purely additive**. Both pre-existing token systems continue to resolve. Migration happens route-by-route; both can coexist in production for as long as the migration takes.
