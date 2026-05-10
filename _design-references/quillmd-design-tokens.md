# QuillMD Design System — Production Reference

> **Single source of truth** for redesigning the SOAP viewing surface. Mirror these tokens **exactly** — the new mockups should look like the next version of `app.quillmd.com`, not a different app.
>
> Source codebase: `apps/transcribe-md/src/` (transcribe-md only — never touch `meddoc-pro/`).
> Stack: **Next.js 15 + Tailwind v4 + next/font/google (Inter + JetBrains Mono)**. No serif. No Lora. No cream.
> Header comment in `globals.css` lines 12–34: *"Phase 5 Linear V1 Faithful — single design language across the entire product. Pure dark canvas (#08090a), hairline borders, sage primary (replaces Linear's purple), Inter for everything, JetBrains Mono for IDs / timestamps / keyboard hints. No serif italic accents, no cream surfaces, no Phase 4 cinematic photo washes."*

---

## 1 · Colors

All tokens are declared in the `@theme { … }` block at `apps/transcribe-md/src/app/globals.css:36–97`. Tailwind v4 auto-exports them as utilities (`bg-linear-bg`, `text-linear-sage-bright`, `border-linear-border`).

### Surface — pure dark canvas + 3 elevations
```
--color-linear-bg:         #08090a    /* page background — pure dark canvas */
--color-linear-surface-1:  #0d0e10    /* cards, sidebar, primary panels */
--color-linear-surface-2:  #131416    /* nested chips, cmd-k pill, dropdowns */
--color-linear-surface-3:  #1a1c1e    /* hover state on surface-2 */
```

### Borders — hairlines, no shadows
Two flavours: opaque greys for solid rules, white-tint variants for borders that ride a translucent surface.
```
--color-linear-border:           #21232a
--color-linear-border-strong:    #2c2f38
--color-linear-hairline:         rgba(255,255,255,0.05)
--color-linear-hairline-strong:  rgba(255,255,255,0.08)
```

### Text — 4 weights (text-3 was bumped for WCAG AA)
```
--color-linear-text:    #f7f8f8     /* primary — body copy, headings */
--color-linear-text-2:  #b4bcc8     /* secondary — labels, supporting */
--color-linear-text-3:  #828995     /* tertiary — meta, timestamps (4.6:1 on bg) */
--color-linear-text-4:  #4b5159     /* DECORATIVE only — large/bold text ≥18pt */
```
**Important** (`globals.css:52–63`): never use `text-4` for body copy or interactive labels — it's 2.0:1 against bg, below WCAG AA for normal text. It exists for the codes power-table + Rx split-pane subtle labels only.

### Sage accent — replaces Linear's purple
```
--color-linear-sage:         #7AA68C            /* everyday accent */
--color-linear-sage-bright:  #9BC4A8            /* hover / active text tone */
--color-linear-sage-soft:    #5d8a73            /* muted */
--color-linear-sage-deep:    #2F5040            /* gradient anchor / brand mark */
--color-linear-sage-tint:    rgba(122,166,140,0.13)  /* active-row bg */
--color-linear-sage-glow:    rgba(122,166,140,0.18)  /* chip bg */
```
**Sage on dark canvas** = the ONLY accent. Do not introduce purple, blue-violet, or pink. The brand mark uses a `sage-deep → sage` gradient.

### Status palette — quiet, desaturated
```
--color-linear-success:  #4caf7d
--color-linear-warning:  #d4a437     /* amber — review-needed */
--color-linear-danger:   #d4574a     /* coral — critical Rx / sign-blocking */
--color-linear-info:     #5b8db8
--color-linear-amber:    #D4A574     /* alt amber for transcribed/risks */
--color-linear-coral:    #C97B6E
--color-linear-sky:      #74A8C9     /* processing pill */
--color-linear-teal:     #5BA3B4
```

### Row hover / active — subtle white tints
```
--color-linear-row-hover:   rgba(255,255,255,0.03)
--color-linear-row-active:  rgba(255,255,255,0.05)
```

