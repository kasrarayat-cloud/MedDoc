# Protected Contracts — QuillMD Transcribe-MD Remodel (Phase 1, Stage C)

**Generated**: 2026-04-29  
**Scope**: `apps/transcribe-md` frontend remodel must NOT modify these paths.  
**Rationale**: Seams are load-bearing. The remodel touches visuals only; everything that produces, validates, persists, or auths data is read-only.

---

## 1. API Routes (62 total)

All files under `apps/transcribe-md/src/app/api/**/route.ts`. Frontend never calls workers directly; only via API routes + status polls.

### Auth routes (6)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/auth/[...nextauth]` | GET, POST | NextAuth catch-all: signin, callback, session, csrf | Core session machinery; URLs are embedded in production email links. |
| `/api/auth/forgot-password` | POST | Email password-reset token | Single-use token generation; changing the URL breaks in-flight requests. |
| `/api/auth/reset-password` | POST | Consume token, update password, revoke all UserSessions | Account security state machine. |
| `/api/auth/verify-email` | GET | Consume token, mark email verified, redirect to /login | Signup verification contract. |
| `/api/auth/confirm-email` | GET | Consume EMAIL_CHANGE token, update email, email old address | Account mutation + notification. |
| `/api/auth/resend-verification` | POST | Re-mint verification token + email link | Rate-limited anti-enumeration endpoint. |

### Visit lifecycle routes (12)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/visits/[id]` | GET, PATCH | Fetch visit detail, edit draft (before pipeline starts) | PATCH validates immutability rules (queued-only editable). |
| `/api/visits/[id]/status` | GET | Real-time status (QUEUED, PROCESSING, READY, SIGNED, FAILED) | Dashboard + visit-detail view polls this; status gates UI rendering. |
| `/api/visits/[id]/progress` | GET | Long-poll: % complete + current layer being run | Used by visit-ready-view to animate progress bar. |
| `/api/visits/[id]/upload` | POST | MinIO presigned-URL + audio file ingest | Audio-uploader.tsx calls this; FormData contract. |
| `/api/visits/[id]/sign` | POST | Freeze soapFinal → signedSoap, set status=SIGNED | Audit + legal hold (signed notes are immutable). |
| `/api/visits/[id]/retry` | POST | Reset status=QUEUED, clear error metadata, requeue | Used by visit-ready-view's retry button. |
| `/api/visits/[id]/delete` | POST | Soft-delete (set deletedAt) with 15-day recoverability | GDPR + doctor's quick-delete pattern. |
| `/api/visits/[id]/archive` | POST | Set archivedAt (hides from default view) | Cleanup pattern — doesn't delete, just hides. |
| `/api/visits/[id]/unarchive` | POST | Clear archivedAt | Undo archive. |
| `/api/visits/[id]/restore` | POST | Clear deletedAt (recover from trash) | Undo delete within 15-day window. |
| `/api/visits/[id]/text` | POST | Save rawTextInput (alt to audio) | Text-composer.tsx calls this; QUEUED-only gate. |

### Visit dictation routes (2)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/visits/[id]/dictation/audio` | POST | Live Deepgram streaming transcription (WebSocket upgrade) | Real-time state — voice-dictator.tsx consumes. |
| `/api/visits/[id]/dictation/upload` | POST | Offline Deepgram batch transcription (audio blob) | Same as dictation/audio but async path. |

### Visit export routes (4)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/visits/[id]/export/clipboard` | POST | Format SOAP for EHR + return as string (for Cmd+C) | SOAP→EHR formatter contract; used by copy buttons. |
| `/api/visits/[id]/export/docx` | POST | Generate .docx file, return blob | Heavy generation logic; byte-stable. |
| `/api/visits/[id]/export/pdf` | POST | Generate .pdf file, return blob | Heavy generation logic; byte-stable. |
| `/api/visits/[id]/export/email` | POST | Email visit to specified recipient (Resend contract) | PHI delivery — destination validation happens here. |

### Patient routes (4)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/patients` | GET, POST | List patients (paginated), create patient | Cursor pagination contract (lib/patients-pagination.ts). |
| `/api/patients/[id]` | GET, PATCH, DELETE | Fetch, edit, soft-delete patient | TranscribeMdPatient mutations; practice-scoped access gate. |
| `/api/patients/[id]/export` | POST | Export patient history as CSV/JSON | Data-subject-access request (GDPR). |
| `/api/patients/fuzzy-match` | GET | Name-based patient picker (deduplicates "Smith, John" vs "John Smith") | Consumed by visit-creation patient picker; must be fast. |

### Settings routes (4)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/settings/change-email` | POST | Mint EMAIL_CHANGE token, email confirmation link | Account mutation; token-based two-step. |
| `/api/settings/change-password` | POST | Update password hash, revoke all UserSessions | Account security; immediate logout on all devices. |
| `/api/settings/delete-account` | POST | Soft-delete user (mark deletedAt), start GDPR grace period | Irreversible 30-day window; audit logged. |
| `/api/settings/export-data` | POST | Bundle all user data (GDPR right-to-data-portability) | Deterministic ZIP; includes audit trail. |

### Admin routes (29)

