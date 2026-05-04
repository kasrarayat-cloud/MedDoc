# Phase 6.2 — QuillMD backup strategy

This is the high-level strategy doc. For the procedural runbook (BAA
signing, key generation, restoration steps) see
`docs/RUNBOOK_OFFSITE_BACKUP.md`. For the navigation index across all
backup artifacts see `scripts/phase-6.2/README.md`.

Phase 6.2 is the second layer of the QuillMD HIPAA technical
safeguard stack:

```
Phase 6.1   At-rest encryption          LUKS on the postgres data volume.
                                         Defends against physical disk theft.

Phase 6.2   Offsite encrypted backup    Daily age-encrypted blobs in B2.
(this doc)                               Defends against VPS loss + ransomware
                                         + accidental deletion + B2 account
                                         compromise (encrypted = useless without
                                         offline private key).
```

---

## Cadence

**Daily, 03:00 UTC** for both Postgres and MinIO.

- 03:00 UTC = ~07:00 PT, ~10:00 ET, ~03:00 BST. Outside doctor active
  hours in every continental US zone we serve and Kasra's home TZ
  (Vancouver / Tehran travel).
- Postgres backup runs first via the `postgres-backup` sidecar's
  built-in scheduler (`prodrigestivill/postgres-backup-local:16`).
  Offsite encrypted upload (`infra/backup-offsite-sync.sh`) is a
  `POST_BACKUP_COMMAND` hook, so it always sees a fresh dump.
- MinIO backup runs second via host crontab calling
  `scripts/minio-offsite-cron.sh`. The two are independent — MinIO
  failure does not affect Postgres backup or vice versa.

## What's backed up

| Source | What | Why |
|---|---|---|
| Postgres (all DBs) | `transcribe_visits`, `transcribe_md_patients`, `users`, `audit_logs`, etc. | All QuillMD clinical state + audit trail. |
| MinIO `transcribe-md-audio` | Original uploaded audio + dictation `.webm`/`.m4a` files + generated PDFs/DOCX. | The audio is the source-of-truth recording; the rendered docs are reproducible from SOAP text + visit metadata, but reproducing them requires the AI pipeline to re-run, which costs money and time. |

`apps/meddoc-pro` tables share the same Postgres instance and ride
along on the `pg_dump`. The CRM is decommissioned (see §21) but its
legacy rows are preserved for the same retention window as QuillMD
data — no extra effort required.

## What's NOT backed up

| Source | Why not |
|---|---|
| Redis | Ephemeral. Session cookies regenerate on next login (worst case: every active user has to sign in again). BullMQ queue state regenerates as workers process the next batch — no QuillMD job depends on a persistent queue across reboots. |
| MinIO scratch buckets (none today, future) | Only buckets named in `MINIO_BUCKETS` env var get backed up. Defaults to `transcribe-md-audio`. |
| `/var/log/*` / Docker container logs | Operational noise; replayable from production via Sentry / `docker logs` in the recovery window. |
| The age **private** key | **Intentionally** never on the VPS. Lives in the operator's offline secret store. See "Disaster scenarios" below. |

## Encryption shape

