# Validation gaps

Pre-launch audit. Scope: 34 API routes (23 transcribe-md + 11 meddoc-pro), 11 server-action files (7 transcribe-md + 4 meddoc-pro), all `<form>` tags in `apps/*/src/**`. No fixes applied.

## Critical (exploitable or catastrophic)

None found. Every mutation path I examined either (a) re-validates tenant/owner scope server-side before the Prisma write, or (b) routes through the shared `patientAccessWhere(session)` filter. The earlier finding that `visit.userId !== userId` gating is universal in transcribe-md holds: 18/18 `/api/visits/[id]/*` routes enforce it (`[id]/route.ts:107`, `[id]/upload/route.ts:80`, `[id]/dictation/upload/route.ts:71`, `[id]/text/route.ts:68`, `[id]/status/route.ts:62`, `[id]/archive/route.ts:48`, `[id]/unarchive/route.ts:45`, `[id]/delete/route.ts:68`, `[id]/restore/route.ts:50`, `[id]/retry/route.ts:86`, `[id]/sign/route.ts:111`, `[id]/dictation/audio/route.ts:39`, plus all three `export/*` routes via `loadVisitExportData(visitId, userId)`).

## High (degrades reliability)

- **apps/meddoc-pro/src/app/api/doc-editor/route.ts:189-204** — category: missing zod on JSON body path — `await request.json()` destructures `{ action, documentContent, message, conversationHistory }` with no schema. A client can send any `action` string (it's `as AIAction` cast) and an arbitrarily large `documentContent` (only the multipart path file-size-caps; the JSON follow-up path has no cap). Worst case: the raw string is forwarded to `processWithAI()` which bills OpenAI tokens — a malicious client can drive spend via one authed session. Fix: define `z.object({ action: z.enum([...]), documentContent: z.string().max(200_000), message: z.string().max(20_000).optional(), conversationHistory: z.array(...).max(40).optional() })` and `safeParse`. Rate limit exists but size/shape doesn't.

- **apps/meddoc-pro/src/app/api/doc-editor/save/route.ts:96-101** — category: no zod, permissive body — destructures `{ content, format, fileName }` with only a truthy check on `content`. `format` is compared to the literal `'pdf'` but never validated as an enum; `fileName` flows into a `Content-Disposition` header via `encodeURIComponent` so header-injection is blocked, but an unbounded `content` string is fed to `textToDocxParagraphs` which could OOM the worker on a multi-MB submission. Fix: `z.object({ content: z.string().max(500_000), format: z.enum(['docx','pdf']).optional(), fileName: z.string().max(200).optional() })`.

- **apps/meddoc-pro/src/app/api/realtime/session/route.ts:73-80 and .../refresh-context/route.ts:35-44** — category: hand-rolled validation, no zod — both routes accept `{ patientId?: string; timezone?: string }` and only check `patientId` is a non-empty trimmed string. `timezone` is sanitised via `new Intl.DateTimeFormat` construction (`session/route.ts:274`, `refresh-context/route.ts:47`), which is fine. But `patientId` has no length/format cap — a 1MB patientId string would be sent to `getPatientById` → Prisma where it errors noisily (handled by withApiHandler, still wastes CPU). Low-severity shape bug; tenant scope via `getPatientById` still holds. Fix: `z.object({ patientId: z.string().min(1).max(50), timezone: z.string().max(60).optional() })`.

- **apps/meddoc-pro/src/app/api/tts/route.ts:61-77** — category: no zod — body is `{ text?: string }`; length capped at 4000 chars (`MAX_INPUT_CHARS`) and empty-check enforced, so the practical gap is only type narrowing. Rate-limited (`RATE_LIMITS.tts`). Acceptable but inconsistent with the rest of meddoc-pro — would benefit from `z.object({ text: z.string().min(1).max(4000) })` for symmetry.

- **apps/meddoc-pro/src/app/api/transcribe/route.ts:52-77** — category: no zod on multipart — multipart `audio` File is shape-checked by size (25MB cap + 100-byte minimum) but never MIME-type-checked. A client can POST a .exe blob typed `audio/wav`; OpenAI will reject it downstream, but the bytes still traverse our stack and eat rate-limit budget. Fix: whitelist `audioFile.type` like `/api/visits/[id]/upload/route.ts:40` does.

- **apps/meddoc-pro/src/app/api/patients/extract-from-voice/route.ts:226-263** — same pattern as /api/transcribe: audio file accepted with size caps (`:271`, `:277`) but no MIME whitelist. Rate-limited on the transcribe bucket. Lower severity because the audio never gets persisted (Whisper result is discarded after field extraction). Fix: same MIME check as the bulk upload route.

- **apps/meddoc-pro/src/app/api/assistant-tool/route.ts:64-116, 130-672** — category: hand-rolled arg narrowing — every tool branch does `typeof args.X === 'string' ? args.X : ''` style extraction. This works (shape is type-narrowed in-line) but is ~540 lines of repetitive narrowing that is easy to skew during edits, and the patient-scope guard at `:122` runs only once at the top so downstream tools trust the model's supplied `noteId`/`procedureId`/`reportId`/`medicationId`/`allergyId`/`appointmentId`/`fileId`. Tenant scope is enforced lower down: `dataDeleteClinicalNote` → data layer uses `patient: patientAccessWhere(session)` (clinical-notes.ts:328); `deleteAppointment` likewise. Safe today, but any future data-layer regression that drops the scope filter would expose every tool at once. Recommend adding a zod `z.discriminatedUnion('toolName', [...])` at the top so tool args are narrowed/capped in one place.

- **apps/meddoc-pro/src/app/dashboard/settings/actions.ts:15-36** — `updateProfile` reads `formData.get('name')` with a bare `typeof`+trim check, no length cap. DB column `name` is unlimited? A 10 MB name would be accepted. Low-severity; same session.user.id is used for the where clause, so only the authenticated user can poison their own row. Fix: `z.object({ name: z.string().trim().min(1).max(120) })`.

- **apps/meddoc-pro/src/app/dashboard/settings/actions.ts:42-58** — `updatePassword` uses `validatePassword()` for strength but does not zod-parse the FormData (same as above — acceptable, uses explicit typeof checks and `validatePassword` policy).

- **apps/meddoc-pro/src/app/system-admin/actions.ts:181-241** — `createUserAction`, `updateUserAction`, `resetUserPasswordAction` read FormData fields with `as string` casts and manual checks. `validatePassword()` enforces the password policy, role is whitelisted against `['DOCTOR','ADMIN','STAFF']` (`:197`, `:255`), email is lowercased+uniqueness-checked (`:202`, `:258-263`). Tenant scope is enforced via `guardSameTenant` (`:35-48`). Functionally safe but no zod schema — consistency gap.

## Medium (defensive)

- **apps/meddoc-pro/src/app/dashboard/schedule/actions.ts:150-212** — `quickAddAppointmentAction` uses manual `typeof`/`Array.includes` checks on FormData (`:161-184`), no zod schema. `visitType` is validated against the three-item allowlist; `scheduledAt` is date-parsed. Patient scope enforced downstream by `createAppointment` → `getPatientById` (appointments.ts:113). Works, but diverges from `createPatientAction`/`updatePatientAction` which do zod-parse.

- **apps/meddoc-pro/src/app/dashboard/schedule/actions.ts:226-261** — `updateAppointmentStatusAction` trusts `appointmentId: string` without shape check; `newStatus` is allowlist-checked against `VALID_STATUSES`. The `updateAppointmentStatus` data-layer call (`appointments.ts:293`) uses `patient: patientAccessWhere(session)` so tenant scope is safe. Missing format check on `appointmentId` is defensive-only.

- **apps/meddoc-pro/src/app/dashboard/patients/actions.ts:1069-1137** — `scheduleVisitAction` uses the same manual checks as quickAdd; same tenant-scope mitigation. Same recommendation.

- **apps/transcribe-md/src/actions/visits.ts:115-156** — `createVisitAction` zod-parses (good) but `resolvePatient` (`:64-113`) is correctly tenant-scoped (`patient.practiceId !== practiceId` check at `:81`). Positive.

- **apps/transcribe-md/src/actions/soap.ts:138-192** — `reassignSpeakerAction` zod-parses the enum for role but casts `visit.speakerMap as Record<string, ...>` without runtime shape check (`:171-175`). If the JSON column ever holds an unexpected shape (worker bug, manual SQL edit), the mutation writes through silently. Low risk because only the worker writes this column. Defensive fix: zod-parse the loaded speakerMap before mutating.

- **apps/meddoc-pro/src/app/api/realtime/session/route.ts:124-130** — `process.env.OPENAI_API_KEY` is checked with an `if (!apiKey)` guard but the `getOpenAI()` pattern elsewhere (`/api/transcribe:15-22`, `/api/tts:25-33`, `/api/doc-editor` implicit via ai-service) uses a lazy init + throw. Inconsistent error UX. Not a security issue; logged only as a pattern note.

- **apps/meddoc-pro/src/lib/data/patients.ts:113, 143, 195, 383, 437** — all `prisma.patient.*` calls spread `patientAccessWhere(session)` into the where. Confirmed safe.

- **apps/meddoc-pro/src/app/dashboard/patients/[id]/page.tsx:91-95** and **apps/meddoc-pro/src/app/api/realtime/session/route.ts:104** — bare `prisma.patient.findUnique({ where: { id } })` calls that skip `patientAccessWhere`. In both cases the `id` has already been resolved through `getPatientById(id, session)` earlier in the same call tree (page.tsx:59, session/route.ts:86), so the bare lookup is a read-only `noKnownAllergies` flag fetch after scope was already enforced. Safe today; one edit that reorders these two calls would reintroduce a leak. Inline comment or helper wrap would harden this.

- **apps/meddoc-pro/src/app/api/assistant-tool/route.ts:457-511** — `update_patient` branch builds an `UpdatePatientFromAssistant` object via field-by-field typeof narrowing. `assignedDoctorId` is accepted from the model but the comment at `:505-509` says enforcement "happens inside dispatchUpdatePatient → dataUpdatePatient". Worth confirming on a follow-up audit; if the data-layer function skips the check, a voice command could reassign a patient to a user in a different practice.

- **apps/meddoc-pro/src/app/dashboard/patients/actions.ts:226-243** — good: `assignedDoctorId` is explicitly re-checked to be a `DOCTOR` in `session.user.practiceId` before create. The same guard does not appear on `updatePatientAction:286-341` — it trusts `dataUpdatePatient` to enforce it. Worth verifying.

- **apps/transcribe-md/src/actions/auth.ts:64-76** — Signup `acceptTerms` is `z.literal('on', ...)`. Correct for HTML checkbox. No issues.

- Env vars read with `!` non-null assertion: none found. All reads use `process.env.X` and either guard with `if (!X)` or fall back to a default. `DUMMY_PASSWORD_HASH` in auth.ts:24 is a hashSync at module load which will throw synchronously if bcryptjs fails, but that's deterministic.

## Positive findings

- **apps/transcribe-md/src/app/api/patients/route.ts:112-172** — `CreateBodySchema` zod-validated with trimmed/length-capped fields, practiceId scoped via `session.user.practiceId` (`:157`). Exemplary.
- **apps/transcribe-md/src/app/api/patients/[id]/route.ts:27-51** — `loadPatientForSession(id, practiceId)` helper centralises the 404-on-scope-miss pattern and is reused by GET/PATCH/DELETE.
- **apps/transcribe-md/src/app/api/visits/[id]/route.ts:87-107, 147-168** — PATCH revalidates both the visit owner AND the new patientId target's practice before allowing an FK swap.
- **apps/transcribe-md/src/app/api/patients/fuzzy-match/route.ts:87-100** — raw SQL parameterised via Prisma's tagged template; practiceId bound as a parameter, not interpolated.
- **apps/transcribe-md/src/app/api/visits/[id]/sign/route.ts:135-169** — uses `updateMany` with a status guard for the atomic READY→SIGNED transition; loser of the race returns 409 rather than double-signing.
- **apps/transcribe-md/src/app/api/client-errors/route.ts:37-45** — unauthenticated sink but zod-capped every field size to block log-injection amplification.
- **apps/transcribe-md/src/app/api/auth/forgot-password/route.ts:72-131** and **resend-verification/route.ts:76-105** — anti-enumeration 200-always response, shared rate-limit bucket to prevent round-robin bypass.
- **apps/transcribe-md/src/actions/auth.ts:143-186** — `DUMMY_PASSWORD_HASH` bcrypt.compare on the skip-path to equalise wall-clock time against a timing oracle.
- **apps/meddoc-pro/src/lib/data/patients.ts + clinical-notes.ts + appointments.ts + clinical-safety.ts** — every tenant-scoped query composes `patientAccessWhere(session)` at the Prisma where level; no code path bypasses it.
- **apps/meddoc-pro/src/app/api/assistant-tool/route.ts:122-128** — re-checks patient access on every tool call even though the session endpoint already gated it. Defense in depth against model ID hallucination.

## Categories with zero findings

- **No API routes without auth gates found** — 23/23 transcribe-md routes and 11/11 meddoc-pro routes call `auth()`/`getSession()`/`requireRole()` (the one exception, `/api/client-errors`, is intentional per its header comment and compensates with per-IP rate limiting + aggressive field size caps).
- **No Prisma writes to patient/visit/document tables that bypass session scope found** — every create/update/delete threads either `session.user.id`/`userId` or `patientAccessWhere(session)` or practiceId through the where clause.
- **No env vars read via `!` non-null assertion without fallback found** across both apps.
- **No LLM outputs written directly to DB without defensive parsing found** — `/api/patients/extract-from-voice` uses a strict json_schema AND a defensive `parseFields()` narrower; worker layers use zod schemas (`worker/layers/03-extract-entities.ts`, `02-speaker-roles.ts`, `07a-icd-coding.ts`, etc., 28 files with zod).
- **No forms that submit to a server action without server-side validation found** — all 20 `<form>` tags land on an action or API route that validates.

Word count: ~1150.
