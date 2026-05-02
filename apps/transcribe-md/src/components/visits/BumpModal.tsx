'use client';

// ============================================================================
// BumpModal — 3-step "Apply additions & re-score" modal
// ----------------------------------------------------------------------------
// Mirrors `.modal-backdrop` + `.modal` (soap-v6.html lines 581-660 + body
// 1119-1140) AND extends the spec §4.3 contract:
//
//   Step 1 — What's missing
//     Renders each gap with the AMA-criterion language verbatim so the
//     doctor sees exactly which 99214 criterion is unmet.
//
//   Step 2 — Auto-suggestion
//     Shows pre-filled SOAP additions per gap (e.g. for missing PFSH:
//     "Family hx: HTN, mother. Lives with husband + 6yo son."). Each is
//     editable inline before applying.
//
//   Step 3 — Confirm
//     Doctor reviews the staged edits. "Apply & save" persists via the
//     existing `saveSoapDraftAction` server action — the modal mutates
//     the SOAP body the parent rail listens to (`qm:soap-edited`),
//     triggering an immediate re-score.
//
// HONORED contracts:
//   - prefers-reduced-motion: reduce → no slide-in (CSS handles this)
//   - Sign & Send is UNTOUCHED — the modal NEVER signs; it only stages
//     SOAP additions and surfaces them to the doctor.
//   - When backend wiring is incomplete (Subagent B's branch owns the
//     `/api/visits/[id]/em-score` endpoint), `onApply` returns a stub
//     OK and the rail performs an optimistic re-render.
// ============================================================================

import { useCallback, useEffect, useState } from 'react';
import { cn } from '@/lib/cn';
import type { BumpSuggestion, EmCode } from '@/lib/em-coding-ui/types';
import { formatDelta } from '@/lib/em-coding-ui/revenueDelta';

type ModalStep = 1 | 2 | 3;

interface BumpModalProps {
  /** Whether the modal is mounted + visible. */
  open: boolean;
  /** Currently suggested code (the "from" half of the bump). */
  current: EmCode;
  /** The bump suggestion payload from EmScore. */
  suggestion: BumpSuggestion;
  /** Visit id — passed to `onApply` for the save action. */
  visitId: string;
  /** Close handler — fired on ESC, backdrop click, or "Not now". */
  onClose: () => void;
  /**
   * Fired when the doctor clicks "Apply & save". Receives the array of
   * additions the doctor edited inline. Resolved promise → modal closes
   * + parent re-scores. Rejected promise → modal stays open with error.
   */
  onApply: (
    additions: Array<{ criterionId: string; text: string }>
  ) => Promise<{ ok: boolean; error?: string }>;
}