### Severity hue triplets (Rx warnings)
The `.qm-warn` family at `globals.css:575–608` uses RGB triplets to compute fg/bg/border alpha-variants from a single severity color. Defaults are CRITICAL:
```
critical:  rgb(212, 87, 74)   /* coral / danger */
serious:   (same as critical — same hue, different copy)
warning:   rgb(212,164, 55)   /* amber */
info:      rgb( 91,141,184)   /* sky */
```
Each severity card paints a **3px left-edge rail** in the severity color (`globals.css:609–618`).

---

## 2 · Typography

### Font wiring (`apps/transcribe-md/src/app/layout.tsx:1–30`)
Loaded via `next/font/google` and exposed as CSS vars on `<html>`:
```ts
const sans = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-sans',
  display: 'swap',
  fallback: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
});
const mono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
  display: 'swap',
  fallback: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
});
```
- **Inter** for ALL chrome and body. Weights 400 / 500 / 600.
- **JetBrains Mono** for IDs, codes, timestamps, keyboard hints, eyebrow micro-labels, pills. Weights 400 / 500.
- **No serif anywhere**. Lora / Source Serif / Georgia are explicitly retired.

### Body baseline (`globals.css:111–121`)
```css
font-family: var(--font-sans);   /* Inter */
font-size: 13px;
line-height: 1.45;
letter-spacing: -0.005em;
font-feature-settings: 'cv11', 'ss01';   /* single-storey g + stylistic-set 1 */
-webkit-font-smoothing: antialiased;
```

### Size scale (observed across visit-ready-view chrome)
| Use                          | Size      | Family    | Weight | Letter-spacing | Notes |
|------------------------------|-----------|-----------|--------|----------------|-------|
| H1 / page title              | 16px      | sans      | 600    | -0.012em       | `qm-lin-soap-md-h1` |
| Headline (Rx / dialog title) | 17px / 14px | sans    | 500–600| -0.012em       | `qm-warn-headline` / `qm-lin-bump-modal-title` |
| Body — SOAP section          | **14px**  | sans      | 400    | -0.005em       | `qm-lin-soap-section-body` line-height 1.6 |
| Body — list / supporting     | 13px / 12.5px | sans  | 400–500| -0.005em       | `qm-lin-em-criterion` 12px / 1.45 |
| Mono numeric / IDs / codes   | 11–18px   | **mono**  | 500–600| 0 to 0.01em    | `qm-lin-coding-code` 18px, vital token 13px |
| **Eyebrow micro-label**      | **10–11px** | **mono** | 500–600 | **0.07–0.18em** | `text-transform: uppercase`, see §3.1 |
| Section status pill (REVIEWED) | 10px    | mono      | 500    | 0.10em         | uppercase |
| Pulse meta / mini-meta       | 9.5–10.5px| mono      | 500    | 0.06–0.08em    | uppercase |
| Tabs                         | 11px      | mono      | 500    | 0.07em         | uppercase, see §3.3 |
| Footer mini                  | 9.5–10px  | mono      | 500    | 0.08em         | uppercase, text-3 / text-4 |

### Eyebrow letter-spacing convention
Mono uppercase eyebrows in QuillMD use a **wider-than-print** tracking ramp depending on size:
- 9px:  `0.16em`
- 10px: `0.10–0.18em` (most common is 0.10em for status pills, 0.18em for section headings)
- 10.5px: `0.07–0.10em` (markdown H2, transcript jump label)
- 11px: `0.06–0.10em` (tabs, criterion-group titles)

---

## 3 · Spacing + radii + cards

### Card pattern
The canonical card surface (`qm-lin-soap-section-v6`, `qm-lin-coding-rail`, `qm-lin-bump-modal`) is:
```
background:    var(--color-linear-surface-1)        /* #0d0e10 */
border:        1px solid var(--color-linear-hairline) | --color-linear-border
border-radius: 6px (sections), 8px (rails), 10px (modals + Rx warning cards)
padding:       14px 16px (sections), 12px 14px (rail head), 18px 20px (modals)
```
Hover bumps the border to `rgba(255,255,255,0.08)` over 130ms with `cubic-bezier(0.16, 1, 0.3, 1)`.

### Border radii — what lives where
| Radius | Use |
|--------|-----|
| 3–4px  | small chips, override-listbox items, status pills, criterion rows |
| 5–6px  | buttons, inputs, SOAP sections, override option dropdowns |
| 6–8px  | Rx-warning action tile, criterion focus ring |
| 8–10px | rails (CodingRail, Rx rail), modals, page-level cards |

