# Production operator tooling recovery, 2026-09-27

Prepared, not run on AWS or installed. No infrastructure, provider call, email,
production database mutation or service change occurred in this work.

## Implemented

`ops/database_roles.py --profile production inspect|apply|verify` dispatches to
an independent production transport; private container behavior remains selected
by default. The production profile still has null endpoint/CA pins and refuses
before any cloud call until they are reviewed and committed.

The production transport requires root, the ruled-mutation runner's declaration
provenance, a matching installed bootstrap receipt, an unexpired JSON declaration
naming the exact operation/action/release/profile, and the actual RDS descriptor.
It checks instance/resource/ARN/endpoint/database identity, PostgreSQL major 16,
private encrypted storage with the declared KMS key and deletion protection.
Direct connections use verify-full TLS with the checked profile CA hash. RDS's
maintenance role is checked through `rds_superuser` membership; no PostgreSQL
superuser assumption remains. AWS documents that distinction in
[the RDS role guide](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Appendix.PostgreSQL.CommonDBATasks.Roles.rds_superuser.html).

Application roles have no privileged flags. The owner cannot log in; the
migrator must explicitly SET ROLE; runtime and backup cannot become the owner.
Verification requires actual table/sequence/schema access and future default
grants as well as absence of dangerous grants. Defaults include PostgreSQL's
implicit global ACLs: a schema-only REVOKE cannot remove global PUBLIC EXECUTE,
so this dedicated owner's function default revocation is global. See
[PostgreSQL default privilege rules](https://www.postgresql.org/docs/16/sql-alterdefaultprivileges.html).

`verify` performs **read-only** catalog/authentication checks on the declared
production target. It does not run mutation proofs there. The old proposed
mutation-verifier behavior is replaced by this safer operational distinction;
permission mutation proofs belong on a separate restored drill. Local proof is
not an AWS/RDS acceptance result.

`manage.py bootstrap_first_admin inspect|create|elevate` uses the same target and
release guard and also checks the actual Django connection, TLS, runtime role,
invite policy, zero welcome credit and production state root. Creation requires
an empty application data boundary, creates exactly the declared UUID/mailbox as
nonstaff and unverified, and sends no email. It creates no wallet, clinic,
patient, template or MFA secret. The owner uses existing verification-resend and
doctor MFA pages. Elevation requires the exact sole bootstrap user, its creation
audit evidence, verified mailbox, usable password and confirmed authenticator;
it grants staff, never superuser, and invalidates pre-elevation sessions.
Repeated creation/elevation refuses; `inspect` reconciles prior outcomes without
resetting credentials or access. This prevents the previous bootstrap deadlock:
staff users cannot sign in before MFA exists.

## Concrete operator inputs and sequence

All of these are future authorized production acts. Do not execute on the VPS.
Keep maintenance until every release gate is satisfied.

1. Activate the reviewed production profile only after authorized AWS/BAA setup.
   Complete host bootstrap and retain its root-only receipt. Obtain the live RDS
   descriptor through the approved operator identity.
2. Commit a JSON declaration through the existing ruled-mutation process. Fields:
   `format: 1`, `operation: database_roles` or `first_admin`, `actions` (only the
   phase(s) authorized), `release_sha`, `profile_sha256`, UTC `expires_at`,
   `database_arn`, `database_resource_id`, `kms_key_arn`. The installed receipt and
   profile must match. First-admin declarations also contain
   `first_admin: {id: <owner-approved UUID>, email: <owner-approved lowercase mailbox>}`.
   No passwords, provider keys or raw verification tokens belong in the declaration.
3. Place RDS credentials as root 0600
   `/etc/quillmd-production/operator/rds-master.json` with only `username` and
   `password`. The descriptor's MasterUsername must match. Invoke the role tool
   under `scripts/run-ruled-mutation.sh --declaration <committed-json> -- ...`.
   `inspect` precedes `apply`. Generated `role-bootstrap.json` contains the three
   login secrets and binds the database resource/profile; preserve it through any
   interrupted attempt. `database-roles.json` contains the migrator/backup subset
   compatible with `with_db_role.py --profile production`. Transfer only runtime
   credentials to the application secret through the approved operator process.
4. Migrate using the production migrator wrapper, then run read-only `verify`.
   Password authentication for all three login roles is checked too. If an apply
   exits after its SQL commit (for example a credential verification or output-file
   failure), reconcile with `inspect`/`verify` and preserved credentials. Do not
   generate a second credential set or infer rollback from a nonzero exit.
5. For first-admin creation, root writes `operator/first-admin-password.json`
   mode 0600 containing only `password` (the normal password validators apply).
   The command runs in the managed application environment, with the same reviewed
   profile values the doctor launcher forces: `QUILLMD_ENV_MANAGED=1`, production
   `QUILLMD_STATE_DIR`, `QUILLMD_DEPLOYMENT_PROFILE=production`, invite registration,
   MFA required, zero welcome credit, and profile `PGSSLMODE=verify-full` /
   `PGSSLROOTCERT`. A transient operator unit may load the existing root-owned
   application EnvironmentFile; never source an untrusted file in a shell or print
   its contents. The operation still passes through the committed mutation gate.
6. `create`; owner requests normal verification email and verifies the mailbox,
   signs in on the doctor origin, enrolls MFA; declared `elevate`; owner signs in
   again on the admin origin with MFA. No email was sent by this engineering
   session. Retain account UUID/audit evidence and seal/delete temporary credential
   files through the approved retention process, after outcomes are reconciled.

## Finite evidence

- Eight offline target/declaration/TLS/refusal tests passed (AWS/connection mocks).
- Eight isolated Django first-admin tests passed, including verification and MFA
  enrollment page access. No real email or provider was called.
- Actual local PostgreSQL 16 with a NOSUPERUSER/CREATEROLE maintenance role:
  role apply and idempotent repeat passed; eight runtime/backup/migrator permission
  checks passed; eleven missing/excess table/sequence/schema/default-grant controls
  were refused; the restored baseline passed. Every probe used fixture port 55704,
  a unique synthetic database/roles, and removed only those objects in `finally`.
- Independent root refutation removed backup SELECT and initially demonstrated a
  false-green verifier. That failure was repaired and the exact independent probe
  now refuses `required_table_privilege`. Root's first-admin source pass found no
  further demonstrated defect. This bounded finding does not establish a completed
  production security review.
- The first admin test run's missing static manifest was a test setup failure;
  the corrected fixture uses the repository's ordinary static test backend. The
  first role proof also caught an invalid self-GRANT ADMIN option; repaired before
  the successful role proof. Failed logs remain in runtime evidence.

Selected evidence is committed in `host-readiness-evidence-20260927/`; full logs
and synthetic scripts remain in `rebuild/.runtime/host-readiness-20260927/`.
Dependency hash locking is separately recorded in `dependency-lock-20260927/`.

## Still required on the actual target

Reviewed account/BAA/funding authority; activated actual endpoint/CA/profile and
installed release; declared RDS role application/migrations; actual RDS restore
permission and recovery drill; owner mailbox/MFA ceremony; live billing/alerts and
all other V1 release gates. The code is prepared, not a deployment or acceptance
claim. RDS-specific behavior must still be verified on the covered AWS target.
