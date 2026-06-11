# Phase 1 — Inventory (raw candidate findings)

**Audit:** Comprehensive code/logic/data quality audit (0→100)
**Generated:** 2026-05-14T03:04:26Z
**Audit pass:** Phase 1 only — candidates, unprioritized. Triage in Phase 2.

## Inventory format

```
DOMAIN | severity_hint | file:line | one-line headline
```

`severity_hint` is the *sub-agent's* guess at intake; Lead re-triages in Phase 2 (notably: 3 P0_candidates from the code-quality-auditor sub-agent are downgraded to P1 in Phase 2 after ground-truth verification against production data).

## Findings (66 total)

### Domain F — Code-pattern + reliability (51, from code-quality-auditor sub-agent + verification)

```
RELIABILITY | P1 (verified)        | apps/transcribe-md/src/actions/soap.ts:130 | signVisitAction has NO logAudit emission (the route-path /api/visits/[id]/sign/route.ts:269 IS audited — but the action-path duplicates the surface and skips it)
RELIABILITY | P1 (verified)        | apps/transcribe-md/src/actions/soap.ts:42  | saveSoapDraftAction mutates clinical note with no audit_logs row (DoctorEditPattern table captures the edit pattern; audit_logs row missing for the EDITED_NOTE action enum that exists but is never written)
RELIABILITY | P1                    | apps/transcribe-md/src/actions/soap.ts:197 | reassignSpeakerAction has no audit emission (mutates speakerMap affecting clinical attribution)
DATA_INTEGRITY | P1 (verified)     | apps/transcribe-md/src/worker/layers/07b-cpt-coding.ts:219,229 | Two sequential prisma.updates (needsReview + cptCodes) NOT in $transaction; worker crash leaves partial state. BullMQ retry mitigates.
DATA_INTEGRITY | P2                | apps/transcribe-md/src/worker.ts:565-635 | Status transitions DRAFTING→CRITIQUING→POLISHING each issued as standalone updates
DATA_INTEGRITY | P2                | apps/transcribe-md/src/worker/layers/01-transcribe.ts:219,279 | transcript update + keytermsApplied update separate (second is fire-and-forget — audit-attribution drift surface)
TYPE_SAFETY    | P2                | apps/transcribe-md/src/worker.ts:599 | resumeState.critique cast to CritiqueReport without Zod re-parse — schema drift between deploys flows through
TYPE_SAFETY    | P2                | apps/transcribe-md/src/worker.ts:449,527,546 | resumeState.entities cast as ExtractedEntities without re-parse
TYPE_SAFETY    | P2                | apps/transcribe-md/src/worker/layers/01-transcribe.ts:240 | audioStats! non-null assertion inside lowConfFlag branch
TYPE_SAFETY    | P2                | apps/transcribe-md/src/worker/layers/03-extract-entities.ts:58 | factWithEvidence() returns object via `as any` cast
TYPE_SAFETY    | P2                | packages/ai/src/api-usage.ts:109 | (prisma as any).apiUsageEvent.create — usage-tracking writes
TYPE_SAFETY    | P2                | apps/transcribe-md/src/lib/audit.ts:232 | prisma.auditLog.create({ data: entry as any })
TYPE_SAFETY    | P2                | apps/transcribe-md/src/app/admin/users/_lib/users-data.ts (5×) | (prisma as any) / (prisma.user as any) in admin users data layer
TYPE_SAFETY    | P2                | apps/transcribe-md/src/app/admin/hipaa/_lib/hipaa-data.ts:25 | (prisma as any).hipaaFinding.findMany + rows: any[]
TYPE_SAFETY    | P2                | apps/transcribe-md/src/app/api/admin/hipaa/[id]/reopen/route.ts:27,45 | (prisma as any) on hipaaFinding mutations
TYPE_SAFETY    | P2                | apps/transcribe-md/src/lib/auth.ts:67 | (session?.user as any)?.sessionId
TYPE_SAFETY    | P2                | apps/transcribe-md/src/lib/nextauth.ts (3×) | (user as any).suspendedAt / .softDeletedAt / .practiceId
TYPE_SAFETY    | P2                | apps/transcribe-md/src/lib/admin-api-gate.ts (3×) | admin gate uses 3 any-casts on session.user
ASYNC          | P1                | apps/transcribe-md/src/actions/soap.ts:177 | void captureEditPattern(...) — fire-and-forget without try/catch wrapper at call site
ASYNC          | P2                | apps/transcribe-md/src/worker.ts:1034 | void prisma.user.update(...) fire-and-forget (lastSeen?) — Prisma errors silently dropped
ASYNC          | P2                | apps/transcribe-md/src/worker.ts:923 | void logAudit({...}) VISIT_AUTOMATION_INCOMPLETE — fire-and-forget audit row
ASYNC          | P2                | apps/transcribe-md/src/worker/layers/01-transcribe.ts:277 | void IIFE with empty catch{} — keytermsApplied write silently dropped
ASYNC          | P2                | apps/transcribe-md/src/worker/layers/01b-transcribe-dictation.ts:210 | Same IIFE pattern duplicated from 01-transcribe.ts
ASYNC          | P3                | apps/transcribe-md/src/worker.ts:1345 | setInterval(() => void tick(), …).unref() — sync throw in tick() silently dropped
RELIABILITY    | P1                | packages/ai/src/deepgram-batch.ts:237 | Deepgram batch has no inline retry — non-L1 callers get zero retries
RELIABILITY    | P1                | packages/ai/src/whisper-batch.ts:189 | Whisper fallback no retry — transient OpenAI 5xx → hard FAILED
RELIABILITY    | P1                | apps/transcribe-md/src/worker/layers/01-transcribe.ts:170 | L1 retry backoff has no jitter — coordinated thunder-herd risk
RELIABILITY    | P1                | apps/transcribe-md/src/worker/layers/01b-transcribe-dictation.ts:135 | Same no-jitter backoff as L1 (duplicate)
RELIABILITY    | P1                | packages/ai/src/anthropic.ts:292 | JSON.parse(unfenced) on final attempt throws if malformed
RELIABILITY    | P2                | apps/transcribe-md/src/lib/em-coding/llm-mdm.ts (3×) | Three nested JSON.parse fallbacks; callers must guard null
RELIABILITY    | P2                | apps/transcribe-md/src/worker.ts:807 | await judgeWarmPromise after Promise.allSettled adds latency
RELIABILITY    | P2                | apps/transcribe-md/src/worker.ts:905 | findUnique().catch(() => null) — DB error indistinguishable from clean nulls → spurious incomplete flag
WORKER         | P1                | apps/transcribe-md/src/worker.ts:234-252 | loadResumeState defensive return; L1/L2 updates run before re-check → P2025 on deleted visit
WORKER         | P1                | apps/transcribe-md/src/worker.ts:944 | confidenceScores cast as plain object — Prisma JSON silent coerce
WORKER         | P1                | apps/transcribe-md/src/worker.ts:984-1000 | shouldFailNow category=='permanent' bypasses retries — categorizeError false-positive risk
WORKER         | P1                | apps/transcribe-md/src/worker.ts:1008-1027 | Nested .catch() inside outer catch swallows the FAILED-write failure — visit stuck non-terminal
WORKER         | P2                | apps/transcribe-md/src/worker.ts:293 | Visit not-found throws raw Error → P2025 on subsequent update masks original error
WORKER         | P2                | apps/transcribe-md/src/worker.ts:189-208 | clearAutomationColumn Record map — undocumented runtime fall-through when new automation key added
PIPELINE       | P1                | apps/transcribe-md/src/worker/layers/04-generate-soap.ts:214 | L4 SOAP output NOT Zod-validated — malformed/empty flows into L5 unchecked
PIPELINE       | P1                | apps/transcribe-md/src/worker/layers/06-polish.ts:74-89 | L6 polish: same raw-text path — soapFinal written without S/O/A/P structural validation
PIPELINE       | P1                | apps/transcribe-md/src/worker/layers/02-speaker-roles.ts:100-115 | Speaker-role fallback writes default map then returns — schema validation skipped
PIPELINE       | P2                | apps/transcribe-md/src/worker/layers/03-extract-entities.ts:68-79 | liftStringToFact preprocess only top-level — nested array string fails silently
PIPELINE       | P2                | apps/transcribe-md/src/worker/layers/05-self-critique.ts:181 | L5 writes critique JSON — verify modelClient.complete enforces Zod
CODE_PATTERN   | P2                | apps/transcribe-md/src/worker.ts:1086-1090 | (err as unknown as { humanReason?: unknown }) — multi-cast smell; needs type-guard
CODE_PATTERN   | P2                | apps/transcribe-md/src/worker.ts (10×) | console.error inside worker.ts mixed with log.info — inconsistent logging shape
CODE_PATTERN   | P2                | apps/transcribe-md/src/worker.ts:300-311 | Per-mode validation if/else chain — better as discriminated-union switch with assertNever
CODE_PATTERN   | P2                | apps/transcribe-md/src/worker.ts:198-204 | clearAutomationColumn duplicates literal column names — needs Prisma model field constants
CODE_PATTERN   | P2                | apps/transcribe-md/src/lib/email.ts (4×) | (result as any)?.data / .error — Resend SDK should be typed
CODE_PATTERN   | P3                | apps/transcribe-md/src/worker/layers/{01-transcribe.ts,01b-transcribe-dictation.ts} | Massive duplication between L1 and L1b (retry block, audioStats, keyterms write, cast)
RELIABILITY    | P2                | packages/ai/src/anthropic.ts:201 | z.toJSONSchema() cast as Anthropic.Messages.Tool.InputSchema — drift surface
TYPE_SAFETY    | P2                | packages/ai/src/whisper-batch.ts:197 | Whisper response cast `as unknown as WhisperBatchResponse` — no runtime shape check
DATA_INTEGRITY | P2                | apps/transcribe-md/src/worker/layers/07c-rx-drafting.ts:348 | input.patient.allergies ?? [] — null allergies → no allergy context to Rx safety prompt
DATA_INTEGRITY | P2                | apps/transcribe-md/src/actions/soap.ts:230-247 | reassignSpeakerAction non-atomic read-modify-write on speakerMap
DATA_INTEGRITY | P2                | apps/transcribe-md/src/worker.ts:335 | confidenceScores cleared to null on attempt N — prior valid signal lost on layer-1 failure
WORKER         | P2                | apps/transcribe-md/src/worker.ts:267-291 | findUnique with no row-version — race between findUnique and FAILED-state update
RELIABILITY    | P2                | apps/transcribe-md/src/worker.ts:1396 | enqueueDlq only fires on attempts-exhausted — Redis blip during enqueue silently misses DLQ
```

