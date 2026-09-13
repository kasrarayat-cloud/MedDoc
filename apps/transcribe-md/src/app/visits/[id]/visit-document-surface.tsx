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

import { YourBlanksPanel } from './your-blanks-panel';

import {
  previewVisitDocumentAction,
  type PreviewFormat,
  type VisitPreviewMiss,
  type VisitPreviewResult,
} from '@/actions/preview-visit-document';
import type { NativePreviewError } from '@/actions/preview-native-document';
import { DocumentPages, type DocumentAnchor } from '@/components/native-preview/document-pages';
import { NativeDocumentPreview } from '@/components/native-preview/native-document-preview';

/**
 * Doctor-facing, PHI-free. Every miss is SAID, never swallowed.
 *
 * ⚠️ KEYED ON THE REASON UNION, NOT ON `string`, AND THAT IS THE FIX FOR A
 * DEFECT THIS FILE ALREADY SUFFERED ONCE. It was `Record<string, string>`, so
 * adding a sixth member to `VisitPreviewResult['reason']` was NOT a type error
 * and the new reason rendered NOTHING — the banner is gated on truthiness. It
 * happened again on 2026-09-08 with `no_tenant_template` (#287): the locum case
 * the ruling exists for produced a silent fallback, where `main` had said "We
 * could not fill your form for this visit". The change DELETED an explanation.
 *
 * EVERY MISS IS `Required`, so the next omission is a COMPILE ERROR rather than
 * a silence a doctor has to interpret. The `NativePreviewError` half stays
 * `Partial` on purpose: those are not misses, this surface speaks only some of
 * them, and demanding text for all would be a different claim.
 */
const MISS_TEXT: Required<Record<VisitPreviewMiss, string>> &
  Partial<Record<NativePreviewError, string>> = {
  not_template_visit: '',
  // ⚠️ THIS WAS THE EMPTY STRING, AND THE BANNER IS GATED ON TRUTHINESS.
  // The one miss a doctor can actually ACT on rendered NOTHING. The comment at
  // the render site says "Silence is illegal" and describes this exact case; the
  // map defeated it. Measured 2026-08-17: a doctor re-uploaded his form, ran a
  // visit, got the standard layout, and no surface told him the template needed
  // certifying — the twin sat at 0 of 80 mappings confirmed.
  //
  // It names the CURE, not just the miss. `not_template_visit` stays empty
  // because there is nothing to do about it; this one is a click-path away from
  // fixed, so it points there. Saying only "this is not your form" is what sent
  // that doctor back to re-upload a file we already had.
  not_certified:
    'This is QuillMD’s layout, not your form — your uploaded template needs ' +
    'confirming once before it can be used. Settings › My Note Format › Confirm fields.',
  no_render: 'We could not draw your form for this visit, so the note is shown instead.',
  fill_failed: 'We could not fill your form for this visit, so the note is shown instead.',
  // ⚠️ OWNER FINDING — A BLOCKED FILL, NOT A FAILED ONE. The form is fine; one
  // field needs a doctor's eye before the verified page can be produced, so
  // QuillMD's layout is shown here and stays exportable. It does NOT say "draw"
  // (the page could be drawn) and does NOT send the doctor to re-upload a form
  // they already have — the cure is reviewing the flagged field, not the form.
  native_fill_blocked:
    'A field on your form needs review, so it could not be filled cleanly for ' +
    'this visit — QuillMD’s layout is shown here and can still be exported.',
  sample_unavailable: 'We could not open your form this time, so the note is shown instead.',
  // ⚠️ #287 — THE TENANT HAS NO CERTIFIED FORM, WHICH IS AN ORDINARY STATE.
  // A locum documenting another practice's patient fills THAT practice's form;
  // if the practice has none certified, there is nothing to fill and the note
  // is the document. It names the cure like `not_certified` does, because the
  // person who can act is the practice that owns the chart.
  no_tenant_template:
    'This visit belongs to a practice with no confirmed form, so QuillMD’s ' +
    'layout is shown. That practice can confirm one in Settings › My Note Format.',
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
  /**
   * ⚠️ THE UNION, NOT `string`. This was `(reason: string | null)`, which threw
   * away a type `r.reason` already carries — and the widening is what let a new
   * miss reach the banner with no text and render nothing. Typed end to end, an
   * unspoken reason is a compile error at `MISS_TEXT`.
   */
  onUnavailable: (reason: VisitDocumentMissReason | null) => void;
}

