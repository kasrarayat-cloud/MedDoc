# Audit — logic + functionality report

Scope: apps/{marketing,meddoc-pro,transcribe-md} + packages/*.
Method: 5 parallel static-analysis agents + 27-case Playwright probe against prod + 41 unauth API probes + cross-subdomain cookie inspection.

No bugs fixed. No PR created. Evidence in `audit-evidence/`.

---

## Critical (blocks launch)

### C1 — Patient birthYear falls back to age 30 when missing
- **Where:** `apps/meddoc-pro/src/lib/data/patients.ts:483`
- **Code:** `birthYear: row.birthYear ?? new Date().getFullYear() - 30`
- **Repro:** Create a patient without a DOB → any LLM path that reads `birthYear` (letters, referrals, SOAP generation, realtime voice context) silently treats them as 30 years old.
- **Actual vs expected:** Expected — a missing DOB produces a clear "unknown" in AI output or forces the caller to require DOB. Actual — AI writes medically-plausible-but-wrong content based on age 30.
- **Blast radius:** Any patient row with NULL `birthYear` in DB. Since this is a HIPAA-facing clinical product, an 82-year-old treated as 30 in a Rx draft is a real safety issue.
- **Fix (est. 1–2h):** Return `birthYear: row.birthYear ?? null`; update downstream consumers in `actions.ts`, `PatientDetailClient.tsx`, and `lib/realtime/*` to guard on null and either omit age from the prompt or force the user to fill DOB first.

---

## High (degrades experience)

### H1 — Stale-closure risk on `recorder.onstop` in live-record flow (defer, monitor)
- **Where:** `apps/transcribe-md/src/app/visits/[id]/record/recording-client.tsx:135-141`
- **What:** `recorder.onstop = () => finalizeAndUpload()` captures the `finalizeAndUpload` reference at `start()` time. Same pattern that caused the mark-moments bug I reverted.
- **Why not Critical now:** `finalizeAndUpload` only closes over `visitId` + `router` (both stable for the page's lifetime). No state variable leaks into the handler today.
- **Risk:** If anyone adds a state dependency to `finalizeAndUpload` later, the same bug returns. Leave a comment at the onstop handler and/or route state through refs explicitly.
- **Fix (est. 30 min):** Stash `finalizeAndUpload` in a ref and read from the ref inside onstop — pattern I used for the reverted mark-moments fix.

### H2 — Mobile pricing page overflows at 393px
- **Where:** `apps/marketing/src/app/pricing/page.tsx` (via dynamic probe)
- **Evidence:** `audit-evidence/perf/mobile-marketing-pricing.json` → scrollWidth 505 vs clientWidth 393. Screenshot at `audit-evidence/screenshots/mobile-marketing-pricing.png`.
- **Impact:** User sees a horizontal scrollbar on mobile; pricing tiers bleed off the right edge.
- **Fix (est. 1h):** Add responsive grid-cols-1 breakpoint + wrap the comparison table in `overflow-x-auto` with clear affordance.

### H3 — Mismatched-passwords submit hangs on /signup
- **Where:** app.quillmd.com/signup
- **Evidence:** `audit-evidence/test-results-raw.json` — `signup — mismatched passwords` → `TimeoutError: locator.click: Timeout 15000ms exceeded`. Screenshot at `audit-evidence/screenshots/signup-mismatch.png`.
- **Repro:** Fill name, email, password="Strong2024Pass", confirmPassword="Different2024Pass", accept terms, click "Create account". Submit button becomes un-interactable for ≥15s.
- **Actual vs expected:** Expected — client or server validation fires instantly with "passwords don't match". Actual — button locks up (likely `pending` state set by `useActionState` never resolves because the server action returns an error shape the form doesn't unwrap correctly, or the button is never re-enabled).
- **Fix (est. 1–2h):** Inspect `apps/transcribe-md/src/app/signup/signup-form.tsx` — the `pending` state from `useActionState` on a form-validation-error path isn't releasing. Add a client-side match-check that fires before submit.

### H4 — 10 API validation gaps in meddoc-pro (no zod on bodies)
- **Where:** All 11 meddoc-pro /api/**/route.ts files
- **Details:** `audit-evidence/validation-gaps.md` (High section)
- **Top offenders:**
  - `/api/doc-editor/route.ts:189-204` — JSON follow-up body unvalidated; client drives OpenAI spend
  - `/api/doc-editor/save/route.ts:96-101` — no `content` size cap, can OOM docx generator
  - `/api/assistant-tool/route.ts` — 540 lines of hand-rolled typeof narrowing instead of zod discriminated union
  - `/api/transcribe/route.ts`, `/api/patients/extract-from-voice/route.ts` — no MIME whitelist on audio
