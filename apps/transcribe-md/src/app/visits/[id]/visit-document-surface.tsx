'use client';

// ============================================================================
// PHASE 2 — the visit page IS the document.
// ----------------------------------------------------------------------------
// For a visit whose template is CERTIFIED, this replaces the styled note with
// the doctor's own form: filled with what has been captured so far, blank where
// nothing has. Suggestions and the gates keep their cards and their behaviour —
// they just sit after the page they belong to instead of under a heading in a
// re-typeset copy.
//
// The reason it matters: reviewing a styled note and then downloading a filled
// Word form means reviewing a different artifact than the one you signed.
//
// IT NEVER GATES. If the fill fails, the template is not certified, the sidecar
// is down and the browser cannot draw the bytes either — this returns null and
// the caller renders the styled note with a named reason. Signing is unaffected
// in every one of those cases.
//
// IT NEVER WRITES. previewVisitDocumentAction is read-only by construction; see
// the note there about why a mid-review fill manifest would be dangerous.
// ============================================================================

import { useCallback, useEffect, useState } from 'react';

import {
  previewVisitDocumentAction,
  type PreviewFormat,
  type VisitPreviewResult,
} from '@/actions/preview-visit-document';
import { DocumentPages, type DocumentAnchor } from '@/components/native-preview/document-pages';
import { NativeDocumentPreview } from '@/components/native-preview/native-document-preview';

/** Doctor-facing, PHI-free. Every miss is SAID, never swallowed. */
const MISS_TEXT: Record<string, string> = {
  not_template_visit: '',
  not_certified: '',
  no_render: 'We could not draw your form for this visit, so the note is shown instead.',
  fill_failed: 'We could not fill your form for this visit, so the note is shown instead.',
  sample_unavailable: 'We could not open your form this time, so the note is shown instead.',
};

export interface VisitDocumentSurfaceProps {
  visitId: string;
  /** Section headings in note order — the anchors cards are placed against. */
  anchors: readonly DocumentAnchor[];
  /** Changes whenever the note does (adoption seq). Refetching on this is what
   *  makes the document visibly fill as the doctor accepts suggestions. */
  revision: number;
  /** The per-section slot renderer, passed straight through unchanged. */
  renderAfterSection: (keys: readonly string[], pageNumber: number) => React.ReactNode;
  renderUnplaced: (keys: readonly string[]) => React.ReactNode;
  /** Told what happened, so the page can say it once, near the document. */
  onOutcome?: (o: { ok: boolean; reason: string | null; counts: VisitPreviewResult['counts'] }) => void;
  /** Fired when there is no document to show at all, so the caller can fall
   *  back to the styled note rather than leave a hole in the page. */
  onUnavailable: (reason: string | null) => void;
}

