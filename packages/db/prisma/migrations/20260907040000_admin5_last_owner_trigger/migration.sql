-- ============================================================================
-- ADMIN-5 / RULING #210 — THE LAST-OWNER INVARIANT, ENFORCED AT THE DATA
-- ----------------------------------------------------------------------------
-- THE INVARIANT
--
--   No write may leave a practice that still has members with zero ACTIVE
--   OWNERs.
--
-- WHY A TRIGGER AND NOT A GUARD. Ruling #210: the invariant binds every
-- surface that can reduce a practice's active-owner count -- a role change, a
-- deactivation, a suspension, a soft-delete, a self-service account deletion.
-- That is five doors today and the set is OPEN: the sixth is written by
-- whoever adds the next admin surface, and they will not read this file. A
-- guard per door is a guard per door you remembered. The `users` row is the
-- one place all of them pass through, so the enforcement lives here and the
-- application guards become the FRIENDLY REFUSAL ("transfer ownership first")
-- rather than the enforcement.
--
-- ⚠️ WHY NOT A CHECK CONSTRAINT: a CHECK sees one row. This invariant is about
-- the SET of a practice's owners, which no row-local expression can express.
--
-- ⚠️ WHY NOT REVOKE: this database has ONE login role and it is SUPERUSER, so a
-- superuser bypasses table privileges. A trigger is a stronger guard than a
-- grant here -- but NOT an absolute one, and the earlier wording of this
-- paragraph ("a superuser does NOT bypass triggers") was FALSE. It was refuted
-- in this change's own adversarial pass, twice, in one statement each:
--
--     SET LOCAL session_replication_role = 'replica';   -- superuser-only
--     ALTER TABLE "users" DISABLE TRIGGER "users_last_owner_guard_after_write";
--
-- Both let the forbidden write through. **A superuser does not bypass triggers
-- BY DEFAULT, and can choose to.** So the honest claim is narrower than the one
-- inherited from `20260811070000_b5_ledger_entries`: this stops every write the
-- APPLICATION can make, through any door, and it does not stop a person at a
-- psql prompt who has decided to turn it off. That is the right guarantee for
-- the threat this ruling names -- a door somebody forgot -- and it is stated
-- here rather than overclaimed.
--
-- ⚠️ AND THE FK-RESTRICT ACCIDENT STOPS BEING LOAD-BEARING. Part of what has
-- been holding this invariant up is `users_practiceId_fkey ... ON DELETE
-- RESTRICT`, which happens to refuse a practice delete while users remain.
-- That is a coincidence that has been lucky, and it is wrong twice over: it is
-- about DELETE and says nothing about UPDATE, while FOUR of the five doors are
-- UPDATEs; and nobody chose it, so the next person to change that relation for
-- an unrelated reason silently removes the guarantee. After this migration the
-- trigger is the load-bearing thing and the FK is incidental again.
--
-- ----------------------------------------------------------------------------
-- WHAT "ACTIVE OWNER" MEANS HERE, AND WHY THE CHOICE IS NOT COSMETIC
--
-- `users` carries FIVE independent expressions of "no longer active":
-- `isActive`, `deactivatedAt`, `suspendedAt`, `softDeletedAt` (plus
-- `lockedUntil` and `forceLogoutAt`, which are transient). The predicate must
-- pick among them and THE CHOICE CHANGES THE ANSWER ON REAL DATA.
--
-- Measured on production, 2026-09-07:
--
--   owners counted by `deactivatedAt IS NULL` alone who CANNOT sign in ....  1
--   practices where the two predicates disagree ..........................  1
--   ⚠️ that ONE practice has ELEVEN members, two rows that `deactivatedAt IS
--      NULL` counts as owners, and exactly ONE owner who can administer it
--
-- ⚠️ THESE READ `6` UNTIL RULING #248, AND `6` WAS A DIFFERENT CLAIM'S NUMBER.
-- Six is the count of ZERO-OWNER PRACTICES. The count of owner rows the loose
-- predicate over-counts is ONE, and the six zero-owner practices are not among
-- them: the two predicates AGREE on every one of those six. Re-measured with a
-- positive control 2026-09-07.
--
-- ⚠️ AND IT IS CANON 124 A THIRD TIME, IN THE FILE THAT RECORDS IT: one
-- alarming number reused for a claim it does not support. The divergence is
-- real and it is worth the predicate — ONE practice with eleven members and a
-- single able owner is exactly the case that matters — but the argument is
-- weakened, not strengthened, by quoting a number six times too large.
--
-- A predicate that counts an owner who cannot authenticate does not implement
-- "somebody can administer this practice"; it implements a proxy that diverges
-- from it. So the predicate here is the CONJUNCTION -- and it is stated ONCE,
-- in `users_is_active_owner`, because a rule with several readers contradicts
-- itself the day one of them is changed.
--
-- ----------------------------------------------------------------------------
-- THE TWO EXEMPTIONS, STATED SO NEITHER IS MISTAKEN FOR AN OVERSIGHT
--
-- 1 · THE ROW WAS NOT AN ACTIVE OWNER TO BEGIN WITH -> allowed.
--     A write that does not remove an active-owner seat cannot reduce the
--     count. This is also what makes the migration INSTALLABLE: production
--     already holds 6 practices with zero active owners, and without this
--     exemption every one of their user rows would become unwritable
--     forever -- a lockout created by the guard against lockout.
--
-- 2 · NO OTHER USER ROW REMAINS IN THE PRACTICE -> allowed.
--     The harm this invariant exists to prevent is STRANDED MEMBERS: people
--     who belong to a practice nobody can administer. A practice with no
--     remaining members strands nobody -- it is being torn down, and that is
--     the self-service account-deletion path (`/api/settings/delete-account`
--     deletes the user and then the practice) that ruling #210 names as a
--     bound surface. Refusing it would break a shipped feature for every
--     solo practice, which is most of them.
--     ⚠️ The APP layer still refuses a solo owner demoting themselves, with
--     the friendly message. That is policy and belongs there. This is the
--     data invariant, and it is the narrower of the two ON PURPOSE.
--
-- ----------------------------------------------------------------------------
-- SERIALIZATION -- THE PART A COUNT CANNOT DO ALONE
--
-- The ADMIN-5 row forbids "a count read and then acted on", and it is right:
-- two owners demoted at the same instant each see the other, both conclude
-- there is another owner, both write, and the practice is left with ZERO.
-- That is not a window to narrow; a read-then-act check cannot see it by
-- construction.
--
-- So the check takes `pg_advisory_xact_lock` on (this guard, practiceId)
-- BEFORE it counts -- the same instrument `ledger_entries_derive` uses one
-- migration over, transaction-scoped and released on COMMIT or ROLLBACK. Two
-- removals in the same practice serialize; two in DIFFERENT practices never
-- meet. In READ COMMITTED a VOLATILE function takes a fresh snapshot per
-- statement, so the second one sees the first one's committed write.
--
-- ⚠️ THAT LAST SENTENCE IS AN ARGUMENT, NOT A PROOF, AND IT IS PROVEN
-- SEPARATELY BY A HARNESS THAT GENUINELY RACES (ruling #205) WITH THE LOCK
-- REMOVED AS ITS NEGATIVE CONTROL. If deleting the lock does not produce a
-- zero-owner practice, the lock was never the thing doing the work.
--
-- ⚠️ THE LOCK IS TAKEN ONLY ON THE PATH THAT CAN ACTUALLY REDUCE THE COUNT.
-- Every other write to `users` -- a login timestamp, an MFA enrolment, a
-- password change -- returns before the lock is reached and pays nothing.
-- ============================================================================

-- ── The predicate, defined ONCE. ────────────────────────────────────────────
-- Both the trigger and the application's SQL guard must mean the same thing by
-- "active owner"; a second copy of this rule drifts from the first the day
-- either is edited, and nothing would fail while they disagreed.
CREATE OR REPLACE FUNCTION users_is_active_owner(u "users") RETURNS boolean AS $fn$
    SELECT u."practiceRole" = 'OWNER'::"PracticeRole"
       AND u."isActive"
       AND u."deactivatedAt"  IS NULL
       AND u."suspendedAt"    IS NULL
       AND u."softDeletedAt"  IS NULL;
$fn$ LANGUAGE sql IMMUTABLE;

-- ⚠️ AND "MEMBER" NEEDS ITS OWN DEFINITION, FOR THE SAME REASON.
-- Exemption 2 asks "is anyone left to strand?", and the first version answered
-- it with a bare row count. Refuted in this change's adversarial pass: a
-- practice whose only other row was a SOFT-DELETED ex-employee could no longer
-- delete its own owner -- and the refusal named a remedy ("transfer ownership
-- first") that is unreachable, because a soft-deleted account cannot receive
-- ownership. A permanent refusal naming an impossible cure is worse than no
-- guard.
--
-- A row that cannot be stranded does not count.
--
-- ⚠️ SUSPENSION IS **EXCLUDED**, AND THE SENTENCE HERE USED TO SAY THE OPPOSITE
-- OF THE FUNCTION THREE LINES BELOW IT -- RULING #241a. It read "Suspension
-- DOES count: a suspended member still has an account and can be restored, so
-- they are a person left behind", while the predicate carries
-- `AND u."suspendedAt" IS NULL`.
--
-- THE CODE IS RIGHT, AND THE REASON IS MEASURED: counting a suspended person as
-- a member would make SUSPENDING A SOLO PRACTICE OWNER IMPOSSIBLE -- suspend the
-- owner and the practice has zero able owners with one "member" (the owner's own
-- suspended row, or a suspended colleague) still counted, so the guard refuses a
-- legitimate operations action forever. `gate-admin5-last-owner-invariant.test.ts`
-- pins the exclusion by name, with two independent assertions that go red if
-- `suspendedAt` is removed from the predicate.
--
-- ⚠️ AND AN ADVERSARIAL LENS GOT THIS BACKWARDS, WHICH IS WHY THE SENTENCE IS
-- CORRECTED RATHER THAN THE FUNCTION. It reproduced the behaviour exactly and
-- then named the WRONG artifact defective; acting on its diagnosis would have
-- broken solo-owner suspension. **A correct observation with an inverted
-- diagnosis is the most expensive kind of finding**, and a comment that
-- contradicts the code three lines below it is how one gets invited -- in a file
-- that spends 150 lines warning that a rule with two readers drifts.
--
-- So: deactivated, soft-deleted and SUSPENDED rows are all excluded. What counts
-- is a member who is live TODAY and would be left with nobody to administer them.
CREATE OR REPLACE FUNCTION users_is_live_member(u "users") RETURNS boolean AS $fn$
    SELECT u."isActive"
       AND u."deactivatedAt" IS NULL
       AND u."softDeletedAt" IS NULL
       AND u."suspendedAt"   IS NULL;
$fn$ LANGUAGE sql IMMUTABLE;

COMMENT ON FUNCTION users_is_live_member("users") IS
    'Ruling #210. A member who could actually be stranded by losing the practice''s last owner. A soft-deleted or deactivated row cannot be stranded and cannot receive ownership, so it must not keep a practice hostage.';

COMMENT ON FUNCTION users_is_active_owner("users") IS
    'Ruling #210. The ONE definition of an active practice OWNER: a seat whose holder can actually administer the practice. Counting an owner who cannot authenticate implements a proxy for the invariant rather than the invariant.';

-- ── The guard. ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION users_last_owner_guard() RETURNS trigger AS $fn$
DECLARE
    owners_left  BIGINT;
    members_left BIGINT;
BEGIN
    -- ⚠️ THE RETURN VALUES BELOW ARE IGNORED. This runs as an AFTER constraint
    -- trigger, where the result is discarded; they are kept because plpgsql
    -- requires a trigger function to return, and because the function must stay
    -- readable as "allow" vs "RAISE". Nothing downstream depends on them.
    -- EXEMPTION 1 — the row was not an active owner, so nothing can be lost.
    IF NOT users_is_active_owner(OLD) THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    -- Still an active owner of the SAME practice afterwards? Nothing lost.
    -- `practiceId` is compared because moving an owner to another practice
    -- removes a seat from the OLD one just as surely as demoting them.
    IF TG_OP = 'UPDATE'
       AND NEW."practiceId" = OLD."practiceId"
       AND users_is_active_owner(NEW) THEN
        RETURN NEW;
    END IF;

    -- From here the write REMOVES an active-owner seat from OLD."practiceId".
    -- Serialize before counting -- see the note above.
    PERFORM pg_advisory_xact_lock(
        hashtext('users_last_owner_guard'),
        hashtext(OLD."practiceId")
    );

    -- ⚠️ LOCK THE SIBLING OWNER ROWS BEFORE COUNTING THEM, AND THE ADVISORY
    -- LOCK IS NOT ENOUGH ON ITS OWN. Refuted in this change's adversarial pass:
    -- under REPEATABLE READ the advisory lock serializes correctly and the
    -- invariant STILL breaks, because the second transaction's snapshot predates
    -- the first one's commit, so the count it takes after acquiring the lock
    -- still sees a demoted owner as active. Classic write skew, and the lock is
    -- innocent -- what made the READ COMMITTED case safe was the per-statement
    -- snapshot, not the lock.
    --
    -- `FOR UPDATE` on those rows makes the same case RAISE instead: under
    -- REPEATABLE READ, locking a row a concurrent transaction has already
    -- committed a change to reports "could not serialize access". SERIALIZABLE
    -- already refused it. So all three isolation levels are now safe, and the
    -- two that are not READ COMMITTED fail LOUDLY rather than silently.
    --
    -- The set is small (a practice's owner rows), it is taken while already
    -- holding the per-practice advisory lock, and the lock order is therefore
    -- the same for every writer -- so this does not introduce a deadlock.
    -- ⚠️ EVERY OTHER ROW IN THE PRACTICE, NOT ONLY THE OWNERS — RULING #248.
    -- This locked `practiceRole = 'OWNER'` only, and then counted TWO things:
    -- `owners_left` (owners) and `members_left` (LIVE MEMBERS). The second count
    -- read rows nothing had locked, so a concurrent write to a non-owner member
    -- could change `members_left` between this lock and that count — the
    -- read-then-act the lock exists to prevent, surviving in the half nobody
    -- locked.
    --
    -- ⚠️ AND ITS REMOVAL REDDENED NOTHING. Round three measured it: the row set
    -- could be emptied entirely with the arms 38/38, the gate 23/23 and the race
    -- harness green, because a single-transaction proof cannot see a lock at all.
    -- That is why #246 replaces the textual lock arm with a `pg_locks` assertion.
    --
    -- The predicate is now the WHOLE practice minus the row being written: both
    -- counts read subsets of it, so locking their union is the only form that
    -- cannot drift when either count's definition changes.
    PERFORM 1
       FROM "users" u
      WHERE u."practiceId" = OLD."practiceId"
        AND u."id" <> OLD."id"
        FOR UPDATE;

    SELECT count(*) INTO owners_left
      FROM "users" u
     WHERE u."practiceId" = OLD."practiceId"
       AND u."id" <> OLD."id"
       AND users_is_active_owner(u);

    IF owners_left > 0 THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    -- EXEMPTION 2 — nobody is left to strand.
    --
    -- ⚠️ AND ON AN UPDATE THE ROW ITSELF IS ONE OF THE PEOPLE LEFT BEHIND.
    -- The first version counted only OTHER rows, which is right for a DELETE
    -- (the row is going) and WRONG for an UPDATE (the row stays). Measured in
    -- this change's adversarial follow-up: a SOLO owner demoting themselves to
    -- CLINICIAN was ALLOWED, leaving a practice with one live member who can log
    -- in, cannot administer, and has nobody left to promote them. 2 of 5 race
    -- runs ended in exactly that state.
    SELECT count(*) INTO members_left
      FROM "users" u
     WHERE u."practiceId" = OLD."practiceId"
       AND u."id" <> OLD."id"
       AND users_is_live_member(u);

    -- ⚠️ AND `practiceId` IS COMPARED HERE TOO — RULING #248, AND #238 LANDED IN
    -- ONLY ONE OF THE TWO PLACES THAT NEEDED IT.
    --
    -- This clause adds the row ITSELF back when the write leaves it behind as a
    -- live member. That is right when the row STAYS. When the row MOVES to
    -- another practice it is no longer in `OLD."practiceId"` at all, and
    -- counting it there invents a member who is not present:
    --
    --   move a SOLO OWNER into a real practice -> the old practice ends EMPTY,
    --   `members_left` is computed as 0 + 1 = 1, and the write is REFUSED with
    --   "while 1 other member(s) remain. Transfer ownership first." There is
    --   nobody to transfer to. ⚠️ THE REFUSAL NAMES AN IMPOSSIBLE REMEDY — the
    --   exact defect recorded at :129-136 for the bare row count, in the other
    --   direction.
    --
    -- ⚠️ AND IT IS THE ASYMMETRY #238 WAS WRITTEN TO REMOVE, SURVIVING IN THE
    -- SIBLING FUNCTION: emptying a practice by DELETING its solo owner is
    -- ALLOWED (arm 9), emptying it by MOVING the same owner was REFUSED.
    -- Identical end state, opposite verdicts, decided only by how it emptied.
    --
    -- ⚠️ THIS IS THE DOOR THE SCHEMA NAMES. `schema.prisma`: "When a solo doctor
    -- later wants to work with colleagues, migrate them to a real Practice."
    IF TG_OP = 'UPDATE'
       AND NEW."practiceId" = OLD."practiceId"
       AND users_is_live_member(NEW) THEN
        members_left := members_left + 1;
    END IF;

    IF members_left = 0 THEN
        IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
        RETURN NEW;
    END IF;

    RAISE EXCEPTION
        'users_last_owner_guard: refusing to leave practice % with zero active OWNERs while % other member(s) remain. Transfer ownership first.',
        OLD."practiceId", members_left
        USING ERRCODE = '23514';
END;
$fn$ LANGUAGE plpgsql;

COMMENT ON FUNCTION users_last_owner_guard() IS
    'Ruling #210. Refuses any UPDATE or DELETE that would leave a practice with members but no active OWNER. Enforcement lives here because five application doors reduce the count and the set is open.';

-- ⚠️ A **CONSTRAINT** TRIGGER, AND THE REASON IS A DEFECT THIS FOUND IN ITSELF.
--
-- The first version of this migration was a plain `BEFORE UPDATE OR DELETE ...
-- FOR EACH ROW` trigger, exactly as ruling #210 words it. It was measured
-- against the E2E suite's own teardown and REFUSED IT:
--
--   cleanup.ts:99 -- DELETE FROM users WHERE id IN (SELECT id FROM target)
--   -> users_last_owner_guard: refusing to leave practice e2e_p with zero
--      active OWNERs while 3 other member(s) remain.
--
-- A BEFORE row trigger fires BEFORE the statement's other rows are applied, so
-- when the owner's row is processed the three members it is being deleted
-- ALONGSIDE are still present, and the guard reads a practice that is losing
-- its owner and keeping its members. It is not: the whole practice is going.
--
-- ⚠️ AND IT IS ORDER-DEPENDENT, WHICH IS WORSE THAN WRONG. Whether the owner
-- row happens to be processed first decides whether a legitimate teardown
-- succeeds. That is canon 121's intermittent guard, in a guard written to
-- illustrate canon 121.
--
-- THE INVARIANT IS A PROPERTY OF THE STATEMENT'S RESULT, SO THE CHECK BELONGS
-- AT THE END OF THE STATEMENT. A CONSTRAINT TRIGGER with `DEFERRABLE INITIALLY
-- IMMEDIATE` is queued and fired once the statement has completed, so the count
-- is taken over the state the statement actually produced.
--
-- ⚠️ THIS DEPARTS FROM #210'S LITERAL WORDING ("a BEFORE UPDATE/DELETE
-- trigger") AND NOT FROM ITS INVARIANT, per #200 -- a ruling binds the
-- invariant and the proof, never the mechanism. Everything the BEFORE form
-- refused that it SHOULD refuse, this form still refuses; the arms and the
-- race harness are the evidence, and both are run against this shape.
CREATE CONSTRAINT TRIGGER "users_last_owner_guard_after_write"
    AFTER UPDATE OR DELETE ON "users"
    DEFERRABLE INITIALLY IMMEDIATE
    FOR EACH ROW EXECUTE FUNCTION users_last_owner_guard();

-- ⚠️ NO `BEFORE TRUNCATE` ARM, AND THE ABSENCE IS DELIBERATE. Row-level
-- triggers do not fire on TRUNCATE -- `ledger_entries` adds a statement-level
-- arm for exactly that reason. It is not needed HERE because this invariant is
-- conditional on members remaining: `TRUNCATE users` removes every member of
-- every practice, so it strands nobody and violates nothing. An arm that
-- refused it would be guarding a different invariant than the one ruled.

-- ============================================================================
-- THE INSERT ARM — BECAUSE THE FORBIDDEN STATE HAS TWO WAYS IN, NOT ONE
-- ----------------------------------------------------------------------------
-- ⚠️ THIS EXISTS BECAUSE THE GUARD ABOVE WAS BYPASSED IN TWO PERMITTED WRITES,
-- demonstrated in this change's own adversarial pass:
--
--   1. suspend the SOLE owner of a practice   -> ALLOWED (exemption 2: nobody
--                                                to strand, and correctly so)
--   2. a CLINICIAN redeems an invite into it  -> ALLOWED (no INSERT arm)
--   => live_members = 1, active_owners = 0. Measured, not argued.
--
-- The second member is stranded on arrival and cannot even be promoted, because
-- `changeMemberRoleAction` requires an OWNER caller and there is none.
--
-- ⚠️ AND THE FIX IS NOT "REMOVE EXEMPTION 2 FOR UPDATES". Suspending a solo
-- practice owner is a legitimate operations action (non-payment, abuse), and
-- refusing it would be a worse product than the hole. The invariant is about
-- MEMBERS AND OWNERS TOGETHER, so the write that completes the violation is the
-- one that must be refused: you may suspend a solo owner, and you may not then
-- add a live member to a practice that has nobody to administer it.
CREATE OR REPLACE FUNCTION users_no_orphan_member() RETURNS trigger AS $fn$
DECLARE
    owners_now BIGINT;
BEGIN
    -- An owner cannot strand themselves, and a row that cannot be stranded
    -- (inactive, deactivated, soft-deleted) is not a member for this purpose.
    IF users_is_active_owner(NEW) OR NOT users_is_live_member(NEW) THEN
        RETURN NEW;
    END IF;

    -- ⚠️ AN INSERT IS NOT THE ONLY WAY TO ADD A LIVE MEMBER. Unsuspending or
    -- reactivating somebody into an ownerless practice strands them just as
    -- surely, and it is an UPDATE whose OLD row is not an active owner -- so the
    -- removal guard returns early on it and never looks. This arm covers the
    -- write that CREATES a live member; when the row was ALREADY one, the
    -- removal guard owns the question and this one must not double-refuse.
    -- ⚠️ AND `practiceId` IS COMPARED, EXACTLY AS THE REMOVAL GUARD COMPARES IT
    -- ONE FUNCTION UP -- RULING #238. Without it this early return was the LAST
    -- REMAINING DOOR into the forbidden state.
    --
    -- "The removal guard owns the question" is true only while the member stays
    -- in the same practice. MOVE a live CLINICIAN into an ownerless practice and
    -- BOTH guards stand down: the removal guard exempts the row because a
    -- CLINICIAN was never an active owner (exemption 1), and this arm exempted
    -- it because it was already a live member. Neither counts, neither takes the
    -- advisory lock, and the end state is the one arm 14 REFUSES on INSERT.
    --
    -- ⚠️ IDENTICAL END STATE, OPPOSITE VERDICTS, DECIDED ONLY BY HOW THE MEMBER
    -- ARRIVED. That is not a policy anybody chose; it is an omission, and the
    -- sibling guard's own comment at :172-173 already says why the comparison
    -- belongs here -- "moving an owner to another practice removes a seat from
    -- the OLD one just as surely as demoting them". Arriving is the same fact
    -- pointed the other way.
    --
    -- ⚠️ NO RUNTIME WRITER OF `users."practiceId"` EXISTS TODAY, and this is
    -- fixed anyway. #210's whole premise is enforcement that does not depend on
    -- remembering doors -- "the sixth is written by whoever adds the next admin
    -- surface, and they will not read this file" -- and the schema comment on
    -- that column names the future door by name: "When a solo doctor later wants
    -- to work with colleagues, migrate them to a real Practice."
    IF TG_OP = 'UPDATE'
       AND NEW."practiceId" = OLD."practiceId"
       AND users_is_live_member(OLD) THEN
        RETURN NEW;
    END IF;

    -- Same lock, same key as the removal guard: an INSERT racing a demotion
    -- must not be able to slip between the demotion's count and its commit.
    PERFORM pg_advisory_xact_lock(
        hashtext('users_last_owner_guard'),
        hashtext(NEW."practiceId")
    );

    SELECT count(*) INTO owners_now
      FROM "users" u
     WHERE u."practiceId" = NEW."practiceId"
       AND u."id" <> NEW."id"
       AND users_is_active_owner(u);

    IF owners_now = 0 THEN
        RAISE EXCEPTION
            'users_last_owner_guard: refusing to place a live member in practice %, which has no active OWNER. Restore or appoint an owner first.',
            NEW."practiceId"
            USING ERRCODE = '23514';
    END IF;

    RETURN NEW;
END;
$fn$ LANGUAGE plpgsql;

COMMENT ON FUNCTION users_no_orphan_member() IS
    'Ruling #210. The other half of the invariant: a live member may not be added to a practice that has no active OWNER. Without it the forbidden state is reachable in two individually-permitted writes.';

-- Deferred to statement end for the same reason as the removal guard: a single
-- INSERT that creates a practice''s owner AND its members must be judged on what
-- the statement produced, not on the order rows happen to be visited in.
CREATE CONSTRAINT TRIGGER "users_no_orphan_member_after_insert"
    AFTER INSERT OR UPDATE ON "users"
    DEFERRABLE INITIALLY IMMEDIATE
    FOR EACH ROW EXECUTE FUNCTION users_no_orphan_member();

-- ============================================================================
-- SELF-VERIFICATION — the migration asserts its own effect before committing.
-- ============================================================================
DO $verify$
DECLARE
    n_trigger  INT;
    n_function INT;
    leaked     INT;
BEGIN
    SELECT count(*) INTO n_trigger
      FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
     WHERE NOT t.tgisinternal AND c.relname = 'users'
       AND t.tgname IN ('users_last_owner_guard_after_write', 'users_no_orphan_member_after_insert');
    IF n_trigger <> 2 THEN
        RAISE EXCEPTION 'admin5_last_owner_trigger: expected 2 triggers on users, found %', n_trigger;
    END IF;

    SELECT count(*) INTO n_function
      FROM pg_proc WHERE proname IN ('users_last_owner_guard', 'users_is_active_owner',
                                     'users_is_live_member', 'users_no_orphan_member');
    IF n_function <> 4 THEN
        RAISE EXCEPTION 'admin5_last_owner_trigger: expected 4 functions, found %', n_function;
    END IF;

    -- ⚠️ NOT AN ASSERTION THAT THE DATA IS CLEAN -- it is NOT. This records
    -- what was true at install time, so a later reading of these numbers is
    -- compared against something rather than guessed at. Exemption 1 is what
    -- keeps these practices writable.
    SELECT count(*) INTO leaked FROM (
        SELECT p.id FROM "practices" p JOIN "users" u ON u."practiceId" = p.id
         GROUP BY p.id
        HAVING count(*) FILTER (WHERE users_is_active_owner(u)) = 0
    ) z;
    RAISE NOTICE 'admin5_last_owner_trigger: installed. Practices with members but no active OWNER at install time: %. These stay writable via exemption 1.', leaked;
END
$verify$;
