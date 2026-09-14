'use server';

// ============================================================================
// previewNativeDocumentAction — show the doctor THEIR OWN PAGE, filled.
// ----------------------------------------------------------------------------
// Until now the "sample" on the settings screen was a block of markdown in a
// <pre>: our fonts, our spacing, our idea of a heading. A doctor looking at it
// could tell whether we had understood their SECTIONS, but not whether their
// document would come back looking like their document. That is the only
// question they actually have.
//
// So the sample is now the certification's own filled artifact, rendered as a
// paginated PDF of their form. Nothing new is generated here:
//
//   DOCX source  the proof DOCX certification already stored
//                (latestTestOutputObjectKey — the exact bytes the roundtrip
//                verified) -> Gotenberg -> PDF
//   PDF source   previewPdfTemplateFill, the existing native path, unchanged
//
// Because the bytes are the ones certification proved, the preview cannot
// flatter the template: if the fill is thin, the doctor sees it thin.
//
// FAILURE IS NOT A BLOCKER. Every failure path returns a named reason plus the
// raw DOCX for the browser to draw. A preview never gates certify, export or
// sign, and this action is not reachable from any of them.
// ============================================================================

import prisma from '@meddoc/db';

import { requireSession } from '@/lib/auth';
import { convertDocxToPdf, type ConvertFailure } from '@/lib/docx-preview/convert';
import { previewPdfTemplateFill } from '@/lib/pdf-native/certify';
import { loadCertifiedTwinFields } from '@/lib/pdf-native/twin-export-data';
import { getTemplateCanvas } from '@/lib/pdf-native/store';
import { createTemplateTwinArtifactStore } from '@/lib/template-twin/storage';

export type NativePreviewKind = 'pdf' | 'docx_fallback';

export type NativePreviewError =
  /** No certified native template — the doctor has nothing to preview yet. */
  | 'no_native_template'
  /** Certified, but the proof artifact is gone (storage down, or pruned). */
  | 'sample_unavailable'
  /** The stored artifact no longer matches the hash certification recorded.
   *  Security-relevant, and NOT the same as storage being unavailable. */
  | 'sample_integrity'
  /** The doctor PASTED text rather than uploading a form. There is no page to
   *  show, and inventing one would be the mock we just deleted. */
  | 'no_form_uploaded'
  | ConvertFailure;

export interface NativePreviewResult {
  ok: boolean;
  kind: NativePreviewKind | null;
  /** base64 — a PDF when kind==='pdf', the true DOCX when 'docx_fallback'. */
  data: string | null;
  /** Named, PHI-free, and SURFACED. Present whenever the PDF path was missed,
   *  including when a fallback succeeded — silence is illegal. */
  reason: NativePreviewError | null;
}

function fail(reason: NativePreviewError): NativePreviewResult {
  return { ok: false, kind: null, data: null, reason };
}

export async function previewNativeDocumentAction(
  noteTemplateId: string,
): Promise<NativePreviewResult> {
  const session = await requireSession();

  // Ownership is a WHERE clause, not a check after the fact.
  const row = await prisma.noteTemplate.findFirst({
    where: { id: noteTemplateId, doctorId: session.user.id },
    select: {
      id: true,
      sections: true,
      styleProfile: true,
      templateTwinCompiledVersion: {
        select: {
          // practiceId lives on the SOURCE ARTIFACT, not the compiled version —
          // the tenant owns the uploaded file, and every artifact key is scoped
          // to it. Reading it from the wrong row throws at request time.
          sourceArtifact: { select: { practiceId: true } },
          latestTestOutputObjectKey: true,
          latestTestOutputSha256: true,
        },
      },
    },
  });
  if (!row) return fail('no_native_template');

  // ---- PDF source: the existing native path already renders a real page. ----
  const canvas = await getTemplateCanvas(row.id);
  if (canvas) {
    try {
      const style = (row.styleProfile ?? {}) as Record<string, unknown>;
      // S2-4 (#322): when the template's twin is CERTIFIED, the preview derives
      // its anchors from the twin's OWN fields — the SAME renderer the visit
      // export uses — so the settings preview and a real export are the same
      // page shape. Otherwise the note-template section/header labels stand.
      const twinFields = await loadCertifiedTwinFields(
        row.id,
        session.user.practiceId,
      ).catch(() => null);
      const filled = await previewPdfTemplateFill({
        sections: ((row.sections ?? []) as unknown) as ReadonlyArray<{
          key: string;
          label: string;
        }>,
        headerFields: (style.headerFields ?? []) as ReadonlyArray<{
          key: string;
          label: string;
        }>,
        pdfBytes: canvas,
        twinFields: twinFields ?? undefined,
      });
      return {
        ok: true,
        kind: 'pdf',
        data: Buffer.from(filled).toString('base64'),
        reason: null,
      };
    } catch {
      console.warn('[native-preview] pdf sample unavailable; nothing is blocked');
      return fail('sample_unavailable');
    }
  }

  // ---- DOCX source: the artifact certification itself verified. ----
  const twin = row.templateTwinCompiledVersion;
  if (!twin?.latestTestOutputObjectKey || !twin.latestTestOutputSha256) {
    return fail('no_native_template');
  }

  let docx: Buffer;
  try {
    const store = createTemplateTwinArtifactStore();
    docx = await store.readOutputArtifact({
      practiceId: twin.sourceArtifact.practiceId,
      objectKey: twin.latestTestOutputObjectKey,
      expectedSha256: twin.latestTestOutputSha256,
    });
  } catch (err) {
    // Log the error CLASS (PHI-free) — collapsing an integrity failure into
    // "storage hiccup" hides the one case that matters.
    const cls = err instanceof Error ? err.constructor.name : 'Unknown';
    console.warn(`[native-preview] proof artifact unreadable (${cls}); nothing is blocked`);
    return fail(cls.includes('Integrity') ? 'sample_integrity' : 'sample_unavailable');
  }

  const converted = await convertDocxToPdf(docx, 'sample.docx');
  if (converted.pdf) {
    return {
      ok: true,
      kind: 'pdf',
      data: Buffer.from(converted.pdf).toString('base64'),
      reason: null,
    };
  }

  // The sidecar was slow, unhealthy, or not deployed. The doctor still sees
  // their document — the browser draws the same bytes. ok:true because the
  // preview SUCCEEDED; `reason` says which engine drew it.
  return {
    ok: true,
    kind: 'docx_fallback',
    data: docx.toString('base64'),
    reason: converted.reason,
  };
}
