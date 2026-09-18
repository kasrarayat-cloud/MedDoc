# Fresh-storage recovery drill and removal of redundant plaintext copies — 2026-09-18

The storage act of 2026-09-18 (`fresh-storage-migrate-20260918b.json`, target
`3eac783a`) moved the fresh QuillMD database, documents, mail outbox, proofs
and service temporary files onto the LUKS2 volume. Plaintext copies of the new
application's data were left on the unencrypted root filesystem. This act
proves encrypted recovery once more, then removes those copies. It does not
deploy code, does not advance main, and makes no provider request.

## What stays exactly as it is

- The running release `3eac783a` on the private services
  (`127.0.0.1:9130/9131`), public maintenance mode and synthetic-only mode.
- The encrypted image, both key slots and both key files
  (`/etc/quillmd/quillmd-fresh-luks.key`, slot 0;
  `/etc/quillmd/quillmd-fresh-luks.recovery-passphrase`, slot 1). No key is
  added, removed, printed or copied.
- Every database row (fingerprints of all 35 tables compared before the drill,
  after it and after removal) and every live document and mail file (inventory
  compared the same way).
- The encrypted backups under `rebuild/.runtime/new-system-backups/`, their keys
  under `rebuild/.runtime/backup-secrets/`, database role secrets, the Word
  review package, terminology data, all evidence and report files, and every
  restore check's `verification.json`.
- Everything that belongs to the original application or to other tenants:
  `/opt/meddoc-pro/backups`, the `meddoc-pro_*` docker volumes, the retired
  LUKS volume at `/mnt/pgdata-encrypted`, the old QA volumes, and the shared
  redis, minio, caddy and marketing containers.

## Preconditions the act asserts before it changes anything

1. The script and `scripts/migrate-fresh-storage.py` equal the reviewed merge,
   and the merge is a merged PR into main that contains the running release.
2. The services run the permanent release, synthetic-only.
3. A fresh encrypted backup, restored in isolation with no decrypted file
   written, equals the live database in every table. Each table's row count and
   content hash, computed by the backup tool's own fingerprint function (the
   one its restore check uses), matches the backup's authenticated manifest. A
   matching total row count is not enough. No job is queued, running or in
   reconciliation.
4. Every active path resolves to exactly one mount, and that mount is
   `/dev/mapper/quillmd-fresh-encrypted`, so nothing is mounted over it:
   `/var/lib/quillmd` and its `files`, `mail`, `proofs` and `tmp`; the
   database directory and `pg_wal`. The WAL is a directory, not a link.
   PostgreSQL reports its data directory as `/var/lib/postgresql/data` and has
   no other tablespace. Each service's startup proof names
   `/var/lib/quillmd/tmp` as its temporary directory. The services' private
   `/tmp` and `/var/tmp` directories hold no files.
5. Key slots 0 and 1 are both present. The key file opens slot 0. The recovery
   passphrase opens slot 1 both from its file and when typed. Both files are
   root 0400.
6. Accounting: every file in every copy below is byte-identical (SHA-256) to
   the file at the same relative path in the live encrypted store. The rollback
   snapshot's census equals the one the storage act recorded when it copied
   that data onto the encrypted volume, with services and database stopped.
   After starting from that copy, the act proved all rows identical.

## The recovery drill (brief private-service restart)

Stop `quillmd-fresh-volume.service`. The database and the three application
services stop with it. Then prove:

- the mapper is closed and nothing is mounted;
- the empty underlying directories are immutable and refuse a root write probe;
- a container started by hand while closed writes nothing.

Then reopen the volume, start the database and the services, and require health
on the same release, the same identity proofs and unchanged rows and files. This
is the drill the storage act ran, repeated as a recovery check. It is not a host
reboot, and reboot recovery stays untested.

## Removal, declared before the act

The accounting is repeated immediately before removal. Directories are removed
one at a time, in the order below. Each directory's files are shredded in place
(`shred -u -n 3 -z`, via `find -xdev`) in its own named host unit. systemd stops
that unit after 900 seconds; measured on this disk, the 143 MB snapshot takes
24 seconds. The act waits slightly longer than the unit can run, so no shred can
outlive it. Each directory is recorded: files before, the shred's exit, files
left, and whether it is gone. Its empty directories are removed only when no
file is left. Otherwise the act stops: that directory is kept with whatever
files remain (the record gives the count), and no later directory is touched.

