// ============================================================================
// Chart ID auto-generation — correctness + per-practice + concurrency
// ----------------------------------------------------------------------------
// Verifies:
//   1. getNextChartId returns C-<start+1> when no patients in a practice
//   2. getNextChartId ignores non-matching formats (CHART-500, DC-123, etc.)
//   3. Practice A and Practice B have independent sequences
//   4. Manual chartId is kept verbatim
//   5. Duplicate manual chartId within a practice is rejected by the DB
//   6. Concurrent createPatient calls in the same practice never collide
//      (the retry loop catches P2002 and regenerates)
// ============================================================================

import { describe, it, expect, beforeEach, afterAll } from 'vitest';

import { createPatient, getNextChartId } from '@/lib/data/patients';

import { USERS, PRACTICE_A_ID, PRACTICE_B_ID } from '../fixtures/tenancy';

// ---------------------------------------------------------------------------
// Each test starts from a clean slate for the patients we create here — we
// only delete rows with IDs that start with `chartid_test_` so the tenancy
// fixture patients aren't touched.
// ---------------------------------------------------------------------------
async function getPrisma() {
  const { PrismaClient } = await import('@prisma/client');
  const { PrismaPg } = await import('@prisma/adapter-pg');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const adapter = new (PrismaPg as any)({ connectionString: process.env.DATABASE_URL });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  return new (PrismaClient as any)({ adapter });
}

async function cleanup() {
  const prisma = await getPrisma();
  // 1. Drop any test-owned rows we created (explicit id prefix).
  await prisma.patient.deleteMany({
    where: { id: { startsWith: 'chartid_test_' } },
  });
  // 2. Scrub any residual auto-created patients from prior test runs.
  //    The tenancy fixture patients use ids prefixed `test_patient_` so
  //    are preserved; anything else in the test practices is pollution.
  await prisma.patient.deleteMany({
    where: {
      practiceId: { in: [PRACTICE_A_ID, PRACTICE_B_ID] },
      NOT: { id: { startsWith: 'test_patient_' } },
    },
  });
  // 3. Null out any chartIds the tests may have set on the fixture rows.
  await prisma.patient.updateMany({
    where: { id: { startsWith: 'test_patient_' }, chartId: { not: null } },
    data: { chartId: null },
  });
  await prisma.$disconnect();
}

beforeEach(cleanup);
afterAll(cleanup);

describe('getNextChartId', () => {
  it('starts at C-1001 when the practice has no C-* chartIds', async () => {
    const id = await getNextChartId(PRACTICE_A_ID);
    expect(id).toMatch(/^C-\d+$/);
    // Parse the number and verify it increments strictly above any existing.
    // We don't assert exactly C-1001 because the DB may have other patients
    // seeded already — the guarantee is "strictly greater than max existing."
    const prisma = await getPrisma();
    const rows: Array<{ chartId: string | null }> = await prisma.patient.findMany({
      where: { practiceId: PRACTICE_A_ID, chartId: { startsWith: 'C-' } },
      select: { chartId: true },
    });
    await prisma.$disconnect();
    const existingMax = rows.reduce((m: number, r) => {
      const match = /^C-(\d+)$/.exec(r.chartId ?? '');
      return match ? Math.max(m, Number(match[1])) : m;
    }, 1000);
    expect(Number(id.slice(2))).toBe(existingMax + 1);
  });

  it('increments above the highest numeric C-* in the practice', async () => {
    const prisma = await getPrisma();
    await prisma.patient.create({
      data: {
        id: 'chartid_test_high',
        firstName: 'High',
        lastName: 'Number',
        practiceId: PRACTICE_A_ID,
        chartId: 'C-9950',
        createdById: USERS.doctorA.id,
        assignedDoctorId: USERS.doctorA.id,
      },
    });
    await prisma.$disconnect();

    const id = await getNextChartId(PRACTICE_A_ID);
    expect(id).toBe('C-9951');
  });

  it('ignores chartIds not matching ^C-\\d+$', async () => {
    const prisma = await getPrisma();
    await prisma.patient.createMany({
      data: [
        {
          id: 'chartid_test_legacy1',
          firstName: 'L1',
          lastName: 'Legacy',
          practiceId: PRACTICE_A_ID,
          chartId: 'CHART-500',
          createdById: USERS.doctorA.id,
        },
        {
          id: 'chartid_test_legacy2',
          firstName: 'L2',
          lastName: 'Legacy',
          practiceId: PRACTICE_A_ID,
          chartId: 'DC-99999',
          createdById: USERS.doctorA.id,
        },
      ],
    });
    await prisma.$disconnect();

    const id = await getNextChartId(PRACTICE_A_ID);
    expect(id).toMatch(/^C-\d+$/);
    // Must NOT jump to C-100000 just because DC-99999 exists.
    expect(Number(id.slice(2))).toBeLessThan(99999);
  });

  it('Practice A and Practice B have independent sequences', async () => {
    const prisma = await getPrisma();
    await prisma.patient.create({
      data: {
        id: 'chartid_test_a_only',
        firstName: 'A',
        lastName: 'Only',
        practiceId: PRACTICE_A_ID,
        chartId: 'C-9990',
        createdById: USERS.doctorA.id,
      },
    });
    await prisma.$disconnect();

    const idA = await getNextChartId(PRACTICE_A_ID);
    const idB = await getNextChartId(PRACTICE_B_ID);
    expect(idA).toBe('C-9991');
    // Practice B should NOT see C-9990 from Practice A.
    expect(Number(idB.slice(2))).toBeLessThan(9990);
  });
});

