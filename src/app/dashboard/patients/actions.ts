'use server';

// ============================================================================
// Patient Server Actions
// ----------------------------------------------------------------------------
// Every action:
//  1. Authorizes via requireRole()
//  2. Validates input via Zod
//  3. Performs the DB mutation through the data layer
//  4. Writes an audit log entry (HIPAA §164.312(b))
//  5. Revalidates affected paths so the UI re-fetches
//
// All actions return a discriminated union { ok: true, data } | { ok: false, error }
// so the client can render success/error states without try/catch.
// ============================================================================

import { revalidatePath } from 'next/cache';
import { z } from 'zod';
import OpenAI from 'openai';

import { requireRole, AuthError } from '@/lib/auth';
import prisma, { isDatabaseHealthy } from '@/lib/db';
import { logAudit } from '@/lib/audit';
import { logApiUsage } from '@/lib/usage';
import {
  createPatient as dataCreatePatient,
  updatePatient as dataUpdatePatient,
  archivePatient as dataArchivePatient,
  getNextChartId,
  getPatientById,
} from '@/lib/data/patients';
import type { PatientView } from '@/lib/data/patients';
import {
  createClinicalNote as dataCreateClinicalNote,
  getNoteById as dataGetNoteById,
  listNotesByPatient as dataListNotesByPatient,
  updateClinicalNote as dataUpdateClinicalNote,
  deleteClinicalNote as dataDeleteClinicalNote,
  createPatientFile as dataCreatePatientFile,
  createFinalReport as dataCreateFinalReport,
  type ClinicalNoteView,
} from '@/lib/data/clinical-notes';
import { PROCEDURE_TEMPLATES } from '@/lib/constants/procedure-templates';
import {
  createAppointment,
  type AppointmentView,
} from '@/lib/data/appointments';
import {
  listAllergiesForPatient as dataListAllergies,
  createAllergy as dataCreateAllergy,
  updateAllergy as dataUpdateAllergy,
  deleteAllergy as dataDeleteAllergy,
  setNoKnownAllergies as dataSetNoKnownAllergies,
  listMedicationsForPatient as dataListMedications,
  createMedication as dataCreateMedication,
  updateMedication as dataUpdateMedication,
  deleteMedication as dataDeleteMedication,
  type AllergyView,
  type MedicationView,
} from '@/lib/data/clinical-safety';
import { editClinicalNoteTwoPass } from '@/lib/ai-service';

// ---------------------------------------------------------------------------
// Validation schemas
// ---------------------------------------------------------------------------

// Only firstName + lastName are required. Everything else is optional —
// intake should be "type two names and go," with richer metadata filled
// in later as the clinic has time.
const createPatientSchema = z.object({
  firstName: z.string().min(1, 'First name is required').max(100),
  lastName: z.string().min(1, 'Last name is required').max(100),
  drChronoId: z
    .string()
    .max(50)
    .regex(/^[A-Za-z0-9-_]+$/, 'DrChrono ID must be alphanumeric')
    .optional()
    .nullable()
    .or(z.literal('')),
  mrn: z.string().max(50).optional().nullable().or(z.literal('')),
  chartId: z.string().max(50).optional().nullable().or(z.literal('')),
  birthYear: z
    .number()
    .int()
    .min(1900)
    .max(new Date().getFullYear())
    .optional()
    .nullable(),
  email: z.string().email('Invalid email').optional().nullable().or(z.literal('')),
  phoneLast4: z
    .string()
    .regex(/^\d{4}$/, 'Phone last 4 must be exactly 4 digits')
    .optional()
    .nullable()
    .or(z.literal('')),
  // Full phones — free-format strings. Loose regex: allow digits, spaces,
  // parens, dashes, plus. Length capped so we don't store nonsense.
  cellPhone: z
    .string()
    .max(32)
    .regex(/^[0-9 ()+\-.]*$/, 'Cell phone contains invalid characters')
    .optional()
    .nullable()
    .or(z.literal('')),
  homePhone: z
    .string()
    .max(32)
    .regex(/^[0-9 ()+\-.]*$/, 'Home phone contains invalid characters')
    .optional()
    .nullable()
    .or(z.literal('')),
  insuranceVerified: z.boolean().optional().nullable(),
  sex: z.enum(['UNKNOWN', 'MALE', 'FEMALE', 'OTHER']).optional().nullable(),
  addressLine1: z.string().max(200).optional().nullable().or(z.literal('')),
  addressLine2: z.string().max(200).optional().nullable().or(z.literal('')),
  city: z.string().max(100).optional().nullable().or(z.literal('')),
  // US 2-char state code. Loose — upper/lower OK; normalized on save.
  state: z
    .string()
    .max(2)
    .regex(/^[A-Za-z]{0,2}$/, 'State must be a 2-letter code')
    .optional()
    .nullable()
    .or(z.literal('')),
  postalCode: z
    .string()
    .max(10)
    .regex(/^[A-Za-z0-9 \-]*$/, 'Postal code contains invalid characters')
    .optional()
    .nullable()
    .or(z.literal('')),
  pharmacyName: z.string().max(150).optional().nullable().or(z.literal('')),
  pharmacyPhone: z
    .string()
    .max(32)
    .regex(/^[0-9 ()+\-.]*$/, 'Pharmacy phone contains invalid characters')
    .optional()
    .nullable()
    .or(z.literal('')),
  tags: z.array(z.string()).optional(),
  briefHistory: z.array(z.string().min(1).max(500)).optional(),
  // Must match a doctor in the creator's practice; enforced at handler
  // level. Loose format here — the cross-practice check is the real gate.
  assignedDoctorId: z.string().min(1).max(50).optional().nullable().or(z.literal('')),
});

const updatePatientSchema = createPatientSchema.partial().extend({
  status: z.enum(['ACTIVE', 'INACTIVE', 'ARCHIVED']).optional(),
});

// ---------------------------------------------------------------------------
// Action result types
// ---------------------------------------------------------------------------

export type ActionResult<T = unknown> =
  | { ok: true; data: T }
  | { ok: false; error: string; fieldErrors?: Record<string, string[]> };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function authErrorResult<T>(err: unknown): ActionResult<T> {
  if (err instanceof AuthError) {
    return { ok: false, error: err.message };
  }
  return { ok: false, error: 'An unexpected error occurred' };
}

// ---------------------------------------------------------------------------
// CREATE
// ---------------------------------------------------------------------------

export async function createPatientAction(
  rawInput: unknown
): Promise<ActionResult<PatientView>> {
  // 1. AuthZ — only DOCTOR or ADMIN can create patients
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'CREATED_PATIENT',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    return authErrorResult(err);
  }

  // 2. Validate
  const parsed = createPatientSchema.safeParse(rawInput);
  if (!parsed.success) {
    return {
      ok: false,
      error: 'Invalid input',
      fieldErrors: parsed.error.flatten().fieldErrors,
    };
  }

  const data = parsed.data;
  // Normalize empty strings to null so the DB stores them uniformly.
  const cleanData = {
    ...data,
    drChronoId: data.drChronoId || null,
    mrn: data.mrn || null,
    chartId: data.chartId || null,
    email: data.email || null,
    phoneLast4: data.phoneLast4 || null,
    cellPhone: data.cellPhone || null,
    homePhone: data.homePhone || null,
    birthYear: data.birthYear ?? null,
    insuranceVerified: data.insuranceVerified ?? null,
    sex: data.sex ?? null,
    addressLine1: data.addressLine1 || null,
    addressLine2: data.addressLine2 || null,
    city: data.city || null,
    state: data.state ? data.state.toUpperCase() : null,
    postalCode: data.postalCode || null,
    pharmacyName: data.pharmacyName || null,
    pharmacyPhone: data.pharmacyPhone || null,
    assignedDoctorId: data.assignedDoctorId || null,
    briefHistory: data.briefHistory ?? [],
  };

  // Tenant guard for assignedDoctorId — must be a DOCTOR in the creator's
  // practice. Prevents the client from passing an arbitrary user ID.
  if (cleanData.assignedDoctorId) {
    const doctor = await prisma.user.findFirst({
      where: {
        id: cleanData.assignedDoctorId,
        practiceId: session.user.practiceId,
        role: 'DOCTOR',
      },
      select: { id: true },
    });
    if (!doctor) {
      return {
        ok: false,
        error: 'Selected doctor is not valid for this practice.',
        fieldErrors: { assignedDoctorId: ['Invalid doctor'] },
      };
    }
  }

  // 3. Create via data layer — patient is tagged with the creator's
  //    practice so it's visible only within that tenant.
  try {
    const patient = await dataCreatePatient(
      cleanData,
      session.user.id,
      session.user.practiceId
    );

    // 4. Audit log — note: only field NAMES, never values
    await logAudit({
      action: 'CREATED_PATIENT',
      targetId: patient.id,
      targetType: 'Patient',
      metadata: {
        fieldsProvided: Object.keys(cleanData).filter(
          (k) => cleanData[k as keyof typeof cleanData] != null
        ),
      },
    });

    // 5. Revalidate the list page
    revalidatePath('/dashboard/patients');

    return { ok: true, data: patient };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to create patient';
    await logAudit({
      action: 'CREATED_PATIENT',
      success: false,
      errorCode: 'CREATE_FAILED',
      metadata: { reason: message },
    });
    return { ok: false, error: message };
  }
}

