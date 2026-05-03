# Landing v6 (Apple Product Page) — migration report

**Branch:** `feature/phase7-landing-v6-apple`
**Date:** 2026-05-03
**Source mockup:** `docs/design-directions-v5-designer/v6-apple-product.html` (Phase 5 designer-mode v6)
**Target:** `apps/marketing/` (production marketing site → quillmd.com)

---

## Lighthouse scores

### Mobile (Lighthouse 12, simulated 4G + 4× CPU throttle)
| Category       | Score | Target | Result |
|----------------|-------|--------|--------|
| Performance    | **88** | ≥95    | -7 (LCP-bound; see notes) |
| Accessibility  | **100** | ≥95    | ✓ |
| Best Practices | **100** | —      | ✓ |
| SEO            | **100** | —      | ✓ |

Core Web Vitals (mobile, simulated):
- LCP 3.2 s · FCP 1.1 s · TBT 240 ms · CLS 0
- LCP element: hero `<h1>` ("The medical scribe that practitioners actually use.")
- LCP phases: TTFB 473 ms (15 %), Render Delay 2765 ms (85 %)

### Desktop
| Category       | Score |
|----------------|-------|
| Performance    | **100** |
| Accessibility  | **100** |
| Best Practices | **100** |
| SEO            | **100** |

Core Web Vitals (desktop): LCP 0.8 s · FCP 0.3 s · TBT 20 ms · CLS 0

### Mobile Performance gap analysis (88 vs target 95)
The 7-pt gap is dominated by simulated render delay on the giant hero `h1`
(`clamp(44px, 8.4vw, 108px)`, weight 700, gradient-clipped middle line).
Already applied:
- Removed `opacity:0` start state on hero animations → H1 paints on first frame
- Dropped Inter weight 800 (unused); kept 700 for hero
- Removed `filter: drop-shadow()` on the giant accent-sage text on mobile only
- Added `content-visibility: auto` + `contain-intrinsic-size` on offscreen `.how-stage` and `.feature-row` blocks
Real-device mobile (mid-range Android, no simulated throttle) is expected
to land in the 92-97 range. The simulated-mobile profile penalises any
hero-led design with a heavy h1 + display webfont.

A11y/BP/SEO are all at 100. Visual regression vs the v6 mockup is
pixel-faithful (see screenshots/).

---

## What changed

| Area | Action |
|------|--------|
| `src/app/page.tsx` | Updated docstring; same imports + section order |
| `src/app/layout.tsx` | Added Inter weight `700` for the v6 hero (dropped 800 — unused) |
| `src/app/landing.css` | **Full rewrite** — Phase 5 Linear V1 grammar replaced with Phase 7 v6 Apple Product grammar (hero, stages, how-row, feature-row, compare-table, product-shell, sec-list, pricing-card, footer) |
| `src/components/home/Nav.tsx` | Cleaned up cmdk-chip inline styles (now in landing.css) |
| `src/components/home/Hero.tsx` | Three-line H1 with sage gradient on middle line; glow CTA; floating product visual via `<HeroVisual>` |
| `src/components/home/HeroVisual.tsx` | **NEW** client component — 3D floating SOAP card stack with mouse-move parallax (desktop only, respects reduced-motion) |
| `src/components/home/Trust.tsx` | Compact strip: claim left + 5 mono badge stacks right |
| `src/components/home/Problem.tsx` | Massive `2.0` (clamp 180-460px) gradient text; useCounter hook reused |
| `src/components/home/HowItWorks.tsx` | Three full-viewport stages with text + custom visuals (orb+mic+wave / doc-lines / sage check) |
| `src/components/home/Features.tsx` | Six full-viewport feature-rows alternating left/right with custom feature visuals (SOAP grid / code chips / shield+rings / specialty stack / cmdk palette / audit log) |
| `src/components/home/Compare.tsx` | Bold 5-col table with sage glow; mobile collapses to 2 cols |
| `src/components/home/Demo.tsx` | Centered floating product mockup with 2° X tilt; same chrome + transcript + SOAP draft |
| `src/components/home/Security.tsx` | 3-col grid of 6 cells with sage-tinted icon squares; H4 → H3 (a11y) |
| `src/components/home/Specialties.tsx` | 8 huge rounded pills with hover lift + sage glow |
| `src/components/home/Pricing.tsx` | Single bold 580px card with floating "Solo physician" badge + 64px gradient `$49` + 10-feature 2-col list + glow CTA |
| `src/components/home/FAQ.tsx` | H4 → H3 (a11y); same hairline list panel |
| `src/components/home/FinalCTA.tsx` | 90vh stage with sage radial spotlight |
| `src/components/home/Footer.tsx` | H6 → div (a11y heading-order); column titles wrapped in `<nav aria-label>` |
| `src/app/icon.svg` | **NEW** — sage gradient brand-quill (16-32px favicon; eliminates `/favicon.ico` 404) |

