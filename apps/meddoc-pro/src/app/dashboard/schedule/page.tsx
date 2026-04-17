// ============================================================================
// Schedule / Calendar — Server Component
// ============================================================================

import { redirect } from 'next/navigation';
import { requireRole, AuthError } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { listAllAppointments } from '@/lib/data/appointments';
import { getAllPatients } from '@/lib/data/patients';
import ScheduleViewClient from './ScheduleViewClient';

export const dynamic = 'force-dynamic';

export default async function SchedulePage() {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN', 'STAFF']);
  } catch (err) {
    if (err instanceof AuthError) {
      await logAudit({
        action: 'VIEWED_PATIENT_LIST',
        success: false,
        errorCode: err.code,
      });
      redirect('/login');
    }
    throw err;
  }

  const [appointments, allPatients] = await Promise.all([
    listAllAppointments(session),
    getAllPatients(session),
  ]);

  // Build a lightweight patient list for the Quick Add dropdown
  const patients = allPatients
    .filter((p) => p.status === 'ACTIVE')
    .map((p) => ({
      id: p.id,
      firstName: p.firstName,
      lastName: p.lastName,
      mrn: p.mrn,
    }));

  return <ScheduleViewClient appointments={appointments} patients={patients} />;
}
