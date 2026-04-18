-- CreateEnum
CREATE TYPE "Product" AS ENUM ('MEDDOC_PRO', 'TRANSCRIBE_MD');

-- AlterTable
ALTER TABLE "users" ADD COLUMN     "products" "Product"[] DEFAULT ARRAY['MEDDOC_PRO']::"Product"[];

-- CreateTable
CREATE TABLE "transcribe_visits" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "patientName" TEXT,
    "specialty" TEXT NOT NULL,
    "chiefComplaint" TEXT,
    "inputMode" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'draft',
    "audioKey" TEXT,
    "transcriptText" TEXT,
    "soapNote" JSONB,
    "icdCodes" JSONB,
    "cptCodes" JSONB,
    "rxDrafts" JSONB,
    "referrals" JSONB,
    "patientSummary" TEXT,
    "confidenceScores" JSONB,
    "signedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "transcribe_visits_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "user_sessions" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "sessionToken" TEXT NOT NULL,
    "ipAddress" TEXT,
    "userAgent" TEXT,
    "deviceFingerprint" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "lastActiveAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expiresAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "user_sessions_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "transcribe_visits_userId_createdAt_idx" ON "transcribe_visits"("userId", "createdAt");

-- CreateIndex
CREATE INDEX "transcribe_visits_status_idx" ON "transcribe_visits"("status");

-- CreateIndex
CREATE UNIQUE INDEX "user_sessions_sessionToken_key" ON "user_sessions"("sessionToken");

-- CreateIndex
CREATE INDEX "user_sessions_userId_idx" ON "user_sessions"("userId");

-- CreateIndex
CREATE INDEX "user_sessions_sessionToken_idx" ON "user_sessions"("sessionToken");

-- CreateIndex
CREATE INDEX "user_sessions_expiresAt_idx" ON "user_sessions"("expiresAt");

-- AddForeignKey
ALTER TABLE "transcribe_visits" ADD CONSTRAINT "transcribe_visits_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "user_sessions" ADD CONSTRAINT "user_sessions_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