### Section padding (SOAP body card)
```
padding: 14px 16px 16px;
margin-bottom: 22px;
```
SOAP section header: 10px bottom margin, 8px bottom padding, 1px hairline divider beneath (`globals.css:3420–3428`).

### Hairline rules
Use `1px solid var(--color-linear-hairline)` (= `rgba(255,255,255,0.05)`) for **internal** dividers inside cards, and `1px solid var(--color-linear-border)` (= `#21232a`) for **edges** between major surfaces.

### Animation timing
- 80–150ms for chrome transitions, with `ease-out` or `cubic-bezier(0.16, 1, 0.3, 1)`
- 200ms for blur-in modal entrances
- 1200–2000ms for ambient pulses (mic halo, billing-coach pulse)
- All wrapped in `@media (prefers-reduced-motion: reduce) { animation: none; transition: none; }`

---

## 4 · Component patterns (preserve exactly)

### 4.1 SOAP section eyebrow — letter chip + label + status pill
**JSX** (`apps/transcribe-md/src/app/visits/[id]/soap/SoapSection.tsx:90–99`):
```tsx
<header className="qm-lin-soap-section-head">
  <div className="qm-lin-soap-section-head-left">
    <span className="qm-lin-soap-section-eyebrow">
      <span className="qm-lin-soap-section-letter">{letter /* "S" | "O" | "A" | "P" */}</span>
      <span className="lbl">{label.toUpperCase() /* "SUBJECTIVE" | … */}</span>
    </span>
    <span className={cn('qm-lin-pill', STATUS_PILL_CLASS[status])}>
      {STATUS_LABEL[status] /* "DRAFTED" | "REVIEWED" | "SIGNED" */}
    </span>
  </div>
  {pulseHint && (
    <span className="qm-lin-soap-section-pulse">
      <span className="pulse-dot" aria-hidden />
      <span>{pulseHint.text /* e.g. "HPI · 4 elements" */}</span>
    </span>
  )}
</header>
```

**CSS** (`globals.css:3416–3487`):
- Letter chip (`.qm-lin-soap-section-letter`): 18×18 sage-tint square, 1px sage border (`rgba(122,166,140,0.28)`), sage-bright glyph, 4px radius, 10px / 600 weight.
- Eyebrow label (`.qm-lin-soap-section-eyebrow`): mono / 10.5px / 0.10em / uppercase / text-2 / 500 weight, 7px gap to chip.
- Status pill: see §4.2.
- Pulse meta (`.qm-lin-soap-section-pulse`): mono 9.5px / 0.08em uppercase / text-3, with 5px sage dot. Boost variant turns dot amber + text `#e3b950`.

### 4.2 Status pill — DRAFTED / REVIEWED / SIGNED
**Class map** (`SoapSection.tsx:65–69`):
```ts
const STATUS_PILL_CLASS = {
  drafted:  'qm-lin-pill--draft',
  reviewed: 'qm-lin-pill--sage',
  signed:   'qm-lin-pill--signed',
};
```

**CSS** (`globals.css:284–326`) — base `.qm-lin-pill` is a 22-26px-tall pill, 2px 8px padding, 4px radius, 11px / 500 weight, 0.02em letter-spacing. Variants:
- `--sage` / `--ready` / **REVIEWED**: bg `sage-tint` + text `sage-bright` + border `rgba(122,166,140,0.30)` (or `0.25`)
- `--review` (amber, used for "needs review"): bg `rgba(212,165,116,0.06)` + color `#e3b984` + border `rgba(212,165,116,0.25)`
- `--draft`: bg `surface-2` + text `text-2`
- `--signed`: transparent bg + text `text-3` + hairline border
- `--processing`: bg `rgba(116,168,201,0.06)` + color `#9bc4d9` + animated 5px sky dot, 1.4s pulse

There's **also** a section-status pill at `globals.css:3276–3304` (`.qm-lin-sec-status` / `--reviewed` / `--drafted` / `--signed`) used elsewhere — same colors, **mono** font, height 22px, 9px padding, letter-spacing 0.10em. Either pattern is correct; SOAP uses the first.

