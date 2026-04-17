# Claude Code Prompt — MedDoc Scribe

> Paste this whole file into Claude Code at the root of `kasrarayat-cloud/MedDoc`. It is tailored to the actual stack of that repo as of the current commit on `main`.

---

## 1. Project Context

I'm adding a new product called **MedDoc Scribe** to my existing **MedDoc Pro** codebase (this repo).

- **MedDoc Pro** = existing CRM/practice automation for doctors (already shipping)
- **MedDoc Scribe** = new AI medical scribe for English-speaking physicians. Doctors can either:
  - Record a visit live and get a real-time transcript, OR
  - Upload an existing mp3/m4a/wav recording and get a transcript

After transcription (live or batch), the same AI pipeline produces a **full clinical output bundle**: SOAP note + ICD-10/CPT codes + e-prescribe-ready prescriptions + referral letters + patient-facing summary.

Scribe must feel like a **separate dashboard** (own subdomain `scribe.<maindomain>`) but share accounts, database, billing, and tenancy with MedDoc Pro.

## 2. Existing Stack (from this repo's `package.json`)

- **Framework:** Next.js 16 (App Router), React 19, TypeScript
- **DB:** PostgreSQL via Prisma 7 + `@prisma/adapter-pg`
- **Auth:** NextAuth v5 (`next-auth@5.0.0-beta.30`) with `@auth/prisma-adapter`
- **Styling:** Tailwind 4
- **State:** Zustand
- **Forms:** React Hook Form + Zod
- **Billing:** Stripe
- **LLM:** OpenAI SDK (`openai@6.x`) — already integrated
- **Doc processing:** `docx`, `pdf-parse`, `mammoth`, `jszip`, `file-saver`
- **Tests:** Playwright (e2e) + Vitest (unit)
- **Evals:** `scripts/eval-doc-editor.ts`, `scripts/eval-clinical-notes.ts` — custom harness already in place
- **Deploy:** Self-hosted Docker + Caddy (`Dockerfile`, `docker-compose.yml`, `Caddyfile`)
- **Multi-tenancy:** Confirmed via `seed:e2e` and `seed:tenancy-fixtures` — every domain entity is scoped to a tenant
- **Agent config:** `.claude/`, `CLAUDE.md`, `AGENTS.md` already present

**Rules:**
- Reuse the existing Prisma schema and tenancy model — do NOT create parallel user/tenant tables
- Reuse NextAuth session — Scribe app gets user identity via the shared DB session
- Extend the existing eval harness for Scribe outputs, don't fork it
- Match existing code style (ESLint config, TSX conventions) — inspect `src/` before writing code

## 3. Repository Restructure → Monorepo

Convert this repo to a **monorepo** using npm workspaces. Target layout:

```
MedDoc/                              (root)
├─ apps/
│  ├─ meddoc-pro/                    (existing app — move current src here)
│  └─ scribe/                        (new app)
├─ packages/
│  ├─ db/                            (Prisma schema + client, shared)
│  ├─ auth/                          (NextAuth config, shared)
│  ├─ types/                         (shared zod schemas, domain types)
│  └─ ai/                            (ModelClient abstraction — OpenAI + Anthropic)
├─ docker-compose.yml                (update: two app services + postgres + redis + minio + caddy)
├─ Caddyfile                         (update: route scribe.domain → scribe app)
├─ package.json                      (workspaces)
└─ turbo.json                        (optional: Turborepo for caching)
```

**First sub-task** before writing any Scribe feature code: propose a migration plan for the monorepo refactor, list every file that moves, and confirm with me before executing.

## 4. Product Positioning (informs design choices)

Competitors: Nuance DAX, Abridge, Suki, DeepScribe, Nabla Copilot, Heidi, Freed.

Our moat:

1. **Deep specialty templates** — 8–10 specialties with real structured prompts, required exam elements, specialty-specific note formats. Not 40 shallow labels.
2. **Native CRM loop-closing** — every signed visit writes follow-up tasks, patient updates, referral drafts, and billing events back into MedDoc Pro. No competitor can do this because none of them own the CRM.
3. **Full output bundle in one pass** — SOAP + ICD-10/CPT + Rx + referrals + patient summary, all reviewed on one screen.

