---
id: A05-P3-001
title: BAA_CHECKLIST.md is stale — Resend, Backblaze, and Phase 6.2 not represented
domain: HIPAA-technical-safeguards
severity: P3
agent: 05
---

## Issue

`docs/BAA_CHECKLIST.md` was authored before two PHI-shipping vendors
were wired into the codebase:

1. **Resend** — the email-export path
   (`apps/transcribe-md/src/lib/email.ts`,
   `apps/transcribe-md/src/app/api/visits/[id]/export/email/route.ts`)
   transmits patient name in the subject and the signed SOAP PDF as
   attachment. The doc mentions "resend" only inside the Sentry row
   description, never as its own row.

2. **Backblaze B2** — Phase 6.2 (`infra/backup-offsite-sync.sh`,
   `infra/minio-offsite-sync.sh`, `.env.phase-6.2.template`) routes
   every Postgres dump and every MinIO bucket to B2. Not in the matrix.

The "Pre-launch checklist" sub-section reflects the same gap (no
Resend or Backblaze rows).

The checklist also lists "OpenAI" as the ASR for batch mode. Code
inspection of `apps/transcribe-md/src/worker/layers/01-transcribe.ts`
+ `01b-transcribe-dictation.ts` should be cross-checked to confirm
that's still accurate after T-M11/T-M14 — the audit didn't dive into
the ASR-vendor selection logic.

## Evidence

- `docs/BAA_CHECKLIST.md` — full processor matrix.
- `apps/transcribe-md/src/lib/email.ts` — Resend integration.
- `infra/backup-offsite-sync.sh` + `.env.phase-6.2.template` —
  Backblaze.

## Risk

- Documentation hygiene only; the upstream P1-001 finding captures
  the operational risk (no signed BAAs).

## Recommended fix

1. Add rows for **Resend** and **Backblaze** to the processor matrix
   with PHI exposure + flow path.
2. Update the "Pre-launch checklist" sub-section to include those
   two rows.
3. Cross-reference each new processor in
   `docs/HIPAA_COMPLIANCE.md` so the engineering and compliance
   docs agree.
4. Re-confirm OpenAI vs Deepgram routing in the worker layers; if
   Whisper is gone, drop OpenAI from the matrix.
