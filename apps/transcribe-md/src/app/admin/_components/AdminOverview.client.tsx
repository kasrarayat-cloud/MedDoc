'use client';

// ============================================================================
// Admin overview dashboard — client component
// ----------------------------------------------------------------------------
// Receives initial SSR data via props; the only client-side fetch is the
// SSE subscription that streams new audit-log rows into the activity feed.
//
// Phase 5 (Linear V1 Faithful) — chrome rendered against the dark canvas
// using the .qm-lin-* catalog + Inter typography. Inline visual primitives
// keep fidelity high without forking the shared Card/Button. Underlying
// data flow, SSE subscription, mutation calls, and event categorization
// are unchanged from Phase 4. The `theme` prop is preserved for caller-
// site compatibility but ignored.
// ============================================================================

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { toast } from 'sonner';
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
  LogOut,
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
import { cls, summarizeHipaaFindings } from '../_lib/admin-format';
import { signOutAction } from '@/actions/session';

// ---------------------------------------------------------------------------
// Top-level component
// ---------------------------------------------------------------------------

interface Props {
  /** Server-rendered seed data; the client mutates `activity` from the SSE stream. */
  initial: AdminOverviewInitialData;
  /** Email of the current SUPER_ADMIN, shown in the header avatar. */
  userEmail: string;
  /** Phase 4 dual-theme prop. Phase 5 ignores it; kept for caller compat. */
  theme?: string;
}

export default function AdminOverview({ initial, userEmail }: Props) {
  const router = useRouter();
  const [filter, setFilter] = useState<FilterKey>('all');
  const [rows, setRows] = useState<ActivityRow[]>(initial.activity);
  const [connected, setConnected] = useState(false);
  // Phase 6E — ref so ThreatsBar's "View all" can scroll the feed into view.
  // Phase 6H — superseded by /admin/threats; kept for layout anchoring only.
  const activityFeedRef = useRef<HTMLDivElement>(null);

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
    <div className="min-h-screen bg-linear-bg text-linear-text">
      {/* Tailwind doesn't ship a one-off keyframe utility; this scoped block
          keeps the row-fade effect without dragging in a Tailwind plugin. */}
      <style>{`@keyframes qm-fade-in { from { opacity: 0; transform: translateY(-2px); } to { opacity: 1; transform: none; } }`}</style>

      <DashboardHeader userEmail={userEmail} lastUpdated={lastUpdated} />
      <AdminNav />

      <main className="mx-auto max-w-[1440px] px-6 py-6 flex flex-col gap-5">
        <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <StatusCard icon={Database} label="Database" health={initial.systemHealth.database} />
          <StatusCard icon={Server} label="Redis" health={initial.systemHealth.redis} />
          <StatusCard icon={HardDrive} label="Object storage" health={initial.systemHealth.minio} />
          <StatusCard icon={Cloud} label="External APIs" health={initial.systemHealth.externalAPIs} />
        </section>

        <ThreatsBar
          threats={initial.threats}
          onViewAll={() => router.push('/admin/threats')}
        />

        <section className="grid grid-cols-1 gap-4 lg:grid-cols-5">
          <div className="lg:col-span-3" ref={activityFeedRef}>
            <ActivityFeed rows={rows} filter={filter} onFilter={setFilter} connected={connected} />
          </div>
          <div className="space-y-4 lg:col-span-2">
            <PipelineMetricsCard data={initial.pipeline} />
            <TimelineChartCard data={initial.timeline} />
            <HipaaComplianceCard data={initial.hipaa} />
          </div>
        </section>

        <footer className="pt-4 text-[11px] text-linear-text-3">
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
  return (
    <header className="sticky top-0 z-20 border-b border-linear-border bg-linear-surface-1/95 backdrop-blur supports-[backdrop-filter]:bg-linear-surface-1/85">
      <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3">
        <div>
          <div className="font-mono text-[10.5px] uppercase tracking-[0.08em] text-linear-text-3 mb-1">
            Admin · QuillMD
          </div>
          <h1 className="text-[20px] font-semibold tracking-tight text-linear-text leading-tight">
            Admin dashboard
          </h1>
          <div className="mt-1 text-[11px] text-linear-text-3">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-linear-sage" />
              Production
            </span>
            <span className="mx-1.5 text-linear-text-3">·</span>
            <span>
              last updated{' '}
              <span className="font-mono tabular-nums text-linear-text-2">{lastUpdated}</span>
            </span>
          </div>
        </div>
        <UserMenu userEmail={userEmail} />
      </div>
    </header>
  );
}

