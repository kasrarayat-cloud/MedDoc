'use client';

// ============================================================================
// RxTab — prescriptions panel for the visit-detail Rx tab. Hosts the
// RxWarningCard family.
// ----------------------------------------------------------------------------
// Phase 5 — Linear V1 Faithful. Prescription cards render on
// surface-1 with hairline borders, action pills mapped to sage /
// neutral / sky / warning / danger tones. RxWarningCard owns the
// `.qm-warn-*` class family and is intentionally NOT touched here —
// those classes were rebuilt in Stage 2 to render correctly on the
// dark canvas. The `theme` prop is preserved as a no-op.
// ============================================================================

import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/cn';
import {
  RxWarningCard,
  type RxWarning as RxWarningCardData,
  type Severity as RxWarningSeverity,
} from '@/components/rx/rx-warning-card';

type RxTabTheme = 'legacy' | 'clinician';

// ---------------------------------------------------------------------------
// Wire types — mirror Layer 7c output.
// ---------------------------------------------------------------------------

type RxAction =
  | 'new'
  | 'continue'
  | 'increase'
  | 'decrease'
  | 'discontinue'
  | 'unclear';

interface Prescription {
  drug: string;
  strength?: string | null;
  form?: string | null;
  sig?: string | null;
  quantity?: string | null;
  refills?: string | null;
  action: RxAction;
  evidence_quote: string;
}

interface RxWarning {
  severity: 'critical' | 'major' | 'minor';
  rx_drug: string;
  message: string;
  evidence_quote?: string | null;
}

export interface RxBlob {
  prescriptions?: Prescription[];
  warnings?: RxWarning[];
}

const SECTION_LABEL =
  'mb-3 text-[10.5px] font-medium uppercase tracking-[0.07em] font-mono text-linear-text-3';

