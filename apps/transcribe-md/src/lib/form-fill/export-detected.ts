// ============================================================================
// ONE-PIPELINE (ruling #326, Slice B) — per-visit EXPORT of a detected form.
// Server-only. Returns the doctor's OWN blank page with the visit's answers drawn
// into the detected boxes, or null to fall back to the styled generator.
// Deterministic; NO AI. Gated: flag ON + a CERTIFIED detected form (canvas + form
// stored). Mirrors `nativePdfExport`'s guard ladder + visible reason.
// ============================================================================
import prisma from '@meddoc/db';
import { redactPhi } from '@meddoc/ai';

import { visitByIdScope, type PracticeId } from '@/lib/practice-scope';
import { formDetectFillEnabled } from '@/config/form-detect-fill';
import { sanitizeExportedSoap } from '@/lib/visit-export';
import { canvasHash } from '@/lib/pdf-native/hash';
import {
  projectEncounterFacts,
  type EncounterEntitySnapshot,
} from '@/lib/template-twin/encounter-facts';
import type { EncounterFact } from '@/lib/template-twin/ir';

import { readDetectedForm, isDetectedFormCertified, getTemplateCanvas } from './detected-form-store';
import { deriveDetectedFormValues } from './derive-values';
import { fillDetectedForm } from './fill-boxes';

/** Why detected-form fill did or did not apply — logged + surfaced on every export
 *  so a silent styled fallback is never invisible. `'true'` = the doctor's own
 *  page was returned. */
export type DetectedFormReason =
  | 'true'
  | 'flag_off'
  | 'not_certified'
  | 'no_form'
  | 'no_canvas'
  | 'stale_canvas'
  | 'nothing_to_fill'
  // Coded only — NEVER carries raw error text (which can echo patient characters).
  | 'fill_error';

export interface DetectedFormResult {
  pdf: Buffer | null;
  applied: boolean;
  reason: DetectedFormReason;
  /** fields whose value overflowed their boxes onto a continuation page. */
  overflowed?: number;
}

/**
 * Build the detected-form-filled PDF for a visit + WHY it did or did not apply.
 * `pdf` is null unless `reason` is `'true'`.
 */
export async function detectedFormExport(
  visitId: string,
  practiceId: PracticeId,
): Promise<DetectedFormResult> {
  const miss = (reason: DetectedFormReason): DetectedFormResult => ({
    pdf: null,
    applied: false,
    reason,
  });

  if (!formDetectFillEnabled()) return miss('flag_off');

  const visit = await prisma.transcribeVisit.findFirst({
    where: { ...visitByIdScope(visitId, practiceId), deletedAt: null },
    select: {
      patientName: true,
      status: true,
      createdAt: true,
      signedAt: true,
      soapFinal: true,
      signedSoap: true,
      rawTextInput: true,
      entities: true,
      noteTemplate: { select: { id: true, styleProfile: true } },
    },
  });
  if (!visit || !visit.noteTemplate) return miss('not_certified');

  const sp = ((visit.noteTemplate.styleProfile ?? {}) as Record<string, unknown>) || {};
  if (!isDetectedFormCertified(sp)) return miss('not_certified');
  const form = readDetectedForm(sp);
  if (!form) return miss('no_form'); // certified flag set but the stored form is unusable

  const canvas = await getTemplateCanvas(visit.noteTemplate.id);
  if (!canvas) return miss('no_canvas');
  // Integrity: the certified canvas must still match its recorded hash (the
  // pdf-native rule — never draw answers onto a swapped/corrupted page).
  if (canvasHash(canvas) !== form.canvasHash) return miss('stale_canvas');

  try {
    const raw =
      visit.status === 'SIGNED' ? visit.signedSoap ?? visit.soapFinal ?? '' : visit.soapFinal ?? '';
    const noteText = sanitizeExportedSoap(raw);

    // Project the visit's STORED L3 entities → facts (deterministic; NO AI at
    // export — the projection is not extraction). No entities → no facts, so every
    // concept box routes to the note-heading split (tier 2), which is safe.
    let facts: EncounterFact[] = [];
    if (visit.entities) {
      facts = projectEncounterFacts({
        mode: 'text',
        contextText: noteText,
        entities: visit.entities as unknown as EncounterEntitySnapshot,
        asrQuality: 'unknown',
      });
    }

    // Ruling #115 — the ENCOUNTER date (createdAt) fills date-of-service, never the
    // signing date. The signing line, when signed, is added by the fill engine.
    const { values, addenda } = deriveDetectedFormValues({
      fields: form.fields,
      facts,
      noteCtx: {
        patientName: visit.patientName,
        visitDate: visit.createdAt,
        noteText,
        dictationText: visit.rawTextInput,
      },
      allowUncertified: false,
    });
    if (values.size === 0) return miss('nothing_to_fill'); // no box has a value → styled

    const filled = await fillDetectedForm({
      originalPdf: new Uint8Array(canvas),
      fields: form.fields,
      values,
      // Unmatched note sections (and ruled-blank boxes' prose) → continuation
      // page, never dropped from the exported record.
      addenda,
    });
    return {
      pdf: Buffer.from(filled.pdf),
      applied: true,
      reason: 'true',
      overflowed: filled.overflowed.length,
    };
  } catch (err) {
    console.error(
      '[form-detect] fill failed:',
      redactPhi(err instanceof Error ? err.message : String(err)),
    );
    return miss('fill_error');
  }
}
