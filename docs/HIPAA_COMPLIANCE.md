# HIPAA Compliance Matrix

*Living tracker for the HIPAA Security Rule findings raised in the
Phase 3 audit. One row per finding; status changes go in this file
along with the linked runbook. Reviewed at every release.*

Status legend:

| Status                                  | Meaning                                                                                                                  |
| ---                                     | ---                                                                                                                      |
| `Mitigated`                             | Control is in place AND verified in production.                                                                          |
| `Mitigated (pending operator migration)`| Code/infra change is shipped; production cutover requires a maintenance window run by the operator per the linked runbook. |
| `Mitigated (pending operator credential population + BAA)` | Code/infra change is shipped; production activation requires the operator to sign the third-party BAA, populate credentials, and run the verification drill per the linked runbook. |
| `In progress`                           | Active work, not yet shipped.                                                                                            |
| `Open`                                  | Acknowledged, not yet started.                                                                                           |
| `Accepted risk`                         | Documented decision not to mitigate; rationale linked.                                                                   |

---

## Findings matrix

| ID  | HIPAA citation                              | Finding                                                                                                                                       | Status                                                              | Evidence / runbook                                                                                                                                                                                |
| --- | ---                                         | ---                                                                                                                                           | ---                                                                 | ---                                                                                                                                                                                              |
| h8  | §164.312(a)(2)(iv) — Encryption & decryption | Postgres data volume on the Zap Hosting VPS is not encrypted at rest.                                                                         | **Mitigated** (verified in production 2026-06-10)                   | Verified 2026-06-10: postgres data dir is a LUKS `dm-crypt` device — `/dev/mapper/pg-encrypted` mounted at `/mnt/pgdata-encrypted` (live `docker-compose.yml` postgres bind mount), container healthy. Code: `infra/setup-encrypted-volume.sh`, `docker-compose.yml`. Runbook: [docs/RUNBOOK_ENCRYPTED_VOLUME.md](RUNBOOK_ENCRYPTED_VOLUME.md). **Operator to reconcile:** the §h8 detail below + the `docker-compose.yml` comment still describe the pre-deploy design paths (`/var/lib/meddoc-postgres-encrypted.img`, `/etc/meddoc/postgres-volume.key`) vs the deployed `/mnt/pgdata-encrypted`; key-escrow/rotation per runbook still apply (root-owned, not agent-verifiable). |
| h16 | §164.308(a)(7)(ii)(A) — Data backup plan    | Backups are co-located with the live database. Loss of the VPS = loss of both. Geographically-distinct, encrypted offsite copy required. Also touches §164.308(a)(7)(ii)(B) (DR plan). | **Mitigated (pending operator credential population + BAA)**       | Code: `infra/backup-offsite-sync.sh`, `docker-compose.yml` (postgres-backup env block + bind mounts), `.env.example`. Runbook: [docs/RUNBOOK_OFFSITE_BACKUP.md](RUNBOOK_OFFSITE_BACKUP.md). |

Additional rows from other Phase 3 findings will be appended here as
each branch lands.

---

## h8 — Encryption at rest for postgres

**Approach.** LUKS-on-loop-file (`cryptsetup luksFormat`), self-managed
key custody. The earlier Hetzner-managed-volume design in
`docs/H3_ENCRYPTED_VOLUME_PROCEDURE.md` is **superseded** —
production deployment is on Zap Hosting, which does not expose
Hetzner-style managed volumes.

