---
id: A09-P0-002
title: AuditLog table is application-mutable — no Postgres role REVOKE on DELETE/UPDATE
severity: P0
domain: data-integrity / HIPAA §164.312(b)
---

## Issue
HIPAA §164.312(b) requires audit records to be tamper-resistant. QuillMD's
`audit_logs` table has NO database-level immutability — the same Postgres role
the application uses for INSERT can also DELETE and UPDATE. There is also no
append-only schema constraint, no row-version protection, and the existing
INSERT path (`prisma.auditLog.create()`) is the only thing standing between
"truthful audit history" and "an attacker who pwns the web container can
rewrite history".

I searched all of `apps/transcribe-md/src/`, `packages/db/`, `infra/`, and
`scripts/` for any `REVOKE … ON audit_logs` / `GRANT … ON audit_logs` /
trigger / RLS policy. None exists.

## Evidence
1. `packages/db/prisma/schema.prisma:848-896` — `AuditLog` model. No `@@db`
   directive setting up triggers, no companion migration that REVOKEs DELETE
   from the application role. Standard table.
2. `grep -rn "REVOKE\|GRANT.*audit_log" packages/db/ infra/ scripts/` returns
   zero results that target permissions on `audit_logs` (only an enum-value
   migration that contains the word "REVOKED").
3. The web + worker containers connect with the same Postgres role
   (`meddoc`, see `docker-compose.yml`). That role owns the table and has
   default ALL privileges.
4. App code (`apps/transcribe-md/src/lib/audit.ts:161`) uses
   `prisma.auditLog.create({ data: entry as any })` only — application code
   doesn't delete audit rows. But "code doesn't delete" is a code-review
   guarantee, not a HIPAA technical safeguard.

## Risk
P0 — directly violates HIPAA technical safeguards. Attack surfaces:
- A web-container RCE (e.g. via a future Next.js route handler vuln) gives
  the attacker the connection string. From there, `DELETE FROM audit_logs
  WHERE userId = '…'` is one statement and erases the trail of their own
  reconnaissance + PHI exfiltration.
- An accidental `DELETE FROM audit_logs WHERE timestamp < '…'` from an
  ops engineer "cleaning up" the table — Prisma's safety nets only catch
  TypeScript-typed paths.
- The retention sweeps in `scripts/` and `apps/transcribe-md/src/worker/
  cleanup/` legitimately delete from other tables; a future maintainer could
  copy that pattern over to audit logs without realising what it implies.

The pre-pilot context makes this *more* urgent, not less: the BAA + HIPAA
risk-assessment package the pilot will live under expects technical
safeguards in place before any patient touches the system.

## Recommended fix
Add a one-time migration (or a host-side bootstrap SQL) that:

```sql
CREATE ROLE meddoc_audit_writer NOINHERIT LOGIN PASSWORD '…';
GRANT INSERT, SELECT ON audit_logs TO meddoc_audit_writer;
REVOKE DELETE, UPDATE, TRUNCATE ON audit_logs FROM meddoc;
GRANT INSERT, SELECT ON audit_logs TO meddoc;  -- retain insert/read
```

Or, as a lighter-weight first step that doesn't require splitting roles:
```sql
REVOKE DELETE, UPDATE, TRUNCATE ON audit_logs FROM meddoc;
```
…and accept that purges (if they're ever needed) require a separate
DBA-only role. Add a CI check that `\dp audit_logs` in the bootstrap snapshot
shows `r` (SELECT) + `a` (INSERT) only for the application role.

Defence in depth: also add a Postgres trigger that raises on
`UPDATE`/`DELETE` to `audit_logs`. Triggers fire even for superusers under
some configurations, providing belt-and-braces.

For completeness: also REVOKE the equivalent privs on
`rx_warning_overrides` and `account_deletions` — both are clinical/HIPAA
audit records.
