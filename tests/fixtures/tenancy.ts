// ============================================================================
// Multi-tenancy test fixtures
// ----------------------------------------------------------------------------
// Stable IDs + credentials shared by the seed script, the Vitest adversarial
// suite, and the Playwright E2E suite. Tests and seed MUST agree on these
// constants — everything else flows from here.
//
// Practice layout:
//   A = clinic_main     (the default practice seeded by migration)
//   B = clinic_test_b   (a second practice created by the seed script)
//
// User matrix:
//   super            SUPER_ADMIN  — bound to A but bypasses tenant scope
//   admin-a, -b      ADMIN        — see everything in their own practice
//   doctor-a, -b     DOCTOR       — see only patients they created/are assigned
//   staff-a          STAFF        — same rule as DOCTOR
//
// Patient/appointment/note rows are created in both practices so we can
// verify isolation from both directions.
// ============================================================================

import type { UserRole } from '@/lib/auth';

export const TEST_PASSWORD = 'test-password';

export const PRACTICE_A_ID = 'clinic_main';
export const PRACTICE_B_ID = 'clinic_test_b';

export interface TestUser {
  id: string;
  email: string;
  name: string;
  role: UserRole;
  practiceId: string;
}

export const USERS = {
  super: {
    id: 'test_user_super',
    email: 'super@test.dev',
    name: 'Super Admin',
    role: 'SUPER_ADMIN',
    practiceId: PRACTICE_A_ID,
  },
  adminA: {
    id: 'test_user_admin_a',
    email: 'admin-a@test.dev',
    name: 'Admin A',
    role: 'ADMIN',
    practiceId: PRACTICE_A_ID,
  },
  doctorA: {
    id: 'test_user_doctor_a',
    email: 'doctor-a@test.dev',
    name: 'Doctor A',
    role: 'DOCTOR',
    practiceId: PRACTICE_A_ID,
  },
  staffA: {
    id: 'test_user_staff_a',
    email: 'staff-a@test.dev',
    name: 'Staff A',
    role: 'STAFF',
    practiceId: PRACTICE_A_ID,
  },
  adminB: {
    id: 'test_user_admin_b',
    email: 'admin-b@test.dev',
    name: 'Admin B',
    role: 'ADMIN',
    practiceId: PRACTICE_B_ID,
  },
  doctorB: {
    id: 'test_user_doctor_b',
    email: 'doctor-b@test.dev',
    name: 'Doctor B',
    role: 'DOCTOR',
    practiceId: PRACTICE_B_ID,
  },
} satisfies Record<string, TestUser>;

export const PATIENTS = {
  a1: {
    id: 'test_patient_a1',
    firstName: 'Alice',
    lastName: 'TenantAlpha',
    practiceId: PRACTICE_A_ID,
    createdById: USERS.doctorA.id,
    assignedDoctorId: USERS.doctorA.id,
  },
  a2: {
    id: 'test_patient_a2',
    firstName: 'Arthur',
    lastName: 'OtherAlpha',
    practiceId: PRACTICE_A_ID,
    createdById: USERS.doctorA.id,
    assignedDoctorId: USERS.doctorA.id,
  },
  b1: {
    id: 'test_patient_b1',
    firstName: 'Bianca',
    lastName: 'TenantBeta',
    practiceId: PRACTICE_B_ID,
    createdById: USERS.doctorB.id,
    assignedDoctorId: USERS.doctorB.id,
  },
  b2: {
    id: 'test_patient_b2',
    firstName: 'Boris',
    lastName: 'OtherBeta',
    practiceId: PRACTICE_B_ID,
    createdById: USERS.doctorB.id,
    assignedDoctorId: USERS.doctorB.id,
  },
} as const;

export const NOTES = {
  a1: { id: 'test_note_a1', patientId: PATIENTS.a1.id, authorId: USERS.doctorA.id },
  b1: { id: 'test_note_b1', patientId: PATIENTS.b1.id, authorId: USERS.doctorB.id },
} as const;

export const APPOINTMENTS = {
  a1: { id: 'test_apt_a1', patientId: PATIENTS.a1.id, userId: USERS.doctorA.id },
  b1: { id: 'test_apt_b1', patientId: PATIENTS.b1.id, userId: USERS.doctorB.id },
} as const;

// Allergies + medications — one row per practice so adversarial cross-tenant
// reads can be checked from both directions.
export const ALLERGIES = {
  a1: {
    id: 'test_allergy_a1',
    patientId: PATIENTS.a1.id,
    practiceId: PRACTICE_A_ID,
    allergen: 'Penicillin',
    severity: 'SEVERE' as const,
  },
  b1: {
    id: 'test_allergy_b1',
    patientId: PATIENTS.b1.id,
    practiceId: PRACTICE_B_ID,
    allergen: 'Latex',
    severity: 'MODERATE' as const,
  },
} as const;

export const MEDICATIONS = {
  a1: {
    id: 'test_med_a1',
    patientId: PATIENTS.a1.id,
    practiceId: PRACTICE_A_ID,
    name: 'Gabapentin',
    dosage: '300mg',
    frequency: 'three times daily',
  },
  b1: {
    id: 'test_med_b1',
    patientId: PATIENTS.b1.id,
    practiceId: PRACTICE_B_ID,
    name: 'Cyclobenzaprine',
    dosage: '10mg',
    frequency: 'at bedtime',
  },
} as const;

/**
 * Build a synthetic Session object for a given test user. Data-layer
 * tests use this directly (no NextAuth round-trip) — the data layer
 * only reads session.user.{id,role,practiceId}.
 */
export function sessionFor(user: TestUser) {
  return {
    user: {
      id: user.id,
      email: user.email,
      fullName: user.name,
      role: user.role,
      practiceId: user.practiceId,
    },
  };
}
