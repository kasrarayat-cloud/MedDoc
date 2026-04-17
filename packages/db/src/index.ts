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
const { PrismaClient } = require('@prisma/client') as { PrismaClient: any };
// eslint-disable-next-line @typescript-eslint/no-require-imports, @typescript-eslint/no-explicit-any
const { PrismaPg } = require('@prisma/adapter-pg') as { PrismaPg: any };

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const globalForPrisma = globalThis as unknown as { prisma?: any };

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
