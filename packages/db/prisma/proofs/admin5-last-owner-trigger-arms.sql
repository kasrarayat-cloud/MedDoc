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

-- ══════════════════════════════════════════════════════════════════════════
-- P_LEGACY — ZERO active owners AND a LIVE member. RULING #240a.
--
-- ⚠️ THIS IS THE ONLY SHAPE THAT REACHES EXEMPTION 1, AND NOTHING REACHED IT.
-- Round two measured the consequence: **delete exemption 1 entirely and all 35
-- arms stay green** — including arms 28-32, the five written to protect it.
-- They run against P_DEAD, whose two members are BOTH `isActive=false`, so
-- `members_left` is 0 and **exemption 2** returns before exemption 1 is ever
-- load-bearing. Five arms pointing at a clause none of them can see.
--
-- ⚠️ AND THE FIXTURE MUST BE SEEDED WITH THE TRIGGER DISARMED, WHICH IS THE
-- POINT RATHER THAN A WORKAROUND. This state can no longer be CREATED — arms 14
-- and 33 refuse both doors into it — but it EXISTS: the migration's own install
-- NOTICE counts the practices already in it and says "these stay writable via
-- exemption 1". A guard for legacy data needs legacy data, and legacy data by
-- definition predates the guard.
-- ⚠️ NO NESTED `BEGIN; … COMMIT;` HERE, AND THE FIRST DRAFT HAD ONE.
-- This whole file is ONE transaction (line 19) that ends in `ROLLBACK` so it
-- leaves the database exactly as it found it. A nested `COMMIT` does not close
-- an inner block — Postgres has no nested transactions — it **ENDS THE OUTER
-- ONE**, committing every fixture row written so far and leaving them behind
-- forever. In CI that database is the one the seed and the whole E2E suite then
-- use. `SET LOCAL` is transaction-scoped, so the disarm reverts at the outer
-- ROLLBACK with the rows.
SET LOCAL session_replication_role = 'replica';
INSERT INTO "practices"(id,name,slug,"updatedAt") VALUES
  ('t210_plegacy','T210 Legacy','t210-legacy',now());
