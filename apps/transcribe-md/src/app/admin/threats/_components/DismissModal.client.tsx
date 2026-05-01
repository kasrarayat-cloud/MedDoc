'use client';

// ============================================================================
// DismissModal — "false positive"
// ----------------------------------------------------------------------------
// Note + a "silence similar future threats" checkbox. The checkbox
// derives a silencePattern server-side based on the threat id (e.g.
// for an xdom threat: { type, userId, domain }). Privilege grants
// don't support pattern silencing — we hide the checkbox.
//
// Phase 5 (Linear V1 Faithful) — spotlight overlay on the dark canvas
// with a warning-amber tinted icon plate and CTA. The `theme` prop
// survives as an ignored compat shim.
// ============================================================================

import { useState } from 'react';
import { ShieldOff, X } from 'lucide-react';
import { toast } from 'sonner';

import type { Threat } from '../_types';

interface Props {
  threat: Threat;
  onClose: () => void;
  onDismissed: () => void;
  /** Phase 4 dual-theme prop. Phase 5 ignores it; kept for caller compat. */
  theme?: string;
}

export default function DismissModal({ threat, onClose, onDismissed }: Props) {
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

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md overflow-hidden rounded-lg border border-linear-border-strong bg-linear-surface-2 shadow-[0_30px_80px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3 border-b border-linear-border px-5 py-4">
          <div className="flex items-start gap-2.5">
            <span
              className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full"
              style={{
                background: 'rgba(212,164,55,0.18)',
                color: 'var(--color-linear-warning)',
              }}
            >
              <ShieldOff className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-linear-text">
                Dismiss as false positive
              </h2>
              <p className="mt-0.5 text-[11px] text-linear-text-3">
                Removes this threat from the active list.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="-mt-1 -mr-1 inline-flex h-7 w-7 items-center justify-center rounded text-linear-text-3 hover:bg-linear-row-hover hover:text-linear-text"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </header>

        <div className="px-5 py-4">
          <div className="mb-3 rounded-md border border-linear-border bg-linear-surface-1 px-3 py-2.5 text-[12px] text-linear-text-2">
            <div className="font-medium text-linear-text">{threat.summary}</div>
            <div className="mt-0.5 text-linear-text-2">{threat.detail}</div>
          </div>

          <label className="block">
            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-text-3">
              Note (optional)
            </span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="Why is this a false positive?"
              className="mt-1 block w-full resize-none rounded-md border border-linear-border bg-linear-surface-1 px-3 py-2 text-sm text-linear-text placeholder:text-linear-text-3 focus:border-linear-border-strong focus:outline-none focus:ring-2 focus:ring-linear-sage/40"
            />
          </label>

          {supportsSilence && (
            <label
              className="mt-3 flex cursor-pointer items-start gap-2 rounded-md px-3 py-2.5"
              style={{
                background: 'rgba(212,164,55,0.10)',
                boxShadow: 'inset 0 0 0 1px rgba(212,164,55,0.30)',
              }}
            >
              <input
                type="checkbox"
                checked={silenceSimilar}
                onChange={(e) => setSilenceSimilar(e.target.checked)}
                className="mt-0.5 h-3.5 w-3.5 cursor-pointer"
                style={{ accentColor: 'var(--color-linear-warning)' }}
              />
              <span className="text-[12px]" style={{ color: 'var(--color-linear-warning)' }}>
                <span className="font-medium">Silence similar future threats.</span>{' '}
                Future detector runs will suppress threats matching this one&apos;s
                identifying tuple (e.g. same IP for failed-login bursts, same
                user+domain for export attempts).
              </span>
            </label>
          )}
        </div>

        <footer className="flex items-center justify-end gap-2 border-t border-linear-border bg-linear-surface-1 px-5 py-3">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="qm-lin-btn"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={submit}
            disabled={busy}
            className="inline-flex items-center justify-center rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-50"
            style={{
              background: 'rgba(212,164,55,0.18)',
              color: 'var(--color-linear-warning)',
              boxShadow: 'inset 0 0 0 1px rgba(212,164,55,0.30)',
            }}
          >
            {busy ? 'Dismissing…' : 'Confirm dismiss'}
          </button>
        </footer>
      </div>
    </div>
  );
}
