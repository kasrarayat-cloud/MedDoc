'use server';

// ============================================================================
// previewUploadedFormAction — the confirm card's document, from the bytes the
// doctor just handed us.
// ----------------------------------------------------------------------------
// The confirm card runs BEFORE anything is activated or certified, so there is
// no stored artifact to show yet. What there is — and all a doctor wants at this
// moment — is their own file:
//
//   flat PDF   previewPdfTemplateFill: their page, with sample answers sitting
//              in their actual blanks. This is the same render the old
//              "Set up native export → preview" step produced, moved to the
//              moment they are deciding.
//   DOCX       their form, converted for display. Unfilled, and labelled as
//              such: at this point we can honestly show the page, not the fill.
//
// What it REPLACES is a markdown mock in our fonts. That mock answered "did we
// read your sections", which is our question, not theirs.
//
// NOTHING IS PERSISTED. The bytes are read from the request, rendered, and
// dropped. No template row, no artifact, no visit — this action writes nothing.
// ============================================================================

import { requireSession } from '@/lib/auth';
import { convertDocxToPdf } from '@/lib/docx-preview/convert';
import { previewPdfTemplateFill } from '@/lib/pdf-native/certify';

import type { NativePreviewResult } from './preview-native-document';

/** Matches the upload path's own ceiling (extract-note-file). A narrower cap
 *  here would refuse to preview forms that parse and certify perfectly well. */
const MAX_BYTES = 5 * 1024 * 1024;

export async function previewUploadedFormAction(
  fd: FormData,
): Promise<NativePreviewResult> {
  await requireSession();

  const file = fd.get('file');
  if (!(file instanceof File) || file.size === 0 || file.size > MAX_BYTES) {
    return { ok: false, kind: null, data: null, reason: 'sample_unavailable' };
  }

  let sections: ReadonlyArray<{ key: string; label: string }> = [];
  let headerFields: ReadonlyArray<{ key: string; label: string }> = [];
  try {
    sections = JSON.parse(String(fd.get('sections') ?? '[]'));
    headerFields = JSON.parse(String(fd.get('headerFields') ?? '[]'));
  } catch {
    // The page still renders, but with NO sample answers in it — and the
    // caption promises answers. Say which one the doctor is looking at.
    sections = [];
    headerFields = [];
  }

  const bytes = Buffer.from(await file.arrayBuffer());
  const isPdf = bytes.subarray(0, 4).toString('latin1') === '%PDF';

  if (isPdf) {
    try {
      const filled = await previewPdfTemplateFill({ sections, headerFields, pdfBytes: bytes });
      return {
        ok: true,
        kind: 'pdf',
        data: Buffer.from(filled).toString('base64'),
        reason: null,
      };
    } catch {
      console.warn('[upload-preview] could not fill the uploaded PDF; nothing is blocked');
      return { ok: false, kind: null, data: null, reason: 'sample_unavailable' };
    }
  }

  // A constant, never the upload's own name — filenames are user-controlled and
  // routinely carry patient identifiers.
  const converted = await convertDocxToPdf(bytes, 'form.docx');
  if (converted.pdf) {
    return {
      ok: true,
      kind: 'pdf',
      data: Buffer.from(converted.pdf).toString('base64'),
      reason: null,
    };
  }
  // Sidecar unavailable — hand the true bytes to the browser to draw.
  return {
    ok: true,
    kind: 'docx_fallback',
    data: bytes.toString('base64'),
    reason: converted.reason,
  };
}
