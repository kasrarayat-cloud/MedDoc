-- ============================================================================
-- Multi-tenancy: Phase 1
-- ----------------------------------------------------------------------------
-- Adds the `practices` table + `practiceId` FK to 5 tenant-scoped tables.
-- Existing data is backfilled into a single default practice (id='clinic_main')
-- so the app has exactly one tenant until we explicitly onboard more.
--
-- Order of operations (critical):
--   1. Create `practices` table + indexes
--   2. Seed the default practice row
--   3. Add `practiceId` columns as NULLABLE (otherwise the ALTER fails on rows)
--   4. Backfill every row → 'clinic_main'
--   5. Tighten columns to NOT NULL
--   6. Add FK constraints + indexes
-- Prisma's auto-generated SQL did steps 3+5 in one step with NOT NULL, which
-- fails on non-empty tables. This hand-edited version splits them.
-- ============================================================================

-- 1. Practices table
CREATE TABLE "practices" (
    "id" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "address" TEXT,
    "phone" TEXT,
    "isActive" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "practices_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "practices_slug_key" ON "practices"("slug");
CREATE INDEX "practices_slug_idx" ON "practices"("slug");

-- 2. Seed default practice. Fixed ID so every environment references the
--    same tenant for pre-multi-tenancy data.
INSERT INTO "practices" ("id", "name", "slug", "isActive", "createdAt", "updatedAt")
VALUES ('clinic_main', 'Main Clinic', 'main-clinic', true, NOW(), NOW());

-- 3. Add nullable practiceId columns (cannot go straight to NOT NULL on
--    existing rows).
ALTER TABLE "users" ADD COLUMN "practiceId" TEXT;
ALTER TABLE "patients" ADD COLUMN "practiceId" TEXT;
ALTER TABLE "audit_logs" ADD COLUMN "practiceId" TEXT;
ALTER TABLE "session_logs" ADD COLUMN "practiceId" TEXT;
ALTER TABLE "api_usage" ADD COLUMN "practiceId" TEXT;

-- 4. Backfill: every pre-existing row belongs to Main Clinic.
UPDATE "users"        SET "practiceId" = 'clinic_main' WHERE "practiceId" IS NULL;
UPDATE "patients"     SET "practiceId" = 'clinic_main' WHERE "practiceId" IS NULL;
UPDATE "audit_logs"   SET "practiceId" = 'clinic_main' WHERE "practiceId" IS NULL;
UPDATE "session_logs" SET "practiceId" = 'clinic_main' WHERE "practiceId" IS NULL;
UPDATE "api_usage"    SET "practiceId" = 'clinic_main' WHERE "practiceId" IS NULL;

-- 5. Tighten to NOT NULL now that every row has a value.
ALTER TABLE "users"        ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "patients"     ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "audit_logs"   ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "session_logs" ALTER COLUMN "practiceId" SET NOT NULL;
ALTER TABLE "api_usage"    ALTER COLUMN "practiceId" SET NOT NULL;

-- 6. Indexes for per-tenant query patterns.
CREATE INDEX "api_usage_practiceId_idx"    ON "api_usage"("practiceId");
CREATE INDEX "audit_logs_practiceId_idx"   ON "audit_logs"("practiceId");
CREATE INDEX "patients_practiceId_idx"     ON "patients"("practiceId");
CREATE INDEX "session_logs_practiceId_idx" ON "session_logs"("practiceId");
CREATE INDEX "users_practiceId_idx"        ON "users"("practiceId");

-- 7. Foreign-key constraints. ON DELETE RESTRICT so you can't accidentally
--    drop a practice that still owns data.
ALTER TABLE "users"        ADD CONSTRAINT "users_practiceId_fkey"        FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "patients"     ADD CONSTRAINT "patients_practiceId_fkey"     FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "audit_logs"   ADD CONSTRAINT "audit_logs_practiceId_fkey"   FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "session_logs" ADD CONSTRAINT "session_logs_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
ALTER TABLE "api_usage"    ADD CONSTRAINT "api_usage_practiceId_fkey"    FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
