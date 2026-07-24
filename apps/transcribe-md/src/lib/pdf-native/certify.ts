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
import { extractHeaderFields, deriveHeaderFieldsFromRun } from '@/lib/note-template-parse/header-fields';
import { pdfToText } from '@/lib/note-template-parse/pdf-to-text';
import { normalizeExtractedText } from '@/lib/note-template-parse/extract-note-text';
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

async function loadTemplateShape(
  templateId: string,
  doctorId?: string
): Promise<{
  sections: NoteTemplateSection[];
  headerFields: NoteTemplateHeaderField[];
  styleProfile: Record<string, unknown>;
}> {
  // Scope by doctorId when provided (defense-in-depth — the action already checks
  // ownership, but the library must not be a way to touch another doctor's row).
  const row = await prisma.noteTemplate.findFirstOrThrow({
    where: doctorId ? { id: templateId, doctorId } : { id: templateId },
    select: { sections: true, styleProfile: true },
  });
  const styleProfile = ((row.styleProfile ?? {}) as Record<string, unknown>) || {};
  return {
    sections: (row.sections as unknown as NoteTemplateSection[]) ?? [],
    headerFields: (styleProfile.headerFields as NoteTemplateHeaderField[]) ?? [],
    styleProfile,
  };
}

/** Scoped styleProfile write (updateMany so a doctorId filter applies). */
async function writeStyleProfile(
  templateId: string,
  doctorId: string | undefined,
  styleProfile: Record<string, unknown>
): Promise<void> {
  await prisma.noteTemplate.updateMany({
    where: doctorId ? { id: templateId, doctorId } : { id: templateId },
    data: { styleProfile: styleProfile as never },
  });
}

/** Certify: store the canvas + re-extracted anchors on the template. Returns the
 *  anchors + any labels that did NOT anchor (surfaced, never silently dropped).
 *  When NO anchor resolves (not a fillable flat form), it neither stores a canvas
 *  nor marks certified — so a bad re-upload can never clobber a prior good cert. */
export async function certifyPdfTemplate(input: {
  templateId: string;
  pdfBytes: Buffer;
  /** When set, all reads/writes are scoped to this doctor's own row. */
  doctorId?: string;
}): Promise<{ anchors: PdfFillAnchor[]; missing: string[]; headerFields: NoteTemplateHeaderField[] }> {
  const { sections, headerFields: existingHeader, styleProfile } = await loadTemplateShape(
    input.templateId,
    input.doctorId
  );

  // Re-derive header fields from the PDF's OWN text using the template's canonical
  // section labels as the boundary. Deterministic (the PDF + stored labels, no
  // fresh LLM output) and FAR more robust than the parse-time capture whose
  // boundary collapses on label drift — so every (re-)cert REFRESHES the header
  // fields. Keep the parsed set only when the PDF yields none.
  let headerFields = existingHeader;
  try {
    // Use the SAME text pipeline as the upload parser (pdfToText → normalize) so
    // the line structure extractHeaderFields depends on matches — raw extractText
    // merges runs differently and defeats the boundary.
    const pdfText = normalizeExtractedText(await pdfToText(new Uint8Array(input.pdfBytes).slice()));
    const specSections = sections.map((s) => ({ label: s.label }));
    // Line-based first (multi-line forms); fall back to the run-aware derivation
    // for flat forms whose text layer flattens to a single line.
    let derived = extractHeaderFields(pdfText, specSections);
    if (derived.length === 0) derived = deriveHeaderFieldsFromRun(pdfText, specSections);
    if (derived.length > 0) headerFields = derived as NoteTemplateHeaderField[];
  } catch {
    // Text-layer extraction failed → keep whatever headerFields were parsed.
  }

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

  // Not a fillable flat form → do NOT store a canvas or mark certified (never
  // overwrite a prior good cert with a bad upload). Flag pending so the CTA
  // persists; leave any existing canvas + cert intact.
  if (anchors.length === 0) {
    await writeStyleProfile(input.templateId, input.doctorId, {
      ...styleProfile,
      pdfNativePendingPreview: true,
    });
    return { anchors, missing, headerFields };
  }

  await putTemplateCanvas(input.templateId, input.pdfBytes);
  await writeStyleProfile(input.templateId, input.doctorId, {
    ...styleProfile,
    // Persist the (refreshed) header fields so the styled export + the native
    // header block both fill even when the parse-time capture missed them.
    headerFields: headerFields as unknown,
    pdfNativeAnchors: anchors as unknown,
    pdfNativeCertified: true,
    // Durable-cert signatures — let a future re-upload (new template id) carry
    // this cert forward instead of silently falling back to styled.
    pdfNativeCanvasHash: canvasHash(input.pdfBytes),
    pdfNativeStructureHash: templateStructureHash(sections, headerFields),
    // A fresh cert clears any prior "needs preview" marker.
    pdfNativePendingPreview: false,
  });
  return { anchors, missing, headerFields };
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
