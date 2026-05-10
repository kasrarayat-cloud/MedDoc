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
//
// Critical-severity override flow (added Round 4 fix):
// the sign-API guard at /api/visits/[id]/sign requires one
// `RxWarningOverride` row per critical warning before allowing
// READY → SIGNED. Each critical warning gets an "Override…" button
// that opens <OverrideConfirmModal>; on success, the rail flips
// that warning's slot to a green "✓ Overridden" chip + the rail
// notifies the parent via `onOverrideRecorded(warningId)` so the
// parent can update its overriddenIds state. The full override
// stack (modal + recordOverride server action + audit table) was
// shipped in Round 3 PR-D but the bridge from the production rail
// to the modal was missing — doctors hit the 422 toast with no UI
// path forward.
// ============================================================================

import { useMemo, useState } from 'react';
import { Ic } from '@/components/ui/icon';
import { OverrideConfirmModal } from '@/components/rx/override-confirm-modal';

// ---------------------------------------------------------------------------
// Wire types — re-declared locally so the worker bundle doesn't ship
// to the browser. Mirrors Layer 7c output exactly.
// ---------------------------------------------------------------------------

export type RailSeverity = 'critical' | 'serious' | 'moderate' | 'info';

export interface RailWarning {
  /** Stable identifier — derived from a hash of (severity + headline + line#).
   *  Used both as the React key and as the warningId in
   *  OverrideConfirmModal / recordOverride; these MUST match for the
   *  sign-API gate's per-warning-override count to work correctly. */
  id: string;
  severity: RailSeverity;
  /** Short headline rendered into `.qm-warn-head`. */
  headline: string;
  /** Long-form body rendered into `.qm-warn-body`. */
  body: string;
  /** Rx ID reference (e.g. "R-001") rendered as a chip beside the headline. */
  rxId: string;
  /** 1-based prescription line number for the override-modal payload.
   *  Parsed by the rail's parent from the rxId's "R-NNN" suffix; the
   *  override server action requires a number, the rail needs a string
   *  for display. Kept as separate fields rather than re-parsing in the
   *  rail. */
  rxLineNumber: number;
}

