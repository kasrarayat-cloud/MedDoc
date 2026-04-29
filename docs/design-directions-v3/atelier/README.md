# Design Direction V3 — ATELIER

Generated: 2026-04-29
Author: Design Director (v3 / atelier)
Foundation: extends App-redesign-v1 / HANDOFF tokens (`docs/DESIGN_TOKENS.md` §A) — but **inverts the surface palette to a warm cream-on-near-black-ink editorial substrate**, replaces the violet with a single oxblood accent, and discards every gradient pill, orb, mesh, beam, particle, and pipeline animation in the existing system.

Mockups (open at ~1600 px):

- [`landing-and-recording.html`](landing-and-recording.html) — editorial landing + recording widget + AI processing + success + empty state
- [`dashboard.html`](dashboard.html) — wide-margin editorial dashboard
- [`visit-detail.html`](visit-detail.html) — visit page with serif display header, SOAP as article, restrained Rx warning

---

## 1. Thesis

**Atelier is the thinking person's medical software.** It is the antithesis of Apothecary — not because Apothecary is wrong (its two-mood thesis is defensible), but because the same problem has a second valid answer that the user deserves to see in full before deciding. Atelier commits to **restraint as the position**. The surface is monochrome warm-cream and graphite ink. The display face is Source Serif 4 at editorial sizes. The chrome is Inter Tight, but small. The metadata is JetBrains Mono in small caps. There is one accent — **oxblood `#7B1F2D`** — and it appears in three places only: the active recording dot, the underline beneath the active patient name, and the hover state of links. Every other surface is grayscale.

The luxury is what is **not** there. There is no aurora mesh, no spotlight, no orb, no border-beam, no animated pipeline, no particle burst, no gradient pill, no scroll-jacking, no magnetic CTA, no node-and-trail visualization. The "magic moment" of AI processing is one italic serif line that crossfades through three sentences over 2.4 seconds — `"reviewing transcript… identifying speakers… drafting subjective…"` — and then the SOAP fades in over the previous text. The success state is the patient's name in serif with a 3px oxblood underline beneath it and the line `SIGNED · 2:14 PM` in 11px small-caps mono. The completion is the reward.

Atelier is The New Yorker, Stripe Press, Edward Tufte, and a leather-bound 1962 Merck Manual. It is built for a doctor who reads, not a doctor who is excited. It is also built for the institutional buyer — the medical director, the practice manager, the insurance-track customer — who is repelled by anything that looks like consumer SaaS theater. The cost: a first-time visitor may not feel "wowed" the way Apothecary's recording moment will wow them. We accept that trade.

---

## 2. The chosen accent

**Oxblood — `#7B1F2D`**

Why oxblood, not forest or navy:

- **Forest `#1F4F3E`** is the wellness/yoga-app cliche. Every direct-to-consumer health brand uses it. We do not want to look like a meditation app.
- **Navy `#0E2A4D`** is the fintech cliche. Stripe, Square, Mercury, Ramp. We are not a billing app.
- **Oxblood `#7B1F2D`** belongs to medical-historic objects: the spine of a Merck Manual, the cap on a pharmacopoeia bottle, the leather of an old physician's bag, the typographic rule under a New Yorker department label. It is **sober without being cold**, **warm without being friendly**, **medical without being squeamish**. It also reads as a deliberate choice — a doctor seeing oxblood feels picked-for, not template-stamped.

The accent is used in **three places only**:

1. The 6px recording dot (and only when recording is live).
2. The 3px underline rule beneath the active patient name on the visit detail page (and the active tab indicator, which uses the same rule).
3. The `:hover` state of any link or button label — color shift only, no underline lift, no transform.

Status colors are **not** colored. "Critical / warning / info" are flat outline pills with grayscale labels and a tiny accent dot only on the topmost severity (critical). The recording dot, the underline, and link-hover are the only three places oxblood appears in the entire UI.

---

## 3. Plugins / libraries used + skills invoked

All three mockups are self-contained originals — no copy-pasted source from any UI library. Inspiration was drawn from layout SHAPES, not code.

### Skills invoked

