'use client';

// ============================================================================
// AuditLogCard — last N events for this visit, most recent first.
// ----------------------------------------------------------------------------
// READ-ONLY surface. Events are derived from data already on the visit
// row (processingStartedAt / processingFinishedAt / signedAt) — we
// never WRITE to the audit log from this tab.
//
// `events` is the caller-supplied list of events. The caller is
// responsible for building the list (typically by inspecting the visit
// timeline) so this component stays display-only.
// ============================================================================

import { ExtrasCard } from './ExtrasCard';
import { formatLocalTime } from '@/lib/format-time';

export interface AuditEvent {
  /** ISO timestamp. Rendered as HH:MM in the viewer's local TZ. */
  at: string;
  /** Display label for the actor avatar (initials, "·" for system). */
  actorInitials: string;
  /** Actor full name. */
  actorName: string;
  /** When true, render the row in the muted "system" treatment. */
  system?: boolean;
  /** Verb phrase ("drafted SOAP plan section"). */
  verb: string;
  /** Optional mono-styled object suffix ("J20.9", "Whisper v3 · 6m04s"). */
  obj?: string | null;
}

interface Props {
  events: AuditEvent[];
  /** Pass true when the underlying timeline holds more entries than
   *  shown — drives the "View full audit · N events" link. */
  totalEvents?: number;
}

const MAX_ROWS = 8;

export function AuditLogCard({ events, totalEvents }: Props) {
  // Defensive: cap at MAX_ROWS visible. Sort newest-first if not
  // already sorted.
  const sorted = [...events].sort(
    (a, b) => new Date(b.at).getTime() - new Date(a.at).getTime()
  );
  const shown = sorted.slice(0, MAX_ROWS);
  const total = totalEvents ?? sorted.length;

  return (
    <ExtrasCard
      icon="📜"
      title="Audit log"
      sub={`Last ${shown.length} event${
        shown.length === 1 ? '' : 's'
      } · most recent first`}
      count={`${total} event${total === 1 ? '' : 's'}`}
      countTone="sage"
      editLabel="View all"
      hideEdit
    >
      {shown.length === 0 ? (
        <div className="qm-lin-extras-empty">
          No audit events recorded for this visit yet.
        </div>
      ) : (
        <div className="qm-lin-extras-audit">
          {shown.map((ev, i) => (
            <div
              key={`${ev.at}-${i}`}
              className={
                ev.system
                  ? 'qm-lin-extras-audit-ev qm-lin-extras-audit-ev--system'
                  : 'qm-lin-extras-audit-ev'
              }
            >
              <span className="qm-lin-extras-audit-ts">
                {formatLocalTime(ev.at)}
              </span>
              <span className="qm-lin-extras-audit-av">
                {ev.actorInitials}
              </span>
              <span className="qm-lin-extras-audit-text">
                <span className="qm-lin-extras-audit-actor">
                  {ev.actorName}
                </span>{' '}
                <span className="qm-lin-extras-audit-verb">{ev.verb}</span>
                {ev.obj && (
                  <>
                    {' '}
                    <span className="qm-lin-extras-audit-obj">{ev.obj}</span>
                  </>
                )}
              </span>
            </div>
          ))}
        </div>
      )}
    </ExtrasCard>
  );
}
