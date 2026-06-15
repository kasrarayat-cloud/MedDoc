'use client';

// ============================================================================
// RxTab — Phase 5.1 Linear V1 V3 split-pane
// ----------------------------------------------------------------------------
// Two-column layout. Left pane (~62-65%): Rx list — each prescription
// renders as a Rx-ID-prefixed card with a four-cell dose/freq/qty/refills
// grid, an action pill, and edit/copy hover affordances. Right pane
// (~32-35%): the RxWarningsRail — a severity-grouped sidebar that uses
// the protected `.qm-warn-{critical|serious|moderate|info}` classes
// byte-identical.
//
// Below 1080px the layout collapses to a single column with the rail
// flowing under the list.
//
// Active card → matching warnings highlight: clicking an Rx card sets
// the card's left-border sage rail and dims non-matching warnings.
// Clicking a warning focuses its corresponding Rx card.
//
// Read-only mode: when the visit is SIGNED, the "+ Add prescription"
// tile and edit affordances are suppressed.
// ============================================================================

import { useCallback, useEffect, useId, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { cn } from '@/lib/cn';
import { Ic } from '@/components/ui/icon';
import {
  RxWarningsRail,
  type RailSeverity,
  type RailWarning,
} from './rx-warnings-rail';
// Canonical warning identity + severity mapping — shared with recordOverride
// and the sign gate so the override warningId the rail emits is exactly what
// the server validates + correlates against (fix/rx-override-gate-correlation).
import { warningIdForIndex, mapWorkerSeverity, criticalWarningRefs } from '@/lib/rx-warnings';

type RxTabTheme = 'legacy' | 'clinician';

// ---------------------------------------------------------------------------
// Wire types — preserve the worker contract byte-identically.
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

/** Shape emitted by `07c-rx-drafting.ts` today. */
interface WorkerWarning {
  severity: 'critical' | 'major' | 'minor';
  rx_drug: string;
  message: string;
  evidence_quote?: string | null;
}

export interface RxBlob {
  prescriptions?: Prescription[];
  warnings?: WorkerWarning[];
}

interface RxTabProps {
  rx: unknown;
  visitId: string;
  /** Visit is SIGNED → suppress mutation affordances. */
  readonly?: boolean;
  /** warningIds (rx-warning-${i}) that already have RxWarningOverride
   *  rows in the database. Threaded from page.tsx's prisma query so the
   *  ✓ Overridden chip persists across reloads + tabs. New overrides
   *  recorded in this session are merged into local state. */
  initialOverriddenIds?: string[];
  /** V2 tabbed review (skin-only, read-only) — reports whether EVERY
   *  critical warning has an override row, so the V2 shell can mirror the
   *  server's fail-closed Rx sign gate as the VISIBLE half (disable the
   *  Sign trigger + the readiness pip). Derived from the SAME shared
   *  warningId/severity identity the server validates; this callback
   *  reads state only and never changes the override flow. */
  onResolvedChange?: (allCriticalResolved: boolean) => void;
  /** @deprecated kept for back-compat; Linear V1 is single-theme. */
  theme?: RxTabTheme;
}

// Public component
// ---------------------------------------------------------------------------

export function RxTab({
  rx,
  visitId,
  readonly = false,
  initialOverriddenIds = [],
  onResolvedChange,
}: RxTabProps) {
  const blob = (rx as RxBlob | null) ?? null;
  const prescriptions = blob?.prescriptions ?? [];
  const warnings = blob?.warnings ?? [];

  // Track which warnings have RxWarningOverride rows. Initial value
  // comes from the page-level prisma query; new overrides recorded
  // via the rail's modal flow merge in via the onOverrideRecorded
  // callback. Set rather than array for O(1) membership in the rail.
  const [overriddenIds, setOverriddenIds] = useState<Set<string>>(
    () => new Set(initialOverriddenIds)
  );
  const handleOverrideRecorded = useCallback((warningId: string) => {
    setOverriddenIds((prev) => {
      if (prev.has(warningId)) return prev;
      const next = new Set(prev);
      next.add(warningId);
      return next;
    });
  }, []);

  // Build stable Rx IDs (R-001, R-002, …). The order in the wire
  // determines the ID — preserved across renders so the rail's
  // data-rxid stays stable.
  const decoratedRx = useMemo(() => {
    return prescriptions.map((p, i) => ({
      ...p,
      rxId: rxIdFor(i),
      _ix: i,
    }));
  }, [prescriptions]);

  // Materialise the rail warnings. Worker doesn't emit explicit Rx IDs
  // yet, so match by `rx_drug` against the drug field; fall back to
  // the first Rx ID when no match (defensive). The 1-based
  // rxLineNumber is parsed from the matched Rx's index — when no
  // match, the warning attaches to the first Rx at line 1 so the
  // override's payload still passes the recordOverride number guard.
  const railWarnings = useMemo<RailWarning[]>(() => {
    return warnings.map((w, i) => {
      const matched = decoratedRx.find(
        (p) => p.drug?.toLowerCase() === w.rx_drug?.toLowerCase()
      );
      const rxId = matched?.rxId ?? decoratedRx[0]?.rxId ?? '—';
      const matchedIx = matched?._ix ?? decoratedRx[0]?._ix ?? 0;
      return {
        id: warningIdForIndex(i),
        severity: mapWorkerSeverity(w.severity),
        headline: w.rx_drug,
        body: w.message + (w.evidence_quote ? ` "${w.evidence_quote}"` : ''),
        rxId,
        rxLineNumber: matchedIx + 1,
      };
    });
  }, [warnings, decoratedRx]);

  // V2 read-only Rx gate mirror — report whether EVERY critical warning has an
  // override, using the SAME `criticalWarningRefs` identity the sign route's
  // fail-closed gate validates. The V2 shell uses this to disable the Sign
  // trigger (the visible half) until the critical override is recorded; the
  // server gate (POST /sign → 422) remains the authoritative enforcement.
  const criticalRefIds = useMemo(() => criticalWarningRefs(rx).map((r) => r.id), [rx]);
  const allCriticalResolved = useMemo(
    () => criticalRefIds.every((id) => overriddenIds.has(id)),
    [criticalRefIds, overriddenIds]
  );
  useEffect(() => {
    onResolvedChange?.(allCriticalResolved);
  }, [allCriticalResolved, onResolvedChange]);

  // Active card → matching warnings rail highlight.
  const [activeRxId, setActiveRxId] = useState<string | null>(null);

  const handleRxFocus = useCallback((rxId: string) => {
    setActiveRxId((current) => (current === rxId ? null : rxId));
  }, []);

  const handleWarningFocus = useCallback((rxId: string) => {
    setActiveRxId(rxId);
  }, []);

  // Empty state: zero prescriptions AND zero warnings.
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

  const activeCount = decoratedRx.filter((p) => p.action !== 'unclear').length;

  return (
    <div className="qm-lin-rx-split">
      {/* LEFT pane — Rx list */}
      <section>
        <div className="qm-lin-rx-pane-head">
          <div className="qm-lin-rx-pane-title">
            <span className="qm-lin-rx-pane-dot" aria-hidden />
            Prescriptions
            <span className="qm-lin-rx-pane-count">
              {decoratedRx.length} total · {activeCount} active
            </span>
          </div>
          {!readonly && (
            <div className="qm-lin-rx-pane-actions">
              <button
                type="button"
                className="qm-lin-rx-ghost-sm qm-lin-rx-ghost-sm-sage"
                disabled
                title="Add prescription (coming in T-M21)"
              >
                + Add Rx
              </button>
            </div>
          )}
        </div>

        <div className="qm-lin-rx-list">
          {decoratedRx.map((p) => (
            <PrescriptionCard
              key={`${p.rxId}-${p._ix}`}
              rx={p}
              active={activeRxId === p.rxId}
              readonly={readonly}
              onActivate={() => handleRxFocus(p.rxId)}
              warningTallies={tallyForRx(railWarnings, p.rxId)}
            />
          ))}

          {!readonly && (
            <button
              type="button"
              className="qm-lin-rx-add"
              disabled
              title="Add new prescription (coming in T-M21)"
            >
              <span className="plus" aria-hidden>+</span>
              Add new prescription
            </button>
          )}
        </div>
      </section>

      {/* RIGHT pane — Interactions rail */}
      <RxWarningsRail
        warnings={railWarnings}
        activeRxId={activeRxId}
        onWarningFocus={handleWarningFocus}
        visitId={visitId}
        overriddenIds={overriddenIds}
        onOverrideRecorded={handleOverrideRecorded}
        readonly={readonly}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// PrescriptionCard — single Rx in the left list.
// ---------------------------------------------------------------------------

interface DecoratedRx extends Prescription {
  rxId: string;
  _ix: number;
}

function PrescriptionCard({
  rx,
  active,
  readonly,
  onActivate,
  warningTallies,
}: {
  rx: DecoratedRx;
  active: boolean;
  readonly: boolean;
  onActivate: () => void;
  warningTallies: Record<RailSeverity, number>;
}) {
  const headlineId = useId();
  const totalWarnings =
    warningTallies.critical +
    warningTallies.serious +
    warningTallies.moderate +
    warningTallies.info;

  const onCopyRx = (e: React.MouseEvent) => {
    e.stopPropagation();
    const lines = [
      `${rx.drug}${rx.strength ? ` ${rx.strength}` : ''}`,
      rx.sig ? `Sig: ${rx.sig}` : null,
      rx.quantity ? `Quantity: ${rx.quantity}` : null,
      rx.refills ? `Refills: ${rx.refills}` : null,
    ]
      .filter(Boolean)
      .join('\n');
    if (typeof navigator !== 'undefined' && navigator.clipboard) {
      navigator.clipboard
        .writeText(lines)
        .then(() => {
          toast.success('Prescription copied to clipboard');
        })
        .catch(() => {
          toast.error('Could not copy prescription');
        });
    }
  };

  return (
    <article
      className={cn('qm-lin-rx-row', active && 'qm-lin-rx-row-active')}
      data-rxid={rx.rxId}
      tabIndex={0}
      role="button"
      aria-pressed={active}
      aria-labelledby={headlineId}
      onClick={onActivate}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onActivate();
        }
      }}
    >
      <div className="qm-lin-rx-row-top">
        <div className="qm-lin-rx-row-l">
          <div className="qm-lin-rx-name" id={headlineId}>
            {rx.drug}
            {rx.strength && (
              <span className="qm-lin-rx-strength">{rx.strength}</span>
            )}
          </div>
          <div className="qm-lin-rx-meta">
            <span className="qm-lin-rx-id">{rx.rxId}</span>
            {rx.form && <span> · {rx.form}</span>}
          </div>
        </div>
        <ActionPill action={rx.action} />
      </div>

      <div className="qm-lin-rx-row-grid">
        <div className="cell">
          <span className="l">Dose</span>
          <span className="v">{rx.sig ?? '—'}</span>
        </div>
        <div className="cell">
          <span className="l">Freq</span>
          <span className="v">{deriveFreq(rx.sig) ?? '—'}</span>
        </div>
        <div className="cell">
          <span className="l">Qty</span>
          <span className="v">{rx.quantity ?? '—'}</span>
        </div>
        <div className="cell">
          <span className="l">Refills</span>
          <span className="v">{rx.refills ?? '—'}</span>
        </div>
      </div>

      <div className="qm-lin-rx-row-foot">
        {totalWarnings > 0 ? (
          <div className="qm-lin-rx-warn-tally">
            <span className="chips" aria-hidden>
              {warningTallies.critical > 0 && (
                <span className="chip critical" />
              )}
              {warningTallies.serious > 0 && <span className="chip serious" />}
              {warningTallies.moderate > 0 && (
                <span className="chip moderate" />
              )}
              {warningTallies.info > 0 && <span className="chip info" />}
            </span>
            <span>
              {totalWarnings} warning{totalWarnings === 1 ? '' : 's'}
            </span>
          </div>
        ) : (
          <div className="qm-lin-rx-warn-tally qm-lin-rx-warn-tally-clean">
            <Ic.check width={11} height={11} aria-hidden />
            <span>Clean</span>
          </div>
        )}

        <div className="qm-lin-rx-row-actions">
          {!readonly && (
            <button
              type="button"
              onClick={(e) => e.stopPropagation()}
              disabled
              title="Edit (coming in T-M21)"
            >
              Edit
            </button>
          )}
          <button type="button" onClick={onCopyRx} title="Copy prescription">
            Copy
          </button>
        </div>
      </div>

      {/* Show evidence inline when the row is active. Quietly tucked
          below the grid for transcript traceability. */}
      {active && rx.evidence_quote && (
        <div className="qm-lin-rx-evidence">
          <span className="qm-lin-rx-evidence-label">Evidence</span>
          <span className="qm-lin-rx-evidence-body">
            “{rx.evidence_quote}”
          </span>
        </div>
      )}
    </article>
  );
}

