# QuillMD — 4 reference-locked hero concepts (`/heroes`)

Staging-only design exploration. Heroes only — no full pages. Same real content rides
every concept: a selectable `<h1>` "The note writes itself", one subhead, two CTAs
(Start free / See it work), one trust row (HIPAA-ready · BAA included · US-hosted · You
sign every note). Content is the single source of truth in `components/motion/shared.tsx`.

Each concept is **locked** to a named Refero reference from the 2026-06-14 research pass.
Tokens (palette / type / spacing / surface) were pulled from Refero — `refero_get_screen`
hex palettes for the locked screens + `refero_get_style` full systems for the closest
grounded token set — not imagined. Refero queries were generic aesthetic descriptors only
(PHI hygiene).

---

## H1 — DARK / CINEMATIC

- **Primary lock:** Resend (`resend.com/features/email-api`) — near-black with a dot-grid
  texture behind the hero and the product shown as a framed panel.
- **Secondary lock:** Rox (`rox.com`) — colour discipline: ONE warm-metallic gold accent.
- **Grounding system:** Depot (`depot.dev`) — near-black command-center; depth via layered
  surfaces + a 1px inset top-highlight, not shadow.
- **Preserve:** near-black canvas (`#040506`); dot-grid texture; a single restrained gold
  accent; the SOAP note as a framed product artifact floating on the grid.
- **Borrow only:** Resend's dot-grid + framed-panel; Rox's single gold accent; Depot's
  `inset 0 1px 0 rgba(255,255,255,.06)` surface highlight.
- **Role rules:** gold = accent word + CTA outline + panel tick ONLY (never a fill, never
  body text). Mono = labels/SOAP only.
- **Media strategy:** code-native framed SOAP panel (no bitmap) — the real note IS the
  product shot. Dot-grid is a CSS background, not an image.
- **Reject:** turquoise (belongs to the obsidian motion-lab, not here); two accents; glow
  soup; heavy drop-shadows.
- **Tokens:** bg `#040506`; panel `#0b0e12`; border `rgba(255,255,255,.08)`; ink `#f4f6fa`;
  muted `#8b8c88`; gold `#e3b667`. Serif headline (Newsreader), accent word italic+gold.
- **THE one borrowed decision:** *dot-grid on near-black + the SOAP note as a framed
  product panel* (Resend), accented by a single gold word (Rox).

## H2 — LIGHT / CLINICAL

- **Primary lock:** Perplexity Enterprise (`perplexity.ai/enterprise`) — uppercase
  "FOR \_\_\_" eyebrow + elegant serif headline on a muted sage band; product-as-proof card.
- **Grounding system:** Ease Health (`easehealth.com`) — cream canvas, forest-green primary
  action, tinted surfaces (no shadows), light-weight serif for understated authority.
- **Continuity:** the sage band doubles as QuillMD's existing sage `#7AA68C`.
- **Preserve:** off-white canvas; sage hero band; uppercase mono eyebrow; serif headline at
  a light weight; a forest/sage solid primary CTA; framed SOAP "answer" card as proof.
- **Borrow only:** Perplexity's eyebrow→serif→band stack; Ease Health's forest-green CTA +
  tinted-surface (shadowless) card system.
- **Role rules:** forest-green = primary CTA + checkmarks ONLY; sage band = atmosphere;
  ink `#1f2a26` = text (never pure black, per Ease Health).
- **Media strategy:** code-native framed SOAP answer-card on the band (product-as-proof).
- **Reject:** dark canvas; gold/turq; drop-shadows (use tinted surfaces); decorative blobs.
- **Tokens:** canvas `#faf8f4`; band `#dde7e1`; card `#ffffff`; border `#e4ebe6`; ink
  `#1f2a26`; muted `#5b6b64`; sage `#7aa68c`; forest `#1c4a35`. Serif headline weight ~380.
