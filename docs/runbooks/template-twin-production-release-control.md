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
TEMPLATE_TWIN_ADMIN_APP_RUNTIME_ATTESTATION=<distinct-signed-APP-envelope>
```

The deployment authority must also issue a short-lived, signed runtime envelope
for every APP and WORKER instance. Each envelope binds the exact release
identity, component, instance ID, commit, image digest, issuance/expiry time,
and a unique nonce. Put only that instance's envelope in
`TEMPLATE_TWIN_RUNTIME_ATTESTATION`; never reuse an APP envelope for a worker or
share a nonce between replicas. Register the public verification key through a
reviewed migration-owner change. Keys are append-only, may only be revoked, and
must not be deleted or rewritten.

The deployment environment supplies the isolated practice-admin APP envelope
through `TEMPLATE_TWIN_ADMIN_APP_RUNTIME_ATTESTATION`; Compose maps it to that
process's `TEMPLATE_TWIN_RUNTIME_ATTESTATION`. It must be distinct from every
physician APP envelope even when both processes use the same immutable image.

The release service verifies the signatures and compares all four identities
before every activate/pass operation. Missing, expired, revoked, replayed, or
mismatched attestations fail closed. Switch the process kill switch to `false`
only inside the approved Canary window; a database gate still remains required.

## Process and ingress isolation

- `transcribe-md` and the worker connect only as `meddoc_runtime`; explicitly
  blank the control, audit-dispatcher, and auth-email-dispatcher credentials in
  those containers.
- `template-twin-admin-app` is a separately attested, unexposed same-image
  process that also connects as `meddoc_runtime`. It receives no release-control
  or object-storage credential. It receives only the provider credential needed
  for the bounded static-image privacy scan. Caddy routes its exact auth/MFA,
  reusable-image page/API and `/_next/static/*`/public-asset paths to this
  process; the process repeats that deny-by-default allowlist before auth.
  Compose probes the exact health route directly inside the container. Caddy
  does not expose that route on the public admin host; the process allowlist
  admits it only for the internal container probe.
  Practice access requires current ADMIN/SUPER_ADMIN + TRANSCRIBE_MD authority,
  and every page or inventory disclosure requires a durable fail-closed access
  audit after rollout, active-practice, and current-actor fences.
- `template-twin-admin-control` is the only HTTP process receiving the
  `meddoc_release_control` DSN. Caddy routes only the release workbench page and
  its exact release/metric endpoints to it. It does not load the application
  `.env`, ordinary runtime DSN, provider keys, object-storage credentials, or
  any APP/WORKER attestation envelope. It remains loopback-only on the host and
  requires a signed cookie plus the narrow database-backed fresh SUPER_ADMIN +
  MFA verifier; that verifier cannot enumerate or mutate session rows.
- `template-twin-audit-dispatcher` connects only as
  `meddoc_audit_dispatcher`, receives no provider credential or control DSN,
  and is the only process allowed to claim and deliver release outbox rows.
- `auth-email-dispatcher` connects only as `meddoc_auth_email_dispatcher`,
  imports no wholesale `.env`, and receives only verified mail-provider
  settings plus the exact physician-app URL. Its procedure-only database role
  cannot read ordinary application tables directly. Operate and roll it back
  through `auth-email-dispatcher.md`.
- Every Caddy site imports the shared access-log filter. The default runtime
  logger repeats it because upstream failures can also emit request URIs. Both
  preserve query parameter names but replace credential-like values, including
  `token`, `code`, `state`, `id_token`, `access_token`, `refresh_token`,
  `secret`, `password`, and `otp`, before encoding. Validate this policy against
  the exact release Caddy image with synthetic markers only.
- Broad legacy `/admin`, `/admin/*`, `/api/admin`, and `/api/admin/*` routes are
  retired on `admin.quillmd.com` and return `404` at Caddy. No admin-host route
  is proxied to the physician `transcribe-md` process, and the bare `/` no
  longer rewrites to `/admin`. Exact Template Twin control matchers are ordered
  before the explicit legacy denies; every other non-allowlisted path reaches
  the catch-all `404`.

The public admin-host allowlist is deliberately small:

| Surface                                            | Exact public path boundary                                                                                  | Process                       |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Sign-in/session                                    | `/api/auth/*`; `/login`, `/forgot-password`, `/reset-password`, `/check-email`                              | `template-twin-admin-app`     |
| Required MFA enrollment and recovery-code rotation | `/api/mfa/enroll`, `/api/mfa/verify-enrollment`, `/api/mfa/recovery-codes/rotate`, `/settings/security/mfa` | `template-twin-admin-app`     |
| Practice static assets                             | `/api/note-templates/template-twin/static-assets`, `/settings/note-format/static-assets`                    | `template-twin-admin-app`     |
| Release workbench                                  | `/admin/template-twin-release` and children                                                                 | `template-twin-admin-control` |
| Release API                                        | `/api/admin/template-twin/releases` and children; `/api/admin/template-twin/release-metrics` and children   | `template-twin-admin-control` |
| Build/public assets                                | `/_next/static/*`, favicon, robots, and manifest files                                                      | `template-twin-admin-app`     |

The admin-app and control health endpoints remain internal container probes;
Caddy does not expose either on the public admin host. Before every deployment,
validate the mounted configuration in the resolved image with
`docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile`, then
repeat the edge path and access-log redaction contract tests. A failed config,
an unredacted synthetic marker, a legacy route that does not return `404`, or
any admin-host route targeting `transcribe-md` is a deployment blocker.

## Database privileges

The hardening migration deliberately refuses to run unless these exact
principals already exist with the expected attributes and memberships:

- NOLOGIN/NOINHERIT groups: `quillmd_runtime`,
  `quillmd_release_control`, `quillmd_release_security`, and
  `quillmd_audit_dispatcher`, plus `quillmd_auth_email_dispatcher`;
- LOGIN/INHERIT principals with exactly one membership each:
  `meddoc_runtime` → `quillmd_runtime`, `meddoc_release_control` →
  `quillmd_release_control`, `meddoc_release_security` →
  `quillmd_release_security`, and `meddoc_audit_dispatcher` →
  `quillmd_audit_dispatcher`, plus `meddoc_auth_email_dispatcher` →
  `quillmd_auth_email_dispatcher`.

For a brand-new database, supply four distinct generated credentials to
`infra/postgres/init-template-twin-roles.sh` through the container secret
environment before first initialization. An existing production data volume
does not rerun entrypoint initialization: a database administrator must apply
the same reviewed role-provisioning block before `prisma migrate deploy`, then
verify attributes and exact membership without recording credential values.

After all production-control migrations have committed, provision the fifth,
procedure-only security login with
`infra/postgres/provision-template-twin-release-security.sh`. Supply its unique
credential through `DB_RELEASE_SECURITY_PASSWORD` and the normal protected
`PG*` connection environment; never put either password on a command line or
in evidence. This step intentionally follows migration v2, whose precondition
verifies the original three-login boundary before v3 makes authority revocation
operational. The release-control PostgreSQL proof must pass only after the
fourth login and its exact single membership exist.

The migration itself installs the least-privilege grants. Runtime cannot read
control receipts or mutate immutable evidence. Release control cannot read
attestation keys/session secrets or dispatch audit rows. The dispatcher cannot
mutate rollout state. Capability, action, coupling, and metric receipts are
transaction/backend-bound and immutable. Do not add application grants in an
operations hotfix; any privilege change requires a new reviewed migration.

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

To revoke authority, connect only as `meddoc_release_security` and invoke
`template_twin_revoke_release_authority(...)` in a reviewed, parameterized
change with a unique non-secret change ID and reason code. Never update
`revokedAt` directly. The procedure takes the advisory/global/practice lock
order and, if the assignment supports a live release, atomically revokes that
release, disables global and practice exposure, appends audit-outbox evidence,
and revokes the assignment. A revoked assignment cannot be restored or
deleted.

Runtime or metric attestation keys are also monotonic. A live runtime key
cannot be revoked while its release remains exposed: first use the release
revoke path (or perform disable and key revocation in one reviewed transaction),
verify global and all manifest practices are disabled, then set the key's
`revokedAt`. Never delete, rewrite, or silently replace key material.

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

The exact audited rollback-fence API remains
`/api/admin/template-twin/rollback`. Caddy routes only that path to the
isolated admin-app process; broad legacy `/api/admin/*` remains retired. Every
rollback mutation requires a fresh host-only admin session, complete current
MFA, current `SUPER_ADMIN`, an active practice, same-origin confirmation, and a
second transaction-final session/identity check under the rollback lock.

## Verification

On a fresh disposable PostgreSQL database, apply all migrations and run:

```bash
TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL='<disposable-test-url>' \
npm run release-control:pg-test -w @meddoc/db
```

The database-name guard rejects production-like targets. The proof covers
the exact four-login role boundary, narrow non-enumerable control-session
verification, live-key-revoke/enable coupling, direct/forged/replayed enable
capability rejection, immutable evidence, ordered 100% advancement,
post-100% revoke, critical automatic revoke, and two-session advance/advance,
global-kill/advance, approval-revoke/advance, operational-revoke/advance, and
critical-guardrail/pass races.

Repeat the proof on a separate fresh database at the maximum supported cohort:

```bash
TEMPLATE_TWIN_RELEASE_CONTROL_SCALE_PRACTICES=10000 \
TEMPLATE_TWIN_RELEASE_CONTROL_TEST_DATABASE_URL='<disposable-test-url>' \
npm run release-control:pg-test -w @meddoc/db
```

Before accepting the result, run the audit dispatcher through its actual
database role and call `template_twin_assert_release_audit_delivery()`. Every
delivered release outbox row must pair with exactly one database-generated
`audit_logs.timestamp`; pending or duplicate pairs block rollout.

## Emergency disable and credential boundary rollback

1. Set `TEMPLATE_TWIN_KILL_SWITCH=true` on all six same-artifact runtimes and
   restart them from the last accepted immutable app/worker image pair through
   `template-twin-runtime-swap.sh`: physician app, practice-admin app,
   release-control app, primary worker, audit dispatcher, and authentication
   email dispatcher. Preserve and reuse the generated content-addressed
   rollback overlay for every later Compose operation. Never include the
   one-shot database migrator and never run a downmigration.
2. Use the fresh-session workbench revoke action for the exact release. If the
   control process is unavailable, Operations uses the separately reviewed
   database emergency procedure; never issue a direct enabling update.
3. Verify the global gate and every exposed practice are disabled, the release
   is terminal, and audit outbox delivery is complete.
4. Keep the isolated control and dispatcher credentials active long enough to
   preserve evidence. Rotate them after containment; do not fall back to the
   migration-owner DSN in an application container.
5. Follow the audited rollback-fence runbooks before rolling back application
   images or schemas. No destructive schema rollback is permitted.
