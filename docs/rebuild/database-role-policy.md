# Fresh database role policy and coordinated activation

## Observed live baseline

Read-only checks on 2026-09-17 found `quillmd_fresh` serving the app as a
superuser with CREATEDB, CREATEROLE, REPLICATION and BYPASSRLS. It owns the fresh
database, and PUBLIC has CONNECT. This is an unresolved live least-privilege gap
until the coordinated activation below is recorded; isolated tests are not a
claim that live privileges have changed.

The dedicated container publishes PostgreSQL only at `127.0.0.1:55438`.
`listen_addresses=*` applies inside that container. The host's published route
uses SCRAM-SHA-256: a deliberately wrong password was rejected. HBA retains
trust for Unix sockets and container-local 127.0.0.1/::1 maintenance. TLS is off
on the local transport. No broad VPS HBA/network changes were made.

## Prepared and tested split

| Role | Purpose and permissions |
| --- | --- |
| `quillmd_owner` | NOLOGIN; owns only the fresh database/schema/objects; no superuser or role/database creation flags |
| `quillmd_runtime` | Login; CONNECT/USAGE; SELECT/INSERT/UPDATE/DELETE on app tables; sequence USAGE/SELECT; no DDL/TRUNCATE/trigger control/owner membership |
| `quillmd_migrator` | Login; must explicitly SET ROLE to the owner; no inherited owner power by default |
| `quillmd_backup` | Login; CONNECT/USAGE and SELECT only, including sequences needed by pg_dump |
| Existing `quillmd_fresh` | Preserved maintenance/bootstrap connection for controlled recovery; never used by the hardened app |

PUBLIC database privileges and schema CREATE/USAGE are revoked. Existing table,
sequence and QuillMD trigger-function ownership moves to the nonlogin owner.
Default privileges preserve runtime/backup access to future migration objects
created **as owner**. New roles are marked with a policy ownership comment;
unmarked collisions refuse. No unrelated database role or schema is modified.

The policy was applied twice to the isolated restored database, demonstrating
idempotence without rotating its generated passwords. Seventeen live SQL
assertions passed there: all managed privileged flags absent, NOLOGIN owner,
PUBLIC CONNECT revoked, wrong password refused, permitted DML rolled back,
runtime CREATE/TRUNCATE/trigger-disable/owner escalation refused, immutable
ledger/audit/usage/mapping/provider receipts refused, read-only backup plus
pg_dump succeeded, and explicit migrator/default-table-and-sequence grants
worked. Complete application table hashes are compared after these probes.

## Interfaces and order

The lead owns deployment and uses the committed
`20260917-quillmd-private-beta-update.md` declaration. All commands below take
paths or metadata, never passwords in arguments. Do not harden live before the
fresh encrypted backup and isolated restore evidence are accepted.

1. Deploy reviewed/cited source while gracefully stopping the three private
   units. Apply application migrations and verify preserved new data/files.
2. Before restarting, install the reviewed unit policy:

   ```bash
   .venv/bin/python ops/install_unit_policy.py --expected-commit FULL_MERGE_SHA --execute
   ```

   This writes only the three tracked `quillmd-fresh-*` units, creates their
   private secret directories, calls daemon-reload and checks exact bytes. It
   requires all three services stopped and does not start them.
3. As a coordinated act, apply the role policy with the actual current full
   Docker container ID:

   ```bash
   .venv/bin/python ops/database_roles.py apply \
     --container quillmd-fresh-postgres --database quillmd_fresh \
     --admin-user quillmd_fresh --expected-container-id FULL_CONTAINER_ID \
     --credentials .runtime/db-role-secrets/fresh-db-roles.json
   ```

4. Switch only `QUILLMD_DB_USER` and `QUILLMD_DB_PASSWORD` in the fresh app's
   private `.env`:

   ```bash
   .venv/bin/python ops/activate_runtime_role.py \
     --credentials .runtime/db-role-secrets/fresh-db-roles.json --execute
   ```

   The helper proves the new login is constrained first, requires all services
   stopped and the loaded secret-hiding policy, preserves every other setting
   and verifies `.runtime/postgres.env` unchanged. It does not restart services.
5. Restart through the lead's existing scoped host-systemd mechanism. Verify
   doctor/admin health, new runtime DB role and public maintenance responses.
   If roles are applied separately after deployment, a second graceful stop /
   start is intentional.

Future migrations use their separate wrapper, which supplies PGOPTIONS to SET
ROLE owner without changing service environment:

```bash
.venv/bin/python ops/with_db_role.py \
  --credentials .runtime/db-role-secrets/fresh-db-roles.json \
  --source /opt/meddoc-pro/rebuild --role migrator -- migrate --noinput
```

The wrapper permits only `migrate`, `showmigrations` and `check`. It cannot start
a worker or call a provider. The backup command accepts the same credential file
but selects the backup login.

## Secret isolation and recovery boundary

All three unit sources hide the Docker socket, root `.env`, retained service
credentials, worktrees, bootstrap credential file, synthetic account passwords,
role credentials, backup keys, backups and restored copies with InaccessiblePaths.
They still read the fresh runtime `.env` that contains only the login they need.
The key/role artifacts are not mounted into a restore container.

Keep the bootstrap role and `.runtime/postgres.env` until a separately reviewed
maintenance/recovery policy replaces them. The apply tool verifies that its
maintenance connection still works after every change. If activation fails,
leave services stopped, use that preserved maintenance connection to inspect
grants/ownership, and restore the prior DB login through a declared repair; do
not erase the database or regenerate credentials blindly.

The three services still share OS user `claude` with development tooling.
Hiding known paths/socket closes specific access paths; it is not an exhaustive
host identity boundary. A dedicated service OS identity and verified secret
distribution/rotation/recovery remain patient-data readiness requirements.
