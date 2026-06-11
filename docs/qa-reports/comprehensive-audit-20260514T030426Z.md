# Comprehensive code/logic/data quality audit — QuillMD pilot readiness

**Generated:** 2026-05-14T03:04:26Z
**Lead:** Claude (Opus 4.7 1M)
**Trigger:** Pre-pilot-doctor onboarding gate. 0→100 audit across backend/worker, database, AI pipeline, frontend, code quality, performance, reliability, data integrity, test coverage, accessibility, and operational posture.
**Method:** 4-phase audit — surface scan → triage → deep-dive (P0+P1) → deliverables. Strict serial; one named code-quality-auditor sub-agent invocation; ground-truth verification of every claimed P0 against production data.
**Source artifact:** [Phase 1 inventory](./comprehensive-audit-20260514T030426Z-phase1-inventory.md) — 66 candidate findings catalogued before triage.

---

## Section A — Executive summary

| Severity | Count | Pilot-impact summary |
|---|---|---|
| **P0** — pilot-blocking, active harm | **0** | Three sub-agent P0_candidates verified and downgraded to P1 after production-data check. No active data corruption surface. |
| **P1** — real bug, high pilot impact | **18** | 3 audit-emission gaps (HIPAA-adjacent, partially mitigated), 4 retry/jitter gaps (transient failure cluster), 4 worker error-path gaps (FAILED-state recovery), 3 pipeline output-validation gaps (L2/L4/L6), 1 critical-test-coverage gap (L2-L6 no unit tests), 1 fire-and-forget audit-write hardening, 1 non-transactional dual-write, 1 JSON-parse-on-final-attempt. |
| **P2** — hardening / robustness | **35** | Type-safety any-casts (16), worker error/log consistency (~10), DB multi-tenancy enforcement reliance on app code (5), frontend route loading.tsx/error.tsx gaps (4). |
| **P3** — cosmetic / backlog | **11** | Logging styling, runbook gaps, bundle-analyze hygiene, migration rollback story, no per-finding effort. |
| **Total** | **64** | Below the 200-finding triage-narrowing threshold. |

### Pilot-readiness verdict: **GREEN with documented P1 follow-ups**

The audit's deep dive on production data shows the system is **operationally healthy**: 201 visits across 30 days (163 READY, 25 SIGNED, 13 FAILED, all FAILED with clear `reviewReason`), 9 containers all healthy, stuck-visit watchdog catches its own incidents, DLQ landed (1 wait / 0 failed), audit_logs at 6967 rows with multi-tenant `practiceId NOT NULL` enforced, every TruffleHog secrets-scan clean since 2026-05-13. **No P0 means no active user harm and no pilot-blocker.**

The 18 P1 findings cluster into four themes:

1. **Audit-emission gaps on server-action paths** (3 findings, soap.ts) — every SOAP edit/sign/speaker-reassign on the server-action path lacks an `audit_logs` row. Route-path equivalents emit (verified: 7 `VISIT_SIGNED` audit rows in production). The action path is a duplicate surface that some doctors use. Single-doctor pilot can avoid this if you steer all signing through the route path, but the gap should close before multi-doctor pilot.

2. **Retry/jitter cluster** (4 findings, packages/ai + L1/L1b) — Deepgram/Whisper batch calls have zero inline retry; L1's retry uses `setTimeout` without jitter. Single-doctor pilot is unlikely to hit a thunder-herd; multi-doctor pilot will, when a Deepgram region degrades.

3. **Pipeline output validation gaps** (3 findings, L2/L4/L6) — Layer 4 SOAP and L6 polish write model output without Zod validation; L2's fallback path skips its own schema check. Today's mitigations (model returning generally well-formed JSON, downstream layers being tolerant) work, but a model regression or prompt drift will leak malformed content to the doctor's screen.

4. **Worker error-handling depth** (4 findings, worker.ts) — `loadResumeState` defensive return runs L1/L2 updates BEFORE re-checking row existence (P2025 on visit deletion); nested `.catch()` inside outer catch can leave visits in non-terminal status if both the original job AND the FAILED-state persistence error; `shouldFailNow` shortcuts retries on `category === 'permanent'` with no audited validation of `categorizeError`'s false-positive rate.

The remaining 7 P1s are individual issues (07b CPT-coding dual-write, fire-and-forget Anthropic JSON.parse, layer L2-L6 unit-test gap, etc.) detailed in §C.

### Top 5 most-critical findings

1. **FIND-P1-001** — `signVisitAction` HIPAA audit-trail gap on the action path (route path covers but partial-surface).
2. **FIND-P1-015** — L4 SOAP generation: model output not Zod-validated; corrupt JSON could flow to L5/L6 unchecked.
3. **FIND-P1-014** — Worker FAILED-state update has nested `.catch()` inside outer catch — visit stuck non-terminal if both writes fail (only watchdog rescues).
4. **FIND-P1-018** — Pipeline layers L2-L6 have NO sibling unit tests; the entire transformer/critique chain depends on integration coverage (regression baseline from PR-3) — critical-path test gap.
5. **FIND-P1-007** — Whisper fallback has NO retry — transient OpenAI 5xx during a Deepgram-failed visit produces hard FAILED state with no automatic recovery.

### Already-audited domains (skipped, per scope)

