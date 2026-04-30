# Direction: CLINICIAN

> **Warm, calm, optimistic. FOR doctors, not for investors.**

---

## Thesis

Most "professional software" assumes the user wants to feel important. Clinician
assumes the user is **tired**. A pediatrician at 5 PM has been on her feet for
nine hours, has seen nineteen kids, has had a difficult conversation with a
parent at 4:30, and now has eight notes left to chart. She does not need her
software to look like a fighter-jet HUD. She needs it to feel like a kind room.

Clinician is light-mode-first because daylight is what humans live in. It uses
muted sage-green and warm teal because clinical-blue is exhausted territory and
because doctors have told us, repeatedly, that the blue/grey UIs make them feel
like they are inside a hospital even when they are at home. Clinician's
typography uses a humanist serif for body content because serifs feel
considered, and a friendly geometric-humanist sans for chrome because it stays
quiet. Patient names are **never** rendered as table-row data — they are rendered
as people, with the breathing room that names of people deserve.

Clinician treats AI as a quiet assistant, not a star. There are no pipeline
visualizations, no glowing beam-of-thought, no "agent thinking" theatrics.
Instead, when AI works, a single sentence in serif quietly crossfades:
*"Reviewing your transcript… Drafting… Polishing…"* The intelligence is in the
output, not the choreography.

---

## Palette

| Role | Token | Hex | Notes |
|---|---|---|---|
| Page background | `--cream` | `#FAF7F2` | Warm off-white, the canvas |
| Card surface | `--cream-card` | `#FFFCF5` | One step lighter, generous |
| Subtle elevation | `--cream-2` | `#F2EDE3` | Section bands, tab tracks |
| Hairline | `--line` | `rgba(43, 38, 32, 0.08)` | Never a hard 1px black |
| Primary text | `--ink` | `#2B2620` | Warm charcoal, not pure black |
| Secondary text | `--ink-2` | `#5C544A` | Body, paragraph |
| Tertiary text | `--ink-3` | `#8A8278` | Labels, captions |
| Sage primary | `--sage` | `#7AA68C` | Brand, primary CTA, focus |
| Sage deep | `--sage-deep` | `#2F5040` | Pill text on sage backgrounds |
| Sage tint | `--sage-tint` | `rgba(122, 166, 140, 0.14)` | Pill backgrounds, soft fills |
| Teal secondary | `--teal` | `#5BA3B4` | Secondary accent, info |
| Teal deep | `--teal-deep` | `#2C5A66` | Pill text on teal backgrounds |
| Teal tint | `--teal-tint` | `rgba(91, 163, 180, 0.14)` | Info pills |
| Warm amber | `--amber` | `#D4A574` | Soft warning, never bright yellow |
| Amber deep | `--amber-deep` | `#7A4F1F` | Pill text on amber |
| Soft coral | `--coral` | `#C97B6E` | Rx caution, gentle red |
| Coral deep | `--coral-deep` | `#7A3329` | Pill text on coral |

**Drop shadow language:** `0 4px 14px rgba(43, 38, 32, 0.04)` for cards.
`0 1px 2px rgba(43, 38, 32, 0.05)` for buttons. **No glow rings. No inset
highlights. No spread > 16px.**

**Radii:** `12px` for cards, `14px` for primary cards, `16px` for hero modules,
`999px` for pills and primary CTAs. Nothing below `8px` except the small icon
chip on a search input.

---

## Typography

| Role | Family | Weight range | Reasoning |
|---|---|---|---|
| Body / patient names / headlines | **Source Serif 4** | 400 / 500 / 600 | Humanist serif optimized for screen. Lora felt blog-y; Cardo too historical. Source Serif 4 holds at 14px and at 40px without losing warmth. |
| Chrome / labels / nav / metadata | **DM Sans** | 400 / 500 / 600 | Geometric-humanist; warmer than Inter Tight, more architectural than Manrope. Quiet enough to stay out of the way of the serif. |
| Codes, IDs, mono-only | **JetBrains Mono** | 400 / 500 | Standard, used sparingly — only for `MRN-77324` and timestamps |

