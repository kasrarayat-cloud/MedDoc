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
-- ⚠️ WHY NOT REVOKE: this database has ONE login role and it is SUPERUSER. A
-- superuser bypasses table privileges. It does NOT bypass triggers. That is
-- the same reasoning `20260811070000_b5_ledger_entries` records.
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
--   owners counted by `deactivatedAt IS NULL` alone who CANNOT sign in ....  6
--   practices where the two predicates disagree ..........................  6
--   ⚠️ one of them has ELEVEN members, two rows that `deactivatedAt IS NULL`
--      counts as owners, and exactly ONE owner who can actually administer it
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

COMMENT ON FUNCTION users_is_active_owner("users") IS
    'Ruling #210. The ONE definition of an active practice OWNER: a seat whose holder can actually administer the practice. Counting an owner who cannot authenticate implements a proxy for the invariant rather than the invariant.';

-- ── The guard. ──────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION users_last_owner_guard() RETURNS trigger AS $fn$
DECLARE
    owners_left  BIGINT;
    members_left BIGINT;
BEGIN
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
    SELECT count(*) INTO members_left
      FROM "users" u
     WHERE u."practiceId" = OLD."practiceId"
       AND u."id" <> OLD."id";

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

-- ⚠️ ONE trigger for BOTH operations, not two. The decision is identical for a
-- demotion, a suspension, a soft-delete and a hard delete -- they differ only
-- in which columns move -- and two triggers would be two places to forget.
CREATE TRIGGER "users_last_owner_guard_before_write"
    BEFORE UPDATE OR DELETE ON "users"
    FOR EACH ROW EXECUTE FUNCTION users_last_owner_guard();

-- ⚠️ NO `BEFORE TRUNCATE` ARM, AND THE ABSENCE IS DELIBERATE. Row-level
-- triggers do not fire on TRUNCATE -- `ledger_entries` adds a statement-level
-- arm for exactly that reason. It is not needed HERE because this invariant is
-- conditional on members remaining: `TRUNCATE users` removes every member of
-- every practice, so it strands nobody and violates nothing. An arm that
-- refused it would be guarding a different invariant than the one ruled.

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
       AND t.tgname = 'users_last_owner_guard_before_write';
    IF n_trigger <> 1 THEN
        RAISE EXCEPTION 'admin5_last_owner_trigger: expected 1 trigger on users, found %', n_trigger;
    END IF;

    SELECT count(*) INTO n_function
      FROM pg_proc WHERE proname IN ('users_last_owner_guard', 'users_is_active_owner');
    IF n_function <> 2 THEN
        RAISE EXCEPTION 'admin5_last_owner_trigger: expected 2 functions, found %', n_function;
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
