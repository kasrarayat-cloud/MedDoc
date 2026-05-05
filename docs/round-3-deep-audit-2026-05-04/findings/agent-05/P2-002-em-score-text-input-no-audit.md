---
id: A05-P2-002
title: Non-critical PHI write paths missing audit rows — em-score POST, text-mode POST
domain: HIPAA-technical-safeguards
severity: P2
agent: 05
---

## Issue

Two PHI-bearing POST endpoints accept raw clinical content in the
request body and act on it without writing an audit row:

1. **`POST /api/visits/[id]/em-score`**
   `apps/transcribe-md/src/app/api/visits/[id]/em-score/route.ts:30-60`
   accepts `{ soapText: string }` (up to 50 000 chars — full SOAP),
   loads the visit, runs the scoring engine. No `logAudit` call. The
   body is the entire SOAP note submitted by the doctor for re-scoring.

2. **`POST /api/visits/[id]/text`**
   `apps/transcribe-md/src/app/api/visits/[id]/text/route.ts:33-100`
   accepts `{ text: string }` (30–5000 chars of doctor-entered free
   text), persists it to `transcribeVisit.rawTextInput`, kicks off
   the pipeline. Equivalent to AUDIO_UPLOADED but for the text-input
   mode. No audit row.

These are PHI writes (the text and SOAP are clinical content). They
sit alongside `dictation/upload` and `upload` which DO emit
`AUDIO_UPLOADED`.

## Evidence

- `app/api/visits/[id]/em-score/route.ts` — no `logAudit` import.
- `app/api/visits/[id]/text/route.ts` — no `logAudit` import.
- Compare with `app/api/visits/[id]/upload/route.ts:208-...` and
  `app/api/visits/[id]/dictation/upload/route.ts:175-...` which both
  emit `AUDIO_UPLOADED`.

## Risk

- §164.312(b) — Audit controls: the audit trail is incomplete for the
  text-input pipeline. If a doctor uploads text-mode notes for a
  patient and the visit is later disputed, there is no row showing
  when the text was uploaded or by whom.
- em-score is more of an analytical re-evaluation than a write, but
  the SOAP body in the request is logged at the LLM-judge boundary
  (AiCall) without being attached to a user-facing audit row.

## Recommended fix

1. Add to `lib/audit.ts` AuditAction union: `'TEXT_INPUT_UPLOADED'`
   and (optionally) `'EM_SCORE_REQUESTED'`.
2. Add `'TEXT_INPUT_UPLOADED'` and `'EM_SCORE_REQUESTED'` to the
   Prisma enum in `schema.prisma:AuditAction` and run a migration.
3. Wire `logAudit({ action: 'TEXT_INPUT_UPLOADED', targetId: visitId,
   targetType: 'TranscribeVisit', metadata: { charCount } })` after
   the prisma.update in text/route.ts. Same shape (size, no values)
   as AUDIO_UPLOADED.
4. em-score: optional — debate whether re-scoring counts as a PHI
   action. If yes, log it; if no, document the decision.
