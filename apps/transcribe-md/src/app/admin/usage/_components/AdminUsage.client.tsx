'use client';

// ============================================================================
// /admin/usage — orchestrator + presentational sub-components
// ----------------------------------------------------------------------------
// Window selector, top stat strip, hand-rolled stacked-area timeline,
// per-provider breakdown bars, top-users list, and anomalies panel —
// all in this file.
//
// Initial data comes from the server `page.tsx`; window changes refetch
// via the existing /api/admin/usage/{summary,timeline,by-user} endpoints.
// Anomalies don't have a JSON endpoint yet — the server seed is the
// only source until that lands. The Refresh button bumps a tick that
// triggers `router.refresh()` so the server data re-runs.
//
// Phase 5 (Linear V1 Faithful) — chart cards rendered against the dark
// canvas. Provider stack uses sage / sky / amber / coral / teal so the
// palette stays semantic on the dark surface. Mono cells throughout.
// The earlier dual-theme branching has been retired; the `theme` prop
// survives as an ignored compat shim.
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
  PROVIDER_LABEL,
  PROVIDER_ORDER,
  WINDOW_LABELS,
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

// Linear V1 provider palette — semantic colours that sit on the dark
// canvas. We deliberately re-derive this here rather than mutating the
// shared admin-format export, which is still imported by other code paths.
const LIN_PROVIDER_COLOR: Record<string, { fill: string; stroke: string }> = {
  deepgram: { fill: '#5BA3B4', stroke: '#3F8290' }, // teal
  anthropic: { fill: '#7AA68C', stroke: '#5d8a73' }, // sage
  whisper: { fill: '#D4A574', stroke: '#a47e51' }, // amber
  openai: { fill: '#4caf7d', stroke: '#2f8055' }, // success-green
  resend: { fill: '#74A8C9', stroke: '#4f7d99' }, // sky
};

// Smaller-context Linear palette for top-user avatars.
function lineaAvatarTone(id: string): { bg: string; fg: string } {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  const ps: Array<{ bg: string; fg: string }> = [
    { bg: 'linear-gradient(135deg,#9bc2ab,#6f9b85)', fg: '#0b1611' },
    { bg: 'linear-gradient(135deg,#a5c8dd,#6e95ad)', fg: '#0a1820' },
    { bg: 'linear-gradient(135deg,#e2bd92,#b88752)', fg: '#1c1409' },
    { bg: 'linear-gradient(135deg,#d99a90,#b06b60)', fg: '#fff' },
    { bg: 'linear-gradient(135deg,#b9b2d9,#7e76a8)', fg: '#fff' },
  ];
  return ps[Math.abs(h) % ps.length]!;
}

interface Props {
  initial: AdminUsageInitialData;
  /** Phase 4 dual-theme prop. Phase 5 ignores it; kept for caller compat. */
  theme?: string;
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

  const breakdownRows = PROVIDER_ORDER.map((k) => ({
    key: k,
    label: PROVIDER_LABEL[k],
    costUsd: summary.byProvider[k] ?? 0,
    unitCount: 0,
    unitLabel: '',
  })).filter((r) => r.costUsd > 0);