// ---------------------------------------------------------------------------
// Action pill
// ---------------------------------------------------------------------------

function ActionPill({ action }: { action: RxAction }) {
  const meta: Record<RxAction, { label: string; cls: string }> = {
    new: { label: 'New', cls: 'qm-lin-rx-tag qm-lin-rx-tag-new' },
    continue: { label: 'Continue', cls: 'qm-lin-rx-tag qm-lin-rx-tag-active' },
    increase: { label: 'Increase', cls: 'qm-lin-rx-tag qm-lin-rx-tag-info' },
    decrease: { label: 'Decrease', cls: 'qm-lin-rx-tag qm-lin-rx-tag-warning' },
    discontinue: {
      label: 'Discontinue',
      cls: 'qm-lin-rx-tag qm-lin-rx-tag-discontinued',
    },
    unclear: { label: 'Unclear', cls: 'qm-lin-rx-tag qm-lin-rx-tag-pending' },
  };
  const m = meta[action];
  return <span className={m.cls}>{m.label}</span>;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function rxIdFor(ix: number): string {
  return `R-${String(ix + 1).padStart(3, '0')}`;
}

function tallyForRx(
  warnings: RailWarning[],
  rxId: string
): Record<RailSeverity, number> {
  const tally: Record<RailSeverity, number> = {
    critical: 0,
    serious: 0,
    moderate: 0,
    info: 0,
  };
  for (const w of warnings) {
    if (w.rxId === rxId) tally[w.severity] += 1;
  }
  return tally;
}

// Best-effort frequency parse out of the `sig`. Worker doesn't yet
// emit a structured `frequency` field, so we degrade gracefully.
function deriveFreq(sig?: string | null): string | null {
  if (!sig) return null;
  const matches = [
    /\b(BID|TID|QID|QHS|QAM|QPM|PRN|q\d+\s*(?:h|hr|hrs))\b/i,
    /\bonce daily\b/i,
    /\btwice daily\b/i,
    /\bevery\s+\d+\s+hours?\b/i,
  ];
  for (const re of matches) {
    const m = sig.match(re);
    if (m) return m[0].toUpperCase();
  }
  return null;
}

// ---------------------------------------------------------------------------
// Exported helper kept for back-compat with the visit-ready-view tab bar.
// ---------------------------------------------------------------------------

export function rxTabWarningLevel(rx: unknown): 'critical' | 'any' | null {
  const blob = (rx as RxBlob | null) ?? null;
  const warnings = blob?.warnings ?? [];
  if (warnings.length === 0) return null;
  return warnings.some((w) => w.severity === 'critical') ? 'critical' : 'any';
}
