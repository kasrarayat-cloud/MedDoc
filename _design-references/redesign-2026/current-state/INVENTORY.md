# QuillMD — Current-State Visual Record (Redesign Phase 0)

*Generated 2026-07-24T02:02:00.032Z · 136 screenshots (68 screens × up to 2 viewports) · 0 render failures*

This is the **master redesign checklist**: one row per screen/state captured before the ground-up visual redesign. Each PNG is named `{area}--{route}--{state}--{viewport}.png` (viewports: `desktop` = 1440×900, `mobile` = 390×844).

## How this was captured

- **Target:** the isolated QA stack (compose project `meddoc-qa`, app at `http://localhost:9020`), image `meddoc-pro-transcribe-md:latest` with **`NEXT_PUBLIC_SKIN_BETA=true`** (C3 "calm" skin — matches production) and **`NEXT_PUBLIC_ULTRASOUND_SPECIALTY=true`** baked in. Prod was never touched (prod DB is empty by design).
- **Marketing** (`quillmd.com`) captured from the live production marketing site — those pages are static/non-PHI, so production *is* the current state.
- **Data:** clearly-synthetic, non-PHI demo seed — 17 patients, 39 visits spanning every status (READY / SIGNED / needs-review / DRAFTING / TRANSCRIBING / FAILED / QUEUED), plus purpose-built visits for the ultrasound report, a critical-Rx sign-block, a pending-E/M confirm, and the anchored-suggestion lane. Seeded owner: `qa-auditor@quillmd.test` (DOCTOR).
- **Admin** captured as a seeded `qa-admin@quillmd.test` (SUPER_ADMIN product). The `/admin/*` gate requires `mfaEnabled=true` + a fresh ≤12h session; both `products` and `mfaEnabled` are read fresh from the DB, so the sweep logs in with MFA off (no TOTP prompt), then flips `mfaEnabled=true` before navigating — all six admin dashboards render populated.

## Coverage summary

| Area | Screens | PNGs |
|---|---|---|
| Authentication & public (app.quillmd.com, unauthenticated) | 5 | 10 |
| Dashboard / clinician inbox | 3 | 6 |
| Patients (list + detail) | 3 | 6 |
| Visits list + filters | 5 | 10 |
| Capture flow (new visit, dictation, processing, failed, queued placeholders) | 9 | 18 |
| SOAP review V2 (visit detail — tabs & states) | 9 | 18 |
| E/M (billing) drawer & at-sign confirm | 2 | 4 |
| Rx interaction warnings & critical-override modal | 3 | 6 |
| Anchored-suggestion review lane | 1 | 2 |
| Ultrasound / venous-duplex imaging report | 3 | 6 |
| Audit view (doctor-facing) | 1 | 2 |
| My Note Format — templates list & detail (WM_IOV) | 2 | 4 |
| Settings (profile / security / sessions / billing / danger / MFA) | 6 | 12 |
| Platform admin (SUPER_ADMIN) | 6 | 12 |
| Marketing site (quillmd.com — prod, static) | 10 | 20 |
| **Total** | **68** | **136** |

## Screen inventory

### Authentication & public (app.quillmd.com, unauthenticated)

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `auth--login--default` | `http://localhost:9020/login` | Sign-in form | email/password/submit + links | mobile+desktop |
| `auth--signup--default` | `http://localhost:9020/signup` | Self-service signup (14-day trial) | name/email/password/confirm/terms | mobile+desktop |
| `auth--forgot-password--default` | `http://localhost:9020/forgot-password` | Password recovery request | email + submit | mobile+desktop |
| `auth--reset-password--token` | `http://localhost:9020/reset-password?token=qa_smoke_invalid_token` | Token-based new-password form | password/confirm | mobile+desktop |
| `auth--check-email--default` | `http://localhost:9020/check-email` | Post-signup verification prompt | resend + back-to-login | mobile+desktop |

### Dashboard / clinician inbox

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `dashboard--dashboard--default` | `/dashboard` | Clinician landing — C3 "ready to sign" inbox, grouped by recency | DashboardInboxC3, grouped sections, search, pager | mobile+desktop |
| `dashboard--dashboard--search-active` | `/dashboard` | Inbox server-side search | search input + filtered rows | mobile+desktop |
| `dashboard--dashboard--page2` | `/dashboard` | Inbox pagination (page 2) | pager | mobile+desktop |

### Patients (list + detail)

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `patients--patients--default` | `/patients` | Practice patient list (C3 server-search) | PatientsListC3 rows, footer count, load-more | mobile+desktop |
| `patients--patients--search-active` | `/patients` | Patient search | search input + narrowed rows | mobile+desktop |
| `patients--patient-detail--default` | `/patients/cmrya5nwv00010tmhwt2wp46a` | Patient detail (C3 inline: visits + deleted sections) | visits section, trash section, actions | mobile+desktop |

