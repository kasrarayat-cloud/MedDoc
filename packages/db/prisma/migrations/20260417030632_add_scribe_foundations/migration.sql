-- CreateEnum
CREATE TYPE "VisitMode" AS ENUM ('LIVE', 'BATCH');

-- CreateEnum
CREATE TYPE "VisitStatus" AS ENUM ('DRAFT', 'RECORDING', 'UPLOADING', 'PROCESSING', 'READY_FOR_REVIEW', 'SIGNED', 'ERROR');

-- CreateEnum
CREATE TYPE "OutputType" AS ENUM ('SOAP', 'ICD10_CPT', 'RX', 'REFERRAL', 'PATIENT_SUMMARY');

-- CreateTable
CREATE TABLE "scribe_visits" (
    "id" TEXT NOT NULL,
    "practiceId" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "patientId" TEXT NOT NULL,
    "specialtyId" TEXT NOT NULL,
    "mode" "VisitMode" NOT NULL,
    "status" "VisitStatus" NOT NULL DEFAULT 'DRAFT',
    "startedAt" TIMESTAMPTZ(6) NOT NULL,
    "endedAt" TIMESTAMPTZ(6),
    "audioObjectKey" TEXT,
    "audioDurationSec" INTEGER,
    "sourceFileName" TEXT,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ(6) NOT NULL,
    "deletedAt" TIMESTAMPTZ(6),

    CONSTRAINT "scribe_visits_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "scribe_transcripts" (
    "id" TEXT NOT NULL,
    "practiceId" TEXT NOT NULL,
    "visitId" TEXT NOT NULL,
    "segments" JSONB NOT NULL,
    "language" TEXT NOT NULL DEFAULT 'en',
    "rawFullText" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "scribe_transcripts_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "scribe_outputs" (
    "id" TEXT NOT NULL,
    "practiceId" TEXT NOT NULL,
    "visitId" TEXT NOT NULL,
    "type" "OutputType" NOT NULL,
    "content" JSONB NOT NULL,
    "version" INTEGER NOT NULL DEFAULT 1,
    "modelUsed" TEXT NOT NULL,
    "templateVersion" TEXT NOT NULL,
    "editedByClinician" BOOLEAN NOT NULL DEFAULT false,
    "signedAt" TIMESTAMPTZ(6),
    "signedBy" TEXT,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "scribe_outputs_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "scribe_specialty_templates" (
    "id" TEXT NOT NULL,
    "slug" TEXT NOT NULL,
    "displayName" TEXT NOT NULL,
    "version" TEXT NOT NULL,
    "systemPrompt" TEXT NOT NULL,
    "requiredExamElements" JSONB NOT NULL,
    "soapSchema" JSONB NOT NULL,
    "defaultIcd10Hints" TEXT[],
    "defaultFormularyHints" TEXT[],
    "active" BOOLEAN NOT NULL DEFAULT true,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "scribe_specialty_templates_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "scribe_audit_events" (
    "id" TEXT NOT NULL,
    "practiceId" TEXT NOT NULL,
    "visitId" TEXT NOT NULL,
    "actorId" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "diff" JSONB,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "scribe_audit_events_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ai_calls" (
    "id" TEXT NOT NULL,
    "practiceId" TEXT NOT NULL,
    "visitId" TEXT,
    "purpose" TEXT NOT NULL,
    "provider" TEXT NOT NULL,
    "model" TEXT NOT NULL,
    "promptHash" TEXT NOT NULL,
    "latencyMs" INTEGER NOT NULL,
    "inputTokens" INTEGER,
    "outputTokens" INTEGER,
    "costUsdCents" INTEGER,
    "success" BOOLEAN NOT NULL,
    "errorCode" TEXT,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ai_calls_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "scribe_visits_practiceId_userId_createdAt_idx" ON "scribe_visits"("practiceId", "userId", "createdAt");

-- CreateIndex
CREATE INDEX "scribe_visits_practiceId_patientId_idx" ON "scribe_visits"("practiceId", "patientId");

-- CreateIndex
CREATE INDEX "scribe_visits_status_idx" ON "scribe_visits"("status");

-- CreateIndex
CREATE UNIQUE INDEX "scribe_transcripts_visitId_key" ON "scribe_transcripts"("visitId");

-- CreateIndex
CREATE INDEX "scribe_transcripts_practiceId_idx" ON "scribe_transcripts"("practiceId");

-- CreateIndex
CREATE INDEX "scribe_outputs_practiceId_visitId_type_idx" ON "scribe_outputs"("practiceId", "visitId", "type");

-- CreateIndex
CREATE UNIQUE INDEX "scribe_specialty_templates_slug_key" ON "scribe_specialty_templates"("slug");

-- CreateIndex
CREATE INDEX "scribe_specialty_templates_active_idx" ON "scribe_specialty_templates"("active");

-- CreateIndex
CREATE INDEX "scribe_audit_events_practiceId_visitId_createdAt_idx" ON "scribe_audit_events"("practiceId", "visitId", "createdAt");

-- CreateIndex
CREATE INDEX "scribe_audit_events_actorId_idx" ON "scribe_audit_events"("actorId");

-- CreateIndex
CREATE INDEX "ai_calls_practiceId_purpose_createdAt_idx" ON "ai_calls"("practiceId", "purpose", "createdAt");

-- CreateIndex
CREATE INDEX "ai_calls_visitId_idx" ON "ai_calls"("visitId");

-- AddForeignKey
ALTER TABLE "scribe_visits" ADD CONSTRAINT "scribe_visits_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_visits" ADD CONSTRAINT "scribe_visits_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_visits" ADD CONSTRAINT "scribe_visits_patientId_fkey" FOREIGN KEY ("patientId") REFERENCES "patients"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_visits" ADD CONSTRAINT "scribe_visits_specialtyId_fkey" FOREIGN KEY ("specialtyId") REFERENCES "scribe_specialty_templates"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_transcripts" ADD CONSTRAINT "scribe_transcripts_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_transcripts" ADD CONSTRAINT "scribe_transcripts_visitId_fkey" FOREIGN KEY ("visitId") REFERENCES "scribe_visits"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_outputs" ADD CONSTRAINT "scribe_outputs_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_outputs" ADD CONSTRAINT "scribe_outputs_visitId_fkey" FOREIGN KEY ("visitId") REFERENCES "scribe_visits"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_audit_events" ADD CONSTRAINT "scribe_audit_events_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_audit_events" ADD CONSTRAINT "scribe_audit_events_visitId_fkey" FOREIGN KEY ("visitId") REFERENCES "scribe_visits"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "scribe_audit_events" ADD CONSTRAINT "scribe_audit_events_actorId_fkey" FOREIGN KEY ("actorId") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ai_calls" ADD CONSTRAINT "ai_calls_practiceId_fkey" FOREIGN KEY ("practiceId") REFERENCES "practices"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "ai_calls" ADD CONSTRAINT "ai_calls_visitId_fkey" FOREIGN KEY ("visitId") REFERENCES "scribe_visits"("id") ON DELETE SET NULL ON UPDATE CASCADE;
