// ============================================================================
// Main Dashboard — Server Component
// ============================================================================

import { redirect } from 'next/navigation';
import { requireRole, AuthError } from '@/lib/auth';
import { getAllPatients } from '@/lib/data/patients';
import { listNotesByPatient } from '@/lib/data/clinical-notes';
import { listAllAppointments } from '@/lib/data/appointments';
import { getMemoryAuditLog } from '@/lib/audit';
import DashboardClient from './DashboardClient';

export const dynamic = 'force-dynamic';

export default async function DashboardPage() {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN', 'STAFF']);
  } catch (err) {
    if (err instanceof AuthError) {
      redirect('/login');
    }
    throw err;
  }

  // Fetch all data in parallel — patients list is session-filtered so
  // a doctor's dashboard shows only their own caseload.
  const [patients, appointments, auditEntries] = await Promise.all([
    getAllPatients(session),
    listAllAppointments(session),
    Promise.resolve(getMemoryAuditLog()),
  ]);

  // Count total clinical notes across all patients
  const noteCounts = await Promise.all(
    patients.slice(0, 20).map((p) =>
      listNotesByPatient(p.id, 'CLINICAL_NOTE', session).then((n) => n.length)
    )
  );
  const totalNotes = noteCounts.reduce((a, b) => a + b, 0);

  // Today's appointments
  const today = new Date();
  const todayAppointments = appointments.filter((apt) => {
    const d = new Date(apt.scheduledAt);
    return (
      d.getFullYear() === today.getFullYear() &&
      d.getMonth() === today.getMonth() &&
      d.getDate() === today.getDate()
    );
  });

  // Tomorrow's appointments
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const tomorrowAppointments = appointments.filter((apt) => {
    const d = new Date(apt.scheduledAt);
    return (
      d.getFullYear() === tomorrow.getFullYear() &&
      d.getMonth() === tomorrow.getMonth() &&
      d.getDate() === tomorrow.getDate()
    );
  });

  // Upcoming = today + tomorrow combined, sorted
  const upcomingAppointments = [...todayAppointments, ...tomorrowAppointments].sort(
    (a, b) => new Date(a.scheduledAt).getTime() - new Date(b.scheduledAt).getTime()
  );

  // Recent audit activity (last 8)
  const recentActivity = [...auditEntries]
    .reverse()
    .slice(0, 8)
    .map((entry) => ({
      action: String(entry.action ?? ''),
      targetType: String(entry.targetType ?? ''),
      targetId: String(entry.targetId ?? ''),
      timestamp: String(entry.timestamp ?? ''),
      success: Boolean(entry.success ?? true),
    }));

  return (
    <DashboardClient
      doctorName={session.user.fullName}
      totalPatients={patients.filter((p) => p.status === 'ACTIVE').length}
      totalNotes={totalNotes}
      todayAppointmentCount={todayAppointments.length}
      totalAppointments={appointments.length}
      upcomingAppointments={upcomingAppointments.slice(0, 5)}
      recentActivity={recentActivity}
    />
  );
}
