'use server';

// ============================================================================
// Schedule Server Actions
// ============================================================================

import { revalidatePath } from 'next/cache';
import OpenAI from 'openai';

import { requireRole, AuthError } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { listNotesByPatient } from '@/lib/data/clinical-notes';
import {
  createAppointment,
  deleteAppointment,
  updateAppointmentPrepNote,
  updateAppointmentStatus,
  type AppointmentView,
} from '@/lib/data/appointments';

type ActionResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string };

let _openai: OpenAI | null = null;
function getOpenAI(): OpenAI {
  if (!_openai) {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey?.trim()) {
      throw new Error('OPENAI_API_KEY is not configured');
    }
    _openai = new OpenAI({ apiKey });
  }
  return _openai;
}

const AI_PREP_SYSTEM_PROMPT = `You are an expert medical assistant preparing a concise visit briefing for a pain management physician. Review the past clinical notes and provide a very concise summary to prep the doctor for today's visit.

FORMAT — return exactly 2 bullet points, nothing else:
- First bullet: Key past treatments, procedures done, and their outcomes.
- Second bullet: Ongoing issues and the likely focus for today's visit.

RULES:
1. Use ONLY information from the provided notes. Never invent findings.
2. Keep each bullet to 1-2 sentences maximum.
3. Use clinical terminology naturally but be concise.
4. Do NOT include greetings, headers, or meta-commentary.
5. Start directly with "•" for each bullet.`;

export async function generateAIPrepNoteAction(
  appointmentId: string,
  patientId: string
): Promise<ActionResult<{ aiPrepNote: string }>> {
  // 1. Authorization — capture the session so we can thread it through
  //    every data-layer call. Without this the client could pass any
  //    patientId / appointmentId and read/mutate across tenants.
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN', 'STAFF']);
  } catch (err) {
    if (err instanceof AuthError) {
      return { ok: false, error: err.message };
    }
    return { ok: false, error: 'Authentication failed.' };
  }

  // 2. Fetch recent clinical notes — tenant-scoped
  const notes = await listNotesByPatient(patientId, 'CLINICAL_NOTE', session);
  const recentNotes = notes.slice(0, 3);

  if (recentNotes.length === 0) {
    // No notes — save a friendly fallback message
    const fallbackMsg = '• No past clinical notes found for this patient.\n• Review intake forms and patient history before the visit.';

    const fallbackUpdated = await updateAppointmentPrepNote(appointmentId, fallbackMsg, session);
    if (!fallbackUpdated) {
      return { ok: false, error: 'Appointment not found.' };
    }

    await logAudit({
      action: 'VIEWED_PATIENT_FILE',
      targetId: patientId,
      targetType: 'Patient',
      metadata: { purpose: 'ai_prep_generation', appointmentId, hadNotes: false },
    });

    revalidatePath('/dashboard/schedule');
    return { ok: true, data: { aiPrepNote: fallbackMsg } };
  }

  // 3. Build context from notes
  const notesContext = recentNotes
    .map(
      (n, i) =>
        `--- Note ${i + 1} (${n.procedureType ?? 'General'}, ${n.createdAt.split('T')[0]}) ---\n${n.content}`
    )
    .join('\n\n');

  // 4. Call GPT-4o-mini
  const openai = getOpenAI();
  let prepNote: string;

  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0.3,
      max_tokens: 300,
      messages: [
        { role: 'system', content: AI_PREP_SYSTEM_PROMPT },
        { role: 'user', content: notesContext },
      ],
    });
    prepNote = (completion.choices[0]?.message?.content ?? '').trim();
  } catch (err) {
    const message = err instanceof Error ? err.message : 'AI generation failed';
    return { ok: false, error: `Failed to generate prep note: ${message}` };
  }

  if (!prepNote) {
    return { ok: false, error: 'AI returned empty — please try again.' };
  }

  // 5. Save to appointment
  const updated = await updateAppointmentPrepNote(appointmentId, prepNote, session);
  if (!updated) {
    return { ok: false, error: 'Appointment not found.' };
  }

  // 6. Audit
  await logAudit({
    action: 'VIEWED_PATIENT_FILE',
    targetId: patientId,
    targetType: 'Patient',
    metadata: {
      purpose: 'ai_prep_generation',
      appointmentId,
      noteCount: recentNotes.length,
      prepLength: prepNote.length,
    },
  });

  revalidatePath('/dashboard/schedule');
  return { ok: true, data: { aiPrepNote: prepNote } };
}

// ===========================================================================
// QUICK ADD — schedule appointment from the calendar page (with patient select)
// ===========================================================================