describe('createPatient chart-id behavior', () => {
  it('auto-generates when input.chartId is empty/null', async () => {
    const patient = await createPatient(
      { firstName: 'Auto', lastName: 'Gen', chartId: null },
      USERS.doctorA.id,
      PRACTICE_A_ID
    );
    expect(patient.chartId).toMatch(/^C-\d+$/);

    // Cleanup this row.
    const prisma = await getPrisma();
    await prisma.patient.delete({ where: { id: patient.id } });
    await prisma.$disconnect();
  });

  it('keeps a manually-supplied chartId verbatim', async () => {
    const patient = await createPatient(
      { firstName: 'Manual', lastName: 'Chart', chartId: 'CHART-MANUAL-42' },
      USERS.doctorA.id,
      PRACTICE_A_ID
    );
    expect(patient.chartId).toBe('CHART-MANUAL-42');

    const prisma = await getPrisma();
    await prisma.patient.delete({ where: { id: patient.id } });
    await prisma.$disconnect();
  });

  it('rejects a duplicate manual chartId within the same practice', async () => {
    const first = await createPatient(
      { firstName: 'First', lastName: 'Dup', chartId: 'C-DUP-TEST' },
      USERS.doctorA.id,
      PRACTICE_A_ID
    );
    try {
      await expect(
        createPatient(
          { firstName: 'Second', lastName: 'Dup', chartId: 'C-DUP-TEST' },
          USERS.doctorA.id,
          PRACTICE_A_ID
        )
      ).rejects.toThrow(/already exists/i);
    } finally {
      const prisma = await getPrisma();
      await prisma.patient.delete({ where: { id: first.id } });
      await prisma.$disconnect();
    }
  });

  it('allows the same chartId string across different practices', async () => {
    const a = await createPatient(
      { firstName: 'Same', lastName: 'InA', chartId: 'C-CROSSTENANT-1' },
      USERS.doctorA.id,
      PRACTICE_A_ID
    );
    const b = await createPatient(
      { firstName: 'Same', lastName: 'InB', chartId: 'C-CROSSTENANT-1' },
      USERS.doctorB.id,
      PRACTICE_B_ID
    );
    expect(a.chartId).toBe('C-CROSSTENANT-1');
    expect(b.chartId).toBe('C-CROSSTENANT-1');

    const prisma = await getPrisma();
    await prisma.patient.deleteMany({ where: { id: { in: [a.id, b.id] } } });
    await prisma.$disconnect();
  });

  it('concurrent auto-creates in the same practice get distinct chartIds (retry loop)', async () => {
    const N = 5;
    // Fire all creates simultaneously so they all read the same "max" at
    // roughly the same time, then race to insert. The retry loop must
    // catch the P2002 collision and regenerate.
    const results = await Promise.all(
      Array.from({ length: N }, (_, i) =>
        createPatient(
          { firstName: `Race${i}`, lastName: 'Concurrent', chartId: null },
          USERS.doctorA.id,
          PRACTICE_A_ID
        )
      )
    );

    const chartIds = results.map((p) => p.chartId);
    const unique = new Set(chartIds);
    expect(unique.size).toBe(N);
    for (const id of chartIds) {
      expect(id).toMatch(/^C-\d+$/);
    }

    const prisma = await getPrisma();
    await prisma.patient.deleteMany({ where: { id: { in: results.map((r) => r.id) } } });
    await prisma.$disconnect();
  });
});
