// ============================================================================
// Patient Detail — Server Component
// ----------------------------------------------------------------------------
// 1. Authorizes the request (DOCTOR/ADMIN only)
// 2. Fetches the patient by ID from the data layer
// 3. Writes a HIPAA audit log: VIEWED_PATIENT_FILE
// 4. Renders 404 NotFound state if patient missing
// 5. Hands data to the client component
//
// ALL PHI access happens here on the server.
// ============================================================================

import Link from 'next/link';
import { redirect } from 'next/navigation';
import { ArrowLeft, UserX } from 'lucide-react';

import { requireRole, AuthError } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { getPatientById } from '@/lib/data/patients';
import { listNotesByPatient } from '@/lib/data/clinical-notes';
import PatientDetailClient from './PatientDetailClient';

export const dynamic = 'force-dynamic'; // never cache PHI

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function PatientDetailPage({ params }: PageProps) {
  const { id } = await params;

  // 1. Authorization
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    if (err instanceof AuthError) {
      await logAudit({
        action: 'VIEWED_PATIENT_FILE',
        targetId: id,
        targetType: 'Patient',
        success: false,
        errorCode: err.code,
      });
      redirect('/login');
    }
    throw err;
  }

  // 2. Fetch patient — access-isolated. getPatientById returns null both
  //    for "doesn't exist" and "session can't see this patient". Combining
  //    the two cases intentionally prevents URL probing from enumerating
  //    other users' charts (both states render as "Patient Not Found").
  const patient = await getPatientById(id, session);

  // 3. Audit log — record the access attempt (success or 404)
  await logAudit({
    action: 'VIEWED_PATIENT_FILE',
    targetId: id,
    targetType: 'Patient',
    success: !!patient,
    errorCode: patient ? null : 'NOT_FOUND',
  });

  // 4. 404 state — clean Patient Not Found
  if (!patient) {
    return <PatientNotFound id={id} />;
  }

  // 5. Fetch clinical notes + custom procedures separately (newest first)
  const [notes, customProcedures] = await Promise.all([
    listNotesByPatient(id, 'CLINICAL_NOTE', session),
    listNotesByPatient(id, 'CUSTOM_PROCEDURE', session),
  ]);

  // 6. Render
  return (
    <PatientDetailClient
      patient={patient}
      notes={notes}
      customProcedures={customProcedures}
    />
  );
}

// ----------------------------------------------------------------------------
// 404 component (kept inline so it shares the dashboard layout/sidebar)
// ----------------------------------------------------------------------------
function PatientNotFound({ id }: { id: string }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0A192F] flex items-center justify-center px-4">
      {/* Ambient glows */}
      <div className="absolute top-[20%] left-[30%] w-[600px] h-[600px] rounded-full bg-blue-500 opacity-15 blur-[120px] pointer-events-none z-0" />
      <div className="absolute bottom-[10%] right-[10%] w-[400px] h-[400px] rounded-full bg-violet-500 opacity-15 blur-[120px] pointer-events-none z-0" />

      <div className="relative z-10 max-w-md w-full">
        <div className="rounded-2xl bg-white/5 backdrop-blur-md border border-white/10 p-8 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-red-500/10 border border-red-500/30 mb-4">
            <UserX className="w-8 h-8 text-red-400" />
          </div>
          <h1 className="text-xl font-bold text-white mb-2">Patient Not Found</h1>
          <p className="text-sm text-slate-400 mb-1">
            No patient exists with the ID:
          </p>
          <p className="text-xs font-mono text-slate-500 mb-6 break-all">{id}</p>
          <p className="text-xs text-slate-500 mb-6">
            The record may have been archived, deleted, or never existed.
            <br />
            This access attempt has been logged.
          </p>
          <Link
            href="/dashboard/patients"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-gradient-to-r from-blue-500 to-teal-500 text-white text-sm font-semibold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 hover:scale-[1.02] transition-all"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Patients
          </Link>
        </div>
      </div>
    </div>
  );
}
