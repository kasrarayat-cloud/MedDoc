# UX-01 — Color contrast on auth surfaces below WCAG AA

**Severity:** P2 (a11y violation, axe-core `serious` impact)
**Domain:** auth surface (`app.quillmd.com/login`, `/signup`,
`/forgot-password`, `/reset-password`, `/check-email`)
**File:** `apps/transcribe-md/src/app/globals.css:56`

## What

Token `--color-linear-text-3 = #6c737f` rendered on `--color-linear-bg
= #08090a` produces a contrast ratio of **4.17:1**. WCAG AA requires
**4.5:1** for normal text (and 3:1 for large text). The labels in
question are 10.5px / 11px small mono — well within the "normal text"
threshold.

Confirmed by axe-core 4.10.0:
- `/login` — 7 elements affected
- `/signup` — 10 elements affected

Affected element examples:
- Form labels: `Email`, `Password`, `Full name`
- Eyebrow tags: `Welcome back`, `New to QuillMD`
- Trust strip: `HIPAA ready`, `BAA included`, `US-hosted`
- Footer caption text

## Why it matters

- WCAG AA non-compliance is a stated brand promise (the marketing
  site's HIPAA messaging). Auth surface should match.
- Real-user impact: doctors with mild contrast sensitivity (very
  common with age, screen brightness, glare, etc.) struggle to
  read field labels, slow down their auth flow.
- Same root cause was fixed for the Phase 7 marketing redesign
  (`landing.css` bumps `--text-3` to `#8b929c`), but the auth shell
  wasn't ported.

## Reproduction

1. Open `https://app.quillmd.com/login` in any modern browser
2. Run Lighthouse mobile audit OR run `axe.run()` from devtools
3. Observe `color-contrast` violation on the elements listed above

Or measure directly:
```js
> getComputedStyle(document.querySelector('label[for="email"]')).color
"rgb(108, 115, 127)"  // #6c737f
```

## Risk if NOT fixed

- Lighthouse a11y stays at 96 (target ≥95 — it passes the bar
  already, but barely)
- Real users with contrast sensitivity have measurably worse UX
- HIPAA-eligible-but-not-WCAG-2.1-compliant is a sub-optimal
  audit posture

## Proposed remediation

```diff
- --color-linear-text-3: #6c737f;
+ --color-linear-text-3: #8b929c;
```
in `apps/transcribe-md/src/app/globals.css:56`.

`#8b929c` on `#08090a` = ~5.2:1 contrast (passes AA).

Visual impact: small mono text becomes slightly less faint.
Brand impact: minimal (the marketing site already uses this brighter
shade since Phase 7 — applying it to the app shell restores brand
parity).

## Effort
- Fix: 1 line
- Re-deploy + smoke test: ~10 min
- Total: ~15 min

## Risk to fix
LOW — single CSS token bump, no logic change. Hundreds of usages
across the app shell, but all uniformly slightly brighter — no
selective effect to test.

## Status
Plan-only per audit rules (P2 ≠ auto-fix). Recommend Kasra approve
the 1-line PR.
