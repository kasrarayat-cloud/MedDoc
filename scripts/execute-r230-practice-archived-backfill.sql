-- ============================================================================
-- RULING #230 — THE SIX ARCHIVED PRACTICES GET THEIR `PRACTICE_ARCHIVED` ROWS
-- ----------------------------------------------------------------------------
-- #230 deferred these rows on purpose: "A real PRACTICE_ARCHIVED action arrives
-- with practice-lifecycle work in the ADMIN arc, with its own migration. These
-- six get their rows then." ADMIN-3a's migration 20260909080000 added the enum
-- value, and it is applied in production. So this is "then".
--
-- Modelled on `scripts/execute-r226-archive.sql` (the act these rows describe),
-- which follows `scripts/execute-gate0-deactivation.sql`: ONE transaction,
-- pre-guards that RAISE on population drift, post-verification that ROLLS BACK.
--
-- Run ONLY through the ruled-mutation door:
--
--   bash scripts/run-ruled-mutation.sh \
--     --declaration docs/foundation/mutations/20260910-r230-practice-archived-backfill.md \
--     -- docker exec -i meddoc-pro-postgres-1 psql -U meddoc -d meddoc \
--          -v ON_ERROR_STOP=1 -f - < scripts/execute-r230-practice-archived-backfill.sql
--
-- ⚠️ IT ADDS SIX ROWS AND WRITES NOTHING ELSE. No practice, no user, no enum.
-- It is reversible by deleting six rows with known, deterministic ids.
--
-- ⚠️ THE ROW TIMESTAMP IS `now()` — WHEN THE RECORD WAS WRITTEN — NEVER THE ACT'S
-- TIME TYPED IN. The act ran at 2026-09-07T08:36:52Z (the runner's transcript,
-- recorded in the r226 judgement commit fca86bb0), but the DATABASE holds no
-- witness to that instant: the raw-SQL archive did not bump
-- `practices.updatedAt`, which still reads 2026-04-13 / 2026-05-03. A literal
-- with no in-database witness is the fabrication #230 warns against. The act's
-- time travels in `metadata.act.executedAt`, attributed to its source.
-- ============================================================================
\set ON_ERROR_STOP on
BEGIN;

-- ── The population, named once. The same six ids as the r226 act. ───────────
CREATE TEMP TABLE r230_practices(id text PRIMARY KEY) ON COMMIT DROP;
INSERT INTO r230_practices(id) VALUES
  ('clinic_test_b'),
  ('cmopgtjqc000h01qxbysh3ccz'),
  ('cmophsjyy000001qqmp2e4qdn'),
  ('cmoq7v57p000z01qqp9u9gd16'),
  ('cmoq7w8vj001301qquq6wzxgc'),
  ('cmoq7wjfm001b01qqvwjqtuih');

-- ── What must not move, captured INSIDE the act so the comparison is exact. ─
CREATE TEMP TABLE r230_before ON COMMIT DROP AS
SELECT (SELECT count(*) FROM practices)                                        AS practices,
       (SELECT count(*) FROM practices WHERE "isActive" = false)               AS archived,
       (SELECT count(*) FROM users)                                            AS users,
       (SELECT count(*) FROM transcribe_visits)                                AS visits,
       (SELECT count(*) FROM transcribe_visits WHERE "signedAt" IS NOT NULL)   AS signed,
       (SELECT string_agg(p.id || '@' || p."updatedAt"::text || '#' || p."isActive"::text, ',' ORDER BY p.id)
          FROM practices p JOIN r230_practices r ON r.id = p.id)               AS six_state,
       (SELECT string_agg(u.id || '@' || u."updatedAt"::text, ',' ORDER BY u.id)
          FROM users u JOIN r230_practices r ON r.id = u."practiceId")         AS six_users_state;

