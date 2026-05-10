# BAA Checklist — third-party data processors

HIPAA §164.308(b) requires a signed Business Associate Agreement (BAA)
with every third party that handles PHI on the covered entity's behalf.
Every row below describes one data processor, what PHI it sees, and the
BAA status. **Do not route real patient data through a processor whose
BAA column is not `COUNTERSIGNED`.**

## How to use this doc (Kasra's signing flow)

This is the **operator's signing checklist**. For each processor:

1. **Click the Portal link** below to reach the vendor's BAA-request flow.
2. **Update the Status column** to one of:
   - `☐ NOT YET` — no BAA, no PHI must flow.
   - `☐ REQUESTED <YYYY-MM-DD>` — outreach sent; PHI still must not flow.
   - `☐ NEGOTIATING <YYYY-MM-DD>` — vendor returned redlines; review.
   - `☐ COUNTERSIGNED <YYYY-MM-DD>` — fully executed BAA on file. PHI may flow.
   - `☐ NOT REQUIRED` — vendor doesn't see PHI in this product line.
3. **Drop a copy of the executed BAA in `secrets/baa/<vendor>-<date>.pdf`**
   (host-only, never committed) for the audit trail. Confirm
   `secrets/` is `.gitignore`d — yes, it is per `.gitignore:86`.
4. **Tick the matching `Pre-launch checklist` checkbox** below when
   the column flips to `COUNTERSIGNED`.

## Processor matrix

