
-- AlterEnum
-- This migration adds more than one value to an enum.
-- With PostgreSQL versions 11 and earlier, this is not possible
-- in a single migration. This can be worked around by creating
-- multiple migrations, each migration adding only one value to
-- the enum.


ALTER TYPE "AuditAction" ADD VALUE 'USER_SUSPENDED';
ALTER TYPE "AuditAction" ADD VALUE 'USER_UNSUSPENDED';
ALTER TYPE "AuditAction" ADD VALUE 'USER_SOFT_DELETED';
ALTER TYPE "AuditAction" ADD VALUE 'USER_FORCE_LOGOUT';
ALTER TYPE "AuditAction" ADD VALUE 'USER_PASSWORD_RESET_TRIGGERED';
ALTER TYPE "AuditAction" ADD VALUE 'USER_GRANTED_SUPER_ADMIN';
ALTER TYPE "AuditAction" ADD VALUE 'USER_REVOKED_SUPER_ADMIN';

-- AlterTable
ALTER TABLE "users" ADD COLUMN     "forceLogoutAt" TIMESTAMPTZ(6),
ADD COLUMN     "softDeletedAt" TIMESTAMPTZ(6),
ADD COLUMN     "softDeletedBy" TEXT,
ADD COLUMN     "suspendedAt" TIMESTAMPTZ(6),
ADD COLUMN     "suspendedBy" TEXT,
ADD COLUMN     "suspendedReason" TEXT;

-- CreateTable
CREATE TABLE "api_usage_events" (
    "id" TEXT NOT NULL,
    "timestamp" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "userId" TEXT,
    "practiceId" TEXT,
    "provider" TEXT NOT NULL,
    "operation" TEXT NOT NULL,
    "audioSeconds" INTEGER,
    "inputTokens" INTEGER,
    "outputTokens" INTEGER,
    "emailCount" INTEGER,
    "unitCount" DOUBLE PRECISION NOT NULL,
    "unitType" TEXT NOT NULL,
    "unitCostUsd" DOUBLE PRECISION NOT NULL,
    "totalCostUsd" DOUBLE PRECISION NOT NULL,
    "visitId" TEXT,
    "requestId" TEXT NOT NULL,
    "modelName" TEXT,
    "metadata" JSONB,

    CONSTRAINT "api_usage_events_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "api_usage_events_userId_timestamp_idx" ON "api_usage_events"("userId", "timestamp");

-- CreateIndex
CREATE INDEX "api_usage_events_practiceId_timestamp_idx" ON "api_usage_events"("practiceId", "timestamp");

-- CreateIndex
CREATE INDEX "api_usage_events_provider_timestamp_idx" ON "api_usage_events"("provider", "timestamp");

-- CreateIndex
CREATE INDEX "api_usage_events_timestamp_idx" ON "api_usage_events"("timestamp");

-- AddForeignKey
ALTER TABLE "api_usage_events" ADD CONSTRAINT "api_usage_events_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "api_usage_events" ADD CONSTRAINT "api_usage_events_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE SET NULL ON UPDATE CASCADE;

