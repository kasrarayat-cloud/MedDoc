// ============================================================================
// Appointments Data Layer
// ----------------------------------------------------------------------------
// Prisma `Appointment` model with in-memory fallback for demo mode.
// ============================================================================

import prisma, { isDatabaseHealthy } from '@meddoc/db';
import type { Session } from '@/lib/auth';
import { patientAccessWhere, getPatientById } from './patients';

export interface AppointmentView {
  id: string;
  patientId: string;
  userId: string;
  scheduledAt: string; // ISO
  type: 'CONSULTATION' | 'FOLLOW_UP' | 'PROCEDURE';
  status: 'SCHEDULED' | 'WAITING' | 'IN_ROOM' | 'COMPLETED' | 'CANCELLED';
  notes: string | null;
  aiPrepNote: string | null;
  createdAt: string; // ISO
}

/** Extended view with patient name for calendar display */
export interface CalendarAppointment extends AppointmentView {
  patientFirstName: string;
  patientLastName: string;
}

export interface CreateAppointmentInput {
  patientId: string;
  userId: string;
  scheduledAt: Date;
  type: AppointmentView['type'];
  notes?: string | null;
}

// ---------------------------------------------------------------------------
// In-memory fallback — persisted on globalThis to survive hot-reload
// ---------------------------------------------------------------------------
const globalForApts = globalThis as unknown as { _memApts?: Map<string, AppointmentView[]> };
if (!globalForApts._memApts) globalForApts._memApts = new Map();
const memoryAppointments = globalForApts._memApts;

