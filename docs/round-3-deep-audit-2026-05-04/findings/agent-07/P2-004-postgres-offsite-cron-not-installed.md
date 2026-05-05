---
id: A07-P2-004
title: Phase 6.2 cron scripts shipped but no host-cron entry actually runs them
severity: P2
domain: infrastructure-opsec
date: 2026-05-04
---

## Issue

Phase 6.2 (PR #107, Apr/May 2026) shipped:
- `scripts/postgres-offsite-cron.sh` (host wrapper for encrypted Postgres
  → Backblaze B2)
- `scripts/minio-offsite-cron.sh` (host wrapper for encrypted MinIO
  buckets → B2)

Both scripts document at the top:
```
# Wiring (host crontab, root):
#   0 4 * * *  /opt/meddoc-pro/scripts/postgres-offsite-cron.sh
#   0 3 * * *  /opt/meddoc-pro/scripts/minio-offsite-cron.sh
```

The actual crontab on the host (claude user — root crontab is unreadable)
contains only the existing test harness entries and the one-shot
`@reboot h8-post-reboot.sh`. There is **no** `postgres-offsite-cron.sh`
or `minio-offsite-cron.sh` entry visible to claude, and `/etc/cron.d/`
has none either.

The .env on the VPS does not yet contain the `BACKBLAZE_*` variables (only
the `.env.phase-6.2.template` is staged). So even if the cron lines were
present, the scripts would `exit 78 / EX_CONFIG`. But the absence of the
cron wiring is itself the gap to flag.

## Evidence

```
$ crontab -l
# MEDDOC-TESTS-START ... uptime/disk/container-health/run-all
@reboot /opt/meddoc-pro/scripts/h8-post-reboot.sh ...

(no postgres-offsite-cron.sh or minio-offsite-cron.sh entry)

$ ls /etc/cron.d/
e2scrub_all
sysstat
.placeholder
```

```
$ ls -la /opt/meddoc-pro/.env.phase-6.2.template
-rw-r----- 1 claude claude 1233 May  4 09:39 /opt/meddoc-pro/.env.phase-6.2.template

$ grep BACKBLAZE /opt/meddoc-pro/.env
(no matches — placeholder values not yet promoted)
```

The memory note "Phase 6.2 activation status: prep done 2026-05-04;
Kasra steps + 2 runbook gaps remain" matches: the work is shipped but the
host wiring is the operator's outstanding step.

## Risk

- Backups remain VPS-local until the cron wiring is complete. The h16
  HIPAA finding (geographically-distinct offsite copy) stays open. A VPS
  loss = a backup loss.
- Phase 6.2 is staged for activation; without the cron lines the
  encryption + B2 path is dormant.

## Recommended fix

Activation checklist (root crontab, after BACKBLAZE_* are in .env):

```bash
sudo crontab -e
# Add (with PATH for cron):
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
0 3 * * *   /opt/meddoc-pro/scripts/minio-offsite-cron.sh
0 4 * * *   /opt/meddoc-pro/scripts/postgres-offsite-cron.sh
```

Then verify on the next morning's logs:
```
ls /var/log/quillmd-backups/
b2 ls --recursive ${BACKBLAZE_BUCKET} meddoc-pro/ | head
```

And gate launch on `scripts/restore-drill.sh` passing on an operator
workstation with the offline private key.

Also add to launch-readiness:
- `[ ] postgres-offsite-cron.sh has run successfully ≥3 days`
- `[ ] minio-offsite-cron.sh has run successfully ≥3 days`
- `[ ] restore-drill.sh has passed against current production blob`
