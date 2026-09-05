'use client';

// ============================================================================
// IcdCodingView — F8-S2. THE CODING SURFACE, ON THE VISIT'S PAPER.
// ----------------------------------------------------------------------------
// Ruling #153. This is the caller F8-S1 and F8-S1b deliberately shipped
// without: the substrate has existed since 2026-08-25 and NOTHING could invoke
// it. AGENTS.md records the opposite failure twice (F4's library with no
// caller; F24-S4's model that was never told), which is why S1's own row named
// this slice rather than claiming F8 was done.
//
// ⚠️ MINIMAL IS THE RULING, NOT A SHORTCUT — #153(c). The Phase-1 redesign
// restyles this, so structure now and style then. The design contract's
// 65/35 split, evidence panel, search-add typeahead and specialty-aware
// ranking are NOT built here and are not silently dropped either: they are
// named at the bottom of this comment as what this view does not claim.
//
// ── WHAT FLOWS WHERE, AND IT IS NOT NEGOTIABLE — #153(d) ────────────────────
//
// Decisions flow ONLY through `transcribe_visits.icdDecisions`, via
// `POST /api/visits/[id]/icd-codes/decision`. The PROVENANCE SEPARATION
// promoted to a design principle on #149(a) is the rule this view is most able
// to break and does not:
//
//   · machine-produced drop records live in `icdCodes`      (read-only here)
//   · clinician acts live in `icdDecisions`                 (written by the route)
//   · THE TWO COLUMNS NEVER CROSS-WRITE
//
// So the amber section below RENDERS and offers no action at all. That is not
// an omission — #149(g) makes *"a dropped code can never be accepted"* a
// property of the data, and a button here would be the one thing capable of
// making it false again.
//
// ── SIGNED IS READ-ONLY, AND THE SERVER IS THE AUTHORITY — #153(e) ─────────
//
// The route refuses a decision on a signed visit with 409 `VISIT_LOCKED`, and
// that refusal is the enforcement. This view hides the controls so it does not
// offer an action the server will refuse — *"the UI wouldn't offer that"* is
// exactly how an office E/M code once reached an ultrasound report, so the UI
// is the second line and never the first.
//
// ── WHAT THIS VIEW DOES NOT CLAIM ──────────────────────────────────────────
//
//   · no search-add typeahead — a code the suggester never proposed has no
//     evidence quote and never met `isValidIcd10`, and the route refuses it
//     (`ICD_CODE_NOT_SUGGESTED`). Adding one needs its own allowlist check on
//     the way in and does not come free with this slice.
//   · no "Use K21.00 instead" chip — #149(f) DELETED that derivation rather
//     than repairing it: prefix-scanning a 604-code STARTER set offered
//     `E66.0 -> E66.01`, upcoding plain obesity to MORBID obesity.
//   · no specialty-aware ranking — order is the suggester's own.
//   · nothing here changes what any export or note emits. An accepted code
//     still flows nowhere; that is a later slice and a document-visible change
//     needing its own adversarial pass.
// ============================================================================

import { useCallback, useMemo, useState } from 'react';

import { ledgerSections } from '@/lib/icd-ledger-sections';
import { ICD_ROW_STATE_LABEL, icdRowState, type IcdRowState } from '@/lib/icd-row-state';
import {
  ICD_REJECTION_REASONS,
  icdDecisionSummary,
  normalizeIcdCode,
  projectIcdDecisions,
  type IcdDecisionProjection,
  type IcdRejectionReason,
} from '@/lib/icd-decisions';
import { amberIcdDrops } from '@/lib/icd-drops';

// ---------------------------------------------------------------------------
// Labels. Prose lives HERE and never in the column — ruling #154.
// ---------------------------------------------------------------------------

const REJECTION_REASON_LABEL: Record<IcdRejectionReason, string> = {
  not_supported_by_note: 'Not supported by the note',
  not_this_encounter: 'Not addressed at this encounter',
  wrong_specificity: 'Wrong specificity',
  duplicate_of_another_code: 'Duplicate of another code',
  other: 'Other',
};

