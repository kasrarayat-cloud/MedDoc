// ============================================================================
// Tenant Isolation — adversarial unit suite
// ----------------------------------------------------------------------------
// These tests hit the real data layer against the DATABASE_URL Postgres with
// the matrix seeded by `scripts/seed-tenancy-fixtures.ts`. Each test forges
// a Session for one persona and attempts an operation that SHOULD return
// null / empty / throw when aimed at a row in the other tenant.
//
// Prereq (run once per DB):
//   npm run seed:e2e
//
// These are the tests a cross-tenant attacker would try. If any assertion
// here fails, we have a real leak — don't let these go red.
// ============================================================================

import { describe, it, expect, afterAll } from 'vitest';

import {
  getAllPatients,
  getPatientById,
  archivePatient,
} from '@/lib/data/patients';
import {
  listNotesByPatient,
  getNoteById,
  updateClinicalNote,
} from '@/lib/data/clinical-notes';
import {
  listAllAppointments,
  listAppointmentsByPatient,
  getAppointmentById,
  updateAppointmentStatus,
  updateAppointmentPrepNote,
  createAppointment,
  deleteAppointment,
} from '@/lib/data/appointments';
import type { Session } from '@/lib/auth';

import {
  USERS,
  PATIENTS,
  NOTES,
  APPOINTMENTS,
  sessionFor,
} from '../fixtures/tenancy';

// ---------------------------------------------------------------------------
// Synthetic sessions — the data layer only cares about session.user.{id,role,practiceId}.
// ---------------------------------------------------------------------------
const sessions = {
  super: sessionFor(USERS.super) as Session,
  adminA: sessionFor(USERS.adminA) as Session,
  doctorA: sessionFor(USERS.doctorA) as Session,
  staffA: sessionFor(USERS.staffA) as Session,
  adminB: sessionFor(USERS.adminB) as Session,
  doctorB: sessionFor(USERS.doctorB) as Session,
};

// ---------------------------------------------------------------------------
// Test-local state cleanup — archivePatient mutates; restore it after.
// ---------------------------------------------------------------------------
afterAll(async () => {
  // Re-run the seed-style upsert to un-archive patient-b1 if any test
  // flipped its deletedAt. Keeps the fixtures green for the next run.
  const { PrismaClient } = await import('@prisma/client');
  const { PrismaPg } = await import('@prisma/adapter-pg');
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const adapter = new (PrismaPg as any)({ connectionString: process.env.DATABASE_URL });
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const prisma = new (PrismaClient as any)({ adapter });
  await prisma.patient.updateMany({
    where: { id: { in: Object.values(PATIENTS).map((p) => p.id) } },
    data: { status: 'ACTIVE', deletedAt: null },
  });
  await prisma.$disconnect();
});

// ===========================================================================
// Patient list scoping
// ===========================================================================
describe('getAllPatients — role-based visibility', () => {
  it('SUPER_ADMIN sees all test patients from both practices', async () => {
    const list = await getAllPatients(sessions.super);
    const ids = new Set(list.map((p) => p.id));
    expect(ids.has(PATIENTS.a1.id)).toBe(true);
    expect(ids.has(PATIENTS.a2.id)).toBe(true);
    expect(ids.has(PATIENTS.b1.id)).toBe(true);
    expect(ids.has(PATIENTS.b2.id)).toBe(true);
  });

  it('ADMIN-A sees only Practice-A patients', async () => {
    const list = await getAllPatients(sessions.adminA);
    const ids = new Set(list.map((p) => p.id));
    expect(ids.has(PATIENTS.a1.id)).toBe(true);
    expect(ids.has(PATIENTS.a2.id)).toBe(true);
    expect(ids.has(PATIENTS.b1.id)).toBe(false);
    expect(ids.has(PATIENTS.b2.id)).toBe(false);
  });

  it('ADMIN-B sees only Practice-B patients', async () => {
    const list = await getAllPatients(sessions.adminB);
    const ids = new Set(list.map((p) => p.id));
    expect(ids.has(PATIENTS.b1.id)).toBe(true);
    expect(ids.has(PATIENTS.b2.id)).toBe(true);
    expect(ids.has(PATIENTS.a1.id)).toBe(false);
    expect(ids.has(PATIENTS.a2.id)).toBe(false);
  });

  it('DOCTOR-A sees only patients they created or are assigned to', async () => {
    const list = await getAllPatients(sessions.doctorA);
    const ids = new Set(list.map((p) => p.id));
    // a1 + a2 are both seeded with createdById=doctorA, so both visible.
    expect(ids.has(PATIENTS.a1.id)).toBe(true);
    expect(ids.has(PATIENTS.a2.id)).toBe(true);
    // Practice-B patients must NEVER appear regardless of the user-level rule.
    expect(ids.has(PATIENTS.b1.id)).toBe(false);
    expect(ids.has(PATIENTS.b2.id)).toBe(false);
  });

  it('STAFF-A in Practice A cannot see patients they did not create', async () => {
    // staffA didn't create any patients, so the list should be empty of A and B.
    const list = await getAllPatients(sessions.staffA);
    const ids = new Set(list.map((p) => p.id));
    expect(ids.has(PATIENTS.a1.id)).toBe(false);
    expect(ids.has(PATIENTS.a2.id)).toBe(false);
    expect(ids.has(PATIENTS.b1.id)).toBe(false);
    expect(ids.has(PATIENTS.b2.id)).toBe(false);
  });
});

