// ============================================================================
// ONE-PIPELINE (ruling #326, Slice B) — CERTIFY a detected form. Server-only.
// prisma singleton + injectable storage + logTwinAudit.
// ----------------------------------------------------------------------------
// certify = on a SYNTHETIC visit, every box that CAN fill fills, and the page is
// PIXEL-IDENTICAL outside the detected boxes. The proof runs the SAME value path a
// real export takes (`fillFromNote`) → the SAME fill engine (`fillDetectedForm`) →
// the fidelity sidecar (`verifyFidelity`). Nothing is bypassed.
//
// ⚠️ "EVERY BOX FILLS" IS AGAINST THE #247/#319 PRECEDENT, NOT LITERAL. A detected
// form's record-derived metadata boxes (PATIENT DOB, PATIENT ID, AGE, DD/DT on the
// owner's own colon form) are blank-unless-dictated — the DOCX twin attests them
// blank rather than filling, and a blank there is correct, not a failure. So the
// gate is: every field is either (a) FILLED on the synthetic visit, or (b) a POLICY
// BLANK (a record-derived metadata field `resolveHeaderFields` does not fill
// deterministically). A field the doctor has NOT yet mapped (concept === null)
// refuses — it is the "confirm every field first" gate, the twin's MAPPINGS_NOT_READY
// applied here.
//
// The synthetic note carries NO patient data and is PHI-gated through the SHARED
// front-half (`deriveSyntheticEncounter`) — one PHI gate for the DOCX twin and the
// detected form both (#326 extraction).
// ============================================================================
import prisma from '@meddoc/db';

import { deriveSyntheticEncounter } from '@/lib/template-twin/synthetic-front-half';
import type { TemplateTwinActor } from '@/lib/template-twin/certification-lifecycle';

import {
  readDetectedForm,
  markDetectedFormCertified,
  getTemplateCanvas,
  type StoredDetectedField,
  type StoredDetectedForm,
} from './detected-form-store';
import { fillFromNote, DETERMINISTICALLY_FILLED_HEADER_KEYS } from './fill-from-note';
import { fillDetectedForm } from './fill-boxes';
import { verifyFidelity, isPixelIdenticalOutsideBoxes } from './verify-fidelity';
import { canvasHash } from '@/lib/pdf-native/hash';
import type { DetectedForm, DetectedPage } from './types';

export class DetectedFormCertifyError extends Error {
  readonly code:
    | 'NOT_FOUND'
    | 'NO_CANVAS'
    | 'STALE_CANVAS'
    | 'FIELDS_NOT_READY'
    | 'BOX_DID_NOT_FILL'
    | 'FIDELITY_FAILED';
  readonly detail: string[];

  constructor(code: DetectedFormCertifyError['code'], message: string, detail: string[] = []) {
    super(message);
    this.name = 'DetectedFormCertifyError';
    this.code = code;
    this.detail = detail;
  }
}

/** A field is EXPECTED to fill on a real (and the synthetic) visit iff it is a
 *  body section OR a metadata field on a deterministically-filled header key.
 *  A record-derived metadata field on any other key is a POLICY BLANK. */
export function fieldExpectedToFill(field: StoredDetectedField): boolean {
  if (field.headerKey === null) return true; // body section
  return DETERMINISTICALLY_FILLED_HEADER_KEYS.has(field.headerKey);
}

/** Reconstruct a minimal `DetectedForm` for the fidelity verifier from the stored
 *  fields (verifyFidelity reads only `pages[].boxes`). */
function detectedFormForVerify(form: StoredDetectedForm): DetectedForm {
  const byPage = new Map<number, DetectedPage>();
  for (const f of form.fields) {
    for (const box of f.boxes) {
      let page = byPage.get(f.page);
      if (!page) {
        page = { index: f.page, widthPt: 0, heightPt: 0, boxes: [] };
        byPage.set(f.page, page);
      }
      page.boxes.push(box);
    }
  }
  const pages = [...byPage.values()].sort((a, b) => a.index - b.index);
  return { model: form.model, weightsSha: form.detector.weightsSha, detector: form.detector, pages };
}

/**
 * Build the synthetic self-test note: a `## <label>` heading + clearly-synthetic
 * body for every BODY field, and a synthetic surgeon line so `procedure.surgeon`
 * fills. NO patient data — PHI-gated by the caller through `deriveSyntheticEncounter`.
 */
export function buildSyntheticDetectedNote(fields: ReadonlyArray<StoredDetectedField>): string {
  const lines: string[] = [];
  // A surgeon line the note-based extractor recognises, clearly synthetic.
  lines.push('Operating surgeon: Dr. Synthetic Example (self-test).');
  lines.push('');
  for (const f of fields) {
    if (f.headerKey !== null) continue; // header fields fill from the record, not the note body
    const label = f.label.replace(/[:*_]+$/g, '').trim() || f.id;
    lines.push(`## ${label}`);
    lines.push(
      `Synthetic self-test content for "${label}" — clearly labeled example text, no patient identifiers.`,
    );
    lines.push('');
  }
  return lines.join('\n');
}