### Domain B — Database schema (8, Lead direct review)

```
DB             | P2                | packages/db/prisma/schema.prisma:702-731 | AccountDeletion TODO(T-M16.3+): scheduled purge of rows where purgeAt < now() not implemented; rows accumulate indefinitely
DB             | P2                | packages/db/prisma/schema.prisma — TranscribeVisit | No direct practiceId column; multi-tenant isolation depends on every query joining via user → practice → small footgun surface
DB             | P2                | packages/db/prisma/schema.prisma — VisitDelivery, DoctorEditPattern, RxWarningOverride, ThreatResolution, HipaaFinding | Models without practiceId — verify each is scoped via parent relation in every query
DB             | P2                | packages/db/prisma/schema.prisma — Document, Appointment | No direct practiceId — scoped via patient.practiceId; needs query-level enforcement
DB             | P2                | packages/db/prisma/schema.prisma:audit_logs | userId column has NO FK constraint to users.id (deletion handling lives in app code via userEmailSnapshot)
DB             | P3                | packages/db/prisma/migrations/* | No migration rollback artifacts (Prisma migrate is forward-only by design) — production-recovery story relies on point-in-time backup
DB             | P2                | Migration: 20260412234252_add_multi_tenancy | ALTER COLUMN practiceId SET NOT NULL on users/patients/audit_logs/session_logs/api_usage — irreversible if backfill fails (no rollback path)
DB             | P3                | Migration: ALTER TYPE ENUM ADD VALUE pattern | Several migrations use this — works in Postgres but cannot be wrapped in transaction; if a deploy fails partway, partial enum state lands
```

