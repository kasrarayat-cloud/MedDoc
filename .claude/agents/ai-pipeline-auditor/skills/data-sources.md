# Data sources — AI Pipeline Auditor

> **Status: design only.** This document names the tables /
> columns the auditor will read. Schema drift since this doc was
> written is expected; activation includes a fresh schema sanity
> check (Phase 0 in `methodology.md`) before any audit phase
> runs.

The auditor is **read-only** against a fixed set of sources.
Adding a new source is a deliberate change — it must be added
here in the same PR that adds the corresponding audit phase.

## §1 — Primary tables (Postgres, `meddoc-pro-postgres-1`)

### `transcribe_visits`

Per-visit pipeline state. The auditor reads:

| Column | Why |
|---|---|
| `id` | Join key for everything; appears in finding drilldowns |
| `userId` | Per-doctor activation gate (≥3 distinct doctors) |
| `practiceId` | Per-practice rollups when multi-tenant data lands |
| `status` | Auditor only reads READY rows except for failure-rate phase |
| `inputMode` | `audio_upload` vs `voice_dictation` vs `text_notes` — different pipeline shapes |
| `transcriptionProvider` | PR-L follow-up column. NULL on legacy, `deepgram-batch` or `whisper-fallback` on rows post-2026-05-06T08:35Z |
| `audioDurationSec` / `dictationDurationSec` | Cost normalizer (cents per minute) |
| `processingStartedAt` / `processingFinishedAt` | Per-visit latency |
| `processingCostCents` | Per-visit total cost (rolled up from ai_calls) |
| `needsReview` + `reviewReason` | Quality signal — needsReview=true is a soft "doctor must double-check" marker |
| `soapVersion` | Versioning for future SOAP-format audits |
| `audioConfidenceStats` | JSON blob of Deepgram confidence aggregates (median, p95, low-conf %) |
| `confidenceScores` | Per-layer JSON confidence — used to detect "L3/L4/L5 returning low confidence" patterns |
| `deletedAt` | Soft-delete filter — every audit query MUST filter to NULL |

The auditor **never reads**:

