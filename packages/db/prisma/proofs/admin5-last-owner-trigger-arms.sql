-- ============================================================================
-- RULING #210 — DETERMINISTIC ARMS FOR THE LAST-OWNER TRIGGER
-- ----------------------------------------------------------------------------
-- Run against an ISOLATED database that has the migration applied. Everything
-- happens inside ONE transaction that ROLLS BACK, so the target database is
-- byte-unchanged; the concurrency proof is a separate harness, because a race
-- cannot be staged inside a single transaction.
--
--   docker exec -i meddoc-qa-postgres-1 psql -U meddoc -d meddoc_qa_test \
--     -X -v ON_ERROR_STOP=0 -f - < this-file
--
-- ⚠️ EVERY ARM STATES WHAT WOULD MAKE IT FAIL, AND THE REFUSAL ARMS ARE READ
-- OFF THE ERROR, NOT OFF AN ABSENCE. An arm that "passes" because nothing
-- happened is the vacuous-control defect this programme keeps meeting.
-- ============================================================================
\set ON_ERROR_STOP 0
\set QUIET 1
\pset pager off
BEGIN;

CREATE TEMP TABLE arm_result(arm text, expected text, got text, verdict text);

-- ── Fixtures ───────────────────────────────────────────────────────────────
-- P_MULTI : 3 members — able owner A, SUSPENDED owner S, clinician C
--           (S is the shape PR #1026's predicate miscounts as a second owner)
-- P_SOLO  : 1 member — able owner O
-- P_DEAD  : 2 members — both inactive, so ZERO active owners already
-- P_OTHER : 1 member — able owner, the destination for the move arm
INSERT INTO "practices"(id,name,slug,"updatedAt") VALUES
  ('t210_pmulti','T210 Multi','t210-multi',now()),
  ('t210_psolo','T210 Solo','t210-solo',now()),
  ('t210_pdead','T210 Dead','t210-dead',now()),
  ('t210_pother','T210 Other','t210-other',now());

INSERT INTO "users"(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
  ('t210_a','t210a@x.test','x',now(),'t210_pmulti','OWNER',     true),
  ('t210_s','t210s@x.test','x',now(),'t210_pmulti','OWNER',     true),
  ('t210_c','t210c@x.test','x',now(),'t210_pmulti','CLINICIAN', true),
  ('t210_o','t210o@x.test','x',now(),'t210_psolo', 'OWNER',     true),
  ('t210_d1','t210d1@x.test','x',now(),'t210_pdead','OWNER',    false),
  ('t210_d2','t210d2@x.test','x',now(),'t210_pdead','CLINICIAN',false),
  ('t210_z','t210z@x.test','x',now(),'t210_pother','OWNER',     true);
-- S is an OWNER row that `deactivatedAt IS NULL` counts and this trigger does not.
UPDATE "users" SET "suspendedAt" = now() WHERE id = 't210_s';

-- ⚠️ POSITIVE CONTROL ON THE FIXTURE ITSELF. If this row is not 2/1 the whole
-- file is measuring something other than what it claims, and every arm below
-- would pass or fail for the wrong reason.
-- ⚠️ AND IT IS A REAL ARM, NOT A PRINT. The first version recorded this row
-- with a NULL verdict and printed it separately, so a fixture that had drifted
-- would show the wrong numbers in a table nobody's exit code depended on. The
-- adversarial pass called that out: a control whose result is only displayed is
-- a control that is only read when someone is already suspicious.
INSERT INTO arm_result
SELECT 'FIXTURE-CONTROL: #1026 predicate sees 2, this trigger sees 1',
       '2|1',
       got,
       CASE WHEN got = '2|1' THEN 'PASS' ELSE 'FAIL' END
  FROM (
    SELECT (SELECT count(*) FROM users WHERE "practiceId"='t210_pmulti' AND "practiceRole"='OWNER' AND "deactivatedAt" IS NULL)::text
           ||'|'||
           (SELECT count(*) FROM users u WHERE u."practiceId"='t210_pmulti' AND users_is_active_owner(u))::text AS got
  ) z;

-- ── Helper: run a statement, record whether it RAISED ───────────────────────
-- ⚠️ THE UNDO IS INSIDE THE HELPER, AND THE RECORD IS OUTSIDE IT. The first
-- version of this file wrapped each arm in SAVEPOINT/ROLLBACK TO — which also
-- rolled back the INSERT of its own result, so the summary printed
-- "pass 0 | fail 0" and read exactly like a clean run. The fixture control is
-- the only reason that was caught: it printed while the arms did not.
--
-- The shape below cannot do that. The inner BEGIN...EXCEPTION is a
-- subtransaction; raising T210_UNDO after a SUCCESSFUL statement forces that
-- subtransaction to roll back, so an allowed write is undone exactly like a
-- refused one — and the INSERT that records the outcome happens AFTER the
-- block, where nothing rolls it back.
CREATE OR REPLACE FUNCTION t210_try(arm text, expected text, stmt text, setup text DEFAULT NULL)
RETURNS void AS $$
DECLARE got text; n_rows bigint := 0;
BEGIN
    BEGIN
        IF setup IS NOT NULL THEN EXECUTE setup; END IF;
        EXECUTE stmt;
        -- ⚠️ AN ALLOW ARM MUST DISTINGUISH "THE GUARD ALLOWED IT" FROM "THE
        -- STATEMENT MATCHED NOTHING". Both complete without raising, and the
        -- first version called both ALLOWED — so an arm whose fixture drifted
        -- out from under it would go on passing while testing nothing. The
        -- adversarial pass found this across five arms at once.
        GET DIAGNOSTICS n_rows = ROW_COUNT;
        RAISE EXCEPTION 'T210_UNDO';       -- the statement was ALLOWED; undo it
    EXCEPTION WHEN others THEN
        IF    SQLERRM = 'T210_UNDO' AND n_rows > 0      THEN got := 'ALLOWED';
        ELSIF SQLERRM = 'T210_UNDO'                     THEN got := 'MATCHED-NOTHING';
        -- The refusal is identified BY ITS OWN MESSAGE, never by "something threw".
        ELSIF SQLERRM LIKE 'users_last_owner_guard:%'   THEN got := 'REFUSED';
        ELSE  got := 'OTHER-ERROR: ' || SQLERRM;
        END IF;
    END;
    INSERT INTO arm_result VALUES (arm, expected, got, CASE WHEN got = expected THEN 'PASS' ELSE 'FAIL' END);
END $$ LANGUAGE plpgsql;

-- ══ THE ARMS ═══════════════════════════════════════════════════════════════
-- Each runs in its own SAVEPOINT so one refusal does not poison the next.

SELECT t210_try('1  demote the LAST able owner (multi-member)','REFUSED',
  $$UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_a'$$);

SELECT t210_try('2  suspend the LAST able owner','REFUSED',
  $$UPDATE users SET "suspendedAt"=now() WHERE id='t210_a'$$);

SELECT t210_try('3  soft-delete the LAST able owner','REFUSED',
  $$UPDATE users SET "softDeletedAt"=now() WHERE id='t210_a'$$);

SELECT t210_try('4  deactivate (isActive=false) the LAST able owner','REFUSED',
  $$UPDATE users SET "isActive"=false, "practiceRole"=NULL WHERE id='t210_a'$$);

SELECT t210_try('5  DELETE the LAST able owner (members remain)','REFUSED',
  $$DELETE FROM users WHERE id='t210_a'$$);

SELECT t210_try('6  move the LAST able owner to another practice','REFUSED',
  $$UPDATE users SET "practiceId"='t210_pother' WHERE id='t210_a'$$);

-- ⚠️ ARM 7'S ORIGINAL JUSTIFICATION IS OBSOLETE, AND SAYING SO IS THE POINT.
-- It was written to prove a BEFORE row trigger could see its siblings'
-- in-statement changes. The shape is now a CONSTRAINT trigger evaluated at
-- statement end, where that is true by construction — so on its own this arm no
-- longer discriminates between the two shapes, and the adversarial pass was
-- right to call it "arm 1 in disguise".
--
-- IT IS KEPT AS THE REFUSAL HALF OF A PAIR WITH ARM 27, and the pair is what
-- carries the meaning: both are MULTI-ROW statements over the same practice,
-- and they must come out DIFFERENTLY.
--
--     arm 7   demote BOTH owners            -> REFUSED   (result: zero owners)
--     arm 27  demote one, promote another   -> ALLOWED   (result: one owner)
--
-- A guard that judged rows instead of the statement's RESULT cannot produce
-- that asymmetry — it refuses both. Neither arm alone says anything; the
-- difference between them is the assertion.
SELECT t210_try('7  ONE statement demoting BOTH owners (pairs with 27)','REFUSED',
  $$UPDATE users SET "practiceRole"='CLINICIAN' WHERE "practiceId"='t210_pmulti' AND "practiceRole"='OWNER'$$);

-- ══ THE ALLOW ARMS — a guard that refuses everything is not a guard ═════════

SELECT t210_try('8  demote the SUSPENDED owner (not the last ABLE one)','ALLOWED',
  $$UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_s'$$);

SELECT t210_try('9  DELETE the solo owner (practice torn down) — exemption 2','ALLOWED',
  $$DELETE FROM users WHERE id='t210_o'$$);

SELECT t210_try('10 demote an owner where ZERO are already active — exemption 1','ALLOWED',
  $$UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_d1'$$);

SELECT t210_try('11 unrelated write to the last able owner','ALLOWED',
  $$UPDATE users SET "forceLogoutAt"=now() WHERE id='t210_a'$$);

SELECT t210_try('12 demote a CLINICIAN (never an owner)','ALLOWED',
  $$UPDATE users SET "practiceRole"='TECH' WHERE id='t210_c'$$);

-- Two able owners: demoting one is fine, and it is the direct control for arm 1.
SELECT t210_try('13 demote one of TWO able owners — the control for arm 1','ALLOWED',
  $$UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_a'$$,
  $$UPDATE users SET "suspendedAt"=NULL WHERE id='t210_s'$$);   -- S becomes able: 2 able owners

-- ══ ARMS 14-19 — ONE PER DEFECT THE ADVERSARIAL PASS FOUND ═════════════════
-- Every one of these was a demonstrated BYPASS or LOCKOUT before the fix. They
-- are arms rather than notes because a fix without an arm is a fix until the
-- next edit.

-- The pass's finding #1: the forbidden state was reachable in TWO permitted
-- writes — suspend a solo owner (legitimately allowed), then let a clinician
-- redeem an invite. There was no INSERT arm at all.
SELECT t210_try('14 INSERT a live member into a practice with NO active owner','REFUSED',
  $$INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive")
      VALUES ('t210_ins','t210ins@x.test','x',now(),'t210_pdead','CLINICIAN',true)$$);

SELECT t210_try('15 INSERT a live member where an owner IS active — must not be refused','ALLOWED',
  $$INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive")
      VALUES ('t210_ins2','t210ins2@x.test','x',now(),'t210_pmulti','CLINICIAN',true)$$);

-- The rescue path must stay open, or a practice with no owner could never get one.
SELECT t210_try('16 INSERT an OWNER into a practice with no active owner — the rescue','ALLOWED',
  $$INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive")
      VALUES ('t210_res','t210res@x.test','x',now(),'t210_pdead','OWNER',true)$$);

SELECT t210_try('17 INSERT an INACTIVE member into an ownerless practice — cannot be stranded','ALLOWED',
  $$INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive")
      VALUES ('t210_ins3','t210ins3@x.test','x',now(),'t210_pdead','CLINICIAN',false)$$);

-- The pass's finding #3: a SOFT-DELETED ex-employee counted as a "member", so a
-- solo owner could never delete their own account — and the refusal named a
-- remedy (transfer ownership) that a soft-deleted row cannot receive.
SELECT t210_try('18 DELETE a solo owner whose only co-row is SOFT-DELETED','ALLOWED',
  $$DELETE FROM users WHERE id='t210_ghost_o'$$,
  $$INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_pghost','G','t210-g',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_ghost_o','tgo@x.test','x',now(),'t210_pghost','OWNER',true),
      ('t210_ghost_x','tgx@x.test','x',now(),'t210_pghost','CLINICIAN',true);
    UPDATE users SET "softDeletedAt"=now(), "isActive"=false WHERE id='t210_ghost_x'$$);

-- ...but a LIVE co-worker still holds the practice. The direct control for 18.
SELECT t210_try('19 DELETE a solo owner whose co-row is LIVE — the control for 18','REFUSED',
  $$DELETE FROM users WHERE id='t210_live_o'$$,
  $$INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_plive','L','t210-l',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_live_o','tlo@x.test','x',now(),'t210_plive','OWNER',true),
      ('t210_live_x','tlx@x.test','x',now(),'t210_plive','CLINICIAN',true)$$);

-- The E2E suite's own teardown (tests/e2e/helpers/cleanup.ts:99) deletes a whole
-- synthetic practice in ONE statement. The BEFORE row trigger REFUSED this, so
-- this arm is the regression test for the shape change to a constraint trigger.
SELECT t210_try('20 tear a whole practice down in ONE statement (the E2E cleanup shape)','ALLOWED',
  $$DELETE FROM users WHERE "practiceId"='t210_pteardown'$$,
  $$INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_pteardown','T','t210-t',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_td_o','tdo@x.test','x',now(),'t210_pteardown','OWNER',true),
      ('t210_td_1','td1@x.test','x',now(),'t210_pteardown','CLINICIAN',true),
      ('t210_td_2','td2@x.test','x',now(),'t210_pteardown','TECH',true)$$);

-- ══ ARMS 21-24 — THE SECOND ROUND OF FINDINGS ══════════════════════════════
-- Exemption 2 originally counted only OTHER rows. On a DELETE that is right (the
-- row is going); on an UPDATE the row STAYS and is one of the people left
-- behind. 2 of 5 race runs ended with a solo owner demoted to CLINICIAN: able to
-- log in, unable to administer, with nobody left who could promote them.

SELECT t210_try('21 a SOLO owner demotes THEMSELVES — they are the stranded member','REFUSED',
  $$UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_o'$$);

-- ...but suspending that same solo owner must stay legal. A suspended person
-- cannot act, so they are not a member left behind, and suspension is a real
-- operations action (non-payment, abuse). This is the direct control for 21:
-- same practice, same row, opposite verdict.
SELECT t210_try('22 the SAME solo owner is SUSPENDED — the control for 21','ALLOWED',
  $$UPDATE users SET "suspendedAt"=now() WHERE id='t210_o'$$);

-- An INSERT is not the only way to add a live member to an ownerless practice.
SELECT t210_try('23 UNSUSPEND a member into a practice with no active owner','REFUSED',
  $$UPDATE users SET "suspendedAt"=NULL WHERE id='t210_sus_m'$$,
  $$INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_pusp','U','t210-u',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_sus_o','tso@x.test','x',now(),'t210_pusp','OWNER',true),
      ('t210_sus_m','tsm@x.test','x',now(),'t210_pusp','CLINICIAN',true);
    UPDATE users SET "suspendedAt"=now() WHERE id='t210_sus_m';
    UPDATE users SET "suspendedAt"=now() WHERE id='t210_sus_o'$$);

-- ...and the rescue must stay open, or an ownerless practice could never recover.
SELECT t210_try('24 UNSUSPEND the OWNER of that practice — the rescue path','ALLOWED',
  $$UPDATE users SET "suspendedAt"=NULL WHERE id='t210_sus_o2'$$,
  $$INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_pusp2','U2','t210-u2',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_sus_o2','tso2@x.test','x',now(),'t210_pusp2','OWNER',true),
      ('t210_sus_m2','tsm2@x.test','x',now(),'t210_pusp2','CLINICIAN',true);
    UPDATE users SET "suspendedAt"=now() WHERE id='t210_sus_m2';
    UPDATE users SET "suspendedAt"=now() WHERE id='t210_sus_o2'$$);

-- ══ ARMS 25-27 — ORDER-INDEPENDENCE, THE PASS'S TOP SURVIVING FINDING ══════
-- Against the BEFORE row trigger, two practices of IDENTICAL logical shape that
-- differed only in physical INSERT order got OPPOSITE verdicts on the SAME
-- teardown statement — refused or allowed by heap order. Under the constraint
-- trigger the whole statement is judged once, on the state it produced, so both
-- orders agree. 25 and 26 are each other's control: if they ever disagree, the
-- trigger has drifted back to a per-row view.

SELECT t210_try('25 tear down a practice, OWNER row physically FIRST','ALLOWED',
  $$DELETE FROM users WHERE "practiceId"='t210_pord1'$$,
  $$INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_pord1','O1','t210-o1',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_o1_own','to1o@x.test','x',now(),'t210_pord1','OWNER',true),
      ('t210_o1_cli','to1c@x.test','x',now(),'t210_pord1','CLINICIAN',true)$$);

