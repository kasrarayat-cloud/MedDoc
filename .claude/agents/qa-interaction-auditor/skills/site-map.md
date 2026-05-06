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
- ✅ **deep** — full element walk via `lib/walker-base.mjs deepWalk()`,
  DB diff per click, audit-row diff. Today: `sweep-visit-page.mjs`.
- 🚧 **v3.2** — stub today, slated for promotion to ✅ in v3.2.
  High-traffic pages that warrant deep walks first.
- 🟡 **stub** — page-load smoke + interactive-element count. The v2
  baseline; the long tail of pages that don't yet need deep walks.
- ⚪ **uncovered** — walker pending (none should remain after agent v2).

## QuillMD app — `apps/transcribe-md` (`app.quillmd.com`)

### Authenticated routes (require TRANSCRIBE_MD entitlement)

| URL | File | Required role | Walker | Status | Description |
|---|---|---|---|---|---|
| `/dashboard` | `src/app/dashboard/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-dashboard.mjs` | ✅ | Main clinician landing — Patients + All Visits tabs. v3.2 deep walker: tab toggle, brand link, Cmd-K palette, avatar dropdown. Patient/visit rows + sidebar nav + "+ New visit" enumerated as outbound. |
| `/visits` | `src/app/visits/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-visits-list.mjs` | ✅ | All-visits list with 5 filter pills (URL-driven). v3.2 deep walker clicks each pill, asserts URL changes + zero `transcribe_visits` writes (filter is RSC-read-only). Visit-row links enumerated but not clicked (outbound). |
| `/visits/new` | `src/app/visits/new/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-new-visit.mjs` | ✅ | Two-stage wizard (PatientPicker → VisitFormStep2). Deep walker lands on Stage 2 via `?patientId=<seeded>`; `--stage 1` walks the picker. **Submit/Continue tiles enumerated but NOT clicked** — would create a real visit + fire AI pipeline. |
| `/visits/[id]` | `src/app/visits/[id]/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-visit-page.mjs` | ✅ | **The flagship walker.** Refactored in v3.1 to use `deepWalk()` + storageState reuse + `--scenario` flag (4 fixture variants). |
| `/visits/[id]/record` | `src/app/visits/[id]/record/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-visit-record.mjs` | 🟡 | Live MediaRecorder dictation interface. Skipped today (needs draft-mode visit + getUserMedia mock). |
| `/patients` | `src/app/patients/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-patients-list.mjs` | 🟡 | Practice patient list, searchable. |
| `/patients/[id]` | `src/app/patients/[id]/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-patient-detail.mjs` | ✅ | Patient detail with Visits / Notes / Files / Trash tabs. Deep walker (v3.2) — tab-stateful clicks + dialog triggers + read-scoping check on `transcribe_md_patients`. Trash tab walked only when DOM-present. |
| `/settings` | `src/app/settings/page.tsx` | DOCTOR / STAFF / ADMIN | `sweep-settings.mjs` | ✅ | Profile / security / sessions / data / billing / danger zone. **Most delicate walker:** 8 destructive buttons (delete account, sign-out-all, password change, MFA toggle, Stripe portal, data export, send-confirmation, sign-out) explicitly enumerated-but-not-clicked via the `FORBIDDEN_BUTTONS` safety net. |
| `/dev/rx-warnings` | `src/app/dev/rx-warnings/page.tsx` | DOCTOR (dev-build only) | `sweep-dev-rx-warnings.mjs` | 🟡 | Rx-warning card variant preview. 404s in production. |

### Authenticated routes (require SUPER_ADMIN + ≤12h session)

