# QuillMD — complete landing page, split-screen spine (`/final`)

Promotes the **S2 split-screen** structure (locked to Squarespace 50/50, `66d5906f`) into a
complete, multi-section landing at a staging-only review route. Split is the spine for two
moments (hero + verification); the rest resolves to full-width in the same palette/type/seam
language so the page reads as one cohesive thing.

## Architecture
1. **Nav** (sticky, translucent over the split).
2. **Hero — split** (signature 50/50): LEFT dark "before" (the 9pm charting pile) ｜ RIGHT light "after" (the clean signed SOAP). Hard vertical seam. Motion: on load the seam draws + the after-side note assembles (subtle, `.js`-gated, reduced-motion static).
3. **How it works** — full-width: Record → Draft → Verify → Sign.
4. **Verification — split** (the differentiator): LEFT raw transcript with an unverifiable suggestion ｜ RIGHT the anchored, verified note + the review lane ("Suggested by AI — not stated in this visit").
5. **Comparison** — full-width: QuillMD vs the typical enterprise scribe.
6. **Pricing** — full-width: $49 flat, single card.
7. **FAQ** — full-width, native `<details>` (works without JS, keyboard-accessible).
8. **Final CTA** — full-width.
9. **Footer** — consistent.

Mobile: both splits stack vertically (before above / after below); the vertical seam becomes a
horizontal divide. Full-width sections stack normally.

## Design
Carry S2 tokens. Dark `#0a0c11`, light `#f4f3ef`/`#faf9f5`, ink `#16201b`, forest `#1c4a35`
(primary CTA), sage `#7aa68c` (tags + the seam-accent), mono labels, Manrope-800 headlines.
The **seam** (a sage hairline) is the recurring motif that ties full-width sections to the split.

## CLAIM-TRUTH LEDGER (public medical site — every claim must be true)

### Approved — used on the page (all confirmed true by the brief)
- Evidence-anchored notes — every line anchored to the visit transcript.
- Machine-verified.
- Review lane for anything it can't ground ("Suggested by AI — not stated in this visit").
- The doctor reviews, edits, and **signs every note**.
- **$49 per provider / month, flat** — "no per-visit fees" (a direct restatement of "flat").
- HIPAA-ready.
- BAA included.
- Visit **audio retained 90 days after signing**, then deleted.
- US-hosted.
- Runs on **a current frontier model** (deliberately unversioned).

### Left OUT as unverifiable / not in the approved set (flagged, per the brief)
- **No accuracy percentages / "<X%" absolutes** — none used anywhere.
- **No time-saved absolutes** (e.g. "save 2 hours/day"). The page only describes the *workflow*
  ("the note is drafted while you're still in the room"), which is a product behaviour, not a
  measured outcome claim.
- **SOC 2 omitted** — not in the approved set; deliberately not claimed (only HIPAA-ready + BAA + US-hosted).
- **No hosting provider / region named** — "US-hosted" only.
- **No model name or version** — "a current frontier model" only.
- **No "unlimited visits" / "no annual contract"** — not confirmed; omitted (only "$49 flat, no per-visit fees").
- **"Start free" CTA** — carried over from the existing product CTAs (motion/heroes/structures).
  It implies a free trial/tier. **FLAG for Kasra: confirm a free trial/tier exists before any
  public launch; otherwise change the CTA to "Get started" / "Book a demo".**
- **Comparison "enterprise scribe" column** describes the *general category* (custom contracts,
  sales cycles, per-seat pricing, varies on verification/ownership) — not a specific named vendor,
  and makes no false specific claim about any competitor.

## Floor
Real selectable `<h1>` (the hero "after" headline); readable without JS (static export, FAQ is
native `<details>`, all reveals `.js`-gated); `prefers-reduced-motion` static; visible focus;
mobile graceful (stacked split verified); 60fps (transform/opacity only). Route-scoped: `final.css`
loads only on `/final`; root landing, `/motion`, `/heroes`, `/structures` stay untouched.