| Processor | Role | PHI exposure | Where it flows | Portal | BAA status |
|---|---|---|---|---|---|
| **Anthropic** | LLM provider (Claude Sonnet 4.6 + Opus 4.7 + judge) | Cleaned transcript text, SOAP note text, Rx drafts, referral letters, patient summaries | `packages/ai/src/anthropic.ts` → `api.anthropic.com` | [trust.anthropic.com](https://trust.anthropic.com/) → "Request a BAA" form. Available on Tier-2+ usage; lower tiers require Anthropic Sales engagement. | ☐ NOT YET |
| **OpenAI** | ASR (`gpt-4o-transcribe` / Whisper) for batch mode + existing voice features in MedDoc Pro | Uploaded audio (batch), transcribed text | `packages/ai/src/openai.ts` → `api.openai.com` | [openai.com/policies/business-associate-agreement](https://openai.com/policies/business-associate-agreement) — self-serve for orgs on Enterprise / Scale tiers via the Compliance API portal. | ☐ NOT YET |
| **Deepgram** | Streaming ASR (nova-3-medical) for live visits | Real-time audio frames, transcript text | `packages/ai/src/deepgram.ts` → `api.deepgram.com` | [deepgram.com/security/hipaa](https://deepgram.com/security/hipaa) → "Request HIPAA BAA" form. Nova-3 Medical is HIPAA-eligible by default; BAA must be on file before any nova-3-medical call carries identifiable audio. | ☐ NOT YET |
| **Sentry (M7)** | Error + performance monitoring | Error messages, breadcrumbs, stack traces. `beforeSend` hook applies `redactPhi()` scrubber (email / phone / SSN masking + >20-word collapse) before events leave the process. **See `apps/*/sentry.*.config.ts` + `packages/ai/src/log.ts`.** | `sentry.io` (or self-hosted Sentry instance) | [sentry.io/legal/baa](https://sentry.io/legal/baa) — Business plan or above. | ☐ NOT YET — required before turning on `SENTRY_DSN_*` env vars |
| **Dropbox** | Document storage (pre-Scribe clinical notes) | Uploaded clinical document files | `apps/meddoc-pro` legacy `Document.dropbox*` fields | [help.dropbox.com](https://help.dropbox.com/security/hipaa-baa) — Business / Advanced / Enterprise tier required. | ☐ VERIFY — was added pre-M7; meddoc-pro is decommissioned per memory + POST_MERGE_TODO §21, so BAA is only relevant if any meddoc-pro Document data still references Dropbox keys |
| **DrChrono** (read-only cache) | External EHR — Patient identifier source-of-truth | Patient name, MRN, chart info (cached locally via `Patient.drChronoId`) | `apps/meddoc-pro/src/lib/data/patients.ts` (no writes from Scribe in M7) | DrChrono partnerships — contact `partnerships@drchrono.com` to request BAA. | ☐ VERIFY — meddoc-pro decommissioned; verify before flipping production |
| **Backblaze B2** | Offsite encrypted backup target (`infra/backup-offsite-sync.sh`) | Encrypted backup blobs (Postgres dumps + MinIO objects, all already at-rest encrypted client-side) | Backblaze B2 bucket — see `.env` `B2_*` keys | [backblaze.com/baa-request](https://www.backblaze.com/baa-request) — Business B2 tier; standard BAA published. | ☐ NOT YET — discovered as a gap in the 2026-05-10 shadow audit (HIPAA_FINDING_006) |
| **VPS host (Docker self-hosted)** | Compute + disk for Postgres, MinIO, Redis | Every row of PHI persists on this host | `docker-compose.yml` services: `postgres`, `minio`, `redis`, app containers | Vendor-specific. Hetzner: [hetzner.com/legal/data-privacy](https://www.hetzner.com/legal/data-privacy) (German DPA, no formal HIPAA BAA — assess fit). DigitalOcean: [digitalocean.com/security/hipaa](https://www.digitalocean.com/security/hipaa) ($500/mo BAA fee). AWS: [aws.amazon.com/compliance/hipaa-compliance](https://aws.amazon.com/compliance/hipaa-compliance) (free, but only for HIPAA-eligible services). | ☐ VERIFY — hosting-provider BAA |
| **Postgres (self-hosted)** | Structured PHI store | All patient records, SOAP outputs, transcripts, audit events | Hosted inside the VPS Docker network; not a third party on its own but requires the VPS BAA | N/A (covered by VPS host BAA) | N/A (hosted on VPS) |
| **MinIO (self-hosted)** | Object store for audio + generated files | Uploaded audio (batch), live-recorded audio | Inside the VPS Docker network | N/A (covered by VPS host BAA) | N/A (hosted on VPS) |
| **Redis (self-hosted)** | BullMQ broker + live-transcript durability list | Ephemeral transcript segments while the live visit is active | Inside the VPS Docker network | N/A (covered by VPS host BAA) | N/A (hosted on VPS) |

## Subprocessor flow diagram (which vendor sees which PHI)

```
                       Doctor's browser
                              │
                              │ HTTPS (Caddy)
                              ▼
                  ┌─────────────────────┐
                  │  apps/transcribe-md │
                  └──────────┬──────────┘
                             │
        ┌────────────────────┼─────────────────────┐
        │                    │                     │
        ▼                    ▼                     ▼
   ┌─────────┐         ┌──────────┐        ┌────────────────┐
   │ Postgres│         │  MinIO   │        │     Redis      │
   │ (PHI)   │         │ (audio)  │        │ (BullMQ)       │
   └─────────┘         └────┬─────┘        └───────┬────────┘
                            │                      │
                            │                      │ jobId enqueue
                            │                      ▼
                            │              ┌──────────────┐
                            │              │ Worker (L1-7)│
                            │              └──┬───────────┘
                            │                 │
                            ▼                 │
                       ┌──────────┐           │
                       │ DEEPGRAM │ ◄─────────┤  Live audio
                       │ nova-3-  │           │  (live visits)
                       │ medical  │           │
                       └──────────┘           │
                                              │
                       ┌──────────┐           │
                       │ OPENAI   │ ◄─────────┤  Audio chunks
                       │ Whisper  │           │  (batch fallback)
                       └──────────┘           │
                                              │
                       ┌──────────┐           │
                       │ANTHROPIC │ ◄─────────┤  Transcript text →
                       │ Claude   │           │  SOAP/Rx/codes
                       └──────────┘           │
                                              │
                       ┌──────────┐           ▼
                       │ SENTRY   │ ◄─── Error events
                       └──────────┘      (redactPhi'd)

                       ┌──────────┐
                       │BACKBLAZE │ ◄─── Encrypted backup blobs
                       │   B2     │      (nightly via
                       └──────────┘      infra/backup-offsite-sync.sh)
```

**PHI tags by vendor:**

| Vendor | Sees |
|---|---|
| **Deepgram** | Live audio frames; transcript text |
| **OpenAI** | Batch audio chunks; transcribed text |
| **Anthropic** | Transcript text; generated SOAP / Rx / ICD-10 / CPT / referrals / patient summaries. **No audio.** |
| **Sentry** | Error messages + stack traces — scrubbed by `redactPhi()` before send. `tracesSampleRate=0` + `replaysSessionSampleRate=0` keep performance + session replay off. |
| **Backblaze B2** | Encrypted backup blobs (already at-rest encrypted client-side). |
| **VPS host** | Every row of PHI; physical/virtual disk hosting Postgres + MinIO + Redis. |
| **DrChrono** | Patient identifiers (read-only cache via `Patient.drChronoId`). Decommissioned with meddoc-pro per POST_MERGE_TODO §21; verify before flipping any production traffic. |
| **Dropbox** | Clinical document files. Decommissioned with meddoc-pro per POST_MERGE_TODO §21. |

## Pre-launch checklist

Before flipping any production traffic — each row maps to a `Status`
column above + a date stamp once countersigned:

- [ ] Anthropic BAA `COUNTERSIGNED <YYYY-MM-DD>`; copy at `secrets/baa/anthropic-<date>.pdf`
- [ ] OpenAI BAA `COUNTERSIGNED <YYYY-MM-DD>`; copy at `secrets/baa/openai-<date>.pdf`
- [ ] Deepgram BAA `COUNTERSIGNED <YYYY-MM-DD>`; copy at `secrets/baa/deepgram-<date>.pdf`
- [ ] Sentry BAA `COUNTERSIGNED <YYYY-MM-DD>` (or Sentry disabled via empty DSN); copy at `secrets/baa/sentry-<date>.pdf`
- [ ] Backblaze B2 BAA `COUNTERSIGNED <YYYY-MM-DD>`; copy at `secrets/baa/backblaze-<date>.pdf`
- [ ] VPS host BAA `COUNTERSIGNED <YYYY-MM-DD>` (or written confirmation that vendor's standard DPA covers HIPAA scope); copy at `secrets/baa/vps-host-<date>.pdf`
- [ ] Dropbox BAA — `NOT REQUIRED` (meddoc-pro decommissioned) OR `COUNTERSIGNED <YYYY-MM-DD>` if any document data is still referenced
- [ ] DrChrono BAA — `NOT REQUIRED` (meddoc-pro decommissioned) OR `COUNTERSIGNED <YYYY-MM-DD>` if patient cache is still being read
- [ ] `.env.production.example` reviewed — no processor is enabled without a `COUNTERSIGNED` BAA
- [ ] Retention job confirmed (see `docs/ROTATION_RUNBOOK.md`): dry-run
      numbers reviewed by clinical advisor for at least one week before
      setting `RETENTION_PURGE_LIVE=true`
- [ ] MFA enrollment complete on both SUPER_ADMIN accounts (closes
      shadow-audit HIPAA_FINDING_001 — see PR #193 for the
      enrollment flow)

## When a processor is added

Every new third party that will see PHI must:

1. Be added to the matrix above with its PHI exposure + data flow path.
2. Have a signed BAA (or be disabled by default via an env var, e.g.
   empty DSN for Sentry).
3. Have `redactPhi()` applied at every log + telemetry boundary that
   touches the processor (see `packages/ai/src/log.ts` and the
   `sentry.*.config.ts` files for the canonical pattern).
4. Appear on the retention matrix — does PHI sent to this processor
   need independent purge workflows?

## Processor-specific notes

### Anthropic
- All prompts go via `packages/ai/src/anthropic.ts`. `AiCall` table
  stores prompt hashes (SHA-256) — NEVER raw prompt content. Model name,
  input/output token counts, latency, and success flag are the only
  fields persisted.
- Retention: prompts + responses live on Anthropic's side per their
  data retention policy. Request zero-retention via the Anthropic
  console for your organisation if patient data will flow.

### OpenAI
- Used for batch audio (`gpt-4o-transcribe`) and the existing Realtime
  voice features in MedDoc Pro. Same `AiCall` logging pattern.
- Audio is sent per-chunk (25 min max per spec §10). OpenAI retains
  request data per their policy unless a zero-retention agreement is
  in place.

### Deepgram
- Live streaming only. Uses `@deepgram/sdk` v4 → WebSocket to
  `wss://api.deepgram.com/v1/listen`.
- Nova-3 Medical is a HIPAA-eligible model; BAA is required before
  sending identifiable audio.
- The scribe-ws sidecar proxies browser frames to Deepgram; no
  recording is retained client-side beyond the MinIO upload.

### Sentry
- DSNs are per-app: `SENTRY_DSN_MEDDOC_PRO`, `SENTRY_DSN_SCRIBE`.
  Empty = SDK no-ops (useful in dev / CI).
- `beforeSend` applies `redactPhi()`: email / phone / SSN masking +
  free-text >20-word collapse. Every Sentry event is scrubbed before
  leaving the process.
- `tracesSampleRate: 0` and `replaysSessionSampleRate: 0` disable
  performance + session replay until an explicit budget + scrubbing
  review is done.
