// ============================================================================
// ONE-PIPELINE (#326) — the SAMPLE-VALUE PREVIEW of a detected form (step 3).
// Server-only. Produces the doctor's OWN blank page filled with clearly-synthetic
// SAMPLE values, so the doctor can SEE what the pipeline draws before any real
// visit. PHI-free (synthetic facts only). Returns bytes — persists nothing.
// ----------------------------------------------------------------------------
// Uses the SAME value path (`deriveDetectedFormValues`) and fill engine
// (`fillDetectedForm`) a real export takes and certification proves, so the
// preview is faithful to what a real visit will produce.
// ============================================================================
import prisma from '@meddoc/db';

import type { TemplateTwinActor } from '@/lib/template-twin/certification-lifecycle';

import { readDetectedForm, getTemplateCanvas } from './detected-form-store';
import { deriveDetectedFormValues } from './derive-values';
import { fillDetectedForm } from './fill-boxes';
import { syntheticFactFor, buildSyntheticDetectedNote } from './certify-detected-form';

export interface PreviewDetectedResult {
  pdf: Uint8Array;
  fieldCount: number;
  filledCount: number;
}

/**
 * Fill a detected form's blank canvas with clearly-synthetic SAMPLE values and
 * return the PDF bytes. Practice-scoped. Throws if the form/canvas is missing.
 */
export async function previewDetectedForm(input: {
  templateId: string;
  actor: TemplateTwinActor;
}): Promise<PreviewDetectedResult> {
  const row = await prisma.noteTemplate.findFirst({
    where: {
      id: input.templateId,
      doctorId: input.actor.userId,
      practiceId: input.actor.practiceId,
    },
    select: { styleProfile: true },
  });
  if (!row) throw new Error('preview: detected form template not found');
  const styleProfile = ((row.styleProfile ?? {}) as Record<string, unknown>) || {};
  const form = readDetectedForm(styleProfile);
  if (!form) throw new Error('preview: no detected form stored on this template');

  const canvas = await getTemplateCanvas(input.templateId);
  if (!canvas) throw new Error('preview: blank canvas missing');

  const noteText = buildSyntheticDetectedNote();
  const facts = form.fields
    .filter((f) => f.headerKey === null && f.concept)
    .map((f) => syntheticFactFor(f.concept as string, f.id));

  const { values, addenda } = deriveDetectedFormValues({
    fields: form.fields,
    facts,
    noteCtx: {
      patientName: 'SAMPLE PATIENT (SYNTHETIC)',
      visitDate: new Date('2020-01-01T00:00:00.000Z'),
      noteText,
      dictationText: noteText,
    },
    allowUncertified: true,
  });

  const filled = await fillDetectedForm({
    originalPdf: new Uint8Array(canvas),
    fields: form.fields,
    values,
    addenda,
  });

  return { pdf: filled.pdf, fieldCount: form.fields.length, filledCount: values.size };
}
