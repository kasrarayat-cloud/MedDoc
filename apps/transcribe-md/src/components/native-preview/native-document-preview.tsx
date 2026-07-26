'use client';

// ============================================================================
// The doctor's own page, on screen.
// ----------------------------------------------------------------------------
// Two engines, one promise: whatever is drawn here came from the bytes the
// certification verified — never a re-typeset approximation.
//
//   kind 'pdf'            the converted PDF, drawn page by page to canvas with
//                         pdf.js. NOT an <object>: a browser without a PDF
//                         plugin — headless Chromium, and Chrome on Android —
//                         renders that as a BLANK WHITE RECTANGLE, which a
//                         doctor reads as "my form came back empty". Drawing it
//                         ourselves is the same pixels everywhere, and it is
//                         verifiable in QA, which the plugin path was not.
//   kind 'docx_fallback'  the sidecar was unreachable, so the browser draws the
//                         SAME DOCX with docx-preview. Layout is close rather
//                         than exact, and we say so rather than pretending.
//
// The fallback is loaded with a dynamic import so its ~200 KB never enters the
// bundle of a doctor whose converter is healthy.
// ============================================================================

import { useEffect, useRef, useState } from 'react';

import type { NativePreviewError, NativePreviewKind } from '@/actions/preview-native-document';

/** Doctor-facing, PHI-free. Every reason has a sentence — silence is illegal. */
const REASON_TEXT: Record<NativePreviewError, string> = {
  no_native_template: 'This template fills our styled layout, not your own form.',
  sample_unavailable: "We couldn't load the sample this time. Your template is unaffected.",
  no_form_uploaded:
    'You pasted a note rather than uploading a form, so there is no page to show — your sections were read from the text.',
  sample_integrity:
    "This sample no longer matches what was certified, so we're not showing it. Your exports are unaffected — re-run setup to refresh it.",
  too_large: 'Showing a close preview — the exact page render came back too large.',
  timeout: 'Showing a close preview — exact page rendering timed out.',
  converter_error: 'Showing a close preview — exact page rendering is unavailable right now.',
  empty_result: 'Showing a close preview — exact page rendering returned nothing.',
};

export interface NativeDocumentPreviewProps {
  kind: NativePreviewKind | null;
  /** base64: a PDF when kind==='pdf', the true DOCX when 'docx_fallback'. */
  data: string | null;
  reason: NativePreviewError | null;
  /** Accessible label; the caller knows whether this is a sample or a visit. */
  label: string;
  /** One line under the page, in the doctor's language, saying what they are
   *  looking at. Blank fields on an unfilled form read as a defect unless we
   *  say plainly that they are blanks. */
  caption?: string;
  className?: string;
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

export function NativeDocumentPreview(props: NativeDocumentPreviewProps) {
  const { kind, data, reason, label } = props;
  const docxHost = useRef<HTMLDivElement | null>(null);
  const [docxFailed, setDocxFailed] = useState(false);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const pdfHost = useRef<HTMLDivElement | null>(null);
  const [pdfDrawn, setPdfDrawn] = useState(false);
  const [pdfFailed, setPdfFailed] = useState(false);

  // Draw every page. Kept in one effect so a re-render cannot leave half a
  // document on screen: the host is cleared, then filled, or the whole thing
  // reports failure.
  // Reset on new input FIRST: a failure from a previous document must not
  // outlive it, or a good render shows as broken.
  useEffect(() => {
    setPdfFailed(false);
    setPdfDrawn(false);
    setDocxFailed(false);
  }, [kind, data]);

  useEffect(() => {
    if (kind !== 'pdf' || !data) return undefined;
    let cancelled = false;
    const bytes = base64ToBytes(data);
    // The download escape hatch is offered regardless of how drawing goes.
    const url = URL.createObjectURL(
      new Blob([bytes.slice() as unknown as BlobPart], { type: 'application/pdf' }),
    );
    setPdfUrl(url);

    (async () => {
      try {
        const pdfjs = await import('pdfjs-dist');
        // Same-origin worker; no CDN, which the app's CSP would refuse anyway.
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          'pdfjs-dist/build/pdf.worker.min.mjs',
          import.meta.url,
        ).toString();
        const doc = await pdfjs.getDocument({ data: bytes.slice() }).promise;
        const host = pdfHost.current;
        if (cancelled || !host) return;
        host.replaceChildren();
        // 2x for legibility on the hidpi screens most doctors read on; the
        // canvas is laid out at CSS width so it still fits a phone.
        const dpr = Math.min(2, typeof window === 'undefined' ? 1 : window.devicePixelRatio || 1);
        for (let n = 1; n <= doc.numPages; n += 1) {
          const page = await doc.getPage(n);
          if (cancelled) return;
          const viewport = page.getViewport({ scale: 1.5 * dpr });
          const canvas = document.createElement('canvas');
          canvas.width = Math.floor(viewport.width);
          canvas.height = Math.floor(viewport.height);
          canvas.className = 'qm-npv-page';
          canvas.setAttribute('role', 'img');
          canvas.setAttribute('aria-label', `${label} — page ${n} of ${doc.numPages}`);
          const ctx = canvas.getContext('2d');
          if (!ctx) throw new Error('no 2d context');
          await page.render({ canvasContext: ctx, viewport }).promise;
          if (cancelled) return;
          host.appendChild(canvas);
        }
        if (!cancelled) setPdfDrawn(true);
      } catch {
        if (!cancelled) setPdfFailed(true);
      }
    })();

    return () => {
      cancelled = true;
      URL.revokeObjectURL(url);
    };
  }, [kind, data, label]);

