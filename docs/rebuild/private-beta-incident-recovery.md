# Private beta incident and recovery instructions

Scope: the rebuilt QuillMD application at `/opt/meddoc-pro/rebuild`. Use synthetic
records only. Preserve public maintenance, administrator MFA and inactive reviewer
access. Do not reboot the shared VPS, prune containers/volumes, alter shared SSH,
change retention, erase historical evidence or restart provider work blindly.

This is an operator runbook. Commands below contain paths and public identifiers,
never passwords, keys or capability links. A status command is not permission to
perform a destructive action. Restoration/promotion and code activation require
the established committed declaration, exact CI and judged rollback procedure.

## 1. Establish scope before changing anything

Read `rebuild/.runtime/CHECKPOINT-LATEST.md` and the latest activation result. Record
UTC time, symptom, request/job identifier and intended scope in a new protected
incident directory. Choose a previously unused identifier; never overwrite an
older report. Keep browser screenshots free of credentials/private link tokens.

Read-only checks from `/opt/meddoc-pro`:

```bash
git rev-parse HEAD
git status --short
systemctl show quillmd-fresh-doctor quillmd-fresh-admin quillmd-fresh-worker \
  -p ActiveState -p SubState -p MainPID -p ExecMainStartTimestamp -p Result
curl --fail --silent --show-error http://127.0.0.1:9130/health/
curl --fail --silent --show-error http://127.0.0.1:9131/health/
rebuild/.venv/bin/python rebuild/manage.py configuration_status
```

Use the exact loopback authority including the port; an altered `Host:localhost`
can correctly fail the private-origin check. For worker release, read
`worker.json` under `/var/lib/quillmd/proofs/` through the approved
`ops.private_storage.read_file` helper and compare its PID to systemd. Do not
dump `/proc/*/environ`, service environment values or `.env`. Doctor/admin HTTP
health plus a worker PID-bound startup proof are separate observations.

The ordinary browser preview is `https://app.quillmd.com:9443/`, using the preview
sign-in and individual account sign-in. Administrator access remains the private
9131 listener via the established authenticated tunnel and application MFA. Public
443 app/admin are intentionally 503. Do not expose 9130/9131/55438 publicly to
work around a failure.

## 2. Job interrupted, timed out or delivered unusable output

Inspect the authenticated job/audit/financial screens. After activation of the
operations milestone, `/console/jobs/<job-uuid>/` explains provider receipt,
request/resource IDs, units/rates, reservation, usage debit, adjustments and
current authorized balances without clinical access. Use the recorded IDs, not
a new generation, to investigate.

- **Queued, no provider request:** the normal cancellation flow may release the
  hold without charge. Do not delete the job or reservation.
- **Running/uncertain:** preserve receipt, audio, result and held funds. Existing
  stale-job handling moves uncertain work to reconciliation without resending.
  Never replay an uncertain request merely to obtain a success or receipt.
- **Provider receipt exists but no settlement:** authentic evidence and the
  administrator reconciliation flow decide the result; no manual balance edit.
- **Failed after settlement:** distinguish unusable/platform failure from usable
  output later discarded or blocked by user-state changes. The accepted policy
  absorbs platform failures with appended reversals; user-declined usable work
  remains billable. A provider result is not silently erased or relabelled.
- **Pending invoice adjustment:** it survives failed callbacks. Use the existing
  authorized reconciliation operation after the underlying problem is repaired;
  idempotent ledger keys prevent a second debit. Do not create another receipt.

Use `cost-definition.md` for the exact binding-limit, absorption and payer rules.
Only an authorized administrator may resolve an uncertain job with a recorded
evidence note. Keep failed attempts and attribution.

## 3. Financial mismatch or payment retry

Run the read-only billing audit into a new private file; it makes no provider
call. From `/opt/meddoc-pro/rebuild`, after creating an unused protected incident
directory, the command shape is:

```bash
.venv/bin/python manage.py audit_billing --maintenance-storage \
  --output .runtime/incidents/INCIDENT-ID/billing-audit.json
```

Check original usage, immutable rate snapshot, authorized payer and hold, exact
1.5×charge within the binding limit, promotional/paid consumption, appended
adjustments and wallet = sum of ledger / reserved = sum of held funds. A missing authentic receipt is
an exception, not permission to reconstruct one. Configured-rate arithmetic and
provider-returned quantities are not invoice reconciliation.

