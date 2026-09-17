# Obsolete resource audit — 2026-09-17

This is the final read-only ownership audit and cleanup preparation following
the completed old-application retirement in `retirement-result.json`. The
owner explicitly authorized the fresh start without migration or an archive.
No images, scheduled jobs, live configuration, or remaining source files were
deleted by this audit. The lead executed the reviewed image cleanup separately,
as recorded below.

## Image ownership and prepared cleanup

At 2026-09-17T08:33:02Z, Docker metadata identified **85 distinct obsolete
application images carrying 104 exact tags**. None was referenced by any running
or stopped container. None had a tag outside these exact dedicated repositories:

- `meddoc-pro-transcribe-md`
- `meddoc-pro-transcribe-md-worker`
- `meddoc-pro-meddoc-pro`
- `meddoc-pro-form-detect`
- `meddoc-pro-gotenberg`

The full tag-to-digest inventory is `obsolete-image-manifest.json`. The Docker
system-disk-usage API reported 24,305,405,245 unique bytes (about 22.64 GiB) and
94,466,514,116 logical bytes for this set. Logical size counts shared layers
multiple times; retained build cache or layer references can reduce the actual
space reclaimed. Disk usage before this cleanup was reported by the lead as
91% used / 28 GB available, following the initial preflight's 90% / 30 GB.

Prepared and read-only checked:

- `scripts/retire-old-quillmd-images.py`
- `docs/rebuild/obsolete-image-manifest.json`
- `docs/foundation/mutations/20260917-quillmd-obsolete-images.md`

The precheck passed all 85 digest/tag checks, all-container consumer checks,
and marketing HTTP 200. Python compilation and diff whitespace checks passed.
The script removes only the pinned repository tags, with `docker image rm
--no-prune`, without force. It rechecks consumers and tags immediately before
each removal and verifies all unselected images and all existing containers
remain present with unchanged image/running state. It does not prune volumes,
containers, networks, build cache, or untagged parent images. Execution requires
the committed declaration gate and unchanged tracked script/manifest. The
execution result is recorded in `obsolete-image-cleanup-result.json`.

**Execution update:** the lead completed the declared image cleanup at
2026-09-17T08:38:03.913113Z, under declaration commit
`44819225e0ff9b2835bbe75b346dff542fd63b58`. All 104 tags across the 85 pinned
images were removed. The result records 514 protected images and 39 protected
containers preserved, with marketing HTTP 200. Observed free space rose from
29,081,100,288 to 59,432,210,432 bytes, a 30,351,110,144-byte increase (about
28.27 GiB); this is observed filesystem change during execution, not a promise
derived from the earlier Docker size estimate.

## Shared deploy tree and remaining runtime dependencies

The shared tree `/opt/meddoc-pro` remained on `main` at
`a995c101e0b6cbe9a1ee5d40290e1b29379af8e1`. Its status contained 76 untracked
preflight-report entries and **zero tracked changes**. It is still the old
deployment baseline until the lead completes the reviewed PR/deployment steps.

The isolated tree `/opt/meddoc-pro/.worktrees/quillmd-fresh` is on
`feat/quillmd-fresh-start`; its head was
`44819225e0ff9b2835bbe75b346dff542fd63b58` at this final inspection, with other
agents' active implementation changes present. These two tree states must not
be conflated when assessing what is live.

In the fresh tree, searches of the preserved root Compose file, marketing
Dockerfile/package manifest, shared package manifest and Caddyfile found no
remaining dependency on `transcribe-md`, the old app container name,
`form-detect`, `gotenberg`, or the deleted `packages/{ai,auth,db,types}` paths.
Marketing health was HTTP 200. Caddy's worktree maintenance responses remain a
separate lead-owned deployment because the live bind points to the shared tree.

## Remaining old implementation source

The following dedicated sidecar source remains present and has no consumer in
the preserved Compose/marketing configuration:

- `services/form-detect/app.py`
- `services/form-detect/requirements.txt`
- `services/form-detect/Dockerfile`
- `docker/gotenberg-fonts.Dockerfile` (its font input belongs to the removed
  `apps/transcribe-md` tree)

These are old implementation retirement candidates, not shared services. They
were left untouched because this assignment was read-only audit/preparation.

The scripts below refer to the retired application/schema and are candidates
for a subsequent exact source cleanup. They are not executed by the preserved
marketing Compose configuration. They were not removed or rewritten here:

- `scripts/backfill-auto-certify.ts`
- `scripts/execute-gate0-deactivation.sql`
- `scripts/execute-r226-archive.sql`
- `scripts/execute-r230-practice-archived-backfill.sql`
- `scripts/migrate-specialty-vocab.sql`
- `scripts/prisma-generate.sh`
- `scripts/assert-migrations-applied.sh`
- `scripts/data/build-icd10cm.mjs`
- `scripts/qa/b6-writer-refuses-on-qa.ts`
- `scripts/qa/b8-failure-cost-log-assert.py`
- `scripts/qa/b8-failure-cost-log-assert.sh`
- `scripts/qa/f2-signed-vs-presign-bytes.ts`
- `scripts/qa/rc1-assembly-on-qa.ts`
- `scripts/qa/rc2-twin-door-on-qa.ts`
- `scripts/qa/settle-word-numbering.ts`

