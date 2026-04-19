
-- DropForeignKey
ALTER TABLE "ai_calls" DROP CONSTRAINT "ai_calls_visitId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_audit_events" DROP CONSTRAINT "scribe_audit_events_actorId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_audit_events" DROP CONSTRAINT "scribe_audit_events_practiceId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_audit_events" DROP CONSTRAINT "scribe_audit_events_visitId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_outputs" DROP CONSTRAINT "scribe_outputs_practiceId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_outputs" DROP CONSTRAINT "scribe_outputs_visitId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_transcripts" DROP CONSTRAINT "scribe_transcripts_practiceId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_transcripts" DROP CONSTRAINT "scribe_transcripts_visitId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_visits" DROP CONSTRAINT "scribe_visits_patientId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_visits" DROP CONSTRAINT "scribe_visits_practiceId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_visits" DROP CONSTRAINT "scribe_visits_specialtyId_fkey";

-- DropForeignKey
ALTER TABLE "scribe_visits" DROP CONSTRAINT "scribe_visits_userId_fkey";

-- DropTable
DROP TABLE "scribe_audit_events";

-- DropTable
DROP TABLE "scribe_outputs";

-- DropTable
DROP TABLE "scribe_specialty_templates";

-- DropTable
DROP TABLE "scribe_transcripts";

-- DropTable
DROP TABLE "scribe_visits";

-- DropEnum
DROP TYPE "ClinicalReviewStatus";

-- DropEnum
DROP TYPE "OutputType";

-- DropEnum
DROP TYPE "VisitMode";

-- DropEnum
DROP TYPE "VisitStatus";