For Stripe, correlate the signed event ID with its durable webhook row and
payment/refund ledger key. A checkout redirect cannot credit a balance. Preserve
failed/out-of-order attempts; replay only the same authenticated event through
the supported verified handler when evidence establishes it is appropriate.
Do not repeat the completed sandbox campaign or perform live charges. Provider
cost evidence is unrelated to Stripe reconciliation.

## 4. Local backup failed, stale or unavailable

After the scheduled-backup milestone is activated:

```bash
systemctl status quillmd-fresh-backup.service quillmd-fresh-backup.timer --no-pager
systemctl list-timers --all quillmd-fresh-backup.timer --no-pager
rebuild/.venv/bin/python rebuild/ops/scheduled_backup.py status
journalctl -u quillmd-fresh-backup.service --since '2 days ago' --no-pager
```

Expected schedule 04:30 UTC. Nonzero status means absent/failed/unfinished capture,
invalid protected files, or last success older than 30 hours. Immutable attempts live in
`.runtime/backup-monitor/`; the latest success cannot hide a later invalid-lock
failure. Fixing permissions alone is not proof of a successful new backup.

Check fresh volume/database service state, correct existing key/role paths,
available space and exact operation cgroup. Never print the key/role files.
The bounded capture refuses low space and times out; it never retries or deletes
old backups. Preserve its `INCOMPLETE` directory. After a demonstrated repair,
use the same project service for one deliberate retry and record its outcome.
No app restart or offsite purchase is necessary for a local backup.

This proves local failure visibility through status/journald, not delivery to an
external alert recipient. The older shared `quillmd-postreboot-proof` unit is a
different, preserved service; do not reset its failure to obtain a green screen.

## 5. Demonstrate restoration without touching the live database

Select a complete authenticated run and its matching existing key. Use the
existing tool from the permanent rebuild directory:

```bash
.venv/bin/python ops/backup_restore.py restore-check \
  --backup .runtime/new-system-backups/VERIFIED-BACKUP-RUN-ID \
  --key-file .runtime/backup-secrets/fresh-backup-current-20260917.key \
  --output .runtime/restore-checks
```

The current key must actually match the chosen backup; older historical backups
may use the preserved predecessor key. Do not generate a replacement key and
expect it to open existing ciphertext. Require `complete`, matching table/file
hashes, zero financial/scope invariant violations, no network/ports/workers/
provider actions, tmpfs without swap and successful owned-container cleanup.
An identical retry after failure is not diagnosis; keep the recorded stage and
error class and investigate first.

This command creates an isolated temporary PostgreSQL container and never
replaces live data. Actual promotion of restored data is a separate declared act
with a baseline, expected schema/data deltas, stopped-writer plan and recovery
judgment. Never aim `pg_restore` at the running fresh database as a test.

Offsite recovery is separate: follow `offsite-backup.md` only after approved
bucket/key configuration exists. Its download-only mode needs authenticated run
ID, manifest ciphertext SHA and the matching independently preserved key. Local
restore is not proof of offsite recovery or independent custody. Preserve
plaintext rollback copies if any exist; this task does not authorize deleting
them or modifying the key-unlock/retention policy.

## 6. Code rollback and incident closeout

Use the exact activation record and established repository wrapper. Feature work
belongs in an isolated worktree; deploy from the permanent shared tree only.
Do not change main outside a PR, substitute an ancestor's CI, repoint shared bind
mounts or issue a generic reset. Only the recorded scoped activation/rollback
procedure may alter the three application units. A documentation correction
requires no restart. A compatible stricter financial evidence trigger can remain
installed during a code rollback; do not erase evidence to make old code pass.

Before closing the incident, record repository and doctor/admin/worker revisions
separately, actual affected checks, compared data/financial invariants, public
maintenance and synthetic-only state, temporary-access cleanup and remaining
coverage limits. Append the durable checkpoint. Native Word/human dictation,
independent penetration testing, invoice reconciliation, offsite custody and
patient-data agreements require their own evidence; none follows automatically
from a healthy process or passing internal test.
