# BAA Checklist — third-party data processors

HIPAA §164.308(b) requires a signed Business Associate Agreement (BAA)
with every third party that handles PHI on the covered entity's behalf.
Every row below describes one data processor, what PHI it sees, and the
BAA status. **Do not route real patient data through a processor whose
BAA column is not `YES`.**

## Processor matrix

| Processor | Role | PHI exposure | Where it flows | BAA status |
|---|---|---|---|---|
| **Anthropic** | LLM provider (Claude Sonnet 4.6 + judge) | Cleaned transcript text, SOAP note text, Rx drafts, referral letters, patient summaries | `packages/ai/src/anthropic.ts` → `api.anthropic.com` | ☐ NOT YET |
| **OpenAI** | ASR (`gpt-4o-transcribe` / Whisper) for batch mode + existing voice features in MedDoc Pro | Uploaded audio (batch), transcribed text | `packages/ai/src/openai.ts` → `api.openai.com` | ☐ NOT YET |
| **Deepgram** | Streaming ASR (nova-3-medical) for live visits | Real-time audio frames, transcript text | `packages/ai/src/deepgram.ts` → `api.deepgram.com` | ☐ NOT YET |
| **Sentry (M7)** | Error + performance monitoring | Error messages, breadcrumbs, stack traces. `beforeSend` hook applies `redactPhi()` scrubber (email / phone / SSN masking + >20-word collapse) before events leave the process. **See `apps/*/sentry.*.config.ts` + `packages/ai/src/log.ts`.** | `sentry.io` (or self-hosted Sentry instance) | ☐ NOT YET — required before turning on `SENTRY_DSN_*` env vars |
| **Dropbox** | Document storage (pre-Scribe clinical notes) | Uploaded clinical document files | `apps/meddoc-pro` legacy `Document.dropbox*` fields | ☐ VERIFY — was added pre-M7 |
| **DrChrono** (read-only cache) | External EHR — Patient identifier source-of-truth | Patient name, MRN, chart info (cached locally via `Patient.drChronoId`) | `apps/meddoc-pro/src/lib/data/patients.ts` (no writes from Scribe in M7) | ☐ VERIFY |
| **VPS host (Docker self-hosted)** | Compute + disk for Postgres, MinIO, Redis | Every row of PHI persists on this host | `docker-compose.yml` services: `postgres`, `minio`, `redis`, app containers | ☐ VERIFY — hosting-provider BAA |
| **Postgres (self-hosted)** | Structured PHI store | All patient records, SOAP outputs, transcripts, audit events | Hosted inside the VPS Docker network; not a third party on its own but requires the VPS BAA | N/A (hosted on VPS) |
| **MinIO (self-hosted)** | Object store for audio + generated files | Uploaded audio (batch), live-recorded audio | Inside the VPS Docker network | N/A (hosted on VPS) |
| **Redis (self-hosted)** | BullMQ broker + live-transcript durability list | Ephemeral transcript segments while the live visit is active | Inside the VPS Docker network | N/A (hosted on VPS) |

## Pre-launch checklist

Before flipping any production traffic:

- [ ] Anthropic BAA signed + on file
- [ ] OpenAI BAA signed + on file
- [ ] Deepgram BAA signed + on file
- [ ] Sentry BAA signed (or Sentry disabled via empty DSN)
- [ ] VPS host BAA signed
- [ ] Dropbox BAA confirmed (carried over from MedDoc Pro MVP)
- [ ] DrChrono BAA confirmed (carried over from MedDoc Pro MVP)
- [ ] `.env.production.example` reviewed — no processor is enabled without a BAA
- [ ] Retention job confirmed (see `docs/ROTATION_RUNBOOK.md`): dry-run
      numbers reviewed by clinical advisor for at least one week before
      setting `RETENTION_PURGE_LIVE=true`

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
