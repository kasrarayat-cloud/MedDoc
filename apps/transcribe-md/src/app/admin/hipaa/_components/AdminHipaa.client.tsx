'use client';

// ============================================================================
// /admin/hipaa — client orchestrator (Phase 7B)
// ----------------------------------------------------------------------------
// Three tabs (Open / Resolved / All) reading from the SSR-seeded findings
// list. Each row expands inline to show the full detail; per-row actions
// (Resolve for open rows, Reopen for resolved rows) modal-confirm before
// firing the API.
//
// Refresh strategy: after a successful action we re-fetch /api/admin/hipaa
// and replace the in-memory list. Avoids router.refresh() so the tab/scroll
// state survives.
// ============================================================================

import { useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { toast } from 'sonner';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
} from 'lucide-react';

import AdminNav from '../../_components/AdminNav.client';
import { cls, relativeTime } from '../../_lib/admin-format';
import type {
  AdminHipaaInitialData,
  HipaaFindingRow,
  HipaaTab,
} from '../_types';

const TAB_OPTIONS: { key: HipaaTab; label: string }[] = [
  { key: 'open', label: 'Open' },
  { key: 'resolved', label: 'Resolved' },
  { key: 'all', label: 'All' },
];

interface Props {
  initial: AdminHipaaInitialData;
}

export default function AdminHipaa({ initial }: Props) {
  const router = useRouter();
  const params = useSearchParams();
  const initialTab = (params.get('tab') as HipaaTab) || 'open';
  const [tab, setTab] = useState<HipaaTab>(
    TAB_OPTIONS.some((o) => o.key === initialTab) ? initialTab : 'open'
  );
  const [findings, setFindings] = useState<HipaaFindingRow[]>(initial.findings);
  const [busy, setBusy] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [resolveOf, setResolveOf] = useState<HipaaFindingRow | null>(null);
  const [reopenOf, setReopenOf] = useState<HipaaFindingRow | null>(null);

  // URL sync.
  useEffect(() => {
    const next = new URLSearchParams(params.toString());
    next.set('tab', tab);
    if (next.toString() !== params.toString()) {
      router.replace(`/admin/hipaa?${next.toString()}`, { scroll: false });
    }
  }, [tab, params, router]);

  async function refresh() {
    setBusy(true);
    try {
      const r = await fetch('/api/admin/hipaa');
      const d = (await r.json()) as { findings?: HipaaFindingRow[] };
      if (Array.isArray(d.findings)) setFindings(d.findings);
    } catch {
      // keep stale
    } finally {
      setBusy(false);
    }
  }

  const counts = useMemo(() => {
    let open = 0;
    let resolved = 0;
    for (const f of findings) {
      if (f.status === 'resolved') resolved++;
      else open++;
    }
    return { open, resolved, all: findings.length };
  }, [findings]);

  const visible = useMemo(() => {
    if (tab === 'open') return findings.filter((f) => f.status !== 'resolved');
    if (tab === 'resolved') return findings.filter((f) => f.status === 'resolved');
    return findings;
  }, [findings, tab]);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="h-5 w-5 text-slate-600" />
            <div>
              <h1 className="text-xl font-semibold tracking-tight text-slate-900">
                HIPAA findings
              </h1>
              <div className="mt-0.5 text-[11px] text-slate-500">
                <span className="font-mono tabular-nums text-slate-700" data-testid="hipaa-page-open-count">
                  {counts.open}
                </span>{' '}
                open
                <span className="mx-1.5 text-slate-300">·</span>
                <span className="font-mono tabular-nums text-slate-700" data-testid="hipaa-page-resolved-count">
                  {counts.resolved}
                </span>{' '}
                resolved
                <span className="mx-1.5 text-slate-300">·</span>
                <span className="font-mono tabular-nums text-slate-700">{counts.all}</span> total
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={busy}
            className="inline-flex items-center gap-1.5 rounded border border-slate-300 bg-white px-2.5 py-1.5 text-[12px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            <RefreshCw className={'h-3.5 w-3.5 ' + (busy ? 'animate-spin' : '')} />
            Refresh
          </button>
        </div>
      </header>

      <AdminNav />

      <main className="mx-auto max-w-[1440px] px-6 py-6">
        <Tabs tab={tab} onChange={setTab} counts={counts} />

        {visible.length === 0 ? (
          <EmptyState tab={tab} />
        ) : (
          <ul className="space-y-2" data-testid="hipaa-list">
            {visible.map((f) => (
              <FindingRow
                key={f.id}
                finding={f}
                expanded={expanded === f.id}
                onToggle={() => setExpanded((cur) => (cur === f.id ? null : f.id))}
                onResolve={() => setResolveOf(f)}
                onReopen={() => setReopenOf(f)}
              />
            ))}
          </ul>
        )}
      </main>

      {resolveOf && (
        <ResolveModal
          finding={resolveOf}
          onClose={() => setResolveOf(null)}
          onResolved={() => {
            setResolveOf(null);
            void refresh();
          }}
        />
      )}
      {reopenOf && (
        <ReopenModal
          finding={reopenOf}
          onClose={() => setReopenOf(null)}
          onReopened={() => {
            setReopenOf(null);
            void refresh();
          }}
        />
      )}
    </div>
  );
}

