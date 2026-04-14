import 'dotenv/config';

async function main() {
  const { PrismaClient } = require('@prisma/client');
  const { PrismaPg } = require('@prisma/adapter-pg');
  const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
  const prisma = new PrismaClient({ adapter });

  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 0, 0, 0);
  const endOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate(), 23, 59, 59);

  // Also pull a wider window (±24h) so we catch anything on the edges from TZ weirdness.
  const windowStart = new Date(startOfToday); windowStart.setDate(windowStart.getDate() - 1);
  const windowEnd = new Date(endOfToday); windowEnd.setDate(windowEnd.getDate() + 1);

  const apts = await prisma.appointment.findMany({
    where: { scheduledAt: { gte: windowStart, lte: windowEnd } },
    orderBy: { scheduledAt: 'asc' },
    include: { patient: { select: { firstName: true, lastName: true, practiceId: true } } },
  });

  console.log(`\nServer now (UTC):     ${now.toISOString()}`);
  console.log(`Server now (local):   ${now.toString()}`);
  console.log(`Local "today" window: ${startOfToday.toString()} → ${endOfToday.toString()}`);
  console.log(`Scan window (±24h):   ${windowStart.toISOString()} → ${windowEnd.toISOString()}\n`);
  console.log(`Found ${apts.length} appointment(s) in ±24h:`);

  for (const a of apts) {
    const d = new Date(a.scheduledAt);
    console.log(
      `  ${a.id}  scheduledAt=${d.toISOString()}  localHour=${d.getHours()}:${String(d.getMinutes()).padStart(2,'0')}  patient=${a.patient?.firstName} ${a.patient?.lastName} (practice=${a.patient?.practiceId})  status=${a.status}`
    );
  }

  await prisma.$disconnect();
}

main().catch((e) => { console.error(e); process.exit(1); });
