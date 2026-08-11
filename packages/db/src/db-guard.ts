// ============================================================================
// db-guard — FAIL-CLOSED protection against running DB-mutating test/QA
// scripts (seeders, fixture builders, the E2E cleanup) against PRODUCTION.
// ----------------------------------------------------------------------------
// WHY: the transcribe-md + meddoc-pro test harnesses historically pointed at
// the ambient DATABASE_URL with only an email-prefix convention for safety —
// i.e. `npm run seed:e2e` / the E2E cleanup could seed/DELETE rows in the live
// `meddoc` database (real PHI). See docs/qa-reports/full-qa-20260604T202447Z.md
// finding F1. This guard makes the harness safe-by-default.
//
// DESIGN: fail CLOSED. A DB-mutating script may proceed ONLY when the target
// is POSITIVELY confirmed to be a non-prod database — i.e. its name carries an
// explicit qa/test/e2e/ci marker AND it is not the known production name/host.
// Anything we cannot positively confirm (unset URL, unparseable URL, the prod
// name `meddoc`, the prod VPS host, or any name without a marker) ABORTS.
//
// This file is PURE: zero dependencies, no Prisma import, no I/O. It is safe to
// import from the prisma-free E2E cleanup helper as well as from the seeders.
// Exposed via the `@meddoc/db/guard` subpath so importing it never instantiates
// the Prisma client.
// ============================================================================

/** The production database name. The live app + worker connect to `meddoc`. */
const PROD_DB_NAMES: ReadonlySet<string> = new Set(['meddoc']);

/** The production VPS public host. Defence-in-depth: even a marker-named DB on
 *  this host is refused. (The prod app reaches postgres as `postgres`/`localhost`
 *  on the compose network, so host alone can't *confirm* non-prod — but it can
 *  positively *deny* the public prod host.) */
const PROD_HOSTS: ReadonlySet<string> = new Set(['5.231.107.93']);

/** A database name positively confirms non-prod only if it carries one of
 *  these markers as a whole, `_`/`-`-delimited word (e.g. `meddoc_qa_test`,
 *  `qa`, `transcribe_e2e`, `ci_db`). `meddoc` does NOT match → refused. */
const QA_MARKER = /(^|[_-])(qa|test|e2e|ci)([_-]|$)/i;

export interface DbTarget {
  host: string;
  database: string;
}

export interface GuardResult {
  ok: boolean;
  reason?: string;
  target?: DbTarget;
}

