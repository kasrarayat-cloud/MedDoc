-- Phase 7B — HIPAA findings table for /admin/hipaa
-- ----------------------------------------------------------------------------
-- Replaces the hardcoded findings array in dashboard-data.ts:getHipaaState()
-- with a real table the admin team can resolve/reopen via /admin/hipaa.
-- See packages/db/prisma/schema.prisma model HipaaFinding for the
-- full lifecycle commentary.

-- AlterEnum: HIPAA_FINDING_RESOLVED + HIPAA_FINDING_REOPENED for the
-- workflow on /admin/hipaa. Two values must be added in separate
-- statements (PG limitation acknowledged in prior migrations).
ALTER TYPE "AuditAction" ADD VALUE 'HIPAA_FINDING_RESOLVED';
ALTER TYPE "AuditAction" ADD VALUE 'HIPAA_FINDING_REOPENED';

-- CreateTable
CREATE TABLE "hipaa_findings" (
    "id" TEXT NOT NULL,
    "control" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "detail" TEXT,
    "status" TEXT NOT NULL DEFAULT 'open',
    "resolvedAt" TIMESTAMPTZ(6),
    "resolvedById" TEXT,
    "resolvedByEmail" TEXT,
    "resolutionNote" TEXT,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "hipaa_findings_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "hipaa_findings_status_severity_idx" ON "hipaa_findings"("status", "severity");

-- CreateIndex
CREATE INDEX "hipaa_findings_resolvedAt_idx" ON "hipaa_findings"("resolvedAt");

-- AddForeignKey
ALTER TABLE "hipaa_findings" ADD CONSTRAINT "hipaa_findings_resolvedById_fkey" FOREIGN KEY ("resolvedById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