Do not bulk-delete `scripts/`: shared mutation/push/merge guards, encrypted-mount
checks, notification credentials, offsite-backup handling and reboot checks
also live there. Historical documents and Git history were not changed.

## Scheduled jobs and reboot behavior

The current user's readable crontab contains these relevant command paths.
Only schedules and paths were recorded; no credentials or command environment
values were exposed.

| Schedule | Command path / observed role |
| --- | --- |
| Every 5 minutes | `tests/automated/monitoring/uptime-check.sh`; HTTP monitoring |
| Hourly | `tests/automated/monitoring/disk-monitor.sh`; disk reporting |
| Every 10 minutes | `tests/automated/monitoring/container-health.sh`; container inspection |
| 02:00 daily | `tests/automated/run-all.sh`; old synthetic smoke/Playwright checks |
| 15:00 and 16:00 daily | `scripts/notify-heartbeat.sh`; notification heartbeat |

The nightly suite still changes into the deleted `apps/transcribe-md` path
and targets old application authentication endpoints when its test credentials
are configured. Retire or replace this obsolete schedule as part of the fresh
deployment. The monitoring scripts inspect status; no old-stack recreation or
container restart was found in them. Public app maintenance responses will
require an intentional monitor update to avoid stale outage alerts. This audit
did not run the scheduled tests or send notifications.

Enabled `quillmd-postreboot-proof.service` invokes
`/usr/local/bin/quillmd-postreboot-proof`, which delegates to
`/opt/meddoc-pro/scripts/verify-post-reboot.sh`. The verification script reads
Compose service/container state and performs host inspection. It still expects
the retired QA Compose file and prints a suggested `docker compose ... up -d`
command when that stack is absent. **That line is a printed instruction, not
an executed restart.** The stale QA check/advice needs updating, while shared
boot verification remains useful.

Enabled `pgdata-encrypted.service` and `miniodata-encrypted.service` open and
mount preserved encrypted storage; they must remain. Existing timers inspected
were host maintenance, certificate renewal or other-project services. No
QuillMD old-app deployment timer was identified. `/etc/rc.local` was absent.

The old `scripts/deploy-prod.sh` can rebuild/start the old stack if manually run
from the current shared main tree; it is not an automatic trigger identified
by this audit. Do not use it to deploy the fresh Python application.

**Follow-up root cron inspection:** direct current-user access was denied, so
the authorized read-only audit used an existing Alpine image with no network,
read-only root filesystem and a read-only bind of the cron spool. Only cron
schedule/path metadata and hashes were returned. Root has five DealHunter jobs
and a 03:15 daily job invoking `/opt/meddoc-pro/scripts/backup-db.sh` with output
to `/var/log/meddoc-backup.log`. The backup script is absent in both trees.
No root entry references the old app, QA stack or deployment script. The
missing backup target is a stale job, but its intended backup ownership cannot
be determined from a missing script, so the prepared cleanup preserves it.
Root crontab SHA-256:
`dc82eff9e1231109512bfe211cc89d70def99c3210cf2364f0e3635a2cce94b8`.
Other users' private cron files remain outside this audit.

## Prepared final source/cron cleanup

`obsolete-source-manifest.json` pins all 19 source paths listed above, their
SHA-256 hashes, the exact obsolete nightly cron line hash, and expected
before/after hashes of user `claude`'s crontab. The independent evidence is:
sidecars have no remaining Compose consumer; database/backfill scripts target
the deleted Prisma schema; QA scripts import the deleted app/AI packages or
target its removed containers; the old ICD builder writes only to deleted
`packages/ai/src/data`. No selected file is imported by fresh Django code,
marketing or the preserved shared package. Remaining references occur in old
tools/tests or explanatory guard comments.

`scripts/retire-old-quillmd-source.py` and declaration
`docs/foundation/mutations/20260917-quillmd-obsolete-source.md` prepare exactly
those removals. They do not execute them as part of this audit. The script
removes source only from the verified isolated worktree and removes only the
02:00 old smoke/E2E cron line. It preserves the shared deployment tree, other
cron bytes, root jobs, monitoring source, shared guards and service resources.
It defaults to read-only checks and refuses path/hash/source/cron drift.

The old `tests/automated/setup-cron.sh` is preserved because it also manages
useful marketing/disk/container checks. Running its installer manually can
reintroduce the retired nightly test line; it needs replacement when those
monitors are adapted. Neither it nor `deploy-prod.sh` was found scheduled for
automatic execution. Preserve reboot/mount services, but update the reboot
verifier's stale QA expectation/advice before relying on its report as evidence
of fresh-application readiness.