Every design decision must strengthen at least one of these three.

## 5. LLM Strategy (important — we are not single-vendor)

Build `packages/ai/` with a `ModelClient` interface that supports **both OpenAI and Anthropic**. Reason: different outputs have different sweet spots, and you already pay OpenAI for Whisper.

| Purpose | Model | Why |
|---|---|---|
| Batch transcription | **OpenAI Whisper** (`whisper-1` or `gpt-4o-transcribe`) | Already in stack, cheap, good English |
| Real-time transcription | **Deepgram Nova-3 Medical** | Purpose-built medical streaming ASR, lowest latency |
| Transcript cleanup + diarization fix | **Claude Sonnet 4** | Strong at medical context + long context |
| SOAP note generation | **Claude Sonnet 4** | Best at schema-constrained structured output |
| ICD-10 / CPT coding | **Claude Sonnet 4** | Needs strict grounding in transcript evidence |
| Prescription draft | **Claude Sonnet 4** | Safety-critical structured output |
| Referral letter | **GPT-4o** or Claude — configurable | Prose quality |
| Patient summary | **GPT-4o** | Good at simple language |
| Drug interaction check | Rule-based + LLM sanity check | Not LLM alone |

Expose this via env-driven config (`MODEL_FOR_SOAP`, `MODEL_FOR_CODING`, etc.) so we can A/B and switch without code changes. Log every call to an `AiCall` table (tenant, visit id, purpose, model, latency, input tokens, output tokens, prompt hash — **no PHI in this table**).

Add `@anthropic-ai/sdk` as a new dependency alongside the existing `openai` package.

## 6. High-Level Architecture

```
                   ┌──────────────────────────┐
                   │    Browser (Scribe UI)   │
                   └────┬──────────────┬──────┘
                        │              │
         (Real-time)    │              │   (Batch)
        WebSocket       │              │   HTTPS upload
                        ▼              ▼
             ┌──────────────┐   ┌────────────────┐
             │  WS server   │   │  /api/upload   │
             │  (Node, in   │   │  → MinIO (S3)  │
             │  scribe app) │   └───────┬────────┘
             └──────┬───────┘           │
                    │                   │
           ┌────────▼─────────┐  ┌──────▼────────┐
           │ Deepgram Nova-3  │  │ Whisper batch │
           │    Medical       │  │ transcription │
           └────────┬─────────┘  └──────┬────────┘
                    │                   │
                    └─────────┬─────────┘
                              ▼
                    Full transcript persisted
                              │
                              ▼
                ┌─────────────────────────────┐
                │  BullMQ job: finalize_visit │
                │  Worker (own container)     │
                └──────────────┬──────────────┘
                               │ fan-out
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
  Clean + diarize         SOAP note           ICD-10 / CPT
  (Claude Sonnet 4)    (Claude Sonnet 4)   (Claude Sonnet 4)
         │                     │                     │
         ├─────────────────────┼─────────────────────┤
         ▼                     ▼                     ▼
    Rx draft              Referral(s)         Patient summary
  (Claude Sonnet 4)       (GPT-4o)             (GPT-4o)
                               │
                               ▼
               Validate w/ Zod → persist → notify client
                               │
                               ▼
                 Review UI (tabbed outputs, editable)
                               │
                   "Sign" button → internal API →
                     MedDoc Pro: patient update, tasks,
                     billing events, referral inbox
```

## 7. Data Model (additions to existing Prisma schema)

All new tables scoped by `tenantId` (match existing convention).