- **Impact:** All routes ARE auth-gated + rate-limited, so gap is server-side reliability + billing abuse, not auth bypass. Still pre-launch fix material.
- **Fix (est. 4–6h): add shared `withApiHandler`-style wrapper + zod schemas for all 11 routes. Matches transcribe-md's pattern.**

---

## Medium

### M1 — Voice-minutes daily cap is read-check-then-issue (concurrent sessions bypass)
- `apps/meddoc-pro/src/lib/realtime/usage-cap.ts:51-58` + `api/realtime/session/route.ts:59`
- Open N tabs in the same second → all pass the cap check → N sessions get minted
- Fix: atomic `UPDATE ... WHERE used + requested ≤ cap` in a transaction, check affected rows > 0

### M2 — `dc.onclose` closes over stale `status` value
- `apps/meddoc-pro/src/lib/hooks/useRealtimeSession.ts:474-476`
- Session status mis-reported after disconnect because the handler sees whatever status was set when dc was created
- Fix: read from a ref or dispatch to a reducer

### M3 — Appointment times render in container timezone (UTC), not doctor's tz
- `apps/meddoc-pro/src/lib/realtime/tools.ts:588-594`
- Timezone is plumbed through the session context but not passed to this render path
- Doctor sees "3pm appointment" when it's really 10am in their tz

### M4 — `lastActiveAt` update is a floating promise
- `packages/auth/src/user-session.ts:97-104`
- `.catch` attached but the promise isn't voided → Node exit-on-unhandled-rejection would be triggered by a future runtime change. Not a bug today; safe to leave.

### M5 — `findUnique({ where: { id } })` without `patientAccessWhere` in 2 spots
- `apps/meddoc-pro/src/app/dashboard/patients/[id]/page.tsx:91`
- `apps/meddoc-pro/src/app/api/realtime/session/route.ts:104`
- Safe TODAY because `getPatientById` already gated the same id earlier in the call tree. One reorder would reintroduce a tenant leak. Mark as refactor target.

### M6 — 2FA is declared in schema, not implemented
- `packages/db/prisma/schema.prisma:274-282` + `apps/transcribe-md/src/app/settings/page.tsx:225-229`
- HIPAA §164.312(d) expects MFA for PHI access. Already in the pre-launch audit as Critical; restating for consolidation.

### M7 — No forgot/reset-password flow on meddoc-pro
- `apps/meddoc-pro/src/app/login/page.tsx:170` "Forgot password?" link is `href="#"`
- Users locked out of pro.quillmd.com have no self-service recovery; requires admin reset via system-admin UI
- Already flagged in the pre-launch audit

### M8 — "Watch Demo" button on meddoc-pro landing is a no-op
- `apps/meddoc-pro/src/components/landing/Hero.tsx:141`
- Button renders with no onClick handler — clicking does nothing visible to users
- Either wire to a video modal or remove the button

### M9 — "More Filters" button on patients list is a no-op
- `apps/meddoc-pro/src/app/dashboard/patients/PatientsListClient.tsx:297`
- Same pattern — button with no handler

### M10 — 429s on unauthenticated /api/auth/* (self-limiting; OK but noted)
- The uptime cron hitting /api/auth/verify-email and /api/auth/reset-password during probing tripped the per-email rate bucket
- Not a bug; documented as a monitoring gotcha — keep the uptime cron on /api/health only

---

## Low / nice-to-have

- **L1** `cap` comparison `> 0` should be `>= 1` — off-by-one in `usage-cap.ts`. No practical effect.
- **L2** Cache eviction uses TTL rather than LRU in `lib/realtime/cache.ts` — fine for current size; revisit if cache grows.
- **L3** Pre-existing eslint errors in Hero.tsx + patient-picker.tsx — fixed in Batch A.
- **L4** `signup/page.tsx` on marketing has a `meta-refresh` to app.quillmd.com without `robots: { index: false }`. SEO-toxic but tracked in pre-launch audit.
- **L5** `app/settings/page.tsx:289` `<a href="/api/settings/export-data">` — plain GET of user data. Enforced by auth; fine.
- **L6** Reduced-motion subscription in recording-client.tsx uses addEventListener/removeEventListener correctly — confirmed via logic-errors audit.
- **L7** Marketing `/signup` page is a meta-refresh stub — documented.
- **L8** `setTimeout` inside modal unmount paths — minor leak, doesn't affect correctness.

