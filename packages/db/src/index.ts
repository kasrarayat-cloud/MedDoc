// ============================================================================
// @meddoc/db — Prisma client singleton + health check
// ----------------------------------------------------------------------------
// Shared by both apps (meddoc-pro today, scribe from Milestone 1). Lifted
// verbatim from apps/meddoc-pro/src/lib/db.ts during the monorepo refactor;
// the behavior is unchanged.
//
// If DATABASE_URL is not set or DB is unreachable, queries will throw —
// data-layer callers handle the fallback to in-memory mocks.
// ============================================================================

// ⚠️ F-TYPE 2026-08-07 — THIS WAS A CommonJS `require` CAST TO `any`, AND THE
// `any` WAS LOAD-BEARING IN THE WORST WAY: it made EVERY Prisma argument in the
// entire codebase unchecked. A missing required column, a misspelled field, a
// wrong nested shape — none of it reachable by `tsc`.
//
// The `require` was inherited verbatim from `apps/meddoc-pro/src/lib/db.ts`
// during the monorepo refactor (see the header above), and the usual
// justification — "the generated client cannot be resolved across the workspace
// boundary" — was TESTED AND IS FALSE HERE. A typed import resolves, and the
// generated types are real: a bogus field errors by name against
// `TranscribeVisitCreateInput`, while a legitimate `where: { practiceId }`
// compiles clean. CI already runs `npm run db:generate` before every typecheck
// step (`.github/workflows/test.yml`), so the client always exists first.
//
// Typing it revealed 42 errors across 25 files. None was a regression; all were
// pre-existing and invisible.
import { PrismaClient, Prisma } from '@prisma/client';
import { PrismaPg } from '@prisma/adapter-pg';

// ⚠️ THE ONE DECLARED CAST EXCEPTION IN F-TYPE, AND IT IS NOT A PRISMA ARGUMENT.
// `globalThis` has no index signature, so attaching a property to it needs
// either this double assertion or a `declare global` block. It launders NOTHING
// about a query: the property's own type is now
// `ReturnType<typeof buildPrisma>` — it was `any` before this change, which is
// the thing being fixed. Narrowing it is what makes the dev-mode singleton
// carry the real client type into every hot reload.
const globalForPrisma = globalThis as unknown as {
  prisma?: ReturnType<typeof buildPrisma>;
};

// Pool + statement timeout defaults. Any of these can be overridden
// via env. Rationale:
//   - PRISMA_POOL_MAX=10 — enough for a single Next instance (one
//     per request, with default Next concurrency) without exhausting
//     postgres' max_connections (100 by default on the VPS image).
//   - PRISMA_POOL_TIMEOUT_MS=20000 — how long to wait for a free
//     connection before throwing. Long enough to ride out a warm-up
//     burst, short enough that a saturated pool fails loudly.
//   - PRISMA_STATEMENT_TIMEOUT_MS=30000 — Postgres-side guard so a
//     rogue query can't hold a connection indefinitely.
const POOL_MAX = Number(process.env.PRISMA_POOL_MAX ?? 10);
const POOL_TIMEOUT_MS = Number(process.env.PRISMA_POOL_TIMEOUT_MS ?? 20_000);
const STATEMENT_TIMEOUT_MS = Number(
  process.env.PRISMA_STATEMENT_TIMEOUT_MS ?? 30_000
);

function buildConnectionString(): string {
  const raw =
    process.env.DATABASE_URL ??
    'postgresql://placeholder@localhost:5432/meddoc';
  // Append `options=-c statement_timeout=<ms>` so Postgres kills any
  // statement that outlives the limit. Preserves any existing query
  // string the caller may have set; we never overwrite.
  const hasQuery = raw.includes('?');
  if (raw.includes('statement_timeout')) return raw;
  const encoded = encodeURIComponent(`-c statement_timeout=${STATEMENT_TIMEOUT_MS}`);
  return `${raw}${hasQuery ? '&' : '?'}options=${encoded}`;
}

function buildPrisma() {
  const adapter = new PrismaPg({
    connectionString: buildConnectionString(),
    max: POOL_MAX,
    connectionTimeoutMillis: POOL_TIMEOUT_MS,
  });
  return new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === 'development' ? ['warn', 'error'] : ['error'],
  });
}

const prisma = globalForPrisma.prisma ?? buildPrisma();

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}

export default prisma;
export { prisma, Prisma };

/**
 * The client handed to a `$transaction(async (tx) => …)` callback.
 *
 * ⚠️ **NOT `typeof prisma`.** That is the FULL client, and it is not assignable
 * to the callback's parameter: a transaction client has `$connect`,
 * `$disconnect`, `$on`, `$use` and `$extends` removed. Annotating the callback
 * `typeof prisma` therefore fails the callback overload, TypeScript silently
 * falls back to the ARRAY overload — `$transaction(PrismaPromise[])` — and the
 * return type becomes `any[]`.
 *
 * That is why two of F-TYPE's errors read like data-shape bugs and are not:
 * `soap.ts` "'soapVersion' does not exist on type 'any[]'" and
 * `stale-visits.ts` "'any[]' is not assignable to type 'number'". The runtime
 * behaviour was always correct; only the annotation was wrong. Ten sites, ONE
 * decision.
 */
export type TransactionClient = Prisma.TransactionClient;

let dbHealthy: boolean | null = null;
let dbHealthCheckedAt = 0;
const HEALTH_CACHE_MS = 30_000;

export async function isDatabaseHealthy(): Promise<boolean> {
  const now = Date.now();
  if (dbHealthy !== null && now - dbHealthCheckedAt < HEALTH_CACHE_MS) {
    return dbHealthy;
  }
  try {
    await prisma.$queryRaw`SELECT 1`;
    dbHealthy = true;
  } catch {
    dbHealthy = false;
  }
  dbHealthCheckedAt = now;
  return dbHealthy;
}
