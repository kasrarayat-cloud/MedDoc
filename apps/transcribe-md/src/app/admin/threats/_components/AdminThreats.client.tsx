'use client';

// ============================================================================
// /admin/threats — orchestrator
// ----------------------------------------------------------------------------
// Three tabs:
//   - Active        → live detector output, filtered through resolutions
//   - Resolved      → ThreatResolution rows with kind=RESOLVED
//   - False positives → kind=FALSE_POSITIVE
//
// Per-row actions: Investigate (drawer) → Resolve / Dismiss (modals).
// Window selector (7d / 30d) applies to both history tabs.
//
// On any successful action we re-fetch from /api/admin/threats and
// /api/admin/threats/history so a resolved row immediately moves
// between tabs without an SSR round-trip.
//
// Phase 5 (Linear V1 Faithful) — tabular list rendered against the
// dark canvas. Severity dots: sage=info, warning=amber, danger=red.
// Drawer + modals receive the (now-no-op) `theme` prop preserving the
// caller-site shape until they're rewritten in this commit batch.
// ============================================================================

import { useEffect, useState, useTransition } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Eye,
  RefreshCw,
  ShieldOff,
} from 'lucide-react';

import AdminNav from '../../_components/AdminNav.client';
import DismissModal from './DismissModal.client';
import InvestigateDrawer from './InvestigateDrawer.client';
import ResolveModal from './ResolveModal.client';
import type {
  AdminThreatsInitialData,
  HistoryWindow,
  ResolvedThreat,
  Threat,
  ThreatTab,
} from '../_types';

interface Props {
  initial: AdminThreatsInitialData;
  /** Phase 4 dual-theme prop. Phase 5 ignores it; kept for caller compat. */
  theme?: string;
}

const TAB_OPTIONS: { key: ThreatTab; label: string }[] = [
  { key: 'active', label: 'Active' },
  { key: 'resolved', label: 'Resolved' },
  { key: 'false_positive', label: 'False positives' },
];

