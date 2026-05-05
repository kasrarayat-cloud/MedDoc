'use client';

// ============================================================================
// CodingRail — Phase 5.2 right-rail Coding Coach
// ----------------------------------------------------------------------------
// Mockup: docs/design-directions-v10-soap/soap-v6.html (lines 270-580 + body
//        910-1113). The right column of the SOAP page.
//
// Composition (top → bottom):
//   1. <head> — Billing support pulse + "AMA 2021" + suggested code +
//      level pill + override dropdown
//   2. <EmTimeTracker> — visit-time meter w/ AMA threshold band
//   3. <EmCheckList> — 3 criterion groups (history / exam / mdm)
//   4. <coach-cta> — sage primary "Bump to 99214 · +$32" + sage outline
//      "Confirm 99213 · sign" + foot meta
//   5. <BumpModal> — opens above the rail when CTA is clicked
//
// Behavior contract (spec §4):
//   - Server-rendered initial score from page.tsx — preserved as `emScore` prop
//   - Re-scoring on edit: 500ms debounced listener for `qm:soap-edited`,
//     POSTs to `/api/visits/[id]/em-score`, swaps state with `qm-lin-fade-in`
//   - Optimistic UI on EmCriterion warn → applying state with subtle pulse
//   - Loading state: subtle pulse on stale score; never blank
//   - Error state: small mono pill "Coding feedback temporarily unavailable",
//     never red, never blocking — keeps last known good score
//   - readonly visits → no override, no Bump CTA, no Modal mount
//
// Direct prop coupling (replaces the orphan window-event contract from
// the original Phase 5.2 standalone build — see em-coding-ui/types.ts
// header for the removal context):
//   - SOAP edits → parent passes `currentSoapText`; the rail's
//     useEffect debounces and calls POST /em-score itself.
//   - Highlight gap criteria → `onHighlightCriteria(criterionIds)`
//     bubbles up to the parent, which sets `highlightedSections`
//     state on <SoapBody>.
//   - Override → `onApplyOverride(code, reason?)` resolves to
//     `{ ok, error?, newScore? }`; the rail updates `score` on
//     success + surfaces a real toast on failure.
// ============================================================================

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from 'react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import {
  type EmCode,
  type EmScore,
  type EmVisitType,
} from '@/lib/em-coding-ui/types';
import { ANNUAL_SAVINGS_FOOTER, formatDelta } from '@/lib/em-coding-ui/revenueDelta';

import { EmCheckList } from './EmCheckList';
import { EmTimeTracker } from './EmTimeTracker';
import { BumpCtaButton } from './BumpCtaButton';
import { BumpModal } from './BumpModal';

// Code lists per AMA 2021 (rubric §1) — drive the override listbox.
const ESTABLISHED_CODES: EmCode[] = ['99211', '99212', '99213', '99214', '99215'];
const NEW_CODES: EmCode[] = ['99202', '99203', '99204', '99205'];

const RESCORE_DEBOUNCE_MS = 500;

interface CodingRailProps {
  /** Server-computed initial score from page.tsx. */
  emScore: EmScore;
  /** Visit id used for re-score POSTs + override persistence. */
  visitId: string;
  /** Signed visits are coaching-only — readonly disables override + bump CTA. */
  readonly: boolean;
  /**
   * Latest SOAP markdown body, supplied by the parent SoapEditor each
   * render. The rail watches this prop, debounces, and POSTs to
   * /em-score for a fresh score on every meaningful edit. Replaces
   * the orphan SOAP_EDITED_EVENT window-event contract.
   *
   * Optional — when undefined the rail simply skips the auto-rescore
   * loop and stays on the server-supplied initial score.
   */
  currentSoapText?: string;
  /** Fired when the doctor accepts a bump suggestion via the modal. */
  onBumpAccepted?: (toCode: EmCode) => void;
  /**
   * Persists SOAP additions when the doctor accepts a bump suggestion.
   * Wired to POST /api/visits/[id]/em-score/apply-additions by the
   * parent (soap-editor.tsx). When the response carries a `newScore`,
   * the rail re-renders with the bumped code.
   */
  onApplyAdditions?: (
    additions: Array<{ criterionId: string; text: string }>
  ) => Promise<{ ok: boolean; error?: string; newScore?: EmScore }>;
  /**
   * Persists a doctor-set CPT override. Wired to
   * POST /api/visits/[id]/em-score/override by the parent. Returning
   * `{ ok: true, newScore }` causes the rail to re-render with the
   * doctor-set code. Returning `{ ok: false, error }` surfaces a real
   * error toast and the rail keeps its prior score (no silent drop —
   * this is the post-fix behaviour for QA-report finding F-01).
   */
  onApplyOverride?: (
    code: EmCode,
    reason?: string
  ) => Promise<{ ok: boolean; error?: string; newScore?: EmScore }>;
  /**
   * Asks the parent to highlight the SOAP sections that contain the
   * given gap criterion ids — typically called when the doctor clicks
   * the bump CTA so the eye is drawn to the right S/O/A/P block.
   * Optional — sections silently don't pulse when the parent doesn't
   * supply a handler.
   */
  onHighlightCriteria?: (criterionIds: string[]) => void;
  /**
   * Fired when the doctor clicks "Confirm <code> · sign". Parent
   * opens its lifted SignAndSendModal (controlled-open mode). When
   * undefined, the button is hidden — there's no fallback signing
   * path inside the rail.
   */
  onConfirmSign?: () => void;
}

