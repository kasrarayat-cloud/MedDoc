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
import { assertNonProdDatabase } from '@meddoc/db/guard';

import {
  PRACTICE_A_ID,
  PRACTICE_B_ID,
  TEST_PASSWORD,
  USERS,
  PATIENTS,
  NOTES,
  APPOINTMENTS,
  ALLERGIES,
  MEDICATIONS,
  type TestUser,
} from '../tests/fixtures/tenancy';

async function main() {
  // FAIL-CLOSED: never seed prod (see packages/db/src/db-guard.ts).
  assertNonProdDatabase();

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
        practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
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
        practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
        isActive: true,
      },
    });

  for (const u of Object.values(USERS)) {
    await upsertUser(u);
  }

  // Phase 8 fix: when AUTH_USE_MOCK=true (CI sets this so the middleware
  // lets pre-authenticated requests through), `getMockSession()` in
  // src/lib/auth.ts returns a session with id='mock_user_doctor_01'.
  // logAudit() inside the credentials authorize() flow then resolves
  // userId from that mock session and tries to INSERT into audit_logs —
  // hitting `audit_logs_userId_fkey` because the mock user didn't exist
  // in the DB. The audit-write failed silently (caught), but the noise
  // polluted the WebServer log and (per Playwright runs) tracked back
  // to the same login flow that 8 E2E tests blocked on.
  //
  // Seeding the mock user against the same `clinic_main` practice
  // satisfies the FK without changing any auth semantics. The mock is
  // still only used when AUTH_USE_MOCK=true AND no real session cookie
  // exists; once the test logs in for real, getSession() returns the
  // real session.
  const MOCK_DEV_USER_ID = 'mock_user_doctor_01';
  const MOCK_DEV_USER_EMAIL = 'doctor@meddoc.local';
  await prisma.user.upsert({
    where: { id: MOCK_DEV_USER_ID },
    update: {
      email: MOCK_DEV_USER_EMAIL,
      name: 'Dr. Bakhtiar Moussazadeh',
      passwordHash,
      role: 'DOCTOR',
      practiceId: PRACTICE_A_ID,
      practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
      isActive: true,
      lockedUntil: null,
      failedLoginCount: 0,
    },
    create: {
      id: MOCK_DEV_USER_ID,
      email: MOCK_DEV_USER_EMAIL,
      name: 'Dr. Bakhtiar Moussazadeh',
      passwordHash,
      role: 'DOCTOR',
      practiceId: PRACTICE_A_ID,
      practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
      isActive: true,
    },
  });

  // --- Patients ---
  for (const p of Object.values(PATIENTS)) {
    await prisma.patient.upsert({
      where: { id: p.id },
      update: {
        firstName: p.firstName,
        lastName: p.lastName,
        practiceId: p.practiceId,
        practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
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
        practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
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

  // --- Allergies ---
  for (const a of Object.values(ALLERGIES)) {
    await prisma.allergy.upsert({
      where: { id: a.id },
      update: {
        allergen: a.allergen,
        severity: a.severity,
        deletedAt: null,
      },
      create: {
        id: a.id,
        patientId: a.patientId,
        practiceId: a.practiceId,
        practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
        allergen: a.allergen,
        severity: a.severity,
      },
    });
  }

  // --- Medications ---
  for (const m of Object.values(MEDICATIONS)) {
    await prisma.medication.upsert({
      where: { id: m.id },
      update: {
        name: m.name,
        dosage: m.dosage,
        frequency: m.frequency,
        isActive: true,
        deletedAt: null,
      },
      create: {
        id: m.id,
        patientId: m.patientId,
        practiceId: m.practiceId,
        practiceRole: 'OWNER', // T6: the CHECK requires a role for an active member
        name: m.name,
        dosage: m.dosage,
        frequency: m.frequency,
        isActive: true,
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