export function RxTab({
  rx,
  visitId,
}: {
  rx: unknown;
  visitId: string;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: RxTabTheme;
}) {
  const blob = (rx as RxBlob | null) ?? null;
  const prescriptions = blob?.prescriptions ?? [];
  const warnings = blob?.warnings ?? [];

  if (prescriptions.length === 0 && warnings.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-linear-border bg-linear-surface-1 p-8 text-center">
        <div className="text-[14px] font-medium text-linear-text">
          No prescriptions from this visit
        </div>
        <div className="mt-2 text-[13px] text-linear-text-2">
          The plan didn’t document any medication changes. You can still add
          prescriptions in your EHR after signing.
        </div>
      </div>
    );
  }

  // Sort warnings by severity (critical → major → minor) so the most
  // important ones are always above the fold.
  const severityOrder: Record<RxWarning['severity'], number> = {
    critical: 0,
    major: 1,
    minor: 2,
  };
  const sortedWarnings = [...warnings].sort(
    (a, b) => severityOrder[a.severity] - severityOrder[b.severity]
  );

  return (
    <div className="space-y-6">
      {sortedWarnings.length > 0 && (
        <div className="flex flex-col gap-3">
          {sortedWarnings.map((w, i) => (
            <RxWarningCard
              key={`${w.rx_drug}-${i}`}
              warning={mapWorkerWarning(w, i)}
              visitId={visitId}
            />
          ))}
        </div>
      )}

      <section>
        <h3 className={SECTION_LABEL}>Prescriptions</h3>
        <div className="space-y-3">
          {prescriptions.map((p, i) => (
            <PrescriptionCard key={`${p.drug}-${i}`} rx={p} />
          ))}
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Worker → component boundary mapping.
// ---------------------------------------------------------------------------
//
// Worker currently emits `severity: 'critical' | 'major' | 'minor'`; the
// RxWarningCard expects the design-spec enum `critical | warning | info`.
// Map at the integration boundary so today's worker output still renders;
// a follow-up PR will narrow the backend enum to match.
// The worker doesn't emit the rich shape (risks / heard / guess / details)
// yet — the card gracefully degrades to header + action tile.

function severityToCardSev(s: RxWarning['severity']): RxWarningSeverity {
  if (s === 'critical') return 'critical';
  if (s === 'major') return 'warning';
  return 'info';
}

function mapWorkerWarning(
  w: RxWarning,
  index: number
): RxWarningCardData {
  return {
    // Worker doesn't emit stable IDs yet; fall back to a positional
    // synthetic so the audit row (which requires an ID) has something
    // deterministic to hash against. Real worker PR will replace this.
    id: `worker-${index}-${w.rx_drug}`,
    rxLineNumber: index + 1,
    sev: severityToCardSev(w.severity),
    headline: `${w.rx_drug} — ${w.message}`,
    action: w.evidence_quote ? `"${w.evidence_quote}"` : undefined,
    // All rich fields stay undefined until the worker is updated.
  };
}

function PrescriptionCard({ rx }: { rx: Prescription }) {
  const [showEvidence, setShowEvidence] = useState(false);
  return (
    <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[17px] font-semibold text-linear-text">
            {rx.drug}
            {rx.strength && (
              <span className="ml-2 text-[14px] text-linear-text-3">
                {rx.strength}
              </span>
            )}
          </div>
          {rx.form && (
            <div className="mt-0.5 text-[12px] text-linear-text-3">
              {rx.form}
            </div>
          )}
        </div>
        <ActionChip action={rx.action} />
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-2 text-[13px] sm:grid-cols-3">
        <DetailRow label="Sig" value={rx.sig} />
        <DetailRow label="Quantity" value={rx.quantity} />
        <DetailRow label="Refills" value={rx.refills} />
      </dl>

      <button
        type="button"
        onClick={() => setShowEvidence((v) => !v)}
        className="mt-3 inline-flex items-center gap-1.5 rounded-md text-[11px] text-linear-text-3 hover:text-linear-text-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage focus-visible:ring-offset-2 focus-visible:ring-offset-linear-bg"
      >
        {showEvidence ? 'Hide evidence' : 'Show evidence'}
        <ChevronDown
          className={cn(
            'h-3 w-3 transition-transform',
            showEvidence && 'rotate-180'
          )}
          aria-hidden
        />
      </button>
      {showEvidence && (
        <div className="mt-2 rounded-md border border-linear-hairline bg-linear-surface-2 p-2.5 text-[12px] italic text-linear-text-3">
          “{rx.evidence_quote}”
        </div>
      )}
    </div>
  );
}

function DetailRow({
  label,
  value,
}: {
  label: string;
  value?: string | null;
}) {
  return (
    <div>
      <dt className="font-mono text-[10px] font-medium uppercase tracking-[0.07em] text-linear-text-3">
        {label}
      </dt>
      <dd
        className={cn(
          'mt-0.5 text-[13px]',
          value ? 'text-linear-text-2' : 'text-linear-text-3 italic'
        )}
      >
        {value ?? 'not specified'}
      </dd>
    </div>
  );
}

function ActionChip({ action }: { action: RxAction }) {
  // Linear V1 maps the action enum to neutral / sage / sky / warning /
  // danger tints. NEW/sage = additive; CONTINUE = neutral pill; the
  // remaining states gradient up the warning spectrum.
  const meta: Record<RxAction, { label: string; cls: string }> = {
    new: { label: 'NEW', cls: 'qm-lin-pill qm-lin-pill--sage' },
    continue: { label: 'CONTINUE', cls: 'qm-lin-pill' },
    increase: {
      label: 'INCREASE',
      cls: 'qm-lin-pill bg-linear-sky/15 text-linear-sky',
    },
    decrease: {
      label: 'DECREASE',
      cls: 'qm-lin-pill bg-linear-warning/15 text-linear-warning',
    },
    discontinue: {
      label: 'DISCONTINUE',
      cls: 'qm-lin-pill bg-linear-danger/15 text-linear-danger',
    },
    unclear: {
      label: 'UNCLEAR',
      cls: 'qm-lin-pill bg-linear-danger/15 text-linear-danger',
    },
  };
  const m = meta[action];
  return <span className={m.cls}>{m.label}</span>;
}

// Exported helper: tells Tabs whether the Rx tab should badge.
export function rxTabWarningLevel(rx: unknown): 'critical' | 'any' | null {
  const blob = (rx as RxBlob | null) ?? null;
  const warnings = blob?.warnings ?? [];
  if (warnings.length === 0) return null;
  return warnings.some((w) => w.severity === 'critical') ? 'critical' : 'any';
}
