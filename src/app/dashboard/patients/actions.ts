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

export async function generateClinicalNoteAction(
  patientId: string,
  audioFormData: FormData
): Promise<ActionResult<ClinicalNoteView>> {
  // 1. Authorization — only clinicians dictate notes
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    await logAudit({
      action: 'CREATED_CLINICAL_NOTE',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'FORBIDDEN',
    });
    return authErrorResult(err);
  }

  // 2. Confirm the patient exists (prevents writing orphan notes)
  const patient = await getPatientById(patientId, session);
  if (!patient) {
    await logAudit({
      action: 'CREATED_CLINICAL_NOTE',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'PATIENT_NOT_FOUND',
    });
    return { ok: false, error: 'Patient not found' };
  }

  // 3. Validate audio blob — FormData entries are File | string | null
  const audio = audioFormData.get('audio');
  if (!audio || typeof audio === 'string') {
    return { ok: false, error: 'No audio data provided' };
  }
  const audioFile = audio as File;
  if (audioFile.size < 500) {
    return { ok: false, error: 'Audio too short — please speak longer.' };
  }
  if (audioFile.size > 25 * 1024 * 1024) {
    return { ok: false, error: 'Audio exceeds 25MB Whisper limit.' };
  }

  const openai = getOpenAI();

  // 4. Stage A — Whisper transcription. Using `verbose_json` so we can
  // capture audio duration for cost tracking; billing is per audio-minute
  // either way.
  let rawTranscript: string;
  try {
    const transcription = await openai.audio.transcriptions.create({
      file: audioFile,
      model: 'whisper-1',
      language: 'en',
      response_format: 'verbose_json',
    });
    rawTranscript = (transcription.text ?? '').trim();

    // Log usage immediately after success. Fire-and-forget so metrics
    // writes don't slow the clinical note flow.
    const durationSeconds =
      typeof transcription.duration === 'number'
        ? Math.round(transcription.duration)
        : null;
    void logApiUsage({
      feature: 'TRANSCRIBE',
      userId: session.user.id,
      practiceId: session.user.practiceId,
      durationSeconds,
    }).catch((err) => {
      console.error('[generateClinicalNote] logApiUsage rejected:', err);
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Whisper transcription failed';
    await logAudit({
      action: 'CREATED_CLINICAL_NOTE',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'WHISPER_FAILED',
      metadata: { reason: message },
    });
    return { ok: false, error: `Transcription failed: ${message}` };
  }

  if (!rawTranscript || rawTranscript.length < 5) {
    return { ok: false, error: 'No speech was detected in the audio.' };
  }

  // 5. Stage B — GPT-4o-mini SOAP formatting
  let soapNote: string;
  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0.2, // clinical accuracy > creativity
      messages: [
        { role: 'system', content: SOAP_SYSTEM_PROMPT },
        {
          role: 'user',
          content: `Patient: ${patient.firstName} ${patient.lastName[0]}. (age ${
            new Date().getFullYear() - patient.birthYear
          }).\n\nDictation:\n${rawTranscript}`,
        },
      ],
    });
    logGptToolUsage(completion, session);
    soapNote = (completion.choices[0]?.message?.content ?? '').trim();
  } catch (err) {
    const message = err instanceof Error ? err.message : 'GPT formatting failed';
    await logAudit({
      action: 'CREATED_CLINICAL_NOTE',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'GPT_FAILED',
      metadata: { reason: message, hadTranscript: true },
    });
    return { ok: false, error: `Note formatting failed: ${message}` };
  }

  if (!soapNote) {
    return { ok: false, error: 'AI returned an empty note — please try again.' };
  }

  // 6. Persist to DB (falls back to memory store automatically)
  let note: ClinicalNoteView;
  try {
    note = await dataCreateClinicalNote({
      patientId,
      title: buildNoteTitle(soapNote),
      procedureType: inferProcedureType(rawTranscript),
      content: soapNote,
      createdById: session.user.id,
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to save note';
    await logAudit({
      action: 'CREATED_CLINICAL_NOTE',
      targetId: patientId,
      targetType: 'Patient',
      success: false,
      errorCode: 'DB_WRITE_FAILED',
      metadata: { reason: message },
    });
    return { ok: false, error: message };
  }

  // 7. HIPAA audit — success. Store only non-PHI metadata (lengths, not text).
  await logAudit({
    action: 'CREATED_CLINICAL_NOTE',
    targetId: note.id,
    targetType: 'Document',
    metadata: {
      patientId,
      transcriptLength: rawTranscript.length,
      noteLength: soapNote.length,
      audioSizeBytes: audioFile.size,
      procedureType: note.procedureType,
    },
  });

  // 8. Revalidate so the patient page re-renders with the new note
  revalidatePath(`/dashboard/patients/${patientId}`);

  return { ok: true, data: note };
}

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

// ===========================================================================
// EDIT CLINICAL NOTE WITH VOICE — Whisper → GPT-4o-mini (context-aware edit)
// ---------------------------------------------------------------------------
// Same two-stage pipeline as creation, but GPT receives the existing note
// plus the doctor's spoken edit instructions. It returns the full updated
// note with only the requested changes applied.
// ===========================================================================

const EDIT_NOTE_SYSTEM_PROMPT = `You are a medical scribe AI for a pain management physician. You have received an EXISTING clinical note and a doctor's VOICE INSTRUCTIONS describing edits to make.

YOUR JOB: Apply the doctor's spoken instructions to the existing note and return the COMPLETE UPDATED note.

RULES:
1. Preserve all sections and formatting of the original note exactly, except where the instructions say to change something.
2. If the doctor says to add information, add it to the appropriate section.
3. If the doctor says to remove or correct something, do so precisely.
4. If the doctor says to change a medication, dosage, diagnosis, or finding, update only that specific item.
5. Do NOT add information that the doctor did not mention. Do NOT remove information unless instructed.
6. Preserve medical terminology exactly as in the original unless the doctor explicitly corrects it.
7. Return the FULL updated note, not just the changed parts.
8. NEVER include meta-commentary, explanations, or markdown. Return only the updated clinical note text.
9. If the instructions are unclear or contradictory, apply the most reasonable interpretation and preserve the original where ambiguous.`;

export async function editClinicalNoteWithVoiceAction(
  noteId: string,
  patientId: string,
  audioFormData: FormData
): Promise<ActionResult<ClinicalNoteView>> {
  // 1. Authorization
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

  // 2. Fetch the existing note — tenant-scoped
  const existingNote = await dataGetNoteById(noteId, session);
  if (!existingNote) {
    await logAudit({
      action: 'EDITED_NOTE',
      targetId: noteId,
      targetType: 'Document',
      success: false,
      errorCode: 'NOTE_NOT_FOUND',
    });
    return { ok: false, error: 'Clinical note not found.' };
  }

  // 3. Cross-check patient ownership (prevents PHI leak via crafted noteId)
  if (existingNote.patientId !== patientId) {
    await logAudit({
      action: 'EDITED_NOTE',
      targetId: noteId,
      targetType: 'Document',
      success: false,
      errorCode: 'PATIENT_MISMATCH',
    });
    return { ok: false, error: 'Note does not belong to this patient.' };
  }

  // 4. Validate audio blob
  const audio = audioFormData.get('audio');
  if (!audio || typeof audio === 'string') {
    return { ok: false, error: 'No audio data provided.' };
  }
  const audioFile = audio as File;
  if (audioFile.size < 500) {
    return { ok: false, error: 'Audio too short — please speak longer.' };
  }
  if (audioFile.size > 25 * 1024 * 1024) {
    return { ok: false, error: 'Audio exceeds 25MB Whisper limit.' };
  }

  const openai = getOpenAI();

  // 5. Whisper transcription. Using `verbose_json` so we can capture
  // audio duration for usage/cost tracking.
  let rawTranscript: string;
  try {
    const transcription = await openai.audio.transcriptions.create({
      file: audioFile,
      model: 'whisper-1',
      language: 'en',
      response_format: 'verbose_json',
    });
    rawTranscript = (transcription.text ?? '').trim();

    const durationSeconds =
      typeof transcription.duration === 'number'
        ? Math.round(transcription.duration)
        : null;
    void logApiUsage({
      feature: 'TRANSCRIBE',
      userId: session.user.id,
      practiceId: session.user.practiceId,
      durationSeconds,
    }).catch((err) => {
      console.error('[editClinicalNoteWithVoice] logApiUsage rejected:', err);
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Whisper transcription failed';
    await logAudit({
      action: 'EDITED_NOTE',
      targetId: noteId,
      targetType: 'Document',
      success: false,
      errorCode: 'WHISPER_FAILED',
      metadata: { reason: message },
    });
    return { ok: false, error: `Transcription failed: ${message}` };
  }

  if (!rawTranscript || rawTranscript.length < 5) {
    return { ok: false, error: 'No speech detected in the audio.' };
  }

  // 6. GPT-4o-mini: apply spoken edit instructions to existing note
  let updatedContent: string;
  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0.2,
      messages: [
        { role: 'system', content: EDIT_NOTE_SYSTEM_PROMPT },
        {
          role: 'user',
          content: `EXISTING NOTE:\n${existingNote.content}\n\nDOCTOR'S EDIT INSTRUCTIONS:\n${rawTranscript}`,
        },
      ],
    });
    logGptToolUsage(completion, session);
    updatedContent = (completion.choices[0]?.message?.content ?? '').trim();
  } catch (err) {
    const message = err instanceof Error ? err.message : 'GPT editing failed';
    await logAudit({
      action: 'EDITED_NOTE',
      targetId: noteId,
      targetType: 'Document',
      success: false,
      errorCode: 'GPT_FAILED',
      metadata: { reason: message, hadTranscript: true },
    });
    return { ok: false, error: `Note editing failed: ${message}` };
  }

  if (!updatedContent) {
    return { ok: false, error: 'AI returned an empty result — please try again.' };
  }

  // 7. Persist the update
  let updatedNote: ClinicalNoteView | null;
  try {
    updatedNote = await dataUpdateClinicalNote(noteId, updatedContent, session.user.id, session);
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Failed to save edited note';
    await logAudit({
      action: 'EDITED_NOTE',
      targetId: noteId,
      targetType: 'Document',
      success: false,
      errorCode: 'DB_WRITE_FAILED',
      metadata: { reason: message },
    });
    return { ok: false, error: message };
  }

  if (!updatedNote) {
    return { ok: false, error: 'Note was deleted before the edit could be saved.' };
  }

  // 8. HIPAA audit — success (lengths only, never PHI content)
  await logAudit({
    action: 'EDITED_NOTE',
    targetId: noteId,
    targetType: 'Document',
    metadata: {
      patientId,
      transcriptLength: rawTranscript.length,
      previousContentLength: existingNote.content.length,
      newContentLength: updatedContent.length,
      audioSizeBytes: audioFile.size,
    },
  });

  // 9. Revalidate so the patient page re-renders with the updated note
  revalidatePath(`/dashboard/patients/${patientId}`);

  return { ok: true, data: updatedNote };
}

