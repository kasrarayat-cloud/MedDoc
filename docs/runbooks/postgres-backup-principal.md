# PostgreSQL backup principal

Status: **technical contract PASS in isolated PostgreSQL 16; production
provisioning and restore evidence OPS PENDING**.

This runbook replaces the long-lived database-owner credential in the
`postgres-backup` service. It does not authorize a production change by
itself. Never run the data-bearing procedure until the release checklist has
the read-only census, an exact rollback artifact, a verified backup/restore
identifier, an approved change window, and named database ownership.

## Exact contract

The cluster role graph is deliberately finite:

```text
meddoc_backup LOGIN INHERIT BYPASSRLS CONNECTION LIMIT 1
  └─[ADMIN FALSE, INHERIT TRUE, SET FALSE; superuser grantor]
    quillmd_backup NOLOGIN NOINHERIT NOBYPASSRLS
      └─[ADMIN FALSE, INHERIT TRUE, SET FALSE; superuser grantor]
        pg_read_all_data
```

`meddoc_backup` has no direct object ACL, ownership, role/database setting, or
membership authority. `quillmd_backup` has non-grantable `CONNECT` on the
application database plus one reviewed function ACL after v9: `EXECUTE` on
the frozen `public.quillmd_boundary_password_is_null(text)` helper. The
provisioner and pre-backup hook bind that exception to the helper's exact
owner, definition, security configuration, ACL, database, and single
`pg_shdepend` tuple; a changed helper or any second shared dependency fails
closed. The successful v9 row in Prisma's durable migration ledger is the
stage boundary: before it, provisioning requires the helper and dependency to
be absent; after it, exactly one successful marker, the exact helper, and one
dependency are mandatory. Failed, rolled-back, malformed, or duplicate marker
state fails. The archive hook is post-migration only and always requires the
successful v9 state. Neither backup role may be a grantor. The login cannot
`SET ROLE`.

The provisioner also enforces the cluster database boundary:

- revoke `CONNECT`, `CREATE`, and `TEMPORARY` from `PUBLIC` and the six
  reviewed boundaries on every database, including currently
  `datallowconn=false` templates, so a later eligibility change cannot expose
  a latent grant;
- grant non-grantable `CONNECT` on the current application database only to
  `quillmd_runtime`, `quillmd_release_control`,
  `quillmd_release_security`, `quillmd_audit_dispatcher`,
  `quillmd_auth_email_dispatcher`, and `quillmd_backup`;
- require the backup login to have effective `CONNECT` on that database only
  and no database `CREATE` or `TEMPORARY` anywhere.

The database change and password rotation are one transaction protected by
the existing release advisory lock. A failed precondition, SQL statement, or
postcondition rolls back the password, memberships, database ACLs, and system
function ACLs together.

### Large objects

MedDoc has no released PostgreSQL large-object workflow. Admission therefore
requires zero rows in `pg_largeobject_metadata`. PostgreSQL 16 grants several
LO mutators to `PUBLIC` by default, so provisioning transactionally revokes
`PUBLIC EXECUTE` on these exact signatures:

- `lo_creat(integer)`
- `lo_create(oid)`
- `lo_from_bytea(oid,bytea)`
- `lo_open(oid,integer)`
- `lo_put(oid,bigint,bytea)`
- `lo_truncate(integer,integer)`
- `lo_truncate64(integer,bigint)`
- `lo_unlink(oid)`
- `lowrite(integer,bytea)`

The gate also inventories the stock owner-only `lo_import(text)`,
`lo_import(text,oid)`, and `lo_export(oid,text)` signatures and proves the
backup login cannot execute any of the twelve functions. A future LO use case
requires a separate reviewed storage, backup, restore, and authorization
design; do not enable `lo_compat_privileges`.

## Immutable service contract

The only accepted runtime exception is the literal `postgres-backup` service:

- image:
  `prodrigestivill/postgres-backup-local@sha256:a0103fbce0c48ccc7693ddbb2a2bfa733048db845354f635efef9e4566de185d`;
- disabled by default behind the exact `backup-ops-approved` Compose profile;
- `restart: unless-stopped`, with the upstream entrypoint unchanged;
- `user: "999:999"` and `cap_drop: [ALL]`;
- `POSTGRES_HOST=postgres`, `POSTGRES_DB=meddoc`,
  `POSTGRES_USER=meddoc_backup`, and
  `POSTGRES_PASSWORD_FILE=/run/secrets/postgres_backup_password`;
- `PGAPPNAME=meddoc-postgres-backup`;
- Docker secret `postgres_backup_password`, sourced from the operator-owned
  `DB_BACKUP_PASSWORD_FILE` path;
- only the internal `backup_database` network, shared with PostgreSQL and with
  no egress-capable service;
- `depends_on: postgres: condition: service_healthy`, with no command or
  entrypoint override;
- only the named `pgbackups:/backups` archive volume and the read-only
  `./infra/postgres-backup/hooks:/hooks:ro` mount; no repository, PostgreSQL
  data, configuration, log, or offsite credential mount;
