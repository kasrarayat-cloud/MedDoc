---
id: A09-P3-002
title: No Redis SETNX cross-process lock — overlapping crons + worker contention possible
severity: P3
domain: distributed-coordination / cron
---

## Issue
The host cron jobs (`scripts/postgres-offsite-cron.sh`,
`scripts/minio-offsite-cron.sh`) and the BullMQ-scheduled jobs inside the
worker container (T-M12 minio orphan cleanup, T-M17.3 stale-visit
cleanup, T-M18.1 retention sweep) operate on overlapping resources:

- Both the host cron and the sidecar's POST_BACKUP_COMMAND can race on
  the `/backups/last/` directory + the B2 bucket if the operator enables
  both legs (script comment in `infra/backup-offsite-sync.sh:15-20` says
  "operators may run BOTH"). No SETNX-style lock prevents the host
  cron's encrypted-B2 push from running concurrently with the sidecar's
  S3-mc push, but they target different destinations so corruption is
  unlikely. The risk is bandwidth contention + duplicate B2 list/prune
  invocations.
- T-M12 MinIO orphan cleanup walks the whole audio bucket. If a visit
  upload happens to land DURING the sweep, the upload's putObject lands
  fine but the orphan-decision logic uses a snapshot of "all
  TranscribeVisit rows" taken at sweep start — a very-fresh upload's
  audio may be miscategorised as orphan if the DB query happened a
  second before the upload row was committed. The 30-day retention
  buffer makes this safe in practice, but the dependency is implicit.
- The T-M17.3 stale-visit cleanup and T-M18.1 retention sweep run on
  cron schedules offset by 1h (3am vs 4am UTC) so they don't fight, but
  this is a configured timing dependency rather than a real lock.

There's no codified "only one instance of each sweep can run at a time"
guard. BullMQ's `upsertJobScheduler` produces idempotent scheduling, so
two worker containers (if we ever scale out) would each schedule the
same recurring job — but BullMQ's repeat key dedupes that. The race
within a single worker is implicit (concurrency=1 on the cleanup
worker per `worker.ts:949-953`).

## Evidence
- `apps/transcribe-md/src/worker.ts:949-953`:
  ```ts
  {
    connection: getSharedRedisConnection(),
    concurrency: 1,
  }
  ```
  Cleanup worker runs sweeps serially. Good.
- `scripts/postgres-offsite-cron.sh` + `scripts/minio-offsite-cron.sh`:
  no `flock` / `SETNX` guard. If a previous run is still active and
  cron tries to start a second, both run.
- `infra/backup-offsite-sync.sh`: no lock either.

## Risk
P3 — current scale doesn't trigger this. Future-proofing concern.

## Recommended fix
Two cheap additions:

1. **flock the host crons**:
   ```bash
   exec 200>/var/lock/quillmd-postgres-offsite.lock
   flock -n 200 || { log "another postgres-offsite-cron already running, skipping"; exit 0; }
   ```
   Standard pattern, zero infrastructure.

2. **Optional: Redis SETNX in the cleanup sweeps**. Each sweep takes a
   distributed lock at start (`SET cleanup:lock:minio NX EX 600`) and
   releases at end. If the lock fails, log and skip. Belt-and-braces in
   case the cleanup worker is ever horizontally scaled.

Both are low-effort, ship before pilot scaling.
