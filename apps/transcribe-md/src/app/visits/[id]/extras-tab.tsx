'use client';

import { useCallback, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';

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
}

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
      <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
        Referrals
      </h3>
      {referrals.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border-subtle bg-bg-surface-1/30 p-6 text-center text-[13px] text-text-tertiary">
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
    routine: { label: 'Routine', cls: 'bg-bg-surface-3 text-text-tertiary border-border-default' },
    urgent: { label: 'Urgent', cls: 'bg-warning/15 text-warning border-warning/40' },
    stat: { label: 'Stat', cls: 'bg-danger/15 text-danger border-danger/40' },
  }[referral.urgency];
  return (
    <li className="rounded-xl border border-border-default bg-bg-surface-1/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
            Refer to
          </div>
          <div className="mt-0.5 text-[16px] font-semibold text-text-primary">
            {referral.to}
          </div>
        </div>
        <span
          className={cn(
            'inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
            urgency.cls
          )}
        >
          {urgency.label}
        </span>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <div className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
            Reason
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">
            {referral.reason}
          </p>
        </div>
        <div>
          <div className="text-[11px] font-medium uppercase tracking-wider text-text-muted">
            Relevant history
          </div>
          <p className="mt-1 text-[13px] leading-relaxed text-text-secondary">
            {referral.relevant_history}
          </p>
        </div>
      </div>
      <div className="mt-4 rounded-lg border border-border-subtle bg-bg-surface-2/40 p-2.5 text-[11px] italic text-text-muted">
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
        <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          Patient summary
        </h3>
        <div className="rounded-xl border border-dashed border-border-subtle bg-bg-surface-1/30 p-6 text-center text-[13px] text-text-tertiary">
          No patient summary generated for this visit.
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3 className="text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          Patient summary
        </h3>
        <div className="flex items-center gap-2">
          {fleschKincaid != null && (
            <span
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider',
                flagged
                  ? 'border-warning/40 bg-warning/10 text-warning'
                  : 'border-border-subtle bg-bg-surface-2/60 text-text-tertiary'
              )}
              title="Flesch-Kincaid reading-grade level. Target is 8 or lower."
            >
              Reading level: grade {fleschKincaid.toFixed(1)}
            </span>
          )}
          <button
            type="button"
            onClick={onCopy}
            className="inline-flex items-center gap-1.5 rounded-full border border-border-subtle bg-bg-surface-2/60 px-3 py-1 text-[11px] text-text-tertiary hover:border-border-default hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base"
          >
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
      <div className="rounded-xl border border-border-default bg-bg-surface-1/60 p-6">
        {/* Serif for that "letter from your doctor" feel. */}
        <div className="whitespace-pre-wrap font-serif text-[14.5px] leading-relaxed text-text-secondary">
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