- `transcriptText` — free-text PHI
- `transcriptRaw` — discriminated union with embedded transcript
- `soapDraft` / `soapFinal` — free-text PHI
- `rawTextInput` — text-notes-mode raw input
- `audioKey` — never used (the auditor doesn't fetch audio)

### `ai_calls`

Per-call telemetry. Populated by every layer's call into a
provider via `model-client.ts` (or the bypass paths documented
in PR #94).

| Column | Why |
|---|---|
| `id` | Identity |
| `visitId` | Join key; FK-shaped string (cuid) |
| `userId` / `practiceId` | Rollup keys |
| `purpose` | `tm_transcribe`, `tm_speaker_roles`, `tm_entities`, `tm_rx_drafting`, `tm_icd_coding`, `tm_polish`, `tm_embed`, etc. |
| `provider` | `anthropic` / `openai` / `deepgram` |
| `model` | Specific model id (e.g. `claude-sonnet-4-6`, `nova-3-medical`) |
| `promptHash` | SHA-256 prefix of the rendered prompt (for prompt-drift phase) |
| `inputTokens` / `outputTokens` | For token-count anomaly phase |
| `latencyMs` | Per-call latency for p95 rollups |
| `costUsdCents` | Per-call cost for cost-analysis phase |
| `success` | Boolean — failure rate per layer |
| `errorCode` | When `success=false`, the structured error (PR-D + PR-J pre-flight rejections fall into known codes) |
| `errorDetails` | T-M17.1 column — capped 10KB error blob; auditor reads as metadata (length present), never the body |
| `createdAt` | Time series filter |

The auditor **never reads** the prompt body or response body —
only the hash + token counts + cost + latency.

### `audit_logs`

Per-action stream emitted by `apps/transcribe-md/src/lib/audit.ts`.

| Column | Why |
|---|---|
| `id`, `userId`, `practiceId` | Identity + rollup |
| `action` | `AuditAction` enum value — see below |
| `targetType` + `targetId` | What the action acted on (e.g. `TranscribeVisit:<id>`) |
| `metadata` (JSON) | Per-action structured metadata — auditor reads keys NOT free text |
| `success` | Boolean (PR-D + PR-J emit failure rows too) |
| `timestamp` | Time series filter |

The `AuditAction` values the auditor specifically inspects:

- `TRANSCRIPTION_PROVIDER_FALLBACK` (PR-L follow-up) — fallback rate phase
- `SOAP_GENERATED` / `RX_DRAFTED` / `ICD_CODES_GENERATED` — per-layer
  audit-row gap phase
- `PIPELINE_REJECTED_*` (PR-D + PR-J family) — pre-flight rejection
  rate per layer; sustained spike is the input-quality signal
- `RX_DOSE_EXCEEDS_VERIFIED_RANGE` / `RX_CONTRAINDICATION_MATCH` /
  `RX_DRUG_NOT_IN_VERIFIED_DATABASE` — Rx safety triggers, used to
  inspect L4 quality
- `EM_BUMP_APPLIED` / `EM_OVERRIDE_APPLIED` — Phase 5.2 SOAP Coding
  Coach acceptance proxies for the L5 family
- `VISIT_RETRY_BUDGET_EXHAUSTED` — visits that hit the retry cap;
  signal of upstream input or model issue

The auditor **never reads** PHI from `metadata` — every emit
site uses field NAMES not values per `audit.ts` IMPORTANT
comment block. The auditor inspects only the keys that are
documented as PHI-safe (action, target type, layer, provider,
errorCode, durationSec, etc.).

### `api_usage_events`

Per-provider rollups (Phase 5.2 introduced for the prompt-cache
visibility on the SOAP Coding Coach LLM-MDM call).

| Column | Why |
|---|---|
| `provider` | `anthropic` / `openai` / `deepgram` |
| `model` | Match against `ai_calls.model` for reconciliation |
| `eventType` | `request` / `cache-hit` / `cache-miss` |
| `cacheCreationTokens` / `cacheReadTokens` | Anthropic prompt-cache effectiveness |
| `inputTokens` / `outputTokens` | Provider-side accounting |
| `costUsdCents` | Reconciliation against `ai_calls.costUsdCents` |
| `windowStart` / `windowEnd` | Rollup window |

Used for the cost-budget reconciliation phase: "Anthropic billed
$X this week; ai_calls sum is $Y. Are they within 1% of each
other?" — drift is a pricing change, a missing rollup, or a
compute-but-don't-charge bug.

## §2 — Eval-suite results

### Open question: where do eval results land?

As of this design's authoring (2026-05-06), QuillMD has:

- `apps/transcribe-md/scripts/llm-mdm-smoke.ts` — Phase 5.2
  Path-C smoke for the SOAP Coding Coach LLM-MDM call. Runs a
  fixture, asserts shape; no DB persistence. Output is stderr.
- No `eval_runs` table.
- No structured per-layer eval suite for L1/L2/L3/L4/L6.

**Activation prerequisite (captured in `activation-criteria.md`'s
backlog):** wire eval-run telemetry into a queryable shape. Two
options at activation time:

1. New `eval_runs` table — columns: `id`, `evalSuiteName`,
   `runAt`, `passCount`, `failCount`, `passRate`, `metadata`
   (per-fixture results). Populated by a CI job + manual smoke
   runs.
2. Hand-rolled JSON files at `docs/eval-snapshots/<suite>/<UTC>.json`
   read by the auditor. Lower-friction; requires no schema
   change.

The activation-time decision goes here as the chosen approach
+ the migration path. Until then, the eval-coverage phase
(`methodology.md` Phase 3) emits NO_DATA on every layer except
the SOAP Coding Coach Path-C.

## §3 — File-system sources (read-only)

Several signals the auditor reads from disk rather than DB:

- **`packages/ai/src/model-client.ts`** — model-name registry
  for the orphan-assignment detection phase
- **`packages/db/prisma/schema.prisma`** — schema sanity
  baseline. The Phase 0 schema check compares the live DB
  against the Prisma model definitions.
- **Eval fixture files** under `apps/transcribe-md/scripts/`
  + future `packages/ai/eval-suites/` — count + last-modified
  used in eval-staleness phase
- **`docs/POST_MERGE_TODO.md` and `docs/COMPLIANCE_REGISTER.md`**
  — read-only context for finding-drilldown links (the auditor
  surfaces a finding + points the operator at the relevant
  runbook entry where one exists)

## §4 — What the auditor does NOT read

Even though the database has them, the auditor explicitly does
not query:

- **Anything in `apps/meddoc-pro`** (memory #9) — separate app,
  separate scope. CRM-side audit is its own initiative.
- **Free-text PHI fields** in any table — see per-table list
  above.
- **`auth_tokens`, `account_deletions`, `sessions`, `accounts`,
  `verification_tokens`** — auth-side tables; out of pipeline
  scope.
- **`doctor_edit_patterns`** — Phase 14.1 captured-edit-pattern
  table. Could surface useful signal eventually but the embeddings
  + edit text contain PHI; out of scope until the embedding-only
  query path is designed.
- **`drchrono_*` tables** — DrChrono sync surface; CRM scope.

## §5 — Querying conventions

- **Connection.** The auditor connects via the same `DATABASE_URL`
  every other agent uses. No separate read-only role required
  pre-pilot, but creating one is captured in the activation
  backlog (defense-in-depth: even though all queries are SELECT,
  guarantee that via the Postgres role).
- **Time zone.** All timestamps in queries are UTC. Cross-
  timezone reporting is a future concern; pre-pilot the operator
  is in one zone.
- **Batch size.** Default audit window is 7 days, ~hundreds of
  visits. Queries that touch full-history data (orphan detection)
  use `LIMIT 10000` as a hard ceiling — if the result set hits
  the limit, the audit emits a `NO_DATA` informational rather
  than a partial finding.
- **Caching.** No caching pre-activation. The audit run is rare
  enough that re-querying is cheap.
- **No prepared statements.** Each phase emits its query inline
  for readability; future optimization is fine when the audit
  matures.

## §6 — Compliance + PHI handling

The auditor's contract is **structured-only reads**. That contract
is enforced by:

1. The query bodies — every SELECT names its columns explicitly
   (no `SELECT *`); reviewers can see what's being read.
2. The reporting format — findings reference visits by ID; the
   doctor opens the visit in the UI to see content.
3. The activation-time review — before activation, an operator
   reviews every query in `scripts/` to confirm no free-text
   columns are read.

The auditor should never produce a report that, if leaked, would
constitute a HIPAA breach. Visit IDs without content aren't
PHI; the auditor stays on that side of the line.
