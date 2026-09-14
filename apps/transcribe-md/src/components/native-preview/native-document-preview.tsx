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
const REASON_TEXT: Partial<Record<string, string>> = {
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
  /** Any named reason from either preview surface. Widened deliberately: the
   *  visit page carries its own misses, and casting them through `as never` at
   *  the call site would keep compiling long after the unions diverged. */
  reason: NativePreviewError | string | null;
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

/**
 * Is there any INK in this rendered page — a pixel meaningfully darker than the
 * white page? PURE, so the blank-render guard is unit-testable without a canvas.
 * Samples on a stride (a preview, not a scanner). RULING #320 (2): a page that
 * carries text but draws NO ink is a RENDER FAILURE, not an empty form — the
 * exact "blank white rectangle" a doctor reads as "my form came back empty".
 * Distinguishing it from a legitimately sparse form is why the caller ALSO
 * requires the page to carry text before treating a no-ink canvas as failed: a
 * sparse form still draws its labels as ink, so it is never mistaken for blank.
 */
export function imageDataHasInk(
  data: Uint8ClampedArray | ReadonlyArray<number>,
  opts?: { pixelStride?: number; darkness?: number },
): boolean {
  // ⚠️ SCAN EVERY PIXEL BY DEFAULT (stride 1), with an early exit on the first
  // ink. A FIXED stride > 1 phase-locks to columns 0, stride, 2·stride, … on
  // every row (ImageData rows are exactly width·4 bytes), so on a canvas whose
  // width is a multiple of the stride, a sub-stride-wide label sitting between
  // sampled columns is missed on EVERY row → a rendered form falsely reads BLANK
  // (adversarial pass, 2026-09-14). The early exit keeps the common (inked) case
  // O(first ink); only a truly blank page scans the whole buffer, once.
  const stride = Math.max(1, opts?.pixelStride ?? 1) * 4;
  const darkness = opts?.darkness ?? 24;
  for (let i = 0; i + 3 < data.length; i += stride) {
    const a = data[i + 3];
    if (a < 8) continue; // fully transparent — not ink
    if (255 - data[i] > darkness || 255 - data[i + 1] > darkness || 255 - data[i + 2] > darkness) {
      return true;
    }
  }
  return false;
}

/**
 * Make the Word preview frame like the PDF one.
 *
 * THE ASYMMETRY THIS FIXES. The PDF path draws each page to a canvas and lets
 * CSS lay it out at `width: 100%` — fit-to-width for free, at any container
 * size. docx-preview instead emits real page boxes at the document's NATURAL
 * width (US Letter is ~816px at 96dpi) and honours it, because `ignoreWidth`
 * is false — which is what keeps the layout faithful. Nothing then scaled it,
 * so in any column narrower than a sheet of paper the Word view rendered at
 * 1:1 and overflowed: to the doctor, "zoomed in and broken", and a horizontal
 * scrollbar under a document the PDF tab had just shown them whole.
 *
 * So: measure the natural width, scale by the container, and pin the origin to
 * the top-left so the page grows down and right from the corner it starts in.
 * A transform does not affect layout size, so the host's height is set to the
 * scaled height — otherwise the stage would keep scrolling over the empty space
 * the unscaled document used to occupy.
 *
 * SCALES BOTH WAYS, because the PDF canvas does. `.qm-npv-page` is
 * `width: 100%`, so in a 1440px column a Letter page is drawn at 1082px — wider
 * than its natural 816. Capping this at 1x therefore did not give parity, it
 * gave a Word view that stopped growing at 816 while the PDF beside it kept
 * going: measured 1082 vs 816 at 1440, and 1562 vs 816 at 1920. Same document,
 * two sizes, on a toggle whose whole promise is that it is the same document.
 * Scaling up is also kinder here than in the PDF path — this is real DOM text,
 * so it resamples cleanly rather than as a stretched raster.
 */
function fitDocxToWidth(host: HTMLElement): void {
  const wrapper = host.querySelector<HTMLElement>('.qm-docxp-wrapper');
  if (!wrapper) return;

  // Measure UNSCALED — reading a width back through an existing transform
  // compounds the scale on every resize until the document vanishes.
  wrapper.style.transform = '';
  wrapper.style.width = '';
  wrapper.style.height = '';
  host.style.height = '';

  const available = host.clientWidth;
  // THE PAGE, not the wrapper. The wrapper is a block and stretches to the
  // host, so its scrollWidth reports the container's width back at us the
  // moment the container is wider than a sheet of paper — scale came out
  // exactly 1.0 at 1440 and 1920 and the Word view simply stopped growing
  // while the PDF beside it filled the column.
  const page = wrapper.querySelector<HTMLElement>('section.qm-docxp');
  const natural = page?.offsetWidth ?? wrapper.scrollWidth;
  if (!available || !natural) return;

  // Hug the page so the scaled box is exactly the page, then fit that.
  wrapper.style.width = `${natural}px`;
  const scale = available / natural;
  wrapper.style.transformOrigin = 'top left';
  wrapper.style.transform = `scale(${scale})`;
  // A scaled box still RESERVES its unscaled size, so the container has to be
  // told what it now actually occupies.
  host.style.height = `${wrapper.scrollHeight * scale}px`;
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
  // Reset on new input: a failure from a previous document must not outlive it,
  // or a good render shows as broken. Queued rather than synchronous — a
  // synchronous setState in an effect cascades an extra render.
  useEffect(() => {
    queueMicrotask(() => {
      setPdfFailed(false);
      setPdfDrawn(false);
      setDocxFailed(false);
    });
  }, [kind, data]);

  useEffect(() => {
    if (kind !== 'pdf' || !data) return undefined;
    let cancelled = false;
    const bytes = base64ToBytes(data);
    // The download escape hatch is offered regardless of how drawing goes.
    const url = URL.createObjectURL(
      new Blob([bytes.slice() as unknown as BlobPart], { type: 'application/pdf' }),
    );

    (async () => {
      // Queued with the draw rather than set synchronously — a setState in the
      // effect body cascades a render before this one has painted.
      setPdfUrl(url);
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
        // RULING #320 (2): track whether the render actually PUT INK ON THE PAGE,
        // and whether the page carries text that should have drawn as ink. A
        // no-ink canvas on a text-bearing page is a blank render — surfaced as a
        // named reason below, never shown as an empty white rectangle.
        let anyInk = false;
        let anyText = false;
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
          if (!anyInk) {
            try {
              const img = ctx.getImageData(0, 0, canvas.width, canvas.height);
              if (imageDataHasInk(img.data)) anyInk = true;
            } catch {
              // getImageData can throw on a tainted canvas — never here (same
              // origin) — but if it does, assume ink so we never HIDE a page.
              anyInk = true;
            }
          }
          if (!anyText) {
            try {
              const tc = await page.getTextContent();
              if (tc.items.some((it) => 'str' in it && (it as { str: string }).str.trim())) {
                anyText = true;
              }
            } catch {
              /* text layer unavailable — leave anyText as measured */
            }
          }
          host.appendChild(canvas);
        }
        if (cancelled) return;
        // A page that carries text but drew NO ink came back blank — report the
        // reason (the doctor gets a download link) rather than an empty page.
        if (anyText && !anyInk) setPdfFailed(true);
        else setPdfDrawn(true);
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
    let cleanup: (() => void) | undefined;
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
        if (cancelled) return;
        fitDocxToWidth(host);
        // The container changes width on rotate, on a sidebar toggle, and on
        // every drag of a desktop window — the fit has to follow it, or the
        // first layout is the only correct one.
        const ro = new ResizeObserver(() => fitDocxToWidth(host));
        ro.observe(host);
        cleanup = () => ro.disconnect();
      } catch {
        if (!cancelled) setDocxFailed(true);
      }
    })();
    return () => {
      cancelled = true;
      cleanup?.();
    };
  }, [kind, data]);

  if (!kind || !data) {
    return (
      <p className="qm-npv-note" role="status">
        {(reason ? REASON_TEXT[reason] : null) ?? 'No preview available.'}
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
          /* ⚠️ `tabIndex` + `role` ARE LOAD-BEARING, NOT DECORATION.
           *
           * `.qm-npv-docx` sets `overflow-x: hidden` (globals.css:7307) so the
           * Word tab cannot grow a horizontal scrollbar the PDF tab lacks. Per
           * CSS, when one axis is `hidden` the other's `visible` computes to
           * **auto** — so this div is a VERTICAL SCROLL CONTAINER whenever the
           * document is taller than its box, without anyone writing
           * `overflow-y`. Measured on the live page, not assumed.
           *
           * A scrollable region a keyboard user cannot focus cannot be
           * scrolled by keyboard at all: axe's `scrollable-region-focusable`,
           * serious. It failed the required a11y gate on /visits/[id] the
           * first time that gate was ever pointed at the shipped skin
           * (F-ret.2), and the gate named this node only after it was taught
           * to print selectors.
           *
           * `role="region"` is needed as well: an `aria-label` on a bare <div>
           * is not exposed without a role, so the label here was doing nothing.
           *
           * ⚠️ IT ONLY OVERFLOWS SOMETIMES, AND THE FIX DOES NOT DEPEND ON
           * THAT. Whether the box scrolls is a function of document height,
           * which is font-metric dependent — it reproduced in CI and never
           * locally, at any viewport. The rule is unconditional: a region that
           * CAN scroll must be reachable. Fixing it only when it happens to
           * overflow would make the guarantee depend on the renderer's fonts.
           */
          <div
            ref={docxHost}
            className="qm-npv-docx"
            role="region"
            aria-label={label}
            tabIndex={0}
          />
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
          {reason ? (REASON_TEXT[reason] ?? null) : null}
        </figcaption>
      )}
    </figure>
  );
}
