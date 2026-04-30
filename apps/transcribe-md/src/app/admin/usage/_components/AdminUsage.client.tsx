'use client';

// ============================================================================
// /admin/usage — orchestrator + presentational sub-components
// ----------------------------------------------------------------------------
// Window selector, top stat strip, hand-rolled stacked-area timeline,
// per-provider breakdown bars, top-users list, and anomalies panel —
// all in this file. Mirrors the AdminOverview pattern (sub-components
// inline because they're only used here).
//
// Initial data comes from the server `page.tsx`; window changes refetch
// via the existing /api/admin/usage/{summary,timeline,by-user} endpoints.
// Anomalies don't have a JSON endpoint yet — the server seed is the
// only source until that lands. The Refresh button bumps a tick that
// triggers `router.refresh()` so the server data re-runs.
//
// Phase 2 (Clinician remodel) — Strategy A dual-theme via additive
// `theme` prop. Default `'legacy'` keeps the slate-on-white rendering
// verbatim. Clinician branch wraps the canvas in cream-card, swaps the
// header chrome to the eyebrow + serif headline pattern, and re-styles
// the breakdown/top-users/anomalies cards using `.qm-cl-card`,
// `.qm-cl-pill-*`, and the cream/sage/ink palette. The hand-rolled
// SVG stacked-area chart keeps its provider colors (semantic), but
// the surrounding chart card switches palette.
// ============================================================================

import { useEffect, useState, useTransition } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  ChevronDown,
  RefreshCw,
  Users as UsersIcon,
} from 'lucide-react';

import {
  cls,
  formatCount2,
  formatDay,
  formatUsd2,
  PROVIDER_COLOR,
  PROVIDER_LABEL,
  PROVIDER_ORDER,
  WINDOW_LABELS,
  avatarPaletteSm,
  userInitials,
} from '../../_lib/admin-format';
import AdminNav from '../../_components/AdminNav.client';
import type {
  AdminUsageInitialData,
  Anomaly,
  TimelineBucket,
  TimelineResponse,
  TopUserRow,
  TopUsersResponse,
  UsageSummary,
  WindowKey,
} from '../_types';

type AdminUsageTheme = 'legacy' | 'clinician';

interface Props {
  initial: AdminUsageInitialData;
  theme?: AdminUsageTheme;
}

