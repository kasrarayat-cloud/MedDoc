---
id: A12-P1-002
title: Phase 6.2 runbook gaps — MinIO offsite activation procedure + MinIO restore drill not in runbook
severity: P1
domain: docs/runbook/phase-6.2
---

# Issue

Memory note for the project explicitly says: "Kasra steps + 2 runbook gaps remain". The deep-audit prompt asks me to identify those 2 gaps explicitly. Both are MinIO-shaped:

1. **MinIO offsite-activation procedure has no runbook section.** The existing authoritative runbook (`docs/RUNBOOK_OFFSITE_BACKUP.md`) is 100% Postgres-only. MinIO offsite activation is described only in the high-level strategy (`docs/phase-6.2-backup-strategy.md`) and in the §22 activation list inside `docs/POST_MERGE_TODO.md`. An operator looking at the runbook gets nothing about MinIO; an operator looking at the strategy gets prose, not steps. The runbook section corresponding to `infra/minio-offsite-sync.sh` simply does not exist.

2. **MinIO restore drill has no runbook procedure.** `scripts/restore-drill.sh` automates Postgres restore-drill only. POST_MERGE_TODO §22 *acknowledges* this gap (see §22 "Open follow-ups" → "MinIO restore drill — `restore-drill.sh` covers Postgres only today. … Document as a runbook addendum when first MinIO restore is exercised."). For a HIPAA technical-safeguard activation gate, "document later" is not enough — the drill is part of activation, and Phase 6.2 cannot be declared `phase-6.2-live` without it.

# Evidence

`grep -nE 'minio|MinIO' /opt/meddoc-pro/docs/RUNBOOK_OFFSITE_BACKUP.md` returns zero results — the runbook never mentions MinIO. The runbook's resolution checklist (`§G`, lines 535-555) ends with "Restoration drill completed end-to-end (C.*)" — "C.*" being only the Postgres restore drill in §C.1-C.8.

`/opt/meddoc-pro/docs/POST_MERGE_TODO.md:1350` (acknowledged gap):
> "**MinIO restore drill** — `restore-drill.sh` covers Postgres only today. A MinIO restore drill is a separate operator task: pull the latest `meddoc-pro/minio/<date>/transcribe-md-audio-*.tar.age` from B2, decrypt, untar, mc-cp into a fresh MinIO bucket on a non-production port, sample-verify a known audio file plays. Document as a runbook addendum when first MinIO restore is exercised."

`/opt/meddoc-pro/scripts/phase-6.2/README.md:14-17` directs operators to `docs/RUNBOOK_OFFSITE_BACKUP.md` as "the authoritative procedural source" — but that runbook has no MinIO content, so the navigation index points to a dead link for MinIO purposes.

`/opt/meddoc-pro/docs/POST_MERGE_TODO.md:1311-1316` (operator MinIO sync test, the closest thing to a runbook for MinIO):
```
sudo bash /opt/meddoc-pro/infra/minio-offsite-sync.sh
# Verify: b2 ls --recursive $BACKBLAZE_BUCKET meddoc-pro/minio/
# should show today's dated blob.
```
Three lines of prose for what should be a runbook section parallel to RUNBOOK_OFFSITE_BACKUP.md §B (Postgres first-run verification, ~50 lines).

The sister script `/opt/meddoc-pro/infra/minio-offsite-sync.sh` exists and is wired (per POST_MERGE_TODO §22 step 9, host crontab pulls it). Its file-info tags, log location, error codes, and prune behaviour mirror the postgres script but **none of that is documented** in the runbook the operator is told to use.

# Risk

