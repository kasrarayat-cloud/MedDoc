# Private operational readiness and response

This supplements the existing recovery and alert runbooks for the synthetic
QuillMD application. Use the permanent `/opt/meddoc-pro` tree for installed
commands and the latest runtime checkpoint for exact deployed revisions.
Preserve public maintenance, MFA, inactive reviewer access, keys, templates,
finalized records, balances and historical evidence. No procedure here authorizes
a public release, provider replay, retention change or restore over live data.

## Read the actual operational state

As the authorized `claude` operator, from `/opt/meddoc-pro`:

```bash
rebuild/.venv/bin/python -B rebuild/ops/backup_alerts.py status
rebuild/.venv/bin/python -B rebuild/ops/scheduled_backup.py status
rebuild/.venv/bin/python -B rebuild/ops/automatic_offsite.py inspect
systemctl list-timers --all quillmd-fresh-backup.timer quillmd-fresh-offsite.timer quillmd-fresh-backup-alerts.timer --no-pager
```

These commands make no provider request. The protected operator status is the
administrative operational surface; no browser dashboard or application access
to backup keys is added. It reports the latest local capture, complete remote
set, matching readback and isolated restore separately, including restore key
source. The next permanent timer time is a future due time, not proof of a
successful firing. A disabled timer exposes its current reason. Policy eligibility,
observation age/expiry and dated local download/request reservations are separate
fields. Reservations are conservative accounting entries, not measured account-wide
provider usage; a previous day's entries do not become today's usage.

The read-only status rechecks local and remote freshness. A previously healthy
monitor tick cannot hide a newly stale local backup. Inspect protected immutable
attempt records for the exact failure stage. Unknown or malformed fields and raw
provider errors are never an acceptable status source.

## Backup, upload and allowance failures

1. Record the UTC time, condition, run ID and exact installed operations revision
   in a new protected incident directory. Read the affected systemd result and
   its latest immutable attempt. Do not erase evidence or reset failure just to
   make a unit green.
2. For `backup_stale`, missing backup or a failed local capture, inspect the
   local timer and free space. Authenticate the selected existing manifest and
   retain the last complete set. Repair the measured cause before one bounded
   capture through the existing declared service procedure.
3. For failed/partial upload, retain every object and journal. No completion
   manifest means no newly complete set. A timeout after write is uncertain:
   the existing engine inventories and authenticates its recorded objects before
   reuse. Do not blindly repeat PUT, delete a version, or publish a manifest by
   hand. An overlapping invocation must lose the existing lock without replacing
   the holder's status.
4. For policy expiry, unsupported account-wide capacity or exhausted allowance,
   keep recurrence disabled. Obtain the exact missing observation/allocation and
   refresh the protected policy through its existing validation and activation
   gate. Include retained versions and unfinished parts. Do not substitute a
   prefix inventory or rounded daily dashboard value for account-wide bytes,
   reset the shared reservation ledger, broaden a key, increase a cap or prune.
5. Once the cause is repaired and the installed guard passes, use the existing
   scoped offsite installer through a matching committed declaration. It requires
   a real authenticated controlled service run and readback before timer enablement.
   A historical no-op cannot qualify activation. Check enabled/active and next
   due time separately; do not call a manual start a daily scheduled firing.

The runtime key cannot delete old versions. Capacity refusal is the intended
boundary until a separately authorized retention or capacity decision exists.
The installed monitor routes actionable failures to the existing approved email
recipient with the existing incident cooldown; uncertain sends are not retried.

## Key recovery and cleanup

Use [recovery-kit.md](recovery-kit.md) and the fixed selected backup identity.
An independently retrieved returned key must pass `recovery_kit.py verify-returned`
before the bounded download-only procedure. The returned key must be the sole
Fernet source. Retrieve remote encrypted objects using the existing scoped B2
identity; never substitute local plaintext or fall back to the working key.
The selected manifest determines actual tables, row hashes, files and invariants.

The restore creates its own labeled PostgreSQL container with no network, ports
or workers and uses tmpfs without swap. A completed data comparison and completed
cleanup are distinct facts: cleanup failure now marks the drill incomplete and
returns failure even when data comparison succeeded. Preserve `verification.json`,
including `data_verification_complete`, `cleanup_failed`, `container_retained`
and the original failure stage. Never remove an unrelated container to clear it.
Retry cleanup only after the existing ownership label, exact name, no-network and
no-port checks pass; then independently confirm absence and append evidence.

After the actual returned-key proof and evidence are retained, remove only the
temporary server return copy, verified disposable recovery scratch and exact
temporary SSH grant through the established cleanup process. The owner can then
remove the desktop temporary return file. Keep Windows vault entries, working
keys, original backup history and all nonsecret proof. Windows account/computer
custody does not establish offline, PC-loss, LUKS or whole-host recovery.

