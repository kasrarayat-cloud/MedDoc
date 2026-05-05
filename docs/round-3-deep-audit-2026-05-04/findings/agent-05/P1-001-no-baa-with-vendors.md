---
id: A05-P1-001
title: Every PHI-handling vendor BAA still "NOT YET" — pilot blocked at the legal layer
domain: HIPAA-technical-safeguards
severity: P1
agent: 05
---

## Issue

`docs/BAA_CHECKLIST.md` lists nine third-party data processors. The
status column for every PHI-touching processor reads `☐ NOT YET`:

| Vendor | PHI exposure | BAA status |
|---|---|---|
| Anthropic | cleaned transcripts, full SOAP, Rx, referrals, summaries | ☐ NOT YET |
| OpenAI | uploaded audio (gpt-4o-transcribe / Whisper batch path) | ☐ NOT YET |
| Deepgram | live audio frames + transcript text (nova-3-medical) | ☐ NOT YET |
| Sentry | error messages + breadcrumbs (redactPhi-scrubbed but assume PHI possible) | ☐ NOT YET |
| Dropbox | uploaded clinical documents (legacy MedDoc-Pro path) | ☐ VERIFY |
| DrChrono | patient name, MRN cache | ☐ VERIFY |
| VPS host (Zap Hosting) | every PHI byte at rest | ☐ VERIFY |

In addition, **Resend is NOT listed** (`grep -i resend
docs/BAA_CHECKLIST.md` returns one mention in the Sentry row only).
Resend transmits the patient name in the email subject line
(`apps/transcribe-md/src/lib/email.ts:80-83 → "${subject} —
${args.patientName}"`) plus the signed SOAP PDF as an attachment.
That's two distinct PHI items per send.

**Backblaze B2** is similarly absent from the checklist despite Phase
6.2 routing every Postgres dump and every MinIO bucket through it.

The doc explicitly states (line 8):
> Do not route real patient data through a processor whose BAA column
> is not `YES`.

## Evidence

- `docs/BAA_CHECKLIST.md` — full processor matrix.
- `apps/transcribe-md/src/lib/email.ts:80` — `${args.patientName}` in
  Resend subject.
- `apps/transcribe-md/src/lib/email.ts:115-119` — PDF attachment
  containing full SOAP.
- `infra/backup-offsite-sync.sh` + `.env.phase-6.2.template` —
  Backblaze B2 destination for encrypted backups.

## Risk

- §164.308(b) (administrative safeguard but mandatory before §164.312
  technical safeguards are deployed): a covered entity (or
  business-associate-of-covered-entity such as QuillMD on behalf of a
  pilot practice) MUST have a signed BAA with every downstream BA.
  Missing BAAs are the single biggest enforcement risk pre-launch.
- Operational risk: AI vendors retain prompts/responses for ≥30 days
  by default; without the BAA-attached zero-retention agreement, every
  prompt + response sits on Anthropic/OpenAI/Deepgram infrastructure
  with no contractual protection.

## Recommended fix

1. **Sign BAAs** with: Anthropic, OpenAI, Deepgram, Sentry, Resend,
   Backblaze, Zap Hosting (VPS). Negotiate zero-retention add-ons with
   AI vendors.
2. **Update `docs/BAA_CHECKLIST.md`** to add Resend and Backblaze
   rows.
3. **Add a deploy-time gate** that refuses to start the worker /
   email-send / B2 upload paths unless an env var like
   `BAA_VERIFIED_<vendor>=true` is set. Operator pastes the SHA-256 of
   the signed PDF into the env var; the gate logs which BAAs were
   present at startup.
4. **Verify Dropbox + DrChrono BAAs** that were claimed as "carried
   over from MedDoc Pro MVP" — confirm the signed PDFs exist and cover
   the new PHI surface added by transcribe-md.

This is P1 (not P0) only because the operational env vars that would
ship PHI to these vendors are gated by code (e.g.
`isEmailDeliveryEnabled()`, `RESEND_API_KEY` blank → `EmailNot
ConfiguredError`). If pilot turns those keys on without BAAs in
place, this becomes a P0 the day pilot starts.
