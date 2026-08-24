-- F24-S5 — the clinician's corrections to enumerated form controls.
--
-- An INPUT to every fill, never part of a fill's output. The fill manifest was
-- measured and refuted as the home for this (RELAY.md, F24-S5 recon): written
-- there, an override is either silently reverted by the export's recompute or
-- it makes the fill throw and the doctor's form stops coming back at all.
--
-- Purely ADDITIVE: a new table, no column added to any existing one, so there
-- is no write-path sweep to run and no existing row to backfill. Nothing that
-- writes today can produce a state this table makes illegal.

CREATE TABLE "template_twin_field_overrides" (
    "id" TEXT NOT NULL,
    "practiceId" TEXT NOT NULL,
    "visitId" TEXT NOT NULL,
    "fieldId" TEXT NOT NULL,
    "selectedOptionOrdinal" INTEGER NOT NULL,
    "optionValue" TEXT NOT NULL,
    "overriddenBy" TEXT NOT NULL,
    "createdAt" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMPTZ(6) NOT NULL,

    CONSTRAINT "template_twin_field_overrides_pkey" PRIMARY KEY ("id")
);

-- ONE LIVE OVERRIDE PER (visit, field). A correction replaces a correction:
-- no stack to unwind, no ordering to get wrong, and the upsert that writes it
-- cannot silently create a second row that the fill would then have to choose
-- between.
CREATE UNIQUE INDEX "template_twin_field_overrides_visitId_fieldId_key"
    ON "template_twin_field_overrides"("visitId", "fieldId");

CREATE INDEX "template_twin_field_overrides_visitId_idx"
    ON "template_twin_field_overrides"("visitId");

CREATE INDEX "template_twin_field_overrides_practiceId_idx"
    ON "template_twin_field_overrides"("practiceId");

-- A negative ordinal cannot address an option. Refused at the database, not
-- only in the resolver, because the resolver is one of several writers a future
-- slice may add and this constraint is the one that cannot be forgotten.
ALTER TABLE "template_twin_field_overrides"
    ADD CONSTRAINT "template_twin_field_overrides_ordinal_nonnegative"
    CHECK ("selectedOptionOrdinal" >= 0);

ALTER TABLE "template_twin_field_overrides"
    ADD CONSTRAINT "template_twin_field_overrides_practiceId_fkey"
    FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "template_twin_field_overrides"
    ADD CONSTRAINT "template_twin_field_overrides_visitId_fkey"
    FOREIGN KEY ("visitId") REFERENCES "transcribe_visits"("id")
    ON DELETE CASCADE ON UPDATE CASCADE;

ALTER TABLE "template_twin_field_overrides"
    ADD CONSTRAINT "template_twin_field_overrides_overriddenBy_fkey"
    FOREIGN KEY ("overriddenBy") REFERENCES "users"("id")
    ON DELETE RESTRICT ON UPDATE CASCADE;
