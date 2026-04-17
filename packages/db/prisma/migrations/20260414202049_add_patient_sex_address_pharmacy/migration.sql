-- CreateEnum
CREATE TYPE "PatientSex" AS ENUM ('UNKNOWN', 'MALE', 'FEMALE', 'OTHER');

-- AlterTable
ALTER TABLE "patients" ADD COLUMN     "addressLine1" TEXT,
ADD COLUMN     "addressLine2" TEXT,
ADD COLUMN     "city" TEXT,
ADD COLUMN     "pharmacyName" TEXT,
ADD COLUMN     "pharmacyPhone" TEXT,
ADD COLUMN     "postalCode" TEXT,
ADD COLUMN     "sex" "PatientSex" NOT NULL DEFAULT 'UNKNOWN',
ADD COLUMN     "state" TEXT;

-- RenameIndex
ALTER INDEX "patient_practice_chartid_unique" RENAME TO "patients_practiceId_chartId_key";
