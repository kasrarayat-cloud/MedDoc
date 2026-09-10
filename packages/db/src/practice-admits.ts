// ============================================================================
// ADMIN-6a — THE ONE PREDICATE FOR "DOES THIS PRACTICE ADMIT ITS MEMBERS?"
// ----------------------------------------------------------------------------
// `practices.isActive` had ZERO readers (measured at 6fcd21d0, raw SQL
// included). Ruling #226 said so in its own words — "a MARKER, not an
// enforcement point" — so an archive set the flag and turned nothing off.
// ADMIN-6a makes the flag a SWITCH, and this file is the only place the rule is
// stated.
//
// ⚠️ EXACTLY THREE DOORS READ IT, AND A GATE PINS THAT BOTH WAYS
// (`gate-admin6a-practice-active-readers.test.ts`):
//
//   D1  login              apps/transcribe-md/src/lib/nextauth.ts    authorize()
//   D2  every request      packages/auth/src/user-session.ts         validateSession()
//   D3  invite redemption  apps/transcribe-md/src/actions/auth.ts    signupAction's transaction
//
// D2 is the one that does the work: a `null` from `validateSession` ends the
// session inside the shared jwt callback, which covers every `auth()`,
// `getSession()`/`requireSession()` and `adminApi()` caller at once. D1 and D3
// stop a NEW session or a NEW member arriving.
//
// ⚠️ D4 — THE WORKER — IS DELIBERATELY NOT A DOOR. It is on the clinical
// generation path. Instead the archive act REFUSES while any visit of the
// practice is still being processed (`practice-write.ts`), so there is nothing
// in flight for a worker door to stop.
//
// ⚠️ WHY A SUBPATH EXPORT AND NOT A NAMED EXPORT ON `@meddoc/db`: dozens of test
// files `vi.mock('@meddoc/db', () => ({ default: … }))`. A named export from
// that specifier would be ABSENT under every one of those mocks, and vitest
// throws on a missing export of a mocked module — or, worse, a hand-rolled
// fallback would read `undefined` and fail open. This file imports nothing, so
// no mock can replace it.
// ============================================================================

/**
 * The `where` fragment a practice must match to admit its members. Spread it
 * into a Prisma `where` (D3) so the database answers, not a second comparison.
 */
export const PRACTICE_ADMITS = { isActive: true } as const;

/**
 * The `select` fragment a door must load to evaluate {@link practiceAdmits}.
 * DERIVED from `PRACTICE_ADMITS`, never retyped: a column added to the
 * predicate and forgotten here would arrive `undefined` and refuse everyone,
 * or — if someone "fixed" that by defaulting — admit everyone.
 */
export const PRACTICE_ADMITS_SELECT = Object.fromEntries(
  Object.keys(PRACTICE_ADMITS).map((k) => [k, true]),
) as { [K in keyof typeof PRACTICE_ADMITS]: true };

/**
 * Does this loaded practice admit its members?
 *
 * ⚠️ FAIL-CLOSED ON ABSENCE. `null`/`undefined` — the relation was not loaded,
 * or the row is gone — REFUSES. `User.practiceId` is NOT NULL with an FK, so in
 * production the practice always loads; the only way to reach absence is a
 * select that forgot the relation, and that must refuse rather than admit.
 *
 * ⚠️ AND IT COMPARES WITH `===` AGAINST THE PREDICATE'S OWN VALUE, so a
 * truthy-but-wrong value (a string `'true'`, a `1`) does not admit.
 */
export function practiceAdmits(
  practice: { readonly [K in keyof typeof PRACTICE_ADMITS]?: unknown } | null | undefined,
): boolean {
  if (practice == null) return false;
  return (Object.keys(PRACTICE_ADMITS) as (keyof typeof PRACTICE_ADMITS)[]).every(
    (k) => practice[k] === PRACTICE_ADMITS[k],
  );
}
