'use client';

// ============================================================================
// /admin/hipaa — client orchestrator
// ----------------------------------------------------------------------------
// Three tabs (Open / Resolved / All) reading from the SSR-seeded findings
// list. Each row expands inline to show the full detail; per-row actions
// (Resolve for open rows, Reopen for resolved rows) modal-confirm before
// firing the API.
//
// Refresh strategy: after a successful action we re-fetch /api/admin/hipaa
// and replace the in-memory list. Avoids router.refresh() so the tab/scroll
// state survives.
//
// Phase 5 (Linear V1 Faithful) — list rendered against the dark canvas
// with sage/warning/danger-tinted severity chips, hairline-bordered
// rows, and sage-active tab underline. The earlier dual-theme branching
// has been retired; the `theme` prop survives as an ignored compat
// shim. Every `data-testid` (hipaa-list, hipaa-row,
// hipaa-tab-{open|resolved|all}, hipaa-resolve-*, hipaa-reopen-*) is
// preserved.
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
  /** Phase 4 dual-theme prop. Phase 5 ignores it; kept for caller compat. */
  theme?: string;
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
    <div className="min-h-screen bg-linear-bg text-linear-text">
      <header className="sticky top-0 z-20 border-b border-linear-border bg-linear-surface-1/95 backdrop-blur supports-[backdrop-filter]:bg-linear-surface-1/85">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3">
          <div className="flex items-center gap-2.5">
            <ShieldCheck className="h-5 w-5 text-linear-sage-bright" />
            <div>
              <div className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-linear-text-3 mb-1">
                Admin · Compliance
              </div>
              <h1 className="text-[20px] font-semibold tracking-tight text-linear-text leading-tight">
                HIPAA findings
              </h1>
              <div className="mt-1 text-[11px] text-linear-text-3">
                <span className="font-mono tabular-nums text-linear-text-2" data-testid="hipaa-page-open-count">
                  {counts.open}
                </span>{' '}
                open
                <span className="mx-1.5 text-linear-text-3">·</span>
                <span className="font-mono tabular-nums text-linear-text-2" data-testid="hipaa-page-resolved-count">
                  {counts.resolved}
                </span>{' '}
                resolved
                <span className="mx-1.5 text-linear-text-3">·</span>
                <span className="font-mono tabular-nums text-linear-text-2">{counts.all}</span> total
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={refresh}
            disabled={busy}
            className="qm-lin-btn"
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
    <nav className="mb-5 flex items-center gap-1 border-b border-linear-border">
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
                ? 'border-linear-sage text-linear-text'
                : 'border-transparent text-linear-text-3 hover:text-linear-text-2')
            }
          >
            {o.label}
            <span
              className={
                'inline-flex min-w-[1.25rem] items-center justify-center rounded px-1.5 py-0.5 font-mono text-[10px] tabular-nums ' +
                (active ? 'bg-linear-sage-tint text-linear-sage-bright' : 'bg-linear-surface-2 text-linear-text-3')
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
      className="overflow-hidden rounded-lg border border-linear-border bg-linear-surface-1"
      data-testid="hipaa-row"
      data-finding-id={finding.id}
      data-finding-status={finding.status}
    >
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-linear-row-hover"
      >
        <SeverityChip severity={finding.severity} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[10px] text-linear-text-3">{finding.control}</span>
            <span
              className="inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.05em]"
              style={
                isResolved
                  ? {
                      background: 'var(--color-linear-sage-tint)',
                      color: 'var(--color-linear-sage-bright)',
                    }
                  : {
                      background: 'rgba(212,164,55,0.18)',
                      color: 'var(--color-linear-warning)',
                    }
              }
            >
              {isResolved ? 'Resolved' : 'Open'}
            </span>
          </div>
          <div className="mt-1 text-sm font-medium text-linear-text">{finding.title}</div>
          {isResolved && finding.resolvedByEmail && finding.resolvedAt && (
            <div className="mt-0.5 text-[11px] text-linear-text-3">
              Closed by{' '}
              <span className="font-mono">{finding.resolvedByEmail}</span>
              <span className="mx-1.5 text-linear-text-3">·</span>
              {relativeTime(finding.resolvedAt)}
            </div>
          )}
        </div>
        <ChevronRight
          className={cls(
            'mt-1 h-4 w-4 shrink-0 text-linear-text-3 transition-transform',
            expanded && 'rotate-90'
          )}
        />
      </button>

      {expanded && (
        <div className="border-t border-linear-border px-4 py-3 text-sm">
          {finding.detail && (
            <p className="whitespace-pre-wrap text-linear-text-2">{finding.detail}</p>
          )}
          {finding.resolutionNote && (
            <div
              className="mt-3 rounded-md border-l-2 px-3 py-2 text-[12px]"
              style={{
                borderColor: 'var(--color-linear-sage)',
                background: 'var(--color-linear-sage-tint)',
                color: 'var(--color-linear-sage-bright)',
              }}
            >
              <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-sage-bright">
                Resolution note
              </div>
              <div className="mt-0.5 whitespace-pre-wrap text-linear-text-2">{finding.resolutionNote}</div>
            </div>
          )}
          <div className="mt-3 flex items-center justify-end gap-2">
            {!isResolved ? (
              <button
                type="button"
                onClick={onResolve}
                data-testid={`hipaa-resolve-${finding.id}`}
                className="qm-lin-btn-primary"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Resolve
              </button>
            ) : (
              <button
                type="button"
                onClick={onReopen}
                data-testid={`hipaa-reopen-${finding.id}`}
                className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors"
                style={{
                  background: 'rgba(212,164,55,0.15)',
                  color: 'var(--color-linear-warning)',
                  boxShadow: 'inset 0 0 0 1px rgba(212,164,55,0.30)',
                }}
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
  const styles: Record<string, React.CSSProperties> = {
    critical: {
      background: 'rgba(212,87,74,0.18)',
      color: 'var(--color-linear-danger)',
    },
    high: {
      background: 'rgba(212,164,55,0.18)',
      color: 'var(--color-linear-warning)',
    },
    medium: {
      background: 'var(--color-linear-surface-2)',
      color: 'var(--color-linear-text-2)',
    },
    low: {
      background: 'var(--color-linear-surface-2)',
      color: 'var(--color-linear-text-3)',
    },
  };
  const s = styles[severity] ?? styles.medium;
  return (
    <span
      className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
      style={s}
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
    <div className="rounded-lg border border-linear-border bg-linear-sage-tint p-8 text-center">
      <ShieldCheck className="mx-auto h-8 w-8 text-linear-sage-bright" />
      <h3 className="mt-2 text-sm font-semibold text-linear-sage-bright">{titleMap[tab]}</h3>
      <p className="mt-1 text-[12px] text-linear-text-2">{bodyMap[tab]}</p>
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4"
      onClick={busy ? undefined : onClose}
    >
      <div
        className="w-full max-w-md overflow-hidden rounded-lg border border-linear-border-strong bg-linear-surface-2 shadow-[0_30px_80px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start gap-2.5 border-b border-linear-border px-5 py-4">
          <span className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full bg-linear-sage-tint text-linear-sage-bright">
            <CheckCircle2 className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-linear-text">Resolve finding</h2>
            <p className="mt-0.5 text-[11px] text-linear-text-3">
              Closes this finding. Reversible via the Resolved tab if the fix doesn&apos;t hold.
            </p>
          </div>
        </header>
        <div className="px-5 py-4">
          <div className="mb-3 rounded-md border border-linear-border bg-linear-surface-1 px-3 py-2.5 text-[12px] text-linear-text-2">
            <div className="font-mono text-[10px] text-linear-text-3">{finding.control}</div>
            <div className="mt-0.5 font-medium text-linear-text">{finding.title}</div>
          </div>
          <label className="block">
            <span className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-text-3">
              Resolution note (optional)
            </span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="What changed? Link to the commit / runbook / ticket."
              data-testid="hipaa-resolve-note"
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
            data-testid="hipaa-resolve-confirm"
            className="qm-lin-btn-primary"
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
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-[2px] p-4"
      onClick={busy ? undefined : onClose}
    >
      <div
        className="w-full max-w-md overflow-hidden rounded-lg border border-linear-border-strong bg-linear-surface-2 shadow-[0_30px_80px_rgba(0,0,0,0.6)]"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex items-start gap-2.5 border-b border-linear-border px-5 py-4">
          <span
            className="mt-0.5 inline-flex h-7 w-7 items-center justify-center rounded-full"
            style={{
              background: 'rgba(212,164,55,0.18)',
              color: 'var(--color-linear-warning)',
            }}
          >
            <RotateCcw className="h-4 w-4" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-linear-text">Reopen finding</h2>
            <p className="mt-0.5 text-[11px] text-linear-text-3">
              Moves this finding back to Open. The original resolution audit row stays intact.
            </p>
          </div>
        </header>
        <div className="px-5 py-4 text-[12px] text-linear-text-2">
          <div className="rounded-md border border-linear-border bg-linear-surface-1 px-3 py-2.5">
            <div className="font-mono text-[10px] text-linear-text-3">{finding.control}</div>
            <div className="mt-0.5 font-medium text-linear-text">{finding.title}</div>
          </div>
          {finding.resolvedByEmail && (
            <p className="mt-3 text-linear-text-3">
              Originally resolved by <span className="font-mono">{finding.resolvedByEmail}</span>
              {finding.resolvedAt ? (
                <>
                  {' '}
                  <span className="text-linear-text-3">·</span> {relativeTime(finding.resolvedAt)}
                </>
              ) : null}
              .
            </p>
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
            data-testid="hipaa-reopen-confirm"
            className="inline-flex items-center justify-center rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors disabled:opacity-50"
            style={{
              background: 'rgba(212,164,55,0.18)',
              color: 'var(--color-linear-warning)',
              boxShadow: 'inset 0 0 0 1px rgba(212,164,55,0.30)',
            }}
          >
            {busy ? 'Reopening…' : 'Confirm reopen'}
          </button>
        </footer>
      </div>
    </div>
  );
}