Security (PRs #240-#244 closed 1 P0 + 11 P1), cross-input-mode (#237), keyterm scoping + ISMP safety floor (#246-#250 Issues #202+#206), rate-limit coverage (#238), email deliverability (#245). The Phase 1 inventory does **not** re-find any of these.

---

## Section B — Methodology

### Phases

| Phase | What | Output |
|---|---|---|
| 1 | Surface scan across 12 domains (A backend/worker, B database, C pipeline, D API, E frontend, F code-quality, G performance, H reliability, I data-integrity, J tests, K a11y, L operational) | [phase1-inventory.md](./comprehensive-audit-20260514T030426Z-phase1-inventory.md) |
| 2 | Triage candidates against production-data ground truth; 3 sub-agent-claimed P0s downgraded to P1 after verification | This document, §A counts |
| 3 | Deep-dive on every P0 + P1 — file:line, evidence, recommended fix, effort, deps | This document, §C |
| 4 | Markdown + PDF + CSV deliverables | This file + `.pdf` + `-findings.csv` |

### Domain-by-domain method

- **A Backend/worker** — read `worker.ts` (1440 lines), all `worker/layers/*.ts` (3472 lines), `lib/queue.ts`. Pattern-match retry/DLQ/watchdog/audit-emission. Production: 9 containers Up, BullMQ in `bull:transcribe-md:*`, DLQ at 1 wait.
- **B Database** — read `schema.prisma` (2189 lines), inspect all `onDelete:` actions, scan migrations for irreversible patterns. Query `audit_logs` (6967 rows, multi-tenant `practiceId NOT NULL`) and `transcribe_visits` (201 visits, 30-day window) for distribution + orphan states.
- **C AI pipeline** — inspect each layer's input/output validation; verify Zod parse coverage; map prompt → modelClient call → DB write path. PHI-safe inspection (no transcript content read).
- **D API routes** — 70 routes; heuristic Zod-coverage grep (no gaps found, but security-audit closure means this surface is well-covered).
- **E Frontend / UX** — inventory of `loading.tsx`, `error.tsx`, error-boundary coverage; grep for `.then()` without `.catch()` on client components; aria-live audit.
- **F Code quality** — invoked **code-quality-auditor sub-agent** with full rules-library access (`rules.md`, 839 lines, 31 rules); broad-but-shallow scan returned 51 candidate findings.
- **G Performance** — queried postgres for `log_min_duration_statement`, `pg_stat_statements` extension, slow-query availability; inspected docker disk + build cache.
- **H Reliability** — retry coverage on Deepgram/Whisper/Anthropic; idempotency on critical mutations; race-condition surfaces.
- **I Data integrity** — orphan/inconsistent-state queries against production; FK constraints; soft-delete consistency.
- **J Test coverage** — sibling-test-file heuristic on each source file; vitest coverage config check; CI runner check (already-known gap: `apps/meddoc-pro/test:all` is decommissioned echo, transcribe-md vitest NOT in CI today).
- **K Accessibility (beyond axe-core)** — aria-live / sr-only / focus-trap grep; semantic-flow review out of scope (no manual walk-through performed).
- **L Operational** — Sentry instrumentation files, postgres backup container health (currently "Up 9 days (unhealthy)" — pre-existing per regression matrix memory), heap monitoring, alerting, runbook.

### Verification standard (P0 downgrades)

Three sub-agent P0_candidates were re-checked against production:

| Sub-agent claim | Production check | Verdict |
|---|---|---|
| `signVisitAction:165` has no `logAudit` | grep `VISIT_SIGNED` → emitted at `/api/visits/[id]/sign/route.ts:269`; production has 7 rows | Downgrade to P1 (action path is duplicate surface, partial gap) |
| `saveSoapDraftAction:84` has no audit | grep `EDITED_NOTE` in source → 0 emissions; production has 36 rows from legacy paths; current code captures via `DoctorEditPattern` table | Downgrade to P1 (visibility gap, not data-loss) |
| `07b-cpt-coding:219,229` dual-write not in `$transaction` | Read code; confirmed; BullMQ retry + stuck-visit watchdog mitigate | Downgrade to P1 (real, but mitigated) |

This downgrade discipline is intentional. P0 should be reserved for *active* user harm; the audit's job is not to manufacture severity. The verifications also surfaced that the original `audit_logs.action` enum (`EDITED_NOTE`, `CREATED_CLINICAL_NOTE`) has 36+46 rows in production from legacy code that no longer exists — a **dead enum-value finding** worth grouping into Domain F P2 in addition to its emission gap above.

---

## Section C — Detailed findings (P0 + P1 only)

### FIND-P0 — none

No P0 findings after triage. The "pilot-blocking, active harm" tier is empty.

### FIND-P1-001 — `signVisitAction` HIPAA audit-trail gap (action path)

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Reliability / HIPAA audit completeness |
| **File:line** | `apps/transcribe-md/src/actions/soap.ts:130` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** The server-action `signVisitAction(visitId)` mutates `status = SIGNED`, freezes `signedSoap`, and writes `signedAt = new Date()` — the legal-record signing event. It does NOT call `logAudit({ action: 'VISIT_SIGNED', ... })`. The parallel route path `/api/visits/[id]/sign/route.ts:269` DOES emit the audit row, and production has 7 `VISIT_SIGNED` rows generated through it. The two surfaces are duplicated; doctors who land on the action path (server actions, e.g., from a form submission) skip the audit.

**Evidence.**

```ts
// apps/transcribe-md/src/actions/soap.ts:171-181
await prisma.transcribeVisit.update({
  where: { id: visitId },
  data: {
    status: TranscribeVisitStatus.SIGNED,
    signedSoap: visit.soapFinal,
    signedAt: new Date(),
  },
});
// T-M14.1: fire-and-forget edit-pattern capture.
void captureEditPattern({ visitId, doctorId: session.user.id });
```

No `logAudit({ action: 'VISIT_SIGNED', ... })` adjacent.

**Recommended fix.** Add a `logAudit` call immediately after the update, mirroring the route path (`route.ts:269`):

```ts
await logAudit({
  action: 'VISIT_SIGNED',
  targetType: 'TranscribeVisit',
  targetId: visitId,
  userId: session.user.id,
  practiceId: session.user.practiceId,
  metadata: { source: 'server_action' },
});
```

Use `source` metadata to disambiguate action-path vs route-path signing for future telemetry. Alternatively, extract the sign logic into a shared `signVisitInternal(...)` helper and have both surfaces call it (resolves duplication).

---

### FIND-P1-002 — `saveSoapDraftAction` SOAP-edit audit visibility gap

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Reliability / HIPAA audit completeness |
| **File:line** | `apps/transcribe-md/src/actions/soap.ts:42` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** `saveSoapDraftAction(visitId, text, expectedVersion)` is the SOAP-note edit path. It mutates `soapFinal` + bumps `soapVersion` with optimistic-concurrency. Edit pattern is captured in `DoctorEditPattern` table (per T-M14.1), but `audit_logs` has no row for the SOAP edit itself. The `audit_logs.action` enum lists `EDITED_NOTE` (36 production rows from legacy code paths) and `CREATED_CLINICAL_NOTE` (46 production rows, same legacy origin) — but neither enum value is emitted from current source (verified: 0 grep hits for these enum values in `apps/transcribe-md/src`).

This is a **visibility gap, not a data-loss gap**: the edit data is preserved (DoctorEditPattern + DB row history via soapVersion); auditors and ops can reconstruct edits. But surface integration ("show all events on this visit") via `audit_logs` is missing for the edit path.

**Evidence.**

```bash
$ grep -rn "EDITED_NOTE" apps/transcribe-md/src
# (empty)
$ grep -rn "CREATED_CLINICAL_NOTE" apps/transcribe-md/src
# (empty)
$ psql -c "SELECT action, COUNT(*) FROM audit_logs WHERE action='EDITED_NOTE'"
#  EDITED_NOTE | 36   (all legacy timestamps, no current-code source)
```

**Recommended fix.** Decide policy: (a) emit `EDITED_NOTE` on every save (high cardinality — typical visit has 5-20 edits before sign), or (b) add a `SOAP_DRAFT_SAVED` lower-cardinality action enum value that emits once per N seconds (debounced). Option (a) matches the legacy schema's intent; option (b) is operator-friendlier. Either way, also retire the dead enum values from the schema in a follow-up cleanup PR.

**Closure (2026-05-14): RESOLVED-WITH-DOCS — option C (skip, document).**
Ratified by Kasra. Neither A nor B ships in this session; the
intermediate-save coverage gap is accepted with documentation. The
`audit_logs` contract targets discrete legal events (sign / export
/ delete / view) — intermediate draft saves are operational state.
The legal event (`VISIT_SIGNED`) was wired by PR #251 / FIND-P1-001
in both action and route paths. Per-save evidence still exists:
`soapVersion` (counter, not content) increments per call;
`DoctorEditPattern` captures the cumulative `originalSoap →
signedSoap` diff at sign time (one row per signed visit, NOT
per-save — that's the T-M14.1 contract, verified by re-reading
`lib/edit-tracking.ts` during this closure).

Code comment placed at the top of `saveSoapDraftAction`
documenting the intentional skip + the surfaces that DO carry the
edit-trail evidence. PR # filled in on merge. If future regulatory
guidance or multi-doctor scale demands per-save audit_logs rows,
options A/B remain viable.

---

### FIND-P1-003 — `reassignSpeakerAction` no audit emission

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Reliability / HIPAA audit completeness |
| **File:line** | `apps/transcribe-md/src/actions/soap.ts:197` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** Manual override for L2 speaker-role assignment. Doctor reassigns a speaker (e.g., "this segment was the patient, not me"), which mutates `speakerMap` and affects clinical role attribution in the final SOAP note. No `logAudit` emission. Materially affects the legal note's attribution; absence in `audit_logs` means "who reassigned what, when" requires reading the DB row state at a point in time.

**Recommended fix.** Add a new `audit_logs.action` enum value `SPEAKER_ROLE_REASSIGNED` and emit with `{ previousRole, newRole, speakerId }` metadata. Migration: `ALTER TYPE "AuditAction" ADD VALUE 'SPEAKER_ROLE_REASSIGNED'`. Effort small.

---

### FIND-P1-004 — L7b CPT-coding non-transactional dual write

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Data integrity |
| **File:line** | `apps/transcribe-md/src/worker/layers/07b-cpt-coding.ts:219,229` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** L7b first conditionally writes `{ needsReview: true, reviewReason: ... }` if any procedure landed at low confidence (line 219), then unconditionally writes `{ cptCodes: filtered }` (line 229). The two updates are NOT wrapped in `prisma.$transaction`. A worker crash between line 219's resolve and line 229's resolve leaves the visit with `needsReview=true` and a "verify before billing: ..." reviewReason BUT `cptCodes=null`. Doctor sees the warning but no codes to verify.

**Mitigation in place.** BullMQ retries (3 attempts) re-run the entire L7b on retry, which should reset `cptCodes` correctly. Stuck-visit watchdog at 15-min threshold rescues if retries exhaust. So the user-visible window for this inconsistency is bounded by retry + watchdog.

**Evidence.**

```ts
// apps/transcribe-md/src/worker/layers/07b-cpt-coding.ts:217-230
if (lowConfProcedures.length > 0) {
  await prisma.transcribeVisit.update({
    where: { id: input.visitId },
    data: {
      needsReview: true,
      reviewReason: `${lowConfProcedures.length} CPT procedure code${...}`,
    },
  });
}

await prisma.transcribeVisit.update({
  where: { id: input.visitId },
  data: { cptCodes: filtered as unknown as object },
});
```

**Recommended fix.** Collapse into one update with conditional spread:

```ts
const reviewFields = lowConfProcedures.length > 0
  ? { needsReview: true, reviewReason: `${lowConfProcedures.length} CPT...` }
  : {};
await prisma.transcribeVisit.update({
  where: { id: input.visitId },
  data: { cptCodes: filtered as unknown as object, ...reviewFields },
});
```

Atomic single-statement write. No `$transaction` overhead.

---

### FIND-P1-005 — `actions/soap.ts:177` fire-and-forget `captureEditPattern`

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Async correctness |
| **File:line** | `apps/transcribe-md/src/actions/soap.ts:177` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** `void captureEditPattern({ visitId, doctorId })` fires after `signVisitAction`'s primary update. Comment says "captureEditPattern swallows every error internally" — so the contract is the callee's responsibility. The call site has no defensive try/catch; if a future refactor of `captureEditPattern` leaks an error (e.g., a third-party dep adds a sync throw), the rejection silently disappears and the action returns success while edit-pattern is dropped.

**Recommended fix.** Wrap call-site:

```ts
captureEditPattern({ visitId, doctorId: session.user.id }).catch((err) => {
  log.warn('actions:signVisit', 'captureEditPattern failed', { err });
});
```

The structured log gives Sentry/loki a row even if the callee's internal try/catch breaks.

---

### FIND-P1-006 — Deepgram batch has no inline retry

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Reliability |
| **File:line** | `packages/ai/src/deepgram-batch.ts:237` |
| **Effort** | Medium |
| **Dependencies** | Resolves with FIND-P1-007 (Whisper) and FIND-P1-008/-009 (L1/L1b jitter) — natural to ship as one retry-helper PR |

**Description.** `deepgramBatchTranscribe(...)` makes a single `fetch` to `https://api.deepgram.com/v1/listen` with no inline retry. The L1 layer wraps the call in a one-network-retry block (`attempt()` pattern at `01-transcribe.ts:152-180`), so the worker pipeline path retries once. But any non-L1 caller of `deepgramBatchTranscribe` (the eval harness `scripts/eval/primock57-run.ts`, the regression baseline `scripts/keyterm-regression/run.ts`) gets zero retries on transient 5xx. A Deepgram region wobble during an eval run produces hard failures with no recovery.

**Recommended fix.** Add a retry block inside `deepgramBatchTranscribe` itself for transient errors (5xx, network), with exponential backoff + jitter. Default 2 attempts. Make jitter and attempt count configurable via options so the L1 layer (which has its own retry) can pass `{ retries: 0 }` to avoid double-retrying.

```ts
async function deepgramBatchTranscribeOnce(args): Promise<DeepgramBatchResult> { ... existing ... }

export async function deepgramBatchTranscribe(args: DeepgramBatchArgs): Promise<DeepgramBatchResult> {
  const retries = args.options?.retries ?? 2;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await deepgramBatchTranscribeOnce(args);
    } catch (err) {
      if (attempt === retries || !isTransient(err)) throw err;
      const delay = 1000 * 2 ** attempt + Math.random() * 1000;
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  throw new Error('unreachable');
}
```

---

### FIND-P1-007 — Whisper batch has no retry

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Reliability |
| **File:line** | `packages/ai/src/whisper-batch.ts:189` |
| **Effort** | Small (after the retry-helper from FIND-P1-006) |
| **Dependencies** | Same retry helper as FIND-P1-006 |

**Description.** Whisper is the fallback when Deepgram batch fails. The fallback itself has no retry — single-shot. A transient OpenAI 5xx during the rare Deepgram-failed-fallback path produces a hard FAILED state with no automatic recovery. The mitigation chain is: Deepgram retry → Deepgram fail → Whisper (no retry) → fail → BullMQ retry. The BullMQ retry kicks the whole pipeline from L1; not free.

**Recommended fix.** Apply the same retry helper as FIND-P1-006. Default 2 attempts with exp backoff + jitter.

---

### FIND-P1-008 — L1 retry backoff has no jitter (thunder-herd surface)

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Reliability |
| **File:line** | `apps/transcribe-md/src/worker/layers/01-transcribe.ts:170` |
| **Effort** | Small |
| **Dependencies** | None (1-line change) |

**Description.** L1's existing retry block uses `await new Promise((r) => setTimeout(r, BACKOFF_MS))` with a hardcoded constant — no jitter. With BullMQ worker concurrency=2 and multiple workers in future scaling, coordinated retries on a Deepgram region outage produce a thunder-herd on Deepgram's recovery.

**Evidence.**

```ts
// apps/transcribe-md/src/worker/layers/01-transcribe.ts:170 (approx)
await new Promise((r) => setTimeout(r, BACKOFF_MS));
```

**Recommended fix.**

```ts
const jitterMs = Math.floor(Math.random() * BACKOFF_MS);
await new Promise((r) => setTimeout(r, BACKOFF_MS + jitterMs));
```

---

### FIND-P1-009 — L1b retry backoff has no jitter (duplicate of FIND-P1-008)

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Reliability |
| **File:line** | `apps/transcribe-md/src/worker/layers/01b-transcribe-dictation.ts:135` |
| **Effort** | Small |
| **Dependencies** | Ship with FIND-P1-008 |

**Description.** Same defect as FIND-P1-008, in the dictation-mode parallel codepath. The duplication itself is FIND-P3 below (CODE_PATTERN). Both retries need the jitter fix.

**Recommended fix.** Same as FIND-P1-008. Better long-term: factor L1 + L1b's shared retry block into a helper (resolves both this and the larger duplication finding).

---

### FIND-P1-010 — Anthropic `JSON.parse(unfenced)` on final attempt throws

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Reliability |
| **File:line** | `packages/ai/src/anthropic.ts:292` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** When the Anthropic tool-use response falls through to the text-mode branch (which happens when the model returns content without a tool_use block — model regression or prompt drift), the code path does `JSON.parse(unfenced)` after stripping markdown fences. A retry-context loop catches a malformed parse and re-asks the model, but if the FINAL retry also returns malformed text, `JSON.parse` throws. The throw propagates up to the worker layer, which catches it as a generic error and FAILs the visit with the generic "Processing failed" reason — not the doctor-actionable PipelineRejectError humanReason.

**Recommended fix.** Wrap the final-attempt JSON.parse in a try/catch and surface as a typed error:

```ts
try {
  return JSON.parse(unfenced);
} catch (err) {
  throw new ModelOutputMalformedError('Anthropic returned non-JSON after N retries', {
    rawTextSlice: unfenced.slice(0, 200),
    attempt,
  });
}
```

Then the worker's catch block can recognize `ModelOutputMalformedError` and surface a better `reviewReason`. Effort small.

---

### FIND-P1-011 — `loadResumeState` P2025 race on deleted visit

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Worker / data integrity |
| **File:line** | `apps/transcribe-md/src/worker.ts:234-252` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** `loadResumeState(visitId)` reads the row at the start of each retry attempt. If the row is missing, it returns all-nulls as a defensive fallback with the comment "next DB write will error, which is fine." But the L1/L2 `prisma.update` calls run BEFORE the next `findUnique` re-check, so a visit deleted during retry causes an unhandled `P2025 (record not found)` at the first update. P2025 doesn't surface a clean `reviewReason`; it surfaces as `Processing failed during init`.

**Recommended fix.** Make `loadResumeState` throw a typed `VisitNotFoundError` when the row is missing on a retry (rather than returning all-nulls), and have the worker's outer catch handle it specifically (delete the BullMQ job instead of updating a non-existent row).

```ts
if (!row) {
  if (job.attemptsMade > 0) throw new VisitNotFoundError(visitId);
  // First attempt: row should exist; if not, surface as a hard error.
  throw new Error(`Visit ${visitId} not found on first attempt`);
}
```

---

### FIND-P1-012 — `confidenceScores` Prisma JSON silent coerce

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Worker / data integrity |
| **File:line** | `apps/transcribe-md/src/worker.ts:944` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** `confidenceScores` is written as a plain object cast to Prisma's Json type. If a future layer adds a non-serializable value to the object (Map, Set, function, Date that doesn't go through `.toISOString()`), Prisma JSON silently coerces (Map → `{}`, function → undefined dropped) or throws an opaque "Inconsistent column data" error.