// ===========================================================================
// CREATE NOTE FROM TEMPLATE — instant pre-filled draft
// ===========================================================================

import { PROCEDURE_TEMPLATES } from '@/lib/constants/procedure-templates';

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

import {
  createAppointment,
  type AppointmentView,
} from '@/lib/data/appointments';

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
// ASSISTANT COMMAND ROUTER — text input → intent → side effect
// ---------------------------------------------------------------------------
// Single entry point for the GlobalAIAssistant. Voice path uploads to
// /api/transcribe first, then sends the text here. Text path sends directly.
//
// Pipeline:
//   1. AuthZ + tenant-scoped patient lookup
//   2. Load recent clinical notes (id, title, content snippet) — context
//      that lets the classifier identify "the last note" or "the LESI note".
//   3. GPT-4o-mini classifies intent in JSON mode and (when applicable)
//      picks the target noteId from the provided list.
//   4. Dispatch:
//        create_note     → SOAP-format the command, save as new note
//        edit_note       → fetch note, GPT-rewrite with instructions, save
//        summarize_chart → GPT summarizes the loaded notes
//        chat            → return GPT's reply directly
//
// Returns AssistantResult — the chat UI maps `action` to a confirmation
// chip (e.g., "Created note · view") and `reply` to the message body.
// ===========================================================================