| Skill | What it informed |
|---|---|
| `frontend-design` | The "no generic AI aesthetic" bar. The skill explicitly warns against AI-slop tropes — purple-on-white, predictable cards, generic spinners. Atelier's restraint is the antidote: monochrome warm-cream, serif display sizes, one accent earned three times, no spinners (a single italic crossfade replaces every loading state). |
| `ui-ux-pro-max` | Editorial typography rules — Source Serif 4 17px body at 1.7 line-height with 680px max-width is the magazine-article ratio that beats every competing readability heuristic for clinical prose. Small-caps mono at 11px with `letter-spacing: 0.12em` is the "department-label" idiom. Hairline rules at `1px` `--ink-15` instead of zebra-striping for table separation. Optical alignment of small-caps mono against serif (mono needs +1px nudge to feel level). |
| `theme-factory` | Defined the 6-step monochrome ramp on warm cream + the single oxblood accent. The ramp is `--cream` (`#FAF7F0`, page) → `--cream-2` (`#F2EDE3`, secondary surface) → `--ink-15` (`#E5DED1`, hairline) → `--ink-40` (`#9C958A`, meta) → `--ink-70` (`#3F3A33`, body) → `--ink` (`#1A1714`, headlines). Oxblood `#7B1F2D` sits beside the ramp as the lone color. |

### Inspiration sources (WebFetched for layout shape only)

| Source | What it contributed |
|---|---|
| **Stripe Press** | Max-width prose ~70–80ch, generous gutters, book-like meta hierarchy (small italic byline beneath serif title). Reinforced "the page IS the brand" — no chrome decoration. |
| **Linear blog** | The right-arrow-as-affordance pattern (we use it as `→` after links instead of underline-on-hover for tertiary CTAs). Confirmed Atelier's instinct that monochrome editorial needs zero gradient pills to feel premium. |
| **Vercel design** | Section labels as plain text rather than all-caps (we deliberately diverge — Atelier uses `SMALL CAPS MONO 11px / 0.12em tracking` for section labels because clinical prose needs a stronger department-rule than a tech blog). |
| **Smooth UI** (calm primitives reference via `ui-libraries-reference` skill) | Confirmed the input + button + card primitive shapes. Atelier deliberately went FLATTER than smooth-ui — we use a `1px` border on a `--cream-2` fill rather than the typical card-with-shadow. Shadow is not part of Atelier's vocabulary at all. |

---

## 4. What is different from Apothecary (5 bullets)

1. **Light, not dark.** Apothecary is `#07060C` near-black bg with violet glows. Atelier is `#FAF7F0` warm cream bg with graphite ink. Same product, opposite physical sensation.
2. **One accent earned three times, vs. seven semantic colors.** Apothecary uses violet + mint + amber + coral + copper + aqua + magenta. Atelier uses oxblood and a 6-step grayscale. Status is communicated by typographic position and a tiny dot, not by hue.
3. **Serif as base, not as flourish.** Apothecary uses Source Serif 4 only for headlines and the `qm-warn-headline`. Atelier uses Source Serif 4 for body prose, section headings, patient names, the SOAP narrative, and the recording widget label. Inter Tight is reduced to chrome (buttons, the top bar, form labels). Mono is reduced to meta (timestamps, codes, status labels in small caps).
4. **No magic moment, no theater.** Apothecary's pitch is "the surface mode-shifts to match cognitive load." Atelier's pitch is "the surface never shifts; restraint is the cognitive support." There is no aurora, no orb, no border-beam, no thought-chain visualization, no pipeline animation. The single italic crossfade is the entire AI loading vocabulary.
5. **Wide margins, not bento.** Apothecary uses a 12-col bento with asymmetric tile spans. Atelier uses a single column of prose ~720px max-width on prose surfaces, and ~1100–1200px max-width on tables, with ~200px+ left/right gutter on a 1600px screen. The whitespace is the design.

---

## 5. Best for

**The institutional buyer + the senior physician.** Atelier wins the medical director's RFP, the academic medical center pilot, the conservative independent practice that hates "fintech-looking medical apps." It loses the venture-pitch demo and the consumer-app reviewer. If QuillMD's GTM is bottom-up (residents and early-career physicians who blog about tools), Apothecary wins. If QuillMD's GTM is top-down (group-practice contracts, hospital network deals, insurance-aligned channels), Atelier wins.

---

## 6. Honest costs