### Domain G — Performance / observability (5, Lead direct review)

```
PERF           | P2                | postgres config | `log_min_duration_statement = -1` — slow-query logging DISABLED; no observability for slow queries in production
PERF           | P2                | postgres extensions | pg_stat_statements extension NOT installed — no query-level latency telemetry available without re-enabling
PERF           | P2                | Worker concurrency | concurrency=2 hardcoded; with prod RAM at 11GB available, could safely go higher; no metric on queue depth-vs-concurrency tuning
PERF           | P3                | Bundle analysis | No record of running `next build --analyze`; client-bundle drift untracked
PERF           | P3                | Docker build cache | 156.9 GB on host; 125.6 GB reclaimable (preflight skill threshold > 30 GB triggers prune)
```

### Domain E — Frontend / UX (8, Lead direct review)

```
FRONTEND       | P2                | apps/transcribe-md/src/app/{patients,visits,visits/new}/ — no loading.tsx | 3 high-traffic routes without Next.js route-level loading state; only dashboard/settings/visits/[id] have loading.tsx
FRONTEND       | P2                | apps/transcribe-md/src/app/{patients,admin/*,signup,forgot-password}/ — no error.tsx | 5+ routes without Next.js error boundary; uncaught errors → unstyled crash page
FRONTEND       | P2                | apps/transcribe-md/src/app/admin/*/_components/*.client.tsx (5×) | `.then((r) => r.json())` without `.catch` on admin client-side fetches — silent failure on auth-expired / network blip
FRONTEND       | P2                | Component scale | 147 .tsx files across components+app; 34 mention empty-state copy; 8 components explicit loading state — large delta suggests inconsistent loading-state implementation
FRONTEND       | P3                | apps/transcribe-md/src/app/visits/[id]/rx-tab.tsx:294 | .then(() => ...) without .catch on a click-handler-derived promise
FRONTEND       | P3                | apps/transcribe-md/src/components/command-palette.tsx:65 | .then((rows) => setRecent(rows)) without .catch — recent items silently miss on failure
A11Y           | P2                | apps/transcribe-md/src/components/visits/CodingRail.tsx + adjacent | Limited aria-live coverage (4 components total mention sr-only/aria-live/role=alert); visit-record + patient-picker (critical paths) not in list
A11Y           | P3                | All routes                 | No screen-reader flow audit recorded; axe-core in CI catches structural a11y but not semantic flow (heading order, focus management on modal close, etc.)
```

