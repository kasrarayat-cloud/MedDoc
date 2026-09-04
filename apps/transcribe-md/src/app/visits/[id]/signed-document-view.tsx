'use client';

// ============================================================================
// UX simplification pack (B) — the SIGNED visit as ONE scrolling document.
// ----------------------------------------------------------------------------
// A signed note is a finished record, not a workspace. The tabbed sign-gate
// workspace (ReviewTabsV2) exists to hold the PRE-SIGN gates visible while the
// doctor works; once the note is locked there are no gates left to clear, so
// six tabs over a read-only artifact is pure navigation tax — the doctor taps
// through Rx/Billing/Codes/Extras to re-read something that could simply be on
// the page.
//
// So: signed → linearise. Nothing is removed; everything the tabs held is still
// reachable, just stacked in reading order:
//
//   signed-lock banner  (unchanged component)
//   the note, top to bottom, clean reading layout
//   one slim summary row — ICD codes · billing level · Rx-override note
//                          (the Rx line appears ONLY if an override was recorded)
//   "View original dictation" — small expandable, collapsed by default
//   "Export again" — pinned, same SignAndSendModal, signOnSubmit={false}
//
// SCOPE: signed/readonly visits ONLY. The unsigned review path is untouched —
// ReviewTabsV2 still renders it verbatim, because that is where the critical-Rx
// and E/M confirm gates live and those are frozen surfaces.
//
// DATA: every value here is already computed by visit-ready-view for the tabs.
// This component re-arranges what it is handed. It performs no fetch, writes
// nothing, and touches neither the sign route nor the audit trail.
// ============================================================================

import { useId, useMemo, useState } from 'react';
import { ChevronRight, Lock, Send } from 'lucide-react';

import { parseNoteSections } from '@/lib/parse-note-sections';
import { spokenBody } from '@/lib/spoken-body';

import { SignAndSendModal } from './sign-and-send-modal';

export interface SignedSummary {
  /** ICD rows as displayed on the Codes tab. */
  icd: { code: string; description?: string }[];
  /** The billing level actually displayed (doctor override wins over suggested);
   *  null when E/M does not apply to this encounter type (e.g. imaging). */
  emCode: string | null;
  /** True when E/M is suppressed for this specialty — we then say so rather
   *  than rendering an empty slot the doctor has to interpret. */
  emNotApplicable: boolean;
}

export interface SignedDocumentViewProps {
  visitId: string;
  doctorEmail: string;
  emailEnabled: boolean;
  /** The signed-lock banner (SignedStateCard) — passed in unchanged. */
  lockBanner: React.ReactNode;
  /** The note itself (SoapEditor, chromeless, readonly). */
  noteNode: React.ReactNode;
  /** PHASE 2 — the FINAL FILE that was delivered, drawn. Null/absent when the
   *  visit has no native document or it could not be produced, in which case
   *  the note renders exactly as before. */
  documentNode?: React.ReactNode;
  /** THE SIGNED NOTE AS TEXT, for the accessibility tree — see the block that
   *  renders it below. This is `soapText`, which `page.tsx:588-591` computes as
   *  `signedSoap ?? soapFinal` for a SIGNED visit: the frozen record, never a
   *  draft. Deliberately NOT `adoption?.text ?? soapText` the way the unsigned
   *  path passes it — an adopted draft must never be what a screen reader hears
   *  from a signed document. Absent → the block does not render, rather than
   *  rendering empty. */
  signedNoteText?: string;
  /** Transcript / dictation / raw-text view — the old "Input" tab, collapsed. */
  dictationNode: React.ReactNode;
  dictationLabel: string;
  summary: SignedSummary;
}