### 4.3 Top tab bar (SOAP / Transcript / Codes / Rx / Extras)
**Inline-styled in JSX** (`apps/transcribe-md/src/app/visits/[id]/visit-ready-view.tsx:545–657`) — there is **no** `qm-lin-tab` class. Pattern:

```tsx
<div role="tablist" style={{
  display: 'flex',
  borderBottom: '1px solid var(--color-linear-hairline)',
}}>
  {tabs.map((t, i) => (
    <button role="tab" aria-selected={active} style={{
      position: 'relative',
      padding: '8px 14px 10px',
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      letterSpacing: '0.07em',
      textTransform: 'uppercase',
      fontWeight: 500,
      color: active ? 'var(--color-linear-text)' : 'var(--color-linear-text-3)',
      background: 'transparent',
      border: 0,
      transition: 'color 100ms ease-out',
      gap: 6,
    }}>
      {t.icon /* lucide-react h-3.5 w-3.5 */}
      <span className="hidden sm:inline">{t.label}</span>
      {t.warning && (
        <span style={{
          width: 5, height: 5, borderRadius: 999,
          background: t.warning === 'critical'
            ? 'var(--color-linear-danger)' : 'var(--color-linear-warning)',
        }} />
      )}
      {active && (
        <span style={{
          position: 'absolute', left: 0, right: 0, bottom: -1,
          height: 1.5, borderRadius: '1px 1px 0 0',
          background: 'var(--color-linear-sage)',
        }} />
      )}
    </button>
  ))}
</div>
```

**Tabs in order**: SOAP Note · Transcript/Input · Codes · Rx · Extras · (Pipeline — dev-only). Each carries an icon (lucide `FileText`, `MessageSquare`, `Stethoscope`, `Pill`, `Sparkles`) at `h-3.5 w-3.5` plus optional warning dot (5px circle, danger/warning color).

### 4.4 SOAP body — markdown shim
The note body renders through a **30-line markdown shim** (`SoapSection.tsx:131–195`), not a full markdown lib. Supports H1, H2, bullets (`- ` or `* `), bold (`**…**`), paragraphs, blank-line spacers. Classes used:
- `.qm-lin-soap-md` — flex column, 1px gap
- `.qm-lin-soap-md-h1` — 16/600/-0.012em, text-1, mt-14
- `.qm-lin-soap-md-h2` — **mono 10.5/500/uppercase/0.07em, sage-bright**, mt-14 (this is the in-section sub-eyebrow for PMH / MEDICATIONS / etc.)
- `.qm-lin-soap-md-p` — 14/1.6, text-1
- `.qm-lin-soap-md-ul` — disc bullets, 22px padding-left, 14/1.55 text-2, 4px gap between li
- `.qm-lin-soap-md-spacer` — 6px-tall blank spacer

### 4.5 PMH / Meds / ROS bullet pattern
Bullets are rendered as `.qm-lin-soap-md-ul` (disc, 22px padding-left, 4px gap). Bold key (`**Lisinopril 20 mg**`) renders as `<strong>` with no extra CSS. **No corner ribbons, no flag chips, no side-rail hooks** in production — bullets are plain prose.

### 4.6 Vital tokens inside SOAP body
When SOAP includes vitals, they render as inline mono spans (`globals.css:3641–3655`):
```html
<span class="vital-tok">
  <span class="v-lbl">BP</span> 138/86
</span>
```
Mono 13px / tabular-nums / text-1, with 10px text-3 uppercase label.

### 4.7 Bracketed clinician-asks — **does not exist in production**
The Round 2 brief described `[Unverified entry — likely transcription error]` as an inline pattern. **No such pattern exists in code today** (verified by `grep -r "\[Unverified\|\[Allergies:" src/` returns zero). Surveyed surfaces:
- SOAP body: pure markdown shim, no bracketed ask renderer.
- Critical Rx flags: surface in the **right-side Rx warnings rail** (`RxWarningsRail`), not inline.
- "Needs review" state: surfaces as a status pill on the section header (`.qm-lin-pill--review`).

The closest analog is the **Rx warnings rail** at `apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx` — see §4.10.

If you're going to introduce inline asks, build them as a **new** pattern; do not assume there's a production CSS class waiting.