### Visits list + filters

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `visits--visits--all` | `/visits` | All-visits list | FilterBar (5 pills), VisitList rows | mobile+desktop |
| `visits--visits--ready` | `/visits?filter=ready` | Ready filter | filter pill active | mobile+desktop |
| `visits--visits--review` | `/visits?filter=review` | Needs-review filter | filter pill active | mobile+desktop |
| `visits--visits--signed` | `/visits?filter=signed` | Signed filter | filter pill active | mobile+desktop |
| `visits--visits--processing` | `/visits?filter=processing` | Processing filter | filter pill active | mobile+desktop |

### Capture flow (new visit, dictation, processing, failed, queued placeholders)

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `capture--visits-new--stage1` | `/visits/new` | New visit — patient picker (stage 1) | PatientPicker search + create toggle | mobile+desktop |
| `capture--visits-new--stage2` | `/visits/new?patientId=cmrya5nwv00010tmhwt2wp46a` | New visit — specialty + capture-mode tiles (stage 2) | VisitFormStep2, specialty dropdown, mode tiles | mobile+desktop |
| `capture--visits-new--specialty-open` | `/visits/new?patientId=cmrya5nwv00010tmhwt2wp46a` | Specialty dropdown open | Radix Select popper | mobile+desktop |
| `capture--visit-record--live` | `/visits/qa_shot_record/record` | Live dictation / recording interface | recording client, mic controls | mobile+desktop |
| `capture--visit--queued-voice` | `/visits/qa_shot_record` | Queued voice-dictation placeholder | VoiceDictator | mobile+desktop |
| `capture--visit--queued-text` | `/visits/qa_shot_textqueued` | Queued text-to-SOAP composer | TextComposer | mobile+desktop |
| `capture--visit--queued-audio` | `/visits/qa_shot_audioqueued` | Queued audio-upload placeholder | AudioUploader | mobile+desktop |
| `capture--visit--processing` | `/visits/qa_shot_processing_01` | Pipeline processing animation | ProcessingTypewriter | mobile+desktop |
| `capture--visit--failed` | `/visits/qa_shot_failed` | Failed visit | VisitFailedView + retry | mobile+desktop |

### SOAP review V2 (visit detail — tabs & states)

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `visit--review--note` | `/visits/qa_shot_bump` | SOAP review V2 — Note tab (S/O/A/P cards) + readiness meter + sign bar | ReviewTabsV2, SoapBody section cards | mobile+desktop |
| `visit--review--rx` | `/visits/qa_shot_bump` | Review — Rx tab | RxTab, prescription list + rail | mobile+desktop |
| `visit--review--billing` | `/visits/qa_shot_bump` | Review — Billing / E/M drawer | BillingCardC3 | mobile+desktop |
| `visit--review--billing-why` | `/visits/qa_shot_bump` | E/M rubric expanded (Why this level) | EmTimeTracker, EmCheckList, bump line | mobile+desktop |
| `visit--review--codes` | `/visits/qa_shot_bump` | Review — Codes tab (ICD/CPT) | CodesTab | mobile+desktop |
| `visit--review--extras` | `/visits/qa_shot_bump` | Review — Extras tab (demographics, vitals, audit log) | ExtrasTab, AuditLogCard | mobile+desktop |
| `visit--review--transcript` | `/visits/qa_shot_bump` | Review — Transcript/Input tab | TranscriptTab | mobile+desktop |
| `visit--review--signed` | `/visits/qa_shot_signed_01` | Signed visit — readonly Note (Note · signed, SignedStateCard, Export again) | SignedStateCard | mobile+desktop |
| `visit--review--nonclinical` | `/visits/qa_shot_nonclinical` | Set-aside / non-clinical note (placeholder sections) | placeholder section body | mobile+desktop |

### E/M (billing) drawer & at-sign confirm

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `em--billing--pending` | `/visits/qa_shot_rx_em` | E/M drawer with pending level-change notice | BillingCardC3 pending notice | mobile+desktop |
| `em--sign-confirm-chip` | `/visits/qa_shot_rx_em` | At-sign E/M confirm toggle inside Sign & Send | SignAndSendModal em-change-confirm | mobile+desktop |

