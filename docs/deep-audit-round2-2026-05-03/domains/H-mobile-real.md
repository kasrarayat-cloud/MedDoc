# Domain H — Mobile Real-Device Behavior

**Run:** 2026-05-03 20:59 UTC
**Device profile:** iPhone 13 (Playwright `devices['iPhone 13']` — 390×844 viewport, devicePixelRatio 3)

## Summary

| # | Test | Status | Finding |
|---|---|---|---|
| H1 | Tap targets ≥44×44 pt | **FAIL** | 17/17 elements on dashboard < 44pt **height** — see H-001 |
| H2 | Pinch-zoom not blocked | ✓ | viewport meta lacks `user-scalable=no` and `maximum-scale=1` |
| H3 | Form input zoom (iOS bug — fonts <16px) | **FAIL** for 1 input | "Search by name or external ID…" is 14px → iOS zooms on focus — see H-002 |
| H4-H10 | Bottom-nav overlap, safe-area, pull-to-refresh, touch gestures, mobile recording, mobile upload, mobile keyboard covering | DEFERRED — needs real iPhone hands-on |

## Findings

### H-001 — Mobile dashboard tap targets all under 44pt height (P2 a11y)

Apple Human Interface Guidelines: minimum tap target is 44×44 points.
On iPhone 13 viewport (390×844), every interactive element on the
authenticated dashboard fails the height threshold:

| Element | Width × Height | Comment |
|---|---|---|
| Dashboard nav link | 373 × 28 | top-nav strip |
| Visits nav link | 373 × 28 | top-nav strip |
| Patients nav link | 373 × 28 | top-nav strip |
| Settings nav link | 373 × 28 | top-nav strip |
| QQuillMD brand | 75 × 19 | brand mark — small target |
| Search Cmd-K bar | 220 × 26 | search bar height |
| "New visit" CTA | 95 × 28 | primary CTA |
| Avatar "QB" | 54 × 32 | profile menu trigger |
| Patients card | 86 × 30 | dashboard tile |
| All visits card | 86 × 30 | dashboard tile |
| Patient row (recent visit) | 294 × 36 | list row height |

**17 of 17 sampled elements fail.** The nav strip in particular is
critical — primary navigation should be effortless to tap. 28-pt
height means a doctor with thumbs-on-iPhone has to hit a band that's
~3.7 mm tall — high mistap rate.

**Recommended fix:** bump core navigation + CTA elements to ≥44pt
height via padding. The marketing site's Phase 7 v6 redesign
already uses ~44pt buttons for CTAs; the auth app shell wasn't
updated to match.

CSS-level: `min-height: 44pt` (or `min-height: 44px` if pt vs px
matters less in Playwright's pixel-density model — recheck against
real iPhone before committing).

**Effort:** ~30 min for nav + dashboard cards
**Risk if NOT fixed:** mid-impact mobile UX. Doctors using the app
on phone (the explicit target audience per marketing copy) will
feel friction immediately.

### H-002 — `<input>` font-size 14px triggers iOS zoom-on-focus (P3 mobile UX)

**Element:** `<input placeholder="Search by name or external ID…">`
on `/visits/new` step 1 (patient search field).
**Computed font-size:** 14px (need ≥16px to prevent zoom).

When a doctor taps this input on iOS, the browser zooms in (because
the font is "too small to read" per iOS heuristics). The zoom
disorients and forces a manual zoom-out — every visit creation.

**Recommended fix:** bump this input's font-size to 16px (in CSS or
Tailwind class). All other inputs in the codebase passed the check;
only this one regressed.

**Effort:** ~2 min (1 CSS line)
**Risk if NOT fixed:** annoying every-visit UX hiccup on mobile.

### H-003 — Pinch-zoom NOT blocked (POSITIVE)

Viewport meta:
```
<meta name="viewport" content="width=device-width, initial-scale=1">
```
No `user-scalable=no`, no `maximum-scale=1`. Users can pinch-zoom to
read small text. Good a11y posture.

## What was NOT covered

- H4 (bottom-nav overlap): app uses top nav, no bottom nav present
- H5 (safe-area insets / notch / home bar)
- H6 (pull-to-refresh)
- H7 (touch gestures — swipe to dismiss, long-press menus)
- H8 (mobile recording — mic permission UX)
- H9 (mobile audio upload from camera roll)
- H10 (mobile keyboard covering inputs)

These require a real iPhone in hand or a more thorough device-
emulation test rig.