#### Users (9)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/admin/users` | GET | List all users (paginated) | Platform-wide visibility; role-gated. |
| `/api/admin/users/[id]` | GET, PUT, DELETE | Fetch, edit, purge user | Hard-delete (not soft). Audit trail mandatory. |
| `/api/admin/users/[id]/grant-admin` | POST | Add SUPER_ADMIN or ADMIN role | Permission escalation; audit-critical. |
| `/api/admin/users/[id]/revoke-admin` | POST | Remove admin role | Permission de-escalation; audit-critical. |
| `/api/admin/users/[id]/suspend` | POST | Set isActive=false (lock them out) | Account suspension; logout all sessions. |
| `/api/admin/users/[id]/unsuspend` | POST | Set isActive=true (restore) | Reverse suspension. |
| `/api/admin/users/[id]/soft-delete` | POST | Set deletedAt (GDPR prep) | Soft-delete; data retention rules. |
| `/api/admin/users/[id]/force-logout` | POST | Revoke all UserSessions for the user | Emergency lock-out. |
| `/api/admin/users/[id]/reset-password` | POST | Admin-initiated password reset (generates token, no email) | Helpdesk pattern. |

#### Audit logs (3)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/admin/audit-logs` | GET | List audit events (paginated, filterable) | Compliance: every ADMIN_* action is logged. |
| `/api/admin/audit-logs/stats` | GET | Aggregate stats (events/hour, top actions) | Dashboard cardinality. |
| `/api/admin/audit-logs/timeline` | GET | Time-bucketed event stream for the threat dashboard | Real-time monitoring. |

#### Threats (5)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/admin/threats` | GET | List threat detections (paginated) | Security: brute-force, rate-limit violations, suspicious patterns. |
| `/api/admin/threats/[id]` | GET | Fetch threat detail | Threat context (IP, user, action, count). |
| `/api/admin/threats/[id]/resolve` | POST | Mark threat as investigated + resolved | Closes the incident. |
| `/api/admin/threats/[id]/dismiss` | POST | Mark threat as false-positive | Suppresses future alerts on the same pattern. |
| `/api/admin/threats/history` | GET | Threat detection timeline | Historical analysis. |

#### Usage (4)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/admin/usage/summary` | GET | Total API calls + costs (this billing period) | Billing-critical cardinality. |
| `/api/admin/usage/by-user` | GET | Per-user usage breakdown (with costs) | Cost allocation. |
| `/api/admin/usage/for-user/[userId]` | GET | Single user's usage detail (paginated) | User-specific billing lookup. |
| `/api/admin/usage/timeline` | GET | Hourly API call + cost rollup | Trend analysis. |

#### HIPAA findings (4)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/admin/hipaa` | GET | List HIPAA findings (potential PHI leaks) | Compliance: each finding represents a reportable incident. |
| `/api/admin/hipaa/[id]` | GET | Fetch finding detail + remediation steps | Evidence + mitigation. |
| `/api/admin/hipaa/[id]/resolve` | POST | Mark finding as investigated + remediated | Close incident. |
| `/api/admin/hipaa/[id]/reopen` | POST | Un-resolve (e.g., new evidence) | Incident reopening. |

#### System (3)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/admin/system/health` | GET | Detailed health check (DB, Redis, MinIO, worker queue) | Uptime monitoring + dependency status. |
| `/api/admin/system/external-services` | GET | Status of Anthropic, Deepgram, Resend APIs | Third-party SLA tracking. |
| `/api/admin/system/pipeline-metrics` | GET | Worker queue depth, layer latencies, error rates | Pipeline health; used by admin dashboard. |

#### Stream (1)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/admin/stream/activity` | GET | Server-Sent Events (SSE) real-time activity feed | Audit log stream for the admin dashboard; do NOT layout-shift this. |

### Health + error reporting (2)

| Route | Methods | Purpose | Protected because |
|---|---|---|---|
| `/api/health` | GET | Liveness probe (unauthenticated) | Docker healthcheck + external uptime monitor. |
| `/api/client-errors` | POST | Browser error capture (Sentry alternative) | PHI redaction (redactPhi must be applied before storage). |

---

## 2. Server Actions (11 files)

All under `apps/transcribe-md/src/actions/` plus 4 lib files marked `'use server'`. These are the primary seam between the server and client components.

### Signature inventory

#### `actions/auth.ts` — Authentication lifecycle

| Function | Args | Return | Consumed by |
|---|---|---|---|
| `loginAction` | `_prev: FormErrorState \| FormOkState, formData: FormData` | `Promise<FormErrorState \| FormOkState>` | `app/login/page.tsx` form submission |
| `signupAction` | `_prev: FormErrorState \| FormOkState, formData: FormData` | `Promise<FormErrorState \| FormOkState>` | `app/signup/page.tsx` form submission |
| `forgotPasswordAction` | `_prev: FormErrorState \| FormOkState, formData: FormData` | `Promise<FormErrorState \| FormOkState>` | `app/forgot-password/page.tsx` form submission |
| `resetPasswordAction` | `_prev: FormErrorState \| FormOkState, formData: FormData` | `Promise<FormErrorState \| FormOkState>` | `app/reset-password/page.tsx` form submission |

**Interface exports**:
- `FormErrorState` — `{ ok: false; errors: Record<string, string>; values?: Record<string, string>; needsVerificationFor?: string; crossAppRedirect?: { message, url, buttonLabel } }`
- `FormOkState` — `{ ok: true }`

**Seam integrity**: Form submission shapes + redirect targets are embedded in email links (production traffic). Changing the URL structure breaks recovery flows already in the field.

