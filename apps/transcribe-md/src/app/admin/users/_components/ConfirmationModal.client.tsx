'use client';

// ============================================================================
// Email-to-confirm modal — gate for destructive admin actions
// ----------------------------------------------------------------------------
// Three kinds: soft_delete, grant_admin, revoke_admin. Caller wires
// `onConfirm` to the matching POST endpoint. The modal tracks its own
// "in flight" state so the user can't double-click the destructive
// button while the request is in flight.
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
        <span className="font-medium text-slate-800">retained</span> per HIPAA
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
        This user will gain access to <span className="font-medium text-slate-800">all</span>{' '}
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
        className="fixed inset-0 z-50 bg-slate-900/40"
      />
      <div
        role="dialog"
        aria-label={copy.title}
        className="fixed left-1/2 top-1/2 z-50 w-[440px] max-w-[calc(100vw-32px)] -translate-x-1/2 -translate-y-1/2 rounded-md border border-slate-200 bg-white shadow-xl"
      >
        <div className="border-b border-slate-100 px-5 py-4">
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-rose-50 ring-1 ring-rose-200">
              <AlertTriangle className="h-3.5 w-3.5 text-rose-600" strokeWidth={2.25} />
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900">{copy.title}</div>
              <div className="mt-1 text-xs leading-relaxed text-slate-600">{copy.body}</div>
            </div>
          </div>
        </div>
        <div className="px-5 py-4">
          <label className="mb-1.5 block text-[11px] uppercase tracking-wide text-slate-500">
            Type the user&apos;s email to confirm
          </label>
          <div className="mb-2 font-mono text-xs tabular-nums text-slate-700">{user.email}</div>
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
              'block h-9 w-full rounded-md border bg-white px-3 py-1.5 font-mono text-sm text-slate-900 placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 ' +
              (typed.length > 0 && !enabled
                ? 'border-rose-300 focus-visible:ring-rose-300'
                : 'border-slate-200 focus-visible:ring-slate-300')
            }
          />
        </div>
        <div className="flex items-center justify-end gap-2 border-t border-slate-100 bg-slate-50/40 px-5 py-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="inline-flex h-8 items-center justify-center rounded-md px-3 text-xs font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={!enabled || busy}
            onClick={handleConfirm}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md bg-rose-600 px-3 text-xs font-medium text-white transition-colors hover:bg-rose-700 disabled:cursor-not-allowed disabled:bg-rose-300"
          >
            <AlertTriangle className="h-3 w-3" />
            {busy ? 'Working…' : copy.cta}
          </button>
        </div>
      </div>
    </>
  );
}