## Pause processing, recover administrator access, and roll back

For a queue/provider incident, record in-flight job IDs and financial states before
any service action. Use a newly scoped committed declaration and the existing
service-control mechanism to stop only the private worker if a pause is needed.
The worker handles SIGTERM by completing its current request before taking another
job; the installed unit bounds stop at 150 seconds. An interrupted/uncertain job
goes to evidence-based reconciliation, never automatic provider replay. Pausing
the worker alone does not prevent new submissions from queuing; use the scoped
private application stop procedure as well when submissions must be paused.
Public maintenance stays in place. Preserve queue rows, receipts, held funds and
source files. Resume only after the failure cause and outstanding jobs are judged.

For a forgotten administrator password with the authenticator available, use the
existing recovery flow. A valid confirmed MFA code is still required, recovery
does not sign the administrator in, and old sessions/used tokens become invalid.
Suspension and reactivation must not revive previously authenticated sessions or
old recovery links. For a lost authenticator, establish identity through an
already trusted independent channel, record the account UUID and approval, revoke
sessions, then supervise replacement enrollment through a reviewed declared act.
An email request alone is insufficient; there is no public email-only MFA reset.
Do not disable MFA globally, export an enrollment secret or mutate a live account
as a qualification test.

Use the exact activation receipt for code rollback; do not reset main or reverse
data migrations indiscriminately. The current approach stops private services on
failed activation, retains stopped-state fingerprints and prefers a cited forward
repair. A compatible security/data invariant may remain installed through code
rollback. An offsite-only rollback uses the scoped `install_offsite_schedule.py`
disable action through a declaration bound to the exact installed source; it
retains units, keys and evidence and does not need a working B2 credential or
eligible policy. Documentation-only edits require no application restart.

## Outside-host integration: prepared, inactive until authorized handoff

No `external-monitor.json` was present at this milestone's inspection. VPS-local
checks cannot detect disappearance of their own host from outside. The optional
adapter now consumes the existing protected contract when an authorized account
administrator provides a check already under their control:

```json
{"version":1,"provider":"healthchecks.io","check_url":"https://hc-ping.com/CHECK-UUID","owner_approval_reference":"RECORDED-APPROVAL-REFERENCE","synthetic_only":true}
```

Place it at `rebuild/.runtime/backup-secrets/external-monitor.json` as a regular
single-link `claude` file mode0600 under mode0700. The approval reference must be
12–256 characters. The actual lowercase UUID URL is secret; do not put it in
chat, Git or screenshots. No management API key, new subscription or provisioning
permission is required or presumed.

The approved check should use period five minutes and grace ten minutes with the
existing authorized owner recipient. The monitor sends a success-only ping when
all local/offsite health requirements pass. Configuration absence sends nothing;
status inspection sends nothing. Transport permits only the exact `hc-ping.com`
HTTPS UUID endpoint, disables redirects/proxy/netrc and implicit retry, sends no
clinical body and reads at most three bytes. It requires exact `OK`: the provider
can return HTTP200 for a missing or rate-limited check too, so status200 alone is
not acceptance. See the [provider's ping contract](https://healthchecks.io/docs/http_api/).

A durable reservation precedes each attempt and blocks repeat pings within five
minutes. A later scheduled period is a fresh heartbeat; uncertain attempts are
not immediately replayed. Receipts expose no URL or response body. A ping receipt
does not establish outage detection. Before claiming outside-host coverage, use
an already authorized isolated check to observe a missed heartbeat, provider alert
generation and delivery independently; human inbox confirmation remains a separate
event. The status deliberately keeps outside-host verification false until such
evidence exists. Do not stop the real VPS or disable real backups for that test.

The earlier one authorized backup email was provider-accepted. Its delivery-status
request returned401, so provider delivery remains unverified and human inbox
confirmation remains pending. Do not resend it to replace that missing confirmation.

## Exercised evidence and its limits

Protected evidence is under
`rebuild/.runtime/private-readiness-20260920/monitoring/`. It records live read-only
installed unit/status observations separately from isolated fixture fault injection.
The original cleanup and stale-status counterexamples were reproduced against
the pre-change source, then passed against the repair. The focused failure matrix
exercises stale/missing local backup, partial/uncertain upload, overlap, expired
policy, capacity refusal, unusable key and cleanup failure without provider calls.
The pause rehearsal drives the actual worker handler with a synthetic in-flight
request; rollback rehearsal uses the existing fake-systemd boundary tests. Admin
recovery uses the separate isolated PostgreSQL security regression evidence.
These are internal engineering exercises, not an independent penetration test,
human acceptance, a real missed-heartbeat incident or whole-host recovery.