- **Activation risk**: an operator running step 7 of POST_MERGE_TODO §22 ("Manual MinIO sync test") has no runbook to consult when the script behaves unexpectedly. The Postgres path has §B.2 ("Watch the offsite sync") with expected log lines; the MinIO path has nothing.
- **First-incident risk**: when the MinIO bucket is nuked (intentional or otherwise), the procedure to restore is invented under load. Recovering from B2 requires knowing the file-name convention (`meddoc-pro/minio/<date>/transcribe-md-audio-*.tar.age`), the encryption-key location (offline private key), the untar workflow, the `mc cp` to a new bucket on a non-prod port, sample-verification — all unwritten.
- **Audit evidence**: `RUNBOOK_OFFSITE_BACKUP.md` §B.4 ("Record evidence") is a compliance artifact reviewers ask for. The MinIO half has no equivalent template; operators improvise the audit trail.
- **Drill cadence**: POST_MERGE_TODO §22 commits to quarterly restore drills. Without a written MinIO drill procedure, the "quarterly drill" reduces to the Postgres half — silently halving the actual exercise.

# Recommended fix

Append two sections to `docs/RUNBOOK_OFFSITE_BACKUP.md`:

**§H — MinIO offsite sync (Phase 6.2 — supplement)**
- §H.1 Pre-flight: confirm `mc`, `b2`, `age` installed (POST_MERGE_TODO §22 step 6 ran during prep).
- §H.2 Wire `MINIO_ENDPOINT`, `MINIO_BUCKETS`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` in `.env` (already present from app config) — link.
- §H.3 Manual first-run: `sudo bash /opt/meddoc-pro/infra/minio-offsite-sync.sh`. Expected log sequence (mirroring Postgres §B.2). Expected B2 path: `meddoc-pro/minio/<YYYY>/<MM>/<DD>/transcribe-md-audio-<bucket>-<UTC>.tar.age`.
- §H.4 Verify in B2 console — File Info tags should include `sha256`, `minio_bucket`, `source_hostname`, `uploaded_at`, `tar_size`.
- §H.5 Wire host crontab `0 3 * * * /opt/meddoc-pro/scripts/minio-offsite-cron.sh`.
- §H.6 Record activation evidence per `audit-evidence/h16/` shape.

**§I — MinIO restore drill**
- §I.1 Pull private key per §C.1 (already documented for Postgres; reuse).
- §I.2 Identify latest blob: `b2 ls --recursive $BACKBLAZE_BUCKET meddoc-pro/minio/`.
- §I.3 Download: `b2 file download` to `/tmp/restore.tar.age`.
- §I.4 Verify pre-encryption sha matches B2 file-info `sha256` tag (after decryption).
- §I.5 Decrypt: `age --decrypt --identity <private-key> --output /tmp/restore.tar /tmp/restore.tar.age`.
- §I.6 Spin up scratch MinIO on port 19000: `docker run -d --name minio-restore -p 19000:9000 -p 19001:9001 -e MINIO_ROOT_USER=test -e MINIO_ROOT_PASSWORD=test123 minio/minio server /data`.
- §I.7 `mc alias set restore http://localhost:19000 test test123`. Untar: `tar xf /tmp/restore.tar -C /tmp/restore-data/`. `mc mirror /tmp/restore-data/transcribe-md-audio restore/transcribe-md-audio`.
- §I.8 Sample-verify: pick one known audio key from a recent visit, `mc cat restore/transcribe-md-audio/<userId>/<visitId>/audio.webm | head -c 100 | xxd` shows valid WebM magic. Optional play-back if a webm decoder is available.
- §I.9 Tear down: `docker stop minio-restore && docker rm minio-restore && shred -u /tmp/restore.tar /tmp/restore.tar.age && rm -rf /tmp/restore-data/`.

Then upgrade `scripts/restore-drill.sh` to optionally include MinIO, or ship a sibling `minio-restore-drill.sh` and reference it from §I. Update §G resolution checklist to include MinIO drill completion as a gate — Phase 6.2 cannot be declared `phase-6.2-live` until §H + §I both run successfully.

Once the runbook is amended, flip POST_MERGE_TODO §22 step 11 ("Update §22 status here from ⏳ pending → ✅ active") and tag `phase-6.2-live`.
