# Template Twin NoteTemplate lineage online migration

Status: **required first-deployment runbook; not authorized for production by this PR**

This runbook replaces the original one-transaction `UPDATE note_templates`
backfill. The expand DDL is admitted only through the closed, cumulative
`db-migrate --phase lineage-expand` release segment. The online phases remain
separate because PostgreSQL cannot build indexes concurrently inside a
transaction, and a million-row data rewrite does not belong in an application
schema migration. Do not invoke raw `prisma migrate deploy`; it bypasses the
reviewed release cut points and their target, ledger, timeout, and prerequisite
proofs.

No step may run with Template Twin globally or practice-enabled. The existing
application, worker, provider calls, and production storage are not part of the
synthetic migration proof.

## Final invariant and transitional compatibility

The final database invariant remains:

```text
note_templates.lineageId IS NOT NULL
UNIQUE (lineageId, version)
```

`schema.prisma` intentionally describes that final non-null shape. During the
bounded deployment window, the expanded database column is nullable. This
temporary mismatch is safe only because:

- every new generic and Template Twin application create explicitly supplies a
  lineage;
- a mixed-version `BEFORE INSERT` trigger self-roots an omitted lineage at the
  new template ID;
- generic lifecycle reads treat a legacy null as `existing.id`, update that
  single row, and give its child the same lineage;
- Template Twin rows cannot be enabled until the durable migration phase is
  `CONTRACTED`; and
- the contract removes the transition trigger only after the validated proof
  and `SET NOT NULL` commit.

Do not add another generic `lineageId` reader during this window without an
explicit null fallback. Do not use Prisma migration status as evidence that the
operator phases completed; the progress row and catalog proof are authoritative.

## Lock order and phase table

Only one lineage operator runs at a time. For each mutating command, the CLI
opens one connection and retains that same target-proved PostgreSQL session for
the live target preflight, coherent initial status snapshot, fingerprint check,
**session** advisory lock
`template_twin_note_templates_lineage_operator_session_v1`, locked status
recheck, mutation, and final status. The lock is held until the complete command
returns. No second session is trusted to carry the approval or the lock. This is
load-bearing: transaction locks cannot span standalone
`CREATE/DROP INDEX CONCURRENTLY` work. An opposing CLI fails immediately with
`LINEAGE_MIGRATION_OPERATOR_BUSY`; it must not overlap or alter progress.

Within that command, every transactional phase also takes the transaction-scoped
advisory lock for `template_twin_note_templates_lineage_online_v1`, then locks
the single progress row. The second lock protects library-level transactional
calls; its distinct key avoids a process blocking itself behind its dedicated
session lock. No operator uses `SKIP LOCKED` because a primary-key cursor must
never advance past a temporarily locked row.

| Phase          | Work                                                                                        | Expected PostgreSQL locks                                                                              | Bound / write behavior                                                                                                                                                                                       |
| -------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Expand         | Add nullable columns, transition trigger, progress table and new empty Template Twin tables | Brief `ACCESS EXCLUSIVE` on `note_templates`; ordinary DDL locks on new objects                        | One explicit transaction; `lock_timeout=2s`, `statement_timeout=30s`; failure rolls the phase back                                                                                                           |
| Guard index    | Partial unique index over populated lineages                                                | `CREATE UNIQUE INDEX CONCURRENTLY`; `SHARE UPDATE EXCLUSIVE` phases, brief catalog locks               | Runs outside a transaction with 2s lock and 15m statement limits; backfill refuses to start until `indisvalid` and `indisready` are true                                                                     |
| Backfill       | `lineageId=id`, ordered by primary-key cursor                                               | `ROW EXCLUSIVE` table intent plus row locks for at most the configured batch and one progress-row lock | Default 1,000 rows, maximum 10,000; 30s statement/2s lock limit; cursor and rows commit atomically                                                                                                           |
| Final indexes  | Full unique lineage/version and doctor/kind/status indexes                                  | `CREATE [UNIQUE] INDEX CONCURRENTLY`; `SHARE UPDATE EXCLUSIVE` phases                                  | Outside transactions, 2s lock and 15m statement limits; an invalid shell is removed only after its complete non-health catalog topology matches the fixed contract, then the replacement is catalog-verified |
| Add proof      | Add `CHECK (lineageId IS NOT NULL) NOT VALID`                                               | Conservatively plan for a brief `ACCESS EXCLUSIVE` metadata lock                                       | 2s lock limit; no table scan                                                                                                                                                                                 |
| Validate proof | Validate the check                                                                          | `SHARE UPDATE EXCLUSIVE`                                                                               | Allows normal reads and row writes; 30s statement limit by default and must be sized from synthetic evidence                                                                                                 |
| Contract       | Set column `NOT NULL`, remove transition trigger, set progress `CONTRACTED`                 | Brief `ACCESS EXCLUSIVE` on `note_templates`                                                           | 2s lock limit; PostgreSQL uses the validated check instead of rescanning; one transaction                                                                                                                    |

