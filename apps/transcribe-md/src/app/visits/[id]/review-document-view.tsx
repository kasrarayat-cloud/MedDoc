'use client';

// ============================================================================
// The pre-sign review AS THE DOCUMENT.
// ----------------------------------------------------------------------------
// The tabbed workspace asks the doctor to assemble the note in their head: the
// prose is on one tab, what the verifier set aside is on another, the drug
// warning that blocks signing is on a third. Every blocker is one tap from
// invisible, and the reward for finishing is a modal.
//
// So: render the thing being signed. Top to bottom, one column, and put every
// decision at the place in the page where it actually applies.
//
//   • A set-aside claim renders IN PLACE, as its proposed text, softly lit —
//     not a bracket placeholder, not a list somewhere else. Reading the note
//     and reviewing the suggestions become the same act.
//   • A critical-Rx warning and an E/M level change render as their own cards,
//     inline, one per item. Never collapsed into a count, never bulk-cleared.
//   • The bar cannot offer "accept remaining" until every suggestion has been
//     on screen IN FULL. Reading is the review; a doctor who has not seen a
//     sentence has not approved it.
//
// WHAT THIS COMPONENT DOES NOT DO: decide anything clinical. Adoption is
// adoptSuggestionAction, per claim, with its content-identity check. The Rx
// override is RxWarningsRail → OverrideConfirmModal → recordOverride. Signing
// is SignAndSendModal → the existing sign route. The E/M confirmation inside
// that modal is untouched and remains the enforcement — the inline card is one
// more thing standing in front of it, never a way around it.
// ============================================================================

import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { AlertTriangle, Check, ChevronRight, FileSignature, Sparkles } from 'lucide-react';
import { toast } from 'sonner';

import { adoptSuggestionAction, dismissSuggestionAction } from '@/actions/suggestion-actions';
import { parseNoteSections, type NoteSection } from '@/lib/parse-note-sections';
import { SignAndSendModal } from './sign-and-send-modal';
import type { SuggestedClaimView } from './suggestions-lane';

export interface ReviewDocumentSummary {
  icd: { code: string; description?: string }[];
  emCode: string | null;
  emNotApplicable: boolean;
}

export interface ReviewDocumentViewProps {
  visitId: string;
  doctorEmail: string;
  emailEnabled: boolean;
  /** Current note markdown — used ONLY to place suggestions against their
   *  section headings. The note itself is rendered by `renderNote`. */
  soapFinal: string;
  /** Renders the real note (SoapEditor, chromeless) with a per-section slot.
   *  The note keeps its markdown fidelity, inline editing, status pills and
   *  copy affordances — this view supplies only what goes UNDER each section. */
  renderNote: (afterSection: (section: NoteSection) => React.ReactNode) => React.ReactNode;
  /** Verifier-demoted claims, in DB-array order — the index IS the action's. */
  claims: SuggestedClaimView[];
  /** The critical-Rx gate, rendered inline and unchanged. Null when the visit
   *  has no warnings at all, in which case no Rx row is drawn. */
  rxGateNode: React.ReactNode;
  /** True while any critical warning is still un-overridden. Mirrors the value
   *  the tabbed view computes from criticalWarningRefs — the same identity the
   *  sign route validates. */
  rxBlocking: boolean;
  /** Unacknowledged E/M level change ({from,to}) or null. */
  emPendingChange: { from: string; to: string } | null;
  summary: ReviewDocumentSummary;
  dictationNode: React.ReactNode;
  dictationLabel: string;
  /** Fired after each successful adopt so the parent stays in sync with the
   *  server's note state (same payload the suggestions lane emits today). */
  onAdopted: (r: {
    soapFinal: string;
    soapVersion: number;
    emPendingChange?: { from: string; to: string } | null;
  }) => void;
}

/** DemotionReason → human chip. Same vocabulary the lane uses; an unknown
 *  reason falls back rather than printing a raw enum at a clinician. */