/**
 * Serialized "I'm about to do this — confirm?" payload. Voice mode returns
 * one of these as `action.pending` instead of executing, and the client
 * sends it back via runAssistantConfirmAction once the doctor confirms.
 * Kept narrow + serializable so it can survive a round-trip through React
 * state without weird re-hydration.
 */
export type PendingAssistantWrite =
  | { kind: 'create_note'; dictation: string }
  | { kind: 'edit_note'; noteId: string; noteTitle: string; instructions: string }
  | {
      kind: 'schedule_appointment';
      scheduledAt: string;
      visitType: 'CONSULTATION' | 'FOLLOW_UP' | 'PROCEDURE';
      notes: string | null;
    };

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
  | { type: 'awaiting_confirmation'; pending: PendingAssistantWrite }
  | { type: 'final_report_generated'; reportId: string; title: string }
  | { type: 'chat' };

export type AssistantResult =
  | { ok: true; reply: string; action: AssistantAction }
  | { ok: false; error: string };

const ASSISTANT_ROUTER_SYSTEM_PROMPT = `You are the routing brain of a clinical AI assistant for a pain management physician. You receive a doctor's command and patient context, and you classify the intent into ONE of five buckets and emit STRUCTURED JSON.

Intents:
- "create_note": doctor is dictating a new clinical note (SOAP). Examples: "patient came in for LESI follow-up, doing well…", "Note: 60yo with chronic back pain…".
- "edit_note": doctor wants to modify an existing note. Examples: "update the dosage in the last note", "in the LESI note, change the diagnosis to L5-S1", "fix the typo in note 2".
- "summarize_chart": doctor wants a quick recap. Examples: "summarize the chart", "what's the history?", "give me a brief".
- "generate_document": doctor wants a drafted document derived from clinical notes. Pick documentType from the four supported templates:
    * REFERRAL_LETTER  — referrals to specialists ("write a referral", "refer to neurosurgery")
    * PATIENT_HANDOUT  — post-procedure / educational instructions ("patient handout", "instructions for the patient", "after-care sheet")
    * DISABILITY_FORM  — disability / functional limitations statements ("disability form", "FMLA letter", "work restrictions")
    * PRIOR_AUTH       — letters of medical necessity / prior authorization ("prior auth", "letter of medical necessity", "insurance approval")
  If the doctor says "generate a document" without specifying type, default to REFERRAL_LETTER and surface the choice in chatReply.
- "schedule_appointment": doctor wants to book a visit. Examples: "schedule a follow-up for next Tuesday at 10 AM", "book a procedure on December 3rd at 2pm", "schedule a consult tomorrow morning". You MUST extract:
    * scheduledAt: ISO-8601 string with timezone offset matching CURRENT_DATE_CONTEXT below. For relative dates ("next Tuesday", "tomorrow"), compute from the provided current date. If only a date is given without a time, default to 09:00 local. If only a time is given without a date, default to today (or tomorrow if the time has already passed today).
    * visitType: one of CONSULTATION, FOLLOW_UP, PROCEDURE. Map natural language: "consult"/"new patient"/"intake" → CONSULTATION, "procedure"/"injection"/"PRP"/"LESI"/"CESI" → PROCEDURE, otherwise → FOLLOW_UP.
    * appointmentNotes: short free-text note if the doctor mentioned a reason ("3rd LESI follow-up", "to review imaging"), else null.
  If you cannot extract a clear scheduledAt, classify as "chat" and ask in chatReply.
- "chat": general medical question or conversation that doesn't fit the above. Examples: "what's the difference between LESI and CESI?", "how long does PRP take to work?".

For "edit_note": you MUST set targetNoteId to one of the IDs from the provided notes list. If the doctor says "the last note", pick the FIRST note in the list (it is sorted newest-first). If you cannot identify a target, classify as "chat" instead and ask which note in chatReply.

Field rules per intent:
- "create_note": leave non-applicable fields null.
- "edit_note": set targetNoteId and editInstructions (the doctor's instructions, paraphrased clearly).
- "summarize_chart": leave non-applicable fields null.
- "generate_document": set documentType to one of the four enum values above.
- "schedule_appointment": set scheduledAt (ISO 8601 with offset), visitType, optionally appointmentNotes.
- "chat": set chatReply to your medical answer (concise, 1–3 sentences).

OUTPUT — return ONLY a single JSON object, no prose, no code fences:
{
  "intent": "create_note" | "edit_note" | "summarize_chart" | "generate_document" | "schedule_appointment" | "chat",
  "targetNoteId": string | null,
  "editInstructions": string | null,
  "documentType": "REFERRAL_LETTER" | "PATIENT_HANDOUT" | "DISABILITY_FORM" | "PRIOR_AUTH" | null,
  "scheduledAt": string | null,
  "visitType": "CONSULTATION" | "FOLLOW_UP" | "PROCEDURE" | null,
  "appointmentNotes": string | null,
  "chatReply": string | null
}`;

