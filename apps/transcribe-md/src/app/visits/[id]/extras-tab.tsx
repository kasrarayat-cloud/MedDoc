'use client';

// ============================================================================
// ExtrasTab — Phase 5.1 EXTRAS V4 Card Stream.
// ----------------------------------------------------------------------------
// Source mockup: docs/design-directions-v9-tabs/extras-v4.html
//
// The Extras tab now renders a single column of 7 patient-/encounter-
// scoped cards plus an 8th supplementary card for AI-generated extras
// (referrals + patient summary, preserved from the previous
// implementation):
//
//   1. Demographics      (DemographicsCard)
//   2. Vitals            (VitalsCard)
//   3. Allergies         (AllergiesCard)
//   4. Current meds      (MedicationsCard)
//   5. Problem list      (ProblemsCard)
//   6. Visit metadata    (VisitMetaCard)
//   7. Audit log         (AuditLogCard)
//   8. AI extras         (referrals + patient summary, opt-in)
//
// Data discipline:
//   * No new Prisma queries are added in this tab. Cards fall back to
//     em-dash placeholders when their data isn't yet wired into the
//     visit row.
//   * `signedAt` (visit lifecycle) drives readonly mode — when set,
//     every "Edit" affordance is hidden.
//   * Audit log is READ-ONLY: this component derives a timeline from
//     fields already on the visit (processingStartedAt, signedAt, …)
//     and never writes to the audit_logs table.
//
// `extrasTabHasFlag` is preserved — visit-ready-view.tsx still calls
// it to decide the Extras-tab dot-badge.
// ============================================================================

import { useCallback, useState } from 'react';
import { Copy, Check } from 'lucide-react';
import { toast } from 'sonner';

import { cn } from '@/lib/cn';
import { reportClipboardCopy } from '@/lib/clipboard-audit';

import { DemographicsCard, type DemographicsCardData } from './extras/DemographicsCard';
import { VitalsCard, type VitalsCardData } from './extras/VitalsCard';
import { AllergiesCard, type Allergy } from './extras/AllergiesCard';
import { MedicationsCard, type ChronicMedication } from './extras/MedicationsCard';
import { ProblemsCard, type Problem } from './extras/ProblemsCard';
import { VisitMetaCard, type VisitMetaData } from './extras/VisitMetaCard';
import { AuditLogCard, type AuditEvent } from './extras/AuditLogCard';

// ---------------------------------------------------------------------------
// Wire types
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

type ExtrasTabTheme = 'legacy' | 'clinician';

interface ExtrasTabProps {
  /** Visit this content belongs to — required so the patient-summary copy
   *  can be audited as a PHI disclosure (S4b). */
  visitId: string;
  /** AI-generated referrals blob (preserved from the previous
   *  ExtrasTab; rendered in the supplementary "AI extras" card). */
  referrals: unknown;
  /** AI-generated patient-friendly summary. */
  patientSummary: string | null;
  /** Flesch-Kincaid grade level for the patient summary. */
  fleschKincaid: number | null;
  /** True when the summary tripped readability QA. */
  flagged: boolean;
  /** When true, the visit is signed → all Edit buttons are hidden and
   *  the cards render in display-only mode. */
  readonly?: boolean;
  /** Card 1 — Demographics. */
  demographics?: DemographicsCardData;
  /** Card 2 — Vitals. */
  vitals?: VitalsCardData;
  /** Card 3 — Allergies. */
  allergies?: Allergy[];
  /** Card 4 — Chronic medications. */
  chronicMedications?: ChronicMedication[];
  /** Card 5 — Problem list. */
  problems?: Problem[];
  /** Card 6 — Visit metadata. */
  visitMeta?: VisitMetaData;
  /** Card 7 — Audit timeline (caller-supplied, READ-ONLY). */
  auditEvents?: AuditEvent[];
  auditTotal?: number;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: ExtrasTabTheme;
}