interface RxWarningsRailProps {
  warnings: RailWarning[];
  /** When set, dim non-matching warnings + sage-rail the matching ones. */
  activeRxId: string | null;
  /** Called when the user clicks a warning to focus its Rx in the left pane. */
  onWarningFocus?: (rxId: string) => void;
  /** Visit ID — passed into OverrideConfirmModal for the recordOverride
   *  server-action payload. Required when `warnings` contains any
   *  critical-severity entries (those get an Override button); pass
   *  the empty string OR an unused value for non-critical-only data
   *  if you must, but in practice every caller has a real visitId. */
  visitId: string;
  /** warningIds for which an override has already been recorded — flips
   *  the rail from Override-button to ✓ Overridden chip on those rows.
   *  Initial value comes from the page-level prisma.rxWarningOverride
   *  query so reloads + cross-tab persistence "just work"; subsequent
   *  in-session recordings flow through onOverrideRecorded back to
   *  the parent's state. */
  overriddenIds: Set<string>;
  /** Fired when OverrideConfirmModal succeeds — parent merges the
   *  warningId into its overriddenIds state so the chip swap renders. */
  onOverrideRecorded?: (warningId: string) => void;
  /** Visit is SIGNED → suppress override affordance (override-after-sign
   *  is a different audit path, not yet in scope). */
  readonly?: boolean;
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
  visitId,
  overriddenIds,
  onOverrideRecorded,
  readonly = false,
}: RxWarningsRailProps) {
  // The warningId of the row whose Override modal is currently open.
  // Single-modal-at-a-time pattern; opening a different warning closes
  // the prior one (Radix Dialog default).
  const [openWarningId, setOpenWarningId] = useState<string | null>(null);

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
              const isOverridden = overriddenIds.has(w.id);
              const showOverrideAction = sev === 'critical' && !readonly;
              return (
                <div
                  key={w.id}
                  className={className}
                  data-rxid={w.rxId}
                  data-warning-id={w.id}
                  data-overridden={isOverridden ? 'true' : 'false'}
                  data-active={matches ? 'true' : 'false'}
                  data-dimmed={dimmed ? 'true' : 'false'}
                  role={SEVERITY_ROLE[sev]}
                  onClick={() => onWarningFocus?.(w.rxId)}
                  style={{ cursor: onWarningFocus ? 'pointer' : 'default' }}
                >
                  <div className="qm-warn-icon" aria-hidden>
                    {SEVERITY_ICON[sev]}
                  </div>
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div className="qm-warn-head">
                      {w.headline}
                      <span className="qm-warn-rx-id">{w.rxId}</span>
                    </div>
                    <div className="qm-warn-body">{w.body}</div>
                    {showOverrideAction && (
                      <div
                        className="qm-warn-action"
                        // Click-bubbling guard: the warning row's onClick
                        // toggles Rx-focus; the override button is a
                        // separate intent.
                        onClick={(e) => e.stopPropagation()}
                      >
                        {isOverridden ? (
                          <span
                            className="qm-warn-overridden"
                            role="status"
                            aria-live="polite"
                          >
                            <span aria-hidden>✓</span>
                            <span>Overridden — sign cleared</span>
                          </span>
                        ) : (
                          <button
                            type="button"
                            className="qm-warn-override-btn"
                            onClick={() => setOpenWarningId(w.id)}
                            aria-label={`Override critical warning for ${w.headline}`}
                          >
                            Override…
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        );
      })}

      {/* Override modals — render one per critical warning that needs
          one. Radix Dialog handles single-open-at-a-time via the open
          prop; closed modals are inert. */}
      {grouped.critical
        .filter((w) => !readonly && !overriddenIds.has(w.id))
        .map((w) => (
          <OverrideConfirmModal
            key={`modal-${w.id}`}
            open={openWarningId === w.id}
            onOpenChange={(next) => {
              if (!next && openWarningId === w.id) setOpenWarningId(null);
            }}
            visitId={visitId}
            warning={{
              id: w.id,
              rxLineNumber: w.rxLineNumber,
              sev: w.severity,
              headline: w.headline,
              action: w.body,
            }}
            onSuccess={() => {
              onOverrideRecorded?.(w.id);
              setOpenWarningId(null);
            }}
          />
        ))}

      <style jsx>{`
        .qm-warn-action {
          margin-top: 10px;
          display: flex;
          align-items: center;
          gap: 10px;
        }
        .qm-warn-override-btn {
          display: inline-flex;
          align-items: center;
          padding: 5px 11px;
          font-family: var(--font-mono, ui-monospace, "SF Mono", Menlo, monospace);
          font-size: 11px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
          color: var(--color-linear-danger, #d4574a);
          background: rgba(212, 87, 74, 0.08);
          border: 1px solid rgba(212, 87, 74, 0.32);
          border-radius: 4px;
          cursor: pointer;
          transition: background 0.15s, border-color 0.15s;
        }
        .qm-warn-override-btn:hover {
          background: rgba(212, 87, 74, 0.14);
          border-color: rgba(212, 87, 74, 0.52);
        }
        .qm-warn-override-btn:focus-visible {
          outline: 2px solid var(--color-linear-sage, #7AA68C);
          outline-offset: 2px;
        }
        .qm-warn-overridden {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          font-family: var(--font-mono, ui-monospace, "SF Mono", Menlo, monospace);
          font-size: 11px;
          letter-spacing: 0.06em;
          color: var(--color-linear-sage, #7AA68C);
          background: rgba(122, 166, 140, 0.08);
          border: 1px solid rgba(122, 166, 140, 0.32);
          border-radius: 4px;
        }
      `}</style>
    </aside>
  );
}
