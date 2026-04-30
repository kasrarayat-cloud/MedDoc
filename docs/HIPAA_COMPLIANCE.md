# HIPAA Compliance Matrix

*Living tracker for the HIPAA Security Rule findings raised in the
Phase 3 audit. One row per finding; status changes go in this file
along with the linked runbook. Reviewed at every release.*

Status legend:

| Status                                  | Meaning                                                                                                                  |
| ---                                     | ---                                                                                                                      |
| `Mitigated`                             | Control is in place AND verified in production.                                                                          |
| `Mitigated (pending operator migration)`| Code/infra change is shipped; production cutover requires a maintenance window run by the operator per the linked runbook. |
| `In progress`                           | Active work, not yet shipped.                                                                                            |
| `Open`                                  | Acknowledged, not yet started.                                                                                           |
| `Accepted risk`                         | Documented decision not to mitigate; rationale linked.                                                                   |

---

## Findings matrix

| ID  | HIPAA citation                              | Finding                                                                 | Status                                       | Evidence / runbook                                                                              |
| --- | ---                                         | ---                                                                     | ---                                          | ---                                                                                             |
| h8  | §164.312(a)(2)(iv) — Encryption & decryption | Postgres data volume on the Zap Hosting VPS is not encrypted at rest. | **Mitigated (pending operator migration)** | Code: `infra/setup-encrypted-volume.sh`, `docker-compose.yml` (postgres bind mount). Runbook: [docs/RUNBOOK_ENCRYPTED_VOLUME.md](RUNBOOK_ENCRYPTED_VOLUME.md). |
| h16 | §164.308(a)(7)(ii)(A) — Data backup plan    | *(populated by sibling branch `feature/phase3-hipaa-h16-offsite-backup` — placeholder row, lead agent merges.)*   | *(see sibling branch)*                       | *(placeholder)*                                                                                 |

Additional rows from other Phase 3 findings will be appended here as
each branch lands.

---

## h8 — Encryption at rest for postgres

**Approach.** LUKS-on-loop-file (`cryptsetup luksFormat` over a sparse
50 GB image at `/var/lib/meddoc-postgres-encrypted.img`), self-managed
key custody. The earlier Hetzner-managed-volume design in
`docs/H3_ENCRYPTED_VOLUME_PROCEDURE.md` is **superseded** —
production deployment is on Zap Hosting, which does not expose
Hetzner-style managed volumes.

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

## Key Rotation Policy

**Rotate the LUKS key:**

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
