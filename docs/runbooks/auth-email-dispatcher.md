# Authentication email dispatcher

Status: TECHNICAL CONTRACT — production authority and provider approval pending
Owner: Operations (named human owner required before production enablement)

This service delivers password-reset, email-verification, account-exists, and
email-change messages from the durable authentication-email outbox. It does not
make production email safe by itself. Provider agreement, verified sending
domain, restore evidence, exact-head review, monitoring ownership, and release
approval remain required gates.

## Security boundary

- `auth-email-dispatcher` imports no wholesale `.env` and has no public port.
- It connects only as `meddoc_auth_email_dispatcher`, whose sole membership is
  the NOLOGIN/NOINHERIT `quillmd_auth_email_dispatcher` boundary role.
- It receives only its database DSN, the exact physician-app URL, and verified
  Resend sender configuration. Runtime, migration-owner, release-control,
  audit-dispatcher, session, AI, object-storage, and queue credentials are
  explicitly absent.
- The database boundary is procedure-only. Do not grant direct table access or
  reuse the ordinary runtime or migration-owner DSN in this container.
- Outbox logs, alerts, and evidence must never contain recipient addresses,
  bearer links, raw tokens, provider identifiers, or driver error text.
- Email SHA-256 bindings are pseudonymous sensitive data, not de-identified
  data. They remain encrypted and procedure-only and follow the bounded purge
  schedule.

## Deployment gate

1. Prove backup restoration in a disposable environment. Keep public auth-email
   delivery disabled until that evidence and production authority are present.
2. Generate a credential distinct from every other database credential and
   store it as `DB_AUTH_EMAIL_DISPATCHER_PASSWORD` in the approved secret store.
   Never put it on a command line, in shell history, or in release evidence.
3. On a fresh database, the Postgres entrypoint creates the exact group/login
   pair. An existing production volume does not rerun entrypoint initialization;
   a database administrator must apply the reviewed equivalent of
   `infra/postgres/init-template-twin-roles.sh` before the outbox migration.
4. Verify role attributes and exact membership using metadata-only queries.
   Evidence may record role names and booleans, but not connection strings:

   ```sql
   SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole,
          rolinherit, rolreplication, rolbypassrls
   FROM pg_roles
   WHERE rolname IN ('quillmd_auth_email_dispatcher',
                     'meddoc_auth_email_dispatcher')
   ORDER BY rolname;

   SELECT member_role.rolname AS member_role,
          granted_role.rolname AS granted_role
   FROM pg_auth_members membership
   JOIN pg_roles member_role ON member_role.oid = membership.member
   JOIN pg_roles granted_role ON granted_role.oid = membership.roleid
   WHERE member_role.rolname IN ('quillmd_auth_email_dispatcher',
                                 'meddoc_auth_email_dispatcher')
   ORDER BY member_role.rolname, granted_role.rolname;
   ```

   The group must be NOLOGIN/NOINHERIT with no memberships. The login must be
   LOGIN/INHERIT, non-privileged, and have exactly the one expected membership.

5. Apply the reviewed migration with the verified migrator. Its transaction
   must commit before the dispatcher starts; do not hot-grant around a failure.
6. Configure the exact `https://app.quillmd.com` origin, verified sender,
   monitored reply-to mailbox, and `RESEND_FROM_VERIFIED=true`. Confirm the
   provider agreement and data-use configuration before any non-synthetic use.
7. Validate the resolved configuration without rendering it into evidence,
   then start only the isolated service:

   ```bash
   docker compose config --quiet
   docker compose up -d --no-deps auth-email-dispatcher
   docker compose ps auth-email-dispatcher
   ```

8. Use reserved synthetic identities to verify each message purpose, provider
   receipt completion, unknown-address nondisclosure, replay rejection, and
   link origin. Never use a physician or patient identity as a smoke test.

## Liveness and alerts

After startup gates, a successful empty drain, and before/after each claimed
item, the process refreshes `/tmp/auth-email-dispatcher-heartbeat`. Compose marks
it unhealthy if the file is missing or at least 90 seconds stale. The
application's provider decision wait is bounded at 30 seconds and every request
uses a stable, non-identifying provider idempotency key. A timeout or missing
provider receipt becomes terminal `AMBIGUOUS`; it is never auto-redelivered.
Missing health, startup failure, or a stale heartbeat is a page-worthy
authentication incident.

Operations must also alert on:

- oldest pending/claimed age above five minutes;
- any increase in terminal failures or provider-ambiguity outcomes;
- expired prepared claim leases or purge failure;
- verified-sender/domain revocation or provider rejection;
- outbox growth without matching hashed provider receipts.

Only PHI-free aggregates may enter monitoring evidence. The dispatcher boundary
may call this reviewed aggregate function; it must not select the table:

```sql
SELECT "pending", "claimed", "ambiguous", "oldestPendingSeconds"
FROM public.auth_email_health();
```

## Fail-closed rollback and recovery

If delivery, ownership, provider outcome, or monitoring becomes ambiguous:

1. Stop the dispatcher immediately:

   ```bash
   docker compose stop auth-email-dispatcher
   ```

2. Set `RESEND_FROM_VERIFIED=false` in protected production configuration and
   recreate the affected application processes so new email-dependent actions
   fail closed. Do not delete outbox rows or tokens and do not roll the schema
   backward.
3. Verify with reserved synthetic identities that no new bearer link is sent.
   Preserve aggregate evidence and follow the authentication incident runbook.
4. If credential exposure is suspected, rotate only the dedicated login
   credential through the approved secret channel and recreate the dispatcher.
   Re-verify exact role attributes and membership; never substitute a broader
   DSN.
5. Resume only after the provider outcome is reconciled, the exact-head fix is
   accepted, the service is healthy, and Operations explicitly owns the alert
   window. A reviewed new user request supersedes old authority; never retry an
   ambiguous prepared row or edit it directly.
