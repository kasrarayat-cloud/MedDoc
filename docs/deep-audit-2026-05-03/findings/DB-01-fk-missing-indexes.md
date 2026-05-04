# DB-01 — 12 FK columns missing covering indexes

**Severity:** P2
**Domain:** database / Prisma schema
**Tables:** allergies, medications, patients, documents, hipaa_findings, billing_events, tasks (and 2 unused NextAuth tables)

## What

12 foreign-key columns lack a covering btree index. Each FK join
that references one of these columns triggers a sequential scan on
the child table, getting slower linearly with row count.

```
table          | fk_column         | actively used?
---------------+-------------------+----------------
accounts       | userId            | NO (empty NextAuth-default table)
allergies      | createdById       | YES
allergies      | updatedById       | YES
billing_events | clinicianUserId   | NO (empty placeholder)
billing_events | submittedById     | NO (empty placeholder)
documents      | updatedById       | YES (64 rows currently)
hipaa_findings | resolvedById      | YES (16 rows)
medications    | createdById       | YES (68 rows)
medications    | updatedById       | YES
patients       | createdById       | YES (CRM patients, 4 rows)
sessions       | userId            | NO (empty NextAuth default)
tasks          | createdByUserId   | NO (empty placeholder)
```

## Why it matters

Today the rows are small (68 medications max), so the seq scan is
microseconds. Once any of these tables grows to 10k+ rows (modest
clinic over a year), every "list medications grouped by createdBy"
query becomes O(n × users), measurable in 100s of ms.

The cost of preventing this is one CREATE INDEX per FK; the cost of
fixing it later is the same plus the time pressure of a slow page
in production.

## Proposed remediation

Add 7 `@@index` entries to the relevant Prisma models (skip the 4
empty/unused tables — adding indexes there pays no dividend):

```prisma
model Allergy {
  // ...
  @@index([createdById])
  @@index([updatedById])
}
model Medication {
  // ...
  @@index([createdById])
  @@index([updatedById])
}
model Document {
  // ...
  @@index([updatedById])
}
model HipaaFinding {
  // ...
  @@index([resolvedById])
}
model Patient {
  // ...
  @@index([createdById])
}
```

Then `prisma migrate dev` to generate the SQL with `CREATE INDEX
CONCURRENTLY` (Prisma can't emit CONCURRENTLY automatically — may
need a manual migration with raw SQL).

## Effort

- Schema edit: ~5 min
- Migration generation + review: ~10 min
- Apply in staging: ~2 min (low row counts → fast)
- Apply in production: ~2 min
- Total: ~20 min

## Risk to fix

LOW. `CREATE INDEX CONCURRENTLY` doesn't lock the table. With
row counts < 100 per table, even a non-concurrent index creates
in milliseconds. No application code changes.

## Status

Plan-only (P2). Recommend bundling with a quarterly DB-hygiene PR.