export function ExtrasTab({
  visitId,
  referrals,
  patientSummary,
  fleschKincaid,
  flagged,
  readonly = false,
  demographics,
  vitals,
  allergies,
  chronicMedications,
  problems,
  visitMeta,
  auditEvents,
  auditTotal,
}: ExtrasTabProps) {
  const refBlob = (referrals as ReferralsBlob | null) ?? null;
  const refs = refBlob?.referrals ?? [];
  const hasAiExtras = refs.length > 0 || Boolean(patientSummary);

  return (
    <div className="qm-lin-card-stream">
      {demographics && (
        <DemographicsCard data={demographics} readonly={readonly} />
      )}
      {vitals && <VitalsCard data={vitals} readonly={readonly} />}
      {allergies && (
        <AllergiesCard allergies={allergies} readonly={readonly} />
      )}
      {chronicMedications && (
        <MedicationsCard
          medications={chronicMedications}
          readonly={readonly}
        />
      )}
      {problems && <ProblemsCard problems={problems} readonly={readonly} />}
      {visitMeta && <VisitMetaCard data={visitMeta} />}
      {auditEvents && (
        <AuditLogCard events={auditEvents} totalEvents={auditTotal} />
      )}
      {hasAiExtras && (
        <AiExtrasCard
          visitId={visitId}
          referrals={refs}
          patientSummary={patientSummary}
          fleschKincaid={fleschKincaid}
          flagged={flagged}
        />
      )}
      {!demographics &&
        !vitals &&
        !allergies &&
        !chronicMedications &&
        !problems &&
        !visitMeta &&
        !auditEvents &&
        !hasAiExtras && (
          <div className="qm-lin-extras-card">
            <div className="qm-lin-extras-body">
              <div className="qm-lin-extras-empty">
                No extras recorded for this visit yet.
              </div>
            </div>
          </div>
        )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI extras card — preserved from the previous implementation. Holds the
// AI-generated referrals + patient-friendly summary (with copy + reading
// level chip).
// ---------------------------------------------------------------------------

function AiExtrasCard({
  visitId,
  referrals,
  patientSummary,
  fleschKincaid,
  flagged,
}: {
  visitId: string;
  referrals: Referral[];
  patientSummary: string | null;
  fleschKincaid: number | null;
  flagged: boolean;
}) {
  return (
    <article className="qm-lin-extras-card">
      <header className="qm-lin-extras-head">
        <div className="qm-lin-extras-head-left">
          <span className="qm-lin-extras-icon" aria-hidden>
            ✨
          </span>
          <div className="qm-lin-extras-title-block">
            <h2 className="qm-lin-extras-title">Visit AI extras</h2>
            <span className="qm-lin-extras-sub">
              Auto-drafted · review before sign
            </span>
          </div>
        </div>
      </header>
      <div className="qm-lin-extras-body">
        <div className="space-y-6">
          <ReferralsSection referrals={referrals} />
          <SummarySection
            visitId={visitId}
            summary={patientSummary}
            fleschKincaid={fleschKincaid}
            flagged={flagged}
          />
        </div>
      </div>
    </article>
  );
}

const SECTION_LABEL =
  'mb-3 text-[10.5px] font-medium uppercase tracking-[0.07em] font-mono text-linear-text-3';

function ReferralsSection({ referrals }: { referrals: Referral[] }) {
  return (
    <section>
      <h3 className={SECTION_LABEL}>Referrals</h3>
      {referrals.length === 0 ? (
        <div className="rounded-lg border border-dashed border-linear-border bg-linear-surface-1 p-4 text-center text-[13px] text-linear-text-3">
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
    <li className="rounded-lg border border-linear-border bg-linear-surface-2 p-5">
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
      <div className="mt-4 rounded-md border border-linear-hairline bg-linear-surface-1 p-2.5 text-[11px] italic text-linear-text-3">
        “{referral.evidence_quote}”
      </div>
    </li>
  );
}

function SummarySection({
  visitId,
  summary,
  fleschKincaid,
  flagged,
}: {
  visitId: string;
  summary: string | null;
  fleschKincaid: number | null;
  flagged: boolean;
}) {
  const [copied, setCopied] = useState(false);

  const onCopy = useCallback(async () => {
    if (!summary) return;
    try {
      await navigator.clipboard.writeText(summary);
      // Post-resolve only: a blocked clipboard throws, and auditing a
      // disclosure that never happened would be a false record.
      reportClipboardCopy(visitId, 'summary', 'Patient summary', summary);
      setCopied(true);
      toast.success('Copied to clipboard');
      setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error('Could not copy — your browser blocked clipboard access.');
    }
  }, [visitId, summary]);

  if (!summary) {
    return (
      <section>
        <h3 className={SECTION_LABEL}>Patient summary</h3>
        <div className="rounded-lg border border-dashed border-linear-border bg-linear-surface-1 p-4 text-center text-[13px] text-linear-text-3">
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
      <div className="rounded-lg border border-linear-border bg-linear-surface-2 p-5">
        <div className="whitespace-pre-wrap text-[14px] leading-relaxed text-linear-text-2">
          {summary}
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Exported helper — decides whether the Extras tab gets a dot badge in
// the visit-ready-view tab bar. Logic preserved verbatim so the
// upstream call site's behaviour is unchanged.
// ---------------------------------------------------------------------------

export function extrasTabHasFlag(
  confidenceScores: unknown,
  hasSummary: boolean
): boolean {
  const cs =
    (confidenceScores as Record<
      string,
      { status?: string; metadata?: { flagged?: boolean } }
    > | null) ?? {};
  const summaryFlagged = Boolean(
    hasSummary && cs.patient_summary?.metadata?.flagged
  );
  const anyFailed =
    cs.referrals?.status === 'failed' ||
    cs.patient_summary?.status === 'failed';
  return summaryFlagged || anyFailed;
}