#### `actions/visits.ts` — Visit creation + list pagination

| Function | Args | Return | Consumed by |
|---|---|---|---|
| `createVisitAction` | `_prev: any, formData: FormData` | `Promise<void>` (redirects or throws) | `app/visits/new/page.tsx` form submission |
| `loadMoreVisitsAction` | `cursor: DashboardCursor` | `Promise<LoadMoreVisitsResult>` | `app/dashboard/page.tsx` infinite-scroll trigger |

**Type exports**:
- `DashboardCursor` — `{ lastId: string; offset: number }` (cursor pagination state)
- `LoadMoreVisitsResult` — `{ visits: DashboardVisit[]; nextCursor: DashboardCursor \| null }`
- `DASHBOARD_PAGE_SIZE` constant (25 visits per page)

**Seam integrity**: The cursor shape is serialized to browser state; changing it breaks pagination across page reloads.

#### `actions/patients.ts` — Patient list pagination

| Function | Args | Return | Consumed by |
|---|---|---|---|
| `loadMorePatientsAction` | `cursor: PatientsCursor` | `Promise<LoadMorePatientsResult>` | `app/patients/page.tsx` infinite-scroll trigger |

**Type exports**:
- `PatientsCursor` — (same shape as DashboardCursor)
- `LoadMorePatientsResult` — `{ patients: PatientRow[]; nextCursor: PatientsCursor \| null }`

#### `actions/soap.ts` — Visit SOAP editing + signing

| Function | Args | Return | Consumed by |
|---|---|---|---|
| `saveSoapDraftAction` | `visitId: string, text: string` | `Promise<SaveSoapResult>` | `visit-ready-view.tsx` editor submit |
| `signVisitAction` | `visitId: string` | `Promise<SaveSoapResult>` | `visit-ready-view.tsx` sign button |
| `reassignSpeakerAction` | `visitId: string, utteranceIndex: number, newSpeaker: string` | `Promise<SaveSoapResult>` | `visit-ready-view.tsx` transcript editor |

**Interface exports**:
- `SaveSoapResult` — `{ ok: boolean; error?: string }`

**Seam integrity**: SOAP text is **50K character max** (Zod schema constraint); changing this affects the editor's validation.

#### `actions/profile.ts` — User profile mutations

| Function | Args | Return | Consumed by |
|---|---|---|---|
| `updateProfileAction` | `_prev: ProfileState, formData: FormData` | `Promise<ProfileState>` | `app/settings/page.tsx` profile form |

**Type exports**:
- `ProfileState` — `{ ok: true; savedAt: number } \| { ok: false; errors: Record<string, string> } \| null`

**Seam integrity**: The form's optional fields (specialty, npi, clinicName, timeZone) can be cleared by sending empty strings.

#### `actions/session.ts` — Session lifecycle

| Function | Args | Return | Consumed by |
|---|---|---|---|
| `signOutAction` | (none) | `Promise<void>` | `user-menu.tsx` logout button |
| `signOutAllDevicesAction` | (none) | `Promise<void>` | `app/settings/page.tsx` "sign out all devices" button |

**Seam integrity**: Both revoke all `UserSession` rows + clear the NextAuth cookie atomically. Changing the revocation logic breaks single-session enforcement.

#### `actions/command-palette.ts` — Search

| Function | Args | Return | Consumed by |
|---|---|---|---|
| `getRecentVisits` | (none) | `Promise<RecentVisitItem[]>` | `command-palette.tsx` Cmd+K search |

**Type exports**:
- `RecentVisitItem` — `{ id, patientName, specialty, createdAt: ISO string }`

**Seam integrity**: `createdAt` is serialized as ISO string (not `Date` object) for RSC transport.

#### `lib/dashboard-pagination.ts` — Pagination helpers (`'use server'`)

| Function | Args | Return |
|---|---|---|
| (exported types, not functions) | — | `DashboardCursor`, `LoadMoreVisitsResult`, `DASHBOARD_PAGE_SIZE` |

#### `lib/patients-pagination.ts` — Patient pagination helpers (`'use server'`)

| Function | Args | Return |
|---|---|---|
| (exported types, not functions) | — | `PatientsCursor`, `LoadMorePatientsResult` |

#### `lib/patients-query.ts` — Patient query helpers (`'use server'`)

| Function | Args | Return | Used by |
|---|---|---|---|
| `fetchPatientsPage` | `practiceId: string, cursor: PatientsCursor` | `Promise<LoadMorePatientsResult>` | `patients.ts` action |

#### `lib/rx-warning-audit.ts` — Rx safety audit (`'use server'`)

| Function | Args | Return | Consumed by |
|---|---|---|---|
| `auditRxWarningOverride` | `visitId: string, overrideReason: string` | `Promise<{ ok: boolean; error?: string }>` | `rx/override-confirm-modal.tsx` override submission |
| `getRxWarningsForVisit` | `visitId: string` | `Promise<RxWarningItem[]>` | `rx/rx-warning-card.tsx` warning display |

**Seam integrity**: The Rx warning types must match the model schema exactly; changing the fields breaks the doctor's override UX.

---

## 3. Auth + Middleware (6 files, entire-file protection)

These are load-bearing for session gating, token validation, and security posture.

### `apps/transcribe-md/src/proxy.ts` (28 lines)

