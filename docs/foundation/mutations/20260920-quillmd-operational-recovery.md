# Declaration — operational recovery and one authorized alert

The owner authorized this milestone on 2026-09-20: resolve the twelve skipped
checks, prepare offsite recovery without purchases, configure backup alerts to
kasra.rayat@gmail.com and send one clearly labelled nonclinical simulated-failure
test. Preserve application release `8aa1d1d4efe090d6f0e6e1bf7d594375ddca9940`.

## Before any act

Baseline `rebuild/.runtime/operational-recovery-20260920/baseline.json` verifies
doctor/admin HTTP health and the separate PID-bound worker startup proof. All
three run 8aa1d1d4 under quillmd-app, PIDs 2964608/2964609/2964610. Public app/admin
are 503, marketing 200, retired pro 410. `data-before.json` records read-only
table fingerprints and referenced file hashes. Latest backup is authenticated;
the previous isolated local restore remains valid mechanism evidence. No new
restore over the running database or repeat provider/Word/Stripe campaign.

## Exact permitted delta

After peer review, focused tests, PR merge and exact merge-commit CI, fast-forward
the permanent main tree. The application runtime, its environment/release stamp,
all existing application/backup units, configuration, processes and stored rows
remain unchanged. Only new operations files, tests, CI history fetching and
documentation change. No application restart or database migration is required.

Create only these additional project resources:

- `.runtime/backup-secrets/backup-alerts.json`, claude0600, exact approved recipient,
  synthetic-only flag and fixed test authorization `20260920-operation-recovery`;
  it contains no provider credential. Reuse the verified Resend transport/key and
  sender from the existing protected application configuration without copying or
  printing secrets.
- `.runtime/backup-alerts/`, claude0700, private immutable send-attempt/result and
  monitor-status evidence. Preserve uncertain results; no blind retries.
- `quillmd-fresh-backup-alerts.service` and `.timer` in `/etc/systemd/system`,
  root0644, exact reviewed bytes. Five-minute local monitoring, bounded resource
  usage, no privilege escalation, write access limited to its evidence directory.
  Enable only this new timer after a successful healthy installed-service check.

Execute exactly one authorized test through `backup_alerts.py test`. Use the real
existing Resend API; never insert clinical data, credentials, private URLs or
tokens. The test simulates the failure condition only in its separate alert path;
it must not alter backup success/failure records, interrupt capture, or disable
the existing backup schedule. Repeating the command may verify idempotency but
must not issue another provider send. A bounded read of the corresponding provider
message may establish provider delivery status if the existing key permits it.
Provider acceptance, delivery and human inbox confirmation remain separate facts.

Missing/failed/stale backup and monitor configuration are redacted actionable
local states. Local email does not establish external detection of complete VPS
failure. No outside monitor account or paid subscription is provisioned.

## Rollback and preservation judgment

`install_backup_alerts.py --action disable` disables only the new timer and stops
only its service, then verifies inactivity. Retain configuration, units, send
receipts and failures. An interrupted send remains uncertain and cannot be
retried automatically. Never stop or reconfigure the application, real backup,
database, shared SSH/nginx/systemd policies or other projects. No global cleanup.

Compare the full existing unit/configuration/process baseline before/after the
scoped installer; compare backup monitor records unchanged; compare data/file
fingerprints and independent doctor/admin/worker revisions. Any delta outside
the declared new alert resources is a finding. Keep administrator MFA, inactive
reviewer access, public maintenance and synthetic-only operation intact.

No approved B2 config exists at declaration time. Offsite upload/restore and
independent key custody remain pending. This declaration neither purchases nor
creates a bucket, changes retention, deletes plaintext rollback copies, reboots
the host, fabricates billing evidence nor grants external reviewer access.
