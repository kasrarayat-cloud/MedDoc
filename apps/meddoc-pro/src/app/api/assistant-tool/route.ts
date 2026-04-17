import { NextRequest, NextResponse } from 'next/server';
import { revalidatePath } from 'next/cache';
import { getSession } from '@/lib/auth';
import { logAudit } from '@/lib/audit';
import { archivePatient as dataArchivePatient } from '@/lib/data/patients';
import { getPatientById, patientAccessWhere } from '@/lib/data/patients';
import {
  listNotesByPatient,
  getNoteById as dataGetNoteById,
  deleteClinicalNote as dataDeleteClinicalNote,
} from '@/lib/data/clinical-notes';
import { deleteAppointment as dataDeleteAppointment } from '@/lib/data/appointments';
import {
  createAllergy,
  deleteAllergy,
  setNoKnownAllergies,
  createMedication,
  deleteMedication,
  updateMedication,
} from '@/lib/data/clinical-safety';
import OpenAI from 'openai';
import {
  dispatchCreateNote,
  dispatchEditNote,
  dispatchScheduleAppointment,
  dispatchSummarize,
  dispatchGenerateDocument,
  dispatchUpdatePatient,
  dispatchGenerateFinalReport,
  type AssistantAction,
  type AssistantResult,
  type DocumentType,
  type UpdatePatientFromAssistant,
} from '@/app/dashboard/patients/actions';

// ============================================================================
// /api/assistant-tool — server-side tool dispatcher for the Realtime model
// ----------------------------------------------------------------------------
// The browser opens a WebRTC peer to OpenAI directly. When the model decides
// to call a tool, the browser receives a function_call event and POSTs here:
//   { patientId, toolName, args }
//
// We:
//   1. AuthZ + tenant-guard (patient must be visible to this session)
//   2. Match toolName against the known set + validate args shape
//   3. Run the corresponding dispatcher (already does its own audit + save)
//   4. Return a string `output` for the browser to ship back to the model
//      via the data channel
//
// HIPAA model: nothing the model "decides" hits the DB without going through
// this gate. The model can request anything; we vet every request.
// ============================================================================

let openaiClient: OpenAI | null = null;
function getOpenAI(): OpenAI {
  if (!openaiClient) {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey) throw new Error('OPENAI_API_KEY is not configured');
    openaiClient = new OpenAI({ apiKey });
  }
  return openaiClient;
}

interface ToolRequest {
  patientId?: string;
  toolName?: string;
  args?: Record<string, unknown>;
}

// Result shape returned to the browser. `output` is the string the browser
// ships back to the Realtime model via the data channel — keep it short and
// natural so the model can paraphrase it for the doctor.
interface ToolResponse {
  ok: boolean;
  output: string;
  /** Surfaced for the panel to render (e.g., document preview chip). */
  action?: AssistantAction;
}

