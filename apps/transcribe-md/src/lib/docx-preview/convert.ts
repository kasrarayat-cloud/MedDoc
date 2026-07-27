// ============================================================================
// DOCX → PDF, for PREVIEW ONLY.
// ----------------------------------------------------------------------------
// A doctor should be able to see their own form, filled, before they trust it
// with a patient's note. Rendering Word layout faithfully needs a Word-class
// renderer, so a Gotenberg sidecar does the conversion.
//
// THE RULE THAT SHAPES THIS FILE: a preview may never gate clinical work.
// Certification, export and signing do not call it and must not learn to. If
// the sidecar is slow, unhealthy, or simply not deployed, this returns null and
// the caller renders the TRUE BYTES in the browser instead — the doctor still
// sees their document, just drawn by a different engine. A preview that can
// block a signature would be worse than no preview at all.
//
// WHERE THE BYTES GO: the filled DOCX (which carries PHI) crosses the internal
// `converter` Docker network to a service with no route off the host, is
// converted in a tmpfs, and comes back as a PDF. Nothing about it is written to
// disk and there is no volume to retain it. See docker-compose.yml → gotenberg.
// ============================================================================

/** Hard ceiling. Gotenberg's own api-timeout is 25s; we give up first so a
 *  wedged sidecar can never hold a request open longer than this. */
const CONVERT_TIMEOUT_MS = 12_000;

const GOTENBERG_URL =
  process.env.GOTENBERG_URL ?? 'http://gotenberg:3000/forms/libreoffice/convert';

/** A rendered page is a few hundred KB; 40 MB is a generous ceiling and a hard
 *  stop. Without one, a wedged sidecar can stream an arbitrary body straight
 *  into the app container's heap. */
const MAX_PDF_BYTES = 40 * 1024 * 1024;

export type ConvertFailure =
  | 'timeout'
  | 'converter_error'
  | 'empty_result'
  /** The response exceeded MAX_PDF_BYTES and was abandoned. */
  | 'too_large';

export interface ConvertResult {
  /** The rendered PDF, or null when the caller must fall back. */
  pdf: Uint8Array | null;
  /** Always present when pdf is null. Named, surfaced, PHI-free. */
  reason: ConvertFailure | null;
}

/**
 * Convert a DOCX to PDF for display. NEVER throws — every failure path returns
 * a named reason so the caller can fall back silently and log honestly.
 */
export async function convertDocxToPdf(
  docx: Uint8Array,
  filename = 'document.docx',
): Promise<ConvertResult> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), CONVERT_TIMEOUT_MS);
  try {
    const form = new FormData();
    form.set(
      'files',
      new Blob([docx as unknown as BlobPart], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      }),
      filename,
    );
    const res = await fetch(GOTENBERG_URL, {
      method: 'POST',
      body: form,
      signal: controller.signal,
    });
    if (!res.ok) {
      console.warn(`[docx-preview] converter returned ${res.status}; falling back`);
      return { pdf: null, reason: 'converter_error' };
    }
    const declared = Number(res.headers.get('content-length') ?? '0');
    if (declared > MAX_PDF_BYTES) {
      console.warn('[docx-preview] converter response over cap; falling back');
      return { pdf: null, reason: 'too_large' };
    }
    const buf = new Uint8Array(await res.arrayBuffer());
    if (buf.byteLength === 0) return { pdf: null, reason: 'empty_result' };
    if (buf.byteLength > MAX_PDF_BYTES) {
      console.warn('[docx-preview] converter response over cap; falling back');
      return { pdf: null, reason: 'too_large' };
    }
    return { pdf: buf, reason: null };
  } catch (err) {
    const timedOut = err instanceof Error && err.name === 'AbortError';
    console.warn(
      `[docx-preview] ${timedOut ? 'timeout' : 'converter unreachable'}; falling back to ` +
        'client-side rendering of the true bytes',
    );
    return { pdf: null, reason: timedOut ? 'timeout' : 'converter_error' };
  } finally {
    clearTimeout(timer);
  }
}