  return (
    <div className="min-h-screen bg-linear-bg text-linear-text">
      <header className="sticky top-0 z-20 border-b border-linear-border bg-linear-surface-1/95 backdrop-blur supports-[backdrop-filter]:bg-linear-surface-1/85">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3">
          <div>
            <div className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-linear-text-3 mb-1">
              Admin · Usage
            </div>
            <h1 className="text-[20px] font-semibold tracking-tight text-linear-text leading-tight">
              API usage &amp; costs
            </h1>
            <div className="mt-1 text-[11px] text-linear-text-3">
              <span className="font-medium text-linear-text-2">QuillMD</span>
              <span className="mx-1.5 text-linear-text-3">·</span>
              <span>
                window{' '}
                <span className="font-mono tabular-nums text-linear-text-2">
                  {WINDOW_LABELS[windowKey] ?? windowKey}
                </span>
              </span>
              {busy && (
                <>
                  <span className="mx-1.5 text-linear-text-3">·</span>
                  <span className="text-linear-text-3">refreshing…</span>
                </>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <WindowSelector value={windowKey} onChange={setWindowKey} />
            <button
              type="button"
              onClick={() => startTransition(() => router.refresh())}
              className="qm-lin-btn"
            >
              <RefreshCw className="mr-1 h-3 w-3" />
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
        <footer className="pt-4 text-[11px] text-linear-text-3">
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
        className="h-8 cursor-pointer appearance-none rounded-md border border-linear-border bg-linear-surface-2 py-0 pl-3 pr-8 text-xs font-medium text-linear-text-2 hover:border-linear-border-strong hover:text-linear-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-linear-sage/40"
      >
        {(['24h', '7d', '30d', 'month'] as WindowKey[]).map((k) => (
          <option key={k} value={k} className="bg-linear-surface-2 text-linear-text">
            {WINDOW_LABELS[k]}
          </option>
        ))}
      </select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 h-3 w-3 -translate-y-1/2 text-linear-text-3" />
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
    <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-5">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-2">
        <div>
          <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">
            Total spend
          </div>
          <div className="font-mono text-3xl font-medium tabular-nums text-linear-text">
            {formatUsd2(total)}
          </div>
        </div>
        <div
          className="inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium"
          style={
            isUp
              ? {
                  background: 'rgba(212,164,55,0.15)',
                  color: 'var(--color-linear-warning)',
                }
              : {
                  background: 'var(--color-linear-sage-tint)',
                  color: 'var(--color-linear-sage-bright)',
                }
          }
        >
          <span aria-hidden>{isUp ? '↑' : '↓'}</span>
          <span className="font-mono tabular-nums">{Math.abs(pctChange).toFixed(1)}%</span>
          <span className="text-linear-text-3">vs last period</span>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-linear-text-3">
        <span>
          <span className="font-mono tabular-nums text-linear-text-2">
            {events.toLocaleString()}
          </span>{' '}
          API calls
        </span>
        <span className="text-linear-text-3">·</span>
        <span>
          <span className="font-mono tabular-nums text-linear-text-2">{activeUsers}</span> active users
        </span>
        <span className="text-linear-text-3">·</span>
        <span>
          <span className="font-mono tabular-nums text-linear-text-2">
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
    <div className="relative rounded-lg border border-linear-border bg-linear-surface-1 p-4">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-linear-text-2" />
          <h2 className="text-sm font-semibold text-linear-text">Daily spend</h2>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-linear-text-2">
          {PROVIDER_ORDER.map((k) => (
            <span key={k} className="inline-flex items-center gap-1.5">
              <span
                className="inline-block h-2 w-2.5 rounded-sm"
                style={{ background: LIN_PROVIDER_COLOR[k]?.fill }}
              />
              {PROVIDER_LABEL[k]}
            </span>
          ))}
        </div>
      </div>

      {buckets.length === 0 ? (
        <div className="flex h-[200px] items-center justify-center text-xs text-linear-text-3">
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
                  stroke="rgba(255,255,255,0.04)"
                  strokeWidth={1}
                />
                <text
                  x={padL - 8}
                  y={yFor(v) + 3}
                  fontSize={10}
                  fill="#6c737f"
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
                idx === 0
                  ? buckets.map(() => 0)
                  : stacks[PROVIDER_ORDER[idx - 1]!]!;
              return (
                <path
                  key={k}
                  d={areaPath(top, below)}
                  fill={LIN_PROVIDER_COLOR[k]?.fill}
                  fillOpacity={0.78}
                  stroke={LIN_PROVIDER_COLOR[k]?.stroke}
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
                      stroke="#f7f8f8"
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
              stroke="#21232a"
              strokeWidth={1}
            />
            {xLabelIdxs.map((i) => (
              <text
                key={i}
                x={xFor(i)}
                y={H - 8}
                fontSize={10}
                fill="#6c737f"
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
                  className="pointer-events-none absolute z-10 -translate-x-1/2 -translate-y-2 rounded-md border border-linear-border bg-linear-surface-2 px-2.5 py-2 text-[11px] shadow-[0_8px_20px_rgba(0,0,0,0.4)]"
                  style={{ left: `${cxPct}%`, top: 0 }}
                >
                  <div className="mb-1 font-medium text-linear-text">
                    {formatDay(b.time.slice(0, 10))}
                  </div>
                  <div className="mb-1.5 font-mono text-sm font-semibold tabular-nums text-linear-text">
                    {formatUsd2(total)}
                  </div>
                  <ul className="space-y-0.5">
                    {[...PROVIDER_ORDER].reverse().map((k) => (
                      <li key={k} className="flex items-center gap-2">
                        <span
                          className="inline-block h-2 w-2 rounded-sm"
                          style={{ background: LIN_PROVIDER_COLOR[k]?.fill }}
                        />
                        <span className="w-16 text-linear-text-2">{PROVIDER_LABEL[k]}</span>
                        <span className="font-mono tabular-nums text-linear-text">
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
    <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-linear-text">Breakdown by provider</h2>
        <span className="text-[11px] text-linear-text-3">
          total{' '}
          <span className="font-mono tabular-nums text-linear-text-2">{formatUsd2(total)}</span>
        </span>
      </div>
      {rows.length === 0 ? (
        <div className="rounded-md border border-dashed border-linear-border px-3 py-6 text-center text-xs text-linear-text-3">
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
                      className="inline-block h-2.5 w-2.5 rounded-sm"
                      style={{ background: LIN_PROVIDER_COLOR[r.key]?.fill }}
                    />
                    <span className="font-medium text-linear-text-2">{r.label}</span>
                  </div>
                  <div className="text-linear-text-3">
                    <span className="font-mono tabular-nums text-linear-text">
                      {formatUsd2(r.costUsd)}
                    </span>
                    <span className="mx-1.5 text-linear-text-3">·</span>
                    <span className="font-mono tabular-nums">{pct.toFixed(1)}%</span>
                  </div>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-linear-surface-2">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${pct}%`, background: LIN_PROVIDER_COLOR[r.key]?.fill }}
                  />
                </div>
                {r.unitLabel && (
                  <div className="mt-1 font-mono text-[11px] tabular-nums text-linear-text-3">
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
    <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <UsersIcon className="h-4 w-4 text-linear-text-2" />
          <h2 className="text-sm font-semibold text-linear-text">Top users by cost</h2>
        </div>
        <span className="text-[11px] text-linear-text-3">top 10</span>
      </div>
      {rows.length === 0 ? (
        <div className="rounded-md border border-dashed border-linear-border px-3 py-6 text-center text-xs text-linear-text-3">
          No attributable usage.
        </div>
      ) : (
        <ol className="space-y-1">
          {rows.map((r, i) => {
            const id = r.userId ?? `unattributed-${i}`;
            const tone = lineaAvatarTone(id);
            return (
              <li key={id}>
                <Link
                  href={r.userId ? `/admin/users?search=${encodeURIComponent(r.userEmail)}` : '/admin/users'}
                  className="group flex w-full items-center gap-3 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-linear-row-hover"
                >
                  <span className="w-4 shrink-0 font-mono text-xs tabular-nums text-linear-text-3">
                    {i + 1}.
                  </span>
                  <span
                    className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md font-semibold tracking-tight text-[10px]"
                    style={{ background: tone.bg, color: tone.fg }}
                  >
                    {userInitials(r.userEmail)}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium text-linear-text-2">
                      {r.userEmail}
                    </span>
                    <span className="block truncate font-mono text-[11px] tabular-nums text-linear-text-3">
                      {r.events.toLocaleString()} events
                    </span>
                  </span>
                  <span className="font-mono text-sm tabular-nums text-linear-text">
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
        className="mt-2 inline-flex items-center gap-1 px-2 text-xs font-medium text-linear-text-2 hover:text-linear-text"
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
    <div
      className="rounded-lg border p-4"
      style={{
        borderColor: 'rgba(212,164,55,0.30)',
        background: 'rgba(212,164,55,0.08)',
      }}
    >
      <div className="mb-2.5 flex items-center gap-2">
        <AlertTriangle className="h-4 w-4 text-linear-warning" strokeWidth={2.25} />
        <h2 className="text-sm font-semibold text-linear-warning">Anomalies</h2>
        <span className="ml-auto text-[11px] font-medium text-linear-text-3">
          {items.length} flagged
        </span>
      </div>
      <ul className="space-y-2.5">
        {items.map((a, i) => (
          <li
            key={i}
            className={cls(
              'pt-2.5 first:pt-0',
              i > 0 && 'border-t'
            )}
            style={i > 0 ? { borderColor: 'rgba(212,164,55,0.20)' } : undefined}
          >
            {a.kind === 'user_spike' ? (
              <div>
                <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-warning">
                  User spend spike
                </div>
                <div className="mt-0.5 text-sm text-linear-text">
                  <span className="font-medium">{a.userName}</span> spent{' '}
                  <span className="font-mono tabular-nums">{formatUsd2(a.todayUsd)}</span>{' '}
                  in 24h —
                  <span className="text-linear-text-2">
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
                  className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-linear-warning hover:underline"
                >
                  Investigate <ArrowUpRight className="h-3 w-3" />
                </Link>
              </div>
            ) : (
              <div>
                <div className="font-mono text-[10px] font-medium uppercase tracking-[0.08em] text-linear-warning">
                  API failure burst
                </div>
                <div className="mt-0.5 text-sm text-linear-text">
                  <span className="font-mono tabular-nums">{a.count}</span>{' '}
                  <span className="font-medium">
                    {PROVIDER_LABEL[a.provider] ?? a.provider}
                  </span>{' '}
                  errors,{' '}
                  <span className="text-linear-text-2">{a.windowLabel}</span>
                </div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