### 4.8 Billing support rail (`CodingRail`)
The right-rail "Billing support" component (`apps/transcribe-md/src/components/visits/CodingRail.tsx`). Top → bottom composition:
1. **Head** (`qm-lin-coding-rail-head`): pulse + "Billing support" label / "AMA 2021" label · current code (mono 18/600) + level pill ("Level 3") + optional "doctor-set" amber badge + override `▾` dropdown (mono 10/uppercase).
2. **EmTimeTracker** (`qm-lin-coding-time`): clock icon · "Visit time" + bold mono number · meter (4px tall, sage gradient `sage-deep → sage`) · "30+ MIN" rule label.
3. **EmCheckList** (`qm-lin-em-checklist`): 3 criterion groups (history / exam / mdm), each with mono heading + count + dashed-hairline divider. Rows are 14×14 ok/warn icons (sage / amber circles with check / dot glyphs) + 12.5/500 head + 11.5/text-3 sub. Warn rows tinted amber.
4. **CTA block** (`qm-lin-coding-cta`): sage primary `Bump to 99214 · +$32` button (full-width, 11px 14px padding, 13/600, sage `#7AA68C` bg / `#0d1611` text — the dark-on-sage contrast lock — with 4px sage glow on hover); ghost outline `Confirm 99213 · sign` button + `⌘ ↵` shortcut hint; mono `AMA 2021 · time-based` foot meta.
5. **BumpModal** (`qm-lin-bump-modal-*`): 440px-max modal opened by the bump button.

**Sticky position** — `top: 60px`, `width: 340px`, `align-self: start`. On `<= 1080px` viewports, the rail collapses to a **bottom drawer** with a 36×3 grab handle (`globals.css:4506–4546`).

### 4.9 Bump CTA — exact spec
**CSS** at `globals.css:4174–4234`. Critical: the sage CTA uses `color: #0d1611` (NOT a token — hand-mixed dark green) on `var(--color-linear-sage)` background. This contrast ratio is the only place a non-token hex is allowed in chrome — a regression bumped it once and it failed audit.

```css
.qm-lin-coding-bump {
  background: var(--color-linear-sage);  /* #7AA68C */
  color: #0d1611;                         /* dark sage — DO NOT change */
  padding: 11px 14px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: -0.005em;
}
.qm-lin-coding-bump:hover {
  background: #88b599;                    /* one step brighter */
  transform: translateY(-1px);
  box-shadow: 0 0 0 4px rgba(122, 166, 140, 0.18);
}
```

The CTA carries a **left half** (small "BUMP TO" mono uppercase eyebrow + arrow + new code) and a **right half** (revenue delta in mono 14/600, e.g. `+$32`).

### 4.10 Rx warnings rail + critical override
Right rail next to Rx list. Severity-grouped (**CRITICAL → SERIOUS → MODERATE → INFO**), each card is `.qm-warn-{severity}`:
- 3px left edge in severity color
- 36×36 icon tile (rounded 8px) with severity glyph (`⚠` for warn-tier, `ⓘ` for info)
- 17/500 sans headline + Rx-id chip
- 14/600 sans action tile (re-stating the recommended action)
- mono "HEARD → GUESS" transcribed comparison with confidence pill
- risks list (6px sage dot per item)
- Critical-only: `Override…` button (mono 11/uppercase, danger-tinted) → opens `<OverrideConfirmModal>` → on success swaps to a green `✓ Overridden — sign cleared` chip.

The sign API (`/api/visits/[id]/sign`) **blocks** READY → SIGNED until every critical warning has an override row. The chip swap is the doctor's signal that the gate is cleared.

### 4.11 Inline edit hint + section editing
Each SOAP section body is a hover-editable region (`globals.css:3507–3548`). Hover shows:
- background `rgba(255,255,255,0.022)`
- border `rgba(255,255,255,0.08)`
- a mono 10/0.08em uppercase edit hint that fades in (opacity 0 → 1 over 100ms)

Focus state adds a 2px sage box-shadow ring at `rgba(122,166,140,0.32)` — explicit WCAG 2.4.7 AA compliance.

The actual edit textarea (`qm-lin-soap-inline-edit-ta`) is **mono 13/1.55** on `surface-1`, sage border at 42% alpha, 3px sage glow. Mono on edit is intentional — clinicians often dictate code-like content (drug names, doses, ICDs) into freeform fields, and tabular-numerics-by-default avoids alignment quirks during paste/edit.