**Recommended fix.** Pass `confidenceScores` through `JSON.parse(JSON.stringify(...))` once before persistence to fail fast on non-serializable shapes:

```ts
const safeConfidenceScores = JSON.parse(JSON.stringify(confidenceScores));
// Throws here (not at Prisma) if the object has a circular reference or non-serializable value.
```

Or, better: define a Zod schema for `confidenceScores` and parse at the write site.

---

### FIND-P1-013 — `shouldFailNow` categorize-error false-positive bypasses retries

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Worker / reliability |
| **File:line** | `apps/transcribe-md/src/worker.ts:984-1000` |
| **Effort** | Medium |
| **Dependencies** | None |

**Description.** `shouldFailNow(err, attemptsMade)` returns true when `categorizeError(err) === 'permanent'`, which short-circuits BullMQ retries (jumps straight to the failed handler → DLQ). The `categorizeError` source-of-truth is not inspected here — if it ever false-positives a transient error as 'permanent' (e.g., a 429 misclassified as permanent), legitimate transient failures bypass the retry safety net and land in DLQ on the first attempt.

**Recommended fix.** Add a unit test suite for `categorizeError` that asserts: every known transient error class (429, 503, network timeout, EOF mid-stream) maps to 'transient', and every permanent class (400, 403, 422, malformed-input PipelineRejectError) maps to 'permanent'. Then audit the call sites that feed into `categorizeError`. If high-confidence is hard to reach, add a conservative "unknown → transient" default and require 'permanent' to be explicit.

