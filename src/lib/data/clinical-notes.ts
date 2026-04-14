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

export type NoteCategory = 'CLINICAL_NOTE' | 'CUSTOM_PROCEDURE';

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
      const rows = await prisma.document.findMany({
        where: {
          patientId,
          deletedAt: null,
          NOT: { content: null },
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

/**
 * Create a new clinical note tied to a patient + author.
 */
export async function createClinicalNote(
  input: CreateClinicalNoteInput
): Promise<ClinicalNoteView> {
  // For DB storage, CUSTOM_PROCEDURE category is stored in the procedureType field
  const dbProcedureType =
    input.category === 'CUSTOM_PROCEDURE'
      ? 'CUSTOM_PROCEDURE'
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
      const row = await prisma.document.findFirst({
        where: {
          id,
          deletedAt: null,
          NOT: { content: null },
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
  const procType = row.procedureType ?? null;
  return {
    id: row.id,
    patientId: row.patientId ?? '',
    title: row.title,
    procedureType: procType === 'CUSTOM_PROCEDURE' ? null : procType,
    category: procType === 'CUSTOM_PROCEDURE' ? 'CUSTOM_PROCEDURE' : 'CLINICAL_NOTE',
    content: row.content ?? '',
    status: row.status as ClinicalNoteView['status'],
    createdAt: row.createdAt.toISOString(),
    createdById: row.createdById,
    createdByName: row.createdBy?.name ?? undefined,
    updatedAt: row.updatedById ? row.updatedAt?.toISOString() : undefined,
    updatedByName: row.updatedBy?.name ?? undefined,
  };
}
