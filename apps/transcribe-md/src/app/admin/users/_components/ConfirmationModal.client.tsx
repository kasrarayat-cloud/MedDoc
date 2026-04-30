'use client';

// ============================================================================
// Email-to-confirm modal — gate for destructive admin actions
// ----------------------------------------------------------------------------
// Three kinds: soft_delete, grant_admin, revoke_admin. Caller wires
// `onConfirm` to the matching POST endpoint. The modal tracks its own
// "in flight" state so the user can't double-click the destructive
// button while the request is in flight.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the slate-on-white modal.
// Clinician branch renders the same shape using `.qm-cl-card`,
// `.qm-cl-input`, `.qm-cl-btn-*`, and the cream/coral palette.
// State machine + email-match validation are unchanged.
// ============================================================================

import { useEffect, useRef, useState } from 'react';
import { AlertTriangle } from 'lucide-react';

import type { ConfirmKind } from '../_types';

type ConfirmationModalTheme = 'legacy' | 'clinician';

interface Props {
  kind: ConfirmKind;
  user: { email: string; fullName: string };
  onCancel: () => void;
  /** Returns a Promise so the modal can show a busy state until the
   *  server commits. The caller is responsible for surfacing toast on
   *  success/failure. */
  onConfirm: () => Promise<void>;
  theme?: ConfirmationModalTheme;
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

export default function ConfirmationModal({ kind, user, onCancel, onConfirm, theme = 'legacy' }: Props) {
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

  if (theme === 'clinician') {
    return (
      <>
        <div
          onClick={busy ? undefined : onCancel}
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 50,
            background: 'rgba(43, 38, 32, 0.32)',
            backdropFilter: 'blur(2px)',
          }}
        />
        <div
          role="dialog"
          aria-label={copy.title}
          className="qm-cl-card"
          style={{
            position: 'fixed',
            left: '50%',
            top: '50%',
            zIndex: 50,
            width: 440,
            maxWidth: 'calc(100vw - 32px)',
            transform: 'translate(-50%, -50%)',
            padding: 0,
            overflow: 'hidden',
          }}
        >
          <div style={{ borderBottom: '1px solid var(--line)', padding: '16px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <div
                style={{
                  marginTop: 2,
                  display: 'inline-flex',
                  width: 24,
                  height: 24,
                  flexShrink: 0,
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 999,
                  background: 'var(--coral-tint)',
                  color: 'var(--coral-deep)',
                }}
              >
                <AlertTriangle style={{ width: 14, height: 14 }} strokeWidth={2.25} />
              </div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>{copy.title}</div>
                <div style={{ marginTop: 4, fontSize: 12, lineHeight: 1.5, color: 'var(--ink-2)' }}>
                  {copy.body}
                </div>
              </div>
            </div>
          </div>
          <div style={{ padding: '16px 20px' }}>
            <label className="qm-cl-section-label" style={{ display: 'block', marginBottom: 6 }}>
              Type the user&apos;s email to confirm
            </label>
            <div className="qm-cl-mono" style={{ marginBottom: 8, fontSize: 12, color: 'var(--ink-2)' }}>
              {user.email}
            </div>
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
              className="qm-cl-input qm-cl-mono"
              style={{
                fontSize: 13,
                ...(typed.length > 0 && !enabled
                  ? { borderColor: 'var(--coral)', boxShadow: '0 0 0 3px var(--coral-tint)' }
                  : {}),
              }}
            />
          </div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'flex-end',
              gap: 8,
              borderTop: '1px solid var(--line)',
              background: 'var(--cream-2)',
              padding: '12px 20px',
            }}
          >
            <button
              type="button"
              onClick={onCancel}
              disabled={busy}
              className="qm-cl-btn qm-cl-btn-ghost"
              style={{ height: 32, padding: '0 14px', fontSize: 12, opacity: busy ? 0.5 : 1 }}
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={!enabled || busy}
              onClick={handleConfirm}
              className="qm-cl-btn"
              style={{
                height: 32,
                padding: '0 14px',
                fontSize: 12,
                fontWeight: 500,
                background: enabled && !busy ? 'var(--coral-deep)' : 'var(--coral-tint)',
                color: enabled && !busy ? 'var(--cream-card)' : 'var(--coral-deep)',
                cursor: enabled && !busy ? 'pointer' : 'not-allowed',
                gap: 6,
              }}
            >
              <AlertTriangle style={{ width: 12, height: 12 }} />
              {busy ? 'Working…' : copy.cta}
            </button>
          </div>
        </div>
      </>
    );
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