// ---------------------------------------------------------------------------
// UPDATE
// ---------------------------------------------------------------------------

export async function updatePatientAction(
  patientId: string,
  rawInput: unknown
): Promise<ActionResult<PatientView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'UPDATED_PATIENT',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    return authErrorResult(err);
  }
  const parsed = updatePatientSchema.safeParse(rawInput);
  if (!parsed.success) {
    return {
      ok: false,
      error: 'Invalid input',
      fieldErrors: parsed.error.flatten().fieldErrors,
    };
  }

  try {
    const result = await dataUpdatePatient(patientId, parsed.data, session);
    if (!result) {
      return { ok: false, error: 'Patient not found' };
    }

    await logAudit({
      action: 'UPDATED_PATIENT',
      targetId: patientId,
      targetType: 'Patient',
      metadata: { changedFields: result.changedFields },
    });

    revalidatePath('/dashboard/patients');
    revalidatePath(`/dashboard/patients/${patientId}`);

    return { ok: true, data: result.patient };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to update patient';
    await logAudit({
      action: 'UPDATED_PATIENT',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'UPDATE_FAILED',
      metadata: { reason: message },
    });
    return { ok: false, error: message };
  }
}

// ---------------------------------------------------------------------------
// NEXT CHART ID (auto-generation preview for the AddPatient modal)
// ---------------------------------------------------------------------------
// Returns the next available `C-<n>` for the current session's practice
// so the Add Patient modal can prefill its Chart ID placeholder. The
// authoritative generator lives in the data layer and runs again at
// insert time (so two concurrent modal-opens don't both stick with the
// same suggestion).
// ---------------------------------------------------------------------------
export async function getNextChartIdAction(): Promise<ActionResult<{ chartId: string }>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    return authErrorResult(err);
  }
  const chartId = await getNextChartId(session.user.practiceId);
  return { ok: true, data: { chartId } };
}

// ---------------------------------------------------------------------------
// LIST DOCTORS (for assignment dropdown)
// ---------------------------------------------------------------------------
// Returns active DOCTOR users in the caller's practice. Used by the Add /
// Edit Patient modals to pick an assigned provider. Tenant-scoped; no
// SUPER_ADMIN cross-practice listing here — that's not a workflow need.
// Gracefully returns an empty list if the DB is unhealthy so the modal
// still opens with a "no doctors available" state.

export interface DoctorOption {
  id: string;
  name: string | null;
  email: string;
}

export async function listPracticeDoctorsAction(): Promise<ActionResult<DoctorOption[]>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    return authErrorResult(err);
  }
  if (!(await isDatabaseHealthy())) {
    return { ok: true, data: [] };
  }
  try {
    const rows = await prisma.user.findMany({
      where: {
        practiceId: session.user.practiceId,
        role: 'DOCTOR',
        isActive: true,
      },
      select: { id: true, name: true, email: true },
      orderBy: [{ name: 'asc' }, { email: 'asc' }],
    });
    return { ok: true, data: rows };
  } catch (err) {
    console.warn('[patients/actions] listPracticeDoctors failed:', err);
    return { ok: true, data: [] };
  }
}

// ---------------------------------------------------------------------------
// ARCHIVE (soft delete)
// ---------------------------------------------------------------------------

export async function archivePatientAction(
  patientId: string
): Promise<ActionResult<{ archived: boolean }>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'ARCHIVED_PATIENT',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    return authErrorResult(err);
  }

  try {
    const archived = await dataArchivePatient(patientId, session);
    if (!archived) {
      return { ok: false, error: 'Patient not found' };
    }

    await logAudit({
      action: 'ARCHIVED_PATIENT',
      targetId: patientId,
      targetType: 'Patient',
    });

    revalidatePath('/dashboard/patients');
    revalidatePath(`/dashboard/patients/${patientId}`);

    return { ok: true, data: { archived: true } };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to archive patient';
    return { ok: false, error: message };
  }
}

// ===========================================================================
// GENERATE CLINICAL NOTE — Whisper → GPT-4o-mini → DB
// ---------------------------------------------------------------------------
// Two-stage AI pipeline:
//   1. Whisper-1 transcribes the raw audio from the dictation widget
//   2. gpt-4o-mini rewrites the transcript into a structured SOAP note
//
// We use the server-side `OPENAI_API_KEY` (NOT NEXT_PUBLIC_*) — exposing an
// API key to the browser would let anyone burn the quota, so the key lives
// only in the server environment and this action runs exclusively on the
// server because of the `'use server'` directive at the top of this file.
// ===========================================================================

let _openaiClient: OpenAI | null = null;
function getOpenAI(): OpenAI {
  if (!_openaiClient) {
    const apiKey = process.env.OPENAI_API_KEY;
    if (!apiKey?.trim()) {
      throw new Error('OPENAI_API_KEY is not configured in .env.local');
    }
    _openaiClient = new OpenAI({ apiKey });
  }
  return _openaiClient;
}

// Fire-and-forget usage log for per-tool GPT-4o-mini calls. Call this
// right after openai.chat.completions.create() — every completion has a
// `usage.total_tokens` we can record. Priced as GPT_TOOL in the metrics
// dashboard. Without this, the per-tool GPT spend (SOAP format, edit
// rewrite, summary, doc draft, router) is invisible to admins.
function logGptToolUsage(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  completion: any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  session: any
): void {
  const tokens = completion?.usage?.total_tokens;
  if (typeof tokens !== 'number' || tokens <= 0) return;
  if (!session?.user?.id || !session?.user?.practiceId) return;
  void logApiUsage({
    feature: 'GPT_TOOL',
    userId: session.user.id,
    practiceId: session.user.practiceId,
    tokens,
  }).catch((err) => {
    console.error('[actions] logGptToolUsage rejected:', err);
  });
}

const SOAP_SYSTEM_PROMPT = `You are a medical scribe AI for a pain management physician. Your job is to clean up a doctor's raw dictation into a polished clinical note ready to chart. You preserve the doctor's intent and structure — you do NOT impose a template.

GUIDELINES:
1. If the dictation is a single coherent thought or short paragraph, return it as a clean paragraph — fix grammar, tighten phrasing, normalize medical terminology, but PRESERVE the natural flow. Do not add headings or sections that aren't in the original.
2. If (and only if) the dictation contains multiple distinct clinical domains (e.g., subjective complaints AND objective exam findings AND a treatment plan), you MAY use SUBJECTIVE / OBJECTIVE / ASSESSMENT / PLAN headings to organize. Include ONLY the sections the doctor actually addressed.
3. NEVER add placeholder text like "Not documented", "[None reported]", "Pending", etc. for sections the doctor did not mention. Omit the section entirely. A blank note is a blank note.
4. Use only information the doctor dictated. Never invent findings, medications, history, or "common follow-up" content.
5. Preserve medical terminology exactly as dictated (LESI, CESI, PRP, LFB, L4-L5, radiculopathy, etc.).
6. Plain text only — no markdown, no code fences, no bullet symbols unless the doctor used them.
7. Start directly with the note content — no preamble, no "Here is the note:", no commentary.`;

// ---------------------------------------------------------------------------
// Tiny helpers — keep heuristics simple and deterministic
// ---------------------------------------------------------------------------

/**
 * Derive a short title from the note. Notes may now be free-form prose
 * (after the SOAP-prompt softening) or sectioned with SUBJECTIVE/OBJECTIVE
 * headings — handle both.
 */