- **age** ([age-encryption.org](https://age-encryption.org)) — modern
  asymmetric file encryption, X25519 keys, ChaCha20-Poly1305 AEAD.
- **Public key** lives at `/etc/meddoc/offsite-backup-public.age` on the
  VPS (mode 0444, world-readable — public keys are public). Backup
  scripts read this on every run.
- **Private key** lives in the operator's offline secret store
  (1Password Vault recommended, plus a paper printout in a fireproof
  safe). Operator carries it to the workstation that performs restoration
  and wipes the workstation copy after.
- **Belt-and-braces server-side**: B2 bucket has SSE-B2 default
  encryption (AES-256). So encrypted blobs are encrypted twice — once
  client-side via age (the load-bearing layer) and once server-side via
  B2 (defence-in-depth against B2 account compromise alone).

## Recovery objectives

**RTO — recovery time objective: under 2 hours.**
Based on the `restore-drill.sh` pipeline timing on a representative
production-sized dump:
- B2 download (encrypted blob, ~50-500 MB compressed): 1-5 min
- age decrypt + gunzip: <1 min
- Temp Postgres spin-up: ~30 sec
- `psql -f` restore: 5-30 min (scales with dump size; the dominant term)
- Volume swap + production container recreate: 10-15 min
- Smoke verification: 10-15 min
**Total: 30-90 min in the median case, well under 2h.**

**RPO — recovery point objective: 24 hours.**
Daily cadence means the worst-case data loss is 24h of QuillMD activity
(visits created since the last successful 03:00 UTC backup). Tightening
this to <24h would require either (a) more frequent backups or
(b) Postgres point-in-time recovery via wal-g / pgBackRest. Both are
out of scope for the pilot tier; revisit at user-count-driven inflection
(documented as a Phase 7 follow-up).

## BAA snippet

Backblaze B2 offers HIPAA Business Associate Agreements at the **B2
Business** tier and above. Process:

1. Email `compliance@backblaze.com` from the deployment-owner account
   that holds the B2 bucket.
2. Reference: account ID, bucket name (`meddoc-offsite-backups-prod`),
   intended use (HIPAA-bound encrypted PHI backup).
3. Wait for the countersigned BAA. **Do not populate live B2 credentials
   in `/opt/meddoc-pro/.env` before the BAA lands** — uploading PHI to a
   non-BAA-covered B2 bucket is itself a HIPAA breach even with
   client-side age encryption (HIPAA covers PHI in transit and at rest
   regardless of crypto, because the BAA is what makes B2 a permitted
   business associate).
4. File the countersigned BAA in the compliance binder. Audit reviewers
   will ask for the date.

Detailed BAA + key-population steps live in
`docs/RUNBOOK_OFFSITE_BACKUP.md` § A.1.

## Disaster scenarios

### Scenario 1: VPS lost or corrupted

Most common case (Hetzner outage, accidental `rm -rf`, ransomware on the
host). Recovery path:

1. Provision a new VPS with the same Docker stack from `infra/` +
   `docker-compose.yml`.
2. Pull the latest encrypted blobs from B2 (Postgres + MinIO).
3. Decrypt with the offline private key on a workstation, restore via
   `restore-drill.sh` shape (or the runbook §C steps for the production
   restore — `restore-drill.sh` is the read-only validation, not the
   production restore tool).
4. Bring the new VPS up, point Caddy / DNS at it.

**RTO ~2h** for a clean disaster; **RPO ~24h** (worst case the most
recent backup is from yesterday's 03:00 UTC).

### Scenario 2: B2 account compromised

Attacker steals the B2 application key + bucket credentials but does NOT
have the offline private key. They can:
- Delete blobs (mitigated by B2 bucket-level lifecycle: 30-day version
  retention; Kasra can reach out to Backblaze support to recover within
  the version window).
- Read encrypted blobs (useless — age decryption needs the private key).

Recovery path:
1. Rotate the B2 application key + push the new credentials to
   `/opt/meddoc-pro/.env` (operator).
2. If blobs were deleted: restore from the B2 version-history window OR
   re-upload from the previous trusted local dump in
   `/opt/meddoc-pro/backups/`.
3. Audit-log the incident.

**The encrypted blob design means a B2 account compromise alone does
not constitute a HIPAA breach** — the data the attacker exfiltrates is
ciphertext.

### Scenario 3: Private key lost

**ALL ENCRYPTED BACKUPS BECOME UNRECOVERABLE.** This is the single
worst failure mode of the entire backup story.

Mitigations the operator MUST take:
- **Multi-locate the private key.** Minimum two copies:
  - 1Password Vault (or equivalent password-manager Vault with
    encrypted sync + backup history).
  - Paper printout in a fireproof / waterproof safe at a physical
    location separate from the deployment-owner's home/office.
- Optionally a third copy on an encrypted USB drive in a safety
  deposit box.
- **Test the offline copies quarterly** by running `restore-drill.sh`
  with the key from each storage location in turn.
- **Never** copy the private key to the VPS, a CI runner, a Slack
  attachment, an email, or a code repo. The crypto is only as strong
  as the weakest place the key has ever lived.

If the key is lost despite these mitigations, the encrypted blobs are
forensically interesting (proof of exfiltration resistance) but
operationally worthless. The only paths forward at that point are
LOCAL `/opt/meddoc-pro/backups/` (pre-encryption gzipped dumps from
the postgres-backup sidecar — only useful if the VPS itself is also
intact, which usually means you didn't need the offsite copy in the
first place) or accepting data loss.

This is bolded for emphasis: **lose the private key, lose the
backups.**

### Scenario 4: Both VPS lost AND private key lost

Total loss. Document the incident, notify users per HIPAA breach
notification rules (60-day window), file with HHS Office for Civil
Rights if PHI for 500+ individuals was affected.

This scenario is the entire reason the strategy doc exists — make it
extremely difficult to land in this state through procedural rigor
about key custody.

---

## Activation status

This document ships the **strategy**. Activation in production is a
manual operator sequence tracked in `docs/POST_MERGE_TODO.md` §22.
At time of writing:

| Component | Status |
|---|---|
| Postgres offsite backup (h16) | ✅ Code shipped + cron live; populated env vars + signed BAA → operator confirmation pending. |
| MinIO offsite backup (Phase 6.2) | ✅ Code shipped (this PR) → cron install pending. |
| `restore-drill.sh` validation | ✅ Code shipped (this PR) → first-run validation pending before declaring Phase 6.2 active. |
