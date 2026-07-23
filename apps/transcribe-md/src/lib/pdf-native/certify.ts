// ============================================================================
// PDF native certify + preview-once (feat/pdf-native-fill). Server-only.
// Certify: extract label anchors from the doctor's blank PDF (once), store the
// canvas bytes + anchors on the template, mark it certified. Preview: a one-time
// synthetic fill so the doctor confirms the regions land before real use.
// Anchors are re-derivable + never client-trusted (re-extracted here).
// ============================================================================
import prisma from '@meddoc/db';
import { getDocumentProxy } from 'unpdf';

import { extractPdfAnchors, missingAnchors, type AnchorLabelSpec } from './anchors';
import { fillPdfTemplate, type PdfFillAnchor } from './fill-engine';
import { putTemplateCanvas } from './store';
import { canvasHash, templateStructureHash } from './hash';
import type {
  NoteTemplateSection,
  NoteTemplateHeaderField,
} from '@/worker/note-templates/system-default-template';

/** Header fields → inline anchors; sections → block anchors, in reading order. */
export function anchorSpecsFor(
  sections: ReadonlyArray<{ key: string; label: string }>,
  headerFields: ReadonlyArray<{ key: string; label: string }>
): AnchorLabelSpec[] {
  return [
    ...headerFields.map((f) => ({ key: f.key, label: f.label, kind: 'inline' as const })),
    ...sections.map((s) => ({ key: s.key, label: s.label, kind: 'block' as const })),
  ];
}

async function loadTemplateShape(templateId: string): Promise<{
  sections: NoteTemplateSection[];
  headerFields: NoteTemplateHeaderField[];
  styleProfile: Record<string, unknown>;
}> {
  const row = await prisma.noteTemplate.findUniqueOrThrow({
    where: { id: templateId },
    select: { sections: true, styleProfile: true },
  });
  const styleProfile = ((row.styleProfile ?? {}) as Record<string, unknown>) || {};
  return {
    sections: (row.sections as unknown as NoteTemplateSection[]) ?? [],
    headerFields: (styleProfile.headerFields as NoteTemplateHeaderField[]) ?? [],
    styleProfile,
  };
}

/** Certify: store the canvas + re-extracted anchors on the template. Returns the
 *  anchors + any labels that did NOT anchor (surfaced, never silently dropped). */
export async function certifyPdfTemplate(input: {
  templateId: string;
  pdfBytes: Buffer;
}): Promise<{ anchors: PdfFillAnchor[]; missing: string[] }> {
  const { sections, headerFields, styleProfile } = await loadTemplateShape(input.templateId);
  const specs = anchorSpecsFor(sections, headerFields);

  // getDocumentProxy detaches its input buffer → give each pass its own copy.
  const missing = await missingAnchors(
    (await getDocumentProxy(new Uint8Array(input.pdfBytes).slice())) as never,
    specs
  );
  const anchors = await extractPdfAnchors(
    (await getDocumentProxy(new Uint8Array(input.pdfBytes).slice())) as never,
    specs
  );

  await putTemplateCanvas(input.templateId, input.pdfBytes);
  await prisma.noteTemplate.update({
    where: { id: input.templateId },
    data: {
      styleProfile: {
        ...styleProfile,
        pdfNativeAnchors: anchors as unknown,
        pdfNativeCertified: true,
        // Durable-cert signatures — let a future re-upload (new template id) carry
        // this cert forward instead of silently falling back to styled.
        pdfNativeCanvasHash: canvasHash(input.pdfBytes),
        pdfNativeStructureHash: templateStructureHash(sections, headerFields),
        // A fresh cert clears any prior "needs preview" marker.
        pdfNativePendingPreview: false,
      } as never,
    },
  });
  return { anchors, missing };
}

/** Preview-once: fill the anchors with SYNTHETIC text so the doctor confirms the
 *  regions before real use (no visit, no patient data). */
export async function previewPdfTemplateFill(input: {
  sections: ReadonlyArray<{ key: string; label: string }>;
  headerFields: ReadonlyArray<{ key: string; label: string }>;
  pdfBytes: Buffer;
}): Promise<Uint8Array> {
  const specs = anchorSpecsFor(input.sections, input.headerFields);
  const anchors = await extractPdfAnchors(
    (await getDocumentProxy(new Uint8Array(input.pdfBytes).slice())) as never,
    specs
  );
  const texts: Record<string, string> = {};
  for (const s of specs) {
    texts[s.key] =
      s.kind === 'inline'
        ? '[sample value]'
        : `Sample ${s.label.replace(/:$/, '').toLowerCase()} content — this is where the generated answer for this section will appear when you export a real visit.`;
  }
  return fillPdfTemplate({
    canvasPdf: new Uint8Array(input.pdfBytes),
    anchors,
    texts,
    signedStatusLine: 'PREVIEW · synthetic content · QuillMD',
  });
}
