-- REVIEW-DEFAULTS item 1 — the doctor asserts their own scaffold default.
--
-- ⚠️ THE ENUM ADD IS PERMANENTLY IRREVERSIBLE. Postgres has no
-- `ALTER TYPE ... DROP VALUE`. Once this runs, 'DEFAULT_INSERTED_BY_DOCTOR'
-- exists for the life of the database. It is added rather than reusing an
-- existing label because the whole product claim of ruling #194 is that a
-- default reaching a note is a HUMAN act; an audit trail that cannot
-- distinguish that act from a machine fill cannot evidence the claim.
--
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'DEFAULT_INSERTED_BY_DOCTOR';

-- ⚠️ THE UNDO GETS ITS OWN LABEL, AND THAT IS THE POINT OF ADDING TWO. Emitting
-- the insert's label for a removal makes every action-level rollup count a
-- reverted assertion as an assertion — defeating the only thing this
-- irreversible enum add was bought for. Found by an adversarial pass.
--
-- Cardinality: 156 -> 158.
ALTER TYPE "AuditAction" ADD VALUE IF NOT EXISTS 'DEFAULT_INSERT_UNDONE';

-- ---------------------------------------------------------------------------
-- template_twin_field_overrides gains a second KIND.
--
-- F24-S5 built this table for ONE shape: a dropdown correction where the
-- ordinal IS the value. A scaffold-default insert has no ordinal, so the two
-- columns that were required become nullable and a discriminator decides which
-- arm applies.
--
-- ⚠️ NULLABILITY IS A LOST GUARANTEE, SO THE CHECK BELOW REPLACES IT. Without
-- it, an 'option' row could exist with no ordinal — a correction that names
-- nothing, stored successfully, and dropped fail-closed at render with no
-- explanation. The constraint is a TOTAL partition: an unrecognised
-- "overrideKind" satisfies neither arm and the write is REFUSED, so a third
-- kind added in application code without touching this migration fails loudly
-- instead of storing a row nothing can read.
-- ---------------------------------------------------------------------------
ALTER TABLE "template_twin_field_overrides"
  ALTER COLUMN "selectedOptionOrdinal" DROP NOT NULL,
  ALTER COLUMN "optionValue" DROP NOT NULL,
  ADD COLUMN IF NOT EXISTS "overrideKind" TEXT NOT NULL DEFAULT 'option',
  ADD COLUMN IF NOT EXISTS "insertedText" TEXT;

-- ⚠️ THE EXISTING ordinal_nonnegative CHECK IS DELIBERATELY LEFT ALONE.
-- `CHECK (x >= 0)` evaluates to NULL — not false — when x IS NULL, and a CHECK
-- passes on NULL. A scaffold_default row with no ordinal therefore does not
-- violate it, and relaxing it would weaken the option arm for no reason.

ALTER TABLE "template_twin_field_overrides"
  DROP CONSTRAINT IF EXISTS "template_twin_field_overrides_kind_shape";

ALTER TABLE "template_twin_field_overrides"
  ADD CONSTRAINT "template_twin_field_overrides_kind_shape"
  CHECK (
    ("overrideKind" = 'option'
       AND "selectedOptionOrdinal" IS NOT NULL
       AND "optionValue" IS NOT NULL
       AND "insertedText" IS NULL)
    OR
    ("overrideKind" = 'scaffold_default'
       AND "insertedText" IS NOT NULL
       AND "selectedOptionOrdinal" IS NULL)
  );
