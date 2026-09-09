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

On your production VPS (after pulling the new migration):

```bash
# Apply all pending migrations. Idempotent — skips ones already applied.
docker compose run --rm db-migrate
```

**First-time setup on a fresh prod DB that has been managed via `db push`
until now:** mark the baseline as already applied so `migrate deploy`
doesn't try to re-create tables that already exist:

```bash
docker compose run --rm --entrypoint /app/node_modules/.bin/prisma db-migrate migrate resolve --applied 0000_init
```

I've already done this for the dev DB; do it once on prod before the
first `migrate deploy`.

## `backup-db.sh`

Daily Postgres dump + rotation. See the header comments for install steps.

**Restore from a dump (in an emergency):**

```bash
# 1. Stop the app (keep postgres running)
docker compose stop transcribe-md transcribe-md-worker

# 2. Copy the dump into the postgres container
docker compose cp /var/backups/meddoc/meddoc-YYYYMMDDTHHMMSSZ.dump \
  postgres:/tmp/restore.dump

# 3. Drop & recreate the DB (DESTRUCTIVE — make sure you have another copy)
docker compose exec -T postgres psql -U meddoc -d postgres -c \
  "DROP DATABASE IF EXISTS meddoc; CREATE DATABASE meddoc;"

# 4. Restore
docker compose exec -T postgres \
  pg_restore -U meddoc -d meddoc /tmp/restore.dump

# 5. Restart the app
docker compose start transcribe-md transcribe-md-worker
```

**Test the restore on a staging VPS before relying on it in prod.** A backup
you've never tried to restore is not actually a backup.