```prisma
model ScribeVisit {
  id                 String         @id @default(cuid())
  tenantId           String
  clinicianId        String
  patientId          String
  specialtyId        String
  mode               VisitMode      // LIVE | BATCH
  status             VisitStatus
  startedAt          DateTime
  endedAt            DateTime?
  audioObjectKey     String?        // MinIO/S3 key, encrypted
  audioDurationSec   Int?
  sourceFileName     String?
  transcript         ScribeTranscript?
  outputs            ScribeOutput[]
  auditEvents        ScribeAuditEvent[]
  createdAt          DateTime       @default(now())

  @@index([tenantId, clinicianId, createdAt])
  @@index([tenantId, patientId])
}

model ScribeTranscript {
  id          String       @id @default(cuid())
  tenantId    String
  visitId     String       @unique
  visit       ScribeVisit  @relation(fields: [visitId], references: [id], onDelete: Cascade)
  segments    Json         // [{ speaker, startMs, endMs, text, confidence }]
  language    String       @default("en")
  rawFullText String       @db.Text
  provider    String       // "deepgram-nova-3-medical" | "openai-whisper"
}

model ScribeOutput {
  id                 String       @id @default(cuid())
  tenantId           String
  visitId            String
  visit              ScribeVisit  @relation(fields: [visitId], references: [id], onDelete: Cascade)
  type               OutputType
  content            Json
  version            Int          @default(1)
  modelUsed          String
  templateVersion    String
  editedByClinician  Boolean      @default(false)
  signedAt           DateTime?
  signedBy           String?

  @@index([tenantId, visitId, type])
}

model ScribeSpecialtyTemplate {
  id                     String    @id @default(cuid())
  slug                   String    @unique
  displayName            String
  version                String
  systemPrompt           String    @db.Text
  requiredExamElements   Json
  soapSchema             Json
  defaultIcd10Hints      String[]
  defaultFormularyHints  String[]
  active                 Boolean   @default(true)
}

model ScribeAuditEvent {
  id         String       @id @default(cuid())
  tenantId   String
  visitId    String
  actorId    String
  action     String
  diff       Json?
  createdAt  DateTime     @default(now())

  @@index([tenantId, visitId, createdAt])
}

model AiCall {
  id             String   @id @default(cuid())
  tenantId       String
  visitId        String?
  purpose        String   // "cleanup" | "soap" | "coding" | "rx" | "referral" | "summary"
  provider       String   // "openai" | "anthropic" | "deepgram"
  model          String
  promptHash     String
  latencyMs      Int
  inputTokens    Int?
  outputTokens   Int?
  costUsdCents   Int?
  success        Boolean
  errorCode      String?
  createdAt      DateTime @default(now())

  @@index([tenantId, purpose, createdAt])
}

enum VisitMode   { LIVE BATCH }
enum VisitStatus { DRAFT RECORDING UPLOADING PROCESSING READY_FOR_REVIEW SIGNED ERROR }
enum OutputType  { SOAP ICD10_CPT RX REFERRAL PATIENT_SUMMARY }
```

## 8. Specialty Template System (the moat — build carefully)

Priority specialties for launch:

1. Primary Care / Family Medicine
2. Internal Medicine
3. Cardiology
4. Dermatology
5. Psychiatry
6. Pediatrics
7. Orthopedics
8. OB/GYN

Store each as a versioned row in `ScribeSpecialtyTemplate`, seeded from YAML files in `apps/scribe/specialties/*.yaml` via a new script `scripts/seed-specialties.ts`. Template version is stamped onto every `ScribeOutput` so outputs are reproducible.

Each YAML defines: required exam elements, SOAP schema, ICD-10 hints, formulary hints, and a specialty-specific system prompt. Example (Cardiology):

```yaml
slug: cardiology
displayName: Cardiology
version: "1.0.0"
requiredExamElements:
  - cardiac_rhythm
  - murmurs
  - jvd
  - peripheral_edema
  - pulses
soapSchema:
  subjective: [chief_complaint, hpi, ros_cardiac]
  objective: [vitals, cardiac_exam, pulmonary_exam, extremities]
  assessment: [problem_list_with_icd10]
  plan: [diagnostics, medications, follow_up, patient_education]
defaultIcd10Hints:
  - I10       # Essential hypertension
  - I25.10    # Atherosclerotic heart disease
  - I48.91    # Unspecified atrial fibrillation
systemPrompt: |
  You are documenting a cardiology visit. Always explicitly document
  rhythm, murmurs, JVD, edema, and peripheral pulses. If the clinician
  did not mention one of these, flag it in `missing_required_elements`
  rather than inventing findings. Use ACC/AHA preferred terminology.
```