function buildNoteTitle(note: string): string {
  // If it's a sectioned note, grab the first sentence of SUBJECTIVE.
  const sectioned = note.match(/SUBJECTIVE:\s*([^\n.]+)/i);
  if (sectioned?.[1]?.trim()) {
    const raw = sectioned[1].trim();
    return raw.length > 60 ? raw.slice(0, 57) + '...' : raw;
  }
  // Free-form prose: take the first sentence (or first line, whichever
  // is shorter), capped at ~60 chars. Fall back to "Clinical Note" only
  // if the note is genuinely empty.
  const firstLine = note.trim().split(/\n/).find((l) => l.trim()) ?? '';
  const firstSentence = firstLine.split(/(?<=[.!?])\s/)[0]?.trim() ?? '';
  const raw = firstSentence || firstLine || 'Clinical Note';
  return raw.length > 60 ? raw.slice(0, 57) + '...' : raw;
}

/** Guess procedure type from keywords in the raw dictation. */
function inferProcedureType(transcript: string): string | null {
  const t = transcript.toLowerCase();
  if (/\blesi\b|lumbar epidural/.test(t)) return 'LESI';
  if (/\bcesi\b|cervical epidural/.test(t)) return 'CESI';
  if (/\blfb\b|facet block/.test(t)) return 'LFB';
  if (/\bprp\b|platelet.?rich/.test(t)) return 'PRP';
  if (/consult|evaluation|intake/.test(t)) return 'Consult';
  if (/follow.?up/.test(t)) return 'Follow-up';
  return null;
}

// ===========================================================================
// GENERATE DRAFT DOCUMENT — from clinical notes context
// ---------------------------------------------------------------------------
// Fetches the most recent 1-2 clinical notes for a patient, passes them to
// GPT-4o-mini with a document-type-specific system prompt, and returns the
// generated text for the doctor to review/edit. Does NOT persist anything —
// that happens only after the doctor approves.
// ===========================================================================

export type DocumentType = 'REFERRAL_LETTER' | 'PATIENT_HANDOUT' | 'DISABILITY_FORM' | 'PRIOR_AUTH';

export interface GeneratedDocument {
  documentType: DocumentType;
  title: string;
  content: string;
  sourceNoteCount: number;
}

const DOCUMENT_PROMPTS: Record<DocumentType, { title: string; systemPrompt: string }> = {
  REFERRAL_LETTER: {
    title: 'Referral Letter',
    systemPrompt: `You are a medical secretary AI for a pain management physician. Draft a formal referral letter based on the clinical notes provided.

FORMAT — produce the letter exactly like this (no markdown, no code fences):

[Date: today's date]

RE: [Patient Name] — Referral for [Specialty/Evaluation]

Dear Colleague,

[Body: 2-3 paragraphs summarizing the clinical situation, relevant history, current treatment, reason for referral, and what you are requesting from the specialist. Use professional medical language. Reference specific findings from the clinical notes.]

Thank you for your time and expertise. Please do not hesitate to contact our office should you require additional information.

Respectfully,
[Referring Physician Name]
[Practice Name / Contact]

RULES:
1. Use ONLY information from the clinical notes. Never invent diagnoses, medications, or findings.
2. Write in professional, formal medical correspondence style.
3. If information is missing, leave a bracket placeholder like [SPECIALIST NAME] or [SPECIFIC REQUEST].
4. Keep the letter concise — 1 page maximum.
5. Start directly with the date line — no preamble.`,
  },

  PATIENT_HANDOUT: {
    title: 'Patient Instructions',
    systemPrompt: `You are a patient education AI for a pain management clinic. Create clear, plain-language patient instructions based on the clinical notes provided.

FORMAT — produce the handout exactly like this (no markdown, no code fences):

PATIENT INSTRUCTIONS
[Procedure/Visit Type]

WHAT WAS DONE:
[1-2 sentences in plain language about the procedure or visit]

AFTER YOUR VISIT:
- [Bullet points of post-procedure care instructions]
- [Activity restrictions]
- [Medication instructions]

WATCH FOR THESE WARNING SIGNS:
- [Red flag symptoms that require immediate medical attention]

FOLLOW-UP:
[When to schedule next appointment, expected timeline for improvement]

CONTACT US:
If you have questions or concerns, call our office at [PHONE NUMBER].

RULES:
1. Write at a 6th-grade reading level — no medical jargon without explanation.
2. Use ONLY information from the clinical notes.
3. Be specific about what procedure was done.
4. If you cannot determine certain details, use bracket placeholders.
5. Keep it to 1 page. Start directly with the title — no preamble.`,
  },

  DISABILITY_FORM: {
    title: 'Disability Statement',
    systemPrompt: `You are a medical documentation AI for a pain management physician. Draft a disability/functional limitations statement based on the clinical notes provided.

FORMAT — produce the statement exactly like this (no markdown, no code fences):

MEDICAL STATEMENT OF DISABILITY / FUNCTIONAL LIMITATIONS

Patient: [Name]
Date: [Today's date]
Treating Physician: [Physician Name]

DIAGNOSIS:
[List diagnoses with ICD-10 codes if mentioned in notes]

CURRENT TREATMENT:
[Summary of current treatment plan from notes]

FUNCTIONAL LIMITATIONS:
[Specific limitations based on clinical findings — lifting restrictions, sitting/standing tolerance, etc. Be specific with quantities where the notes support it.]

PROGNOSIS:
[Expected duration of limitations, anticipated recovery timeline]

PHYSICIAN ATTESTATION:
I attest that the above information is accurate and based on my clinical examination and treatment of this patient.

Signature: ________________________
[Physician Name], [Credentials]
Date: [Today's date]

RULES:
1. Use ONLY information from the clinical notes. Never fabricate findings or limitations.
2. Be specific and quantifiable where the notes support it (e.g., "cannot lift more than 10 lbs" not just "limited lifting").
3. Use bracket placeholders for anything not in the notes.
4. Write in formal medical-legal style. Start directly — no preamble.`,
  },

  PRIOR_AUTH: {
    title: 'Prior Authorization Letter',
    systemPrompt: `You are a medical documentation AI for a pain management physician. Draft a prior authorization / medical necessity letter based on the clinical notes provided.

FORMAT — produce the letter exactly like this (no markdown, no code fences):

LETTER OF MEDICAL NECESSITY

Date: [Today's date]
Patient: [Name]
Insurance: [INSURANCE COMPANY]
Member ID: [MEMBER ID]

RE: Prior Authorization Request for [Procedure/Treatment]

To Whom It May Concern:

[Opening paragraph: I am writing to request prior authorization for the above-named procedure for my patient.]

CLINICAL HISTORY:
[Summary from clinical notes — chief complaint, duration of symptoms, prior treatments tried and failed]

CURRENT CLINICAL FINDINGS:
[Relevant exam findings, imaging results from notes]

MEDICAL NECESSITY:
[Why this treatment is necessary — failed conservative measures, clinical indications, evidence-based guidelines supporting this treatment]

REQUESTED PROCEDURE:
[Specific procedure with CPT codes if inferable, frequency, duration]

Thank you for your prompt review of this request. Please contact our office for additional information.

Respectfully,
[Physician Name]
[NPI / Practice Info]

RULES:
1. Use ONLY information from the clinical notes. Never fabricate clinical findings.
2. Emphasize failed conservative treatments and medical necessity.
3. Reference evidence-based guidelines where appropriate.
4. Use bracket placeholders for insurance details and any missing info.
5. Write in a persuasive but factual medical-legal style. Start directly — no preamble.`,
  },
};

