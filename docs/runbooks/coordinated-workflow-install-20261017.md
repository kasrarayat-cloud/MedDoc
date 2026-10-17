# Coordinated clinical and coding installation

This is prepared machinery, not an installation record. The lead owns release,
provider requests and browser verification. `python -B -m
ops.activate_coordinated_workflow` is inert without `--execute`. This new
controller starts from `7e2db4f2b16db806a5953427a8e8c11483bcf086`; never rerun a
consumed supporting-facts or other activation controller, plan or attempt.

The finite source boundary admits `semantic_generation.py`, `jobs.py`, the new
`clinical_source_context.py` helper, `corti_coding.py`, `corti_semantics.py`,
`coding_engine.py`, `coding_dispatch.py`, `coding_output.py`, the
explicitly named focused tests and synthetic fixtures, this new operator/test
and this runbook. `RUNTIME`, `SUPPORT` and `FIXTURES` in the operator contain
every admitted path. The actual complete committed delta must equal the plan's
source hashes. The three admitted fixtures are the retained Elias clinical and
coding responses and `iris_clinical_constructed.json`, containing constructed
offline proposals for the approved unfamiliar 34-field template; the latter is
not provider output or evidence of live acceptance. The boundary contains 18
explicit paths. An additional path requires a reviewed explicit boundary change;
no directory wildcard is permitted. Historical source-context helpers,
recovery controllers, coding output policies/references, settings, templates,
static assets, migrations, service units and credentials are outside this act.

Only the `QUILLMD_RELEASE_SHA` environment line changes. Every other environment
byte remains identical, including Corti admission, credentials, output-reference
hashes and historical recovery configuration. There is no DDL, migration,
entitlement change or terminology waiver. The installer submits no provider
request and creates no clinical or coding decision.

All current database table fingerprints, migration rows including their IDs and
timestamps, sequences and watched catalog/function properties must remain equal
before stopping, after stopping and immediately before resuming. The catalog
comparison covers its named properties, not every possible PostgreSQL property.
All clinical files, static bytes, unrelated configuration and unrelated services
remain fixed. Only the existing doctor, admin and worker units restart. Pending
generation/provider work refuses installation.

This controller uses the explicit snapshot contract
`sha256-sorted-jsonb-row-sha256-count-v1`. PostgreSQL serializes each complete row
with `to_jsonb`, hashes its UTF-8 text to 32 bytes, and sorts only those hashes.
A named cursor fetches at most 128 hashes per batch. Python folds every sorted
digest, including duplicates, into a domain-separated SHA-256 and appends the
eight-byte row count. No whole-table JSON concatenation or client hash list is
built. The sort uses 4 MB `work_mem` and may spill to disk; an individual row
still requires serialization memory, so this is not a fixed ceiling for an
arbitrarily large row. All row, catalog, migration-ledger and pending-work
observations share one read-only repeatable-read transaction. Watched tables
and sequences are explicitly qualified with the public schema.

The new snapshot contract is not hash-compatible with historical aggregate-MD5
receipts. Preserve those receipts and historical controllers unchanged; take
fresh baseline/after-stop/before-resume snapshots with this one contract. The
contract marker participates in strict equality. The failed aggregate baseline
is retained as a failure, not relabeled as a completed baseline. Changing the
fingerprint method does not expand the watched catalog properties or authorize
any data repair.

Preserve the original Elias failure, Nadia's original failure and both completed
successors, and Rowan's saved review: source/template bytes, raw stages, answers,
validation history, approvals, reviewer/timestamps, coding facts, audits, usage,
unknown reservations and existing Word downloads. Existing jobs keep their
recorded historical validation contracts. No snapshot is restored, no failed
answer is edited, and no existing decision is reopened by this installation.

1. Finish focused positive/adversarial controls and independent finished-diff
   refutation. Use the guarded PR/merge process, then wait for the required
   workflows on the exact merged full revision. Keep the candidate worktree
   clean at that revision and shared `/opt/meddoc-pro` clean on `main` at the
   exact installed base. Coordinate with the deployment owner.