const VALID_VISIT_TYPES = new Set(['CONSULTATION', 'FOLLOW_UP', 'PROCEDURE']);
const VALID_DOC_TYPES = new Set([
  'REFERRAL_LETTER',
  'PATIENT_HANDOUT',
  'DISABILITY_FORM',
  'PRIOR_AUTH',
]);

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json<ToolResponse>(
      { ok: false, output: 'Unauthorized.' },
      { status: 401 }
    );
  }

  let body: ToolRequest;
  try {
    body = (await request.json()) as ToolRequest;
  } catch {
    return NextResponse.json<ToolResponse>(
      { ok: false, output: 'Invalid JSON body.' },
      { status: 400 }
    );
  }

  const patientId = body.patientId?.trim();
  const toolName = body.toolName?.trim();
  const args = body.args ?? {};

  if (!patientId || !toolName) {
    return NextResponse.json<ToolResponse>(
      { ok: false, output: 'Missing patientId or toolName.' },
      { status: 400 }
    );
  }

  // Tenant guard. Even though the browser already passed patientId into the
  // session-token endpoint, we re-check on every tool call — the model could
  // hallucinate a different patientId, and the data layer would still
  // protect us, but failing fast here gives a cleaner error to the model.
  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return NextResponse.json<ToolResponse>(
      { ok: false, output: 'Patient not found or not accessible.' },
      { status: 404 }
    );
  }

  try {
    switch (toolName) {
      case 'create_clinical_note': {
        const dictation = typeof args.dictation === 'string' ? args.dictation : '';
        if (!dictation.trim()) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Dictation is empty.' },
            { status: 400 }
          );
        }
        const result = await dispatchCreateNote(patient, dictation, getOpenAI(), session);
        return NextResponse.json<ToolResponse>(toToolResponse(result));
      }

      case 'edit_clinical_note': {
        const noteId = typeof args.noteId === 'string' ? args.noteId : '';
        const instructions = typeof args.instructions === 'string' ? args.instructions : '';
        if (!noteId || !instructions.trim()) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'noteId and instructions are required.' },
            { status: 400 }
          );
        }
        const result = await dispatchEditNote(patient, noteId, instructions, getOpenAI(), session);
        return NextResponse.json<ToolResponse>(toToolResponse(result));
      }

      case 'edit_custom_procedure': {
        // Custom procedures are Document rows just like clinical notes —
        // same data-layer fns work for both. Routing is separate so the AI
        // doesn't cross-target between RECENT_NOTES and CUSTOM_PROCEDURES.
        const procedureId = typeof args.procedureId === 'string' ? args.procedureId : '';
        const instructions = typeof args.instructions === 'string' ? args.instructions : '';
        if (!procedureId || !instructions.trim()) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'procedureId and instructions are required.' },
            { status: 400 }
          );
        }
        const result = await dispatchEditNote(patient, procedureId, instructions, getOpenAI(), session);
        return NextResponse.json<ToolResponse>(toToolResponse(result));
      }

      case 'edit_final_report': {
        // Final reports are Document rows like notes/procedures — same
        // dispatcher, separate tool so the model can't cross-route.
        const reportId = typeof args.reportId === 'string' ? args.reportId : '';
        const instructions = typeof args.instructions === 'string' ? args.instructions : '';
        if (!reportId || !instructions.trim()) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'reportId and instructions are required.' },
            { status: 400 }
          );
        }
        const result = await dispatchEditNote(patient, reportId, instructions, getOpenAI(), session);
        return NextResponse.json<ToolResponse>(toToolResponse(result));
      }

      case 'schedule_appointment': {
        const scheduledAt = typeof args.scheduledAt === 'string' ? args.scheduledAt : '';
        const visitType = typeof args.visitType === 'string' ? args.visitType : 'FOLLOW_UP';
        const notes = typeof args.notes === 'string' ? args.notes : null;
        if (!scheduledAt) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'scheduledAt is required.' },
            { status: 400 }
          );
        }
        if (!VALID_VISIT_TYPES.has(visitType)) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: `Invalid visitType: ${visitType}` },
            { status: 400 }
          );
        }
        const result = await dispatchScheduleAppointment(
          patient,
          scheduledAt,
          visitType as 'CONSULTATION' | 'FOLLOW_UP' | 'PROCEDURE',
          notes,
          session
        );
        return NextResponse.json<ToolResponse>(toToolResponse(result));
      }

      case 'summarize_chart': {
        const recentNotes = await listNotesByPatient(patientId, 'CLINICAL_NOTE', session);
        const result = await dispatchSummarize(patient, recentNotes.slice(0, 5), getOpenAI(), session);
        return NextResponse.json<ToolResponse>(toToolResponse(result));
      }

      case 'read_clinical_note':
      case 'read_custom_procedure':
      case 'read_final_report':
      case 'read_patient_file': {
        // Same underlying fetch for all four — differs only in where the
        // model sourced the ID. Tenant guard lives inside dataGetNoteById.
        const id =
          typeof args.noteId === 'string'
            ? args.noteId
            : typeof args.procedureId === 'string'
              ? args.procedureId
              : typeof args.reportId === 'string'
                ? args.reportId
                : typeof args.fileId === 'string'
                  ? args.fileId
                  : '';
        if (!id) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Missing noteId/procedureId/reportId/fileId.' },
            { status: 400 }
          );
        }
        const note = await dataGetNoteById(id, session);
        if (!note || note.patientId !== patientId) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Document not found or not accessible.' },
            { status: 404 }
          );
        }
        // Cap the returned content so a massive uploaded DOC doesn't blow
        // up the model's context or cost — 8000 chars ≈ 2000 tokens,
        // enough for a detailed LOMN letter + plenty of header/footer.
        const MAX_CONTENT = 8000;
        const truncated =
          note.content.length > MAX_CONTENT
            ? note.content.slice(0, MAX_CONTENT) + '\n\n[content truncated — full document available via the chart UI]'
            : note.content;
        await logAudit({
          action: 'VIEWED_DOCUMENT',
          targetId: id,
          targetType: 'Document',
          metadata: { via: 'assistant', patientId },
        });
        // File-only rows (images without extracted text) have no content.
        // Return the metadata so the model can describe the file instead
        // of reporting an empty document.
        if (!note.content.trim() && note.fileName) {
          const size = note.sizeBytes ? `${Math.round(note.sizeBytes / 1024)} KB` : 'unknown size';
          return NextResponse.json<ToolResponse>({
            ok: true,
            output: `File "${note.fileName}" (${note.mimeType ?? 'unknown type'}, ${size}). No extracted text — this is an image or non-text upload.`,
          });
        }
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: `Document "${note.title}" content:\n\n${truncated}`,
        });
      }

      case 'delete_clinical_note': {
        const noteId = typeof args.noteId === 'string' ? args.noteId : '';
        if (!noteId) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'noteId is required.' },
            { status: 400 }
          );
        }
        const ok = await dataDeleteClinicalNote(noteId, session);
        if (!ok) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Note not found or not accessible.' },
            { status: 404 }
          );
        }
        await logAudit({
          action: 'DELETED_DOCUMENT',
          targetId: noteId,
          targetType: 'Document',
          metadata: { via: 'assistant', patientId, category: 'CLINICAL_NOTE' },
        });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: 'Clinical note deleted.',
        });
      }

      case 'delete_custom_procedure': {
        const procedureId = typeof args.procedureId === 'string' ? args.procedureId : '';
        if (!procedureId) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'procedureId is required.' },
            { status: 400 }
          );
        }
        const ok = await dataDeleteClinicalNote(procedureId, session);
        if (!ok) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Procedure not found or not accessible.' },
            { status: 404 }
          );
        }
        await logAudit({
          action: 'DELETED_DOCUMENT',
          targetId: procedureId,
          targetType: 'Document',
          metadata: { via: 'assistant', patientId, category: 'CUSTOM_PROCEDURE' },
        });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: 'Custom procedure deleted.',
        });
      }

      case 'delete_final_report': {
        const reportId = typeof args.reportId === 'string' ? args.reportId : '';
        if (!reportId) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'reportId is required.' },
            { status: 400 }
          );
        }
        const ok = await dataDeleteClinicalNote(reportId, session);
        if (!ok) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Final report not found or not accessible.' },
            { status: 404 }
          );
        }
        await logAudit({
          action: 'DELETED_DOCUMENT',
          targetId: reportId,
          targetType: 'Document',
          metadata: { via: 'assistant', patientId, category: 'FINAL_REPORT' },
        });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: 'Final report deleted.',
        });
      }

      case 'delete_patient_file': {
        const fileId = typeof args.fileId === 'string' ? args.fileId : '';
        if (!fileId) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'fileId is required.' },
            { status: 400 }
          );
        }
        const ok = await dataDeleteClinicalNote(fileId, session);
        if (!ok) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'File not found or not accessible.' },
            { status: 404 }
          );
        }
        await logAudit({
          action: 'DELETED_DOCUMENT',
          targetId: fileId,
          targetType: 'Document',
          metadata: { via: 'assistant', patientId, category: 'PATIENT_FILE' },
        });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: 'File deleted.',
        });
      }

      case 'cancel_appointment': {
        const appointmentId = typeof args.appointmentId === 'string' ? args.appointmentId : '';
        if (!appointmentId) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'appointmentId is required.' },
            { status: 400 }
          );
        }
        const ok = await dataDeleteAppointment(appointmentId, session);
        if (!ok) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Appointment not found or not accessible.' },
            { status: 404 }
          );
        }
        await logAudit({
          action: 'DELETED_APPOINTMENT',
          targetId: appointmentId,
          targetType: 'Appointment',
          metadata: { via: 'assistant', patientId },
        });
        revalidatePath(`/dashboard/patients/${patientId}`);
        revalidatePath('/dashboard/schedule');
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: 'Appointment cancelled.',
        });
      }

      case 'archive_patient': {
        const ok = await dataArchivePatient(patientId, session);
        if (!ok) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Could not archive patient.' },
            { status: 500 }
          );
        }
        await logAudit({
          action: 'ARCHIVED_PATIENT',
          targetId: patientId,
          targetType: 'Patient',
          metadata: { via: 'assistant' },
        });
        revalidatePath(`/dashboard/patients/${patientId}`);
        revalidatePath('/dashboard/patients');
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: 'Patient archived.',
        });
      }

      case 'request_file_upload': {
        // No DB side effect — just a UI signal. The panel sees the
        // awaiting_file_upload action and opens the file picker. The
        // actual upload uses the existing audited uploadCustomProcedureAction
        // path. The model gets a synthetic user message after the upload
        // completes (or fails) so it can confirm aloud.
        const reason = typeof args.reason === 'string' ? args.reason : 'a procedure document';
        return NextResponse.json<ToolResponse>({
          ok: true,
          output:
            'File picker opened. Tell the user to pick the file they want to attach. Wait for the upload confirmation message before responding further.',
          action: { type: 'awaiting_file_upload', reason },
        });
      }

      case 'update_patient': {
        // Whitelist + type-check each field. Anything the model sends that
        // isn't recognized is dropped silently — the tool schema declares
        // additionalProperties: false so this is mostly defensive.
        const updates: UpdatePatientFromAssistant = {};
        if (typeof args.firstName === 'string') updates.firstName = args.firstName;
        if (typeof args.lastName === 'string') updates.lastName = args.lastName;
        if (typeof args.mrn === 'string') updates.mrn = args.mrn;
        if (typeof args.chartId === 'string') updates.chartId = args.chartId;
        if (typeof args.birthYear === 'number') updates.birthYear = Math.trunc(args.birthYear);
        if (typeof args.email === 'string') updates.email = args.email;
        if (typeof args.cellPhone === 'string') updates.cellPhone = args.cellPhone;
        if (typeof args.homePhone === 'string') updates.homePhone = args.homePhone;
        if (typeof args.insuranceVerified === 'boolean') updates.insuranceVerified = args.insuranceVerified;
        if (Array.isArray(args.tags) && args.tags.every((t) => typeof t === 'string')) {
          updates.tags = args.tags as string[];
        }
        if (
          typeof args.status === 'string' &&
          (args.status === 'ACTIVE' || args.status === 'INACTIVE' || args.status === 'ARCHIVED')
        ) {
          updates.status = args.status;
        }
        if (Array.isArray(args.briefHistory) && args.briefHistory.every((b) => typeof b === 'string')) {
          updates.briefHistory = args.briefHistory as string[];
        }
        if (
          typeof args.sex === 'string' &&
          (args.sex === 'UNKNOWN' ||
            args.sex === 'MALE' ||
            args.sex === 'FEMALE' ||
            args.sex === 'OTHER')
        ) {
          updates.sex = args.sex;
        }
        if (typeof args.addressLine1 === 'string') updates.addressLine1 = args.addressLine1;
        if (typeof args.addressLine2 === 'string') updates.addressLine2 = args.addressLine2;
        if (typeof args.city === 'string') updates.city = args.city;
        if (typeof args.state === 'string') {
          // US 2-char upper to match what the DB stores + the form
          // normalizes to. Keeps voice edits consistent with typed edits.
          updates.state = args.state.replace(/[^A-Za-z]/g, '').slice(0, 2).toUpperCase();
        }
        if (typeof args.postalCode === 'string') updates.postalCode = args.postalCode;
        if (typeof args.pharmacyName === 'string') updates.pharmacyName = args.pharmacyName;
        if (typeof args.pharmacyPhone === 'string') updates.pharmacyPhone = args.pharmacyPhone;
        if (typeof args.assignedDoctorId === 'string') {
          // dispatchUpdatePatient → dataUpdatePatient enforces tenant
          // scope on the patient, but the target user has to be
          // validated separately. Do the same check the Add Patient
          // server action does.
          updates.assignedDoctorId = args.assignedDoctorId;
        }
        const result = await dispatchUpdatePatient(patient, updates, session);
        return NextResponse.json<ToolResponse>(toToolResponse(result));
      }

      case 'generate_final_report': {
        const result = await dispatchGenerateFinalReport(patientId);
        return NextResponse.json<ToolResponse>(toToolResponse(result));
      }

      case 'generate_document': {
        const documentType = typeof args.documentType === 'string' ? args.documentType : '';
        if (!VALID_DOC_TYPES.has(documentType)) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: `Invalid documentType: ${documentType}` },
            { status: 400 }
          );
        }
        const result = await dispatchGenerateDocument(
          patientId,
          documentType as DocumentType
        );
        return NextResponse.json<ToolResponse>(toToolResponse(result));
      }

      // === CLINICAL SAFETY: allergies + medications ===

      case 'add_allergy': {
        const allergen = typeof args.allergen === 'string' ? args.allergen.trim() : '';
        if (!allergen) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Allergen name is required.' },
            { status: 400 }
          );
        }
        const severity = typeof args.severity === 'string' && ['UNKNOWN', 'MILD', 'MODERATE', 'SEVERE'].includes(args.severity)
          ? (args.severity as 'UNKNOWN' | 'MILD' | 'MODERATE' | 'SEVERE')
          : 'UNKNOWN';
        const reaction = typeof args.reaction === 'string' ? args.reaction.trim() || null : null;
        const allergy = await createAllergy(session, {
          patientId,
          allergen,
          reaction,
          severity,
        });
        await logAudit({ action: 'CREATED_ALLERGY', targetId: allergy.id, targetType: 'Allergy' });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: `Added allergy: ${allergen}${severity !== 'UNKNOWN' ? ` [${severity}]` : ''}.`,
          action: { type: 'clinical_safety_updated' },
        });
      }

      case 'remove_allergy': {
        const allergyId = typeof args.allergyId === 'string' ? args.allergyId.trim() : '';
        if (!allergyId) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'allergyId is required.' },
            { status: 400 }
          );
        }
        await deleteAllergy(session, allergyId);
        await logAudit({ action: 'DELETED_ALLERGY', targetId: allergyId, targetType: 'Allergy' });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: 'Allergy removed.',
          action: { type: 'clinical_safety_updated' },
        });
      }

      case 'set_nka': {
        const value = typeof args.value === 'boolean' ? args.value : true;
        await setNoKnownAllergies(session, patientId, value);
        await logAudit({ action: 'UPDATED_PATIENT', targetId: patientId, targetType: 'Patient', metadata: { field: 'noKnownAllergies', value } });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: value ? 'Marked No Known Allergies.' : 'NKA flag cleared.',
          action: { type: 'clinical_safety_updated' },
        });
      }

      case 'add_medication': {
        const name = typeof args.name === 'string' ? args.name.trim() : '';
        if (!name) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Medication name is required.' },
            { status: 400 }
          );
        }
        const dosage = typeof args.dosage === 'string' ? args.dosage.trim() || null : null;
        const frequency = typeof args.frequency === 'string' ? args.frequency.trim() || null : null;
        const med = await createMedication(session, { patientId, name, dosage, frequency });
        await logAudit({ action: 'CREATED_MEDICATION', targetId: med.id, targetType: 'Medication' });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: `Added medication: ${name}${dosage ? ` ${dosage}` : ''}${frequency ? ` ${frequency}` : ''}.`,
          action: { type: 'clinical_safety_updated' },
        });
      }

      case 'remove_medication': {
        const medicationId = typeof args.medicationId === 'string' ? args.medicationId.trim() : '';
        if (!medicationId) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'medicationId is required.' },
            { status: 400 }
          );
        }
        await deleteMedication(session, medicationId);
        await logAudit({ action: 'DELETED_MEDICATION', targetId: medicationId, targetType: 'Medication' });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: 'Medication removed.',
          action: { type: 'clinical_safety_updated' },
        });
      }

      case 'toggle_medication_active': {
        const medicationId = typeof args.medicationId === 'string' ? args.medicationId.trim() : '';
        if (!medicationId) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'medicationId is required.' },
            { status: 400 }
          );
        }
        // Read current state, flip it. The model uses this for both
        // "stop the gabapentin" (active→inactive) and "resume the
        // gabapentin" (inactive→active).
        const { default: prisma } = await import('@meddoc/db');
        const existingMed = await prisma.medication.findFirst({
          where: {
            id: medicationId,
            deletedAt: null,
            patient: patientAccessWhere(session),
          },
          select: { isActive: true },
        });
        if (!existingMed) {
          return NextResponse.json<ToolResponse>(
            { ok: false, output: 'Medication not found.' },
            { status: 404 }
          );
        }
        const newActive = !existingMed.isActive;
        await updateMedication(session, medicationId, { isActive: newActive });
        await logAudit({ action: 'UPDATED_MEDICATION', targetId: medicationId, targetType: 'Medication', metadata: { isActive: newActive } });
        revalidatePath(`/dashboard/patients/${patientId}`);
        return NextResponse.json<ToolResponse>({
          ok: true,
          output: newActive ? 'Medication resumed.' : 'Medication stopped.',
          action: { type: 'clinical_safety_updated' },
        });
      }

      default:
        return NextResponse.json<ToolResponse>(
          { ok: false, output: `Unknown tool: ${toolName}` },
          { status: 400 }
        );
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Tool execution failed';
    console.error('[assistant-tool] dispatch error:', err);
    return NextResponse.json<ToolResponse>(
      { ok: false, output: message },
      { status: 500 }
    );
  }
}

// AssistantResult → ToolResponse adapter. The dispatchers' `reply` becomes
// the model-facing output string; the action surfaces for UI rendering.
function toToolResponse(result: AssistantResult): ToolResponse {
  if (!result.ok) {
    return { ok: false, output: result.error };
  }
  return { ok: true, output: result.reply, action: result.action };
}