/** Parse the host + database out of a postgres connection string. */
export function describeDbTarget(databaseUrl: string): DbTarget {
  const u = new URL(databaseUrl);
  return {
    host: u.hostname.toLowerCase(),
    database: decodeURIComponent(u.pathname.replace(/^\//, '')).toLowerCase(),
  };
}

/** PURE core check. Returns {ok:false, reason} unless the target is positively
 *  a non-prod database. `host` is optional (the name marker is the primary
 *  signal; host only adds a prod-deny). */
export function checkNonProdDb(database: string, host?: string): GuardResult {
  const db = (database ?? '').trim().toLowerCase();
  const h = (host ?? '').trim().toLowerCase();
  if (!db) return { ok: false, reason: 'no database name present' };
  if (h && PROD_HOSTS.has(h))
    return { ok: false, reason: `host "${h}" is the production VPS` };
  if (PROD_DB_NAMES.has(db))
    return { ok: false, reason: `database "${db}" is the production database name` };
  if (!QA_MARKER.test(db))
    return {
      ok: false,
      reason: `database "${db}" lacks a qa/test/e2e/ci marker — cannot positively confirm a non-prod target`,
    };
  return { ok: true, target: { host: h, database: db } };
}

function fail(detail: string): never {
  throw new Error(
    `[db-guard] FAIL-CLOSED: ${detail}\n` +
      `  Refusing to run a DB-mutating test/QA script.\n` +
      `  Point DATABASE_URL (or the cleanup target) at an ISOLATED qa/test database\n` +
      `  whose name carries a qa/test/e2e/ci marker, e.g. "meddoc_qa_test"\n` +
      `  (see docs/qa/README.md — the meddoc-qa isolated stack).`
  );
}

/** Guard for DATABASE_URL-based scripts (seeders, fixture builders). Reads
 *  process.env.DATABASE_URL by default. Throws (fail-closed) unless the target
 *  is positively a non-prod database. Returns the parsed target on success. */
export function assertNonProdDatabase(
  databaseUrl: string | undefined = process.env.DATABASE_URL
): DbTarget {
  if (!databaseUrl || !databaseUrl.trim()) fail('DATABASE_URL is not set');
  let target: DbTarget;
  try {
    target = describeDbTarget(databaseUrl);
  } catch {
    fail('DATABASE_URL is not a parseable postgres connection string');
  }
  const res = checkNonProdDb(target.database, target.host);
  if (!res.ok) fail(res.reason!);
  return target;
}

/** Guard for the psql-based E2E cleanup, which holds the target database name
 *  (and optionally host) as plain strings rather than a full URL. */
export function assertNonProdDbName(database: string, host?: string): void {
  const res = checkNonProdDb(database, host);
  if (!res.ok) fail(res.reason!);
}

// ============================================================================
// THE OTHER DIRECTION — B6. Is this POSITIVELY the production database?
// ----------------------------------------------------------------------------
// SPEC §2.4: "Prod-only billing writer — refuses in QA/mock. The writer asserts
// it is in production and refuses otherwise." RELAY F4 adds that "incapable"
// needs TWO conditions: the code gate, and credentials that are not real.
// This is the code gate.
//
// ⚠️ IT IS NOT `!checkNonProdDb(...).ok`, AND THAT IS THE WHOLE POINT.
//
// The negation READS like the mirror and is a fail-OPEN. `checkNonProdDb`
// returns not-ok for five genuinely different situations, and only ONE of them
// is "this is production":
//
//     DATABASE_URL unset          → not-ok  → negation says PRODUCTION → writes
//     DATABASE_URL unparseable    → not-ok  → negation says PRODUCTION → writes
//     name has no qa/test marker  → not-ok  → negation says PRODUCTION → writes
//     name is the prod host       → not-ok  → negation says PRODUCTION → writes
//     name is `meddoc`            → not-ok  → negation says PRODUCTION → correct
//
// Four of the five are "we cannot tell", and a billing writer that charges
// money whenever it cannot tell where it is pointing is the fail-open shape
// this programme has now closed three times (a defaulted provenance column,
// a minted request id, `claudeCostCents` returning 0 for an unknown model).
// Both directions must demand POSITIVE confirmation of the thing they permit,
// which means two independent checks rather than one and its negation.
//
// So: the ONLY thing that confirms production is the production database name.
// Anything else — unset, unparseable, a marker name, an unfamiliar name —
// refuses. The two functions are therefore NOT complements: a database called
// `staging` is confirmed by neither, and is refused by both. That gap is
// deliberate. It is the set "we do not know", and both guards decline it.
// ============================================================================

/** PURE core check, the mirror-in-intent of {@link checkNonProdDb} — but not
 *  its negation. Returns `{ok:true}` only when the name IS a known production
 *  database name. Everything else, including anything unrecognised, is refused
 *  with the reason. */
export function checkProdDb(database: string, host?: string): GuardResult {
  const db = (database ?? '').trim().toLowerCase();
  const h = (host ?? '').trim().toLowerCase();
  if (!db) return { ok: false, reason: 'no database name present' };
  // A qa/test/e2e/ci marker is checked FIRST and named explicitly, so the
  // refusal a QA run sees says why it is a QA run rather than the generic
  // "not a production name". Same evidence, a message somebody can act on.
  if (QA_MARKER.test(db))
    return {
      ok: false,
      reason: `database "${db}" carries a qa/test/e2e/ci marker — this is not production`,
    };
  if (!PROD_DB_NAMES.has(db))
    return {
      ok: false,
      reason: `database "${db}" is not a known production database name — cannot positively confirm production`,
    };
  return { ok: true, target: { host: h, database: db } };
}

function failNotProd(detail: string): never {
  throw new Error(
    `[db-guard] FAIL-CLOSED: ${detail}\n` +
      `  Refusing to run the BILLING WRITER outside production.\n` +
      `  SPEC §2.4: the writer asserts it is in production and refuses otherwise.\n` +
      `  This is not a bug and it is not something to work around — a charge\n` +
      `  written against a QA practice is a charge nobody can delete, because\n` +
      `  ledger_entries is append-only by trigger.`
  );
}

/** Guard for the billing writer. Throws unless DATABASE_URL positively names
 *  the production database. Returns the parsed target on success. */
export function assertProdDatabase(
  databaseUrl: string | undefined = process.env.DATABASE_URL
): DbTarget {
  if (!databaseUrl || !databaseUrl.trim()) failNotProd('DATABASE_URL is not set');
  let target: DbTarget;
  try {
    target = describeDbTarget(databaseUrl);
  } catch {
    failNotProd('DATABASE_URL is not a parseable postgres connection string');
  }
  const res = checkProdDb(target.database, target.host);
  if (!res.ok) failNotProd(res.reason!);
  return target;
}