- **THE one borrowed decision:** *uppercase "FOR CLINICIANS" eyebrow + elegant serif on a
  sage band* (Perplexity) — which is also the QuillMD-sage continuity move.

## H3 — EDITORIAL / TYPOGRAPHIC

- **Primary lock:** Medium (`medium.com/about`) + Polar (`polar.sh`) — one dominant display
  headline, thin dividers, magazine restraint, strong left alignment, huge negative space.
- **Grounding system:** Attio (`attio.com`) — soft-serif headlines on white, hairline
  borders as the primary separation device, ink-on-white CTA, colour reserved as a rare cue.
- **Preserve:** white/off-white canvas; ONE oversized serif display headline; hairline
  rules; left alignment; ink CTA; colour-free headline (emphasis via italic, not colour).
- **Borrow only:** Medium's "Start reading / Start writing"-style hairline-divided rows for
  the trust row; Attio's Tiempos→Newsreader serif at -0.03em and 1px Slate dividers.
- **Role rules:** NO colour in the headline or primary CTA (Attio rule). Emphasis word set
  in serif ITALIC, not a colour. Hairlines = structure, not decoration.
- **Media strategy:** none — type IS the hero. No product card (keeps the editorial purity).
- **Reject:** coloured accent word; boxes/cards; centre alignment; gradients; drop-shadows.
- **Tokens:** canvas `#fbfbfb`; ink `#16181c`; muted `#6a6e78`; hairline `#dcdfe5`; CTA ink
  `#16181c`. Serif display (Newsreader) clamp to ~8rem, -0.03em, line-height 1.02.
- **THE one borrowed decision:** *one dominant serif headline + hairline rules, left-aligned,
  colour-free (italic for emphasis)* — Medium's composition on Attio's serif/border system.

## H4 — BOLD-TYPE / STATEMENT

- **Primary lock:** Tome (`tome.app`) + Washington Post Solutions
  (`washingtonpost.com/solutions`) — oversized heavy display on charcoal, ONE saturated CTA.
- **Grounding system:** Framer (`framer.com`) — inky-black layered surfaces (`#000`→`#080808`),
  oversized tight-kerned display (line-height 0.85, -0.05em), one electric accent, pill CTA.
- **Preserve:** pure-black canvas; the headline AS the hero (max type scale); ONE saturated
  accent; a single loud action (pill CTA).
- **Borrow only:** Framer's display kerning/line-height + `#000`→`#080808` layering + 100px
  pill CTA; Tome's "one loud action" discipline.
- **Role rules:** electric accent = pill CTA + accent word ONLY. Everything else is
  white/ash on black. No second accent (Tome's magenta and WaPo's lime are not both used).
- **Media strategy:** none — type IS the visual.
- **Reject:** serif; two accents; uppercase Anton (that's the motion-lab); busy background.
- **Tokens:** bg `#08090a`; raised `#101114`; ink `#ffffff`; ash `#9aa0a8`; accent electric
  `#2e8bff`. Display = Manrope 800, clamp to ~9rem, line-height 0.9, -0.04em.
- **THE one borrowed decision:** *the headline IS the hero — Framer's oversized tight display
  on pure black with one saturated electric accent reserved for the pill CTA + accent word.*

---

## a11y / quality floor (all four)

- Real selectable `<h1>` built from the shared `HEADLINE` constant.
- Readable without JS: H1 is the SSR'd default; all motion is `.js`-gated CSS so no-JS
  renders the final, fully-visible frame.
- `prefers-reduced-motion: reduce` → every concept settles to a static, fully-visible frame.
- Visible keyboard focus on every interactive element (switcher + CTAs).
- Mobile: single column, type clamps down, no horizontal scroll.
- 60fps: animation is transform/opacity only (GPU), no layout thrash.

## Deploy

`/heroes` is a new static route (`out/heroes/index.html`) served by the existing
`staging.quillmd.com` nginx vhost via `try_files`. No vhost/cert change. The staging root
(`/`) and the motion lab (`/motion`) are untouched.
