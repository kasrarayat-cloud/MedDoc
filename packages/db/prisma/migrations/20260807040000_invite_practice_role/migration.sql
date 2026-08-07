-- ===========================================================================
-- T8 — an invite mints a MEMBER, not just a user.
-- ---------------------------------------------------------------------------
-- Two nullable columns and one CHECK. The branch that uses them lives in the
-- signup transaction (`src/actions/auth.ts`).
--
-- ⚠️ THE LEGACY BEHAVIOUR IS DECLARED HERE, NOT LEFT TO INFERENCE.
--
--     practiceId IS NULL  →  signup mints a FRESH SOLO PRACTICE and the
--                            redeemer becomes its OWNER — exactly what every
--                            signup did before T8, unchanged.
--
-- Every existing row is in that state and stays there. They are NOT backfilled,
-- and the reason is the standing no-downgrade principle read in the other
-- direction: there is no practice these codes were "meant" to point at, so
-- inventing one would be a guess wearing a migration's authority. An
-- outstanding invite keeps doing what its issuer expected when they issued it.
--
-- ⚠️ BOTH-OR-NEITHER, ENFORCED BY THE DATABASE.
-- `practiceRole` without `practiceId` is meaningless. `practiceId` WITHOUT a
-- role is worse than meaningless: the redeemer would join a real clinic and
-- fall to whatever the application picked — and the application's own default
-- for a new signup is OWNER, which would hand an owner's rights over somebody
-- else's practice to anyone holding the code. That is the failure this CHECK
-- exists to make unrepresentable, and it is why the pair is a constraint rather
-- than a convention.
--
-- ⚠️ NO BACKFILL, SO NO ABORT GUARD IS NEEDED — and that is stated rather than
-- silently omitted. T3 and T6 both carried `RAISE EXCEPTION` guards because
-- they derived values for existing rows. This migration derives nothing: the
-- columns arrive NULL and mean "legacy", which is a state every existing row is
-- already correctly in.
-- ===========================================================================

ALTER TABLE "invite_codes" ADD COLUMN "practiceId" TEXT;
ALTER TABLE "invite_codes" ADD COLUMN "practiceRole" "PracticeRole";

ALTER TABLE "invite_codes"
  ADD CONSTRAINT "invite_codes_practice_and_role_together"
  CHECK (
    ("practiceId" IS NULL AND "practiceRole" IS NULL)
    OR ("practiceId" IS NOT NULL AND "practiceRole" IS NOT NULL)
  );

ALTER TABLE "invite_codes"
  ADD CONSTRAINT "invite_codes_practiceId_fkey"
  FOREIGN KEY ("practiceId") REFERENCES "practices"("id")
  ON DELETE RESTRICT ON UPDATE CASCADE;

-- Redemption looks the code up by hash and then reads the practice; the index
-- serves the admin surface that lists a practice's outstanding invites.
-- Declared in schema.prisma in this same commit — a raw index the schema does
-- not know about is drift.
CREATE INDEX "invite_codes_practiceId_idx" ON "invite_codes" ("practiceId");
