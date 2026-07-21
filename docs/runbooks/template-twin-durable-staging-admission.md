# Template Twin durable synthetic-QA admission

## Boundary

Synthetic QA is a default-off, non-clinical workflow. Environment flags,
routes, fixture names, and request-local provider context are safety gates but
are not authorization. PostgreSQL is the authorization source.

Before the first synthetic inspection, privacy, transcription, or model
callback, the app commits a `TemplateTwinSyntheticQaAdmission` root or child
row and rereads it through the root Prisma client. The provider boundary checks
the exact practice, active physician, allowlisted source digest and byte count,
template/version, provider mode, lifecycle phase, expiry, and pinned global and
practice rollout generations. The raw context constructor is not exported from
the public AI package surface.

No document text, encounter text, audio, field value, token, object URL, or
credential is stored in admission metadata. Only opaque identifiers, hashes,
versions, states, timestamps, and rollout generations are retained.

## State and retry contract

The database transition trigger permits only:

`ADMITTED -> SOURCE_VERIFIED -> TEMPLATE_LINKED -> CERTIFIED -> VISIT_LINKED -> PROCESSING -> REVIEW_READY -> SIGNED`

An active state may transition to `FAILED` or `REVOKED`. `SIGNED`, `FAILED`,
and `REVOKED` are terminal and cannot be revived. A signed child must carry the
same-transaction `consumedAt` proof. Failed or revoked provider admissions need
a new admission; they cannot be retried under an old capability.

Queue or object-store admission can fail before a provider owns a run. That
case stays `VISIT_LINKED`, records a durable run failure and outbox event, and
allows exactly one monotonic attempt advance. Replaying the same retry does not
create another run, job identity, object, or audit event. Review regeneration
uses the separately allowed `REVIEW_READY -> VISIT_LINKED` transition while
incrementing the same admission attempt.

## Tenant and lineage backstops

Database triggers and foreign keys require:

- the actor is an active `DOCTOR` in the admission practice;
- a visit child has a certified root parent for the same actor, practice,
  source, template/version, certification, mapping hash, and rollout
  generations;
- source bytes match the single reviewed synthetic fixture;
- template, compilation, source artifact, certification, synthetic patient,
  visit, and run all share one immutable lineage; and
- each run has exactly one child admission already committed at
  `VISIT_LINKED`.

Existing generic templates receive no admission row and remain ordinary when
synthetic QA is not requested. When synthetic QA is requested, the settings
query returns only templates related to a current root admission; generic
templates cannot fall through certification, processing, review, signing, or
download.

## Migration and expected locks

`20260717170000_template_twin_durable_staging_admission_v1` is additive. It
creates one empty admission table, adds one nullable legacy-compatible foreign
key column to the already default-off staging-run table, replaces that table's
lineage trigger, and adds audit enum values. It contains no data backfill and
does not rewrite or auto-admit existing templates, visits, or runs.

The migration runs in one transaction with `lock_timeout = 2s` and
`statement_timeout = 30s`:

- audit enum additions briefly lock the enum catalog;
- the new table, its checks, foreign keys, indexes, and triggers do not scan an
  existing application table;
- `ALTER TABLE template_twin_synthetic_qa_runs ADD COLUMN` and trigger
  replacement require short table-definition locks on that default-off table;
- the new foreign key reads the referenced admission index; and
- no lock is taken for a clinical-row backfill because none exists.

If a conflicting transaction holds the staging-run table longer than two
seconds, the complete migration transaction rolls back. Verify that the new
table and run column are absent, record the non-PHI blocker, let the owning
transaction finish, preserve the failed-attempt row and diagnostic, and take a
fresh protected snapshot. The closed runner rejects an unresolved attempt. A
separately reviewed DBA forward-reconciliation decision must address that exact
failure; this runbook does not authorize a ledger-repair command. Do not
increase timeouts, edit a migration checksum or ledger, or run raw Prisma
deploy/resolve.

Only after the reviewed reconciliation may the exact unchanged migration be
retried through the closed `auth-expand` cumulative segment. Run
`docker compose run --rm db-migrate --phase status`, independently verify the
exact ledger prefix/target and fresh `targetFingerprints.auth-expand` entry,
and follow the phase-specific approval flow in `docs/DEPLOYMENT_RUNBOOK.md`
§1.4.1. The entry is ledger-, accepted-source-, phase-, and target-bound; never
reuse it for a retry or derive it when status emits no entry. The lineage
contract must already be exactly `CONTRACTED`.

## Deployment, rollback, and retained evidence

Apply only through the closed status-and-approved `auth-expand` segment after
taking the existing backup and change-control gates. Fresh-database and
data-bearing 73-to-74 upgrade tests must both pass. Confirm that the admission
table is empty after upgrade and that existing structured templates retain
their lineage, version, status, and kind.

Application rollback is to disable the synthetic staging process gate and the
global/practice rollout gates. Keep the additive schema and immutable evidence;
do not down-migrate or delete rows or objects from a request path. Rejected or
unclaimed objects continue through the existing object-ledger reconciliation
workflow.

This runbook does not authorize production migration, provider access, real
PHI, Microsoft Word approval, or production enablement.
