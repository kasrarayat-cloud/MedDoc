// ============================================================================
// Patients List — Server Component
// ----------------------------------------------------------------------------
// Authorizes the request, fetches patients from the data layer, writes an
// audit log entry, and hands the data to the client component for rendering.
//
// All PHI access happens here on the server — never in the client component.
// ============================================================================

import { redirect } from 'next/navigation';
import { requireRole, AuthError } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { getAllPatients } from '@/lib/data/patients';
import PatientsListClient from './PatientsListClient';

export const dynamic = 'force-dynamic'; // never cache PHI

export default async function PatientsListPage() {
  // 1. Authorization — only DOCTOR or ADMIN can view patient list.
  //    requireRole returns the session, which we thread into getAllPatients
  //    so the data layer can enforce per-user patient isolation (HIPAA).
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
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

  // 2. Fetch patients the session is authorized to see
  const patients = await getAllPatients(session);

  // 3. HIPAA audit log — record that the list was viewed
  await logAudit({
    action: 'VIEWED_PATIENT_LIST',
    metadata: { resultCount: patients.length },
  });

  // 4. Render client component with the data
  return <PatientsListClient initialPatients={patients} />;
}
