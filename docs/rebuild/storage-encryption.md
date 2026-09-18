# Fresh-application storage encryption

Updated 2026-09-18. What backs each class of QuillMD data, what the encrypted
volume protects, how it unlocks, who holds the keys, how to roll back, and what
remains outside QuillMD's control. The declared act is
`docs/foundation/mutations/20260918-quillmd-fresh-storage-encryption.md`.

## Applied 2026-09-18

The declared act ran twice from `/opt/meddoc-pro`.

- **Attempt 1** (target `69f39be4`) stopped at its first host step. A module was imported after the change of root. The automatic revert restored the running release with every row identical in 17 seconds, and nothing had been created.
- **Attempt 2** (target `3eac783a`) completed between 04:58:28Z and 04:59:57Z and was judged against all 29 declared quantities. Permanent main and the three services now run `3eac783a`, synthetic-only.

Independent checks after the act:

- `findmnt` shows `/var/lib/quillmd` and the database directory on `/dev/mapper/quillmd-fresh-encrypted`, mounted `nosuid,nodev`.
- The billing audit passes, reading files through the version-2 identity pin.
- A post-act encrypted backup restores with no decrypted files written: 35 tables, 75,457 rows and 28 files, identical to the pre-act backup.
- The administrator console check passes.

Not exercised live:

- a reboot, because this is a shared host (`scripts/verify-post-reboot.sh` checks the boot order next time);
- the keyless unlock with a typed passphrase, which needs the owner (slot 1 was proven with a typed passphrase at format time).

Private evidence: `rebuild/.runtime/CHECKPOINT-LATEST.md`.

## Storage trace (verified 2026-09-17/18)

| Data | Location | Before | After the act |
| --- | --- | --- | --- |
| PostgreSQL data and WAL | named volume `quillmd_fresh_pg`, `/var/lib/docker/volumes/quillmd_fresh_pg/_data` | `/dev/sda2` ext4, plain | bind of `/mnt/quillmd-fresh-encrypted/postgres` (LUKS2) |
| Originals, exports, receipts, mail outbox, proofs | `/var/lib/quillmd/{files,mail,proofs}` | `/dev/sda2` ext4, plain | bind of `/mnt/quillmd-fresh-encrypted/state` (LUKS2) |
| Temporary files created through Python `tempfile` | services' private `/tmp` | `/dev/sda2` ext4, plain | `/var/lib/quillmd/tmp` on the encrypted state; the launcher refuses to start otherwise |
| Database container log | `/var/lib/docker/containers/<id>/<id>-json.log` | plain; held logged statement text | archived to the encrypted volume, truncated; statement logging suppressed |
| Restore checks | `rebuild/.runtime/restore-checks/` | wrote decrypted file copies | decrypt and verify in memory; restore database on tmpfs with swap disabled |
| Encrypted backups | `rebuild/.runtime/new-system-backups` | ciphertext on `/dev/sda2`; the dump passed through a temporary file in `/tmp` | ciphertext; the dump is captured and encrypted in memory |
| Host swap `/swap.img` | `/dev/sda2` | plain, in use | unchanged, host-level; QuillMD services and the database container are barred from swap |
| journald | `/var/log/journal` | plain | unchanged, host-level |

The virtual disk (`QEMU HARDDISK`, `/dev/sda`) has one ext4 root partition with
no LUKS, dm-crypt or documented provider-side encryption. The two LUKS loop
volumes on the host (`pg-encrypted`, `minio-encrypted`) hold only the retired
stack's data and are not touched.

## Design

- A sparse 16 GiB loop file `/var/lib/quillmd-encrypted/quillmd-fresh.luks`
  (directory root-only) holds a LUKS2 container. Its ext4 filesystem carries
  `postgres/`, `state/`, `archive/` and a marker file.
- `quillmd-fresh-volume.service` runs `quillmd-fresh-volume open`: open the
  mapper with the key file, mount, verify the marker, then bind `postgres/`
  over the docker volume directory and `state/` over `/var/lib/quillmd`. The
  container keeps its identity and the application keeps its paths. The unit is
  not ordered before docker, so a slow or failed unlock never delays another
  tenant.
- `quillmd-fresh-database.service` binds to the volume unit, checks the binds,
  starts the existing container (restart policy `no`) and waits for readiness.
  The three application units require it.
