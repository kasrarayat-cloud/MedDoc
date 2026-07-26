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
  type VisitPreviewResult,
} from '@/actions/preview-visit-document';
import { DocumentPages, type DocumentAnchor } from '@/components/native-preview/document-pages';
import { NativeDocumentPreview } from '@/components/native-preview/native-document-preview';

/** Doctor-facing, PHI-free. Every miss is SAID, never swallowed. */
const MISS_TEXT: Record<string, string> = {
  not_template_visit: '',
  not_certified:
    "This visit's template isn't set up to fill your own form yet, so the note is shown instead.",
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

  useEffect(() => {
    let cancelled = false;
    (async () => {
      // Inside the async body — a synchronous setState in an effect cascades.
      setDrawFailed(false);
      try {
        const r = await previewVisitDocumentAction(visitId);
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
  }, [visitId, revision, onOutcome, onUnavailable]);

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
  if (result.kind === 'docx_fallback') {
    return (
      <div data-testid="visit-document-fallback">
        <NativeDocumentPreview
          kind={result.kind}
          data={result.data}
          reason={result.reason}
          label="this visit, on your form"
          caption="Your form, filled so far. Blank fields are what has not been dictated yet."
        />
        <div className="qm-vdoc-unplaced" data-testid="vdoc-unplaced">
          {props.renderUnplaced(props.anchors.map((a) => a.key))}
        </div>
      </div>
    );
  }

  return (
    <>
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
        label="this visit, on your form"
        anchors={props.anchors}
        renderAfterPage={props.renderAfterSection}
        renderUnplaced={props.renderUnplaced}
        onFailed={handleDrawFailed}
      />
    </>
  );
}

export { MISS_TEXT as VISIT_DOCUMENT_MISS_TEXT };
