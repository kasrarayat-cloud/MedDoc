---
id: A10-P1-001
severity: P1
domain: a11y / WCAG 1.4.3
title: axe-core color-contrast rule globally suppressed; 480 sites use sub-AA token text-3 (#6c737f)
---

## Issue

The Round-2 axe-core gate was made green by adding `color-contrast` to a hard-coded ignore list in `tests/e2e/a11y.spec.ts`. The rule remains failing on the live UI — the gate just stops reporting it. The two app-wide text tokens that fail WCAG 1.4.3 AA are:

- `--color-linear-text-3: #6c737f` on `--color-linear-bg: #08090a` — measured contrast ~4.04:1 against pure black, ~4.0:1 on the surface-1 (#0d0e10). Floor for AA on normal text (<18pt or <14pt bold) is 4.5:1.
- `--color-linear-text-4: #4b5159` on the same canvas — ~2.4:1. Fails AA at any size.

`text-linear-text-3` / `text-linear-text-4` / inline `var(--color-linear-text-3)` and `var(--color-linear-text-4)` appear in 480 source-level call sites across `apps/transcribe-md/src/` and `apps/marketing/src/` (grep count). High-traffic surfaces using text-3 for prose-grade body content include: dashboard greeting subtitle, dashboard tab counts, top-nav avatar caret, sign-up password hint ("At least 10 characters…"), check-email subtitle, error-fallback "Error ID:" label, 404 helper copy, and every admin sub-page.

text-4 is rarer (Rx split-pane subtle labels, em-coding power table) but actively used in clinician-facing surfaces.

## Evidence

`apps/transcribe-md/src/app/globals.css:64-67`

```css
--color-linear-text-3: #6c737f;
--color-linear-text-4: #4b5159;
```

`apps/transcribe-md/tests/e2e/a11y.spec.ts:113-119`

```ts
const KNOWN_NON_BLOCKING_RULE_IDS = new Set<string>(['color-contrast']);
function blockingViolations(violations: AxeViolation[]): AxeViolation[] {
  return violations.filter(
    (v) =>
      (v.impact === 'critical' || v.impact === 'serious') &&
      !KNOWN_NON_BLOCKING_RULE_IDS.has(v.id)
  );
}
```

The comment block above the `KNOWN_NON_BLOCKING_RULE_IDS` declaration explicitly acknowledges this is design debt tracked as "Round 1 UX-01" — Round-2 closure was procedural, not actual.

Sample call sites (one per file shown; 480 total):

- `apps/transcribe-md/src/app/signup/signup-form.tsx:135` — password requirements help text uses `var(--color-linear-text-3)`. This is core onboarding prose for a brand-new user; failing contrast here is a P1.
- `apps/transcribe-md/src/app/admin/usage/_components/AdminUsage.client.tsx:292` — "vs last period" body row in the active-period stats summary.
- `apps/transcribe-md/src/app/visits/[id]/transcript-tab.tsx` — diarised meta rows.

Marketing's `landing.css:36` defines `--text-3: #8b929c` (~4.7:1 — borderline AA pass), so the contrast issue is concentrated in the app, not the public site. The two apps drifted: marketing token is one full step lighter than the app's token.

## Risk

- WCAG 2.1 AA non-conformance — material legal risk for HIPAA / federal-funded clinic procurement. Doctors are professional users; many in pilot demographic are 50+ and lower-vision use text-3 prose constantly.
- Re-running axe-core without the suppression on the live login + dashboard at desktop and mobile would flag dozens of nodes per page as "serious" (axe's standard severity for color-contrast failures). The gate is not catching real regressions.
- Suppressing a single rule globally is the wrong tool: the original Round 2 promise was a token-level fix that "cascades through 400+ surfaces." That fix was deferred, not delivered.

## Recommended fix

Two options, in order of preference:

1. **Token bump (best — 1 line of CSS):** lift `--color-linear-text-3` to `#8a929c` (matches marketing's `--text-3`, ~4.7:1 on `--bg`) and `--color-linear-text-4` to `#7a808b` (~3.2:1 — still fails normal-text AA, so restrict text-4 usage to large-text only via a token-level audit). Re-run axe and confirm. The 480 call sites need no changes — Tailwind `text-linear-text-3` and `var(...)` resolve through the var so the lift is transparent.

2. **Remove the suppression and run axe to enumerate the surface:** drop `KNOWN_NON_BLOCKING_RULE_IDS` from `a11y.spec.ts`, run the project=a11y test, capture the failure list, and triage. If (1) lands first, this becomes a no-op confirmation.

After (1), update `apps/transcribe-md/tests/e2e/a11y.spec.ts` lines 105-116 to delete the comment that frames color-contrast as design debt — the gate is a real gate again.

This is the highest-leverage UX fix in the entire audit: one CSS commit removes 480 violations from a11y tooling and restores legibility for the lower-vision pilot demographic.