export async function generateDocumentAction(
  patientId: string,
  documentType: DocumentType
): Promise<ActionResult<GeneratedDocument>> {
  // 1. Authorization
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'GENERATED_DRAFT_DOCUMENT',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    return authErrorResult(err);
  }

  // 2. Validate document type
  const docConfig = DOCUMENT_PROMPTS[documentType];
  if (!docConfig) {
    return { ok: false, error: 'Unknown document type.' };
  }

  // 3. Fetch patient + recent clinical notes for context
  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return { ok: false, error: 'Patient not found.' };
  }

  const { listNotesByPatient } = await import('@/lib/data/clinical-notes');
  const notes = await listNotesByPatient(patientId, undefined, session);
  const recentNotes = notes.slice(0, 2); // newest 2

  if (recentNotes.length === 0) {
    return {
      ok: false,
      error: 'No clinical notes found for this patient. Dictate a note first, then generate a document.',
    };
  }

  // 4. Build context string from notes (content only — no raw PHI goes to audit)
  const notesContext = recentNotes
    .map(
      (n, i) =>
        `--- Clinical Note ${i + 1} (${n.procedureType ?? 'General'}, ${n.createdAt.split('T')[0]}) ---\n${n.content}`
    )
    .join('\n\n');

  const age = new Date().getFullYear() - patient.birthYear;

  // 5. Call GPT-4o-mini
  const openai = getOpenAI();
  let generatedText: string;

  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0.3,
      max_tokens: 2000,
      messages: [
        { role: 'system', content: docConfig.systemPrompt },
        {
          role: 'user',
          content: `Patient: ${patient.firstName} ${patient.lastName} (age ${age})\nPhysician: Dr. Bakhtiar Moussazadeh\nPractice: MedDoc Pro Pain Management\n\n${notesContext}`,
        },
      ],
    });
    logGptToolUsage(completion, session);
    generatedText = (completion.choices[0]?.message?.content ?? '').trim();
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Document generation failed';
    await logAudit({
      action: 'GENERATED_DRAFT_DOCUMENT',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'GPT_FAILED',
      metadata: { documentType, reason: message },
    });
    return { ok: false, error: `Generation failed: ${message}` };
  }

  if (!generatedText) {
    return { ok: false, error: 'AI returned an empty document — please try again.' };
  }

  // 6. Audit log — success (no PHI in metadata, just type + lengths)
  await logAudit({
    action: 'GENERATED_DRAFT_DOCUMENT',
    targetId: patientId,
    targetType: 'Patient',
    metadata: {
      documentType,
      generatedLength: generatedText.length,
      sourceNoteCount: recentNotes.length,
      userId: session.user.id,
    },
  });

  return {
    ok: true,
    data: {
      documentType,
      title: docConfig.title,
      content: generatedText,
      sourceNoteCount: recentNotes.length,
    },
  };
}

// dispatchEditNote no longer keeps a local edit-note system prompt — it
// delegates to editClinicalNoteTwoPass in @/lib/ai-service, which runs
// a structured intent parse (Pass 1) followed by an executor (Pass 2)
// tuned for clinical-note edits. The single-shot prompt that used to
// live here had the same fragility we already fixed for the Doc Editor.

// ===========================================================================
// CREATE NOTE FROM TEMPLATE — instant pre-filled draft
// ===========================================================================


export async function createNoteFromTemplateAction(
  patientId: string,
  templateId: string
): Promise<ActionResult<ClinicalNoteView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    return authErrorResult(err);
  }

  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return { ok: false, error: 'Patient not found.' };
  }

  const template = PROCEDURE_TEMPLATES.find((t) => t.id === templateId);
  if (!template) {
    return { ok: false, error: 'Unknown template.' };
  }

  let note: ClinicalNoteView;
  try {
    note = await dataCreateClinicalNote({
      patientId,
      title: `${template.name} — ${patient.firstName} ${patient.lastName[0]}.`,
      procedureType: template.procedureType,
      content: template.content,
      createdById: session.user.id,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to create note';
    return { ok: false, error: message };
  }

  await logAudit({
    action: 'CREATED_CLINICAL_NOTE',
    targetId: note.id,
    targetType: 'Document',
    metadata: { patientId, source: 'template', templateId },
  });

  revalidatePath(`/dashboard/patients/${patientId}`);
  return { ok: true, data: note };
}

// ===========================================================================
// UPDATE NOTE MANUALLY — plain text save (no AI)
// ===========================================================================

export async function updateNoteManuallyAction(
  noteId: string,
  patientId: string,
  newContent: string
): Promise<ActionResult<ClinicalNoteView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'EDITED_NOTE',
      targetId: noteId,
      targetType: 'Document',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    return authErrorResult(err);
  }

  const existingNote = await dataGetNoteById(noteId, session);
  if (!existingNote) {
    return { ok: false, error: 'Note not found.' };
  }

  if (existingNote.patientId !== patientId) {
    return { ok: false, error: 'Note does not belong to this patient.' };
  }

  if (!newContent.trim()) {
    return { ok: false, error: 'Note content cannot be empty.' };
  }

  let updatedNote: ClinicalNoteView | null;
  try {
    updatedNote = await dataUpdateClinicalNote(noteId, newContent, session.user.id, session);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to save';
    return { ok: false, error: message };
  }

  if (!updatedNote) {
    return { ok: false, error: 'Note was deleted before it could be saved.' };
  }

  await logAudit({
    action: 'EDITED_NOTE',
    targetId: noteId,
    targetType: 'Document',
    metadata: {
      patientId,
      editMethod: 'manual',
      previousContentLength: existingNote.content.length,
      newContentLength: newContent.length,
    },
  });

  revalidatePath(`/dashboard/patients/${patientId}`);
  return { ok: true, data: updatedNote };
}

// ===========================================================================
// UPLOAD CUSTOM PROCEDURE — PDF / DOCX → text → Clinical Note
// ===========================================================================

const ALLOWED_MIME_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
]);

export async function uploadCustomProcedureAction(
  patientId: string,
  formData: FormData
): Promise<ActionResult<ClinicalNoteView>> {
  // 1. Authorization
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    return authErrorResult(err);
  }

  // 2. Validate patient
  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return { ok: false, error: 'Patient not found.' };
  }

  // 3. Validate file
  const file = formData.get('file');
  if (!file || typeof file === 'string') {
    return { ok: false, error: 'No file provided.' };
  }
  const uploadedFile = file as File;

  if (!ALLOWED_MIME_TYPES.has(uploadedFile.type)) {
    return { ok: false, error: 'Unsupported file type. Please upload a PDF or Word (.docx) file.' };
  }

  if (uploadedFile.size > 10 * 1024 * 1024) {
    return { ok: false, error: 'File exceeds 10MB limit.' };
  }

  if (uploadedFile.size < 100) {
    return { ok: false, error: 'File appears to be empty.' };
  }

  // 4. Extract text
  let extractedText: string;
  const buffer = Buffer.from(await uploadedFile.arrayBuffer());

  try {
    if (uploadedFile.type === 'application/pdf') {
      // pdf-parse v1 is CJS — use require for compatibility
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const pdfParse = require('pdf-parse') as (buf: Buffer) => Promise<{ text: string }>;
      const pdfData = await pdfParse(buffer);
      extractedText = (pdfData.text ?? '').trim();
    } else {
      const mammoth = await import('mammoth');
      const result = await mammoth.extractRawText({ buffer });
      extractedText = (result.value ?? '').trim();
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to read file';
    await logAudit({
      action: 'CREATED_CLINICAL_NOTE',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'FILE_PARSE_FAILED',
      metadata: {
        source: 'file_upload',
        filename: uploadedFile.name,
        mimeType: uploadedFile.type,
        reason: message,
      },
    });
    return { ok: false, error: `Failed to extract text from file: ${message}` };
  }

  if (!extractedText || extractedText.length < 10) {
    return { ok: false, error: 'Could not extract meaningful text from this file. It may be image-based or empty.' };
  }

  // 5. Save as clinical note
  const filename = uploadedFile.name.replace(/\.[^/.]+$/, ''); // strip extension
  let note: ClinicalNoteView;
  try {
    note = await dataCreateClinicalNote({
      patientId,
      title: `Uploaded: ${filename}`,
      procedureType: null,
      category: 'CUSTOM_PROCEDURE',
      content: extractedText,
      createdById: session.user.id,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to save note';
    return { ok: false, error: message };
  }

  // 6. HIPAA audit — filename is safe metadata (not PHI content)
  await logAudit({
    action: 'CREATED_CLINICAL_NOTE',
    targetId: note.id,
    targetType: 'Document',
    metadata: {
      patientId,
      source: 'file_upload',
      filename: uploadedFile.name,
      mimeType: uploadedFile.type,
      fileSizeBytes: uploadedFile.size,
      extractedTextLength: extractedText.length,
    },
  });

  // 7. Revalidate
  revalidatePath(`/dashboard/patients/${patientId}`);
  return { ok: true, data: note };
}

// ===========================================================================
// SCHEDULE VISIT — create an appointment for a patient
// ===========================================================================


export async function scheduleVisitAction(
  patientId: string,
  formData: FormData
): Promise<ActionResult<AppointmentView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN', 'STAFF']);
  } catch (err) {
    return authErrorResult(err);
  }

  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return { ok: false, error: 'Patient not found.' };
  }

  // Parse form fields. Client sends `scheduledAt` as an ISO-8601 UTC string
  // built from the browser's local TZ (see src/lib/datetime.ts) — no zone
  // guessing on the server.
  const scheduledAtStr = formData.get('scheduledAt');
  const visitType = formData.get('visitType');
  const notes = formData.get('notes');

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
    const message = err instanceof Error ? err.message : 'Failed to schedule visit';
    return { ok: false, error: message };
  }

  await logAudit({
    action: 'SCHEDULED_VISIT',
    targetId: appointment.id,
    targetType: 'Appointment',
    metadata: {
      patientId,
      visitType,
      scheduledAt: scheduledAt.toISOString(),
    },
  });

  revalidatePath(`/dashboard/patients/${patientId}`);
  return { ok: true, data: appointment };
}