export default function AdminThreats({ initial }: Props) {
  const router = useRouter();
  const params = useSearchParams();
  const [, startTransition] = useTransition();

  const initialTab = (params.get('tab') as ThreatTab) || 'active';
  const initialWindow = ((params.get('window') as HistoryWindow) || '7d') as HistoryWindow;

  const [tab, setTab] = useState<ThreatTab>(
    TAB_OPTIONS.some((o) => o.key === initialTab) ? initialTab : 'active'
  );
  const [window, setWindow] = useState<HistoryWindow>(
    initialWindow === '30d' ? '30d' : '7d'
  );

  const [active, setActive] = useState<Threat[]>(initial.active);
  const [resolved, setResolved] = useState<ResolvedThreat[]>(initial.resolved);
  const [busy, setBusy] = useState(false);

  const [investigating, setInvestigating] = useState<Threat | null>(null);
  const [resolveOf, setResolveOf] = useState<Threat | null>(null);
  const [dismissOf, setDismissOf] = useState<Threat | null>(null);

  // Push URL state on tab/window changes so back-button / sharing works.
  useEffect(() => {
    const next = new URLSearchParams(params.toString());
    next.set('tab', tab);
    next.set('window', window);
    const qs = next.toString();
    const cur = params.toString();
    if (qs !== cur) {
      startTransition(() => {
        router.replace(`/admin/threats?${qs}`, { scroll: false });
      });
    }
  }, [tab, window, params, router]);

  // Refetch resolved when window changes.
  useEffect(() => {
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBusy(true);
    fetch(`/api/admin/threats/history?window=${window}`)
      .then((r) => r.json())
      .then((d: { threats?: ResolvedThreat[] }) => {
        if (cancelled) return;
        if (Array.isArray(d.threats)) setResolved(d.threats);
      })
      .catch(() => {
        // Keep stale data on screen
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [window]);

  async function refreshAll() {
    setBusy(true);
    try {
      const [aRes, rRes] = await Promise.all([
        fetch('/api/admin/threats').then((r) => r.json()),
        fetch(`/api/admin/threats/history?window=${window}`).then((r) => r.json()),
      ]);
      if (Array.isArray(aRes.threats)) setActive(aRes.threats);
      if (Array.isArray(rRes.threats)) setResolved(rRes.threats);
    } catch {
      // Keep stale
    } finally {
      setBusy(false);
    }
  }

  function onResolved() {
    setResolveOf(null);
    setInvestigating(null);
    void refreshAll();
  }

  function onDismissed() {
    setDismissOf(null);
    setInvestigating(null);
    void refreshAll();
  }

  const counts = {
    active: active.length,
    resolved: resolved.filter((r) => r.resolutionKind === 'RESOLVED').length,
    false_positive: resolved.filter((r) => r.resolutionKind === 'FALSE_POSITIVE').length,
  };

  return (
    <div className="min-h-screen bg-linear-bg text-linear-text">
      <header className="sticky top-0 z-20 border-b border-linear-border bg-linear-surface-1/95 backdrop-blur supports-[backdrop-filter]:bg-linear-surface-1/85">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3">
          <div>
            <div className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-linear-text-3 mb-1">
              Admin · Security
            </div>
            <h1 className="text-[20px] font-semibold tracking-tight text-linear-text leading-tight">
              Threats
            </h1>
            <div className="mt-1 text-[11px] text-linear-text-3">
              <span className="font-mono tabular-nums text-linear-text-2">{counts.active}</span> active
              <span className="mx-1.5 text-linear-text-3">·</span>
              <span className="font-mono tabular-nums text-linear-text-2">{counts.resolved}</span> resolved
              <span className="mx-1.5 text-linear-text-3">·</span>
              <span className="font-mono tabular-nums text-linear-text-2">{counts.false_positive}</span> dismissed
            </div>
          </div>
          <div className="flex items-center gap-2">
            {tab !== 'active' && (
              <WindowSelector value={window} onChange={setWindow} />
            )}
            <button
              type="button"
              onClick={() => void refreshAll()}
              disabled={busy}
              className="qm-lin-btn"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${busy ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <AdminNav />

      <main className="mx-auto max-w-[1440px] px-6 py-6">
        <Tabs tab={tab} onChange={setTab} counts={counts} />

        {tab === 'active' && (
          <ActiveList
            rows={active}
            onInvestigate={(t) => setInvestigating(t)}
            onResolve={(t) => setResolveOf(t)}
            onDismiss={(t) => setDismissOf(t)}
          />
        )}
        {tab === 'resolved' && (
          <ResolvedList
            rows={resolved.filter((r) => r.resolutionKind === 'RESOLVED')}
            kind="resolved"
          />
        )}
        {tab === 'false_positive' && (
          <ResolvedList
            rows={resolved.filter((r) => r.resolutionKind === 'FALSE_POSITIVE')}
            kind="false_positive"
          />
        )}
      </main>

      {investigating && (
        <InvestigateDrawer
          threat={investigating}
          onClose={() => setInvestigating(null)}
          onResolve={() => {
            setResolveOf(investigating);
          }}
          onDismiss={() => {
            setDismissOf(investigating);
          }}
        />
      )}
      {resolveOf && (
        <ResolveModal
          threat={resolveOf}
          onClose={() => setResolveOf(null)}
          onResolved={onResolved}
        />
      )}
      {dismissOf && (
        <DismissModal
          threat={dismissOf}
          onClose={() => setDismissOf(null)}
          onDismissed={onDismissed}
        />
      )}
    </div>
  );
}

// --------------------------------------------------------------------------
// Tabs
// --------------------------------------------------------------------------

function Tabs({
  tab,
  onChange,
  counts,
}: {
  tab: ThreatTab;
  onChange: (t: ThreatTab) => void;
  counts: Record<ThreatTab, number>;
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

// --------------------------------------------------------------------------
// Active list
// --------------------------------------------------------------------------

function ActiveList({
  rows,
  onInvestigate,
  onResolve,
  onDismiss,
}: {
  rows: Threat[];
  onInvestigate: (t: Threat) => void;
  onResolve: (t: Threat) => void;
  onDismiss: (t: Threat) => void;
}) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No active threats"
        body="The detectors are clean over the last 24 hours. Nice."
      />
    );
  }
  return (
    <ul className="space-y-2">
      {rows.map((t) => {
        const isRed = t.severity === 'red';
        return (
          <li
            key={t.id}
            className="flex items-start justify-between gap-4 rounded-lg border bg-linear-surface-1 p-4"
            style={{
              borderColor: isRed
                ? 'rgba(212,87,74,0.32)'
                : 'rgba(212,164,55,0.32)',
            }}
          >
            <div className="flex min-w-0 items-start gap-3">
              <span
                className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
                style={{
                  background: isRed ? 'rgba(212,87,74,0.18)' : 'rgba(212,164,55,0.18)',
                  color: isRed ? 'var(--color-linear-danger)' : 'var(--color-linear-warning)',
                }}
              >
                <AlertTriangle className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span
                    className="rounded px-1.5 py-0.5 font-mono text-[10px] font-medium uppercase tracking-[0.05em]"
                    style={{
                      background: isRed ? 'rgba(212,87,74,0.18)' : 'rgba(212,164,55,0.18)',
                      color: isRed ? 'var(--color-linear-danger)' : 'var(--color-linear-warning)',
                    }}
                  >
                    {t.severity}
                  </span>
                  <span className="font-mono text-[10px] text-linear-text-3">{t.type}</span>
                </div>
                <div className="mt-1 truncate text-sm font-medium text-linear-text">
                  {t.summary}
                </div>
                <div className="mt-0.5 text-[12px] text-linear-text-2">{t.detail}</div>
                <div className="mt-1 font-mono text-[10px] text-linear-text-3">{t.id}</div>
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              <button
                type="button"
                onClick={() => onInvestigate(t)}
                className="qm-lin-btn"
              >
                <Eye className="h-3.5 w-3.5" />
                Investigate
              </button>
              <button
                type="button"
                onClick={() => onResolve(t)}
                className="qm-lin-btn-primary"
              >
                <CheckCircle2 className="h-3.5 w-3.5" />
                Resolve
              </button>
              <button
                type="button"
                onClick={() => onDismiss(t)}
                className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-[11px] font-medium transition-colors"
                style={{
                  background: 'rgba(212,164,55,0.15)',
                  color: 'var(--color-linear-warning)',
                  boxShadow: 'inset 0 0 0 1px rgba(212,164,55,0.30)',
                }}
              >
                <ShieldOff className="h-3.5 w-3.5" />
                Dismiss
              </button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

// --------------------------------------------------------------------------
// Resolved/false-positive list
// --------------------------------------------------------------------------

function ResolvedList({
  rows,
  kind,
}: {
  rows: ResolvedThreat[];
  kind: 'resolved' | 'false_positive';
}) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title={kind === 'resolved' ? 'No resolved threats' : 'No dismissed threats'}
        body={
          kind === 'resolved'
            ? 'Resolved actions will show up here with the admin and timestamp.'
            : 'Threats marked as false positive will show up here.'
        }
      />
    );
  }
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li
          key={r.id}
          className="flex items-start justify-between gap-4 rounded-lg border border-linear-border bg-linear-surface-1 p-4"
        >
          <div className="flex min-w-0 items-start gap-3">
            <span
              className="mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full"
              style={{
                background:
                  kind === 'resolved'
                    ? 'var(--color-linear-sage-tint)'
                    : 'rgba(212,164,55,0.18)',
                color:
                  kind === 'resolved'
                    ? 'var(--color-linear-sage-bright)'
                    : 'var(--color-linear-warning)',
              }}
            >
              {kind === 'resolved' ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <ShieldOff className="h-4 w-4" />
              )}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-linear-text-3">{r.type}</span>
              </div>
              <div className="mt-1 truncate text-sm font-medium text-linear-text">
                {r.summary}
              </div>
              <div className="mt-0.5 text-[12px] text-linear-text-2">{r.detail}</div>
              {r.note && (
                <blockquote className="mt-2 rounded border-l-2 border-linear-border bg-linear-surface-2 px-2 py-1 text-[12px] italic text-linear-text-2">
                  {r.note}
                </blockquote>
              )}
              <div className="mt-1 font-mono text-[10px] text-linear-text-3">{r.id}</div>
            </div>
          </div>
          <div className="shrink-0 text-right text-[11px] text-linear-text-3">
            <div className="font-mono tabular-nums">{formatLocal(r.resolvedAt)}</div>
            <div className="mt-0.5 text-linear-text-2">{r.resolvedByEmail ?? 'system'}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------
// Misc
// --------------------------------------------------------------------------

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border border-linear-border bg-linear-sage-tint p-8 text-center">
      <CheckCircle2 className="mx-auto h-8 w-8 text-linear-sage-bright" />
      <h3 className="mt-2 text-sm font-semibold text-linear-sage-bright">{title}</h3>
      <p className="mt-1 text-[12px] text-linear-text-2">{body}</p>
    </div>
  );
}

function WindowSelector({
  value,
  onChange,
}: {
  value: HistoryWindow;
  onChange: (w: HistoryWindow) => void;
}) {
  return (
    <label className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as HistoryWindow)}
        className="cursor-pointer appearance-none rounded-md border border-linear-border bg-linear-surface-2 py-1.5 pl-2.5 pr-7 text-[12px] font-medium text-linear-text-2 hover:border-linear-border-strong hover:text-linear-text focus:outline-none"
      >
        <option value="7d" className="bg-linear-surface-2 text-linear-text">Last 7 days</option>
        <option value="30d" className="bg-linear-surface-2 text-linear-text">Last 30 days</option>
      </select>
      <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-linear-text-3" />
    </label>
  );
}

function formatLocal(iso: string): string {
  const d = new Date(iso);
  const yy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  const hh = String(d.getHours()).padStart(2, '0');
  const mi = String(d.getMinutes()).padStart(2, '0');
  return `${yy}-${mm}-${dd} ${hh}:${mi}`;
}