| URL | File | Walker | Status | Description |
|---|---|---|---|---|
| `/admin` | `src/app/admin/page.tsx` | `sweep-admin-dashboard.mjs` | 🟡 | Platform-admin dashboard — health / activity / threats / pipeline / HIPAA. |
| `/admin/users` | `src/app/admin/users/page.tsx` | `sweep-admin-users.mjs` | 🟡 | User management — filter by product / role / status; export. |
| `/admin/usage` | `src/app/admin/usage/page.tsx` | `sweep-admin-usage.mjs` | 🟡 | API usage analytics — billing-adjacent. |
| `/admin/hipaa` | `src/app/admin/hipaa/page.tsx` | `sweep-admin-hipaa.mjs` | 🟡 | HIPAA compliance dashboard. |
| `/admin/threats` | `src/app/admin/threats/page.tsx` | `sweep-admin-threats.mjs` | 🟡 | Security threats / anomalies log. |

### Public routes (no auth)

| URL | File | Walker | Status | Description |
|---|---|---|---|---|
| `/` | `src/app/page.tsx` | _(redirect-only)_ | n/a | Server redirect → `/dashboard` or `/login`. No render. Agent sees the redirect chain via `sweep-login.mjs`. |
| `/login` | `src/app/login/page.tsx` | `sweep-login.mjs` | 🟡 | Sign-in form. The agent's own happy-path entry point. |
| `/signup` | `src/app/signup/page.tsx` | `sweep-signup.mjs` | 🟡 | Self-service signup (free 14-day trial). |
| `/forgot-password` | `src/app/forgot-password/page.tsx` | `sweep-forgot-password.mjs` | 🟡 | Email-based recovery request form. |
| `/reset-password` | `src/app/reset-password/page.tsx` | `sweep-reset-password.mjs` | 🟡 | Token-based new-password form (`?token=...`). |
| `/check-email` | `src/app/check-email/page.tsx` | `sweep-check-email.mjs` | 🟡 | Verification confirmation page after signup. |

## Marketing site — `apps/marketing` (`quillmd.com`)

All routes are public; same `NavBar` + `Footer` chrome on every page.

| URL | File | Walker | Status | Description |
|---|---|---|---|---|
| `/` | `src/app/page.tsx` | `sweep-marketing-home.mjs` | 🟡 | Landing — hero / features / pricing teaser / FAQ. |
| `/about` | `src/app/about/page.tsx` | `sweep-marketing-about.mjs` | 🟡 | Company story. |
| `/pricing` | `src/app/pricing/page.tsx` | `sweep-marketing-pricing.mjs` | 🟡 | Pricing tiers + FAQ. |
| `/demo` | `src/app/demo/page.tsx` | `sweep-marketing-demo.mjs` | 🟡 | "Coming soon" placeholder. |
| `/signup` | `src/app/signup/page.tsx` | `sweep-marketing-signup.mjs` | 🟡 | Meta-refresh redirect to `app.quillmd.com/signup`. |
| `/security` | `src/app/security/page.tsx` | `sweep-marketing-security.mjs` | 🟡 | Security posture. |
| `/hipaa` | `src/app/hipaa/page.tsx` | `sweep-marketing-hipaa.mjs` | 🟡 | HIPAA compliance overview ([DRAFT] header — pending legal). |
| `/privacy` | `src/app/privacy/page.tsx` | `sweep-marketing-privacy.mjs` | 🟡 | Privacy policy. |
| `/contact` | `src/app/contact/page.tsx` | `sweep-marketing-contact.mjs` | 🟡 | Contact form (support / sales / compliance / security). |
| `/terms` | `src/app/terms/page.tsx` | `sweep-marketing-terms.mjs` | 🟡 | Terms of service. |

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

The remaining 🟡 routes (admin / public / marketing) stay 🟡
indefinitely. Marketing has no DB writes; admin pages 404 for
DOCTOR-role test user (the gate check IS the deep walk); public
pages can't safely submit forms in QA (would create stale users /
fire real emails). `/visits/[id]/record` stays 🟡 pending a
getUserMedia mock and a draft-mode fixture.

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

The minimum bar is the 🟡 status. ✅ comes when someone wires real
element clicks + DB diffs into the walker. Empty status (route in code,
no walker) is a regression and the next agent run flags it.