Non-engineers (a clinical advisor) should be able to PR a YAML without touching code.

## 9. Real-Time Mode (live visit)

- Browser captures mic via `MediaRecorder` — 16kHz mono PCM, 250ms chunks
- Opens WebSocket to `scribe.domain.com/api/ws/visit/{visitId}`
- WS server (inside the Scribe Next.js app, Node runtime) proxies to Deepgram streaming API:
  - `model=nova-3-medical`, `diarize=true`, `interim_results=true`, `punctuate=true`, `smart_format=true`
- Interim + final results pushed back to browser live
- Finalized segments appended to Redis list `visit:{id}:transcript` for durability
- On "End visit": flush Redis → Postgres, close Deepgram WS, enqueue `finalize_visit` job
- Also upload the full encoded audio to MinIO for later replay/audit

Latency target: first visible interim token within 800ms of speech.

## 10. Batch Mode (upload)

- UI: drag-drop or file picker; accept `.mp3 .m4a .wav .webm`; max 2 hours per file
- POST `/api/scribe/visits` → creates `ScribeVisit` with `mode=BATCH`, `status=UPLOADING`
- Browser uploads file directly to MinIO via presigned URL (do NOT proxy through app server)
- On upload complete: webhook → `status=PROCESSING` → enqueue `transcribe_batch` job
- Worker chunks audio if >25 min (OpenAI Whisper limit), transcribes each chunk, stitches results, diarizes via a Claude cleanup pass
- Persist transcript → enqueue the same `finalize_visit` job used by real-time mode
- **Single post-processing pipeline for both modes** — keep code paths unified

## 11. AI Extraction Pipeline

`finalize_visit` worker runs these **in parallel** after transcript is ready:

1. **Transcript cleanup + diarization fix** — input: raw transcript + specialty + patient demographics. Output: cleaned transcript JSON with speakers labeled `CLINICIAN | PATIENT | OTHER`. Fixes obvious medical ASR errors.

2. **SOAP note** — input: cleaned transcript + specialty template. Output: JSON matching `soapSchema`. Includes `missing_required_elements[]` if any required exam element wasn't documented — **never invent findings**.

3. **ICD-10 + CPT coding** — input: SOAP + specialty hints. Output: `{ icd10: [{code, description, evidence_quote, confidence}], cpt: [...] }`. Every code must have an evidence quote from the transcript. No ungrounded codes.

4. **Prescription draft** — input: SOAP Plan section + patient's current meds from MedDoc Pro. Output: list of `{ drug, dose, route, frequency, duration, quantity, refills, sig, warnings[] }`. Cross-check drug interactions. Never draft controlled substances unless clinician explicitly stated it.

5. **Referral letters** — one per referral in Plan. Output: `{ specialty, urgency, clinical_summary, reason_for_referral, relevant_history }`.

6. **Patient-facing summary** — 6th-grade reading level, clear next steps.

**Universal rules in every extraction prompt:**
- Never invent findings not supported by transcript
- Flag ambiguities explicitly instead of guessing
- Return `confidence: low|medium|high` per output
- Output must pass Zod schema validation; on first fail, retry once with error appended; on second fail, mark that output `ERROR` and surface to reviewer

Validate every AI response server-side against a Zod schema living in `packages/types/` BEFORE persisting. Never trust model output blindly.

## 12. MedDoc Pro Integration (the loop-closing moat)

Add an internal API inside `apps/meddoc-pro/` with routes under `/api/internal/` protected by a shared service token (rotated, stored in env). Scribe calls these **only after the clinician clicks "Sign & Send"**:

- `POST /api/internal/patients/:id/notes` — attach signed SOAP note
- `POST /api/internal/patients/:id/tasks` — create follow-up tasks from Plan
- `POST /api/internal/patients/:id/billing-events` — log ICD-10/CPT
- `POST /api/internal/referrals` — create referral draft in MedDoc Pro
- `PATCH /api/internal/patients/:id` — update problem list, medication list

Use `packages/types/` to share the request/response shapes between both apps. Type-safe end to end.

## 13. Security & Compliance

- All audio encrypted at rest (MinIO SSE) and in transit (TLS 1.3 via Caddy)
- Audio auto-deleted after configurable retention (default 90 days, clinic-configurable)
- Transcripts retained per tenant's retention policy
- Every read/write to `ScribeVisit` logged to `ScribeAuditEvent`
- **No PHI in logs, Sentry, or analytics.** Add a `redactPhi()` util and use it everywhere structured logs touch model I/O
- Rate limit per clinician (max 1 concurrent live stream)
- MFA inherited from MedDoc Pro
- Separate 15-minute idle session timeout for Scribe app
- Signed BAAs required with OpenAI, Anthropic, Deepgram before production traffic — flag in the README so ops doesn't forget

## 14. Infrastructure Changes (Docker + Caddy)

Update `docker-compose.yml` to add:

```yaml
services:
  postgres:        # existing
  meddoc-pro:      # existing (rename from current 'app' if needed)
  scribe:          # new — apps/scribe
    build: ./apps/scribe
    depends_on: [postgres, redis, minio]
    environment:
      DATABASE_URL: ...
      NEXTAUTH_URL: https://scribe.${DOMAIN}
  scribe-worker:   # new — runs BullMQ worker for finalize_visit, transcribe_batch
    build: ./apps/scribe
    command: ["node", "dist/worker.js"]
    depends_on: [postgres, redis, minio]
  redis:           # new
    image: redis:7-alpine
  minio:           # new — self-hosted S3-compatible object storage
    image: minio/minio
    command: ["server", "/data", "--console-address", ":9001"]
  caddy:           # existing — update Caddyfile
```

Update `Caddyfile`:

```
meddocpro.com {
    reverse_proxy meddoc-pro:3000
}

scribe.meddocpro.com {
    reverse_proxy scribe:3000
}
```

## 15. File Structure for `apps/scribe/`

```
apps/scribe/
├─ src/
│  ├─ app/
│  │  ├─ (dashboard)/
│  │  │  ├─ visits/
│  │  │  │  ├─ page.tsx                    # visit list
│  │  │  │  ├─ new/page.tsx                # patient + specialty + live/batch
│  │  │  │  └─ [id]/
│  │  │  │     ├─ record/page.tsx          # live recording UI
│  │  │  │     ├─ upload/page.tsx          # batch upload UI
│  │  │  │     └─ review/page.tsx          # tabbed output review
│  │  │  ├─ templates/page.tsx             # specialty template admin
│  │  │  └─ settings/page.tsx
│  │  └─ api/
│  │     ├─ ws/visit/[id]/route.ts         # WS handler for real-time
│  │     ├─ visits/route.ts
│  │     ├─ visits/[id]/finalize/route.ts  # enqueue finalize job
│  │     ├─ visits/[id]/sign/route.ts      # sign + push to MedDoc Pro
│  │     └─ uploads/presign/route.ts       # MinIO presigned URL
│  ├─ components/recorder/
│  ├─ components/review/
│  ├─ lib/
│  │  ├─ deepgram.ts
│  │  ├─ whisper.ts
│  │  ├─ minio.ts
│  │  └─ meddoc-client.ts                  # calls MedDoc Pro internal API
│  ├─ server/
│  │  ├─ workers/
│  │  │  ├─ finalize-visit.ts
│  │  │  ├─ transcribe-batch.ts
│  │  │  └─ pipeline/
│  │  │     ├─ cleanup-transcript.ts
│  │  │     ├─ generate-soap.ts
│  │  │     ├─ extract-codes.ts
│  │  │     ├─ draft-rx.ts
│  │  │     ├─ draft-referrals.ts
│  │  │     └─ patient-summary.ts
│  │  └─ prompts/                          # versioned .md prompt files
│  ├─ specialties/                         # YAML templates
│  └─ worker.ts                            # BullMQ worker entry
├─ prisma/                                  # re-export from packages/db
└─ package.json
```

