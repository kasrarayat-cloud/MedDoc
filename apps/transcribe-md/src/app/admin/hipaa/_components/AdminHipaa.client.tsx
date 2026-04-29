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
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the slate-on-white rendering
// verbatim. Clinician branch renders parallel chrome using `.qm-cl-card`,
// `.qm-cl-pill-*` (sage = clear, amber = open, coral = critical),
// `.qm-cl-tab-row` for the tab strip, and the cream/sage/ink palette.
// Every `data-testid` (hipaa-list, hipaa-row, hipaa-tab-{open|resolved|all},
// hipaa-resolve-*, hipaa-reopen-*) is preserved.
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

type AdminHipaaTheme = 'legacy' | 'clinician';

interface Props {
  initial: AdminHipaaInitialData;
  theme?: AdminHipaaTheme;
}

export default function AdminHipaa({ initial, theme = 'legacy' }: Props) {
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

  if (theme === 'clinician') {
    return (
      <div style={{ minHeight: '100vh', color: 'var(--ink)' }}>
        <header
          style={{
            position: 'sticky',
            top: 0,
            zIndex: 20,
            borderBottom: '1px solid var(--line)',
            background: 'var(--cream-card)',
          }}
        >
          <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-4">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <ShieldCheck style={{ width: 22, height: 22, color: 'var(--sage-deep)' }} />
              <div>
                <div className="qm-cl-eyebrow" style={{ marginBottom: 4 }}>
                  Admin · Compliance
                </div>
                <h1
                  className="qm-cl-serif"
                  style={{
                    fontSize: 28,
                    fontWeight: 400,
                    letterSpacing: '-0.01em',
                    color: 'var(--ink)',
                    lineHeight: 1.15,
                  }}
                >
                  HIPAA findings
                </h1>
                <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-3)' }}>
                  <span
                    className="qm-cl-mono"
                    style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}
                    data-testid="hipaa-page-open-count"
                  >
                    {counts.open}
                  </span>{' '}
                  open
                  <span style={{ margin: '0 8px', color: 'var(--ink-4)' }}>·</span>
                  <span
                    className="qm-cl-mono"
                    style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}
                    data-testid="hipaa-page-resolved-count"
                  >
                    {counts.resolved}
                  </span>{' '}
                  resolved
                  <span style={{ margin: '0 8px', color: 'var(--ink-4)' }}>·</span>
                  <span
                    className="qm-cl-mono"
                    style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}
                  >
                    {counts.all}
                  </span>{' '}
                  total
                </div>
              </div>
            </div>
            <button
              type="button"
              onClick={refresh}
              disabled={busy}
              className="qm-cl-btn qm-cl-btn-soft"
              style={{ height: 32, padding: '0 12px', fontSize: 12, opacity: busy ? 0.5 : 1 }}
            >
              <RefreshCw style={{ width: 14, height: 14 }} className={busy ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </header>

        <AdminNav theme="clinician" />

        <main className="mx-auto max-w-[1440px] px-6 py-6">
          <ClinicianHipaaTabs tab={tab} onChange={setTab} counts={counts} />

          {visible.length === 0 ? (
            <ClinicianHipaaEmptyState tab={tab} />
          ) : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }} data-testid="hipaa-list">
              {visible.map((f) => (
                <ClinicianFindingRow
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
          <ClinicianHipaaResolveModal
            finding={resolveOf}
            onClose={() => setResolveOf(null)}
            onResolved={() => {
              setResolveOf(null);
              void refresh();
            }}
          />
        )}
        {reopenOf && (
          <ClinicianHipaaReopenModal
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

// ---------------------------------------------------------------------------
// Clinician variants — same data, warm cream + sage palette. Sub-components
// are duplicated rather than parameterised so the legacy slate-on-white
// path above stays byte-for-byte unchanged. Every data-testid is preserved.
// ---------------------------------------------------------------------------

function ClinicianHipaaTabs({
  tab,
  onChange,
  counts,
}: {
  tab: HipaaTab;
  onChange: (t: HipaaTab) => void;
  counts: { open: number; resolved: number; all: number };
}) {
  return (
    <nav
      style={{
        marginBottom: 20,
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        borderBottom: '1px solid var(--line)',
      }}
    >
      {TAB_OPTIONS.map((o) => {
        const active = tab === o.key;
        return (
          <button
            key={o.key}
            type="button"
            onClick={() => onChange(o.key)}
            data-testid={`hipaa-tab-${o.key}`}
            style={{
              marginBottom: -1,
              display: 'inline-flex',
              alignItems: 'center',
              gap: 8,
              borderBottom: '2px solid',
              borderColor: active ? 'var(--sage-deep)' : 'transparent',
              padding: '8px 12px',
              fontSize: 12,
              fontWeight: 500,
              color: active ? 'var(--ink)' : 'var(--ink-3)',
              background: 'transparent',
              border: 0,
              borderBottomWidth: 2,
              borderBottomStyle: 'solid',
              borderBottomColor: active ? 'var(--sage-deep)' : 'transparent',
              cursor: 'pointer',
              transition: 'color 240ms var(--ease-clinician), border-color 240ms var(--ease-clinician)',
            }}
          >
            {o.label}
            <span
              style={{
                display: 'inline-flex',
                minWidth: 20,
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 999,
                padding: '2px 6px',
                fontFamily: 'var(--mono)',
                fontSize: 10,
                fontVariantNumeric: 'tabular-nums',
                background: active ? 'var(--sage-tint-strong)' : 'var(--cream-2)',
                color: active ? 'var(--sage-deep)' : 'var(--ink-2)',
              }}
            >
              {counts[o.key]}
            </span>
          </button>
        );
      })}
    </nav>
  );
}

function ClinicianFindingRow({
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
      className="qm-cl-card"
      style={{ overflow: 'hidden', padding: 0 }}
      data-testid="hipaa-row"
      data-finding-id={finding.id}
      data-finding-status={finding.status}
    >
      <button
        type="button"
        onClick={onToggle}
        style={{
          display: 'flex',
          width: '100%',
          alignItems: 'flex-start',
          gap: 12,
          padding: '12px 16px',
          textAlign: 'left',
          background: 'transparent',
          border: 0,
          cursor: 'pointer',
          color: 'var(--ink)',
          transition: 'background 200ms var(--ease-clinician)',
        }}
        className="hover:bg-clinician-cream-2"
      >
        <ClinicianSeverityChip severity={finding.severity} />
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className="qm-cl-mono" style={{ fontSize: 10, color: 'var(--ink-3)' }}>
              {finding.control}
            </span>
            <span
              className={`qm-cl-pill ${isResolved ? 'qm-cl-pill-sage' : 'qm-cl-pill-amber'}`}
              style={{ fontSize: 10, padding: '2px 8px', textTransform: 'uppercase', letterSpacing: '0.04em' }}
            >
              {isResolved ? 'Resolved' : 'Open'}
            </span>
          </div>
          <div style={{ marginTop: 4, fontSize: 13, fontWeight: 500, color: 'var(--ink)' }}>{finding.title}</div>
          {isResolved && finding.resolvedByEmail && finding.resolvedAt && (
            <div style={{ marginTop: 2, fontSize: 11, color: 'var(--ink-3)' }}>
              Closed by{' '}
              <span className="qm-cl-mono">{finding.resolvedByEmail}</span>
              <span style={{ margin: '0 8px', color: 'var(--ink-4)' }}>·</span>
              {relativeTime(finding.resolvedAt)}
            </div>
          )}
        </div>
        <ChevronRight
          style={{
            marginTop: 4,
            width: 16,
            height: 16,
            flexShrink: 0,
            color: 'var(--ink-4)',
            transition: 'transform 240ms var(--ease-clinician)',
            transform: expanded ? 'rotate(90deg)' : 'none',
          }}
        />
      </button>

      {expanded && (
        <div
          style={{
            borderTop: '1px solid var(--line)',
            padding: '12px 16px',
            fontSize: 13,
            color: 'var(--ink-2)',
          }}
        >
          {finding.detail && (
            <p style={{ whiteSpace: 'pre-wrap', color: 'var(--ink-2)' }}>{finding.detail}</p>
          )}
          {finding.resolutionNote && (
            <div
              style={{
                marginTop: 12,
                borderRadius: 8,
                borderLeft: '2px solid var(--sage)',
                background: 'var(--sage-tint)',
                padding: '8px 12px',
                fontSize: 12,
                color: 'var(--sage-deep)',
              }}
            >
              <div className="qm-cl-section-label" style={{ color: 'var(--sage-deep)', opacity: 0.85 }}>
                Resolution note
              </div>
              <div style={{ marginTop: 2, whiteSpace: 'pre-wrap' }}>{finding.resolutionNote}</div>
            </div>
          )}
          <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 8 }}>
            {!isResolved ? (
              <button
                type="button"
                onClick={onResolve}
                data-testid={`hipaa-resolve-${finding.id}`}
                className="qm-cl-btn qm-cl-btn-primary"
                style={{ height: 32, padding: '0 14px', fontSize: 12, gap: 6 }}
              >
                <CheckCircle2 style={{ width: 14, height: 14 }} />
                Resolve
              </button>
            ) : (
              <button
                type="button"
                onClick={onReopen}
                data-testid={`hipaa-reopen-${finding.id}`}
                className="qm-cl-btn qm-cl-btn-soft"
                style={{ height: 32, padding: '0 14px', fontSize: 12, gap: 6, color: 'var(--amber-deep)' }}
              >
                <RotateCcw style={{ width: 14, height: 14 }} />
                Reopen
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

function ClinicianSeverityChip({ severity }: { severity: string }) {
  const map: Record<string, { bg: string; fg: string }> = {
    critical: { bg: 'var(--coral-tint)', fg: 'var(--coral-deep)' },
    high: { bg: 'var(--amber-tint)', fg: 'var(--amber-deep)' },
    medium: { bg: 'var(--cream-2)', fg: 'var(--ink-2)' },
    low: { bg: 'var(--cream-2)', fg: 'var(--ink-3)' },
  };
  const palette = map[severity] ?? map.medium!;
  return (
    <span
      style={{
        marginTop: 2,
        display: 'inline-flex',
        width: 28,
        height: 28,
        flexShrink: 0,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: 999,
        background: palette.bg,
        color: palette.fg,
      }}
      title={`severity: ${severity}`}
    >
      <AlertTriangle style={{ width: 14, height: 14 }} />
    </span>
  );
}

function ClinicianHipaaEmptyState({ tab }: { tab: HipaaTab }) {
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
    <div
      style={{
        borderRadius: 12,
        border: '1px solid var(--sage-tint-strong)',
        background: 'var(--sage-tint)',
        padding: 32,
        textAlign: 'center',
      }}
    >
      <ShieldCheck style={{ margin: '0 auto', width: 32, height: 32, color: 'var(--sage-deep)' }} />
      <h3 style={{ marginTop: 8, fontSize: 14, fontWeight: 600, color: 'var(--sage-deep)' }}>{titleMap[tab]}</h3>
      <p style={{ marginTop: 4, fontSize: 12, color: 'var(--sage-deep)', opacity: 0.85 }}>{bodyMap[tab]}</p>
    </div>
  );
}

function ClinicianHipaaResolveModal({
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
      const data: { ok?: boolean; error?: string } = await res.json().catch(() => ({}));
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
      onClick={busy ? undefined : onClose}
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
        style={{
          width: '100%',
          maxWidth: 448,
          padding: 0,
          overflow: 'hidden',
        }}
      >
        <header
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            borderBottom: '1px solid var(--line)',
            padding: '16px 20px',
          }}
        >
          <span
            style={{
              marginTop: 2,
              display: 'inline-flex',
              width: 28,
              height: 28,
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 999,
              background: 'var(--sage-tint-strong)',
              color: 'var(--sage-deep)',
            }}
          >
            <CheckCircle2 style={{ width: 14, height: 14 }} />
          </span>
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Resolve finding</h2>
            <p style={{ marginTop: 2, fontSize: 11, color: 'var(--ink-3)' }}>
              Closes this finding. Reversible via the Resolved tab if the fix doesn&apos;t hold.
            </p>
          </div>
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
            <div className="qm-cl-mono" style={{ fontSize: 10, color: 'var(--ink-3)' }}>
              {finding.control}
            </div>
            <div style={{ marginTop: 2, fontWeight: 500, color: 'var(--ink)' }}>{finding.title}</div>
          </div>
          <label style={{ display: 'block' }}>
            <span className="qm-cl-section-label">Resolution note (optional)</span>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              maxLength={2000}
              placeholder="What changed? Link to the commit / runbook / ticket."
              data-testid="hipaa-resolve-note"
              className="qm-cl-input"
              style={{
                marginTop: 4,
                width: '100%',
                resize: 'none',
                fontSize: 13,
              }}
            />
          </label>
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
            data-testid="hipaa-resolve-confirm"
            className="qm-cl-btn qm-cl-btn-primary"
            style={{ height: 32, padding: '0 14px', fontSize: 12, opacity: busy ? 0.5 : 1 }}
          >
            {busy ? 'Resolving…' : 'Confirm resolve'}
          </button>
        </footer>
      </div>
    </div>
  );
}

function ClinicianHipaaReopenModal({
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
      const data: { ok?: boolean; error?: string } = await res.json().catch(() => ({}));
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
      onClick={busy ? undefined : onClose}
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
        style={{
          width: '100%',
          maxWidth: 448,
          padding: 0,
          overflow: 'hidden',
        }}
      >
        <header
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: 10,
            borderBottom: '1px solid var(--line)',
            padding: '16px 20px',
          }}
        >
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
            <RotateCcw style={{ width: 14, height: 14 }} />
          </span>
          <div>
            <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Reopen finding</h2>
            <p style={{ marginTop: 2, fontSize: 11, color: 'var(--ink-3)' }}>
              Moves this finding back to Open. The original resolution audit row stays intact.
            </p>
          </div>
        </header>
        <div style={{ padding: '16px 20px', fontSize: 12, color: 'var(--ink-2)' }}>
          <div
            style={{
              borderRadius: 8,
              border: '1px solid var(--line)',
              background: 'var(--cream-2)',
              padding: '10px 12px',
            }}
          >
            <div className="qm-cl-mono" style={{ fontSize: 10, color: 'var(--ink-3)' }}>
              {finding.control}
            </div>
            <div style={{ marginTop: 2, fontWeight: 500, color: 'var(--ink)' }}>{finding.title}</div>
          </div>
          {finding.resolvedByEmail && (
            <p style={{ marginTop: 12, color: 'var(--ink-3)' }}>
              Originally resolved by <span className="qm-cl-mono">{finding.resolvedByEmail}</span>
              {finding.resolvedAt ? (
                <>
                  {' '}
                  <span style={{ color: 'var(--ink-4)' }}>·</span> {relativeTime(finding.resolvedAt)}
                </>
              ) : null}
              .
            </p>
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
            data-testid="hipaa-reopen-confirm"
            className="qm-cl-btn qm-cl-btn-soft"
            style={{ height: 32, padding: '0 14px', fontSize: 12, color: 'var(--amber-deep)', background: 'var(--amber-tint)', opacity: busy ? 0.5 : 1 }}
          >
            {busy ? 'Reopening…' : 'Confirm reopen'}
          </button>
        </footer>
      </div>
    </div>
  );
}
