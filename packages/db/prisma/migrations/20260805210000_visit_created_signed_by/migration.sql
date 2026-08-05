-- ============================================================================
-- T4 — createdBy / signedBy attribution on transcribe_visits.
-- ----------------------------------------------------------------------------
-- DERIVATIONS, STATED (T3 style — the ruling lives with the migration, not in
-- a session transcript):
--
--   createdBy  ← v."userId", the visit's existing author field. It has always
--                meant "who created this visit"; the new column names that
--                explicitly so a later `userId` semantic drift cannot silently
--                rewrite history. NOT NULL.
--
--   signedBy   ← the VISIT_SIGNED audit row's "userId", for visits that carry a
--                signature. NULL for unsigned visits BY DESIGN: there is no
--                signer, and a sentinel would be a lie about who signed.
--
-- ⚠️ THE AUDIT DERIVATION IS EXACT, NOT APPROXIMATE — verified before writing:
--     37 VISIT_SIGNED rows · 16 whose visit still exists · 21 whose visit was
--     deleted (audit_logs is append-only and preserved on delete, by policy).
--     Every one of the 16 signed visits has EXACTLY ONE VISIT_SIGNED row.
--     All 16 name a user; all 16 resolve; 0 orphaned.
--   That 1:1 is what makes this derivable at all. It also RECONCILES the
--   "36/16/16 disagreeing signer records" DISCOVERY §B.7 flagged: they never
--   disagreed. The surplus is signed visits that were later deleted.
--
-- ⚠️ AND ALL 16 HAVE signer == author TODAY. A solo-practice database cannot
--   tell these two columns apart, which is exactly why T4's gate demands a
--   NON-OWNER member sign on the T1 fixture.
--
-- ⚠️ THE FORBIDDEN STATE IS UNREPRESENTABLE, NOT DISCOURAGED.
--   A signature with no signer is the state this column exists to prevent, so
--   a CHECK refuses it rather than a code path avoiding it.
--   The discriminator is `signedAt`, NOT `status`: the e2e fixture
--   `seedVisitStates` writes a visit with `signedAt` set and `status='READY'`,
--   so keying on status would leave a real signature unattributed. `signedAt`
--   is the signature; status is workflow.
-- ============================================================================

-- 1. createdBy — nullable, backfill, assert, NOT NULL.
ALTER TABLE "transcribe_visits" ADD COLUMN "createdBy" TEXT;
UPDATE "transcribe_visits" SET "createdBy" = "userId" WHERE "createdBy" IS NULL;

DO $$
DECLARE unset int;
BEGIN
  SELECT count(*) INTO unset FROM "transcribe_visits" WHERE "createdBy" IS NULL;
  IF unset > 0 THEN
    RAISE EXCEPTION 'T4 ABORT: % visits have no derivable createdBy', unset;
  END IF;
END $$;

ALTER TABLE "transcribe_visits" ALTER COLUMN "createdBy" SET NOT NULL;

-- 2. signedBy — stays NULLABLE. Unsigned visits genuinely have no signer.
ALTER TABLE "transcribe_visits" ADD COLUMN "signedBy" TEXT;

UPDATE "transcribe_visits" v
   SET "signedBy" = a."userId"
  FROM "audit_logs" a
 WHERE a."targetId" = v.id
   AND a.action::text = 'VISIT_SIGNED'
   AND a."userId" IS NOT NULL
   AND v."signedAt" IS NOT NULL
   AND v."signedBy" IS NULL;

-- 3. FALLBACK, declared as one. Production's 16 signed visits are ALL
--    audit-derivable (verified above), so on prod step 2 finishes the job and
--    this touches nothing. It exists for rows that carry a signature with no
--    VISIT_SIGNED row at all — fixture-seeded visits in QA and CI, which were
--    never signed through the app and therefore have no signer to recover.
--
--    ⚠️ THIS IS A FALLBACK, NOT A DERIVATION, AND THE DIFFERENCE IS RECORDED
--    IN THE ROW ITSELF: it writes the visit's own author. For a fixture that is
--    exactly right (the fixture's author is its signer). For a real signature it
--    would be a GUESS — which is why step 2 runs first and why the NOTICE below
--    prints the count. If that count is ever non-zero on production, something
--    signed a visit without writing an audit row, and THAT is the finding.
DO $$
DECLARE fallback_rows int; still_null int;
BEGIN
  UPDATE "transcribe_visits"
     SET "signedBy" = "userId"
   WHERE "signedAt" IS NOT NULL AND "signedBy" IS NULL;
  GET DIAGNOSTICS fallback_rows = ROW_COUNT;
  IF fallback_rows > 0 THEN
    RAISE NOTICE 'T4: % signed visit(s) had NO VISIT_SIGNED audit row and fell '
                 'back to the visit author. On production this count must be 0 '
                 '— investigate if it is not.', fallback_rows;
  END IF;

  -- The guard still has teeth: `userId` is NOT NULL, so reaching here with a
  -- NULL means the fallback itself failed, not that a row was unattributable.
  SELECT count(*) INTO still_null
    FROM "transcribe_visits"
   WHERE "signedAt" IS NOT NULL AND "signedBy" IS NULL;
  IF still_null > 0 THEN
    RAISE EXCEPTION
      'T4 ABORT: % signed visits still have no signer after the audit '
      'derivation AND the author fallback. Do NOT relax the CHECK to land '
      'this.', still_null;
  END IF;
END $$;

-- 4. Referential integrity. RESTRICT, not CASCADE: deleting a user must not
--    silently erase who signed a clinical record.
ALTER TABLE "transcribe_visits"
  ADD CONSTRAINT "transcribe_visits_createdBy_fkey"
  FOREIGN KEY ("createdBy") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE RESTRICT;

ALTER TABLE "transcribe_visits"
  ADD CONSTRAINT "transcribe_visits_signedBy_fkey"
  FOREIGN KEY ("signedBy") REFERENCES "users"("id") ON UPDATE CASCADE ON DELETE RESTRICT;

-- 5. THE FORBIDDEN STATE, refused by name.
ALTER TABLE "transcribe_visits"
  ADD CONSTRAINT "transcribe_visits_signed_requires_signer"
  CHECK ("signedAt" IS NULL OR "signedBy" IS NOT NULL);

CREATE INDEX "transcribe_visits_signedBy_idx" ON "transcribe_visits"("signedBy");
