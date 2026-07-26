'use client';

// ============================================================================
// The document, as pages — with things anchored to the page they belong to.
// ----------------------------------------------------------------------------
// Renders a PDF page by page and lets the caller drop a node after any page.
// That is how suggestions and gate cards sit AT their place in the document
// instead of in a lane beside it.
//
// ANCHORING IS BY PAGE, NOT BY PIXEL. pdf.js gives us each page's text, so we
// can say honestly "this belongs to the page where IMPRESSION appears". We
// cannot say WHERE on the page without laying the document out ourselves, and
// pretending otherwise would put a card beside the wrong sentence — worse than
// putting it under the right page.
//
// Anything that cannot be placed is NOT dropped. It goes into a named group at
// the end, with the reason it could not be anchored.
// ============================================================================

import { useCallback, useEffect, useMemo, useState } from 'react';

export interface DocumentAnchor {
  key: string;
  /** Heading text to find in the document. */
  text: string;
}

export interface DocumentPagesProps {
  /** base64 PDF. */
  data: string;
  label: string;
  anchors: readonly DocumentAnchor[];
  /** Rendered immediately after the page these anchors resolved to. */
  renderAfterPage: (keys: readonly string[], pageNumber: number) => React.ReactNode;
  /** Rendered at the end for anchors that matched no page. */
  renderUnplaced: (keys: readonly string[]) => React.ReactNode;
  /** Called when the document could not be drawn at all, so the caller can fall
   *  back rather than leave an empty frame on screen. */
  onFailed?: () => void;
}

function base64ToBytes(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i);
  return out;
}

/** A heading in a Word form rarely matches the note's heading byte for byte —
 *  case, punctuation and trailing colons all drift. Compare on letters. */
function normalize(s: string): string {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim();
}

interface Rendered {
  /** One bitmap per page, already drawn. */
  bitmaps: HTMLCanvasElement[];
  /** anchor key -> 1-based page; 0 when it matched nothing. */
  placement: Record<string, number>;
}

export function DocumentPages(props: DocumentPagesProps) {
  const { data, label, anchors, onFailed } = props;
  const [rendered, setRendered] = useState<Rendered | null>(null);
  const [failed, setFailed] = useState(false);

  // The effect must not redraw the whole document just because the parent
  // re-rendered with a new array identity. Key it on the CONTENT of the anchor
  // list, and read the anchors back out of that same signature inside — so
  // what it places is exactly what it was keyed on.
  const anchorSig = useMemo(
    () => JSON.stringify(anchors.map((a) => [a.key, a.text])),
    [anchors],
  );
  useEffect(() => {
    let cancelled = false;

    (async () => {
      // Reset INSIDE the async body: a synchronous setState here would cascade
      // a second render before this one has painted.
      setFailed(false);
      setRendered(null);
      try {
        const pdfjs = await import('pdfjs-dist');
        pdfjs.GlobalWorkerOptions.workerSrc = new URL(
          'pdfjs-dist/build/pdf.worker.min.mjs',
          import.meta.url,
        ).toString();
        const doc = await pdfjs.getDocument({ data: base64ToBytes(data).slice() })
          .promise;
        if (cancelled) return;

        const dpr = Math.min(
          2,
          typeof window === 'undefined' ? 1 : window.devicePixelRatio || 1,
        );
        const bitmaps: HTMLCanvasElement[] = [];
        const pageText: string[] = [];

        for (let n = 1; n <= doc.numPages; n += 1) {
          const page = await doc.getPage(n);
          if (cancelled) return;
          const viewport = page.getViewport({ scale: 1.5 * dpr });
          const canvas = document.createElement('canvas');
          canvas.width = Math.floor(viewport.width);
          canvas.height = Math.floor(viewport.height);
          const ctx = canvas.getContext('2d');
          if (!ctx) throw new Error('no 2d context');
          await page.render({ canvasContext: ctx, viewport }).promise;
          if (cancelled) return;
          bitmaps.push(canvas);

          const tc = await page.getTextContent();
          pageText.push(
            normalize(
              tc.items
                .map((it) => ('str' in it ? (it as { str: string }).str : ''))
                .join(' '),
            ),
          );
        }

        const placement: Record<string, number> = {};
        for (const [key, text] of JSON.parse(anchorSig) as Array<[string, string]>) {
          const needle = normalize(text);
          placement[key] = needle
            ? pageText.findIndex((pt) => pt.includes(needle)) + 1
            : 0;
        }

        if (!cancelled) setRendered({ bitmaps, placement });
      } catch {
        if (!cancelled) {
          setFailed(true);
          onFailed?.();
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [data, anchorSig, onFailed]);

  /** Mounts the pre-drawn bitmap for a page into its React slot. Ref callbacks
   *  run during commit, so the canvas is in the DOM before paint. */
  const mountPage = useCallback(
    (index: number) => (host: HTMLDivElement | null) => {
      const canvas = rendered?.bitmaps[index];
      if (!host || !canvas) return;
      canvas.className = 'qm-npv-page';
      canvas.setAttribute('role', 'img');
      canvas.setAttribute(
        'aria-label',
        `${label} — page ${index + 1} of ${rendered.bitmaps.length}`,
      );
      host.replaceChildren(canvas);
    },
    [rendered, label],
  );

  if (failed) return null;
  if (!rendered) {
    return (
      <p className="qm-npv-note" role="status">
        Opening your document…
      </p>
    );
  }

  const byPage = new Map<number, string[]>();
  const unplaced: string[] = [];
  for (const a of anchors) {
    const p = rendered.placement[a.key] ?? 0;
    if (p > 0) byPage.set(p, [...(byPage.get(p) ?? []), a.key]);
    else unplaced.push(a.key);
  }

  return (
    <div
      className="qm-vdoc"
      data-pages={rendered.bitmaps.length}
      data-drawn="true"
      data-testid="visit-document"
    >
      {rendered.bitmaps.map((_, i) => {
        const n = i + 1;
        const keys = byPage.get(n);
        return (
          <div key={n} className="qm-vdoc-page">
            <div ref={mountPage(i)} className="qm-vdoc-pageslot" />
            {keys?.length ? (
              <div className="qm-vdoc-afterpage" data-after-page={n}>
                {props.renderAfterPage(keys, n)}
              </div>
            ) : null}
          </div>
        );
      })}
      {unplaced.length > 0 && (
        <div className="qm-vdoc-unplaced" data-testid="vdoc-unplaced">
          {props.renderUnplaced(unplaced)}
        </div>
      )}
    </div>
  );
}
