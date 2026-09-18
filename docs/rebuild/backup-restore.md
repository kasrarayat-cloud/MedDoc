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

Since migration 0013 (2026-09-18) the `usage_multiplier` invariant is the capped charge rule `audit_billing` checks: each
usage row's charge equals 1.5 × its cost, capped at the settled hold for its request, and any excess appears exactly as one
`absorbed_over_limit` platform cost. Exercises recorded below from before that date checked the exact 1.5 × multiplier.

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

## The restore that failed first, diagnosed rather than retried

**2026-09-18.** A restore of backup `20260918T110842Z-cd2a7006` failed and an
identical retry succeeded. A retry that works is not a diagnosis, so the failure
was traced through the records that still exist:

| record | evidence |
| --- | --- |
| `.runtime/restore-checks/restore-417021bdffeac74f/verification.json` | `complete: false`, started `11:09:06.970867Z`, finished `11:09:09.218215Z` — **2.25 seconds**, `container_retained: false` |
| `.runtime/restore-checks/restore-a2b12ce681fc4aa0/verification.json` | `complete: true`, same backup, started `11:09:29.589447Z`, finished `11:09:41.348696Z` — **11.76 seconds** |

The successful run needed 11.76 s. The failed one ended after 2.25 s, which is
long enough to start a container and far too short to restore the dump, so the
failure was inside `pg_restore` rather than in starting the database.

⚠️ **What follows is an inference consistent with that evidence, not a log
reading — and the difference is stated because it matters.** The restore
container is removed by the tool's own cleanup (`container_retained: false`), so
its PostgreSQL log no longer exists, and the docker daemon's event buffer has
since rolled past the window. An earlier draft of this section quoted event
timestamps and the wrong backup id; both are corrected above against files that
can still be opened.

**The mechanism, which is checkable in the image:** `docker-entrypoint.sh`
starts a *temporary* server for initialisation with `-c listen_addresses=''`,
then stops it and execs the real `postgres`. `pg_isready` cannot tell the two
apart. A restore that connects during that handover meets a shutdown mid-dump,
and a connection that closes mid-restore surfaces as an ordinary restore error
with nothing naming the race.

**To settle it rather than infer it**, re-run the restore with the container
retained and read the PostgreSQL log directly. That has not been done, because
the repair below removes the race in either case.

**Repair.** `ops/backup_restore.py` gained `restore_ready()`, which treats the
database as ready only when all three hold:

1. the container log contains `PostgreSQL init process complete; ready for start up.`
   — the marker the entrypoint prints *after* the temporary server is gone;
2. `pg_isready` succeeds;
3. `SELECT 1` returns `1` over the real connection.

The wait is bounded (120 polls) and `restore()` now records `stage`,
`failed_stage` and `error_class` on every path, so the next failure names where
it stopped instead of requiring a journal reading. Raw stderr is deliberately
**not** stored: a failing `pg_restore` can quote row values.

A regression test simulates the race — `pg_isready` succeeding before the marker
appears — and asserts that readiness is reached before `pg_restore` is invoked,
that the failed stage is recorded, and that no raw stderr is kept
(`ops/test_backup_restore.py`, `RestoreReadinessSurvivesThePostgresInitRace`).
**This test does not depend on the diagnosis being right**: it pins the ordering
that makes the race impossible, whatever caused this particular failure.

### Exercised after the 2026-09-18 activation

Backup `20260918T161229Z-2ee211a0` (35 tables, **225,079 rows**, 28 files,
source commit `5f8050df`) restored **on the first attempt** — no retry — with
every ordered table hash and every file hash matching, `decrypted_files_written`
0, and the restore database on tmpfs with swap disabled. `stage` reached
`complete`, and neither `failed_stage` nor `cleanup_failed` appears.

⚠️ **What that does and does not show.** One clean restore does not prove the
init-server race is gone; a race not hit is not a race removed. What removes it
is the readiness gate — the marker, `pg_isready` and a `SELECT 1` that returns 1
— and the test that pins readiness before `pg_restore`. This run is evidence the
gate does not break an ordinary restore, which is the other thing worth knowing.

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
- 12 focused tool tests (18 as of 2026-09-18) cover ciphertext tampering, wrong keys, wrong object
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