SELECT t210_try('26 the SAME teardown, CLINICIAN row first — control for 25','ALLOWED',
  $$DELETE FROM users WHERE "practiceId"='t210_pord2'$$,
  $$INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_pord2','O2','t210-o2',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_o2_cli','to2c@x.test','x',now(),'t210_pord2','CLINICIAN',true),
      ('t210_o2_own','to2o@x.test','x',now(),'t210_pord2','OWNER',true)$$);

-- An ATOMIC ownership transfer — demote one owner and promote another in ONE
-- statement — is the shape a real transfer feature would use. A per-row view
-- refuses it whenever the outgoing owner is reached first.
SELECT t210_try('27 atomic ownership transfer in ONE statement','ALLOWED',
  $$UPDATE users SET "practiceRole" = (CASE WHEN id='t210_x_own' THEN 'CLINICIAN' ELSE 'OWNER' END)::"PracticeRole"
     WHERE "practiceId"='t210_pxfer'$$,
  $$INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_pxfer','X','t210-x',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_x_own','txo@x.test','x',now(),'t210_pxfer','OWNER',true),
      ('t210_x_cli','txc@x.test','x',now(),'t210_pxfer','CLINICIAN',true)$$);

-- ══ ARMS 28-32 — RULING #222: A ZERO-OWNER PRACTICE STAYS WRITABLE ═════════
-- The invariant is about a write that reduces a practice from ONE able owner to
-- NONE. A practice already at zero cannot be reduced by any write, so refusing
-- there would be a lockout created by the guard against lockout — and it would
-- fall on SIX REAL PRACTICES holding SEVEN REAL USERS in production today.
--
-- Exemption 1 implements it. These arms are what keep it true: one per write
-- shape, because "it works" was measured on one shape and the ruling binds all
-- of them. `t210_pdead` has two members and zero active owners by construction.

