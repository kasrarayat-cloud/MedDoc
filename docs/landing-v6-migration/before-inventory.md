# Landing v6 Apple-Product migration — before inventory (2026-05-03)

## Branch
- Source: `main` @ 6a280de (phase6.1 reboot test reports)
- New branch: `feature/phase7-landing-v6-apple`

## Marketing app structure
- `apps/marketing/`
- Next.js 16.2.4, React 19.2.4
- Standalone build output (Docker)
- Pages: `/` (home), `/about`, `/contact`, `/demo`, `/hipaa`, `/pricing`, `/privacy`, `/security`, `/signup`, `/terms`, `/not-found`
- Styles: `globals.css` (@theme tokens, .qm-lin-* utility), `landing.css` (landing-specific grammar)
- Fonts: next/font (Inter 400/500/600 + JetBrains_Mono 400/500) — to be EXTENDED for v6 (700/800)

## What to PRESERVE byte-identical
- **Metadata** (`src/app/layout.tsx`):
  - title default: `QuillMD — Stop writing notes. Start practicing medicine.`
  - description: `AI medical scribe for US doctors. Real-time SOAP notes, ICD-10/CPT codes, Rx drafts — $49/month flat.`
  - openGraph: title `QuillMD`, description `Stop writing notes. Start practicing medicine.`, type `website`
- **Viewport**: themeColor `#08090a`, colorScheme `dark`
- **next.config.ts**: `output: 'standalone'`, `outputFileTracingRoot` for monorepo, `optimizePackageImports: ['lucide-react']`
- **All other pages** (privacy, terms, etc.) untouched
- **Constants** (`src/lib/constants.ts`): `APP_URL` + `APP_SIGNUP_URL`

## Analytics / tracking
- **NONE detected.** No Plausible, no GA4, no Segment, no tracking pixels in current layout.tsx or anywhere in the marketing app.
- No A/B test integrations.
- No newsletter signup endpoints in current src.
- Implication: zero risk of funnel breakage from this migration.

## What to REPLACE
- `src/app/page.tsx` (re-imports new components)
- `src/app/landing.css` (full rewrite for v6 grammar)
- `src/components/home/*.tsx` — every section component
- Adds: `src/components/home/HeroVisual.tsx` (client, mouse-move parallax)

## Reuse intact
- `src/hooks/useReveal.ts` — IntersectionObserver fade-up
- `src/hooks/useCounter.ts` — number counter for Problem section
- `src/components/home/RevealMount.tsx` — invisible client mount
- `src/app/globals.css` — Linear V1 sage @theme tokens (already production-grade)

## Public assets
- `public/` is empty (just `.gitkeep`). No favicons / logos. v6 mockup uses inline SVG everywhere, so no asset migration needed.

## Verbatim content source
- All copy from `docs/landing-immersive-enhance/before-inventory.md` (the production content map). v6 mockup mirrors this byte-for-byte.

## Key v6 design tokens (in addition to existing Linear V1 set)
- New display weights: Inter 700, 800
- New CSS vars: `--sage-glow-2: rgba(122,166,140,0.45)` (heavier glow)
- Hero H1: clamp(44px, 8.4vw, 108px), font-weight 700, line-height 0.97
- Stage H2: clamp(40px, 6.5vw, 84px), font-weight 700
- Problem number: clamp(180px, 32vw, 460px), JetBrains Mono 500
- Pricing card: 580px max-width, 44/40 padding, sage badge floating top
- New btn-glow: linear-gradient sage with heavy drop-shadow

## Animation strategy
- All scroll-triggered: existing `useReveal` hook (fade-up via .reveal → .in)
- Counter on Problem 2.0: existing `useCounter` hook
- Hero card 3D float: pure CSS @keyframes (no JS)
- Hero card mouse parallax: NEW small client component (HeroVisual.tsx)
- Live-dot pulse, wave bars, doc-line draw, ring-pulse, orb breath, blink: pure CSS @keyframes
- Reduced-motion respected throughout