export async function quickAddAppointmentAction(
  formData: FormData
): Promise<ActionResult<AppointmentView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN', 'STAFF']);
  } catch (err) {
    if (err instanceof AuthError) return { ok: false, error: err.message };
    return { ok: false, error: 'Authentication failed.' };
  }

  const patientId = formData.get('patientId');
  // Client sends an ISO-8601 UTC string built from the browser's local TZ
  // (see src/lib/datetime.ts) so the server never has to guess a zone.
  const scheduledAtStr = formData.get('scheduledAt');
  const visitType = formData.get('visitType');
  const notes = formData.get('notes');

  if (typeof patientId !== 'string' || !patientId) {
    return { ok: false, error: 'Please select a patient.' };
  }
  if (typeof scheduledAtStr !== 'string' || !scheduledAtStr) {
    return { ok: false, error: 'Date and time are required.' };
  }
  if (
    typeof visitType !== 'string' ||
    !['CONSULTATION', 'FOLLOW_UP', 'PROCEDURE'].includes(visitType)
  ) {
    return { ok: false, error: 'Valid visit type is required.' };
  }

  const scheduledAt = new Date(scheduledAtStr);
  if (isNaN(scheduledAt.getTime())) {
    return { ok: false, error: 'Invalid date or time.' };
  }

  let appointment: AppointmentView;
  try {
    appointment = await createAppointment(
      {
        patientId,
        userId: session.user.id,
        scheduledAt,
        type: visitType as AppointmentView['type'],
        notes: typeof notes === 'string' && notes.trim() ? notes.trim() : null,
      },
      session
    );
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Failed to schedule';
    return { ok: false, error: msg };
  }

  await logAudit({
    action: 'SCHEDULED_VISIT',
    targetId: appointment.id,
    targetType: 'Appointment',
    metadata: { patientId, visitType, scheduledAt: scheduledAt.toISOString() },
  });

  revalidatePath('/dashboard/schedule');
  return { ok: true, data: appointment };
}

// ===========================================================================
// UPDATE APPOINTMENT STATUS — Clinic Flow transitions
// ===========================================================================

const VALID_STATUSES: AppointmentView['status'][] = [
  'SCHEDULED',
  'WAITING',
  'IN_ROOM',
  'COMPLETED',
  'CANCELLED',
];

export async function updateAppointmentStatusAction(
  appointmentId: string,
  newStatus: string
): Promise<ActionResult<AppointmentView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN', 'STAFF']);
  } catch (err) {
    if (err instanceof AuthError) return { ok: false, error: err.message };
    return { ok: false, error: 'Authentication failed.' };
  }

  if (!VALID_STATUSES.includes(newStatus as AppointmentView['status'])) {
    return { ok: false, error: `Invalid status: ${newStatus}` };
  }

  const updated = await updateAppointmentStatus(
    appointmentId,
    newStatus as AppointmentView['status'],
    session
  );

  if (!updated) {
    return { ok: false, error: 'Appointment not found.' };
  }

  await logAudit({
    action: 'UPDATED_APPOINTMENT_STATUS',
    targetId: appointmentId,
    targetType: 'Appointment',
    metadata: { newStatus },
  });

  revalidatePath('/dashboard/schedule');
  return { ok: true, data: updated };
}

// ===========================================================================
// DELETE APPOINTMENT — soft-delete via status='CANCELLED'
// ---------------------------------------------------------------------------
// HIPAA-friendly: we never hard-delete appointment rows. Setting the status
// to CANCELLED hides it from the default calendar view while preserving the
// row + the audit trail. If staff entered the wrong date/time, they delete
// the bad row and create a new one; the audit log shows both events.
// ===========================================================================

export async function deleteAppointmentAction(
  appointmentId: string
): Promise<ActionResult<{ deleted: boolean }>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN', 'STAFF']);
  } catch (err) {
    await logAudit({
      action: 'DELETED_APPOINTMENT',
      targetId: appointmentId,
      targetType: 'Appointment',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    if (err instanceof AuthError) return { ok: false, error: err.message };
    return { ok: false, error: 'Authentication failed.' };
  }

  const ok = await deleteAppointment(appointmentId, session);
  if (!ok) {
    return { ok: false, error: 'Appointment not found.' };
  }

  await logAudit({
    action: 'DELETED_APPOINTMENT',
    targetId: appointmentId,
    targetType: 'Appointment',
  });

  revalidatePath('/dashboard/schedule');
  return { ok: true, data: { deleted: true } };
}