/**
 * ⚠️ THE AMBER LABEL IS A FACT ABOUT OUR COVERAGE, NOT ABOUT THE CODE — and
 * getting this wrong was a WITHDRAWN first draft in #149(e), so it is spelled
 * out rather than paraphrased.
 *
 * `isValidIcd10` is membership of a **604-code STARTER SET** whose own header
 * says it "does NOT replace the full CMS list (~70 000 codes)". Measured over
 * all 64 production rejections — 65 distinct codes, partition reconciling
 * 12 + 2 + 51 = 65 — **51 are REAL, SUBMITTABLE codes** simply absent from the
 * starter set. Telling a physician those are "not billable" is FALSE, and the
 * direction of harm is UNDER-CODING.
 *
 * So the label is "Not in verified set", which is also what the design
 * contract's own verification badge reads.
 */
const AMBER_DROP_LABEL = 'Not in this build’s verified set';

// ---------------------------------------------------------------------------
// Wire shape — the suggester's own output, read for display only.
// ---------------------------------------------------------------------------

interface SuggestedDetail {
  description?: string;
  evidenceQuote?: string;
  confidence?: number;
}

/**
 * Detail for the cards, keyed by NORMALISED code.
 *
 * ⚠️ ONE MATCHER, AND THAT IS WHY `normalizeIcdCode` IS IMPORTED RATHER THAN
 * RE-DERIVED. `icd-decisions.ts` keys its stored map with it and tests
 * membership of the suggested set with it, and its header records that a read
 * path and a write path resolving one identifier with two matchers is a defect
 * this repository has already shipped (the chat-editor silent no-op). A
 * lower-cased key here would render every card blank while the projection was
 * perfectly correct.
 */
function readSuggestedDetail(rawIcdCodes: unknown): Record<string, SuggestedDetail> {
  const out: Record<string, SuggestedDetail> = {};
  const rows =
    Array.isArray(rawIcdCodes)
      ? rawIcdCodes
      : rawIcdCodes && typeof rawIcdCodes === 'object'
        ? ((rawIcdCodes as { codes?: unknown }).codes ?? [])
        : [];
  if (!Array.isArray(rows)) return out;
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue;
    const r = row as Record<string, unknown>;
    const code = normalizeIcdCode(r.code);
    if (!code || out[code]) continue;
    out[code] = {
      description: typeof r.description === 'string' ? r.description : undefined,
      evidenceQuote:
        typeof r.evidence_quote === 'string' && r.evidence_quote.length > 0
          ? r.evidence_quote
          : undefined,
      confidence: typeof r.confidence === 'number' ? r.confidence : undefined,
    };
  }
  return out;
}

// ---------------------------------------------------------------------------

export interface IcdCodingViewProps {
  visitId: string;
  /** The suggester's blob. Read-only here — #149(a) provenance separation. */
  icdCodes: unknown;
  /** The stored decision map. */
  icdDecisions: unknown;
  /** Signed OR otherwise read-only. Controls are not rendered; the server
   *  refuses regardless. */
  readonly: boolean;
}

