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
//   • the manual code override as a calm SECONDARY control
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
// The card shows the server level at load + on override.
// ============================================================================

import { useState } from 'react';
import { toast } from 'sonner';

import { EmCheckList } from '@/components/visits/EmCheckList';
import { EmTimeTracker } from '@/components/visits/EmTimeTracker';
import type { EmCode, EmScore } from '@/lib/em-coding-ui/types';

const ESTABLISHED_CODES: EmCode[] = ['99211', '99212', '99213', '99214', '99215'];
const NEW_CODES: EmCode[] = ['99202', '99203', '99204', '99205'];

const MDM_LABEL: Record<EmScore['mdmTier'], string> = {
  straightforward: 'straightforward complexity',
  low: 'low complexity',
  moderate: 'moderate complexity',
  high: 'high complexity',
};

export function BillingCardC3({
  initialScore,
  visitId,
  readonly,
  emPendingChange,
  notApplicable,
}: {
  initialScore: EmScore | null;
  visitId: string;
  readonly: boolean;
  /** E/M confirm gate signal (codes only). When set, surface — never block;
   *  the actual fail-closed enforcement stays in <SignAndSendModal>. */
  emPendingChange: { from: string; to: string } | null;
  /** Ultrasound (flag-gated) — an IMAGING REPORT has no office-visit E/M
   *  level. Render an explicit "not applicable" note rather than a coding
   *  score (the pipeline already skips L7b CPT/E&M for these). */
  notApplicable?: boolean;
}) {
  const [score, setScore] = useState<EmScore | null>(initialScore);
  const [overriding, setOverriding] = useState(false);

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
  const overrideOptions = score.visitType === 'new' ? NEW_CODES : ESTABLISHED_CODES;

  const applyOverride = async (code: EmCode) => {
    if (code === displayedCode || overriding) return;
    setOverriding(true);
    try {
      const res = await fetch(`/api/visits/${visitId}/em-score/override`, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ overrideToCode: code }),
      });
      if (!res.ok) {
        const body = (await res.json().catch(() => ({}))) as { error?: string };
        toast.error(body.error ?? `Couldn't set ${code} — try again.`);
        return;
      }
      const data = (await res.json()) as { ok: boolean; newScore?: EmScore };
      if (data.ok && data.newScore) setScore(data.newScore);
      toast.success(`Code set to ${code}`, {
        description: 'Doctor-set code saved to the audit trail.',
      });
    } catch {
      toast.error('Network error setting the code — try again.');
    } finally {
      setOverriding(false);
    }
  };

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

      {!readonly && (
        <div className="qm-c3-bill-override">
          <label className="qm-c3-bill-override-label" htmlFor={`bill-ovr-${visitId}`}>
            Set a different code
          </label>
          <select
            id={`bill-ovr-${visitId}`}
            className="qm-c3-bill-override-select"
            value={displayedCode}
            disabled={overriding}
            onChange={(e) => applyOverride(e.target.value as EmCode)}
          >
            {overrideOptions.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