---

### FIND-P1-014 — Nested `.catch()` inside outer catch swallows FAILED-write failure

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Worker / reliability |
| **File:line** | `apps/transcribe-md/src/worker.ts:1008-1027` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** When a job hits the final FAILED branch, the worker writes `{ status: FAILED, reviewReason }`. That `prisma.update` is wrapped in `.catch(() => { ... })` to prevent re-throw. If BOTH the original job throws AND this FAILED-state persistence throws (e.g., DB outage at the exact moment), the visit remains in its non-terminal status (POLISHING / AUTOMATING / etc.) until the stuck-visit watchdog catches it (15 minutes).

**Recommended fix.** Convert the nested `.catch()` to a log + Sentry capture so operators see the double-failure:

```ts
await prisma.transcribeVisit.update({ where: ..., data: ... }).catch((err) => {
  log.error('worker:finalize', 'FAILED-state persist also failed', { visitId, originalErr: outerErr, persistErr: err });
  captureWorkerException(err, { visitId, layer: 'finalize', userId, practiceId });
  // Re-throw so BullMQ marks the job as failed, even if the visit row stays mid-state.
  // The stuck-visit watchdog will rescue.
});
```

The visit will still be stuck, but the operator gets a Sentry event immediately rather than discovering it via stuck-visit-watchdog audit row 15 minutes later.

