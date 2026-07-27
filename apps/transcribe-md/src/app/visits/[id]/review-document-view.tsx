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
import { claimProse } from '@/lib/claim-prose';
import { spokenBody } from '@/lib/spoken-body';
import { parseNoteSections, type NoteSection } from '@/lib/parse-note-sections';
import {
  emChangeEq,
  normalizeSectionLabel as norm,
  sectionLabelForClaim,
  suggestionReasonLabel as reasonLabel,
} from '@/lib/suggestion-labels';
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
  /** PHASE 2 — the doctor's own form, filled so far, INSTEAD of the styled
   *  note. Given a per-section slot renderer, exactly as `renderNote` is, so
   *  the suggestion cards and gates below are byte-identical either way; only
   *  what the page is made of changes. Absent (or returning null) → the styled
   *  note renders, which is the correct page for a non-template visit and the
   *  honest fallback when the document could not be produced. */
  /*  Takes a slot renderer keyed by SECTION LABEL — the document surface has
   *  headings, not parsed note sections, and synthesising a NoteSection to feed
   *  it would break the moment that type gains a field. */
  renderDocument?: (
    afterLabel: (label: string) => React.ReactNode,
  ) => React.ReactNode;
  /** Verifier-demoted claims, in DB-array order — the index IS the action's. */
  claims: SuggestedClaimView[];
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
  summary: ReviewDocumentSummary;
  /** The EXISTING billing panel and codes table, passed in verbatim. Collapsing
   *  a surface is not the same as removing it: the doctor must be able to
   *  override, rescore or dispute a level from here, with the same components,
   *  the same enforcement and the same audit the Billing/Codes tabs had. */
  /** The note changed since the level was scored — the sign route refuses
   *  while this holds. Opening the codes row re-scores it. */
  emStale?: boolean;
  /** Re-scores lazily. Returns whether the level moved. */
  onRescoreEm?: () => Promise<void>;
  billingNode: React.ReactNode;
  codesNode: React.ReactNode;
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