2. Capture a fresh read-only full baseline. Cross-check overlapping historical
   declarations using actual completion evidence; explicitly preserve/defer any
   unresolved owner-browser, native Word or unknown-accounting obligations.
   An old date is not proof that an act completed, and a completed installation
   does not discharge its separate acceptance obligations.
3. Bind a new private closed plan with format
   `quillmd-coordinated-workflow-native-install-v1`, exact base/candidate,
   complete source hashes, clean candidate worktree, unused private evidence
   directory, current protected environment SHA-256, `environment: {}` and
   `static: []`. Commit a prospective declaration in a separate execution
   worktree descended from the candidate. Bind the full candidate, plan hash,
   format, finite source scope, release-only delta and current preservation.
4. From the execution worktree, invoke `scripts/run-ruled-mutation.sh
   --declaration <absolute committed declaration>` with
   `env PYTHONPATH=<clean candidate>/rebuild` and the installed venv Python
   executing `-B -m ops.activate_coordinated_workflow --execute --plan
   <new private plan> --plan-sha256 <exact hash>`. Retain wrapper supervision.
   The operator checks the committed declaration bytes and exact candidate CI.
5. Independently judge the result against the declaration. Verify source and
   environment bytes, normal HTTPS full revision, preserved records and files,
   and active owned services. Do not infer fresh clinical acceptance from an
   installation receipt. Use separately purpose-bound ordinary HTTPS synthetic
   successor tests, independent complete-source/answer review, approval, reload
   persistence and actual clinical/coded Word downloads. Recheck the saved
   Nadia and Rowan reviews and byte-identical existing downloads without
   reopening those decisions. No consumed provider allowance is renewed.

The private attempt retains `baseline.json`, including the full database
fingerprint/catalog snapshot and static inventory; `database-after-stop.json`;
and `database-before-resume.json`. Each later database snapshot is written
before comparison, so a refused difference is retained. Successful preservation
and completion receipts bind the SHA-256 of all three files. An evidence-write
failure prevents progression. The completion receipt also binds the exact plan
hash and execution declaration commit/hash. Environment bytes remain encrypted.
Strict database/file equality ends before services resume and before separately
authorized ordinary browser activity; post-resume service-health updates and
new synthetic audit events require their own honest classification.

Failure receipts retain the operation stage, sanitized exception class, valid
SQLSTATE, fixed connection-failure classification and known operator locations.
They never copy exception messages, SQL, credentials or clinical text. A missing
SQLSTATE is null, not a guessed cause. Before any source-publication attempt,
original-release recovery requires the base HEAD, clean tracked tree and index,
exact original environment/file proofs and absence of newly introduced paths.
After any publication attempt, automatic original-release recovery is forbidden
even if HEAD remains old: a failed fast-forward can already have changed runtime
files and the index. After new services begin starting, any failure before
completion attempts to stop every owned unit and verifies every unit inactive
while retaining coordination locks. Stop/verification failures remain explicit;
the operator cannot claim a shutdown it did not verify. There is no automatic
retry, overwritten attempt or clinical rollback. Diagnose actual state before a
new prospective recovery act.

Focused offline controls (temporary Git repository and mocked operational
transports; no native database, provider or service mutations):
`PYTHONPATH=rebuild python -B -m unittest ops.test_activate_coordinated_workflow`.
Optional real-SQL tests require `QUILLMD_SNAPSHOT_TEST_DSN` with exactly localhost
`127.0.0.1:55449`; other hosts, ports and connection-routing options are refused
before connecting. They use a temporary table and never call the native snapshot
identity boundary. The large-row control additionally requires
`QUILLMD_SNAPSHOT_TEST_REFERENCE` pointing to the private retained coding-reference
JSON. The release owner runs this isolated proof separately; unset variables
skip it, and a skipped integration check is not a passing database proof.