## 16. Evals (extend the existing harness)

You already have `scripts/eval-clinical-notes.ts`. Extend it into `scripts/eval-scribe.ts` with golden datasets:

- `evals/scribe/transcripts/` — input transcripts (real or synthetic)
- `evals/scribe/expected/` — expected SOAP JSON, ICD-10 sets, Rx drafts per transcript
- Scoring: exact match for codes (precision/recall), LLM-as-judge for SOAP narrative, schema validation pass rate, hallucination detector (any SOAP finding with no evidence quote in transcript)

Run evals in CI on every PR that touches `server/prompts/` or `specialties/`.

## 17. Build Order (milestones — do NOT skip ahead)

**Milestone 0 — Monorepo refactor**
- Convert to npm workspaces, move existing app to `apps/meddoc-pro`
- Create `packages/db`, `packages/auth`, `packages/types`, `packages/ai`
- Verify existing app + tests still pass
- Commit, get my approval before moving on

**Milestone 1 — Scribe foundations (no AI yet)**
- Scaffold `apps/scribe` as new Next.js app, shared auth/db
- Prisma migration for `Scribe*` + `AiCall` tables
- Docker + Caddy updates; `scribe.localhost` reachable
- Visit list page + "New visit" page (patient + specialty + mode picker)
- Specialty YAML seed script

**Milestone 2 — Batch mode end to end**
- Upload UI → MinIO presign → Whisper batch transcription
- Persist transcript
- SOAP-only pipeline using Claude Sonnet 4 (single output type)
- Review UI showing SOAP, editable
- Sign writes SOAP to MedDoc Pro via internal API

**Milestone 3 — Real-time mode**
- WS handler + Deepgram streaming integration
- Live transcript UI with diarization
- Share `finalize_visit` job with batch mode

**Milestone 4 — Full output bundle**
- Add ICD-10/CPT extraction
- Add Rx draft (with drug-interaction cross-check against patient meds)
- Add referral drafts
- Add patient-facing summary
- Tabbed review UI

**Milestone 5 — All 8 specialties**
- Author remaining YAML templates with clinical advisor
- Template versioning on outputs
- Specialty-specific eval runs

**Milestone 6 — CRM loop-closing**
- Auto-create tasks in MedDoc Pro from Plan
- Billing event creation
- Referral inbox integration
- Patient record updates

**Milestone 7 — Harden & ship**
- Audit log UI
- Retention settings
- Sentry with PHI scrubbing
- Load test: 10 concurrent live streams per server
- BAA checklist in README

## 18. Coding Standards (match existing repo conventions)

- TypeScript strict mode, no `any`
- Every AI call wrapped in a function that: (1) builds prompt from a versioned template file in `server/prompts/`, (2) validates output with Zod, (3) writes an `AiCall` row with no PHI
- Prompts are version-controlled markdown files, reviewed in PRs
- Feature flags via env for each output type so we can disable e.g. Rx draft if it misbehaves
- Unit tests for every Zod schema with real-world payloads
- Never call Deepgram/OpenAI/Anthropic from client — always server-side
- Match existing ESLint config; run `npm run lint` before commit

## 19. First Task for Claude Code

**Do NOT start building features.** First:

1. Read the existing repo carefully: `CLAUDE.md`, `AGENTS.md`, `package.json`, `prisma/schema.prisma`, `src/` layout, `docker-compose.yml`, `Caddyfile`
2. Read `scripts/eval-clinical-notes.ts` to understand the existing eval pattern
3. Produce a written plan for **Milestone 0 (monorepo refactor) only** — which files move where, new `package.json` workspace config, what breaks, test plan
4. Wait for my explicit approval before executing
5. Do not build ahead of the current milestone
