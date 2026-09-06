// ============================================================================
// ADMIN-5 — THE GUARD'S SQL, AS DATA.
// ----------------------------------------------------------------------------
// ⚠️ THIS MODULE HAS NO IMPORTS, AND THAT IS ITS ENTIRE REASON FOR EXISTING.
//
// The correctness of the last-owner guard lives in these three statements, and
// the only honest proof of a concurrency property is two real sessions racing
// against a real Postgres. This repository's E2E process deliberately CANNOT
// load Prisma — `tests/e2e/helpers/cleanup.ts` reaches the database through
// `docker compose exec postgres psql` precisely so the test process does not
// depend on `@meddoc/db` compiling or on loading a `.env`.
//
// So the proof and the product must share ONE string. A proof that retypes the
// SQL it is checking proves that the author can type the same thing twice: it
// goes green against a guard that was never shipped, and it stays green when
// the shipped guard changes. Exporting the statements as data lets the E2E arm
// `PREPARE` the EXACT text the server runs — `PREPARE` takes `$1` placeholders,
// which is why the parameters are positional rather than tagged-template.
//
// ⚠️ POSITIONAL PARAMETERS ARE STILL PARAMETERS. These strings reach
// `$executeRawUnsafe(sql, ...params)`, which sends the values to Postgres as
// bound query parameters — the "Unsafe" in the name is about the SQL text being
// a variable, not about the arguments being interpolated. Nothing here
// concatenates a caller's value into the statement, and nothing may start.
// ============================================================================

/**
 * The per-practice lock. `$1` = practiceId.
 *
 * ⚠️ IT LOCKS `practices`, NOT `users`, AND THE CHOICE IS THE DESIGN. The
 * invariant is about the SET of a practice's owners, so the row that must not
 * be missed is the one the OTHER actor is about to write — which no lock on the
 * rows you already know about can cover. One row per practice also means two
 * admin actions in DIFFERENT practices never meet.
 */
export const PRACTICE_LOCK_SQL = 'SELECT id FROM practices WHERE id = $1 FOR UPDATE';

/**
 * The last-owner clause. `$2` = practiceId.
 *
 * ⚠️ THE COUNT IS INSIDE THE STATEMENT, WHICH IS THE WHOLE POINT. The ADMIN-5
 * row forbids "a count read and then acted on"; here nothing reads a count.
 * Postgres evaluates the subquery and performs the write as one statement, and
 * the number of rows affected IS the decision. There is no arithmetic in
 * TypeScript to get wrong, and no window between deciding and writing.
 *
 * ⚠️ `IS DISTINCT FROM`, NOT `<>`. `practiceRole` is NULLABLE, and `NULL <>
 * 'OWNER'` is NULL — which is not TRUE, so a plain `<>` would make the whole
 * conjunction NULL and REFUSE every change to a member whose role is NULL.
 * That is a fail-closed direction, but it would refuse silently and for the
 * wrong reason, and the row it refuses is exactly the one a removed-then-
 * readded member carries.
 */
export const LAST_OWNER_CLAUSE = `(
         "practiceRole" IS DISTINCT FROM 'OWNER'::"PracticeRole"
      OR (SELECT count(*) FROM users u2
           WHERE u2."practiceId" = $2
             AND u2."practiceRole" = 'OWNER'::"PracticeRole"
             AND u2."deactivatedAt" IS NULL) > 1
       )`;

/** Demotion / role change. `$1` = userId, `$2` = practiceId, `$3` = new role. */
export const CHANGE_ROLE_GUARDED_SQL = `UPDATE users
     SET "practiceRole" = $3::"PracticeRole"
   WHERE id = $1
     AND "practiceId" = $2
     AND "deactivatedAt" IS NULL
     AND ${LAST_OWNER_CLAUSE}`;

/**
 * A lateral or promotion. `$1` = userId, `$2` = practiceId, `$3` = new role.
 *
 * ⚠️ NO LAST-OWNER CLAUSE, AND THAT IS A DECISION ABOUT AN INPUT RATHER THAN
 * ABOUT DATA. Moving somebody TO owner cannot reduce the owner count, so
 * guarding it would refuse a move that is safe by construction — and it would
 * refuse it precisely when the practice has one owner, which is the first case
 * a solo owner meets. `$2` is still bound so both statements take the same
 * parameter list and a caller cannot pass them in the wrong order.
 */
export const PROMOTE_SQL = `UPDATE users
     SET "practiceRole" = $3::"PracticeRole"
   WHERE id = $1
     AND "practiceId" = $2
     AND "deactivatedAt" IS NULL`;

/**
 * Removal. `$1` = userId, `$2` = practiceId, `$3` = the actor's id.
 *
 * ⚠️ IT CARRIES THE SAME CLAUSE AS DEMOTION, AND THAT IS THE FINDING THIS
 * FEATURE ALMOST SHIPPED WITHOUT. Removing the last owner destroys "every
 * practice has at least one owner" exactly as demoting them does — removal is
 * the SECOND DOOR to one invariant. A guard fitted to only the first door looks
 * complete and is not.
 *
 * ⚠️ `"practiceRole" = NULL` IS PART OF THE ACT, NOT TIDYING. The column's own
 * doc requires it of a deactivated row — "a deactivated account has no role in
 * a practice, and a sentinel there would be a claim nobody made" — and the
 * `users_active_member_has_practice_role` CHECK permits it because `"isActive"
 * = false` satisfies the first arm. It also means a removed row can never be
 * counted as an owner by any query that forgets the `deactivatedAt` conjunct.
 */
export const REMOVE_MEMBER_GUARDED_SQL = `UPDATE users
     SET "isActive"      = false,
         "deactivatedAt" = now(),
         "deactivatedBy" = $3,
         "practiceRole"  = NULL
   WHERE id = $1
     AND "practiceId" = $2
     AND "deactivatedAt" IS NULL
     AND ${LAST_OWNER_CLAUSE}`;