// ===========================================================================
// ASSISTANT TYPES — shared by the Realtime tool dispatchers below
// ===========================================================================

export type AssistantAction =
  | { type: 'created_note'; noteId: string; noteTitle: string }
  | { type: 'edited_note'; noteId: string; noteTitle: string }
  | { type: 'summarized' }
  | {
      type: 'generated_document';
      documentType: DocumentType;
      documentTitle: string;
      content: string;
    }
  | {
      type: 'scheduled_appointment';
      appointmentId: string;
      scheduledAt: string;
      visitType: 'CONSULTATION' | 'FOLLOW_UP' | 'PROCEDURE';
    }
  | { type: 'updated_patient'; patientId: string; changedFields: string[] }
  | { type: 'awaiting_file_upload'; reason: string }
  | { type: 'final_report_generated'; reportId: string; title: string }
  | { type: 'clinical_safety_updated' }
  | { type: 'chat' };

export type AssistantResult =
  | { ok: true; reply: string; action: AssistantAction }
  | { ok: false; error: string };


const SUMMARIZE_SYSTEM_PROMPT = `You summarize a patient's clinical notes for a pain management physician. Output 3–5 sentences in plain prose: key conditions, recent procedures, current treatment plan, and any open concerns. No bullets, no markdown, no preamble — start directly with the summary.`;

// ---------------------------------------------------------------------------
// Dispatchers — each owns its audit log and revalidate
// ---------------------------------------------------------------------------

export async function dispatchCreateNote(
  patient: PatientView,
  dictation: string,
  openai: OpenAI,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  session: any
): Promise<AssistantResult> {
  let soapNote: string;
  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0.2,
      messages: [
        { role: 'system', content: SOAP_SYSTEM_PROMPT },
        {
          role: 'user',
          content: `Patient: ${patient.firstName} ${patient.lastName[0]}. (age ${
            new Date().getFullYear() - patient.birthYear
          }).\n\nDictation:\n${dictation}`,
        },
      ],
    });
    logGptToolUsage(completion, session);
    soapNote = (completion.choices[0]?.message?.content ?? '').trim();
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Note formatting failed';
    return { ok: false, error: `Note formatting failed: ${message}` };
  }
  if (!soapNote) return { ok: false, error: 'AI returned an empty note — please try again.' };

  let note: ClinicalNoteView;
  try {
    note = await dataCreateClinicalNote({
      patientId: patient.id,
      title: buildNoteTitle(soapNote),
      procedureType: inferProcedureType(dictation),
      content: soapNote,
      createdById: session.user.id,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to save note';
    return { ok: false, error: message };
  }

  await logAudit({
    action: 'CREATED_CLINICAL_NOTE',
    targetId: note.id,
    targetType: 'Document',
    metadata: {
      patientId: patient.id,
      via: 'assistant',
      dictationLength: dictation.length,
      noteLength: soapNote.length,
    },
  });
  revalidatePath(`/dashboard/patients/${patient.id}`);

  return {
    ok: true,
    reply: `Created clinical note "${note.title}".`,
    action: { type: 'created_note', noteId: note.id, noteTitle: note.title },
  };
}

export async function dispatchEditNote(
  patient: PatientView,
  targetNoteId: string | null,
  instructions: string,
  // Kept in the signature for back-compat with the realtime tool router's
  // call sites; the two-pass executor uses its own client internally.
  _openai: OpenAI,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  session: any
): Promise<AssistantResult> {
  if (!targetNoteId) {
    return {
      ok: true,
      reply: 'Which note should I edit? Try "edit the last note" or name the note explicitly.',
      action: { type: 'chat' },
    };
  }

  const existing = await dataGetNoteById(targetNoteId, session);
  if (!existing || existing.patientId !== patient.id) {
    return { ok: false, error: 'Could not find that note on this patient.' };
  }

  // Two-pass edit (Pass 1: gpt-4o-mini classifies intent into a structured
  // EditIntent; Pass 2: gpt-4o applies it). Replaces the previous single-shot
  // gpt-4o-mini call which had the same fragility we already fixed for the
  // Doc Editor — silent drops of replacement content, judging short inputs
  // as invalid, leaving boilerplate paragraphs behind, etc.
  let result;
  try {
    result = await editClinicalNoteTwoPass(existing.content, instructions);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Edit failed';
    return { ok: false, error: `Edit failed: ${message}` };
  }

  // Low-confidence / unclear → ask doctor to rephrase. Don't burn a Pass 2
  // call and don't risk silently mangling a signed clinical record on a
  // guessed interpretation.
  if (!result.ok) {
    return {
      ok: true,
      reply: result.message,
      action: { type: 'chat' },
    };
  }

  const updatedContent = result.content;
  if (!updatedContent) {
    return { ok: false, error: 'AI returned an empty result — please try again.' };
  }

  const updated = await dataUpdateClinicalNote(
    targetNoteId,
    updatedContent,
    session.user.id,
    session
  );
  if (!updated) return { ok: false, error: 'Note was deleted before the edit could be saved.' };

  await logAudit({
    action: 'EDITED_NOTE',
    targetId: targetNoteId,
    targetType: 'Document',
    metadata: {
      patientId: patient.id,
      via: 'assistant',
      instructionLength: instructions.length,
      // Audit trail captures Pass 1's interpretation. Useful for "the AI
      // butchered my note — what did it think I asked for?" debugging.
      intentOperation: result.intent.operation,
      intentTarget: result.intent.target_section,
      intentConfidence: result.intent.confidence,
    },
  });
  revalidatePath(`/dashboard/patients/${patient.id}`);

  return {
    ok: true,
    reply: `Updated "${updated.title}".`,
    action: { type: 'edited_note', noteId: updated.id, noteTitle: updated.title },
  };
}

export async function dispatchSummarize(
  patient: PatientView,
  recentNotes: ClinicalNoteView[],
  openai: OpenAI,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  session?: any
): Promise<AssistantResult> {
  if (recentNotes.length === 0) {
    return {
      ok: true,
      reply: `No clinical notes yet for ${patient.firstName}. Dictate one to get started.`,
      action: { type: 'summarized' },
    };
  }
  const context = recentNotes
    .map((n, i) => `--- Note ${i + 1} (${n.procedureType ?? 'General'}, ${n.createdAt.split('T')[0]}) ---\n${n.content}`)
    .join('\n\n');

  let summary: string;
  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0.3,
      max_tokens: 300,
      messages: [
        { role: 'system', content: SUMMARIZE_SYSTEM_PROMPT },
        { role: 'user', content: context },
      ],
    });
    logGptToolUsage(completion, session);
    summary = (completion.choices[0]?.message?.content ?? '').trim();
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Summary failed';
    return { ok: false, error: `Summary failed: ${message}` };
  }
  if (!summary) return { ok: false, error: 'AI returned an empty summary — please try again.' };

  await logAudit({
    action: 'VIEWED_PATIENT_FILE',
    targetId: patient.id,
    targetType: 'Patient',
    metadata: { via: 'assistant', purpose: 'summarize', noteCount: recentNotes.length },
  });

  return {
    ok: true,
    reply: summary,
    action: { type: 'summarized' },
  };
}

export async function dispatchGenerateDocument(
  patientId: string,
  documentType: DocumentType | null
): Promise<AssistantResult> {
  if (!documentType) {
    return {
      ok: true,
      reply:
        'Which document? I can draft a referral letter, patient handout, disability form, or prior authorization letter.',
      action: { type: 'chat' },
    };
  }

  // Reuse the existing action — its own auth + tenant + audit chain. Note
  // that this triggers a second `requireRole` call (one already happened in
  // runAssistantCommandAction). Cheap (cookie read), and keeping the flow
  // funneled through the public action means audit logging stays consistent
  // with documents generated from the modal UI.
  const result = await generateDocumentAction(patientId, documentType);
  if (!result.ok) return { ok: false, error: result.error };

  return {
    ok: true,
    reply: `Drafted ${result.data.title}.`,
    action: {
      type: 'generated_document',
      documentType,
      documentTitle: result.data.title,
      content: result.data.content,
    },
  };
}

