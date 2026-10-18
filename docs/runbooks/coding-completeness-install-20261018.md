# Source coding completeness installation — 2026-10-18

`ops.activate_coding_completeness` is a new, inert controller. Its only starting
revision is `96f750f9d9c984db0839352777e099d740d87b72`. No previous controller,
plan, declaration, attempt directory or live testing purpose is reusable.
The release owner alone executes native commands. The controller submits zero
provider requests and creates no clinical approval or coding decision.

## Finite release boundary

The candidate must be the clean, cited merge commit on `origin/main`. Its entire
base-to-candidate delta must equal the plan's SHA-256 source map. The finite
allowlist currently comprises 19 paths: 12 runtime/migration/template/static
paths, three focused test modules, the new controller and its test, this runbook
and the named audit report. The executable constants are authoritative; no
glob, unrelated documentation, settings, provider policy, terminology catalogue,
credential, clinical generation, historical controller or migration path is
admitted. No source deletion is allowed.

The only environment delta is `QUILLMD_RELEASE_SHA`; every other byte, including
line endings and credential references, is retained. The only public asset input
is `rebuild/static/coding.js`. Its alias, gzip alias, immutable hashed twins and
`staticfiles.json` may change. Old hashed asset bytes, all other assets and all
other manifest routes remain fixed. Templates publish as candidate source.

The only database delta is migration `core.0032_coding_source_decision`: one empty
`core_codingsourcedecision` table, its exact indexes/constraints and the
`coding_source_decision_append_only` trigger calling the existing
`public.quillmd_append_only()` function. The table uses UUID identity, four
protected foreign keys, unique predecessor and a unique first decision per run.
Existing rows, explicit guards, functions and sequences remain fixed except for
the single exact migration ledger append and its sequence advance. Installation
does not backfill reviews, import references, add audit/content-type/permission
rows, or alter existing approval/export records.

## Independent schema rehearsal

Use isolated PostgreSQL **17**, with the same exact server version as the native
capture. Do not point rehearsal at the native database. The release owner prepares
the base through `MigrationExecutor` at migration0031, captures the catalog,
applies only0032 transactionally and captures it again. Ordinary `manage.py
migrate` sends `post_migrate` signals and is unsuitable here: the resulting
content-type/permission writes would violate the declared old-row preservation.

The new controller exposes two importable, non-mutating functions:

```python
# Each catalog capture runs inside an existing READ ONLY, REPEATABLE READ
# transaction on the isolated connection. Collection issues no writes.
before_catalog = catalog(connection)
after_catalog = catalog(connection)
contract = rehearsal_contract(
    plan, before_catalog, after_catalog,
    server_version_num="170011",
    role_mapping={
        "quillmd_source_owner": "quillmd_owner",
        "quillmd_source_runtime": "quillmd_runtime",
    },
)
```

The two captures bracket the migration in separate read-only transactions; the
example is an interface sketch, not an executable migration runner. The caller
must retain the isolated identity, migration transcript and positive/adversarial
schema/append-only evidence independently. The pure builder does not claim to
prove where its inputs originated.

Only typed owner/grantee/grantor fields on newly added table/index metadata are
normalized through the closed, explicit two-role mapping. SQL text, column
definitions and all old catalog entries are never rewritten. Rehearse the same
default grants: owner privileges and runtime SELECT/INSERT/UPDATE/DELETE only;
PUBLIC or additional grants refuse. The native runtime snapshot retains its
fixed `quillmd_fresh` / `quillmd_runtime` identity check without a test bypass.

The private contract binds the full candidate source map, migration bytes, exact
server version and measured additions: complete declared column metadata,
table owner/privileges/RLS, constraints, indexes and explicit trigger attributes.
The collector also watches functions/procedures, sequence metadata, policies,
default ACLs, views and rules. Internal FK trigger names contain database-local
OIDs; their exact declared FK constraints and the admitted CreateModel operation
govern those system-generated triggers instead. This is a finite public catalog
contract, not a claim to compare every PostgreSQL system catalog.

Migration source admission hashes the complete parsed syntax of the reviewed
generated file: imports, dependency, all model fields/options and the sole literal
append-only RunSQL. An extra import, RunPython, field change or SQL operation
refuses even if a constructed contract would otherwise look acceptable.

## Prospective plan and execution

Prepare a new owner-only private plan with the existing baseline-bound fields
plus `schema_contract_path` and `schema_contract_sha256`. Its closed format is
`quillmd-coding-completeness-native-install-v1`. Record the exact source map,
candidate, environment-before SHA, fresh read-only baseline path/SHA and schema
contract path/SHA. Shape validation admits uncreated capture paths; execution
must read and verify the real private bytes. No zero-hash placeholder executes.