export function IcdCodingView(props: IcdCodingViewProps) {
  // Server truth on first paint, then replaced by whatever each response
  // returns. The route projects from what it just computed rather than
  // re-reading, so the rendered state is the state the write produced.
  //
  // ⚠️ THE INITIALISER RUNS ONCE, AND `detail`/`drops` BELOW DO NOT — so if
  // `props.icdCodes` ever changed under this component, the two would disagree:
  // the cards would re-derive from the new blob while the partition kept
  // describing the old one. **Unreachable today, by measurement rather than by
  // hope:** `icdCodes` has exactly ONE writer (`07a-icd-coding.ts:572`) and
  // `layer-skip.ts:101` skips L7a whenever that column has content, so within a
  // page session the prop is fixed by the server render.
  //
  // ⚠️ WHAT RE-ARMS IT, so this is a lookup and not a judgement: any path that
  // clears or rewrites `icdCodes` on a visit that already has content — a
  // "re-code this note" action, a force-rerun flag on L7a, or a manual repair.
  // The cure at that point is to key this component on the blob, or to lift the
  // projection to a prop; it is deliberately NOT built now, because a
  // synchronisation mechanism with no trigger is untestable code on a clinical
  // surface.
  const [projection, setProjection] = useState<IcdDecisionProjection>(() =>
    projectIcdDecisions(props.icdCodes, props.icdDecisions),
  );
  /**
   * The code with a decision in flight — and EVERY control is disabled while it
   * is set, not just this code's.
   *
   * ⚠️ THE ADVERSARIAL PASS FOUND THIS, AND A PER-CODE DISABLE WAS THE FIRST
   * DRAFT. Two decisions in flight at once are serialised correctly by the
   * SERVER — the route takes a row lock, so the second request reads the map
   * after the first commits. The defect is on the CLIENT: each response carries
   * a full projection, and whichever arrives LAST wins the render. If response
   * A lands after response B, the screen shows a projection computed before B
   * existed, and **the doctor watches a decision they just made disappear.**
   *
   * The server is right and the screen is wrong until a reload — which is
   * exactly the "your work vanished" perception this whole slice's view switch
   * was built to avoid. One in-flight request at a time removes the race
   * outright rather than reconciling it, which is the minimal fix and the one
   * that cannot be subtly wrong.
   */
  const [pending, setPending] = useState<string | null>(null);
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const detail = useMemo(() => readSuggestedDetail(props.icdCodes), [props.icdCodes]);
  const drops = useMemo(() => amberIcdDrops(props.icdCodes), [props.icdCodes]);
  const summary = useMemo(() => icdDecisionSummary(projection), [projection]);

  const send = useCallback(
    async (code: string, decision: 'accepted' | 'rejected' | 'cleared', reason?: IcdRejectionReason) => {
      setPending(code);
      setError(null);
      try {
        const res = await fetch(`/api/visits/${props.visitId}/icd-codes/decision`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ code, decision, ...(reason ? { reason } : {}) }),
        });
        const body = await res.json().catch(() => null);
        if (!res.ok) {
          // ⚠️ SILENCE IS ILLEGAL. A refused decision that renders as nothing
          // teaches the doctor the button is broken, and the refusal is now
          // audited server-side — so a UI that swallowed it would leave the
          // log and the screen disagreeing about the same event.
          setError(
            (body && typeof body.error === 'string' && body.error) ||
              'That coding decision could not be saved.',
          );
          return;
        }
        if (body?.projection) setProjection(body.projection as IcdDecisionProjection);
        setRejecting(null);
      } catch {
        setError('That coding decision could not be saved.');
      } finally {
        setPending(null);
      }
    },
    [props.visitId],
  );

  const kicker = 'qm-rounds-kicker'; // the DARK-surface kicker. See the design contract.

  // ── THE LEDGER ROW — the frames' unit, in all five states ────────────────
  // `icd-code-row-states` (24:2): identical geometry in every state, only the
  // colour and the one tint change, which is what makes them read as one
  // object. The grid is 96 / 1fr / 60 — the frames' 96 / 484 / 60 summing to the
  // card's 720 less its 40px side padding.
  //
  // ⚠️ THE TESTID STAYS `icd-card-${code}`. The card became a row, but the
  // suites address it by that name and renaming it would break them for a
  // cosmetic reason. What the element IS changed; what it is CALLED did not.
  const ledgerRow = (
    code: string,
    state: IcdRowState,
    below?: React.ReactNode,
    // ⚠️ AN OUTER TESTID, NOT A REPLACEMENT FOR THE INNER ONE. The amber
    // section's suite reads `icd-drop-<code>`.textContent for the label and
    // counts buttons INSIDE it, so that name has to sit on the wrapper that
    // CONTAINS the label — putting it on the row itself would leave the label
    // a sibling and turn a true assertion false for a cosmetic reason.
    outerTestId?: string,
  ) => {
    const d = detail[code];
    const decision = projection.decisions[code];
    const reason = decision?.reason;
    return (
      <div key={code} {...(outerTestId ? { 'data-testid': outerTestId } : {})}>
        <div
          className="qm-icd-row"
          data-state={state}
          data-testid={`icd-card-${code}`}
          data-code={code}
        >
          {/* ⚠️ THE STATE, AS TEXT. FOUND BY THE ADVERSARIAL PASS.
              The three sections this row replaced carried the decision state in
              a HEADING — "Needs review · 1", "Accepted · 1". Moving the state
              onto the row moved it into `data-state` and a CSS tint, and
              `ICD_ROW_STATE_LABEL` — defined in this slice — was rendered
              NOWHERE. Measured on a signed visit: an accepted row and a held
              row were byte-identical in text, and the only accessible name was
              `null`.

              That is an accepted-capability loss on the surface a doctor
              attests from, and it is WCAG 1.4.1 (colour as the sole carrier of
              information): invisible to a screen reader, to greyscale print,
              to a PDF of the tab, and to a colour-vision-deficient physician.
              The auto-accept in this same slice makes the mixed state the
              NORMAL case — codes at or above the threshold become accepted at
              signature and the rest stay held forever — so every signed note
              now carries both kinds side by side.

              ⚠️ VISUALLY HIDDEN, NOT VISIBLE, AND THAT IS A DELIBERATE LIMIT.
              This restores the accessibility-tree parity that existed before
              the conversion without moving one pixel of the ratified frames. It
              does NOT help the sighted colour-blind reader or a greyscale
              print — that needs a visible marker, which is a DESIGN decision
              and is on the owner's batched list rather than invented here. */}
          <span className="qm-sr-only">
            {ICD_ROW_STATE_LABEL[state]}
            {/* ⚠️ AND THE PROVENANCE, IN THE ONE PLACE IT LANDS. The orphaned
                sentence below was made provenance-aware and the ROW was not —
                but `orphaned` is documented as unreachable today, while every
                auto-accept lands HERE as `pre-accepted`. A machine-written
                acceptance and a doctor's own were indistinguishable in text,
                on a signed claim, under a caption that says the physician
                makes the final coding decision. */}
            {projection.decisions[code]?.auto ? ' — accepted automatically at signing' : ''}
            {'. '}
          </span>
          <span className="qm-icd-row-code">{code}</span>
          <span className="qm-icd-row-desc">
            {d?.description ?? ''}
            {/* State 3 carries the doctor's reason as a second line — the frame
                draws the description and the reason stacked in one cell. */}
            {state === 'rejected' && reason ? (
              <span className="qm-icd-row-reason" data-testid={`icd-rejected-reason-${code}`}>
                {REJECTION_REASON_LABEL[reason]}
              </span>
            ) : null}
          </span>
          <span className="qm-icd-row-pct">
            {/* State 5 shows an em dash, never a number: the code never reached
                the note, so a confidence would be a claim about something that
                did not happen. */}
            <span className="qm-icd-row-conf">
              {state === 'not-carried'
                ? '—'
                : typeof d?.confidence === 'number'
                  ? `${Math.round(d.confidence * (d.confidence <= 1 ? 100 : 1))}%`
                  : ''}
            </span>
            {/* ⚠️ THE PROVENANCE WORD — ruling #187(2). VISIBLE TEXT, NEVER A
                COLOUR. It survives greyscale print and colour-vision
                deficiency, which is exactly what the hidden accessibility label
                below cannot do for a sighted reader.
                ⚠️ AND IT DOES NOT REPLACE THAT HIDDEN LABEL. The ruling keeps
                both, because they answer different readers: the hidden text
                restores the parity the pre-conversion section HEADINGS carried
                for assistive technology, and this word reaches the doctor
                looking at the screen. Removing either re-opens half the defect.

                ⚠️ IT APPEARS ONLY WHERE A DECISION EXISTS. A HELD row has no
                provenance to state, and printing `you` on a code nobody has
                decided would assert an attestation that did not happen — the
                wrong-field harm, which this arc has already paid for once in
                the orphaned sentence.

                ⚠️ STACKED UNDER THE CONFIDENCE RATHER THAN BESIDE IT, and that
                is geometry, not taste: the frames fix this meta column at 60px,
                and `95%` + a separator + `auto` does not fit. Stacking keeps the
                frames' column width and adds no new element. */}
            {decision ? (
              <span className="qm-icd-row-prov" data-provenance={decision.auto ? 'auto' : 'you'}>
                {decision.auto ? 'auto' : 'you'}
              </span>
            ) : null}
          </span>
        </div>
        {d?.evidenceQuote ? (
          <p
            className="qm-icd-row-evidence"
            data-testid={`icd-evidence-${code}`}
          >
            “{d.evidenceQuote}”
          </p>
        ) : null}
        {below}
      </div>
    );
  };

  const section = (title: string, count: number, children: React.ReactNode) => (
    <section className="mb-5" data-testid={`icd-section-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <h3 className={`${kicker} mb-2`} style={{ color: 'var(--rounds-ink-muted)' }}>
        {title} · {count}
      </h3>
      {children}
    </section>
  );

  // ── THE RECEIPT ─────────────────────────────────────────────────────────
  // The owner's frames put the ledger on a single card: `claim-summary-ready` /
  // `claim-summary-signed` (vDPGIxwPmm08BTzBD99vfQ) for the shell, and
  // `icd-code-row-states` (24:2, Zvgz37i6jVoNYy9BzAAtoQ) for the five row
  // states. Geometry, type and copy are the frames'; colours map by ROLE to
  // Rounds tokens, per the standing ruling.
  //
  // ⚠️ THE COUNTS LINE STAYS, AND IT IS NOT IN THE FRAMES. The frames put patient
  // identity above the card — which this component does not own; the Rounds
  // stage renders it — leaving that slot free. The chip carries a property a
  // gate asserts and a doctor needs: an ORPHANED accept reads "0 accepted",
  // because it is a decision about a code this note no longer carries. Dropping
  // it to match a mockup would delete a tested clinical claim, so it keeps its
  // slot and the frames' caption is added below the card where the frames put it.
  return (
    <div className="w-full" data-testid="icd-coding-view">
      <div
        className="mb-4 text-[13px]"
        style={{ color: 'var(--rounds-ink-muted)' }}
        data-testid="icd-summary-chip"
      >
        <strong style={{ color: 'var(--rounds-ink)' }}>{summary.suggested}</strong> suggested ·{' '}
        <strong style={{ color: 'var(--rounds-ink)' }}>{summary.accepted}</strong> accepted ·{' '}
        <strong style={{ color: 'var(--rounds-ink)' }}>{summary.needsReview}</strong> needs review
      </div>

      {error ? (
        <div
          role="alert"
          data-testid="icd-decision-error"
          className="mb-4 rounded-lg px-3 py-2 text-[13px]"
          style={{
            border: '1px solid var(--rounds-critical)',
            color: 'var(--rounds-critical-on-dark)',
          }}
        >
          {error}
        </div>
      ) : null}

      {props.readonly ? (
        <p
          className="mb-4 text-[13px]"
          role="status"
          data-testid="icd-frozen-notice"
          style={{ color: 'var(--rounds-ink-muted)' }}
        >
          This visit is signed — coding decisions are frozen.
        </p>
      ) : null}

      {projection.suggested.length === 0 ? (
        <p className="text-[13px]" style={{ color: 'var(--rounds-ink-muted)' }} data-testid="icd-empty">
          The suggester proposed no codes for this note.
        </p>
      ) : null}

      <div className="qm-icd-ledger" data-testid="icd-ledger">
        <div className="qm-icd-ledger-title" data-testid="icd-ledger-title">
          {props.readonly ? 'Coding — signed' : 'Coding — ready to sign'}
        </div>
        <hr className="qm-icd-ledger-rule" />

      {/* ── THE LEDGER, GROUPED BY CLINICAL CATEGORY ──────────────────────
          The frames group by category — DIAGNOSES / HISTORY & SCREENING — where
          this surface grouped by decision state. The five STATES did not go
          away: they moved onto the row, which is what `icd-code-row-states`
          approves, so the same five distinctions survive on a denser surface.

          ⚠️ ORPHANED AND NOT-CARRIED KEEP THEIR OWN SECTIONS BELOW, and that is
          not an inconsistency: neither is a SUGGESTED code, so neither belongs
          under a heading that partitions the suggestions. */}
      {ledgerSections(projection.suggested).map((sec) => (
        <section key={sec.id} data-testid={`icd-section-${sec.id}`}>
          <div className="qm-icd-section-label">{sec.label}</div>
          {sec.codes.map((code) => {
            const state = icdRowState(code, projection);
            return ledgerRow(
              code,
              state,
              // ⚠️ THE RULED CONTROLS, UNCHANGED IN BEHAVIOUR. Only a HELD row
              // offers them, and only when the caller is not readonly — the
              // three independent `!props.readonly` gates and the frozen notice
              // stay exactly as #153(e) requires: the surface must not offer an
              // action the server will refuse.
              state === 'held' && !props.readonly ? (
                rejecting === code ? (
                  <div className="qm-icd-row-actions" data-testid={`icd-reason-picker-${code}`}>
                    <span className={kicker} style={{ color: 'var(--rounds-text-3)' }}>
                      Why is this code wrong?
                    </span>
                    {ICD_REJECTION_REASONS.map((r) => (
                      <button
                        key={r}
                        type="button"
                        data-testid={`icd-reason-${code}-${r}`}
                        disabled={pending !== null}
                        onClick={() => void send(code, 'rejected', r)}
                        className="rounded-md px-2 py-1 text-[12px]"
                        style={{
                          border: '1px solid var(--rounds-line-2)',
                          color: 'var(--rounds-text-2)',
                        }}
                      >
                        {REJECTION_REASON_LABEL[r]}
                      </button>
                    ))}
                    <button
                      type="button"
                      data-testid={`icd-reason-cancel-${code}`}
                      onClick={() => setRejecting(null)}
                      className="rounded-md px-2 py-1 text-[12px]"
                      style={{ color: 'var(--rounds-text-3)' }}
                    >
                      Cancel
                    </button>
                  </div>
                ) : (
                  <div className="qm-icd-row-actions">
                    <button
                      type="button"
                      data-testid={`icd-accept-${code}`}
                      disabled={pending !== null}
                      onClick={() => void send(code, 'accepted')}
                      className="rounded-md px-2.5 py-1 text-[12px] font-medium"
                      style={{
                        background: 'var(--rounds-accent)',
                        color: 'var(--rounds-on-accent)',
                      }}
                    >
                      Accept
                    </button>
                    <button
                      type="button"
                      data-testid={`icd-reject-${code}`}
                      disabled={pending !== null}
                      onClick={() => setRejecting(code)}
                      className="rounded-md px-2.5 py-1 text-[12px]"
                      style={{
                        border: '1px solid var(--rounds-line-2)',
                        color: 'var(--rounds-text-2)',
                      }}
                    >
                      Reject
                    </button>
                  </div>
                )
              ) : // A DECIDED row keeps its Undo — the same control the two
              // decision-state sections carried, on the same testid, emitted
              // from ONE branch now instead of two.
              (state === 'pre-accepted' || state === 'rejected') && !props.readonly ? (
                <div className="qm-icd-row-actions">
                  <button
                    type="button"
                    data-testid={`icd-undo-${code}`}
                    disabled={pending !== null}
                    onClick={() => void send(code, 'cleared')}
                    className="rounded-md px-2.5 py-1 text-[12px]"
                    style={{
                      border: '1px solid var(--rounds-line-2)',
                      color: 'var(--rounds-text-2)',
                    }}
                  >
                    Undo
                  </button>
                </div>
              ) : null,
            );
          })}
        </section>
      ))}

      {/* ⚠️ ORPHANED KEEPS ITS OWN SECTION, and that is not a departure from
          the frames' category grouping. An orphaned code is NOT in
          `projection.suggested` — the suggester no longer proposes it — so it
          cannot be filed under a heading that partitions the suggestions. The
          section title is load-bearing: `icd-section-no-longer-suggested`. */}
      {projection.orphaned.length > 0 &&
        section(
          'No longer suggested',
          projection.orphaned.length,
          projection.orphaned.map((code) =>
            ledgerRow(
              code,
              'orphaned',
              // ⚠️ "YOU DECIDED" IS FALSE OF A MACHINE-WRITTEN RECORD, and an
              // orphaned auto-accept is reachable: `icdCodes` can be rewritten
              // on a visit that already has content (the re-arming paths named
              // in `icd-decisions.ts`), which turns yesterday's auto-accepted
              // code into today's orphan. Telling a doctor they decided
              // something they never saw is the wrong-field harm, not the
              // absent-field one — so the sentence follows the provenance.
              <p className="qm-icd-row-note">
                {projection.decisions[code]?.auto
                  ? 'This code was accepted automatically at signing, and the suggester no longer proposes it for this note.'
                  : 'You decided this code, and the suggester no longer proposes it for this note.'}
              </p>,
            ),
          ),
        )}

      {/* THE AMBER RULE — owner-decided, #149(c): SHOW, never hide. Read-only
          by construction: no action is offered, so a dropped code can never be
          accepted. 64 production rejections exist and no doctor has seen one. */}
      {drops.length > 0 &&
        section(
          'Suggested but not carried',
          drops.length,
          drops.map((d) =>
            ledgerRow(
              d.code,
              'not-carried',
              <p
                className="qm-icd-row-note"
                // `--rounds-em-text`, never `--rounds-em` — the fill token
                // fails AA as text and the row's tint is where it belongs.
                style={{ color: 'var(--rounds-em-text)' }}
              >
                {AMBER_DROP_LABEL}
              </p>,
              `icd-drop-${d.code}`,
            ),
          ),
        )}

      </div>

      {/* The frames' caption, below the card, in their own words. It is the one
          place the surface names quantities rather than showing them, so both
          numbers are COMPUTED from the projection — never written down. */}
      <p className="qm-icd-ledger-caption" data-testid="icd-ledger-caption">
        Suggestions are validated against this build’s verified ICD-10-CM set. The physician makes
        the final coding decision.
      </p>
    </div>
  );
}
