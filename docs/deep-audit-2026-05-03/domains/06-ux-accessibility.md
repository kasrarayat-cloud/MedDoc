# Agent 6 — UX & Accessibility

**Run:** 2026-05-03 20:01-20:05 UTC
**Tools:** axe-core 4.10.0 (via Playwright), Lighthouse v12 (from prior sweep)

## Executive summary

The marketing site `quillmd.com` is **fully accessible** (0 axe-core
violations, Lighthouse a11y 100 from prior sweep). The auth surfaces
on `app.quillmd.com` carry color-contrast issues that the Phase 7 v6
marketing redesign already fixed for landing.css but were never
ported to the app shell — same root cause across `/login`, `/signup`,
`/forgot-password`, `/reset-password`, `/check-email`.

**Findings: 0 P0, 0 P1, 5 P2 (all carried over from prior sweeps), 0 NEW P3.**

| # | Finding | Severity | Status |
|---|---|---|---|
| UX-01 | Color contrast `#6c737f` on `#08090a` = 4.17:1 (needs 4.5:1) — 7 elements on /login, 10 on /signup, axe `serious` impact | P2 | known, carried from prior QA sweep (`P2-001`) |
| UX-02 | Mono labels at 10.5px on auth surfaces — Lighthouse flags as illegible at mobile zoom | P2 | known (`P2-002`) |
| UX-03 | `app.quillmd.com` has no favicon — `/favicon.ico` + `/icon.svg` both 404 | P2 | known (`P2-003`) |
| UX-04 | `/verify-email` (no token query) returns bare 404 | P3 | known (`P3-001`) |
| UX-05 | Auth pages have no Privacy/Terms/HIPAA legal footer | P3 | known (`P3-002`) |

---

## axe-core scan (WCAG 2.0 + 2.1 A + AA)

| URL | Violations | Worst impact | Total elements affected |
|---|---|---|---|
| `https://quillmd.com/` (marketing v6) | **0** ✓ | — | 0 |
| `https://app.quillmd.com/login` | 1 (color-contrast) | serious | 7 |
| `https://app.quillmd.com/signup` | 1 (color-contrast) | serious | 10 |

All violations are the **same root cause**:
- foreground: `var(--color-linear-text-3) = #6c737f`
- background: `var(--color-linear-bg) = #08090a`
- contrast: **4.17:1** (WCAG AA needs 4.5:1)

Affected elements: small mono labels (`Email`, `Password`, `Welcome
back`, `New to QuillMD`, `HIPAA ready`, `BAA included`, `US-hosted`,
trust strip, footer captions).

---

## Re-verified prior findings (still apply)

| # | Finding | Verified |
|---|---|---|
| 1 | `--color-linear-text-3: #6c737f` in `apps/transcribe-md/src/app/globals.css:56` | ✓ unchanged |
| 2 | Login labels still `font-size: 10.5px` (3 hits in rendered HTML) | ✓ |
| 3 | `https://app.quillmd.com/icon.svg` → **404** | ✓ |
| 4 | `https://app.quillmd.com/favicon.ico` → **404** | ✓ |
| 5 | `https://app.quillmd.com/verify-email` → **404** (bare, no token UX) | ✓ |
| 6 | `app.quillmd.com/login` HTML has zero `href="...privacy/terms/hipaa..."` | ✓ |

---

## Lighthouse (from prior sweep, re-confirmed applicable)

| URL | Form factor | Perf | A11y | BP | SEO |
|---|---|---|---|---|---|
| `quillmd.com/` (marketing v6) | mobile | **95** | **100** | **100** | **100** |
| `quillmd.com/` | desktop | **100** | **100** | **100** | **100** |
| `app.quillmd.com/login` | mobile | 90 | **96** | **93** | **100** |
| `app.quillmd.com/login` | desktop | **100** | **96** | **96** | **100** |

Authenticated dashboard route (`/dashboard`) was NOT re-scanned in
this audit (Lighthouse against an authed route requires session-
cookie injection). Inferred from /login scores: similar a11y/BP gap
because the auth surface uses the same `--text-3` token pattern.

---

## Consolidated fix recommendation

The single fix that resolves UX-01 + UX-02 (and likely lifts
auth-surface a11y from 96 → 100):

```diff
- --color-linear-text-3: #6c737f;
+ --color-linear-text-3: #8b929c;
```
in `apps/transcribe-md/src/app/globals.css:56`. This token bump was
already done for the marketing site in Phase 7 (`apps/marketing/src/
app/landing.css` — commit `c8dc8ec`). Porting it to the auth-app
globals is a 1-line change.

For UX-03 (favicon): clone `apps/marketing/src/app/icon.svg` into
`apps/transcribe-md/src/app/icon.svg`. Next 16's file convention
auto-emits `<link rel="icon" type="image/svg+xml">` and stops the
`/favicon.ico` 404 storm.

For UX-04 (`/verify-email` bare 404) and UX-05 (legal footer):
plan-only — not in the cleanup PR scope.

---

## What was NOT covered

- **Lighthouse on authed `/dashboard`** — would need a session-cookie
  injection mechanism in Playwright. Likely scores similar to /login.
- **Keyboard-trap testing** — needs a real-browser headed session.
- **Screen reader (VoiceOver / NVDA / JAWS)** — out of scope for
  automated audit.
- **Mobile tap target audit at 375px** — partial coverage from prior
  Lighthouse runs (no `tap-targets` failure). Manual session would
  be more thorough.
- **Animation / reduced-motion** — Phase 7 v6 hero card honors
  `prefers-reduced-motion` (verified in PR #95). Not re-tested.
- **`prefers-color-scheme: light`** — app is dark-only by design;
  no light-theme accessibility concerns.
