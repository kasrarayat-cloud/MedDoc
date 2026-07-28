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
| **Anthropic** | LLM provider — `claude-opus-4-8` (L3/L4/L5/L7c-Rx + note-format parse + synthetic preview) + `claude-sonnet-4-6` (L2/L6/L7a/L7b/L7d/L7e); env-overridable via `TRANSCRIBE_MD_CLINICAL_MODEL` (default unchanged) | Cleaned transcript text, SOAP note text, Rx drafts, referral letters, patient summaries (note-format **preview** sends a FIXED SYNTHETIC demo transcript only — no PHI) | `packages/ai/src/anthropic.ts` → `api.anthropic.com` | [trust.anthropic.com](https://trust.anthropic.com/) → "Request a BAA" form. Available on Tier-2+ usage; lower tiers require Anthropic Sales engagement. | ☐ NOT YET |
| **OpenAI** | ASR fallback (`whisper-1`) — **GATED, DISABLED BY DEFAULT** (2026-06-10 kill-switch, audit 4.2). Would fire on a Deepgram failure (5xx/408/429/network/timeout, audio ≤ 25 MB) ONLY if `TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED=true`. Unset/false → a Deepgram failure fails the visit into the retryable DLQ, never OpenAI. | Raw patient audio, transcribed text — **only if the flag is enabled** | `packages/ai/src/whisper-batch.ts` (via `transcribe.ts` orchestrator + worker L1) → `api.openai.com` `POST /v1/audio/transcriptions` | [openai.com/policies/business-associate-agreement](https://openai.com/policies/business-associate-agreement) — self-serve for orgs on Enterprise / Scale tiers via the Compliance API portal. | ☐ NOT REQUIRED while the fallback is disabled (current prod state). **Sign + file BEFORE setting the enable flag.** |
| **Deepgram** | **PRIMARY batch ASR** (nova-3-medical) | Uploaded + dictation audio bytes, transcript text | `packages/ai/src/deepgram-batch.ts` (HTTPS `POST /v1/listen`) → `api.deepgram.com` | [deepgram.com/security/hipaa](https://deepgram.com/security/hipaa) → "Request HIPAA BAA" form. Nova-3 Medical is HIPAA-eligible by default; BAA must be on file before any nova-3-medical call carries identifiable audio. | ☐ NOT YET |
| **Resend** | Transactional email delivery (visit-note notification + auth emails) | ⚠️ **NO PHI as of 2026-07-28 — pending deploy.** The visit email previously carried the patient name in the subject and the signed SOAP note as a PDF attachment. It now sends a GENERIC subject, no patient details, no attachment, and an authenticated portal link the doctor opens over their own session (`lib/email.ts`). Auth emails were always link/text-only. | `apps/transcribe-md/src/lib/email.ts` → `api.resend.com` | [resend.com/legal](https://resend.com/legal) → request a HIPAA BAA via Resend support. | ☑ **NOT REQUIRED once the change is live** — see "Resend" under Processor-specific notes for the reasoning and the one residual judgement call. **Re-classify to NOT YET the moment any PHI is put back on this path.** |
| **Sentry (M7)** | Error + performance monitoring | Error messages, breadcrumbs, stack traces. `beforeSend` hook applies `redactPhi()` scrubber (email / phone / SSN masking + >20-word collapse) before events leave the process. **See `apps/*/sentry.*.config.ts` + `packages/ai/src/log.ts`.** | `sentry.io` (or self-hosted Sentry instance) | [sentry.io/legal/baa](https://sentry.io/legal/baa) — Business plan or above. | ☐ NOT YET — required before turning on `SENTRY_DSN_*` env vars; currently DSN unset in prod containers (SDK no-ops) |
| **Dropbox** | Document storage (pre-Scribe clinical notes) | Uploaded clinical document files | `apps/meddoc-pro` legacy `Document.dropbox*` fields | [help.dropbox.com](https://help.dropbox.com/security/hipaa-baa) — Business / Advanced / Enterprise tier required. | ☐ VERIFY — was added pre-M7; meddoc-pro is decommissioned per memory + POST_MERGE_TODO §21, so BAA is only relevant if any meddoc-pro Document data still references Dropbox keys |
| **DrChrono** (read-only cache) | External EHR — Patient identifier source-of-truth | Patient name, MRN, chart info (cached locally via `Patient.drChronoId`) | `apps/meddoc-pro/src/lib/data/patients.ts` (no writes from Scribe in M7) | DrChrono partnerships — contact `partnerships@drchrono.com` to request BAA. | ☐ VERIFY — meddoc-pro decommissioned; verify before flipping production |
| **Backblaze B2** | Offsite encrypted backup target (`infra/backup-offsite-sync.sh`) | Encrypted backup blobs (Postgres dumps + MinIO objects, all already at-rest encrypted client-side) | Backblaze B2 bucket — see `.env` `B2_*` keys | [backblaze.com/baa-request](https://www.backblaze.com/baa-request) — Business B2 tier; standard BAA published. | ☐ NOT YET — discovered as a gap in the 2026-05-10 shadow audit (HIPAA_FINDING_006) |
| **Zap Hosting (VPS, Docker self-hosted)** | Compute + disk for Postgres, MinIO, Redis, app containers | Every row of PHI persists on this host (postgres data on a LUKS dm-crypt volume at rest, Phase 6.1) | `docker-compose.yml` services: `postgres`, `minio`, `redis`, app containers | Production host is **Zap Hosting** (per `HIPAA_COMPLIANCE.md` + `COMPLIANCE_REGISTER.md`) — request via Zap Hosting support → "HIPAA BAA". If Zap won't sign, migrate to a HIPAA-eligible host (DigitalOcean $500/mo BAA, or AWS HIPAA-eligible services). | ☐ VERIFY — hosting-provider BAA |
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

                       ┌──────────┐
                       │ RESEND   │ ◄─── Visit-export email:
                       │ (email)  │      patient name (subject) +
                       └──────────┘      signed SOAP note PDF (attachment)
```

**PHI tags by vendor:**

| Vendor | Sees |
|---|---|
| **Deepgram** | Live audio frames; transcript text |
| **OpenAI** | Batch audio chunks; transcribed text |
| **Anthropic** | Transcript text; generated SOAP / Rx / ICD-10 / CPT / referrals / patient summaries. **No audio.** (Note-format preview sends a fixed synthetic demo transcript only — no PHI.) |
| **Resend** | Visit-export email: patient name in subject + signed SOAP note PDF attachment. Auth emails link/text-only (no PHI). |
| **Sentry** | Error messages + stack traces — scrubbed by `redactPhi()` before send. `tracesSampleRate=0` + `replaysSessionSampleRate=0` keep performance + session replay off. |
| **Backblaze B2** | Encrypted backup blobs (already at-rest encrypted client-side). |
| **VPS host** | Every row of PHI; physical/virtual disk hosting Postgres + MinIO + Redis. |
| **DrChrono** | Patient identifiers (read-only cache via `Patient.drChronoId`). Decommissioned with meddoc-pro per POST_MERGE_TODO §21; verify before flipping any production traffic. |
| **Dropbox** | Clinical document files. Decommissioned with meddoc-pro per POST_MERGE_TODO §21. |

## Pre-launch checklist

Before flipping any production traffic — each row maps to a `Status`
column above + a date stamp once countersigned:

- [ ] Anthropic BAA `COUNTERSIGNED <YYYY-MM-DD>`; copy at `secrets/baa/anthropic-<date>.pdf`
- [ ] OpenAI BAA — **NOT REQUIRED for pilot** while the Whisper fallback is disabled (default; 2026-06-10 kill-switch). Required ONLY before setting `TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED=true` → then `COUNTERSIGNED <YYYY-MM-DD>`; copy at `secrets/baa/openai-<date>.pdf`
- [ ] Deepgram BAA `COUNTERSIGNED <YYYY-MM-DD>`; copy at `secrets/baa/deepgram-<date>.pdf`
- [ ] Resend BAA `COUNTERSIGNED <YYYY-MM-DD>`; copy at `secrets/baa/resend-<date>.pdf` (visit-export email transports the signed SOAP PDF + patient-named subject — PHI, not metadata-only)
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
- **Model (as of 2026-06-10):** prod = `claude-opus-4-8` (L3/L4/L5/L7c-Rx
  + note-format parse + synthetic preview) + `claude-sonnet-4-6`
  (L2/L6/L7a/L7b/L7d/L7e), now env-overridable via
  `TRANSCRIBE_MD_CLINICAL_MODEL` (default unchanged → prod = Opus).
  **Fable 5 was evaluated 2026-06-10 (PR #292) and REJECTED for prod:**
  the global flip is a NO-GO (Fable rejects forced `tool_choice`, which
  breaks the note-format parse + structured PHI-scan), and Fable 5 is a
  Mythos-class *Covered Model* requiring **mandatory 30-day retention
  with NO zero-data-retention option** — incompatible with the
  zero-retention posture above. Fable routes through this same
  `api.anthropic.com` BAA scope (no new processor) but changes the
  retention footprint — re-assess here before ever enabling it. See
  `docs/qa-reports/fable5-flip-baa-gate-20260610T144302Z.md`.

### OpenAI
- In `apps/transcribe-md`, OpenAI is used ONLY as a **Whisper ASR fallback**
  (`whisper-1`, `packages/ai/src/whisper-batch.ts`), reached via the
  `transcribe()` orchestrator (`transcribe.ts`) from worker L1.
- **KILL-SWITCH (2026-06-10, audit 4.2): the cross-provider fallback is
  FAIL-CLOSED / disabled by default.** It fires ONLY when
  `TRANSCRIBE_MD_WHISPER_FALLBACK_ENABLED=true`. With the flag unset (current
  prod state), a Deepgram failure that WOULD have been fallback-eligible
  (5xx / 408 / 429 / network / timeout, audio ≤ 25 MB) instead throws
  `CrossProviderFallbackDisabledError` → the visit fails into the retryable
  BullMQ DLQ (surfaced on `/admin/queues`) + a `TRANSCRIPTION_PROVIDER_FALLBACK`
  audit row (`suppressed:true`) is emitted. **Raw patient audio never reaches
  OpenAI unless the flag is explicitly enabled.** `isPermanent4xxError` still
  treats 408/429 as recoverable for the eligibility check; the gate sits after
  it. Do NOT set the flag until an OpenAI BAA is countersigned + filed.
- When enabled, a transcript produced by the fallback is tagged
  `provider:'whisper-fallback'`. Same `AiCall` logging pattern.
- (Stale refs removed: `gpt-4o-transcribe`, `packages/ai/src/openai.ts`,
  and "MedDoc Pro Realtime voice" — that file does not exist in the
  live app; MedDoc Pro is decommissioned. Any OpenAI *embeddings* /
  edit-tracking is a Doc-Editor concern, not the transcribe-md PHI path;
  the 2026-06-10 code sweep found no embeddings egress in `packages/ai`.)
- OpenAI retains request data per their policy unless a zero-retention
  agreement is in place.

### Deepgram
- **Batch** transcription in the live app: `packages/ai/src/deepgram-batch.ts`
  → HTTPS `POST https://api.deepgram.com/v1/listen?model=nova-3-medical`.
  Audio is uploaded/dictated, stored in MinIO, then batch-transcribed by
  worker L1. (Stale: there is no live/streaming Deepgram path, no
  `deepgram.ts`, and no `wss://` / scribe-ws sidecar in
  `apps/transcribe-md` — that described the decommissioned scribe surface.)
- Nova-3 Medical is a HIPAA-eligible model; BAA is required before
  sending identifiable audio.

### Sentry
- DSNs are per-app: `SENTRY_DSN_MEDDOC_PRO`, `SENTRY_DSN_SCRIBE`.
  Empty = SDK no-ops (useful in dev / CI).
- `beforeSend` applies `redactPhi()`: email / phone / SSN masking +
  free-text >20-word collapse. Every Sentry event is scrubbed before
  leaving the process.
- `tracesSampleRate: 0` and `replaysSessionSampleRate: 0` disable
  performance + session replay until an explicit budget + scrubbing
  review is done.


---

# BAA facts memo — 2026-07-28

Research only. No vendor was contacted, no account was created, no migration was
executed. Every row ends in exactly ONE owner action for Kasra, because a memo
that ends in three actions ends in none.

> ⚠️ **Vendor terms move.** Every claim below is dated and sourced. Confirm with
> the vendor before relying on it — this memo narrows the question, it does not
> answer it on the vendor's behalf.

## Deepgram — PRIMARY ASR, receives raw patient audio

**A BAA exists and is obtainable.** Deepgram's own compliance page states
*"Deepgram is considered a Business Associate as defined by the US HIPAA
legislation"* and, for customers who qualify as a Covered Entity, *"Deepgram may
qualify as a business associate."* The stated route is plain: *"To secure a BAA
(Business Associate Agreement) with Deepgram, please contact us."*

**No plan or tier requirement is documented.** The page conditions eligibility on
the customer qualifying as a Covered Entity, not on a pricing tier. Do not assume
an enterprise upgrade is required until Deepgram says so.

**One caveat found, and it matters for scheduling.** A public Deepgram
discussion thread reports customers submitting the BAA request form and receiving
no response across multiple attempts. Treat the form as best-effort and expect to
need a named human. Budget calendar time, not effort.

Supporting facts already in QuillMD's favour: nova-3-medical is HIPAA-eligible by
default, the default configuration is zero-retention after processing, and
Deepgram holds SOC 2 Type II.

> **OWNER ACTION (Kasra):** Request the Deepgram BAA — and if the web form is
> silent for five business days, escalate to a named sales/compliance contact
> rather than resubmitting.

## The VPS host — every row of PHI lives here

**The finding is not "unknown". It is "structurally unlikely", and that changes
the shape of the decision.**

The host is **ZAP-Hosting GmbH & Co. KG**, a German company. Third-party GDPR
guidance treats it as a processor requiring an **Art. 28 GDPR
Auftragsverarbeitungsvertrag (AVV)** — the European instrument. Nothing in the
public material mentions HIPAA, a BAA, or US healthcare compliance at all. A
German provider signing a US HIPAA BAA is unusual: an AVV and a BAA are different
instruments under different statutes, and having one says nothing about
willingness to sign the other.

So the realistic planning assumption is **migration, not signature** — while
still asking, because asking is free.

### Realistic PHI-hosting options (options only — nothing executed)

| Option | Shape | What it costs beyond money |
|---|---|---|
| **DigitalOcean** | Signs a BAA. ePHI restricted to Covered Products (Droplets, Kubernetes, Spaces, Volumes, Load Balancers, Firewalls, VPC, Monitoring, Backups) and **requires Standard or Premium Support** alongside the executed BAA. New customers via Sales; existing via Support. | Closest to today's shape — Docker Compose on Droplets is nearly a lift-and-shift. Support tier is a recurring line item. |
| **AWS / GCP / Azure** | All sign BAAs, with a defined list of HIPAA-eligible services. | Most capable, least similar to the current single-box deployment. A real re-architecture, not a move. |
| **Managed HIPAA platforms** (Aptible and similar) | BAA plus opinionated controls out of the box. | Highest per-month cost, lowest compliance effort. Sensible if the operator stays a team of one. |

### Scope class of a migration

**LARGE**, and it is the honest word. Not because any single step is hard, but
because the inventory is: Postgres (the PHI store, on a LUKS volume), MinIO
(patient audio), Redis, four app containers, the Gotenberg sidecar, host nginx
holding TLS for five hostnames plus **four unrelated co-tenant projects on the
same box**, cron-driven backups, and DNS. The co-tenants are the part that makes
this a project rather than a weekend: QuillMD does not own that host alone, and
the isolation rule in AGENTS.md exists precisely because breaking a neighbour is
easy.

It also has a natural sequencing constraint: it should happen **before** a pilot
doctor's real data lands, not after. Migrating an empty system is an engineering
task; migrating a populated one is an engineering task plus a PHI-handling
exercise plus a downtime window.

> **OWNER ACTION (Kasra):** Ask ZAP-Hosting directly whether they will sign a US
> HIPAA BAA — and treat a "no" or a non-answer as the expected outcome that
> starts the DigitalOcean conversation.

## Resend — reclassified, pending this shipping

**Post-mitigation, Resend no longer receives PHI**, and the reasoning is recorded
here so the next reader does not have to re-derive it.

What changed (`apps/transcribe-md/src/lib/email.ts`):

- the subject is **generic and identical for every visit and every patient** —
  it no longer carries the patient name
- **no attachment**: the signed note is not sent
- no patient name, date of birth, MRN, or note text in either body
- the doctor gets a link and downloads from QuillMD over their **own
  authenticated session**

The function signature is the guard: `sendVisitPdfEmail` no longer *accepts* a
`pdfBuffer` or a `patientName`. A future caller cannot leak them by forgetting,
because there is no parameter to forget — both call sites failed to compile until
they stopped passing PHI.

Proven by `src/lib/__tests__/email-no-phi.test.ts`, which runs the **real message
builder** with only the transport mocked, sweeps **every** sender that could
reference a visit, and is negative-controlled: restoring the old
patient-name-in-subject plus attachment turns it red.

### The one residual judgement call, stated rather than buried

The portal link contains an opaque visit id (a cuid). **That is a record
locator, not a patient identifier** — it names nobody, reveals nothing on its
own, and is useless without an authenticated session. It is the same class of
value as the message-id Resend already assigns to every email it handles.

Claiming the payload contains "no identifiers of any kind" would be false, so
this memo does not claim it. The claim is narrower and true: **no patient
identifier and no clinical content.** If a reviewer disagrees with that line, the
fix is small — drop the deep link for a bare `/visits` link — and it should be
made deliberately rather than discovered in an audit.

> **OWNER ACTION (Kasra):** Confirm you accept the record-locator reasoning
> above; if you would rather send no visit id at all, say so and the deep link
> becomes a bare `/visits` link in one edit.

## What this memo does NOT resolve

The Anthropic BAA countersign is excluded by standing instruction and tracked
elsewhere. Backblaze B2 (offsite backup) remains **☐ NOT YET** and is unchanged
by any of the above — it is the same blocker as the open `h16-offsite-backup`
finding seen from the other side.