export function ReviewDocumentView(props: ReviewDocumentViewProps) {
  const router = useRouter();
  /** One panel now, where there were two standing rows. */
  const detailsPanelId = useId();

  const [claims, setClaims] = useState<SuggestedClaimView[]>(props.claims);
  const [busy, setBusy] = useState<number | 'bulk' | null>(null);
  const [openDetails, setOpenDetails] = useState(false);
  const [emConfirmed, setEmConfirmed] = useState(false);

  // Claims arrive fresh on every server refresh; the local copy is replaced
  // wholesale from each action's response so rendered indices never drift from
  // the DB array (the same discipline the lane keeps).
  const [prevClaims, setPrevClaims] = useState(props.claims);
  if (prevClaims !== props.claims) {
    setPrevClaims(props.claims);
    setClaims(props.claims);
  }

  // BLOCK fix. `emConfirmed` is a local acknowledgement of a value the SERVER
  // recomputes: adopting another suggestion can move the level again (see
  // suggestion-actions' mergeEmPendingChange). Left latched, the card would go
  // on saying "Level confirmed" for a level the doctor never saw — the exact
  // silent-flip regression prod-smoke #311 closed. Same derived-state-during-
  // render pattern the claims list uses above.
  //
  // Compared by VALUE, not identity. The parent re-sets this state after EVERY
  // adopt (the action returns the current pending record either way), so an
  // identity check would silently un-confirm the level each time the doctor
  // accepted an unrelated suggestion — confirm/re-confirm churn on a clinical
  // gate. Only a real change to the codes should re-arm the card.
  const [prevEm, setPrevEm] = useState(props.emPendingChange);
  if (!emChangeEq(prevEm, props.emPendingChange)) {
    setPrevEm(props.emPendingChange);
    setEmConfirmed(false);
  }

  const sections = useMemo(() => parseNoteSections(props.soapFinal), [props.soapFinal]);

  // Which claims sit under which section heading.
  //
  // Keyed by the NORMALISED LABEL, not by parseNoteSections' generated id. The
  // slot's section comes from SoapBody's own parse of its own (editable) text,
  // while this map is built from the soapFinal prop; the moment the doctor
  // edits inline those two parses can produce different ids for the same
  // heading, and a suggestion keyed by id would silently disappear off the
  // page. The label is what the adopt action joins on anyway.
  //
  // Index is preserved because the action addresses claims BY INDEX — the
  // entries here are positions in the DB array, never renumbered.
  const claimsByLabel = useMemo(() => {
    const byLabel = new Map<string, number[]>();
    const labels = new Set(sections.map((s) => norm(s.label)));
    const placed = new Set<number>();
    claims.forEach((c, i) => {
      // Resolves a `###` sub-heading to the top-level section that owns it —
      // the section the adopt action will actually append into.
      const key = sectionLabelForClaim(c.section, sections);
      if (!key || !labels.has(key)) return;
      const list = byLabel.get(key) ?? [];
      list.push(i);
      byLabel.set(key, list);
      placed.add(i);
    });
    const orphans = claims.map((_, i) => i).filter((i) => !placed.has(i));
    return { byLabel, orphans };
  }, [claims, sections]);

  // ── READING IS THE REVIEW ────────────────────────────────────────────────
  // Bulk-accept unlocks only after every suggestion has been fully on screen.
  // threshold:1 means the whole card, not a sliver of it; once seen, a card
  // stays seen (scrolling back up must not re-lock the bar).
  const [seen, setSeen] = useState<Set<string>>(new Set());
  const observerRef = useRef<IntersectionObserver | null>(null);

  const markSeen = useCallback((key: string) => {
    setSeen((prev) => (prev.has(key) ? prev : new Set(prev).add(key)));
  }, []);

  /** The observer is created LAZILY, here, rather than in an effect. Ref
   *  callbacks fire during commit, before effects run — an observer built in
   *  useEffect did not exist yet when the cards attached, so nothing was ever
   *  observed and the bar could never unlock.
   *
   *  WHAT IS OBSERVED IS A SENTINEL AT THE CARD'S BOTTOM EDGE, not the card.
   *  Inferring "fully read" from intersectionRatio cannot work: the observer
   *  only reports when the crossed-threshold BUCKET changes, so a card 5%
   *  taller than the viewport tops out at a reported ratio of 0.75 and never
   *  satisfies any "seen" test — the gate would stay locked forever, with no
   *  error, for exactly the card size a long suggestion on a phone produces.
   *  Scrolling the BOTTOM of the card into view is the semantics we actually
   *  mean, and it is height-independent. */
  const attachSuggestion = useCallback(
    (el: HTMLElement | null) => {
      if (!el) return;
      const key = el.dataset.suggestionKey;
      if (!key) return;
      if (typeof IntersectionObserver === 'undefined') {
        // No observer (jsdom, very old browsers): do not hold the doctor
        // hostage to a capability the browser lacks.
        markSeen(key);
        return;
      }
      if (!observerRef.current) {
        observerRef.current = new IntersectionObserver(
          (entries) => {
            for (const e of entries) {
              if (!e.isIntersecting) continue;
              const k = (e.target as HTMLElement).dataset.suggestionKey;
              if (k) markSeen(k);
            }
          },
          // The sentinel is a zero-height element; any intersection at all
          // means its edge has entered the viewport.
          { threshold: 0 },
        );
      }
      observerRef.current.observe(el);
    },
    [markSeen],
  );

  useEffect(() => () => observerRef.current?.disconnect(), []);

  /** Content-derived, NOT index-derived. Accepting one claim renumbers the DB
   *  array, so an index-keyed set invalidated every remaining card's "seen"
   *  mark: the bar fell back to "scroll to review" and the bulk button vanished
   *  even though the doctor had read everything — intermittently, because a card
   *  still fully in view re-fired the observer and one scrolled off did not. */
  const claimKey = (c: SuggestedClaimView) => `${c.section}::${c.text}`;
  const allSeen = claims.every((c) => seen.has(claimKey(c)));

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
        // Parity with the suggestions lane: an adoption that moves the billing
        // level says so out loud.
        if (res.emPendingChange) {
          toast.warning('Documentation level changed', {
            description: `Now supports ${res.emPendingChange.to} — confirm before signing.`,
            duration: 8_000,
          });
        }
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
      let last: Awaited<ReturnType<typeof adoptSuggestionAction>> | null = null;
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
        // Collected, not emitted: onAdopted bumps a key that remounts the whole
        // SoapEditor subtree, so emitting per iteration re-parsed the note and
        // tore down every card once per suggestion.
        last = res;
      }
      if (last && typeof last.soapFinal === 'string' && typeof last.soapVersion === 'number') {
        props.onAdopted({
          soapFinal: last.soapFinal,
          soapVersion: last.soapVersion,
          emPendingChange: last.emPendingChange,
        });
      }
      if (last?.emPendingChange) {
        toast.warning('Documentation level changed', {
          description: `Now supports ${last.emPendingChange.to} — confirm before signing.`,
          duration: 8_000,
        });
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
    const key = claimKey(c);
    return (
      <div
        key={`${i}::${key}`}
        data-testid="review-doc-suggestion"
        className="qm-rdoc-sugg"
      >
        {/* A measurement row quoted from the note is markup, not a clinical
            statement — and the doctor is being asked whether it belongs in a
            patient's record. Rendered as a sentence, in their own column
            names. Anything that is not a table row is untouched. */}
        <p className="qm-rdoc-sugg-text">{claimProse(c.text, props.soapFinal)}</p>
        {/* The bottom-edge sentinel: reaching it IS having read the card. */}
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
        <span
          ref={attachSuggestion}
          data-suggestion-key={key}
          aria-hidden
          className="qm-rdoc-sugg-end"
        />
      </div>
    );
  };

  // The codes row is also where a stale billing level gets re-checked, so a
  // visit with nothing to summarise must still be able to open it — otherwise
  // the sign gate refuses and there is no control on the page that clears it.
  const hasSummary =
    props.summary.icd.length > 0 ||
    props.summary.emCode !== null ||
    props.summary.emNotApplicable ||
    Boolean(props.emStale);

  return (
    <div className="qm-rdoc" data-testid="review-document-view">
      {/* THE DOCUMENT — the real note renderer, with each section's suggestions
          rendered directly beneath it, where they would land if accepted. */}
      <article className="qm-rdoc-page">
        {(() => {
          // ONE slot renderer, used by whichever surface is drawing. The cards,
          // their indices, and the adopt action they call do not know or care
          // which one it is.
          const afterLabel = (label: string) => {
            const idx = claimsByLabel.byLabel.get(norm(label)) ?? [];
            if (idx.length === 0) return null;
            return (
              <div className="qm-rdoc-sugg-group">{idx.map((i) => renderSuggestion(i))}</div>
            );
          };
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
                    {/* The review placeholder is a UI artifact, not note
                        content — the inline highlight is what says "set aside",
                        and reading the marker aloud would say it twice. */}
                    <p>{spokenBody(sec.body, props.soapFinal)}</p>
                  </section>
                ))}
              </div>
            </>
          );
        })()}

        {/* A suggestion whose section heading is not in this note still gets
            read — dropping it silently would be the one unacceptable outcome. */}
        {claimsByLabel.orphans.length > 0 && (
          <div className="qm-rdoc-sugg-group qm-rdoc-orphans">
            <h3 className="qm-rdoc-orphan-h">Also suggested</h3>
            {claimsByLabel.orphans.map((i) => renderSuggestion(i))}
          </div>
        )}

        {/* ── INLINE GATES ───────────────────────────────────────────────
            At the position they belong to, one card per item, never a count.
            The Rx rail is the existing component: same override modal, same
            recordOverride action, one button per warning. */}
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

      {/* ── ON DEMAND ─────────────────────────────────────────────────────
          ONE affordance where there were two standing rows.

          "CODES · BILLING" and the dictation row sat under every note, on every
          visit, whether or not they had anything to say — an ultrasound report
          carried a billing row for a level that does not apply to it. They are
          not deleted, they are folded: everything both rows held is behind this
          one, and the chat opens it by name ("show billing"). A test asserts
          each datum is still reachable.

          The E/M CONFIRM CARD above is untouched and remains the gate. This is
          where a level is CHANGED or disputed — one tap, exactly as before. */}
      <section className="qm-rdoc-meta">
        <button
          type="button"
          className="qm-rdoc-meta-row qm-tap-44"
          aria-expanded={openDetails}
          aria-controls={detailsPanelId}
          data-chat-target="codes"
          onClick={() => {
            const next = !openDetails;
            setOpenDetails(next);
            // LAZY RE-SCORE, moved with the panel it belonged to. Opening this
            // is the moment the doctor is actually looking at the level, so it
            // is the moment to check it — not on every keystroke-sized save.
            if (next && props.emStale) void props.onRescoreEm?.();
          }}
          data-testid="review-doc-details-toggle"
        >
          <ChevronRight
            className={`h-3.5 w-3.5 qm-rdoc-chev ${openDetails ? 'open' : ''}`}
            aria-hidden
          />
          <span className="qm-rdoc-meta-key">⋯ details</span>
          <span className="qm-rdoc-meta-val">
            {/* Say WHY signing is blocked, at the control that resolves it. A
                gate the doctor cannot see the reason for is a dead end — so
                this badge follows the panel rather than staying on a row that
                no longer exists. */}
            {props.emStale && (
              <span className="qm-rdoc-stale" data-testid="em-stale-badge">
                needs re-check
              </span>
            )}
          </span>
        </button>
        {openDetails && (
          <div id={detailsPanelId} className="qm-rdoc-meta-body qm-rdoc-meta-panels">
            {/* Verbatim: BillingCardC3 and CodesTab, the same components the
                tabs rendered. Override / rescore / dispute all live here, so a
                doctor who disagrees with a level never needs the surface
                changed under them. */}
            {hasSummary && (
              <>
                <div className="qm-rdoc-panel" data-testid="review-doc-billing-panel">
                  {props.billingNode}
                </div>
                <div className="qm-rdoc-panel" data-testid="review-doc-codes-panel">
                  {props.codesNode}
                </div>
              </>
            )}
            <div className="qm-rdoc-panel" data-testid="review-doc-dictation-panel">
              <h4 className="qm-rdoc-panel-h">{props.dictationLabel.toUpperCase()}</h4>
              {props.dictationNode}
            </div>
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
            {/* Re-check before the modal opens. The gate render IS a moment
                the doctor is looking at the level, and it means they meet the
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
              disabled={blocked || busy !== null}
            />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
