'use client';

// ============================================================================
// DismissModal — Phase 6H "false positive"
// ----------------------------------------------------------------------------
// Note + a "silence similar future threats" checkbox. The checkbox
// derives a silencePattern server-side based on the threat id (e.g.
// for an xdom threat: { type, userId, domain }). Privilege grants
// don't support pattern silencing — we hide the checkbox.
// ============================================================================

import { useState } from 'react';
import { ShieldOff, X } from 'lucide-react';
import { toast } from 'sonner';

import type { Threat } from '../_types';

type DismissModalTheme = 'legacy' | 'clinician';

interface Props {
  threat: Threat;
  onClose: () => void;
  onDismissed: () => void;
  theme?: DismissModalTheme;
}

export default function DismissModal({ threat, onClose, onDismissed, theme = 'legacy' }: Props) {
  const [note, setNote] = useState('');
  const [silenceSimilar, setSilenceSimilar] = useState(false);
  const [busy, setBusy] = useState(false);

  // privilege_escalation rows are unique by audit-log id; no class
  // pattern would be useful, so don't show the checkbox.
  const supportsSilence = threat.type !== 'privilege_escalation';

  async function submit() {
    setBusy(true);
    try {
      const body: Record<string, unknown> = {};
      if (note.trim()) body.note = note.trim();
      if (silenceSimilar) body.silenceSimilar = true;
      const res = await fetch(
        `/api/admin/threats/${encodeURIComponent(threat.id)}/dismiss`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        }
      );
      const data: { ok?: boolean; error?: string } = await res
        .json()
        .catch(() => ({}));
      if (res.ok && data.ok) {
        toast.success(
          silenceSimilar
            ? 'Dismissed and silenced similar threats'
            : 'Dismissed as false positive'
        );
        onDismissed();
      } else {
        toast.error('Dismiss failed', {
          description: data.error ?? `HTTP ${res.status}`,
        });
      }
    } catch (err) {
      toast.error('Dismiss failed', {
        description: err instanceof Error ? err.message : 'network error',
      });
    } finally {
      setBusy(false);
    }
  }

  if (theme === 'clinician') {
    return (
      <div
        onClick={onClose}
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 50,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 16,
          background: 'rgba(43, 38, 32, 0.32)',
          backdropFilter: 'blur(2px)',
        }}
      >
        <div
          className="qm-cl-card"
          onClick={(e) => e.stopPropagation()}
          style={{ width: '100%', maxWidth: 448, padding: 0, overflow: 'hidden' }}
        >
          <header
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: 12,
              borderBottom: '1px solid var(--line)',
              padding: '16px 20px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
              <span
                style={{
                  marginTop: 2,
                  display: 'inline-flex',
                  width: 28,
                  height: 28,
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 999,
                  background: 'var(--amber-tint)',
                  color: 'var(--amber-deep)',
                }}
              >
                <ShieldOff style={{ width: 14, height: 14 }} />
              </span>
              <div>
                <h2 className="qm-cl-serif" style={{ fontSize: 16, fontWeight: 500, color: 'var(--ink)' }}>
                  Dismiss as false positive
                </h2>
                <p style={{ marginTop: 2, fontSize: 11, color: 'var(--ink-3)' }}>
                  Removes this threat from the active list.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close"
              style={{
                marginTop: -4,
                marginRight: -4,
                display: 'inline-flex',
                width: 28,
                height: 28,
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 8,
                color: 'var(--ink-3)',
                background: 'transparent',
                border: 0,
                cursor: 'pointer',
              }}
            >
              <X style={{ width: 14, height: 14 }} />
            </button>
          </header>

          <div style={{ padding: '16px 20px' }}>
            <div
              style={{
                marginBottom: 12,
                borderRadius: 8,
                border: '1px solid var(--line)',
                background: 'var(--cream-2)',
                padding: '10px 12px',
                fontSize: 12,
                color: 'var(--ink-2)',
              }}
            >
              <div style={{ fontWeight: 500, color: 'var(--ink)' }}>{threat.summary}</div>
              <div style={{ marginTop: 2, color: 'var(--ink-2)' }}>{threat.detail}</div>
            </div>

            <label style={{ display: 'block' }}>
              <span className="qm-cl-section-label">Note (optional)</span>
              <textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                rows={3}
                maxLength={2000}
                placeholder="Why is this a false positive?"
                className="qm-cl-input"
                style={{ marginTop: 4, width: '100%', resize: 'none', fontSize: 13 }}
              />
            </label>

            {supportsSilence && (
              <label
                style={{
                  marginTop: 12,
                  display: 'flex',
                  cursor: 'pointer',
                  alignItems: 'flex-start',
                  gap: 8,
                  borderRadius: 8,
                  border: '1px solid var(--amber-tint-strong, rgba(212,165,116,0.32))',
                  background: 'var(--amber-tint)',
                  padding: '10px 12px',
                }}
              >
                <input
                  type="checkbox"
                  checked={silenceSimilar}
                  onChange={(e) => setSilenceSimilar(e.target.checked)}
                  style={{ marginTop: 2, width: 14, height: 14, cursor: 'pointer', accentColor: 'var(--amber-deep)' }}
                />
                <span style={{ fontSize: 12, color: 'var(--amber-deep)' }}>
                  <span style={{ fontWeight: 500 }}>Silence similar future threats.</span>{' '}
                  Future detector runs will suppress threats matching this one&apos;s
                  identifying tuple (e.g. same IP for failed-login bursts, same
                  user+domain for export attempts).
                </span>
              </label>
            )}
          </div>

          <footer
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
              onClick={onClose}
              disabled={busy}
              className="qm-cl-btn qm-cl-btn-ghost"
              style={{ height: 32, padding: '0 14px', fontSize: 12, opacity: busy ? 0.5 : 1 }}
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={submit}
              disabled={busy}
              className="qm-cl-btn qm-cl-btn-soft"
              style={{
                height: 32,
                padding: '0 14px',
                fontSize: 12,
                color: 'var(--amber-deep)',
                background: 'var(--amber-tint)',
                opacity: busy ? 0.5 : 1,
              }}
            >
              {busy ? 'Dismissing…' : 'Confirm dismiss'}
            </button>
          </footer>
        </div>
      </div>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div className="flex items-start gap-2.5">
            <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full bg-amber-100 text-amber-700">
              <ShieldOff className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-slate-900">
                Dismiss as false positive
              </h2>
              <p className="mt-0.5 text-[11px] text-slate-500">
                Removes this threat from the active list.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="-mt-1 -mr-1 inline-flex h-7 w-7 items-center justify-center rounded text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="px-5 py-4">
          <div className="mb-3 rounded border border-slate-200 bg-slate-50 px-3 py-2.5 text-[12px] text-slate-700">
            <div className="font-medium text-slate-900">{threat.summary}</div>
            <div className="mt-0.5 text-slate-600">{threat.detail}</div>
          </div>

          <label className="block">
            <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
              Note (optional)
            </span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="Why is this a false positive?"
              className="mt-1 block w-full resize-none rounded border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-slate-500 focus:outline-none"
            />
          </label>

          {supportsSilence && (
            <label className="mt-3 flex cursor-pointer items-start gap-2 rounded border border-amber-200 bg-amber-50 px-3 py-2.5">
              <input
                type="checkbox"
                checked={silenceSimilar}
                onChange={(e) => setSilenceSimilar(e.target.checked)}
                className="mt-0.5 h-3.5 w-3.5 cursor-pointer accent-amber-600"
              />
              <span className="text-[12px] text-amber-900">
                <span className="font-medium">Silence similar future threats.</span>{' '}
                Future detector runs will suppress threats matching this one&apos;s
                identifying tuple (e.g. same IP for failed-login bursts, same
                user+domain for export attempts).
              </span>
            </label>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-slate-200 bg-slate-50 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded border border-slate-300 bg-white px-3 py-1.5 text-[12px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={busy}
            className="rounded bg-amber-600 px-3 py-1.5 text-[12px] font-medium text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {busy ? 'Dismissing…' : 'Confirm dismiss'}
          </button>
        </footer>
      </div>
    </div>
  );
}