INSERT INTO "users"(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
  ('t210_lg_own','t210lgo@x.test','x',now(),'t210_plegacy','OWNER',     false),
  ('t210_lg_mem','t210lgm@x.test','x',now(),'t210_plegacy','CLINICIAN', true);
-- ⚠️ RE-ARM IMMEDIATELY. Every arm below must run against a LIVE trigger; a
-- disarm left in place would make all 38 of them measure nothing at all.
SET LOCAL session_replication_role = 'origin';

-- ⚠️ POSITIVE CONTROL ON THAT FIXTURE. If it is not 0 active owners / 1 LIVE
-- member then arm 36 below is exercising exemption 2 like its five
-- predecessors, and would pass for the same wrong reason they do.
INSERT INTO arm_result
SELECT 'FIXTURE-CONTROL: P_LEGACY has 0 able owners and 1 LIVE member',
       '0|1', got, CASE WHEN got = '0|1' THEN 'PASS' ELSE 'FAIL' END
  FROM (
    SELECT (SELECT count(*) FROM users u WHERE u."practiceId"='t210_plegacy' AND users_is_active_owner(u))::text
           || '|' ||
           (SELECT count(*) FROM users u WHERE u."practiceId"='t210_plegacy' AND users_is_live_member(u))::text AS got
  ) q;

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
        -- ⚠️ A REFUSAL RAISED BY THE **SETUP** IS NOT THE ARM'S RESULT --
        -- RULING #240b. Setup and statement shared one handler, so a setup
        -- that hit the guard produced `SQLERRM LIKE 'users_last_owner_guard:%'`
        -- and a REFUSED-expecting arm PASSED with its statement never executed
        -- -- and reported 0 vacuous while doing it, because MATCHED-NOTHING is
        -- the only vacuity this harness could previously see.
        --
        -- ⚠️ THE SETUP STAYS INSIDE THIS SUBTRANSACTION ON PURPOSE. Moving it
        -- to its own block would classify the error correctly and LEAK the
        -- setup's writes into every later arm, because it is `T210_UNDO`
        -- unwinding this block that rolls the fixture back. So the inner block
        -- re-raises with a distinguishable prefix instead of relocating the work.
        IF setup IS NOT NULL THEN
            BEGIN
                EXECUTE setup;
            EXCEPTION WHEN others THEN
                RAISE EXCEPTION 'T210_SETUP_FAILED: %', SQLERRM;
            END;
        END IF;
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
        -- ⚠️ TESTED BEFORE THE GUARD CLAUSE, AND THE ORDER IS THE WHOLE FIX.
        -- A setup that trips the guard raises the guard's own message; checked
        -- after, it would still read as REFUSED.
        ELSIF SQLERRM LIKE 'T210_SETUP_FAILED:%'        THEN
              got := 'SETUP-FAILED';
              RAISE NOTICE '%: %', arm, SQLERRM;   -- the detail survives, in the log
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

-- ══════════════════════════════════════════════════════════════════════════
-- RULING #238 — THE THIRD WAY IN, AND IT WAS THE LAST REMAINING DOOR.
--
-- A live member ARRIVING by an UPDATE of `practiceId` reached the exact state
-- arm 14 refuses on INSERT, and both guards stood down: the removal guard by
-- exemption 1 (a CLINICIAN was never an active owner) and the orphan arm by its
-- UPDATE early return (the row was already a live member). Neither counted;
-- neither took the advisory lock.
--
-- ⚠️ IDENTICAL END STATE, OPPOSITE VERDICTS, DECIDED ONLY BY HOW THE MEMBER
-- ARRIVED. Arm 14 covers the INSERT; nothing covered the MOVE. Arm 6 covers
-- moving an owner OUT — the mirror image — which is exactly why the omission
-- reads as an oversight rather than a policy.
SELECT t210_try('33 MOVE a live member INTO a zero-owner practice','REFUSED',
  $$UPDATE users SET "practiceId"='t210_pdead' WHERE id='t210_c'$$);

-- ⚠️ AND THE OTHER DIRECTION MUST STAY OPEN, or #238 has bought the invariant
-- by making the zero-owner practices unrepairable — the same lockout exemption
-- 1 exists to prevent, re-entering through the fix for a different hole.
SELECT t210_try('34 MOVE a member OUT of a zero-owner practice — the rescue','ALLOWED',
  $$UPDATE users SET "practiceId"='t210_pmulti' WHERE id='t210_d1'$$);

-- ⚠️ EXEMPTION 1, AT LAST REACHABLE — RULING #240a. Deleting
-- `IF NOT users_is_active_owner(OLD) THEN RETURN` makes this arm RED, and made
-- nothing red before. The write is benign, the row is not an active owner, and
-- the practice is ALREADY ownerless with somebody live in it: without the
-- exemption the guard counts 0 owners and 1 member and REFUSES — locking a real
-- production practice out of every write, which is the lockout the guard against
-- lockout would itself have created.
SELECT t210_try('35 legacy ownerless practice WITH a live member: a benign write','ALLOWED',
  $$UPDATE users SET "forceLogoutAt"=now() WHERE id='t210_lg_mem'$$);

-- ⚠️ HARNESS SELF-TEST — RULING #240b. `t210_try` credited a refusal raised by
-- an arm's own SETUP to the arm, so a REFUSED-expecting arm whose fixture never
-- built PASSED, and reported 0 vacuous while doing it. This arm's setup trips
-- the guard deliberately; the harness must call that SETUP-FAILED and not
-- REFUSED. ⚠️ IT IS A TEST OF THE INSTRUMENT, NOT OF THE TRIGGER — the statement
-- is never reached, and that is what is being asserted.
-- ══════════════════════════════════════════════════════════════════════════
-- RULING #253 — EMPTYING A PRACTICE IS NOT STRANDING ANYBODY, HOWEVER IT EMPTIES.
--
-- #238 added the `practiceId` comparison to the ORPHAN arm and not to the
-- removal guard's `members_left := members_left + 1`, which adds the row back
-- into the practice it just LEFT. So moving a SOLO owner out computed
-- `members_left` as 0 + 1 = 1 and REFUSED with "while 1 other member(s) remain.
-- Transfer ownership first" — ⚠️ NAMING A REMEDY WITH NOBODY TO PERFORM IT ON,
-- which is the defect recorded at :129-136 pointing the other way.
--
-- ⚠️ ARM 37 IS THE MIRROR OF ARM 6, AND THE PAIR IS THE POINT: the SAME
-- operation — move the last able owner to another practice — REFUSES when
-- members remain (arm 6) and ALLOWS when the practice ends empty (arm 37).
-- Arm 6 alone reads as "moving the last owner is forbidden", which is not the
-- rule. And ⚠️ the shipped 38-arm pack scored 38/38 both WITH and WITHOUT this
-- defect, so nothing here could see it.
--
-- ⚠️ THIS IS THE DOOR `schema.prisma` NAMES BY NAME: "When a solo doctor later
-- wants to work with colleagues, migrate them to a real Practice."
SELECT t210_try('37 move a SOLO owner out — the practice ends EMPTY, nobody is stranded','ALLOWED',
  $$UPDATE users SET "practiceId"='t210_pother' WHERE id='t210_o'$$);

-- The multi-row form of the same fact: a whole roster merged into another
-- practice in ONE statement. The source ends empty; the destination gains an
-- able owner. Both halves are improvements and the write must not be refused.
SELECT t210_try('38 merge a WHOLE roster into another practice in one statement','ALLOWED',
  $$UPDATE users SET "practiceId"='t210_pother' WHERE "practiceId"='t210_pmulti'$$);

SELECT t210_try('36 HARNESS SELF-TEST: a refusal raised by the SETUP is not credited to the arm',
  'SETUP-FAILED',
  $$UPDATE users SET "forceLogoutAt"=now() WHERE id='t210_c'$$,
  $$UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_a'$$);

-- ══════════════════════════════════════════════════════════════════════════
-- ⚠️ THE LOCK IS ASSERTED FROM `pg_locks`, NOT FROM THE SOURCE — RULING #251.
--
-- The textual arm ("does the function body contain pg_advisory_xact_lock, and
-- before the count?") has now been defeated TWICE by comments: first by a `--`
-- line, and then — after the fix that stripped `--` — by a NESTED block comment,
-- because SQL block comments nest and a non-greedy stripper stops at the first
-- terminator. Both times the lock could be DELETED with every arm green.
--
-- ⚠️ NO SPELLING SURVIVES THIS ARM, BECAUSE IT CONSULTS NO TEXT. It performs a
-- write that reaches the counting path and then asks the SERVER whether the
-- advisory lock is held, keyed on the exact pair the guard computes:
-- `hashtext('users_last_owner_guard')` and `hashtext(<practiceId>)`, masked to
-- 32 bits because `pg_locks` exposes them as `oid`. A commented-out lock holds
-- no lock and this reads 0.
CREATE OR REPLACE FUNCTION t210_lock_probe() RETURNS text AS $$
DECLARE before_n int; after_n int; k_class oid; k_obj oid;
BEGIN
    k_class := (hashtext('users_last_owner_guard')::bigint & 4294967295)::oid;
    k_obj   := (hashtext('t210_plock')::bigint & 4294967295)::oid;

    -- ⚠️ ITS OWN PRACTICE, AND ITS OWN KEY. The first version of this probe used
    -- `t210_pmulti` and PASSED WITH THE LOCK DELETED — because an advisory xact
    -- lock is released only at TRANSACTION end, not at subtransaction rollback,
    -- and an earlier arm inserting into that practice had already taken a lock
    -- on the same key. The probe was reading somebody else's lock.
    --
    -- ⚠️ CAUGHT BY ITS OWN CONTROL, which is the only reason it is not shipping
    -- as the third defeated lock arm in this file.
    INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_plock','T210 Lock','t210-lock',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_lk1','tlk1@x.test','x',now(),'t210_plock','OWNER',true),
      ('t210_lk2','tlk2@x.test','x',now(),'t210_plock','OWNER',true);

    -- BEFORE: nothing may hold this key yet, or the "after" reading proves nothing.
    SELECT count(*) INTO before_n FROM pg_locks
     WHERE locktype='advisory' AND pid=pg_backend_pid()
       AND classid=k_class AND objid=k_obj;

    -- A demotion that is ALLOWED (a second able owner remains) and therefore
    -- reaches the lock and the count instead of short-circuiting.
    UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_lk1';

    SELECT count(*) INTO after_n FROM pg_locks
     WHERE locktype='advisory' AND pid=pg_backend_pid()
       AND classid=k_class AND objid=k_obj;

    RAISE EXCEPTION 'T210_LOCK_UNDO:%|%', before_n, after_n;
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'T210_LOCK_UNDO:%' THEN RETURN split_part(SQLERRM, ':', 2); END IF;
    RETURN 'ERR: ' || SQLERRM;
END $$ LANGUAGE plpgsql;

-- ══════════════════════════════════════════════════════════════════════════
-- ⚠️ THE **ROW** LOCK GETS ITS OWN DETECTOR — RULING #251, GAP (1).
--
-- `LOCK-CONTROL` below asks `pg_locks WHERE locktype='advisory'`. A `FOR UPDATE`
-- never takes an advisory lock, so that arm is STRUCTURALLY BLIND to the row
-- set — and round four measured the consequence: #253's widening of the
-- `FOR UPDATE` from owners-only to every member could be REVERTED, or the whole
-- statement DELETED, with all 41 arms, the gate and the race harness green.
--
-- ⚠️ AND THE MIGRATION'S OWN COMMENT POINTED AT `LOCK-CONTROL` AS THE ANSWER FOR
-- THIS CLAUSE. It asks about a different lock. A citation to an instrument that
-- measures something else is the same defect as a citation to a ruling that does
-- not exist.
--
-- THE DETECTOR IS `xmax`, MEASURED NOT ASSUMED: a row locked by the current
-- transaction carries a non-zero `xmax`. Owner-only locks 2 of the 3 rows in the
-- fixture below; the shipped predicate locks all 3. The two are distinguishable,
-- which is the entire requirement.
CREATE OR REPLACE FUNCTION t210_rowlock_probe() RETURNS text AS $$
DECLARE others_total int; others_locked int;
BEGIN
    INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_prow','T210 Row','t210-row',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive") VALUES
      ('t210_rw1','trw1@x.test','x',now(),'t210_prow','OWNER',true),
      ('t210_rw2','trw2@x.test','x',now(),'t210_prow','OWNER',true),
      ('t210_rwc','trwc@x.test','x',now(),'t210_prow','CLINICIAN',true);

    -- An ALLOWED demotion (a second able owner remains), so the guard reaches the
    -- lock and the counts rather than short-circuiting.
    UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_rw1';

    SELECT count(*) INTO others_total
      FROM users WHERE "practiceId"='t210_prow' AND id <> 't210_rw1';
    SELECT count(*) INTO others_locked
      FROM users WHERE "practiceId"='t210_prow' AND id <> 't210_rw1' AND xmax <> '0';

    RAISE EXCEPTION 'T210_ROWLOCK:%|%', others_locked, others_total;
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'T210_ROWLOCK:%' THEN RETURN split_part(SQLERRM, ':', 2); END IF;
    RETURN 'ERR: ' || SQLERRM;
END $$ LANGUAGE plpgsql;

INSERT INTO arm_result
SELECT 'ROW-LOCK-CONTROL (xmax): EVERY other member row is locked, not only the owners',
       '2|2', got, CASE WHEN got = '2|2' THEN 'PASS' ELSE 'FAIL' END
  FROM (SELECT t210_rowlock_probe() AS got) q;

-- ⚠️ THE ORPHAN GUARD'S ADVISORY LOCK GETS ITS OWN ARM TOO — GAP (2).
-- `LOCK-CONTROL` asserted ONE of the guard pair's TWO advisory locks, so
-- `users_no_orphan_member`'s could be deleted outright with every arm green.
-- Each must be independently detectable, or "the lock is load-bearing" is a
-- claim about whichever one somebody happened to measure.
CREATE OR REPLACE FUNCTION t210_orphan_lock_probe() RETURNS text AS $$
DECLARE before_n int; after_n int; k_class oid; k_obj oid;
BEGIN
    k_class := (hashtext('users_last_owner_guard')::bigint & 4294967295)::oid;
    k_obj   := (hashtext('t210_porph')::bigint & 4294967295)::oid;

    INSERT INTO practices(id,name,slug,"updatedAt") VALUES ('t210_porph','T210 Orph','t210-orph',now());
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive")
      VALUES ('t210_op_o','top@x.test','x',now(),'t210_porph','OWNER',true);

    SELECT count(*) INTO before_n FROM pg_locks
     WHERE locktype='advisory' AND pid=pg_backend_pid() AND classid=k_class AND objid=k_obj;

    -- An INSERT of a LIVE non-owner: the orphan arm cannot early-return on it, so
    -- it reaches ITS advisory lock. The practice has an able owner, so the write
    -- is ALLOWED and the lock is the only thing being measured.
    INSERT INTO users(id,email,"passwordHash","updatedAt","practiceId","practiceRole","isActive")
      VALUES ('t210_op_c','topc@x.test','x',now(),'t210_porph','CLINICIAN',true);

    SELECT count(*) INTO after_n FROM pg_locks
     WHERE locktype='advisory' AND pid=pg_backend_pid() AND classid=k_class AND objid=k_obj;

    RAISE EXCEPTION 'T210_ORPHLOCK:%|%', before_n, after_n;
EXCEPTION WHEN others THEN
    IF SQLERRM LIKE 'T210_ORPHLOCK:%' THEN RETURN split_part(SQLERRM, ':', 2); END IF;
    RETURN 'ERR: ' || SQLERRM;
END $$ LANGUAGE plpgsql;

INSERT INTO arm_result
SELECT 'LOCK-CONTROL (pg_locks): the ORPHAN guard holds its own advisory lock',
       '0|1', got, CASE WHEN got = '0|1' THEN 'PASS' ELSE 'FAIL' END
  FROM (SELECT t210_orphan_lock_probe() AS got) q;

INSERT INTO arm_result
SELECT 'LOCK-CONTROL (pg_locks): 0 held before the counted write, 1 held after',
       '0|1', got, CASE WHEN got = '0|1' THEN 'PASS' ELSE 'FAIL' END
  FROM (SELECT t210_lock_probe() AS got) q;

-- ══════════════════════════════════════════════════════════════════════════
-- ⚠️ THE REFUSAL'S SENTENCE IS READ — RULING #256. NO ARM COULD READ IT BEFORE.
--
-- `t210_try` reduces every outcome to ALLOWED / REFUSED / MATCHED-NOTHING /
-- SETUP-FAILED by prefix-matching `users_last_owner_guard:%`. That is the right
-- shape for asking WHETHER a write was refused, and it is structurally blind to
-- WHAT the doctor was told — so all 41 arms passed over a refusal that called
-- the caller an "other member" and told a solo owner to transfer ownership to
-- nobody.
--
-- ⚠️ THE MIGRATION NAMES THAT EXACT CLASS TWICE AS "WORSE THAN NO GUARD" AND
-- THEN SHIPPED IT IN ITS OWN RAISE. A message is a product surface; a pack that
-- cannot see one cannot certify it.
CREATE OR REPLACE FUNCTION t210_message(stmt text) RETURNS text AS $$
BEGIN
    BEGIN
        EXECUTE stmt;
        RETURN 'NOT-REFUSED';
    EXCEPTION WHEN others THEN
        RETURN SQLERRM;
    END;
END $$ LANGUAGE plpgsql;

-- A SOLO owner demoting themselves: refused correctly (arm 21), and the sentence
-- must not invent a member or prescribe an impossible remedy.
INSERT INTO arm_result
SELECT 'MESSAGE-CONTROL: a solo owner is not told to transfer ownership to nobody',
       'names-no-other-member', got,
       CASE WHEN got = 'names-no-other-member' THEN 'PASS' ELSE 'FAIL' END
  FROM (
    SELECT CASE
             WHEN msg LIKE '%other member(s) remain%' OR msg LIKE '%Transfer ownership first%'
               THEN 'FALSE-SENTENCE: ' || msg
             WHEN msg LIKE '%no one to transfer ownership to%' THEN 'names-no-other-member'
             ELSE 'UNEXPECTED: ' || msg
           END AS got
      FROM (SELECT t210_message(
              $$UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_o'$$) AS msg) m
  ) q;

-- ⚠️ THE OTHER HALF, OR THE ARM ABOVE IS SATISFIED BY DELETING BOTH SENTENCES.
-- When OTHER members really do remain, the doctor must still be told to transfer
-- ownership — and the COUNT must be of other people, not of the caller.
INSERT INTO arm_result
SELECT 'MESSAGE-CONTROL: with real others remaining, the count excludes the caller',
       'transfer-1', got,
       CASE WHEN got = 'transfer-1' THEN 'PASS' ELSE 'FAIL' END
  FROM (
    -- ⚠️ ONE, NOT TWO — AND MY FIRST DRAFT OF THIS ARM EXPECTED TWO AND FAILED.
    -- `t210_pmulti` holds three rows: an able OWNER, a SUSPENDED owner and a live
    -- CLINICIAN. Only the clinician is a LIVE MEMBER, so demoting the able owner
    -- genuinely leaves ONE other person behind. The arm was wrong and the code
    -- was right — which is the arm doing its job in the direction nobody plans
    -- for, and the reason the expectation is spelled out here rather than
    -- computed from the same predicate the guard uses.
    SELECT CASE
             WHEN msg LIKE '%while 1 other member(s) remain%' THEN 'transfer-1'
             ELSE 'WRONG-COUNT-OR-SENTENCE: ' || msg
           END AS got
      FROM (SELECT t210_message(
              $$UPDATE users SET "practiceRole"='CLINICIAN' WHERE id='t210_a'$$) AS msg) m
  ) q;

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
       45                                                AS arms_expected,
       CASE WHEN count(*) = 45 AND count(*) FILTER (WHERE verdict='FAIL') = 0
            THEN '🟢 all arms ran and passed'
            ELSE '🔴 ARM COUNT OR VERDICT MISMATCH' END  AS verdict
  FROM arm_result WHERE verdict IS NOT NULL;

ROLLBACK;
