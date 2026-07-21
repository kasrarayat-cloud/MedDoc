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

// eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-explicit-any
const { PrismaClient } = require("@prisma/client") as { PrismaClient: any };
// eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-explicit-any
const { PrismaPg } = require("@prisma/adapter-pg") as { PrismaPg: any };

import {
  buildDatabaseConnectionString,
  parseStatementTimeoutMs,
} from "./database-connection-string";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const globalForPrisma = globalThis as unknown as { prisma?: any };

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
const STATEMENT_TIMEOUT_MS = parseStatementTimeoutMs(
  process.env.PRISMA_STATEMENT_TIMEOUT_MS,
);

function buildConnectionString(): string {
  const raw =
    process.env.DATABASE_URL ??
    "postgresql://placeholder@localhost:5432/meddoc";
  // The reviewed search_path and timeout must be sent through one effective
  // startup-options value. The builder rejects duplicate or unreviewed
  // options rather than relying on the driver's last-value-wins parser.
  return buildDatabaseConnectionString(raw, STATEMENT_TIMEOUT_MS);
}

function buildPrisma() {
  const adapter = new PrismaPg({
    connectionString: buildConnectionString(),
    max: POOL_MAX,
    connectionTimeoutMillis: POOL_TIMEOUT_MS,
  });
  return new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === "development" ? ["warn", "error"] : ["error"],
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const prisma: any = globalForPrisma.prisma ?? buildPrisma();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}

export default prisma;
export { prisma };

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