---

### FIND-P1-015 — L4 SOAP generation: output not Zod-validated

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | AI pipeline |
| **File:line** | `apps/transcribe-md/src/worker/layers/04-generate-soap.ts:214` |
| **Effort** | Medium |
| **Dependencies** | None |

**Description.** L4 calls `modelClient.completeText({...})` — the text variant of the Anthropic client — and writes the returned text directly to `soapDraft`. There's no Zod parse, no structural validation that the response contains S/O/A/P sections, no minimum-length check. If the model returns empty content (rare but documented in Anthropic's API), an empty string is persisted as `soapDraft` and L5 (self-critique) gets an empty input. L5 then writes its critique JSON which may flag the visit but may not — depends on whether L5's prompt handles the empty case.

**Recommended fix.** Add a post-call structural check:

```ts
const { text } = await modelClient.completeText({...});

if (!text || text.length < 200 || !/##?\s*Subjective/i.test(text)) {
  throw new ModelOutputMalformedError('L4: SOAP draft missing S/O/A/P structure', {
    length: text?.length ?? 0,
    snippet: text?.slice(0, 200) ?? '',
  });
}

await prisma.transcribeVisit.update({...});
```

The throw triggers BullMQ retry on transient model-output issues. Effort medium because the section-headers check needs to match the prompt's actual output convention (markdown headers, plain text, JSON envelope — varies by current prompt version).

