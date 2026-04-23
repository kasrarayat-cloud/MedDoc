'use client';

// ============================================================================
// RxWarningCard — HANDOFF docs/design/rx_warning_handoff/DESIGN_SPEC.md
// ----------------------------------------------------------------------------
// Three severities (critical / warning / info) rendered from one
// component + CSS modifier classes. Info auto-compacts to 3 regions;
// critical + warning render all 8. Keyboard shortcuts are card-scoped
// (only fire while the card contains document.activeElement) so every
// open warning doesn't steal keys from the app-wide ⌘K / G-prefix
// shortcuts.
//
// Override flow for critical is escalated to <OverrideConfirmModal>
// which writes to the RxWarningOverride audit table. See
// lib/rx-warning-audit.ts for the server action contract.
//
// Rich fields (heard/guess/risks/nextStep/details/source) are optional
// — the worker doesn't emit them yet (Phase 2). When absent, the card
// degrades to header + action tile + action row. Never throws on
// missing data.
// ============================================================================

import { useCallback, useEffect, useId, useRef, useState } from 'react';
import type { ReactNode } from 'react';

import { Ic } from '@/components/ui/icon';
import { CLINICAL_RULES_VERSION } from '@/config/clinical-rules';
import { OverrideConfirmModal } from './override-confirm-modal';

export type Severity = 'critical' | 'warning' | 'info';
export type ActionKind = 'ban' | 'alert' | 'info';

export interface RiskFragment {
  t: string;
  /** Bold = rendered as a severity-tinted pill on the primary line,
   *  as a bold fragment on the outcome line. */
  b?: boolean;
}
export interface RiskLine {
  parts: RiskFragment[];
  outcome?: RiskFragment[];
}

export interface RxWarning {
  /** Audit identifier — stable hash of (severity + headline + line#)
   *  emitted by the worker. The card never generates this itself. */
  id: string;
  /** 1-based line number in the SOAP note's Rx section. */
  rxLineNumber: number;
  sev: Severity;
  headline: string;
  action?: string;
  actionKind?: ActionKind;
  heard?: string;
  guess?: string;
  /** Render the confidence chip only when BOTH are present. */
  transcriberConfidence?: number;
  confidenceThreshold?: number;
  risks?: RiskLine[];
  nextStep?: string;
  details?: string[];
  /** Free-text source citation, e.g. "Transcript 14:22". */
  source?: string;
}

export interface RxWarningCardProps {
  warning: RxWarning;
  visitId: string;
  /** Details panel initial state. Defaults to closed. */
  defaultOpen?: boolean;
  /** Hides the dismiss X when omitted. Critical severity never gets
   *  dismiss regardless of this prop. */
  onDismiss?: () => void;
  onEdit?: () => void;
  onCall?: () => void;
  onAcknowledge?: () => void;
  /** Fires after a successful override audit write. */
  onOverridden?: (auditId: string) => void;
}

const SEV_CLASS: Record<Severity, string> = {
  critical: 'qm-warn',
  warning: 'qm-warn qm-warn-sev-warning',
  info: 'qm-warn qm-warn-sev-info',
};
const SEV_LABEL: Record<Severity, string> = {
  critical: 'Critical',
  warning: 'Warning',
  info: 'Info',
};
const SEV_ROLE: Record<Severity, 'alert' | 'status' | 'note'> = {
  critical: 'alert',
  warning: 'status',
  info: 'note',
};
const SEV_LIVE: Record<Severity, 'assertive' | 'polite' | 'off'> = {
  critical: 'assertive',
  warning: 'polite',
  info: 'off',
};

function resolveActionKind(sev: Severity, explicit?: ActionKind): ActionKind {
  if (explicit) return explicit;
  if (sev === 'critical') return 'ban';
  if (sev === 'warning') return 'alert';
  return 'info';
}

function actionIcon(kind: ActionKind): ReactNode {
  if (kind === 'ban') return <Ic.close width={18} height={18} />;
  if (kind === 'alert') return <Ic.alert width={18} height={18} />;
  return <Ic.info width={18} height={18} />;
}

