-- ============================================================================
-- RULING #226 — ARCHIVE THE SIX TEST PRACTICES, RECONCILE THE SEVEN USERS
-- ----------------------------------------------------------------------------
-- Modelled line-for-line on `scripts/execute-gate0-deactivation.sql`, which is
-- this repository's precedent for an owner-ruled one-shot: ONE transaction,
-- pre-guards that RAISE on population drift, post-verification that ROLLS BACK
-- on any mismatch.
--
-- Run ONLY through the ruled-mutation door, which refuses unless the
-- declaration is TRACKED, UNMODIFIED and COMMITTED:
--
--   bash scripts/run-ruled-mutation.sh \
--     --declaration docs/deploy-declarations/20260907-r226-archive-six-test-practices.md \
--     -- docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc \
--          -v ON_ERROR_STOP=1 -f - < scripts/execute-r226-archive.sql
--
-- ⚠️ SOFT ARCHIVE. NO ROW IS DELETED. #226 forbids the hard delete that
-- `settings/delete-account/route.ts:200` performs one route over.
-- ============================================================================
\set ON_ERROR_STOP on
BEGIN;

-- ── The population, named once and re-derived rather than trusted. ──────────
CREATE TEMP TABLE r226_practices(id text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO r226_practices(id) VALUES
  ('clinic_test_b'),
  ('cmopgtjqc000h01qxbysh3ccz'),
  ('cmophsjyy000001qqmp2e4qdn'),
  ('cmoq7v57p000z01qqp9u9gd16'),
  ('cmoq7w8vj001301qquq6wzxgc'),
  ('cmoq7wjfm001b01qqvwjqtuih');

CREATE TEMP TABLE r226_users(id text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO r226_users(id) VALUES
  ('cmopgtjtu000i01qxkbjop4gq'),
  ('cmophsjzn000101qqgy3e4kmv'),
  ('cmoq7v58f001001qqw9vivgzr'),
  ('cmoq7w8vz001401qqbk9q46bb'),
  ('cmoq7wjfo001c01qqo6yn3tjy');

-- ══ PRE-GUARDS — the act refuses if the world is not what the declaration says
DO $pre$
DECLARE n int; ts timestamptz;
BEGIN
  SELECT count(*) INTO n FROM r226_practices p JOIN practices x ON x.id = p.id;
  IF n <> 6 THEN RAISE EXCEPTION 'r226: expected 6 named practices to exist, found %', n; END IF;

  -- ⚠️ EVERY ONE MUST STILL BE ZERO-ABLE-OWNER AND ZERO-VISIT. If a practice
  -- has come back to life since the declaration was written, this is no longer
  -- the act that was declared.
  SELECT count(*) INTO n FROM r226_practices rp JOIN practices p ON p.id = rp.id
    JOIN users u ON u."practiceId" = p.id
   GROUP BY p.id
  HAVING count(*) FILTER (WHERE u."practiceRole" = 'OWNER' AND u."isActive"
           AND u."deactivatedAt" IS NULL AND u."suspendedAt" IS NULL
           AND u."softDeletedAt" IS NULL) > 0
   LIMIT 1;
  IF FOUND THEN RAISE EXCEPTION 'r226: a named practice has an ABLE OWNER — refusing'; END IF;

  SELECT count(*) INTO n FROM transcribe_visits v
    JOIN users u ON u.id = v."userId" JOIN r226_practices rp ON rp.id = u."practiceId";
  IF n <> 0 THEN RAISE EXCEPTION 'r226: named practices hold % visit(s) — refusing', n; END IF;

  SELECT count(*) INTO n FROM r226_users ru JOIN users u ON u.id = ru.id
   WHERE u."isActive" = false AND u."deactivatedAt" IS NULL;
  IF n <> 5 THEN RAISE EXCEPTION 'r226: expected 5 divergent users, found %', n; END IF;

  -- ⚠️ THE RECOVERED TIMESTAMP IS RE-DERIVED FROM THE AUDIT TRAIL, NOT TYPED IN.
  -- The declaration states 2026-08-08 20:07:02.578745+00; this proves the audit
  -- rows still say so, and that all five agree. A hard-coded literal that had
  -- drifted from its own evidence is exactly the fabrication this avoids.
  SELECT count(DISTINCT a."timestamp") INTO n
    FROM audit_logs a JOIN r226_users ru ON ru.id = a."targetId"
   WHERE a.action::text = 'USER_DEACTIVATED';
  IF n <> 1 THEN RAISE EXCEPTION 'r226: the five users do not share ONE deactivation instant (% distinct)', n; END IF;

  SELECT DISTINCT a."timestamp" INTO ts
    FROM audit_logs a JOIN r226_users ru ON ru.id = a."targetId"
   WHERE a.action::text = 'USER_DEACTIVATED';
  IF ts <> TIMESTAMPTZ '2026-08-08 20:07:02.578745+00' THEN
    RAISE EXCEPTION 'r226: the audit trail says %, the declaration says 2026-08-08 20:07:02.578745+00', ts;
  END IF;
  RAISE NOTICE 'r226 pre-guards: 6 practices, 0 visits, 5 divergent users, one instant %', ts;
END
$pre$;

-- ══ THE ACT ════════════════════════════════════════════════════════════════
-- 1 · the archive — a MARKER. Nothing reads practices.isActive; this disables
--     nothing and is not claimed to.
UPDATE practices SET "isActive" = false
 WHERE id IN (SELECT id FROM r226_practices);

-- 2 · the reconciliation — the RECOVERED instant, taken from the audit trail
--     itself rather than retyped, and `updatedAt` DELIBERATELY NOT NAMED so the
--     corroborating witness survives the act that records it.
UPDATE users u
   SET "deactivatedAt" = (SELECT DISTINCT a."timestamp" FROM audit_logs a
                           JOIN r226_users r ON r.id = a."targetId"
                          WHERE a.action::text = 'USER_DEACTIVATED'),
       -- ⚠️ THE RULING IDENTIFIER, NOT A PERSON AND NOT THE CONTAINMENT'S NAME.
       -- The established practice in this very column: the other two users in
       -- this population read `gate0-ruling-2026-08-05`. The actor for a ruled
       -- one-shot is the RULING, and `deactivatedBy` has no FK precisely so it
       -- can say so.
       "deactivatedBy" = 'r226-ruling-2026-09-07'
 WHERE u.id IN (SELECT id FROM r226_users);

-- ══ POST-VERIFICATION — ROLLS BACK ON ANY MISMATCH ═════════════════════════
DO $post$
DECLARE n int; v int; s int; up int;
BEGIN
  SELECT count(*) INTO n FROM practices p JOIN r226_practices rp ON rp.id = p.id
   WHERE p."isActive" = false;
  IF n <> 6 THEN RAISE EXCEPTION 'r226 VERIFY C1: expected 6 archived, found %', n; END IF;

  SELECT count(*) INTO n FROM users WHERE "isActive" = false AND "deactivatedAt" IS NULL;
  IF n <> 0 THEN RAISE EXCEPTION 'r226 VERIFY C2: % users still divergent', n; END IF;

  SELECT count(*) INTO n FROM users u JOIN r226_users ru ON ru.id = u.id
   WHERE u."deactivatedAt" = TIMESTAMPTZ '2026-08-08 20:07:02.578745+00'
     AND u."deactivatedBy" = 'r226-ruling-2026-09-07';
  IF n <> 5 THEN RAISE EXCEPTION 'r226 VERIFY C3/C4: % of 5 carry the recovered instant', n; END IF;

  -- ⚠️ N3 — the witness must survive. A Prisma write, or naming updatedAt here,
  -- would have bumped it and destroyed the evidence for the value just written.
  SELECT count(*) INTO up FROM users u JOIN r226_users ru ON ru.id = u.id
   WHERE u."updatedAt" = TIMESTAMPTZ '2026-08-08 20:07:02.578745+00';
  IF up <> 5 THEN RAISE EXCEPTION 'r226 VERIFY N3: updatedAt moved on % of 5 — the witness is gone', 5 - up; END IF;

  SELECT count(*) INTO n FROM users;   IF n <> 198 THEN RAISE EXCEPTION 'r226 VERIFY N2: users % <> 198 — A ROW WAS DELETED', n; END IF;
  SELECT count(*) INTO n FROM practices; IF n <> 199 THEN RAISE EXCEPTION 'r226 VERIFY N2: practices % <> 199 — A ROW WAS DELETED', n; END IF;

  -- N1 — the clinical counts, never omitted per §2.5.
  SELECT count(*), count(*) FILTER (WHERE "signedAt" IS NOT NULL) INTO v, s FROM transcribe_visits;
  IF v <> 58 OR s <> 40 THEN RAISE EXCEPTION 'r226 VERIFY N1: visits %/signed % <> 58/40 — CLINICAL DATA MOVED', v, s; END IF;

  SELECT count(*) INTO n FROM users u JOIN r226_users ru ON ru.id = u.id WHERE u."isActive" <> false;
  IF n <> 0 THEN RAISE EXCEPTION 'r226 VERIFY N4: isActive flipped on % users', n; END IF;

  -- N6 — the single most dangerous failure: a wrong WHERE touching other rows.
  SELECT count(*) INTO n FROM practices
   WHERE "isActive" = false AND id NOT IN (SELECT id FROM r226_practices);
  IF n <> 0 THEN RAISE EXCEPTION 'r226 VERIFY N6: % practice(s) OUTSIDE the six are archived', n; END IF;

  -- N7 — the act must not create the harm it cleans up after.
  SELECT count(*) INTO n FROM (
    SELECT p.id FROM practices p JOIN users u ON u."practiceId" = p.id GROUP BY p.id
    HAVING count(*) FILTER (WHERE u."practiceRole"='OWNER' AND u."isActive" AND u."deactivatedAt" IS NULL
             AND u."suspendedAt" IS NULL AND u."softDeletedAt" IS NULL) = 0
       AND count(*) FILTER (WHERE u."isActive" AND u."deactivatedAt" IS NULL
             AND u."softDeletedAt" IS NULL AND u."suspendedAt" IS NULL) > 0) z;
  IF n <> 0 THEN RAISE EXCEPTION 'r226 VERIFY N7: % practice(s) now have a LIVE member and no able owner', n; END IF;

  RAISE NOTICE 'r226 VERIFY: 6 archived, 0 divergent, 5 reconciled to the recovered instant, witness intact, 198/199 rows, 58/40 visits, nothing outside the six touched.';
END
$post$;

COMMIT;
