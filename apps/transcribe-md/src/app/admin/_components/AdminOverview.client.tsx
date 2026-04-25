'use client';

// ============================================================================
// Admin overview dashboard — client component
// ----------------------------------------------------------------------------
// Adapted from the Claude Design output. Receives initial SSR data via
// props; the only client-side fetch is the SSE subscription that streams
// new audit-log rows into the activity feed.
//
// Visual primitives (Card / Badge / Button) are inlined as plain
// Tailwind divs/buttons. The codebase's existing shared `Card` and
// `Button` components have heavy framer-motion / gradient styling that
// fights the design's flat, minimalist look — duplicating the small
// surface here keeps fidelity high without forking the shared
// components.
// ============================================================================

import { useEffect, useMemo, useRef, useState } from 'react';
import {
  Database,
  Server,
  HardDrive,
  Cloud,
  AlertTriangle,
  ChevronDown,
  CheckCircle2,
  ShieldCheck,
  Activity,
  ArrowUpRight,
  Search,
} from 'lucide-react';

import type {
  AdminOverviewInitialData,
  ActivityCategory,
  ActivityRow,
  FilterKey,
  HealthStatus,
  HipaaState,
  PipelineMetrics,
  ServiceHealth,
  Threat,
  TimelineBucket,
} from '../_types';
import AdminNav from './AdminNav.client';

// ---------------------------------------------------------------------------
// Top-level component
// ---------------------------------------------------------------------------

interface Props {
  /** Server-rendered seed data; the client mutates `activity` from the SSE stream. */
  initial: AdminOverviewInitialData;
  /** Email of the current SUPER_ADMIN, shown in the header avatar. */
  userEmail: string;
}

export default function AdminOverview({ initial, userEmail }: Props) {
  const [filter, setFilter] = useState<FilterKey>('all');
  const [rows, setRows] = useState<ActivityRow[]>(initial.activity);
  const [connected, setConnected] = useState(false);

  // Cosmetic ticker — shows "last updated Ns ago" on the header. Kept
  // bounded to 0..59 so the header text stays narrow.
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => (t + 1) % 60), 1000);
    return () => clearInterval(id);
  }, []);

  // Reset the tick whenever a new SSE event arrives — "last updated"
  // really means "since last event" not "since page mount".
  const onNewEvent = () => setTick(0);

  // SSE — single subscription for the lifetime of the page. EventSource
  // auto-reconnects on transient errors; we surface that via the
  // `connected` flag in the activity-feed header.
  useEffect(() => {
    const es = new EventSource('/api/admin/stream/activity');
    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.addEventListener('open', () => setConnected(true));
    es.onmessage = (event) => {
      try {
        const data: unknown = JSON.parse(event.data);
        if (!data || typeof data !== 'object') return;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const e = data as any;
        if (typeof e.action !== 'string') return; // skip non-audit messages

        const row: ActivityRow = {
          id: typeof e.id === 'string' ? e.id : crypto.randomUUID(),
          timestamp: formatClock(e.timestamp ? new Date(e.timestamp) : new Date()),
          action: e.action,
          category: categorizeAction(e.action),
          actorEmail: e.userEmailSnapshot ?? 'system',
          target:
            e.targetType && e.targetId
              ? `${e.targetType}:${String(e.targetId).slice(0, 8)}`
              : undefined,
          ip: e.ipAddress ?? '—',
          success: typeof e.success === 'boolean' ? e.success : true,
          isNew: true,
        };

        setRows((prev) => [row, ...prev].slice(0, 50));
        onNewEvent();

        // Clear the fade-in flag after the animation runs.
        window.setTimeout(() => {
          setRows((prev) =>
            prev.map((r) => (r.id === row.id ? { ...r, isNew: false } : r))
          );
        }, 250);
      } catch {
        // Malformed payload — ignore silently. We don't want to break the
        // whole feed because one event was unparseable.
      }
    };
    return () => es.close();
  }, []);

  const lastUpdated = `${tick}s ago`;

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Tailwind doesn't ship a one-off keyframe utility; this scoped block
          keeps the row-fade effect without dragging in a Tailwind plugin. */}
      <style>{`@keyframes qm-fade-in { from { opacity: 0; transform: translateY(-2px); } to { opacity: 1; transform: none; } }`}</style>

      <DashboardHeader userEmail={userEmail} lastUpdated={lastUpdated} />
      <AdminNav />

      <main className="mx-auto max-w-[1440px] space-y-4 px-6 py-5">
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatusCard icon={Database} label="Database" health={initial.systemHealth.database} />
          <StatusCard icon={Server} label="Redis" health={initial.systemHealth.redis} />
          <StatusCard icon={HardDrive} label="Object storage" health={initial.systemHealth.minio} />
          <StatusCard icon={Cloud} label="External APIs" health={initial.systemHealth.externalAPIs} />
        </section>

        <ThreatsBar threats={initial.threats} />

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <ActivityFeed rows={rows} filter={filter} onFilter={setFilter} connected={connected} />
          </div>
          <div className="space-y-4 lg:col-span-2">
            <PipelineMetricsCard data={initial.pipeline} />
            <TimelineChartCard data={initial.timeline} />
            <HipaaComplianceCard data={initial.hipaa} />
          </div>
        </section>

        <footer className="pt-4 text-[11px] text-slate-400">
          Audit logs retained 7 years per HIPAA §164.316(b)(2)(i). All admin actions on this page are themselves logged.
        </footer>
      </main>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header
