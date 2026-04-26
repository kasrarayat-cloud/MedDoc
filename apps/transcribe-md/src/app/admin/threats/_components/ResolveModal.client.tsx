'use client';

// ============================================================================
// ResolveModal — Phase 6H "mark as resolved"
// ----------------------------------------------------------------------------
// Confirms an admin reviewed the threat and decided no further action
// is needed. Note is optional but encouraged. Posts to
// /api/admin/threats/[id]/resolve and lets the parent re-fetch.
// ============================================================================

import { useState } from 'react';
import { CheckCircle2, X } from 'lucide-react';
import { toast } from 'sonner';

import type { Threat } from '../_types';

interface Props {
  threat: Threat;
  onClose: () => void;
  onResolved: () => void;
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div className="flex items-start gap-2.5">
            <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
              <CheckCircle2 className="h-4 w-4" />
            </span>
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-slate-900">
                Resolve threat
              </h2>
              <p className="mt-0.5 text-[11px] text-slate-500">
                Marks this threat as reviewed and acted on.
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
              placeholder="What did you find? What did you do?"
              className="mt-1 block w-full resize-none rounded border border-slate-300 px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:border-slate-500 focus:outline-none"
            />
          </label>
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
            className="rounded bg-emerald-600 px-3 py-1.5 text-[12px] font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {busy ? 'Resolving…' : 'Confirm resolve'}
          </button>
        </footer>
      </div>
    </div>
  );
}