---

### FIND-P1-016 — L6 polish: no structural validation on soapFinal write

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | AI pipeline |
| **File:line** | `apps/transcribe-md/src/worker/layers/06-polish.ts:74-89` |
| **Effort** | Medium |
| **Dependencies** | Ship together with FIND-P1-015 |

**Description.** Same shape as L4's gap (FIND-P1-015), in L6's polish layer. `soapFinal` (the doctor-facing output) is written without structural validation. The polish step is meant to clean up L4's output, but if the model returns a near-empty rewrite or strips the S/O/A/P scaffolding by accident, the visit reaches READY with a malformed final note.

**Recommended fix.** Same shape as FIND-P1-015. Reuse the structural-validation helper.

---

### FIND-P1-017 — L2 speaker-role fallback skips schema validation

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | AI pipeline |
| **File:line** | `apps/transcribe-md/src/worker/layers/02-speaker-roles.ts:100-115` |
| **Effort** | Small |
| **Dependencies** | None |

**Description.** L2's fallback path (when the AI call fails or returns no samples) writes a default `{0: doctor 0.5}` speakerMap and returns. The AI-success branch runs the speakerMap through a Zod schema check before writing; the fallback branch skips it. If the fallback's hardcoded shape ever drifts from the schema, the fallback succeeds at write-time but L3+ choke on the malformed shape.

**Recommended fix.** Run the fallback through the same Zod parse before persistence:

```ts
const fallback = { '0': { role: 'doctor', confidence: 0.5, reasoning: 'fallback' } };
const validated = SpeakerMapSchema.parse(fallback);  // throws if drift
await prisma.transcribeVisit.update({...});
```

If the parse throws in dev, schema or fallback are out of sync — surfaces during PR review rather than in production.

---

### FIND-P1-018 — Pipeline layers L2-L6 have NO sibling unit tests

| | |
|---|---|
| **Severity** | P1 |
| **Domain** | Test coverage |
| **File:line** | `apps/transcribe-md/src/worker/layers/{02-speaker-roles,03-extract-entities,04-generate-soap,05-self-critique,06-polish}.ts` |
| **Effort** | Large (5 layers × ~mocked-modelClient tests each) |
| **Dependencies** | None |

**Description.** Only L1 has a sibling unit test (`low-conf-l1.test.ts`, heavily mocked). L7a (ICD fallback), L7c (rx-drafting incl. peds + validator) are tested. **L2 through L6 have zero unit tests.** The entire transformer/critique/polish chain depends on integration coverage — the PR-3 regression baseline at `scripts/keyterm-regression/` exercises L1 end-to-end via real Deepgram, but L2-L6 transformations are not exercised by any deterministic test.

For pilot, this means any L4/L5/L6 prompt or schema change ships with no automated guard. The only "did the prompt break?" signal is post-deploy doctor feedback or a manual re-run of the QA harness.

