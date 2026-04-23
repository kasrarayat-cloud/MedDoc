# Rx Warning Card — Design Spec

**Component:** `RxWarningCard`
**Parent system:** QuillMD — dark theme, purple accent
**Last updated:** April 23, 2026
**Status:** Ready for implementation

---

## 1. Purpose

The Rx Warning Card surfaces AI-confidence and clinical-rules issues on prescription lines of an AI-drafted SOAP note. It **must** let a physician resolve or understand a warning in under two seconds of glance time, while preserving the full clinical rationale for those who want it.

One component, three severity levels:
- `critical` — blocks signing; requires deliberate resolution
- `warning` — needs attention; physician acknowledges
- `info` — FYI; compact, no action required

---

## 2. Design tokens

All tokens referenced below exist in `app/tokens.css`. No new root tokens were added.

### 2.1 Colors — global

| Purpose                | Token               | Hex       |
|------------------------|---------------------|-----------|
| Page background        | `--bg`              | `#07060C` |
| Card background-1      | `--bg-1`            | `#0C0A16` |
| Card background-2      | `--bg-2`            | `#14111F` |
| Border default         | `--line`            | `#26222F` |
| Border soft            | `--line-soft`       | `#191524` |
| Border strong          | `--line-strong`     | `#3A3445` |
| Text primary           | `--fg`              | `#F5F2FA` |
| Text secondary         | `--fg-2`            | `#B9B2C9` |
| Text tertiary          | `--fg-3`            | `#7E7791` |
| Text quaternary        | `--fg-4`            | `#4B4558` |
| Accent (guess text)    | `--accent-bright`   | `#A87CFF` |

### 2.2 Colors — severity

The card exposes 4 CSS custom properties that the three severity modifiers rewrite:

```css
.qm-warn               /* default = critical */
  --sev-hue-r:   251;  /* rgb channels, used for rgba() ramps */
  --sev-hue-g:   113;
  --sev-hue-b:   133;
  --sev-fg:       rgb(251,113,133);   /* icon + badge bg + rail + dots     */
  --sev-fg-2:     rgb(253,164,175);   /* action text, headline accent      */
  --sev-bg:       rgba(251,113,133, 0.04);   /* card tint                  */
  --sev-border:   rgba(251,113,133, 0.28);   /* card border                */
  --sev-border-strong: rgba(251,113,133, 0.55); /* badge + primary button  */
```

| Severity  | `--sev-hue`       | `--sev-fg`   | Source token  |
|-----------|-------------------|--------------|---------------|
| critical  | `251, 113, 133`   | `#FB7185`    | `--coral`     |
| warning   | `251, 191,  36`   | `#FBBF24`    | `--amber`     |
| info      | ` 96, 165, 250`   | `#7DB7FF`    | `--accent-c`  |

> **Never** apply `--sev-fg` as a flat fill on the card. It lives only on the rail, icon square, badge, action tile, risk dots, and primary button border. Keeping the rest of the card neutral is what makes the red mean something.

### 2.3 Typography

```
--serif: 'Source Serif 4', Georgia, serif;
--sans:  'Inter Tight', -apple-system, BlinkMacSystemFont, sans-serif;
--mono:  'JetBrains Mono', ui-monospace, SFMono-Regular, monospace;
```

| Role                         | Family | Size / Weight / Tracking        |
|------------------------------|--------|---------------------------------|
| Headline                     | serif  | 19 / 500 / -0.015em             |
| Action line                  | sans   | 14.5 / 600 / -0.005em           |
| Risk bullet prose            | serif  | 13.5 / 400 / -0.005em           |
| Risk outcome sub-line        | sans   | 12.5 / 400 / -0.005em           |
| Severity badge               | mono   | 10 / 600 / 0.14em, UPPERCASE    |
| Field label (`Rx · Line 2`)  | mono   | 10 / 400 / 0.14em, UPPERCASE    |
| Transcribed value            | mono   | 14 / 500 / 0                    |
| Section mini-labels          | mono   | 9–10 / 400 / 0.14–0.16em, UPPERCASE |
| Next-step body               | sans   | 13 / 400 / -0.005em             |
| Button labels                | sans   | 12.5 / 500 / -0.005em           |
| Keyboard hint (`⇧O`)         | mono   | 10 / 400 / 0                    |
| Details body (expanded)      | serif  | 13 / 400 / -0.005em, LH 1.65    |

