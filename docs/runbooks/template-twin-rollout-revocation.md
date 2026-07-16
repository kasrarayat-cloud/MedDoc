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
