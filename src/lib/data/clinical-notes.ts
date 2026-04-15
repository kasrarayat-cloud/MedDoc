// ============================================================================
// Clinical Notes Data Layer
// ----------------------------------------------------------------------------
// Backed by the existing Prisma `Document` model (Documents with non-null
// `content` field are inline clinical notes). Falls back to an in-memory
// store when the DB is unavailable so demos work without Postgres.
//
// In-memory notes survive within a single Node process — they reset on a
// full dev-server restart, which is fine for demo purposes.
// ============================================================================

import prisma, { isDatabaseHealthy } from '@/lib/db';
import type { Session } from '@/lib/auth';
import { patientAccessWhere } from './patients';

export type NoteCategory =
  | 'CLINICAL_NOTE'
  | 'CUSTOM_PROCEDURE'
  /** AI-synthesized summary/discharge reports. One content blob per row. */
  | 'FINAL_REPORT'
  /** Uploaded patient-chart attachment — metadata only (no bytes stored
   *  yet). Distinct from CUSTOM_PROCEDURE because those carry the full
   *  extracted procedure text as content; file attachments are pointers
   *  (name / mime / size) for the doctor to reference. */
  | 'PATIENT_FILE';

// Sentinel values we write into the procedureType column to distinguish
// non-clinical-note categories. CLINICAL_NOTE is the "null sentinel" case.
const CATEGORY_SENTINELS: Record<Exclude<NoteCategory, 'CLINICAL_NOTE'>, string> = {
  CUSTOM_PROCEDURE: 'CUSTOM_PROCEDURE',
  FINAL_REPORT: 'FINAL_REPORT',
  PATIENT_FILE: 'PATIENT_FILE',
};

function categoryFromProcedureType(procType: string | null): NoteCategory {
  if (procType === 'CUSTOM_PROCEDURE') return 'CUSTOM_PROCEDURE';
  if (procType === 'FINAL_REPORT') return 'FINAL_REPORT';
  if (procType === 'PATIENT_FILE') return 'PATIENT_FILE';
  return 'CLINICAL_NOTE';
}

export interface ClinicalNoteView {
  id: string;
  patientId: string;
  title: string;
  procedureType: string | null;
  /** Distinguishes daily notes from uploaded custom procedures */
  category: NoteCategory;
  content: string;
  status: 'DRAFT' | 'FINALIZED' | 'SIGNED';
  createdAt: string; // ISO
  createdById: string;
  createdByName?: string;
  updatedAt?: string; // ISO — present only after an edit
  updatedByName?: string;
  /** Only populated for PATIENT_FILE rows — the original filename. */
  fileName?: string;
  /** Only populated for PATIENT_FILE rows. */
  mimeType?: string;
  /** Only populated for PATIENT_FILE rows. */
  sizeBytes?: number;
}

export interface CreateClinicalNoteInput {
  patientId: string;
  title: string;
  procedureType?: string | null;
  /** Defaults to 'CLINICAL_NOTE' if omitted */
  category?: NoteCategory;
  content: string;
  createdById: string;
}

// ---------------------------------------------------------------------------
// In-memory fallback store — Map<patientId, ClinicalNoteView[]>
// ---------------------------------------------------------------------------
const memoryNotes = new Map<string, ClinicalNoteView[]>();

function memoryAdd(note: ClinicalNoteView): void {
  const list = memoryNotes.get(note.patientId) ?? [];
  list.unshift(note); // newest first
  memoryNotes.set(note.patientId, list);
}