### 2.4 Spacing, radii, shadow

| Token                | Value                             |
|----------------------|-----------------------------------|
| Card radius          | `12px`                            |
| Inner tile radius    | `8–9px`                           |
| Badge radius         | `4px`                             |
| Button radius        | `7px`                             |
| Icon square          | `36 × 36, radius 10px, border 1`  |
| Card inner padding   | `18/22/14/22` (T/R/B/L) header; `22px` horizontal rhythm |
| Vertical stride      | Header → action: `10`; action → trans: `14`; trans → risks: `14`; risks → next: `14`; next → details: `0` (border-top) |
| Rail width           | `3px`                             |
| Severity shadow      | Inset 1px white top on badge + `0 1px 4px rgba(0,0,0,.3)` |
| Action tile shadow   | Inset `0 0 0 1px rgba(sev,.04)` ring — subtle halo, not a drop shadow |

### 2.5 Motion

| Element              | Property           | Timing                 |
|----------------------|--------------------|------------------------|
| Button hover         | `all`              | 150ms ease             |
| Dismiss-button hover | `color, border, bg`| 150ms ease             |
| Details toggle icon  | `transform`        | 200ms ease             |
| Details body         | (no slide anim — content swaps; chevron rotates) | |
| Reduced motion       | Respect `prefers-reduced-motion: reduce` — disable chevron rotation. |

---

## 3. Component anatomy

The card is eight stacked regions, each with a single job. Indices match the numbered callouts in `§02 Anatomy` of the design doc.

```
┌─ 3px severity rail ─────────────────────────────────────┐
│  ┌──────┐  ┌ badge ┐ ┌ field ┐           ┌───┐          │
│  │ icon │  │CRITIC.│ │Rx·L2 │           │ X │ ① ②     │  → Header
│  └──────┘  └───────┘ └──────┘           └───┘          │
│            Cannot verify medication.                    │
├─────────────────────────────────────────────────────────┤
│  [ ⊘  Do NOT prescribe until confirmed. ]               │  → ③ Action tile
├─────────────────────────────────────────────────────────┤
│  HEARD               PHONETIC GUESS                     │
│  "abirrobing"    →   possibly ibuprofen?                │  → ④ Transcribed
├─────────────────────────────────────────────────────────┤
│  PATIENT-SPECIFIC RISKS · 2  ────────────               │  → ⑤ Risks
│  • Patient is on [Valsartan + HCTZ] (ACE-I + thiazide). │
│    → Adding an NSAID risks [acute kidney injury] …      │
│  • Patient is on [Omeprazole] — active GI prophylaxis.  │
│    → NSAIDs may [aggravate gastric irritation].         │
├─ dashed border ─────────────────────────────────────────┤
│  📞  NEXT  Confirm medication name verbally with …      │  → ⑥ Next step
├─────────────────────────────────────────────────────────┤
│  › Show clinical reasoning          transcript 14:22    │  → ⑦ Details
│    (open)                                               │
├─ solid border ──────────────────────────────────────────┤
│  [Edit medication] [Call provider]     [Override ⇧O]    │  → ⑧ Actions
└─────────────────────────────────────────────────────────┘
```

### 3.1 Region-by-region