---

## Security posture — explicit positives

- **Session isolation:** `__Host-authjs.csrf-token` on both app.quillmd.com and pro.quillmd.com — exact-host scoping means no cross-subdomain cookie bleed. Verified via direct cookie-header inspection.
- **HSTS preload:** both apps set `max-age=31536000; includeSubDomains; preload` on every response.
- **Auth gating universal:** 44/44 API routes return 401 on unauth probe (excluding /api/health which is intentionally public). Verified via `audit-evidence/api-probes/results.jsonl`.
- **Tenant scope universal:** `visit.userId !== userId` guards on all 18 transcribe-md visit routes; `patientAccessWhere(session)` composes into every meddoc-pro patient/appointment/note Prisma query.
- **No XSS execution:** POST to /signup with `<script>window.__xss_fired=true</script>` in the name field — payload didn't execute (React escaping + server-side rendering).
- **No 5xx responses captured** on any page load in the probe suite (30+ pages).
- **No PHI in error responses** tested — all 401s return opaque `{"error":"Unauthorized"}` / `{"error":"Forbidden"}`.

---

## Test coverage stats (this audit)

| Category | Tested | Total | Notes |
|---|---:|---:|---|
| Public pages | 18 | 18 | all 2xx, no console errors except one expected 429 |
| Mobile viewports | 5 | 5 | 1 overflow (pricing) |
| Form edge cases | 7 | 7 | signup-mismatch hangs (H3) |
| API routes (unauth probe) | 41 | 44 | 3 skipped: NextAuth catchall, PDF export (stream), client-errors nested |
| Authenticated flows | 0 | N/A | skipped — no test account in .env.test yet |
| Browsers | 1 | 1 | Chromium only (as configured) |

### Gaps explicitly NOT covered
- Authenticated user flows (dashboard, patient CRUD, visit wizard, SOAP editor, sign & send, export PDF/DOCX)
- Settings profile/password update end-to-end
- Realtime voice assistant (pro.quillmd.com core feature)
- BullMQ worker pipeline under real load
- External services: Anthropic, Deepgram, Whisper, Resend, MinIO — verified via code paths only, not live calls

To close these: set `TEST_APP_EMAIL` / `TEST_APP_PASSWORD` in `tests/automated/.env.test`, set `E2E_READ_ONLY=false`, run `bash tests/automated/run-all.sh --e2e`.

---

## Performance findings

Per-page navigation timing (ms) — all pages well under 1s on the first byte:

| Surface | Slowest page | TTFB | DCL | Load |
|---|---|---:|---:|---:|
| marketing | /pricing | 202 | 292 | 518 |
| marketing | /  | 162 | 1030 | 1031 |
| app.quillmd.com | /login | 402 | 494 | 661 |
| pro.quillmd.com | / | 122 | 448 | 862 |

- No LCP captured via PerformanceObserver (probe limitation, not a real finding).
- No bundle-analysis run in this audit — `next.config.ts` doesn't wire `@next/bundle-analyzer` in any app; flagged for the next round.

---

## Accessibility findings

Not comprehensively audited this round. Deferred items from pre-launch audit still stand:
- WCAG AA contrast failures on `--color-fg-4` (2.3:1) and `--color-text-muted` (3.7:1) — globals.css
- No universal screen-reader smoke test was run — requires a separate axe-playwright integration

Fix candidates: adopt `@axe-core/playwright` in a new spec + fix the two offending color tokens.

---

## Evidence

```
audit-evidence/
├── screenshots/           (30+ PNGs: desktop + mobile)
├── console-logs/          (per-page console/pageerror capture)
├── network-logs/          (5xx capture, currently empty = good)
├── api-probes/results.jsonl (41 probes)
├── perf/                  (Navigation Timing per page)
├── test-results-raw.json  (full Playwright run)
├── inventory-transcribe-md.md
├── inventory-meddoc-pro.md
├── inventory-marketing.md
├── issues-meddoc-pro.md
├── validation-gaps.md
└── logic-errors.md
```