export function SignedDocumentView(props: SignedDocumentViewProps) {
  const [openDictation, setOpenDictation] = useState(false);
  const dictationPanelId = useId();
  const { summary } = props;

  // The document is what renders whenever we HAVE one; `??` falls through only
  // on null/undefined. So this is exactly the condition under which the note
  // exists solely as canvas bitmaps.
  const usingDocument = props.documentNode != null;
  // ⚠️ GUARD ON THE TEXT, NOT ON THE SECTION COUNT. `parseNoteSections('')`
  // returns FOUR sections — the empty SOAP skeleton, S/O/A/P with blank bodies —
  // measured, not assumed. So `sections.length > 0` is vacuously true and would
  // have announced four empty headings to a screen reader on a note with no
  // text: structure that is not there. The condition is whether there is a note
  // at all, which is a fact about the string.
  const hasNoteText = (props.signedNoteText ?? '').trim().length > 0;
  const spokenSections = useMemo(
    () =>
      usingDocument && hasNoteText ? parseNoteSections(props.signedNoteText ?? '') : [],
    [usingDocument, hasNoteText, props.signedNoteText]
  );

  const hasIcd = summary.icd.length > 0;
  const hasEm = summary.emCode !== null || summary.emNotApplicable;
  const hasAnySummary = hasIcd || hasEm;

  return (
    <div className="qm-ux-doc" data-testid="signed-document-view">
      {props.lockBanner}

      {/* The FINAL FILE, when we have it: the delivered document itself, not a
          re-typeset copy of it. A signed note is a record — what it looked like
          when it was signed is the thing worth showing. Falls back to the note
          whenever the file cannot be produced. */}
      <article className="qm-ux-doc-note">{props.documentNode ?? props.noteNode}</article>

      {/* ── THE SIGNED NOTE, STILL READABLE ────────────────────────────────
          The document above renders as <canvas> bitmaps (document-pages.tsx
          paints each page and sets role="img"), so to a screen reader it is one
          unlabelled raster per page and nothing else.

          ⚠️ WHAT THIS BLOCK CARRIES IS THE NOTE'S SOAP-HEADING SECTIONS, NOT THE
          NOTE. An earlier version of this comment said "the signed note's text",
          and the adversarial pass proved that false in three ways — all three
          INHERITED from the shared parse/spoken pipeline this reuses, all three
          reproduced against the real shipped functions, and all three now pinned
          as executable facts in gate-signed-note-accessible-text.test.tsx so
          they cannot be forgotten:

            · CONTENT ABOVE THE FIRST SOAP HEADING IS DROPPED.
              `parse-soap-sections.ts` says so in its own docstring — "anything
              before the first SOAP heading is dropped". Measured: an
              "ADDENDUM … ALLERGIC TO PENICILLIN" line above `## Subjective`
              is absent from this block while the drawn document renders it.
            · ABSENT SOAP HEADINGS ARE ANNOUNCED AS "Not documented."
              The parser returns all four of S/O/A/P unconditionally, so a note
              carrying only `## Subjective` tells a listener the physician
              documented no assessment and no plan. The export prints those words
              only under a heading that EXISTS, so the two disagree.
            · TABLE HEADERS ARE DELETED and only conditionally restored, so a
              measurement table whose rows collide can reach a listener as
              unlabelled, unitless numbers in raw pipe markup.

          None of that is introduced here — before this block the signed note had
          NO accessible copy at all, so this is strictly more of the record than
          zero. It is written down because the next session will read this
          comment as the specification, and a false record about clinical text is
          how the next incident starts.

          ⚠️ AND IT CAN DUPLICATE ON THE WORD PATH. `usingDocument` tests whether
          a documentNode ELEMENT was passed, never how it draws; `format` is
          state held inside VisitDocumentSurface. On `docx_fallback` — one click
          of the Word toggle, or any signed visit whose signature froze no native
          document, or Gotenberg being down — the document renders as REAL DOM
          TEXT and a screen reader meets the note twice. Threading the render
          mode out of that component is the fix and it is a follow-up: it reaches
          the renderer seam, which does not belong in an accessibility change.

          ⚠️ THE UNSIGNED PATH ALREADY DOES THIS, AND SAYS WHY IN ITS OWN WORDS
          (review-document-view.tsx:243-249): "Without this the entire clinical
          note a doctor is about to sign would exist nowhere in the DOM, which is
          not a degraded experience but an absent one." That reasoning does not
          weaken once the note is signed — the signed note is the PERMANENT
          record, and it was the only one of the two surfaces without the block.
          Measured: `qm-sr-only` occurred in exactly ONE source file in the whole
          app, and it was not this one.

          ⚠️ RENDERED ONLY WHEN THE DOCUMENT IS. On the fallback path
          `props.noteNode` mounts a real SoapEditor whose text is already in the
          DOM, and a second copy would make a screen reader read the note twice.

          Presentation only: `spokenBody` is the same pure function the unsigned
          path uses, it touches no stored text, and nothing here is interactive —
          so this adds reading matter to the accessibility tree and no controls
          to it. */}
      {usingDocument && hasNoteText && (
        <div className="qm-sr-only" data-testid="signed-document-text">
          <h2>The signed note, as text</h2>
          {spokenSections.map((sec) => (
            <section key={sec.id}>
              <h3>{sec.label}</h3>
              <p>{spokenBody(sec.body, props.signedNoteText ?? '')}</p>
            </section>
          ))}
        </div>
      )}

      {/* One slim summary row. Everything the Codes / Billing tabs carried
          for a SIGNED note, in a single glance-able strip. */}
      {hasAnySummary && (
        <section className="qm-ux-doc-summary" aria-label="Coding summary">
          {hasIcd && (
            <div className="qm-ux-sum-item">
              <span className="qm-ux-sum-key">DIAGNOSES</span>
              <span className="qm-ux-sum-val">
                {summary.icd.map((r, i) => (
                  <span key={r.code} className="qm-ux-sum-code" title={r.description ?? r.code}>
                    {r.code}
                    {i < summary.icd.length - 1 ? ' · ' : ''}
                  </span>
                ))}
              </span>
            </div>
          )}

          {hasEm && (
            <div className="qm-ux-sum-item">
              <span className="qm-ux-sum-key">BILLING</span>
              <span className="qm-ux-sum-val">
                {summary.emNotApplicable ? (
                  <span className="qm-ux-sum-muted">Not applicable to this encounter</span>
                ) : (
                  summary.emCode
                )}
              </span>
            </div>
          )}

        </section>
      )}

      {/* The original dictation / transcript — present, collapsed, one tap. */}
      <section className="qm-ux-doc-dictation">
        <button
          type="button"
          className="qm-ux-doc-disclosure qm-tap-44"
          aria-expanded={openDictation}
          aria-controls={dictationPanelId}
          onClick={() => setOpenDictation((v) => !v)}
          data-testid="signed-doc-dictation-toggle"
        >
          <ChevronRight
            className={`h-3.5 w-3.5 qm-ux-doc-chev ${openDictation ? 'open' : ''}`}
            aria-hidden
          />
          <span>{openDictation ? `Hide ${props.dictationLabel}` : `View ${props.dictationLabel}`}</span>
        </button>
        {openDictation && (
          <div id={dictationPanelId} className="qm-ux-doc-dictation-body">
            {props.dictationNode}
          </div>
        )}
      </section>

      {/* Pinned export bar — reuses the review skin's sign-bar chrome (and its
          mobile-nav offset) so the two surfaces feel like one product. */}
      <div className="qm-c3-rev2-signbar">
        <div className="qm-c3-rev2-signbar-in">
          <div className="qm-c3-rev2-sign-status">
            <Lock
              className="h-3.5 w-3.5 flex-none"
              aria-hidden
              style={{ color: 'var(--color-linear-sage-bright)' }}
            />
            <span className="qm-c3-rev2-sign-msg">This note is signed</span>
          </div>
          <div className="qm-c3-rev2-sign-action">
            <SignAndSendModal
              visitId={props.visitId}
              doctorEmail={props.doctorEmail}
              emailEnabled={props.emailEnabled}
              signOnSubmit={false}
              triggerLabel="Export again"
              triggerIcon={<Send className="h-3.5 w-3.5" aria-hidden />}
              triggerVariant="secondary"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