/** Phase 6E — header user chip with a working dropdown. The previous
 *  version was a static `<button>` with no onClick; clicks did nothing.
 *  Hand-rolled instead of pulling in a popover primitive — consistent
 *  with the rest of the admin surface (no Radix / no headlessui). */
function UserMenu({ userEmail }: { userEmail: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const initial = userEmail.slice(0, 1).toUpperCase();

  // Click-outside + Escape to close.
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!wrapperRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  async function handleSignOut() {
    if (signingOut) return;
    setSigningOut(true);
    try {
      const result = await signOutAction();
      if (!result.ok) {
        toast.error('Sign-out was not completed', {
          description: result.message,
        });
        return;
      }
      // Host-relative navigation preserves the admin host-only boundary.
      router.push('/login');
      router.refresh();
    } catch {
      toast.error('Sign-out was not completed', {
        description: 'Please check your connection and try again.',
      });
    } finally {
      setSigningOut(false);
    }
  }

  return (
    <div className="relative" ref={wrapperRef}>
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="qm-lin-btn"
        style={{ padding: '6px 10px' }}
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-linear-sage-tint text-[10px] font-semibold text-linear-sage-bright">
          {initial}
        </span>
        <span className="hidden font-medium text-linear-text-2 sm:inline">{userEmail}</span>
        <ChevronDown className="h-3 w-3 text-linear-text-3" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-30 mt-1.5 w-56 overflow-hidden rounded-md border border-linear-border bg-linear-surface-2 shadow-[0_20px_40px_rgba(0,0,0,0.5)]"
        >
          <div className="border-b border-linear-border px-3 py-2">
            <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">Signed in as</div>
            <div className="mt-0.5 truncate font-mono text-xs text-linear-text-2">{userEmail}</div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={handleSignOut}
            disabled={signingOut}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-linear-text-2 hover:bg-linear-surface-3 disabled:opacity-60"
          >
            <LogOut className="h-3.5 w-3.5 text-linear-text-3" />
            {signingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status strip
// ---------------------------------------------------------------------------

function StatusDot({ status }: { status: HealthStatus }) {
  const dotCls =
    status === 'healthy'
      ? 'bg-linear-sage'
      : status === 'degraded'
        ? 'bg-linear-warning'
        : 'bg-linear-danger';
  return (
    <span className="relative inline-flex h-2 w-2">
      {status === 'healthy' && (
        <span className="absolute inline-flex h-full w-full rounded-full bg-linear-sage opacity-50 animate-ping" />
      )}
      <span className={`relative inline-flex h-2 w-2 rounded-full ${dotCls}`} />
    </span>
  );
}

function StatusBadge({ status }: { status: HealthStatus }) {
  const palette: Record<HealthStatus, string> = {
    healthy: 'bg-linear-sage-tint text-linear-sage-bright',
    degraded: 'bg-[rgba(212,164,55,0.15)] text-linear-warning',
    down: 'bg-[rgba(212,87,74,0.15)] text-linear-danger',
  };
  const label: Record<HealthStatus, string> = { healthy: 'Healthy', degraded: 'Degraded', down: 'Down' };
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 font-mono text-[10px] font-medium tracking-[0.05em] uppercase ${palette[status]}`}
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
    <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-4 transition-colors hover:border-linear-border-strong">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-linear-sage-tint">
            <Icon className="h-4 w-4 text-linear-sage-bright" />
          </div>
          <div className="text-sm font-medium text-linear-text">{label}</div>
        </div>
        <StatusBadge status={health.status} />
      </div>
      <div className="mt-3 font-mono text-xs text-linear-text-3">{health.metric}</div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Threats bar
// ---------------------------------------------------------------------------

function ThreatsBar({
  threats,
  onViewAll,
}: {
  threats: Threat[];
  onViewAll: () => void;
}) {
  // Phase 6G — render a calm empty state instead of vanishing the
  // whole bar. Phase 5 — sage-tinted on dark canvas.
  if (threats.length === 0) {
    return (
      <div className="flex items-center gap-3 rounded-lg border border-linear-border bg-linear-sage-tint px-4 py-3">
        <CheckCircle2
          className="h-4 w-4 shrink-0 text-linear-sage-bright"
          strokeWidth={2.25}
        />
        <div className="min-w-0 flex-1 text-sm">
          <span className="font-medium text-linear-sage-bright">No active threats</span>
          <span className="mx-2 text-linear-text-3">·</span>
          <span className="text-linear-text-2">
            last 24h failed-login bursts · last 24h cross-tenant attempts · last 24h
            blocked external email exports · last 7d privilege escalations
          </span>
        </div>
      </div>
    );
  }
  const headline = threats[0]!;
  return (
    <div className="flex items-center gap-3 rounded-lg border border-linear-border bg-[rgba(212,164,55,0.10)] px-4 py-3">
      <AlertTriangle className="h-4 w-4 shrink-0 text-linear-warning" strokeWidth={2.25} />
      <div className="min-w-0 flex-1">
        <div className="text-sm">
          <button
            type="button"
            onClick={onViewAll}
            className="font-semibold text-linear-warning underline decoration-linear-warning/40 underline-offset-2 hover:decoration-linear-warning"
          >
            {threats.length} active threat{threats.length === 1 ? '' : 's'}
          </button>
          <span className="mx-2 text-linear-text-3">·</span>
          <span className="text-linear-text">{headline.summary}</span>
        </div>
        <div className="mt-0.5 text-xs text-linear-text-3">{headline.detail}</div>
      </div>
      <button type="button" onClick={onViewAll} className="qm-lin-btn">
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
        (active
          ? 'bg-linear-sage-tint text-linear-sage-bright'
          : 'bg-linear-surface-2 text-linear-text-2 hover:bg-linear-surface-3 hover:text-linear-text')
      }
    >
      {children}
      {typeof count === 'number' && (
        <span
          className={
            'rounded-sm px-1 font-mono text-[10px] ' +
            (active ? 'text-linear-sage-bright/85' : 'text-linear-text-3')
          }
        >
          {count}
        </span>
      )}
    </button>
  );
}

function ActionChip({ action, success }: { action: string; success: boolean }) {
  const chipCls = success
    ? 'bg-linear-surface-2 text-linear-text-2'
    : 'bg-[rgba(212,87,74,0.15)] text-linear-danger';
  return (
    <span
      className={`inline-flex items-center rounded px-1.5 py-0.5 font-mono text-[10px] font-medium tracking-tight ${chipCls}`}
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
    <div className="flex flex-col overflow-hidden rounded-lg border border-linear-border bg-linear-surface-1">
      <div className="flex items-center justify-between border-b border-linear-border px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-linear-text">Live activity</h2>
          <span className="flex items-center gap-1.5 text-[11px] text-linear-text-3">
            <span
              className={`h-1.5 w-1.5 rounded-full ${connected ? 'bg-linear-sage' : 'bg-linear-text-3'} ${connected ? 'animate-pulse' : ''}`}
            />
            {connected ? 'Streaming' : 'Reconnecting…'}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-linear-text-3">
          <Search className="h-3.5 w-3.5" />
          <span className="font-mono">{filtered.length} events</span>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1.5 border-b border-linear-border px-4 py-2.5">
        {FILTER_TABS.map((t) => (
          <FilterPill key={t.key} active={filter === t.key} onClick={() => onFilter(t.key)} count={counts[t.key]}>
            {t.label}
          </FilterPill>
        ))}
      </div>

      <div className="max-h-[560px] overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 px-6 py-16 text-center">
            <div className="text-sm text-linear-text-3">No events match this filter.</div>
            <button
              type="button"
              className="qm-lin-btn"
              onClick={() => onFilter('all')}
            >
              Show all
            </button>
          </div>
        ) : (
          <ul className="divide-y divide-linear-border">
            {filtered.map((row) => (
              <li
                key={row.id}
                className="group relative flex items-center gap-3 px-4 py-2.5 text-sm text-linear-text-2 transition-colors duration-200 hover:bg-linear-row-hover"
                style={row.isNew ? { animation: 'qm-fade-in 200ms ease-out both' } : undefined}
              >
                <span
                  className={`absolute left-0 top-0 h-full w-[3px] ${row.success ? 'bg-linear-sage/70' : 'bg-linear-danger'}`}
                  aria-hidden
                />
                <span className="font-mono text-[11px] tabular-nums text-linear-text-3 w-[68px] shrink-0">
                  {row.timestamp}
                </span>
                <ActionChip action={row.action} success={row.success} />
                <span className="truncate text-linear-text">{row.actorEmail}</span>
                {row.target && (
                  <>
                    <span className="text-linear-text-3">·</span>
                    <span className="truncate font-mono text-xs text-linear-text-3">{row.target}</span>
                  </>
                )}
                <span className="ml-auto hidden font-mono text-[11px] text-linear-text-3 group-hover:inline lg:inline">
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
    <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-4">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-linear-text">Transcription pipeline</h2>
        <span className="text-[11px] text-linear-text-3">last 24h</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <div className="font-mono text-2xl font-medium tabular-nums text-linear-text">{data.successRate.toFixed(1)}%</div>
          <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">Success rate</div>
        </div>
        <div>
          <div className="font-mono text-2xl font-medium tabular-nums text-linear-text">{data.p50}</div>
          <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">p50 latency</div>
        </div>
        <div>
          <div className="font-mono text-2xl font-medium tabular-nums text-linear-text">{data.p95}</div>
          <div className="font-mono text-[10px] uppercase tracking-[0.08em] text-linear-text-3">p95 latency</div>
        </div>
      </div>

      <div className="mt-4">
        <div className="flex h-1.5 w-full overflow-hidden rounded-full bg-linear-surface-2">
          <div className="bg-linear-sage" style={{ width: `${okPct}%` }} />
          <div className="bg-linear-danger" style={{ width: `${failPct}%` }} />
          <div className="bg-linear-warning" style={{ width: `${pendPct}%` }} />
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-linear-text-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-linear-sage" />
            <span className="font-mono tabular-nums text-linear-text-2">{data.succeeded.toLocaleString()}</span> succeeded
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-linear-danger" />
            <span className="font-mono tabular-nums text-linear-text-2">{data.failed}</span> failed
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-linear-warning" />
            <span className="font-mono tabular-nums text-linear-text-2">{data.pending}</span> pending
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
    <div className="rounded-lg border border-linear-border bg-linear-surface-1 p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <div className="flex items-baseline gap-2">
          <h2 className="text-sm font-semibold text-linear-text">Audit events</h2>
          <span className="text-[11px] text-linear-text-3">last 24h</span>
        </div>
        <div className="flex items-center gap-3 text-[11px] text-linear-text-3">
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-3 rounded-sm bg-linear-text-3" /> total{' '}
            <span className="font-mono tabular-nums text-linear-text-2">{totalEvents.toLocaleString()}</span>
          </span>
          <span className="inline-flex items-center gap-1.5">
            <span className="h-1.5 w-3 rounded-sm bg-linear-danger" /> failed{' '}
            <span className="font-mono tabular-nums text-linear-text-2">{totalFailed}</span>
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
                  <rect x={padL + i * slot} y={padT} width={slot} height={innerH} fill="rgba(122,166,140,0.08)" />
                )}
                <rect x={x} y={yTotal} width={barW} height={totalH} fill={isHover ? '#7AA68C' : '#3a3d44'} rx="1" />
                {d.failed > 0 && <rect x={x} y={yFailed} width={barW} height={failedH} fill="#d4574a" rx="1" />}
              </g>
            );
          })}
          <line x1={padL} x2={W - padR} y1={padT + innerH + 0.5} y2={padT + innerH + 0.5} stroke="#21232a" strokeWidth="1" />
          {xTicks.map((h) => {
            const cx = padL + (h + 0.5) * slot;
            const label = h === 0 ? '12a' : h === 12 ? '12p' : h < 12 ? `${h}a` : `${h - 12}p`;
            return (
              <text key={h} x={cx} y={H - 4} fontSize="10" fill="#6c737f" textAnchor="middle" fontFamily="Inter, sans-serif">
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
                className="pointer-events-none absolute -top-1 z-10 -translate-x-1/2 -translate-y-full whitespace-nowrap rounded border border-linear-border bg-linear-surface-2 px-2 py-1 text-[11px] shadow-[0_8px_20px_rgba(0,0,0,0.4)]"
                style={{ left: `${cx}%` }}
              >
                <div className="font-medium text-linear-text">{label}</div>
                <div className="font-mono tabular-nums text-linear-text-2">
                  total {d.total}
                  {d.failed > 0 ? <span className="text-linear-danger"> · {d.failed} failed</span> : null}
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
  // Phase 7A consistency fix: every figure on this card now flows from a
  // single derivation. Phase 7B: card now click-throughs to /admin/hipaa
  // where each finding can be opened + resolved.
  const summary = summarizeHipaaFindings(data.findings);
  const critical = summary.bySeverity.critical;
  const high = summary.bySeverity.high;
  const medium = summary.bySeverity.medium;
  const cov = data.auditCoverage;
  const covPct = cov.total > 0 ? (cov.covered / cov.total) * 100 : 0;
  return (
    <Link
      href="/admin/hipaa"
      data-testid="hipaa-card"
      className="block rounded-lg border border-linear-border bg-linear-surface-1 p-4 transition-colors hover:border-linear-border-strong"
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-linear-text-2" />
          <h2 className="text-sm font-semibold text-linear-text">HIPAA compliance</h2>
        </div>
        <div className="flex items-center gap-2">
          <HipaaStatusBadge totalOpen={summary.totalOpen} />
          <span className="text-[11px] text-linear-text-3">reviewed {data.lastReview}</span>
        </div>
      </div>

      <ul className="space-y-2.5 text-sm">
        <li className="flex items-center justify-between" data-testid="hipaa-row-critical">
          <span className="inline-flex items-center gap-2 text-linear-text-2">
            <CheckCircle2
              className={cls(
                'h-4 w-4',
                critical.open === 0 ? 'text-linear-sage-bright' : 'text-linear-danger'
              )}
            />
            <span className="font-mono tabular-nums text-linear-text" data-testid="hipaa-critical-total">{critical.total}</span>
            critical
            <span className="text-linear-text-3">·</span>
            <span className="text-linear-text-3">
              <span data-testid="hipaa-critical-resolved">{critical.resolved}</span> resolved,{' '}
              <span data-testid="hipaa-critical-pending">{critical.open}</span> pending
            </span>
          </span>
        </li>

        <li data-testid="hipaa-row-high">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-2 text-linear-text-2">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-[rgba(212,164,55,0.18)] text-[10px] font-bold text-linear-warning">!</span>
              <span className="font-mono tabular-nums text-linear-text" data-testid="hipaa-high-total">{high.total}</span> high
              <span className="text-linear-text-3">·</span>
              <span className="text-linear-text-3">
                <span data-testid="hipaa-high-resolved">{high.resolved}</span> resolved,{' '}
                <span data-testid="hipaa-high-pending">{high.open}</span> pending
              </span>
            </span>
          </div>
          <div className="mt-1.5 ml-6 h-1 w-full overflow-hidden rounded-full bg-[rgba(212,164,55,0.18)]">
            <div
              className="h-full bg-linear-warning"
              style={{ width: `${(high.resolved / Math.max(1, high.total)) * 100}%` }}
            />
          </div>
        </li>

        <li className="flex items-center justify-between" data-testid="hipaa-row-medium">
          <span className="inline-flex items-center gap-2 text-linear-text-2">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-linear-surface-2 text-[10px] font-bold text-linear-text-3">·</span>
            <span className="font-mono tabular-nums text-linear-text" data-testid="hipaa-medium-total">{medium.total}</span> medium
            <span className="text-linear-text-3">·</span>
            <span className="text-linear-text-3">
              <span data-testid="hipaa-medium-resolved">{medium.resolved}</span> resolved,{' '}
              <span data-testid="hipaa-medium-pending">{medium.open}</span> pending
            </span>
          </span>
        </li>

        <li className="flex items-center justify-between border-t border-linear-border pt-2.5">
          <span className="inline-flex items-center gap-2 text-linear-text-2">
            <Activity className="h-4 w-4 text-linear-sage-bright" />
            Audit coverage <span className="font-mono tabular-nums text-linear-text">{covPct.toFixed(0)}%</span>
            <span className="text-linear-text-3">·</span>
            <span className="font-mono text-xs text-linear-text-3">
              {cov.covered}/{cov.total} actions
            </span>
          </span>
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-linear-text-3">
            View all <ArrowUpRight className="h-3 w-3" />
          </span>
        </li>
      </ul>
    </Link>
  );
}

/** Phase 7A: card-header status pill. Derived from totalOpen so it
 *  CAN'T disagree with the per-severity rows below. */
function HipaaStatusBadge({ totalOpen }: { totalOpen: number }) {
  if (totalOpen === 0) {
    return (
      <span
        data-testid="hipaa-status-badge"
        data-open-count={0}
        className="qm-lin-pill qm-lin-pill--sage"
      >
        <CheckCircle2 className="h-3 w-3" />
        All clear
      </span>
    );
  }
  return (
    <span
      data-testid="hipaa-status-badge"
      data-open-count={totalOpen}
      className="qm-lin-pill"
      style={{
        background: 'rgba(212,164,55,0.15)',
        color: 'var(--color-linear-warning)',
      }}
    >
      <AlertTriangle className="h-3 w-3" />
      {totalOpen} open
    </span>
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
