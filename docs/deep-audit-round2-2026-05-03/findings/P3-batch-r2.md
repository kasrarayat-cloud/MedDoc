# P3 batch — Round 2 nitpicks

A consolidated list of P3 nitpicks identified in Round 2. Each
is small enough that a single batched cleanup PR could address
all of them in <2 hours total work.

## P3-R2-001 — Patient-create button has no client-side debounce

**Domain A finding A4-001.**

Rapid clicks on "Create & continue" fire one POST per click:
- 5 rapid clicks → 5 × `/api/patients/fuzzy-match` + 5 × `/api/patients`
- All 10 returned 429 (server rate limit caught it) ✓
- 0 patients created in DB ✓

UX is degraded (user sees rate-limit error instead of progress).

**Fix:** disable button on click, show spinner, re-enable on response.

```diff
+ const [busy, setBusy] = useState(false);
- <button onClick={handleSubmit}>Create & continue</button>
+ <button disabled={busy} onClick={async () => {
+   setBusy(true);
+   try { await handleSubmit(); } finally { setBusy(false); }
+ }}>{busy ? <Spinner/> : 'Create & continue'}</button>
```

Apply same pattern to "Create new patient", "Sign in", "Sign & Send".

**Effort:** ~30 min across 4-5 buttons.

---

## P3-R2-002 — Profile-update toast text duplicated in DOM

**Domain F finding F-002.**

When the profile name save succeeds, the `[role="alert"]` element
ends up with text:
```
"Profile updatedYour changes are saved.Profile updatedYour changes are saved."
```

Likely a React rerender landing duplicate content on the same
toast container without clearing.

**Fix:** investigate `<Toast>` from sonner (or whichever toast lib
is in use) — likely fixed by `toast.dismiss()` before `toast.success()`
in the save handler.

**Effort:** ~15 min once root cause confirmed.

**Risk if NOT fixed:** zero (cosmetic; only visible to screen readers
which would announce twice).

---

## P3-R2-003 — No skip-to-content link

**Domain G finding G-001.**

WCAG 2.4.1 (Bypass Blocks) requires a `Skip to main content` link
as the first focusable element. Not present in the auth-app shell.

**Fix:**
```tsx
// apps/transcribe-md/src/app/layout.tsx (or app shell)
<a href="#main" className="sr-only focus:not-sr-only">Skip to main content</a>
// then ensure <main id="main"> wraps page content
```

**Effort:** ~10 min (1 component + 1 wrapper update).

---

## P3-R2-004 — Patient-search input is 14px (iOS zoom-on-focus)

**Domain H finding H-002.**

The patient search input on `/visits/new` step 1 has `font-size:
14px`. iOS Safari zooms in on inputs <16px when focused — disorients
mobile doctors.

**Fix:** bump to 16px:
```diff
- <input style="font-size: 14px" placeholder="Search by name or external ID…">
+ <input style="font-size: 16px" placeholder="Search by name or external ID…">
```

**Effort:** ~2 min (1 CSS line).

---

## P3-R2-005 — Round 1 P3-001 (Codes-tab Cmd-K) is a TEST RIG ARTIFACT

**Domain E finding E-002.**

The prior P3-001 finding from `docs/qa-sweep-authenticated-2026-05-03/`
was a test-rig artifact — Playwright's `:has-text("Codes")` selector
matched the Cmd-K search bar (button label `"Search patients,
visits, codes…⌘K"`) instead of the Codes tab. The Codes tab itself
works correctly.

**Action:** mark Round 1 P3-001 RESOLVED. No code change needed.

---

## P3-R2-006 — `/api/visits/{id}/export/fhir` returns 404

**Domain C finding C-002.**

Marketing copy advertises FHIR JSON export. The endpoint doesn't
exist. Either:
1. Marketing aspiration / future feature → either build it or
   trim the marketing copy
2. Different surface (e.g., a future direct EHR integration)

**Action:** clarify with Kasra whether FHIR JSON is on roadmap.
If not, edit marketing copy to remove the claim.

**Effort:** marketing edit ~5 min; FHIR build ~4-8 hours
depending on scope.
