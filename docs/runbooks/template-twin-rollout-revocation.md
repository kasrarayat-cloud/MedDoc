# Template Twin rollout revocation

Template Twin has three independent, fail-closed rollout boundaries:

1. `TEMPLATE_TWIN_KILL_SWITCH=false` must be present in each app and worker
   process. This remains a boot/runtime safety boundary; a process-local
   environment read is not described as transactionally linearizable.
2. The singleton `template_twin_rollout_controls(id='global')` row must be
   enabled.
3. The owning `practices.templateTwinEnabled` row must be enabled.

The persisted rows each carry a positive, monotonic generation. The global row
is seeded **disabled** at generation 1, and every practice remains disabled by
default. Template Twin cannot be enabled until
`template_twin_lineage_migration_progress(operationKey='note_templates_lineage_v1')`
is in phase `CONTRACTED`.

## Rollout-generation migration lock envelope

Migration
`20260716113000_template_twin_rollout_generations` installs the persisted
generation contract. It is one explicit PostgreSQL transaction:

```sql
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';
-- complete additive rollout-generation DDL
COMMIT;
```

The `SET LOCAL` values apply to every subsequent statement and disappear on
commit or rollback. They do not leak into Prisma's connection pool or the next
migration. The two-second value bounds each wait to acquire a lock; it is not a
two-second bound on the whole migration. The 30-second value independently
bounds each DDL statement. Prisma's migration advisory lock still serializes
migration runners; these PostgreSQL bounds protect ordinary application/table
contention after that advisory lock is obtained.

Expected locks, in migration order:

1. Both `ALTER TABLE practices` statements require `ACCESS EXCLUSIVE`. The
   first granted lock is held through commit.
2. `CREATE TABLE template_twin_rollout_controls` holds `ACCESS EXCLUSIVE` on
   that new relation; its seed `INSERT` takes `ROW EXCLUSIVE`. The function DDL
   also takes ordinary write locks on its new PostgreSQL catalog rows.
3. Each `CREATE TRIGGER` requires `SHARE ROW EXCLUSIVE` on its target. The
   global trigger targets the new rollout-control table. The practice trigger
   reuses the stronger `ACCESS EXCLUSIVE` lock already held on `practices`.
4. Both `ALTER TABLE template_twin_fill_manifests` statements require
   `ACCESS EXCLUSIVE`, also held through commit. The second statement adds the
   three generation-pair proof constraints; the signed-match proof remains
   `NOT VALID` for historical immutable rows.

Consequently a conflict on either populated table fails closed. The explicit
transaction rolls back the earlier column, table, seed, functions, triggers,
and constraints as one unit. A later conflict on
`template_twin_fill_manifests` cannot leave the earlier `practices` change or
global singleton installed.

Prisma currently reports a lock timeout inside this explicit transaction as a
non-zero migration failure ending in `current transaction is aborted`; the
PostgreSQL server diagnostic retains the originating `55P03`/lock-timeout
reason. Do not treat the less-specific Prisma terminal message as evidence that
the bound was absent. Require all of the following before retry:

- PostgreSQL recorded the lock-timeout reason and the elapsed wait was bounded;
- `_prisma_migrations.finished_at` is null for the failed attempt;
- every rollout-generation column/table/function/trigger/constraint remains
  absent; and
- pre-existing practice/template data is unchanged.

After the conflicting transaction is identified and safely cleared, mark only
that verified failed attempt rolled back and rerun the unchanged migration:

```bash
prisma migrate resolve --rolled-back \
  20260716113000_template_twin_rollout_generations
prisma migrate deploy
```

Do not delete or update `_prisma_migrations` manually, use `--applied`, or retry
while the blocker remains. A second `migrate deploy` after success must report
no pending migration. Rollout stays disabled throughout installation and retry.

The focused disposable proof is:

```bash
node_modules/.bin/tsx \
  packages/db/scripts/template-twin-rollout-migration-lock-test.ts
```

It creates isolated synthetic PostgreSQL databases from the actual preceding
70 migrations, invokes the real `prisma migrate deploy/resolve` runner, and
uses a granted `ACCESS SHARE` lock as a deterministic barrier. One scenario
blocks the first `practices` DDL; a second blocks the later fill-manifest DDL
after the migration has performed earlier work. Each scenario proves atomic
rollback, unchanged synthetic data, reviewed rollback resolution, complete
retry, and an idempotent no-pending run. The harness accepts only PostgreSQL
diagnostics appended during that scenario and requires the failed statement to
name the expected blocked table; an earlier scenario's server log cannot prove
a later timeout. Sanitized evidence is written to
`/tmp/template-twin-rollout-migration-lock-evidence.json`. The harness starts
and destroys its own loopback-only `pgvector/pgvector:pg16` container and never
accepts a production database URL.

### Development checksum handling

This migration changed before any production application. A disposable
development/QA database that successfully applied its earlier checksum must be
destroyed and recreated from the committed migrations. Do not copy the new
checksum into `_prisma_migrations` or use `migrate resolve` to disguise drift.
A non-disposable environment that recorded the earlier successful checksum is
blocked pending a reviewed DBA forward-reconciliation plan and snapshot; the
automatic retry procedure above does not apply to checksum drift. It applies
only to a failed attempt of the current checksum whose full transactional
rollback was independently verified.

