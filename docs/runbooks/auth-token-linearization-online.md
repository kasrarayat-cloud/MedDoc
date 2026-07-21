# Authentication-token online linearization

Status: **required first-deployment gate; production authority pending**

Migration `20260720150000_auth_token_linearization_v5` no longer builds a
plain index on the populated `auth_tokens` table. It installs a bounded,
fail-closed transition trigger. The operator in this runbook then retires
legacy duplicate unused tokens in bounded batches and creates the final
partial unique index concurrently, outside a transaction.

The final invariant is exactly one unused row for each `(userId, purpose)`.
Older duplicates are marked used; the newest `createdAt`, then greatest `id`,
is retained. Raw tokens, hashes, email addresses, and user identifiers must
never enter operator output or release evidence.

## Safety and lock boundary

- `prisma migrate deploy` takes only the short metadata lock needed to install
  the transition trigger, with `lock_timeout=2s` and
  `statement_timeout=30s`. A timeout is a failed migration attempt.
- The trigger serializes exact `(userId,purpose)` writers and rejects a second
  unused row while no final index exists. During this transition only,
  unused-token inserts/updates require READ COMMITTED. REPEATABLE READ and
  SERIALIZABLE fail closed because their transaction snapshot can remain stale
  after an advisory-lock wait. Once the exact index is valid and the trigger is
  removed, PostgreSQL's normal supported transaction isolation levels resume.
- Reconciliation locks only the token rows belonging to at most the requested
  number of duplicate keys. A batch is one transaction and one bounded
  statement; the default is 100 keys and the hard maximum is 1,000.
- One session advisory lock spans reconciliation and standalone concurrent
  index work. An opposing operator fails with
  `AUTH_TOKEN_LINEARIZATION_OPERATOR_BUSY`.
- `CREATE UNIQUE INDEX CONCURRENTLY` permits ordinary reads and writes. Its
  brief catalog locks and total build retain explicit 2-second lock and
  15-minute statement bounds.
- The transition trigger is removed only after PostgreSQL reports the exact
  index unique, live, ready, and valid and duplicate-group count is zero.

## Forward gate

Before any production command, require a verified backup/restore identifier,
current row and duplicate-group census, free disk/WAL/replication capacity,
monitoring ownership, approved maintenance window, and the accepted immutable
migrator SHA. Record `SHOW default_transaction_isolation` and verify every
current token writer/app transaction remains READ COMMITTED for the transition;
a higher configured default is a migration blocker. Do not start or promote application or dispatcher processes
between the expand migration and a complete operator status.

The examples intentionally omit the database URL. Supply
`AUTH_TOKEN_LINEARIZATION_DATABASE_URL` through the approved secret mechanism.

1. Apply the reviewed migrations. A failed v5 attempt must be inspected and
   retried through the standard Prisma failed-migration procedure; never edit
   `_prisma_migrations` or copy a checksum.
2. Record aggregate status:

   ```bash
   npm run auth-token-linearization -- --phase status
   ```

   This phase is server-enforced read-only. It also emits phase-specific opaque
   `targetFingerprints` derived from the configured host, port, database and
   login plus the live server address/port, PostgreSQL major version, TLS peer
   certificate identity (or explicit plaintext transport), and phase. Verify
   those target facts against approved infrastructure evidence before selecting
   the fingerprint for a mutating phase. Before the operator, expect
   `transitionTriggerEnabled=true`. The duplicate count may be nonzero. Neither
   state authorizes process promotion.

3. Reconcile in measured batches:

   ```bash
   npm run auth-token-linearization -- \
     --phase reconcile --batch-size 100 --batch-delay-ms 100
   ```

   Start smaller if measured production lock/WAL evidence requires it. Rerun
   until `duplicateGroups=0`; then rerun once and require zero retired rows.

4. Build and catalog-verify the index:

   ```bash
   npm run auth-token-linearization -- --phase index
   ```

   Alternatively `--phase all` performs reconciliation then the index phase
   under the same session lock.

5. Require status to report all of:

   ```text
   duplicateGroups=0
   indexExists=true
   indexValid=true
   indexReady=true
   indexExact=true
   transitionTriggerEnabled=false
   complete=true
   ```

Only this complete catalog proof, a successful idempotent rerun, and the wider
release gates permit application promotion.

Production mutation also requires all four explicit controls:

```text
AUTH_TOKEN_LINEARIZATION_ALLOW_PRODUCTION=true
AUTH_TOKEN_LINEARIZATION_PRODUCTION_CHANGE_ID=<approved change identifier>
AUTH_TOKEN_LINEARIZATION_PRODUCTION_ACK=<database-name>:<phase>
AUTH_TOKEN_LINEARIZATION_APPROVED_TARGET_FINGERPRINT=<exact lowercase phase fingerprint from verified status>
```

The fingerprint is phase-specific. A separate `reconcile` then `index` sequence
requires the matching fingerprint for each invocation; `all` uses its own
fingerprint. Rerun status and reverify the target whenever DNS resolution, the
server address or port, PostgreSQL major, transport mode, or TLS certificate
changes. Never approve a fingerprint solely because the operator printed it.
Independently verify the configured and live target through the approved
infrastructure, DNS, transport, and certificate evidence, then bind the opaque
fingerprint returned for that phase to the change record.
These variables are an execution guard, not production authorization.

## Interruption, resume, and rollback

- A stopped reconciliation batch rolls back; prior batches remain committed.
  Rerun the same phase. No cursor can skip a duplicate group because every
  batch selects the current deterministic first keys.
- An interrupted concurrent build may leave an invalid index shell. The
  operator inspects `pg_index`, drops only the fixed invalid protocol index
  with `DROP INDEX CONCURRENTLY`, rebuilds it, and verifies the exact target,
  columns, predicate, uniqueness, readiness, liveness, and validity.
- If the exact-name index has a different definition, stop. The operator fails
  closed and does not replace a valid but unexpected object.
- A trigger-removal lock timeout is safe: the valid unique index and transition
  trigger both remain protective. Rerun the index phase after the blocker is
  gone.
- Application rollback keeps the additive function/index and all used-token
  history. Do not reactivate retired bearers, drop the index, delete token rows,
  or down-migrate. Disable auth-email delivery if the authority state is
  ambiguous and follow the authentication incident procedure.
- Database restore requires the same operator status proof before restored
  application processes can start.

Evidence is aggregate only: batch count/duration, retired-row count,
duplicate-group count, index catalog booleans, lock timeouts, interruption and
resume result, and backup/restore identifier. Never capture connection strings,
tokens, hashes, account identifiers, or provider data.

## Earlier unpublished checksum

The pre-remediation v5 file used a blocking plain index build. It was confined
to disposable engineering/staging databases and was never an authorized
production migration. Correcting that unpublished migration changes its Prisma
checksum by design. Every disposable or synthetic stack that applied the old
checksum, including an e7-era test database, is invalidated and must be
destroyed and rebuilt from the accepted corrected migration history. Do not
edit `_prisma_migrations`, copy a checksum, or add a post-side-effect migration
that pretends the online protocol ran. The supported data-bearing rehearsal
starts from an authentic pre-v5 database, applies corrected v5, completes this
operator, and then continues through the remaining migrations.
