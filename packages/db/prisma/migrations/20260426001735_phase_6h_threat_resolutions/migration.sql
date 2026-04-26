
-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "AuditAction" ADD VALUE 'THREAT_INVESTIGATED';
ALTER TYPE "AuditAction" ADD VALUE 'THREAT_RESOLVED';
ALTER TYPE "AuditAction" ADD VALUE 'THREAT_DISMISSED_FALSE_POSITIVE';

-- CreateTable
CREATE TABLE "threat_resolutions" (
    "id" TEXT NOT NULL,
    "threatId" TEXT NOT NULL,
    "resolutionKind" TEXT NOT NULL,
    "resolvedAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "resolvedById" TEXT,
    "resolvedByEmail" TEXT,
    "note" TEXT,
    "silencePattern" JSONB,

    CONSTRAINT "threat_resolutions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "threat_resolutions_threatId_key" ON "threat_resolutions"("threatId");

-- CreateIndex
CREATE INDEX "threat_resolutions_resolvedAt_idx" ON "threat_resolutions"("resolvedAt");

-- CreateIndex
CREATE INDEX "threat_resolutions_resolvedById_idx" ON "threat_resolutions"("resolvedById");

-- CreateIndex
CREATE INDEX "threat_resolutions_resolutionKind_idx" ON "threat_resolutions"("resolutionKind");

-- AddForeignKey
ALTER TABLE "threat_resolutions" ADD CONSTRAINT "threat_resolutions_resolvedById_fkey" FOREIGN KEY ("resolvedById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

