# Postgres recovery runbook

**Cluster:** `meddoc-pro-postgres-1` (pgvector/pgvector:pg16 — PostgreSQL 16.13)
**Bootstrap superuser:** `meddoc` (created via `POSTGRES_USER=meddoc` at initdb time)
**Data dir:** `/var/lib/postgresql/data/pgdata` (Phase 6.1 LUKS-encrypted volume)

This runbook is the operator escape hatch for Postgres-level admin work. It exists because there is no `postgres` role in the cluster — the bootstrap superuser is `meddoc`, and that's the only login-capable role. There is no separate admin / DBA role.

When in doubt: `docker exec -it meddoc-pro-postgres-1 psql -U meddoc -d meddoc` and you're a superuser. The harder cases below cover what to do when even that doesn't work.

---

## When to use this runbook

| Scenario                                                                         | Method                                                                                                                | Downtime?                                             |
| -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- |
| Run a one-off SQL as superuser (CREATE EXTENSION, ALTER ROLE another role, etc.) | §1 docker exec + psql                                                                                                 | none                                                  |
| Inspect or resume a reviewed database release                                    | Read-only `docker compose run --rm db-migrate --phase status`, then `docs/DEPLOYMENT_RUNBOOK.md` §1.4.1 if authorized | keep app tier stopped until every gate passes         |
| Reset `meddoc` password (lost from .env / Bitwarden)                             | §2 docker exec + ALTER ROLE                                                                                           | brief (rotate DB_PASSWORD in .env + restart app tier) |
| `meddoc` somehow loses LOGIN attribute (someone ran `ALTER ROLE meddoc NOLOGIN`) | §3 single-user mode                                                                                                   | yes — postgres restart                                |
| Cluster won't start (corruption, fsync, etc.)                                    | §3 single-user mode + escalate                                                                                        | yes                                                   |
| Audit-log immutability fix (Round 3 PR-C.1 deferred to Phase 7)                  | see §4 background                                                                                                     | —                                                     |

---

## §1 — Standard superuser shell (no downtime)

The pg_hba.conf inside the container has `local all all trust` for unix-socket connections. From the host, `docker exec` lands you on the unix socket as the `postgres` unix user, and trust-auth lets you connect as ANY role without a password.

```bash
# Drop into a psql shell as meddoc (the bootstrap superuser):
docker exec -it meddoc-pro-postgres-1 psql -U meddoc -d meddoc

# Or run a single command:
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "SELECT current_user, current_setting('is_superuser');"
```

Inside the shell, you have **full superuser** for any administrative SQL:

```sql
-- Example: install a new extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Example: rotate another role's password
ALTER ROLE backup_user PASSWORD 'new_password_here';

-- Example: re-grant something stripped accidentally
GRANT ALL ON TABLE transcribe_visits TO meddoc;
```

**Verification this works right now:**

```
$ docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -At -c \
    "SELECT current_user, current_setting('is_superuser');"
meddoc|on
```

**Important caveats:**

1. **Trust auth is local-only.** The `local all all trust` line in pg_hba only applies to unix-socket connections from inside the container. External connections (host:port from outside) require `scram-sha-256` and the password from `.env`'s `DB_PASSWORD`.

2. **Do not run `\password` to set a password** while connected via trust auth — it works, but it puts the new password in the psql history. Use `ALTER ROLE meddoc PASSWORD '...'` directly.

3. **`docker exec` runs as the container's unix user** (uid 999, named `postgres`). That user owns the postgres data dir. It does NOT need to match any DB role name.

4. **HBA authentication is not transport encryption.** The immutable HBA file
   controls which database identities may authenticate and which method they
   use. It does not provide or prove TLS; TLS configuration and peer evidence
   remain a separate infrastructure gate.

### Schema-release boundary

Do not paste migration DDL into this superuser shell and do not run raw Prisma
deploy or resolve commands during recovery. The only routine migration command
is the read-only closed-runner status:

```bash
cd /opt/meddoc-pro
docker compose run --rm db-migrate --phase status
```

If the restored database is an exact accepted ledger prefix, use only the
status-and-approved cumulative phase flow in `docs/DEPLOYMENT_RUNBOOK.md`
§1.4.1, including the intervening lineage and authentication online contracts.
Every cumulative-segment invocation requires a newly verified
`targetFingerprints.<segment>` status entry. The map is phase-, ledger-,
accepted-source-, and target-bound and is empty while PostgreSQL is in
recovery; never derive or reuse an entry.
Unknown checksums, unresolved attempts, catalog/ledger disagreement, or an
ambiguous target are not permission to repair Prisma's ledger. Preserve a new
snapshot and escalate for a reviewed DBA forward-reconciliation decision while
the application tier remains stopped.

---

## §2 — Reset `meddoc` password (lost from custody)

Scenario: `DB_PASSWORD` in `.env` no longer matches what the role actually has, or the value was lost from Bitwarden. The app can't connect.

```bash
# 1. Pick a new password (keep it open in your password manager — you'll save it in .env in a moment)
NEW_PW='<24-chars from openssl rand -base64 18>'

# 2. Reset the password via local trust auth
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c \
  "ALTER ROLE meddoc PASSWORD '$NEW_PW';"

# 3. Update /opt/meddoc-pro/.env DB_PASSWORD line to match
nano /opt/meddoc-pro/.env  # edit the DB_PASSWORD= value

# 4. Verify mode is still 600
stat -c '%a %n' /opt/meddoc-pro/.env

# 5. Save NEW_PW to Bitwarden as "QuillMD — Postgres meddoc <date>"

# 6. Restart app tier so the new password reaches the connection pool
docker compose up -d --force-recreate \
  transcribe-md transcribe-md-worker meddoc-pro marketing postgres-backup

# 7. Verify each container is healthy + can connect
docker compose ps
docker logs --tail 20 meddoc-pro-transcribe-md-1 | grep -iE 'error|fatal' | head -5
```

