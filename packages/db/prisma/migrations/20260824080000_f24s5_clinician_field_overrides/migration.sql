-- F24-S5 — the clinician's correction to an enumerated form control, and the
-- other half of a fill manifest's bound identity.
--
-- TWO OBJECTS, ONE CHANGE, AND THEY ONLY WORK TOGETHER:
--
--   1. `template_twin_field_overrides` — the correction itself, read as an
--      INPUT on every fill so a recompute RE-APPLIES it.
--   2. `template_twin_fill_manifests.overridesSha256` — the identity of the
--      override set a fill ran against.
--
-- (1) alone was built and REFUTED (PR #824). The two surfaces that decide
-- whether a fill runs at all — `native-export.ts` and `sign-freeze.ts` — both
-- gate on a predicate over the NOTE, and an override deliberately never touches
-- `soapFinal`. So the fill was never reached: the preview showed the
-- correction, the download served the stored pre-override bytes, and signing
-- pinned the pre-override manifest forever. (2) is what makes the gates SEE an
-- override without any gate being loosened.

-- ── 1. the correction ───────────────────────────────────────────────────────
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

-- ONE LIVE OVERRIDE PER (visit, field). A correction replaces a correction;
-- there is no stack to unwind and no ordering to get wrong.
CREATE UNIQUE INDEX "template_twin_field_overrides_visitId_fieldId_key"
    ON "template_twin_field_overrides"("visitId", "fieldId");

CREATE INDEX "template_twin_field_overrides_visitId_idx"
    ON "template_twin_field_overrides"("visitId");

CREATE INDEX "template_twin_field_overrides_practiceId_idx"
    ON "template_twin_field_overrides"("practiceId");

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

-- ⚠️ DECLARED DRIFT, DOCUMENTED BESIDE THE MODEL IN schema.prisma. Prisma
-- cannot express a CHECK, and `Int` admits negatives the database must refuse:
-- a negative ordinal cannot address an option in `allowedOptions`. The schema
-- is the WEAKER statement here — do not "close" the drift by dropping this.
ALTER TABLE "template_twin_field_overrides"
    ADD CONSTRAINT "template_twin_field_overrides_ordinal_nonnegative"
    CHECK ("selectedOptionOrdinal" >= 0);

-- ── 2. the other half of the bound identity ─────────────────────────────────
--
-- ⚠️ NULLABLE AND DELIBERATELY NOT BACKFILLED. A null here can only mean the
-- manifest predates THIS migration, and no override row can exist before the
-- table created above it. So null reads as the identity of the EMPTY set — true
-- by construction rather than inferred. Backfilling a constant would assert a
-- correspondence nobody verified, and the ruling forbids it.
--
-- This is NOT the same null as `noteSha256`'s, which means *we do not know which
-- note this was* and therefore fails closed. The two nulls carry different
-- meanings and `manifestMatchesDocument` treats them differently, on purpose.
ALTER TABLE "template_twin_fill_manifests"
    ADD COLUMN "overridesSha256" CHAR(64);