// ---------------------------------------------------------------------------

function DashboardHeader({
  userEmail,
  lastUpdated,
}: {
  userEmail: string;
  lastUpdated: string;
}) {
  const initial = userEmail.slice(0, 1).toUpperCase();
  return (
    <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85">
      <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">Admin Dashboard</h1>
          <div className="mt-0.5 text-[11px] text-slate-500">
            <span className="font-medium text-slate-600">QuillMD</span>
            <span className="mx-1.5 text-slate-300">·</span>
            <span className="inline-flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Production
            </span>
            <span className="mx-1.5 text-slate-300">·</span>
            <span>
              last updated <span className="font-mono tabular-nums">{lastUpdated}</span>
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="ml-1 flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs hover:bg-slate-50"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-[10px] font-semibold text-white">
              {initial}
            </span>
            <span className="hidden font-medium text-slate-800 sm:inline">{userEmail}</span>
            <ChevronDown className="h-3 w-3 text-slate-500" />
          </button>
        </div>
      </div>
    </header>
  );
}

// ---------------------------------------------------------------------------
// Status strip
// ---------------------------------------------------------------------------

function StatusDot({ status }: { status: HealthStatus }) {
  const cls =
    status === 'healthy' ? 'bg-emerald-500' : status === 'degraded' ? 'bg-amber-500' : 'bg-rose-500';
  return (
    <span className="relative inline-flex h-2 w-2">
      {status === 'healthy' && (
        <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-60 animate-ping" />
      )}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${cls}`} />
    </span>
  );
}

function StatusBadge({ status }: { status: HealthStatus }) {
  const map: Record<HealthStatus, string> = {
    healthy: 'bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20',
    degraded: 'bg-amber-50 text-amber-800 ring-1 ring-amber-600/30',
    down: 'bg-rose-50 text-rose-700 ring-1 ring-rose-600/30',
  };
  const label: Record<HealthStatus, string> = { healthy: 'Healthy', degraded: 'Degraded', down: 'Down' };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-medium tracking-tight ${map[status]}`}
    >
      <StatusDot status={status} />
      {label[status]}
    </span>
  );
}