- Closed volume: both bind targets are empty, root-owned, immutable
  directories. A service or container started without the volume cannot write
  plaintext there, and the storage identity pin (version 2) refuses to run
  because the mapper device is absent.

## Unlock, restart and custody

| Situation | What happens | Operator action |
| --- | --- | --- |
| Boot with the key file present | volume, database and application units start unattended | none; confirm with `bash scripts/verify-post-reboot.sh` |
| Boot without the key file | volume stays closed; database and application stay down | `bash scripts/ops/unlock-fresh-volume.sh`, type the recovery passphrase |
| Planned restart | stop the application units, then the database unit, then the volume unit; start in reverse | root through the documented docker helper (no sudo on this host) |

- **Slot 0**: `/etc/quillmd/quillmd-fresh-luks.key`, 64 random bytes, root 0400,
  needed for unattended boot.
- **Slot 1**: recovery passphrase, generated at
  `/etc/quillmd/quillmd-fresh-luks.recovery-passphrase`, root 0400. The owner
  copies it into the owner-controlled vault and records the custodian. After
  that the host copy is shredded.
- **Protection level.** While the key file is on the host, anyone with a full
  disk copy or root on the running host can open the volume. Deleting the key
  file is not enough to change that. Slot 0 stays valid, and the key file's
  blocks may survive on the virtual disk. Protection against disk-level access
  needs three steps in one maintenance window, after the passphrase is vaulted:
  1. remove slot 0 (`cryptsetup luksKillSlot <image> 0`);
  2. re-encrypt the volume (`cryptsetup reencrypt`), so that a recovered key
     file together with an older header copy opens nothing;
  3. remove the key file.
  Every boot then needs the unlock script and the passphrase, so the service is
  down until someone types it.
- **Crypto-erase.** `cryptsetup luksErase` on the image destroys every key slot
  in the header, so no key or passphrase opens the volume again. Shredding the
  key file alone is best effort on a virtual disk. Neither step protects against
  anyone who already copied the key material together with the header.
- **Rotation.** Adding a key slot and removing the old one changes how the volume
  key is wrapped, not the volume key itself. That is enough when a passphrase
  holder changes. If the key file or a header copy may have been exposed, the
  volume must be re-encrypted (`cryptsetup reencrypt`) in a maintenance window.
  Record the date in the checkpoint.

## Rollback

- Before main advances, any failure reverts automatically to the untouched
  plaintext originals and the running release. Then run
  `discard-failed-attempt` under the same declaration.
- If the run was killed outright before main advanced, run
  `revert-interrupted --from-result <result>-progress.json` first. It finishes
  the revert from any partial state. It refuses while the interrupted process
  or one of its root steps is still running. Ctrl-C at the runner does not stop
  the act, so wait for its result file first.
- After main advances, run `rollback --from-result <migrate result>` under the
  same declaration. It copies the current data back to plaintext, restores
  plaintext units, re-enables the container restart policy and keeps the image,
  key and pre-migration snapshot.
- `/var/lib/quillmd-rollback-20260918` holds a plaintext copy of the data as it
  was before the act. It stays until the owner accepts the migration and
  approves its destruction. It must be shredded before any real patient data
  is admitted.

## Limits and remaining dependencies

- Host swap, journald and the shared root filesystem are host-level. Encrypting
  them is a host or provider decision outside QuillMD's scope.
- Freed plaintext blocks on the virtual disk are not overwritten. The data they
  held is synthetic.
- The image is sparse, so its allocation map shows which regions have ever been
  written. That reveals volume and growth, not content. Its space is not reserved
  in advance: the migration requires 24 GiB free, and disk usage stays on the
  owner's host checklist.
- Plaintext copies of QuillMD data remain on the root disk and must be
  destroyed before any real patient data is admitted. All of them are
  synthetic.
  - `/var/lib/quillmd-rollback-20260918`, the pre-migration snapshot.
  - `rebuild/.runtime/files` (27 originals, exports, receipts and audio files)
    and `rebuild/.runtime/mail` (2 items), the application state from before the
    2026-09-17 service-identity cutover.
  - `rebuild/.runtime/restore-checks/restore-*/files`, decrypted copies written
    by earlier restore checks.
- After a rollback, `scripts/verify-post-reboot.sh` still expects the encrypted
  layout and reports failure. That report is correct: the data is plaintext
  again.
- Backups stay on this VPS until the offsite destination is approved.
