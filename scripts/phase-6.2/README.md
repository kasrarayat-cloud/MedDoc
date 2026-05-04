# Phase 6.2 — Backblaze B2 offsite encrypted backup

This directory is a **navigation index** for Phase 6.2. The actual backup
machinery for Postgres landed earlier under the **h16-offsite-backup**
deliverable (Phase 17) and is fully production-ready. Phase 6.2 closes
the two pieces h16 didn't cover:

1. **MinIO offsite backup** — the audio + exports bucket needs the same
   encrypted offsite mirror that Postgres got in h16.
2. **Automated restore drill** — h16 documented the restore procedure;
   Phase 6.2 turns it into a runnable script so it can be exercised on
   demand and quarterly.

If you're new to the offsite backup story, start with the **strategy
overview** at `docs/phase-6.2-backup-strategy.md`, then the **detailed
runbook** at `docs/RUNBOOK_OFFSITE_BACKUP.md` (the h16 runbook — still
the authoritative procedural source).

---

## What ships in Phase 6.2

| Artifact | What it does |
|---|---|
| `infra/minio-offsite-sync.sh` | MinIO bucket → tar → age-encrypt → B2 upload. Run via host crontab. Mirrors h16's pattern for Postgres but for MinIO. |
| `scripts/minio-offsite-cron.sh` | Host-crontab wrapper around the sync. Logs to `/var/log/quillmd-backups/`, optional Slack alert on failure, 30-day log rotation. |
| `scripts/restore-drill.sh` | Operator-run proof-of-restore for Postgres encrypted blobs. Pulls latest from B2, decrypts with offline private key, restores into a temp Postgres on `:5433`, asserts row counts. |
| `docs/phase-6.2-backup-strategy.md` | High-level strategy: scope, RTO/RPO, disaster scenarios, key custody warnings. |
| (this file) | Navigation index. |

## What was already shipped in h16 (Phase 17)

| Artifact | Status |
|---|---|
| `infra/backup-offsite-sync.sh` | ✅ Postgres → age → B2. Wired as the `postgres-backup` sidecar's `POST_BACKUP_COMMAND`. |
| `docs/RUNBOOK_OFFSITE_BACKUP.md` | ✅ Authoritative procedural runbook (BAA, key custody, rotation, restoration). |
| `docs/H16_OFFSITE_BACKUP_PROCEDURE.md` | ✅ Sister runbook for the Hetzner unencrypted mirror (separate path; Phase 6.2 doesn't touch). |
| `docker-compose.yml` env var wiring | ✅ `BACKBLAZE_KEY_ID` / `_APPLICATION_KEY` / `_BUCKET` are already plumbed into the postgres-backup container. |

If h16 is already activated in production (Postgres backups landing in
B2 daily), Phase 6.2 only needs the **MinIO sync activation** + **first
restore-drill run**. Both are the responsibility of the operator and
tracked in `docs/POST_MERGE_TODO.md` §22.

---

## New env vars added by Phase 6.2

None. Phase 6.2 reuses the h16 env vars:

| Var | Source | Used by |
|---|---|---|
| `BACKBLAZE_KEY_ID` | `/opt/meddoc-pro/.env` (h16) | both Postgres + MinIO sync |
| `BACKBLAZE_APPLICATION_KEY` | `/opt/meddoc-pro/.env` (h16) | both |
| `BACKBLAZE_BUCKET` | `/opt/meddoc-pro/.env` (h16) | both |
| `MINIO_ROOT_USER` | `/opt/meddoc-pro/.env` (existing app config) | MinIO sync only |
| `MINIO_ROOT_PASSWORD` | `/opt/meddoc-pro/.env` (existing app config) | MinIO sync only |

Optional (Phase 6.2 adds):

| Var | Default | Used by |
|---|---|---|
| `QUILLMD_BACKUP_ALERT_WEBHOOK` | unset (no alert) | `minio-offsite-cron.sh` — Slack incoming webhook URL |
| `MINIO_ENDPOINT` | `http://127.0.0.1:9000` | MinIO sync (override if MinIO not on loopback) |
| `MINIO_BUCKETS` | `transcribe-md-audio` | MinIO sync (space-separated for multi-bucket future) |

The age keypair lives at `/etc/meddoc/offsite-backup-public.age` (public,
read by both Postgres and MinIO sync). The private key never touches the
VPS — it lives in the operator's offline secret store. **Without the
private key, all encrypted blobs are unrecoverable.** See
`docs/RUNBOOK_OFFSITE_BACKUP.md` § Key custody.

---

## Required CLIs on the VPS

The h16 path needs `age`, `b2`, `sha256sum`, `python3`. Phase 6.2's
MinIO path adds `mc` and `tar`.

```bash
# 1. age (Ubuntu 22.04+)
sudo apt install -y age

# 2. b2 CLI (via pip — official path)
sudo pip install b2

# 3. mc (MinIO client — single binary download)
curl -fsSL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc
sudo chmod +x /usr/local/bin/mc

# 4. tar, sha256sum, python3 — already on every supported distro
```

`scripts/restore-drill.sh` additionally needs `docker` (for the temp
Postgres) and `psql` (`sudo apt install postgresql-client`). Restore is
typically run from an operator workstation, not the VPS — see the drill
script's header comment for the recommended workflow.

---

## Cron wiring

Postgres (already wired via h16 — no change needed):
The `postgres-backup` sidecar in `docker-compose.yml` runs daily via its
built-in scheduler and fires `infra/backup-offsite-sync.sh` as
`POST_BACKUP_COMMAND`. No host crontab entry needed.

MinIO (new — Phase 6.2 wiring step):
```cron
# /etc/crontab or `crontab -e` — pairs with Postgres 03:00 UTC window.
0 3 * * *  /opt/meddoc-pro/scripts/minio-offsite-cron.sh
```

Activation is a manual operator step (see `docs/POST_MERGE_TODO.md`
§22 → step 5). This PR ships the script but does NOT install the cron.

---

## Cross-references

- Strategy + RTO/RPO + disaster scenarios → `docs/phase-6.2-backup-strategy.md`
- Activation checklist → `docs/POST_MERGE_TODO.md` §22
- Detailed runbook (BAA, restore procedure, rotation) → `docs/RUNBOOK_OFFSITE_BACKUP.md`
- h16 background → `docs/H16_OFFSITE_BACKUP_PROCEDURE.md`
- LUKS at-rest encryption (Phase 6.1, the layer below offsite backup) →
  the production VPS's postgres data volume sits on a LUKS-encrypted
  partition; even if the offsite blob and the host disk are both
  attacked, plaintext PHI never appears.
