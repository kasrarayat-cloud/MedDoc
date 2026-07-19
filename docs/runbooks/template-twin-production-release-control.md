# Template Twin production release control

Status: TECHNICAL CONTROL IMPLEMENTED — production authority and human gates pending
Owner: Operations (named human owner required before rollout)
Applies to: `admin.quillmd.com` production release workbench

This runbook operates the fixed Template Twin rail: Disabled → Canary → 10% →
25% → 50% → 100%. It does not authorize a release by itself. Desktop Microsoft
Word, Clinical Safety, Privacy/Legal, Operations, restore, exact-head review,
and production infrastructure evidence remain separate gates.

## Invariants

- The environment kill switch and database global gate start disabled.
- One immutable release identity binds the exact commit, application/worker/
  migrator image digests, evidence hashes, guardrail policy, and authorized
  practice manifest.
- The release creator/finalizer cannot approve their release.
- Human authorities are assigned out of band. There is no authority-grant API.
- Every enabling mutation takes advisory lock `(73119, 20260719)`, then the
  global row, then practice rows. Never introduce a different lock order.
- Safety actions are monotonic: an exact-identity revoke remains valid across a
  concurrently committed advance. Enabling actions remain strict CAS actions.
- A practice is indivisible. The workbench reports target and actual physician
  counts rather than claiming a false exact percentage.
- No PHI, document content, evidence quote, credential, patient identifier, or
  free text belongs in a guardrail snapshot.

## Preconditions

Record PASS, FAIL, or HUMAN PENDING in the release checklist. Do not proceed
while any item is FAIL or HUMAN PENDING.

1. The exact release SHA has an independent detached-workspace ACCEPT review.
2. Application, worker, and migrator images are immutable, scanned, and their
   `sha256:` digests are recorded.
3. A disposable restore of the production backup has succeeded and its evidence
   hash is recorded.
4. Returned desktop Microsoft Word evidence has passed.
5. Clinical Safety has signed the exact guardrail policy and quality thresholds.
6. Privacy/Legal and Operations have signed their exact evidence packages.
7. The production schema migration has succeeded while the global gate remains
   disabled.
8. `TEMPLATE_TWIN_KILL_SWITCH=true` remains set until the accepted candidate is
   ready for Canary.

## Runtime identity

Populate these non-secret values from the accepted release manifest. Do not use
tags, shortened SHAs, staging identities, or mutable registry references.

```dotenv
TEMPLATE_TWIN_RELEASE_COMMIT_SHA=<40-lowercase-hex-exact-head>
TEMPLATE_TWIN_APP_IMAGE_DIGEST=sha256:<64-lowercase-hex>
TEMPLATE_TWIN_WORKER_IMAGE_DIGEST=sha256:<64-lowercase-hex>
TEMPLATE_TWIN_MIGRATOR_IMAGE_DIGEST=sha256:<64-lowercase-hex>
TEMPLATE_TWIN_RUNTIME_MODE=standard
TEMPLATE_TWIN_KILL_SWITCH=true
```

The release service compares all four identities before every activate/pass
operation. Missing or mismatched values fail closed. Switch the process kill
switch to `false` only inside the approved Canary window; a database gate still
remains required.

## Database privileges

The migration creates the capability issuer as `SECURITY DEFINER` and revokes
public execution. A database administrator must grant only the production app
runtime role permission to execute that exact signature. Substitute the actual
role using the approved secret-free infrastructure inventory; do not paste
credentials into evidence.

```sql
GRANT EXECUTE ON FUNCTION template_twin_issue_release_capability(
  UUID, CHAR(64), UUID, BIGINT, BIGINT
) TO <production_app_runtime_role>;
```

The app runtime role must not receive direct INSERT/UPDATE/DELETE/TRUNCATE on
`template_twin_release_capabilities`. Capability receipts are immutable and
transaction/backend-bound. The migration owner retains emergency database
administration authority under the production change-control process.

## Human authority assignment

Use a reviewed database change, not the web application. Confirm the user is a
named human, holds current `Product.SUPER_ADMIN`, uses MFA, is not the release
creator/finalizer, and is authorized for exactly one of:

- `DESKTOP_WORD`
- `CLINICAL_SAFETY`
- `PRIVACY_LEGAL`
- `OPERATIONS`

