-- app-redesign-v1: additive columns for the new dashboard/patient/visit
-- screens + clinician profile + TOTP recovery codes moved to a String[].
--
-- mfaBackupCodes was confirmed empty (0 non-null rows in `users`) before
-- the DROP+ADD, so no data loss. The new type is the canonical shape the
-- Settings 2FA flow (otplib) writes.

-- AlterTable
ALTER TABLE "users" ADD COLUMN     "clinicName" TEXT,
ADD COLUMN     "npi" TEXT,
ADD COLUMN     "specialty" TEXT,
ADD COLUMN     "timeZone" TEXT DEFAULT 'America/Los_Angeles',
DROP COLUMN "mfaBackupCodes",
ADD COLUMN     "mfaBackupCodes" TEXT[] DEFAULT ARRAY[]::TEXT[];

-- AlterTable
ALTER TABLE "transcribe_md_patients" ADD COLUMN     "insurance" TEXT,
ADD COLUMN     "mrn" TEXT,
ADD COLUMN     "problemList" JSONB;

-- AlterTable
ALTER TABLE "transcribe_visits" ADD COLUMN     "draftedInSeconds" INTEGER,
ADD COLUMN     "markedMoments" JSONB;
