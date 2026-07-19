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

| Layer                        | Ordinary visits          | Synthetic staging | Reason                                                                                  |
| ---------------------------- | ------------------------ | ----------------- | --------------------------------------------------------------------------------------- |
| ICD coding                   | Optional when enabled    | Required          | Existing ordinary coding-assist contract; staging fixture is mandatory                  |
| CPT coding                   | Optional when applicable | Required          | Existing ordinary coding-assist contract; staging fixture is mandatory                  |
| Prescription drafting/safety | Optional when enabled    | Required          | No draft means no prescription claim; staging fixture is mandatory                      |
| Referrals                    | Optional when enabled    | Required          | Adjunct ordinarily; staging exercises the complete deterministic boundary               |
| Patient summary              | Optional when enabled    | Required          | Adjunct ordinarily; staging exercises the complete deterministic boundary               |
| E/M MDM cache prewarm        | Not applicable           | Not applicable    | On-demand E/M remains available; the legacy prewarm cannot satisfy this ledger contract |

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
The E/M cache prewarm is `NOT_APPLICABLE` in the durable fanout for both
workflows. Its legacy helper performs an internal provider retry and Redis
write, so it cannot be represented as one at-most-once provider execution plus
one atomic database projection. On-demand E/M scoring is unchanged.

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
9. provider execution rows in ascending `id` order;
10. transactional audit outbox.

`automation-locks.ts` owns this order. Staging reuses the rollout/admission
locking helpers and ordinary visits start at practice. Worker audits use the
same helper and the transactional outbox. They no longer insert directly into
`audit_logs`, whose implicit user/practice foreign-key checks caused the
independently reproduced inverse lock order.

Queue-admission failure cleanup uses the same shared admission-then-run lock
primitive as normal processing and crash reconciliation. Rollout revocation
does not prevent that cleanup from recording `ENQUEUE_FAILED`, but the cleanup
may only remove authority: it cannot advance admission, visit, manifest, or
output state.

A transient synthetic worker delivery uses the same lock order to move
`PROCESSING -> RETRY_ENQUEUED`. That transaction clears the expiring delivery
lease, preserves the admission in `PROCESSING`, and records the retry outbox
event atomically. Only the next numbered BullMQ delivery may consume the
handoff and return the run to `PROCESSING`; the database caps the delivery
counter at three. The expired-lease reconciler ignores `RETRY_ENQUEUED`, so it
cannot race a legitimate bounded retry. A rollout generation change still
rejects the replacement claim.

Database-owning L7 tasks execute in deterministic layer order. A committed
provider reservation is independently reread before the provider boundary is
invoked. The provider call occurs outside every retryable database transaction.
Its durable private result is then projected with the clinical result, layer
terminal state, captured worker audits, and layer-completion outbox event in
one separately retryable transaction.

## Durable provider execution

Each enabled L7 layer owns one tenant-scoped execution row and one deterministic
idempotency key. The state machine is:

`RESERVED -> IN_FLIGHT -> SUCCEEDED | FAILED | UNKNOWN_OUTCOME`

- `RESERVED` is committed and independently reread before the call.
- `RESERVED -> IN_FLIGHT` is one atomic compare-and-set. The winning worker
  writes a unique, server-only internal concurrency token; only the typed
  `CLAIMED_BY_CALLER` result returned to that worker permits provider
  invocation. A competing worker receives `ALREADY_IN_PROGRESS`, never learns
  the token, waits for a terminal row, and reuses `SUCCEEDED` when available.
- Every application terminal write matches the same internal concurrency
  token. A non-matching worker cannot mark success, failure, or unknown. Claim
  tokens are excluded from audit metadata, logs, browser responses, and public
  return types.
- `SUCCEEDED` stores the bounded private result envelope, result SHA-256, and
  capture contract version. A job retry reuses that result and cannot invoke
  the provider again.
- `UNKNOWN_OUTCOME` is terminal and blocks review, signing, and download. It is
  used when a process can no longer prove whether an in-flight provider call
  completed. The system never blindly replays it.
- Provider implementations receive the deterministic key, but the application
  does not claim provider exactly-once semantics. Providers without a proven
  retrieval/idempotency contract remain at-most-once with fail-closed unknown
  outcomes.

The result envelope is private clinical workflow data. Audit metadata contains
only safe identifiers, versions, hashes, status codes, and layer names.

## Transaction retry contract

`runSerializableTransactionWithRetry` retries the complete idempotent database
transaction for PostgreSQL `40P01`, `40001`, and Prisma `P2034` only.

- Maximum: three attempts. Values outside one through three are rejected before
  a transaction begins; a fourth attempt is impossible.
- Backoff: bounded exponential jitter, 25–200 ms ceilings.
- Metrics: attempts, retries, exhausted retries, deadlocks, and serialization
  failures; logs contain only operation names and non-clinical identifiers.
- Exhaustion: throws `DATABASE_TRANSACTION_RETRY_EXHAUSTED`; BullMQ sees a
  failure and the visit cannot finalize.
- Forbidden inside retry: provider calls, object writes, email, or other
  irreversible side effects.

An already committed provider result is identified by its tenant lineage,
input hash, deterministic idempotency key, and output hash. Clinical projection
failure therefore reuses the provider result without a second call. Worker
audit event keys are hashes of the complete safe logical event; re-enqueue is
idempotent, while an actual outbox failure rolls the projection back.

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

Migration `20260718090000_visit_automation_provider_execution_v1` is also
additive. It creates the private provider-execution ledger, tenant/lineage
foreign keys, unique layer and idempotency identities, transition guards, and
the provider-execution lock-order index. It also adds the bounded
`workerDeliveryCount` and `workerRetryReadyAt` columns plus the
`RETRY_ENQUEUED` transition to the pre-existing synthetic run table. Existing
runs default to zero deliveries and are not inferred complete; existing
generic visits receive neither an execution nor a synthetic admission. The
migration performs no historical insert or clinical-table update and never
infers a successful execution for an existing visit. It uses the same
transaction-local 5-second lock timeout and 60-second statement timeout.
Rollback is operational: disable the feature and preserve immutable evidence.
A known failed disposable/development attempt must be marked rolled back before
retrying; production operators must not edit migration checksums or drop
evidence ad hoc.

Migration `20260718180000_visit_automation_provider_claim_ownership_v1` adds
the nullable unique `claimId` internal concurrency token and `claimedAt`
timestamp, then tightens provider state-shape and transition constraints. It
uses transaction-local 5-second lock and 60-second statement timeouts. Existing
terminal rows retain their outcome and receive a deterministic private legacy
marker solely to satisfy the immutable state contract. An execution that is
`IN_FLIGHT` during upgrade becomes terminal `UNKNOWN_OUTCOME`; the migration
never assumes that an ambiguous provider call failed or succeeded, and it
never schedules a replay. Reserved or historical failed-before-invocation rows
remain unclaimed. The migration recreates both lineage and transition triggers
inside the same transaction, so timeout or constraint failure restores the
pre-migration schema and data completely.

Operational rollback is disable-only: stop new provider work through the
existing rollout controls and retain the additive columns and immutable
evidence. Do not drop claim data or reinterpret unknown outcomes. A failed
deployment can be retried after the blocking transaction is released; do not
edit the migration checksum.

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
