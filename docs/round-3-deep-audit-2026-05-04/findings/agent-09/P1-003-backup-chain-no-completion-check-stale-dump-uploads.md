---
id: A09-P1-003
title: Postgres offsite backup uploads "freshest mtime" without completion check — half-written or stale dumps land in B2
severity: P1
domain: data-integrity / backup chain
---

## Issue
The Postgres backup chain (sidecar → host cron → encrypted B2) has TWO race
windows, neither of which is closed by a completion manifest, lock file, or
size-vs-yesterday sanity check:

**Race 1 — sidecar pg_dump still running when host cron picks up.** The
postgres-backup sidecar runs at @daily (~00:00 UTC). The host cron at
`scripts/postgres-offsite-cron.sh` runs at 04:00 UTC. The cron picks the
freshest `*.sql.gz` by mtime:

```bash
DUMP_PATH="$(find "${HOST_BACKUP_DIR}/last" -maxdepth 1 -type f -name '*.sql.gz' \
  -printf '%T@ %p\n' 2>/dev/null \
  | sort -nr \
  | head -n 1 \
  | awk '{print $2}')"
```

The 4-hour gap is comfortable for our current data size (~1 GB), but:
- If pg_dump SIGKILL'd or OOM'd partway, a partial `meddoc-<date>.sql.gz`
  file with newer mtime is on disk. The cron picks it. age-encrypts it.
  Uploads it to B2. The encrypted blob is unrestorable, but B2 looks happy
  and the Slack alert hook sees exit code 0.
- If pg_dump runs >4h (unlikely now, possible at scale), the cron picks
  YESTERDAY'S freshest dump and re-uploads it. The B2 path is namespaced
  by today's date (`meddoc-pro/$(date)/…`), so B2 ends up with two
  pointers to logically-identical content.

**Race 2 — sidecar's `last/` filename pattern.** `ls backups/last/` shows:
```
meddoc-20260504-000000.sql.gz
meddoc-latest.sql.gz
```
Two files. The cron picks the newest by mtime, which is whichever one
prodrigestivill/postgres-backup-local last touched. Some versions of the
image symlink `meddoc-latest.sql.gz` AFTER fully writing the dated file —
so picking by mtime is correct. But:
- The dated file is written non-atomically (no temp + rename in the upstream
  image's default config that I can see).
- If the host crashes between "dated file written, latest symlink updated"
  and "next day's run", the post-crash filesystem could leave them
  out-of-sync; the cron picks one that's not what the operator expects.

There is also no check that today's dump is roughly the size of yesterday's.
A pg_dump that connects to an empty DB (e.g. a misconfigured `POSTGRES_DB`
env after a deploy) produces a tiny "valid" gz that age-encrypts cleanly
and uploads — silently destroying the offsite chain because the bucket
retention is 30 days and after 30 days of empty backups, restorable history
is gone.

## Evidence
- `scripts/postgres-offsite-cron.sh:115-126`: 24h grace check is "does
  `${HOST_BACKUP_DIR}/last` exist with any *.sql.gz?" — no manifest, no
  completion check, no size sanity.
- `infra/backup-offsite-sync.sh:124-143`: `find_latest_dump()` — same
  freshest-mtime pick.
- `infra/postgres-backup/postscript.sh`: doesn't write any "I finished"
  marker that the host cron could check.
- `docker-compose.yml:514-543`: postgres-backup sidecar config — no
  `POST_BACKUP_COMMAND` that touches a sentinel file the host could read.
- `infra/backup-offsite-sync.sh:284-321`: `prune_old_blobs()` deletes
  blobs older than 30 days from B2. So a stretch of bad uploads erases
  the historical good ones in 30 days.

## Risk
P1 — corrupted / stale offsite backups. Severity logic:
- The local sidecar still keeps 7 daily / 4 weekly / 6 monthly snapshots on
  the host volume. So even if every offsite upload were stale for 30 days,
  the on-host last-good-dump would still be intact. P1 not P0 because of
  this fallback.
- However, h16 was specifically about "VPS lost → restore from offsite". A
  silently-broken offsite chain defeats that whole control. If the VPS dies
  on day 31 and the last 30 days of B2 blobs are all "yesterday's dump
  encrypted with today's path", restore-drill discovers a 30-day data hole.

## Recommended fix
Three things, in order:

1. **Completion sentinel from the sidecar**. Add a wrapper script
   `infra/postgres-backup/postscript.sh` (or a separate hook) that, after
   pg_dump completes successfully, writes
   `/backups/last/.last-success-<date>.txt` with `pg_dump exit=0
   sha256=<hash> size=<bytes>`. The host cron checks for THIS file with
   today's date before picking the dump:
   ```bash
   today_marker="${HOST_BACKUP_DIR}/last/.last-success-$(date -u +%Y%m%d).txt"
   if [[ ! -f "$today_marker" ]]; then
     log "INFO: no completion marker for today — sidecar still running or failed; skipping with grace"
     exit 0
   fi
   ```

2. **Size sanity check.** Compare today's dump size to the previous
   uploaded blob's size. If it's <50% of yesterday's size, alert and refuse
   to upload (someone hit the wrong DB, or the data was accidentally
   truncated). Pull yesterday's size from `b2 file info` on the previous
   B2 key.

3. **Atomic write in the sidecar**. Change the sidecar's
   POSTGRES_EXTRA_OPTS or wrap pg_dump so the dump goes to a `.tmp` file
   then `mv` to its final name only on exit code 0. The upstream image
   may already do this — verify and document, or fork the wrapper.

A separate weekly restore-drill (already in `scripts/restore-drill.sh`,
worth verifying it still passes against the encrypted chain) is the
ultimate safety net but tangentially scoped.
