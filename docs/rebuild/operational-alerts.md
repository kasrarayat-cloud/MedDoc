# Operational backup alerts

Scope: the synthetic private rebuild only. This monitor never accesses the
clinical database, starts a backup, changes backup history, restarts application
services, or sends clinical content. The application release remains independent
of this operations installation.

## Installed design and acceptance gates

`quillmd-fresh-backup-alerts.timer` runs a bounded check every five minutes. The
service uses claude, `NoNewPrivileges`, a read-only filesystem except its private
`.runtime/backup-alerts/` directory, 256 MB memory, no swap and a 60-second bound.
It reads existing local backup status, the actual backup timer and service result.
A legitimate capture has its existing ten-minute completion bound. A last success
older than 30 hours is unhealthy. No backup or alert history is deleted.

It reuses the verified Resend sender and existing protected application key.
The monitor imports only the email transport, with minimal email settings; it
does not initialize the application or import private-preview credentials.
The fixed approved recipient is `kasra.rayat@gmail.com`. Configuration is
`rebuild/.runtime/backup-secrets/backup-alerts.json`, claude0600. Its exact schema
is installed by the reviewed scoped installer. No new provider key is required.

One alert is attempted when an unhealthy incident opens, with a 24-hour interval
between the first notices of successive incidents, so a condition flapping between
healthy and unhealthy cannot send more than once a day. Inside an open incident:

- a change to a condition the incident has not yet announced is a new notice
  (subject `ESCALATION`) with its own identity and receipt, stating the new
  condition and whether severity rose, held or fell. It is sent at once when it is
  more severe than anything the incident has announced (at most once per
  incident: warning to failure), otherwise no sooner than one hour after the
  incident's previous notice;
- a condition the incident has already announced is never announced again, so
  flapping between announced conditions sends nothing more;
- a still-open incident is re-announced 24 hours after its last notice (subject
  `REMINDER`), naming how long it has been open and its current condition.

A healthy check ends the incident. The pending record is
written before a provider request; a timeout or interruption is uncertain and
must not be retried automatically, even after provider idempotency expires. An
uncertain attempt requires operator review, and it also stops every later
escalation and reminder for that incident. The JSON status carries an `incident`
summary (opened, notices, last notice and its condition, next reminder, any
deferred escalation) without identities. The monitor's own status becomes
stale after 15 minutes without a check. A broken monitor or lost email credential
cannot reliably notify through that same broken channel: inspect its service
failure and status locally, and keep outside-host detection separately gated.

The user-authorized test has a separate fixed identity
`20260920-operation-recovery` and subject
`[QuillMD NONCLINICAL TEST] Simulated backup failure`. It leaves the actual backup
and monitor status untouched. Reinvocation reads the existing receipt rather
than sending again. This one authorization is not a reusable future test grant.

**Installation, actual send, provider delivery and inbox receipt require their
own measured evidence.** The runtime milestone report and checkpoint record
which occurred; source code and isolated tests alone do not establish them.

## Diagnose from the VPS as claude

From `/opt/meddoc-pro`:

```bash
systemctl status quillmd-fresh-backup-alerts.service quillmd-fresh-backup-alerts.timer --no-pager
systemctl list-timers --all quillmd-fresh-backup-alerts.timer --no-pager
rebuild/.venv/bin/python -B rebuild/ops/backup_alerts.py status
rebuild/.venv/bin/python -B rebuild/ops/scheduled_backup.py status
journalctl -u quillmd-fresh-backup-alerts.service --since '2 days ago' --no-pager
```

The JSON status contains a fixed condition and a concrete action, never provider
error bodies, keys, patient rows or URLs with credentials. A nonzero result must
be investigated. `provider_accepted` is not delivery or human inbox confirmation.
Keep subsequent delivery or owner confirmation as additive evidence; do not
rewrite the original send receipt. `.runtime/backup-alerts/` retains private
pending/result files. Its permissions must stay 0700/0600.

For a missing/invalid configuration, inspect ownership/mode and the expected
protected paths; never print `.env`. For stale monitor status, inspect the new
timer and service. For backup failure, follow
`private-beta-incident-recovery.md` section 4 and the recorded backup attempt.
Do not retry an uncertain provider send or reset a failed unit merely to make
status green. Repair the demonstrated cause and run the affected check.

## Scoped installation and rollback

The installer validates reviewed source hashes, permanent main, committed
declaration, exact new units and protected configuration/process baselines.
It exclusively creates the new units; an existing file refuses overwrite.
Install and activation are separate declared actions. A healthy first service
check is required before enabling the timer. No application restart is needed.

Use the exact installed operations commit from the installation receipt, through
the committed operational-recovery declaration:

```bash
bash scripts/run-ruled-mutation.sh \
  --declaration docs/foundation/mutations/20260920-quillmd-operational-recovery.md \
  -- rebuild/.venv/bin/python -B rebuild/ops/install_backup_alerts.py \
  --expected-commit EXACT-INSTALLED-OPERATIONS-COMMIT --action disable --execute
```

Rollback disables only the alert timer and stops only its service; both are
checked inactive. All units, configuration and receipts remain for diagnosis.
The monitor state `.runtime/backup-alerts/status.json` is format 2 since the
escalation change: format 2 keeps every format-1 key and adds the incident's
opening time, notice count, last notice kind and condition, and the conditions it
has announced. The current monitor upgrades a format-1 file in place on its first
check. A release older than that change refuses format 2 as invalid
(`monitoring_state_unavailable`, no email) until the file holds format 1's six
keys again; reverting the source alone is therefore not a working rollback.
An in-flight send stopped during rollback remains uncertain. If source has moved
since installation, the exact-source gate requires a new reviewed scope; do not
bypass it or apply an old declaration to different source.

## Outside-host outage detection — prepared, not active

There is no authorized external heartbeat configuration in this project's current
protected configuration. This VPS cannot send an email after total power, network,
disk or host loss. Local systemd and Resend do not close that coverage gap.

The selected handoff is one owner-controlled Healthchecks.io check named
`quillmd-private-backup-monitor`, period five minutes, grace ten minutes, with
email notification to the approved owner inbox. Its documented design alerts
when expected pings stop; the check's UUID URL is a secret.
[Provider documentation](https://healthchecks.io/docs/).

An authorized account administrator must enable that check/recipient in the
owner's account and securely place its individual check URL, without an account
management key, in
`/opt/meddoc-pro/rebuild/.runtime/backup-secrets/external-monitor.json`
(claude0600, parent0700), together with the approval reference:

```json
{"version":1,"provider":"healthchecks.io","check_url":"SECRET-CHECK-URL","owner_approval_reference":"RECORDED-APPROVAL","synthetic_only":true}
```

No account, subscription or check is provisioned by this milestone. The file is
a protected future handoff, **not a currently consumed or verified integration**.
Engineering must then connect success-only pings to the reviewed monitor, validate
TLS and the fixed provider host, and demonstrate a missed heartbeat using an
isolated synthetic check without stopping the real VPS or backups. Keep provider
alert generation and inbox receipt separate. No server credentials, logs or
clinical content need to leave the host for a heartbeat.
