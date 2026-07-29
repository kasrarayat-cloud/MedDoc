# Design tokens — "Rounds"

**This document is the authority.** Where a component and this file disagree,
this file is right and the component is a bug. Where this file and a rendered
screenshot disagree, this file is still right — screenshots go stale.

Rounds is the merge of two directions: **Ward Board** (the dark stage, the
patient-lane × stage-column matrix, position-awareness, blocker language) and
**Focus Flow** (the spotlit sheet, the sequential gates, the deep paper shadow).
Neither shipped alone. Where they conflicted, the resolution is recorded here
rather than left to whoever reads the CSS next.

---

## The one idea

**The stage is dark. The paper is not.**

Everything that is *software* — navigation, queue, gates, chrome — sits on a dark
stage. Everything that is *the clinical document* sits on paper: near-white, warm,
serif, shadowed, and read-only. A doctor should be able to tell at a glance
whether they are looking at the app or at the note, without reading a word.

That split is why there are two colour families below instead of one, and why the
paper family is not simply "the light theme".

---

## Colour

### Stage (the application)

| Token | Value | Use |
|---|---|---|
| `--rounds-stage-bg-1` | `#232B3A` | radial gradient inner |
| `--rounds-stage-bg-2` | `#171D27` | radial gradient mid |
| `--rounds-stage-bg-3` | `#12161E` | radial gradient outer |
| `--rounds-surface-1` | `#161B24` | recessed / lowest |
| `--rounds-surface-2` | `#1E2530` | default card |
| `--rounds-surface-3` | `#252D3A` | raised / hover |
| `--rounds-line-1` | `#2C3442` | hairline, default |
| `--rounds-line-2` | `#3A4353` | emphasised border |
| `--rounds-text-1` | `#E7EBF1` | primary on stage |
| `--rounds-text-2` | `#98A2B1` | secondary |
| `--rounds-text-3` | `#7C8694` | tertiary / kickers |

The stage background is a **radial** gradient, not linear: the lightest point sits
behind the content the clinician is meant to be looking at, which is what makes
the sheet in Screen 2 read as spotlit rather than merely pasted on.

### Paper (the clinical document)

| Token | Value | Use |
|---|---|---|
| `--rounds-paper-1` | `#FCFCFA` | the sheet |
| `--rounds-paper-2` | `#F3F4EF` | inset / alternating |
| `--rounds-paper-3` | `#ECEDE7` | wells, quiet blocks |
| `--rounds-ink` | `#191E26` | clinical prose |
| `--rounds-ink-muted` | `#525A66` | labels, meta on paper |
| `--rounds-paper-line-1` | `#E7E8E3` | hairline rules |
| `--rounds-paper-line-2` | `#D8DAD3` | section dividers |

Warm off-white, never `#FFFFFF`. Pure white next to a dark stage glares, and the
document is the thing a clinician stares at longest.

### Accent

| Token | Value | Use |
|---|---|---|
| `--rounds-accent` | `#5B5BD6` | primary actions, focus rings |
| `--rounds-accent-hover` | `#4A49C4` | hover / active |
| `--rounds-accent-tint-10` | `rgba(91,91,214,.10)` | selected row wash |
| `--rounds-accent-tint-16` | `rgba(91,91,214,.16)` | stronger wash |

### Status

| Token | Value | Meaning |
|---|---|---|
| `--rounds-critical` | `#C93A2E` | critical Rx, failure — borders, glyphs, fills |
| `--rounds-critical-on-dark` | `#FF8D7E` | critical red as **small text on a dark surface** |
| `--rounds-ready` | `#187A4E` | ready to review; completed track runs |
| `--rounds-em` | `#C4841C` | E/M amber |
| `--rounds-em-fill` | `#E29A34` | **E/M action buttons only** |
| `--rounds-processing` | `#3B6FD4` | in pipeline |
| `--rounds-signed` | `#6B7480` | signed accents — **not small text on dark** (fails AA; use `--rounds-text-2`) |

⚠️ **`--rounds-signed` is grey on the stage, but a completed track run draws in
`--rounds-ready` green.** Those are not the same thing and the difference is
deliberate: the *card* is finished business and recedes; the *line* is a
successful journey and should read as such at a glance across the board.

⚠️ **Critical has two tokens, for the same reason E/M does.** `#C93A2E` is a
border and fill colour; as small text on `--rounds-surface-2` it fails AA, which
axe caught on the board's REC kicker. Borders and glyphs keep the true red; text
on dark uses `--rounds-critical-on-dark`.

⚠️ **E/M has two tokens.** `--rounds-em` is the status colour; `--rounds-em-fill`
is lighter and exists only so an amber button clears AA against dark text. Do not
fill a button with `--rounds-em`.

---

## Type

| Family | Token | Use |
|---|---|---|
| Bricolage Grotesque | `--rounds-font-display` | display, page titles, big numerals |
| Figtree | `--rounds-font-ui` | all UI text |
| Source Serif 4 | `--rounds-font-clinical` | **ALL clinical prose** |
| JetBrains Mono | `--rounds-font-mono` | labels, MRNs, codes, drug-pair lines |

**Source Serif 4 covers every piece of clinical prose, including the default
QuillMD paper template.** Not just quotes, not just the note body — if a clinician
would read it as part of the record, it is serif. Clinical prose is read
differently from interface text, and the typeface is the cue.

Clinical body: **15–16.5px / 1.7**. Wide for a UI, correct for prose.

**Mono is for things that are looked up, not read**: an MRN, a CPT code, a drug
pair, a section kicker. If a human scans it character by character, it is mono.

---

## Shape and depth

- Radii **9–18px**. Small controls at the bottom of the range, paper cards at the top.
- Paper cards carry the **deep two-layer Focus Flow shadow** — a tight contact
  shadow plus a wide soft one. One layer looks flat against a radial stage; two
  is what sells the sheet as lifted.

---

## Non-negotiables

These are not style choices and a redesign does not get to overrule them.

- **WCAG AA for all text.** Including amber on dark, which is why
  `--rounds-em-fill` exists.
- **`prefers-reduced-motion` honoured everywhere.** The board's pulsing REC
  kicker and the deck-advance transition both have still fallbacks.
- **Visible keyboard focus on every interactive element.** The accent ring, never
  `outline: none` without a replacement.
- **The paper is read-only.** No edit affordance renders on the document at any
  breakpoint. The chat editor is the only edit path. This is an architecture
  invariant, not a visual one — see AGENTS.md.

---

## What Rounds does NOT restyle

- **Custom templates.** A doctor's uploaded form renders exactly as it does
  today. Rounds styles the **default QuillMD layout only**. A practice that
  uploaded its own letterhead did not ask for our typography.
- **Server semantics of any gate.** The gates are UI over server refusals which
  remain the sole source of truth.
- **PDF / Word export parity, and the 820px paper width.**

---

## Flag

Built behind `NEXT_PUBLIC_SKIN_ROUNDS`. Build-time inlined, so flipping it needs a
rebuild — verify with the flag-inlining grep in the prod smoke, not by reading
`.env`.

Rollback tag at flip: `:pre-rounds-<date>`.
