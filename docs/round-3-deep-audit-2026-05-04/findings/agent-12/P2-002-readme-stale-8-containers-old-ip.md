---
id: A12-P2-002
title: README + WORKER.md + LAUNCH_CHECKLIST drift — 8 containers (actual 9), old IP 5.231.107.93 in WORKER.md, encrypted-volume runbook paths obsolete
severity: P2
domain: docs/staleness
---

# Issue

Several authoritative docs are stale relative to actually-shipped state. A new engineer (or an onboardee) reading these in good faith encounters wrong commands, wrong counts, and wrong paths.

# Evidence

**1. README.md claims 8 containers, actual is 9.**

`README.md:24`:
> "Everything runs in Docker Compose on a single VPS — 8 containers total at steady state."

`README.md:48-49`:
> `docker-compose.yml     8 services (caddy + marketing + meddoc-pro + transcribe-md + transcribe-md-worker + postgres + redis + minio)`

`README.md:61`:
> "A VPS with ≥2 GB RAM for all 8 containers at idle."

Actual count from `docker-compose.yml` services block: **10 services defined**, of which **9 are long-running** (the 10th, `db-migrate`, is run-once via `docker compose run --rm`). Long-running containers:
1. caddy
2. marketing
3. meddoc-pro
4. transcribe-md
5. transcribe-md-worker
6. postgres
7. redis
8. minio
9. **postgres-backup** ← added in T-M16.4 backup sidecar; missing from README

`PILOT_STATUS.md` and `LAUNCH_READINESS.md` correctly say 9/9. POST_MERGE_TODO §22 also says 9. The README is the only outlier — and it's the most-read entry point.

**2. WORKER.md references the old IP `5.231.107.93`.**

`apps/transcribe-md/WORKER.md:72`:
```
2. **Sign up** at `http://5.231.107.93:9020/signup`, or reuse an existing account.
```

Per `POST_MERGE_TODO.md` §23 (2026-05-04), the VPS IP migrated to `147.189.172.8`. Per memory, the active production hostname is `app.quillmd.com` over HTTPS. The IP is doubly stale (wrong IP + wrong protocol + wrong port — port 9020 was MODE A pre-Phase-13/T-M19 HTTPS cutover). An engineer following WORKER.md verbatim hits a dead address.

`docs/LAUNCH_CHECKLIST.md:41` ("TranscribeMD currently answers on `http://5.231.107.93:9020`") is also stale, but the section is dated 2026-04-22 and the doc has a "last reviewed: 2026-04-22" stamp — at least it's clear this is historical. WORKER.md has no date and reads as current.

`README.md` itself has no stale IP — it uses `app.quillmd.com` consistently.

**3. RUNBOOK_ENCRYPTED_VOLUME.md documents the wrong path scheme.**

`docs/RUNBOOK_ENCRYPTED_VOLUME.md:11-15`:
> "The postgres service's data directory is bind-mounted from `/var/lib/meddoc-postgres-data` on the host. That host directory is the mount point of an ext4 filesystem inside a LUKS2 container backed by a sparse 50 GB loop file at `/var/lib/meddoc-postgres-encrypted.img`. The LUKS key file lives at `/etc/meddoc/postgres-volume.key`..."

Actual deployment per Phase 6.1 / POST_MERGE_TODO §12 (2026-05-02):
- Bind-mount: `/mnt/pgdata-encrypted:/var/lib/postgresql/data` (NOT `/var/lib/meddoc-postgres-data`)
- LUKS file: `/opt/meddoc-pro/secrets/pgdata.luks` (NOT `/var/lib/meddoc-postgres-encrypted.img`; NOT 50 GB — 1 GB sparse)
- Key file: `/etc/quillmd/pg-luks.key` (NOT `/etc/meddoc/postgres-volume.key`)
- systemd unit: `pgdata-encrypted.service` (NOT `meddoc-postgres-volume.service`)
- Mapper name: `pg-encrypted` (matched `/dev/mapper/pg-encrypted`)