## Linearization protocol

Every worker render, correction, signing request, and original-template
download pins the current global and practice generations at admission. For a
worker, admission is the exact transaction that authorizes the selected
Template Twin version: that token is returned with the selection, carried
unchanged through L4-L6, and supplied to fill/render finalization. The fill
engine must never replace it with a newer token. Any expensive DOCX or
object-storage work happens outside the final database transaction.

The final transaction always locks rows in this order:

1. global rollout control `FOR UPDATE`;
2. owning practice `FOR UPDATE`;
3. operation-specific visit/fill rows.

The synthetic staging workflow extends (and does not replace) that ordering.
Its complete order is global rollout, practice, durable staging run, current
actor, visit, then fill manifest or output claim when that operation uses one:
`global -> practice -> run -> actor -> visit -> fill/output`. A transaction
may omit rows that are not applicable, but must never reverse the relative
order of rows it locks. Re-locking the actor at this boundary ensures that
tenant membership, active state, and the DOCTOR role have not been revoked
after admission.

It then rereads enabled state and both generations, verifies the lineage phase
is `CONTRACTED`, and compares the rows with the admission token. The clinical
transition/output claim and its PHI-safe audit-outbox event commit in the same
transaction. The transaction commit is the final claim's linearization point.

Global disable locks the global row. Practice disable locks global and then the
practice. A successful disable transaction increments the relevant generation.
Therefore either a final claim commits before disable obtains the rollout lock,
or disable commits first and the older operation observes disabled/stale state
and is rejected. Re-enabling increments generation again; it never revives an
old token or output.

Database triggers prevent direct enabled-state changes from retaining the old
generation and reject generation rollback. Controlled service operations also
increment the generation for repeated toggles, producing an unambiguous audit
epoch.

`setTemplateTwinGlobalRollout` and `setTemplateTwinPracticeRollout` are the
only controlled mutation boundary: they take the documented locks, enforce the
lineage prerequisite, increment generation, and enqueue the operator audit in
one transaction. This slice deliberately exposes no production HTTP/admin
endpoint for those functions. Until a separately authorized Operations/admin
surface supplies fresh privileged identity and change control, production
rollout therefore remains disabled. Direct SQL flag changes are not an
approved operating procedure; the triggers protect generation monotonicity but
cannot supply the required application actor/audit context.

## Rejected work and immutable evidence

DOCX bytes written before a rejected final claim stay
`WRITTEN_UNCLAIMED` in the object ledger. Request paths do not delete them.
Normal reconciliation applies the configured retention/purge policy. The
rejection audit records only identifiers, generation strings, stable reason
codes, and whether an unclaimed output was written—never document or field
content.

Unsigned legacy manifests without pinned generations fail signing and export
and must be regenerated. A new signed transition stores signed generations
equal to the output's pinned generations. Existing signed rows are never
rewritten, but legacy/null or stale-generation output is not downloadable.

## Stable refusal codes

- `TEMPLATE_TWIN_KILL_SWITCH_ACTIVE`
- `TEMPLATE_TWIN_GLOBAL_DISABLED`
- `TEMPLATE_TWIN_PRACTICE_DISABLED`
- `TEMPLATE_TWIN_GLOBAL_GENERATION_STALE`
- `TEMPLATE_TWIN_PRACTICE_GENERATION_STALE`
- `TEMPLATE_TWIN_LINEAGE_MIGRATION_INCOMPLETE`
- `TEMPLATE_TWIN_ROLLOUT_CONTROL_UNAVAILABLE`
- `TEMPLATE_TWIN_OUTPUT_ROLLOUT_STALE`
- `TEMPLATE_TWIN_OUTPUT_CLAIM_STALE`

These codes instruct the physician to refresh/regenerate after rollout is
enabled; they do not reveal clinical data.

## Verification gates

Deterministic unit tests pause work at explicit barriers between admission and
final claim. The disposable-PostgreSQL proof
`npm run rollout:pg-test -w @meddoc/db` uses independent connections and
`pg_blocking_pids`, without timing sleeps. It imports the same global/practice
mutation, final-lock, object-ledger claim, and audit-outbox helpers used by the
application. Against a synthetic fill and `WRITTEN_UNCLAIMED` ledger row, it
proves both practice and global disable commit ahead of a waiting final claim;
the stale claim records a blocker outbox event while leaving the clinical fill
and object claim unchanged. A valid control claim proves the fixture can reach
`VERIFIED`/`CLAIMED`; changing only its audit event key to a deliberate unique
collision then proves that the fill and ledger updates roll back with the
outbox failure. This is a PostgreSQL transaction/locking gate only—not object
storage, queue, worker-process, or Office compatibility validation.

The proof refuses any database that does not have an explicit QA/test/CI name,
requires the lineage phase to be `CONTRACTED`, uses only `synthetic.test`
identity/content, and retains its immutable source row only inside the
disposable database. Destroy that database after collecting the sanitized
JSON result.

The environment kill switch remains additional defense in depth. Linearizable
global revocation is performed through the persisted global-control operation,
not by claiming that environment propagation is atomic across processes.