Body copy is **never below 16px**. Patient names start at 18px in lists and 36px on detail. Line-height is generous — `1.7` for SOAP body. Letter-spacing is positive (`+0.01em`) for the wordmark and labels, neutral for body.

---

## Skills + libraries used

- **frontend-design** — for distinctiveness; Clinician's warmth is the differentiation, not generic AI-app aesthetics
- **ui-ux-pro-max** — sage-led palette selection, soft-shadow theory, warm-light accessibility (all body text passes 4.5:1 against `#FAF7F2`)
- **theme-factory** — generated the warm-light theme, sage primary + teal secondary, committed hex codes
- **framer-motion** — slow ease-out transitions philosophy; final motion is CSS-only with `cubic-bezier(0.22, 1, 0.36, 1)` at 240–400ms, **no springs**
- **WebFetch (inspiration only):** Notion's warmth in a productivity tool, Cron/Notion Calendar's calm chrome, Spark's friendly tone, anyone.app's wellness-leaning health vocabulary
- **ui-libraries-reference** — Smooth UI for soft-component primitives (referenced, not copied)

---

## How Clinician differs from Apothecary (v2)

These are not surface differences — they are tonal and philosophical:

1. **Mode shift.** Apothecary is dark-mode-first with violet/aurora theatrical
   gradients. Clinician is **light-mode-first** with warm cream — the inverse.
   Dark mode in Clinician is also warm (soft charcoal, never pure black).
2. **Motion philosophy.** Apothecary uses spring-y, cinematic moments —
   beam-of-thought processing, hero-scale transitions. Clinician uses **only
   240–400ms ease-out crossfades**. No springs. No bounces. Unhurried.
3. **AI presentation.** Apothecary makes AI a star (pipeline visualization,
   beam, dramatic reveal). Clinician makes AI a **quiet assistant** — a single
   serif sentence crossfading: "Drafting…" "Polishing…".
4. **Palette philosophy.** Apothecary is saturated violet / aurora /
   high-contrast theatrical. Clinician is **muted sage / warm teal / cream**
   — every color is desaturated by ~25% from its "vivid" form on purpose.
5. **Patient as person, not row.** Apothecary's lists are dense, dark, and
   data-first. Clinician's lists are 60–80px tall with serif names and warm
   metadata — patients **read as people**, not rows.

---

## Best for

Older clinicians, primary-care and pediatric clinics, wellness-leaning
practices, mental-health and integrative practitioners, mid-career physicians
who are exhausted by EHR brutalism and want one tool that feels human.

---

## Honest costs

- **Light-mode-first means dark-mode users are second-class.** A doctor
  charting at 11 PM may want a true dark experience; Clinician's warm-charcoal
  alternate dark is gentle but not as deep as Apothecary's. Some users will
  prefer the v2 direction at night.
- **"Warm" can be misread as "unprofessional"** by enterprise procurement.
  A 600-bed academic medical center's IT committee may glance at Clinician
  and think "this looks like a wellness app, not an EHR adjunct" — even when
  the underlying functionality is identical.
- **Absence of AI showmanship may make AI feel hidden, not valuable.**
  Investors and demo audiences expect glowing pipelines. Clinician's
  serif-crossfade approach is honest but un-flashy. The sales narrative has to
  carry the AI story, because the UI deliberately doesn't.
- **Doctors at academic medical centers** trained on clinical-blue Epic and
  Cerner UIs may experience Clinician's sage palette as "not medical" until
  they use it for a few days. There is a 1–2 week acclimation tax.
- **Serif body copy** is lovely on retina screens but can feel slightly soft on
  older Windows displays without ClearType subpixel rendering tuned correctly.

---

## The test

> A tired pediatrician at 5 PM should look at this UI and feel a *tiny bit
> better*, not a *tiny bit worse*.

Every decision in this folder is in service of that test.