| path | origin | files | bytes |
|---|---|---|---|
| `/var/lib/quillmd-rollback-20260918` | pre-migration snapshot of release `19d46ad3`, moved aside by the storage act | 2,499 database + 44 state (34 documents, 6 mail, 4 superseded startup proofs) | 143,248,132 + 1,176,723 |
| `/opt/meddoc-pro/rebuild/.runtime/files` | document root of releases up to `66acbba7`, superseded by `/var/lib/quillmd` at the OS-identity cutover (2026-09-17 17:42Z) | 27 | 927,320 |
| `/opt/meddoc-pro/rebuild/.runtime/mail` | outbox of the same releases | 2 | 1,227 |
| `…/restore-checks/restore-3cb2094861b0221f/files` | restore check of backup `20260917T174418Z-220e52ba` (source `66acbba7`) | 21 | 927,150 |
| `…/restore-checks/restore-8ff86eb5e74a79c6/files` | backup `20260917T190612Z-48741b09` (source `68883747`) | 22 | 963,799 |
| `…/restore-checks/restore-082a2b3c778bf220/files` | backup `20260917T211935Z-6f919769` (source `5d43d3d6`) | 25 | 1,064,574 |
| `…/restore-checks/restore-c5846e432dececd0/files` | backup `20260917T214244Z-c2b7f69c` (source `8f8a6763`) | 26 | 1,111,178 |
| `…/restore-checks/restore-d56b7fa1af209561/files` | backup `20260917T234313Z-56be2efa` (source `8f8a6763`) | 28 | 1,169,128 |
| `…/restore-checks/restore-d74d8e2b0746dd01/files` | backup `20260918T015725Z-f9fb8a56` (source `19d46ad3`) | 28 | 1,169,128 |

Totals: **2,722 files, 151,758,359 bytes, nine directories.** Every file in
this list is a copy of new-application synthetic data. None belongs to the
original application.

The result records every removed path with its SHA-256 and size. It is private
evidence at
`/opt/meddoc-pro/rebuild/.runtime/plaintext-recovery-reap-<label>.json`.

## What must NOT change

Row fingerprints, live file inventory, key slots and key files, the backup
proof, the release, co-tenant HTTP status, and the protected containers. A
difference in any of them is the finding, whatever it seems to mean afterwards.

## Limits, stated before the act so they are not discovered after it

- `shred` overwrites a file's current blocks. On ext4 with a journal, on a
  provider's virtual disk, earlier copies of those blocks can survive in the
  journal, in free space or in provider snapshots. This act removes the
  accessible copies. It cannot promise physical erasure of blocks this
  filesystem has already released.
- Both keys are on this host, so the encryption does not protect against root
  on the host or a copy of the whole disk. It does protect an image-only or
  backup-only copy, and it allows crypto-erase. Independent custody of the
  recovery passphrase is pending with the owner.
- The document backups exclude the private outbox and unreferenced scratch
  files by design. After this act, those exist only on the encrypted volume.
- Swap, the service journal and the database container's log stay on the
  plaintext root filesystem, as recorded by the storage act.

## Failure handling

- An accounting or precondition failure stops the act before anything is
  removed.
- A drill failure stops the act with nothing removed, and the volume, database
  and services are started again.
- A shred failure, a timeout or the watchdog's signal stops the act at that
  directory. Earlier directories are removed and recorded. That directory may
  be partly shredded, and its record or the failure record gives the files
  left. Every later directory is untouched. The running shred unit is stopped
  and its root step settled before the result is written.
- When nothing was removed and the services were restarted, the act's lock is
  released, so it can be run again. Once removal has begun, the lock stays for
  inspection.

The result file names the stage in every case.

## How it runs

Only through `scripts/run-ruled-mutation.sh`, with this committed declaration and
`RULED_ACT_MAX_SECS=3600`, from permanent main at `/opt/meddoc-pro`, running the
reviewed script:

    verify-and-reap-fresh-plaintext.py --target <merge sha> \
        --backup-report rebuild/.runtime/restore-checks/backup-restore-<run>.json \
        --result /opt/meddoc-pro/rebuild/.runtime/plaintext-recovery-reap-<label>.json --execute
