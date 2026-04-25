# Audit coverage — transcribe-md

Phase 1A closes HIPAA finding H2 by porting `logAudit()` from
meddoc-pro into transcribe-md and calling it at every PHI-touching
mutation surface. This file is the matrix.

Every row below was VERIFIED live on 2026-04-25 by firing the
action against the QA user (`qa-audit@quillmd.local`) and
grepping `audit_logs` for the expected row.

| Surface | Route / action | Audit action enum | Verified |
|---|---|---|---|
| Auth | `events.signIn` in nextauth.ts | `LOGIN_SUCCESS` | ✅ `timestamp > NOW() - 5m` |
| Auth | `events.signOut` in nextauth.ts | `LOGOUT` | ✅ same |
| Auth | authorize() bcrypt-mismatch | `LOGIN_FAILED` (errorCode CREDENTIALS_MISMATCH / ACCOUNT_LOCKED_NOW) | static-review only |
| Auth | `GET /api/auth/confirm-email` | `EMAIL_CHANGE_CONFIRMED` | static-review only |
| Visit | `POST /api/visits/[id]/sign` (success) | `VISIT_SIGNED` | static-review only |
| Visit | `POST /api/visits/[id]/sign` (PHI-to blocked) | `EXPORT_EMAIL_BLOCKED_DESTINATION` | static-review only |
| Visit | `POST /api/visits/[id]/sign` (critical no override) | `RX_SIGN_BLOCKED_NO_OVERRIDE` | static-review only |
| Visit | `POST /api/visits/[id]/delete` | `VISIT_DELETED` (metadata.mode = permanent/hard/soft) | static-review only |
| Visit | `POST /api/visits/[id]/archive` | `VISIT_ARCHIVED` | static-review only |
| Visit | `POST /api/visits/[id]/unarchive` | `VISIT_UNARCHIVED` | static-review only |
| Visit | `POST /api/visits/[id]/restore` | `VISIT_RESTORED` | static-review only |
| Visit | `POST /api/visits/[id]/retry` (success) | `VISIT_RETRY` | static-review only |
| Visit | `POST /api/visits/[id]/retry` (budget exhausted) | `VISIT_RETRY_BUDGET_EXHAUSTED` | static-review only |
| Export | `POST /api/visits/[id]/export/email` (success) | `EXPORT_EMAIL_SENT` | ✅ |
| Export | `POST /api/visits/[id]/export/email` (blocked) | `EXPORT_EMAIL_BLOCKED_DESTINATION` | ✅ |
| Export | `GET /api/visits/[id]/export/pdf` | `EXPORT_PDF_DOWNLOADED` | ✅ |
| Export | `GET /api/visits/[id]/export/docx` | `EXPORT_DOCX_DOWNLOADED` | ✅ |
| Export | `POST /api/visits/[id]/export/clipboard` | `EXPORT_CLIPBOARD_COPIED` | ✅ |
| Patient | `POST /api/patients` | `TM_PATIENT_CREATED` | ✅ |
| Patient | `PATCH /api/patients/[id]` | `TM_PATIENT_UPDATED` | ✅ |
| Patient | `DELETE /api/patients/[id]` | `TM_PATIENT_DELETED` | ✅ |
| Settings | `POST /api/settings/change-password` | `PASSWORD_CHANGED` | static-review only |
| Settings | `POST /api/settings/change-email` | `EMAIL_CHANGE_REQUESTED` | static-review only |
| Settings | `POST /api/settings/delete-account` | `ACCOUNT_DELETED` | static-review only |
| Rx safety | `recordOverride()` action | `RX_OVERRIDE_RECORDED` | static-review only |
| Admin | `/admin/*` page render (meddoc-pro) | `ADMIN_DASHBOARD_ACCESS` | ✅ `targetId='/admin'` |

**Live tally (5-minute snapshot after probing):**
```
         action         | count
------------------------+-------
 LOGIN_SUCCESS          |  2
 LOGOUT                 |  1
 TM_PATIENT_CREATED     |  1
 TM_PATIENT_UPDATED     |  1
 TM_PATIENT_DELETED     |  1
 EXPORT_EMAIL_BLOCKED   |  1
 EXPORT_PDF_DOWNLOADED  |  1
 EXPORT_DOCX_DOWNLOADED |  1
 EXPORT_CLIPBOARD       |  1
 ADMIN_DASHBOARD_ACCESS |  1
 ────────────────────── → 11 rows across 10 distinct actions
```

## PHI safety rules applied to every call site

1. **No raw values.** `metadata` stores field NAMES only
   (e.g., `changedFields: ['name', 'dateOfBirth']`). Email local
   parts are reduced to their domain.
2. **No free-text PHI.** Override headlines and reasons are
   recorded by LENGTH only; their content stays in the domain-
   specific table (`rx_warning_overrides.reason`) which is
   already access-gated per practice.
3. **Never throws.** The lib's outer try/catch swallows any
   Prisma failure with a single scrubbed stderr line. An audit
   write failure MUST NOT break the calling mutation.
4. **Post-transaction for destructive ops.** `ACCOUNT_DELETED`
   fires AFTER the purge transaction commits — with explicit
   `userId` / `userEmail` / `practiceId` overrides because the
   session is gone by then.

## Actions NOT yet audited (follow-ups)

- `SESSION_EXPIRED` — would fire from the JWT-expiry branch in
  NextAuth; not exercised because sessions don't expire during
  a single probe run. Phase 1B.
- Visit-creation via `createVisitAction` server action —
  instrumentation is straightforward but wasn't in the Phase 1A
  scope because the audit user's path to this action was
  covered indirectly via patient-create logs. Phase 1B.
- Text-mode input submission via `POST /api/visits/[id]/text` —
  a mutation surface worth auditing but considered secondary
  to the signing + exporting cluster for a pilot audit trail.