// ===========================================================================
// Patient detail probing
// ===========================================================================
describe('getPatientById — cross-tenant probing returns null', () => {
  it('DOCTOR-A forging Practice-B patient id gets null', async () => {
    const p = await getPatientById(PATIENTS.b1.id, sessions.doctorA);
    expect(p).toBeNull();
  });

  it('ADMIN-A forging Practice-B patient id gets null', async () => {
    const p = await getPatientById(PATIENTS.b1.id, sessions.adminA);
    expect(p).toBeNull();
  });

  it('SUPER_ADMIN can see Practice-B patient by id', async () => {
    const p = await getPatientById(PATIENTS.b1.id, sessions.super);
    expect(p?.id).toBe(PATIENTS.b1.id);
  });

  it('DOCTOR-B can see their own Practice-B patient', async () => {
    const p = await getPatientById(PATIENTS.b1.id, sessions.doctorB);
    expect(p?.id).toBe(PATIENTS.b1.id);
  });
});

// ===========================================================================
// Clinical notes
// ===========================================================================
describe('clinical-notes — cross-tenant access', () => {
  it('listNotesByPatient with forged B patientId + DOCTOR-A session returns []', async () => {
    const notes = await listNotesByPatient(PATIENTS.b1.id, undefined, sessions.doctorA);
    expect(notes).toEqual([]);
  });

  it('listNotesByPatient with own patient returns the note', async () => {
    const notes = await listNotesByPatient(PATIENTS.b1.id, undefined, sessions.doctorB);
    expect(notes.map((n) => n.id)).toContain(NOTES.b1.id);
  });

  it('getNoteById with forged B noteId + DOCTOR-A session returns null', async () => {
    const note = await getNoteById(NOTES.b1.id, sessions.doctorA);
    expect(note).toBeNull();
  });

  it('updateClinicalNote ownership check rejects cross-tenant write', async () => {
    // Try to overwrite B's note from A's session.
    const result = await updateClinicalNote(
      NOTES.b1.id,
      'pwned content from Practice A',
      sessions.doctorA.user.id,
      sessions.doctorA
    );
    expect(result).toBeNull();

    // And prove the note content was NOT mutated.
    const stillOriginal = await getNoteById(NOTES.b1.id, sessions.doctorB);
    expect(stillOriginal?.content).not.toContain('pwned');
  });
});

// ===========================================================================
// Appointments
// ===========================================================================
describe('appointments — cross-tenant access', () => {
  it('listAllAppointments for DOCTOR-A excludes Practice-B rows', async () => {
    const apts = await listAllAppointments(sessions.doctorA);
    const ids = new Set(apts.map((a) => a.id));
    expect(ids.has(APPOINTMENTS.a1.id)).toBe(true);
    expect(ids.has(APPOINTMENTS.b1.id)).toBe(false);
  });

  it('listAllAppointments for SUPER_ADMIN includes both practices', async () => {
    const apts = await listAllAppointments(sessions.super);
    const ids = new Set(apts.map((a) => a.id));
    expect(ids.has(APPOINTMENTS.a1.id)).toBe(true);
    expect(ids.has(APPOINTMENTS.b1.id)).toBe(true);
  });

  it('listAppointmentsByPatient with forged B patientId + A session returns []', async () => {
    const apts = await listAppointmentsByPatient(PATIENTS.b1.id, sessions.doctorA);
    expect(apts).toEqual([]);
  });

  it('getAppointmentById with forged B id + A session returns null', async () => {
    const apt = await getAppointmentById(APPOINTMENTS.b1.id, sessions.doctorA);
    expect(apt).toBeNull();
  });

  it('updateAppointmentStatus cross-tenant returns null (no-op)', async () => {
    const result = await updateAppointmentStatus(
      APPOINTMENTS.b1.id,
      'COMPLETED',
      sessions.doctorA
    );
    expect(result).toBeNull();

    // And the row must still be SCHEDULED from B's perspective.
    const aptFromB = await getAppointmentById(APPOINTMENTS.b1.id, sessions.doctorB);
    expect(aptFromB?.status).toBe('SCHEDULED');
  });

  it('updateAppointmentPrepNote cross-tenant returns null', async () => {
    const result = await updateAppointmentPrepNote(
      APPOINTMENTS.b1.id,
      'injected prep from A',
      sessions.doctorA
    );
    expect(result).toBeNull();

    const aptFromB = await getAppointmentById(APPOINTMENTS.b1.id, sessions.doctorB);
    expect(aptFromB?.aiPrepNote ?? '').not.toContain('injected');
  });

  it('deleteAppointment cross-tenant returns false (no-op)', async () => {
    const ok = await deleteAppointment(APPOINTMENTS.b1.id, sessions.doctorA);
    expect(ok).toBe(false);

    // And the row must still be SCHEDULED from B's perspective.
    const aptFromB = await getAppointmentById(APPOINTMENTS.b1.id, sessions.doctorB);
    expect(aptFromB?.status).toBe('SCHEDULED');
  });

  it('createAppointment with forged B patientId + A session throws', async () => {
    await expect(
      createAppointment(
        {
          patientId: PATIENTS.b1.id,
          userId: sessions.doctorA.user.id,
          scheduledAt: new Date('2026-07-01T10:00:00Z'),
          type: 'CONSULTATION',
        },
        sessions.doctorA
      )
    ).rejects.toThrow(/patient not found/i);
  });
});

// ===========================================================================
// Archive
// ===========================================================================
describe('archivePatient — cross-tenant protection', () => {
  it('DOCTOR-A cannot archive a Practice-B patient', async () => {
    const ok = await archivePatient(PATIENTS.b2.id, sessions.doctorA);
    expect(ok).toBe(false);

    // Confirm the row is still ACTIVE for B.
    const stillThere = await getPatientById(PATIENTS.b2.id, sessions.doctorB);
    expect(stillThere?.status).toBe('ACTIVE');
  });
});