### 4.12 Bottom action strip — last edit + Copy SOAP
Below the SOAP body (`SoapBody.tsx:86–97`):
```tsx
<div className="qm-lin-soap-notebody-foot">
  <div className="qm-lin-soap-notebody-foot-meta">
    <span className="dot" aria-hidden />
    <span>4 sections{lastEditLabel && ` · last edit ${lastEditLabel}`}</span>
  </div>
  <button className="qm-lin-btn"><Copy className="h-3.5 w-3.5" /> Copy SOAP</button>
</div>
```
- Mono 10.5/0.08em uppercase, text-3 color, 4px sage dot.
- Top hairline rule, 14px padding-top.

### 4.13 Buttons
Two flavours, both at `globals.css:366–440`:
- **Ghost outline** (`.qm-lin-btn`): transparent bg, hairline border, text-2 → text-1 on hover. 6px radius, 12px / 500, 6×12 padding. Used for everything secondary.
- **Sage primary** (`.qm-lin-btn-primary`): sage bg, `#0d1611` text (same dark-sage as Bump CTA), 0.5px translate-down on press, 30% sage box-shadow ring.

Both get a mobile floor of `min-height: 44px` at viewport ≤ 639px (Apple HIG).

---

## 5 · App-shell chrome (page-level layout, not in scope but useful context)

```
.qm-lin-app   → 240px sidebar | content (single column < 980px)
.qm-lin-chrome → sticky 48px top bar, hairline-bottom, blurred translucent
.qm-lin-sidebar → 240px, surface-1 bg, hairline right border, sticky to top bar
.qm-lin-cmdk  → search-shaped Cmd+K trigger pill in the chrome
```
The visit-ready view renders inside `<AppFrame>` (`components/ui/app-frame.tsx`), which composes the sidebar + topbar + main slot. Don't redesign this — just reserve the same outer dimensions when mocking.

---

## 6 · What NOT to redesign — preserve byte-identical

These patterns are part of the **QuillMD contract** and have downstream dependencies (audit logs, sign-API gates, analytics). Do not rename or restructure:

1. **SOAP section eyebrow + REVIEWED chip** (§4.1, §4.2) — letter chip + mono uppercase + status pill, in that order, with sage-tinted "REVIEWED".
2. **Top tab bar** (§4.3) — SOAP / Transcript / Codes / Rx / Extras (in order), mono uppercase, sage 1.5px underline on active, 5px warning dot. The inline-styled JSX is intentional — Tailwind has nothing better.
3. **Right-rail Billing support** (`CodingRail` — §4.8) — head + time tracker + checklist + sage CTA + confirm-sign + foot meta. The sage `#0d1611` text-on-sage CTA contrast is locked.
4. **Rx warnings rail + critical-override flow** (§4.10) — `.qm-warn-{severity}` class names are protected. The override button → `OverrideConfirmModal` → green ✓ chip swap is wired into the sign-API gate.
5. **Color discipline** — pure dark canvas, single sage accent, hairline borders, 4-weight text ramp. **No** secondary accent colors, **no** gradients beyond the sage CTA glow / brand mark, **no** drop shadows except the modal `0 30px 80px rgba(0,0,0,0.6)`.
6. **Typography discipline** — Inter for chrome + body, JetBrains Mono for IDs / timestamps / eyebrows / pills. **No serif. No script. No display fonts.**
7. **REDUCED-motion gates** — every animation must drop to `none` under `@media (prefers-reduced-motion: reduce)`. This is enforced for accessibility and mockups should mirror it.

---

## 7 · What CAN evolve (the redesign target)

- **SOAP section layout** — currently single-column markdown prose inside a hairline card. The previous wall-of-prose was the complaint. **Layout, hierarchy, and scannability of dense subsections (PMH / Medications / ROS / Exam) are the redesign target.**
- **How asks / flags surface** — currently the only inline mechanism is the section-status pill (DRAFTED / REVIEWED). Critical Rx surfaces in a separate right rail. There is **no** bracketed-ask UI in production today — if you introduce inline asks, you're inventing a new pattern (welcome, but be explicit).
- **Subsection rhythm** — the markdown H2 (sage mono uppercase) is the only sub-eyebrow tool today. Two-column splits, vital-token grids, problem-cards, side-anchored marginalia are all open territory.
- **Visit-time → billing** — the EmTimeTracker is a meter today. Surfacing the gap-to-99214 more prominently, or anchoring it to the relevant SOAP section, is fair game.
- **Mobile / iPad reflow** — production has a bottom-drawer Coding Coach below 1080px and 44px tap floors. Mocks should reflow in the same spirit but layout particulars are yours.

