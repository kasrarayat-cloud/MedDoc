# T-M12 — MinIO orphan cleanup

Scheduled sweep that deletes audio objects in the `transcribe-md-audio`
bucket that no `transcribe_visits` row references. Disabled by default;
ops has to opt in via `.env`.

## Why it exists

Audio objects land in MinIO before Postgres writes the visit row.
Visits may later be deleted (test cleanup, HIPAA retention, account
deletion) while the MinIO object persists. Over time the bucket grows
unbounded. Without this sweep the only way to reclaim space is
manual mc commands.

## How the sweep decides

For every object in the bucket:

| Object state | Sweep action |
|---|---|
| Referenced by a visit's `audioKey` or `dictationAudioKey` | **keep** |
| Orphan, younger than `retentionDays` | **keep** (race guard) |
| Orphan, older than `retentionDays` | **delete** (or log in dry-run) |

**The race guard matters.** An upload that just landed in MinIO might
not have its Prisma row written yet (route writes MinIO then Prisma).
`retentionDays` must be longer than any plausible in-flight upload —
the default of 30 days is intentionally loose.

## Enabling in production

Edit `.env` on the VPS:

```
MINIO_ORPHAN_CLEANUP_ENABLED=true
MINIO_ORPHAN_CLEANUP_DRY_RUN=true              # KEEP true for first run
MINIO_ORPHAN_CLEANUP_RETENTION_DAYS=30
MINIO_ORPHAN_CLEANUP_CRON=0 3 * * 0            # Sundays 3am UTC
```

Then restart the worker:

```
docker compose up -d transcribe-md-worker
```

On boot you'll see one of:

```
[ops:minio-cleanup] disabled (MINIO_ORPHAN_CLEANUP_ENABLED != "true")
[ops:minio-cleanup] enabled, cron="0 3 * * 0" UTC, retentionDays=30, dryRun=true
```

### Recommended rollout

1. **Enable in DRY_RUN for at least one cron cycle** (one week).
   Grep the logs:
   ```
   docker compose logs transcribe-md-worker --since 7d | grep ops:minio-cleanup
   ```
   Review `WOULD DELETE` lines. If anything looks wrong, tighten
   retentionDays or debug before flipping.
2. **Flip DRY_RUN=false** once the list is trusted. Restart worker.
3. **Check the next-run summary** for expected totals
   (`bytesReclaimed`, `deleted`, `kept`).

## Manual run (outside the schedule)

From the host:

```
npm run minio:cleanup -w transcribe-md
```

Or inside the container:

```
docker compose exec transcribe-md-worker npx tsx scripts/minio-cleanup.ts
```

Reads the same env vars as the scheduled run. Override inline for a
one-off test:

```
docker compose exec \
  -e MINIO_ORPHAN_CLEANUP_DRY_RUN=true \
  -e MINIO_ORPHAN_CLEANUP_RETENTION_DAYS=90 \
  transcribe-md-worker npx tsx scripts/minio-cleanup.ts
```

## Tuning retention

| Value | When to pick it |
|---|---|
| 30 days (default) | Normal operation. Safe margin over any in-flight upload, gives ops a week+ to notice if something's wrong. |
| 7 days | Aggressive recovery on a storage-pressured bucket. Never less than 1 day. |
| 90+ days | Extra caution during the first few production cycles. |

## Failure modes

| Symptom | Likely cause | What to do |
|---|---|---|
| `[ops:minio-cleanup] delete failed for <key>` | Transient MinIO blip | No action — next scheduled run picks up the leftover. |
| `retentionDays` reading as NaN in logs | Env variable set but empty | Ops set the var to a blank value; either unset it or give it a real number. |
| Unexpectedly large `deleted` count | Postgres was partially wiped (e.g., a test cleanup that missed some rows) | Set DRY_RUN=true IMMEDIATELY, inspect the WOULD DELETE list, restore from the most recent `/home/claude/meddoc-pro-backup-*.sql` if needed. |
| Zero deletes for months on a growing bucket | No visits being deleted → no orphans. Expected. | Nothing to do. |

## What's NOT in scope

- No cleanup of MinIO objects that belong to OTHER buckets (meddoc-pro,
  marketing artifacts). Only `transcribe-md-audio`.
- No cleanup of Postgres rows. A missing MinIO object won't trigger
  the app to null out `audioKey` — a future enhancement.
- No ops dashboard for the sweep. Logs are the only surface; that's
  deliberate (no new table, no new UI).
