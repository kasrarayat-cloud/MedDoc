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

import bcrypt from 'bcryptjs';

import { prisma } from '@meddoc/db';
import { assertNonProdDatabase } from '@meddoc/db/guard';

export const T1_ALPHA_SLUG = 't1-alpha';
export const T1_BETA_SLUG = 't1-beta';

/** Stable member identities. The T4 gate signs as ALPHA_2 a visit authored by
 *  ALPHA_1, so it needs to name them — a random email cannot be looked up. */
export const T1_ALPHA_1_EMAIL = 't1-alpha-1@t1.invalid';
export const T1_ALPHA_2_EMAIL = 't1-alpha-2@t1.invalid';
export const T1_BETA_1_EMAIL = 't1-beta-1@t1.invalid';
/** ⚠️ T6 — the TECH seat. The negative half of the sign gate needs a member who
 *  is legitimately IN the practice and legitimately may NOT sign; without one,
 *  "TECH is refused by name" can only be tested by mutating a role at runtime,
 *  which proves the branch fires and not that the fixture can reach it. */
export const T1_ALPHA_3_EMAIL = 't1-alpha-3@t1.invalid';

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

async function upsertMember(
  email: string,
  name: string,
  practiceId: string,
  // ⚠️ T6 — THE ROLE IS AN ARGUMENT, NOT A DEFAULT, AND THAT IS THE POINT.
  // Before this the fixture seeded three members and never set `practiceRole`,
  // so all three took the schema default and T4's positive gate — "a non-owner
  // member signs, signedBy ≠ createdBy" — could not pass EVEN AFTER T6 landed:
  // §4.1a refuses a non-clinical role by name, so the gate would have failed for
  // a reason that has nothing to do with T4. Measured before building; see the
  // T6 reconnaissance in docs/foundation/RELAY.md.
  practiceRole: 'OWNER' | 'CLINICIAN' | 'TECH',
) {
  // ⚠️ `passwordHash` and `updatedAt` ARE REQUIRED and the first version of this
  // omitted both. I extracted required fields for the three clinical models and
  // never ran the same extraction over `User` — the third partial-inspection
  // miss of the day, after a compose build block and a flag census. The
  // corrective is the same each time: dump the WHOLE object and read it, rather
  // than the fields you expect to matter.
  //
  // ⚠️ THESE ACCOUNTS ARE LOGGABLE, AND THAT REVERSES AN EARLIER DECISION.
  // The first version used a deliberately-invalid hash so they could own rows
  // but never authenticate. T4's gate then required something that fixture
  // could not provide: "a NON-OWNER member signs a visit and signedBy ≠ userId
  // — a solo-practice run cannot pass this gate."
  //
  // Proving a signer is recorded correctly means a SECOND member actually
  // signing through the real route. Simulating it with a direct UPDATE would
  // prove the columns can differ and say nothing about whether the ROUTE stamps
  // the right person, which is the only thing worth asserting.
  //
  // Safe because: the password is supplied by env and never committed, the
  // emails are under `.invalid` (RFC 2606, cannot resolve), the practices are
  // fixtures, and `assertNonProdDatabase` refuses to run this anywhere but a
  // marked non-production database.
  const password = process.env.T1_MEMBER_PASSWORD;
  if (!password || password.length < 12) {
    throw new Error('[t1] T1_MEMBER_PASSWORD must be set (>=12 chars) — the T4 gate needs these members to sign');
  }
  const NEVER_A_VALID_HASH = await bcrypt.hash(password, 12);
  return prisma.user.upsert({
    where: { email },
    update: { practiceId, practiceRole },
    create: {
      email,
      name,
      practiceId,
      practiceRole,
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
  // ⚠️ FIND-THEN-CREATE, NOT UPSERT, AND THE REASON IS SCHEMA DRIFT.
  // `note_templates` carries a UNIQUE on (doctorId, encounterType) in the
  // DATABASE — added by a raw migration — but the Prisma model declares no
  // `@@unique`, so there is no compound where-input to upsert on. The
  // constraint is real and Prisma cannot see it.
  //
  // With deterministic member emails the second run hits the same doctor and a
  // bare `create` throws. The random-email bug had been hiding that behind a
  // fresh doctor every run — fixing one defect exposed the next.
  //
  // ⚠️ CARRIED, NOT FIXED HERE: the schema/database divergence itself. Adding
  // `@@unique([doctorId, encounterType])` to the model is a schema change with
  // its own migration and blast radius; doing it inside a fixture seed would be
  // smuggling. Recorded in the RELAY.
  const existingTemplate = await prisma.noteTemplate.findFirst({
    where: { doctorId: userId },
    select: { id: true },
  });
  if (!existingTemplate) await prisma.noteTemplate.create({
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
        // T4 — the author, explicitly. Required NOT NULL as of T4's migration.
        createdBy: userId,
        specialty: 'primary-care',
        inputMode: 'text_notes',
        status: signed ? 'SIGNED' : 'READY',
        signedAt: signed ? new Date() : null,
        // ⚠️ T4 — A SIGNATURE NEEDS A SIGNER, and the database enforces it:
        // `transcribe_visits_signed_requires_signer` rejected this seed until
        // this line existed. That is the constraint doing its job — the
        // createdBy sweep covered every CREATE, but signedBy applies only to
        // the subset that sets `signedAt`, and this fixture is in it.
        //
        // For a fixture the author IS the signer, which is exactly why this
        // fixture cannot satisfy T4's POSITIVE gate: proving signedBy can
        // DIFFER from createdBy needs a second member signing through the real
        // route. That is T4-b.
        signedBy: signed ? userId : null,
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

  // ⚠️ DETERMINISTIC EMAILS. These were `t1-alpha-1-${randomUUID()}@…`, which
  // made the upsert key different every run — so `upsert` never matched and each
  // invocation created NEW members. Alpha reached 4 members after two runs while
  // the seed cheerfully reported 2. An upsert whose key is random is an insert.
  // alpha-1 OWNS the practice and authors the visits.
  const a1 = await upsertMember(T1_ALPHA_1_EMAIL, 'T1 Alpha One', alpha.id, 'OWNER');
  // ⚠️ alpha-2 is a CLINICIAN, not an owner. This is what makes T4's positive
  // gate meaningful: a NON-OWNER signs a colleague's visit, so signedBy and
  // createdBy differ for a reason the production data has never produced.
  const a2 = await upsertMember(T1_ALPHA_2_EMAIL, 'T1 Alpha Two', alpha.id, 'CLINICIAN');
  // The TECH seat — in the practice, reads everything (§4.1b), signs nothing.
  await upsertMember(T1_ALPHA_3_EMAIL, 'T1 Alpha Three', alpha.id, 'TECH');
  const b1 = await upsertMember(T1_BETA_1_EMAIL, 'T1 Beta One', beta.id, 'OWNER');

  await seedClinicalData(a1.id, alpha.id, 'A1', 4);
  await seedClinicalData(a2.id, alpha.id, 'A2', 2);
  await seedClinicalData(b1.id, beta.id, 'B1', 3);

  // ⚠️ REPORT THE COUNTS. A seed that says "done" without saying how much it
  // wrote is how a gate ends up asserting against an empty set and passing.
  // ⚠️ MEASURED, NOT ASSERTED. `members=2` was a LITERAL in this string — the
  // seed printed a count it never took, and that count was wrong from the second
  // run onward while the comment above demanded the opposite. A number in a log
  // line is evidence only if something measured it.
  const [alphaVisits, betaVisits, alphaMembers, betaMembers] = await Promise.all([
    prisma.transcribeVisit.count({ where: { user: { practiceId: alpha.id } } }),
    prisma.transcribeVisit.count({ where: { user: { practiceId: beta.id } } }),
    prisma.user.count({ where: { practiceId: alpha.id } }),
    prisma.user.count({ where: { practiceId: beta.id } }),
  ]);

  console.log(
    `[t1] alpha=${T1_ALPHA_SLUG} members=${alphaMembers} visits=${alphaVisits} · ` +
      `beta=${T1_BETA_SLUG} members=${betaMembers} visits=${betaVisits}`,
  );
  if (alphaMembers < 3) {
    throw new Error(
      `[t1] alpha has ${alphaMembers} member(s) — T6's gates need an OWNER, a CLINICIAN and a TECH`,
    );
  }

  // ⚠️ THE ROLES ARE ASSERTED, NOT ASSUMED. `upsert` with `update: { … }` is
  // easy to get wrong in a way that silently leaves an existing row's role
  // stale — and a stale role turns the sign gates into tests of the wrong
  // member. MEASURED from the database, like the counts above.
  const roles: Array<{ email: string; practiceRole: string | null }> = await prisma.user.findMany({
    where: { practiceId: alpha.id },
    select: { email: true, practiceRole: true },
    orderBy: { email: 'asc' },
  });
  const shape = roles.map((r) => `${r.email}=${r.practiceRole}`).join(' ');
  console.log(`[t1] alpha roles: ${shape}`);
  const want: Record<string, string> = {
    [T1_ALPHA_1_EMAIL]: 'OWNER',
    [T1_ALPHA_2_EMAIL]: 'CLINICIAN',
    [T1_ALPHA_3_EMAIL]: 'TECH',
  };
  for (const [email, expected] of Object.entries(want)) {
    const got = roles.find((r) => r.email === email)?.practiceRole ?? null;
    if (got !== expected) {
      throw new Error(`[t1] ${email} has practiceRole=${got}, expected ${expected}`);
    }
  }
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