SELECT t210_try('28 zero-owner practice: an unrelated write to a member','ALLOWED',
  $$UPDATE users SET "forceLogoutAt"=now() WHERE id='t210_d1'$$);

SELECT t210_try('29 zero-owner practice: change a member''s ROLE','ALLOWED',
  $$UPDATE users SET "practiceRole"='TECH' WHERE id='t210_d2'$$);

SELECT t210_try('30 zero-owner practice: DELETE a member','ALLOWED',
  $$DELETE FROM users WHERE id='t210_d2'$$);

SELECT t210_try('31 zero-owner practice: suspend a member','ALLOWED',
  $$UPDATE users SET "suspendedAt"=now() WHERE id='t210_d1'$$);

-- ⚠️ THE ONE THAT MATTERS MOST, AND IT IS THE RESCUE PATH. If this were
-- refused, a zero-owner practice could never be repaired and the data-hygiene
-- half of #222 would be unexecutable.
SELECT t210_try('32 zero-owner practice: PROMOTE a member to OWNER — the repair','ALLOWED',
  $$UPDATE users SET "practiceRole"='OWNER', "isActive"=true WHERE id='t210_d1'$$);

\pset format aligned
\echo ''
\echo '=== RULING #210 — DETERMINISTIC ARMS ==='
SELECT arm, expected, got, verdict FROM arm_result WHERE verdict IS NOT NULL ORDER BY arm;
\echo ''
SELECT arm, expected AS must_be, got FROM arm_result WHERE verdict IS NULL;
\echo ''
-- ⚠️ THE SUMMARY ASSERTS ITS OWN POPULATION. Counting only the rows that
-- happen to be present lets a silently-dropped arm read as a clean run — the
-- check whose passing condition is an empty set passes hardest when pointed at
-- nothing. EXPECTED_ARMS is stated here and compared.
SELECT count(*) FILTER (WHERE verdict='PASS')            AS pass,
       count(*) FILTER (WHERE verdict='FAIL')            AS fail,
       count(*) FILTER (WHERE got = 'MATCHED-NOTHING')   AS vacuous,
       count(*)                                          AS arms_run,
       33                                                AS arms_expected,
       CASE WHEN count(*) = 33 AND count(*) FILTER (WHERE verdict='FAIL') = 0
            THEN '🟢 all arms ran and passed'
            ELSE '🔴 ARM COUNT OR VERDICT MISMATCH' END  AS verdict
  FROM arm_result WHERE verdict IS NOT NULL;

ROLLBACK;
