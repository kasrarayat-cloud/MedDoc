// ============================================================================
// Seed Script — Multi-tenancy test fixtures
// ----------------------------------------------------------------------------
// Idempotent upsert of the full user/patient/note/appointment matrix used
// by both the Vitest adversarial suite and the Playwright E2E suite.
// Source of truth for IDs + credentials is `tests/fixtures/tenancy.ts`.
//
// Safe to run repeatedly. On re-run: resets password, role, isActive,
// lockedUntil, failedLoginCount so the test environment is always in a
// known-good shape. Practice B is created if absent.
//
// Run with: npm run seed:e2e
// ============================================================================

import 'dotenv/config';
import bcrypt from 'bcryptjs';

import {
  PRACTICE_A_ID,
  PRACTICE_B_ID,
  TEST_PASSWORD,
  USERS,
  PATIENTS,
  NOTES,
  APPOINTMENTS,
  type TestUser,
} from '../tests/fixtures/tenancy';

async function main() {
  const { PrismaClient } = require('@prisma/client');
  const { PrismaPg } = require('@prisma/adapter-pg');

  const adapter = new PrismaPg({ connectionString: process.env.DATABASE_URL });
  const prisma = new PrismaClient({ adapter });

  const passwordHash = await bcrypt.hash(TEST_PASSWORD, 12);

  // --- Practices ---
  await prisma.practice.upsert({
    where: { id: PRACTICE_A_ID },
    update: {},
    create: { id: PRACTICE_A_ID, name: 'Main Clinic', slug: 'main-clinic', isActive: true },
  });
  await prisma.practice.upsert({
    where: { id: PRACTICE_B_ID },
    update: {},
    create: { id: PRACTICE_B_ID, name: 'Test Clinic B', slug: 'test-clinic-b', isActive: true },
  });

  // --- Users ---
  const upsertUser = (u: TestUser) =>
    prisma.user.upsert({
      where: { id: u.id },
      update: {
        email: u.email,
        name: u.name,
        passwordHash,
        role: u.role,
        practiceId: u.practiceId,
        isActive: true,
        lockedUntil: null,
        failedLoginCount: 0,
      },
      create: {
        id: u.id,
        email: u.email,
        name: u.name,
        passwordHash,
        role: u.role,
        practiceId: u.practiceId,
        isActive: true,
      },
    });

  for (const u of Object.values(USERS)) {
    await upsertUser(u);
  }

  // --- Patients ---
  for (const p of Object.values(PATIENTS)) {
    await prisma.patient.upsert({
      where: { id: p.id },
      update: {
        firstName: p.firstName,
        lastName: p.lastName,
        practiceId: p.practiceId,
        createdById: p.createdById,
        assignedDoctorId: p.assignedDoctorId,
        status: 'ACTIVE',
        deletedAt: null,
      },
      create: {
        id: p.id,
        firstName: p.firstName,
        lastName: p.lastName,
        birthYear: 1980,
        mrn: `MRN-${p.id}`,
        practiceId: p.practiceId,
        createdById: p.createdById,
        assignedDoctorId: p.assignedDoctorId,
        status: 'ACTIVE',
      },
    });
  }

  // --- Clinical notes (stored as Documents with content) ---
  for (const n of Object.values(NOTES)) {
    await prisma.document.upsert({
      where: { id: n.id },
      update: { content: 'Test note content', createdById: n.authorId, patientId: n.patientId, deletedAt: null },
      create: {
        id: n.id,
        patientId: n.patientId,
        title: 'Test Clinical Note',
        content: 'Test note content',
        status: 'DRAFT',
        createdById: n.authorId,
      },
    });
  }

  // --- Appointments ---
  for (const a of Object.values(APPOINTMENTS)) {
    await prisma.appointment.upsert({
      where: { id: a.id },
      update: { patientId: a.patientId, userId: a.userId, status: 'SCHEDULED' },
      create: {
        id: a.id,
        patientId: a.patientId,
        userId: a.userId,
        scheduledAt: new Date('2026-06-01T10:00:00Z'),
        type: 'CONSULTATION',
        status: 'SCHEDULED',
      },
    });
  }

  console.log('\n  Tenancy fixtures seeded.');
  console.log(`  Password for all test users: ${TEST_PASSWORD}`);
  console.log(`  Practice A: ${PRACTICE_A_ID}`);
  console.log(`  Practice B: ${PRACTICE_B_ID}`);
  console.log(`  Users:    ${Object.values(USERS).map((u) => u.email).join(', ')}`);
  console.log(`  Patients: ${Object.values(PATIENTS).map((p) => p.id).join(', ')}\n`);

  await prisma.$disconnect();
}

main().catch((err) => {
  console.error('Seed failed:', err);
  process.exit(1);
});
