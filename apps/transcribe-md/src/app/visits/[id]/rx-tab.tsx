'use client';

import { useState } from 'react';
import { ChevronDown, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/cn';

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

export function RxTab({ rx }: { rx: unknown }) {
  const blob = (rx as RxBlob | null) ?? null;
  const prescriptions = blob?.prescriptions ?? [];
  const warnings = blob?.warnings ?? [];

  if (prescriptions.length === 0 && warnings.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border-subtle bg-bg-surface-1/30 p-8 text-center">
        <div className="text-[14px] font-medium text-text-primary">
          No prescriptions from this visit
        </div>
        <div className="mt-2 text-[13px] text-text-tertiary">
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
        <WarningsPanel warnings={sortedWarnings} />
      )}

      <section>
        <h3 className="mb-3 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          Prescriptions
        </h3>
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
// Sub-components
// ---------------------------------------------------------------------------

function WarningsPanel({ warnings }: { warnings: RxWarning[] }) {
  const hasCritical = warnings.some((w) => w.severity === 'critical');
  return (
    <div
      role="alert"
      className={cn(
        'rounded-xl border p-4',
        hasCritical
          ? 'border-danger/40 bg-danger/5'
          : 'border-warning/40 bg-warning/5'
      )}
    >
      <div className="mb-3 flex items-center gap-2">
        <AlertTriangle
          className={cn(
            'h-4 w-4',
            hasCritical ? 'text-danger' : 'text-warning'
          )}
          aria-hidden
        />
        <span className="text-[13px] font-semibold text-text-primary">
          {hasCritical
            ? 'Critical safety warnings — review before signing'
            : 'Review these warnings before signing'}
        </span>
      </div>
      <ul className="space-y-2">
        {warnings.map((w, i) => (
          <li
            key={i}
            className="rounded-lg border border-border-subtle bg-bg-surface-1/40 px-3 py-2"
          >
            <div className="flex flex-wrap items-center gap-2 text-[12px]">
              <span
                className={cn(
                  'inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider',
                  w.severity === 'critical'
                    ? 'border-danger/40 bg-danger/10 text-danger'
                    : w.severity === 'major'
                      ? 'border-warning/40 bg-warning/10 text-warning'
                      : 'border-border-default bg-bg-surface-2 text-text-tertiary'
                )}
              >
                {w.severity}
              </span>
              <span className="font-medium text-text-primary">{w.rx_drug}</span>
            </div>
            <div className="mt-1 text-[12px] text-text-secondary">
              {w.message}
            </div>
            {w.evidence_quote && (
              <div className="mt-1 text-[11px] italic text-text-muted">
                “{w.evidence_quote}”
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function PrescriptionCard({ rx }: { rx: Prescription }) {
  const [showEvidence, setShowEvidence] = useState(false);
  return (
    <div className="rounded-xl border border-border-default bg-bg-surface-1/60 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[17px] font-semibold text-text-primary">
            {rx.drug}
            {rx.strength && (
              <span className="ml-2 text-[14px] text-text-tertiary">
                {rx.strength}
              </span>
            )}
          </div>
          {rx.form && (
            <div className="mt-0.5 text-[12px] text-text-muted">{rx.form}</div>
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
        className="mt-3 inline-flex items-center gap-1.5 text-[11px] text-text-muted hover:text-text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-bg-base rounded-md"
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
        <div className="mt-2 rounded-lg border border-border-subtle bg-bg-surface-2/40 p-2.5 text-[12px] italic text-text-tertiary">
          “{rx.evidence_quote}”
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-[10px] font-medium uppercase tracking-wider text-text-muted">
        {label}
      </dt>
      <dd
        className={cn(
          'mt-0.5 text-[13px]',
          value ? 'text-text-secondary' : 'text-text-muted italic'
        )}
      >
        {value ?? 'not specified'}
      </dd>
    </div>
  );
}

function ActionChip({ action }: { action: RxAction }) {
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
