// ============================================================================
// Clinical Safety — tenant isolation adversarial suite
// ----------------------------------------------------------------------------
// Allergies + medications carry the same multi-tenancy guarantees as patient
// charts. These tests forge a session for one practice and try to read,
// modify, or delete safety data owned by the other practice. Every cross-
// tenant attempt MUST fail (return empty / throw / no-op).
//
// Prereq: `npm run seed:e2e` populates ALLERGIES.{a1,b1} and MEDICATIONS.{a1,b1}.
// ============================================================================

import { describe, it, expect } from 'vitest';

import {
  listAllergiesForPatient,
  createAllergy,
  updateAllergy,
  deleteAllergy,
  setNoKnownAllergies,
  listMedicationsForPatient,
  createMedication,
  updateMedication,
  deleteMedication,
} from '@/lib/data/clinical-safety';
import type { Session } from '@/lib/auth';

import {
  USERS,
  PATIENTS,
  ALLERGIES,
  MEDICATIONS,
  sessionFor,
} from '../fixtures/tenancy';

const sessions = {
  super: sessionFor(USERS.super) as Session,
  adminA: sessionFor(USERS.adminA) as Session,
  doctorA: sessionFor(USERS.doctorA) as Session,
  staffA: sessionFor(USERS.staffA) as Session,
  adminB: sessionFor(USERS.adminB) as Session,
  doctorB: sessionFor(USERS.doctorB) as Session,
};

// ---------------------------------------------------------------------------
// READ isolation
// ---------------------------------------------------------------------------
describe('Allergies — read isolation', () => {
  it('Doctor A sees only their patient\'s allergies', async () => {
    const aRows = await listAllergiesForPatient(sessions.doctorA, PATIENTS.a1.id);
    expect(aRows.some((r) => r.id === ALLERGIES.a1.id)).toBe(true);
    expect(aRows.some((r) => r.id === ALLERGIES.b1.id)).toBe(false);
  });

  it('Doctor A querying Practice B\'s patient gets an empty list (no leak)', async () => {
    const rows = await listAllergiesForPatient(sessions.doctorA, PATIENTS.b1.id);
    expect(rows).toEqual([]);
  });

  it('Admin A querying Practice B\'s patient gets an empty list', async () => {
    const rows = await listAllergiesForPatient(sessions.adminA, PATIENTS.b1.id);
    expect(rows).toEqual([]);
  });

  it('SUPER_ADMIN sees every practice\'s allergies', async () => {
    const aRows = await listAllergiesForPatient(sessions.super, PATIENTS.a1.id);
    const bRows = await listAllergiesForPatient(sessions.super, PATIENTS.b1.id);
    expect(aRows.length).toBeGreaterThan(0);
    expect(bRows.length).toBeGreaterThan(0);
  });

  it('Doctor A querying a forged patient ID gets empty (no enumeration)', async () => {
    const rows = await listAllergiesForPatient(sessions.doctorA, 'not_a_real_patient');
    expect(rows).toEqual([]);
  });
});

describe('Medications — read isolation', () => {
  it('Doctor A sees only their patient\'s medications', async () => {
    const aRows = await listMedicationsForPatient(sessions.doctorA, PATIENTS.a1.id);
    expect(aRows.some((r) => r.id === MEDICATIONS.a1.id)).toBe(true);
    expect(aRows.some((r) => r.id === MEDICATIONS.b1.id)).toBe(false);
  });

  it('Doctor A querying Practice B\'s patient gets empty', async () => {
    const rows = await listMedicationsForPatient(sessions.doctorA, PATIENTS.b1.id);
    expect(rows).toEqual([]);
  });

  it('Doctor B sees their own patient\'s medications', async () => {
    const rows = await listMedicationsForPatient(sessions.doctorB, PATIENTS.b1.id);
    expect(rows.some((r) => r.id === MEDICATIONS.b1.id)).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// WRITE isolation — adversarial
// ---------------------------------------------------------------------------
describe('Allergies — write isolation', () => {
  it('Doctor A cannot create an allergy on Practice B\'s patient', async () => {
    await expect(
      createAllergy(sessions.doctorA, {
        patientId: PATIENTS.b1.id,
        allergen: 'cross-tenant probe',
      })
    ).rejects.toThrow(/not found|access denied/i);
  });

  it('Doctor A cannot update Practice B\'s allergy', async () => {
    await expect(
      updateAllergy(sessions.doctorA, ALLERGIES.b1.id, { severity: 'SEVERE' })
    ).rejects.toThrow(/not found|access denied/i);
  });

  it('Doctor A cannot delete Practice B\'s allergy', async () => {
    await expect(
      deleteAllergy(sessions.doctorA, ALLERGIES.b1.id)
    ).rejects.toThrow(/not found|access denied/i);
  });

  it('Doctor A cannot toggle NKA on Practice B\'s patient', async () => {
    await expect(
      setNoKnownAllergies(sessions.doctorA, PATIENTS.b1.id, true)
    ).rejects.toThrow(/not found|access denied/i);
  });
});

describe('Medications — write isolation', () => {
  it('Doctor A cannot create a medication on Practice B\'s patient', async () => {
    await expect(
      createMedication(sessions.doctorA, {
        patientId: PATIENTS.b1.id,
        name: 'cross-tenant probe',
      })
    ).rejects.toThrow(/not found|access denied/i);
  });

  it('Doctor A cannot update Practice B\'s medication', async () => {
    await expect(
      updateMedication(sessions.doctorA, MEDICATIONS.b1.id, { isActive: false })
    ).rejects.toThrow(/not found|access denied/i);
  });

  it('Doctor A cannot delete Practice B\'s medication', async () => {
    await expect(
      deleteMedication(sessions.doctorA, MEDICATIONS.b1.id)
    ).rejects.toThrow(/not found|access denied/i);
  });
});

// ---------------------------------------------------------------------------
// Same-practice writes — happy path round-trip (so we know the rejection
// behavior above isn't a blanket "everything throws").
// ---------------------------------------------------------------------------
describe('Allergies + Medications — same-practice round-trip', () => {
  it('Doctor A can create + delete their own patient\'s allergy', async () => {
    const created = await createAllergy(sessions.doctorA, {
      patientId: PATIENTS.a1.id,
      allergen: 'temp probe — safe to delete',
      severity: 'MILD',
    });
    expect(created.allergen).toBe('temp probe — safe to delete');
    await deleteAllergy(sessions.doctorA, created.id);
    // Soft-deleted rows are excluded from the list.
    const after = await listAllergiesForPatient(sessions.doctorA, PATIENTS.a1.id);
    expect(after.some((r) => r.id === created.id)).toBe(false);
  });

  it('Doctor A can create + delete their own patient\'s medication', async () => {
    const created = await createMedication(sessions.doctorA, {
      patientId: PATIENTS.a1.id,
      name: 'temp probe — safe to delete',
    });
    expect(created.name).toBe('temp probe — safe to delete');
    await deleteMedication(sessions.doctorA, created.id);
    const after = await listMedicationsForPatient(sessions.doctorA, PATIENTS.a1.id);
    expect(after.some((r) => r.id === created.id)).toBe(false);
  });
});