export default function AdminUsage({ initial, theme = 'legacy' }: Props) {
  const router = useRouter();
  const [, startTransition] = useTransition();

  const [windowKey, setWindowKey] = useState<WindowKey>(
    (initial.summary.window as WindowKey) ?? 'month'
  );
  const [summary, setSummary] = useState<UsageSummary>(initial.summary);
  const [timeline, setTimeline] = useState<TimelineResponse>(initial.timeline);
  const [topUsers, setTopUsers] = useState<TopUsersResponse>(initial.topUsers);
  const anomalies = initial.anomalies;
  const [busy, setBusy] = useState(false);

  // On window change, fetch the three live endpoints in parallel.
  useEffect(() => {
    if (windowKey === (initial.summary.window as WindowKey)) return;
    let cancelled = false;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setBusy(true);
    const qs = `?window=${windowKey}`;
    Promise.all([
      fetch(`/api/admin/usage/summary${qs}`).then((r) => r.json()),
      fetch(`/api/admin/usage/timeline${qs}`).then((r) => r.json()),
      fetch(`/api/admin/usage/by-user${qs}&limit=10`).then((r) => r.json()),
    ])
      .then(([s, t, u]) => {
        if (cancelled) return;
        setSummary(s);
        setTimeline(t);
        setTopUsers(u);
      })
      .catch(() => {
        // Swallow — keep stale data on screen rather than blanking it
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [windowKey, initial.summary.window]);

  const totalSpend = summary.totalCostUsd;
  const totalEvents = summary.totalEvents;
  const activeUsers = topUsers.rows.length;
  const avgPerUser = activeUsers > 0 ? totalSpend / activeUsers : 0;
  const pctChange = summary.vsLastPeriod.percentChange ?? 0;

  // Map provider rollup → ordered breakdown rows. We project the
  // friendly unit string (token-count etc.) from PROVIDER_LABEL plus a
  // synthesised unit count where we don't have it (the summary endpoint
  // only returns dollars, not units — for unit precision the drawer
  // hits the per-user endpoint).
  const breakdownRows = PROVIDER_ORDER.map((k) => ({
    key: k,
    label: PROVIDER_LABEL[k],
    costUsd: summary.byProvider[k] ?? 0,
    unitCount: 0,
    unitLabel: '',
  })).filter((r) => r.costUsd > 0);

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
            <div>
              <div className="qm-cl-eyebrow" style={{ marginBottom: 4 }}>
                Admin · Usage
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
                API usage &amp; costs
              </h1>
              <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-3)' }}>
                <span style={{ color: 'var(--ink-2)', fontWeight: 500 }}>QuillMD</span>
                <span style={{ margin: '0 8px', color: 'var(--ink-4)' }}>·</span>
                window{' '}
                <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
                  {WINDOW_LABELS[windowKey] ?? windowKey}
                </span>
                {busy && (
                  <>
                    <span style={{ margin: '0 8px', color: 'var(--ink-4)' }}>·</span>
                    <span style={{ color: 'var(--ink-3)' }}>refreshing…</span>
                  </>
                )}
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <ClinicianWindowSelector value={windowKey} onChange={setWindowKey} />
              <button
                type="button"
                onClick={() => startTransition(() => router.refresh())}
                className="qm-cl-btn qm-cl-btn-soft"
                style={{ height: 32, padding: '0 12px', fontSize: 12 }}
              >
                <RefreshCw style={{ width: 12, height: 12 }} />
                Refresh
              </button>
            </div>
          </div>
        </header>
        <AdminNav theme="clinician" />

        <main className="mx-auto max-w-[1440px] px-6 py-6" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <ClinicianTopStatBar
            total={totalSpend}
            pctChange={pctChange}
            events={totalEvents}
            activeUsers={activeUsers}
            avgPerUser={avgPerUser}
          />
          <ClinicianTimelineChart buckets={timeline.buckets} />
          <section className="grid grid-cols-1 gap-4 lg:grid-cols-5">
            <div className="lg:col-span-3">
              <ClinicianProviderBreakdown rows={breakdownRows} total={totalSpend} />
            </div>
            <div className="space-y-4 lg:col-span-2">
              <ClinicianTopUsers rows={topUsers.rows} />
              <ClinicianAnomaliesPanel items={anomalies} />
            </div>
          </section>
          <footer style={{ paddingTop: 16, fontSize: 11, color: 'var(--ink-4)' }}>
            Cost figures aggregated from per-call api_usage_events rows. Pricing snapshotted at log time, so historical totals reflect the rate that was charged.
          </footer>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-slate-900">
              API Usage &amp; Costs
            </h1>
            <div className="mt-0.5 text-[11px] text-slate-500">
              <span className="font-medium text-slate-600">QuillMD</span>
              <span className="mx-1.5 text-slate-300">·</span>
              <span>
                window{' '}
                <span className="font-mono tabular-nums text-slate-700">
                  {WINDOW_LABELS[windowKey] ?? windowKey}
                </span>
              </span>
              {busy && (
                <>
                  <span className="mx-1.5 text-slate-300">·</span>
                  <span className="text-slate-400">refreshing…</span>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <WindowSelector value={windowKey} onChange={setWindowKey} />
            <button
              type="button"
              onClick={() => startTransition(() => router.refresh())}
              className="inline-flex h-8 items-center rounded-md border border-slate-200 bg-white px-2.5 text-xs hover:bg-slate-50"
            >
              <RefreshCw className="mr-1.5 h-3 w-3" />
              Refresh
            </button>
          </div>
        </div>
      </header>
      <AdminNav />

      <main className="mx-auto max-w-[1440px] space-y-4 px-6 py-5">
        <TopStatBar
          total={totalSpend}
          pctChange={pctChange}
          events={totalEvents}
          activeUsers={activeUsers}
          avgPerUser={avgPerUser}
        />
        <TimelineChart buckets={timeline.buckets} />
        <section className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <ProviderBreakdown rows={breakdownRows} total={totalSpend} />
          </div>
          <div className="space-y-4 lg:col-span-2">
            <TopUsers rows={topUsers.rows} />
            <AnomaliesPanel items={anomalies} />
          </div>
        </section>
        <footer className="pt-4 text-[11px] text-slate-400">
          Cost figures aggregated from per-call api_usage_events rows. Pricing
          snapshotted at log time, so historical totals reflect the rate that
          was charged.
        </footer>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// WindowSelector
// ---------------------------------------------------------------------------

function WindowSelector({
  value,
  onChange,
}: {
  value: WindowKey;
  onChange: (v: WindowKey) => void;
}) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as WindowKey)}
        className="h-8 cursor-pointer appearance-none rounded-md border border-slate-200 bg-white py-0 pl-3 pr-8 text-xs font-medium text-slate-700 hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-300"
      >
        {(['24h', '7d', '30d', 'month'] as WindowKey[]).map((k) => (
          <option key={k} value={k}>
            {WINDOW_LABELS[k]}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-slate-400" />
    </div>
  );
}

// ---------------------------------------------------------------------------
// TopStatBar
// ---------------------------------------------------------------------------

function TopStatBar({
  total,
  pctChange,
  events,
  activeUsers,
  avgPerUser,
}: {
  total: number;
  pctChange: number;
  events: number;
  activeUsers: number;
  avgPerUser: number;
}) {
  const isUp = pctChange >= 0;
  return (
    <div className="rounded-md border border-slate-200 bg-white p-5">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">
            Total spend
          </div>
          <div className="font-mono text-3xl font-semibold tabular-nums text-slate-900">
            {formatUsd2(total)}
          </div>
        </div>
        <div
          className={cls(
            'inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium',
            isUp
              ? 'bg-amber-50 text-amber-800 ring-1 ring-amber-600/20'
              : 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20'
          )}
        >
          <span aria-hidden>{isUp ? '↑' : '↓'}</span>
          <span className="font-mono tabular-nums">{Math.abs(pctChange).toFixed(1)}%</span>
          <span className="text-slate-500">vs last period</span>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>
          <span className="font-mono tabular-nums text-slate-700">
            {events.toLocaleString()}
          </span>{' '}
          API calls
        </span>
        <span className="text-slate-300">·</span>
        <span>
          <span className="font-mono tabular-nums text-slate-700">{activeUsers}</span> active
          users
        </span>
        <span className="text-slate-300">·</span>
        <span>
          <span className="font-mono tabular-nums text-slate-700">
            {formatUsd2(avgPerUser)}
          </span>{' '}
          avg per user
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TimelineChart — hand-rolled stacked-area SVG, ported from the design
// ---------------------------------------------------------------------------

function TimelineChart({ buckets }: { buckets: TimelineBucket[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 1280,
    H = 200,
    padL = 44,
    padR = 16,
    padT = 16,
    padB = 28;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const dailyTotals = buckets.map((b) =>
    PROVIDER_ORDER.reduce((s, k) => s + (b.byProvider[k] ?? 0), 0)
  );
  const yMax = Math.max(1, ...dailyTotals) * 1.08;
  const yTicks = 4;
  const xFor = (i: number) =>
    padL + (buckets.length === 1 ? innerW / 2 : (i / (buckets.length - 1)) * innerW);
  const yFor = (v: number) => padT + innerH - (v / yMax) * innerH;
  const stacks: Record<string, number[]> = {};
  PROVIDER_ORDER.forEach((k) => (stacks[k] = []));
  buckets.forEach((b, i) => {
    let acc = 0;
    PROVIDER_ORDER.forEach((k) => {
      acc += b.byProvider[k] ?? 0;
      stacks[k]![i] = acc;
    });
  });
  function areaPath(top: number[], bottom: number[]): string {
    const n = top.length;
    if (n === 0) return '';
    let d = `M ${xFor(0)} ${yFor(top[0]!)}`;
    for (let i = 1; i < n; i++) d += ` L ${xFor(i)} ${yFor(top[i]!)}`;
    for (let i = n - 1; i >= 0; i--) d += ` L ${xFor(i)} ${yFor(bottom[i]!)}`;
    return d + ' Z';
  }
  const xLabelIdxs: number[] = (() => {
    const n = buckets.length,
      want = 5;
    if (n === 0) return [];
    const step = Math.max(1, Math.floor((n - 1) / (want - 1)));
    const set = new Set<number>();
    for (let i = 0; i < n; i += step) set.add(i);
    set.add(n - 1);
    return [...set].sort((a, b) => a - b);
  })();
  const yTickVals = Array.from({ length: yTicks + 1 }, (_, i) => (yMax * i) / yTicks);

  return (
    <div className="relative rounded-md border border-slate-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-slate-600" />
          <h2 className="text-sm font-semibold text-slate-900">Daily spend</h2>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-600">
          {PROVIDER_ORDER.map((k) => (
            <span key={k} className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-2.5 rounded-sm"
                style={{ background: PROVIDER_COLOR[k]?.fill }}
              />
              {PROVIDER_LABEL[k]}
            </span>
          ))}
        </div>
      </div>

      {buckets.length === 0 ? (
        <div className="flex h-[200px] items-center justify-center text-xs text-slate-500">
          No usage data in this window.
        </div>
      ) : (
        <div className="relative">
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="block h-[200px] w-full"
            preserveAspectRatio="none"
            onMouseLeave={() => setHover(null)}
          >
            {yTickVals.map((v, i) => (
              <g key={i}>
                <line
                  x1={padL}
                  x2={W - padR}
                  y1={yFor(v)}
                  y2={yFor(v)}
                  stroke="#f1f5f9"
                  strokeWidth={1}
                />
                <text
                  x={padL - 8}
                  y={yFor(v) + 3}
                  fontSize={10}
                  fill="#94a3b8"
                  textAnchor="end"
                  fontFamily="ui-monospace, Menlo, monospace"
                >
                  ${v.toFixed(0)}
                </text>
              </g>
            ))}
            {[...PROVIDER_ORDER].reverse().map((k) => {
              const top = stacks[k]!;
              const idx = PROVIDER_ORDER.indexOf(k);
              const below =
                idx === 0
                  ? buckets.map(() => 0)
                  : stacks[PROVIDER_ORDER[idx - 1]!]!;
              return (
                <path
                  key={k}
                  d={areaPath(top, below)}
                  fill={PROVIDER_COLOR[k]?.fill}
                  fillOpacity={0.78}
                  stroke={PROVIDER_COLOR[k]?.stroke}
                  strokeOpacity={0.6}
                  strokeWidth={0.75}
                />
              );
            })}
            {buckets.map((_, i) => {
              const slot = innerW / Math.max(1, buckets.length - 1);
              const x = xFor(i);
              return (
                <g key={i}>
                  <rect
                    x={x - slot / 2}
                    y={padT}
                    width={slot}
                    height={innerH}
                    fill="transparent"
                    onMouseEnter={() => setHover(i)}
                  />
                  {hover === i && (
                    <line
                      x1={x}
                      x2={x}
                      y1={padT}
                      y2={padT + innerH}
                      stroke="#0f172a"
                      strokeOpacity={0.18}
                      strokeWidth={1}
                    />
                  )}
                </g>
              );
            })}
            <line
              x1={padL}
              x2={W - padR}
              y1={padT + innerH + 0.5}
              y2={padT + innerH + 0.5}
              stroke="#e2e8f0"
              strokeWidth={1}
            />
            {xLabelIdxs.map((i) => (
              <text
                key={i}
                x={xFor(i)}
                y={H - 8}
                fontSize={10}
                fill="#64748b"
                textAnchor="middle"
                fontFamily="Inter, sans-serif"
              >
                {formatDay(buckets[i]!.time.slice(0, 10))}
              </text>
            ))}
          </svg>
          {hover !== null &&
            (() => {
              const b = buckets[hover]!;
              const total = PROVIDER_ORDER.reduce(
                (s, k) => s + (b.byProvider[k] ?? 0),
                0
              );
              const cxPct = (xFor(hover) / W) * 100;
              return (
                <div
                  className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-2 rounded-md border border-slate-200 bg-white px-2.5 py-2 text-[11px] shadow-md"
                  style={{ left: `${cxPct}%`, top: 0 }}
                >
                  <div className="mb-1 font-medium text-slate-800">
                    {formatDay(b.time.slice(0, 10))}
                  </div>
                  <div className="mb-1.5 font-mono text-sm font-semibold tabular-nums text-slate-900">
                    {formatUsd2(total)}
                  </div>
                  <ul className="space-y-0.5">
                    {[...PROVIDER_ORDER].reverse().map((k) => (
                      <li key={k} className="flex items-center gap-2">
                        <span
                          className="inline-block h-2 w-2 rounded-sm"
                          style={{ background: PROVIDER_COLOR[k]?.fill }}
                        />
                        <span className="w-16 text-slate-600">{PROVIDER_LABEL[k]}</span>
                        <span className="font-mono tabular-nums text-slate-800">
                          {formatUsd2(b.byProvider[k] ?? 0)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })()}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// ProviderBreakdown
// ---------------------------------------------------------------------------

function ProviderBreakdown({
  rows,
  total,
}: {
  rows: { key: string; label: string; costUsd: number; unitCount: number; unitLabel: string }[];
  total: number;
}) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Breakdown by provider</h2>
        <span className="text-[11px] text-slate-500">
          total{' '}
          <span className="font-mono tabular-nums text-slate-700">{formatUsd2(total)}</span>
        </span>
      </div>
      {rows.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-200 px-3 py-6 text-center text-xs text-slate-500">
          No spend in this window.
        </div>
      ) : (
        <ul className="space-y-3.5">
          {rows.map((r) => {
            const pct = total > 0 ? (r.costUsd / total) * 100 : 0;
            return (
              <li key={r.key}>
                <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                  <div className="flex items-center gap-2">
                    <span
                      className={cls(
                        'inline-block h-2.5 w-2.5 rounded-sm',
                        PROVIDER_COLOR[r.key]?.chip
                      )}
                    />
                    <span className="font-medium text-slate-800">{r.label}</span>
                  </div>
                  <div className="text-slate-600">
                    <span className="font-mono tabular-nums text-slate-900">
                      {formatUsd2(r.costUsd)}
                    </span>
                    <span className="mx-1.5 text-slate-300">·</span>
                    <span className="font-mono tabular-nums">{pct.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${pct}%`, background: PROVIDER_COLOR[r.key]?.fill }}
                  />
                </div>
                {r.unitLabel && (
                  <div className="mt-1 font-mono text-[11px] tabular-nums text-slate-500">
                    {formatCount2(r.unitCount)} {r.unitLabel}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// TopUsers
// ---------------------------------------------------------------------------

function TopUsers({ rows }: { rows: TopUserRow[] }) {
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <UsersIcon className="h-4 w-4 text-slate-600" />
          <h2 className="text-sm font-semibold text-slate-900">Top users by cost</h2>
        </div>
        <span className="text-[11px] text-slate-500">top 10</span>
      </div>
      {rows.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-200 px-3 py-6 text-center text-xs text-slate-500">
          No attributable usage.
        </div>
      ) : (
        <ol className="space-y-1">
          {rows.map((r, i) => {
            const id = r.userId ?? `unattributed-${i}`;
            const pal = avatarPaletteSm(id);
            return (
              <li key={id}>
                <Link
                  href={r.userId ? `/admin/users?search=${encodeURIComponent(r.userEmail)}` : '/admin/users'}
                  className="group flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-slate-50"
                >
                  <span className="w-4 shrink-0 font-mono text-xs tabular-nums text-slate-400">
                    {i + 1}.
                  </span>
                  <span
                    className={cls(
                      'flex h-6 w-6 shrink-0 items-center justify-center rounded-full ring-1 ring-slate-200',
                      pal.bg,
                      pal.text
                    )}
                  >
                    <span className="text-[10px] font-semibold tracking-tight">
                      {userInitials(r.userEmail)}
                    </span>
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-slate-800">
                      {r.userEmail}
                    </span>
                    <span className="block truncate font-mono text-[11px] tabular-nums text-slate-500">
                      {r.events.toLocaleString()} events
                    </span>
                  </span>
                  <span className="font-mono text-sm tabular-nums text-slate-900">
                    {formatUsd2(r.totalCostUsd)}
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
      <Link
        href="/admin/users"
        className="mt-2 inline-flex items-center gap-1 px-2 text-xs font-medium text-slate-700 hover:text-slate-900"
      >
        View all users <ArrowUpRight className="h-3 w-3" />
      </Link>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AnomaliesPanel — hides itself when empty
// ---------------------------------------------------------------------------

function AnomaliesPanel({ items }: { items: Anomaly[] }) {
  if (items.length === 0) return null;
  return (
    <div className="rounded-md border border-amber-300 bg-amber-50/60 p-4">
      <div className="mb-2.5 flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-amber-700" strokeWidth={2.25} />
        <h2 className="text-sm font-semibold text-amber-900">Anomalies</h2>
        <span className="ml-auto text-[11px] font-medium text-amber-800/80">
          {items.length} flagged
        </span>
      </div>
      <ul className="space-y-2.5">
        {items.map((a, i) => (
          <li
            key={i}
            className="border-t border-amber-200/70 pt-2.5 first:border-t-0 first:pt-0"
          >
            {a.kind === 'user_spike' ? (
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-amber-900/80">
                  User spend spike
                </div>
                <div className="mt-0.5 text-sm text-amber-900">
                  <span className="font-medium">{a.userName}</span> spent{' '}
                  <span className="font-mono tabular-nums">{formatUsd2(a.todayUsd)}</span>{' '}
                  in 24h —
                  <span className="text-amber-800">
                    {' '}
                    avg{' '}
                    <span className="font-mono tabular-nums">
                      {formatUsd2(a.avgDailyUsd)}
                    </span>
                    /day
                  </span>
                </div>
                <Link
                  href={`/admin/users?search=${encodeURIComponent(a.userName)}`}
                  className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-amber-900 hover:text-amber-950"
                >
                  Investigate <ArrowUpRight className="h-3 w-3" />
                </Link>
              </div>
            ) : (
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-amber-900/80">
                  API failure burst
                </div>
                <div className="mt-0.5 text-sm text-amber-900">
                  <span className="font-mono tabular-nums">{a.count}</span>{' '}
                  <span className="font-medium">
                    {PROVIDER_LABEL[a.provider] ?? a.provider}
                  </span>{' '}
                  errors,{' '}
                  <span className="text-amber-800">{a.windowLabel}</span>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Clinician variants — same data, warm cream + sage palette. Sub-components
// are duplicated rather than parameterised so the legacy slate-on-white
// path above stays byte-for-byte unchanged.
// ---------------------------------------------------------------------------

function ClinicianWindowSelector({
  value,
  onChange,
}: {
  value: WindowKey;
  onChange: (v: WindowKey) => void;
}) {
  return (
    <div style={{ position: 'relative' }}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as WindowKey)}
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
        {(['24h', '7d', '30d', 'month'] as WindowKey[]).map((k) => (
          <option key={k} value={k}>
            {WINDOW_LABELS[k]}
          </option>
        ))}
      </select>
      <ChevronDown
        style={{
          pointerEvents: 'none',
          position: 'absolute',
          right: 10,
          top: '50%',
          width: 12,
          height: 12,
          transform: 'translateY(-50%)',
          color: 'var(--ink-3)',
        }}
      />
    </div>
  );
}

function ClinicianTopStatBar({
  total,
  pctChange,
  events,
  activeUsers,
  avgPerUser,
}: {
  total: number;
  pctChange: number;
  events: number;
  activeUsers: number;
  avgPerUser: number;
}) {
  const isUp = pctChange >= 0;
  return (
    <div className="qm-cl-card" style={{ padding: 20 }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', gap: '8px 24px' }}>
        <div>
          <div className="qm-cl-section-label">Total spend</div>
          <div
            className="qm-cl-serif qm-cl-big-num"
            style={{ fontSize: 36, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}
          >
            {formatUsd2(total)}
          </div>
        </div>
        <div
          className={`qm-cl-pill ${isUp ? 'qm-cl-pill-amber' : 'qm-cl-pill-sage'}`}
          style={{ fontSize: 11, gap: 4 }}
        >
          <span aria-hidden>{isUp ? '↑' : '↓'}</span>
          <span className="qm-cl-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>
            {Math.abs(pctChange).toFixed(1)}%
          </span>
          <span style={{ color: 'inherit', opacity: 0.7 }}>vs last period</span>
        </div>
      </div>
      <div
        style={{
          marginTop: 12,
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: '4px 16px',
          fontSize: 12,
          color: 'var(--ink-3)',
        }}
      >
        <span>
          <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
            {events.toLocaleString()}
          </span>{' '}
          API calls
        </span>
        <span style={{ color: 'var(--ink-4)' }}>·</span>
        <span>
          <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
            {activeUsers}
          </span>{' '}
          active users
        </span>
        <span style={{ color: 'var(--ink-4)' }}>·</span>
        <span>
          <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
            {formatUsd2(avgPerUser)}
          </span>{' '}
          avg per user
        </span>
      </div>
    </div>
  );
}

function ClinicianTimelineChart({ buckets }: { buckets: TimelineBucket[] }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 1280,
    H = 200,
    padL = 44,
    padR = 16,
    padT = 16,
    padB = 28;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const dailyTotals = buckets.map((b) =>
    PROVIDER_ORDER.reduce((s, k) => s + (b.byProvider[k] ?? 0), 0)
  );
  const yMax = Math.max(1, ...dailyTotals) * 1.08;
  const yTicks = 4;
  const xFor = (i: number) =>
    padL + (buckets.length === 1 ? innerW / 2 : (i / (buckets.length - 1)) * innerW);
  const yFor = (v: number) => padT + innerH - (v / yMax) * innerH;
  const stacks: Record<string, number[]> = {};
  PROVIDER_ORDER.forEach((k) => (stacks[k] = []));
  buckets.forEach((b, i) => {
    let acc = 0;
    PROVIDER_ORDER.forEach((k) => {
      acc += b.byProvider[k] ?? 0;
      stacks[k]![i] = acc;
    });
  });
  function areaPath(top: number[], bottom: number[]): string {
    const n = top.length;
    if (n === 0) return '';
    let d = `M ${xFor(0)} ${yFor(top[0]!)}`;
    for (let i = 1; i < n; i++) d += ` L ${xFor(i)} ${yFor(top[i]!)}`;
    for (let i = n - 1; i >= 0; i--) d += ` L ${xFor(i)} ${yFor(bottom[i]!)}`;
    return d + ' Z';
  }
  const xLabelIdxs: number[] = (() => {
    const n = buckets.length,
      want = 5;
    if (n === 0) return [];
    const step = Math.max(1, Math.floor((n - 1) / (want - 1)));
    const set = new Set<number>();
    for (let i = 0; i < n; i += step) set.add(i);
    set.add(n - 1);
    return [...set].sort((a, b) => a - b);
  })();
  const yTickVals = Array.from({ length: yTicks + 1 }, (_, i) => (yMax * i) / yTicks);

  return (
    <div className="qm-cl-card" style={{ padding: 16, position: 'relative' }}>
      <div style={{ marginBottom: 8, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Activity style={{ width: 16, height: 16, color: 'var(--ink-2)' }} />
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Daily spend</h2>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '4px 12px', fontSize: 11, color: 'var(--ink-2)' }}>
          {PROVIDER_ORDER.map((k) => (
            <span key={k} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{
                  display: 'inline-block',
                  height: 8,
                  width: 10,
                  borderRadius: 2,
                  background: PROVIDER_COLOR[k]?.fill,
                }}
              />
              {PROVIDER_LABEL[k]}
            </span>
          ))}
        </div>
      </div>

      {buckets.length === 0 ? (
        <div style={{ display: 'flex', height: 200, alignItems: 'center', justifyContent: 'center', fontSize: 12, color: 'var(--ink-3)' }}>
          No usage data in this window.
        </div>
      ) : (
        <div style={{ position: 'relative' }}>
          <svg
            viewBox={`0 0 ${W} ${H}`}
            className="block w-full"
            style={{ height: 200 }}
            preserveAspectRatio="none"
            onMouseLeave={() => setHover(null)}
          >
            {yTickVals.map((v, i) => (
              <g key={i}>
                <line
                  x1={padL}
                  x2={W - padR}
                  y1={yFor(v)}
                  y2={yFor(v)}
                  stroke="rgba(43, 38, 32, 0.06)"
                  strokeWidth={1}
                />
                <text
                  x={padL - 8}
                  y={yFor(v) + 3}
                  fontSize={10}
                  fill="#8A8278"
                  textAnchor="end"
                  fontFamily="JetBrains Mono, monospace"
                >
                  ${v.toFixed(0)}
                </text>
              </g>
            ))}
            {[...PROVIDER_ORDER].reverse().map((k) => {
              const top = stacks[k]!;
              const idx = PROVIDER_ORDER.indexOf(k);
              const below =
                idx === 0 ? buckets.map(() => 0) : stacks[PROVIDER_ORDER[idx - 1]!]!;
              return (
                <path
                  key={k}
                  d={areaPath(top, below)}
                  fill={PROVIDER_COLOR[k]?.fill}
                  fillOpacity={0.78}
                  stroke={PROVIDER_COLOR[k]?.stroke}
                  strokeOpacity={0.6}
                  strokeWidth={0.75}
                />
              );
            })}
            {buckets.map((_, i) => {
              const slot = innerW / Math.max(1, buckets.length - 1);
              const x = xFor(i);
              return (
                <g key={i}>
                  <rect
                    x={x - slot / 2}
                    y={padT}
                    width={slot}
                    height={innerH}
                    fill="transparent"
                    onMouseEnter={() => setHover(i)}
                  />
                  {hover === i && (
                    <line
                      x1={x}
                      x2={x}
                      y1={padT}
                      y2={padT + innerH}
                      stroke="#2B2620"
                      strokeOpacity={0.16}
                      strokeWidth={1}
                    />
                  )}
                </g>
              );
            })}
            <line
              x1={padL}
              x2={W - padR}
              y1={padT + innerH + 0.5}
              y2={padT + innerH + 0.5}
              stroke="rgba(43, 38, 32, 0.1)"
              strokeWidth={1}
            />
            {xLabelIdxs.map((i) => (
              <text
                key={i}
                x={xFor(i)}
                y={H - 8}
                fontSize={10}
                fill="#8A8278"
                textAnchor="middle"
                fontFamily="DM Sans, sans-serif"
              >
                {formatDay(buckets[i]!.time.slice(0, 10))}
              </text>
            ))}
          </svg>
          {hover !== null &&
            (() => {
              const b = buckets[hover]!;
              const total = PROVIDER_ORDER.reduce((s, k) => s + (b.byProvider[k] ?? 0), 0);
              const cxPct = (xFor(hover) / W) * 100;
              return (
                <div
                  style={{
                    pointerEvents: 'none',
                    position: 'absolute',
                    zIndex: 10,
                    left: `${cxPct}%`,
                    top: 0,
                    transform: 'translate(-50%, -8px)',
                    borderRadius: 8,
                    border: '1px solid var(--line)',
                    background: 'var(--cream-card)',
                    padding: '8px 10px',
                    fontSize: 11,
                    boxShadow: 'var(--shadow-card)',
                  }}
                >
                  <div style={{ marginBottom: 4, fontWeight: 500, color: 'var(--ink-2)' }}>
                    {formatDay(b.time.slice(0, 10))}
                  </div>
                  <div
                    className="qm-cl-mono"
                    style={{ marginBottom: 6, fontSize: 13, fontWeight: 600, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}
                  >
                    {formatUsd2(total)}
                  </div>
                  <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 2 }}>
                    {[...PROVIDER_ORDER].reverse().map((k) => (
                      <li key={k} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span
                          style={{
                            display: 'inline-block',
                            width: 8,
                            height: 8,
                            borderRadius: 2,
                            background: PROVIDER_COLOR[k]?.fill,
                          }}
                        />
                        <span style={{ width: 64, color: 'var(--ink-3)' }}>{PROVIDER_LABEL[k]}</span>
                        <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
                          {formatUsd2(b.byProvider[k] ?? 0)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })()}
        </div>
      )}
    </div>
  );
}

function ClinicianProviderBreakdown({
  rows,
  total,
}: {
  rows: { key: string; label: string; costUsd: number; unitCount: number; unitLabel: string }[];
  total: number;
}) {
  return (
    <div className="qm-cl-card" style={{ padding: 16 }}>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Breakdown by provider</h2>
        <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>
          total{' '}
          <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
            {formatUsd2(total)}
          </span>
        </span>
      </div>
      {rows.length === 0 ? (
        <div
          style={{
            borderRadius: 8,
            border: '1px dashed var(--line-strong, rgba(43,38,32,0.14))',
            padding: '24px 12px',
            textAlign: 'center',
            fontSize: 12,
            color: 'var(--ink-3)',
          }}
        >
          No spend in this window.
        </div>
      ) : (
        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {rows.map((r) => {
            const pct = total > 0 ? (r.costUsd / total) * 100 : 0;
            return (
              <li key={r.key}>
                <div
                  style={{
                    marginBottom: 4,
                    display: 'flex',
                    alignItems: 'baseline',
                    justifyContent: 'space-between',
                    gap: 12,
                    fontSize: 13,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span
                      style={{
                        display: 'inline-block',
                        width: 10,
                        height: 10,
                        borderRadius: 2,
                        background: PROVIDER_COLOR[r.key]?.fill,
                      }}
                    />
                    <span style={{ fontWeight: 500, color: 'var(--ink)' }}>{r.label}</span>
                  </div>
                  <div style={{ color: 'var(--ink-3)' }}>
                    <span className="qm-cl-mono" style={{ color: 'var(--ink), fontVariantNumeric: tabular-nums' }}>
                      {formatUsd2(r.costUsd)}
                    </span>
                    <span style={{ margin: '0 6px', color: 'var(--ink-4)' }}>·</span>
                    <span className="qm-cl-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>{pct.toFixed(1)}%</span>
                  </div>
                </div>
                <div style={{ height: 8, overflow: 'hidden', borderRadius: 999, background: 'var(--cream-2)' }}>
                  <div
                    style={{
                      height: '100%',
                      borderRadius: 999,
                      width: `${pct}%`,
                      background: PROVIDER_COLOR[r.key]?.fill,
                    }}
                  />
                </div>
                {r.unitLabel && (
                  <div className="qm-cl-mono" style={{ marginTop: 4, fontSize: 11, color: 'var(--ink-3)', fontVariantNumeric: 'tabular-nums' }}>
                    {formatCount2(r.unitCount)} {r.unitLabel}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function ClinicianTopUsers({ rows }: { rows: TopUserRow[] }) {
  return (
    <div className="qm-cl-card" style={{ padding: 16 }}>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <UsersIcon style={{ width: 16, height: 16, color: 'var(--ink-2)' }} />
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Top users by cost</h2>
        </div>
        <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>top 10</span>
      </div>
      {rows.length === 0 ? (
        <div
          style={{
            borderRadius: 8,
            border: '1px dashed var(--line-strong, rgba(43,38,32,0.14))',
            padding: '24px 12px',
            textAlign: 'center',
            fontSize: 12,
            color: 'var(--ink-3)',
          }}
        >
          No attributable usage.
        </div>
      ) : (
        <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 4 }}>
          {rows.map((r, i) => {
            const id = r.userId ?? `unattributed-${i}`;
            const tones = ['sage', 'teal', 'amber', 'coral', 'sky'] as const;
            const tone = tones[(id.charCodeAt(0) || 0) % tones.length]!;
            return (
              <li key={id}>
                <Link
                  href={r.userId ? `/admin/users?search=${encodeURIComponent(r.userEmail)}` : '/admin/users'}
                  style={{
                    display: 'flex',
                    width: '100%',
                    alignItems: 'center',
                    gap: 12,
                    borderRadius: 8,
                    padding: '6px 8px',
                    textAlign: 'left',
                    color: 'inherit',
                    textDecoration: 'none',
                    transition: 'background 200ms var(--ease-clinician)',
                  }}
                  className="hover:bg-clinician-cream-2"
                >
                  <span
                    className="qm-cl-mono"
                    style={{ width: 16, flexShrink: 0, fontSize: 12, color: 'var(--ink-4)', fontVariantNumeric: 'tabular-nums' }}
                  >
                    {i + 1}.
                  </span>
                  <span
                    aria-hidden
                    className={`qm-cl-avatar qm-cl-avatar-${tone}`}
                    style={{ width: 26, height: 26, fontSize: 10, borderRadius: 8 }}
                  >
                    {userInitials(r.userEmail)}
                  </span>
                  <span style={{ minWidth: 0, flex: 1 }}>
                    <span
                      style={{
                        display: 'block',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontSize: 13,
                        fontWeight: 500,
                        color: 'var(--ink)',
                      }}
                    >
                      {r.userEmail}
                    </span>
                    <span
                      className="qm-cl-mono"
                      style={{
                        display: 'block',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontSize: 11,
                        color: 'var(--ink-3)',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {r.events.toLocaleString()} events
                    </span>
                  </span>
                  <span
                    className="qm-cl-mono"
                    style={{ fontSize: 13, color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}
                  >
                    {formatUsd2(r.totalCostUsd)}
                  </span>
                </Link>
              </li>
            );
          })}
        </ol>
      )}
      <Link
        href="/admin/users"
        style={{
          marginTop: 8,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 4,
          padding: '0 8px',
          fontSize: 12,
          fontWeight: 500,
          color: 'var(--ink-2)',
          textDecoration: 'none',
        }}
      >
        View all users <ArrowUpRight style={{ width: 12, height: 12 }} />
      </Link>
    </div>
  );
}

function ClinicianAnomaliesPanel({ items }: { items: Anomaly[] }) {
  if (items.length === 0) return null;
  return (
    <div
      style={{
        borderRadius: 12,
        border: '1px solid var(--amber-tint-strong, rgba(212,165,116,0.32))',
        background: 'var(--amber-tint)',
        padding: 16,
      }}
    >
      <div style={{ marginBottom: 10, display: 'flex', alignItems: 'center', gap: 8 }}>
        <AlertTriangle style={{ width: 16, height: 16, color: 'var(--amber-deep)' }} strokeWidth={2.25} />
        <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--amber-deep)' }}>Anomalies</h2>
        <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 500, color: 'var(--amber-deep)', opacity: 0.8 }}>
          {items.length} flagged
        </span>
      </div>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        {items.map((a, i) => (
          <li
            key={i}
            style={{
              borderTop: i === 0 ? 'none' : '1px solid rgba(122,79,31,0.18)',
              paddingTop: i === 0 ? 0 : 10,
            }}
          >
            {a.kind === 'user_spike' ? (
              <div>
                <div className="qm-cl-section-label" style={{ color: 'rgba(122,79,31,0.85)' }}>User spend spike</div>
                <div style={{ marginTop: 2, fontSize: 13, color: 'var(--amber-deep)' }}>
                  <span style={{ fontWeight: 500 }}>{a.userName}</span> spent{' '}
                  <span className="qm-cl-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>
                    {formatUsd2(a.todayUsd)}
                  </span>{' '}
                  in 24h —
                  <span style={{ opacity: 0.8 }}>
                    {' '}
                    avg{' '}
                    <span className="qm-cl-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>
                      {formatUsd2(a.avgDailyUsd)}
                    </span>
                    /day
                  </span>
                </div>
                <Link
                  href={`/admin/users?search=${encodeURIComponent(a.userName)}`}
                  style={{
                    marginTop: 4,
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 4,
                    fontSize: 12,
                    fontWeight: 500,
                    color: 'var(--amber-deep)',
                    textDecoration: 'none',
                  }}
                >
                  Investigate <ArrowUpRight style={{ width: 12, height: 12 }} />
                </Link>
              </div>
            ) : (
              <div>
                <div className="qm-cl-section-label" style={{ color: 'rgba(122,79,31,0.85)' }}>API failure burst</div>
                <div style={{ marginTop: 2, fontSize: 13, color: 'var(--amber-deep)' }}>
                  <span className="qm-cl-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>{a.count}</span>{' '}
                  <span style={{ fontWeight: 500 }}>
                    {PROVIDER_LABEL[a.provider] ?? a.provider}
                  </span>{' '}
                  errors,{' '}
                  <span style={{ opacity: 0.8 }}>{a.windowLabel}</span>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