### Rx interaction warnings & critical-override modal

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `rx--rail--critical` | `/visits/qa_shot_critrx` | RxWarningsRail with a critical interaction (sign-blocked) | RxTab, qm-warn-critical, override affordance | mobile+desktop |
| `rx--override-modal` | `/visits/qa_shot_critrx` | Critical-Rx typed-override confirm modal | OverrideConfirmModal, #override-reason | mobile+desktop |
| `rx--override-modal-ready` | `/visits/qa_shot_critrx` | Override modal with reason filled (confirm enabled) | OverrideConfirmModal enabled | mobile+desktop |

### Anchored-suggestion review lane

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `suggestions--review-lane` | `/visits/qa_shot_suggestions` | Anchored-suggestion review lane | SuggestionsLane, suggestion items (Adopt/Dismiss) | mobile+desktop |

### Ultrasound / venous-duplex imaging report

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `ultrasound--report--note` | `/visits/qa_shot_ultrasound` | Ultrasound venous-duplex imaging report (Exam/Indication/Technique/Comparison/Findings/Impression + vein tables) | VisitReadyView generic sections, markdown tables | mobile+desktop |
| `ultrasound--report--billing-na` | `/visits/qa_shot_ultrasound` | Imaging report — E/M not applicable | BillingCardC3 not-applicable | mobile+desktop |
| `ultrasound--report--signed` | `/visits/qa_shot_ultrasound_signed` | Signed imaging report (readonly) | SignedStateCard | mobile+desktop |

### Audit view (doctor-facing)

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `audit--extras-audit-log` | `/visits/qa_shot_signed_01` | Doctor-facing audit log (Extras tab, signed visit) | AuditLogCard event rows | mobile+desktop |

### My Note Format — templates list & detail (WM_IOV)

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `templates--list` | `/settings` | My Note Format — templates list (WM_IOV + follow-up + standard fallback) | NoteFormatManager home, TemplateRow | mobile+desktop |
| `templates--wm-iov-detail` | `/settings` | WM_IOV template detail / review editor (structured sections) | TemplateReviewEditor, SectionCard, SamplePreview | mobile+desktop |

### Settings (profile / security / sessions / billing / danger / MFA)

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `settings--profile` | `/settings` | Settings — Profile panel | SettingsSectionsC3, ProfileForm | mobile+desktop |
| `settings--security` | `/settings` | Settings — Security (password + 2FA box) | ChangePasswordForm | mobile+desktop |
| `settings--sessions` | `/settings` | Settings — Active session | SessionPanel | mobile+desktop |
| `settings--billing` | `/settings` | Settings — Billing | billing panel | mobile+desktop |
| `settings--danger` | `/settings` | Settings — Danger zone | DeleteAccountDialog trigger | mobile+desktop |
| `settings--mfa-enroll` | `/settings/security/mfa` | Two-factor authentication enrollment (step 1) | MfaEnrollmentPanel | mobile+desktop |

### Platform admin (SUPER_ADMIN)

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `admin--overview` | `/admin` | Platform admin overview (health/threats/activity/pipeline/HIPAA) | StatusCards, ActivityFeed, PipelineMetricsCard, TimelineChart | mobile+desktop |
| `admin--users` | `/admin/users` | User management | filters, users table, pagination | mobile+desktop |
| `admin--usage` | `/admin/usage` | API usage analytics | WindowSelector, TopStatBar, TimelineChart, ProviderBreakdown | mobile+desktop |
| `admin--hipaa` | `/admin/hipaa` | HIPAA findings | tabs, findings list | mobile+desktop |
| `admin--threats` | `/admin/threats` | Security threats | tabs, active/resolved lists | mobile+desktop |
| `admin--queues` | `/admin/queues` | BullMQ queue health | queues table, DLQ table | mobile+desktop |

### Marketing site (quillmd.com — prod, static)

| Screen / state | Route | Purpose | Key components | Viewports |
|---|---|---|---|---|
| `marketing--home` | `(mktg) /` | Marketing / | NavBar + Footer + page content | mobile+desktop |
| `marketing--about` | `(mktg) /about` | Marketing /about | NavBar + Footer + page content | mobile+desktop |
| `marketing--pricing` | `(mktg) /pricing` | Marketing /pricing | NavBar + Footer + page content | mobile+desktop |
| `marketing--demo` | `(mktg) /demo` | Marketing /demo | NavBar + Footer + page content | mobile+desktop |
| `marketing--security` | `(mktg) /security` | Marketing /security | NavBar + Footer + page content | mobile+desktop |
| `marketing--hipaa` | `(mktg) /hipaa` | Marketing /hipaa | NavBar + Footer + page content | mobile+desktop |
| `marketing--privacy` | `(mktg) /privacy` | Marketing /privacy | NavBar + Footer + page content | mobile+desktop |
| `marketing--contact` | `(mktg) /contact` | Marketing /contact | NavBar + Footer + page content | mobile+desktop |
| `marketing--terms` | `(mktg) /terms` | Marketing /terms | NavBar + Footer + page content | mobile+desktop |
| `marketing--signup-redirect` | `(mktg) /signup` | Marketing /signup | NavBar + Footer + page content | mobile+desktop |

