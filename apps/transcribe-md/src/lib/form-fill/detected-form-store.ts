// ============================================================================
// ONE-PIPELINE (ruling #326, Slice B) — persist / read a DETECTED form on the
// note template. Server-only. prisma singleton + the shared pdf-native canvas
// store.
// ----------------------------------------------------------------------------
// A detected form is SELF-CONTAINED on the NoteTemplate: unlike the DOCX twin it
// has no compiled-IR / source-artifact / field-definition rows. Everything the
// certify + export paths need lives in `styleProfile.formDetect*` (parallel to
// `pdfNative*`, so NO schema migration and the DOCX-twin columns stay byte-stable
// — #217) plus the blank PDF canvas in the shared object store (reused verbatim,
// key `pdf-native/${templateId}/canvas.pdf`).
//
// The stored fields carry the grouped detected boxes AND their mapped concept +
// source classification, so export can rebuild `fillDetectedForm` input and route
// each field to the right deterministic value source (note section vs header
// field) with NO model call and NO fabricated DOCX IR.
// ============================================================================
import prisma from '@meddoc/db';

import { putTemplateCanvas, getTemplateCanvas } from '@/lib/pdf-native/store';

import type { DetectedBox, DetectorSignature } from './types';
import type { FidelityResult } from './verify-fidelity';

/** A grouped detected field with its mapping, as persisted. Mirrors `FormField`
 *  plus the stage-3 concept and the export routing (`headerKey`). */
export interface StoredDetectedField {
  id: string;
  label: string;
  page: number;
  boxes: DetectedBox[];
  multiline: boolean;
  /** mapped note-model concept, or null when the doctor must still confirm it. */
  concept: string | null;
  /** provenance class (#247) — visit_metadata / extraction / manual / … */
  sourceType: string;
  /** canonical header key when this field is a record-derived metadata field
   *  (patient_name / date_of_surgery / surgeon / patient_dob / …), else null.
   *  A non-null headerKey routes the field to `resolveHeaderFields`; null routes
   *  it to the note-section split. */
  headerKey: string | null;
}

/** The whole detected form, as it lives on `styleProfile.formDetect`. */
export interface StoredDetectedForm {
  model: string;
  detector: DetectorSignature;
  /** sha256 of the blank canvas at persist time — export refuses to draw onto a
   *  canvas that no longer matches (the pdf-native `pdfNativeCanvasHash` rule). */
  canvasHash: string;
  pageCount: number;
  fields: StoredDetectedField[];
}

/** Scoped read of a template's styleProfile (defense-in-depth — the action
 *  already checks ownership, but the library must not be a way to touch another
 *  doctor's row). */
async function loadStyleProfile(
  templateId: string,
  doctorId: string,
): Promise<Record<string, unknown>> {
  const row = await prisma.noteTemplate.findFirstOrThrow({
    where: { id: templateId, doctorId },
    select: { styleProfile: true },
  });
  return ((row.styleProfile ?? {}) as Record<string, unknown>) || {};
}

/** Scoped styleProfile write (updateMany so the doctorId filter applies — the
 *  T5-W lesson: no unscoped-by-id fallback). */
async function writeStyleProfile(
  templateId: string,
  doctorId: string,
  styleProfile: Record<string, unknown>,
): Promise<void> {
  await prisma.noteTemplate.updateMany({
    where: { id: templateId, doctorId },
    data: { styleProfile: styleProfile as never },
  });
}

/**
 * Persist a detected form on a template + store its blank canvas. Sets
 * `formDetectPendingPreview` (the doctor still confirms the sample-value preview
 * and certifies) and clears any prior certified marker — a re-detect is a new
 * form and must be re-proven, never inheriting the old cert (the pdf-native
 * "bad re-upload never clobbers a prior good cert" posture, applied here by
 * requiring a fresh certify before export will draw).
 */
export async function persistDetectedForm(input: {
  templateId: string;
  doctorId: string;
  form: StoredDetectedForm;
  canvas: Buffer;
}): Promise<void> {
  const styleProfile = await loadStyleProfile(input.templateId, input.doctorId);
  await putTemplateCanvas(input.templateId, input.canvas);
  await writeStyleProfile(input.templateId, input.doctorId, {
    ...styleProfile,
    formDetect: input.form as unknown,
    formDetectPendingPreview: true,
    formDetectCertified: false,
  });
}

/** Mark a detected form CERTIFIED, recording the fidelity summary that proved it.
 *  Clears the pending-preview marker. Returns nothing — the caller audits. */
export async function markDetectedFormCertified(input: {
  templateId: string;
  doctorId: string;
  fidelity: FidelityResult;
}): Promise<void> {
  const styleProfile = await loadStyleProfile(input.templateId, input.doctorId);
  await writeStyleProfile(input.templateId, input.doctorId, {
    ...styleProfile,
    formDetectCertified: true,
    formDetectPendingPreview: false,
    formDetectFidelity: input.fidelity as unknown,
  });
}

/** Coerce a persisted detected form back to its type, or null when the
 *  styleProfile carries none / a malformed one. Defensive: a malformed stored
 *  form must never draw onto a doctor's page — it reads as "no detected form". */
export function readDetectedForm(styleProfile: Record<string, unknown>): StoredDetectedForm | null {
  const raw = styleProfile.formDetect;
  if (!raw || typeof raw !== 'object') return null;
  const f = raw as Record<string, unknown>;
  if (typeof f.canvasHash !== 'string') return null;
  if (!Array.isArray(f.fields)) return null;
  const detector = f.detector as Record<string, unknown> | undefined;
  if (!detector || typeof detector.weightsSha !== 'string') return null;
  const fields: StoredDetectedField[] = [];
  for (const rawField of f.fields) {
    if (!rawField || typeof rawField !== 'object') return null;
    const x = rawField as Record<string, unknown>;
    if (typeof x.id !== 'string' || typeof x.label !== 'string') return null;
    if (typeof x.page !== 'number' || !Array.isArray(x.boxes)) return null;
    fields.push({
      id: x.id,
      label: x.label,
      page: x.page,
      boxes: x.boxes as DetectedBox[],
      multiline: x.multiline === true,
      concept: typeof x.concept === 'string' ? x.concept : null,
      sourceType: typeof x.sourceType === 'string' ? x.sourceType : 'extraction',
      headerKey: typeof x.headerKey === 'string' ? x.headerKey : null,
    });
  }
  return {
    model: typeof f.model === 'string' ? f.model : 'FFDNet',
    detector: detector as unknown as DetectorSignature,
    canvasHash: f.canvasHash,
    pageCount: typeof f.pageCount === 'number' ? f.pageCount : 0,
    fields,
  };
}

/** Is this template a CERTIFIED detected form? (styleProfile predicate; the
 *  certified-in-slot + export gates read it.) */
export function isDetectedFormCertified(styleProfile: Record<string, unknown>): boolean {
  return styleProfile.formDetectCertified === true;
}

export { getTemplateCanvas };