const SUMMARIZE_SYSTEM_PROMPT = `You summarize a patient's clinical notes for a pain management physician. Output 3–5 sentences in plain prose: key conditions, recent procedures, current treatment plan, and any open concerns. No bullets, no markdown, no preamble — start directly with the summary.`;

interface RouterDecision {
  intent:
    | 'create_note'
    | 'edit_note'
    | 'summarize_chart'
    | 'generate_document'
    | 'schedule_appointment'
    | 'chat';
  targetNoteId: string | null;
  editInstructions: string | null;
  documentType: DocumentType | null;
  scheduledAt: string | null;
  visitType: 'CONSULTATION' | 'FOLLOW_UP' | 'PROCEDURE' | null;
  appointmentNotes: string | null;
  chatReply: string | null;
}

export interface RunAssistantOptions {
  /** Voice mode default. When true, write intents (create_note / edit_note /
   *  schedule_appointment) return `awaiting_confirmation` with a serialized
   *  pending payload instead of executing. The client speaks the proposal,
   *  collects "yes", and round-trips through runAssistantConfirmAction.
   *  Reads (summarize_chart / chat / generate_document) execute either way —
   *  they're either reversible or read-only. */
  confirmWrites?: boolean;
}

export async function runAssistantCommandAction(
  patientId: string,
  command: string,
  options: RunAssistantOptions = {}
): Promise<AssistantResult> {
  // 1. AuthZ
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    if (err instanceof AuthError) return { ok: false, error: err.message };
    return { ok: false, error: 'Authentication failed.' };
  }

  // 2. Tenant-scoped patient lookup
  const patient = await getPatientById(patientId, session);
  if (!patient) return { ok: false, error: 'Patient not found.' };

  const trimmed = command.trim();
  if (!trimmed) return { ok: false, error: 'Command is empty.' };

  // 3. Recent notes for the classifier — sorted newest-first by the data layer.
  const notes = await dataListNotesByPatient(patientId, 'CLINICAL_NOTE', session);
  const recentNotes = notes.slice(0, 5);
  const noteIndex = recentNotes
    .map((n, i) => {
      const snippet = (n.content ?? '').replace(/\s+/g, ' ').slice(0, 120);
      return `[${i + 1}] id=${n.id} | title="${n.title}" | created=${n.createdAt.split('T')[0]} | snippet="${snippet}…"`;
    })
    .join('\n');

  // 4. Classify intent
  const openai = getOpenAI();
  let decision: RouterDecision;
  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0.1,
      response_format: { type: 'json_object' },
      messages: [
        { role: 'system', content: ASSISTANT_ROUTER_SYSTEM_PROMPT },
        {
          role: 'user',
          content: `CURRENT_DATE_CONTEXT: ${new Date().toISOString()} (use this to resolve relative dates like "next Tuesday")\n\nPatient: ${patient.firstName} ${patient.lastName} (born ${patient.birthYear}, status ${patient.status})\n\nRecent notes (newest first):\n${noteIndex || '(none)'}\n\nDoctor's command:\n${trimmed}`,
        },
      ],
    });
    logGptToolUsage(completion, session);
    const raw = completion.choices[0]?.message?.content ?? '{}';
    decision = JSON.parse(raw) as RouterDecision;
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Routing failed';
    return { ok: false, error: `Could not understand command: ${message}` };
  }

  // 5. Dispatch. In voice mode, writes propose-then-confirm; reads execute
  //    immediately. Reads are either read-only (chat/summarize) or reversible
  //    (generate_document — drafts a doc, doesn't persist), so they don't
  //    need a confirmation gate.
  switch (decision.intent) {
    case 'create_note':
      if (options.confirmWrites) {
        return proposeCreateNote(trimmed);
      }
      return dispatchCreateNote(patient, trimmed, openai, session);
    case 'edit_note':
      if (options.confirmWrites) {
        return proposeEditNote(
          decision.targetNoteId,
          decision.editInstructions ?? trimmed,
          recentNotes
        );
      }
      return dispatchEditNote(
        patient,
        decision.targetNoteId,
        decision.editInstructions ?? trimmed,
        openai,
        session
      );
    case 'summarize_chart':
      return dispatchSummarize(patient, recentNotes, openai, session);
    case 'generate_document':
      return dispatchGenerateDocument(patient.id, decision.documentType);
    case 'schedule_appointment':
      if (options.confirmWrites) {
        return proposeScheduleAppointment(
          decision.scheduledAt,
          decision.visitType,
          decision.appointmentNotes
        );
      }
      return dispatchScheduleAppointment(
        patient,
        decision.scheduledAt,
        decision.visitType,
        decision.appointmentNotes,
        session
      );
    case 'chat':
    default:
      return {
        ok: true,
        reply: decision.chatReply ?? 'Sorry — could you rephrase that?',
        action: { type: 'chat' },
      };
  }
}

