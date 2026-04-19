// ============================================================================
// Playwright globalTeardown — belt-and-braces cleanup
// ----------------------------------------------------------------------------
// Each test already cleans up its own user in afterEach, but if any test
// crashed mid-run the afterEach hook may not have fired. This teardown
// runs the same prefix-scoped DELETE one more time so the DB is clean
// for the next suite (and for human inspection).
// ============================================================================

import { cleanupTestUsers } from './helpers/cleanup';

export default async function globalTeardown(): Promise<void> {
  cleanupTestUsers();
}