function generateId(): string {
  return `apt_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function listAppointmentsByPatient(
  patientId: string,
  session: Session
): Promise<AppointmentView[]> {
  if (await isDatabaseHealthy()) {
    try {
      const rows = await prisma.appointment.findMany({
        where: {
          patientId,
          patient: patientAccessWhere(session),
        },
        orderBy: { scheduledAt: 'asc' },
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return rows.map((r: any) => toView(r));
    } catch (err) {
      console.warn('[data/appointments] Prisma findMany failed, using memory:', err);
    }
  }
  return (memoryAppointments.get(patientId) ?? []).sort(
    (a, b) => new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime()
  );
}

/**
 * Look up an appointment by id, restricted to appointments whose parent
 * patient the session can see. Returns null for both "doesn't exist" and
 * "forbidden" — callers can't distinguish.
 */
export async function getAppointmentById(
  id: string,
  session: Session
): Promise<AppointmentView | null> {
  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.appointment.findFirst({
        where: {
          id,
          patient: patientAccessWhere(session),
        },
      });
      if (!row) return null;
      return toView(row);
    } catch (err) {
      console.warn('[data/appointments] Prisma findFirst failed, using memory:', err);
    }
  }
  for (const apts of memoryAppointments.values()) {
    const found = apts.find((a) => a.id === id);
    if (found) return found;
  }
  return null;
}

export async function createAppointment(
  input: CreateAppointmentInput,
  session: Session
): Promise<AppointmentView> {
  // Verify the patient is visible to the session before writing —
  // stops a Practice-A user from scheduling against a Practice-B
  // patient by sending that patientId from the client.
  const patient = await getPatientById(input.patientId, session);
  if (!patient) {
    throw new Error('Patient not found');
  }

  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.appointment.create({
        data: {
          patientId: input.patientId,
          userId: input.userId,
          scheduledAt: input.scheduledAt,
          type: input.type,
          status: 'SCHEDULED',
          notes: input.notes ?? null,
        },
      });
      return toView(row);
    } catch (err) {
      console.warn('[data/appointments] Prisma create failed, using memory:', err);
    }
  }

  const apt: AppointmentView = {
    id: generateId(),
    patientId: input.patientId,
    userId: input.userId,
    scheduledAt: input.scheduledAt.toISOString(),
    type: input.type,
    status: 'SCHEDULED',
    notes: input.notes ?? null,
    aiPrepNote: null,
    createdAt: new Date().toISOString(),
  };
  const list = memoryAppointments.get(input.patientId) ?? [];
  list.push(apt);
  memoryAppointments.set(input.patientId, list);
  return apt;
}

/**
 * List all appointments visible to the session, newest-scheduled first.
 * Tenant-scoped via `patient: patientAccessWhere(session)` — SUPER_ADMIN
 * sees every practice, ADMIN sees their practice, DOCTOR/STAFF see only
 * their own caseload.
 */
export async function listAllAppointments(
  session: Session,
  options: { includeCancelled?: boolean } = {}
): Promise<CalendarAppointment[]> {
  if (await isDatabaseHealthy()) {
    try {
      const rows = await prisma.appointment.findMany({
        where: {
          patient: patientAccessWhere(session),
          // Hide soft-deleted (CANCELLED) appointments by default — the
          // audit row remains in AuditLog. Pass includeCancelled: true
          // from an admin/audit UI if you want to surface them.
          ...(options.includeCancelled ? {} : { NOT: { status: 'CANCELLED' } }),
        },
        orderBy: { scheduledAt: 'asc' },
        include: { patient: { select: { firstName: true, lastName: true } } },
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return rows.map((r: any) => ({
        ...toView(r),
        patientFirstName: r.patient?.firstName ?? 'Unknown',
        patientLastName: r.patient?.lastName ?? '',
      }));
    } catch (err) {
      console.warn('[data/appointments] Prisma listAll failed, using memory:', err);
    }
  }

  // Memory fallback — merge all patient arrays, resolve names from mock data
  const { MOCK_PATIENTS } = await import('@/lib/mock-patients');
  const patientMap = new Map(MOCK_PATIENTS.map((p) => [p.id, p]));
  const all: CalendarAppointment[] = [];

  for (const apts of memoryAppointments.values()) {
    for (const apt of apts) {
      if (!options.includeCancelled && apt.status === 'CANCELLED') continue;
      const pat = patientMap.get(apt.patientId);
      all.push({
        ...apt,
        patientFirstName: pat?.firstName ?? 'Unknown',
        patientLastName: pat?.lastName ?? '',
      });
    }
  }

  return all.sort(
    (a, b) => new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime()
  );
}

/**
 * Update an appointment's clinic flow status.
 */
export async function updateAppointmentStatus(
  appointmentId: string,
  newStatus: AppointmentView['status'],
  session: Session
): Promise<AppointmentView | null> {
  // Ownership check before mutating — otherwise a client could PATCH any
  // appointmentId across tenant boundaries.
  const existing = await getAppointmentById(appointmentId, session);
  if (!existing) return null;

  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.appointment.update({
        where: { id: appointmentId },
        data: { status: newStatus },
      });
      return toView(row);
    } catch (err) {
      console.warn('[data/appointments] Prisma status update failed, using memory:', err);
    }
  }
  for (const apts of memoryAppointments.values()) {
    const idx = apts.findIndex((a) => a.id === appointmentId);
    if (idx !== -1) {
      apts[idx] = { ...apts[idx], status: newStatus };
      return apts[idx];
    }
  }
  return null;
}

/**
 * Save an AI prep note to an appointment.
 */
/**
 * "Delete" an appointment. In a HIPAA-audited system we don't hard-delete
 * — we set status to CANCELLED so the row (and the audit trail leading up
 * to it) survives. `listAllAppointments` hides CANCELLED rows from the
 * calendar by default, so from the doctor's perspective the appointment
 * disappears. Ownership check via `getAppointmentById` prevents cross-tenant
 * deletes.
 */
export async function deleteAppointment(
  appointmentId: string,
  session: Session
): Promise<boolean> {
  const existing = await getAppointmentById(appointmentId, session);
  if (!existing) return false;

  if (await isDatabaseHealthy()) {
    try {
      await prisma.appointment.update({
        where: { id: appointmentId },
        data: { status: 'CANCELLED' },
      });
      return true;
    } catch (err) {
      console.warn('[data/appointments] Prisma delete (soft) failed, using memory:', err);
    }
  }

  for (const apts of memoryAppointments.values()) {
    const idx = apts.findIndex((a) => a.id === appointmentId);
    if (idx !== -1) {
      apts[idx] = { ...apts[idx], status: 'CANCELLED' };
      return true;
    }
  }
  return false;
}

export async function updateAppointmentPrepNote(
  appointmentId: string,
  aiPrepNote: string,
  session: Session
): Promise<AppointmentView | null> {
  const existing = await getAppointmentById(appointmentId, session);
  if (!existing) return null;

  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.appointment.update({
        where: { id: appointmentId },
        data: { aiPrepNote },
      });
      return toView(row);
    } catch (err) {
      console.warn('[data/appointments] Prisma update failed, using memory:', err);
    }
  }

  // Memory fallback
  for (const apts of memoryAppointments.values()) {
    const idx = apts.findIndex((a) => a.id === appointmentId);
    if (idx !== -1) {
      apts[idx] = { ...apts[idx], aiPrepNote };
      return apts[idx];
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Internal
// ---------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function toView(row: any): AppointmentView {
  return {
    id: row.id,
    patientId: row.patientId,
    userId: row.userId,
    scheduledAt: row.scheduledAt.toISOString(),
    type: row.type as AppointmentView['type'],
    status: (row.status ?? 'SCHEDULED') as AppointmentView['status'],
    notes: row.notes ?? null,
    aiPrepNote: row.aiPrepNote ?? null,
    createdAt: row.createdAt.toISOString(),
  };
}