The contract transaction commit is the schema linearization point. Before it,
the feature stays unavailable. After it, every committed row is non-null and the
full unique index is independently valid. A lock timeout is a failed attempt,
never a pass; remove the blocker and rerun the same idempotent phase.

## Required status challenge and approval protocol

Every mutating lineage invocation, including a retry, resumed batch, and
zero-change idempotency run, requires a **fresh** server-enforced read-only
status command immediately beforehand:

```bash
npm run lineage:online -w @meddoc/db -- --phase status
```

The status event contains an opaque, phase-specific challenge under
`targetFingerprints.<phase>`. It binds the configured and live database target,
PostgreSQL cluster system identifier, transport identity, requested phase,
durable progress phase, and complete protocol status epoch. Independently
verify those target facts against the approved infrastructure/change evidence;
the fact that the operator emitted a fingerprint does not approve it. Select
only the matching phase fingerprint and pass it to that one invocation:

```bash
export TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT='<verified lowercase targetFingerprints.<phase> value>'
npm run lineage:online -w @meddoc/db -- --phase <phase>
unset TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT
```

Do not reuse a challenge for another phase or after any status/progress change.
The mutating command repeats the live target and status proof on its one retained
session, obtains the session advisory lock, and rejects the invocation if the
locked protocol epoch no longer matches the approved challenge.

At every status checkpoint require all three exactness fields to be true:

```text
presentIndexesExact=true
validationConstraintExact=true
transitionContractExact=true
```

These fields mean that every fixed-name object that is present has the complete
expected catalog definition, and that the transition function/trigger pair is
either exact or, after contract, completely absent. They do not replace the
phase-specific existence, readiness, validation, row-count, and nullability
checks below.

## Forward deployment

The commands below omit the database URL deliberately. Supply it through the
approved deployment secret mechanism; never paste it into a ticket or log.

1. Confirm both rollout layers are disabled and record an approved database
   backup/restore point, current migration status, row count, PostgreSQL version,
   free disk, replication lag, and the current checksum of the expand migration.
2. From the reviewed immutable migrator image, run the read-only
   `db-migrate --phase status`, independently verify its exact target
   fingerprint, and admit only the closed `lineage-expand` segment with
   `DATABASE_RELEASE_MIGRATION_APPROVED_TARGET_FINGERPRINT`. A production
   invocation also needs the migration runner's phase-specific production
   approval variables documented in `docs/DEPLOYMENT_RUNBOOK.md`. The expand
   segment must finish within its lock and statement bounds. If it fails, stop.
3. Inspect, without printing template content, and obtain the fresh
   `guard-index` challenge:

   ```bash
   npm run lineage:online -w @meddoc/db -- --phase status
   ```

   Expected: `phase=EXPANDED`, `columnNotNull=false`,
   `transitionTriggerPresent=true`, all three exactness fields true, and a
   non-negative null count. Prisma migration status alone is insufficient.

4. Establish transition-safe uniqueness:

   ```bash
   export TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT='<verified targetFingerprints.guard-index value>'
   npm run lineage:online -w @meddoc/db -- --phase guard-index
   unset TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT
   ```

   Do not deploy/promote new application processes until status reports
   `phase=GUARDED`, the partial index is present, ready, and valid, and all
   three exactness fields are true.

5. Run status again, independently verify the fresh `backfill` challenge, then
   run bounded batches. Start conservatively and tune only from measured lock,
   WAL, replication, and request-latency evidence:

   ```bash
   export TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT='<verified targetFingerprints.backfill value>'
   npm run lineage:online -w @meddoc/db -- \
     --phase backfill --batch-size 1000 --batch-delay-ms 100
   unset TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT
   ```

   `SIGINT`/`SIGTERM`, process loss, or a database restart is safe: the last
   committed cursor remains in the progress row. Rerun the same command. A
   failed batch cannot advance its cursor.

