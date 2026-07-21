# Operations scripts

## Prisma migrations (replacement for `db push`)

The repo now has `prisma/migrations/` with a baseline. Schema changes from
here on should go through migrations, not `prisma db push`:

```bash
# Make a schema change in prisma/schema.prisma, then:
npx prisma migrate dev --name describe_your_change
# This generates prisma/migrations/<timestamp>_describe_your_change/,
# applies it locally, and regenerates the Prisma client.

# Commit the new migration folder to git along with your code change.
```

Production and recovery do not run Prisma from an application container and do
not apply every pending migration in one shot. From the repository root, the
Compose migrator defaults to a server-enforced read-only status:

```bash
docker compose run --rm db-migrate --phase status
```

Schema mutation is limited to the closed cumulative `lineage-expand`,
`auth-expand`, `pre-v9`, and `v9` release cut points. Each segment requires its
own freshly verified `targetFingerprints.<segment>` status entry and, in
production, all phase-specific approval controls. The status map is
phase-, ledger-, accepted-source-, and target-bound and is empty on a recovery
target; never reuse or synthesize an entry. The lineage and authentication
online contracts must complete at their intervening gates. Follow
`docs/DEPLOYMENT_RUNBOOK.md` §1.4.1 and the linked online-migration runbooks;
raw `prisma migrate deploy` is not an operations entrypoint.

An existing database created through `db push`, an unknown checksum, or a
non-prefix ledger is **not** eligible for a routine baseline marker. Preserve a
snapshot and the exact ledger/catalog evidence, keep applications stopped, and
obtain a reviewed DBA forward-reconciliation plan under an approved change.
Never mark `0000_init` or another migration applied merely to make status look
clean, and never edit `_prisma_migrations` directly.

## `backup-db.sh`

Daily Postgres dump + rotation. See the header comments for install steps.

**Restore from a dump (in an emergency):**

```bash
# 1. Stop the app (keep postgres running)
docker compose stop app

# 2. Copy the dump into the postgres container
docker compose cp /var/backups/meddoc/meddoc-YYYYMMDDTHHMMSSZ.dump \
  postgres:/tmp/restore.dump

# 3. Drop & recreate the DB (DESTRUCTIVE — make sure you have another copy)
docker compose exec -T postgres psql -U meddoc -d postgres -c \
  "DROP DATABASE IF EXISTS meddoc; CREATE DATABASE meddoc;"

# 4. Restore
docker compose exec -T postgres \
  pg_restore -U meddoc -d meddoc /tmp/restore.dump

# 5. Inspect restored migration state only (applies nothing)
docker compose run --rm db-migrate --phase status
```

Keep the app stopped. For a production restore, complete the exact-ledger,
closed-phase, online-contract, and database-principal recovery gates in
`docs/runbooks/disaster-recovery.md`; this condensed script note does not
authorize migration or ledger repair. Only after every recovery gate passes:

```bash
# 6. Restart the app
docker compose start app
```

**Test the restore on a staging VPS before relying on it in prod.** A backup
you've never tried to restore is not actually a backup.
