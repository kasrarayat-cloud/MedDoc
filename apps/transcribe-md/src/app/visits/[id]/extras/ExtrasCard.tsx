'use client';

// ============================================================================
// ExtrasCard — shared card scaffold for the Phase 5.1 EXTRAS V4 stream.
// ----------------------------------------------------------------------------
// Each Extras tab category (demographics, vitals, allergies, ...) renders
// inside this scaffold. The scaffold owns the standard head row (icon +
// title + sub-eyebrow + count pill + edit button) and the body / foot
// containers. Per-category visual layout lives in the consumer.
//
// Read-only mode: when `readonly` is true, the Edit button is hidden so
// signed visits stay locked.
// ============================================================================

import type { ReactNode } from 'react';
import { cn } from '@/lib/cn';

export type ExtrasCardCountTone = 'default' | 'sage' | 'warn' | 'danger';

interface ExtrasCardProps {
  /** Category emoji rendered in the head icon tile. */
  icon: ReactNode;
  /** Title (Inter 16px). */
  title: string;
  /** Mono uppercase eyebrow rendered below the title. */
  sub?: string;
  /** Count pill text on the right. Tone controls colour. */
  count?: string | null;
  countTone?: ExtrasCardCountTone;
  /** Edit button label. Defaults to "Edit". */
  editLabel?: string;
  /** Click handler for the edit button. When omitted, the button is
   *  rendered but non-actionable (still keyboard-focusable for parity
   *  with the static mock). */
  onEdit?: () => void;
  /** When true, the edit button is hidden entirely. Used for signed
   *  visits (readonly = true) and for cards that have no edit affordance
   *  (e.g. audit log uses a custom "View all" button instead). */
  hideEdit?: boolean;
  /** Marks the card as the focused / recently-edited one (sage left
   *  border accent). */
  focused?: boolean;
  /** Body slot. */
  children: ReactNode;
  /** Optional foot row for "+ Add …" + secondary metadata. */
  foot?: ReactNode;
}

export function ExtrasCard({
  icon,
  title,
  sub,
  count,
  countTone = 'default',
  editLabel = 'Edit',
  onEdit,
  hideEdit,
  focused,
  children,
  foot,
}: ExtrasCardProps) {
  const countCls =
    countTone === 'sage'
      ? 'qm-lin-extras-count-pill qm-lin-extras-count-pill--sage'
      : countTone === 'warn'
        ? 'qm-lin-extras-count-pill qm-lin-extras-count-pill--warn'
        : countTone === 'danger'
          ? 'qm-lin-extras-count-pill qm-lin-extras-count-pill--danger'
          : 'qm-lin-extras-count-pill';

  return (
    <article
      className={cn(
        'qm-lin-extras-card',
        focused && 'qm-lin-extras-card--focus'
      )}
    >
      <header className="qm-lin-extras-head">
        <div className="qm-lin-extras-head-left">
          <span className="qm-lin-extras-icon" aria-hidden>
            {icon}
          </span>
          <div className="qm-lin-extras-title-block">
            <h2 className="qm-lin-extras-title">{title}</h2>
            {sub && <span className="qm-lin-extras-sub">{sub}</span>}
          </div>
        </div>
        <div className="qm-lin-extras-head-right">
          {count && <span className={countCls}>{count}</span>}
          {!hideEdit && (
            <button
              type="button"
              className="qm-lin-extras-edit-btn"
              onClick={onEdit}
              disabled={!onEdit}
              aria-label={`${editLabel} ${title.toLowerCase()}`}
            >
              {editLabel}
            </button>
          )}
        </div>
      </header>
      <div className="qm-lin-extras-body">{children}</div>
      {foot && <footer className="qm-lin-extras-foot">{foot}</footer>}
    </article>
  );
}

// ---------------------------------------------------------------------------
// KV row — used by Demographics + Visit metadata cards.
// ---------------------------------------------------------------------------

interface KvProps {
  label: string;
  /** Primary value text. */
  value: ReactNode;
  /** Optional secondary text rendered next to the value, muted. */
  secondary?: ReactNode;
  /** When true, render the value in mono / tabular-nums (IDs, MRN,
   *  durations). */
  mono?: boolean;
}

export function Kv({ label, value, secondary, mono }: KvProps) {
  const isEmpty =
    value == null ||
    (typeof value === 'string' && value.trim().length === 0);
  return (
    <div className="qm-lin-extras-kv">
      <span className="qm-lin-extras-kv-key">{label}</span>
      <span className="qm-lin-extras-kv-val">
        {isEmpty ? (
          <span className="qm-lin-extras-kv-secondary">—</span>
        ) : mono ? (
          <span className="qm-lin-extras-kv-mono">{value}</span>
        ) : (
          value
        )}
        {secondary != null && (
          <span className="qm-lin-extras-kv-secondary">· {secondary}</span>
        )}
      </span>
    </div>
  );
}
