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

- a condition more severe than the incident's LAST notice is announced at once,
  whether or not the incident announced it before, as a new notice (subject
  `ESCALATION`) with its own identity and receipt, stating the condition and that
  severity rose. A failure that returns after a notice said the severity
  decreased is therefore never left standing on "decreased";
- any other change to a condition the incident has not yet announced is a new
  `ESCALATION` notice stating whether severity held or fell, sent no sooner than
  one hour after the incident's previous notice;
- nothing else is announced before the reminder: a still-open incident is
  re-announced 24 hours after its last notice (subject `REMINDER`), naming how
  long it has been open and its current condition.

This cannot loop. Once the last notice is the more severe one, flapping between
conditions already announced sends nothing until the reminder. A rise needs a
notice at a lower severity first, and such a notice is either a newly announced
condition (at most once per condition, an hour after the previous notice) or the
daily reminder.

When an incident has ended and a new one opens inside the 24-hour interval, its
first notice is still sent (subject `ESCALATION`) if it is more severe than every
notice of the last 24 hours; otherwise the interval holds. A notice the state
records that no sidecar stamp reaches (none at or after its time) counts as a
failure for this purpose, so it can only hold the interval. The converse is never
trusted: a notice the sidecar describes but `status.json` never recorded (a check
that stopped between writing the two files, before any request began) is
discarded with the sidecar record that described it, even after an earlier
release has checked in between, so it can never hold anything. Flapping at the
same or a lower severity therefore sends nothing extra, and healthy/failure
flapping after a warning sends at most one extra notice a day.

A healthy check ends the incident. The pending record is
written before a provider request; a timeout or interruption is uncertain and
must not be retried automatically, even after provider idempotency expires. An
uncertain attempt requires operator review, and it also stops every later
escalation and reminder for that incident. The JSON status carries an `incident`
summary (opened, notices, last notice and its condition, next reminder, any
deferred escalation) without identities; `status` reports the deferred
escalation the last check decided, recomputed by the same rule over the recorded
state (none after an uncertain notice, which is never followed).

`status` reads the state under the check's own lock, held shared and opened
read-only. It waits up to 30 seconds for a running check; a check still running
after that (the check unit allows 60 seconds) is reported, not treated as a
fault: `status` then reads the last completed state without the lock, marks it
`check_running: true`, and never reports the monitor broken merely because a
check is running. A notice that check is making at that moment is not yet part
of any completed state and is not shown. A check waits up to two seconds for a
reader, which holds the lock only while it reads the state files and the named
notice's record.

A recorded time later than the monitor's clock (a clock that ran fast and was
corrected) is read as the moment it is first seen, so it never delays a notice,
including after a check stopped between the two files of a close, and an
incident's age is never negative. The monitor's own status becomes stale after
15 minutes without a check.

### Fail closed means alert, not silence

A design rule for this monitor, decided by the lead on 2026-09-27: a state the
monitor cannot validate or recover must never leave it refusing for ever with no
email. Those states are `status.json` missing while incident records remain;
`status.json` or the sidecar unsafe or malformed; a notice the state names that
has no request record, or one that cannot be read or disagrees with the state;
and an incident record that breaks its own invariants.

The check that meets one sends, at most once per 24 hours, an operator notice
with the subject `MONITOR RESTARTED: the backup monitor could not read its own
state`. It says plainly that the monitor could not read its own state and why,
as one fixed label (`state_missing`, `state_invalid`, `ledger_invalid`,
`notice_record_missing`, `notice_record_invalid`, `notice_record_mismatch`,
`incident_record_invalid`) and never any content; the current backup condition,
its severity and action; and that the monitor has restarted its incident record
from this check. It then continues from a fresh, valid state. When the current
condition is one that is announced, that notice is the new incident's first
notice; otherwise it is sent on its own and holds nothing. Notices sent before it
are not carried forward, so it may repeat one already received. A possible
duplicate is acceptable; permanent silence is not.

Nothing is lost for diagnosis: the unreadable `status.json` and sidecar are kept
beside the new record as `monitor-restart-<id>-status.json` and
`monitor-restart-<id>-incident-notices.json` (hard links, so `status.json` is
never missing), with a `monitor-restart-<id>.json` marker recording the label and
time. Request records are never rewritten, and no request is ever made for a
notice the unreadable state named. A restart counts toward the 24 hours once its
notice's request record exists; inside that window a state that cannot be read
again is refused without any change, and `check` reports `state_unreadable`,
`state_restarted: false` and `next_state_notice_at`. `status` stays read-only and
reports `state_unreadable`; the next check restarts. Without a working email
configuration nothing is restarted, because nothing could be announced.

The rule does not reach a monitor directory or lock file that is itself unsafe,
a directory the check cannot write, or a parallel check: those still fail closed
without email. A broken monitor or lost email credential cannot reliably notify
through that same broken channel: inspect its service failure and status
locally, and keep outside-host detection separately gated.

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
The monitor state `.runtime/backup-alerts/status.json` stays format 1 with
exactly its six keys; `incident_attempt` names the incident's latest notice. The
escalation change keeps its extension (when the incident opened, the last
notice's kind and condition, the notice count, the conditions announced, and
when each severity was last announced) in a sidecar,
`.runtime/backup-alerts/incident-notices.json` (0600, atomic writes, created on
first need, restarted with a notice if malformed). A release without the sidecar
never opens it, nor the `monitor-restart-*` files, so reverting `backup_alerts.py`
is a complete rollback with no state repair: the previous release runs on every
state this release leaves behind as it does on its own, with ONE known
exception. A brand-new monitor (no `status.json` yet) whose very first notice is
stopped between writing the sidecar and `status.json` leaves the sidecar alone;
the previous release reads any incident file without a `status.json` as lost
state and refuses, sending nothing and inventing no incident. This release
recovers that directory and sends the owed notice: roll forward, not back. The
current monitor adopts whatever an earlier release leaves behind, reading what an
unrecorded first notice announced from that notice's own receipt, including after
this release stopped between its two files and the earlier release then checked.

While an incident is open the sidecar is written before `status.json`, and a
write that makes a notice also keeps, until the next write, the exact
`status.json` it began from and what the sidecar said about it. The newer notice
counts only if `status.json` records it (its incident, identity and time) or its
own request record (its condition, at its time) shows it began. Otherwise a check
stopped between the two files is read as though it never ran: the monitor reads
the kept record and discards the newer notice, which provably never began (a
request only follows both writes), whether or not an earlier release has since
rewritten `status.json`, and the next check sends whatever is owed. An earlier
release's own first notice for the same incident, under the same name, is read
from its own receipt and never merged with the discarded one. `status.json` is
the commit point: a notice it names with no request record is never sent, and the
monitor restarts its record and says so (see "Fail closed means alert, not
silence"). An in-flight send stopped during rollback remains uncertain. If source has moved
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