**Entire file protected**. This is the renamed Next.js 16 Edge middleware (NOT `middleware.ts`).

**Purpose**: On every request to `/dashboard/*`, `/visits/*`, `/settings/*`, calls the edge-safe `authConfig` to validate the NextAuth session cookie. On failure, redirects to `/login?callbackUrl=...`.

**Hazards**:
- **Do NOT rename to `middleware.ts`** — Next 16 broke the convention; this filename is deliberate.
- **Do NOT add a separate `middleware.ts`** — Next 16 will not load it alongside `proxy.ts`.
- **Do NOT move the matcher** — routes are deliberately narrow (`/dashboard/*`, `/visits/*`, `/settings/*`); `/admin/*` is gated in `app/admin/layout.tsx` instead (deliberate separation).
- The JSON Web Token (JWT) is **edge-safe** (no Prisma, no Node). Node-side session validation (single-session enforcement) happens in `lib/nextauth.ts` after the edge pass.

### `apps/transcribe-md/src/lib/auth.config.ts` (entire file protected)

Re-exports `authConfig` from `@meddoc/auth` (the shared package). No Prisma. Used by `proxy.ts` on the Edge.

### `apps/transcribe-md/src/lib/nextauth.ts` (entire file protected)

The full Node-side NextAuth v5 instance. Contains:
- **Credentials provider**: `signIn(email, password)` bcrypt validation.
- **JWT callback**: validates `UserSession` (single-session enforcement via DB lookup).
- **Session callback**: injects user data into the session object.
- **Session maxAge**: 7 days (even though single-session limits concurrent use to one).

**Hazard**: Changing the session shape or maxAge breaks the JWT structure and client code expecting specific claims.

### `apps/transcribe-md/src/lib/auth.ts` (69 lines)

**Key exports**:
- `getSession(): Promise<Session | null>` — calls `auth()`, re-reads DB for isActive check (immediate revocation).
- `requireSession(): Promise<Session>` — throws `AuthError` if not signed in.
- `getCurrentSessionId(): Promise<string | null>` — extracts the `sessionId` claim from the JWT.

**Seam integrity**: `getSession()` re-reads the DB on every call to honour emergency revocation (e.g., admin suspended a user). Removing this DB check breaks the revocation mechanism.

### `apps/transcribe-md/src/lib/auth-tokens.ts` (entire file protected)

Email verification + password-reset token state machine.

**Key exports**:
- `generateRawToken(): string` — 32 bytes CSPRNG → 43 chars base64url.
- `hashToken(raw: string): string` — SHA-256 (not bcrypt; one-shot tokens are already high-entropy).
- `createAuthToken(args: CreateAuthTokenArgs): Promise<CreatedAuthToken>` — mints token, invalidates prior unused tokens for the same (user, purpose), returns raw token for embedding in email.
- `consumeAuthToken(id: string, hash: string): Promise<...>` — atomic single-consume via `updateMany(...WHERE usedAt IS NULL)`.

**Hazard**: Token-lifecycle bugs (e.g., allowing re-use, or double-consuming) leak account access. The SHA-256 choice is deliberate (no bcrypt overhead on one-shot tokens).

### `apps/transcribe-md/src/app/admin/layout.tsx` (99 lines, lines 1–100 protected)

**CRITICAL SECURITY NOTE**: Uses `notFound()` (not `redirect()`) when the caller lacks `Product.SUPER_ADMIN`.

**Lines 1–60**: Config (dynamic = force-dynamic, revalidate = 0) + layout signature.

**Lines 32–60**: Auth gate logic:
- Reads session JWT.
- Looks for `products` claim (if missing, falls back to DB lookup).
- Checks `Product.SUPER_ADMIN` presence.
- **If missing: calls `notFound()`** ← This is deliberate to avoid exposing `/admin` existence to anonymous probers.

**Lines 62–70**: Admin session freshness check (12-hour ceiling on top of the 7-day cookie — Phase 19 hardening).

**Lines 77–92**: Audit logging (every `/admin/*` render is logged).

**Lines 94–99**: Main tag + children render.

**DO NOT CHANGE to `redirect('/login')`** — that's a security regression. A reflexive "make auth errors redirect instead of 404" change will expose the `/admin` surface to enumeration.

---

## 4. Worker + Sidecar (20+ files, entire directories protected)

The BullMQ async pipeline that processes audio → SOAP notes.

### Entry points

- `apps/transcribe-md/src/worker.ts` — BullMQ consumer entrypoint (starts listening on the queue).
- `apps/transcribe-md/src/worker-sentry.ts` — Sentry integration for worker errors.

### Pipeline layer files (`apps/transcribe-md/src/worker/layers/`)

Each layer is a processing stage. Do NOT modify any of these:

| File | Purpose | Input | Output |
|---|---|---|---|
| `01-transcribe.ts` | Deepgram batch transcription (audio blob → raw text) | AudioKey | Transcript |
| `01b-transcribe-dictation.ts` | Voice-dictation path (live streaming) | DictationAudioKey | Transcript |
| `02-speaker-roles.ts` | Diarization (who said what; assign speaker labels) | Transcript | Diarized utterances + speakers |
| `03-extract-entities.ts` | Entity extraction (medications, allergies, problems) | Diarized transcript | Extracted entities (JSON) |
| `04-generate-soap.ts` | LLM: raw SOAP note generation (Claude Sonnet 4.6) | Transcript + entities | Initial SoapNote (Zod-validated) |
| `05-self-critique.ts` | LLM: verify SOAP quality (completeness, accuracy) | SoapNote | Critique + confidence scores |
| `06-polish.ts` | LLM: readability pass (grammar, tone) | SoapNote + critique | Final SoapNote |
| `07a-icd-coding.ts` | ICD-10 diagnosis code recommendations | Problems from SOAP | ICD codes |
| `07b-cpt-coding.ts` | CPT procedure code recommendations | Procedures from SOAP | CPT codes |
| `07c-rx-drafting.ts` | Prescription drafting + Rx safety checking | Medications from SOAP | Drafted Rx + warnings |
| `07d-referrals.ts` | Referral recommendations | Problems from SOAP | Referral suggestions |
| `07e-patient-summary.ts` | Summary for patient portal | Full SOAP | Summary text |
| `readability.ts` | Reading-level scoring (Flesch-Kincaid) | SOAP text | Grade level + score |

### Cleanup jobs (`apps/transcribe-md/src/worker/cleanup/`)

| File | Purpose |
|---|---|
| `minio-orphans.ts` | Finds and deletes orphaned audio files in MinIO (> 30 days without a visit reference). |
| `retention-sweep.ts` | Soft-deletes visits older than the practice's retention window. |
| `stale-visits.ts` | Resets visits stuck in PROCESSING > 24 hours back to QUEUED. |

### Control files

| File | Purpose |
|---|---|
| `error-categorize.ts` | Classifies layer errors into retry-able vs permanent. |
| `layer-skip.ts` | Determines which layers to skip (e.g., skip ICD-coding if disabled). |
| `retry-decision.ts` | Decides whether to retry a failed job + exponential backoff. |

### Prompts

| File | Purpose |
|---|---|
| `prompts/specialty-guidance.ts` | Specialty-specific LLM system prompts (e.g., cardiology → focus on heart/meds). |

### Tests covering the worker

These are canaries — if they break, a remodel touched something in the protected zone:

- `tests/worker/auth-tokens.test.ts` — Token generation / consumption.
- `tests/worker/ehr-formatters.test.ts` — EHR export format shapes. **Medium risk**: frontend imports `ehr-formatters.ts` for copy buttons.
- `tests/worker/edit-tracking.test.ts` — Edit distance + edit-pattern capture.
- `tests/worker/layer-skip.test.ts` — Pipeline layer skip logic.
- `tests/worker/readability.test.ts` — Reading-level scoring.
- `tests/worker/edit-distance.test.ts` — String diff algorithm.
- `tests/worker/generators.test.ts` — DOCX/PDF document generation.
- `tests/worker/embed-mock.test.ts` — OpenAI embedding mocks.
- `tests/worker/rate-limit.test.ts` — Redis rate limiter.
- `tests/worker/minio-orphans.test.ts` — MinIO cleanup.

### Deployment artifact

- `apps/transcribe-md/Dockerfile.worker` — Builds the `transcribe-md-worker` container (separate from the Next.js app).

---

## 5. AI Pipeline (`packages/ai/`)

### Index exports (`packages/ai/src/index.ts`)

| Export | File | Purpose |
|---|---|---|
| `ModelClient` | `model-client.ts` | Anthropic + OpenAI dispatch. Used by worker layers. |
| `redactPhi` | `log.ts` | Canonical PHI scrubber (applies before logging any user text). **Wired into `sentry.{server,edge}.config.ts` of transcribe-md.** |
| `logAiCall` | `log.ts` | Logs API calls to the `AiCall` table (audit + billing). |
| `deepgramBatchCostCents`, `claudeSonnet46CostCents` | `pricing.ts` | Cost calculators for billing. |
| `hashPrompt` | `prompt-hash.ts` | Deterministic cache key generation (for prompt deduplication). |
| `embedText` | `embed.ts` | OpenAI text-embedding-3-small. Returns vector of dimension 1536 (exported constant `EMBED_DIMENSION`). |
| `PRICING` object | `api-usage.ts` | Rate card (cents per 1M tokens, per provider). |
| `logApiUsage`, `buildDeepgramUsage`, etc. | `api-usage.ts` | Usage event capture for the admin usage dashboard. |

**Seam integrity**: `redactPhi` must strip PHI before **any** error logging. If a new client-side error logger is added (e.g., Datadog instead of Sentry), it must call `redactPhi` on every payload.

---

## 6. DB Layer (`packages/db/`)

### Schema file

- **`packages/db/prisma/schema.prisma`** — **1,980 lines, 28 models**.

**Models** (do NOT reshape or add required fields without a migration):

