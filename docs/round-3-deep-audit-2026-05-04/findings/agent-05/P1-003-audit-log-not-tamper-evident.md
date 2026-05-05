---
id: A05-P1-003
title: AuditLog is a naive Prisma table — no hash chain, no DB-level write-only role, schema rules unenforced
domain: HIPAA-technical-safeguards
severity: P1
agent: 05
---

## Issue

`packages/db/prisma/schema.prisma:836-895`:

```
// AUDIT LOG — immutable append-only trail (HIPAA §164.312(b))
// Rules:
//  - ONLY insert; never update or delete (enforce via DB role grants in prod)
//  - One row per sensitive action
//  - Captures who / what / when / where (IP + user agent)
//  ...

model AuditLog {
  id String @id @default(cuid())
  ... (no hash, no signature, no previousHash)
}
```

The schema comment promises three integrity controls: (a) insert-only
DB role, (b) tamper-evident chain, (c) immutability. **None of these
are implemented:**

1. **No DB role grants.** `grep -rn "REVOKE\|GRANT" packages/db/
   prisma/migrations/` returns zero matches relating to `audit_logs`.
   The same `meddoc` Postgres user that the app uses for ordinary
   reads has full UPDATE / DELETE on this table.
2. **No append-only trigger.** No
   `BEFORE UPDATE OR DELETE ... RAISE EXCEPTION` defined.
3. **No hash chain.** AuditLog has no `previousRowHash`,
   `signature`, or `merkleRoot` field — a row is a plain Prisma row;
   tampering is undetectable.
4. **No row-level periodic export to immutable storage** (e.g. WORM
   bucket, append-only S3, blockchain-style anchoring).

The audit table is therefore as trustworthy as the database itself —
which means a single compromise of the `meddoc` DB user (already used
by every app container) gives an attacker the ability to silently
alter or delete audit history.

## Evidence

- `schema.prisma:836-895` — naive model.
- `grep "REVOKE\|GRANT" packages/db/prisma/migrations/*.sql` — empty.
- `apps/transcribe-md/src/lib/audit.ts:127-194` — uses standard
  `prisma.auditLog.create({...})`; same prisma client / DB user as the
  rest of the app.
- `apps/transcribe-md/src/app/api/admin/audit-logs/route.ts` reads
  audit; no write path is locked down.

## Risk

- §164.312(c)(1) "Integrity": ePHI must be protected from improper
  alteration. The audit log is itself ePHI-adjacent (it documents PHI
  access). If an attacker tampers with audit rows after exfiltrating
  data, the breach investigation chain-of-custody collapses.
- HHS / OCR enforcement actions have specifically faulted covered
  entities for audit-log mutability (Anthem 2018 settlement explicitly
  required tamper-evident log architecture).

## Recommended fix

Three layers, in order of impact:

1. **DB role separation (immediate, free).** Add a migration:
   ```sql
   CREATE ROLE meddoc_app NOINHERIT;
   GRANT INSERT, SELECT ON audit_logs TO meddoc_app;
   REVOKE UPDATE, DELETE, TRUNCATE ON audit_logs FROM meddoc_app;
   -- DDL and admin-export remain on the migration / owner role.
   ```
   Switch `DATABASE_URL` to `meddoc_app` for app containers; keep the
   admin user only for migrations and offline export.

2. **Hash chain (medium effort).** Add `previousRowHash` and `rowHash`
   columns. On every insert, compute
   `rowHash = sha256(canonical(row) || previousRowHash)` and write it
   in. A daily verification job walks the chain and alarms on
   mismatch. Optionally anchor the daily-final hash on a third-party
   timestamping service (e.g. RFC 3161, OpenTimestamps) for external
   integrity proof.

3. **Periodic export to WORM storage** (long-horizon). Daily ship
   `audit_logs WHERE timestamp > last_export AND timestamp < midnight`
   to a S3 bucket with Object Lock / compliance-mode retention. The
   B2 bucket from Phase 6.2 can be reconfigured for this if a
   separate "audit-immutable" bucket with object-lock is provisioned.

Document the chosen integrity model in `docs/HIPAA_COMPLIANCE.md` —
right now the schema comment and reality diverge.