// ===========================================================================
// PROPOSE — voice-mode handlers that return awaiting_confirmation instead
// of executing. Each returns a spoken reply describing the action and a
// `pending` payload the client round-trips back via runAssistantConfirmAction.
// ===========================================================================

function proposeCreateNote(dictation: string): AssistantResult {
  // Short prompt — TTS latency scales with output length. Doctor sees the
  // dictation preview on screen via the pending chip.
  return {
    ok: true,
    reply: 'Save this as a clinical note? Say yes.',
    action: {
      type: 'awaiting_confirmation',
      pending: { kind: 'create_note', dictation },
    },
  };
}

function proposeEditNote(
  targetNoteId: string | null,
  instructions: string,
  recentNotes: ClinicalNoteView[]
): AssistantResult {
  if (!targetNoteId) {
    return {
      ok: true,
      reply: 'Which note should I edit? Try "edit the last note" or name the note.',
      action: { type: 'chat' },
    };
  }
  const target = recentNotes.find((n) => n.id === targetNoteId);
  if (!target) {
    return {
      ok: false,
      error: 'Could not find that note to edit.',
    };
  }
  return {
    ok: true,
    reply: `Edit "${target.title}"? Say yes.`,
    action: {
      type: 'awaiting_confirmation',
      pending: {
        kind: 'edit_note',
        noteId: targetNoteId,
        noteTitle: target.title,
        instructions,
      },
    },
  };
}

