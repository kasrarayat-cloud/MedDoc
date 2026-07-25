// ============================================================================
// Delete every clinical row the smoke doctor produced. Run AFTER each smoke.
// ----------------------------------------------------------------------------
//   DATABASE_URL=... npx tsx scripts/prod-smoke/clean.ts
//
// WHAT IT DELETES: visits, patients and note templates owned by the smoke
// fixture — i.e. the synthetic clinical data a smoke run creates.
//
// WHAT IT DELIBERATELY KEEPS:
//   * the user + practice rows      — so the next smoke can just log in
//   * audit_logs                    — append-only by policy. The smoke run's
//                                     own audit trail is evidence; deleting it
//                                     would be exactly the tampering the audit
//                                     layer exists to make impossible.
//
// Every query is keyed on the smoke practice/user id resolved from the
// constants in smoke-account.ts. If the fixture does not exist, this exits 0
// without touching anything rather than guessing.
// ============================================================================

import { prisma } from '@meddoc/db';

import { SMOKE_EMAIL, SMOKE_PRACTICE_SLUG, assertIsSmokeFixture } from './smoke-account';

async function main() {
  const user = await prisma.user.findUnique({
    where: { email: SMOKE_EMAIL },
    include: { practice: { select: { slug: true, id: true } } },
  });

  if (!user) {
    console.log('[prod-smoke] no smoke fixture on this database — nothing to clean.');
    return;
  }

  // Belt and braces: the row must be the fixture on BOTH axes before we delete.
  assertIsSmokeFixture({ email: user.email, practice: { slug: user.practice.slug } });
  if (user.practice.slug !== SMOKE_PRACTICE_SLUG) {
    throw new Error('prod-smoke: resolved user is not in the smoke practice — aborting.');
  }

  // Visits first: they reference patients, and visit children cascade from here.
  const visits = await prisma.transcribeVisit.deleteMany({ where: { userId: user.id } });
  const patients = await prisma.transcribeMdPatient.deleteMany({
    where: { practiceId: user.practice.id },
  });
  const templates = await prisma.noteTemplate.deleteMany({ where: { doctorId: user.id } });

  console.log(
    `[prod-smoke] cleaned visits=${visits.count} patients=${patients.count} templates=${templates.count}`
  );
  console.log('[prod-smoke] user, practice and audit_logs intentionally preserved.');
}

main()
  .catch((err) => {
    console.error('[prod-smoke] clean FAILED:', err);
    process.exitCode = 1;
  })
  .finally(() => prisma.$disconnect());