// ── Tabs ───────────────────────────────────────────────────────────────────

function Tabs({
  tab,
  onChange,
  counts,
}: {
  tab: HipaaTab;
  onChange: (t: HipaaTab) => void;
  counts: { open: number; resolved: number; all: number };
}) {
  return (
    <nav className="mb-5 flex items-center gap-1 border-b border-slate-200">
      {TAB_OPTIONS.map((o) => {
        const active = tab === o.key;
        return (
          <button
            key={o.key}
            type="button"
            onClick={() => onChange(o.key)}
            data-testid={`hipaa-tab-${o.key}`}
            className={
              '-mb-px inline-flex items-center gap-2 border-b-2 px-3 py-2 text-[12px] font-medium transition-colors ' +
              (active
                ? 'border-slate-900 text-slate-900'
                : 'border-transparent text-slate-500 hover:text-slate-800')
            }
          >
            {o.label}
            <span
              className={
                'inline-flex min-w-[1.25rem] items-center justify-center rounded px-1.5 py-0.5 font-mono text-[10px] tabular-nums ' +
                (active ? 'bg-slate-900 text-white' : 'bg-slate-200 text-slate-700')
              }
            >
              {counts[o.key]}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

// ── Per-finding row ────────────────────────────────────────────────────────

function FindingRow({
  finding,
  expanded,
  onToggle,
  onResolve,
  onReopen,
}: {
  finding: HipaaFindingRow;
  expanded: boolean;
  onToggle: () => void;
  onResolve: () => void;
  onReopen: () => void;
}) {
  const isResolved = finding.status === 'resolved';
  return (
    <li
      className="overflow-hidden rounded-lg border border-slate-200 bg-white"
      data-testid={`hipaa-row`}
      data-finding-id={finding.id}
      data-finding-status={finding.status}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-slate-50"
      >
        <SeverityChip severity={finding.severity} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-slate-500">{finding.control}</span>
            <span
              className={cls(
                'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide',
                isResolved
                  ? 'bg-emerald-100 text-emerald-800'
                  : 'bg-amber-100 text-amber-800'
              )}
            >
              {isResolved ? 'Resolved' : 'Open'}
            </span>
          </div>
          <div className="mt-1 text-sm font-medium text-slate-900">{finding.title}</div>
          {isResolved && finding.resolvedByEmail && finding.resolvedAt && (
            <div className="mt-0.5 text-[11px] text-slate-500">
              Closed by{' '}
              <span className="font-mono">{finding.resolvedByEmail}</span>
              <span className="mx-1.5 text-slate-300">·</span>
              {relativeTime(finding.resolvedAt)}
            </div>
          )}
        </div>
        <ChevronRight
          className={cls(
            'mt-1 h-4 w-4 shrink-0 text-slate-400 transition-transform',
            expanded && 'rotate-90'
          )}
        />
      </button>

      {expanded && (
        <div className="border-t border-slate-100 px-4 py-3 text-sm">
          {finding.detail && (
            <p className="whitespace-pre-wrap text-slate-700">{finding.detail}</p>
          )}
          {finding.resolutionNote && (
            <div className="mt-3 rounded border-l-2 border-emerald-300 bg-emerald-50 px-3 py-2 text-[12px] text-emerald-900">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-emerald-700">
                Resolution note
              </div>
              <div className="mt-0.5 whitespace-pre-wrap">{finding.resolutionNote}</div>
            </div>
          )}
          <div className="mt-3 flex items-center justify-end gap-2">
            {!isResolved ? (
              <button
                type="button"
                onClick={onResolve}
                data-testid={`hipaa-resolve-${finding.id}`}
                className="inline-flex items-center gap-1.5 rounded bg-emerald-600 px-3 py-1.5 text-[12px] font-medium text-white hover:bg-emerald-700"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Resolve
              </button>
            ) : (
              <button
                type="button"
                onClick={onReopen}
                data-testid={`hipaa-reopen-${finding.id}`}
                className="inline-flex items-center gap-1.5 rounded border border-amber-300 bg-white px-3 py-1.5 text-[12px] font-medium text-amber-800 hover:bg-amber-50"
              >
                <RotateCcw className="h-3.5 w-3.5" />
                Reopen
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

function SeverityChip({ severity }: { severity: string }) {
  const map: Record<string, string> = {
    critical: 'bg-rose-100 text-rose-800',
    high: 'bg-amber-100 text-amber-800',
    medium: 'bg-slate-100 text-slate-700',
    low: 'bg-slate-100 text-slate-500',
  };
  const cls0 = map[severity] ?? 'bg-slate-100 text-slate-700';
  return (
    <span
      className={
        'mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full ' +
        cls0
      }
      title={`severity: ${severity}`}
    >
      <AlertTriangle className="h-4 w-4" />
    </span>
  );
}

function EmptyState({ tab }: { tab: HipaaTab }) {
  const titleMap: Record<HipaaTab, string> = {
    open: 'No open findings',
    resolved: 'No resolved findings',
    all: 'No findings yet',
  };
  const bodyMap: Record<HipaaTab, string> = {
    open: 'Nothing to act on right now. Audit team adds new findings via the seed for now.',
    resolved: 'Resolved findings will appear here with the admin and timestamp.',
    all: 'The audit team adds findings via the seed; nothing has landed yet.',
  };
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-8 text-center">
      <ShieldCheck className="mx-auto h-8 w-8 text-emerald-600" />
      <h3 className="mt-2 text-sm font-semibold text-emerald-900">{titleMap[tab]}</h3>
      <p className="mt-1 text-[12px] text-emerald-800">{bodyMap[tab]}</p>
    </div>
  );
}

// ── Resolve modal ──────────────────────────────────────────────────────────

function ResolveModal({
  finding,
  onClose,
  onResolved,
}: {
  finding: HipaaFindingRow;
  onClose: () => void;
  onResolved: () => void;
}) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      const res = await fetch(`/api/admin/hipaa/${finding.id}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(note.trim() ? { note: note.trim() } : {}),
      });
      const data: { ok?: boolean; error?: string } = await res
        .json()
        .catch(() => ({}));
      if (res.ok && data.ok) {
        toast.success('Finding resolved');
        onResolved();
      } else {
        toast.error('Resolve failed', { description: data.error ?? `HTTP ${res.status}` });
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
      onClick={busy ? undefined : onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start gap-2.5 border-b border-slate-200 px-5 py-4">
          <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full bg-emerald-100 text-emerald-700">
            <CheckCircle2 className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Resolve finding</h2>
            <p className="mt-0.5 text-[11px] text-slate-500">
              Closes this finding. Reversible via the Resolved tab if the fix doesn&apos;t hold.
            </p>
          </div>
        </header>
        <div className="px-5 py-4">
          <div className="mb-3 rounded border border-slate-200 bg-slate-50 px-3 py-2.5 text-[12px] text-slate-700">
            <div className="font-mono text-[10px] text-slate-500">{finding.control}</div>
            <div className="mt-0.5 font-medium text-slate-900">{finding.title}</div>
          </div>
          <label className="block">
            <span className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
              Resolution note (optional)
            </span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="What changed? Link to the commit / runbook / ticket."
              data-testid="hipaa-resolve-note"
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
            data-testid="hipaa-resolve-confirm"
            className="rounded bg-emerald-600 px-3 py-1.5 text-[12px] font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {busy ? 'Resolving…' : 'Confirm resolve'}
          </button>
        </footer>
      </div>
    </div>
  );
}

// ── Reopen modal ───────────────────────────────────────────────────────────

function ReopenModal({
  finding,
  onClose,
  onReopened,
}: {
  finding: HipaaFindingRow;
  onClose: () => void;
  onReopened: () => void;
}) {
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    try {
      const res = await fetch(`/api/admin/hipaa/${finding.id}/reopen`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data: { ok?: boolean; error?: string } = await res
        .json()
        .catch(() => ({}));
      if (res.ok && data.ok) {
        toast.success('Finding reopened');
        onReopened();
      } else {
        toast.error('Reopen failed', { description: data.error ?? `HTTP ${res.status}` });
      }
    } catch (err) {
      toast.error('Reopen failed', {
        description: err instanceof Error ? err.message : 'network error',
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
      onClick={busy ? undefined : onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-slate-200 bg-white shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start gap-2.5 border-b border-slate-200 px-5 py-4">
          <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full bg-amber-100 text-amber-800">
            <RotateCcw className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-slate-900">Reopen finding</h2>
            <p className="mt-0.5 text-[11px] text-slate-500">
              Moves this finding back to Open. The original resolution audit row stays intact.
            </p>
          </div>
        </header>
        <div className="px-5 py-4 text-[12px] text-slate-700">
          <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2.5">
            <div className="font-mono text-[10px] text-slate-500">{finding.control}</div>
            <div className="mt-0.5 font-medium text-slate-900">{finding.title}</div>
          </div>
          {finding.resolvedByEmail && (
            <p className="mt-3 text-slate-500">
              Originally resolved by <span className="font-mono">{finding.resolvedByEmail}</span>
              {finding.resolvedAt ? (
                <>
                  {' '}
                  <span className="text-slate-300">·</span> {relativeTime(finding.resolvedAt)}
                </>
              ) : null}
              .
            </p>
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
            data-testid="hipaa-reopen-confirm"
            className="rounded bg-amber-600 px-3 py-1.5 text-[12px] font-medium text-white hover:bg-amber-700 disabled:opacity-50"
          >
            {busy ? 'Reopening…' : 'Confirm reopen'}
          </button>
        </footer>
      </div>
    </div>
  );
}
