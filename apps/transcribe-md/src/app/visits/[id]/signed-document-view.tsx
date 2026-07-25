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

import { useId, useState } from 'react';
import { ChevronRight, Lock, Send } from 'lucide-react';
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
  /** Present ONLY when a critical-Rx override was actually recorded. Absent
   *  otherwise — an empty "no overrides" row would be noise on most notes. */
  rxOverrideNote: string | null;
}

export interface SignedDocumentViewProps {
  visitId: string;
  doctorEmail: string;
  emailEnabled: boolean;
  /** The signed-lock banner (SignedStateCard) — passed in unchanged. */
  lockBanner: React.ReactNode;
  /** The note itself (SoapEditor, chromeless, readonly). */
  noteNode: React.ReactNode;
  /** Transcript / dictation / raw-text view — the old "Input" tab, collapsed. */
  dictationNode: React.ReactNode;
  dictationLabel: string;
  summary: SignedSummary;
}

export function SignedDocumentView(props: SignedDocumentViewProps) {
  const [openDictation, setOpenDictation] = useState(false);
  const dictationPanelId = useId();
  const { summary } = props;

  const hasIcd = summary.icd.length > 0;
  const hasEm = summary.emCode !== null || summary.emNotApplicable;
  const hasRx = !!summary.rxOverrideNote;
  const hasAnySummary = hasIcd || hasEm || hasRx;

  return (
    <div className="qm-ux-doc" data-testid="signed-document-view">
      {props.lockBanner}

      {/* The note — the whole point of the page, so it gets the full measure
          and nothing sits beside it at any width. */}
      <article className="qm-ux-doc-note">{props.noteNode}</article>

      {/* One slim summary row. Everything the Codes / Billing / Rx tabs carried
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

          {hasRx && (
            <div className="qm-ux-sum-item qm-ux-sum-rx">
              <span className="qm-ux-sum-key">RX OVERRIDE</span>
              <span className="qm-ux-sum-val">{summary.rxOverrideNote}</span>
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
