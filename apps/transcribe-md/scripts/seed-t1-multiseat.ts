// ============================================================================
// T1 — the multi-seat fixture.
// ----------------------------------------------------------------------------
// Two practices with REAL clinical data, so a practice-scoping predicate has
// something to filter and something to exclude.
//
//   t1-alpha   2 members, patients + visits (some SIGNED) + templates
//   t1-beta    1 member,  its own patients + visits + templates
//
// ⚠️ WHY THE DATA IS THE POINT, NOT THE MEMBERSHIP. Production already has
// three multi-member practices — main-clinic (11), qa-audit (5), test-clinic-b
// (2) — and every one of them has ZERO visits, ZERO templates. Measured
// 2026-08-05. A filter test over an empty practice PASSES FOR FREE: remove the
// predicate and nothing changes, because there was nothing to leak. T1's gate
// demands a mutation-proven red, and an empty fixture cannot produce one.
//
// That is why T1 blocks every item below it in the RELAY, and it is a
// structural instance of the vacuity trap this program keeps meeting: an
// assertion about a set whose size was never established.
//
// ⚠️ BOTH PRACTICES GET DATA, NOT JUST ALPHA. A one-sided fixture proves a query
// returns rows; it cannot prove the query EXCLUDES anything, because there is
// nothing on the other side to exclude. The beta rows exist to be absent from
// alpha's results.
//
// FAIL-CLOSED: `assertNonProdDatabase` refuses to run against an unmarked
// database (packages/db/src/db-guard.ts, #278).
// ============================================================================

import { randomUUID } from 'node:crypto';

import { prisma } from '@meddoc/db';
import { assertNonProdDatabase } from '@meddoc/db/guard';

export const T1_ALPHA_SLUG = 't1-alpha';
export const T1_BETA_SLUG = 't1-beta';

/** Marks every row this seed writes, so cleanup can key on it and a human
 *  reading the table can tell fixture from clinical data at a glance. */
const TAG = 'T1FIXTURE';

async function upsertPractice(slug: string, name: string) {
  return prisma.practice.upsert({
    where: { slug },
    update: {},
    create: { slug, name },
  });
}

async function upsertMember(email: string, name: string, practiceId: string) {
  // ⚠️ `passwordHash` and `updatedAt` ARE REQUIRED and the first version of this
  // omitted both. I extracted required fields for the three clinical models and
  // never ran the same extraction over `User` — the third partial-inspection
  // miss of the day, after a compose build block and a flag census. The
  // corrective is the same each time: dump the WHOLE object and read it, rather
  // than the fields you expect to matter.
  //
  // The hash is a fixed, obviously-fake constant: these accounts must never be
  // loggable-into, and a real bcrypt hash of a known string would make them so.
  // They exist to own rows, not to authenticate.
  const NEVER_A_VALID_HASH = 'T1FIXTURE-not-a-bcrypt-hash-never-authenticates';
  return prisma.user.upsert({
    where: { email },
    update: { practiceId },
    create: {
      email,
      name,
      practiceId,
      passwordHash: NEVER_A_VALID_HASH,
      emailVerified: new Date(),
      products: ['TRANSCRIBE_MD'] as const,
      updatedAt: new Date(),
    },
  });
}

async function seedClinicalData(
  userId: string,
  practiceId: string,
  label: string,
  visitCount: number,
) {
  const patient = await prisma.transcribeMdPatient.create({
    data: {
      practiceId,
      name: `${TAG} ${label} Patient`,
      dateOfBirth: new Date('1980-01-01'),
      updatedAt: new Date(),
    },
  });

  // A template — "edit patterns" in T1's wording: a doctor-owned note format.
  await prisma.noteTemplate.create({
    data: {
      name: `${TAG} ${label} Template`,
      doctorId: userId,
      sections: [
        { key: 'subjective', label: 'Subjective' },
        { key: 'objective', label: 'Objective' },
      ],
      updatedAt: new Date(),
    },
  });

  for (let i = 0; i < visitCount; i++) {
    // Half SIGNED, so a scoping bug that leaks only finalised notes is visible.
    const signed = i % 2 === 0;
    await prisma.transcribeVisit.create({
      data: {
        userId,
        patientId: patient.id,
        // ⚠️ T3 MADE THIS REQUIRED, AND OMITTING IT FAILS CONFUSINGLY.
        // Prisma reports `Argument \`user\` is missing` — not "practiceId is
        // missing". Passing scalar FKs selects the UNCHECKED create variant;
        // drop one required scalar and Prisma falls back to the CHECKED
        // variant, which wants `user: { connect: … }`. The error names the
        // symptom, not the cause.
        //
        // It must equal the patient's practice — the composite FK
        // (patientId, practiceId) → (id, practiceId) refuses anything else, by
        // design. Passing it explicitly rather than deriving it here keeps the
        // fixture honest: if the derivation ever disagreed, this seed would
        // fail loudly instead of quietly writing a row the constraint allows.
        practiceId,
        specialty: 'primary-care',
        inputMode: 'text_notes',
        status: signed ? 'SIGNED' : 'READY',
        signedAt: signed ? new Date() : null,
        soapFinal: `${TAG} ${label} note ${i} — synthetic, no clinical meaning.`,
        updatedAt: new Date(),
      },
    });
  }
  return patient.id;
}

async function main() {
  // FAIL-CLOSED before anything is written.
  await assertNonProdDatabase();

  const alpha = await upsertPractice(T1_ALPHA_SLUG, 'T1 Alpha Clinic (fixture)');
  const beta = await upsertPractice(T1_BETA_SLUG, 'T1 Beta Clinic (fixture)');

  const a1 = await upsertMember(`t1-alpha-1-${randomUUID().slice(0, 8)}@t1.invalid`, 'T1 Alpha One', alpha.id);
  const a2 = await upsertMember(`t1-alpha-2-${randomUUID().slice(0, 8)}@t1.invalid`, 'T1 Alpha Two', alpha.id);
  const b1 = await upsertMember(`t1-beta-1-${randomUUID().slice(0, 8)}@t1.invalid`, 'T1 Beta One', beta.id);

  await seedClinicalData(a1.id, alpha.id, 'A1', 4);
  await seedClinicalData(a2.id, alpha.id, 'A2', 2);
  await seedClinicalData(b1.id, beta.id, 'B1', 3);

  // ⚠️ REPORT THE COUNTS. A seed that says "done" without saying how much it
  // wrote is how a gate ends up asserting against an empty set and passing.
  const [alphaVisits, betaVisits] = await Promise.all([
    prisma.transcribeVisit.count({ where: { user: { practiceId: alpha.id } } }),
    prisma.transcribeVisit.count({ where: { user: { practiceId: beta.id } } }),
  ]);

  console.log(
    `[t1] alpha=${T1_ALPHA_SLUG} members=2 visits=${alphaVisits} · ` +
      `beta=${T1_BETA_SLUG} members=1 visits=${betaVisits}`,
  );
  if (alphaVisits === 0 || betaVisits === 0) {
    throw new Error('[t1] a side has zero visits — the isolation gate would be vacuous');
  }
}

main()
  .then(() => prisma.$disconnect())
  .catch(async (err) => {
    console.error('[t1] seed failed:', err);
    await prisma.$disconnect();
    process.exit(1);
  });