Under the global release-control advisory lock, insert a UUID assignment with a
non-secret change-ticket reference in `sourceRef`. The database permits one
active assignment per user/discipline and preserves assignment history.

To revoke authority, first revoke/reject any APPROVED, ROLLING_OUT, or
STABLE_100 release whose latest decision uses that assignment. The database
rejects authority revocation while such a release is live. Then set
`revokedAt=CURRENT_TIMESTAMP` in a reviewed change. A revoked assignment cannot
be restored or deleted.

## Create and freeze

1. Open **Template Twin control plane** on `admin.quillmd.com` using a fresh,
   MFA-verified platform-admin session.
2. Paste the signed, PHI-free release manifest. It contains only `evidence`,
   `guardrailPolicy`, `authorizedPracticeIds`, and `canaryPracticeIds`.
3. Review every exact SHA/digest and the displayed practice/canary counts.
4. Type `CREATE EXACT RELEASE`. Creation records a DRAFT and cannot enable a
   rollout gate.
5. Re-open/refresh exact database state, review the server-computed release and
   manifest hashes, then type the displayed `FREEZE <identity-prefix>` phrase.
6. Do not edit evidence in place. A rejected/incorrect identity requires a new
   candidate after the current candidate is made terminal.

## Human decisions

Each discipline's named authority signs in separately, selects their discipline,
enters the evidence SHA-256, reviews the full evidence outside the workbench,
and types the exact displayed APPROVE/REJECT/REVOKE phrase. Decisions are
append-only and session/authority-bound. The release becomes APPROVED only when
all four latest decisions are current APPROVE decisions for the same identity.

After rollout begins, new APPROVE decisions are forbidden. A REJECT or REVOKE
decision atomically disables the global gate, disables exposed practices, makes
the release terminal, and retains the decision/outbox evidence.

## Checkpoint operation

For each of Canary, 10%, 25%, 50%, and 100%:

1. Confirm the rollback fence is OPEN and no rollback operation is active.
2. Confirm runtime SHA/image identity and the process kill switch.
3. Inspect target versus assigned/current physician count and the exact practice
   cohort. Never split a practice to manufacture an exact percentage.
4. Type the displayed `ACTIVATE <STAGE> <identity-prefix>` phrase. The database
   global gate changes before newly in-scope practice gates.
5. Observe the full signed bake interval. Record one PHI-free aggregate metric
   snapshot using the versioned exact key set.
6. Missing, stale, under-sampled, unknown-key, nonnumeric, out-of-bounds, or
   breached metrics block PASS. A critical breach atomically revokes and
   disables without waiting for a browser action.
7. Confirm audit-outbox delivery, object storage, queue, provider, latency,
   error, upload/render/signing, and clinical-quality metrics in their source
   systems.
8. Type the displayed `PASS <STAGE> <identity-prefix>` phrase. The next stage
   remains a separate deliberate activation.
9. At 100%, verify that every practice in the frozen authorized manifest is
   enabled and the current entitled-physician census is recorded. `STABLE_100`
   is still revocable and is not permission to remove monitoring.

## Immediate revoke

Use the workbench's global release revoke for any guardrail failure, ambiguous
provider outcome, audit/storage/queue failure, evidence invalidation, or human
approval withdrawal. Enter an uppercase reason code and type the exact
`REVOKE <identity-prefix>` phrase. The safety request is monotonic and must end
with:

- global database gate disabled;
- every release-manifest practice disabled;
- active checkpoint REVOKED, when present;
- release REVOKED;
- durable release and rollout audit events.

Then follow `template-twin-audited-rollback-control.md` and
`template-twin-rollback-compat-v2.md`. Keep the process kill switch active.
Never delete release, decision, metric, capability, checkpoint, or outbox
evidence.

## Verification

On a fresh disposable PostgreSQL database, apply all migrations and run:

```bash
TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL='<disposable-test-url>' \
npm run release-control:pg-test -w @meddoc/db
```

The database-name guard rejects production-like targets. The proof covers
direct/forged/replayed enable capability rejection, immutable evidence,
ordered 100% advancement, post-100% revoke, critical automatic revoke, and
two-session advance/advance, global-kill/advance, approval-revoke/advance,
operational-revoke/advance, and critical-guardrail/pass races.