1. `Practice` — org/clinic record
2. `User` — doctor account
3. `Account` — OAuth integration (NextAuth)
4. `Session` — NextAuth session
5. `VerificationToken` — email verification (deprecated, use AuthToken)
6. `AuthToken` — email tokens (PASSWORD_RESET, EMAIL_VERIFICATION, EMAIL_CHANGE)
7. `AccountDeletion` — GDPR deletion grace period record
8. `Patient` — CRM patient (meddoc-pro legacy; **not used by transcribe-md**)
9. `Document` — CRM document (legacy)
10. `AuditLog` — action audit trail
11. `Appointment` — CRM appointment (legacy)
12. `Allergy` — allergy record
13. `Medication` — medication record
14. `Task` — task/to-do
15. `BillingEvent` — usage charge log
16. `SessionLog` — session activity (login/logout/activity)
17. `ApiUsageLog` — per-call API usage (deprecated; see ApiUsageEvent)
18. `ApiUsage` — aggregate usage stats (legacy)
19. `AiCall` — audit log of AI (Anthropic, Deepgram, OpenAI) calls
20. `TranscribeMdPatient` — transcribe-md patient (DISTINCT from `Patient`)
21. `TranscribeVisit` — visit record (audio, SOAP, status, timestamps)
22. `VisitDelivery` — which EHRs a visit was exported to
23. `DoctorEditPattern` — tracks edit diffs (edit distance, patterns)
24. `UserSession` — single-session enforcement (revocation list)
25. `RxWarningOverride` — doctor's explicit Rx safety override decision
26. `ApiUsageEvent` — per-call usage event (Phase 6 replacement for ApiUsageLog)
27. `ThreatResolution` — threat-detection resolution (Phase 6)
28. `HipaaFinding` — HIPAA audit findings (Phase 7B)

**Seam integrity**: `TranscribeMdPatient` and `Patient` are **separate models** with separate IDs. Code touching "patient" must verify which one it hits.

### Migrations (41 directories)

All under `packages/db/prisma/migrations/`:

```
0000_init
20260412234252_add_multi_tenancy
20260413001104_add_super_admin_role
20260413051135_add_deleted_appointment_action
20260413053230_add_patient_chartid_unique_per_practice
20260414013538_add_patient_brief_history
20260414202049_add_patient_sex_address_pharmacy
20260415203807_add_allergies_medications
20260417030632_add_scribe_foundations
20260417072107_add_scribe_specialty_cpt_hints_and_review_status
20260417144000_add_m6_tasks_billing_events_provenance
20260417144501_add_m6_audit_actions
20260417170100_add_retention_fields_to_practice
20260418231501_add_transcribe_md_product_and_sessions
20260419012302_add_audio_pipeline_fields
20260419033313_add_dictation_and_text_fields
20260419041733_add_automating_status
20260419052324_add_visit_deliveries
20260419155934_remove_scribe_tables
20260420100000_add_t_m14_edit_tracking
20260420143000_add_auth_tokens_and_account_deletions
20260420153157_add_ai_call_error_details
20260420171302_add_transcribe_md_patients
20260420192818_transcribe_visits_patient_id_required
20260420210513_transcribe_visits_soft_delete
20260421045628_t_m18_3_visit_dashboard_indexes
20260421211200_t_m24_custom_templates
20260422000000_t_m24_smart_inject
20260422100000_drop_t_m24_templates
20260423024335_app_redesign_v1_new_fields
20260423183431_rx_warning_override
20260425000112_voice_retry_robustness
20260425023425_admin_phase_1a_audit_actions
20260425045108_admin_api_access
20260425194125_phase_6_users_and_usage
20260426001735_phase_6h_threat_resolutions
20260426062414_phase_7b_hipaa_findings
20260426071519_phase_8_pilot_followup_findings
20260427013322_phase_17_audit_completeness_actions
20260427023420_phase_19_realtime_audit_actions
migration_lock.toml
```

---

## 7. Type Contracts (`packages/types/`)

### Core exports

| File | Key exports | Purpose |
|---|---|---|
| `src/soap.ts` | `SoapNoteSchema` (Zod), `SoapNote` type, `AssessmentItemSchema`, `ConfidenceLevel` enum | **THE critical seam** — visit-detail view editor + display consumers must validate SOAP text against this schema. Changing field names / required status breaks doctor workflow. |
| `src/soap-render.ts` | `sectionSoap()`, `sectionCodes()`, `sectionRx()`, `sectionExtras()` | Render helpers (text/markdown projections). Used by copy buttons + EHR export. |
| `src/index.ts` | Re-exports both files | — |

**Seam integrity**: `SoapNoteSchema` is the contract between the AI pipeline (output validation) and the visit-ready view (display/edit). It travels across the boundary unchanged.

---

## 8. App-Internal Logic Libs (`apps/transcribe-md/src/lib/`)

37 .ts files total. Categorized by modification risk:

### Safe to read (display helpers, no shape-changing)

| File | Lines | Purpose | Why safe |
|---|---|---|---|
| `cn.ts` | 14 | Class name merger (clsx + twMerge) | Pure utility; no Prisma, no state. |
| `format-time.ts` | 129 | Timezone-safe date formatters | Pure client helpers; return shapes are stable. |
| `dob.ts` | 56 | Date-of-birth validator | Pure validation logic; return shapes stable. |
| `constants.ts` | ~30 | App-wide constants (APP_URL, etc.) | Config only. |
| `specialties.ts` | ~150 | Specialty catalog + lookup helpers | Static data. |
| `deepgram-vocabulary.ts` | ~200 | Deepgram vocab boost (medical terms) | Static list used by voice pipeline. |
| `shortcuts.ts` | ~80 | Keyboard shortcut bindings | Event handlers; pure logic. |
| `cleanup-heartbeat.ts` | ~50 | Worker heartbeat ping | Liveness check only. |

### DO NOT TOUCH (logic / data / state)