Capture a fresh baseline of all current database rows/catalogs/migration rows,
clinical files, static files, service configuration and foreign running services.
The baseline must use this controller's richer snapshot, be no more than one
hour old, and bind this exact candidate/source manifest. Use measured counts;
do not copy prior table, migration or file counts. All 13 preserved encounters
and their actual clinical/coded Word receipts belong in the separate record
inventory. Preserve the failed generation, previous installation refusals and
their complete provenance.

Commit the prospective declaration in an isolated execution worktree. It must
name the exact plan SHA, candidate and controller format, state the schema/static
delta and strict preservation limits, account for active overlapping owners and
bind the completed refutation plus exact merge CI citation. Execute only through
the established `run-ruled-mutation.sh` wrapper. The default module invocation is
inert and reads no operational inputs.

Under operation and activation-exclusion locks, the controller captures another
baseline and compares it **before any stop or publication**. Only a same-count
`core_servicehealth` fingerprint refresh is permitted between the earlier
read-only observation and the locked baseline. Foreign-service additions or
disappearances, other row/metadata changes, changed files/configuration/static,
stale source/index or changed baseline/contract bytes refuse. Prior fwupd drift
is a demonstrated reason to prepare a fresh attempt, never a reason to waive
the service identity check.

The controller then stops and verifies exactly doctor/admin/worker, retains the
after-stop snapshot and requires full locked-baseline equality. It publishes
the cited source, rechecks migration admission, applies only0032 transactionally,
retains the post-migration snapshot and judges its exact contract. It publishes
the bounded static delta and release stamp, then retains a fourth snapshot and
requires exact equality to the post-migration snapshot before starting services.
All clinical files and unrelated services/configuration must still match. The
receipt hashes all four raw snapshots, the contract and pre-stop comparison.
Normal HTTPS must report the exact candidate and all three owned units must be
active before completion is written. Strict database preservation ends before
resume; later normal health observations may write their ordinary health rows.

Fingerprints reuse `sha256-sorted-jsonb-row-sha256-count-v1`: fixed 32-byte row
hashes sorted by PostgreSQL and consumed by a bounded named cursor, retaining
duplicates and count framing. All row/catalog/ledger/pending reads share one
read-only repeatable-read transaction. No whole-table JSON aggregation is used.
One exceptionally large row still requires its own serialization memory; this
is not an arbitrary-row memory ceiling.

## Failure and recovery

Every attempt has exclusive evidence paths. A refusal or transport failure never
silently retries or overwrites an earlier receipt. Diagnostics retain safe stage,
class, SQLSTATE and connection classification, never raw exception text, SQL or
credential values. Raw post-stop/post-migration/pre-resume snapshots are retained
before judging them.

Before source publication, an unchanged original release may resume only after
its clean HEAD/index, environment, file proofs and absence of new paths are
verified under the locks. `publication_attempted` is set before Git publication;
partial publication can alter runtime files while leaving HEAD old. Once source
publication or migration is attempted, the controller never automatically
restarts old code or rolls back clinical/schema state. Migration failure or a
failed preservation proof leaves the owned units stopped. Any failure after
resume begins attempts every owned stop and verifies every unit, retaining an
explicit incomplete-drain result if one fails.

## Required proofs and ordinary verification

Run the focused controller tests with the installed Python environment; they use
only isolated temporary files, mocked lifecycle operations and temporary Git
repositories. Independently refute the finished operator/migration/runtime diff.
The release owner additionally runs the isolated real-PG migration and append-only
controls, validates the entire rehearsal contract and reviews actual native
receipts. Mocked tests do not substitute for those schema proofs.

After installation, use normal HTTPS as the authorized synthetic clinician.
Source coverage review and additional coding approval are separate, purpose-bound
application actions, not installer work. For existing Tessa, preserve every
original source/generation/approval/provider row and old Word object while
admitting only the explicit new review/approval/export records. Compare original
rows as an exact subset when those additions are intentional; do not falsely
claim unchanged whole encounter payloads after a new decision.

Download the prior coded Word through its retained export identity **after** the
new approval, plus the newly approved Word. Require the old artifact to remain
byte-identical and accessible, the clinical body/destinations to remain fixed,
and the new appendix to contain only the newly approved set. File hashes alone
do not prove old-download accessibility. Preserve the other 12 encounters,
prior clinical/coded artifacts, approvals, reviewers, timestamps and audit rows.
Report source-coverage/classifier limitations and actual provider usage honestly;
installation completion is not workflow acceptance.