---

## §3 — Single-user mode (cluster-down recovery)

Scenario: standard psql via `docker exec` doesn't work — usually because the role attributes themselves are broken (e.g., someone ran `ALTER ROLE meddoc NOLOGIN`), or the DB is corrupted and won't accept connections, or you need to bypass authentication entirely.

Single-user mode runs postgres as a single-user backend with **implicit superuser regardless of the connecting role's attributes**. This is the nuclear option — it requires shutting down the running postgres container.

```bash
# 1. Stop the running postgres (this DROPS production traffic — coordinate)
docker compose stop postgres
sleep 5
docker compose ps postgres   # confirm "Exited"

# 2. Run a one-shot postgres in single-user mode against the same data volume.
#    The volume name is meddoc-pro_pgdata (check with `docker volume ls`).
docker run --rm -it \
  --user 999:999 \
  -v meddoc-pro_pgdata:/var/lib/postgresql/data \
  pgvector/pgvector:pg16 \
  postgres --single -D /var/lib/postgresql/data/pgdata meddoc

# Inside the single-user backend prompt (looks like "PostgreSQL stand-alone backend 16.13" then "backend>"):
backend> ALTER ROLE meddoc LOGIN;
backend> ALTER ROLE meddoc PASSWORD 'recovery_pw';
backend> \q

# 3. Restart the regular postgres
docker compose start postgres
sleep 10
docker compose ps postgres   # confirm "healthy"

# 4. Verify connectivity
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c "SELECT 1"
```

**Caveats for single-user mode:**

- The `backend>` prompt has no transactional context — every statement auto-commits.
- No autocommit means you can't BEGIN/COMMIT — single statements only.
- No fancy psql features (`\d`, `\du`, etc.). Use raw SQL: `SELECT * FROM pg_roles WHERE rolname='meddoc';`
- The `--user 999:999` arg makes the container run as the unix `postgres` user that owns the data dir. Without it, root-as-process-owner panics with "could not change directory to / : Permission denied" or similar.

---

## §4 — Bootstrap-user SUPERUSER constraint (background for Round 3 PR-C.1)

Postgres source `src/backend/commands/user.c` rejects any `ALTER ROLE … NOSUPERUSER` against the bootstrap user with:

```
ERROR:  permission denied to alter role
DETAIL:  The bootstrap user must have the SUPERUSER attribute.
```

The bootstrap user is whichever role was created by `initdb` — in our cluster, that's `meddoc` (because `docker-compose.yml` sets `POSTGRES_USER=meddoc`, and the postgres docker-entrypoint feeds that to `initdb`). The `meddoc` row in `pg_authid` has a hardcoded "must keep SUPERUSER" flag that no superuser, including itself, can override.

**This is the reason Round 3 PR-C.1 (audit_logs application-mutability fix, audit finding A09-P0-002) was deferred to Phase 7.** See `POST_MERGE_TODO.md §24.C` for the full deferral reasoning.

The eventual fix is **Option B** — create a separate `meddoc_app` NOSUPERUSER LOGIN role for runtime app connections, with `INSERT, SELECT` only on `audit_logs`, while `meddoc` remains the bootstrap superuser used by migrations + emergency recovery (this runbook). That work is post-pilot scope.

What's still in place from PR-C without PR-C.1:

- `REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM meddoc` is committed (defends against any non-bootstrap role)
- App-layer `logAudit()` calls in 9 PHI-read paths
- `audit_logs` has no UPDATE/DELETE/TRUNCATE endpoints in the application API surface
- Limitation: a malicious actor with DB credentials AND who bypasses the application code path can still mutate `audit_logs`. Mitigated by DB credentials never leaving operator custody + audit rows being one of multiple integrity signals (Sentry, Caddy access logs, app logs all corroborate).

---

## §5 — Common operations cookbook

### Install a new extension

```bash
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c \
  "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
```

### List all roles + their attributes

```bash
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -At -c \
  "SELECT rolname, rolsuper, rolcanlogin FROM pg_roles ORDER BY rolname;"
```

### List which user owns which table

```bash
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -At -c \
  "SELECT tableowner, count(*) FROM pg_tables WHERE schemaname='public' GROUP BY tableowner;"
```

### Drop a stuck connection (if a query hangs)

```bash
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state='active' AND query_start < now() - interval '5 minutes' AND application_name LIKE '%prisma%';"
```

### Find biggest tables (storage + row count)

```bash
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -At -c "
  SELECT
    relname,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
    n_live_tup
  FROM pg_class c
  LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
  WHERE c.relkind = 'r'
  ORDER BY pg_total_relation_size(c.oid) DESC
  LIMIT 10;
"
```

---

## §6 — When this runbook isn't enough

Escalate to:

1. **Phase 6.2 backup restore** — if the data is corrupted, the encrypted offsite backup at Backblaze B2 is the recovery source. See `docs/RUNBOOK_OFFSITE_BACKUP.md`.
2. **`postgres-backup` sidecar** — runs `pg_dump` daily to `/opt/meddoc-pro/backups/last/`. Faster recovery than B2 for recent corruption.
3. **A real DBA** — if you're considering rolling back a migration in prod, or upgrading the major version, get a second pair of eyes. Pre-pilot this is a single-engineer team; post-pilot allocate this work properly.

---

## Verification this runbook is up to date

Last verified: 2026-05-05. Re-verify when:

- Postgres major version upgrade
- `pg_hba.conf` changes (e.g., dropping local trust)
- A new bootstrap user model adopted (e.g., Option B from PR-C.1 deferral)
- New container orchestration (Kubernetes, separate Postgres host, etc.)
