---
id: A05-P0-004
title: PHI-read endpoints emit zero audit rows — visit GET, patient GET, list endpoints, SSR pages
domain: HIPAA-technical-safeguards
severity: P0
agent: 05
---

## Issue

§164.312(b) "Audit controls" requires recording "and examin[ing]
activity in information systems that contain or use" ePHI. The schema
comment in `/opt/meddoc-pro/packages/db/prisma/schema.prisma:6`
codifies the policy: "Every sensitive read/write MUST create an
AuditLog row."

Every PHI-mutating endpoint (sign, archive, delete, restore, patient
CRUD, audio upload) does emit a row. **Every PHI-READ endpoint emits
zero rows.** The complete list:

### API GETs (no audit row)

| Endpoint | PHI read | File |
|---|---|---|
| `GET /api/visits/[id]` | full SOAP, transcript, patient name, MRN, DOB | `app/api/visits/[id]/route.ts:67-139` |
| `GET /api/patients/[id]` | patient name, DOB, MRN, insurance, problem list | `app/api/patients/[id]/route.ts:54-95` |
| `GET /api/patients` (list) | every patient name + MRN for the practice | `app/api/patients/route.ts:50-111` |
| `GET /api/visits/[id]/dictation/audio` | streams raw audio bytes | `app/api/visits/[id]/dictation/audio/route.ts:22-70` |
| `GET /api/visits/[id]/text` (POST raw text → no audit) | raw doctor notes | `app/api/visits/[id]/text/route.ts:33-100` |
| `GET /api/visits/[id]/em-score` (POST soapText) | full SOAP body in request | `app/api/visits/[id]/em-score/route.ts:30-60` |

### SSR pages (no audit row)

| Page | PHI read | File |
|---|---|---|
| `/visits/[id]/page.tsx` | full SOAP, transcript, patient demographics | `app/visits/[id]/page.tsx:122-235` (`prisma.transcribeVisit.findUnique`) |
| `/visits/page.tsx` (list) | visit list + patient names | `app/visits/page.tsx:102-123` |
| `/patients/page.tsx` (list) | every patient + visit count | `app/patients/page.tsx:57-90` |
| `/patients/[id]/page.tsx` | patient demographics + visit history | `app/patients/[id]/page.tsx:149-203` |

The `lib/audit.ts` API supports read events — the `VIEWED_PATIENT_LIST`,
`VIEWED_PATIENT_FILE`, `VIEWED_DOCUMENT` enum values exist in
`schema.prisma:73-83` — they just aren't emitted from any of these
call sites.

## Evidence

- `grep -rln "logAudit" apps/transcribe-md/src/` shows ~30 emit-points,
  zero of which are GET handlers on visit/patient resources or SSR
  pages.
- `app/api/visits/[id]/route.ts:67` — `GET = withApiHandler(...)`
  returns visit (full SOAP) with no `logAudit` call in the success
  path.
- `app/visits/[id]/page.tsx:177-235` — `Promise.all([prisma.user.find,
  prisma.transcribeVisit.findUnique{...}])` returns the full SOAP/
  transcript/demographics; renders directly. No audit call.
- Schema comment `schema.prisma:6` explicitly mandates the rule that
  the code violates.

## Risk

- §164.312(b) — primary control. Without read audit rows, an inside
  attacker (compromised staff account, curious SUPER_ADMIN, or any
  ADMIN who is exfiltrating data via the UI) leaves no trace. A breach
  investigation cannot reconstruct who saw which patient's record on
  which day.
- HHS OCR enforcement actions (Memorial Healthcare 2017, $5.5 M; UCLA
  Health 2011, $865 K) directly cited audit-log gaps on PHI views.
- Phase 17 added AUDIO_UPLOADED, DOC_EDITOR_SAVED,
  PHI_EXTRACTED_FROM_VOICE for writes — the read side was missed.

## Recommended fix

1. **Wire `logAudit({ action: 'VIEWED_PATIENT_FILE', targetId, ...})`
   into every handler above.** Treat it as a non-blocking await
   (already the pattern in audit.ts — fire-and-forget).
2. **Page handlers (Server Components):** call `logAudit` AFTER the
   ownership check passes and BEFORE `return`. Add a once-per-render
   guard in middleware so list-page pagination doesn't N+1 the audit
   table.
3. **Add new enum values where the existing ones don't fit:**
   - `VIEWED_VISIT` (separate from `VIEWED_DOCUMENT`)
   - `VIEWED_TRANSCRIPT`
   - `DOWNLOADED_AUDIO` (Phase 17 added `AUDIO_UPLOADED` — symmetric
     read counterpart)
   - `VIEWED_VISIT_LIST`
4. **Add a Round-3 follow-up audit-coverage check** that fails CI if a
   new prisma.transcribe* findUnique/findMany lands in a route or
   page without an adjacent `logAudit`.

This is P0 because read audit is one of the two minimum HIPAA technical
safeguards (§164.312(a)(1) access control + §164.312(b) audit
controls); pre-pilot launch with zero read audit rows is a categorical
failure.
