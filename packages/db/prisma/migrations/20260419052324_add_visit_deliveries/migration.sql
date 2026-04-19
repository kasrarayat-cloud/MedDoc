-- T-M7: export-delivery audit trail.
CREATE TABLE "visit_deliveries" (
    "id"          TEXT NOT NULL,
    "visitId"     TEXT NOT NULL,
    "channel"     TEXT NOT NULL,
    "destination" TEXT,
    "sizeBytes"   INTEGER,
    "createdAt"   TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "visit_deliveries_pkey" PRIMARY KEY ("id")
);

CREATE INDEX "visit_deliveries_visitId_idx" ON "visit_deliveries"("visitId");

ALTER TABLE "visit_deliveries"
  ADD CONSTRAINT "visit_deliveries_visitId_fkey"
  FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id")
  ON DELETE CASCADE ON UPDATE CASCADE;
