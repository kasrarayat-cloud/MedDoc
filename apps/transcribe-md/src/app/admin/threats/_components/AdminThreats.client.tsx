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
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the slate-on-white rendering
// verbatim. Clinician branch renders the same data using `.qm-cl-card`,
// `.qm-cl-pill-{coral,amber,sage}` for severity badges, and the
// cream/sage/ink palette. Refetch logic + URL state sync are
// unchanged. Drawer + modals receive `theme="clinician"`.
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

type AdminThreatsTheme = 'legacy' | 'clinician';

interface Props {
  initial: AdminThreatsInitialData;
  theme?: AdminThreatsTheme;
}

const TAB_OPTIONS: { key: ThreatTab; label: string }[] = [
  { key: 'active', label: 'Active' },
  { key: 'resolved', label: 'Resolved' },
  { key: 'false_positive', label: 'False positives' },
];

export default function AdminThreats({ initial, theme = 'legacy' }: Props) {
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

  const isClinician = theme === 'clinician';

  return (
    <div
      className={isClinician ? '' : 'min-h-screen bg-slate-50 text-slate-900'}
      style={isClinician ? { minHeight: '100vh', color: 'var(--ink)' } : undefined}
    >
      <header
        className={
          isClinician
            ? ''
            : 'sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85'
        }
        style={
          isClinician
            ? {
                position: 'sticky',
                top: 0,
                zIndex: 20,
                borderBottom: '1px solid var(--line)',
                background: 'var(--cream-card)',
              }
            : undefined
        }
      >
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-4">
          <div>
            {isClinician ? (
              <>
                <div className="qm-cl-eyebrow" style={{ marginBottom: 4 }}>
                  Admin · Security
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
                  Threats
                </h1>
                <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-3)' }}>
                  <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
                    {counts.active}
                  </span>{' '}
                  active
                  <span style={{ margin: '0 8px', color: 'var(--ink-4)' }}>·</span>
                  <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
                    {counts.resolved}
                  </span>{' '}
                  resolved
                  <span style={{ margin: '0 8px', color: 'var(--ink-4)' }}>·</span>
                  <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
                    {counts.false_positive}
                  </span>{' '}
                  dismissed
                </div>
              </>
            ) : (
              <>
                <h1 className="text-xl font-semibold tracking-tight text-slate-900">Threats</h1>
                <div className="mt-0.5 text-[11px] text-slate-500">
                  <span className="font-mono tabular-nums text-slate-700">{counts.active}</span> active
                  <span className="mx-1.5 text-slate-300">·</span>
                  <span className="font-mono tabular-nums text-slate-700">{counts.resolved}</span> resolved
                  <span className="mx-1.5 text-slate-300">·</span>
                  <span className="font-mono tabular-nums text-slate-700">{counts.false_positive}</span> dismissed
                </div>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
            {tab !== 'active' && (
              <WindowSelector value={window} onChange={setWindow} theme={theme} />
            )}
            <button
              type="button"
              onClick={() => void refreshAll()}
              disabled={busy}
              className={
                isClinician
                  ? 'qm-cl-btn qm-cl-btn-soft'
                  : 'inline-flex items-center gap-1.5 rounded border border-slate-300 bg-white px-2.5 py-1.5 text-[12px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50'
              }
              style={isClinician ? { height: 32, padding: '0 12px', fontSize: 12, opacity: busy ? 0.5 : 1 } : undefined}
            >
              <RefreshCw
                className={busy ? 'animate-spin' : ''}
                style={isClinician ? { width: 14, height: 14 } : undefined}
              />
              Refresh
            </button>
          </div>
        </div>
      </header>

      <AdminNav theme={theme} />

      <main className="mx-auto max-w-[1440px] px-6 py-6">
        <Tabs tab={tab} onChange={setTab} counts={counts} theme={theme} />

        {tab === 'active' && (
          <ActiveList
            rows={active}
            onInvestigate={(t) => setInvestigating(t)}
            onResolve={(t) => setResolveOf(t)}
            onDismiss={(t) => setDismissOf(t)}
            theme={theme}
          />
        )}
        {tab === 'resolved' && (
          <ResolvedList
            rows={resolved.filter((r) => r.resolutionKind === 'RESOLVED')}
            kind="resolved"
            theme={theme}
          />
        )}
        {tab === 'false_positive' && (
          <ResolvedList
            rows={resolved.filter((r) => r.resolutionKind === 'FALSE_POSITIVE')}
            kind="false_positive"
            theme={theme}
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
          theme={theme}
        />
      )}
      {resolveOf && (
        <ResolveModal
          threat={resolveOf}
          onClose={() => setResolveOf(null)}
          onResolved={onResolved}
          theme={theme}
        />
      )}
      {dismissOf && (
        <DismissModal
          threat={dismissOf}
          onClose={() => setDismissOf(null)}
          onDismissed={onDismissed}
          theme={theme}
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
  theme = 'legacy',
}: {
  tab: ThreatTab;
  onChange: (t: ThreatTab) => void;
  counts: Record<ThreatTab, number>;
  theme?: AdminThreatsTheme;
}) {
  if (theme === 'clinician') {
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
              style={{
                marginBottom: -1,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
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
  return (
    <nav className="mb-5 flex items-center gap-1 border-b border-slate-200">
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

// --------------------------------------------------------------------------
// Active list
// --------------------------------------------------------------------------

function ActiveList({
  rows,
  onInvestigate,
  onResolve,
  onDismiss,
  theme = 'legacy',
}: {
  rows: Threat[];
  onInvestigate: (t: Threat) => void;
  onResolve: (t: Threat) => void;
  onDismiss: (t: Threat) => void;
  theme?: AdminThreatsTheme;
}) {
  if (rows.length === 0) {
    return (
      <EmptyState
        title="No active threats"
        body="The detectors are clean over the last 24 hours. Nice."
        theme={theme}
      />
    );
  }
  if (theme === 'clinician') {
    return (
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {rows.map((t) => {
          const isRed = t.severity === 'red';
          const accentBg = isRed ? 'var(--coral-tint)' : 'var(--amber-tint)';
          const accentFg = isRed ? 'var(--coral-deep)' : 'var(--amber-deep)';
          return (
            <li
              key={t.id}
              className="qm-cl-card"
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: 16,
                padding: 16,
                borderColor: isRed ? 'var(--coral-tint)' : 'var(--amber-tint-strong, rgba(212,165,116,0.32))',
              }}
            >
              <div style={{ display: 'flex', minWidth: 0, alignItems: 'flex-start', gap: 12 }}>
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
                    background: accentBg,
                    color: accentFg,
                  }}
                >
                  <AlertTriangle style={{ width: 14, height: 14 }} />
                </span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span
                      className={`qm-cl-pill ${isRed ? 'qm-cl-pill-coral' : 'qm-cl-pill-amber'}`}
                      style={{ fontSize: 10, padding: '2px 8px', textTransform: 'uppercase', letterSpacing: '0.04em' }}
                    >
                      {t.severity}
                    </span>
                    <span className="qm-cl-mono" style={{ fontSize: 10, color: 'var(--ink-3)' }}>
                      {t.type}
                    </span>
                  </div>
                  <div
                    style={{
                      marginTop: 4,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      fontSize: 13,
                      fontWeight: 500,
                      color: 'var(--ink)',
                    }}
                  >
                    {t.summary}
                  </div>
                  <div style={{ marginTop: 2, fontSize: 12, color: 'var(--ink-2)' }}>{t.detail}</div>
                  <div className="qm-cl-mono" style={{ marginTop: 4, fontSize: 10, color: 'var(--ink-4)' }}>
                    {t.id}
                  </div>
                </div>
              </div>
              <div style={{ display: 'flex', flexShrink: 0, alignItems: 'center', gap: 6 }}>
                <button
                  type="button"
                  onClick={() => onInvestigate(t)}
                  className="qm-cl-btn qm-cl-btn-soft"
                  style={{ height: 30, padding: '0 12px', fontSize: 11, gap: 6 }}
                >
                  <Eye style={{ width: 12, height: 12 }} />
                  Investigate
                </button>
                <button
                  type="button"
                  onClick={() => onResolve(t)}
                  className="qm-cl-btn qm-cl-btn-primary"
                  style={{ height: 30, padding: '0 12px', fontSize: 11, gap: 6 }}
                >
                  <CheckCircle2 style={{ width: 12, height: 12 }} />
                  Resolve
                </button>
                <button
                  type="button"
                  onClick={() => onDismiss(t)}
                  className="qm-cl-btn qm-cl-btn-soft"
                  style={{
                    height: 30,
                    padding: '0 12px',
                    fontSize: 11,
                    gap: 6,
                    color: 'var(--amber-deep)',
                    background: 'var(--amber-tint)',
                  }}
                >
                  <ShieldOff style={{ width: 12, height: 12 }} />
                  Dismiss
                </button>
              </div>
            </li>
          );
        })}
      </ul>
    );
  }
  return (
    <ul className="space-y-2">
      {rows.map((t) => (
        <li
          key={t.id}
          className={
            'flex items-start justify-between gap-4 rounded-lg border bg-white p-4 ' +
            (t.severity === 'red'
              ? 'border-rose-200'
              : 'border-amber-200')
          }
        >
          <div className="flex min-w-0 items-start gap-3">
            <span
              className={
                'mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full ' +
                (t.severity === 'red'
                  ? 'bg-rose-100 text-rose-700'
                  : 'bg-amber-100 text-amber-700')
              }
            >
              <AlertTriangle className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span
                  className={
                    'rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ' +
                    (t.severity === 'red'
                      ? 'bg-rose-100 text-rose-800'
                      : 'bg-amber-100 text-amber-800')
                  }
                >
                  {t.severity}
                </span>
                <span className="font-mono text-[10px] text-slate-400">{t.type}</span>
              </div>
              <div className="mt-1 truncate text-sm font-medium text-slate-900">
                {t.summary}
              </div>
              <div className="mt-0.5 text-[12px] text-slate-600">{t.detail}</div>
              <div className="mt-1 font-mono text-[10px] text-slate-400">{t.id}</div>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <button
              type="button"
              onClick={() => onInvestigate(t)}
              className="inline-flex items-center gap-1.5 rounded border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-medium text-slate-700 hover:bg-slate-50"
            >
              <Eye className="h-3.5 w-3.5" />
              Investigate
            </button>
            <button
              type="button"
              onClick={() => onResolve(t)}
              className="inline-flex items-center gap-1.5 rounded bg-emerald-600 px-2.5 py-1.5 text-[11px] font-medium text-white hover:bg-emerald-700"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Resolve
            </button>
            <button
              type="button"
              onClick={() => onDismiss(t)}
              className="inline-flex items-center gap-1.5 rounded border border-amber-300 bg-white px-2.5 py-1.5 text-[11px] font-medium text-amber-800 hover:bg-amber-50"
            >
              <ShieldOff className="h-3.5 w-3.5" />
              Dismiss
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------
// Resolved/false-positive list
// --------------------------------------------------------------------------

function ResolvedList({
  rows,
  kind,
  theme = 'legacy',
}: {
  rows: ResolvedThreat[];
  kind: 'resolved' | 'false_positive';
  theme?: AdminThreatsTheme;
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
        theme={theme}
      />
    );
  }
  if (theme === 'clinician') {
    return (
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {rows.map((r) => (
          <li
            key={r.id}
            className="qm-cl-card"
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: 16,
              padding: 16,
            }}
          >
            <div style={{ display: 'flex', minWidth: 0, alignItems: 'flex-start', gap: 12 }}>
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
                  background:
                    kind === 'resolved' ? 'var(--sage-tint-strong)' : 'var(--amber-tint)',
                  color: kind === 'resolved' ? 'var(--sage-deep)' : 'var(--amber-deep)',
                }}
              >
                {kind === 'resolved' ? (
                  <CheckCircle2 style={{ width: 14, height: 14 }} />
                ) : (
                  <ShieldOff style={{ width: 14, height: 14 }} />
                )}
              </span>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span className="qm-cl-mono" style={{ fontSize: 10, color: 'var(--ink-3)' }}>
                    {r.type}
                  </span>
                </div>
                <div
                  style={{
                    marginTop: 4,
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    fontSize: 13,
                    fontWeight: 500,
                    color: 'var(--ink)',
                  }}
                >
                  {r.summary}
                </div>
                <div style={{ marginTop: 2, fontSize: 12, color: 'var(--ink-2)' }}>{r.detail}</div>
                {r.note && (
                  <blockquote
                    style={{
                      marginTop: 8,
                      borderRadius: 8,
                      borderLeft: '2px solid var(--cream-3)',
                      background: 'var(--cream-2)',
                      padding: '6px 10px',
                      fontSize: 12,
                      fontStyle: 'italic',
                      color: 'var(--ink-2)',
                    }}
                  >
                    {r.note}
                  </blockquote>
                )}
                <div className="qm-cl-mono" style={{ marginTop: 4, fontSize: 10, color: 'var(--ink-4)' }}>
                  {r.id}
                </div>
              </div>
            </div>
            <div style={{ flexShrink: 0, textAlign: 'right', fontSize: 11, color: 'var(--ink-3)' }}>
              <div className="qm-cl-mono">{formatLocal(r.resolvedAt)}</div>
              <div style={{ marginTop: 2, color: 'var(--ink-2)' }}>{r.resolvedByEmail ?? 'system'}</div>
            </div>
          </li>
        ))}
      </ul>
    );
  }
  return (
    <ul className="space-y-2">
      {rows.map((r) => (
        <li
          key={r.id}
          className="flex items-start justify-between gap-4 rounded-lg border border-slate-200 bg-white p-4"
        >
          <div className="flex min-w-0 items-start gap-3">
            <span
              className={
                'mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full ' +
                (kind === 'resolved'
                  ? 'bg-emerald-100 text-emerald-700'
                  : 'bg-amber-100 text-amber-700')
              }
            >
              {kind === 'resolved' ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : (
                <ShieldOff className="h-4 w-4" />
              )}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-slate-400">{r.type}</span>
              </div>
              <div className="mt-1 truncate text-sm font-medium text-slate-900">
                {r.summary}
              </div>
              <div className="mt-0.5 text-[12px] text-slate-600">{r.detail}</div>
              {r.note && (
                <blockquote className="mt-2 rounded border-l-2 border-slate-300 bg-slate-50 px-2 py-1 text-[12px] italic text-slate-700">
                  {r.note}
                </blockquote>
              )}
              <div className="mt-1 font-mono text-[10px] text-slate-400">{r.id}</div>
            </div>
          </div>
          <div className="shrink-0 text-right text-[11px] text-slate-500">
            <div>{formatLocal(r.resolvedAt)}</div>
            <div className="mt-0.5 text-slate-700">{r.resolvedByEmail ?? 'system'}</div>
          </div>
        </li>
      ))}
    </ul>
  );
}

// --------------------------------------------------------------------------
// Misc
// --------------------------------------------------------------------------

function EmptyState({ title, body, theme = 'legacy' }: { title: string; body: string; theme?: AdminThreatsTheme }) {
  if (theme === 'clinician') {
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
        <CheckCircle2 style={{ margin: '0 auto', width: 32, height: 32, color: 'var(--sage-deep)' }} />
        <h3 style={{ marginTop: 8, fontSize: 14, fontWeight: 600, color: 'var(--sage-deep)' }}>{title}</h3>
        <p style={{ marginTop: 4, fontSize: 12, color: 'var(--sage-deep)', opacity: 0.85 }}>{body}</p>
      </div>
    );
  }
  return (
    <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-8 text-center">
      <CheckCircle2 className="mx-auto h-8 w-8 text-emerald-600" />
      <h3 className="mt-2 text-sm font-semibold text-emerald-900">{title}</h3>
      <p className="mt-1 text-[12px] text-emerald-800">{body}</p>
    </div>
  );
}

function WindowSelector({
  value,
  onChange,
  theme = 'legacy',
}: {
  value: HistoryWindow;
  onChange: (w: HistoryWindow) => void;
  theme?: AdminThreatsTheme;
}) {
  if (theme === 'clinician') {
    return (
      <label style={{ position: 'relative' }}>
        <select
          value={value}
          onChange={(e) => onChange(e.target.value as HistoryWindow)}
          className="qm-cl-input"
          style={{
            height: 32,
            fontSize: 12,
            fontWeight: 500,
            padding: '0 28px 0 12px',
            appearance: 'none',
            cursor: 'pointer',
          }}
        >
          <option value="7d">Last 7 days</option>
          <option value="30d">Last 30 days</option>
        </select>
        <ChevronDown
          style={{
            pointerEvents: 'none',
            position: 'absolute',
            right: 8,
            top: '50%',
            width: 12,
            height: 12,
            transform: 'translateY(-50%)',
            color: 'var(--ink-3)',
          }}
        />
      </label>
    );
  }
  return (
    <label className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as HistoryWindow)}
        className="cursor-pointer appearance-none rounded border border-slate-300 bg-white py-1.5 pl-2.5 pr-7 text-[12px] font-medium text-slate-700 hover:bg-slate-50 focus:outline-none"
      >
        <option value="7d">Last 7 days</option>
        <option value="30d">Last 30 days</option>
      </select>
      <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
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