| # | Region          | Contents                                                                 | Width  | Height (approx) |
|---|-----------------|--------------------------------------------------------------------------|--------|-----------------|
| 1 | Header          | 36×36 icon square + badge + field label + headline + optional dismiss   | full   | 70–80px         |
| 2 | *Severity pill* | Mono `CRITICAL / WARNING / INFO`, height 20px, padding 0/8/0/7, radius 4 | auto   | 20px            |
| 3 | Action tile     | 18×18 icon + bold sans sentence; tinted `--sev-fg` @ 10%                | full - 44 | 44–48px      |
| 4 | Transcribed     | 2 mono fields separated by `→`; divider line before the guess field      | full - 44 | 52–56px      |
| 5 | Risks           | Stacked tiles; each tile: 6px dot + serif sentence + optional outcome line | full - 44 | variable     |
| 6 | Next step       | Dashed border; phone icon + `NEXT` mono label + sentence                 | full - 44 | 40–44px       |
| 7 | Details toggle  | Button row with chevron + label + source count; expands to serif body   | full   | 36px collapsed / content + 14px padding expanded |
| 8 | Actions         | 2–3 buttons; right-aligned spacer; severity-tinted primary               | full   | 52px            |

### 3.2 Risk-tile structure

```
[ • ]  Patient is on <b>Valsartan + HCTZ</b> (ACE-I + thiazide).
        → Adding an NSAID risks <b>acute kidney injury</b> ("triple whammy").
```

- Dot: `6 × 6` circle, `--sev-fg`, with `0 0 0 3px rgba(sev, .12)` halo.
- Primary line — serif, 13.5px; bold fragments render as **sans 12.5px**, weight 600, `--sev-fg-2`, with a `rgba(sev, .08)` pill background (`padding: 1px 6px; radius: 4`). Mixing families signals "this fragment is a drug/fact, not prose."
- Outcome sub-line — sans 12.5px, `--fg-3`, prefixed with `→ `. Bolded fragments in this line are `--sev-fg-2` without the pill background.

---

## 4. Severity variants

### 4.1 Critical

- **Blocks signing.** Cannot be dismissed — only resolved.
- Shows: all 8 regions.
- Action tile background: `rgba(coral, .10)`, border `rgba(coral, .28)`.
- Actions row: `Edit medication` (primary) · `Call provider` · `Override & sign anyway` (⇧O).
- Right-side dismiss **X** button is hidden (`onDismissLabel === null` in the component API).

### 4.2 Warning

- Shows: all 8 regions, but the **action tile** is tonally softer (amber vs coral).
- Actions row: `Edit` (primary) · `Call provider` · `Acknowledge` (A).
- Dismiss button visible (optional).

### 4.3 Info

- **Compact mode:** hides regions 4 (transcribed), 5 (risks), 6 (next step), 7 (details), 8 (actions).
- Action tile keeps less weight: `padding: 8px 14px`, text weight 500 (not 600).
- Exactly three parts render: icon square · badge + field · action line.
- Single action (if any) is `Dismiss`.

### 4.4 Shared button model

| Severity  | Primary          | Secondary       | Tertiary (right-aligned)  | Keystroke |
|-----------|------------------|-----------------|---------------------------|-----------|
| critical  | Edit medication  | Call provider   | Override & sign anyway    | ⇧O        |
| warning   | Edit             | Call provider   | Acknowledge               | A         |
| info      | —                | —               | Dismiss                   | Esc       |

Critical warnings **never** offer a passive "Dismiss." Overriding is a deliberate action that opens a confirmation modal and is recorded in the audit log.

---

## 5. Collapsed vs expanded

Details default to **collapsed**. The toggle is a full-width button row with:

- Left: chevron (13×13, rotates 90° when open), label `Show / Hide clinical reasoning`
- Right: source count, mono, `--fg-4`, e.g. `Transcript 14:22 · clinical rules v2.1`

When expanded:
- Dashed 1px top border appears inside the details region (visual separator inside the card)
- Body renders serif 13px paragraphs, LH 1.65, `--fg-2`
- Trailing source citation re-displays as a mono subline prefixed with `↳`

Details never contain interactive elements beyond inline links — this is read-only context.

---

## 6. Keyboard shortcuts

