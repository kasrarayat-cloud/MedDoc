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
landing surface; two tabs (Patients + All Visits) inside a
`<Tabs>` shell. Sidebar nav comes from `AppFrame` layout.

- **Doctor's intent:** triage — see what's pending review; jump
  into a visit; create a new one.
- **Top-level interactive elements (v2 walker stubs the click set;
  future depth):**
  - `<Tabs>` switcher between Patients + All Visits
  - "+ New visit" button → `/visits/new`
  - Each row in either tab → patient detail or visit detail
  - Search palette trigger (Cmd-K) — opens the global palette
- **DB tables read:** `transcribe_visits`, `transcribe_md_patients`
  (both scoped to the user's practice).
- **Audit rows expected on load:** `VIEWED_PATIENT_LIST`
  + `VIEWED_VISIT_LIST` (Round 3 PR-C compliance).

### Visits list — `/visits`

File: `apps/transcribe-md/src/app/visits/page.tsx`. All-visits
table with filter pills.

- **Filter pills:** all / ready / review / signed / processing
  — each is a `Link` that adds a `?filter=` query param. v2
  walker confirms each pill renders; future deepens with row
  counts per filter.
- **Each row:** `<Link href="/visits/{id}">` — drives the visit
  detail walker.
- **Audit rows expected on load:** `VIEWED_VISIT_LIST`.

### New visit — `/visits/new`

File: `apps/transcribe-md/src/app/visits/new/page.tsx` (+
`new-visit-client.tsx`, `visit-form-step2.tsx`).

- **Doctor's intent:** start a new visit by picking a patient +
  capture mode (audio_upload / voice_dictation / text_notes).
- **Two stages internally** (single page):
  1. PatientPicker (no patient yet) — search + select, or "+ New
     patient" link.
  2. VisitFormStep2 — specialty dropdown + 3 capture-mode tiles.
     Submitting any tile creates the `transcribe_visits` row.
- **DB writes on submit:** new `transcribe_visits` row (status
  QUEUED) + optionally a new `transcribe_md_patients` row.
- **Audit rows expected:** `CREATED_PATIENT` (only when a new
  patient is created inline), then visit-creation flow.

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
Visits (default) / Notes (stub) / Files (stub) / Trash (only when
items exist).

- **Audit rows expected on load:** `VIEWED_PATIENT_FILE`.
- **Stub-tab copy** (intentional empty-state, NOT a Pattern C
  bug): "Notes coming soon" / "Files coming soon".

### Settings — `/settings`

File: `apps/transcribe-md/src/app/settings/page.tsx`. Single-page
form with 6 sticky-anchor sections: profile / security / sessions
/ data / billing / danger-zone.

- **Walker constraint (read-only assertions for v2):** never click
  "Delete account" or "Revoke all sessions" against the test
  user. Click count is enumerated; submission is suppressed.
- **Per-section save actions** each fire their own server action
  + audit row on success.

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