| File | Lines | Purpose | Why protected |
|---|---|---|---|
| `auth.ts` | 69 | Session wrapper + `requireSession()` | Revocation enforcement (DB re-read on every call). |
| `auth.config.ts` | ~30 | Edge-safe NextAuth config | Edge middleware contract. |
| `auth-tokens.ts` | ~150 | Token generation/consumption | Account security. |
| `nextauth.ts` | ~200 | NextAuth config + callbacks | JWT shape + session maxAge. |
| `api-error.ts` | ~80 | API error classification + HTTP responses | Consumed by all 62 API routes. |
| `audit.ts` | ~100 | Audit logging to DB | Compliance audit trail. |
| `admin-api-gate.ts` | ~80 | Admin route authorization | RBAC checks. |
| `admin-session-freshness.ts` | ~60 | 12-hour session freshness ceiling | Security hardening. |
| `admin-notifications.ts` | ~100 | Admin alert + email dispatch | Incident notification. |
| `dashboard-pagination.ts` | ~80 | Cursor pagination helpers | Pagination state shape (serialized to browser). |
| `patients-pagination.ts` | ~60 | Patient list pagination | Pagination state shape. |
| `patients-query.ts` | ~100 | Patient lookup + filtering | DB query contract. |
| `rx-warning-audit.ts` | ~200 | Rx safety checking + override tracking | Medical safety; audit-critical. |
| `ehr-formatters.ts` | ~300 | SOAP → EHR format converters (Epic, Athena, Cerner, eCW, generic) | **Frontend calls this from copy buttons** — do NOT change return shapes. |
| `visit-export.ts` | ~150 | Visit data export shape | Consumed by clipboard/docx/pdf/email routes. |
| `visit-export-server.ts` | ~200 | Server-side export helpers | DOCX/PDF generation. |
| `email.ts` | ~250 | Email dispatch (Resend SDK) | Outbound PHI delivery. |
| `email-enabled.ts` | ~30 | Feature flag for email delivery | Config-driven. |
| `minio.ts` | ~200 | MinIO object storage (S3-compatible) | Audio file storage + retrieval. |
| `queue.ts` | ~100 | BullMQ queue initialization | Worker job submission. |
| `redis.ts` | ~50 | Redis client (shared with queue + rate limiter) | Shared infrastructure. |
| `rate-limit.ts` | ~150 | IP-based rate limiting | Security; prevents brute force. |
| `fingerprint.ts` | ~80 | Browser fingerprinting | User identification (anti-account-takeover). |
| `log.ts` | ~50 | Server-side logging (structured + PHI-safe) | Observability. |
| `problem-list.ts` | ~100 | Problem-list extraction from SOAP | AI output parsing. |
| `edit-distance.ts` | ~80 | String diff / edit distance | Used by edit-tracking tests. |
| `edit-tracking.ts` | ~150 | Doctor-edit pattern capture (for billing) | Audit + analytics. |
| `deliveries.ts` | ~100 | EHR delivery tracking (which visit went to which system) | Compliance logging. |
| `docx-generator.ts` | ~400 | Microsoft Word .docx file generation (using `docx` library) | Patient-facing export. |
| `pdf-generator.ts` | ~400 | PDF generation (using `pdfkit` + `archiver`) | Patient-facing export. |

**Sum**: ~5,900 lines of lib code. Only the top 8 are "safe to read"; the other 29 are logic/data and protected.

---

## 9. Component-Level Seam Notes

For each non-migrated component in COMPONENT_INVENTORY.md, the exact imports the remodel must preserve:

### Feature — Visit creation / recording

#### `audio-uploader.tsx` (274 LOC)

**Imports to preserve**:
```typescript
import { uploadAudio } from '@/actions/visits'  // ← actual function name may differ; check live code
```

**API contract**:
- POST `/api/visits/[id]/upload`
- Request body: `FormData` with `audio: Blob` field
- Response: `{ url: string }` (MinIO presigned URL)

**Call pattern**: `const { data } = await uploadFile(formData)`

#### `voice-dictator.tsx` (342 LOC)

**Imports to preserve**:
```typescript
import { submitDictationAudio } from '@/actions/visits'  // ← check live
```

**API contracts**:
- POST `/api/visits/[id]/dictation/audio` — WebSocket upgrade for streaming transcription
- POST `/api/visits/[id]/dictation/upload` — offline batch transcription

**Call pattern**: Real-time byte stream or FormData blob

#### `text-composer.tsx` (152 LOC)

**Imports to preserve**:
```typescript
import { createVisitAction } from '@/actions/visits'
```

**Call pattern**: `const result = await createVisitAction(formData)`
- Form fields: `patientId`, `patientName`, `specialty`, `chiefComplaint`, `inputMode`
- Validation: specialty required, inputMode must be one of `['audio_upload', 'voice_dictation', 'text_notes']`

#### `command-palette.tsx` (300 LOC)

**Imports to preserve**:
```typescript
import { getRecentVisits } from '@/actions/command-palette'
```

**Call pattern**: `const visits = await getRecentVisits()`
- Returns: `[{ id, patientName, specialty, createdAt: ISO string }]`

### Feature — Dashboard

#### `dashboard/patient-card.tsx` (148 LOC, **migrated**)

**Exports**:
```typescript
export interface DashboardPatient { id, name, … }
```

**Consumed by**: `app/dashboard/page.tsx`

#### `dashboard/visit-list.tsx` (209 LOC, **migrated**)

**Imports to preserve**:
```typescript
import { loadMoreVisitsAction } from '@/actions/visits'
import type { DashboardVisit } from '@/lib/dashboard-pagination'
```

