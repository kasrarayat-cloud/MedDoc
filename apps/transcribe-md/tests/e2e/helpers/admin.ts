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