function StatusCard({
  icon: Icon,
  label,
  health,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  health: ServiceHealth;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-slate-300">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-slate-50 ring-1 ring-slate-200">
            <Icon className="h-4 w-4 text-slate-600" />
          </div>
          <div className="text-sm font-medium text-slate-900">{label}</div>
        </div>
        <StatusBadge status={health.status} />
      </div>
      <div className="mt-3 font-mono text-xs text-slate-500">{health.metric}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Threats bar
// ---------------------------------------------------------------------------

function ThreatsBar({ threats }: { threats: Threat[] }) {
  if (threats.length === 0) return null;
  const headline = threats[0]!;
  return (
    <div className="flex items-center gap-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3">
      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700" strokeWidth={2.25} />
      <div className="min-w-0 flex-1">
        <div className="text-sm">
          <span className="font-semibold text-amber-900">
            {threats.length} active threat{threats.length === 1 ? '' : 's'}
          </span>
          <span className="mx-2 text-amber-700/40">·</span>
          <span className="text-amber-900">{headline.summary}</span>
        </div>
        <div className="mt-0.5 text-xs text-amber-800/80">{headline.detail}</div>
      </div>
      <button
        type="button"
        className="inline-flex h-7 items-center rounded-md border border-amber-300 bg-white px-2.5 text-xs font-medium text-amber-900 hover:bg-amber-100"
      >
        View all <ArrowUpRight className="ml-1 h-3 w-3" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Activity feed
// ---------------------------------------------------------------------------

const FILTER_TABS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'auth', label: 'Auth' },
  { key: 'visit', label: 'Visits' },
  { key: 'export', label: 'Exports' },
  { key: 'admin', label: 'Admin' },
];

function FilterPill({
  active,
  onClick,
  children,
  count,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        'inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-xs font-medium transition-colors ' +
        (active ? 'bg-slate-900 text-white' : 'bg-slate-100 text-slate-700 hover:bg-slate-200')
      }
    >
      {children}
      {typeof count === 'number' && (
        <span
          className={
            'rounded-sm px-1 text-[10px] font-mono ' +
            (active ? 'bg-white/15 text-white/90' : 'text-slate-500')
          }
        >
          {count}
        </span>
      )}
    </button>
  );
}

function ActionChip({ action, success }: { action: string; success: boolean }) {
  const cls = success
    ? 'bg-slate-100 text-slate-700'
    : 'bg-rose-50 text-rose-700 ring-1 ring-rose-600/20';
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-medium tracking-tight ${cls}`}
    >
      {action}
    </span>
  );
}

function ActivityFeed({
  rows,
  filter,
  onFilter,
  connected,
}: {
  rows: ActivityRow[];
  filter: FilterKey;
  onFilter: (f: FilterKey) => void;
  connected: boolean;
}) {
  const counts = useMemo(() => {
    const c: Record<FilterKey, number> = { all: rows.length, auth: 0, visit: 0, export: 0, admin: 0 };
    for (const r of rows) c[r.category]++;
    return c;
  }, [rows]);

  const filtered = filter === 'all' ? rows : rows.filter((r) => r.category === filter);

  return (
    <div className="flex flex-col overflow-hidden rounded-lg border border-slate-200 bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-900">Live activity</h2>
          <span className="flex items-center gap-1.5 text-[11px] text-slate-500">
            <span
              className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-emerald-500' : 'bg-slate-300'} ${connected ? 'animate-pulse' : ''}`}
            />
            {connected ? 'Streaming' : 'Reconnecting…'}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Search className="h-3.5 w-3.5" />
          <span className="font-mono">{filtered.length} events</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 border-b border-slate-200 px-4 py-2.5">
        {FILTER_TABS.map((t) => (
          <FilterPill key={t.key} active={filter === t.key} onClick={() => onFilter(t.key)} count={counts[t.key]}>
            {t.label}
          </FilterPill>
        ))}
      </div>

      <div className="max-h-[560px] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
            <div className="text-sm text-slate-500">No events match this filter.</div>
            <button
              type="button"
              className="inline-flex h-7 items-center rounded-md border border-slate-200 bg-white px-2.5 text-xs font-medium text-slate-700 hover:bg-slate-50"
              onClick={() => onFilter('all')}
            >
              Show all
            </button>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {filtered.map((row) => (
              <li
                key={row.id}
                className="group relative flex items-center gap-3 px-4 py-2.5 text-sm transition-colors duration-200 hover:bg-slate-50"
                style={row.isNew ? { animation: 'qm-fade-in 200ms ease-out both' } : undefined}
              >
                <span
                  className={`absolute left-0 top-0 h-full w-[3px] ${row.success ? 'bg-emerald-400/70' : 'bg-rose-500'}`}
                  aria-hidden
                />
                <span className="font-mono text-[11px] tabular-nums text-slate-500 w-[68px] shrink-0">
                  {row.timestamp}
                </span>
                <ActionChip action={row.action} success={row.success} />
                <span className="truncate text-slate-800">{row.actorEmail}</span>
                {row.target && (
                  <>
                    <span className="text-slate-300">·</span>
                    <span className="truncate font-mono text-xs text-slate-500">{row.target}</span>
                  </>
                )}
                <span className="ml-auto hidden font-mono text-[11px] text-slate-400 group-hover:inline lg:inline">
                  {row.ip}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pipeline metrics
// ---------------------------------------------------------------------------

function PipelineMetricsCard({ data }: { data: PipelineMetrics }) {
  const total = Math.max(1, data.total);
  const okPct = (data.succeeded / total) * 100;
  const failPct = (data.failed / total) * 100;
  const pendPct = (data.pending / total) * 100;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-900">Transcription pipeline</h2>
        <span className="text-[11px] text-slate-500">last 24h</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <div className="text-2xl font-semibold tabular-nums text-slate-900">{data.successRate.toFixed(1)}%</div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">Success rate</div>
        </div>
        <div>
          <div className="text-2xl font-semibold tabular-nums text-slate-900">{data.p50}</div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">p50 latency</div>
        </div>
        <div>
          <div className="text-2xl font-semibold tabular-nums text-slate-900">{data.p95}</div>
          <div className="text-[11px] uppercase tracking-wide text-slate-500">p95 latency</div>
        </div>
      </div>

      <div className="mt-4">
        <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div className="bg-emerald-500" style={{ width: `${okPct}%` }} />
          <div className="bg-rose-500" style={{ width: `${failPct}%` }} />
          <div className="bg-amber-400" style={{ width: `${pendPct}%` }} />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span className="font-mono tabular-nums text-slate-700">{data.succeeded.toLocaleString()}</span> succeeded
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-rose-500" />
            <span className="font-mono tabular-nums text-slate-700">{data.failed}</span> failed
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
            <span className="font-mono tabular-nums text-slate-700">{data.pending}</span> pending
          </span>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Timeline chart (24h)
// ---------------------------------------------------------------------------

function TimelineChartCard({ data }: { data: TimelineBucket[] }) {
  const totalEvents = data.reduce((s, b) => s + b.total, 0);
  const totalFailed = data.reduce((s, b) => s + b.failed, 0);
  const [hover, setHover] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const W = 460;
  const H = 120;
  const padL = 8;
  const padR = 8;
  const padT = 8;
  const padB = 18;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const max = Math.max(1, ...data.map((d) => d.total));
  const slot = innerW / data.length;
  const barW = Math.max(2, slot - 2);
  const xTicks = [0, 6, 12, 18];

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <div className="flex items-baseline gap-2">
          <h2 className="text-sm font-semibold text-slate-900">Audit events</h2>
          <span className="text-[11px] text-slate-500">last 24h</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-slate-500">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-3 rounded-sm bg-slate-300" /> total{' '}
            <span className="font-mono tabular-nums text-slate-700">{totalEvents.toLocaleString()}</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-3 rounded-sm bg-rose-500" /> failed{' '}
            <span className="font-mono tabular-nums text-slate-700">{totalFailed}</span>
          </span>
        </div>
      </div>
      <div className="relative" ref={containerRef}>
        <svg viewBox={`0 0 ${W} ${H}`} className="block w-full h-[120px]" preserveAspectRatio="none">
          {data.map((d, i) => {
            const x = padL + i * slot + (slot - barW) / 2;
            const totalH = (d.total / max) * innerH;
            const failedH = (d.failed / max) * innerH;
            const yTotal = padT + innerH - totalH;
            const yFailed = padT + innerH - failedH;
            const isHover = hover === i;
            return (
              <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)}>
                <rect x={padL + i * slot} y={padT} width={slot} height={innerH} fill="transparent" />
                {isHover && (
                  <rect x={padL + i * slot} y={padT} width={slot} height={innerH} fill="rgba(15,23,42,0.04)" />
                )}
                <rect x={x} y={yTotal} width={barW} height={totalH} fill={isHover ? '#94a3b8' : '#cbd5e1'} rx="1" />
                {d.failed > 0 && <rect x={x} y={yFailed} width={barW} height={failedH} fill="#f43f5e" rx="1" />}
              </g>
            );
          })}
          <line x1={padL} x2={W - padR} y1={padT + innerH + 0.5} y2={padT + innerH + 0.5} stroke="#e2e8f0" strokeWidth="1" />
          {xTicks.map((h) => {
            const cx = padL + (h + 0.5) * slot;
            const label = h === 0 ? '12a' : h === 12 ? '12p' : h < 12 ? `${h}a` : `${h - 12}p`;
            return (
              <text key={h} x={cx} y={H - 4} fontSize="10" fill="#64748b" textAnchor="middle" fontFamily="Inter, sans-serif">
                {label}
              </text>
            );
          })}
        </svg>
        {hover !== null &&
          (() => {
            const d = data[hover]!;
            const cx = ((padL + (hover + 0.5) * slot) / W) * 100;
            const label = d.hour === 0 ? '12am' : d.hour === 12 ? '12pm' : d.hour < 12 ? `${d.hour}am` : `${d.hour - 12}pm`;
            return (
              <div
                className="pointer-events-none absolute -top-1 z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded border border-slate-200 bg-white px-2 py-1 text-[11px] shadow-sm"
                style={{ left: `${cx}%` }}
              >
                <div className="font-medium text-slate-700">{label}</div>
                <div className="font-mono tabular-nums text-slate-600">
                  total {d.total}
                  {d.failed > 0 ? <span className="text-rose-600"> · {d.failed} failed</span> : null}
                </div>
              </div>
            );
          })()}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// HIPAA compliance card
// ---------------------------------------------------------------------------

function HipaaComplianceCard({ data }: { data: HipaaState }) {
  const critical = data.findings.find((f) => f.severity === 'critical') ?? { severity: 'critical', total: 0, resolved: 0 };
  const high = data.findings.find((f) => f.severity === 'high') ?? { severity: 'high', total: 0, resolved: 0 };
  const medium = data.findings.find((f) => f.severity === 'medium') ?? { severity: 'medium', total: 0, resolved: 0 };
  const cov = data.auditCoverage;
  const covPct = cov.total > 0 ? (cov.covered / cov.total) * 100 : 0;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-slate-600" />
          <h2 className="text-sm font-semibold text-slate-900">HIPAA compliance</h2>
        </div>
        <span className="text-[11px] text-slate-500">reviewed {data.lastReview}</span>
      </div>

      <ul className="space-y-2.5 text-sm">
        <li className="flex items-center justify-between">
          <span className="inline-flex items-center gap-2 text-slate-800">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span className="font-mono tabular-nums">{critical.total}</span> critical findings
          </span>
          <span className="text-[11px] font-medium text-emerald-700">{critical.total === 0 ? 'Clear' : 'Open'}</span>
        </li>

        <li>
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-2 text-slate-800">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-100 text-[10px] font-bold text-amber-800">!</span>
              <span className="font-mono tabular-nums">{high.total}</span> high
              <span className="text-slate-400">·</span>
              <span className="text-slate-500">
                {high.resolved} resolved, {high.total - high.resolved} pending
              </span>
            </span>
          </div>
          <div className="mt-1.5 ml-6 h-1 w-full overflow-hidden rounded-full bg-amber-100">
            <div className="h-full bg-amber-500" style={{ width: `${(high.resolved / Math.max(1, high.total)) * 100}%` }} />
          </div>
        </li>

        <li className="flex items-center justify-between">
          <span className="inline-flex items-center gap-2 text-slate-800">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-600">·</span>
            <span className="font-mono tabular-nums">{medium.total}</span> medium
            <span className="text-slate-400">·</span>
            <span className="text-slate-500">
              {medium.resolved} resolved, {medium.total - medium.resolved} pending
            </span>
          </span>
        </li>

        <li className="flex items-center justify-between border-t border-slate-100 pt-2.5">
          <span className="inline-flex items-center gap-2 text-slate-800">
            <Activity className="h-4 w-4 text-emerald-600" />
            Audit coverage <span className="font-mono tabular-nums text-slate-900">{covPct.toFixed(0)}%</span>
            <span className="text-slate-400">·</span>
            <span className="font-mono text-xs text-slate-500">
              {cov.covered}/{cov.total} actions
            </span>
          </span>
        </li>
      </ul>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helpers — duplicated from the server-side data layer because we
// reapply them on the SSE-injected rows. Keep them in sync.
// ---------------------------------------------------------------------------

function categorizeAction(action: string): ActivityCategory {
  if (action.startsWith('LOGIN') || action === 'LOGOUT' || action === 'SESSION_EXPIRED') return 'auth';
  if (action.startsWith('VISIT_')) return 'visit';
  if (
    action.includes('EXPORT') ||
    action.includes('EMAIL_SENT') ||
    action.includes('EMAIL_BLOCKED') ||
    action.includes('PDF') ||
    action.includes('DOCX') ||
    action.includes('CLIPBOARD')
  )
    return 'export';
  return 'admin';
}

function formatClock(d: Date): string {
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${h}:${m}:${s}`;
}
