// ============================================================================
// ONE-PIPELINE (ruling #326, Slice B) — CERTIFY a detected form. Server-only.
// prisma singleton.
// ----------------------------------------------------------------------------
// certify = on a SYNTHETIC visit, every box that CAN fill fills, and the page is
// PIXEL-IDENTICAL outside the detected boxes. The proof runs the SAME value path a
// real export takes (`deriveDetectedFormValues`) → the SAME fill engine
// (`fillDetectedForm`) → the fidelity sidecar (`verifyFidelity`). Nothing is
// bypassed.
//
// ⚠️ THE SYNTHETIC VISIT'S FACTS ARE CONSTRUCTED DIRECTLY, NOT VIA L3/L4. A real
// export projects the visit's stored `entities` into facts; the certify proof
// constructs one affirmed synthetic fact per clinical-concept box (PHI-free) —
// the SAME `EncounterFact` shape, so the tier-1 resolver, the fill engine and the
// fidelity check are exercised identically. L3 extraction fidelity is the shared
// twin's, already proven; this proves the DETECTED-form binding + fill + page
// fidelity, which is what is new. `deriveVerificationEncounter` is NOT usable here
// — it generates dictation only for MEASUREMENT forms and refuses a narrative
// operative note (the owner's colon note certified via the #127 auto-certify path,
// not that generator).
//
// ⚠️ "EVERY BOX FILLS" IS AGAINST THE #247/#319 PRECEDENT, NOT LITERAL. Record-
// derived metadata boxes the record cannot answer (PATIENT DOB / ID / AGE / DD /
// DT) are POLICY BLANKS — attested blank, not fill failures. The gate: every field
// is either FILLED or a policy blank; an unmapped box (concept === null) refuses.
// ============================================================================
import prisma from '@meddoc/db';
import { createHash } from 'node:crypto';

import { deriveSyntheticEncounter } from '@/lib/template-twin/synthetic-front-half';
import type { TemplateTwinActor } from '@/lib/template-twin/certification-lifecycle';
import { EncounterFactSchema, type EncounterFact } from '@/lib/template-twin/ir';
import { canvasHash } from '@/lib/pdf-native/hash';

import {
  readDetectedForm,
  markDetectedFormCertified,
  getTemplateCanvas,
  type StoredDetectedField,
  type StoredDetectedForm,
} from './detected-form-store';
import { deriveDetectedFormValues } from './derive-values';
import { DETERMINISTICALLY_FILLED_HEADER_KEYS } from './fill-from-note';
import { fillDetectedForm } from './fill-boxes';
import { verifyFidelity, isPixelIdenticalOutsideBoxes } from './verify-fidelity';
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
 *  clinical/section box OR a metadata field on a deterministically-filled header
 *  key. A record-derived metadata field on any other key is a POLICY BLANK. */
export function fieldExpectedToFill(field: StoredDetectedField): boolean {
  if (field.headerKey === null) return true;
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

/** One affirmed, PHI-free synthetic fact for a clinical concept — the shape
 *  `projectEncounterFacts` emits, so the resolver treats it identically. */
export function syntheticFactFor(concept: string, seed: string): EncounterFact {
  return EncounterFactSchema.parse({
    factId: `ttfact_${createHash('sha256').update(`synthetic:${concept}:${seed}`).digest('hex').slice(0, 24)}`,
    sourceType: 'encounter_evidence',
    concept,
    value: 'Synthetic self-test value',
    polarity: 'affirmed',
    temporality: 'current',
    experiencer: 'patient',
    laterality: 'not_applicable',
    number: null,
    unit: null,
    speaker: null,
    sourceTranscriptOffsets: null,
    audioTimestampSeconds: null,
    evidenceAnchorIds: ['synthetic-self-test'],
    evidenceQuote: 'Clearly labeled synthetic self-test evidence, no patient identifiers.',
    quality: { asr: 'high', evidence: 'direct' },
  });
}

/** A synthetic note carrying a `## <label>` for each clinical/section box (so a
 *  note-split box would fill) + a synthetic surgeon line (so `procedure.surgeon`
 *  fills). PHI-free — gated by the caller through `deriveSyntheticEncounter`. */
export function buildSyntheticDetectedNote(fields: ReadonlyArray<StoredDetectedField>): string {
  const lines: string[] = ['Operating surgeon: Dr. Synthetic Example (self-test).', ''];
  for (const f of fields) {
    if (f.headerKey !== null) continue;
    const label = f.label.replace(/[:*_]+$/g, '').trim() || f.id;
    lines.push(`## ${label}`);
    lines.push(`Synthetic self-test content for "${label}" — no patient identifiers.`);
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
 * Certify a detected form. Proves on a synthetic visit that every fillable box
 * fills and the page is pixel-identical outside the boxes, then marks it
 * certified. Refuses (never certifies) on any failure, naming the offenders.
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

  // Every field must be MAPPED first (the doctor confirmed the sample-value
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
  if (canvasHash(canvas) !== form.canvasHash) {
    throw new DetectedFormCertifyError('STALE_CANVAS', 'The stored canvas no longer matches the detected form.');
  }

  // ── SYNTHETIC VISIT — a note (PHI-gated) + one affirmed fact per clinical box.
  const noteText = buildSyntheticDetectedNote(form.fields);
  await deriveSyntheticEncounter({
    deriveEncounter: () => ({ ok: true, text: noteText }) as never,
    actor: input.actor,
    totalFields: form.fields.length,
  });
  const facts = form.fields
    .filter((f) => f.headerKey === null && f.concept)
    .map((f) => syntheticFactFor(f.concept as string, f.id));

  const syntheticDate = new Date('2020-01-01T00:00:00.000Z');
  const { values } = deriveDetectedFormValues({
    fields: form.fields,
    facts,
    noteCtx: {
      patientName: 'SAMPLE PATIENT (SYNTHETIC)',
      visitDate: syntheticDate,
      noteText,
      dictationText: noteText,
    },
    allowUncertified: true,
  });

  // Every EXPECTED-TO-FILL field must have drawn a value; policy blanks may be empty.
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
  // AuditAction — no new enum value, #326 stays migration-free); the library logs
  // the proof structurally (PHI-safe: ids + counts only).
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