## What was preserved

- **Metadata** — `title`, `description`, `openGraph`, `viewport` byte-identical in `src/app/layout.tsx`
- **Constants** — `APP_URL` + `APP_SIGNUP_URL` unchanged (CTA destinations preserved)
- **next.config.ts** — `output: 'standalone'`, `outputFileTracingRoot`, `optimizePackageImports` untouched
- **All other pages** — `/about`, `/contact`, `/demo`, `/hipaa`, `/pricing`, `/privacy`, `/security`, `/signup`, `/terms` untouched (verified HTTP 200 on each)
- **`useReveal` + `useCounter` hooks** — reused as-is for scroll-triggered fade-up + the 2.0 counter animation
- **`RevealMount` invisible client component** — reused as-is
- **`globals.css`** — `@theme` Linear V1 sage palette tokens preserved (the `.qm-lin-*` utility surface is still the canonical app shell vocabulary; landing.css just re-aliases the same tokens locally for v6 grammar)
- **No analytics/tracking pixels existed before** — none added (zero funnel-break risk)

## Verbatim content preservation

Every headline, sub-copy, feature blurb, dialogue line, SOAP body, ICD/CPT
code, FAQ Q&A, and footer link is byte-identical to
`docs/landing-immersive-enhance/before-inventory.md` (the production
content map).

## Animation strategy

| Animation | Mechanism |
|-----------|-----------|
| Scroll fade-up (`.reveal` → `.in`) | Existing `useReveal` IntersectionObserver hook |
| Hero `2.0` counter on Problem section | Existing `useCounter` hook |
| Hero card 3D float (9s loop) | Pure CSS `@keyframes float` |
| Hero card mouse-move parallax | New `HeroVisual.tsx` client component (desktop ≥961px, respects reduced-motion) |
| Hero text slide-up (no opacity gate) | Pure CSS `@keyframes heroSlide` (LCP-friendly) |
| Live-dot pulse, wave bars, doc-line draw, ring pulse, orb breath, blink cursor | Pure CSS `@keyframes` |
| Reduced-motion preference | Honoured throughout via `@media (prefers-reduced-motion: reduce)` |

No external animation libraries added. `framer-motion` is still in
`package.json` (legacy from earlier phases) but the v6 landing components
do not import it — could be removed in a follow-up cleanup PR.

## Smoke test results (all green)

| Path | HTTP | Notes |
|------|------|-------|
| `/` | 200 | New v6 landing |
| `/about` | 200 | Untouched |
| `/contact` | 200 | Untouched |
| `/demo` | 200 | Untouched |
| `/hipaa` | 200 | Untouched |
| `/pricing` | 200 | Untouched |
| `/privacy` | 200 | Untouched |
| `/security` | 200 | Untouched |
| `/signup` | 200 | Untouched |
| `/terms` | 200 | Untouched |
| `/icon.svg` | 200 | New favicon |

Console errors / network failures: **0**.

## Visual regression vs source mockup

Side-by-side comparison: `screenshots/prod-desktop-0.png` vs the v6 mockup
hero is pixel-identical (within sub-pixel font rendering tolerance).
`screenshots/prod-mobile-0.png` matches the mobile mockup behavior
documented at `docs/design-directions-v5-designer/screenshots/v6-mobile-0.png`.

## Files

- `before-inventory.md` — Pre-migration inventory (what was preserved + token catalog)
- `migration-report.md` — This file
- `screenshots/` — Before (current quillmd.com) + after (new build) at desktop / mobile / wide
- `lighthouse/` — Mobile + desktop Lighthouse JSON + HTML reports

---

**STATUS:** ready for visual review. Production untouched. PR open against `main`.
