-- CreateEnum
CREATE TYPE "ClinicalReviewStatus" AS ENUM ('DRAFT', 'SPECIALIST_REVIEWED', 'PRODUCTION');

-- AlterTable
ALTER TABLE "scribe_specialty_templates" ADD COLUMN     "clinicalReviewStatus" "ClinicalReviewStatus" NOT NULL DEFAULT 'DRAFT',
ADD COLUMN     "defaultCptHints" TEXT[] DEFAULT ARRAY[]::TEXT[];