export async function dispatchScheduleAppointment(
  patient: PatientView,
  scheduledAtIso: string | null,
  visitType: 'CONSULTATION' | 'FOLLOW_UP' | 'PROCEDURE' | null,
  notes: string | null,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  session: any
): Promise<AssistantResult> {
  if (!scheduledAtIso) {
    return {
      ok: true,
      reply:
        'When should I schedule it? Try "schedule a follow-up next Tuesday at 10 AM" or give a specific date and time.',
      action: { type: 'chat' },
    };
  }

  const scheduledAt = new Date(scheduledAtIso);
  if (Number.isNaN(scheduledAt.getTime())) {
    return { ok: false, error: `Could not parse date/time: ${scheduledAtIso}` };
  }
  // Sanity guard — refuse to schedule far in the past. Lets us catch GPT
  // returning a bogus year (e.g., default ISO with year 0001) without a
  // mysterious "appointment in 1970" showing up on the calendar.
  if (scheduledAt.getTime() < Date.now() - 24 * 60 * 60 * 1000) {
    return {
      ok: false,
      error: `That date is in the past (${scheduledAt.toLocaleString()}). Please pick a future date.`,
    };
  }

  const resolvedType = visitType ?? 'FOLLOW_UP';

  let appointment;
  try {
    appointment = await createAppointment(
      {
        patientId: patient.id,
        userId: session.user.id,
        scheduledAt,
        type: resolvedType,
        notes: notes?.trim() || null,
      },
      session
    );
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to schedule appointment';
    return { ok: false, error: message };
  }

  await logAudit({
    action: 'SCHEDULED_VISIT',
    targetId: appointment.id,
    targetType: 'Appointment',
    metadata: {
      patientId: patient.id,
      via: 'assistant',
      visitType: resolvedType,
      scheduledAt: scheduledAt.toISOString(),
    },
  });
  revalidatePath(`/dashboard/patients/${patient.id}`);
  revalidatePath('/dashboard/schedule');

  // Friendly confirmation. Use the user's locale for the readable timestamp;
  // the server's locale would be UTC which reads weird to clinicians.
  const friendly = scheduledAt.toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });

  return {
    ok: true,
    reply: `Scheduled ${resolvedType.toLowerCase().replace('_', ' ')} for ${friendly}.`,
    action: {
      type: 'scheduled_appointment',
      appointmentId: appointment.id,
      scheduledAt: scheduledAt.toISOString(),
      visitType: resolvedType,
    },
  };
}

// ===========================================================================
// UPDATE PATIENT — voice-tool entry for editing any patient profile field
// (including briefHistory). Reuses the existing tenant-scoped data layer.
// Audited as UPDATED_PATIENT with field NAMES only — never values.
// ===========================================================================

export interface UpdatePatientFromAssistant {
  firstName?: string;
  lastName?: string;
  mrn?: string;
  chartId?: string;
  birthYear?: number;
  email?: string;
  cellPhone?: string;
  homePhone?: string;
  tags?: string[];
  status?: 'ACTIVE' | 'INACTIVE' | 'ARCHIVED';
  insuranceVerified?: boolean;
  briefHistory?: string[];
  sex?: 'UNKNOWN' | 'MALE' | 'FEMALE' | 'OTHER';
  addressLine1?: string;
  addressLine2?: string;
  city?: string;
  state?: string;
  postalCode?: string;
  pharmacyName?: string;
  pharmacyPhone?: string;
  /** User ID of the assigned provider. Must belong to the same
   *  practice; enforced at dispatch time. */
  assignedDoctorId?: string;
}

export async function dispatchUpdatePatient(
  patient: PatientView,
  updates: UpdatePatientFromAssistant,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  session: any
): Promise<AssistantResult> {
  // Strip undefined fields so we only send actual changes to the data layer.
  const cleanUpdates: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(updates)) {
    if (v !== undefined) cleanUpdates[k] = v;
  }
  if (Object.keys(cleanUpdates).length === 0) {
    return { ok: false, error: 'No fields specified to update.' };
  }

  let result;
  try {
    result = await dataUpdatePatient(patient.id, cleanUpdates as Parameters<typeof dataUpdatePatient>[1], session);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Update failed';
    return { ok: false, error: message };
  }
  if (!result) {
    return { ok: false, error: 'Patient not found or not accessible.' };
  }

  await logAudit({
    action: 'UPDATED_PATIENT',
    targetId: patient.id,
    targetType: 'Patient',
    metadata: {
      via: 'assistant',
      // Field NAMES only — never values. HIPAA §164.530.
      changedFields: result.changedFields,
    },
  });
  revalidatePath(`/dashboard/patients/${patient.id}`);

  // Friendly summary for the model to paraphrase. Brief by design.
  const summary =
    result.changedFields.length === 0
      ? 'No changes were needed.'
      : result.changedFields.length === 1
        ? `Updated ${humanize(result.changedFields[0])}.`
        : `Updated: ${result.changedFields.map(humanize).join(', ')}.`;

  return {
    ok: true,
    reply: summary,
    action: {
      type: 'updated_patient',
      patientId: patient.id,
      changedFields: result.changedFields,
    },
  };
}

function humanize(field: string): string {
  // Camel/lowercase → spaced human form. "briefHistory" → "brief history".
  return field
    .replace(/([A-Z])/g, ' $1')
    .toLowerCase()
    .trim();
}

// ============================================================================
// UPLOAD PATIENT FILE (metadata only for now)
// ============================================================================
// Accepts file metadata from PatientFileUploadModal and writes a
// PATIENT_FILE-categorized Document row. Actual bytes are not persisted
// yet — when Dropbox/S3 storage lands, extend this action to take a
// FormData blob and hand the file off before inserting.
// ----------------------------------------------------------------------------

// Accepts the actual file bytes (FormData) rather than just metadata so
// PDF/DOCX text can be extracted and saved as searchable, editable
// content — same flow as uploadCustomProcedureAction. Image uploads keep
// metadata-only (no OCR yet).
const UPLOAD_PATIENT_FILE_ALLOWED_MIMES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'image/png',
  'image/jpeg',
  'image/webp',
]);

export async function uploadPatientFileAction(
  patientId: string,
  formData: FormData
): Promise<ActionResult<ClinicalNoteView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'CREATED_DOCUMENT',
      success: false,
      errorCode: 'FORBIDDEN',
      metadata: { category: 'PATIENT_FILE' },
    });
    return authErrorResult(err);
  }

  if (!patientId || typeof patientId !== 'string') {
    return { ok: false, error: 'Invalid patient id' };
  }

  // Tenant guard — patient must be visible to this session.
  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return { ok: false, error: 'Patient not found.' };
  }

  // Which chart card the upload should land under (optional, defaults to
  // PATIENT_FILE). Sent as a plain form field alongside the file.
  const rawCategory = formData.get('category');
  const category: 'PATIENT_FILE' | 'FINAL_REPORT' =
    rawCategory === 'FINAL_REPORT' ? 'FINAL_REPORT' : 'PATIENT_FILE';

  const file = formData.get('file');
  if (!file || typeof file === 'string') {
    return { ok: false, error: 'No file provided.' };
  }
  const uploadedFile = file as File;

  if (!UPLOAD_PATIENT_FILE_ALLOWED_MIMES.has(uploadedFile.type)) {
    return {
      ok: false,
      error: 'Unsupported file type. Allowed: PDF, DOCX, PNG, JPG, WEBP.',
    };
  }
  if (uploadedFile.size > 25 * 1024 * 1024) {
    return { ok: false, error: 'File exceeds 25MB limit.' };
  }
  if (uploadedFile.size < 100) {
    return { ok: false, error: 'File appears to be empty.' };
  }

  // Extract text when the file type supports it. Images skip extraction —
  // they persist as metadata only until we wire OCR or real storage.
  const buffer = Buffer.from(await uploadedFile.arrayBuffer());
  let extractedText = '';
  const isExtractable =
    uploadedFile.type === 'application/pdf' ||
    uploadedFile.type ===
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document';

  if (isExtractable) {
    try {
      if (uploadedFile.type === 'application/pdf') {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const pdfParse = require('pdf-parse') as (
          buf: Buffer
        ) => Promise<{ text: string }>;
        const pdfData = await pdfParse(buffer);
        extractedText = (pdfData.text ?? '').trim();
      } else {
        const mammoth = await import('mammoth');
        const result = await mammoth.extractRawText({ buffer });
        extractedText = (result.value ?? '').trim();
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to read file';
      await logAudit({
        action: 'CREATED_DOCUMENT',
        success: false,
        errorCode: 'FILE_PARSE_FAILED',
        metadata: {
          category,
          patientId,
          filename: uploadedFile.name,
          mimeType: uploadedFile.type,
          reason: message,
        },
      });
      return { ok: false, error: `Failed to extract text from file: ${message}` };
    }

    if (!extractedText || extractedText.length < 10) {
      return {
        ok: false,
        error:
          'Could not extract meaningful text from this file. It may be image-based or empty.',
      };
    }
  }

  // When we have extracted content, store it on a text-style row so the
  // UI can display + edit inline (matching CUSTOM_PROCEDURE pattern).
  // When we don't (images), fall back to metadata-only.
  const filename = uploadedFile.name.replace(/\.[^/.]+$/, ''); // strip extension
  try {
    let row: ClinicalNoteView;
    if (isExtractable && extractedText) {
      row = await dataCreateClinicalNote({
        patientId,
        title:
          category === 'FINAL_REPORT'
            ? `Final Report: ${filename}`
            : `Uploaded: ${filename}`,
        procedureType: null,
        category,
        content: extractedText,
        createdById: session.user.id,
      });
    } else {
      row = await dataCreatePatientFile({
        patientId,
        fileName: uploadedFile.name,
        mimeType: uploadedFile.type,
        sizeBytes: uploadedFile.size,
        createdById: session.user.id,
        category,
      });
    }

    await logAudit({
      action: 'CREATED_DOCUMENT',
      targetId: row.id,
      targetType: 'Document',
      metadata: {
        category,
        patientId,
        filename: uploadedFile.name,
        mimeType: uploadedFile.type,
        sizeBytes: uploadedFile.size,
        extracted: Boolean(isExtractable && extractedText),
      },
    });

    revalidatePath(`/dashboard/patients/${patientId}`);
    return { ok: true, data: row };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Upload failed';
    await logAudit({
      action: 'CREATED_DOCUMENT',
      success: false,
      errorCode: 'UPLOAD_FAILED',
      metadata: { category, patientId, reason: message },
    });
    return { ok: false, error: message };
  }
}

