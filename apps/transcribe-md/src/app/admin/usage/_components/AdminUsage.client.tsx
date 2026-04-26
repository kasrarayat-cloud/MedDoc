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

interface Props {
  initial: AdminUsageInitialData;
}

export default function AdminUsage({ initial }: Props) {
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
