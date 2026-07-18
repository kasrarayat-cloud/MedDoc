# Visit automation transaction integrity

Status: synthetic QA only; independent exact-head audit is required.

## Safety boundary

A visit may enter `READY` only through `finalizeVisitAutomationReady`. The
same current manifest is independently locked and checked again by signing and
export. `READY` and `SIGNED` database transitions also have a trigger guard, so
a caller cannot bypass the application gate by updating the visit directly.

The proof is current only when it has the exact visit/practice, SOAP version
and SHA-256, source-fact SHA-256, policy/version inventory, and (for synthetic
QA) durable admission/run plus pinned global and practice rollout generations.
Clinical content is not stored in the manifest or its failure metadata.

## Layer policy

| Layer                        | Ordinary visits          | Synthetic staging | Reason                                                                    |
| ---------------------------- | ------------------------ | ----------------- | ------------------------------------------------------------------------- |
| ICD coding                   | Optional when enabled    | Required          | Existing ordinary coding-assist contract; staging fixture is mandatory     |
| CPT coding                   | Optional when applicable | Required          | Existing ordinary coding-assist contract; staging fixture is mandatory     |
| Prescription drafting/safety | Optional when enabled    | Required          | No draft means no prescription claim; staging fixture is mandatory         |
| Referrals                    | Optional when enabled    | Required          | Adjunct ordinarily; staging exercises the complete deterministic boundary |
| Patient summary              | Optional when enabled    | Required          | Adjunct ordinarily; staging exercises the complete deterministic boundary |
| E/M MDM cache prewarm        | Optional                 | Not applicable    | Performance cache only; live E/M provider use is prohibited in staging    |

A disabled or specialty-inapplicable layer is persisted as
`NOT_APPLICABLE`; it never disappears from the inventory. Required failures,
missing rows, `PENDING`, or `RUNNING` block finalization. Optional failures are
visible but do not misrepresent a required clinical result as successful.

The rejected-result and swallowed-audit mechanics were shared, so both
workflows now retain a complete durable inventory and atomic completion audit.
The original ordinary product contract, however, explicitly treated each L7
assistant as optional; only synthetic staging requires all five L7 fixtures.
Accordingly, an ordinary optional failure is recorded and visible without
silently redefining SOAP readiness, while a staging failure blocks `READY`.
The E/M prewarm is also `NOT_APPLICABLE` under `MOCK_AI_CALLS` so disposable QA
cannot escape the deterministic provider boundary.

## Canonical lock order

All affected state-changing transactions acquire locks in this order:

1. global Template Twin rollout control (when staging applies);
2. practice;
3. durable staging admission (when staging applies);
4. durable staging run (when staging applies);
5. actor/user;
6. visit;
7. visit automation manifest;
8. automation layer rows in ascending `layerId` order;
9. transactional audit outbox.

`automation-locks.ts` owns this order. Staging reuses the rollout/admission
locking helpers and ordinary visits start at practice. Worker audits use the
same helper and the transactional outbox. They no longer insert directly into
`audit_logs`, whose implicit user/practice foreign-key checks caused the
independently reproduced inverse lock order.

Database-owning L7 tasks execute in deterministic layer order. Their provider
call occurs outside a retryable database transaction, followed by separately
retryable output and manifest commits. This intentionally trades some fanout
latency for bounded, observable transaction behavior until each L7 layer is
split into an independently pure provider phase and one aggregate commit.

## Transaction retry contract

`runSerializableTransactionWithRetry` retries the complete idempotent database
transaction for PostgreSQL `40P01`, `40001`, and Prisma `P2034` only.

- Maximum: three attempts (hard-capped at five for explicit callers).
- Backoff: bounded exponential jitter, 25–200 ms ceilings.
- Metrics: attempts, retries, exhausted retries, deadlocks, and serialization
  failures; logs contain only operation names and non-clinical identifiers.
- Exhaustion: throws `DATABASE_TRANSACTION_RETRY_EXHAUSTED`; BullMQ sees a
  failure and the visit cannot finalize.
- Forbidden inside retry: provider calls, object writes, email, or other
  irreversible side effects.

An already committed layer result is identified by its input hash,
idempotency key, and output hash, so retry/resume does not call the provider
again. Worker audit event keys are hashes of the complete safe logical event;
re-enqueue is idempotent, while an actual outbox failure propagates.

An unsigned visit that is deliberately reprocessed after a SOAP/Twin
invalidation first enters `AUTOMATING` under the canonical locks. PostgreSQL
then permits exactly one `COMPLETE -> RUNNING` rebind with
`manifestVersion + 1`, no prior layer rows, no `signedAt`, and the current SOAP
version. All other COMPLETE mutations fail. A signed manifest and its terminal
layer results remain immutable; an ordinary BullMQ database retry continues to
reuse the current input/idempotency hashes rather than entering this explicit
new-proof path.

## Migration and historical rows

Migration `20260717230000_visit_automation_manifest_v1` is additive: two empty
tables, enums, indexes, constraints, and bounded trigger/function DDL. It does
not update `transcribe_visits` or label any historical output successful.
Existing visits without a manifest are `LEGACY_UNKNOWN` and require explicit
reprocessing before a new sign/export claim can prove automation completion.

Expected locks are catalog locks for enum/table/index/function/trigger
creation; there is no data backfill or unbounded table update. The migration
sets transaction-local `lock_timeout = 5s` and `statement_timeout = 60s`, so a
busy deployment fails and can be retried rather than waiting indefinitely.
Prisma records that bounded failure as a failed migration. After the blocking
transaction is investigated and released, an operator must mark only this
known failed attempt rolled back with `prisma migrate resolve --rolled-back
20260717230000_visit_automation_manifest_v1`, verify the proof tables/types are
absent (the explicit transaction rolls them all back), and rerun `migrate
deploy`. The disposable contention test proves that sequence.

Rollback/disable does not delete proof. Disable staging through the existing
global/practice controls, stop new workers, and retain the additive rows and
outbox evidence. Application rollback to code unaware of the trigger requires
a reviewed forward migration; do not drop proof tables or triggers ad hoc.

## Disposable PostgreSQL verification

Run only against a database name positively containing `qa` or `test`:

```text
npm --workspace @meddoc/db run visit-automation:pg-test
```

The harness uses synthetic identities and validates:

- database-enforced tenant and READY/SIGNED gates;
- two recorded required failures;
- atomic rollback when completion-audit insertion fails;
- deterministic real `40P01` and `40001` whole-transaction retries;
- no duplicate provider result after retry;
- twenty consecutive six-layer completion manifests with one completion audit
  each;
- cleanup of only harness-created records and probe tables.

This is PostgreSQL transaction evidence, not production, provider, Microsoft
Word, clinical-safety, privacy/legal, storage/IAM, backup/restore, or operations
approval.
