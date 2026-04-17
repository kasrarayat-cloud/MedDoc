import { NextRequest, NextResponse } from 'next/server';
import { getSession } from '@/lib/auth';
import { getPatientById } from '@/lib/data/patients';
import { listNotesByPatient } from '@/lib/data/clinical-notes';
import { listAppointmentsByPatient, type AppointmentView } from '@/lib/data/appointments';
import { listAllergiesForPatient, listMedicationsForPatient } from '@/lib/data/clinical-safety';
import prisma from '@meddoc/db';
import { buildSystemPrompt } from '@/lib/realtime/tools';
import {
  buildClinicalTrajectory,
  fetchRecentAiActions,
  invalidateTrajectory,
} from '@/lib/realtime/intelligence';

// ============================================================================
// /api/realtime/refresh-context — return fresh system instructions for an
// active session
// ----------------------------------------------------------------------------
// Used by the panel after a side-channel write completes (file upload, AI-
// driven note edit, brief-history change, etc.) so the model's CONTEXT stays
// current. The Realtime API supports `session.update` over the data channel
// to swap in new instructions without restarting the connection.
//
// Same auth + tenant guard as the session endpoint — never lets a stale
// browser tab pull instructions for a patient outside the doctor's scope.
// ============================================================================

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let body: { patientId?: string; timezone?: string };
  try {
    body = (await request.json()) as { patientId?: string; timezone?: string };
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const patientId = body.patientId?.trim();
  if (!patientId) {
    return NextResponse.json({ error: 'patientId is required' }, { status: 400 });
  }
  const tz = body.timezone?.trim();
  let timezone = 'UTC';
  if (tz) {
    try {
      new Intl.DateTimeFormat('en-US', { timeZone: tz });
      timezone = tz;
    } catch {
      // bad input — stays UTC
    }
  }

  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return NextResponse.json({ error: 'Patient not found' }, { status: 404 });
  }

  // A refresh is always triggered by a chart write — bust the trajectory
  // cache so the regenerated prompt reflects whatever just changed.
  invalidateTrajectory(patientId);

  const [recentNotes, customProcedures, finalReports, patientFiles, appointments, recentAiActions, allergiesRaw, medicationsRaw, safetyFlags] =
    await Promise.all([
      listNotesByPatient(patientId, 'CLINICAL_NOTE', session),
      listNotesByPatient(patientId, 'CUSTOM_PROCEDURE', session),
      listNotesByPatient(patientId, 'FINAL_REPORT', session),
      listNotesByPatient(patientId, 'PATIENT_FILE', session),
      listAppointmentsByPatient(patientId, session),
      fetchRecentAiActions(patientId, session),
      listAllergiesForPatient(session, patientId),
      listMedicationsForPatient(session, patientId, { includeInactive: true }),
      prisma.patient.findUnique({ where: { id: patientId }, select: { noKnownAllergies: true } }),
    ]);
  const upcomingAppointments = filterUpcoming(appointments);
  const clinicalTrajectory = await buildClinicalTrajectory(
    patient,
    recentNotes,
    customProcedures
  );

  const instructions = buildSystemPrompt({
    patient,
    recentNotes: recentNotes.slice(0, 10),
    customProcedures: customProcedures.slice(0, 10),
    finalReports: finalReports.slice(0, 10),
    patientFiles: patientFiles.slice(0, 10),
    upcomingAppointments: upcomingAppointments.slice(0, 10),
    currentDateIso: new Date().toISOString(),
    timezone,
    clinicalTrajectory,
    recentAiActions,
    allergies: allergiesRaw.map((a) => ({ id: a.id, allergen: a.allergen, reaction: a.reaction, severity: a.severity })),
    medications: medicationsRaw.map((m) => ({ id: m.id, name: m.name, dosage: m.dosage, frequency: m.frequency, isActive: m.isActive })),
    noKnownAllergies: safetyFlags?.noKnownAllergies ?? false,
  });

  return NextResponse.json({ instructions });
}

function filterUpcoming(all: AppointmentView[]): AppointmentView[] {
  const now = Date.now();
  return all
    .filter((a) => a.status !== 'CANCELLED' && a.status !== 'COMPLETED')
    .filter((a) => new Date(a.scheduledAt).getTime() >= now - 24 * 60 * 60 * 1000)
    .sort((x, y) => new Date(x.scheduledAt).getTime() - new Date(y.scheduledAt).getTime());
}
