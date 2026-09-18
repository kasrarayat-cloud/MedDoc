# Fresh-application storage encryption

Updated 2026-09-18. This page records what backs each class of QuillMD data,
what the encrypted volume protects, how it unlocks, who holds the keys, how to
roll back, and what remains outside QuillMD's control.

## Storage trace (verified 2026-09-17/18)

| Data | Location | Backing before | Backing after this change |
| --- | --- | --- | --- |
| PostgreSQL data + WAL (`quillmd_fresh`) | docker named volume `quillmd_fresh_pg` → `/var/lib/docker/volumes/quillmd_fresh_pg/_data` | `/dev/sda2` ext4 (plain) | bind of `/mnt/quillmd-fresh-encrypted/postgres` (LUKS2) |
| Originals, exports, provider receipts, mail outbox, proofs | `/var/lib/quillmd/{files,mail,proofs}` | `/dev/sda2` ext4 (plain) | bind of `/mnt/quillmd-fresh-encrypted/state` (LUKS2) |
| Parser and SDK temporary workspaces | services' private `/tmp` | `/dev/sda2` ext4 (plain) | `TMPDIR=/var/lib/quillmd/tmp` on the encrypted state |
| Encrypted backups | `rebuild/.runtime/new-system-backups` | Fernet ciphertext on `/dev/sda2` | unchanged (ciphertext; key in `rebuild/.runtime/backup-secrets`) |
| Private evidence and reports | `rebuild/.runtime` | `/dev/sda2` ext4 (plain), synthetic data only | unchanged |
| Host swap | `/swap.img` (4 GiB, in use) | `/dev/sda2` ext4 (plain) | **unchanged — host-level, outside scope** |
| journald | `/var/log/journal` | `/dev/sda2` ext4 (plain); application logs omit payloads | unchanged |

The virtual disk (`QEMU HARDDISK`, `/dev/sda`) carries a single ext4 root
partition. No LUKS, dm-crypt or documented provider-side encryption exists for
it; ext4 alone establishes nothing. The two LUKS loop volumes on the host
(`pg-encrypted`, `minio-encrypted`) hold only the retired stack's data.
Reference: Red Hat, *Encrypting block devices using LUKS*.

## Design

- A sparse 16 GiB loop file `/opt/meddoc-pro/secrets/quillmd-fresh.luks` holds a
  LUKS2 container; its ext4 filesystem has the roots `postgres/`, `state/` and a
  marker file `.quillmd-fresh-volume`.
- `quillmd-fresh-volume.service` (`Before=docker.service`) runs
  `/usr/local/bin/quillmd-fresh-volume open`: opens the mapper with the key
  file, mounts the filesystem, verifies the marker, then bind-mounts
  `postgres/` over the docker volume directory and `state/` over
  `/var/lib/quillmd`. The database container therefore keeps its identity and
  the application keeps its paths.
- `quillmd-fresh-database.service` (`BindsTo` the volume unit) verifies the
  binds and starts the existing `quillmd-fresh-postgres` container, whose
  restart policy is `no` so nothing else starts it.
- The three application units `Requires=quillmd-fresh-database.service`.
- When the volume is closed, both bind targets are empty, root-owned,
  **immutable** (`chattr +i`) directories: a container or service started
  without the volume cannot initialise or write plaintext there, and the
  storage helper's device/inode pin (`rebuild/.runtime/state-identity.json`)
  refuses the wrong filesystem.

## Unlock, restart and custody

- Boot: systemd starts the volume unit before docker; docker starts; the
  database unit starts the container; the application units follow. The
  post-reboot proof (`scripts/verify-post-reboot.sh`) asserts the whole chain.
- Manual: `systemctl start quillmd-fresh-volume.service`, then
  `quillmd-fresh-database.service`, then the three application units; stop in
  reverse. Root operations on this host go through the documented docker
  helper (the operator has no sudo).
- Key custody: slot 0 = `/etc/quillmd/quillmd-fresh-luks.key` (root, 0400,
  random 64 bytes) — required for unattended boot; slot 1 = generated recovery
  passphrase at `/etc/quillmd/quillmd-fresh-luks.recovery-passphrase` (root,
  0400). **Owner action:** move the passphrase into the owner-controlled vault
  and then have it shredded from the host; record the custodian. While both
  live on the host, the volume protects against reuse or exposure of the disk
  image and backups without `/etc` access, not against a root compromise of
  the running host.
- Rotation: `cryptsetup luksChangeKey` on the image with a new key file, then
  replace the file atomically; document the date in the checkpoint.

## Rollback

`scripts/migrate-fresh-storage.py --rollback` (declared) stops the
application, database and volume units, restores the plaintext copies from
`/var/lib/quillmd-rollback-20260918`, restores the baseline units, re-enables
the container's restart policy and restarts everything. The encrypted image,
key and passphrase stay for inspection. Rollback material must not be deleted
until the owner accepts the migration; it holds a plaintext copy of the data.

## Limits and remaining dependencies

- Host swap, journald and the shared root filesystem are host-level; encrypting
  them requires host changes outside QuillMD's scope (owner/provider decision).
- Off-host key escrow and the provider's own disk-encryption statement are
  owner actions; without them, at-rest protection is partial and is recorded as
  such in `patient-data-release-requirements.md`.
- Backups remain on the same VPS until the offsite destination is approved.
