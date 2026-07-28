'use client';

// ============================================================================
// The pre-sign review AS THE DOCUMENT.
// ----------------------------------------------------------------------------
// The tabbed workspace asked the doctor to assemble the note in their head: the
// prose on one tab, the drug warning that blocks signing on another. Every
// blocker was one tap from invisible, and the reward for finishing was a modal.
//
// So: render the thing being signed. Top to bottom, one column, and put every
// decision at the place in the page where it actually applies.
//
//   • A critical-Rx warning and an E/M level change render as their own cards,
//     inline, one per item. Never collapsed into a count, never bulk-cleared,
//     and never behind a disclosure.
//   • Everything that blocks the signature says so where the signature is.
//
// NO SUGGESTION LANE. The anchored verifier is AUDIT-ONLY: it still runs and
// still judges, but nothing it finds becomes pending state. Every generated
// line is in the draft below, and what the verifier thought is an
// ANCHOR_FLAGS_RECORDED row rather than a stack of Accept/Dismiss cards. The
// per-section slot survives as a no-op because both renderers take it and a
// future non-suggestion annotation belongs there — it simply never draws.
//
// WHAT THIS COMPONENT DOES NOT DO: decide anything clinical. The Rx override is
// RxWarningsRail → OverrideConfirmModal → recordOverride. Signing is
// SignAndSendModal → the existing sign route. The E/M confirmation inside that
// modal is untouched and remains the enforcement — the inline cards here stand
// in front of it, never around it.
// ============================================================================

import { useMemo, useState } from 'react';
import { AlertTriangle, Check, FileSignature, RefreshCw } from 'lucide-react';

import { spokenBody } from '@/lib/spoken-body';
import { parseNoteSections, type NoteSection } from '@/lib/parse-note-sections';
import { emChangeEq } from '@/lib/suggestion-labels';
import { SignAndSendModal } from './sign-and-send-modal';

export interface ReviewDocumentViewProps {
  visitId: string;
  doctorEmail: string;
  emailEnabled: boolean;
  /** Current note markdown — rendered by `renderNote`, and read here only for
   *  the screen-reader transcript of the document. */
  soapFinal: string;
  /** Renders the real note (SoapEditor, chromeless) with a per-section slot.
   *  The note keeps its markdown fidelity, inline editing, status pills and
   *  copy affordances — this view supplies only what goes UNDER each section. */
  renderNote: (afterSection: (section: NoteSection) => React.ReactNode) => React.ReactNode;
  /** PHASE 2 — the doctor's own form, filled so far, INSTEAD of the styled
   *  note. Given a per-section slot renderer exactly as `renderNote` is, so the
   *  gates below are byte-identical either way; only what the page is made of
   *  changes. Absent (or returning null) → the styled note renders, which is
   *  the correct page for a non-template visit and the honest fallback when the
   *  document could not be produced. */
  /*  Takes a slot renderer keyed by SECTION LABEL — the document surface has
   *  headings, not parsed note sections, and synthesising a NoteSection to feed
   *  it would break the moment that type gains a field. */
  renderDocument?: (
    afterLabel: (label: string) => React.ReactNode,
  ) => React.ReactNode;
  /** The critical-Rx gate, rendered inline and unchanged. Null when the visit
   *  has no warnings at all, in which case no Rx row is drawn. */
  rxGateNode: React.ReactNode;
  /** True while any critical warning is still un-overridden. Mirrors the value
   *  the tabbed view computes from criticalWarningRefs — the same identity the
   *  sign route validates. */
  rxBlocking: boolean;
  /** Whether the Rx panel has an actual WARNING, as opposed to just
   *  medications. Drives the alarm styling only; the gate keys on rxBlocking. */
  rxHasWarnings: boolean;
  /** Unacknowledged E/M level change ({from,to}) or null. */
  emPendingChange: { from: string; to: string } | null;
  /** The note changed since the level was scored — the sign route refuses while
   *  this holds. The inline card below is where it is re-checked. */
  emStale?: boolean;
  /** Re-scores lazily. Returns whether the level moved. */
  onRescoreEm?: () => Promise<void>;
}