**Deployed reality (verified 2026-06-10).** The migration is **complete and
live** — postgres runs on the encrypted volume in production. Verified from
the host: the postgres data dir is a LUKS `dm-crypt` device
`/dev/mapper/pg-encrypted` mounted at `/mnt/pgdata-encrypted` (ext4), which
the `postgres` service bind-mounts at `docker-compose.yml` (`- /mnt/pgdata-encrypted:/var/lib/postgresql/data`); the container is healthy on it.
This **replaces** the pre-deploy design paths this section originally
described (`/var/lib/meddoc-postgres-encrypted.img` / a `…-postgres-data`
bind target / a sparse 50 GB image — the deployed dm-crypt device is ~1 GB).
The "Cryptographic posture" specifics below (exact key-file path
`/etc/meddoc/postgres-volume.key`, cipher params, the boot-remount
`meddoc-postgres-volume.service`) describe the intended design per
[RUNBOOK_ENCRYPTED_VOLUME.md](RUNBOOK_ENCRYPTED_VOLUME.md); they are
root-owned and were **not** re-verified in this docs pass.

**Operator residual (Kasra).** Per `RUNBOOK_ENCRYPTED_VOLUME.md`: confirm the
LUKS key-escrow + rotation procedure and that the on-disk key-custody path +
boot-remount unit match the deployed `/dev/mapper/pg-encrypted` setup. This
is the only remaining h8 sub-item; the encryption-at-rest control itself is
verified live (above).

**Cryptographic posture.**

- LUKS2 with `aes-xts-plain64`, 512-bit key, sha256, argon2id PBKDF.
- 4 KB random key file at `/etc/meddoc/postgres-volume.key`, mode
  `0400`, owned `root:root`.
- Re-mounted on boot by `meddoc-postgres-volume.service`, ordered
  `Before=docker.service` so the postgres bind mount has its data
  dir ready before the container starts.

**What "encryption at rest" actually buys you here.**

- Mitigates: physical disk theft from the datacenter, careless
  decommission of the underlying block storage, accidental disk
  imaging by the hosting provider's staff (within the limits of
  Zap's BAA).
- Does NOT mitigate: a compromised host root account (key file is
  readable as root), a compromised running postgres container
  (data is plaintext through the bind mount inside the container),
  or memory-resident PHI (covered separately by transport encryption
  + `cap_drop: ALL` + non-root containers — Phase 3 h4/h16-cap-drop).

**Operational responsibilities.**

1. The key file MUST be escrowed off-host (encrypted with the team's
   GPG key, uploaded to the secrets vault) at provisioning time.
   Loss of the key file = unrecoverable encrypted volume.
2. The key file is rotated per the schedule below.
3. Migration date and every rotation are logged in the HIPAA audit
   trail (see runbook §6 for the entry format).

---

## h16 — Offsite encrypted backup

**Approach.** After every `pg_dump` produced by the existing
`postgres-backup` sidecar, a post-hook script
(`infra/backup-offsite-sync.sh`) **age-encrypts** the dump using a
public key whose private counterpart is held by the operator
off-host, then uploads the encrypted blob to a Backblaze B2 bucket
under a HIPAA BAA. Retains 30 days of offsite blobs; the live local
backups remain unchanged.

**Why Backblaze B2.** Cheapest HIPAA-eligible S3-compatible object
store with a published BAA process (~$6/TB/month at the time of
writing). Buying offsite is a pure docs/operator gate — the code is
provider-agnostic via the standard `b2` CLI; swapping providers is a
runbook change, not a code change.

**Why age (not GPG).** Single-recipient encryption with a fixed
public key, no agent, no keyring, simple to audit. Private key never
touches the VPS — it lives on an offline workstation in the
operator's secrets store.

**What "offsite encrypted backup" actually buys you here.**

- Mitigates: total VPS loss (datacenter fire, account compromise,
  ransomware on the host filesystem). Restoration requires only the
  age private key + the latest B2 blob.
- Does NOT mitigate: data integrity bugs that produce a corrupt
  pg_dump (the offsite is a faithful copy of whatever the live
  backup is — verify pg_restore drills quarterly).

**Operational responsibilities.**

1. Sign the BAA with Backblaze and file the countersigned copy in
   the corporate compliance vault.
2. Generate and **off-host archive** the age private key. The public
   key (`/etc/meddoc/offsite-backup-public.age`) lives on the VPS;
   the private key MUST NOT.
3. Verify the encrypted blob hash + a successful end-to-end restore
   drill on a non-prod host within 14 days of going live, and then
   quarterly.
