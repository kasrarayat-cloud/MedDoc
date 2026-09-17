# Fresh database and protected-file backup / restore

Implemented 2026-09-17 for **new synthetic QuillMD data only**. No old application
data or credentials are imported. Tool: `rebuild/ops/backup_restore.py`.

## What is coherent and protected

The tool holds a PostgreSQL repeatable-read, read-only transaction open and
exports its snapshot. The same snapshot supplies ordered table fingerprints,
row counts, financial/department invariants and all document references; `pg_dump`
imports that exact snapshot. Each referenced original, finalized export, audio
input and stored provider response is copied and hashed. Recorded database hashes
must match, and files are checked again before completion. Files are immutable
in the application; a missing or changed reference makes the backup fail.
Unreferenced scratch files, logs, file-mail outbox and provider/service credentials
are excluded. This is a database snapshot with matching referenced files, not an
atomic filesystem snapshot. Avoid schema deployments during capture.

Every dump/file and the manifest are encrypted and authenticated with the
established `cryptography.Fernet` implementation. File paths and document hashes
exist only inside the encrypted manifest. A nonclinical summary records totals
and the encrypted manifest hash. The key is separate from the backup directory;
directories are 0700 and files 0600. Existing destinations are never overwritten.
An `INCOMPLETE` marker prevents restoration of a failed capture.

Each plaintext object is limited to 256 MiB because Fernet requires the complete
message in memory. Exceeding that limit fails explicitly. Qualify a maintained
streaming backup tool before the database exceeds this bounded private-beta
tool's capacity; never truncate or silently omit data.

References: [PostgreSQL snapshot synchronization](https://www.postgresql.org/docs/17/functions-admin.html#FUNCTIONS-SNAPSHOT-SYNCHRONIZATION),
[pg_dump snapshot option](https://www.postgresql.org/docs/17/app-pgdump.html),
[Fernet authenticated encryption and memory limit](https://cryptography.io/en/latest/fernet/).

## Verified exercise and preserved evidence

Backup `20260917T165751Z-eccb5538` captured source commit
`ddc923e873d20c6ec1c9f93a95878039ff323473` and restored successfully twice:

- 33 public tables, 75,100 rows and 15 referenced files (535,268 bytes).
- Every ordered table hash, row count and file hash matched.
- Wallet bounds, exact 1.5 multiplier, department scope and held-reservation
  totals had zero violations before and after restoration.
- Six custom immutability/scope triggers were restored and enabled.
- Fresh owned PostgreSQL container: no network, no published ports, tmpfs data,
  no source mounts, no worker and no provider credentials/actions.
- The second restore explicitly initialized host SCRAM authentication. A first
  role-authentication probe exposed PostgreSQL initdb's localhost trust default;
  that restore-test setup was repaired, recreated and retested successfully.
- 12 focused tool tests cover ciphertext tampering, wrong keys, wrong object
  substitution, traversal/symlinks, key modes, incomplete backups, duplicate paths
  and refusal to delete unrelated restore containers.

Permanent protected copies, transferred exclusively with hash equality:

- Backup: `/opt/meddoc-pro/rebuild/.runtime/new-system-backups/20260917T165751Z-eccb5538/`
- Key: `/opt/meddoc-pro/rebuild/.runtime/backup-secrets/fresh-backup-20260917T165751Z-eccb5538.key`
- Activation precheck report:
  `/opt/meddoc-pro/rebuild/.runtime/restore-checks/backup-restore-20260917T165751Z-eccb5538.json`

The report has `complete: true`. It contains no document contents, credentials or
user identifiers. The backup contains account/MFA secrets as database data and
must remain encrypted and protected.

## Operator commands

Run from the activated `rebuild` directory using its virtual environment. Keep
the key destination outside the backup directory. Generate a key only once:

```bash
.venv/bin/python ops/backup_restore.py keygen \
  --key-file .runtime/backup-secrets/fresh-backup.key

.venv/bin/python ops/backup_restore.py backup \
  --source /opt/meddoc-pro/rebuild \
  --database-credentials .runtime/db-role-secrets/fresh-db-roles.json \
  --key-file .runtime/backup-secrets/fresh-backup.key \
  --output .runtime/new-system-backups

.venv/bin/python ops/backup_restore.py restore-check \
  --backup .runtime/new-system-backups/REPORTED_BACKUP_ID \
  --key-file .runtime/backup-secrets/fresh-backup.key \
  --output .runtime/restore-checks
```

The role credential option selects the read-only backup login after coordinated
role hardening. Before hardening, omit that option to use the existing fresh
connection. No passwords appear in arguments or normal output. `restore-check`
creates and removes only its labelled temporary container; `--keep-container`
retains it for explicitly scoped role/security tests. Restored files and evidence
are private local artifacts. It never overwrites the live database or starts an
application/worker. Production recovery/promotion is a separate reviewed act.

## Operational limits that remain

This is a demonstrated local backup/restore, **not a completed disaster-recovery
program**. The encrypted backup and separate key are still on one VPS. Offsite
storage, separate key escrow/recovery, retention, RPO/RTO, scheduled monitoring,
failed-backup alerts and an operator promotion rehearsal need decisions and
qualification. No subscription, cloud resource, remote upload or schedule was
created. Preserve new backups and their keys across deployments/worktree removal.