6. Require `phase=BACKFILLED`, `nullRows=0`, zero duplicate
   `(lineageId,version)` groups, and all three exactness fields true. Run status
   yet again, use its fresh `backfill` challenge for one idempotency rerun, and
   require `batchRows=0`, `complete=true`, and `cursorRestarted=false`.
7. Run status, verify the fresh `indexes` challenge, then build and verify final
   indexes outside a transaction:

   ```bash
   export TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT='<verified targetFingerprints.indexes value>'
   npm run lineage:online -w @meddoc/db -- --phase indexes
   unset TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT
   ```

   Require `phase=INDEXED`, the partial index absent, both final indexes
   present/ready/valid, and all three exactness fields true.

8. Run status, verify the fresh `validate` challenge, then add and validate the
   proof constraint:

   ```bash
   export TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT='<verified targetFingerprints.validate value>'
   npm run lineage:online -w @meddoc/db -- --phase validate
   unset TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT
   ```

   Require `phase=VALIDATED`, a present and validated check, both final indexes
   valid/ready, no nulls, no duplicates, the transition trigger still present,
   and all three exactness fields true.

9. Schedule the short contract lock during a monitored low-write window. Run
   status and verify the fresh `contract` challenge. The separate exact
   acknowledgement prevents accidental invocation:

   ```bash
   export TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT='<verified targetFingerprints.contract value>'
   export TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK='note_templates_lineage_v1:<database-name>'
   npm run lineage:online -w @meddoc/db -- --phase contract
   unset TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK
   unset TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT
   ```

10. Require `phase=CONTRACTED`, `columnNotNull=true`, transition trigger absent,
    partial index absent, final indexes valid/ready, the validation constraint
    present/validated, `nullRows=0`, zero duplicate groups, and all three
    exactness fields true. Only then may the next closed migration segment and
    a separately approved rollout operation proceed.

Production use additionally requires all of these explicit variables:

```text
TEMPLATE_TWIN_LINEAGE_ALLOW_PRODUCTION=true
TEMPLATE_TWIN_LINEAGE_PRODUCTION_CHANGE_ID=<approved change identifier>
TEMPLATE_TWIN_LINEAGE_PRODUCTION_ACK=<database-name>:<phase>
TEMPLATE_TWIN_LINEAGE_APPROVED_TARGET_FINGERPRINT=<fresh verified lowercase phase fingerprint>
```

The production acknowledgement and fingerprint are phase-specific and must be
updated from a fresh status challenge before every invocation. Contract also
requires `TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK` as shown above. Their presence is
an execution guard, not production authorization. This PR does not authorize
setting them.

## Pause, resume, recovery, and rollback

- **Pause:** terminate between batches or use `--max-batches`. Do not edit the
  progress row. Template Twin stays disabled.
- **Opposing operator:** `LINEAGE_MIGRATION_OPERATOR_BUSY` means another command
  holds the whole-command session lock. Inspect the approved operator session;
  do not bypass the lock. PostgreSQL releases it automatically if that session
  crashes.
- **Batch lock/statement timeout:** status records only a stable failure code.
  Resolve the conflicting transaction or lower batch size, then rerun.
- **Interrupted concurrent index:** PostgreSQL can leave an invalid index
  shell. Before any drop, the operator proves that the fixed-name object is the
  expected persistent btree index on the exact table, with the exact
  uniqueness, key attributes/order, predicate, expression/options, and
  dependency topology; only health bits may reflect the interrupted build. It
  then drops that proven shell with `DROP INDEX CONCURRENTLY`, recreates it, and
  verifies the complete healthy catalog contract. A wrong same-name object
  fails closed and is never modified.
- **Expand failure:** because expand is an explicit transaction, verify its DDL
  rolled back, preserve the failed-attempt row/diagnostic, and take a fresh
  protected snapshot. The closed runner rejects an unresolved attempt. A
  separately reviewed DBA forward-reconciliation decision must address that
  exact failure before a new status/fingerprint and approved unchanged
  `lineage-expand` retry. This runbook does not authorize ledger repair.
- **Validation failure:** phase cannot become `VALIDATED`; do not contract.
- **Contract lock timeout:** the transaction rolls back and cannot report
  `CONTRACTED`. Retry after the blocker is gone.