export function BumpModal({
  open,
  current,
  suggestion,
  onClose,
  onApply,
}: BumpModalProps) {
  const [step, setStep] = useState<ModalStep>(1);
  // Editable copies of the auto-suggestion strings — keyed by criterion id.
  const [additions, setAdditions] = useState<Record<string, string>>(() => {
    const seed: Record<string, string> = {};
    for (const gap of suggestion.gaps) {
      seed[gap.criterionId] = gap.suggestion;
    }
    return seed;
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset state whenever the modal is re-opened with a new suggestion.
  useEffect(() => {
    if (open) {
      setStep(1);
      setError(null);
      const seed: Record<string, string> = {};
      for (const gap of suggestion.gaps) {
        seed[gap.criterionId] = gap.suggestion;
      }
      setAdditions(seed);
    }
  }, [open, suggestion]);

  // ESC closes the modal (when not submitting).
  useEffect(() => {
    if (!open) return;
    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !submitting) {
        onClose();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, submitting, onClose]);

  const handleNext = useCallback(() => {
    setStep((s) => (s < 3 ? ((s + 1) as ModalStep) : s));
  }, []);

  const handleBack = useCallback(() => {
    setStep((s) => (s > 1 ? ((s - 1) as ModalStep) : s));
  }, []);

  const handleApply = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      const payload = suggestion.gaps.map((gap) => ({
        criterionId: gap.criterionId,
        text: additions[gap.criterionId] ?? gap.suggestion,
      }));
      const result = await onApply(payload);
      if (result.ok) {
        onClose();
      } else {
        setError(result.error ?? 'Apply failed. Try again.');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Apply failed. Try again.');
    } finally {
      setSubmitting(false);
    }
  }, [suggestion.gaps, additions, onApply, onClose]);

  if (!open) return null;

  const gapCount = suggestion.gaps.length;
  const subTitle = `${gapCount} quick add${gapCount === 1 ? '' : 's'} · ~30 sec · ${formatDelta(suggestion.revenueDelta)}`;

  return (
    <div
      className="qm-lin-bump-modal-backdrop"
      role="presentation"
      onClick={(event) => {
        if (event.target === event.currentTarget && !submitting) onClose();
      }}
    >
      <div
        className="qm-lin-bump-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="qm-lin-bump-modal-ttl"
        aria-describedby="qm-lin-bump-modal-sub"
      >
        <h4 id="qm-lin-bump-modal-ttl" className="qm-lin-bump-modal-title">
          Bump {current} → {suggestion.toCode}
        </h4>
        <div id="qm-lin-bump-modal-sub" className="qm-lin-bump-modal-sub">
          {subTitle}
        </div>

        <ol className="qm-lin-bump-modal-steps" aria-label="Apply steps">
          {/* Step 1 — What's missing */}
          <li
            className={cn(
              'qm-lin-bump-modal-step',
              step === 1 && 'qm-lin-bump-modal-step--active'
            )}
          >
            <span className="qm-lin-bump-modal-step-num">01</span>
            <div className="qm-lin-bump-modal-step-body">
              <strong>What&rsquo;s missing</strong>
              <ul className="qm-lin-bump-modal-gap-list">
                {suggestion.gaps.map((gap) => (
                  <li key={gap.criterionId}>{gap.label}</li>
                ))}
              </ul>
            </div>
          </li>

          {/* Step 2 — Auto-suggestion (editable) */}
          <li
            className={cn(
              'qm-lin-bump-modal-step',
              step === 2 && 'qm-lin-bump-modal-step--active'
            )}
          >
            <span className="qm-lin-bump-modal-step-num">02</span>
            <div className="qm-lin-bump-modal-step-body">
              <strong>Suggested additions</strong>
              <div className="qm-lin-bump-modal-suggestions">
                {suggestion.gaps.map((gap) => (
                  <label
                    key={gap.criterionId}
                    className="qm-lin-bump-modal-suggestion"
                  >
                    <span className="qm-lin-bump-modal-suggestion-label">
                      {gap.label}
                    </span>
                    <textarea
                      className="qm-lin-bump-modal-suggestion-input"
                      rows={2}
                      value={additions[gap.criterionId] ?? ''}
                      disabled={submitting || step !== 2}
                      onChange={(event) =>
                        setAdditions((prev) => ({
                          ...prev,
                          [gap.criterionId]: event.target.value,
                        }))
                      }
                    />
                  </label>
                ))}
              </div>
            </div>
          </li>

          {/* Step 3 — Confirm */}
          <li
            className={cn(
              'qm-lin-bump-modal-step',
              step === 3 && 'qm-lin-bump-modal-step--active'
            )}
          >
            <span className="qm-lin-bump-modal-step-num">03</span>
            <div className="qm-lin-bump-modal-step-body">
              <strong>Auto-recheck.</strong> Coach will re-evaluate criteria
              and confirm {suggestion.toCode} once additions are saved.
            </div>
          </li>
        </ol>

        {error ? (
          <div className="qm-lin-bump-modal-error" role="alert">
            {error}
          </div>
        ) : null}

        <div className="qm-lin-bump-modal-actions">
          <button
            type="button"
            className="qm-lin-bump-modal-btn-ghost"
            onClick={onClose}
            disabled={submitting}
          >
            Not now
          </button>
          {step > 1 ? (
            <button
              type="button"
              className="qm-lin-bump-modal-btn-ghost"
              onClick={handleBack}
              disabled={submitting}
            >
              Back
            </button>
          ) : null}
          {step < 3 ? (
            <button
              type="button"
              className="qm-lin-bump-modal-btn-prim"
              onClick={handleNext}
              disabled={submitting}
            >
              Next
            </button>
          ) : (
            <button
              type="button"
              className="qm-lin-bump-modal-btn-prim"
              onClick={handleApply}
              disabled={submitting}
            >
              {submitting ? 'Applying…' : 'Apply & save · recheck'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
