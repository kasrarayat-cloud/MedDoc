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

  const card = (code: string, body: React.ReactNode) => (
    <div
      key={code}
      data-testid={`icd-card-${code}`}
      data-code={code}
      className="mb-2 rounded-lg px-3 py-2.5"
      style={{
        background: 'var(--rounds-surface-1)',
        border: '1px solid var(--rounds-line-1)',
      }}
    >
      {body}
    </div>
  );

  const codeLine = (code: string) => {
    const d = detail[code];
    return (
      <>
        <div className="flex items-baseline gap-2">
          <span
            className="font-mono text-[14px] font-semibold"
            style={{ color: 'var(--rounds-text-1)' }}
          >
            {code}
          </span>
          {d?.description ? (
            <span className="text-[13px]" style={{ color: 'var(--rounds-text-2)' }}>
              {d.description}
            </span>
          ) : null}
          {typeof d?.confidence === 'number' ? (
            <span
              className="ml-auto text-[12px] tabular-nums"
              // `--rounds-ready-text`, never `--rounds-ready`: the design
              // contract measures the fill token at 3.392:1 / 3.233:1 / 2.661:1
              // and it FAILS AA as text. The `-text` variant exists for this.
              style={{ color: 'var(--rounds-ready-text)' }}
            >
              {Math.round(d.confidence * (d.confidence <= 1 ? 100 : 1))}%
            </span>
          ) : null}
        </div>
        {d?.evidenceQuote ? (
          <p
            className="mt-1 text-[12px] italic"
            style={{ color: 'var(--rounds-text-3)' }}
            data-testid={`icd-evidence-${code}`}
          >
            “{d.evidenceQuote}”
          </p>
        ) : null}
      </>
    );
  };

  const section = (title: string, count: number, children: React.ReactNode) => (
    <section className="mb-5" data-testid={`icd-section-${title.toLowerCase().replace(/\s+/g, '-')}`}>
      <h3 className={`${kicker} mb-2`} style={{ color: 'var(--rounds-text-3)' }}>
        {title} · {count}
      </h3>
      {children}
    </section>
  );

  return (
    <div className="w-full" data-testid="icd-coding-view">
      <div
        className="mb-4 text-[13px]"
        style={{ color: 'var(--rounds-text-2)' }}
        data-testid="icd-summary-chip"
      >
        <strong style={{ color: 'var(--rounds-text-1)' }}>{summary.suggested}</strong> suggested ·{' '}
        <strong style={{ color: 'var(--rounds-text-1)' }}>{summary.accepted}</strong> accepted ·{' '}
        <strong style={{ color: 'var(--rounds-text-1)' }}>{summary.needsReview}</strong> needs review
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
          style={{ color: 'var(--rounds-signed-text)' }}
        >
          This visit is signed — coding decisions are frozen.
        </p>
      ) : null}

      {projection.suggested.length === 0 ? (
        <p className="text-[13px]" style={{ color: 'var(--rounds-text-3)' }} data-testid="icd-empty">
          The suggester proposed no codes for this note.
        </p>
      ) : null}

      {projection.undecided.length > 0 &&
        section(
          'Needs review',
          projection.undecided.length,
          projection.undecided.map((code) =>
            card(
              code,
              <>
                {codeLine(code)}
                {!props.readonly ? (
                  rejecting === code ? (
                    <div className="mt-2" data-testid={`icd-reason-picker-${code}`}>
                      <p className={kicker} style={{ color: 'var(--rounds-text-3)' }}>
                        Why is this code wrong?
                      </p>
                      <div className="mt-1.5 flex flex-wrap gap-1.5">
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
                    </div>
                  ) : (
                    <div className="mt-2 flex gap-2">
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
                ) : null}
              </>,
            ),
          ),
        )}

      {projection.accepted.length > 0 &&
        section(
          'Accepted',
          projection.accepted.length,
          projection.accepted.map((code) =>
            card(
              code,
              <>
                {codeLine(code)}
                {!props.readonly ? (
                  <button
                    type="button"
                    data-testid={`icd-undo-${code}`}
                    disabled={pending !== null}
                    onClick={() => void send(code, 'cleared')}
                    className="mt-2 rounded-md px-2.5 py-1 text-[12px]"
                    style={{
                      border: '1px solid var(--rounds-line-2)',
                      color: 'var(--rounds-text-2)',
                    }}
                  >
                    Undo
                  </button>
                ) : null}
              </>,
            ),
          ),
        )}

      {projection.rejected.length > 0 &&
        section(
          'Rejected',
          projection.rejected.length,
          projection.rejected.map((code) =>
            card(
              code,
              <>
                {codeLine(code)}
                <p
                  className="mt-1 text-[12px]"
                  data-testid={`icd-rejected-reason-${code}`}
                  style={{ color: 'var(--rounds-signed-text)' }}
                >
                  {/* The stored token, rendered through the label map. The
                      column holds the token; the prose lives in this file. */}
                  {projection.decisions[code]?.reason
                    ? REJECTION_REASON_LABEL[projection.decisions[code].reason!]
                    : null}
                </p>
                {!props.readonly ? (
                  <button
                    type="button"
                    data-testid={`icd-undo-${code}`}
                    disabled={pending !== null}
                    onClick={() => void send(code, 'cleared')}
                    className="mt-2 rounded-md px-2.5 py-1 text-[12px]"
                    style={{
                      border: '1px solid var(--rounds-line-2)',
                      color: 'var(--rounds-text-2)',
                    }}
                  >
                    Undo
                  </button>
                ) : null}
              </>,
            ),
          ),
        )}

      {/* ⚠️ ORPHANED IS SURFACED AND IS NOBODY'S DEFAULT.
          A decision whose code is no longer suggested is neither accepted nor
          undecided — it is a decision about a code this note no longer carries.
          It must not flow into the record and must not be silently discarded
          either, because the doctor made it. UNREACHABLE TODAY by measurement
          (`icdCodes` has one writer and `layer-skip.ts:101` skips L7a whenever
          it has content), kept because it costs nothing while the path is shut
          and because its absence would be invisible if the path re-opened. */}
      {projection.orphaned.length > 0 &&
        section(
          'No longer suggested',
          projection.orphaned.length,
          projection.orphaned.map((code) =>
            card(
              code,
              <>
                <span
                  className="font-mono text-[14px] font-semibold"
                  style={{ color: 'var(--rounds-text-1)' }}
                >
                  {code}
                </span>
                <p className="mt-1 text-[12px]" style={{ color: 'var(--rounds-text-3)' }}>
                  You decided this code, and the suggester no longer proposes it for this note.
                </p>
              </>,
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
          drops.map((d) => (
            <div
              key={d.code}
              data-testid={`icd-drop-${d.code}`}
              className="mb-2 rounded-lg px-3 py-2.5"
              style={{
                background: 'var(--rounds-surface-1)',
                border: '1px solid var(--rounds-em)',
              }}
            >
              <span
                className="font-mono text-[14px] font-semibold"
                style={{ color: 'var(--rounds-text-1)' }}
              >
                {d.code}
              </span>
              <p
                className="mt-1 text-[12px]"
                // `--rounds-em-text`, never `--rounds-em` — the fill token
                // fails AA as text and the border above is where it belongs.
                style={{ color: 'var(--rounds-em-text)' }}
              >
                {AMBER_DROP_LABEL}
              </p>
            </div>
          )),
        )}

      <p className="mt-6 text-[12px]" style={{ color: 'var(--rounds-text-3)' }}>
        Suggestions are validated against this build’s verified ICD-10-CM set. The physician makes
        the final coding decision.
      </p>
    </div>
  );
}