interface RescoreResult {
  ok: boolean;
  score?: EmScore;
  error?: string;
}

export function CodingRail({
  emScore: initialScore,
  visitId,
  readonly,
  currentSoapText,
  onBumpAccepted,
  onApplyAdditions,
  onApplyOverride,
  onHighlightCriteria,
  onConfirmSign,
}: CodingRailProps) {
  // Last known-good server score; fall back here on rescoring failures.
  const [score, setScore] = useState<EmScore>(initialScore);
  // Stale flag triggers the sage subtle pulse during rescoring.
  const [stale, setStale] = useState(false);
  // Soft error pill ("Coding feedback temporarily unavailable") — never red.
  const [unavailable, setUnavailable] = useState(false);
  // BumpModal open state.
  const [bumpOpen, setBumpOpen] = useState(false);
  // Override dropdown open state — uncontrolled UX, listbox closes on select.
  const [overrideOpen, setOverrideOpen] = useState(false);

  const debounceRef = useRef<number | null>(null);
  const inflightRef = useRef<AbortController | null>(null);
  // Skip the rescore loop on the very first render — the score from
  // the server already reflects the initial SOAP body. This prevents
  // a redundant POST on every page load.
  const lastRescoredTextRef = useRef<string | null>(null);

  // Reflect prop changes when the parent server-rerenders with a new score
  // (e.g. after page-level revalidatePath). Keeps the rail in sync without
  // tearing the local stale flag.
  useEffect(() => {
    setScore(initialScore);
    setStale(false);
    setUnavailable(false);
  }, [initialScore]);

  // ---------------------------------------------------------------------------
  // Re-score on SOAP edits (debounced 500 ms)
  // ---------------------------------------------------------------------------
  const rescore = useCallback(
    async (soapText: string) => {
      // Cancel any inflight request — we only care about the latest body.
      if (inflightRef.current) {
        inflightRef.current.abort();
      }
      const controller = new AbortController();
      inflightRef.current = controller;
      setStale(true);
      try {
        const res = await fetch(`/api/visits/${visitId}/em-score`, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ soapText }),
          signal: controller.signal,
        });
        if (!res.ok) {
          throw new Error(`em-score returned ${res.status}`);
        }
        const result = (await res.json()) as RescoreResult;
        if (result.ok && result.score) {
          setScore(result.score);
          setUnavailable(false);
        } else {
          // Soft-fail — keep last good score.
          setUnavailable(true);
        }
      } catch (err) {
        if ((err as Error).name === 'AbortError') return;
        // Network / 5xx — keep the last known good score.
        setUnavailable(true);
      } finally {
        if (inflightRef.current === controller) {
          inflightRef.current = null;
        }
        setStale(false);
      }
    },
    [visitId]
  );

  // Watch the parent-supplied SOAP text and debounce-rescore on change.
  // The first render seeds the ref so we don't re-fetch a score the
  // server has already produced. Subsequent prop changes (the doctor
  // typed in <SoapInlineEdit>, parent persisted via saveSoapDraftAction
  // and re-rendered with the new text) trigger the debounced POST.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (currentSoapText === undefined) return;

    if (lastRescoredTextRef.current === null) {
      // Initial seed — the server-rendered score already reflects this
      // text, so suppress the first-render rescore.
      lastRescoredTextRef.current = currentSoapText;
      return;
    }
    if (currentSoapText === lastRescoredTextRef.current) return;
    lastRescoredTextRef.current = currentSoapText;

    if (debounceRef.current !== null) {
      window.clearTimeout(debounceRef.current);
    }
    const textForRescore = currentSoapText;
    debounceRef.current = window.setTimeout(() => {
      debounceRef.current = null;
      void rescore(textForRescore);
    }, RESCORE_DEBOUNCE_MS);

    return () => {
      if (debounceRef.current !== null) {
        window.clearTimeout(debounceRef.current);
        debounceRef.current = null;
      }
    };
  }, [currentSoapText, rescore]);

  // Cancel any inflight request on unmount.
  useEffect(() => {
    return () => {
      if (inflightRef.current) {
        inflightRef.current.abort();
        inflightRef.current = null;
      }
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Override dropdown
  // ---------------------------------------------------------------------------
  const overrideOptions = useMemo<EmCode[]>(
    () => (score.visitType === 'new' ? NEW_CODES : ESTABLISHED_CODES),
    [score.visitType]
  );

  const handleOverrideSelect = useCallback(
    async (code: EmCode) => {
      setOverrideOpen(false);
      if (!onApplyOverride) {
        // No persistence handler wired — refuse silently rather than
        // surface a "success" toast for a dropped click. The rail
        // dropdown is hidden in readonly mode, so reaching this branch
        // in production indicates a parent-wiring bug, not a doctor-
        // facing flow.
        toast.error('Override is not wired — reload or contact support.');
        return;
      }
      const result = await onApplyOverride(code);
      if (!result.ok) {
        toast.error(result.error ?? 'Override failed — try again.');
        return;
      }
      if (result.newScore) {
        setScore(result.newScore);
        setStale(false);
        setUnavailable(false);
      }
      toast.success(`Override applied — ${code}`, {
        description: 'Doctor-set code persisted to the audit trail.',
      });
    },
    [onApplyOverride]
  );

  // ---------------------------------------------------------------------------
  // Bump CTA click → open modal + emit highlight event
  // ---------------------------------------------------------------------------
  const handleBumpClick = useCallback(() => {
    setBumpOpen(true);
  }, []);

  const handleApplyAdditions = useCallback(
    async (additions: Array<{ criterionId: string; text: string }>) => {
      // Phase 5.2 stub completion — the parent (soap-editor.tsx) wires
      // onApplyAdditions to POST /api/visits/[id]/em-score/apply-
      // additions. The route returns the new UI EmScore so the rail
      // re-renders with the bumped code without a full page reload.
      // When the prop is unwired (e.g. unit tests), the modal still
      // sees an error and stays open — no more silent "pretend success"
      // fallback (that was the bug we shipped this PR to fix).
      if (!onApplyAdditions) {
        return {
          ok: false,
          error:
            'Apply path is not wired. Reload the page or contact support.',
        };
      }
      const result = await onApplyAdditions(additions);
      if (result.ok) {
        if (result.newScore) {
          // Server-derived new score includes the post-merge code +
          // groups + bump suggestion. Updating local state here means
          // the rail flips from 99213 → 99214 (or whatever the new
          // tier is) the moment the modal closes.
          setScore(result.newScore);
          setStale(false);
          setUnavailable(false);
        }
        if (score.bump) onBumpAccepted?.(score.bump.toCode);
      }
      return result;
    },
    [onApplyAdditions, onBumpAccepted, score.bump]
  );

  // ---------------------------------------------------------------------------
  // Display helpers
  // ---------------------------------------------------------------------------
  const displayedCode: EmCode = score.override?.code ?? score.suggestedCode;
  const isOverridden = Boolean(score.override?.code);
  const levelLabel = useMemo(() => deriveLevelLabel(displayedCode), [displayedCode]);

  // The bump CTA + confirm-secondary mirror exactly the v6 mockup. When the
  // bump.gaps array is empty (already at next level), the primary turns into
  // a "Confirm 99214 · sign" outline (mode: 'confirm-bump') — but signing is
  // owned by the existing Sign & Send flow (UNTOUCHED). The CTA only invites
  // the doctor to switch their code; the actual sign is its own button.
  const showBump =
    !readonly &&
    score.bump &&
    score.bump.mode === 'almost-there' &&
    score.bump.gaps.length > 0;

  return (
    <aside
      className={cn(
        'qm-lin-coding-rail',
        stale && 'qm-lin-coding-rail--stale',
        readonly && 'qm-lin-coding-rail--readonly'
      )}
      aria-label="Billing support"
    >
      {/* ── Head ─────────────────────────────────────────────────────────── */}
      <header className="qm-lin-coding-rail-head">
        <div className="qm-lin-coding-rail-head-top">
          <span className="qm-lin-coding-rail-label qm-lin-coding-rail-label--coach">
            <span className="qm-lin-coding-rail-pulse" aria-hidden="true" />
            Billing support
          </span>
          <span className="qm-lin-coding-rail-label">AMA 2021</span>
        </div>
        <div className="qm-lin-coding-rail-code-row">
          <span className="qm-lin-coding-code" aria-live="polite">
            {displayedCode}
          </span>
          <span className="qm-lin-coding-level">{levelLabel}</span>
          {isOverridden ? (
            <span
              className="qm-lin-coding-override-badge"
              title={
                score.override?.reason
                  ? `Doctor override: ${score.override.reason}`
                  : 'Doctor-set code'
              }
            >
              doctor-set
            </span>
          ) : null}
          {readonly ? null : (
            <div className="qm-lin-coding-override-wrap">
              <button
                type="button"
                className="qm-lin-coding-override"
                aria-haspopup="listbox"
                aria-expanded={overrideOpen}
                onClick={() => setOverrideOpen((v) => !v)}
              >
                <span>override</span>
                <span className="qm-lin-coding-override-caret" aria-hidden="true">
                  {overrideOpen ? '▴' : '▾'}
                </span>
              </button>
              {overrideOpen ? (
                <ul
                  className="qm-lin-coding-override-listbox"
                  role="listbox"
                  aria-label="Override CPT code"
                >
                  {overrideOptions.map((code) => (
                    <li
                      key={code}
                      role="option"
                      aria-selected={code === displayedCode}
                      className={cn(
                        'qm-lin-coding-override-option',
                        code === displayedCode &&
                          'qm-lin-coding-override-option--current'
                      )}
                    >
                      <button
                        type="button"
                        onClick={() => handleOverrideSelect(code)}
                      >
                        {code}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          )}
        </div>
      </header>

      {/* ── Time tracker ─────────────────────────────────────────────────── */}
      <EmTimeTracker
        visitTimeSec={score.visitTimeSec}
        estimatedTotalSec={score.estimatedTotalSec}
        thresholdBand={score.timeBand}
      />

      {/* ── Checklist (3 groups) ─────────────────────────────────────────── */}
      <div className={cn(stale && 'qm-lin-coding-rail-fade')}>
        <EmCheckList groups={score.groups} />
      </div>

      {/* ── Soft error pill (never red, never blocking) ──────────────────── */}
      {unavailable ? (
        <div className="qm-lin-coding-rail-error" role="status">
          Coding feedback temporarily unavailable
        </div>
      ) : null}

      {/* ── CTA block ────────────────────────────────────────────────────── */}
      {readonly ? null : (
        <div className="qm-lin-coding-cta">
          {showBump && score.bump ? (
            <BumpCtaButton
              current={displayedCode}
              bumpTo={score.bump.toCode}
              revenueDelta={score.bump.revenueDelta}
              gaps={score.bump.gaps.map((g) => g.label)}
              gapCriterionIds={score.bump.gaps.map((g) => g.criterionId)}
              onClick={handleBumpClick}
              onHighlight={onHighlightCriteria}
              disabled={readonly}
            />
          ) : null}
          {/* Phase 5.2 stub completion — confirm-sign now calls the
              `onConfirmSign` prop which the parent wires to its lifted
              SignAndSendModal open state. Pre-fix this dispatched a
              `qm:request-sign` window event that had no listener (the
              integration was deferred to "Subagent B's merge" that
              never landed). When the prop is missing the button is
              hidden — there is no fallback signing path inside the
              rail. */}
          {onConfirmSign ? (
          <button
            type="button"
            className="qm-lin-coding-confirm"
            onClick={() => onConfirmSign()}
            disabled={readonly}
            title={
              readonly
                ? 'This visit is read-only.'
                : undefined
            }
          >
            <span className="qm-lin-coding-confirm-label">
              <span className="qm-lin-coding-confirm-check" aria-hidden="true">
                ✓
              </span>
              <span>Confirm {displayedCode} · sign</span>
            </span>
            <span className="qm-lin-coding-confirm-shortcut" aria-hidden="true">
              ⌘ ↵
            </span>
          </button>
          ) : null}
          <div className="qm-lin-coding-cta-foot">
            <span className="qm-lin-coding-cta-foot-ama">
              AMA 2021 · time-based
            </span>
            <span>{ANNUAL_SAVINGS_FOOTER}</span>
          </div>
          {score.bump && score.bump.gaps.length > 0 ? (
            <div className="qm-lin-coding-cta-foot qm-lin-coding-cta-foot--gap">
              <span>
                {displayedCode} supports · {score.bump.gaps.length} gap
                {score.bump.gaps.length === 1 ? '' : 's'} to {score.bump.toCode}
              </span>
              <span>{formatDelta(score.bump.revenueDelta)}</span>
            </div>
          ) : null}
        </div>
      )}

      {/* ── Modal ────────────────────────────────────────────────────────── */}
      {!readonly && score.bump && score.bump.gaps.length > 0 ? (
        <BumpModal
          open={bumpOpen}
          current={displayedCode}
          suggestion={score.bump}
          visitId={visitId}
          onClose={() => setBumpOpen(false)}
          onApply={handleApplyAdditions}
        />
      ) : null}
    </aside>
  );
}

// ----------------------------------------------------------------------------
// Helpers
// ----------------------------------------------------------------------------

function deriveLevelLabel(code: EmCode): string {
  // Last digit of the CPT maps directly to the level (1..5).
  const level = code.slice(-1);
  return `Level ${level}`;
}

// Re-export the visit-type alias so consumer pages can stay narrow.
export type { EmVisitType };
