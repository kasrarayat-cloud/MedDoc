-- rx-warning-card: audit log for critical Rx warning overrides.
-- One row per "sign anyway" with the doctor's typed reason.

-- CreateTable
CREATE TABLE "rx_warning_overrides" (
    "id" TEXT NOT NULL,
    "visitId" TEXT NOT NULL,
    "rxLineNumber" INTEGER NOT NULL,
    "warningId" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "headline" TEXT NOT NULL,
    "reason" TEXT NOT NULL,
    "overriddenBy" TEXT NOT NULL,
    "overriddenAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "rx_warning_overrides_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "rx_warning_overrides_visitId_idx" ON "rx_warning_overrides"("visitId");

-- CreateIndex
CREATE INDEX "rx_warning_overrides_overriddenBy_idx" ON "rx_warning_overrides"("overriddenBy");

-- AddForeignKey
ALTER TABLE "rx_warning_overrides" ADD CONSTRAINT "rx_warning_overrides_visitId_fkey" FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "rx_warning_overrides" ADD CONSTRAINT "rx_warning_overrides_overriddenBy_fkey" FOREIGN KEY ("overriddenBy") REFERENCES "users"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