### Domain J — Test coverage (4, Lead direct review)

```
TESTS          | P1                | apps/transcribe-md/src/worker/layers/{02,03,04,05,06}.ts | Pipeline layers L2-L6 have NO sibling unit tests in __tests__/ — only L1 has low-conf-l1.test.ts (heavy mock); L7a fallback + L7c rx-drafting tested
TESTS          | P2                | apps/transcribe-md/vitest.config.* | Vitest coverage NOT configured (no c8/v8/istanbul); coverage thresholds unenforced
TESTS          | P2                | apps/transcribe-md unit-test ratio | 67 .test.ts + 5 .test.tsx = 72 tests vs 185 source TS files (~39% colocation); ratio not the whole story but no critical-path coverage matrix
TESTS          | P2                | apps/meddoc-pro test:all | Decommissioned echo (`"echo '[meddoc-pro] CRM decommissioned…'"`) — root test:all chains through it, so transcribe-md vitest tests are NOT in CI today (confirmed gap; documented in PR-4 closure §F.4)
```

### Domain L — Operational / ops (5, Lead direct review)

```
OPS            | P2                | Sentry instrumentation     | Only 1 explicit `Sentry.captureException` call in source; rely on Next.js auto-instrumentation + worker captureWorkerException helper — verify worker-layer errors actually flow through (e.g., L4 model timeouts at line 214 are caught higher up; no captureWorkerException at point-of-failure)
OPS            | P2                | postgres backup            | sidecar container `meddoc-pro-postgres-backup-1` has been "Up 9 days (unhealthy)" — verify backups are actually completing despite the unhealthy flag
OPS            | P2                | Heap monitoring            | No `process.memoryUsage()` polling in worker; long-running BullMQ worker process — leak would manifest as gradual swap pressure with no alert
OPS            | P3                | Alerting                   | No alert rules visible for: queue depth growing > N, DLQ size > 0, postgres connections approaching max, /api/health 5xx rate
OPS            | P3                | Runbook                    | Production-recovery procedure for "worker crashed with 50 visits queued" not documented in repo (oral knowledge with Kasra)
```

### Other (1)

```
DOMAIN_F (extra) | P2 | Several apps/transcribe-md/src/lib/* files | Two TODO/FIXME comments total in production code (1 in rate-limit.ts, 1 in retention-sweep.ts) — both have ticket references; not problematic
```

---

## Summary count by severity_hint

| Severity_hint | Count | Notes |
|---|---|---|
| P0_candidate (sub-agent) | 3 | All downgraded to P1 in Phase 2 after ground-truth verification |
| P1 confirmed/promoted | 17 | Including the 3 downgraded from P0 |
| P2 | 35 | |
| P3 | 11 | |
| **Total** | **66** | well below the 200-finding stop threshold |

Phase 2 triage: see the final report `comprehensive-audit-20260514T030426Z.md`.