`docker-compose.yml` confirms the actual: `- /mnt/pgdata-encrypted:/var/lib/postgresql/data` is the bind line. Every key path in the runbook §0 is wrong. An operator following §1.1-§1.5 pre-flight + §2 maintenance window verbatim will reach for paths that don't exist.

**4. RUNBOOK_OFFSITE_BACKUP.md A.4 + the H16 procedure both refer to a postgres-backup image install path that may not match the actual.**

`RUNBOOK_OFFSITE_BACKUP.md:82-93` discusses installing `age` + `b2` "in a derived image" or via host bind-mount. Per POST_MERGE_TODO §22 step 6 (2026-05-04), the actual install is on the **host** via Docker bind-mount:
```bash
docker run --rm -v /usr/local/bin:/host_bin ubuntu:24.04 bash -c '...'
```
End state: `age`, `age-keygen`, `mc`, `b2` at `/usr/local/bin/`. The runbook's A.4 doesn't reflect this — an operator reading it gets confused about which path was taken.

# Risk

- **Onboarding cost**: every stale claim is a small detour an onboardee takes before realising the doc is wrong.
- **Operational mistakes during stress**: at 02:00, an operator following `RUNBOOK_ENCRYPTED_VOLUME.md` paths verbatim will fail. The path mismatch is silent — no error message says "this path is from the pre-Phase-6.1 design" — they get `cryptsetup: device not found` and have to re-derive.
- **Audit trust**: a reviewer who spot-checks one doc and finds it stale loses trust in the whole compliance program. Even though the runbook is *almost* right, the gap is auditable.
- **2-AM wrong path on a real disaster**: combined with A12-P1-001 (no DR runbook), an operator could try to fail-over via the LUKS runbook's wrong paths and burn an hour.

# Recommended fix

**README.md** —
- Replace 3 instances of "8 containers" / "8 services" with "9 containers" / "9 services (10 with one-shot db-migrate)". Update the service list to include `postgres-backup`.
- Add a "last reviewed" stamp at the top so future drift is visible.

**apps/transcribe-md/WORKER.md** —
- §"Manual test procedure" step 2: replace `http://5.231.107.93:9020/signup` with `https://app.quillmd.com/signup` (or `http://localhost:9020` for local dev).
- Add a "last reviewed" stamp.

**docs/RUNBOOK_ENCRYPTED_VOLUME.md** —
- This runbook predates Phase 6.1's actual implementation. Either:
  - **(preferred)** rewrite §0-§5 to match the Phase 6.1 actuals: `/mnt/pgdata-encrypted` + `/opt/meddoc-pro/secrets/pgdata.luks` + `/etc/quillmd/pg-luks.key` + `pgdata-encrypted.service` + mapper `pg-encrypted`.
  - **OR** mark §0 as "Original h8 design (superseded by Phase 6.1 — see POST_MERGE_TODO §12)" and add §7 "Phase 6.1 actuals" with the deployed paths.
- Update the §6 audit-trail entry format to reference the actual key file location.

**docs/RUNBOOK_OFFSITE_BACKUP.md** —
- §A.4: replace the "Option 1 / Option 2" framing with the chosen approach (host install via Docker bind-mount, post-prep state on 2026-05-04). Reference POST_MERGE_TODO §22 step 6 for the install commands.
- §G resolution checklist: add an item for "MinIO offsite-sync activation verified (per §H)" once §H is added per A12-P1-002.

**Lightweight CI guard.**
Add a CI check that fails the build if any of these tokens are found in tracked docs:
- `5.231.107.93` (old IP — should never appear unless in a §dated historical note)
- `8 containers` / `8 services` (outdated count)
- `/var/lib/meddoc-postgres` (pre-Phase-6.1 path)

Tiny script in the existing GitHub Actions workflow next to the a11y job. The same pattern as the `grep -rE` route-inventory check from POST_MERGE_TODO §7. Output is fail-fast at PR time, so future drift is caught at PR review rather than at 02:00.