---

## 8 · Reference file index

| Path                                                                              | Lines | What |
|-----------------------------------------------------------------------------------|-------|------|
| `apps/transcribe-md/src/app/globals.css`                                          | 4577  | All `qm-lin-*` + `qm-warn-*` utilities (single source of truth) |
| `apps/transcribe-md/src/app/layout.tsx`                                           |       | Inter + JetBrains Mono next/font wiring |
| `apps/transcribe-md/src/app/visits/[id]/visit-ready-view.tsx`                     | 936   | Tab bar (`function Tabs`) + page composition |
| `apps/transcribe-md/src/app/visits/[id]/soap/SoapSection.tsx`                     | 195   | Section header + markdown shim |
| `apps/transcribe-md/src/app/visits/[id]/soap/SoapBody.tsx`                        | 100   | Stacks 4 sections + foot meta |
| `apps/transcribe-md/src/app/visits/[id]/soap/SoapInlineEdit.tsx`                  |       | Hover-edit affordance |
| `apps/transcribe-md/src/app/visits/[id]/rx-warnings-rail.tsx`                     | 319   | Severity-grouped Rx rail |
| `apps/transcribe-md/src/app/visits/[id]/rx-tab.tsx`                               | 479   | Rx list + rail composition |
| `apps/transcribe-md/src/components/visits/CodingRail.tsx`                         | 546   | Billing-support right rail |
| `apps/transcribe-md/src/components/visits/EmCheckList.tsx`                        |       | 3 criterion groups |
| `apps/transcribe-md/src/components/visits/EmTimeTracker.tsx`                      |       | Visit-time meter |
| `apps/transcribe-md/src/components/visits/BumpCtaButton.tsx`                      |       | Sage primary CTA composition |
| `apps/transcribe-md/src/components/visits/BumpModal.tsx`                          |       | 440px-max bump-suggestions modal |
| `apps/transcribe-md/src/components/rx/override-confirm-modal.tsx`                 |       | Critical-Rx override (sign-API gate) |
| `apps/transcribe-md/src/components/ui/app-frame.tsx`                              |       | App shell wrapper |

---

## 9 · Quick-paste palette (for mockup CSS)

```css
:root {
  --bg:           #08090a;
  --surface-1:    #0d0e10;
  --surface-2:    #131416;
  --surface-3:    #1a1c1e;
  --border:       #21232a;
  --border-strong:#2c2f38;
  --hairline:     rgba(255,255,255,0.05);
  --hairline-2:   rgba(255,255,255,0.08);
  --text:         #f7f8f8;
  --text-2:       #b4bcc8;
  --text-3:       #828995;
  --text-4:       #4b5159;          /* large/decorative only */
  --sage:         #7aa68c;
  --sage-bright:  #9bc4a8;
  --sage-soft:    #5d8a73;
  --sage-deep:    #2f5040;
  --sage-tint:    rgba(122,166,140,0.13);
  --sage-glow:    rgba(122,166,140,0.18);
  --warning:      #d4a437;          /* amber — review */
  --danger:       #d4574a;          /* coral — critical */
  --info:         #5b8db8;
  --row-hover:    rgba(255,255,255,0.03);
  --row-active:   rgba(255,255,255,0.05);
  --font-sans:    'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  --font-mono:    'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
}
body {
  background: var(--bg);
  color: var(--text);
  font-family: var(--font-sans);
  font-size: 13px;
  line-height: 1.45;
  letter-spacing: -0.005em;
  font-feature-settings: 'cv11', 'ss01';
  -webkit-font-smoothing: antialiased;
}
```

That's the contract. New mockups that match these tokens will feel like the next iteration of the same product. Mockups that drift into Lora / cream / amber-on-tan / drop-shadow territory will not.