export function VisitDocumentSurface(props: VisitDocumentSurfaceProps) {
  const { visitId, revision, onOutcome, onUnavailable } = props;
  const [result, setResult] = useState<VisitPreviewResult | null>(null);
  const [drawFailed, setDrawFailed] = useState(false);
  /** PDF is the faithful page; Word shows the file as Word will open it. Same
   *  bytes underneath — only the engine that draws them differs. */
  const [format, setFormat] = useState<PreviewFormat>('pdf');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Inside the async body — a synchronous setState in an effect cascades.
      setDrawFailed(false);
      try {
        const r = await previewVisitDocumentAction(visitId, format);
        if (cancelled) return;
        setResult(r);
        onOutcome?.({ ok: r.ok, reason: r.reason, counts: r.counts });
        if (!r.ok || !r.data) onUnavailable(r.reason);
      } catch {
        if (cancelled) return;
        // A thrown action is still an answer: say so and step aside.
        onUnavailable('fill_failed');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [visitId, revision, format, onOutcome, onUnavailable]);

  const handleDrawFailed = useCallback(() => {
    setDrawFailed(true);
    onUnavailable('no_render');
  }, [onUnavailable]);

  if (!result) {
    return (
      <p className="qm-npv-note" role="status" data-testid="visit-document-loading">
        Opening your document…
      </p>
    );
  }
  if (!result.ok || !result.data || drawFailed) return null;

  // The converter was unavailable, so the browser draws the true DOCX. Page
  // anchoring needs pdf.js text, which this path does not have — the cards are
  // shown together under the document rather than at pages we cannot locate.
  const styledLayout = Boolean(result.fillSha?.startsWith('styled:'));

  // ONE slim row. The format control and the "whose page is this" hint were two
  // stacked blocks above the document, which is most of the dead band that used
  // to sit between the heading and the page. Same controls, same words, one
  // line — and the hint sits with the toggle it qualifies rather than floating
  // over the paper.
  const toolbar = (
    <div className="qm-vdoc-toolbar">
      <div className="qm-vdoc-format" role="group" aria-label="Preview format">
        {(['pdf', 'word'] as const).map((f) => (
          <button
            key={f}
            type="button"
            className={f === format ? 'qm-vdoc-format-on' : undefined}
            aria-pressed={f === format}
            onClick={() => setFormat(f)}
            data-testid={`preview-format-${f}`}
          >
            {f === 'pdf' ? 'PDF' : 'Word'}
          </button>
        ))}
      </div>
      {/* WHOSE page this is. A styled document is still a document — but the
          doctor should know it is our layout, not their form, and what to do
          about it. Quiet, and only when it is true. */}
      {styledLayout && (
        <p className="qm-vdoc-toolbar-hint" data-testid="visit-document-styled-note">
          QuillMD&rsquo;s layout — upload your own blank form in Settings ›{' '}
          <em>My Note Format</em> and this becomes your page.
        </p>
      )}
    </div>
  );

  if (result.kind === 'docx_fallback') {
    return (
      <div data-testid="visit-document-fallback">
        {/* The toggle lives in BOTH branches. Word mode returns here, and
            rendering the control only in the PDF branch made it a one-way
            trapdoor: click Word and there was no way back. */}
        {toolbar}
        <NativeDocumentPreview
          kind={result.kind}
          data={result.data}
          reason={result.reason}
          label={styledLayout ? 'this visit' : 'this visit, on your form'}
          caption={
            styledLayout
              ? // ⚠️ R1 — SAID ONCE, NOT TWICE. The toolbar above already
                // carries this exact sentence (`visit-document-styled-note`),
                // so on the styled layout this figcaption repeated it verbatim
                // below the pages: one message, two chrome rows, the paper
                // sandwiched between them. The toolbar is the spec's slim row
                // and it wins; the caption yields.
                // It is NOT dropped for a custom form — there the toolbar hint
                // does not render at all, so the sentence below is the only
                // place the doctor is told what they are looking at.
                undefined
              : 'Your form, filled so far. Blank fields are what has not been dictated yet.'
          }
        />
        <div className="qm-vdoc-unplaced" data-testid="vdoc-unplaced">
          {props.renderUnplaced(props.anchors.map((a) => a.key))}
        </div>
      </div>
    );
  }

  return (
    <>
      {toolbar}
      {result.counts && (
        <p
          className="qm-vdoc-counts"
          data-testid="visit-document-counts"
          /* The fill's identity. Two different fills can report the same
             counts, so a test (and a support question) needs to tell "it did
             not refresh" from "it refreshed and nothing moved". */
          data-fill-sha={result.fillSha ?? ''}
        >
          {result.counts.filled} field{result.counts.filled === 1 ? '' : 's'} filled
          {result.counts.notMentioned > 0
            ? ` · ${result.counts.notMentioned} still blank — nothing dictated for those yet`
            : ''}
          {result.counts.needsReview > 0 ? ` · ${result.counts.needsReview} to check` : ''}
        </p>
      )}
      <DocumentPages
        data={result.data}
        label={styledLayout ? 'this visit' : 'this visit, on your form'}
        anchors={props.anchors}
        renderAfterPage={props.renderAfterSection}
        renderUnplaced={props.renderUnplaced}
        onFailed={handleDrawFailed}
      />
    </>
  );
}

export { MISS_TEXT as VISIT_DOCUMENT_MISS_TEXT };