Shortcuts are local to the **focused** card (i.e. once the physician tabs into it or opens it from the Rx slip).

| Key                 | Action                                    | Available on   |
|---------------------|-------------------------------------------|----------------|
| `Enter` / `Space`   | Activate focused button                   | all            |
| `Tab` / `Shift+Tab` | Move between buttons, toggle, dismiss     | all            |
| `D`                 | Toggle details (show/hide clinical)       | all            |
| `E`                 | Primary action (Edit / Edit medication)   | critical, warn |
| `C`                 | Call provider                             | critical, warn |
| `A`                 | Acknowledge                               | warning        |
| `⇧ O`               | Override & sign anyway → confirm modal    | critical       |
| `Esc`               | Dismiss (info only) / close details       | info, any open |

Buttons render their keystroke as a trailing `.qm-warn-kbd` chip (mono 10px, 2×5 padding, `rgba(0,0,0,.2)` bg, 1px `rgba(255,255,255,.08)` border). Respect the app-wide `⌘K` command palette — it takes precedence when open.

---

## 7. Interaction states

### 7.1 Buttons

| State     | Secondary button                                     | Primary (severity-tinted) button                                  |
|-----------|------------------------------------------------------|-------------------------------------------------------------------|
| default   | bg `rgba(255,255,255,.02)`, border `--line`, fg `--fg-2` | bg gradient `rgba(sev,.22)→rgba(sev,.10)`, border `--sev-border-strong`, fg `--sev-fg-2` |
| hover     | bg `rgba(255,255,255,.04)`, border `--line-strong`, fg `--fg` | bg gradient `rgba(sev,.32)→rgba(sev,.16)`, fg `#fff`          |
| focus     | outline `2px solid rgba(139,92,255,.55)`, offset `2`, radius `6` | same outline — uses app-wide `:focus-visible` rule |
| active    | bg `rgba(255,255,255,.06)`                           | brightness(0.95), translateY(0)                                  |
| disabled  | opacity `.45`, cursor `not-allowed`                  | opacity `.45`, cursor `not-allowed`                              |

### 7.2 Details toggle

| State    | Style                                                    |
|----------|----------------------------------------------------------|
| default  | fg `--fg-3`                                              |
| hover    | fg `--fg-2`, bg `rgba(255,255,255,.02)`                  |
| open     | chevron rotated 90°, source count stays `--fg-4`         |
| focus    | standard focus outline                                   |

### 7.3 Dismiss (X) button

| State    | Style                                                    |
|----------|----------------------------------------------------------|
| default  | transparent bg, transparent border, fg `--fg-3`          |
| hover    | bg `rgba(255,255,255,.03)`, border `--line`, fg `--fg`   |
| focus    | standard focus outline, radius `6`                       |

### 7.4 Card-level

The card itself has **no hover state** — it isn't a clickable surface. Nested elements (buttons, toggle) own their own states.

---

## 8. Accessibility

### 8.1 Semantics

```html
<section role="alert" aria-labelledby="warn-123-headline">
  <h3 id="warn-123-headline">Cannot verify medication.</h3>
  …
  <button aria-expanded="false" aria-controls="warn-123-details">
    Show clinical reasoning
  </button>
  <div id="warn-123-details" hidden>…</div>
</section>
```

- `role="alert"` + `aria-live="assertive"` for **critical**. Warning uses `role="status"` + `aria-live="polite"`. Info uses `role="note"` (no live region — the physician is already scanning the Rx slip).
- `aria-labelledby` points at the serif headline.
- Details toggle: `aria-expanded` + `aria-controls`; body uses `hidden` attribute (not `display: none`) so screen readers can address it once expanded.
- Severity badge is decorative; **do not** mark `aria-hidden`. Include it in the accessible name via visually-hidden text if needed: `<span class="sr-only">Critical. </span>` before the headline.

### 8.2 Color contrast

All text meets WCAG AA (4.5:1) on the card's blended background. Verified against:

