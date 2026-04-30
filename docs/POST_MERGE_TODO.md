# Post-merge cleanup tasks

Items deferred from the Phase 2 Clinician remodel — to be addressed AFTER `feature/clinician-remodel` lands on `main`. None of these block the merge.

Created: 2026-04-29 during Phase 2 D+E gate review.

---

## 1. ✅ Verified: `/dev/rx-warnings` 404 in production is INTENTIONAL

**Status:** documented; no action needed.

`apps/transcribe-md/src/app/dev/rx-warnings/page.tsx:51` explicitly calls `notFound()` when `process.env.NODE_ENV === 'production'`. The route is a designer/QA preview surface for the RxWarningCard variants and is gated to development builds only. The page header itself notes "Dev-only route. 404s in production." (line 75).

QA Layer 3b's 404 on this route during Strategy A (production build) is therefore the **correct behavior**, not a regression. Surfaced here for forward-looking clarity so future contributors don't chase the 404 as a bug.

---

## 2. ✅ Fixed: typo `processing-state.tsx:426` literal `’` in JSX text

**Status:** fixed during merge prep, commit `87340e0`. Replaced the 8-character literal escape with the actual U+2019 character.

**Original notes (kept for archival):**

**Severity:** trivial; not Clinician-scope.

```tsx
// Line 426 — current:
Elapsed {elapsedMin} min · leave the page and we’ll finish in the background
```

JSX text content does NOT interpret backslash escapes like `’`, so users see the literal characters `we’ll` instead of the typographically-correct `we'll`.

**Fix options:**

- **Simplest:** replace `we’ll` with the actual Unicode character `we'll` (U+2019 right single quotation mark).
- **Or:** ASCII apostrophe `we'll`.
- **Or:** template-wrap inside JSX: `we{'’'}ll`.

Any of the above is a one-line change. Pre-existed before Phase 2; preserved verbatim through the Batch D dual-theme migration (commit `34e5dad remodel(clinician): processing-state dual-theme via theme prop`).

---

## 3. A11y pass via Playwright/axe-core

**Severity:** test-coverage gap; needs to run before final merge.

Layer 6 (a11y smoke) of the `qa-clinician-remodel` skill was SKIPPED in every batch (B+C, D, E) because the QA sandbox host has no headed browser binary. The a11y harness must run on a dev box or in CI before the PR ships.

**Suggested setup** (per the skill spec):

```javascript
// browser_evaluate in Playwright MCP
await import('https://cdn.jsdelivr.net/npm/axe-core@4.10.0/+esm')
  .then(m => m.default || m);
const results = await axe.run(document, { resultTypes: ['violations'] });
return results.violations.filter(
  v => v.impact === 'critical' || v.impact === 'serious'
);
```

**Routes to cover** (per QA skill):
- `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/check-email` (Batch A + F)
- `/dashboard` (Batch C)
- `/visits`, `/visits/[id]?status=READY`, `?status=SIGNED`, `?status=PROCESSING` (Batch D)
- `/visits/new`, `/visits/[id]/record` (Batch E)
- `/admin/audit-logs` (Batch G — when complete)

**Pass criterion:** zero critical OR serious violations (color-contrast, missing-alt, missing-label, role-lacks-required-children).

---

## 4. (Reserved) Items surfaced during Batch G

To be appended after Batch G QA completes.

---

## 6. 📝 Pull mockup-fidelity dashboard content (Phase 3)

Current dashboard renders 4 metric cards + 1 patient pill. The Clinician mockup at `docs/design-directions-v3/clinician/dashboard.html` shows a richer surface: morning greeting ("Good morning, Dr. Chen."), 11-row patient list with colored avatars per specialty, "Three drafts, ready when you are." section with named surface CTAs.

Implementation gap is content/data-emit, not visual — palette + typography 100% match the mockup. Phase 3 task: extend dashboard data layer to surface the mockup's content density.

**Surfaced by:** merge-prep round 1 verdict `🟡 PASS-WITH-FLAGS` (report `merge-prep-20260430T001246Z.md`, Flag #2). Deferred per user decision at the merge-prep gate; merge-prep round 2 (`merge-prep-20260430T010915Z.md`) confirmed the deferral and proceeded to 🟢 PASS without it.
