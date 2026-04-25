-- Voice retry robustness: failure categorization + manual-retry budget.
-- Both columns added in one migration so prod sees a single ALTER TABLE.
-- failureCategory is nullable text (no enum yet — easier to extend later).
-- manualRetryCount has a default 0 so existing rows backfill cleanly.

-- AlterTable
ALTER TABLE "transcribe_visits" ADD COLUMN     "failureCategory" TEXT,
ADD COLUMN     "manualRetryCount" INTEGER NOT NULL DEFAULT 0;
