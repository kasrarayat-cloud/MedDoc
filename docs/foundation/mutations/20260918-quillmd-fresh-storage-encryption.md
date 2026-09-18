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
2. the billing boundary (PR #1192): `jobs.cancel` and the `job_cancel` route (a
   queued request cancels free, before any provider request); the
   additional-request disclosures; the `not_adopted:` / `platform_failure:`
   failure classes, with output validity checked before the user-state checks;
   `Not processed` failures before any provider request, which release the hold;
   provider output delivered only for requests that stand charged; failed jobs
   freeing their request key for a retry; `cancel`, `settle` and
   `absorb_failed_job` locking only the job row; and the matching
   `audit_billing` checks, including cancelled jobs. No schema change
   (`makemigrations --check`: no changes). Measured before the act, the live
   database holds 12 jobs, all `succeeded`, none carrying either prefix. The
   billing audit's verdict on existing rows is therefore unchanged, and every
   stored result stays downloadable;
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
indexes; every private file and mail item (the service proofs in `proofs/` are
rewritten by each service start, as on every restart); the Word runtime; the
reports retained before the act (reports other sessions add meanwhile are
allowed);
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

Before this act, three things hold:

- exact merge CI on the target;
- the read-only preflight from permanent main;
- a validated encrypted backup taken with the target's backup tool, which encrypts
  the dump in memory. Its isolated restore check reports
  `decrypted_files_written = 0` and covers the current row count.

The act runs once through `run-ruled-mutation.sh` with this committed
declaration and `RULED_ACT_MAX_SECS=10800`. A normal run takes minutes. Every
command the act issues itself has a timeout of at most 15 minutes, and phase one
checks a 30-minute budget at each stage boundary. So an ordinary hang becomes an
ordinary failure, and the automatic revert follows well inside the ceiling.

Two limits remain. The billing helper's database reads have no timeout of their
own. The client of a `systemd-run --wait` host command can be stopped without
stopping the command itself. A hang there can still reach the watchdog, which
sends SIGTERM and then SIGKILL 15 seconds later. That case is what the progress
file and `revert-interrupted` are for.

Each stage is written to `<result>-progress.json` as it starts, so even a run
killed outright says how far it got. A root step whose container outlives its
client is waited for, or stopped, before any revert or rollback touches the host.

- Any failure before main advances reverts automatically: the untouched
  originals return, baseline units are restored, the container's restart policy
  and memory limits are restored, the version-1 pin returns and the application
  restarts on the running release. `discard-failed-attempt` then removes the
  partial image, key and mount point.
- Any failure after main advances stops the application services. `rollback`
  (with `--from-result`, under this same declaration) copies the current data
  back to plaintext, restores plaintext units and keeps the encrypted image, key
  and pre-migration snapshot for inspection.
- If the run is killed outright before main advances, its lock and progress
  file remain. `revert-interrupted --from-result <progress file>` finishes the
  revert from whatever state the kill left, then `discard-failed-attempt`
  removes the partial artifacts.
- Ctrl-C or a lost SSH session at the runner does not stop the act: the
  watchdog runs it in its own process group. `revert-interrupted` refuses while
  the recorded migrate process or any of its root-step containers is still
  running. It exits non-zero if the revert does not complete.
- Never rerun blindly; the lock and evidence stay until inspected.

## Key custody and what this act does not establish

While the slot-0 key file is on this host, anyone with a full copy of the
virtual disk or root on the running host can open the volume. What the act does
establish:

- new database, WAL, file, mail, proof and service temporary writes no longer
  reach the plain root filesystem;
- the whole volume becomes cryptographically erasable (`luksErase`);
- the path to protection against disk-level access is written down: vault the
  passphrase, remove slot 0, re-encrypt, remove the key file. After that, every
  boot needs the typed passphrase. Deleting the key file alone establishes
  nothing, because slot 0 stays valid and the file's blocks may survive.

Not established:

- encryption of the host swap file, journald or the shared root filesystem
  (host-level);
- overwriting of freed plaintext blocks on the virtual disk;
- temporary files written to hard-coded paths rather than through `TMPDIR`;
- off-host custody of the recovery passphrase (owner action).

Plaintext copies remain on the root disk until the owner approves their
destruction:

- the rollback snapshot;
- `rebuild/.runtime/files` and `rebuild/.runtime/mail`, from before the
  service-identity cutover;
- the decrypted files left by earlier restore checks.

All of them are synthetic, and all must go before real patient data. No claim
about Stripe, Resend, offsite restoration, invoice reconciliation or
independent testing follows from this act.
