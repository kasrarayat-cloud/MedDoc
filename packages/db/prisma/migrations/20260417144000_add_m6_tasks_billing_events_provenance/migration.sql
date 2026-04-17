-- CreateEnum
CREATE TYPE "TaskStatus" AS ENUM ('OPEN', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED');
-- CreateEnum
CREATE TYPE "BillingEventStatus" AS ENUM ('PENDING_REVIEW', 'SUBMITTED', 'PAID', 'DENIED');
-- AlterTable
ALTER TABLE "documents" ADD COLUMN     "sourceItemIndex" INTEGER,
ADD COLUMN     "sourceScribeOutputId" TEXT;
-- AlterTable
ALTER TABLE "medications" ADD COLUMN     "sourceScribeOutputId" TEXT;
-- CreateTable
CREATE TABLE "tasks" (
    "id" TEXT NOT NULL,
    "practiceId" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "assignedUserId" TEXT,
    "createdByUserId" TEXT,
    "title" TEXT NOT NULL,
    "description" TEXT,
    "status" "TaskStatus" NOT NULL DEFAULT 'OPEN',
    "dueAt" TIMESTAMPTZ(6),
    "sourceVisitId" TEXT,
    "sourceScribeOutputId" TEXT,
    "sourceItemIndex" INTEGER,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ(6) NOT NULL,
    "completedAt" TIMESTAMPTZ(6),
    "completedById" TEXT,
    CONSTRAINT "tasks_pkey" PRIMARY KEY ("id")
);
-- CreateTable
CREATE TABLE "billing_events" (
    "id" TEXT NOT NULL,
    "practiceId" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "clinicianUserId" TEXT NOT NULL,
    "icd10Items" JSONB NOT NULL,
    "cptItems" JSONB NOT NULL,
    "status" "BillingEventStatus" NOT NULL DEFAULT 'PENDING_REVIEW',
    "sourceVisitId" TEXT,
    "sourceScribeOutputId" TEXT,
    "submittedAt" TIMESTAMPTZ(6),
    "submittedById" TEXT,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ(6) NOT NULL,
    CONSTRAINT "billing_events_pkey" PRIMARY KEY ("id")
);
-- CreateIndex
CREATE INDEX "tasks_practiceId_status_dueAt_idx" ON "tasks"("practiceId", "status", "dueAt");
-- CreateIndex
CREATE INDEX "tasks_patientId_idx" ON "tasks"("patientId");
-- CreateIndex
CREATE INDEX "tasks_assignedUserId_idx" ON "tasks"("assignedUserId");
-- CreateIndex
CREATE INDEX "tasks_sourceVisitId_idx" ON "tasks"("sourceVisitId");
-- CreateIndex
CREATE UNIQUE INDEX "tasks_sourceScribeOutputId_sourceItemIndex_key" ON "tasks"("sourceScribeOutputId", "sourceItemIndex");
-- CreateIndex
CREATE UNIQUE INDEX "billing_events_sourceScribeOutputId_key" ON "billing_events"("sourceScribeOutputId");
-- CreateIndex
CREATE INDEX "billing_events_practiceId_status_createdAt_idx" ON "billing_events"("practiceId", "status", "createdAt");
-- CreateIndex
CREATE INDEX "billing_events_patientId_idx" ON "billing_events"("patientId");
-- CreateIndex
CREATE INDEX "billing_events_sourceVisitId_idx" ON "billing_events"("sourceVisitId");
-- CreateIndex
CREATE UNIQUE INDEX "documents_sourceScribeOutputId_sourceItemIndex_key" ON "documents"("sourceScribeOutputId", "sourceItemIndex");
-- CreateIndex
CREATE INDEX "medications_sourceScribeOutputId_idx" ON "medications"("sourceScribeOutputId");
-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE CASCADE ON UPDATE CASCADE;
-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_assignedUserId_fkey" FOREIGN KEY ("assignedUserId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
-- AddForeignKey
ALTER TABLE "tasks" ADD CONSTRAINT "tasks_createdByUserId_fkey" FOREIGN KEY ("createdByUserId") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
-- AddForeignKey
ALTER TABLE "billing_events" ADD CONSTRAINT "billing_events_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
-- AddForeignKey
ALTER TABLE "billing_events" ADD CONSTRAINT "billing_events_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE CASCADE ON UPDATE CASCADE;
-- AddForeignKey
ALTER TABLE "billing_events" ADD CONSTRAINT "billing_events_clinicianUserId_fkey" FOREIGN KEY ("clinicianUserId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
-- AddForeignKey
ALTER TABLE "billing_events" ADD CONSTRAINT "billing_events_submittedById_fkey" FOREIGN KEY ("submittedById") REFERENCES "users"("id") ON DELETE SET NULL ON UPDATE CASCADE;
