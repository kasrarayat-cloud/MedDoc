'use client';

// ============================================================================
// RxWarningsRail — Phase 5.1 Linear V1 V3 split-pane right rail
// ----------------------------------------------------------------------------
// Severity-grouped sidebar that lives next to the prescription list.
// Renders four severity groups in fixed order (CRITICAL → SERIOUS →
// MODERATE → INFO). Each warning uses the protected
// `.qm-warn-{critical|serious|moderate|info}` class names with the
// `.qm-warn-icon` / `.qm-warn-head` / `.qm-warn-body` slots — those
// names are PART OF THE QUILLMD CONTRACT and stay byte-identical.
//
// Highlighting: when an Rx row is "active" upstream, the rail filters
// to that Rx's `data-rxid` and applies an inset sage shadow on
// matching warnings. Clicking the rail header's "All / R-NNN" filter
// also drives this.
// ============================================================================

import { useMemo } from 'react';
import { Ic } from '@/components/ui/icon';

// ---------------------------------------------------------------------------
// Wire types — re-declared locally so the worker bundle doesn't ship
// to the browser. Mirrors Layer 7c output exactly.
// ---------------------------------------------------------------------------

export type RailSeverity = 'critical' | 'serious' | 'moderate' | 'info';

export interface RailWarning {
  /** Stable identifier — derived from a hash of (severity + headline + line#). */
  id: string;
  severity: RailSeverity;
  /** Short headline rendered into `.qm-warn-head`. */
  headline: string;
  /** Long-form body rendered into `.qm-warn-body`. */
  body: string;
  /** Rx ID reference (e.g. "R-001") rendered as a chip beside the headline. */
  rxId: string;
}

interface RxWarningsRailProps {
  warnings: RailWarning[];
  /** When set, dim non-matching warnings + sage-rail the matching ones. */
  activeRxId: string | null;
  /** Called when the user clicks a warning to focus its Rx in the left pane. */
  onWarningFocus?: (rxId: string) => void;
}

const SEVERITY_ORDER: RailSeverity[] = ['critical', 'serious', 'moderate', 'info'];
const SEVERITY_LABEL: Record<RailSeverity, string> = {
  critical: 'Critical',
  serious: 'Serious',
  moderate: 'Moderate',
  info: 'Info',
};
const SEVERITY_ROLE: Record<RailSeverity, 'alert' | 'note'> = {
  critical: 'alert',
  serious: 'alert',
  moderate: 'note',
  info: 'note',
};
const SEVERITY_ICON: Record<RailSeverity, '⚠' | 'ⓘ'> = {
  critical: '⚠',
  serious: '⚠',
  moderate: '⚠',
  info: 'ⓘ',
};

export function RxWarningsRail({
  warnings,
  activeRxId,
  onWarningFocus,
}: RxWarningsRailProps) {
  const grouped = useMemo(() => {
    const buckets: Record<RailSeverity, RailWarning[]> = {
      critical: [],
      serious: [],
      moderate: [],
      info: [],
    };
    for (const w of warnings) {
      buckets[w.severity].push(w);
    }
    return buckets;
  }, [warnings]);

  const total = warnings.length;
  const hasCritical = grouped.critical.length > 0;

  if (total === 0) {
    return (
      <aside className="qm-lin-rx-rail" aria-label="Interaction warnings">
        <div className="qm-lin-rx-rail-head">
          <div className="qm-lin-rx-rail-title">Interactions · 0 active</div>
        </div>
        <div className="qm-lin-rx-rail-empty">
          <Ic.check width={14} height={14} aria-hidden />
          <span>No interaction warnings</span>
        </div>
      </aside>
    );
  }

  return (
    <aside className="qm-lin-rx-rail" aria-label="Interaction warnings">
      <div className="qm-lin-rx-rail-head">
        <div className="qm-lin-rx-rail-title">
          {hasCritical && <span className="qm-lin-rx-rail-pulse" aria-hidden />}
          Interactions · {total} active
        </div>
        <div className="qm-lin-rx-rail-filter" aria-live="polite">
          {activeRxId ? activeRxId : 'All severities'}
        </div>
      </div>

      {SEVERITY_ORDER.map((sev) => {
        const list = grouped[sev];
        if (list.length === 0) return null;
        return (
          <div key={sev} className="qm-lin-rx-rail-group">
            <div className="qm-lin-rx-rail-group-h">
              <div className={`qm-lin-rx-rail-group-l qm-lin-rx-rail-group-l-${sev}`}>
                {SEVERITY_LABEL[sev]}
              </div>
              <div className="qm-lin-rx-rail-group-n">
                {list.length} {list.length === 1 ? 'issue' : 'issues'}
              </div>
            </div>

            {list.map((w) => {
              const matches = activeRxId !== null && activeRxId === w.rxId;
              const dimmed = activeRxId !== null && !matches;
              const className = `qm-warn-${sev}`;
              return (
                <div
                  key={w.id}
                  className={className}
                  data-rxid={w.rxId}
                  data-active={matches ? 'true' : 'false'}
                  data-dimmed={dimmed ? 'true' : 'false'}
                  role={SEVERITY_ROLE[sev]}
                  onClick={() => onWarningFocus?.(w.rxId)}
                  style={{ cursor: onWarningFocus ? 'pointer' : 'default' }}
                >
                  <div className="qm-warn-icon" aria-hidden>
                    {SEVERITY_ICON[sev]}
                  </div>
                  <div>
                    <div className="qm-warn-head">
                      {w.headline}
                      <span className="qm-warn-rx-id">{w.rxId}</span>
                    </div>
                    <div className="qm-warn-body">{w.body}</div>
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}
    </aside>
  );
}
