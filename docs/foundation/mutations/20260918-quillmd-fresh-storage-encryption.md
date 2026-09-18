# Private fresh-storage encryption and billing boundary — 2026-09-18

Verified 2026-09-17/18: the fresh QuillMD database volume (docker named volume
`quillmd_fresh_pg` under `/var/lib/docker/volumes`), the state directory
`/var/lib/quillmd` (originals, exports, provider receipts, mail outbox, proofs),
the services' temporary files under their private `/tmp`, the database
container's json log (it held logged statement text) and the host swap file all
live on the plain ext4 root filesystem of a virtual disk (`/dev/sda2`) with no
documented provider encryption. The two LUKS volumes on the host belong to the
retired stack. This act corrects the parts that are QuillMD's to correct and
names the parts that are not.

## The tree this act ships

The act fast-forwards permanent main from the running release `19d46ad3` to the
cited target and restarts the private services on it. The target contains three
changes, and this declaration covers all of them:

1. documentation merged since the running release (PR #1191);
2. the billing boundary: `jobs.cancel` and the `job_cancel` route (a queued
   request cancels free, before any provider request), the additional-generation
   disclosures, `not_adopted:` / `platform_failure:` failure classes, the refusal
   to absorb a `not_adopted:` row and the matching `audit_billing` check. No
   schema change (`makemigrations --check`: no changes). No existing row carries
   either prefix, so the billing audit's verdict on existing rows is unchanged;
3. the storage change below.

## Expected delta, declared before the act

Created on the host:

- `/var/lib/quillmd-encrypted/` (root, 0700) holding a sparse 16 GiB LUKS2 loop
  file `quillmd-fresh.luks`: aes-xts-plain64, 512-bit key, sha256, argon2id;
- slot 0: a random 64-byte key file `/etc/quillmd/quillmd-fresh-luks.key`
  (root, 0400), used for unattended boot;
- slot 1: a generated recovery passphrase
  `/etc/quillmd/quillmd-fresh-luks.recovery-passphrase` (root, 0400, no trailing
  newline), proven to open when typed, and a wrong passphrase proven refused;
- an ext4 filesystem mounted `nodev,nosuid` at `/mnt/quillmd-fresh-encrypted`
  with roots `postgres/`, `state/` (including `tmp/`, owner `quillmd-app`,
  0700), `archive/` and a marker file;
- `/usr/local/bin/quillmd-fresh-volume` and the units
  `quillmd-fresh-volume.service` (opens and bind-mounts; deliberately not
  ordered before docker, so a failed unlock never delays a co-tenant) and
  `quillmd-fresh-database.service` (`BindsTo` the volume, starts the existing
  container, waits for readiness).

Changed:

- the three application units require the database unit, set
  `TMPDIR=/var/lib/quillmd/tmp`, `LimitCORE=0` and `MemorySwapMax=0`;
- the container `quillmd-fresh-postgres` keeps its id, image, port and named
  volume declaration; its restart policy changes from unless-stopped to no so
  only the database unit starts it, and its memory-plus-swap limit drops from
  768 MiB to its 384 MiB memory limit, so it cannot swap;
- `ALTER SYSTEM` sets `log_min_messages = fatal` and
  `log_min_error_statement = panic`, so statement text no longer reaches the
  container log; the existing log is archived to the encrypted volume after main
  advances and the plaintext log is truncated;
- the storage identity pin moves from version 1 (device and inode) to version 2
  (inodes, with the device read from `/dev/mapper/quillmd-fresh-encrypted` at
  check time); the version-1 pin is kept beside it;
- permanent main fast-forwards to the target and only the release line of the
  protected environment changes.

Moved, never deleted: the plaintext originals go to
`/var/lib/quillmd-rollback-20260918` (root, 0700). Both former locations become
empty, root-owned, immutable directories.

Must not change: every PostgreSQL row fingerprint, the schema, constraints and
indexes; every private file and mail item; the Word runtime; retained reports;
the six protected shared containers; public statuses. Zero provider calls, zero
migration commands.

## Drill declared as part of the act

After the application serves from the encrypted volume, the volume unit is
stopped. The database and application units must stop with it, both bind
targets must be empty and immutable, a plaintext write probe must be refused,
and a manual container start must write nothing into the closed database
directory. Then the volume, database and application units start again, and
rows, files, identity proofs and health are verified a second time.

## Preconditions and failure handling

Before this act: exact merge CI on the target, the read-only preflight from
permanent main, and a validated encrypted backup whose isolated restore check
reports `decrypted_files_written = 0` and covers the current row count. The act
runs once through `run-ruled-mutation.sh` with this committed declaration.

- Any failure before main advances reverts automatically: the untouched
  originals return, baseline units are restored, the container's restart policy
  and memory limits are restored, the version-1 pin returns and the application
  restarts on the running release. `discard-failed-attempt` then removes the
  partial image, key and mount point.
- Any failure after main advances stops the application services. `rollback`
  (with `--from-result`, under this same declaration) copies the current data
  back to plaintext, restores plaintext units and keeps the encrypted image, key
  and pre-migration snapshot for inspection.
- Never rerun blindly; the lock and evidence stay until inspected.

## Key custody and what this act does not establish

While the slot-0 key file is on this host, anyone with a full copy of the
virtual disk or root on the running host can open the volume. What the act does
establish: new database, WAL, file, mail, proof and temporary writes no longer
reach the plain root filesystem; the whole volume becomes cryptographically
erasable by destroying two small key artifacts; and full at-rest protection
becomes one owner decision, which is to remove the key file from the host and
unlock with the recovery passphrase after each boot.

Not established: encryption of the host swap file, journald or the shared root
filesystem (host-level); overwriting of freed plaintext blocks on the virtual
disk; temporary files written to hard-coded paths rather than through `TMPDIR`;
off-host custody of the recovery passphrase (owner action). The rollback
snapshot holds a plaintext copy until the owner accepts the migration and
approves its destruction. No claim about Stripe, Resend, offsite restoration,
invoice reconciliation or independent testing follows from this act.
