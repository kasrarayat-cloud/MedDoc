'use client';

// ============================================================================
// ExtrasTab — referrals + patient-summary panel.
// ----------------------------------------------------------------------------
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the existing dark cards
// verbatim. Migrated surfaces (visit-detail) pass `theme="clinician"`
// to render the .qm-cl-card surfaces + soft urgency pills + serif
// patient-summary body matching the visit-detail mockup's extras
// panel.
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
  theme?: ExtrasTabTheme;
}

export function ExtrasTab({
  referrals,
  patientSummary,
  fleschKincaid,
  flagged,
  theme = 'legacy',
}: ExtrasTabProps) {
  const refBlob = (referrals as ReferralsBlob | null) ?? null;
  const refs = refBlob?.referrals ?? [];

  return (
    <div className="space-y-8">
      <ReferralsSection referrals={refs} theme={theme} />
      <SummarySection
        summary={patientSummary}
        fleschKincaid={fleschKincaid}
        flagged={flagged}
        theme={theme}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Referrals
// ---------------------------------------------------------------------------

function ReferralsSection({
  referrals,
  theme,
}: {
  referrals: Referral[];
  theme: ExtrasTabTheme;
}) {
  const isClinician = theme === 'clinician';
  return (
    <section>
      <h3
        className={cn(
          'mb-3 text-[11px] font-semibold uppercase tracking-wider',
          isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
        )}
      >
        Referrals
      </h3>
      {referrals.length === 0 ? (
        <div
          className={cn(
            'rounded-xl p-6 text-center text-[13px]',
            isClinician
              ? 'border border-dashed border-clinician-line bg-clinician-cream-card text-clinician-ink-3'
              : 'border border-dashed border-border-subtle bg-bg-surface-1/30 text-text-tertiary'
          )}
        >
          No referrals documented in the plan.
        </div>
      ) : (
        <ul className="space-y-3">
          {referrals.map((r, i) => (
            <ReferralCard key={i} referral={r} theme={theme} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ReferralCard({
  referral,
  theme,
}: {
  referral: Referral;
  theme: ExtrasTabTheme;
}) {
  const isClinician = theme === 'clinician';
  const urgency = isClinician
    ? {
        routine: { label: 'Routine', cls: 'qm-cl-pill qm-cl-pill-soft' },
        urgent: { label: 'Urgent', cls: 'qm-cl-pill qm-cl-pill-amber' },
        stat: { label: 'Stat', cls: 'qm-cl-pill qm-cl-pill-coral' },
      }[referral.urgency]
    : {
        routine: {
          label: 'Routine',
          cls: 'bg-bg-surface-3 text-text-tertiary border-border-default',
        },
        urgent: {
          label: 'Urgent',
          cls: 'bg-warning/15 text-warning border-warning/40',
        },
        stat: { label: 'Stat', cls: 'bg-danger/15 text-danger border-danger/40' },
      }[referral.urgency];

  return (
    <li
      className={cn(
        'p-5',
        isClinician
          ? 'qm-cl-card'
          : 'rounded-xl border border-border-default bg-bg-surface-1/60'
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div
            className={cn(
              'text-[11px] font-medium uppercase tracking-wider',
              isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
            )}
          >
            Refer to
          </div>
          <div
            className={cn(
              'mt-0.5 text-[16px] font-semibold',
              isClinician ? 'text-clinician-ink' : 'text-text-primary'
            )}
          >
            {referral.to}
          </div>
        </div>
        {isClinician ? (
          <span
            className={urgency.cls}
            style={{
              fontSize: 10.5,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            {urgency.label}
          </span>
        ) : (
          <span
            className={cn(
              'inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
              urgency.cls
            )}
          >
            {urgency.label}
          </span>
        )}
      </div>
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <div
            className={cn(
              'text-[11px] font-medium uppercase tracking-wider',
              isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
            )}
          >
            Reason
          </div>
          <p
            className={cn(
              'mt-1 text-[13px] leading-relaxed',
              isClinician ? 'text-clinician-ink-2' : 'text-text-secondary'
            )}
          >
            {referral.reason}
          </p>
        </div>
        <div>
          <div
            className={cn(
              'text-[11px] font-medium uppercase tracking-wider',
              isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
            )}
          >
            Relevant history
          </div>
          <p
            className={cn(
              'mt-1 text-[13px] leading-relaxed',
              isClinician ? 'text-clinician-ink-2' : 'text-text-secondary'
            )}
          >
            {referral.relevant_history}
          </p>
        </div>
      </div>
      <div
        className={cn(
          'mt-4 rounded-lg p-2.5 text-[11px] italic',
          isClinician
            ? 'border border-clinician-line bg-clinician-cream-2 text-clinician-ink-3'
            : 'border border-border-subtle bg-bg-surface-2/40 text-text-muted'
        )}
      >
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
  theme,
}: {
  summary: string | null;
  fleschKincaid: number | null;
  flagged: boolean;
  theme: ExtrasTabTheme;
}) {
  const isClinician = theme === 'clinician';
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
        <h3
          className={cn(
            'mb-3 text-[11px] font-semibold uppercase tracking-wider',
            isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
          )}
        >
          Patient summary
        </h3>
        <div
          className={cn(
            'rounded-xl p-6 text-center text-[13px]',
            isClinician
              ? 'border border-dashed border-clinician-line bg-clinician-cream-card text-clinician-ink-3'
              : 'border border-dashed border-border-subtle bg-bg-surface-1/30 text-text-tertiary'
          )}
        >
          No patient summary generated for this visit.
        </div>
      </section>
    );
  }

  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h3
          className={cn(
            'text-[11px] font-semibold uppercase tracking-wider',
            isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
          )}
        >
          Patient summary
        </h3>
        <div className="flex items-center gap-2">
          {fleschKincaid != null &&
            (isClinician ? (
              <span
                className={cn(
                  'qm-cl-pill',
                  flagged ? 'qm-cl-pill-amber' : 'qm-cl-pill-soft'
                )}
                style={{ fontSize: 10.5 }}
                title="Flesch-Kincaid reading-grade level. Target is 8 or lower."
              >
                Reading level: grade {fleschKincaid.toFixed(1)}
              </span>
            ) : (
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
            ))}
          <button
            type="button"
            onClick={onCopy}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[11px]',
              isClinician
                ? 'border border-clinician-line bg-clinician-cream-card text-clinician-ink-3 hover:border-clinician-line-strong hover:text-clinician-ink-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream'
                : 'border border-border-subtle bg-bg-surface-2/60 text-text-tertiary hover:border-border-default hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base'
            )}
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
      <div
        className={cn(
          'p-6',
          isClinician
            ? 'qm-cl-card'
            : 'rounded-xl border border-border-default bg-bg-surface-1/60'
        )}
      >
        {/* Serif for that "letter from your doctor" feel. */}
        <div
          className={cn(
            'whitespace-pre-wrap text-[14.5px] leading-relaxed',
            isClinician
              ? 'qm-cl-serif text-clinician-ink-2'
              : 'font-serif text-text-secondary'
          )}
        >
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
