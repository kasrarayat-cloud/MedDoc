-- AlterTable
ALTER TABLE "practices" ADD COLUMN     "audioRetentionDays" INTEGER NOT NULL DEFAULT 90,
ADD COLUMN     "transcriptRetentionDays" INTEGER NOT NULL DEFAULT 2555;
