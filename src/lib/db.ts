// ============================================================================
// Prisma Client Singleton
// ----------------------------------------------------------------------------
// Avoids creating multiple PrismaClient instances during Next.js dev hot-reload.
// In production, a single instance is created on the first import.
//
// If DATABASE_URL is not set or DB is unreachable, queries will throw —
// the data layer (`src/lib/data/*`) handles the fallback to in-memory mocks.
// ============================================================================

// eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-explicit-any
const { PrismaClient } = require('@prisma/client') as { PrismaClient: any };
// eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-explicit-any
const { PrismaPg } = require('@prisma/adapter-pg') as { PrismaPg: any };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const globalForPrisma = globalThis as unknown as { prisma?: any };

// Prisma v7 requires either an adapter or accelerateUrl. We use the
// pg driver adapter, which lazy-connects on the first query — so the
// constructor never throws even if Postgres isn't running. Health checks
// (isDatabaseHealthy) decide whether to actually use it or fall back to
// the in-memory store in `src/lib/data/*`.
function buildPrisma() {
  const adapter = new PrismaPg({
    connectionString:
      process.env.DATABASE_URL ?? 'postgresql://placeholder@localhost:5432/meddoc',
  });
  return new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === 'development' ? ['warn', 'error'] : ['error'],
  });
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const prisma: any = globalForPrisma.prisma ?? buildPrisma();

if (process.env.NODE_ENV !== 'production') {
  globalForPrisma.prisma = prisma;
}

export default prisma;

/**
 * Quick health check — does the DB respond?
 * Used by the data layer to decide whether to use Prisma or fall back to mocks.
 */
let dbHealthy: boolean | null = null;
let dbHealthCheckedAt = 0;
const HEALTH_CACHE_MS = 30_000; // re-check every 30s

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
