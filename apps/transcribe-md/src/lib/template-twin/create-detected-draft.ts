// ============================================================================
// ONE-PIPELINE (ruling #326, Slice B) — the DETECTED-form upload path. A PDF
// upload is detected (FFDNet sidecar) → grouped → mapped to concepts → persisted
// as a self-contained detected form on a fresh NoteTemplate (styleProfile.formDetect
// + the blank canvas). Server-only. prisma singleton + logTwinAudit.
// ----------------------------------------------------------------------------
// This is the #326 replacement for the DOCX-twin derivation of a PDF upload. It
// mints NO twin source-artifact / compiled-version / field-definition rows — the
// detected form lives entirely on the NoteTemplate (styleProfile) + the shared
// pdf-native canvas store — so there is NO schema migration and the DOCX-twin
// columns stay byte-stable (#217). Behind `formDetectFillEnabled()`; nothing
// reaches it while the flag is OFF.
// ============================================================================
import { randomUUID } from 'node:crypto';

import prisma from '@meddoc/db';
import { Prisma } from '@prisma/client';

import { logTwinAudit as logAudit } from './twin-audit';
import {
  detectFormFields,
  groupDetectedFields,
  mapFieldsToConcepts,
  persistDetectedForm,
  headerKeyForConcept,
  type StoredDetectedField,
  type StoredDetectedForm,
} from '@/lib/form-fill';
import { canvasHash } from '@/lib/pdf-native/hash';
import type { CreateTemplateTwinDraftResult } from './create-draft';

/** Build the persisted field list: join each grouped detected box to its mapped
 *  concept + source class, and derive the export-routing header key. */
function toStoredFields(
  grouped: ReturnType<typeof groupDetectedFields>,
  mapped: ReturnType<typeof mapFieldsToConcepts>,
): StoredDetectedField[] {
  const conceptById = new Map(mapped.map((m) => [m.fieldId, m]));
  return grouped.map((f) => {
    const m = conceptById.get(f.id);
    const concept = m?.concept ?? null;
    return {
      id: f.id,
      label: f.label,
      page: f.page,
      boxes: f.boxes,
      multiline: f.multiline,
      concept,
      sourceType: m?.sourceType ?? 'extraction',
      headerKey: headerKeyForConcept(concept),
    };
  });
}

export async function createDetectedFormDraft(input: {
  /** the ORIGINAL uploaded PDF (the canvas the visit export fills). */
  pdf: Uint8Array;
  actor: { userId: string; userEmail: string; practiceId: string };
  attachToNoteTemplateId?: string;
}): Promise<CreateTemplateTwinDraftResult> {
  // ── DETECT → GROUP → MAP (once per template; the doctor confirms in preview).
  const detected = await detectFormFields(input.pdf);
  const grouped = groupDetectedFields(detected);
  const mapped = mapFieldsToConcepts(grouped);
  const fields = toStoredFields(grouped, mapped);

  const canvas = Buffer.from(input.pdf);
  const form: StoredDetectedForm = {
    model: detected.model,
    detector: detected.detector,
    canvasHash: canvasHash(canvas),
    pageCount: detected.pages.length,
    fields,
  };

  // ── MINT (or attach to) a NoteTemplate. The detected form is self-contained on
  // styleProfile; sections/headerFields are derived from the fields so a visit's
  // note generation produces `## <label>` sections the export split can fill.
  const noteTemplateId = input.attachToNoteTemplateId ?? randomUUID();
  const sections = fields
    .filter((f) => f.headerKey === null)
    .map((f) => ({ key: f.id, label: f.label.replace(/[:*_]+$/g, '').trim() || f.id }));
  const headerFields = fields
    .filter((f) => f.headerKey !== null)
    .map((f, i) => ({ key: f.headerKey as string, label: f.label, order: i + 1 }));

  if (!input.attachToNoteTemplateId) {
    await prisma.noteTemplate.create({
      data: {
        id: noteTemplateId,
        doctorId: input.actor.userId,
        // T7 — the practice_iff_doctor biconditional pairs these two.
        practiceId: input.actor.practiceId,
        name: 'Uploaded form (detected)',
        encounterType: null,
        sections: sections as unknown as Prisma.InputJsonValue,
        styleProfile: { headerFields } as unknown as Prisma.InputJsonValue,
        specialtyBaseline: null,
        version: 1,
        status: 'draft',
        isSystemDefault: false,
      },
    });
  }

  // ── PERSIST the detected form + canvas (sets formDetectPendingPreview).
  await persistDetectedForm({
    templateId: noteTemplateId,
    doctorId: input.actor.userId,
    form,
    canvas,
  });

  await logAudit({
    action: 'TEMPLATE_TWIN_SOURCE_UPLOADED',
    targetType: 'NoteTemplate',
    targetId: noteTemplateId,
    userId: input.actor.userId,
    userEmail: input.actor.userEmail,
    practiceId: input.actor.practiceId,
    metadata: {
      pipeline: 'form_detect',
      model: detected.detector.model,
      weightsSha: detected.detector.weightsSha,
      fieldCount: fields.length,
      mappedCount: fields.filter((f) => f.concept !== null).length,
      pageCount: detected.pages.length,
    },
  });

  const needsConfirm = fields.filter((f) => f.concept === null).length;
  return {
    noteTemplateId,
    sourceSha256: form.canvasHash,
    compilerVersion: `form-detect/${detected.detector.commonformsVersion}`,
    fieldCount: fields.length,
    blockingUnsupportedCount: needsConfirm,
    usedFallbackMappings: false,
  };
}