export function ReviewDocumentView(props: ReviewDocumentViewProps) {
  const [emConfirmed, setEmConfirmed] = useState(false);
  const [rescoring, setRescoring] = useState(false);

  // BLOCK fix. `emConfirmed` is a local acknowledgement of a value the SERVER
  // recomputes. Left latched, the card would go on saying "Level confirmed" for
  // a level the doctor never saw — the exact silent-flip regression prod-smoke
  // #311 closed.
  //
  // Compared by VALUE, not identity: the parent re-sets this state on note
  // changes, and an identity check would silently un-confirm the level on every
  // unrelated refresh — confirm/re-confirm churn on a clinical gate. Only a real
  // change to the codes should re-arm the card.
  const [prevEm, setPrevEm] = useState(props.emPendingChange);
  if (!emChangeEq(prevEm, props.emPendingChange)) {
    setPrevEm(props.emPendingChange);
    setEmConfirmed(false);
  }

  const sections = useMemo(() => parseNoteSections(props.soapFinal), [props.soapFinal]);

  const emBlocking = props.emPendingChange != null && !emConfirmed;
  const blocked = props.rxBlocking || emBlocking;

  async function rescore() {
    if (!props.onRescoreEm) return;
    setRescoring(true);
    try {
      await props.onRescoreEm();
    } finally {
      setRescoring(false);
    }
  }

  return (
    <div className="qm-rdoc" data-testid="review-document-view">
      {/* THE DOCUMENT — the real note renderer. */}
      <article className="qm-rdoc-page">
        {(() => {
          // The verifier is AUDIT-ONLY: nothing is ever staged beneath a
          // section. The slot stays in the signature because both renderers
          // take it and a future non-suggestion annotation would land here — it
          // simply never has anything to draw.
          const afterLabel = (_label: string) => null;
          const doc = props.renderDocument?.(afterLabel);
          if (!doc) return props.renderNote((section) => afterLabel(section.label));
          return (
            <>
              {doc}
              {/* THE NOTE, STILL READABLE.
                  The document renders as canvases — to a screen reader, one
                  unlabelled raster per page. Without this the entire clinical
                  note a doctor is about to sign would exist nowhere in the DOM,
                  which is not a degraded experience but an absent one. The text
                  is here, in reading order, for anyone whose reader needs it. */}
              <div className="qm-sr-only" data-testid="visit-document-text">
                <h2>The note this document was filled from</h2>
                {sections.map((sec) => (
                  <section key={sec.id}>
                    <h3>{sec.label}</h3>
                    <p>{spokenBody(sec.body, props.soapFinal)}</p>
                  </section>
                ))}
              </div>
            </>
          );
        })()}

        {/* ── INLINE GATES ───────────────────────────────────────────────
            At the position they belong to, one card per item, never a count. */}

        {/* THE ALARM IS FOR A WARNING, NOT FOR A PRESCRIPTION.
            Widening this panel to render whenever there are medications was
            right — a doctor must be able to see what they prescribed — but it
            brought the amber triangle and the words "Prescription safety" with
            it, so a visit with a routine refill and nothing wrong looked
            exactly like a visit with an interaction. The card is BYTE-IDENTICAL
            when a warning exists; without one it is a quiet list. */}
        {props.rxGateNode && (
          <section
            className={`qm-rdoc-gate${props.rxHasWarnings ? '' : ' qm-rdoc-gate-quiet'}`}
            data-testid="review-doc-rx-gate"
            data-rx-warnings={props.rxHasWarnings ? 'true' : 'false'}
          >
            <div className="qm-rdoc-gate-head">
              {props.rxHasWarnings && <AlertTriangle className="h-3.5 w-3.5" aria-hidden />}
              <span>{props.rxHasWarnings ? 'Prescription safety' : 'Prescriptions'}</span>
            </div>
            <div className="qm-rdoc-gate-body">{props.rxGateNode}</div>
          </section>
        )}

        {/* ── E/M STALE — THE SIGN-BLOCKER, INLINE ────────────────────────
            This used to live as a badge on the "⋯ details" disclosure, which
            meant the one thing standing between the doctor and a signature was
            behind a control they had no reason to open: the sign route refused,
            and the reason was folded away. A blocker that cannot be seen is a
            dead end.

            So it renders here, in the gate stack, next to the signature it
            blocks — and it carries the re-check itself. Opening a panel is no
            longer what re-scores the level; pressing the control that says the
            level needs re-checking is. */}
        {props.emStale && !props.emPendingChange && (
          <section
            className="qm-rdoc-gate qm-rdoc-gate-em"
            data-testid="review-doc-em-stale-gate"
            data-chat-target="em_gate"
          >
            <div className="qm-rdoc-gate-head">
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
              <span>Documentation level needs re-checking</span>
            </div>
            <div className="qm-rdoc-gate-body">
              <p className="qm-rdoc-gate-text">
                The note changed after this visit&rsquo;s level was scored.{' '}
                <span className="qm-rdoc-stale" data-testid="em-stale-badge">
                  needs re-check
                </span>
              </p>
              <button
                type="button"
                className="qm-rdoc-gate-btn qm-tap-44"
                onClick={() => void rescore()}
                disabled={rescoring}
                data-testid="review-doc-em-rescore"
              >
                <RefreshCw className="h-3.5 w-3.5" aria-hidden />
                {rescoring ? 'Re-checking…' : 'Re-check level'}
              </button>
            </div>
          </section>
        )}

        {props.emPendingChange && (
          <section
            className={`qm-rdoc-gate qm-rdoc-gate-em${emConfirmed ? ' is-done' : ''}`}
            data-testid="review-doc-em-gate"
            data-chat-target="em_gate"
          >
            <div className="qm-rdoc-gate-head">
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
              <span>Documentation level changed</span>
            </div>
            <div className="qm-rdoc-gate-body">
              <p className="qm-rdoc-gate-text">
                This visit now supports{' '}
                <strong className="qm-rdoc-em-code">{props.emPendingChange.to}</strong>, up from{' '}
                <strong className="qm-rdoc-em-code">{props.emPendingChange.from}</strong>. Confirm
                the level before signing.
                {props.emStale && (
                  <>
                    {' '}
                    <span className="qm-rdoc-stale" data-testid="em-stale-badge">
                      needs re-check
                    </span>
                  </>
                )}
              </p>
              <button
                type="button"
                className="qm-rdoc-gate-btn qm-tap-44"
                onClick={() => setEmConfirmed(true)}
                disabled={emConfirmed}
                data-testid="review-doc-em-confirm"
              >
                {emConfirmed ? (
                  <>
                    <Check className="h-3.5 w-3.5" aria-hidden /> Level confirmed
                  </>
                ) : (
                  <>Confirm {props.emPendingChange.to}</>
                )}
              </button>
            </div>
          </section>
        )}
      </article>

      {/* NO BILLING PANEL, NO CODES TABLE, NO INPUT TRANSCRIPT.
          They were here, inline, and before that behind a "⋯ details"
          disclosure. Both arrangements answered the wrong question. This page
          is the document being signed; a coding worksheet, an ICD table with
          confidence scores and the raw dictation are reference material for
          three different jobs, none of which is "read this and sign it".

          The coding still RUNS. Layer 7a still writes icdCodes, 7b still writes
          cptCodes, the transcript is still stored, and export and billing read
          all of it exactly as before — see the worker layers and
          visit-export-server. What changed is only that this page stopped
          drawing them.

          The one billing control that belongs on a signing surface is the level
          gate, and it is above, in the gate stack, where it blocks the
          signature it applies to. */}

      {/* ── THE BAR ─────────────────────────────────────────────────────── */}
      <div className="qm-c3-rev2-signbar">
        <div className="qm-c3-rev2-signbar-in">
          <div className="qm-c3-rev2-sign-status">
            {blocked ? (
              <>
                <AlertTriangle
                  className="h-3.5 w-3.5 flex-none"
                  aria-hidden
                  style={{ color: 'var(--color-linear-amber)' }}
                />
                <span className="qm-c3-rev2-sign-msg" data-testid="review-doc-bar-msg">
                  {props.rxBlocking
                    ? 'Resolve the prescription warning above'
                    : 'Confirm the documentation level above'}
                </span>
              </>
            ) : props.emStale ? (
              <>
                <AlertTriangle
                  className="h-3.5 w-3.5 flex-none"
                  aria-hidden
                  style={{ color: 'var(--color-linear-amber)' }}
                />
                <span className="qm-c3-rev2-sign-msg" data-testid="review-doc-bar-msg">
                  Re-check the documentation level above
                </span>
              </>
            ) : (
              <>
                <Check
                  className="h-3.5 w-3.5 flex-none"
                  aria-hidden
                  style={{ color: 'var(--color-linear-sage-bright)' }}
                />
                <span className="qm-c3-rev2-sign-msg" data-testid="review-doc-bar-msg">
                  Reviewed
                </span>
              </>
            )}
          </div>

          <div className="qm-c3-rev2-sign-action qm-rdoc-bar-actions">
            {/* Re-check before the modal opens. The gate render IS a moment the
                doctor is looking at the level, and it means they meet the
                confirm card rather than a refusal they have to interpret. */}
            <span
              onClickCapture={() => {
                if (props.emStale) void props.onRescoreEm?.();
              }}
            >
              <SignAndSendModal
                visitId={props.visitId}
                doctorEmail={props.doctorEmail}
                emailEnabled={props.emailEnabled}
                signOnSubmit
                emPendingChange={props.emPendingChange}
                triggerLabel="Sign &amp; Download"
                triggerIcon={<FileSignature className="h-3.5 w-3.5" aria-hidden />}
                disabled={blocked}
              />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
