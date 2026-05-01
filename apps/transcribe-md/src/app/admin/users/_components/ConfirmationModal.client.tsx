'use client';

// ============================================================================
// Email-to-confirm modal — gate for destructive admin actions
// ----------------------------------------------------------------------------
// Three kinds: soft_delete, grant_admin, revoke_admin. Caller wires
// `onConfirm` to the matching POST endpoint. The modal tracks its own
// "in flight" state so the user can't double-click the destructive
// button while the request is in flight.
//
// Phase 5 (Linear V1 Faithful) — spotlight overlay on the dark canvas:
// `.qm-lin-spotlight` backdrop, hairline-bordered panel on
// linear-surface-2, sage primary CTA, danger-tinted icon plate. State
// machine + email-match validation are unchanged. The `theme` prop
// survives as an ignored compat shim.
// ============================================================================

import { useEffect, useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

import type { ConfirmKind } from '../_types';

interface Props {
  kind: ConfirmKind;
  user: { email: string; fullName: string };
  onCancel: () => void;
  /** Returns a Promise so the modal can show a busy state until the
   *  server commits. The caller is responsible for surfacing toast on
   *  success/failure. */
  onConfirm: () => Promise<void>;
  /** Phase 4 dual-theme prop. Phase 5 ignores it; kept for caller compat. */
  theme?: string;
}

const COPY: Record<
  ConfirmKind,
  { title: string; body: React.ReactNode; cta: string }
> = {
  soft_delete: {
    title: 'Soft delete user?',
    body: (
      <>
        The account will be marked deleted and the user will be unable to sign in.
        Their visits, PHI, and audit logs are{' '}
        <span className="font-medium text-linear-text">retained</span> per HIPAA
        §164.316(b)(2)(i). The row remains for the 7-year window; only a
        future purge sweep removes it.
      </>
    ),
    cta: 'Confirm soft delete',
  },
  grant_admin: {
    title: 'Grant admin privileges?',
    body: (
      <>
        This user will gain access to <span className="font-medium text-linear-text">all</span>{' '}
        admin pages including PHI, billing, audit logs, and user management. This
        action is itself logged to the audit trail.
      </>
    ),
    cta: 'Grant admin',
  },
  revoke_admin: {
    title: 'Revoke admin privileges?',
    body: (
      <>
        This user will lose access to admin pages immediately. Active admin sessions
        will be terminated. Their doctor account and visits are unaffected.
      </>
    ),
    cta: 'Revoke admin',
  },
};

export default function ConfirmationModal({ kind, user, onCancel, onConfirm }: Props) {
  const [typed, setTyped] = useState('');
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const copy = COPY[kind];

  useEffect(() => {
    inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !busy) onCancel();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onCancel, busy]);

  const enabled = typed.trim().toLowerCase() === user.email.toLowerCase();

  async function handleConfirm() {
    if (!enabled || busy) return;
    setBusy(true);
    try {
      await onConfirm();
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div
        onClick={busy ? undefined : onCancel}
        className="fixed inset-0 z-50 bg-black/60 backdrop-blur-[2px]"
      />
      <div
        role="dialog"
        aria-label={copy.title}
        className="fixed left-1/2 top-1/2 z-50 w-[440px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 overflow-hidden rounded-lg border border-linear-border-strong bg-linear-surface-2 shadow-[0_30px_80px_rgba(0,0,0,0.6)]"
      >
        <div className="border-b border-linear-border px-5 py-4">
          <div className="flex items-start gap-2.5">
            <div
              className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full"
              style={{
                background: 'rgba(212, 87, 74, 0.18)',
                color: 'var(--color-linear-danger)',
              }}
            >
              <AlertTriangle className="h-3.5 w-3.5" strokeWidth={2.25} />
            </div>
            <div>
              <div className="text-sm font-semibold text-linear-text">{copy.title}</div>
              <div className="mt-1 text-xs leading-relaxed text-linear-text-2">{copy.body}</div>
            </div>
          </div>
        </div>
        <div className="px-5 py-4">
          <label className="mb-1.5 block font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">
            Type the user&apos;s email to confirm
          </label>
          <div className="mb-2 font-mono text-xs tabular-nums text-linear-text-2">{user.email}</div>
          <input
            ref={inputRef}
            type="email"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && enabled && !busy) handleConfirm();
            }}
            placeholder="email@example.com"
            disabled={busy}
            className={
              'block h-9 w-full rounded-md border bg-linear-surface-1 px-3 py-1.5 font-mono text-sm text-linear-text placeholder:text-linear-text-3 focus-visible:outline-none focus-visible:ring-2 ' +
              (typed.length > 0 && !enabled
                ? 'border-linear-danger focus-visible:ring-linear-danger/40'
                : 'border-linear-border focus-visible:ring-linear-sage/40 focus-visible:border-linear-border-strong')
            }
          />
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-linear-border bg-linear-surface-1/40 px-5 py-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="qm-lin-btn"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!enabled || busy}
            onClick={handleConfirm}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md px-3 text-xs font-medium transition-colors disabled:cursor-not-allowed"
            style={{
              background: enabled && !busy
                ? 'var(--color-linear-danger)'
                : 'rgba(212, 87, 74, 0.18)',
              color: enabled && !busy ? '#fff' : 'var(--color-linear-danger)',
              opacity: enabled && !busy ? 1 : 0.7,
            }}
          >
            <AlertTriangle className="h-3 w-3" />
            {busy ? 'Working…' : copy.cta}
          </button>
        </div>
      </div>
    </>
  );
}
