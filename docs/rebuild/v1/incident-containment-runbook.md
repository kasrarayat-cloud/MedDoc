# QuillMD V1 incident containment runbook (technical part)

Prepared 2026-10-01 for the production design in `production-hosting.md` (AWS, us-east-1). This is the
**technical** containment sequence only. Severity, the HIPAA breach-notification clock, who decides,
who is told, and the legal assessment belong to the owner's incident response plan (security checklist
item J5, counsel); nothing here starts a notification or decides one is not owed.

Every irreversible step (anything that deletes, rotates away or rewrites) runs through
`scripts/run-ruled-mutation.sh --declaration <committed declaration> -- <command>`, as every other
ruled act. Containment that only **stops** something (a unit, a session, an account, a listener rule) is
reversible and is done first; it is recorded in the incident log with UTC times as it happens.

## 0. Preserve before changing

Containment must not destroy the evidence it needs. Before stopping or rotating anything that could
change state:

1. **Snapshot, do not repair.** Create an EBS snapshot of the state volume
   (`/var/lib/quillmd-production`) and a manual RDS snapshot of `quillmd-production`. The host is
   replaced, never repaired in place (`production-hosting.md` section 17); the suspect instance is
   stopped, not terminated, until the evidence is copied.
2. **Journal.** The application journal stays on the host's encrypted root volume (`journald`,
   2 GB / 30 days). Export it from the stopped instance's volume, not from a live session that keeps
   writing to it. Request logs do not exist anywhere by design (capability tokens in URLs).
3. **AWS trail.** CloudTrail (organization trail, backup account bucket with Object Lock), GuardDuty
   findings and AWS Config history are already outside the host; note the time window.
4. **Preservation hold.** If clinical records may be evidence, an administrator places a retention
   hold at `/console/retention/` (scope global, organization, department, patient or document; the
   reference is a SHA-256 of the instruction, never prose). Corrections then keep their prior values
   and file cleanup keeps the bytes (`core/retention.py`). A hold is journaled independently when the
   journal is configured. Redaction and disposition are refused while it applies.

## 1. Stop the bleeding (reversible)

| Threat | Action | Command or place |
| --- | --- | --- |
| One account compromised | Sign the account out everywhere (keeps its access) | `/console/accounts/<id>/detail/` → sessions (`admin_revoke_sessions`) |
| | Suspend the account (signs out and blocks sign-in) | `/console/accounts/<id>/` (`admin_account`, bumps `session_version`) |
| | Lost authenticator of a clinical account | `/console/accounts/<id>/mfa-reset/` (only while `QUILLMD_MFA_REQUIRED_ALL=1`; never for an administrator) |
| Administrator account compromised | Remove its source address from the admin allowlist; revoke its Identity Center session; suspend through a second administrator | ALB listener rule and `/etc/quillmd-production/ingress/admin-allow.conf` (`deny all;` closes the surface) |
| Admin surface exposed | Close it entirely | `admin-allow.conf` → `deny all;`, reload nginx; ALB admin rule → fixed 403 |
| Application suspected | Stop the units, worker first | `systemctl stop quillmd-production-worker.service`, then `quillmd-production-doctor.service`, `quillmd-production-admin.service` |
| Provider spend or misuse | Stop the worker (no provider request leaves without it); queued jobs stay queued and held, nothing is charged | `systemctl stop quillmd-production-worker.service`; `/health/ready/` then reports the stale heartbeat and the outside heartbeat stops pinging, which is expected |
| Host suspected | Stop the instance (do not terminate); replace it from the recorded AMI later | EC2 console / `aws ec2 stop-instances` |
| Data exfiltration path | Detach the instance from the target group; tighten `sg-app` egress | ALB target group; security group |

After the worker stops, confirm with `manage.py configuration_status` (as the application identity,
with the rendered environment) that the single-worker lock reads "not held". That shows no worker
holds the lock, not that no worker process exists: stop the unit, then check.

The outside heartbeat (`quillmd-production-heartbeat.timer`) pings only when both surfaces answer
`/health/` and the doctor surface answers `/health/ready/` with 200. A deliberate containment stop
therefore raises the missed-heartbeat alert at both custodians; say so in the incident channel rather
than silencing the check.

## 2. Rotate what may be known (declared acts)

Use `key-rotation-runbook.md`. Order for a host or application compromise: the Django secret key (it
also signs sessions, usage quotes and checkout tokens, so rotating it signs everyone out), the
runtime role password, provider keys (Anthropic, Deepgram, Stripe, Resend), the heartbeat URL, then
the disposition journal writer key if the host held it. KMS keys are not rotated by hand for an
incident; the question for KMS is who could call `Decrypt`, answered from CloudTrail.

## 3. Restore, if data is damaged

Never restore over the live resources. Follow `cutover-plan.md`'s restore section: new RDS instance
and state volume, `QUILLMD_RESTORE_QUARANTINE=1` with a new `QUILLMD_RESTORE_INSTANCE_ID`, replay the
independent journal at `/console/disposition-execution/` (it re-imports every journaled disposition,
preservation hold and release and, since the 0033 release, re-applies every journaled redaction in
journal order), then `manage.py restore_admission ... --check-only`, then admission. Restored rows are
never deleted by the replay except the clinical content a journaled redaction had already removed.

`manage.py backup_exposure_ledger --checkpoint <file> --recovery-points <inventory> --output <new file>`
lists which recovery points still hold a disposed or redacted document; restoring any of them
re-applies those acts before the target is admitted.

## 4. Return to service

1. Replacement host from the recorded AMI and release artifact (`bootstrap-host.sh
   --existing-state-volume`), launcher proofs green.
2. Old host's units stopped (worker first) before the new host's units start.
3. `GET /health/` 200 on both surfaces and `GET /health/ready/` 200 on the doctor surface (from the
   host), heartbeat pings resume.
4. A synthetic smoke on the smoke account only. A real doctor's visit is never a smoke target.
5. Record what changed, with times, in the incident log and the deploy declaration.

## What this runbook does not do

- No breach determination, notification, or communication to doctors or patients.
- No deletion of data, backups or logs. Backups and the journal are evidence.
- No outside service is configured from here (Healthchecks.io, AWS alarms stay as configured).