function proposeScheduleAppointment(
  scheduledAtIso: string | null,
  visitType: 'CONSULTATION' | 'FOLLOW_UP' | 'PROCEDURE' | null,
  notes: string | null
): AssistantResult {
  if (!scheduledAtIso) {
    return {
      ok: true,
      reply: 'When should I schedule it? Give me a date and time.',
      action: { type: 'chat' },
    };
  }
  const scheduledAt = new Date(scheduledAtIso);
  if (Number.isNaN(scheduledAt.getTime())) {
    return { ok: false, error: `Could not parse date/time: ${scheduledAtIso}` };
  }
  const resolvedType = visitType ?? 'FOLLOW_UP';
  const friendly = scheduledAt.toLocaleString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
  return {
    ok: true,
    reply: `Schedule ${resolvedType.toLowerCase().replace('_', ' ')} for ${friendly}? Say yes.`,
    action: {
      type: 'awaiting_confirmation',
      pending: {
        kind: 'schedule_appointment',
        scheduledAt: scheduledAtIso,
        visitType: resolvedType,
        notes,
      },
    },
  };
}

// ===========================================================================
// CONFIRM — execute a previously-proposed pending write. Voice client calls
// this after the doctor says "yes" / "confirm" / etc. AuthZ + tenant + audit
// chain mirrors the regular dispatch path; the propose step's payload is
// the only state that crosses the wire.
// ===========================================================================