// ============================================================================
// GENERATE FINAL REPORT (AI-synthesized discharge/evaluation summary)
// ============================================================================
// Gathers the patient's brief history, clinical notes, and custom procedures,
// sends them to GPT-4o, and persists the response as a FINAL_REPORT document.
// Shared between the card button and the Realtime `generate_final_report`
// tool, so both paths produce identical output.
// ----------------------------------------------------------------------------

const FINAL_REPORT_SYSTEM_PROMPT = `You are an expert clinical writer preparing a comprehensive Final Evaluation Report for a pain management practice.

Given the patient's brief history, clinical notes, and procedure documents below, produce ONE cohesive narrative report with these sections in order:

1. Patient Summary — name, age, sex, relevant demographics. One paragraph.
2. Clinical History — chronologic synthesis of the brief-history entries and the presenting complaint. One paragraph.
3. Course of Treatment — what was done, in order. Reference individual notes/procedures by date. Keep it factual, no invention.
4. Findings & Outcomes — response to treatment per the notes. Call out pain-scale changes, functional improvements/declines, complications if noted.
5. Current Status — where the patient stands as of the most recent note.
6. Plan & Recommendations — next steps if notes indicate them; otherwise "to be determined at next follow-up."

Rules:
- Prose, not bullet lists, except for optional citations at end of each section.
- Never invent facts. If a section has no source data, write "Not documented."
- Do not include pleasantries, hedging, or meta-commentary about your own writing.
- No markdown headers with # — use plain "Section Name:" prefixes.`;

export async function generateFinalReportAction(
  patientId: string
): Promise<ActionResult<ClinicalNoteView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'GENERATED_DRAFT_DOCUMENT',
      success: false,
      errorCode: 'FORBIDDEN',
      metadata: { category: 'FINAL_REPORT' },
    });
    return authErrorResult(err);
  }

  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return { ok: false, error: 'Patient not found' };
  }

  // Pull context. Cap each list so one overgrown chart doesn't blow past
  // the model's context window — newest-first ordering means the cap
  // keeps the most recent/relevant entries.
  const [notes, procedures] = await Promise.all([
    dataListNotesByPatient(patientId, 'CLINICAL_NOTE', session),
    dataListNotesByPatient(patientId, 'CUSTOM_PROCEDURE', session),
  ]);

  const NOTE_CAP = 12;
  const PROC_CAP = 6;
  const HISTORY_CAP = 20;

  const briefHistoryBlock =
    patient.briefHistory.slice(0, HISTORY_CAP).join('\n- ') || '(none)';
  const notesBlock =
    notes.slice(0, NOTE_CAP).map((n, i) =>
      `### Note ${i + 1} — ${n.title} (${n.createdAt.slice(0, 10)})\n${n.content}`
    ).join('\n\n') || '(none)';
  const proceduresBlock =
    procedures.slice(0, PROC_CAP).map((p, i) =>
      `### Procedure Document ${i + 1} — ${p.title} (${p.createdAt.slice(0, 10)})\n${p.content}`
    ).join('\n\n') || '(none)';

  const demographics = [
    `Name: ${patient.firstName} ${patient.lastName}`,
    `Age: ${patient.birthYear ? new Date().getFullYear() - patient.birthYear : 'unknown'}`,
    `MRN: ${patient.mrn || '(none)'}`,
    `Chart ID: ${patient.chartId || '(none)'}`,
  ].join('\n');

  const userMessage = `PATIENT DEMOGRAPHICS:
${demographics}

BRIEF HISTORY:
- ${briefHistoryBlock}

CLINICAL NOTES (${notes.length} total, showing ${Math.min(notes.length, NOTE_CAP)} most recent):
${notesBlock}

PROCEDURE DOCUMENTS (${procedures.length} total, showing ${Math.min(procedures.length, PROC_CAP)} most recent):
${proceduresBlock}`;

  const apiKey = process.env.OPENAI_API_KEY;
  if (!apiKey?.trim()) {
    return { ok: false, error: 'AI service is not configured.' };
  }

  let content: string;
  let totalTokens: number | null = null;
  try {
    const client = new OpenAI({ apiKey });
    const completion = await client.chat.completions.create({
      // gpt-4o here, not mini — this is a long-form clinical synthesis
      // where the quality jump is worth the cost. Matches what the user
      // specifically asked for in this feature.
      model: 'gpt-4o',
      temperature: 0.3,
      messages: [
        { role: 'system', content: FINAL_REPORT_SYSTEM_PROMPT },
        { role: 'user', content: userMessage },
      ],
    });
    content = (completion.choices[0]?.message?.content ?? '').trim();
    totalTokens = completion.usage?.total_tokens ?? null;
  } catch (err) {
    console.error('[generateFinalReportAction] OpenAI call failed:', err);
    const message = err instanceof Error ? err.message : 'AI generation failed';
    await logAudit({
      action: 'GENERATED_DRAFT_DOCUMENT',
      success: false,
      errorCode: 'AI_FAILED',
      metadata: { category: 'FINAL_REPORT', patientId, reason: message },
    });
    return { ok: false, error: message };
  }

  if (!content) {
    return { ok: false, error: 'AI returned an empty report. Try again.' };
  }

  // Persist + audit + revalidate.
  const title = `Final Report — ${new Date().toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })}`;

  try {
    const report = await dataCreateFinalReport({
      patientId,
      title,
      content,
      createdById: session.user.id,
    });
    await logAudit({
      action: 'GENERATED_DRAFT_DOCUMENT',
      targetId: report.id,
      targetType: 'Document',
      metadata: { category: 'FINAL_REPORT', patientId, totalTokens },
    });
    void logApiUsage({
      feature: 'GPT_TOOL',
      userId: session.user.id,
      practiceId: session.user.practiceId,
      tokens: totalTokens,
    }).catch((e) => console.error('[generateFinalReportAction] usage log failed:', e));
    revalidatePath(`/dashboard/patients/${patientId}`);
    return { ok: true, data: report };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Save failed';
    return { ok: false, error: message };
  }
}

// ============================================================================
// DELETE DOCUMENT (clinical note / custom procedure / final report / file)
// ============================================================================
// All four chart categories live in the Document table, so one action
// covers every card's delete button. Tenant isolation + soft-delete live
// inside dataDeleteClinicalNote; this wrapper adds auth + audit + path
// revalidation.
// ----------------------------------------------------------------------------

