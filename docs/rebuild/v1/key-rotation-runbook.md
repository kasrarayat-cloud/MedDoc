# QuillMD V1 key and credential rotation runbook

Prepared 2026-10-01 for the production design in `production-hosting.md` (sections 7, 11 and 14) and
security checklist item I3. Every rotation is a **declared act**: a committed declaration names the
secret, the reason (schedule or incident), the expected effect and the verification, and the act runs
through `scripts/run-ruled-mutation.sh --declaration <committed file> -- <command>` where it changes
production state. Values are never printed, pasted into tickets or written outside the paths named here.

No rotation period is set here: the schedule (next-due dates) is the owner's, recorded in the rotation
log the checklist asks for. This runbook says **how**, and what each rotation breaks.

## Where each secret lives

| Secret | Lives in | Read by | Rotation effect |
| --- | --- | --- | --- |
| `QUILLMD_SECRET_KEY` | Secrets Manager `quillmd-production/application-environment` (rendered to `/run/quillmd-production/application.env`) | doctor, admin, worker | every session ends (the session hash is keyed on it); open usage quotes, checkout tokens and password-recovery links (all signed with it) stop verifying; email-verification and invitation links are random tokens stored as hashes and keep working; no `SECRET_KEY_FALLBACKS` is configured |
| `QUILLMD_DB_PASSWORD` (runtime role `quillmd_production_runtime`) | same secret; role password in RDS | doctor, admin, worker | units must restart with the new value after the role changes |
| migrator and backup role passwords | `/etc/quillmd-production/operator/role-bootstrap.json` and `database-roles.json` (root 0600, written by the role tool for a declared act and shredded after); Secrets Manager `quillmd-production/database-roles` | operators during declared acts | none for the application |
| RDS master | RDS-managed secret | break-glass and declared role acts | managed by RDS |
| `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY` | application secret | worker | in-flight provider requests finish on the old key; queued jobs wait for the restart |
| `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | application secret | doctor, admin | rotate the webhook signing secret in Stripe and here together, or signed events are refused (and retried by Stripe) until both match |
| `RESEND_API_KEY` | application secret | doctor, admin | verification, invitation and recovery mail fails until restarted |
| heartbeat URL | Secrets Manager `quillmd-production/heartbeat-url`, `/etc/quillmd-production/operator/heartbeat-url` (LoadCredential) | `quillmd-production-heartbeat.service` | a new check in Healthchecks.io; retire the old one only after the new one has pinged |
| ALB-to-host TLS key | `/etc/quillmd-production/ingress/target.key` and `.crt` (self-signed, 825 days, `bootstrap-host.sh`) | nginx | the ALB does not validate target certificates; replace before expiry and reload nginx |
| Public TLS | ACM on the ALB | ALB | renewed by ACM; nothing on the host |
| KMS keys (`alias/quillmd-production-data`, `-secrets`, `alias/quillmd-backup-vault`) | KMS | AWS services | automatic yearly rotation (checklist B7); never rotated by hand |
| Logical backup encryption key (Fernet) | backup account Secrets Manager plus the custodians' sealed copy (section 14) | backup and restore tools | new backups use the new key; **every older backup still needs the old key**: keep it for the life of those backups |
| Disposition journal writer key and the authority/checkpoint public keys | not part of the production environment today: `DISPOSITION_*` names are absent from `ops.deployment_profile.ENVIRONMENT_NAMES`, so journal-dependent acts (disposition, redaction) cannot be enabled in production until a reviewed change adds them | — | see the note at the end |

## Procedure: a secret in the application environment

Applies to `QUILLMD_SECRET_KEY`, provider keys, Stripe secrets, Resend.

1. Declaration committed (which name, why, expected effect from the table above).
2. Create the new value at its issuer (provider console, Stripe, Resend) or generate it
   (`python3 -c "import secrets; print(secrets.token_urlsafe(64))"` for the Django key, typed into the
   secret directly, never into a shell history file).
3. Update the JSON in `quillmd-production/application-environment` (only names in
   `ops.deployment_profile.ENVIRONMENT_NAMES` are accepted when it is rendered).
4. `systemctl restart quillmd-production-environment.service`, then restart
   `quillmd-production-worker.service` (stop first, so no request is sent while the doctor surface runs
   on the old key), `quillmd-production-doctor.service` and `quillmd-production-admin.service`.
5. Verify: the launcher proofs are green; `GET /health/` 200 on both surfaces and `GET /health/ready/`
   200 from the host; `manage.py configuration_status` shows the expected shapes (it prints shapes,
   never values); a synthetic smoke on the smoke account only.
6. Revoke the old value at its issuer once step 5 passed. Record the time in the rotation log.

## Procedure: database role passwords

The role tool sets passwords from its credential file and creates new random ones only when that file
is absent (`ops/production_database_roles.py`, `role_credentials`). A rotation is therefore:

1. Declaration committed with the action `apply` (and `verify`).
2. Move the existing `/etc/quillmd-production/operator/role-bootstrap.json` and `database-roles.json`
   aside (root only).
3. `python3 ops/database_roles.py apply --profile production` through `run-ruled-mutation.sh`: it
   connects as the RDS master over `verify-full`, sets new passwords for the runtime, migrator and
   backup roles, re-verifies the role policy and each role's authentication, and writes new files.
4. Put the new runtime password into `quillmd-production/application-environment`
   (`QUILLMD_DB_PASSWORD`) and the migrator/backup pair into `quillmd-production/database-roles`;
   restart the environment unit and the units as above, worker first.
5. `python3 ops/database_roles.py verify --profile production`; then shred the moved-aside files and,
   after the act, the operator copies.

This production path is prepared, not yet exercised on the real target
(`production-hosting.md` section 4, "must be verified on the actual target"): rehearse it on a drill
instance before relying on it in an incident.

## After a compromise

Rotate in this order: Django secret key (ends every session), runtime role password, provider keys,
Stripe and Resend, heartbeat URL, then any operator credential the host held. Administrators re-enrol
nothing (TOTP devices are database rows, not host secrets) unless the database itself is suspected; then
every clinical account can be reset with `/console/accounts/<id>/mfa-reset/` while
`QUILLMD_MFA_REQUIRED_ALL=1`, and administrator authenticators through the bootstrap path, which is an
open item (inventory 7A F2: no audited second-administrator or administrator-MFA reset exists yet).

## Note: journal keys

The independent journal (holds, releases, dispositions, redactions) is configured by `DISPOSITION_*`
settings that the production environment cannot carry today. Before it is enabled: the writer's
private key must live where only the application identity can read it, the checkpoint signer and the
policy authority keys must be held by different custodians, and rotating the writer key must append
the new public key to `DISPOSITION_JOURNAL_KEYS` (the chain keeps verifying old entries by their
`key_id`) rather than replace it. That design and its rotation test are owner and engineering work
not done here.