export function VisitDocumentSurface(props: VisitDocumentSurfaceProps) {
  const { visitId, revision, onOutcome, onUnavailable } = props;
  const [result, setResult] = useState<VisitPreviewResult | null>(null);
  const [drawFailed, setDrawFailed] = useState(false);
  /** PDF is the faithful page; Word shows the file as Word will open it. Same
   *  bytes underneath — only the engine that draws them differs. */
  const [format, setFormat] = useState<PreviewFormat>('pdf');
  /** Bumped when the doctor inserts or undoes one of their own defaults. The
   *  fetch effect already keys on `revision`; this is the same mechanism for a
   *  change this surface made itself, so the document is redrawn from the new
   *  fill rather than showing the page they just changed. */
  const [localRevision, setLocalRevision] = useState(0);

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
  }, [visitId, revision, localRevision, format, onOutcome, onUnavailable]);

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

  // WHY this is the styled layout, when there is a specific reason to give.
  //
  // ⚠️ OWNER FINDING — THE REASON MUST BE SHOWN ON A RENDERED DOCUMENT, not only
  // when the surface steps aside. A blocked/failed fill (or a tenant with no
  // confirmed form) now degrades to the styled document with `ok:true`, so
  // `onUnavailable` never fires and the caller's miss line never draws — this is
  // the only place left to speak the reason. It is also MORE use than the
  // generic "set up a form" hint, and for a doctor who HAS a certified form that
  // simply could not fill this visit, that generic hint is wrong. So a specific
  // reason wins; the generic hint stands only for the genuine no-form case
  // (`reason === null`), which is the common styled visit the e2e pins.
  const styledReasonText = styledLayout
    ? visitDocumentMissText(result.reason)
    : undefined;

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
      {styledLayout &&
        (styledReasonText ? (
          <p className="qm-vdoc-toolbar-hint" data-testid="visit-document-styled-reason">
            {styledReasonText}
          </p>
        ) : (
          <p className="qm-vdoc-toolbar-hint" data-testid="visit-document-styled-note">
            QuillMD&rsquo;s layout — set up your own blank form in Settings ›{' '}
            <em>My Note Format</em> and this becomes your page.
          </p>
        ))}
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
          // ⚠️ DON'T SPEAK THE SAME REASON TWICE. When the toolbar already shows
          // the styled reason (`styledReasonText` set — a degrade the doctor can
          // act on), suppress it here so the figcaption does not repeat it or
          // render an empty status line for a reason NativeDocumentPreview has no
          // text for. When the toolbar shows only the generic hint
          // (`styledReasonText` unset), the reason still surfaces here — that is
          // where a converter notice ('converter_error' etc.) is spoken.
          reason={styledReasonText ? null : result.reason}
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
      {result.insertableDefaults && result.insertableDefaults.length > 0 && (
        <YourBlanksPanel
          visitId={visitId}
          groups={result.insertableDefaults}
          onChanged={() => setLocalRevision((n) => n + 1)}
        />
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

/**
 * ⚠️ THE ONLY SUPPORTED WAY TO READ THE MAP. Indexing it with a bare `string`
 * silently yields `undefined` for a reason nobody added text for — which is the
 * silence this file has now been bitten by twice. Callers pass the reason they
 * actually hold and get `undefined` only when the map genuinely has no entry.
 */
export type VisitDocumentMissReason = VisitPreviewMiss | NativePreviewError;

export function visitDocumentMissText(
  reason: VisitDocumentMissReason | null | undefined,
): string | undefined {
  if (!reason) return undefined;
  return (MISS_TEXT as Partial<Record<string, string>>)[reason];
}
