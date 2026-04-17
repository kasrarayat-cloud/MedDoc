import 'dotenv/config';

async function main() {
  const { PrismaClient } = require('@prisma/client');
  const { PrismaPg } = require('@prisma/adapter-pg');
  const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
  const prisma = new PrismaClient({ adapter });

  const dupes: Array<{ practiceId: string; chartId: string; count: bigint }> = await prisma.$queryRawUnsafe(
    `SELECT "practiceId", "chartId", COUNT(*)::bigint AS count FROM patients WHERE "chartId" IS NOT NULL GROUP BY "practiceId", "chartId" HAVING COUNT(*) > 1`
  );
  console.log(`Duplicate (practiceId, chartId) rows: ${dupes.length}`);
  for (const d of dupes) {
    console.log(`  practice=${d.practiceId} chartId=${d.chartId} count=${d.count}`);
  }
  await prisma.$disconnect();
}

main().catch((e) => { console.error(e); process.exit(1); });