**Call pattern**: `const result = await loadMoreVisitsAction(cursor)`
- Returns paginated visits with DashboardVisit type shape

#### `patient-card.tsx` (89 LOC, **top-level duplicate**)

**Status**: Should be removed or merged with `dashboard/patient-card.tsx`. Grep for call sites before deleting:
```bash
grep -r "from.*components/patient-card\>" src/
```

#### `visit-card.tsx` (123 LOC, **legacy**)

**Status**: Likely superseded by `visit-list.tsx`. Check for call sites before removing.

### Feature — Rx safety

#### `rx/rx-warning-card.tsx` (518 LOC, **migrated**)

**DO NOT change the visual structure without updating the RTL test** (`rx/__tests__/rx-warning-card.test.tsx`).

**Imports to preserve**:
```typescript
import { getRxWarningsForVisit } from '@/lib/rx-warning-audit'
```

**Seam**: Returns warnings in shape `{ medication, severity, reason, override: boolean }`

#### `rx/override-confirm-modal.tsx` (308 LOC, **migrated**)

**Imports to preserve**:
```typescript
import { auditRxWarningOverride } from '@/lib/rx-warning-audit'
```

**Call pattern**: `await auditRxWarningOverride(visitId, overrideReason)`

### Feature — Global UX

#### `user-menu.tsx` (102 LOC, **legacy**)

**Imports to preserve**:
```typescript
import { signOut } from 'next-auth/react'
import { signOutAction } from '@/actions/session'
```

**Call pattern**: Calls `signOutAction()` on logout button click (revokes UserSession + clears cookie)

#### `command-palette.tsx` (300 LOC, **legacy**)

(Already listed above under visit creation.)

#### `toaster.tsx` (41 LOC, **legacy**)

**Imports to preserve**:
```typescript
import { Toaster } from 'sonner'
```

**No backend seam** — purely visual. Can reskin to `.qm-toast` styling.

---

## 10. Tests Covering the Protected Zone

**HIGH RISK**: Any test breakage signals a protected seam was crossed.

### E2E scenarios (`apps/transcribe-md/tests/e2e/scenarios/`)

| File | Scope | Brittle selectors |
|---|---|---|
| `1-audio-upload-full.spec.ts` | Signup → upload audio → wait → review → sign → dashboard | Yes (form fields, progress bar, button text) |
| `2-voice-dictation.spec.ts` | Voice capture flow | Yes (recording UI, timer, submit button) |
| `3-text-to-soap.spec.ts` | Text-input flow | Yes (textarea, submit, validation) |
| `4-back-to-dashboard.spec.ts` | Navigation contract (visit → dashboard links) | Yes (link selectors) |

### Worker tests (`apps/transcribe-md/tests/worker/`)

| File | Protected area |
|---|---|
| `auth-tokens.test.ts` | Token generation/consumption logic |
| `ehr-formatters.test.ts` | **MEDIUM RISK** — tests EHR formatter return shapes; frontend copy buttons depend on these |
| `edit-tracking.test.ts` | Edit-distance capture |
| `layer-skip.test.ts` | Pipeline layer skip rules |
| `readability.test.ts` | Reading-level scoring |
| `edit-distance.test.ts` | String diff algorithm |
| `generators.test.ts` | DOCX/PDF generation |
| `embed-mock.test.ts` | OpenAI embedding |
| `rate-limit.test.ts` | Rate limiter |
| `minio-orphans.test.ts` | MinIO orphan cleanup |

### Component tests

| File | Protected area |
|---|---|
| `src/components/rx/__tests__/rx-warning-card.test.tsx` | **HIGH RISK** — RTL test with selector assertions; if the remodel touches the card structure, this breaks |

---

## 11. Summarized "Do Not Touch" Checklist

Use this as a final gate before committing remodel code:

- [ ] **API routes**: All 62 files under `apps/transcribe-md/src/app/api/**`
- [ ] **Server actions**: All 11 files in `apps/transcribe-md/src/actions/` + 4 lib files with `'use server'`
- [ ] **Auth machinery**: `proxy.ts`, `lib/auth*.ts`, `lib/nextauth.ts`, `app/admin/layout.tsx` (entire files)
- [ ] **Worker + pipeline**: All 20+ files under `src/worker/**`, `worker.ts`, `worker-sentry.ts`, `Dockerfile.worker`
- [ ] **AI package**: `packages/ai/src/**` (entire directory)
- [ ] **DB schema**: `packages/db/prisma/**` (schema + 41 migrations)
- [ ] **Type contracts**: `packages/types/src/{soap,soap-render}.ts`
- [ ] **Lib logic files** (29 of 37): anything touching Prisma, Redis, MinIO, auth, email, queue, audit, rate-limit, EHR formatters, visit exports, edit tracking, code generators
- [ ] **Component seam imports**: Exact import paths in `<AudioUploader>`, `<VoiceDictator>`, `<CommandPalette>`, etc.
- [ ] **Test canaries**: All 14 worker tests + 4 e2e scenarios + 1 RTL test must pass (if broken, a seam was crossed)

---

## End of Protected Contracts

**Document version**: Phase 1, Stage C (Logic Protector)  
**Last updated**: 2026-04-29  
**Next action**: Design Director produces visual directions A/B/C for Stage D handoff.
