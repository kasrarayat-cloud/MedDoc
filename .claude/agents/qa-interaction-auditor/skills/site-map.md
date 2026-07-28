# QuillMD site map — every route the agent walks

This is the agent's **complete inventory** of routes in the QuillMD UI.
It exists so future sweeps don't miss surfaces. Each row names the
walker script that exercises that route. New routes added to the app
MUST land here in the same PR — orphan routes (in code but not in this
file) are surfaces no one is auditing.

Source of truth: `apps/transcribe-md/src/app/**/page.tsx` and
`apps/marketing/src/app/**/page.tsx`. The CRM at `apps/meddoc-pro` is
**out of scope** (memory #9).

Status legend:
- ✅ **deep** — promoted past v2 smoke. See **walker tiers** below for the
  three sub-tiers (transactional / gate-check / preview-only).
- 🚧 **v3.2** — stub today, slated for promotion to ✅ in v3.2.
  High-traffic pages that warrant deep walks first.
- 🟡 **stub** — page-load smoke + interactive-element count. The v2
  baseline. After v3.3 there should be **zero 🟡 rows** in this matrix.
- ⚪ **uncovered** — walker pending (none should remain after agent v2).

## Walker tiers (introduced v3.3)

Not every ✅ walker is the same shape. Surfaces have different
"deepest honest test" — forcing every walker into the
`sweep-visit-page` transactional shape would mean inventing fake
assertions on pages that genuinely don't transact. Three explicit
tiers, with named reference walkers:

| Tier | When it applies | Reference walker | What the walker does |
|---|---|---|---|
| **transactional** | Page has clickable affordances that legitimately mutate DB or fire audit rows when clicked. The walker's job is to walk those clicks and assert the right side-effects. | `sweep-visit-page.mjs` (also `-dashboard`, `-visits-list`, `-new-visit`, `-patient-detail`, `-settings`, `-visit-record`) | `clickAndClassify` per affordance, with `dbSnapshotSpec` + `snapshotAuditCountWithSettle`. Outbound nav links + destructive buttons enumerated-but-skipped. |
| **gate-check** | Surface IS the gate — either role-blocked (admin/* returns 404 for DOCTOR), or a server-rendered marketing page with no DB writes, or a debug route that 404s in production. The walker's job is to verify the gate fires correctly. | `sweep-admin-queues.mjs` | Smoke load, then assert the gate signal: title contains "404", body length under threshold, or expected static-content markers present. A 200 on an admin route by a DOCTOR user IS the finding — `ok: looksGated`. |
| **preview-only** | Page has affordances but clicking them mutates state outside the test scope (signup creates a real user, password-reset fires email, MediaRecorder Stop POSTs an upload, Stripe portal redirects offsite, etc.). The walker's job is shape-assertion: confirm the affordances are present and not regressed; **never click**. | `sweep-visit-record.mjs` (also `-login` shape) | Smoke load + structured shape-check (form-field presence, expected button labels, role/aria attributes). Optionally clicks one safe affordance (e.g. mocked-side-effect buttons) but never the destructive ones. Stripe redirect / signup submit / password reset all explicitly enumerated-but-skipped. |

**Honest classification, not gradient.** A walker is *gate-check* not
because the author was lazy — it's because that's what the surface
honestly supports. Adding fake transactional assertions to a
marketing page would be theatre. The tier label tells future
contributors which shape to grow if the route changes (e.g. if a
marketing page gains a contact form, the walker grows from
gate-check → preview-only; if that contact form starts mutating a
support-ticket DB, the walker grows to transactional).

**Adopting a new tier mid-life.** If a walker that started as
gate-check picks up a real DB-mutating affordance, the row's tier
note in the matrix below should be updated and the walker rewritten
to the transactional shape. Mixed-tier walkers are fine — the
flagship `sweep-visit-page.mjs` clicks transactionally on most
buttons but enumerate-without-click on outbound-nav links.

## QuillMD app — `apps/transcribe-md` (`app.quillmd.com`)

### Authenticated routes (require TRANSCRIBE_MD entitlement)

| URL | File | Required role | Walker | Status | Description |
|---|---|---|---|---|---|
| `/dashboard` | `src/app/dashboard/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-dashboard.mjs` | ✅ transactional | Main clinician landing — Patients + All Visits tabs. v3.2 deep walker: tab toggle, brand link, Cmd-K palette, avatar dropdown. Patient/visit rows + sidebar nav + "+ New visit" enumerated as outbound. |
| `/visits` | `src/app/visits/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-visits-list.mjs` | ✅ transactional | All-visits list with 5 filter pills (URL-driven). v3.2 deep walker clicks each pill, asserts URL changes + zero `transcribe_visits` writes (filter is RSC-read-only). Filter-pill locator pins to `a[href="/visits[?filter=...]"]` (F-16 hardening — text-locator collision-prone). Visit-row links enumerated but not clicked (outbound). |
| `/visits/new` | `src/app/visits/new/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-new-visit.mjs` | ✅ transactional | Two-stage wizard (PatientPicker → VisitFormStep2). Deep walker lands on Stage 2 via `?patientId=<seeded>`; `--stage 1` walks the picker. **Submit/Continue tiles enumerated but NOT clicked** — would create a real visit + fire AI pipeline. |
| `/visits/[id]` | `src/app/visits/[id]/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-visit-page.mjs` | ✅ transactional | **The flagship walker.** Refactored in v3.1 to use `deepWalk()` + storageState reuse + `--scenario` flag (4 fixture variants). Round 4 added `assertCriticalRxOverrideFlow` — when `--scenario criticalRx`, walks the RxWarningsRail's override-button → OverrideConfirmModal flow (cancels modal without submitting); regression guard against the class of bug where API-side enforces a guard but production UI lacks the path to satisfy it. **2026-07-28: gained its own `FORBIDDEN_BUTTONS` net.** The element map is built at runtime, so it followed the page: when the per-section "Edit &lt;SECTION&gt;" pills were deleted and the review page became read-only paper, the enumerator's remaining targets became the chat editor's **Send** and **Sign &amp; Download** — both of which write, and the walker defaults to the production base URL. Sign / Send / E-M confirm / Rx override are now enumerated-and-classified but never clicked. **2026-07-28 (later): + "Save level".** The gate stack gained a documentation-level row with an Adjust affordance — the rehomed E/M override. "Adjust" and "Cancel" are safe and ARE clicked (they open and close a form); "Save level" writes `cptCodes.em.override`, an `EM_OVERRIDE_APPLIED` audit row, and arms the confirm gate, so it is enumerated-and-classified only. Expect no `section-edit-*` pills and no `review-doc-{billing,codes,dictation}-panel` in the enumeration — those surfaces are gone. |
| `/visits/[id]/record` | `src/app/visits/[id]/record/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-visit-record.mjs` | ✅ transactional | Live MediaRecorder dictation interface. v3.3 deep walker — uses `lib/media-mocks.mjs` (`addInitScript` of getUserMedia + MediaRecorder stubs) so headless Chromium never asks for the mic. Lands on the seeded `recordDraft` fixture (status=QUEUED). Clicks "Start recording", asserts NO_NETWORK_FIRED + DOM transition to RECORDING phase. **"Stop & process" enumerated but NOT clicked** — that triggers `/dictation/upload` (out of read-only scope). |
| `/patients` | `src/app/patients/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-patients-list.mjs` | ✅ transactional | Practice patient list, searchable. v3.3 walker types into the `<input type="search">` (client-side `useState` + `useMemo` filter — no URL push, no `?q=` query, no `/api/*` call) and asserts URL is unchanged + DOM card count drops as the seeded "QA" prefix narrows the grid. DB snapshot pinned to seeded `transcribe_md_patients` row to confirm zero writes during search. Patient row links + "+ New visit" button enumerated as outbound (skipped — clicking would leave the page or, in the case of /visits/new, create a stale visit if submitted). The page emits one `VIEWED_PATIENT_LIST` audit row on the initial RSC render; per-click audits are not expected (`auditTargetId: null`). |
| `/patients/[id]` | `src/app/patients/[id]/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-patient-detail.mjs` | ✅ transactional | Patient detail with Visits / Notes / Files / Trash tabs. Deep walker (v3.2) — tab-stateful clicks + dialog triggers + read-scoping check on `transcribe_md_patients`. Trash tab walked only when DOM-present. |
| `/settings` | `src/app/settings/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-settings.mjs` | ✅ transactional | Profile / security / sessions / data / billing / danger zone. **Most delicate walker:** 8 destructive buttons (delete account, sign-out-all, password change, MFA toggle, Stripe portal, data export, send-confirmation, sign-out) explicitly enumerated-but-not-clicked via the `FORBIDDEN_BUTTONS` safety net. |
| `/dev/rx-warnings` | `src/app/dev/rx-warnings/page.tsx` | DOCTOR (dev-build only) | `sweep-dev-rx-warnings.mjs` | ✅ gate-check | Rx-warning card variant preview. v3.3 walker confirms either `looksDevPreview` (title not 404 AND body > 500 chars AND `.qm-warn-*` class or "Dev / Rx warnings" eyebrow present) OR `looksGated` (title contains 404 OR body < 200 chars — the production `notFound()` path). Silent 200 with empty content is the failure mode. v2 iterated a `VARIANTS` list (cosmetic design-system smoke); v3.3 simplifies because variant enumeration adds zero gate-check value. |

### Authenticated routes (require SUPER_ADMIN + ≤12h session)

| URL | File | Walker | Status | Description |
|---|---|---|---|---|
| `/admin` | `src/app/admin/page.tsx` | `sweep-admin-dashboard.mjs` | ✅ gate-check | Platform-admin dashboard — health / activity / threats / pipeline / HIPAA. v3.3 walker confirms `notFound()` gate fires for DOCTOR-role test user (looksGated → title contains 404/Not Found OR body length < 200). 200 here is a gate-broken finding. |
| `/admin/users` | `src/app/admin/users/page.tsx` | `sweep-admin-users.mjs` | ✅ gate-check | User management — filter by product / role / status; export. v3.3 walker — DOCTOR-role gate-check, same shape as `/admin`. 200 here is a gate-broken finding. |
| `/admin/usage` | `src/app/admin/usage/page.tsx` | `sweep-admin-usage.mjs` | ✅ gate-check | API usage analytics — billing-adjacent. v3.3 walker — DOCTOR-role gate-check, same shape as `/admin`. 200 here is a gate-broken finding. |
| `/admin/hipaa` | `src/app/admin/hipaa/page.tsx` | `sweep-admin-hipaa.mjs` | ✅ gate-check | HIPAA compliance dashboard. v3.3 walker — DOCTOR-role gate-check, same shape as `/admin`. 200 here is a gate-broken finding. |
| `/admin/threats` | `src/app/admin/threats/page.tsx` | `sweep-admin-threats.mjs` | ✅ gate-check | Security threats / anomalies log. v3.3 walker — DOCTOR-role gate-check, same shape as `/admin`. 200 here is a gate-broken finding. |
| `/admin/queues` | `src/app/admin/queues/page.tsx` | `sweep-admin-queues.mjs` | ✅ gate-check | **NEW PR-L** — BullMQ queue health dashboard (depth across transcribe-md / cleanup / dlq:permanent-failures + recent DLQ jobs). Same SUPER_ADMIN gate as the other `/admin/*` routes; DOCTOR test user expects 404. **Reference walker for the gate-check tier** (see "Walker tiers" above). 200 here is a gate-broken finding. |

### Public routes (no auth)

| URL | File | Walker | Status | Description |
|---|---|---|---|---|
| `/` | `src/app/page.tsx` | _(redirect-only)_ | n/a | Server redirect → `/dashboard` or `/login`. No render. Agent sees the redirect chain via `sweep-login.mjs`. |
| `/login` | `src/app/login/page.tsx` | `sweep-login.mjs` | ✅ preview-only | Sign-in form. v3.3 walker confirms email + password + submit field presence + submit-button label + outbound links to `/forgot-password` and `/signup`. **Never submits** — every authenticated walker exercises the real login path via `getOrCreateAuthState`. |
| `/signup` | `src/app/signup/page.tsx` | `sweep-signup.mjs` | ✅ preview-only | Self-service signup (free 14-day trial). v3.3 walker confirms `name` + email + `password` + `confirmPassword` + `acceptTerms` checkbox + submit field presence + outbound links (back-to-`/login` + ToS/privacy off-site to `MARKETING_URL`). **Never submits** — would create a real user + fire the verification-email pipeline. |
| `/forgot-password` | `src/app/forgot-password/page.tsx` | `sweep-forgot-password.mjs` | ✅ preview-only | Email-based recovery request form. v3.3 walker confirms email + submit field presence + back-to-`/login` link. **Never submits** — would fire a real password-reset email + tick the per-IP rate-limit bucket (5/hour/IP). |
| `/reset-password` | `src/app/reset-password/page.tsx` | `sweep-reset-password.mjs` | ✅ preview-only | Token-based new-password form (`?token=...`). v3.3 walker hits `?token=qa_smoke_invalid_token` so the form branch renders; predicate accepts EITHER (a) form rendered with `password` + `confirmPassword` inputs OR (b) the missing-token fallback rendered. **Never submits** — would either reset a real password (valid token) or generate audit-log noise (invalid token). |
| `/check-email` | `src/app/check-email/page.tsx` | `sweep-check-email.mjs` | ✅ preview-only | Verification confirmation page after signup. No `<form>` element — just informational copy + envelope SVG + a single `Resend verification link` button + back-to-`/login` link. v3.3 walker confirms button presence + label + outbound links. **Never clicks Resend** — would POST `/api/auth/resend-verification` (fires real email + ticks the verification rate-limit). |

## Marketing site — `apps/marketing` (`quillmd.com`)

All routes are public; same `NavBar` + `Footer` chrome on every page.

| URL | File | Walker | Status | Description |
|---|---|---|---|---|
| `/` | `src/app/page.tsx` | `sweep-marketing-home.mjs` | ✅ gate-check | Landing — hero / features / pricing teaser / FAQ. v3.3 walker asserts page renders + Nav (home uses `<nav class="top">`, not the sub-page `<header><nav>`) + Footer + hero h1 + at least one Get-started CTA. Outbound link count emitted for regression-detection. |
| `/about` | `src/app/about/page.tsx` | `sweep-marketing-about.mjs` | ✅ gate-check | Company story. v3.3 walker asserts page renders + NavBar/Footer chrome + h1 + the "story" / "approach" section headings. Outbound link count emitted. |
| `/pricing` | `src/app/pricing/page.tsx` | `sweep-marketing-pricing.mjs` | ✅ gate-check | Pricing tiers + FAQ. v3.3 walker asserts page renders + NavBar/Footer chrome + h1 + at least 2 tier headings (proxy for tier-card count). Outbound + dollar-price mention counts emitted for regression-detection. |
| `/demo` | `src/app/demo/page.tsx` | `sweep-marketing-demo.mjs` | ✅ gate-check | "Coming soon" placeholder. v3.3 walker asserts the placeholder copy is still present — when the real demo lands and that assertion fails, the walker grows from gate-check → preview-only with player-affordance enumeration. |
| `/signup` | `src/app/signup/page.tsx` | `sweep-marketing-signup.mjs` | ✅ gate-check | Meta-refresh redirect to the app's `/signup`. v3.3 walker uses `domcontentloaded` (not `networkidle`) to read the meta tag before the redirect fires, then asserts the target is an absolute URL ending in `/signup` (currently `http://5.231.107.93:9020/signup` per the IP-based default; will become `app.quillmd.com/signup` once DNS lands). |
| `/security` | `src/app/security/page.tsx` | `sweep-marketing-security.mjs` | ✅ gate-check | Security posture. v3.3 walker asserts page renders + NavBar/Footer + "Security practices" h1 + Application/Infrastructure section headings + the `security@ashtechgroup.com` contact marker. |
| `/hipaa` | `src/app/hipaa/page.tsx` | `sweep-marketing-hipaa.mjs` | ✅ gate-check | HIPAA compliance overview ([DRAFT] header — pending legal). v3.3 walker explicitly asserts the `[DRAFT` marker is still present so we notice when counsel signs off; also asserts h1 + BAA section heading + `compliance@ashtechgroup.com` contact. |
| `/privacy` | `src/app/privacy/page.tsx` | `sweep-marketing-privacy.mjs` | ✅ gate-check | Privacy policy. v3.3 walker asserts page renders + NavBar/Footer + "Privacy Policy" h1 + retention section + the `privacy@ashtechgroup.com` contact. DRAFT marker tracked alongside the assertions. |
| `/contact` | `src/app/contact/page.tsx` | `sweep-marketing-contact.mjs` | ✅ gate-check | Mailto-link contact list (NOT a real form — `<dl>` of `mailto:` links across 6 categories). v3.3 walker asserts the four canonical destinations are present (support / sales / compliance / security), surfaces the form-shape so an upgrade to a real `<form>` becomes visible in the report (and triggers a tier promotion to preview-only). |
| `/terms` | `src/app/terms/page.tsx` | `sweep-marketing-terms.mjs` | ✅ gate-check | Terms of service. v3.3 walker asserts page renders + NavBar/Footer + "Terms of Service" h1 + Acceptance / Limitation-of-liability section headings + the `legal@ashtechgroup.com` contact. DRAFT marker tracked. |

## Dynamic route parameters

| Param | Routes | Binding |
|---|---|---|
| `[id]` (visit) | `/visits/[id]`, `/visits/[id]/record` | `transcribeVisit.id` (cuid). User-scoped: ownership check ensures session user owns the row. |
| `[id]` (patient) | `/patients/[id]` | `transcribeMdPatient.id` (cuid). Practice-scoped: cross-practice access blocked at the router level. |

The agent uses the seeded fixtures (`fixtures/seeded-ids.json`) for both
binding parameters — `userId`, `patientId`. New visits the agent
creates use the seeded patient.

## Layouts that add chrome

These add navigation surface that's also click-able and audit-worthy.
Element coverage for the chrome lives in `quillmd-workflows.md`.

| Layout | Wraps | Chrome |
|---|---|---|
| `AppFrame` | `/dashboard`, `/patients*`, `/visits*`, `/settings`, `/admin*`, `/dev/*` | 240 px sidebar + topnav + Cmd+K palette + dark canvas. |
| Root layout | All transcribe-md routes | Command palette host, global shortcuts, skip-to-content link. |
| `/admin/layout.tsx` | All `/admin*` | SUPER_ADMIN gate + 12-hour session-freshness check + access-audit log. 404s if unauthorized. |
| Marketing root | All marketing routes | `NavBar` (top) + `Footer` (bottom). Identical on every page. |

## Coverage budget

For the **v2** build, every route had a 🟡 walker that confirms the
page loads as the test user (or as anonymous for public routes). The
flagship `sweep-visit-page.mjs` was the only ✅.

The **v3.1** build added:
  - `lib/walker-base.mjs deepWalk()` — the shared element-walk +
    DB-diff helper that v3.2 walkers use
  - storageState session reuse (28 logins → 1 login + 28 cookie
    loads); fixes the v2 rate-limit cascade
  - `seed-qa-fixtures.ts` — four scripted fixture visits
    (bumpEligible / criticalRx / pediatric / nonClinical) so the
    flagship walker can exercise different code paths via
    `--scenario`
  - 5 routes marked 🚧 v3.2 as the v3.2 deep-walk priority list

The **v3.2** build (this PR) promoted all 5 of those routes from
🚧 to ✅:
  - `/dashboard` — tab toggle, brand link, Cmd-K palette, avatar
    dropdown; outbound nav enumerated
  - `/visits` — 5 filter pills walked + URL-change assertion +
    zero-DB-write check
  - `/visits/new` — Stage 2 specialty + capture-mode-tile
    enumeration; submits explicitly skipped (would create real
    visit + fire pipeline)
  - `/patients/[id]` — 4 tabs (Trash conditional) + dialog
    triggers + intentional-stub-copy capture
  - `/settings` — 6-section anchor walk + ProfileForm no-op save;
    8 destructive buttons explicitly enumerated-but-skipped
    (delete-account / sign-out-all / password / MFA / Stripe /
    export / send-confirmation / bare-sign-out)

The **v3.3 broader-walker-depth** build closed the matrix. Three
explicit tiers (transactional / gate-check / preview-only — see
"Walker tiers" at the top of this doc) replaced the binary 🟡/✅
distinction. Every ✅ row now carries its tier label so future
contributors know which shape to grow if the underlying surface
changes.

The 23 stubs that v3.3 promoted, by tier:

- **transactional (1):** `/patients` — search input + zero-write
  assertion against the seeded `transcribe_md_patients` row
- **gate-check (16):** all 10 marketing routes (server-rendered,
  no DB writes — chrome + content-marker assertion), all 6
  `/admin/*` routes (DOCTOR test user expects 404 — `looksGated`
  via title-404 OR body<200 chars), `/dev/rx-warnings`
  (production 404 OR dev-build render — both are valid)
- **preview-only (5):** `/login`, `/signup`, `/forgot-password`,
  `/reset-password`, `/check-email` — form-shape assertion
  without submit (would create real users / fire real emails /
  poison rate-limits)

`/visits/[id]/record` was promoted earlier in v3.3 via
`lib/media-mocks.mjs` (`addInitScript` of getUserMedia +
MediaRecorder stubs) + the seeded `recordDraft` fixture
(`qa_fix_visit_record_draft`, status=QUEUED).

**After v3.3 broader, zero 🟡 rows remain** in the matrix above.

## When a new route is added to the app

The agent owner must:

1. Add a row to the table above with the new route's URL, file, role,
   and a one-line description.
2. Add a stub walker `scripts/sweep-<page>.mjs` (mirror an existing
   stub).
3. Append a `quillmd-workflows.md` workflow section documenting the
   page's interactive elements.
4. Add the new walker name to the registry in `scripts/sweep-all.mjs`
   so the next full-site sweep picks it up.

**Pick the tier** from "Walker tiers" at the top: transactional if
the surface has affordances that legitimately mutate state when
clicked; gate-check if the surface IS the gate (role-blocked,
server-rendered marketing, dev-build-only debug); preview-only if
the affordances would mutate state outside the test scope. The tier
label goes in the row's Status column (e.g. `✅ gate-check`).

Don't ship 🟡 — every new walker should land at its tier-correct
✅ from day one. The 🟡 status is reserved as a regression marker
(walker exists but didn't get tier-promoted in the same PR as the
route — flag for follow-up). Empty status (route in code, no
walker) is a strict regression and the next agent run surfaces it.