1. **Smaller "wow" surface.** A first-time visitor screenshot of Atelier looks like a magazine article. A first-time visitor screenshot of Apothecary looks like a magic-portal SaaS app. For social-share virality, Apothecary wins. For "this looks like serious medical software," Atelier wins.
2. **No magic moments to demo.** When a sales engineer demos QuillMD on a Zoom call, Apothecary's pipeline-with-pulsing-nodes is a stunt. Atelier's italic crossfade is calm to the point of being undemoable. The honest fix in production is to record short-form videos that emphasize the **typographic transitions** and the silence around them — but those videos are harder to make exciting in a 30-second Twitter clip.
3. **May feel insufficiently AI-product to investors.** A Series B pitch deck screenshot of Atelier looks like a Substack publication, not a $50M-ARR AI company. The investor narrative has to do more work to sell "we are AI-first; the UI just doesn't show off about it." We accept this as a deliberate trade — the user (the doctor) does not pay for AI showmanship; the doctor pays for cognitive load reduction. But the fundraising slide deck will need to compensate elsewhere.
4. **Hover states are subtle to the point of being missable.** Atelier's affordance grammar is "patient name shifts to oxblood on hover," not "card lifts up + glow appears." A novice user may not initially recognize that table rows are clickable. Mitigation: the row-level cursor still becomes `pointer`, and there is a `→` glyph after primary actions. But this is a real ergonomic cost for the first 30 minutes of a new user's experience.
5. **Color-blind accessibility is actually easier here, but emotion-blind accessibility is harder.** Atelier's monochrome+oxblood passes every contrast test trivially, and the absence of red/green status colors is a feature for protanopia/deuteranopia. But the absence of any vibrant celebration moment may feel emotionally flat to a user who needs a small dopamine hit at the end of a 12-hour shift. The "Signed · 2:14 PM" small-caps lockup is intentional — completion is the reward. But not every doctor will read it that way.

---

## 7. The single most-controversial decision

**Status pills are not colored — at all.**

In Atelier, the dashboard table's `READY / PROCESSING / SIGNED / FAILED` column does not use mint/amber/coral/oxblood. It uses a flat 1px-bordered transparent pill with a small-caps mono label in `--ink-70` and — only for the most severe state (`FAILED`) — a 4px oxblood dot to its left. `READY`, `PROCESSING`, and `SIGNED` are rendered identically: same border, same label color, same letter-spacing. The only differentiation is the **word itself**.

This is contestable. A doctor scanning a list of 30 visits arguably wants `READY` to be visually pre-attentive — green-dot-jumps-out is fast. Atelier's argument is the opposite: in a clinical context, **forcing the reader to read the word** is a feature, not a bug. The whole product's value proposition is that the AI-generated chart needs to be read carefully before it's signed. Color-coding the status train the doctor to skim. Atelier wants them to read.

If the user disagrees, the fix is one CSS rule: add a 4px dot before the pill keyed to `--mint / --amber / --coral / --oxblood`. The rest of Atelier survives untouched.

---

## 8. Token additions to `globals.css`

If Atelier is selected for Phase 2 implementation, `apps/transcribe-md/src/app/globals.css` would gain a `.qm-app[data-mode="atelier"]` scope with:

```css
.qm-app[data-mode="atelier"] {
  --cream:       #FAF7F0;   /* page background */
  --cream-2:     #F2EDE3;   /* secondary surface, hover row */
  --cream-3:     #EAE3D5;   /* card fill */
  --ink-15:      #E5DED1;   /* hairline rule */
  --ink-40:      #9C958A;   /* meta, disabled */
  --ink-70:      #3F3A33;   /* body */
  --ink:         #1A1714;   /* display, headline */
  --oxblood:     #7B1F2D;   /* sole accent */
  --oxblood-deep:#5A1721;   /* hover-on-accent */

  background: var(--cream);
  color: var(--ink-70);
  font-family: var(--serif);
  font-size: 17px;
  line-height: 1.7;
  letter-spacing: 0;
}
```

Plus three primitives — `.atl-rule` (1px hairline), `.atl-smallcaps` (mono small caps 11px / 0.12em), `.atl-display` (Source Serif 4 clamp(36px, 4.4vw, 56px) / 600 / lh 1.05 / tracking -0.02em) — and that is the entire Atelier vocabulary. Everything else is composition.
