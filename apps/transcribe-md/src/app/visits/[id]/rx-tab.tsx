'use client';

// ============================================================================
// RxTab — prescriptions panel for the visit-detail Rx tab. Hosts the
// RxWarningCard family.
// ----------------------------------------------------------------------------
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the existing dark cards
// verbatim. Migrated surfaces (visit-detail) pass `theme="clinician"`
// to render the .qm-cl-card prescription rows + soft action chips
// matching the visit-detail mockup's Rx panel.
//
// IMPORTANT: rx-warning-card.tsx is not threaded a theme here — it
// owns its own dual-theme branching internally (the .qm-warn-* family
// retains the same structure but resolves to clinician color tokens
// when wrapped in .qm-cl-app, per the §H.6 reskin policy).
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

export function RxTab({
  rx,
  visitId,
  theme = 'legacy',
}: {
  rx: unknown;
  visitId: string;
  theme?: RxTabTheme;
}) {
  const blob = (rx as RxBlob | null) ?? null;
  const prescriptions = blob?.prescriptions ?? [];
  const warnings = blob?.warnings ?? [];
  const isClinician = theme === 'clinician';

  if (prescriptions.length === 0 && warnings.length === 0) {
    return (
      <div
        className={cn(
          'rounded-xl p-8 text-center',
          isClinician
            ? 'border border-dashed border-clinician-line bg-clinician-cream-card'
            : 'border border-dashed border-border-subtle bg-bg-surface-1/30'
        )}
      >
        <div
          className={cn(
            'text-[14px] font-medium',
            isClinician ? 'text-clinician-ink' : 'text-text-primary'
          )}
        >
          No prescriptions from this visit
        </div>
        <div
          className={cn(
            'mt-2 text-[13px]',
            isClinician ? 'text-clinician-ink-2' : 'text-text-tertiary'
          )}
        >
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
        <h3
          className={cn(
            'mb-3 text-[11px] font-semibold uppercase tracking-wider',
            isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
          )}
        >
          Prescriptions
        </h3>
        <div className="space-y-3">
          {prescriptions.map((p, i) => (
            <PrescriptionCard
              key={`${p.drug}-${i}`}
              rx={p}
              theme={theme}
            />
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

function PrescriptionCard({
  rx,
  theme,
}: {
  rx: Prescription;
  theme: RxTabTheme;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const isClinician = theme === 'clinician';
  return (
    <div
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
              'text-[17px] font-semibold',
              isClinician ? 'text-clinician-ink' : 'text-text-primary'
            )}
          >
            {rx.drug}
            {rx.strength && (
              <span
                className={cn(
                  'ml-2 text-[14px]',
                  isClinician ? 'text-clinician-ink-3' : 'text-text-tertiary'
                )}
              >
                {rx.strength}
              </span>
            )}
          </div>
          {rx.form && (
            <div
              className={cn(
                'mt-0.5 text-[12px]',
                isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
              )}
            >
              {rx.form}
            </div>
          )}
        </div>
        <ActionChip action={rx.action} theme={theme} />
      </div>

      <dl className="mt-4 grid grid-cols-1 gap-2 text-[13px] sm:grid-cols-3">
        <DetailRow label="Sig" value={rx.sig} theme={theme} />
        <DetailRow label="Quantity" value={rx.quantity} theme={theme} />
        <DetailRow label="Refills" value={rx.refills} theme={theme} />
      </dl>

      <button
        type="button"
        onClick={() => setShowEvidence((v) => !v)}
        className={cn(
          'mt-3 inline-flex items-center gap-1.5 rounded-md text-[11px]',
          isClinician
            ? 'text-clinician-ink-3 hover:text-clinician-ink-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-clinician-sage focus-visible:ring-offset-2 focus-visible:ring-offset-clinician-cream'
            : 'text-text-muted hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base'
        )}
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
        <div
          className={cn(
            'mt-2 rounded-lg p-2.5 text-[12px] italic',
            isClinician
              ? 'border border-clinician-line bg-clinician-cream-2 text-clinician-ink-3'
              : 'border border-border-subtle bg-bg-surface-2/40 text-text-tertiary'
          )}
        >
          “{rx.evidence_quote}”
        </div>
      )}
    </div>
  );
}

function DetailRow({
  label,
  value,
  theme,
}: {
  label: string;
  value?: string | null;
  theme: RxTabTheme;
}) {
  const isClinician = theme === 'clinician';
  return (
    <div>
      <dt
        className={cn(
          'text-[10px] font-medium uppercase tracking-wider',
          isClinician ? 'text-clinician-ink-3' : 'text-text-muted'
        )}
      >
        {label}
      </dt>
      <dd
        className={cn(
          'mt-0.5 text-[13px]',
          value
            ? isClinician
              ? 'text-clinician-ink-2'
              : 'text-text-secondary'
            : isClinician
              ? 'text-clinician-ink-4 italic'
              : 'text-text-muted italic'
        )}
      >
        {value ?? 'not specified'}
      </dd>
    </div>
  );
}

function ActionChip({
  action,
  theme,
}: {
  action: RxAction;
  theme: RxTabTheme;
}) {
  const isClinician = theme === 'clinician';
  // Clinician maps the legacy success/cyan/warning/danger triad to
  // .qm-cl-pill-* tones — sage = new, soft = continue, sky = increase,
  // amber = decrease, coral = discontinue/unclear. Same semantic
  // ordering, soft palette.
  if (isClinician) {
    const meta: Record<RxAction, { label: string; cls: string }> = {
      new: { label: 'NEW', cls: 'qm-cl-pill qm-cl-pill-sage' },
      continue: { label: 'CONTINUE', cls: 'qm-cl-pill qm-cl-pill-soft' },
      increase: { label: 'INCREASE', cls: 'qm-cl-pill qm-cl-pill-sky' },
      decrease: { label: 'DECREASE', cls: 'qm-cl-pill qm-cl-pill-amber' },
      discontinue: { label: 'DISCONTINUE', cls: 'qm-cl-pill qm-cl-pill-coral' },
      unclear: { label: 'UNCLEAR', cls: 'qm-cl-pill qm-cl-pill-coral' },
    };
    const m = meta[action];
    return (
      <span
        className={m.cls}
        style={{
          fontSize: 10,
          letterSpacing: '0.04em',
          textTransform: 'uppercase',
        }}
      >
        {m.label}
      </span>
    );
  }

  const meta: Record<RxAction, { label: string; cls: string }> = {
    new: { label: 'NEW', cls: 'bg-success/15 text-success border-success/40' },
    continue: {
      label: 'CONTINUE',
      cls: 'bg-bg-surface-3 text-text-tertiary border-border-default',
    },
    increase: {
      label: 'INCREASE',
      cls: 'bg-cyan-500/15 text-cyan-400 border-cyan-500/40',
    },
    decrease: {
      label: 'DECREASE',
      cls: 'bg-warning/15 text-warning border-warning/40',
    },
    discontinue: {
      label: 'DISCONTINUE',
      cls: 'bg-danger/15 text-danger border-danger/40',
    },
    unclear: {
      label: 'UNCLEAR',
      cls: 'bg-transparent text-danger border-danger/50',
    },
  };
  const m = meta[action];
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider',
        m.cls
      )}
    >
      {m.label}
    </span>
  );
}

// Exported helper: tells Tabs whether the Rx tab should badge.
export function rxTabWarningLevel(rx: unknown): 'critical' | 'any' | null {
  const blob = (rx as RxBlob | null) ?? null;
  const warnings = blob?.warnings ?? [];
  if (warnings.length === 0) return null;
  return warnings.some((w) => w.severity === 'critical') ? 'critical' : 'any';
}