4. Rotate the age keypair every 12 months. Old encrypted blobs
   remain decryptable with the historical private key — keep an
   offline archive.

The code does NOT contain real B2 credentials. They live only in
`.env` on the VPS, sourced into the `postgres-backup` container
environment.

---

## Cross-reference

The companion **unencrypted** offsite-backup procedure
(`docs/H16_OFFSITE_BACKUP_PROCEDURE.md`, Hetzner Object Storage via `mc
mirror`) remains in the repo and is independent of this work. For
HIPAA-bound deployments, **prefer the encrypted-with-BAA path documented
above**. The unencrypted Hetzner mirror is fine for non-PHI operational
redundancy or as a second offsite copy after the encrypted one is
running.

---

## Key Rotation Policy

**Rotate the LUKS key (h8):**

- **Every 12 months**, on a fixed calendar reminder.
- **Immediately** after any privileged-staff turnover — anyone who
  had root on the host, or access to the secrets vault that holds
  the escrowed key.
- **Immediately** if there is any suspicion the key file was
  copied off-host without authorization.

**Mechanism: LUKS2 supports up to 32 key slots. Always add the new
key to a free slot, verify it opens the device, and only then kill
the old slot — never leave the volume protected by zero keys.**

```bash
# 1. Generate the new 4 KB key file with strict perms.
sudo install -m 0400 /dev/null /etc/meddoc/postgres-volume.key.new
sudo dd if=/dev/urandom of=/etc/meddoc/postgres-volume.key.new \
  bs=4096 count=1 status=none

# 2. Add it to a free slot (the existing key authorizes the addition).
sudo cryptsetup luksAddKey \
  --key-file /etc/meddoc/postgres-volume.key \
  /var/lib/meddoc-postgres-encrypted.img \
  /etc/meddoc/postgres-volume.key.new

# 3. Verify the new key actually opens the device.
sudo cryptsetup luksOpen --test-passphrase \
  --key-file /etc/meddoc/postgres-volume.key.new \
  /var/lib/meddoc-postgres-encrypted.img \
  && echo "new key OK"

# 4. Find which slot the OLD key occupies.
sudo cryptsetup luksDump /var/lib/meddoc-postgres-encrypted.img \
  | grep -E 'Keyslot|^[[:space:]]+[0-9]+:'

# 5. Kill the OLD slot, authorizing with the NEW key. Replace <N>
#    with the slot number from step 4 (typically 0 for first rotation).
sudo cryptsetup luksKillSlot \
  --key-file /etc/meddoc/postgres-volume.key.new \
  /var/lib/meddoc-postgres-encrypted.img <N>

# 6. Promote the new key file to the canonical path, escrow it
#    off-host, then shred the old copy.
sudo mv /etc/meddoc/postgres-volume.key /etc/meddoc/postgres-volume.key.OLD
sudo mv /etc/meddoc/postgres-volume.key.new /etc/meddoc/postgres-volume.key
# (escrow step here — see runbook §2.3)
sudo shred -u /etc/meddoc/postgres-volume.key.OLD

# 7. Log the rotation in the HIPAA audit trail.
echo "$(date -u +%FT%TZ), h8-encrypt-at-rest, ROTATE, operator=<you>, sha256(key)=$(sudo sha256sum /etc/meddoc/postgres-volume.key | cut -d' ' -f1), slot_killed=<N>" \
  | sudo tee -a /var/log/meddoc/hipaa-audit.log
```

The full procedure with rollback notes lives in
[docs/RUNBOOK_ENCRYPTED_VOLUME.md §5](RUNBOOK_ENCRYPTED_VOLUME.md#5-key-rotation).

**Rotate the age keypair (h16):** see
[docs/RUNBOOK_OFFSITE_BACKUP.md §D](RUNBOOK_OFFSITE_BACKUP.md). Old
encrypted blobs remain decryptable with the historical private key —
the operator MUST keep an offline archive of every key version.