export async function deleteDocumentAction(
  documentId: string,
  patientId: string
): Promise<ActionResult<{ deleted: true }>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'DELETED_DOCUMENT',
      targetId: documentId,
      targetType: 'Document',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    return authErrorResult(err);
  }

  if (!documentId || typeof documentId !== 'string') {
    return { ok: false, error: 'Invalid document ID' };
  }

  const ok = await dataDeleteClinicalNote(documentId, session);
  if (!ok) {
    // Either the document doesn't exist or the session can't see it —
    // same "collapsed" response as elsewhere so cross-tenant probes
    // can't distinguish the two.
    return { ok: false, error: 'Document not found or not accessible.' };
  }

  await logAudit({
    action: 'DELETED_DOCUMENT',
    targetId: documentId,
    targetType: 'Document',
    metadata: { patientId, via: 'manual' },
  });

  revalidatePath(`/dashboard/patients/${patientId}`);
  return { ok: true, data: { deleted: true } };
}

// Thin dispatcher wrapper for the Realtime assistant `generate_final_report`
// tool. Returns an AssistantResult so /api/assistant-tool can adapt it
// to the voice-channel response shape.
export async function dispatchGenerateFinalReport(
  patientId: string
): Promise<AssistantResult> {
  const result = await generateFinalReportAction(patientId);
  if (!result.ok) {
    return { ok: false, error: result.error };
  }
  return {
    ok: true,
    reply: `Generated the Final Report. It's in the patient's Final Reports section as a draft — review and sign when ready.`,
    action: {
      type: 'final_report_generated',
      reportId: result.data.id,
      title: result.data.title,
    },
  };
}

// ===========================================================================
// CLINICAL SAFETY — Allergies + Medications
// ---------------------------------------------------------------------------
// Doctor-only writes: STAFF can view a patient but not edit safety data
// (matches archivePatientAction's role guard). Every mutation:
//   - re-validates session role
//   - delegates tenant-isolation to the data layer (patientAccessWhere)
//   - logs an audit row keyed by allergy/medication id
//   - revalidates /dashboard/patients/[patientId] so the panel refreshes
// ===========================================================================

const allergySeveritySchema = z.enum(['UNKNOWN', 'MILD', 'MODERATE', 'SEVERE']);

const addAllergySchema = z.object({
  patientId: z.string().min(1),
  allergen: z.string().min(1, 'Allergen is required').max(200),
  reaction: z.string().max(200).nullable().optional(),
  severity: allergySeveritySchema.optional(),
  notes: z.string().max(2000).nullable().optional(),
});

const updateAllergySchema = z.object({
  allergen: z.string().min(1).max(200).optional(),
  reaction: z.string().max(200).nullable().optional(),
  severity: allergySeveritySchema.optional(),
  notes: z.string().max(2000).nullable().optional(),
});

const addMedicationSchema = z.object({
  patientId: z.string().min(1),
  name: z.string().min(1, 'Medication name is required').max(200),
  dosage: z.string().max(120).nullable().optional(),
  frequency: z.string().max(120).nullable().optional(),
  isActive: z.boolean().optional(),
  notes: z.string().max(2000).nullable().optional(),
});

const updateMedicationSchema = z.object({
  name: z.string().min(1).max(200).optional(),
  dosage: z.string().max(120).nullable().optional(),
  frequency: z.string().max(120).nullable().optional(),
  isActive: z.boolean().optional(),
  notes: z.string().max(2000).nullable().optional(),
});

// ----- READ -----

export async function listAllergiesAction(
  patientId: string
): Promise<ActionResult<AllergyView[]>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN', 'STAFF']);
  } catch (err) {
    return authErrorResult(err);
  }
  try {
    const data = await dataListAllergies(session, patientId);
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to load allergies' };
  }
}

export async function listMedicationsAction(
  patientId: string,
  includeInactive = false
): Promise<ActionResult<MedicationView[]>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN', 'STAFF']);
  } catch (err) {
    return authErrorResult(err);
  }
  try {
    const data = await dataListMedications(session, patientId, { includeInactive });
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to load medications' };
  }
}

// ----- ALLERGY MUTATIONS -----

export async function addAllergyAction(
  raw: z.input<typeof addAllergySchema>
): Promise<ActionResult<AllergyView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'CREATED_ALLERGY',
      targetId: raw?.patientId ?? '',
      targetType: 'Patient',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    return authErrorResult(err);
  }
  const parsed = addAllergySchema.safeParse(raw);
  if (!parsed.success) {
    return { ok: false, error: 'Invalid input', fieldErrors: parsed.error.flatten().fieldErrors };
  }
  try {
    const data = await dataCreateAllergy(session, parsed.data);
    await logAudit({ action: 'CREATED_ALLERGY', targetId: data.id, targetType: 'Allergy' });
    revalidatePath(`/dashboard/patients/${parsed.data.patientId}`);
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to add allergy' };
  }
}

export async function updateAllergyAction(
  allergyId: string,
  patientId: string,
  raw: z.input<typeof updateAllergySchema>
): Promise<ActionResult<AllergyView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    return authErrorResult(err);
  }
  const parsed = updateAllergySchema.safeParse(raw);
  if (!parsed.success) {
    return { ok: false, error: 'Invalid input', fieldErrors: parsed.error.flatten().fieldErrors };
  }
  try {
    const data = await dataUpdateAllergy(session, allergyId, parsed.data);
    await logAudit({ action: 'UPDATED_ALLERGY', targetId: allergyId, targetType: 'Allergy' });
    revalidatePath(`/dashboard/patients/${patientId}`);
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to update allergy' };
  }
}

export async function deleteAllergyAction(
  allergyId: string,
  patientId: string
): Promise<ActionResult<{ deleted: true }>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    return authErrorResult(err);
  }
  try {
    await dataDeleteAllergy(session, allergyId);
    await logAudit({ action: 'DELETED_ALLERGY', targetId: allergyId, targetType: 'Allergy' });
    revalidatePath(`/dashboard/patients/${patientId}`);
    return { ok: true, data: { deleted: true } };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to delete allergy' };
  }
}

export async function setNoKnownAllergiesAction(
  patientId: string,
  value: boolean
): Promise<ActionResult<{ noKnownAllergies: boolean }>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    return authErrorResult(err);
  }
  try {
    await dataSetNoKnownAllergies(session, patientId, value);
    await logAudit({
      action: 'UPDATED_PATIENT',
      targetId: patientId,
      targetType: 'Patient',
      metadata: { field: 'noKnownAllergies', value },
    });
    revalidatePath(`/dashboard/patients/${patientId}`);
    return { ok: true, data: { noKnownAllergies: value } };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to update NKA' };
  }
}

// ----- MEDICATION MUTATIONS -----

export async function addMedicationAction(
  raw: z.input<typeof addMedicationSchema>
): Promise<ActionResult<MedicationView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'CREATED_MEDICATION',
      targetId: raw?.patientId ?? '',
      targetType: 'Patient',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    return authErrorResult(err);
  }
  const parsed = addMedicationSchema.safeParse(raw);
  if (!parsed.success) {
    return { ok: false, error: 'Invalid input', fieldErrors: parsed.error.flatten().fieldErrors };
  }
  try {
    const data = await dataCreateMedication(session, parsed.data);
    await logAudit({ action: 'CREATED_MEDICATION', targetId: data.id, targetType: 'Medication' });
    revalidatePath(`/dashboard/patients/${parsed.data.patientId}`);
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to add medication' };
  }
}

export async function updateMedicationAction(
  medicationId: string,
  patientId: string,
  raw: z.input<typeof updateMedicationSchema>
): Promise<ActionResult<MedicationView>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    return authErrorResult(err);
  }
  const parsed = updateMedicationSchema.safeParse(raw);
  if (!parsed.success) {
    return { ok: false, error: 'Invalid input', fieldErrors: parsed.error.flatten().fieldErrors };
  }
  try {
    const data = await dataUpdateMedication(session, medicationId, parsed.data);
    await logAudit({ action: 'UPDATED_MEDICATION', targetId: medicationId, targetType: 'Medication' });
    revalidatePath(`/dashboard/patients/${patientId}`);
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to update medication' };
  }
}

export async function deleteMedicationAction(
  medicationId: string,
  patientId: string
): Promise<ActionResult<{ deleted: true }>> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    return authErrorResult(err);
  }
  try {
    await dataDeleteMedication(session, medicationId);
    await logAudit({ action: 'DELETED_MEDICATION', targetId: medicationId, targetType: 'Medication' });
    revalidatePath(`/dashboard/patients/${patientId}`);
    return { ok: true, data: { deleted: true } };
  } catch (err) {
    return { ok: false, error: err instanceof Error ? err.message : 'Failed to delete medication' };
  }
}
