// Dev helper — enqueue a BullMQ retry job for a single visit so the
// worker re-runs any layers that aren't marked complete (T-M13 layer-
// skip). For T-M24.smart testing: clear filledTemplate to NULL first,
// then call this to re-run only L7f.
//
// Usage: tsx requeue-visit.ts <visitId>

import prisma from '@meddoc/db';

import { enqueueProcessVisit } from '../src/lib/queue';

async function main() {
  const visitId = process.argv[2];
  if (!visitId) throw new Error('usage: requeue-visit.ts <visitId>');

  const v = await prisma.transcribeVisit.findUnique({
    where: { id: visitId },
    select: { id: true, userId: true, status: true, templateId: true },
  });
  if (!v) throw new Error(`visit ${visitId} not found`);
  console.log(`Visit ${v.id}: status=${v.status} templateId=${v.templateId ?? '(none)'}`);

  await enqueueProcessVisit(v.id, v.userId, { retry: true });
  console.log('→ enqueued retry job');

  await prisma.$disconnect();
}

main().catch((e) => {
  console.error('requeue failed:', e);
  process.exit(1);
});
