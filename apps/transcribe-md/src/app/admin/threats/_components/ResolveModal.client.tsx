'use client';

// ============================================================================
// ResolveModal — "mark as resolved"
// ----------------------------------------------------------------------------
// Confirms an admin reviewed the threat and decided no further action
// is needed. Note is optional but encouraged. Posts to
// /api/admin/threats/[id]/resolve and lets the parent re-fetch.
//
// Phase 5 (Linear V1 Faithful) — spotlight overlay on the dark canvas
// with sage-tinted icon plate and sage primary CTA. The `theme` prop
// survives as an ignored compat shim.
// ============================================================================

import { useState } from 'react';
import { CheckCircle2, X } from 'lucide-react';
import { toast } from 'sonner';

import type { Threat } from '../_types';

interface Props {
  threat: Threat;
  onClose: () => void;
  onResolved: () => void;
  /** Phase 4 dual-theme prop. Phase 5 ignores it; kept for caller compat. */
  theme?: string;
}

export default function ResolveModal({ threat, onClose, onResolved }: Props) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      const res = await fetch(
        `/api/admin/threats/${encodeURIComponent(threat.id)}/resolve`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(note.trim() ? { note: note.trim() } : {}),
        }
      );
      const data: { ok?: boolean; error?: string } = await res
        .json()
        .catch(() => ({}));
      if (res.ok && data.ok) {
        toast.success('Threat resolved');
        onResolved();
      } else {
        toast.error('Resolve failed', {
          description: data.error ?? `HTTP ${res.status}`,
        });
      }
    } catch (err) {
      toast.error('Resolve failed', {
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
            <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full bg-linear-sage-tint text-linear-sage-bright">
              <CheckCircle2 className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-linear-text">
                Resolve threat
              </h2>
              <p className="mt-0.5 text-[11px] text-linear-text-3">
                Marks this threat as reviewed and acted on.
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
              placeholder="What did you find? What did you do?"
              className="mt-1 block w-full resize-none rounded-md border border-linear-border bg-linear-surface-1 px-3 py-2 text-sm text-linear-text placeholder:text-linear-text-3 focus:border-linear-border-strong focus:outline-none focus:ring-2 focus:ring-linear-sage/40"
            />
          </label>
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
            className="qm-lin-btn-primary"
          >
            {busy ? 'Resolving…' : 'Confirm resolve'}
          </button>
        </footer>
      </div>
    </div>
  );
}
