// ============================================================================
// Realtime tool definitions — what the gpt-4o-realtime model can call
// ----------------------------------------------------------------------------
// These schemas are passed to OpenAI when minting a Realtime session. The
// model decides on its own when to call them based on the doctor's voice
// commands. Each tool's `name` corresponds to a case in /api/assistant-tool
// which runs the actual server action with full auth + tenant + audit.
//
// Design rules:
//   - Keep argument schemas tight — fewer optional fields = fewer ways the
//     model can hallucinate. If a field is required clinically, mark it
//     required in the JSON schema so the model can't omit it.
//   - Descriptions are read by the model; write them like API docs targeted
//     at a careful clinician AI. They influence which tool gets called and
//     what arguments are extracted.
//   - The model is instructed (via the system prompt) to ALWAYS confirm
//     before calling write tools. Schemas don't enforce that — the system
//     prompt does. We trust the prompt + audit log, not the schema.
// ============================================================================

import type { PatientView } from '@/lib/data/patients';
import type { ClinicalNoteView } from '@/lib/data/clinical-notes';
import type { AppointmentView } from '@/lib/data/appointments';
import { enrichNoteLine } from './intelligence';

export interface RealtimeTool {
  type: 'function';
  name: string;
  description: string;
  parameters: {
    type: 'object';
    properties: Record<string, unknown>;
    required?: string[];
    additionalProperties?: boolean;
  };
}