| Text                  | On bg                               | Ratio  |
|-----------------------|-------------------------------------|--------|
| `--fg` headline       | card bg (coral 4% on `#07060C`)    | 15.8:1 |
| `--fg-2` action text  | action tile (coral 10%)            | 9.2:1  |
| `--sev-fg-2` action   | action tile (coral 10%)            | 6.3:1  |
| `--fg-3` mono labels  | card bg                             | 5.4:1  |
| `--fg-4` source citation | card bg                          | **3.9:1** — acceptable for decorative timestamp only; never use for actionable text |

**Never** use `--sev-fg` (full saturation) as a text color on dark bg smaller than 18px — it clips on the coral end. Use `--sev-fg-2` (desaturated +20) for any text ≤ 16px.

### 8.3 Keyboard & focus

- All actions reachable by keyboard in source order: dismiss → toggle → buttons (primary first).
- Focus ring is the app's standard `2px solid rgba(139,92,255,.55)` with 2px offset and `6px` radius — do not override inside the card.
- When the card mounts, focus does **not** auto-move to it (that would steal from the physician's scanning). The Rx slip scrolls the card into view with `scroll-margin-top: 80px`.

### 8.4 Motion & density

- Chevron rotation, toggle hover — all respect `prefers-reduced-motion: reduce`. Disable the 200ms rotation; swap chevron glyph instead.
- Density is fixed (the card is already dense). Do not add a "compact" mode — info already is the compact variant.

### 8.5 Screen readers — recommended reading order

```
Critical. Rx, Line 2. Cannot verify medication.
Do not prescribe until confirmed.
Heard: abirrobing. Phonetic guess: possibly ibuprofen.
Two patient-specific risks.
 1. Patient is on Valsartan and HCTZ, an ACE inhibitor plus thiazide.
    Adding an NSAID risks acute kidney injury, the triple whammy effect.
 2. Patient is on Omeprazole, active GI prophylaxis.
    NSAIDs may aggravate gastric irritation.
Next step: Confirm medication name verbally with the prescribing provider before signing.
Show clinical reasoning. Transcript 14:22, clinical rules v2.1.
Edit medication, button. Call provider, button. Override and sign anyway, button. Shift O.
```

---

## 9. Component API (implementation reference)

```ts
type Severity = 'critical' | 'warning' | 'info';
type ActionKind = 'ban' | 'alert' | 'info';

interface RiskLineFragment {
  t: string;
  b?: boolean;  // bold pill
}

interface RxWarning {
  sev: Severity;
  field: string;                        // e.g. "Rx · Line 2"
  headline: string | ReactNode;
  action?: string | ReactNode;
  actionKind?: ActionKind;              // default 'ban' for critical, 'alert' for warning, 'info' for info
  heard?: string;
  guess?: string;
  risks?: Array<{
    parts: RiskLineFragment[];
    outcome?: RiskLineFragment[];
  }>;
  nextStep?: string | ReactNode;
  details?: string[];                   // paragraphs; collapsible
  source?: string;                      // citation
  defaultOpen?: boolean;                // details initial state
  compact?: boolean;                    // auto-set true for info
  onDismiss?: () => void | null;        // null hides dismiss X
  onEdit?: () => void;
  onCall?: () => void;
  onAcknowledge?: () => void;
  onOverride?: () => void;              // opens confirm modal
}
```

---

## 10. What NOT to change

- Don't add a "severity: blocker" level. Critical already blocks signing.
- Don't let info ever render action buttons beyond Dismiss. If the FYI requires resolution, it should be a warning.
- Don't tint the card background at full severity saturation (>5%) — you lose the contrast the action tile relies on.
- Don't move the action tile below the transcribed/risks region "to test." The eye-path is the whole point.
- Don't swap the serif headline for sans. Serif is the system's "this is a clinical statement" voice.

---

**Source files:**
- Live spec page — `screens/Unverified Rx Warning.html`
- Tokens — `app/tokens.css`
- Screenshots — `exports/01..06-*.png`