- exact `POSTGRES_EXTRA_OPTS` value
  `--format=custom --compress=6 --no-owner --create --large-objects --lock-wait-timeout=60s`;
- exact `BACKUP_SUFFIX=.dump`, matching the custom archive consumed by
  `pg_restore`;
- exact daily schedule, retention, resource, and fixed local healthcheck
  values frozen by the database-principal runtime census.

ACLs must remain in the archive: `--no-acl` is forbidden. The service must not
receive `DB_PASSWORD`, an owner URL, `DATABASE_URL`, `POSTGRES_USER_FILE`, or
any other identity indirection. The pre-backup hook is the supported upstream
`/hooks` mechanism; do not represent the deprecated post-backup command as a
release gate.

The backup service intentionally has no offsite-storage environment or egress
network. Offsite replication, point-in-time recovery, retention monitoring,
and restore ownership remain separate Operations gates; a local custom archive
does not prove any of them.

The repository's current `pgbackups` named volume has no production
encryption-at-rest proof on the observed host, and the Docker database network
has no PostgreSQL TLS/peer-authentication proof. The profile must remain
disabled for PHI until Operations supplies an approved encrypted archive
target and key/restore evidence, verifies encrypted in-transit backup
connections, proves external unhealthy/freshness alert routing and partial-file
handling, and names the responders. The isolated test proves format and ACL
fidelity only; it is not production storage or transport authorization.
Activation therefore requires a later additive, exact-head-reviewed update to
the Compose storage/TLS contract and runtime census; do not bypass the census
with an ad hoc production override.

CI validates the unresolved Compose source contract without resolving any
credential-bearing environment values:

```sh
docker compose --profile "*" -f docker-compose.yml \
  config --no-interpolate --no-env-resolution --format json |
  node scripts/database-principal-runtime-census.mjs --static-unresolved
```

That static result is not deployment evidence. During an authorized change,
Operations must configure `QUILLMD_APPROVED_DB_BACKUP_PASSWORD_FILE` to the
same approved absolute path supplied through `DB_BACKUP_PASSWORD_FILE`, then
pipe the fully resolved model directly into the default census mode:

```sh
docker compose --profile "*" -f docker-compose.yml config --format json |
  node scripts/database-principal-runtime-census.mjs
```

Never write or display the resolved Compose model. The deployment gate accepts
only the fixed `mode=resolved` PASS line; missing, null, indirect, or unresolved
database identities and a different secret source fail closed.

Archives created before this change with the upstream default `.sql.gz`
suffix remain immutable under their existing retention policy. They are a
different backup generation and cannot be cited as custom-format/`pg_restore`
evidence. Do not rename or destroy them during this rollout.

The secret file must be an approved generated base64url secret in a regular
readable file containing 43–128 characters (`A–Z`, `a–z`, `0–9`, `_`, or `-`)
and no NUL, CR, or LF. A 43-character base64url value can encode 32 random
bytes; human-chosen passwords are not accepted. Both provisioning and every
pre-backup run validate the raw file before command substitution can alter it.
Password rotation uses the client-side `psql` password command so plaintext
does not enter a SQL statement, server activity, or statement log. Do not
print the file, put its value in a command argument, commit it, or retain it in
evidence.

## Pre-backup gate

`infra/postgres-backup/hooks/10-principal-preflight` runs before archive
creation and emits exactly one fixed line. `PASS` requires all of the
following:

- exact session/login identity, role attributes, two-edge graph, grantors,
  current-only database ACLs, primary-server state, and no direct authority;
- the canonical Prisma migration-ledger table and sole primary-key index, plus
  exactly one successful v9 row whose checksum is
  `8d2c4fe1075490085b34397cdecde3d8c6e50b3e21c778ac9d491da071faf404`;
- effective read access to every supported user schema, table, view,
  materialized view, partitioned table, and sequence;
- no relation writes, sequence mutation, schema/database creation, temporary
  tables, executable user-schema `SECURITY DEFINER` routine other than the
  exact v9 password-null helper, or `SET ROLE`;
- zero large objects and no executable LO entrypoint;
- no foreign table, logical subscription, invalid index, or not-ready index.

Any mismatch prints only `postgres-backup-preflight: FAIL` and stops the dump.
Foreign tables and PostgreSQL LOs are explicitly unsupported, not partially
backed up.

The hook and principal provisioner share the exact release advisory-lock key
with v9. They use a nonblocking acquisition: an in-progress migration,
provisioning transaction, or another pre-backup proof produces the same fixed
`FAIL` promptly and makes no principal or archive change. Operations must
confirm the competing reviewed transaction completed, then rerun the gate and
obtain a fresh `PASS`; never bypass or replace the lock on a backup schedule.

## Fresh installation

1. Create the five existing service boundaries and `quillmd_backup` with the
   reviewed fresh-init role bootstrap.
2. Mount `infra/postgres/provision-postgres-backup-principal.sh` read-only in
   the PostgreSQL container and mount the backup password secret only at its
   configured secret path.