export const REALTIME_TOOLS: RealtimeTool[] = [
  {
    type: 'function',
    name: 'create_clinical_note',
    description:
      "Save a new clinical note for the current patient. Use when the doctor dictates a SOAP-style note or any narrative clinical observation. The dictation argument is the doctor's raw speech — the server runs it through SOAP formatting before saving. Execute immediately — do NOT ask for confirmation.",
    parameters: {
      type: 'object',
      properties: {
        dictation: {
          type: 'string',
          description:
            "The doctor's full dictation in their own words. Do not summarize or rephrase — pass through verbatim. The server formats into SOAP only when the dictation contains multiple clinical domains; short paragraphs stay as natural prose.",
        },
      },
      required: ['dictation'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'read_clinical_note',
    description:
      "Fetch the FULL TEXT of a clinical note so you can read it, quote from it, or apply precise edits. Pick `noteId` from RECENT_NOTES. Read-only — no confirmation needed. Use before any complex edit where you need the current contents.",
    parameters: {
      type: 'object',
      properties: {
        noteId: { type: 'string', description: 'ID of the clinical note, from RECENT_NOTES.' },
      },
      required: ['noteId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'read_custom_procedure',
    description:
      "Fetch the FULL TEXT of an uploaded custom procedure (the extracted content of the PDF/DOCX the doctor attached). Pick `procedureId` from CUSTOM_PROCEDURES. Read-only — no confirmation needed. Use before any complex edit where you need the current contents, or when the doctor asks you to describe / read / look at the document.",
    parameters: {
      type: 'object',
      properties: {
        procedureId: { type: 'string', description: 'ID of the custom procedure, from CUSTOM_PROCEDURES.' },
      },
      required: ['procedureId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'edit_clinical_note',
    description:
      'Modify an existing CLINICAL NOTE (SOAP/dictated note). Pick `noteId` from RECENT_NOTES in the system context. Execute immediately — do NOT ask for confirmation. "The last note" = the FIRST entry in RECENT_NOTES (sorted newest-first). Use edit_custom_procedure instead if the doctor refers to an uploaded procedure document.',
    parameters: {
      type: 'object',
      properties: {
        noteId: {
          type: 'string',
          description: 'ID of the clinical note to edit, taken from RECENT_NOTES in the session context.',
        },
        instructions: {
          type: 'string',
          description:
            "Clear paraphrased description of what to change. e.g. 'Add ibuprofen 400mg PRN to plan section', 'Change L4-L5 to L5-S1 in assessment'.",
        },
      },
      required: ['noteId', 'instructions'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'edit_custom_procedure',
    description:
      'Modify an UPLOADED CUSTOM PROCEDURE document (PDF/DOCX the doctor previously attached). Pick `procedureId` from CUSTOM_PROCEDURES in the system context. Execute immediately — do NOT ask for confirmation. Use this — NOT edit_clinical_note — when the doctor refers to a procedure document, attached file, uploaded protocol, etc.',
    parameters: {
      type: 'object',
      properties: {
        procedureId: {
          type: 'string',
          description: 'ID of the custom procedure to edit, taken from CUSTOM_PROCEDURES in the session context.',
        },
        instructions: {
          type: 'string',
          description:
            "Clear paraphrased description of what to change. e.g. 'Add a section about post-procedure care', 'Change the sedation dose from 2mg to 4mg'.",
        },
      },
      required: ['procedureId', 'instructions'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'delete_clinical_note',
    description:
      "Soft-delete a CLINICAL NOTE (SOAP/dictated). Record stays in the audit log per HIPAA; note disappears from active views. Pick `noteId` from RECENT_NOTES in context. Execute immediately. Use delete_custom_procedure instead for uploaded procedure documents.",
    parameters: {
      type: 'object',
      properties: {
        noteId: { type: 'string', description: 'ID of the clinical note to delete, from RECENT_NOTES.' },
      },
      required: ['noteId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'delete_custom_procedure',
    description:
      'Soft-delete an UPLOADED CUSTOM PROCEDURE. Pick `procedureId` from CUSTOM_PROCEDURES in context. Execute immediately. Record stays in the audit log per HIPAA; procedure disappears from active views.',
    parameters: {
      type: 'object',
      properties: {
        procedureId: { type: 'string', description: 'ID of the custom procedure to delete, from CUSTOM_PROCEDURES.' },
      },
      required: ['procedureId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'cancel_appointment',
    description:
      "Cancel/soft-delete an EXISTING APPOINTMENT. Pick `appointmentId` from UPCOMING_APPOINTMENTS in context. Execute immediately. Appointment disappears from the calendar but stays in the audit log.",
    parameters: {
      type: 'object',
      properties: {
        appointmentId: { type: 'string', description: 'ID of the appointment to cancel, from UPCOMING_APPOINTMENTS.' },
      },
      required: ['appointmentId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'archive_patient',
    description:
      "Archive the current patient (soft-delete, HIPAA-preserved). Use when the doctor says 'archive this patient', 'remove from active list', etc. Execute immediately. The patient record is retained; they disappear from the active patients list.",
    parameters: {
      type: 'object',
      properties: {},
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'schedule_appointment',
    description:
      "Book a future visit for the current patient. Execute immediately — do NOT ask for confirmation. Resolve relative dates ('next Tuesday', 'tomorrow') from the current_date provided in the session context.",
    parameters: {
      type: 'object',
      properties: {
        scheduledAt: {
          type: 'string',
          description:
            "ISO-8601 timestamp with timezone offset matching the session's current_date. Required. If the doctor gives only a date, default to 09:00 local. If only a time, default to today (or tomorrow if the time has passed).",
        },
        visitType: {
          type: 'string',
          enum: ['CONSULTATION', 'FOLLOW_UP', 'PROCEDURE'],
          description:
            'CONSULTATION = new patient / intake. PROCEDURE = injection/LESI/CESI/PRP. Default to FOLLOW_UP for routine visits.',
        },
        notes: {
          type: 'string',
          description:
            "Optional short reason or context, e.g. '3rd LESI follow-up', 'review imaging'. Pass null/omit if the doctor didn't mention one.",
        },
      },
      required: ['scheduledAt', 'visitType'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'summarize_chart',
    description:
      "Generate a 3-5 sentence brief of the patient's recent clinical notes for visit prep. Read-only — no confirmation needed before calling. Speak the summary back to the doctor when the tool returns.",
    parameters: {
      type: 'object',
      properties: {},
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'request_file_upload',
    description:
      "Open the file picker so the doctor can attach a procedure document (PDF or DOCX) to the patient's Custom Procedures. Use when the doctor says 'attach a file', 'upload procedure', 'add a referral document', etc. The browser opens the file picker; YOU then tell the doctor to pick the file. After they pick + upload, you'll receive a follow-up user message naming the file — confirm aloud.",
    parameters: {
      type: 'object',
      properties: {
        reason: {
          type: 'string',
          description:
            "Brief context for the upload, e.g. 'LESI procedure document', 'referral letter from neurology'. Helps you confirm what was attached.",
        },
      },
      required: ['reason'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'update_patient',
    description:
      "Update editable fields on the patient record — including brief history, profile fields (name, contact, MRN, chart ID, birth year), tags, status, and insurance flag. Execute immediately — do NOT ask for confirmation. Send ONLY the fields you want to change. For briefHistory: send the FULL updated list (existing entries you want to keep PLUS new ones); the server replaces the whole array. The current values are in the system context — use them to preserve what shouldn't change.",
    parameters: {
      type: 'object',
      properties: {
        firstName: { type: 'string', description: "Patient's first name. Only send when actually changing." },
        lastName: { type: 'string', description: "Patient's last name. Only send when actually changing." },
        mrn: { type: 'string', description: 'Medical record number for insurance filings.' },
        chartId: { type: 'string', description: "Practice-internal chart number (e.g. C-1042)." },
        birthYear: { type: 'integer', minimum: 1900, maximum: 2100, description: 'Year only; HIPAA Safe Harbor — never full DOB.' },
        email: { type: 'string', description: "Patient's email address." },
        cellPhone: { type: 'string', description: 'Cell phone, free-format (digits, spaces, dashes, parens).' },
        homePhone: { type: 'string', description: 'Home phone, free-format.' },
        tags: { type: 'array', items: { type: 'string' }, description: 'Replace the whole tags list. Include existing tags to keep.' },
        status: { type: 'string', enum: ['ACTIVE', 'INACTIVE', 'ARCHIVED'], description: "Patient's CRM status." },
        insuranceVerified: { type: 'boolean', description: 'Insurance verification flag.' },
        briefHistory: {
          type: 'array',
          items: { type: 'string' },
          description:
            "Patient's running clinical history bullets. REPLACE-SEMANTICS: send the FULL list (existing entries the doctor wants to keep + any new ones). Never send a list that omits existing entries unless the doctor explicitly asks to remove them.",
        },
        sex: {
          type: 'string',
          enum: ['UNKNOWN', 'MALE', 'FEMALE', 'OTHER'],
          description:
            "Biological sex — clinical context only. Set only on direct statement from the doctor (\"mark as female\", \"set sex to male\"). Don't infer from pronouns.",
        },
        addressLine1: { type: 'string', description: 'Street address line 1 (e.g., "5325 New Castle Ave").' },
        addressLine2: { type: 'string', description: 'Apt / suite / unit, optional.' },
        city: { type: 'string', description: 'City name.' },
        state: { type: 'string', description: 'US 2-letter state code ("CA"). Spell out → abbreviate (California → CA).' },
        postalCode: { type: 'string', description: 'ZIP / postal code.' },
        pharmacyName: { type: 'string', description: 'Preferred pharmacy name + location, e.g. "CVS on Market Street".' },
        pharmacyPhone: { type: 'string', description: "Pharmacy phone, free-format — same rules as cellPhone." },
        assignedDoctorId: {
          type: 'string',
          description:
            "User ID of the assigned provider. ONLY set this if you have an actual cuid — do NOT pass a name here. If the doctor says 'assign to Dr. Smith', you cannot resolve the name to an ID from voice, so acknowledge verbally but leave this alone; the doctor can re-assign from the Edit modal.",
        },
      },
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'generate_document',
    description:
      'Draft a clinical document (referral letter, patient handout, disability form, prior auth letter) from the patient\'s recent notes. Read-only — no confirmation needed; the doc is a draft, not persisted. Tell the doctor it\'s drafted and visible in the panel when the tool returns.',
    parameters: {
      type: 'object',
      properties: {
        documentType: {
          type: 'string',
          enum: ['REFERRAL_LETTER', 'PATIENT_HANDOUT', 'DISABILITY_FORM', 'PRIOR_AUTH'],
          description:
            'Pick by the doctor\'s phrasing: "referral" → REFERRAL_LETTER, "instructions"/"handout" → PATIENT_HANDOUT, "disability"/"FMLA" → DISABILITY_FORM, "prior auth"/"medical necessity" → PRIOR_AUTH.',
        },
      },
      required: ['documentType'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'read_patient_file',
    description:
      "Fetch details and extracted text (if any) of an attached file. Pick `fileId` from ATTACHED_FILES. Read-only — no confirmation. Image files have metadata only (filename, mime, size) until OCR lands; PDF/DOCX uploads return their extracted text.",
    parameters: {
      type: 'object',
      properties: {
        fileId: { type: 'string', description: 'ID of the attached file, from ATTACHED_FILES.' },
      },
      required: ['fileId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'delete_patient_file',
    description:
      "Soft-delete an attached file. Pick `fileId` from ATTACHED_FILES. Execute immediately. Record stays in audit log per HIPAA; file disappears from active views.",
    parameters: {
      type: 'object',
      properties: {
        fileId: { type: 'string', description: 'ID of the attached file, from ATTACHED_FILES.' },
      },
      required: ['fileId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'read_final_report',
    description:
      'Fetch the FULL TEXT of a final report so you can read it, quote from it, or apply precise edits. Pick `reportId` from FINAL_REPORTS. Read-only — no confirmation needed. Use before any complex edit where you need the current contents.',
    parameters: {
      type: 'object',
      properties: {
        reportId: { type: 'string', description: 'ID of the final report, from FINAL_REPORTS.' },
      },
      required: ['reportId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'edit_final_report',
    description:
      'Modify an existing FINAL REPORT. Pick `reportId` from FINAL_REPORTS in the system context. Execute immediately — do NOT ask for confirmation. Use this — NOT edit_custom_procedure — when the doctor refers to the final report, discharge summary, case summary, etc.',
    parameters: {
      type: 'object',
      properties: {
        reportId: {
          type: 'string',
          description: 'ID of the final report to edit, taken from FINAL_REPORTS in the session context.',
        },
        instructions: {
          type: 'string',
          description:
            "Specific edit instructions in natural language. Be concrete: quote the exact current phrasing to replace, and the new wording. The server model rewrites precisely — don't send vague 'make it better'.",
        },
      },
      required: ['reportId', 'instructions'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'delete_final_report',
    description:
      'Soft-delete a FINAL REPORT. Pick `reportId` from FINAL_REPORTS in context. Execute immediately. Record stays in the audit log per HIPAA; report disappears from active views.',
    parameters: {
      type: 'object',
      properties: {
        reportId: { type: 'string', description: 'ID of the final report to delete, from FINAL_REPORTS.' },
      },
      required: ['reportId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'generate_final_report',
    description:
      'Synthesize a comprehensive Final Evaluation Report from the patient\'s brief history, clinical notes, and procedure documents. Saved as a DRAFT final report on the chart. Use when the doctor says "generate a final report", "write the discharge summary", "compose the case summary", or similar. No arguments — everything comes from the patient record.',
    parameters: {
      type: 'object',
      properties: {},
      additionalProperties: false,
    },
  },
  // === CLINICAL SAFETY: allergies + medications ===
  {
    type: 'function',
    name: 'add_allergy',
    description:
      'Record a drug, food, or environmental allergy for this patient. Execute immediately — do NOT ask for confirmation. If the patient currently has NKA (No Known Allergies) set, adding an allergy automatically clears the NKA flag.',
    parameters: {
      type: 'object',
      properties: {
        allergen: { type: 'string', description: 'What the patient is allergic to (e.g. "Penicillin", "Latex", "NSAIDs", "Sulfa drugs").' },
        reaction: { type: 'string', description: 'Observed reaction (e.g. "anaphylaxis", "hives", "GI upset"). Optional — some allergies are patient-reported without reaction detail.' },
        severity: { type: 'string', enum: ['UNKNOWN', 'MILD', 'MODERATE', 'SEVERE'], description: 'Severity. SEVERE triggers a red banner on the chart. Default UNKNOWN if not stated.' },
      },
      required: ['allergen'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'remove_allergy',
    description:
      'Remove an allergy from the patient\'s chart (soft-delete — audit trail preserved). Pick allergyId from the ALLERGIES list in the system context. Execute immediately.',
    parameters: {
      type: 'object',
      properties: {
        allergyId: { type: 'string', description: 'ID of the allergy to remove (from the ALLERGIES list).' },
      },
      required: ['allergyId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'add_medication',
    description:
      'Add an active medication to the patient\'s chart. Execute immediately — do NOT ask for confirmation.',
    parameters: {
      type: 'object',
      properties: {
        name: { type: 'string', description: 'Drug name — brand or generic, doctor\'s choice (e.g. "Gabapentin", "Oxycodone", "Meloxicam").' },
        dosage: { type: 'string', description: 'Dose strength + form (e.g. "300mg", "5mg tablet", "0.5%"). Optional.' },
        frequency: { type: 'string', description: 'Frequency / schedule (e.g. "twice daily", "PRN", "q6h", "at bedtime"). Optional.' },
      },
      required: ['name'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'remove_medication',
    description:
      'Remove a medication from the patient\'s chart entirely (soft-delete). Pick medicationId from the MEDICATIONS list. Use this for corrections ("that was wrong, remove it"). For stopping a med the patient was actually taking, prefer toggle_medication_active instead — that preserves the history.',
    parameters: {
      type: 'object',
      properties: {
        medicationId: { type: 'string', description: 'ID of the medication to remove (from the MEDICATIONS list).' },
      },
      required: ['medicationId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'toggle_medication_active',
    description:
      'Stop or resume a medication. Stopped meds stay on the chart as historical records but show as inactive. Use when the doctor says "stop the gabapentin", "discontinue oxycodone", "resume the meloxicam", etc. Pick medicationId from the MEDICATIONS list.',
    parameters: {
      type: 'object',
      properties: {
        medicationId: { type: 'string', description: 'ID of the medication to toggle (from the MEDICATIONS list).' },
      },
      required: ['medicationId'],
      additionalProperties: false,
    },
  },
  {
    type: 'function',
    name: 'set_nka',
    description:
      'Mark or unmark "No Known Allergies" on the patient. Set value=true when the doctor confirms the patient has no allergies. Setting NKA while allergies exist is blocked server-side — remove the allergies first.',
    parameters: {
      type: 'object',
      properties: {
        value: { type: 'boolean', description: 'true = patient confirmed no known allergies. false = unmark NKA.' },
      },
      required: ['value'],
      additionalProperties: false,
    },
  },
];

/**
 * Build the per-session system prompt. Includes patient context + recent
 * note titles so the model can route edit_note correctly.
 *
 * Kept tight — every extra word costs latency. The model sees this once at
 * session start and doesn't re-read it per turn.
 */
export function buildSystemPrompt(input: {
  patient: PatientView;
  recentNotes: ClinicalNoteView[];
  customProcedures: ClinicalNoteView[];
  finalReports: ClinicalNoteView[];
  patientFiles: ClinicalNoteView[];
  upcomingAppointments: AppointmentView[];
  currentDateIso: string;
  /** IANA tz, e.g. "America/Los_Angeles". Defaults to UTC. */
  timezone?: string;
  /** One-line AI-synthesized trajectory so the model doesn't have to
   *  read five notes to answer "where are we with her?" */
  clinicalTrajectory?: string;
  /** Recent audit rows on this patient — cross-visit memory. */
  recentAiActions?: string[];
  /** Patient's recorded allergies (from the Allergy table). */
  allergies?: { id: string; allergen: string; reaction: string | null; severity: string }[];
  /** Patient's active medications (from the Medication table). */
  medications?: { id: string; name: string; dosage: string | null; frequency: string | null; isActive: boolean }[];
  /** Whether the patient has been explicitly marked "No Known Allergies". */
  noKnownAllergies?: boolean;
}): string {
  const {
    patient,
    recentNotes,
    customProcedures,
    finalReports,
    patientFiles,
    upcomingAppointments,
    currentDateIso,
    timezone = 'UTC',
    clinicalTrajectory = '',
    recentAiActions = [],
    allergies = [],
    medications = [],
    noKnownAllergies = false,
  } = input;

  // Pre-format the current moment IN THE USER'S TZ so the model sees a
  // "now" that matches the doctor's clock. Also emit a sample local-offset
  // ISO string the model can mimic when constructing scheduledAt.
  const now = new Date(currentDateIso);
  const localHumanNow = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    dateStyle: 'full',
    timeStyle: 'short',
  }).format(now);
  const localOffsetIso = toLocalOffsetIso(now, timezone);
  // Lists are enriched with a short semantic hint per row (#3) so voice
  // phrasings like "edit the back injection note" can match LESI even
  // when the title doesn't contain "back". Cap raised from 5 → 10 (#2).
  const noteList =
    recentNotes.length === 0
      ? '(no prior notes)'
      : recentNotes
          .slice(0, 10)
          .map((n, i) => `  ${i + 1}.${enrichNoteLine(n)}`)
          .join('\n');
  const procedureList =
    customProcedures.length === 0
      ? '(no uploaded procedures)'
      : customProcedures
          .slice(0, 10)
          .map((p, i) => `  ${i + 1}.${enrichNoteLine(p)}`)
          .join('\n');
  // Final reports — both AI-generated syntheses and uploaded report files
  // live here. The model uses these IDs to route edit_final_report /
  // delete_clinical_note correctly when the doctor says "the final
  // report" (vs. notes or procedures).
  const finalReportList =
    finalReports.length === 0
      ? '(no final reports)'
      : finalReports
          .slice(0, 10)
          .map(
            (r, i) =>
              `  ${i + 1}. id="${r.id}" title="${r.title}" created=${r.createdAt.split('T')[0]}${r.fileName ? ' (uploaded file)' : ' (AI-generated)'}`
          )
          .join('\n');
  const attachedFileList =
    patientFiles.length === 0
      ? '(no attached files)'
      : patientFiles
          .slice(0, 10)
          .map(
            (f, i) =>
              `  ${i + 1}. id="${f.id}" name="${f.fileName ?? f.title}"${f.mimeType ? ` (${f.mimeType})` : ''} uploaded=${f.createdAt.split('T')[0]}`
          )
          .join('\n');
  const appointmentList =
    upcomingAppointments.length === 0
      ? '(no upcoming appointments)'
      : upcomingAppointments
          .slice(0, 5)
          .map((a, i) => {
            const when = new Date(a.scheduledAt).toLocaleString('en-US', {
              weekday: 'short',
              month: 'short',
              day: 'numeric',
              hour: 'numeric',
              minute: '2-digit',
            });
            return `  ${i + 1}. id="${a.id}" ${a.type.toLowerCase().replace('_', ' ')} @ ${when} status=${a.status}`;
          })
          .join('\n');

  // Brief history snapshot — the AI needs the FULL current list so it can
  // preserve entries when adding new ones (briefHistory is replace-semantic
  // on update_patient).
  const briefHistoryList =
    !patient.briefHistory || patient.briefHistory.length === 0
      ? '(empty)'
      : patient.briefHistory.map((line, i) => `  ${i + 1}. ${line}`).join('\n');

  // Profile snapshot — current values so the AI knows what to preserve when
  // calling update_patient. Don't echo PHI back to the doctor unprompted.
  // Only include fields that have a value so the prompt stays compact
  // (every token costs Realtime-voice latency).
  const addressParts = [
    patient.addressLine1,
    patient.addressLine2,
    [patient.city, patient.state].filter(Boolean).join(', '),
    patient.postalCode,
  ]
    .filter(Boolean)
    .join(' · ');
  const profileLines = [
    `  mrn: ${patient.mrn || '(none)'}`,
    `  chartId: ${patient.chartId || '(none)'}`,
    `  email: ${patient.email || '(none)'}`,
    `  cellPhone: ${patient.cellPhone || '(none)'}`,
    `  homePhone: ${patient.homePhone || '(none)'}`,
    `  sex: ${patient.sex && patient.sex !== 'UNKNOWN' ? patient.sex : '(not specified)'}`,
    `  address: ${addressParts || '(none)'}`,
    `  pharmacy: ${patient.pharmacyName || '(none)'}${patient.pharmacyPhone ? ` [${patient.pharmacyPhone}]` : ''}`,
    `  assignedDoctor: ${patient.assignedDoctor || '(unassigned)'}`,
    `  insuranceVerified: ${patient.insuranceVerified === undefined ? '(unknown)' : String(patient.insuranceVerified)}`,
    `  tags: [${(patient.tags ?? []).join(', ')}]`,
  ].join('\n');

  return `You are a calm, concise clinical voice assistant for a pain management physician. You speak with the doctor while they work — keep replies SHORT (one sentence when possible) so they can stay focused on the patient.

USER_TIMEZONE: ${timezone}
CURRENT_TIME_LOCAL: ${localHumanNow}
CURRENT_TIME_ISO: ${localOffsetIso}   (this is "now" expressed with the local offset — MIMIC this offset when emitting scheduledAt)

TIMESTAMP RULES — READ CAREFULLY:
- When you emit a scheduledAt value, ALWAYS use an ISO-8601 string with the OFFSET from CURRENT_TIME_ISO above (e.g., "2026-04-15T10:00:00${localOffsetIso.slice(-6)}").
- NEVER emit a bare "Z" (UTC). If you do, the appointment will save at the wrong hour because the model and the doctor are not on the same clock.
- Resolve relative dates from CURRENT_TIME_LOCAL — "tomorrow at 10 AM" = tomorrow's date at 10:00:00 in USER_TIMEZONE, then serialized with the local offset.

DELIVERY GUIDELINES:
- Speak at a measured, confident clinical pace. Not rushed, not slow.
- Enunciate medical terminology crisply — doctors depend on unambiguous pronunciation.
- Pronunciation cheatsheet (follow these when speaking these terms):
    LESI  → "ell-ee-ess-eye"
    CESI  → "see-ee-ess-eye"
    PRP   → "pee-are-pee"
    LFB   → "ell-eff-bee"
    L4-L5 → "L four L five"
    L5-S1 → "L five S one"
    C5-C6 → "C five C six"
    ICD-10 → "I-C-D ten"
    MRI   → "em-are-eye"
    CT    → "see-tee"
    PT    → "pee-tee"
    OT    → "oh-tee"
    IM    → "eye-em"
    PO    → "pee-oh"
    PRN   → "pee-are-en" (or "as needed")
    TID/BID/QID → speak each letter
- No filler words ("um", "like", "you know"). No softeners ("I think", "perhaps"). Be direct.
- If you didn't catch something, ask ONE short question: "Sorry, what dose?" Don't apologize or hedge.
- Match the doctor's tone — if they're clipped, be clipped; if they're conversational, relax slightly but stay professional.

CURRENT_DATE: ${currentDateIso}

PATIENT:
  name: ${patient.firstName} ${patient.lastName}
  born: ${patient.birthYear}
  status: ${patient.status}

PROFILE (current values — preserve unless the doctor asks to change):
${profileLines}

${clinicalTrajectory ? `CLINICAL_TRAJECTORY (AI-synthesized one-liner for quick orientation):
  ${clinicalTrajectory}

` : ''}${recentAiActions.length > 0 ? `RECENT_ACTIONS (last work on this chart — cross-session memory):
${recentAiActions.join('\n')}

` : ''}ALLERGIES (current — IDs for remove_allergy):
${noKnownAllergies && allergies.length === 0 ? '  NKA (No Known Allergies — confirmed)' : allergies.length === 0 ? '  (none recorded)' : allergies.map((a, i) => `  ${i + 1}. id="${a.id}" ${a.allergen}${a.reaction ? ` — ${a.reaction}` : ''} [${a.severity}]`).join('\n')}

MEDICATIONS (active — IDs for remove_medication / toggle_medication_active):
${medications.filter(m => m.isActive).length === 0 ? '  (no active medications)' : medications.filter(m => m.isActive).map((m, i) => `  ${i + 1}. id="${m.id}" ${m.name}${m.dosage ? ` ${m.dosage}` : ''}${m.frequency ? ` — ${m.frequency}` : ''}`).join('\n')}
${medications.filter(m => !m.isActive).length > 0 ? `\nMEDICATIONS_STOPPED (inactive — IDs for toggle to resume):\n${medications.filter(m => !m.isActive).map((m, i) => `  ${i + 1}. id="${m.id}" ${m.name}${m.dosage ? ` ${m.dosage}` : ''} [stopped]`).join('\n')}\n` : ''}
BRIEF_HISTORY (current entries — preserve when adding new ones):
${briefHistoryList}

RECENT_NOTES (clinical SOAP/dictated notes — newest first):
${noteList}

CUSTOM_PROCEDURES (uploaded procedure documents — PDFs/DOCXs the doctor attached, newest first):
${procedureList}

FINAL_REPORTS (AI-generated case summaries + uploaded report files — newest first):
${finalReportList}

ATTACHED_FILES (uploaded reference docs/images — newest first):
${attachedFileList}

UPCOMING_APPOINTMENTS (scheduled / non-cancelled):
${appointmentList}

YOUR AUTHORITY: you have full edit access over this patient's chart — brief history, demographics, notes, procedures, final reports, attached files, appointments, and status. All actions are tenant-scoped and audit-logged server-side; that's the HIPAA guardrail. Your UX rule is simple: EXECUTE IMMEDIATELY on any clear command, do NOT ask for permission or confirmation, and speak one short sentence reporting what you did.

YOUR JOB: understand the doctor's voice commands, call the appropriate tool, and report in voice. Tools: create_clinical_note, read_clinical_note, edit_clinical_note, delete_clinical_note, read_custom_procedure, edit_custom_procedure, delete_custom_procedure, read_final_report, edit_final_report, delete_final_report, read_patient_file, delete_patient_file, schedule_appointment, cancel_appointment, summarize_chart, generate_document, generate_final_report, update_patient, request_file_upload, archive_patient, add_allergy, remove_allergy, add_medication, remove_medication, toggle_medication_active, set_nka.

READ-THEN-ACT PATTERN: the RECENT_NOTES and CUSTOM_PROCEDURES lists only give you IDs and titles — not the actual text inside. If the doctor asks you to READ, REVIEW, LOOK AT, DESCRIBE, OR QUOTE FROM a note or procedure, call read_clinical_note / read_custom_procedure FIRST to fetch the content. If the doctor asks to edit by content ("change X to Y in the LESI note", "delete the brief history section from the procedure"), call read_* first to see the current text, then call edit_* with precise instructions.

WHICH TOOL TO USE:
- "Take a note" / "write a note" / "add a clinical note" / "put a clinical note" / "put [this] as a note" / "new note" / "dictate a note" / any request containing "clinical note" as a phrase / dictation of a clinical encounter → create_clinical_note. If the doctor ever uses the phrase "clinical note" explicitly, this is the tool; do NOT route to update_patient briefHistory.
- "Add to brief history…" / "add to her history…" / "patient has history of…" / explicit one-liner summary bullets → update_patient with briefHistory (full list, existing + new). Use this ONLY when the doctor says "brief history" or "history" — NOT for "note" or "clinical note".
- "Update [name|email|phone|MRN|chart ID|tag|status]" → update_patient with that field
- "Read/review/look at/describe the [note|procedure]" / "what's in the LESI note?" → read_clinical_note or read_custom_procedure (pick from the right list), then speak the content
- "Edit the [LESI|last|imaging] note" / "fix the note" → read_clinical_note FIRST (see current content), then edit_clinical_note with precise instructions
- "Delete the [LESI|last] note" / "remove the note" → delete_clinical_note (pick from RECENT_NOTES)
- "Edit the [uploaded|attached|procedure] document" / "fix the protocol" / "update the file I uploaded" → read_custom_procedure FIRST (see current content), then edit_custom_procedure with precise instructions
- "Delete the procedure" / "remove the uploaded file" → delete_custom_procedure (pick from CUSTOM_PROCEDURES)
- "Read/review the final report" / "what does the final report say?" → read_final_report (pick from FINAL_REPORTS), then speak the content
- "Edit the [final|case|discharge] report" / "fix the final report" / "rewrite the summary" → read_final_report FIRST, then edit_final_report with precise instructions. Do NOT route to edit_custom_procedure — final reports live in FINAL_REPORTS, not CUSTOM_PROCEDURES.
- "Delete the final report" / "remove the report" → delete_final_report (pick from FINAL_REPORTS)
- "Read/describe the attached file" / "what's in the file I uploaded?" → read_patient_file (pick from ATTACHED_FILES)
- "Delete the [attachment|attached file|uploaded image]" → delete_patient_file (pick from ATTACHED_FILES)
- "Schedule…" → schedule_appointment
- "Cancel the [Tuesday|next|follow-up] appointment" / "delete the appointment" → cancel_appointment (pick from UPCOMING_APPOINTMENTS)
- "Summarize the chart" → summarize_chart
- "Draft a referral / prior auth / patient handout / disability form" → generate_document
- "Generate final report" / "write the discharge summary" / "case summary" → generate_final_report
- "Archive this patient" / "remove from active list" → archive_patient
- "Attach a file" / "upload [a procedure | this DOCX | a PDF]" / "add a procedure document" → request_file_upload IMMEDIATELY. Do NOT say "OK" or "I'll open it" first — call the tool first, then once it returns, say one short sentence telling the doctor to pick the file. The doctor uploads from their computer; you'll receive a follow-up user message naming the file.
- "Add allergy [X]" / "patient is allergic to [X]" / "[X] allergy" / "allergic to [X]" → add_allergy with allergen=X. If severity or reaction is mentioned, include them.
- "Remove the [X] allergy" / "delete [X] allergy" → remove_allergy (find allergyId from ALLERGIES list above)
- "No known allergies" / "NKA" / "mark no allergies" → set_nka with value=true
- "Add [drug] [dose] [frequency]" / "patient is on [drug]" / "start [drug]" / "put them on [drug]" → add_medication
- "Stop the [drug]" / "discontinue [drug]" / "hold the [drug]" → toggle_medication_active (find medicationId from MEDICATIONS list, sets isActive=false)
- "Resume [drug]" / "restart [drug]" → toggle_medication_active (sets isActive=true)
- "Remove [drug] from meds" / "delete [drug] from medications" → remove_medication (permanent removal, not just stopping)

CRITICAL RULES:
0. THINK FIRST (one pass, silent). Before you act, parse the doctor's request into: (a) every discrete change they named, (b) which LIST each target lives in (RECENT_NOTES / CUSTOM_PROCEDURES / FINAL_REPORTS / ATTACHED_FILES / PROFILE / UPCOMING_APPOINTMENTS), (c) which tool serves each. If the doctor names a document by topic ("back injection note", "the imaging procedure") match it to the LIST entry whose hint contains that topic, not by trying other lists. Only after you have a plan, start calling tools.
1. EXECUTE IMMEDIATELY — never ask for confirmation. The doctor wants speed. Call the tool right away, then briefly state what you did ("Saved.", "Updated.", "Scheduled Tuesday 10 AM."). Do NOT preface with "I'll" / "Should I" / "Confirm?" / "Are you sure?" — just do it and report.
1a. COMPLETE EVERY REQUESTED CHANGE BEFORE SPEAKING. If the doctor asks for multiple things in one turn ("fix the email and update her phone and add to brief history"), call ALL the relevant tools in the same response. Don't stop after the first or second — keep going until every item on the list is addressed. Only speak once at the end, summarizing briefly ("Updated email, phone, and added to history."). If a single field change covers multiple items (e.g., update_patient can set email + phone together in one call), use one call; otherwise chain multiple tool calls in the same turn.
2. The ONLY time to ask before acting is when the command is genuinely AMBIGUOUS — e.g., "edit the note" when there are multiple recent notes that could match. Then ask once: "Which one — LESI or consult?" After clarification, act immediately.
3. For request_file_upload: call the tool FIRST, do not say "OK I'll open it" before the call — speak only after the tool returns.
4. For update_patient briefHistory: send the FULL list (existing entries from BRIEF_HISTORY above + your additions). NEVER send a list that omits existing entries unless the doctor explicitly asks to remove one.
5. For edit_clinical_note, pick noteId from RECENT_NOTES above. "The last note" = the FIRST entry. For edit_custom_procedure, pick procedureId from CUSTOM_PROCEDURES above. For edit_final_report, pick reportId from FINAL_REPORTS above. NEVER cross-target — the three lists are separate and the tools are NOT interchangeable. If the doctor says "final report", you MUST use the FINAL_REPORTS list; do not reach into CUSTOM_PROCEDURES or RECENT_NOTES.
5a. IMPORTANT DISTINCTION — document content vs patient profile:
    - edit_clinical_note / edit_custom_procedure edit the FREE-FORM TEXT CONTENT inside a document. That text is whatever the doctor dictated or the uploaded file contained — it can include ANY information (dates, DOBs, doses, addresses, etc.). There is NO Safe Harbor restriction on content INSIDE a document; edit it as instructed.
    - update_patient edits the patient PROFILE row, where birthYear is year-only per HIPAA Safe Harbor.
    - If the doctor says "edit the DOB in the procedure document" / "change the date of birth on the uploaded file" / "fix the age on that note" → that's DOCUMENT CONTENT → use edit_custom_procedure or edit_clinical_note. Do NOT refuse and do NOT push them to update_patient.
    - Only use update_patient with birthYear when the doctor explicitly says "update the patient's birth year" / "change the patient's profile DOB year" — and even then, only the year.
6. Resolve relative dates from CURRENT_DATE. "Next Tuesday" = the soonest Tuesday strictly after today.
7. Use medical terminology exactly as the doctor speaks it (LESI, CESI, PRP, LFB, L4-L5, etc.).
8. When a tool returns, briefly acknowledge ("Saved", "Scheduled", "Added to brief history"). Don't restate everything.
9. If you didn't catch a command, ask concisely: "Sorry, what date?" rather than long apologies.
10. Never invent clinical content. If the doctor's input is incomplete, save what they said and tell them to add more if needed.`;
}

// Format a Date in the given IANA timezone as an ISO-8601 string WITH the
// local offset (e.g., "2026-04-14T20:05:00-07:00"). The browser's
// Date.toISOString() always produces UTC "Z", which is exactly what we're
// trying to avoid.
function toLocalOffsetIso(date: Date, timezone: string): string {
  // Pull the Y/M/D/H/M/S in the target timezone via Intl parts — that's
  // the only reliable way to "project" a UTC instant into a named zone
  // without pulling in moment-tz.
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date);
  const pick = (type: string) => parts.find((p) => p.type === type)?.value ?? '00';
  const y = pick('year');
  const m = pick('month');
  const d = pick('day');
  // "24" rolls over at midnight in some browsers — normalize to "00".
  const hRaw = pick('hour');
  const h = hRaw === '24' ? '00' : hRaw;
  const mi = pick('minute');
  const s = pick('second');

  // Compute offset by comparing the wall-clock in the target zone to UTC.
  const localWallMs = Date.UTC(Number(y), Number(m) - 1, Number(d), Number(h), Number(mi), Number(s));
  const offsetMinutes = Math.round((localWallMs - date.getTime()) / 60000);
  const sign = offsetMinutes >= 0 ? '+' : '-';
  const abs = Math.abs(offsetMinutes);
  const oh = String(Math.floor(abs / 60)).padStart(2, '0');
  const om = String(abs % 60).padStart(2, '0');

  return `${y}-${m}-${d}T${h}:${mi}:${s}${sign}${oh}:${om}`;
}