export async function runAssistantConfirmAction(
  patientId: string,
  pending: PendingAssistantWrite
): Promise<AssistantResult> {
  let session;
  try {
    session = await requireRole(['DOCTOR', 'ADMIN']);
  } catch (err) {
    if (err instanceof AuthError) return { ok: false, error: err.message };
    return { ok: false, error: 'Authentication failed.' };
  }

  const patient = await getPatientById(patientId, session);
  if (!patient) return { ok: false, error: 'Patient not found.' };

  const openai = getOpenAI();

  switch (pending.kind) {
    case 'create_note':
      return dispatchCreateNote(patient, pending.dictation, openai, session);
    case 'edit_note':
      return dispatchEditNote(
        patient,
        pending.noteId,
        pending.instructions,
        openai,
        session
      );
    case 'schedule_appointment':
      return dispatchScheduleAppointment(
        patient,
        pending.scheduledAt,
        pending.visitType,
        pending.notes,
        session
      );
  }
}

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
  openai: OpenAI,
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

  let updatedContent: string;
  try {
    const completion = await openai.chat.completions.create({
      model: 'gpt-4o-mini',
      temperature: 0.2,
      messages: [
        { role: 'system', content: EDIT_NOTE_SYSTEM_PROMPT },
        {
          role: 'user',
          content: `EXISTING NOTE:\n${existing.content}\n\nDOCTOR'S EDIT INSTRUCTIONS:\n${instructions}`,
        },
      ],
    });
    logGptToolUsage(completion, session);
    updatedContent = (completion.choices[0]?.message?.content ?? '').trim();
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Edit failed';
    return { ok: false, error: `Edit failed: ${message}` };
  }
  if (!updatedContent) return { ok: false, error: 'AI returned an empty result — please try again.' };

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

const uploadPatientFileSchema = z.object({
  // Loose ID format — the real authz is the getPatientById tenant guard
  // below. z.string().cuid() was rejecting valid Prisma IDs in some
  // environments and surfacing as a confusing "metadata error" to the
  // doctor.
  patientId: z.string().min(1).max(50),
  fileName: z.string().min(1).max(255),
  mimeType: z.string().min(1).max(100),
  sizeBytes: z.number().int().min(1).max(25 * 1024 * 1024), // 25 MB cap
});

export async function uploadPatientFileAction(
  rawInput: unknown
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

  const parsed = uploadPatientFileSchema.safeParse(rawInput);
  if (!parsed.success) {
    // Surface the first real Zod issue so "Invalid file metadata" doesn't
    // hide what actually failed validation.
    const first = parsed.error.issues[0];
    const detail = first ? `${first.path.join('.')}: ${first.message}` : 'Unknown';
    return {
      ok: false,
      error: `Invalid file metadata — ${detail}`,
      fieldErrors: parsed.error.flatten().fieldErrors,
    };
  }
  const { patientId, fileName, mimeType, sizeBytes } = parsed.data;

  // Tenant guard — patient must be visible to this session. getPatientById
  // returns null both for "doesn't exist" and "forbidden", which is the
  // right behavior here (don't leak existence to other tenants).
  const patient = await getPatientById(patientId, session);
  if (!patient) {
    return { ok: false, error: 'Patient not found' };
  }

  try {
    const file = await dataCreatePatientFile({
      patientId,
      fileName,
      mimeType,
      sizeBytes,
      createdById: session.user.id,
    });

    await logAudit({
      action: 'CREATED_DOCUMENT',
      targetId: file.id,
      targetType: 'Document',
      metadata: {
        category: 'PATIENT_FILE',
        patientId,
        fileName,
        mimeType,
        sizeBytes,
      },
    });

    revalidatePath(`/dashboard/patients/${patientId}`);
    return { ok: true, data: file };
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Upload failed';
    await logAudit({
      action: 'CREATED_DOCUMENT',
      success: false,
      errorCode: 'UPLOAD_FAILED',
      metadata: { category: 'PATIENT_FILE', patientId, reason: message },
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