## Site-map route coverage (cross-check vs `qa-interaction-auditor/skills/site-map.md`)

Every authoritative site-map route is either captured (with the screens that cover it) or explicitly skipped with a reason.

| Site-map route | Status | Covered by |
|---|---|---|
| `/dashboard (app)` | ✅ | dashboard--dashboard--{default,search-active,page2} |
| `/visits` | ✅ | visits--visits--{all,ready,review,signed,processing} |
| `/visits/new` | ✅ | capture--visits-new--{stage1,stage2,specialty-open} |
| `/visits/[id]` | ✅ | visit--review--{note,rx,billing,billing-why,codes,extras,transcript,signed,nonclinical}; em--*; rx--*; suggestions--review-lane; ultrasound--report--*; audit--extras-audit-log; capture--visit--{queued-voice,queued-text,queued-audio,processing,failed} |
| `/visits/[id]/record` | ✅ | capture--visit-record--live |
| `/patients` | ✅ | patients--patients--{default,search-active} |
| `/patients/[id]` | ✅ | patients--patient-detail--default |
| `/settings` | ✅ | settings--{profile,security,sessions,billing,danger}; templates--{list,wm-iov-detail} |
| `/dev/rx-warnings` | ⏭️ SKIP | Dev-build-only preview route; returns production `notFound()` (404) in the QA `NODE_ENV=production` image. Not a product surface for the redesign. |
| `/admin` | ✅ | admin--overview |
| `/admin/users` | ✅ | admin--users |
| `/admin/usage` | ✅ | admin--usage |
| `/admin/hipaa` | ✅ | admin--hipaa |
| `/admin/threats` | ✅ | admin--threats |
| `/admin/queues` | ✅ | admin--queues |
| `/ (app root)` | ⏭️ SKIP | Server redirect only (→ /dashboard or /login); no render. Both redirect targets are captured. |
| `/login` | ✅ | auth--login--default |
| `/signup (app)` | ✅ | auth--signup--default |
| `/forgot-password` | ✅ | auth--forgot-password--default |
| `/reset-password` | ✅ | auth--reset-password--token |
| `/check-email` | ✅ | auth--check-email--default |
| `/ (marketing)` | ✅ | marketing--home |
| `/about (marketing)` | ✅ | marketing--about |
| `/pricing (marketing)` | ✅ | marketing--pricing |
| `/demo (marketing)` | ✅ | marketing--demo |
| `/signup (marketing)` | ✅ | marketing--signup-redirect |
| `/security (marketing)` | ✅ | marketing--security |
| `/hipaa (marketing)` | ✅ | marketing--hipaa |
| `/privacy (marketing)` | ✅ | marketing--privacy |
| `/contact (marketing)` | ✅ | marketing--contact |
| `/terms (marketing)` | ✅ | marketing--terms |

### Route found in code but NOT in site-map.md (flagged)

- **`/settings/security/mfa`** — the two-factor-authentication enrollment/management page. It exists in `src/app/settings/security/mfa/page.tsx` but is **absent from the authoritative site-map**, and nothing in the doctor UI links to it (the Settings→Security 2FA box is static "coming soon" copy). Captured here as `settings--mfa-enroll` (enrollment step 1). **Recommend adding it to site-map.md.**

## Notes for the redesign

- **Skin:** all app screens are the production **C3 "calm" skin** (dark `#08090a`, sage `#7AA68C`, Inter + JetBrains Mono). The legacy Linear-V1 layouts (flag OFF) were NOT captured — they are not what ships.
- **SOAP review = workflow tabs, not S/O/A/P letters.** The `/visits/[id]` V2 shell (`ReviewTabsV2`) tabs are `Note · Review · Rx · Billing · Codes · Extras · Transcript`; the S/O/A/P split is *inside* the Note tab as stacked section cards.
- **Ultrasound reports reuse the same review shell** — no dedicated imaging component; sections are driven by the note headings (Exam/Indication/Technique/Comparison/Findings/Impression) and E/M is suppressed (Billing shows "not applicable").
- **Empty-state screens are real, not errors:** admin Threats/HIPAA/Usage show sage empty-states because the QA stack has no threat/usage history; that is the honest current state of those surfaces with no data.
- `_manifest.json` in this folder is the machine-readable index (per-viewport file, final URL, purpose, components).