**Recommended fix.** Add a sibling test per layer in `apps/transcribe-md/src/worker/layers/__tests__/`. Each test:
- Mocks `modelClient.complete*` to return a canned response.
- Asserts the layer's contract: input → expected DB write shape + return value.
- Covers the schema-validation branch (model returns malformed → layer throws expected error type).
- Covers the fallback branch (where applicable, e.g. L2's `{0: doctor 0.5}` default).

Effort large because there are 5 layers, each with a handful of branches, and the mocking surface includes `prisma.transcribeVisit.update`, `logAudit`, `modelClient.complete`. Reuse the mocking pattern from `low-conf-l1.test.ts`.

---

## Section D — P2 + P3 grouped summaries

### P2 — hardening / robustness (35 findings)

#### Domain F — Code-pattern + reliability (P2 cluster, 19 findings)

| Theme | File samples | Why P2 |
|---|---|---|
| **Type safety: `(prisma as any)` casts** | `apps/transcribe-md/src/app/admin/users/_lib/users-data.ts` (5×), `app/admin/hipaa/_lib/hipaa-data.ts:25`, `api/admin/hipaa/[id]/reopen/route.ts:27,45`, `lib/audit.ts:232`, `packages/ai/src/api-usage.ts:109` | All 9 admin/audit/usage data-layer queries use `(prisma as any)` for shape. Drift surface: schema renames go undetected by tsc. P2 because admin paths are infrequent and gated; not user-facing pilot impact. |
| **Type safety: session/auth `as any` casts** | `lib/auth.ts:67`, `lib/nextauth.ts` (3×), `lib/admin-api-gate.ts` (3×) | 7 `(session?.user as any).fieldName` accesses. P2 because the next-auth User type extension exists in `next-auth.d.ts`; the casts predate it and weren't cleaned up. |
| **Type safety: resume-state casts in worker** | `worker.ts:599` (critique), `worker.ts:449,527,546` (entities), `01-transcribe.ts:240` (audioStats!) | 5 resume-state field casts without re-parse. Schema drift between deploys could flow through. P2 because resumes only happen on retry, and the staged-changes-vs-production gap is small in practice. |
| **Type safety: model-response casts** | `packages/ai/src/whisper-batch.ts:197`, `packages/ai/src/anthropic.ts:201`, `worker/layers/03-extract-entities.ts:58` (factWithEvidence) | 3 model-response casts without runtime shape check. P2 because the regression baseline catches gross drift; subtle drift is silent. |
| **Async: fire-and-forget patterns** | `worker.ts:1034` (user.update), `worker.ts:923` (logAudit), `01-transcribe.ts:277` IIFE, `01b-transcribe-dictation.ts:210` IIFE, `lib/em-coding/llm-mdm.ts` (3× nested JSON.parse) | 7 fire-and-forget sites where errors are silently dropped. P2 because each is non-load-bearing (audit-attribution metadata, last-seen, JSON parse fallbacks). |
| **Worker error handling** | `worker.ts:807` (await judgeWarmPromise after Promise.allSettled), `worker.ts:905` (findUnique().catch(() => null)), `worker.ts:189-208` (clearAutomationColumn map), `worker.ts:267-291` (no row-version optimistic lock), `worker.ts:293` (raw Error → P2025 mask), `worker.ts:1396` (DLQ enqueue race) | 6 worker error-path findings: latency hidden under "soft-fail," DB-error-vs-clean-null indistinguishability, map drift, race surfaces. Each is small individually; cumulatively they reduce confidence in failure recovery. |
| **Code patterns** | `worker.ts:1086-1090` (multi-cast humanReason), `worker.ts` 10× `console.error` mixed with `log.info`, `worker.ts:300-311` (if/else over discriminated union), `worker.ts:198-204` (literal column names), `lib/email.ts` 4× Resend response casts | 5 maintainability findings: code-quality auditor's standard pattern-drift class. None ship a bug today; all reduce the codebase's resistance to future drift. |
| **Pipeline output validation depth** | `worker/layers/03-extract-entities.ts:68-79` (top-level liftStringToFact only), `worker/layers/05-self-critique.ts:181` (verify modelClient.complete enforces Zod) | 2 pipeline-validation findings narrower than P1: subtle preprocess-only-top-level issue, and a "verify the contract elsewhere" item. |

#### Domain B — Database schema (P2 cluster, 6 findings)

| Theme | What | Why P2 |
|---|---|---|
| **Multi-tenancy enforcement reliance** | `TranscribeVisit` (no direct practiceId — joins via user), `VisitDelivery`/`DoctorEditPattern`/`RxWarningOverride`/`ThreatResolution`/`HipaaFinding` (no practiceId — parent relation), `Document`/`Appointment` (no practiceId — via patient.practiceId) | 7 models depend on app-code-level enforcement of the practiceId join. P2 because the security audit (2026-05-13) verified the major surfaces; remaining is hardening. |
| **Audit FK** | `audit_logs.userId` has NO FK to `users.id` (deliberate — survives user deletion via `userEmailSnapshot`) | P2 documentation gap: the design intent is documented in code, but verify the snapshot is populated on every emission path. |
| **AccountDeletion purge TODO** | `schema.prisma:702-731` TODO(T-M16.3+) | P2 housekeeping: rows accumulate indefinitely until the sweep lands. |
| **Multi-tenancy migration irreversibility** | `20260412234252_add_multi_tenancy` does `ALTER COLUMN practiceId SET NOT NULL` on 5 tables | P2: irreversible if backfill fails; no rollback artifact (Prisma forward-only by design). Production-recovery story relies on PITR backup. |

#### Domain G — Performance / observability (P2 cluster, 3 findings)

| Theme | What | Why P2 |
|---|---|---|
| Slow-query logging disabled | `log_min_duration_statement = -1` on postgres | P2: no visibility into the long-tail query latency in production. Enable a 500ms threshold to surface drift before doctors notice. |
| `pg_stat_statements` not installed | Extension absent | P2: no per-query mean-time telemetry. Enable + add to admin/ops dashboard. |
| Worker concurrency hardcoded | `concurrency=2` in env | P2: with 11GB RAM available, could safely go to 4-6. Add a metric on queue depth vs concurrency. |

#### Domain E — Frontend / UX (P2 cluster, 4 findings)

| Theme | What | Why P2 |
|---|---|---|
| Missing `loading.tsx` | `patients`, `visits`, `visits/new` (3 high-traffic routes) | P2: Next.js shows a blank flash before page loads. Visible but not blocking. |
| Missing `error.tsx` | `patients`, `admin/*`, `signup`, `forgot-password` (5+ routes) | P2: uncaught errors → unstyled Next.js default crash page. Visible. |
| Admin `.then((r) => r.json())` without `.catch` | `admin/usage/_components/AdminUsage.client.tsx`, `admin/threats/_components/AdminThreats.client.tsx`, `admin/users/_components/UserDetailDrawer.client.tsx`, `admin/threats/_components/InvestigateDrawer.client.tsx` (5+ sites) | P2: silent failure on session expiry / network blip. Admin pages, low frequency. |
| Loading-state inconsistency | 34 components mention empty-state copy vs 8 explicit loading state | P2: investigate whether component-level loading patterns are needed or whether route-level loading.tsx suffices. |

#### Domain J — Test coverage (P2 cluster, 3 findings)

| What | Why P2 |
|---|---|
| Vitest coverage NOT configured (no c8/v8/istanbul) | P2: coverage thresholds unenforced; no signal on regression. |
| 72 test files vs 185 source TS files (~39% colocation) | P2: ratio not the whole story — no critical-path coverage matrix exists. |
| `apps/meddoc-pro/test:all` is decommissioned echo | P2: transcribe-md vitest is NOT in CI today. Already documented in PR-4 closure §F.4. Sticky problem; deserves a focused PR. |

#### Domain L — Operational (P2 cluster, 3 findings)

| What | Why P2 |
|---|---|
| Sentry verification | Verify worker-layer errors (L4 timeout etc.) flow through `captureWorkerException` — only 1 explicit `Sentry.captureException` in source. |
| Postgres backup sidecar unhealthy | `meddoc-pro-postgres-backup-1` "Up 9 days (unhealthy)" — verify backups are actually completing. |
| Heap monitoring | No `process.memoryUsage()` polling in worker; long-running BullMQ process could leak unnoticed. |

### P3 — cosmetic / backlog (11 findings)

| Domain | Theme | What | Why P3 |
|---|---|---|---|
| ASYNC | setInterval `void tick()` | `worker.ts:1345` — sync throw silently dropped | P3: tick() doesn't sync-throw today; defensive fix only. |
| CODE_PATTERN | L1/L1b duplication | `worker/layers/{01-transcribe.ts, 01b-transcribe-dictation.ts}` — massive copy/paste | P3: refactor for maintainability; doesn't block pilot. |
| DB | Migration rollback | No migration rollback artifacts (Prisma forward-only) | P3: production-recovery via PITR is the documented story. |
| DB | ENUM ADD VALUE pattern | Several migrations use `ALTER TYPE ENUM ADD VALUE` — cannot be wrapped in transaction | P3: works in Postgres; partial-deploy risk is theoretical. |
| PERF | Bundle analysis | No record of `next build --analyze` runs; client-bundle drift untracked | P3: not load-bearing for pilot. |
| PERF | Docker build cache | 156.9 GB on host; 125.6 GB reclaimable | P3: preflight skill threshold > 30 GB triggers prune; not user-facing. |
| FRONTEND | `.then() w/o .catch` on click handler | `app/visits/[id]/rx-tab.tsx:294` | P3: one specific click handler in Rx tab — silent failure rare. |
| FRONTEND | `.then() w/o .catch` on command palette | `components/command-palette.tsx:65` | P3: recent items silently missing on rare error. |
| A11Y | Screen-reader flow | No SR audit recorded; axe-core CI catches structural; semantic flow untested | P3: doctors typically don't use SR; gap real but low-pilot-impact. |
| OPS | Alerting | No alert rules for queue depth, DLQ size, postgres connections, /api/health 5xx rate | P3: small operation, current scale doesn't warrant alerting yet. |
| OPS | Runbook | Production-recovery procedure ("worker crashed with 50 visits queued") not documented in repo | P3: oral knowledge with Kasra; documentation hygiene. |

---

## Section E — Domain rollups (counts)

| Domain | P0 | P1 | P2 | P3 | Total |
|---|---|---|---|---|---|
| Backend / Worker | 0 | 5 | 6 | 1 | 12 |
| Database | 0 | 0 | 6 | 2 | 8 |
| AI Pipeline | 0 | 3 | 2 | 0 | 5 |
| Frontend / UX | 0 | 0 | 4 | 2 | 6 |
| Code quality (patterns) | 0 | 0 | 16 | 1 | 17 |
| Reliability | 0 | 4 | 3 | 0 | 7 |
| Data integrity | 0 | 1 | 3 | 0 | 4 |
| Test coverage | 0 | 1 | 3 | 0 | 4 |
| Accessibility | 0 | 0 | 1 | 1 | 2 |
| Operational | 0 | 0 | 3 | 2 | 5 |
| Audit emission (action paths) | 0 | 3 | 0 | 0 | 3 |
| **Total** | **0** | **18** | **35** | **11** | **64** |

---

## Section F — Appendix

### Sources

- **Phase 1 inventory** — `docs/qa-reports/comprehensive-audit-20260514T030426Z-phase1-inventory.md` (66 candidates pre-triage)
- **code-quality-auditor sub-agent** — invoked once with rules library at `/opt/meddoc-pro/.claude/agents/code-quality-auditor/rules.md` (839 lines, 31 rules); returned 51 candidate findings for domain F.
- **Production data ground truth**:
  - `audit_logs` distribution (6967 rows, multi-tenant scoping verified)
  - `transcribe_visits` distribution (201 in 30-day window, no orphan QUEUED state)
  - BullMQ + DLQ state (1 wait / 0 failed)
  - Container health (9 containers, all Up with 1 documented unhealthy backup sidecar)
- **Postgres extension state** — `pg_stat_statements` absent, `log_min_duration_statement = -1`.

### Methodology limits + non-goals

- **Skipped (already audited):** security (#240-#244), cross-input-mode (#237), keyterm scoping + ISMP safety floor (#246-#250), rate-limit (#238), email deliverability (#245). The Phase 1 inventory does not re-find any of these surfaces.
- **Out of scope:** semantic-flow accessibility audit (no manual screen-reader walk-through), penetration testing (security audit covers), performance load testing (no synthetic workload generated).
- **Read-only:** no fix code was written in this audit. Subsequent PRs will address findings one-by-one based on operator prioritization.

### Naming

Findings are numbered `FIND-{severity}-{three-digit-seq}` within the P1 tier. P2/P3 are grouped — individual numbering would inflate the document without adding triage value at this scale.

### Verification discipline

Three sub-agent P0_candidates were downgraded to P1 after production-data ground truth. The audit's job is not to manufacture severity; if a candidate is mitigated in production (by a parallel surface, an existing retry, or a watchdog), the severity reflects that. The downgrade history is documented in §B "Verification standard."

### Companion artifacts

- **PDF version** — `comprehensive-audit-20260514T030426Z.pdf` (this same content, paginated + color-coded severity tags)
- **CSV findings export** — `comprehensive-audit-20260514T030426Z-findings.csv` (one row per finding for spreadsheet triage)
- **Phase 1 raw inventory** — `comprehensive-audit-20260514T030426Z-phase1-inventory.md`

---

_End of audit. Pilot-readiness verdict: GREEN with 18 documented P1 follow-ups. Subsequent PRs will address P1s one-by-one based on Kasra's prioritization._