function generateId(): string {
  return `note_${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * List documents for a patient, newest first.
 * Filter by category to separate clinical notes from custom procedures.
 *
 * TENANT-SAFE: scopes via the parent Patient row using
 * `patient: patientAccessWhere(session)`, so callers cannot read notes
 * for a patient outside their practice even if they pass an arbitrary
 * patientId from the client.
 */
export async function listNotesByPatient(
  patientId: string,
  category: NoteCategory | undefined,
  session: Session
): Promise<ClinicalNoteView[]> {
  if (await isDatabaseHealthy()) {
    try {
      // PATIENT_FILE rows have no content (they're metadata only) so we
      // MUST NOT filter by content-null when the caller asks for files.
      // For all other categories, the content-null filter keeps stray
      // Dropbox-backed documents out of the clinical-note lists.
      const excludeContentless =
        category === undefined ||
        category === 'CLINICAL_NOTE' ||
        category === 'CUSTOM_PROCEDURE' ||
        category === 'FINAL_REPORT';
      const rows = await prisma.document.findMany({
        where: {
          patientId,
          deletedAt: null,
          ...(excludeContentless ? { NOT: { content: null } } : {}),
          patient: patientAccessWhere(session),
        },
        orderBy: { createdAt: 'desc' },
        include: {
          createdBy: { select: { name: true } },
        },
      });
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const all: ClinicalNoteView[] = rows.map((r: any) => prismaToView(r));
      return category ? all.filter((n) => n.category === category) : all;
    } catch (err) {
      console.warn('[data/clinical-notes] Prisma findMany failed, using memory:', err);
    }
  }
  const all = memoryNotes.get(patientId) ?? [];
  return category ? all.filter((n) => n.category === category) : all;
}

// ---------------------------------------------------------------------------
// File-attachment helpers (PATIENT_FILE category)
// ---------------------------------------------------------------------------
// Stored in the Document table; no bytes persisted — this is a metadata
// pointer the doctor uses to know what's been attached to the chart. When
// actual file storage (Dropbox / S3) is wired later, set fileHash/dropbox*
// on these same rows.
// ---------------------------------------------------------------------------

export interface CreatePatientFileInput {
  patientId: string;
  fileName: string;
  mimeType: string;
  sizeBytes: number;
  createdById: string;
  /** Which chart card the upload should surface under. Defaults to
   *  PATIENT_FILE (Attached Documents). FINAL_REPORT is used when the
   *  doctor hits Upload on the Final Reports card — typically a signed
   *  external PDF they want alongside AI-generated reports. */
  category?: 'PATIENT_FILE' | 'FINAL_REPORT';
}

export async function createPatientFile(
  input: CreatePatientFileInput
): Promise<ClinicalNoteView> {
  const category = input.category ?? 'PATIENT_FILE';
  const sentinel = CATEGORY_SENTINELS[category];
  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.document.create({
        data: {
          patientId: input.patientId,
          title: input.fileName,
          procedureType: sentinel,
          status: 'FINALIZED',
          content: null,
          mimeType: input.mimeType,
          fileSizeBytes: input.sizeBytes,
          createdById: input.createdById,
        },
        include: { createdBy: { select: { name: true } } },
      });
      return prismaToView(row);
    } catch (err) {
      console.warn('[data/clinical-notes] Prisma createPatientFile failed, using memory:', err);
    }
  }
  const note: ClinicalNoteView = {
    id: generateId(),
    patientId: input.patientId,
    title: input.fileName,
    procedureType: null,
    category,
    content: '',
    status: 'FINALIZED',
    createdAt: new Date().toISOString(),
    createdById: input.createdById,
    fileName: input.fileName,
    mimeType: input.mimeType,
    sizeBytes: input.sizeBytes,
  };
  memoryAdd(note);
  return note;
}

// ---------------------------------------------------------------------------
// Final-report helper (FINAL_REPORT category)
// ---------------------------------------------------------------------------

export interface CreateFinalReportInput {
  patientId: string;
  title: string;
  content: string;
  createdById: string;
}

export async function createFinalReport(
  input: CreateFinalReportInput
): Promise<ClinicalNoteView> {
  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.document.create({
        data: {
          patientId: input.patientId,
          title: input.title,
          procedureType: CATEGORY_SENTINELS.FINAL_REPORT,
          content: input.content,
          // DRAFT until a doctor signs off. No separate workflow for reports
          // yet — matches how clinical notes ship as DRAFT and get edited.
          status: 'DRAFT',
          createdById: input.createdById,
        },
        include: { createdBy: { select: { name: true } } },
      });
      return prismaToView(row);
    } catch (err) {
      console.warn('[data/clinical-notes] Prisma createFinalReport failed, using memory:', err);
    }
  }
  const note: ClinicalNoteView = {
    id: generateId(),
    patientId: input.patientId,
    title: input.title,
    procedureType: null,
    category: 'FINAL_REPORT',
    content: input.content,
    status: 'DRAFT',
    createdAt: new Date().toISOString(),
    createdById: input.createdById,
  };
  memoryAdd(note);
  return note;
}

/**
 * Create a new clinical note tied to a patient + author.
 */
export async function createClinicalNote(
  input: CreateClinicalNoteInput
): Promise<ClinicalNoteView> {
  // For DB storage, non-CLINICAL_NOTE categories use a sentinel value in
  // the procedureType column. CLINICAL_NOTE stores the real procedure name
  // (or null) there.
  const dbProcedureType =
    input.category && input.category !== 'CLINICAL_NOTE'
      ? CATEGORY_SENTINELS[input.category]
      : input.procedureType ?? null;

  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.document.create({
        data: {
          patientId: input.patientId,
          title: input.title,
          procedureType: dbProcedureType,
          content: input.content,
          status: 'DRAFT',
          createdById: input.createdById,
        },
        include: {
          createdBy: { select: { name: true } },
        },
      });
      return prismaToView(row);
    } catch (err) {
      console.warn('[data/clinical-notes] Prisma create failed, using memory:', err);
    }
  }

  // Memory fallback
  const note: ClinicalNoteView = {
    id: generateId(),
    patientId: input.patientId,
    title: input.title,
    procedureType: input.procedureType ?? null,
    category: input.category ?? 'CLINICAL_NOTE',
    content: input.content,
    status: 'DRAFT',
    createdAt: new Date().toISOString(),
    createdById: input.createdById,
    createdByName: 'Dr. Moussazadeh',
  };
  memoryAdd(note);
  return note;
}

/**
 * Get a single clinical note by ID. Returns null if not found / deleted
 * OR if the session isn't allowed to see the parent patient (cross-tenant
 * and non-admin cross-doctor access both collapse to null so callers
 * can't distinguish "forbidden" from "missing").
 */
export async function getNoteById(
  id: string,
  session: Session
): Promise<ClinicalNoteView | null> {
  if (await isDatabaseHealthy()) {
    try {
      // No content-null filter here — PATIENT_FILE rows have null content
      // by design (metadata only), and callers like deleteClinicalNote
      // need to be able to find them. The category system (via
      // procedureType sentinels) distinguishes row kinds; content presence
      // is no longer a useful gate.
      const row = await prisma.document.findFirst({
        where: {
          id,
          deletedAt: null,
          patient: patientAccessWhere(session),
        },
        include: {
          createdBy: { select: { name: true } },
          updatedBy: { select: { name: true } },
        },
      });
      if (!row) return null;
      return prismaToView(row);
    } catch (err) {
      console.warn('[data/clinical-notes] Prisma findFirst failed, using memory:', err);
    }
  }
  // Memory fallback — scan all patient arrays (store is keyed by patientId)
  for (const notes of memoryNotes.values()) {
    const found = notes.find((n) => n.id === id);
    if (found) return found;
  }
  return null;
}

/**
 * Update the content of an existing clinical note.
 * Returns the updated note or null if not found.
 */
export async function updateClinicalNote(
  id: string,
  newContent: string,
  updatedById: string,
  session: Session
): Promise<ClinicalNoteView | null> {
  // Ownership check — getNoteById enforces tenant + access predicates.
  // Refusing to update if the caller can't see the note closes the
  // "guess a note id from another practice and PATCH it" path.
  const existing = await getNoteById(id, session);
  if (!existing) return null;

  if (await isDatabaseHealthy()) {
    try {
      const row = await prisma.document.update({
        where: { id },
        data: {
          content: newContent,
          updatedById,
          // updatedAt is auto-set by Prisma @updatedAt
        },
        include: {
          createdBy: { select: { name: true } },
          updatedBy: { select: { name: true } },
        },
      });
      return prismaToView(row);
    } catch (err) {
      console.warn('[data/clinical-notes] Prisma update failed, using memory:', err);
    }
  }
  // Memory fallback — find the note across all patients, mutate in place
  for (const [patientId, notes] of memoryNotes.entries()) {
    const idx = notes.findIndex((n) => n.id === id);
    if (idx !== -1) {
      const updated: ClinicalNoteView = {
        ...notes[idx],
        content: newContent,
        updatedAt: new Date().toISOString(),
      };
      notes[idx] = updated;
      memoryNotes.set(patientId, notes);
      return updated;
    }
  }
  return null;
}

/**
 * Soft-delete a clinical note or custom procedure. Per HIPAA we never hard-
 * delete — set deletedAt, which listNotesByPatient / getNoteById filter out.
 * Returns true if deletion succeeded, false if the caller can't see the note.
 */
export async function deleteClinicalNote(
  id: string,
  session: Session
): Promise<boolean> {
  // Ownership check — same rationale as updateClinicalNote. If the session
  // can't see the note, this is a cross-tenant probe.
  const existing = await getNoteById(id, session);
  if (!existing) return false;

  if (await isDatabaseHealthy()) {
    try {
      await prisma.document.update({
        where: { id },
        data: { deletedAt: new Date() },
      });
      return true;
    } catch (err) {
      console.warn('[data/clinical-notes] Prisma delete failed, using memory:', err);
    }
  }
  // Memory fallback — drop the entry.
  for (const [patientId, notes] of memoryNotes.entries()) {
    const idx = notes.findIndex((n) => n.id === id);
    if (idx !== -1) {
      notes.splice(idx, 1);
      memoryNotes.set(patientId, notes);
      return true;
    }
  }
  return false;
}

// ---------------------------------------------------------------------------
// Internal
// ---------------------------------------------------------------------------
// eslint-disable-next-line @typescript-eslint/no-explicit-any
function prismaToView(row: any): ClinicalNoteView {
  const procType: string | null = row.procedureType ?? null;
  const category = categoryFromProcedureType(procType);
  const isSentinel =
    procType === 'CUSTOM_PROCEDURE' ||
    procType === 'FINAL_REPORT' ||
    procType === 'PATIENT_FILE';
  return {
    id: row.id,
    patientId: row.patientId ?? '',
    title: row.title,
    procedureType: isSentinel ? null : procType,
    category,
    content: row.content ?? '',
    status: row.status as ClinicalNoteView['status'],
    createdAt: row.createdAt.toISOString(),
    createdById: row.createdById,
    createdByName: row.createdBy?.name ?? undefined,
    updatedAt: row.updatedById ? row.updatedAt?.toISOString() : undefined,
    updatedByName: row.updatedBy?.name ?? undefined,
    // File-upload metadata. fileSizeBytes being set is the marker that
    // this row represents an uploaded file (vs. text content). We used
    // to gate this on category === 'PATIENT_FILE', which broke once
    // FINAL_REPORT rows could also be file uploads — Final Reports UI
    // then rendered them as empty text reports.
    fileName: row.fileSizeBytes != null ? row.title : undefined,
    mimeType: row.fileSizeBytes != null ? row.mimeType ?? undefined : undefined,
    sizeBytes: row.fileSizeBytes != null ? row.fileSizeBytes : undefined,
  };
}
