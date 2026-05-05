---
id: A09-P3-001
title: mfaBackupCodes column was DROP+ADD'd in a single migration — destructive even when comment claims zero rows
severity: P3
domain: migration-safety / convention
---

## Issue
Migration `20260423024335_app_redesign_v1_new_fields` does:

```sql
ALTER TABLE "users" ADD COLUMN     "clinicName" TEXT,
ADD COLUMN     "npi" TEXT,
ADD COLUMN     "specialty" TEXT,
ADD COLUMN     "timeZone" TEXT DEFAULT 'America/Los_Angeles',
DROP COLUMN "mfaBackupCodes",
ADD COLUMN     "mfaBackupCodes" TEXT[] DEFAULT ARRAY[]::TEXT[];
```

The comment block says: "mfaBackupCodes was confirmed empty (0 non-null
rows in `users`) before the DROP+ADD, so no data loss." That's true for
the production database at the moment the migration was applied, but
breaks two conventions:

1. **No expand/contract**. A safe rename/retype pattern would be:
   - Migration N: ADD COLUMN `mfaBackupCodesV2 TEXT[]`. App writes both
     columns, reads the new one with fallback.
   - Migration N+1 (after a deploy): DROP COLUMN `mfaBackupCodes`.

2. **Pre-deploy data check is a manual, fragile step**. If a future
   migration follows this template ("we checked, it's empty, just
   DROP+ADD") and the check is wrong, data is silently lost. CI doesn't
   guard against this.

The other DROP_COLUMN cases in `migrations/20260422100000_drop_t_m24_
templates/migration.sql` (templateId, filledTemplate) carry similar risk
but those are inside a DROP TABLE step — fine.

## Evidence
`packages/db/prisma/migrations/20260423024335_app_redesign_v1_new_fields/
migration.sql:13-14`:
```sql
DROP COLUMN "mfaBackupCodes",
ADD COLUMN     "mfaBackupCodes" TEXT[] DEFAULT ARRAY[]::TEXT[];
```

## Risk
P3 — pre-pilot, the column was demonstrably empty, so this specific
migration didn't lose data. The risk is forward-looking: if the
migration-review process accepts this pattern, the next time a column is
type-changed the operator may apply the same approach and lose data
without the empty-table reprieve.

## Recommended fix
Document a rule in the migration runbook: **never DROP+ADD the same column
in one migration**. Always:

1. ADD the new column with the new shape.
2. Backfill via a `db-migrate` profile script.
3. Switch app writes to the new column.
4. Switch app reads to the new column with fallback.
5. After a full release cycle, DROP the old column.

For Prisma specifically: the schema rename annotation
(`@map("oldName")` → `@map("newName")`) doesn't issue DROP+ADD; it issues
RENAME. If the type also changes, the safe path is the 5-step expand/
contract above, with each step a separate migration.

Add a CI check (a simple grep) that fails on:
```
git diff packages/db/prisma/migrations/ | grep -E "DROP COLUMN.*\".*\".*ADD COLUMN.*\".*\""
```
…matching the same column name in the same file, so a future
DROP+ADD-same-column gets caught at PR time.
