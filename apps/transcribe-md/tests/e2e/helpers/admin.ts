// ============================================================================
// E2E helper — admin / SUPER_ADMIN seeding + out-of-band assertions (Batch 5)
// ----------------------------------------------------------------------------
// The /admin/* surface is gated on the `Product.SUPER_ADMIN` entitlement
// (apps/transcribe-md/src/lib/admin-api-gate.ts + admin/layout.tsx), which is
// granted MANUALLY via DB (no self-service). These helpers promote a freshly-
// signed-up test user to SUPER_ADMIN and read user state back so specs can
// assert an admin action's real EFFECT (products / suspendedAt / forceLogoutAt),
// not just an HTTP code.
//
// Same guarded psql channel as helpers/rxSafety.ts / seedVisitStates.ts
// (PSQL_BIN in CI; compose exec locally), fail-closed to the qa stack DB.
// ============================================================================

import { execSync } from 'node:child_process';

import { assertNonProdDbName } from '@meddoc/db/guard';

import { QA_COMPOSE as COMPOSE, QA_DB as DB } from './qa-compose';

function psql(sql: string): string {
  const bin = process.env.PSQL_BIN; // CI: full prefix incl. connection string
  if (bin) {
    return execSync(`${bin} -A -t -f -`, {
      input: sql,
      encoding: 'utf8',
      stdio: ['pipe', 'pipe', 'pipe'],
    }).trim();
  }
  assertNonProdDbName(DB); // fail-closed: never touch a prod DB
  return execSync(`${COMPOSE} exec -T postgres psql -U meddoc -d ${DB} -A -t -f -`, {
    input: sql,
    encoding: 'utf8',
    stdio: ['pipe', 'pipe', 'pipe'],
  }).trim();
}

function lit(v: string): string {
  return `'${v.replace(/'/g, "''")}'`;
}

/** Promote a user (by email) to platform SUPER_ADMIN: append the
 *  `Product.SUPER_ADMIN` entitlement (deduped) AND set `mfaEnabled=true`,
 *  which the /admin layout requires before it will render any admin page.
 *  Mirrors the manual DB grant the product documents — no self-service path. */
export function promoteToSuperAdmin(email: string): void {
  psql(
    `UPDATE users SET ` +
      `products = ARRAY(SELECT DISTINCT unnest(products || ARRAY['SUPER_ADMIN']::"Product"[])), ` +
      `"mfaEnabled" = true ` +
      `WHERE email = ${lit(email)};`,
  );
}

/**
 * A psql channel for DESTRUCTIVE writes that fails closed on BOTH branches.
 *
 * ⚠️ `psql()` above calls `assertNonProdDbName` only on the compose branch.
 * When `PSQL_BIN` is set the guard is skipped entirely and the statement goes
 * wherever that variable points — and `PSQL_BIN` is not hypothetical:
 * `.github/workflows/a11y.yml:101` exports it at JOB level, so every step in
 * that workflow inherits `psql "postgresql://…/meddoc"`. That job's postgres is
 * a throwaway service container, but its database is NAMED `meddoc`, which is
 * exactly the name the guard exists to refuse — which is presumably why the
 * branch skips it.
 *
 * That is tolerable for the existing callers (they run only where PSQL_BIN is
 * unset). It is not something new `UPDATE users` helpers should inherit
 * silently, so these two re-assert on whichever target is actually in play.
 * Today nothing reaches the PSQL_BIN branch with these — `e2e.yml` sets no
 * PSQL_BIN — so this costs nothing and fails loudly if that ever changes.
 */
function psqlGuardedWrite(sql: string): void {
  const bin = process.env.PSQL_BIN;
  if (bin) {
    // Parse the database out of the connection string and hold it to the same
    // rule the compose branch is held to.
    const dbName = bin.match(/\/([A-Za-z0-9_-]+)(?:["'\s?]|$)/)?.[1];
    if (!dbName) {
      throw new Error(
        '[admin] refusing a destructive write: PSQL_BIN is set but no database ' +
          'name could be parsed from it, so the target cannot be confirmed non-prod.',
      );
    }
    assertNonProdDbName(dbName);
  } else {
    assertNonProdDbName(DB);
  }
  psql(sql);
}

// ── Login sub-screen fixtures (rounds-c1 / C1-d) ───────────────────────────
// Two of `login-form.tsx`'s four conditional sub-screens are unreachable
// through the UI on a fresh account, so the pack that has to photograph them
// arranges the server-side precondition directly. Both are deliberately the
// NARROWEST write that makes the branch render.

/** Set ONLY `mfaEnabled`, so /login renders its second-factor step.
 *
 *  ⚠️ NOT `promoteToSuperAdmin`, which is the obvious lift and is wrong here:
 *  it also grants `SUPER_ADMIN`, and that changes the very screen under test.
 *  `actions/auth.ts` excludes SUPER_ADMIN from the cross-app entitlement
 *  branch, and `login/page.tsx` redirects admin hosts elsewhere — so the
 *  shortcut would quietly measure a different login.
 *
 *  `mfaSecret` is deliberately left NULL: the sign-in preflight reads
 *  passwordHash / mfaEnabled / isActive / lockedUntil and never looks at the
 *  secret, so the flag alone renders the field. This fixture reaches the
 *  SCREEN, not a passing second factor — scenario 15 owns the real enrolment
 *  round-trip and this pack does not duplicate it. */
export function enableMfaPromptOnly(email: string): void {
  psqlGuardedWrite(`UPDATE users SET "mfaEnabled" = true WHERE email = ${lit(email)};`);
}

/** REPLACE the user's products with MEDDOC_PRO alone, so /login renders the
 *  cross-app redirect panel.
 *
 *  Replace, never append: the branch fires only for an account that HAS
 *  MEDDOC_PRO and LACKS TRANSCRIBE_MD, and signup writes TRANSCRIBE_MD. An
 *  append leaves both present and the panel never renders — the test would
 *  then pass by photographing the ordinary login form. */
export function setProductsMeddocProOnly(email: string): void {
  psqlGuardedWrite(
    `UPDATE users SET products = ARRAY['MEDDOC_PRO']::"Product"[] ` +
      `WHERE email = ${lit(email)};`,
  );
}

export interface AdminUserRow {
  id: string;
  products: string[];
  suspendedAt: string | null;
  forceLogoutAt: string | null;
  mfaEnabled: boolean;
  isActive: boolean;
}

/** Read the committed admin-relevant state for a user (the source of truth
 *  for "did the admin action take effect"). Throws if the user is absent. */
export function getAdminUser(email: string): AdminUserRow {
  const out = psql(
    `SELECT json_build_object(` +
      `'id', id, 'products', products, 'suspendedAt', "suspendedAt", ` +
      `'forceLogoutAt', "forceLogoutAt", 'mfaEnabled', "mfaEnabled", 'isActive', "isActive")::text ` +
      `FROM users WHERE email = ${lit(email)};`,
  );
  if (!out) throw new Error(`getAdminUser: no user row for ${email}`);
  return JSON.parse(out) as AdminUserRow;
}

/** Convenience: the user's id (for /api/admin/users/:id/* calls). */
export function getUserId(email: string): string {
  return getAdminUser(email).id;
}
