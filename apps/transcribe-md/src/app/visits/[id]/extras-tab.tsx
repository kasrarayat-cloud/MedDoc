'use client';

// ============================================================================
// ExtrasTab — referrals + patient-summary panel.
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Hairline-bordered surface-1 cards on
// the dark canvas. Urgency pills tinted via `.qm-lin-pill--sage` /
// warning / danger. Patient-summary body uses Inter (no serif). The
// `theme` prop is preserved on the public API as a no-op.
// ============================================================================

import { useCallback, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';

type ExtrasTabTheme = 'legacy' | 'clinician';

// ---------------------------------------------------------------------------
// Wire types — mirror Layer 7d + 7e output.
// ---------------------------------------------------------------------------

interface Referral {
  to: string;
  reason: string;
  relevant_history: string;
  urgency: 'routine' | 'urgent' | 'stat';
  evidence_quote: string;
}

export interface ReferralsBlob {
  referrals?: Referral[];
}

interface ExtrasTabProps {
  referrals: unknown;
  patientSummary: string | null;
  /** Grade level recorded by Layer 7e (stashed on confidenceScores). */
  fleschKincaid: number | null;
  flagged: boolean;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: ExtrasTabTheme;
}

const SECTION_LABEL =
  'mb-3 text-[10.5px] font-medium uppercase tracking-[0.07em] font-mono text-linear-text-3';

export function ExtrasTab({
  referrals,
  patientSummary,
  fleschKincaid,
  flagged,
}: ExtrasTabProps) {
  const refBlob = (referrals as ReferralsBlob | null) ?? null;
  const refs = refBlob?.referrals ?? [];

  return (
    <div className="space-y-8">
      <ReferralsSection referrals={refs} />
      <SummarySection
        summary={patientSummary}
        fleschKincaid={fleschKincaid}
        flagged={flagged}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Referrals
// ---------------------------------------------------------------------------

function ReferralsSection({ referrals }: { referrals: Referral[] }) {
  return (
    <section>
      <h3 className={SECTION_LABEL}>Referrals</h3>
      {referrals.length === 0 ? (
        <div className="rounded-lg border border-dashed border-linear-border bg-linear-surface-1 p-6 text-center text-[13px] text-linear-text-3">
          No referrals documented in the plan.
        </div>
      ) : (
        <ul className="space-y-3">
          {referrals.map((r, i) => (
            <ReferralCard key={i} referral={r} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ReferralCard({ referral }: { referral: Referral }) {
  const urgency = {
    routine: { label: 'Routine', cls: 'qm-lin-pill' },
    urgent: {
      label: 'Urgent',
      cls: 'qm-lin-pill bg-linear-warning/15 text-linear-warning',
    },
    stat: {
      label: 'Stat',
      cls: 'qm-lin-pill bg-linear-danger/15 text-linear-danger',
    },
  }[referral.urgency];

  return (
    <li className="rounded-lg border border-linear-border bg-linear-surface-1 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className={SECTION_LABEL.replace('mb-3', '')}>Refer to</div>
          <div className="mt-0.5 text-[16px] font-semibold text-linear-text">
            {referral.to}
          </div>
        </div>
        <span className={urgency.cls}>{urgency.label}</span>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <div className={SECTION_LABEL.replace('mb-3', '')}>Reason</div>
          <p className="mt-1 text-[13px] leading-relaxed text-linear-text-2">
            {referral.reason}
          </p>
        </div>
        <div>
          <div className={SECTION_LABEL.replace('mb-3', '')}>
            Relevant history
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-linear-text-2">
            {referral.relevant_history}
          </p>
        </div>
      </div>
      <div className="mt-4 rounded-md border border-linear-hairline bg-linear-surface-2 p-2.5 text-[11px] italic text-linear-text-3">
        “{referral.evidence_quote}”
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Patient summary
// ---------------------------------------------------------------------------

function SummarySection({
  summary,
  fleschKincaid,
  flagged,
}: {
  summary: string | null;
  fleschKincaid: number | null;
  flagged: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const onCopy = useCallback(async () => {
    if (!summary) return;
    try {
      await navigator.clipboard.writeText(summary);
      setCopied(true);
      toast.success('Copied to clipboard');
      // Don't setState inside an effect — just a plain timeout is fine.
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Could not copy — your browser blocked clipboard access.');
    }
  }, [summary]);

  if (!summary) {
    return (
      <section>
        <h3 className={SECTION_LABEL}>Patient summary</h3>
        <div className="rounded-lg border border-dashed border-linear-border bg-linear-surface-1 p-6 text-center text-[13px] text-linear-text-3">
          No patient summary generated for this visit.
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className={SECTION_LABEL.replace('mb-3', '')}>Patient summary</h3>
        <div className="flex items-center gap-2">
          {fleschKincaid != null && (
            <span
              className={cn(
                'qm-lin-pill',
                flagged && 'bg-linear-warning/15 text-linear-warning'
              )}
              title="Flesch-Kincaid reading-grade level. Target is 8 or lower."
            >
              Reading level: grade {fleschKincaid.toFixed(1)}
            </span>
          )}
          <button type="button" onClick={onCopy} className="qm-lin-btn">
            {copied ? (
              <>
                <Check className="h-3 w-3" aria-hidden />
                Copied
              </>
            ) : (
              <>
                <Copy className="h-3 w-3" aria-hidden />
                Copy
              </>
            )}
          </button>
        </div>
      </div>
      <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-6">
        <div className="whitespace-pre-wrap text-[14px] leading-relaxed text-linear-text-2">
          {summary}
        </div>
      </div>
    </section>
  );
}

// Exported helper: decide whether the Extras tab should badge.
export function extrasTabHasFlag(
  confidenceScores: unknown,
  hasSummary: boolean
): boolean {
  const cs =
    (confidenceScores as Record<string, { status?: string; metadata?: { flagged?: boolean } }> | null) ?? {};
  const summaryFlagged = Boolean(
    hasSummary && cs.patient_summary?.metadata?.flagged
  );
  const anyFailed =
    cs.referrals?.status === 'failed' || cs.patient_summary?.status === 'failed';
  return summaryFlagged || anyFailed;
}