3. Read and approve the local cluster's `pg_control_system()` system
   identifier. Run the provisioner locally as the PostgreSQL owner/superuser
   with `POSTGRES_USER`, `POSTGRES_DB`, `DB_BACKUP_PASSWORD_FILE`, and
   `DB_EXPECTED_SYSTEM_IDENTIFIER` set to paths, names, and the approved
   identifier—never credential values. The script pins the local PostgreSQL
   socket and refuses ambient libpq routing/session variables.
4. Apply all migrations. The schema migration set must revoke `CREATE` on user
   schemas from `PUBLIC` and establish the reviewed application ACLs.
5. Start `postgres-backup` only after the runtime principal census and the
   fixed-output pre-backup hook both pass.
6. Create an archive, hash it, and complete a no-egress disposable restore
   before declaring the installation restorable.

## Existing data-bearing cluster

This operation changes cluster-wide database ACLs and requires separate
production authority.

1. Read only: record the exact PostgreSQL version, current database/owner,
   every database ACL (including templates), all six boundary attributes and
   ACLs, the complete backup-related membership graph (including grantors), LO
   function ACLs, LO count, foreign tables, subscriptions, invalid indexes,
   and current trusted-login sessions. Hash the redacted manifest.
2. Verify the immediately preceding production backup in a disposable,
   no-egress restore. Record its immutable restore identifier and result.
3. Generate and independently review an exact transactional rollback SQL
   artifact from the pre-change ACL census. Store it restricted and outside
   the repository; evidence contains only its SHA-256.
4. Stop the backup service and drain the application, worker, migrator,
   release-control, audit-dispatcher, auth-email-dispatcher, and backup
   connections. The provisioner fails if a trusted service session remains.
5. Run the provisioner from the immutable release checkout through the local
   PostgreSQL socket, supplying the approved pre-change system identifier. The
   only success output is
   `postgres-backup-principal: PASS`.
6. Rerun the exact role/ACL census and compare it with the approved target.
7. Start only `postgres-backup`; require the fixed pre-backup `PASS`, a
   successful archive, an archive SHA-256, and normal database latency/locks.
8. Restore that archive in a new no-egress PostgreSQL 16 cluster. Bootstrap
   referenced roles before `pg_restore --create --no-owner`, then rerun the
   privileged provisioner: role memberships and the `pg_catalog` LO ACL
   hardening are cluster/bootstrap state and are not assumed to be carried by
   `pg_dump`.
9. Compare normalized database, schema, relation, routine, and default ACLs;
   row counts/hashes; RLS-visible contents; and the final exact principal
   census. Only then may the service change be accepted.

Use a migration/change window clear of DDL. `pg_dump` takes `ACCESS SHARE`
locks; `--lock-wait-timeout=60s` fails rather than waiting indefinitely. A
failed or partial archive must never be promoted as the latest verified
backup.

## Rollback

Before `COMMIT`, failure is automatically atomic; the actual-PG test injects a
failure after all postconditions and proves the original password verifier,
membership graph, database ACLs, and LO function ACLs return byte-for-byte.

After a committed production change:

1. Stop `postgres-backup` and all six trusted service principals; confirm zero
   sessions.
2. Keep the new backup login disabled from use. Do not broadly regrant
   `PUBLIC` privileges from memory.
3. Apply the independently reviewed, exact pre-change ACL artifact in one
   owner transaction and compare its canonical hash before commit.
4. Restore the prior immutable service definition and credential source only
   if its backup archive was already restored successfully and its credential
   remains valid. Otherwise keep backups stopped and escalate; an unverified
   owner-backed backup is not a safe rollback.
5. Leave `meddoc_backup`/`quillmd_backup` in place but unused unless an
   independently reviewed dependency census proves they can be removed. Role
   deletion is not required for functional rollback and must not be improvised.
6. Run a new archive/restore rehearsal and record monitoring results.

If the exact pre-change artifact or verified prior backup is unavailable,
safe rollback is **not proven** and the production operation must not begin.

## Verification evidence

The isolated contract test is:

```sh
node_modules/.bin/tsx packages/db/scripts/postgres-backup-principal-pg-test.ts
```

It uses immutable PostgreSQL 16 image
`pgvector/pgvector:pg16@sha256:7d400e340efb42f4d8c9c12c6427adb253f726881a9985d2a471bf0eed824dff`
with `--network none`, plus the exact pinned backup image as uid/gid 999 with
all capabilities dropped in the same no-egress network namespace. It proves
exact graph/ACLs, transitive table/sequence and
forced-RLS reads, rejected writes/DDL/temporary tables/`SET ROLE`/LO calls,
weak/malformed-secret rejection, local-socket and approved-system-identifier
binding, fixed hook output, `log_statement=all` plaintext/verifier exclusion,
unsupported foreign-table and LO admission failures, injected transactional
rollback including password rotation, `pg_dump` with retained ACLs, normalized
ACL fidelity after `pg_restore`, and required post-restore privileged
reprovisioning.

Production backup identifiers, archive hashes, cluster census, restore logs,
monitoring, and operator approval remain **OPS/HUMAN PENDING** until produced
in the authorized window. Isolated test evidence is not production evidence.