export function RxWarningCard({
  warning,
  visitId,
  defaultOpen = false,
  onDismiss,
  onEdit,
  onCall,
  onAcknowledge,
  onOverridden,
}: RxWarningCardProps) {
  const [detailsOpen, setDetailsOpen] = useState<boolean>(defaultOpen);
  const [modalOpen, setModalOpen] = useState<boolean>(false);
  const cardRef = useRef<HTMLDivElement | null>(null);
  const overrideBtnRef = useRef<HTMLButtonElement | null>(null);
  const headlineId = useId();
  const detailsId = useId();

  const isCritical = warning.sev === 'critical';
  const isWarning = warning.sev === 'warning';
  const isInfo = warning.sev === 'info';
  const compact = isInfo;
  const showDismiss = !isCritical && typeof onDismiss === 'function';
  const hasDetails = !isInfo && Boolean(warning.details?.length);
  const actionKind = resolveActionKind(warning.sev, warning.actionKind);

  const openOverride = useCallback(() => {
    setModalOpen(true);
  }, []);
  const toggleDetails = useCallback(() => {
    setDetailsOpen((v) => !v);
  }, []);

  // ── Card-scoped keyboard shortcuts ──
  //
  // Listens on document keydown but short-circuits when (a) the modal
  // is open, (b) the card doesn't contain the active element, (c) any
  // modifier is held, (d) the target is a form field (textarea/input).
  useEffect(() => {
    if (modalOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
      const card = cardRef.current;
      if (!card || !card.contains(document.activeElement)) return;
      const tag = (e.target as HTMLElement | null)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

      switch (e.key) {
        case '?':
          if (hasDetails) {
            e.preventDefault();
            toggleDetails();
          }
          break;
        case 'E':
        case 'e':
          if ((isCritical || isWarning) && onEdit) {
            e.preventDefault();
            onEdit();
          }
          break;
        case 'C':
        case 'c':
          if ((isCritical || isWarning) && onCall) {
            e.preventDefault();
            onCall();
          }
          break;
        case 'A':
        case 'a':
          if (isWarning && onAcknowledge) {
            e.preventDefault();
            onAcknowledge();
          }
          break;
        case 'O':
        case 'o':
          if (isCritical) {
            e.preventDefault();
            openOverride();
          }
          break;
        case 'D':
        case 'd':
          if (isInfo && onDismiss) {
            e.preventDefault();
            onDismiss();
          }
          break;
        case 'Escape':
          if (detailsOpen) {
            e.preventDefault();
            setDetailsOpen(false);
          } else if (isInfo && onDismiss) {
            e.preventDefault();
            onDismiss();
          }
          break;
      }
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [
    modalOpen,
    detailsOpen,
    hasDetails,
    isCritical,
    isWarning,
    isInfo,
    onEdit,
    onCall,
    onAcknowledge,
    onDismiss,
    openOverride,
    toggleDetails,
  ]);

  const confidencePct =
    typeof warning.transcriberConfidence === 'number' &&
    typeof warning.confidenceThreshold === 'number'
      ? Math.round(warning.transcriberConfidence * 100)
      : null;

  const sourceCitation = (() => {
    const src = warning.source?.trim();
    if (!src) return `clinical rules ${CLINICAL_RULES_VERSION}`;
    return `${src} · clinical rules ${CLINICAL_RULES_VERSION}`;
  })();

  return (
    <>
      <section
        ref={cardRef}
        role={SEV_ROLE[warning.sev]}
        aria-live={SEV_LIVE[warning.sev]}
        aria-labelledby={headlineId}
        className={SEV_CLASS[warning.sev]}
        data-severity={warning.sev}
      >
        {/* ── Region 1 — Header ── */}
        <div className="qm-warn-head">
          <div className="qm-warn-icon" aria-hidden>
            <Ic.alert width={18} height={18} />
          </div>
          <span className="qm-warn-badge" aria-hidden>
            {SEV_LABEL[warning.sev]}
          </span>
          <span className="qm-warn-field">
            {`Rx · Line ${warning.rxLineNumber}`}
          </span>
          <span />
          {showDismiss ? (
            <button
              type="button"
              onClick={onDismiss}
              className="qm-warn-dismiss"
              aria-label="Dismiss warning"
            >
              <Ic.close width={14} height={14} />
            </button>
          ) : (
            <span />
          )}
          <h3 id={headlineId} className="qm-warn-headline">
            <span
              style={{
                position: 'absolute',
                width: 1,
                height: 1,
                margin: -1,
                padding: 0,
                overflow: 'hidden',
                clip: 'rect(0,0,0,0)',
                whiteSpace: 'nowrap',
                border: 0,
              }}
            >
              {SEV_LABEL[warning.sev]}.{' '}
            </span>
            {warning.headline}
          </h3>
        </div>

        {!compact && warning.action && (
          <div className="qm-warn-body">
            {/* ── Region 3 — Action tile ── */}
            <div className="qm-warn-action">
              <span className="qm-warn-action-icon" aria-hidden>
                {actionIcon(actionKind)}
              </span>
              <span>{warning.action}</span>
            </div>

            {/* ── Region 4 — Transcribed heard → guess ── */}
            {(warning.heard || warning.guess) && (
              <div className="qm-warn-transcribed">
                {warning.heard ? (
                  <div className="qm-warn-field-block">
                    <div className="qm-warn-field-label">Heard</div>
                    <div className="qm-warn-field-value">
                      &ldquo;{warning.heard}&rdquo;
                      {confidencePct != null && (
                        <span
                          className="qm-warn-confidence"
                          title={`Transcriber confidence ${confidencePct}% (threshold ${Math.round(
                            (warning.confidenceThreshold ?? 0) * 100
                          )}%)`}
                        >
                          {confidencePct}%
                        </span>
                      )}
                    </div>
                  </div>
                ) : (
                  <span />
                )}
                <span className="qm-warn-transcribed-arrow" aria-hidden>
                  →
                </span>
                {warning.guess ? (
                  <div className="qm-warn-field-block">
                    <div className="qm-warn-field-label">Phonetic guess</div>
                    <div className="qm-warn-field-value">{warning.guess}</div>
                  </div>
                ) : (
                  <span />
                )}
              </div>
            )}

            {/* ── Region 5 — Patient-specific risks ── */}
            {warning.risks && warning.risks.length > 0 && (
              <div className="qm-warn-risks">
                <div className="qm-warn-mini-label">
                  {`Patient-specific risks · ${warning.risks.length}`}
                </div>
                {warning.risks.map((risk, i) => (
                  <div key={i} className="qm-warn-risk">
                    <span className="qm-warn-risk-dot" aria-hidden />
                    <div className="qm-warn-risk-body">
                      <div className="qm-warn-risk-primary">
                        {risk.parts.map((p, j) =>
                          p.b ? (
                            <span key={j} className="qm-warn-pill">
                              {p.t}
                            </span>
                          ) : (
                            <span key={j}>{p.t}</span>
                          )
                        )}
                      </div>
                      {risk.outcome && risk.outcome.length > 0 && (
                        <div className="qm-warn-risk-outcome">
                          {'→ '}
                          {risk.outcome.map((p, j) =>
                            p.b ? (
                              <span key={j} className="qm-warn-outcome-bold">
                                {p.t}
                              </span>
                            ) : (
                              <span key={j}>{p.t}</span>
                            )
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ── Region 6 — Next step ── */}
            {warning.nextStep && (
              <div className="qm-warn-next">
                <span className="qm-warn-next-icon" aria-hidden>
                  <Ic.info width={16} height={16} />
                </span>
                <span className="qm-warn-next-label">Next</span>
                <span>{warning.nextStep}</span>
              </div>
            )}
          </div>
        )}

        {/* ── Region 7 — Details toggle + body ── */}
        {hasDetails && (
          <>
            <button
              type="button"
              className="qm-warn-details-toggle"
              aria-expanded={detailsOpen}
              aria-controls={detailsId}
              onClick={toggleDetails}
            >
              <span className="qm-warn-details-chev" aria-hidden>
                <Ic.chevRight width={13} height={13} />
              </span>
              <span>
                {detailsOpen ? 'Hide clinical reasoning' : 'Show clinical reasoning'}
              </span>
              <span className="qm-warn-details-source">{sourceCitation}</span>
            </button>
            <div id={detailsId} className="qm-warn-details-body" hidden={!detailsOpen}>
              {warning.details?.map((para, i) => (
                <p key={i}>{para}</p>
              ))}
              {warning.source && (
                <div className="qm-warn-details-cite">
                  {`↳ ${warning.source} · clinical rules ${CLINICAL_RULES_VERSION}`}
                </div>
              )}
            </div>
          </>
        )}

        {/* ── Region 8 — Actions ── */}
        {!compact && (isCritical || isWarning) && (
          <div className="qm-warn-actions">
            {onEdit && (
              <button
                type="button"
                onClick={onEdit}
                className="qm-warn-btn qm-warn-btn-primary"
              >
                {isCritical ? 'Edit medication' : 'Edit'}
                <span className="qm-warn-kbd" aria-hidden>
                  E
                </span>
              </button>
            )}
            {onCall && (
              <button type="button" onClick={onCall} className="qm-warn-btn">
                <Ic.mic width={13} height={13} aria-hidden />
                Call provider
                <span className="qm-warn-kbd" aria-hidden>
                  C
                </span>
              </button>
            )}
            <span className="qm-warn-actions-spacer" />
            {isCritical && (
              <button
                ref={overrideBtnRef}
                type="button"
                onClick={openOverride}
                className="qm-warn-btn"
              >
                Override &amp; sign anyway
                <span className="qm-warn-kbd" aria-hidden>
                  O
                </span>
              </button>
            )}
            {isWarning && onAcknowledge && (
              <button
                type="button"
                onClick={onAcknowledge}
                className="qm-warn-btn"
              >
                Acknowledge
                <span className="qm-warn-kbd" aria-hidden>
                  A
                </span>
              </button>
            )}
          </div>
        )}

        {isInfo && onDismiss && (
          <div className="qm-warn-actions">
            <span className="qm-warn-actions-spacer" />
            <button type="button" onClick={onDismiss} className="qm-warn-btn">
              Dismiss
              <span className="qm-warn-kbd" aria-hidden>
                D
              </span>
            </button>
          </div>
        )}
      </section>

      {isCritical && (
        <OverrideConfirmModal
          open={modalOpen}
          onOpenChange={(next) => {
            setModalOpen(next);
            if (!next) {
              // Return focus to the Override button.
              overrideBtnRef.current?.focus();
            }
          }}
          warning={{
            id: warning.id,
            rxLineNumber: warning.rxLineNumber,
            sev: warning.sev,
            headline: warning.headline,
            action: warning.action,
          }}
          visitId={visitId}
          onSuccess={onOverridden}
        />
      )}
    </>
  );
}