-- ══ PRE-GUARDS — refuse if the world is not what the declaration says ════════
DO $pre$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n FROM r230_practices r JOIN practices p ON p.id = r.id WHERE p."isActive" = false;
  IF n <> 6 THEN RAISE EXCEPTION 'r230: expected the 6 named practices to exist and be archived, found %', n; END IF;

  -- The archived set is EXACTLY the six. If ADMIN-6 or anything else has archived
  -- another practice since the declaration, this is not the act that was declared.
  SELECT count(*) INTO n FROM practices WHERE "isActive" = false;
  IF n <> 6 THEN RAISE EXCEPTION 'r230: expected exactly 6 archived practices in total, found %', n; END IF;

  -- Nothing has written these rows yet — including this script, run twice.
  SELECT count(*) INTO n FROM audit_logs WHERE action::text = 'PRACTICE_ARCHIVED';
  IF n <> 0 THEN RAISE EXCEPTION 'r230: % PRACTICE_ARCHIVED row(s) already exist — refusing', n; END IF;
  SELECT count(*) INTO n FROM audit_logs WHERE id LIKE 'r230-%';
  IF n <> 0 THEN RAISE EXCEPTION 'r230: % row(s) with an r230- id already exist — refusing', n; END IF;

  -- The enum value exists (ADMIN-3a's migration). Without it the INSERT would fail
  -- anyway; this makes the refusal say why.
  SELECT count(*) INTO n FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid
   WHERE t.typname = 'AuditAction' AND e.enumlabel = 'PRACTICE_ARCHIVED';
  IF n <> 1 THEN RAISE EXCEPTION 'r230: AuditAction has no PRACTICE_ARCHIVED label — migration 20260909080000 not applied'; END IF;

  -- Corroborate the act these rows describe: its five reconciled users carry the
  -- ruling identifier it wrote.
  SELECT count(*) INTO n FROM users u JOIN r230_practices r ON r.id = u."practiceId"
   WHERE u."deactivatedBy" = 'r226-ruling-2026-09-07';
  IF n <> 5 THEN RAISE EXCEPTION 'r230: expected 5 users carrying r226-ruling-2026-09-07 in the six, found %', n; END IF;

  RAISE NOTICE 'r230 pre-guards: 6 archived (and only 6), 0 existing rows, enum present, r226 corroborated';
END
$pre$;

-- ══ THE ACT — six rows, in the shape `updatePractice()` writes for an archive ═
-- `changed.isActive {from,to}` and `reason` are exactly the live writer's keys
-- (`apps/transcribe-md/src/lib/practice-write.ts`), so every reader of
-- PRACTICE_ARCHIVED sees one format. The rest says what this row is and where
-- its evidence lives.
INSERT INTO audit_logs
  (id, action, "practiceId", "practiceIdSnapshot", "targetType", "targetId",
   "userId", "userEmailSnapshot", success, metadata, "timestamp")
SELECT 'r230-practice-archived-' || r.id,
       'PRACTICE_ARCHIVED'::"AuditAction",
       r.id, r.id, 'Practice', r.id,
       NULL, NULL, true,
       jsonb_build_object(
         'changed',  jsonb_build_object('isActive', jsonb_build_object('from', true, 'to', false)),
         'reason',   'ruling #226 — archive the six test practices (row backfilled per #230)',
         'backfill', true,
         'ruling',   '#226/#230',
         'actor',    'r226-ruling-2026-09-07',
         'act',      jsonb_build_object(
                       'declaration',       'docs/deploy-declarations/20260907-r226-archive-six-test-practices.md',
                       'declarationCommit', '071b80ab',
                       'judgementCommit',   'fca86bb0',
                       'executedAt',        '2026-09-07T08:36:52Z',
                       'executedAtSource',  'the run-ruled-mutation transcript, recorded in the r226 judgement'),
         'backfillDeclaration', 'docs/foundation/mutations/20260910-r230-practice-archived-backfill.md'),
       now()
  FROM r230_practices r;

-- ══ POST-VERIFICATION — ROLLS BACK ON ANY MISMATCH ═════════════════════════
DO $post$
DECLARE n int; b record;
BEGIN
  SELECT * INTO b FROM r230_before;

  SELECT count(*) INTO n FROM audit_logs a JOIN r230_practices r ON a.id = 'r230-practice-archived-' || r.id
   WHERE a.action::text = 'PRACTICE_ARCHIVED' AND a."practiceId" = r.id AND a."targetId" = r.id
     AND a."targetType" = 'Practice' AND a."userId" IS NULL
     AND a.metadata #>> '{changed,isActive,to}' = 'false';
  IF n <> 6 THEN RAISE EXCEPTION 'r230 VERIFY C1: % of 6 rows carry the declared shape', n; END IF;

  SELECT count(*) INTO n FROM audit_logs WHERE action::text = 'PRACTICE_ARCHIVED';
  IF n <> 6 THEN RAISE EXCEPTION 'r230 VERIFY C2: % PRACTICE_ARCHIVED rows in total, expected 6', n; END IF;

  SELECT count(*) INTO n FROM audit_logs WHERE id LIKE 'r230-%';
  IF n <> 6 THEN RAISE EXCEPTION 'r230 VERIFY C3: % r230- rows, expected 6', n; END IF;

  -- N1 — the clinical counts, never omitted per §2.5.
  IF (SELECT count(*) FROM transcribe_visits) <> b.visits
     OR (SELECT count(*) FROM transcribe_visits WHERE "signedAt" IS NOT NULL) <> b.signed THEN
    RAISE EXCEPTION 'r230 VERIFY N1: CLINICAL COUNTS MOVED inside the act';
  END IF;
  -- N2 — nothing but audit rows: practices and users untouched, row for row.
  IF (SELECT count(*) FROM practices) <> b.practices OR (SELECT count(*) FROM users) <> b.users THEN
    RAISE EXCEPTION 'r230 VERIFY N2: a practices or users row count moved';
  END IF;
  IF (SELECT count(*) FROM practices WHERE "isActive" = false) <> b.archived THEN
    RAISE EXCEPTION 'r230 VERIFY N3: the archived set moved';
  END IF;
  IF (SELECT string_agg(p.id || '@' || p."updatedAt"::text || '#' || p."isActive"::text, ',' ORDER BY p.id)
        FROM practices p JOIN r230_practices r ON r.id = p.id) IS DISTINCT FROM b.six_state THEN
    RAISE EXCEPTION 'r230 VERIFY N4: a named practice row changed';
  END IF;
  IF (SELECT string_agg(u.id || '@' || u."updatedAt"::text, ',' ORDER BY u.id)
        FROM users u JOIN r230_practices r ON r.id = u."practiceId") IS DISTINCT FROM b.six_users_state THEN
    RAISE EXCEPTION 'r230 VERIFY N5: a member row of the six changed';
  END IF;

  RAISE NOTICE 'r230 VERIFY: 6 rows in the declared shape, 6 PRACTICE_ARCHIVED in total, practices/users/visits untouched (visits %/signed %).', b.visits, b.signed;
END
$post$;

COMMIT;