const REASON_LABELS: Record<string, string> = {
  model_suggested: 'not stated',
  no_anchor: 'not stated',
  anchor_not_in_transcript: 'quote not in transcript',
  anchor_overlaps_unclear: 'unclear audio',
  digits_unsupported: 'numbers not supported',
  negation_mismatch: 'negation mismatch',
  gloss_unsupported: 'explanation not in transcript',
  process_assertion_unsupported: 'reasoning not stated',
  form_route_unsupported: 'form/route not stated',
  not_entailed: "couldn't verify",
  verifier_failed: "couldn't verify",
};
const reasonLabel = (r: string) => REASON_LABELS[r] ?? "couldn't verify";

/** Match a claim to the section it belongs under. The claim carries the
 *  heading text the adopt action will append it to, so equality on the
 *  normalised label is the same join the server makes. Claims whose section
 *  has no matching heading fall to the end of the document rather than
 *  vanishing — an unplaceable suggestion is still a suggestion. */
const norm = (s: string) => s.trim().toLowerCase().replace(/\s+/g, ' ');

export function ReviewDocumentView(props: ReviewDocumentViewProps) {
  const router = useRouter();
  const dictationPanelId = useId();

  const [claims, setClaims] = useState<SuggestedClaimView[]>(props.claims);
  const [busy, setBusy] = useState<number | 'bulk' | null>(null);
  const [openDictation, setOpenDictation] = useState(false);
  const [openSummary, setOpenSummary] = useState(false);
  const [emConfirmed, setEmConfirmed] = useState(false);

  // Claims arrive fresh on every server refresh; the local copy is replaced
  // wholesale from each action's response so rendered indices never drift from
  // the DB array (the same discipline the lane keeps).
  const [prevClaims, setPrevClaims] = useState(props.claims);
  if (prevClaims !== props.claims) {
    setPrevClaims(props.claims);
    setClaims(props.claims);
  }

  const sections = useMemo(() => parseNoteSections(props.soapFinal), [props.soapFinal]);

  // Which claims sit under which section heading. Index is preserved because
  // the action addresses claims BY INDEX — never re-number them.
  const claimsBySection = useMemo(() => {
    const bySection = new Map<string, number[]>();
    const placed = new Set<number>();
    claims.forEach((c, i) => {
      const hit = sections.find((s) => norm(s.label) === norm(c.section));
      if (!hit) return;
      const list = bySection.get(hit.id) ?? [];
      list.push(i);
      bySection.set(hit.id, list);
      placed.add(i);
    });
    const orphans = claims.map((_, i) => i).filter((i) => !placed.has(i));
    return { bySection, orphans };
  }, [claims, sections]);

  // ── READING IS THE REVIEW ────────────────────────────────────────────────
  // Bulk-accept unlocks only after every suggestion has been fully on screen.
  // threshold:1 means the whole card, not a sliver of it; once seen, a card
  // stays seen (scrolling back up must not re-lock the bar).
  const [seen, setSeen] = useState<Set<string>>(new Set());
  const seenRef = useRef(seen);
  seenRef.current = seen;
  const observerRef = useRef<IntersectionObserver | null>(null);

  const markSeen = useCallback((key: string) => {
    setSeen((prev) => (prev.has(key) ? prev : new Set(prev).add(key)));
  }, []);

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          const key = (e.target as HTMLElement).dataset.suggestionKey;
          if (key) markSeen(key);
        }
      },
      { threshold: 1 },
    );
    observerRef.current = io;
    return () => io.disconnect();
  }, [markSeen]);

  const attachSuggestion = useCallback((el: HTMLElement | null) => {
    if (el && observerRef.current) observerRef.current.observe(el);
  }, []);

  const claimKey = (c: SuggestedClaimView, i: number) => `${i}:${c.text.slice(0, 40)}`;
  const allSeen = claims.every((c, i) => seen.has(claimKey(c, i)));

  // ── the one mechanism for adoption ───────────────────────────────────────
  async function act(index: number, kind: 'adopt' | 'dismiss') {
    setBusy(index);
    try {
      const expectedText = claims[index].text;
      const res =
        kind === 'adopt'
          ? await adoptSuggestionAction(props.visitId, index, expectedText)
          : await dismissSuggestionAction(props.visitId, index, expectedText);
      if (!res.ok) {
        toast.error(kind === 'adopt' ? 'Could not accept' : 'Could not dismiss', {
          description: res.error,
        });
        return false;
      }
      setClaims(res.suggestedClaims ?? []);
      if (kind === 'adopt' && typeof res.soapFinal === 'string' && typeof res.soapVersion === 'number') {
        props.onAdopted({
          soapFinal: res.soapFinal,
          soapVersion: res.soapVersion,
          emPendingChange: res.emPendingChange,
        });
      }
      router.refresh();
      return true;
    } finally {
      setBusy(null);
    }
  }

  /** Accept everything still outstanding. This is a LOOP over the same
   *  per-claim action, always index 0 because each success re-writes the
   *  array — so the audit sees N individual SUGGESTION_ADOPTED rows, exactly
   *  as if the doctor had tapped each one. It is deliberately not a bulk
   *  endpoint; there is nothing to add server-side and a bulk row would erase
   *  the per-claim trail. */
  async function acceptRemaining() {
    setBusy('bulk');
    try {
      let queue = claims;
      let guard = queue.length + 2;
      while (guard-- > 0) {
        if (queue.length === 0) break;
        const expectedText = queue[0].text;
        const res = await adoptSuggestionAction(props.visitId, 0, expectedText);
        if (!res.ok) {
          toast.error('Could not accept the remaining suggestions', { description: res.error });
          break;
        }
        queue = res.suggestedClaims ?? [];
        setClaims(queue);
        if (typeof res.soapFinal === 'string' && typeof res.soapVersion === 'number') {
          props.onAdopted({
            soapFinal: res.soapFinal,
            soapVersion: res.soapVersion,
            emPendingChange: res.emPendingChange,
          });
        }
      }
      router.refresh();
    } finally {
      setBusy(null);
    }
  }

  const remaining = claims.length;
  const emBlocking = props.emPendingChange != null && !emConfirmed;
  const blocked = props.rxBlocking || emBlocking;

  const renderSuggestion = (i: number) => {
    const c = claims[i];
    if (!c) return null;
    const key = claimKey(c, i);
    return (
      <div
        key={key}
        ref={attachSuggestion}
        data-suggestion-key={key}
        data-testid="review-doc-suggestion"
        className="qm-rdoc-sugg"
      >
        <p className="qm-rdoc-sugg-text">{c.text}</p>
        <div className="qm-rdoc-sugg-foot">
          <span className="qm-rdoc-sugg-tag">
            <Sparkles className="h-3 w-3" aria-hidden /> suggested — {reasonLabel(c.reason)}
          </span>
          <span className="qm-rdoc-sugg-acts">
            <button
              type="button"
              className="qm-rdoc-accept qm-tap-44"
              disabled={busy !== null}
              onClick={() => void act(i, 'adopt')}
              data-testid="review-doc-accept"
            >
              <Check className="h-3.5 w-3.5" aria-hidden /> Accept
            </button>
            <button
              type="button"
              className="qm-rdoc-dismiss qm-tap-44"
              disabled={busy !== null}
              onClick={() => void act(i, 'dismiss')}
            >
              Dismiss
            </button>
          </span>
        </div>
      </div>
    );
  };

  const hasSummary = props.summary.icd.length > 0 || props.summary.emCode !== null || props.summary.emNotApplicable;

  return (
    <div className="qm-rdoc" data-testid="review-document-view">
      {/* THE DOCUMENT — the real note renderer, with each section's suggestions
          rendered directly beneath it, where they would land if accepted. */}
      <article className="qm-rdoc-page">
        {props.renderNote((section) => {
          const idx = claimsBySection.bySection.get(section.id) ?? [];
          if (idx.length === 0) return null;
          return <div className="qm-rdoc-sugg-group">{idx.map((i) => renderSuggestion(i))}</div>;
        })}

        {/* A suggestion whose section heading is not in this note still gets
            read — dropping it silently would be the one unacceptable outcome. */}
        {claimsBySection.orphans.length > 0 && (
          <div className="qm-rdoc-sugg-group qm-rdoc-orphans">
            <h3 className="qm-rdoc-orphan-h">Also suggested</h3>
            {claimsBySection.orphans.map((i) => renderSuggestion(i))}
          </div>
        )}

        {/* ── INLINE GATES ───────────────────────────────────────────────
            At the position they belong to, one card per item, never a count.
            The Rx rail is the existing component: same override modal, same
            recordOverride action, one button per warning. */}
        {props.rxGateNode && (
          <section className="qm-rdoc-gate" data-testid="review-doc-rx-gate">
            <div className="qm-rdoc-gate-head">
              <AlertTriangle className="h-3.5 w-3.5" aria-hidden />
              <span>Prescription safety</span>
            </div>
            <div className="qm-rdoc-gate-body">{props.rxGateNode}</div>
          </section>
        )}

        {props.emPendingChange && (
          <section
            className={`qm-rdoc-gate qm-rdoc-gate-em${emConfirmed ? ' is-done' : ''}`}
            data-testid="review-doc-em-gate"
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

      {/* Everything else, linearised: one slim row, tap to expand. */}
      {hasSummary && (
        <section className="qm-rdoc-meta">
          <button
            type="button"
            className="qm-rdoc-meta-row qm-tap-44"
            aria-expanded={openSummary}
            onClick={() => setOpenSummary((v) => !v)}
            data-testid="review-doc-codes-toggle"
          >
            <ChevronRight
              className={`h-3.5 w-3.5 qm-rdoc-chev ${openSummary ? 'open' : ''}`}
              aria-hidden
            />
            <span className="qm-rdoc-meta-key">CODES · BILLING</span>
            <span className="qm-rdoc-meta-val">
              {props.summary.icd.map((r) => r.code).join(' · ') || '—'}
              {props.summary.emNotApplicable
                ? ''
                : props.summary.emCode
                  ? `  ·  ${props.summary.emCode}`
                  : ''}
            </span>
          </button>
          {openSummary && (
            <div className="qm-rdoc-meta-body">
              {props.summary.icd.map((r) => (
                <div key={r.code} className="qm-rdoc-meta-line">
                  <span className="qm-rdoc-meta-code">{r.code}</span>
                  <span>{r.description ?? ''}</span>
                </div>
              ))}
              {props.summary.emNotApplicable && (
                <div className="qm-rdoc-meta-line qm-rdoc-meta-muted">
                  E/M not applicable to this encounter
                </div>
              )}
            </div>
          )}
        </section>
      )}

      <section className="qm-rdoc-meta">
        <button
          type="button"
          className="qm-rdoc-meta-row qm-tap-44"
          aria-expanded={openDictation}
          aria-controls={dictationPanelId}
          onClick={() => setOpenDictation((v) => !v)}
          data-testid="review-doc-dictation-toggle"
        >
          <ChevronRight
            className={`h-3.5 w-3.5 qm-rdoc-chev ${openDictation ? 'open' : ''}`}
            aria-hidden
          />
          <span className="qm-rdoc-meta-key">{props.dictationLabel.toUpperCase()}</span>
        </button>
        {openDictation && (
          <div id={dictationPanelId} className="qm-rdoc-meta-body">
            {props.dictationNode}
          </div>
        )}
      </section>

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
            ) : remaining > 0 ? (
              <>
                <Sparkles
                  className="h-3.5 w-3.5 flex-none"
                  aria-hidden
                  style={{ color: 'var(--color-linear-sage-bright)' }}
                />
                <span className="qm-c3-rev2-sign-msg" data-testid="review-doc-bar-msg">
                  {remaining} suggestion{remaining === 1 ? '' : 's'} remaining
                  {!allSeen ? ' — scroll to review' : ''}
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
            {remaining > 0 && allSeen && (
              <button
                type="button"
                className="qm-rdoc-bulk qm-tap-44"
                onClick={() => void acceptRemaining()}
                disabled={busy !== null}
                data-testid="review-doc-accept-remaining"
              >
                {busy === 'bulk' ? 'Accepting…' : `Accept remaining (${remaining})`}
              </button>
            )}
            <SignAndSendModal
              visitId={props.visitId}
              doctorEmail={props.doctorEmail}
              emailEnabled={props.emailEnabled}
              signOnSubmit
              emPendingChange={props.emPendingChange}
              triggerLabel="Sign &amp; Download"
              triggerIcon={<FileSignature className="h-3.5 w-3.5" aria-hidden />}
              disabled={blocked || busy !== null}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
