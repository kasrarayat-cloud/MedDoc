// ============================================================================
// RETROACTIVE AUTO-CERTIFICATION — ruling: auto-certification is the default.
// ----------------------------------------------------------------------------
// Templates uploaded BEFORE auto-certification shipped sit at
// NEEDS_CONFIRMATION forever: compile-on-upload is what enqueues the job, and
// theirs already ran. This enqueues that job for the twins that were merely
// early.
//
// ⚠️ IT ENQUEUES; IT DOES NOT CERTIFY. The worker job is the ONE certification
// path — same auto-confirm plan, same round-trip proof, same lifecycle
// transition, same audit rows. A backfill that certified directly would be a
// SECOND path, and the two would drift until only one of them was the one that
// had actually been proven.
//
// ⚠️ DRY RUN BY DEFAULT. It prints what it would enqueue and exits 0. Acting
// requires --commit, because every enqueue costs a live model generation and
// this is production.
//
//   npx tsx scripts/backfill-auto-certify.ts              # report only
//   npx tsx scripts/backfill-auto-certify.ts --commit     # enqueue
//
// Exit: 0 report/success · 1 nothing eligible is NOT an error, still 0 · 2 refused
// ============================================================================
import prisma from '@meddoc/db';

const COMMIT = process.argv.includes('--commit');

async function main(): Promise<number> {
  // ⚠️ ELIGIBILITY IS AN ENUMERATED SET, NOT A NEGATION.
  // The enum has FIVE members and only two of them mean "compiled, waiting for
  // someone to confirm it". Excluding only CERTIFIED also sweeps in QUARANTINED
  // (pulled deliberately) and UNSUPPORTED (compiled and found wanting) —
  // auto-certifying either would silently overturn a refusal made on purpose.
  const ELIGIBLE = ['RECOGNIZED', 'NEEDS_CONFIRMATION'] as const;

  // CENSUS FIRST, so the excluded buckets are VISIBLE rather than silently
  // dropped: a backfill reporting "3 eligible" without saying what it passed
  // over cannot be checked by anyone reading its output.
  const census = await prisma.templateTwinCompiledVersion.groupBy({
    by: ['certificationStatus'],
    _count: { _all: true },
  });
  const total = census.reduce((n, c) => n + c._count._all, 0);
  console.log('compiled twins by certification status:');
  for (const c of census) {
    const mark = (ELIGIBLE as readonly string[]).includes(c.certificationStatus)
      ? 'eligible'
      : 'EXCLUDED';
    console.log(`  ${c.certificationStatus.padEnd(20)} ${String(c._count._all).padStart(4)}   ${mark}`);
  }
  console.log(`  ${'TOTAL'.padEnd(20)} ${String(total).padStart(4)}`);

  const rows = await prisma.templateTwinCompiledVersion.findMany({
    where: {
      certificationStatus: { in: [...ELIGIBLE] },
      blockingUnsupportedCount: 0,
    },
    select: {
      noteTemplateId: true,
      certificationStatus: true,
      blockingUnsupportedCount: true,
      practiceId: true,
      noteTemplate: { select: { name: true, doctorId: true } },
    },
  });

  console.log(`eligible twins: ${rows.length}${COMMIT ? '' : '   (DRY RUN — pass --commit to enqueue)'}`);
  if (rows.length === 0) {
    console.log('nothing to backfill — every compiled twin is certified or has blocking elements');
    return 0;
  }

  for (const r of rows) {
    console.log(
      `  ${r.noteTemplateId}  ${r.certificationStatus.padEnd(20)}  ${r.noteTemplate?.name ?? '(unnamed)'}`,
    );
  }

  if (!COMMIT) return 0;

  // ⚠️ THE DOCTOR'S OWN ID IS THE ACTOR, NOT A SYSTEM USER. Certification writes
  // to the doctor's template and the audit row must name a real accountable
  // owner. A system actor here would put an unattributable certification on a
  // clinical artifact.
  const { enqueueAutoCertifyTwin } = await import('../apps/transcribe-md/src/lib/queue');
  let enqueued = 0;
  for (const r of rows) {
    const doctorId = r.noteTemplate?.doctorId;
    if (!doctorId || !r.practiceId) {
      console.warn(`  SKIP ${r.noteTemplateId} — no doctorId/practiceId to attribute the certification to`);
      continue;
    }
    const user = await prisma.user.findUnique({ where: { id: doctorId }, select: { email: true } });
    if (!user?.email) {
      console.warn(`  SKIP ${r.noteTemplateId} — doctor has no email; the actor would be incomplete`);
      continue;
    }
    await enqueueAutoCertifyTwin({
      noteTemplateId: r.noteTemplateId,
      userId: doctorId,
      userEmail: user.email,
      practiceId: r.practiceId,
    });
    enqueued += 1;
    console.log(`  ENQUEUED ${r.noteTemplateId}`);
  }
  console.log(`enqueued ${enqueued} of ${rows.length}`);
  return 0;
}

main()
  .then((code) => process.exit(code))
  .catch((err) => {
    console.error('backfill FAILED:', err instanceof Error ? err.message : err);
    process.exit(2);
  });