  useEffect(() => {
    if (kind !== 'docx_fallback' || !data) return;
    let cancelled = false;
    (async () => {
      try {
        const { renderAsync } = await import('docx-preview');
        const host = docxHost.current;
        if (cancelled || !host) return;
        host.replaceChildren();
        await renderAsync(base64ToBytes(data), host, undefined, {
          className: 'qm-docxp',
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
          breakPages: true,
          experimental: true,
          // Show the document as it stands, not as a diff of tracked edits.
          renderChanges: false,
        });
      } catch {
        if (!cancelled) setDocxFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [kind, data]);

  if (!kind || !data) {
    return (
      <p className="qm-npv-note" role="status">
        {reason ? REASON_TEXT[reason] : 'No preview available.'}
      </p>
    );
  }

  return (
    <figure className={`qm-npv ${props.className ?? ''}`.trim()}>
      <div
        className="qm-npv-stage"
        tabIndex={0}
        role="group"
        aria-label={label}
      >
        {kind === 'pdf' ? (
          pdfFailed ? (
            <p className="qm-npv-note" role="status">
              We couldn&rsquo;t draw your form here.{' '}
              {pdfUrl ? <a href={pdfUrl} download="your-form.pdf">Download it instead</a> : null}
            </p>
          ) : (
            <div ref={pdfHost} className="qm-npv-pdf" data-drawn={pdfDrawn ? 'true' : 'false'} />
          )
        ) : docxFailed ? (
          <p className="qm-npv-note" role="status">
            We couldn&rsquo;t draw this document in the browser. Your template is unaffected.
          </p>
        ) : (
          <div ref={docxHost} className="qm-npv-docx" aria-label={label} />
        )}
      </div>
      {kind === 'pdf' && pdfUrl && !pdfFailed ? (
        // A canvas has no text. Anyone using a screen reader — or who simply
        // wants the file — needs a real document, not a picture of one.
        <p className="qm-npv-note">
          <a href={pdfUrl} download="your-form.pdf">
            Download this form as a PDF
          </a>
        </p>
      ) : null}
      {(reason || props.caption) && (
        <figcaption className="qm-npv-note" role="status">
          {props.caption}
          {props.caption && reason ? ' ' : null}
          {reason ? REASON_TEXT[reason] : null}
        </figcaption>
      )}
    </figure>
  );
}
