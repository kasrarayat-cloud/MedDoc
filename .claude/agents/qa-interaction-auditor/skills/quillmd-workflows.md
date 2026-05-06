# QuillMD workflows + interactive-element inventory

The agent walks workflows, not pages. A workflow is a sequence of
clicks the doctor takes from start (signed-in dashboard) to a
terminal state (signed visit, sent to EHR). Each workflow names
every interactive element with its `file:line` so the agent can
locate it programmatically.

This file is current as of commit `42357d6` (PR #132). When the
codebase moves, the agent re-discovers; this file is a starting
map, not an authoritative cache.

---

## Primary workflow — Sign & send a visit

This is the workflow Kasra exercised in his smoke tests this week.
It's the single most important path to keep healthy because every
real visit goes through it.

### Step 1 — Dashboard / visits list

URL: `/visits`
File: `apps/transcribe-md/src/app/visits/page.tsx`

Interactive elements:
- `<Link>` to `/visits/new` — "New visit" button
- Each row in the visits table is `<Link href="/visits/{id}">`
- Filter dropdown (status: all / draft / signed)

### Step 2 — Create visit

URL: `/visits/new`
File: `apps/transcribe-md/src/app/visits/new/page.tsx` and
`apps/transcribe-md/src/app/visits/new/step-2/page.tsx`

Interactive elements:
- Patient picker (`<input>` with `/api/patients/fuzzy-match` POST)
- Specialty dropdown
- Input mode picker (audio_upload / voice_dictation / text_notes)
- "Continue" → POST `/visits/new` server action

DB writes on submit:
- `transcribe_md_patients` row (if new patient)
- `transcribe_visits` row (status: QUEUED)

Audit row expected: none for visit creation (current state — could
be a Pattern flag if a `VISIT_CREATED` action is added later).

### Step 3 — Upload audio

URL: `/visits/{id}` (after creation, before pipeline runs)
File: `apps/transcribe-md/src/app/visits/[id]/page.tsx` (server)
+ `apps/transcribe-md/src/app/visits/[id]/audio-uploader.tsx`
(client)

Interactive elements:
- File input → `POST /api/visits/{id}/upload` (audio_upload mode)
- Microphone record button → `POST /api/visits/{id}/dictation/upload`
  (voice_dictation mode)
- Text textarea → `POST /api/visits/{id}/text` (text_notes mode)

DB writes on upload:
- `transcribe_visits.audioKey` set
- `transcribe_visits.audioMimeType` set
- `transcribe_visits.audioSizeBytes` set
- BullMQ `transcribe-md` queue gets a `process-visit` job

Audit row expected: `AUDIO_UPLOADED` (Phase 17 §164.312(b)).

### Step 4 — Pipeline runs (worker side; no doctor interaction)

The doctor sees a "Processing" view with a status pill that
progresses: QUEUED → TRANSCRIBING → EXTRACTING → DRAFTING →
CRITIQUING → POLISHING → AUTOMATING → READY.

File: `apps/transcribe-md/src/app/visits/[id]/processing-state.tsx`

This polls `GET /api/visits/{id}/status`. **Pattern A risk:** the
pill text is hand-typed; if a new `TranscribeVisitStatus` enum value
is added without updating the pill component, the doctor sees
"Unknown" or the pill goes blank. The agent's content-rendering
sanity pass should walk every status enum value once.

### Step 5 — View visit (the page where most bugs live)

URL: `/visits/{id}` after `status = READY`
File: `apps/transcribe-md/src/app/visits/[id]/page.tsx` →
`apps/transcribe-md/src/app/visits/[id]/visit-ready-view.tsx` →
multiple sub-components.

Tabs / sub-views:
- `soap-editor.tsx` (default — the SOAP body + Coding Rail)
- `transcript-tab.tsx` (Deepgram transcript view)
- `codes-tab.tsx` (ICD + CPT codes)
- `rx-tab.tsx` (Rx drafts + warnings)
- `extras-tab.tsx` (referrals + patient summary)

Interactive elements in `soap-editor.tsx`:
- SOAP section bodies — each is editable inline via
  `soap/SoapInlineEdit.tsx` → debounced
  `saveSoapDraftAction(visitId, text)` server action
- Coding Rail (`components/visits/CodingRail.tsx`):
  - Override dropdown (manual code override)
  - Bump CTA → opens BumpModal → `onApplyAdditions` →
    `POST /api/visits/{id}/em-score/apply-additions`
  - Confirm-sign button → `onConfirmSign` → opens
    `SignAndSendModal` (controlled-open mode)
- Bottom action bar:
  - `<SignAndSendModal triggerLabel="Sign & Send">` →
    `POST /api/visits/{id}/sign`
  - On signed visits, switches to `<SignAndSendModal
    triggerLabel="Export again">` (no sign; just re-export)

Interactive elements in `rx-tab.tsx`:
- Each Rx warning row has an "Override" button →
  `recordOverride()` server action → writes
  `rx_warning_overrides` row
- Critical warnings BLOCK signing until overridden (PR-E)

Interactive elements in `codes-tab.tsx`:
- ICD codes: each has a dismiss/accept icon
- CPT E&M code: clickable for evidence popover
- Modifier add button

DB writes throughout step 5:
- `transcribe_visits.soapDraft` / `soapFinal` (inline edits)
- `rx_warning_overrides` (override clicks)
- `transcribe_visits.cptCodes` (apply-additions endpoint)

Audit rows expected:
- `EDITED_NOTE` on every save
- `RX_OVERRIDE_RECORDED` on critical-warning override
- `EM_BUMP_APPLIED` on apply-additions success (per PR #132)

### Step 6 — Sign

The SignAndSendModal flow:
- Doctor picks destinations (clipboard / PDF / DOCX / email)
- Clicks "Sign & Deliver"
- `POST /api/visits/{id}/sign` runs:
  - Sets `transcribe_visits.signedAt`
  - Sets `transcribe_visits.status = SIGNED`
  - Generates clipboard text + PDF/DOCX URLs
  - Optionally queues email via Resend
- Browser-side: modal closes, `router.refresh()`, downloads fire,
  toast surfaces

DB writes:
- `transcribe_visits` row updated (signedAt, status, processingFinishedAt)
- `audit_logs` row: `VISIT_SIGNED`

Audit rows expected: `VISIT_SIGNED` (Phase 1A H2).

---

## Element inventory — verbatim file:line cites (commit 42357d6)

The agent uses these as anchor points. When the codebase moves,
re-discover via grep; don't trust this list blindly.

### CodingRail (the rail with the most-touched bugs)

`apps/transcribe-md/src/components/visits/CodingRail.tsx`

| Line | Element | Wires to |
|---|---|---|
| 226 | `dispatchEvent(EM_OVERRIDE_EVENT)` | **NO LISTENER** (active orphan) |
| 365 | `<EmCheckList>` row click | `qm:soap-jump` event (orphan?) |
| 396 | `<BumpCtaButton onClick={handleBumpClick}>` | opens `<BumpModal>` |
| 408 | "Confirm {code} · sign" button | `onConfirmSign` prop (was orphan in v1) |
| 432 | `<BumpModal onApply={handleApplyAdditions}>` | `onApplyAdditions` prop |

### SignAndSendModal

`apps/transcribe-md/src/app/visits/[id]/sign-and-send-modal.tsx`

| Line | Element | Wires to |
|---|---|---|
| 215 | `<Dialog.Trigger>` button | toggles internal or controlled open |
| 333 | "Sign & Deliver" button | `submit()` → `fetchSignAndDeliver()` |

### BumpModal

`apps/transcribe-md/src/components/visits/BumpModal.tsx`

| Line | Element | Wires to |
|---|---|---|
| 199 | `<textarea>` (per-gap suggestion) | `setAdditions` local state |
| 261 | "Next" button | `setStep((s) => s+1)` |
| 269 | "Apply & save · recheck" button | `handleApply` → parent `onApply` |

### Rx warning card

`apps/transcribe-md/src/components/rx/rx-warning-card.tsx`

| Element | Wires to |
|---|---|
| Override button | `recordOverride()` server action |
| Dismiss button | local state (no DB write — by design for non-critical) |

---

## Audit-action enum values — what the agent expects to see

Every workflow step that mutates state should produce an audit
row. These are the values that should appear in `audit_logs.action`
during a healthy workflow walk:

- `LOGIN_SUCCESS` (after authenticated session start)
- `AUDIO_UPLOADED` (audio submission)
- `EDITED_NOTE` (SOAP inline edit)
- `RX_OVERRIDE_RECORDED` (critical warning override)
- `EM_BUMP_APPLIED` (bump-additions accept — added in PR #132)
- `VISIT_SIGNED` (sign action)
- `VIEWED_VISIT` / `VIEWED_VISIT_AUDIO` (PHI-read audit)
- `EXPORT_PDF_DOWNLOADED` / `EXPORT_DOCX_DOWNLOADED` /
  `EXPORT_CLIPBOARD_COPIED` / `EXPORT_EMAIL_SENT`

If the workflow walk completes a step that should have written
one of these and `audit_logs` shows nothing, that's a finding —
either the audit hook is missing or the step actually didn't
execute (Pattern A or B class).

---

## Marketing site workflows (out of doctor scope but in agent scope)

### Public landing → signup

URL: `/` → `/signup`
Files: `apps/marketing/src/app/page.tsx` →
`apps/marketing/src/app/signup/page.tsx`

Interactive elements:
- Hero CTA → `/signup`
- Pricing tier "Get started" → `/signup`
- Signup form → POST to authentication API

These are simpler workflows. Most marketing pages are static; the
agent should sweep them for orphan dispatchers + stub comments
but doesn't need DB diffs (no DB writes on marketing pages).

---

## Per-page workflow stubs (v2 baseline)

These are short workflow entries for every page beyond the flagship
sign-and-send sequence. Each page has a 🟡 walker today
(`scripts/sweep-<name>.mjs`) and a deeper element-by-element walk in
its future. The minimum each entry captures: doctor's intent on the
page, the load-state DB tables, and the audit-action values we
expect to see.

### Dashboard — `/dashboard`

File: `apps/transcribe-md/src/app/dashboard/page.tsx`. Linear V1
landing surface; `?tab=patients` (default) ↔ `?tab=all`.

- **Doctor's intent:** triage — see what's pending review; jump
  into a visit; create a new one.
- **In-page clickables (deep-walked):**
  - TabBar Patients ↔ All visits — `Link` with `scroll={false}`,
    URL changes via `?tab=`. Pure server re-render; no DB write.
  - Top-bar brand "QuillMD" — Link to `/dashboard` (same-page).
  - Cmd-K palette `<button>` — synthesises `Meta+K` keydown to
    toggle the global `<CommandPalette>`. In-page DOM mutation
    only.
  - Avatar dropdown `<button>` — Radix dropdown trigger; opens a
    portal with Settings + Sign-out items.
- **Enumerated, not clicked (outbound):**
  - PatientList rows → `/patients/[id]`
  - VisitList / DraftsReady rows → `/visits/[id]`
  - Sidebar nav (Visits / Patients / Settings) and "+ New visit"
  - Avatar-dropdown Settings + Sign-out items
- **DB tables snapshotted (read-scoping check):**
  `transcribe_visits`, `transcribe_md_patients`. Either changing
  on a view-only click is a finding.
- **Audit rows expected on load:** `VIEWED_PATIENT_LIST` +
  `VIEWED_VISIT_LIST` (Round 3 PR-C compliance).
- **Audit rows expected per click:** none. Tab toggle, palette
  open, dropdown open are pure UI — `auditDelta` should be 0.
- **Walker tier:** ✅ v3.2 deep walker (`sweep-dashboard.mjs`).
  Auth via shared `getOrCreateAuthState`; mid-walk /login retry;
  per-click classification via `clickAndClassify()`.

### Visits list — `/visits`

File: `apps/transcribe-md/src/app/visits/page.tsx`. All-visits list
with URL-driven filter pills and a grouped `<VisitList>` table.

- **Filter pills:** all / ready / review / signed / processing — each
  is a `<Link href="/visits[?filter=...]">` with `scroll={false}`. The
  page is a Server Component, so each click triggers a Next.js RSC
  re-fetch (a GET) that swaps the rendered table for the new
  `?filter=` slice. **No DB write**: the filter is a `WHERE` clause
  in `prisma.transcribeVisit.findMany`, plus a `userId +
  deletedAt:null + archivedAt:null` base scope. Walker emits a
  per-pill `filter-pill` event with `{ urlBefore, urlAfter,
  urlChanged, dbChanged }` — any `dbChanged: true` is a hard finding.
- **Click classification:** because RSC re-fetches are GETs,
  `clickAndClassify` reports each pill as `VISUAL_ONLY` (DOM swap
  observed) or `NO_NETWORK_FIRED` (swap completes inside the settle
  window). Both are expected; only `PRETEND_SUCCESS_FALLBACK`,
  `CLICK_THREW`, `HTTP_5xx`, or any `dbChanged` count as findings.
- **Each row:** `<Link href="/visits/{id}">` — drives the visit
  detail walker. Walker enumerates rows (with `click-skipped`,
  reason='leaves-page') but never clicks them.
- **Audit rows expected:** one `VIEWED_VISIT_LIST` per RSC render
  (Round 3 PR-C, A05-P0-004). Walker captures the unscoped baseline
  count via `audit-baseline` and tracks per-click `auditDelta`.
- **Walker tier:** ✅ v3.2 deep walker (`sweep-visits-list.mjs`).

### New visit — `/visits/new`

File: `apps/transcribe-md/src/app/visits/new/page.tsx` (+
`new-visit-client.tsx`, `patient-picker.tsx`, `visit-form-step2.tsx`,
`mode-tile-with-form.tsx`, `duplicate-modal.tsx`).

- **Doctor's intent:** start a new visit by picking a patient + capture
  mode (audio_upload / voice_dictation / text_notes).
- **Two stages on a single URL** (driven by `selectedPatient` state in
  `new-visit-client.tsx`):
  1. **Stage 1 — PatientPicker.** Debounced search input → GET
     `/api/patients?search=`. "Create new patient" toggle expands an
     inline form (name + DOB + externalId). Submit → POST
     `/api/patients/fuzzy-match`; matches with score > 0.6 open the
     `DuplicateModal`, otherwise POST `/api/patients` directly.
  2. **Stage 2 — VisitFormStep2.** Patient pill (`Change patient`
     button resets to Stage 1 client-side, OR Link → `/visits/new` when
     opened with `?patientId=`). `<SpecialtyDropdown>` (Radix Select).
     Chief-complaint `<input>` (optional). Three `<ModeTileWithForm>`
     buttons — each is `<button type="submit" form="new-visit-form"
     name="inputMode" value="audio_upload|voice_dictation|text_notes">`
     and triggers `createVisitAction` directly.
- **DB writes on submit:** new `transcribe_visits` row (status QUEUED)
  + optionally a new `transcribe_md_patients` row.
- **Audit rows expected on submit:** `TM_PATIENT_CREATED` (only when
  patient created inline). No `VISIT_CREATED` action exists in the
  enum today — Pattern-A risk if added later without instrumentation.
- **Walker (`sweep-new-visit.mjs` ✅):** lands on Stage 2 via
  `?patientId=<seeded.patientId>` (`--stage 1` walks picker).
  Classifies submit-named buttons + outbound nav before clicking.
  Tile-submit / "Create & continue" / "+ New patient"-equivalents are
  enumerated but never clicked. dbSnapshotSpec watches
  `transcribe_visits ORDER BY "createdAt" DESC LIMIT 5` — any
  `dbChanged` mid-walk = finding.

### Visit record — `/visits/[id]/record`

File: `apps/transcribe-md/src/app/visits/[id]/record/page.tsx`.
Live MediaRecorder dictation interface for `voice_dictation` mode.

- **Interactive elements:** record / pause / stop buttons; live
  waveform (visual only); transcript-placeholder pane.
- **POST endpoint:** `/api/visits/[id]/dictation/upload`
  (multi-chunk).
- **Audit rows expected:** `AUDIO_UPLOADED` once final chunk
  lands.

### Patients list — `/patients`

File: `apps/transcribe-md/src/app/patients/page.tsx`. Practice
patient list, searchable via the command palette.

- **Each row:** `<Link href="/patients/{id}">`.
- **Audit rows expected on load:** `VIEWED_PATIENT_LIST`.

### Patient detail — `/patients/[id]`

File: `apps/transcribe-md/src/app/patients/[id]/page.tsx`. Tabs:
Visits (default) / Notes (stub) / Files (stub) / Trash (only
rendered when the patient has trashed visits — `trashCount === 0`
hides the tab; page.tsx :478).

- **Doctor's intent:** review one patient's visit history; trigger
  Edit / Delete / Problem-list management; jump into a visit; restore
  a trashed visit.
- **Top-level interactive elements** (deep-walked by
  `sweep-patient-detail.mjs` v3.2):
  - Breadcrumb back to `/patients` (outbound)
  - PatientHeaderCard:
    - `[Manage]` → ProblemListDialog (Radix; in-page DOM mutation)
    - `+ New visit` → `/visits/new?patientId=...` (outbound)
    - `Export` → `/api/patients/{id}/export` (outbound; downloads ZIP)
    - `[Edit]` → EditPatientDialog (Radix; in-page)
    - `[Delete patient]` → DeletePatientDialog (Radix; in-page)
  - TabBar — 4 `<Link>`s, `scroll={false}`. Each is server-rendered
    via `?tab=` query param.
  - Visits tab → `<VisitList>` row links (outbound to `/visits/{id}`)
  - Notes tab → `<StubTab title="Notes" body="A freeform clinical
    notepad … Coming soon">`. **Intentional empty-state copy — NOT
    a Pattern C bug.**
  - Files tab → `<StubTab title="Files" body="Patient-attached files
    … Not ported yet">`. Same intentional-stub status.
  - Trash tab → grid of `<TrashedVisitCard>` (Restore / Delete
    permanently buttons mutate `transcribe_visits`; **walker
    enumerates but never clicks** them).
- **DB tables read:** `transcribe_md_patients`, `transcribe_visits`
  (both practice + user scoped).
- **Audit rows expected on load:** `VIEWED_PATIENT_FILE` (Round 3
  PR-C, page.tsx :170). One row per RSC render — i.e. one on initial
  load + one per tab click.
- **DB writes expected from view-only clicks:** none. Walker fails
  if `transcribe_md_patients` row diffs across any tab/dialog-trigger
  click (read-scoping regression).

### Settings — `/settings`

File: `apps/transcribe-md/src/app/settings/page.tsx`. Single-page
form with 6 sticky-anchor sections: profile / security / sessions /
data / billing / danger-zone.

- **Walker tier:** v3.2 deep walker (`sweep-settings.mjs`). MOST
  DELICATE walker in the fleet — every section hosts at least one
  irreversible action against the QA test user.
- **Safe click surface:** 6 sticky-aside anchor links
  (`#profile` … `#danger`) + ProfileForm "Save profile" submit
  with the prefilled-unchanged FormData (no-op equality write).
- **Forbidden buttons** (enumerated but never clicked; each fires a
  `click-skipped reason='destructive-not-clicked'` event with a
  per-button `risk` tag):
  - "Delete my account" — `would-delete-qa-user`
  - "Sign out all devices" / "Revoke all" — `kills-agent-session`
  - "Sign out" (bare) — `kills-agent-session`
  - "Update password" — `rotates-qa-password`
  - "Enable/Disable 2FA / MFA" — `mfa-lockout`
  - "Manage billing" — `outbound-stripe` (currently disabled in
    the build, kept in the safety net for when it ships)
  - "Export my data" — `outbound-download`
  - "Send confirmation" (ChangeEmailDialog submit) — `fires-real-email`
- **DB snapshot scope:** `users` + `user_sessions` rows for the QA
  user. Anchor-link clicks must produce `dbChanged=false` AND
  `auditDelta=0`; either is upgraded to a `finding` event.
- **Audit rows expected on load:** none. There is no
  `VIEWED_SETTINGS` action in the AuditAction enum at the time of
  writing (see v3.2 finding); a clean read-only load is expected.
- **Pattern matching is case-insensitive** and runs against the
  combined text + aria-label so renames do not silently disarm the
  safety net.

### Admin routes — `/admin*` (5 routes)

Files: `apps/transcribe-md/src/app/admin/{page,users/page,usage/page,hipaa/page,threats/page}.tsx`.

- **Gate:** `admin/layout.tsx` requires SUPER_ADMIN role + ≤12-
  hour session freshness.
- **QA test user is DOCTOR** — every admin-route walker expects a
  404 / not-authorized response. A 200 here is a finding (the gate
  is broken).
- **Audit rows expected on access:** Round 3 PR-C admin-access
  audit row (`ADMIN_DASHBOARD_ACCESS` etc) ONLY fires when the
  gate passes — i.e. never for the QA test user.

### Public app routes — `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/check-email`

Files under `apps/transcribe-md/src/app/<route>/page.tsx`.

- **Walker constraint:** never SUBMITS the signup or
  forgot-password forms — would create stale users / fire real
  emails.
- **Login** is the agent's own happy path; every authenticated
  walker exercises it via `lib/walker-base.mjs login()`.

### Marketing site — 10 routes under `apps/marketing/src/app`

All public, all share `NavBar` + `Footer` chrome. No DB writes on
any of them; the walker just confirms page-load + element-count.
The contact form is exempt from any submit attempt — would page
support / sales.

---

## Adding a new workflow

When a new feature ships, append a workflow section here with:
- URL + entry file
- Each interactive element (file:line, prop wiring)
- DB writes expected
- Audit-action enum values expected

The agent's first run on the new feature reads this file and
auto-generates the walk plan. If the section is missing, the agent
falls back to enumerating elements from the page DOM at runtime
(less precise; verbatim cites from this file are better).

When you add a new route, also:
1. Add a row to `skills/site-map.md` so the inventory stays
   current (orphan routes are surfaces no one is auditing).
2. Add a stub walker `scripts/sweep-<name>.mjs` (mirror an
   existing one).
3. Add the walker name to `scripts/sweep-all.mjs`'s WALKERS
   registry.