- **Application rollback after contract:** keep the additive schema, all
  progress/evidence, and rollout controls disabled. Use only a reviewed current
  image carrying the `template-twin-final-schema-v2` protocol epoch in
  `rollback-compat-v2` mode. Pre-stack images are incompatible once lineage is
  `NOT NULL` and are prohibited. Follow
  `docs/runbooks/template-twin-rollback-compat-v2.md`; do not drop columns,
  tables, indexes, triggers, outbox rows, or clinical evidence.
- **Data rollback:** none is needed for the deterministic `lineageId=id`
  backfill. Destructive reversal is prohibited; database restore requires its
  own approved incident/change procedure.

## Earlier development checksum

The committed migration previously contained an unbounded `UPDATE`, immediate
`SET NOT NULL`, and plain indexes. No production database applied it. Its file
now has a different checksum by design.

- A disposable local/QA database that applied the earlier checksum **must be
  destroyed and recreated from main plus the new migrations**.
- Do not update `_prisma_migrations`, copy a checksum, or use `migrate resolve`
  to pretend the new SQL ran.
- A non-disposable environment that applied the earlier checksum is blocked
  from this automated path. Preserve a snapshot and escalate for an explicit
  DBA reconciliation plan. Do not improvise an in-place checksum repair.

This is deliberately stricter than hiding drift: independently reviewable
migration history is part of the release evidence.

## Prisma migration history and future schema changes

This rollout has a **composite migration state**:

1. versioned Prisma expand migrations; plus
2. the versioned lineage operator contract recorded by
   `template_twin_lineage_migration_progress` and PostgreSQL catalogs.

Therefore the closed `lineage-expand` cumulative segment intentionally produces
the transitional nullable shape, while `schema.prisma` describes the final
contracted shape. A raw one-shot deploy is not an operations entrypoint. This
is not permission to ignore drift. It is the unavoidable representation of a
data migration and `CREATE INDEX CONCURRENTLY` that cannot safely execute in the
normal migration transaction.

Until a production rollout has completed and a separately reviewed post-rollout
baseline is committed:

- application promotion and rollout enablement must query the progress/catalog
  proof and fail unless it is `CONTRACTED`;
- `prisma validate` and client generation remain usable read-only development
  checks; release mutation remains limited to the closed cumulative runner, and
  a fresh uncontracted shadow is expected to report the lineage `SET NOT NULL`
  and full-index delta;
- do not accept a generated migration that reintroduces the full-table update,
  plain populated-table index, or automatic contract;
- prepare any future migration from a disposable database built by applying
  migrations **and then running guard/backfill/index/validate/contract** with
  synthetic data; use `prisma migrate diff --from-config-datasource` against
  the proposed schema and review the SQL; and
- keep a pre-operator `--from-migrations` diff and post-operator datasource diff
  in CI evidence. The scaled harness records hashes/booleans rather than raw SQL
  so no document content can enter the artifact.

After every approved environment is contracted, the next database-only change
must establish a reviewed migration-history baseline for this operational DDL.
That work must not edit old checksums or `_prisma_migrations`; it should be a new
forward baseline/migration epoch agreed with the database owner. Until then,
standard `prisma migrate dev` shadow generation for new schema work is a
**blocked gate**, not a reason to suppress drift warnings.

## Monitoring and evidence

Record only aggregate metadata:

- phase, durable cursor hash or opaque ID (never template content), processed
  row/batch counts, remaining null count, duplicate-group count;
- batch p50/p95/max duration, rows/second, WAL and replication lag;
- `pg_stat_activity` lock wait type/duration and blocked/failed write counts;
- concurrent-index `indisready`/`indisvalid`, constraint `convalidated`, column
  `attnotnull`, table/index sizes, and free disk;
- interruption time, committed cursor before/after restart, and idempotent
  second-run result.

Never record sections, styles, template names from existing data, users, visit
content, connection strings, or credentials.

The disposable harness defaults to one million synthetic rows and writes its
sanitized JSON evidence under `/tmp`:

```bash
npm run lineage:scale-test -w @meddoc/db
```

It reconstructs the exact main schema at
`1be101912f01293de3b8fddae722c823ecc86f29`, continuously reads/inserts/updates
generic synthetic templates, applies expand, builds the guard, kills a live
backfill after a durable barrier, resumes it, proves idempotency, builds and
validates indexes, attempts the contract, and destroys its PostgreSQL container.
Any row count below one million must be reported by its exact count and is not
production-scale proof.