export interface CertifyDetectedFormResult {
  templateId: string;
  fieldCount: number;
  filledCount: number;
  policyBlankCount: number;
  fidelity: { pages: number; dpi: number };
}

/**
 * Certify a detected form. Loads its stored shape + blank canvas, proves on a
 * synthetic visit that every fillable box fills and the page is pixel-identical
 * outside the boxes, then marks it certified. Refuses (never certifies) on any
 * failure, naming the offending fields.
 */
export async function certifyDetectedForm(input: {
  templateId: string;
  actor: TemplateTwinActor;
}): Promise<CertifyDetectedFormResult> {
  const row = await prisma.noteTemplate.findFirst({
    where: { id: input.templateId, doctorId: input.actor.userId },
    select: { styleProfile: true },
  });
  if (!row) throw new DetectedFormCertifyError('NOT_FOUND', 'Detected form template not found.');
  const styleProfile = ((row.styleProfile ?? {}) as Record<string, unknown>) || {};
  const form = readDetectedForm(styleProfile);
  if (!form) throw new DetectedFormCertifyError('NOT_FOUND', 'No detected form is stored on this template.');

  // ── Every field must be MAPPED first (the doctor confirmed the sample-value
  // preview). A null concept is "needs_confirmation" → refuse, naming them.
  const unconfirmed = form.fields.filter((f) => f.concept === null);
  if (unconfirmed.length > 0) {
    throw new DetectedFormCertifyError(
      'FIELDS_NOT_READY',
      'Every detected field needs a confirmed mapping before certifying.',
      unconfirmed.map((f) => `${f.id}:${f.label}`),
    );
  }

  const canvas = await getTemplateCanvas(input.templateId);
  if (!canvas) throw new DetectedFormCertifyError('NO_CANVAS', 'The blank form canvas is missing.');
  // Integrity — the stored canvas must still match the hash recorded at persist.
  if (canvasHash(canvas) !== form.canvasHash) {
    throw new DetectedFormCertifyError('STALE_CANVAS', 'The stored canvas no longer matches the detected form.');
  }

  // ── SYNTHETIC VISIT — build the note, PHI-gate it through the SHARED front-half.
  const noteText = buildSyntheticDetectedNote(form.fields);
  await deriveSyntheticEncounter({
    deriveEncounter: () => ({ ok: true, text: noteText }) as never,
    actor: input.actor,
    totalFields: form.fields.length,
  });

  // Fixed synthetic visit date (no Date.now — reproducible proof).
  const syntheticDate = new Date('2020-01-01T00:00:00.000Z');
  const { values } = fillFromNote(form.fields, {
    patientName: 'SAMPLE PATIENT (SYNTHETIC)',
    visitDate: syntheticDate,
    noteText,
    dictationText: noteText,
  });

  // ── Every EXPECTED-TO-FILL field must have drawn a value; policy blanks may be
  // empty. A box that should fill and did not means the pipeline does not bind.
  const shouldFillButBlank = form.fields.filter(
    (f) => fieldExpectedToFill(f) && !values.has(f.id),
  );
  if (shouldFillButBlank.length > 0) {
    throw new DetectedFormCertifyError(
      'BOX_DID_NOT_FILL',
      'A detected box that should fill did not on the synthetic visit.',
      shouldFillButBlank.map((f) => `${f.id}:${f.label}`),
    );
  }

  // ── FILL + FIDELITY.
  const filled = await fillDetectedForm({
    originalPdf: new Uint8Array(canvas),
    fields: form.fields,
    values,
  });
  const fidelity = await verifyFidelity(
    new Uint8Array(canvas),
    filled.pdf,
    detectedFormForVerify(form),
  );
  if (!isPixelIdenticalOutsideBoxes(fidelity)) {
    const offenders = fidelity.pages
      .filter((p) => p.outsideBoxChangedPx > 0)
      .map((p) => `page${p.page}:${p.outsideBoxChangedPx}px`);
    throw new DetectedFormCertifyError(
      'FIDELITY_FAILED',
      'Filling the form changed the page outside the detected boxes.',
      offenders.length > 0 ? offenders : ['no box drew ink'],
    );
  }

  // ── PERSIST CERTIFIED. The ACTION layer writes the audit row (an existing
  // AuditAction — no new enum value, so #326 stays migration-free); the library
  // logs the proof structurally (PHI-safe: ids + counts, never a field label's
  // content beyond what the doctor's own form already carries in the styleProfile).
  await markDetectedFormCertified({
    templateId: input.templateId,
    doctorId: input.actor.userId,
    fidelity,
  });
  console.info(
    `[form-detect:certify] template=${input.templateId} ` +
      `model=${form.detector.model} weightsSha=${form.detector.weightsSha.slice(0, 12)} ` +
      `fields=${form.fields.length} filled=${values.size} ` +
      `fidelityPages=${fidelity.pages.length} dpi=${fidelity.dpi}`,
  );

  return {
    templateId: input.templateId,
    fieldCount: form.fields.length,
    filledCount: values.size,
    policyBlankCount: form.fields.filter((f) => !fieldExpectedToFill(f)).length,
    fidelity: { pages: fidelity.pages.length, dpi: fidelity.dpi },
  };
}
