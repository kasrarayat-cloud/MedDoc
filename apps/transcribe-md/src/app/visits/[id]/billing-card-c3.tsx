'use client';

// ============================================================================
// BillingCardC3 — the calm E/M coding card for the C3 review drawer.
// ----------------------------------------------------------------------------
// Replaces the dense permanent right-rail (99214 + full AMA-2021 rubric +
// green "Bump +$44" CTA) with ONE quiet card inside the "N to review" drawer:
//   • a plain-language level line ("Supports a level 4 visit, 99214 —
//     established patient, moderate complexity")
//   • a "Why this level?" disclosure holding the full AMA rubric (collapsed)
//   • a NEUTRAL "documentation could also support 99215" line (no dollar
//     figure, no green Bump CTA)
//
// THE OVERRIDE CONTROL IS GONE FROM HERE (2026-07-28). It moved to the gate
// stack on the read-only review page (<EmLevelCard>), which is the product's
// single billing surface now, and that move made the REASON REQUIRED at
// POST /em-score/override. This card's dropdown sent no reason, so every code
// change through it would have 400'd — a control that looks live and cannot
// work. It is not re-created here rather than fabricating a rationale to
// satisfy the route: an audit row's "why" is the doctor's words or nothing.
// This card is reachable only with NEXT_PUBLIC_REVIEW_DOC_VIEW off (its
// documented rollback), and on that path the level is read-only.
//
// SKIN-ONLY: this is PRESENTATION over the SAME server-computed EmScore the
// rail consumed. It reuses the existing <EmTimeTracker> + <EmCheckList>
// verbatim and the existing POST /api/visits/[id]/em-score/override endpoint
// (so the EM_OVERRIDE_APPLIED audit row is unchanged). It does NOT touch the
// E/M scoring engine, the code computation, the sign route, or the E/M
// confirm-before-sign GATE — that gate stays in <SignAndSendModal>
// (emPendingChange) and still fail-closes Sign. The deliberate, compliance-
// motivated omission vs the rail: NO revenue-delta loop and NO rescore-on-edit
// coaching loop — i.e. the upcoding-pressure feedback is intentionally gone.
// The card shows the server level as loaded.
// ============================================================================

import { EmCheckList } from '@/components/visits/EmCheckList';
import { EmTimeTracker } from '@/components/visits/EmTimeTracker';
import type { EmScore } from '@/lib/em-coding-ui/types';


const MDM_LABEL: Record<EmScore['mdmTier'], string> = {
  straightforward: 'straightforward complexity',
  low: 'low complexity',
  moderate: 'moderate complexity',
  high: 'high complexity',
};

export function BillingCardC3({
  initialScore,
  emPendingChange,
  notApplicable,
}: {
  initialScore: EmScore | null;
  /** Kept on the interface, unread since the override control left: the callers
   *  still pass both, and this card is a read-only presentation of the level. */
  visitId?: string;
  readonly?: boolean;
  /** E/M confirm gate signal (codes only). When set, surface — never block;
   *  the actual fail-closed enforcement stays in <SignAndSendModal>. */
  emPendingChange: { from: string; to: string } | null;
  /** Ultrasound (flag-gated) — an IMAGING REPORT has no office-visit E/M
   *  level. Render an explicit "not applicable" note rather than a coding
   *  score (the pipeline already skips L7b CPT/E&M for these). */
  notApplicable?: boolean;
}) {
  // Read-only since the override left: nothing on this card mutates the score.
  const score = initialScore;

  if (notApplicable) {
    return (
      <div className="qm-c3-bill-card">
        <span className="qm-c3-bill-kicker">Billing</span>
        <p className="qm-c3-bill-level" style={{ color: 'var(--color-linear-text-2)' }}>
          E/M coding does not apply to an imaging report. This is a diagnostic
          ultrasound study, not an office visit — code it with the appropriate
          imaging CPT in your billing system.
        </p>
      </div>
    );
  }

  if (!score) {
    return (
      <div className="qm-c3-bill-card">
        <span className="qm-c3-bill-kicker">Billing support</span>
        <p className="qm-c3-bill-level" style={{ color: 'var(--color-linear-text-3)' }}>
          Coding feedback is being computed…
        </p>
      </div>
    );
  }

  const displayedCode = score.override?.code ?? score.suggestedCode;
  const level = Number(displayedCode.slice(-1));
  const patient = score.visitType === 'new' ? 'new' : 'established';

  return (
    <div className="qm-c3-bill-card">
      <span className="qm-c3-bill-kicker">Billing support · AMA 2021</span>

      <p className="qm-c3-bill-level">
        Supports a level {level} visit, <span className="qm-c3-bill-code">{displayedCode}</span> —{' '}
        {patient} patient, {MDM_LABEL[score.mdmTier]}.
        {score.override && (
          <span className="qm-c3-bill-set"> · doctor-set</span>
        )}
      </p>

      {emPendingChange && (
        <p className="qm-c3-bill-pending" role="status">
          The documented level changed to{' '}
          <span className="qm-c3-bill-code">{emPendingChange.to}</span> — you&apos;ll
          confirm it when you sign.
        </p>
      )}

      <details className="qm-c3-bill-details">
        <summary className="qm-c3-bill-why">Why this level?</summary>
        <div className="qm-c3-bill-rubric">
          <EmTimeTracker
            visitTimeSec={score.visitTimeSec}
            estimatedTotalSec={score.estimatedTotalSec}
            thresholdBand={score.timeBand}
          />
          <EmCheckList groups={score.groups} />
          {score.bump && score.bump.toCode !== displayedCode && (
            <div className="qm-c3-bill-next">
              <p className="qm-c3-bill-next-head">
                Documentation could also support{' '}
                <span className="qm-c3-bill-code">{score.bump.toCode}</span> if the
                following were added:
              </p>
              <ul className="qm-c3-bill-next-list">
                {score.bump.gaps.map((g) => (
                  <li key={g.criterionId}>{g.label}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </details>
    </div>
  );
}
