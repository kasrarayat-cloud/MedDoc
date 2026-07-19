# Template Twin NoteTemplate lineage online migration

Status: **required first-deployment runbook; not authorized for production by this PR**

This runbook replaces the original one-transaction `UPDATE note_templates`
backfill. It is intentionally separate from `prisma migrate deploy`: PostgreSQL
cannot build indexes concurrently inside a transaction, and a million-row data
rewrite does not belong in an application schema migration.

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

Only one lineage operator runs at a time. The CLI first obtains the PostgreSQL
**session** advisory lock for
`template_twin_note_templates_lineage_operator_session_v1` on a dedicated
connection and holds it until the complete command returns. This is load-bearing:
transaction locks cannot span standalone `CREATE/DROP INDEX CONCURRENTLY` or
`VALIDATE` statements. An opposing CLI fails immediately with
`LINEAGE_MIGRATION_OPERATOR_BUSY`; it must not overlap or alter progress.

Within that command, every transactional phase also takes the transaction-scoped
advisory lock for `template_twin_note_templates_lineage_online_v1`, then locks
the single progress row. The second lock protects library-level transactional
calls; its distinct key avoids a process blocking itself behind its dedicated
session lock. No operator uses `SKIP LOCKED` because a primary-key cursor must
never advance past a temporarily locked row.

| Phase | Work | Expected PostgreSQL locks | Bound / write behavior |
| --- | --- | --- | --- |
| Expand | Add nullable columns, transition trigger, progress table and new empty Template Twin tables | Brief `ACCESS EXCLUSIVE` on `note_templates`; ordinary DDL locks on new objects | One explicit transaction; `lock_timeout=2s`, `statement_timeout=30s`; failure rolls the phase back |
| Guard index | Partial unique index over populated lineages | `CREATE UNIQUE INDEX CONCURRENTLY`; `SHARE UPDATE EXCLUSIVE` phases, brief catalog locks | Runs outside a transaction with 2s lock and 15m statement limits; backfill refuses to start until `indisvalid` and `indisready` are true |
| Backfill | `lineageId=id`, ordered by primary-key cursor | `ROW EXCLUSIVE` table intent plus row locks for at most the configured batch and one progress-row lock | Default 1,000 rows, maximum 10,000; 30s statement/2s lock limit; cursor and rows commit atomically |
| Final indexes | Full unique lineage/version and doctor/kind/status indexes | `CREATE [UNIQUE] INDEX CONCURRENTLY`; `SHARE UPDATE EXCLUSIVE` phases | Outside transactions, 2s lock and 15m statement limits; invalid shells are detected and rebuilt, then catalog-verified |
| Add proof | Add `CHECK (lineageId IS NOT NULL) NOT VALID` | Conservatively plan for a brief `ACCESS EXCLUSIVE` metadata lock | 2s lock limit; no table scan |
| Validate proof | Validate the check | `SHARE UPDATE EXCLUSIVE` | Allows normal reads and row writes; 30s statement limit by default and must be sized from synthetic evidence |
| Contract | Set column `NOT NULL`, remove transition trigger, set progress `CONTRACTED` | Brief `ACCESS EXCLUSIVE` on `note_templates` | 2s lock limit; PostgreSQL uses the validated check instead of rescanning; one transaction |

The contract transaction commit is the schema linearization point. Before it,
the feature stays unavailable. After it, every committed row is non-null and the
full unique index is independently valid. A lock timeout is a failed attempt,
never a pass; remove the blocker and rerun the same idempotent phase.

## Forward deployment

The commands below omit the database URL deliberately. Supply it through the
approved deployment secret mechanism; never paste it into a ticket or log.

1. Confirm both rollout layers are disabled and record an approved database
   backup/restore point, current migration status, row count, PostgreSQL version,
   free disk, replication lag, and the current checksum of the expand migration.
2. Apply schema migrations using the reviewed migrator image. The expand phase
   must finish within its lock and statement bounds. If it fails, stop.
3. Inspect, without printing template content:

   ```bash
   npm run lineage:online -w @meddoc/db -- --phase status
   ```

   Expected: `phase=EXPANDED`, `columnNotNull=false`, and a non-negative null
   count. Migration status alone is insufficient.
4. Establish transition-safe uniqueness:

   ```bash
   npm run lineage:online -w @meddoc/db -- --phase guard-index
   ```

   Do not deploy/promote new application processes until status reports
   `phase=GUARDED` and the partial index is present, ready, and valid.
5. Run bounded batches. Start conservatively and tune only from measured lock,
   WAL, replication, and request-latency evidence:

   ```bash
   npm run lineage:online -w @meddoc/db -- \
     --phase backfill --batch-size 1000 --batch-delay-ms 100
   ```

   `SIGINT`/`SIGTERM`, process loss, or a database restart is safe: the last
   committed cursor remains in the progress row. Rerun the same command. A
   failed batch cannot advance its cursor.
6. Require `phase=BACKFILLED`, `nullRows=0`, and zero duplicate
   `(lineageId,version)` groups. Rerun backfill once and require zero changed
   rows as the idempotency proof.
7. Build and verify final indexes outside a transaction:

   ```bash
   npm run lineage:online -w @meddoc/db -- --phase indexes
   ```

8. Add and validate the proof constraint:

   ```bash
   npm run lineage:online -w @meddoc/db -- --phase validate
   ```

   Require `phase=VALIDATED`, a validated check, both final indexes valid/ready,
   no nulls, and no duplicates.
9. Schedule the short contract lock during a monitored low-write window. The
   exact acknowledgement prevents accidental invocation:

   ```bash
   export TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK='note_templates_lineage_v1:<database-name>'
   npm run lineage:online -w @meddoc/db -- --phase contract
   unset TEMPLATE_TWIN_LINEAGE_CONTRACT_ACK
   ```

10. Require `phase=CONTRACTED`, `columnNotNull=true`, transition trigger absent,
    and final indexes valid/ready. Only then may a separately approved rollout
    operation enable Template Twin.

Production use additionally requires all of these explicit variables:

```text
TEMPLATE_TWIN_LINEAGE_ALLOW_PRODUCTION=true
TEMPLATE_TWIN_LINEAGE_PRODUCTION_CHANGE_ID=<approved change identifier>
TEMPLATE_TWIN_LINEAGE_PRODUCTION_ACK=<database-name>:<phase>
```

Their presence is an execution guard, not production authorization. This PR
does not authorize setting them.

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
  shell. The operator checks `pg_index`, drops only the fixed-name invalid shell
  with `DROP INDEX CONCURRENTLY`, recreates it, and verifies validity.
- **Expand failure:** because expand is an explicit transaction, verify its DDL
  rolled back. Only then may the migration be marked rolled back under the
  standard reviewed Prisma failed-migration procedure and retried.
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

Therefore `prisma migrate deploy` alone intentionally produces the transitional
nullable shape, while `schema.prisma` describes the final contracted shape.
This is not permission to ignore drift. It is the unavoidable representation of
a data migration and `CREATE INDEX CONCURRENTLY` that cannot safely execute in
the normal migration transaction.

Until a production rollout has completed and a separately reviewed post-rollout
baseline is committed:

- application promotion and rollout enablement must query the progress/catalog
  proof and fail unless it is `CONTRACTED`;
- `prisma validate`, client generation, and `migrate deploy` remain usable, but
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
