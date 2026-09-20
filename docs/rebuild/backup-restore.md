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

## 2026-09-20 — Current recovery proof and local schedule

The earlier operational limits above remain historical evidence. The authorized
overnight continuation closes the local scheduling omission independently of the
still unavailable offsite destination. No retention or key-custody policy changes.

Current backup `20260920T081236Z-04a49ff8` restored successfully on its first
attempt into `quillmd-restore-c965470cd3de6157`: 35 tables, 225,581 rows and 42
referenced files (2,428,954 bytes). All table/file hashes matched, all four
financial/scope invariants were zero and eight custom triggers were enabled.
The restore used no network or published ports, no workers/provider credentials,
and tmpfs without swap. It wrote zero decrypted files and removed its owned
container. This proof includes the completed Stripe/email/SOAP records and the
deferred human-dictation draft; it does not turn the same-VPS backup into offsite
recovery or independent key custody.

Evidence: `rebuild/.runtime/overnight-completion-20260920/backup-attempt-01.json`
and `restore-attempt-01.json`. Source repository identity in the backup is
`db5f54524a2b3bbda4eaa28a46612e9523966697`; running application identity was
separately verified as `928897f4e934f1912855f96662617c6d0d9df629` on doctor,
administrator and worker.

### Local operation

`ops/scheduled_backup.py` wraps the existing audited backup tool. The dedicated
`quillmd-fresh-backup.service` runs as the existing operator identity with the
read-only database role and existing current encryption key. Its timer uses
04:30 UTC daily and catches a missed schedule after downtime. No application
restart, cloud access, credential creation, provider request, automatic retry,
retention deletion or shared scheduler modification is involved. Activation
requires the exact reviewed release and a committed scoped declaration; source
files alone are not evidence that the timer was installed.

The service limits the supervisor and its children to 2 GiB without swap, and
allows ten minutes for the operation. The child has a nine-minute timeout. It
refuses less than 2 GiB free disk space, unsafe permissions/symlinks, mismatched
summary/manifest identity and concurrent execution. An incomplete run stays
preserved. Each attempt has a private immutable JSON record under
`.runtime/backup-monitor/`; `latest.json` is atomically replaced. A failed
attempt retains the last successful run identity and exits nonzero. Child
stderr and exception messages are never copied into status or the journal.

An independent fixture refutation found that an invalid capture-lock mode could
fail before a new attempt was recorded, leaving status green from the preceding
success. The repaired runner records failed attempts even when the lock cannot
be opened or validated; only the lock holder replaces shared status. The status
reader checks the lock and immutable attempt history. Repairing a lock's mode
alone cannot stand in for a new successful capture. Twelve focused tests include
this reproduced case and an unopenable symlink lock; no lock checks were relaxed.

Create the monitor directory as owner `claude`, mode `0700`, before installing
the two exact reviewed units from `rebuild/deploy/`. Installation must preserve
the existing source/key/role owners and permissions. No `.env` or credentials
are installed into the service unit.

Operator checks (no secrets or clinical contents in output):

```bash
systemctl status quillmd-fresh-backup.service quillmd-fresh-backup.timer --no-pager
systemctl list-timers --all quillmd-fresh-backup.timer --no-pager
rebuild/.venv/bin/python rebuild/ops/scheduled_backup.py status
journalctl -u quillmd-fresh-backup.service --since '2 days ago' --no-pager
```

The status command returns a nonzero exit for no successful scheduled capture,
a failed/unfinished latest attempt, future timestamps, or age over 30 hours.
The initial manually verified backup above does not count as execution of this
new runner; one controlled service capture must pass at activation. It need not
repeat the completed isolated restore unless backup/restore code changes.

### Incident and recovery

1. Read status, service exit code and the immutable attempt record. Preserve an
   incomplete capture and its error evidence. Do not delete older backups to
   hide a disk-space failure or change permissions to bypass a refusal.
2. Check `quillmd-fresh-volume`, `quillmd-fresh-database`, doctor, admin and worker
   states. The service startup proofs under `/var/lib/quillmd/proofs/` bind each
   process PID and release; read them through `ops/private_storage.py`.
3. For low space, pause capture and investigate project-scoped growth. Retention
   changes need their own recorded policy. For permission/configuration errors,
   compare the installed identity and protected files to the runbook. Never
   print key/role file contents. For a timeout, check the exact service cgroup
   has ended before a single deliberate retry; no uncertain provider calls are
   part of this backup operation.
4. For restoration, keep the live database untouched. Use `restore-check` above
   with an authenticated complete backup and the matching separately preserved
   key. Inspect the resulting report and require all hashes/invariants, network
   isolation, no worker/provider actions and owned-container cleanup. Promotion
   of a restored database is a separate declared operation with its own data
   delta and rollback plan.
5. Recheck public maintenance and synthetic-only health after any actual repair.
   A documentation/status change does not warrant application redeployment.

Failure visibility here is local status plus systemd/journald. No external alert
delivery or operator acknowledgement is claimed. An approved destination and
scoped key are still required for offsite upload/restore; independent key
custody, remote recovery, RPO/RTO beyond the measured local exercise, and verified
out-of-band alert routing remain separate release gates. The inherited shared
`quillmd-postreboot-proof.service` failed on 2026-09-06 and is explicitly preserved
by the ownership audit; it is not this rebuild's backup service and must not be
silently reset, rewritten or cited as a successful reboot proof.
