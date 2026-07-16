// ============================================================================
// Small shared utilities for the E2E suite (T-M10)
// ============================================================================

/** Test email prefix. All test users have this prefix so global teardown
 *  can wipe them out with a single LIKE query without touching real
 *  users. NEVER change without updating cleanup.ts. */
export const TEST_EMAIL_PREFIX = 'qa-e2e-';

/** Unique email for a single test run. Timestamp + random suffix keeps
 *  parallel workers from colliding on the users.email unique index. */
export function uniqueTestEmail(tag: string): string {
  const stamp = Date.now().toString(36);
  const noise = Math.random().toString(36).slice(2, 6);
  return `${TEST_EMAIL_PREFIX}${tag}-${stamp}-${noise}@synthetic.test`;
}

/** Password that passes the signup policy (10+ chars, upper, lower, digit). */
export const TEST_PASSWORD = 'QaE2eTestPass9';
