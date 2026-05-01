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
//
// Phase 2 (Clinician remodel) — Batch G — Strategy A dual-theme via
// additive `theme` prop. Default `'legacy'` keeps the slate-on-white
// rendering verbatim. The Clinician branch renders a parallel layout
// using `.qm-cl-card`, `.qm-cl-pill-*`, `.qm-cl-btn-*`, the
// `.qm-cl-eyebrow` + serif headline pattern from the dashboard mockup,
// and the cream/sage/ink palette via tokens. Underlying data flow,
// SSE subscription, and event categorization are unchanged.
// ============================================================================

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { signOut } from 'next-auth/react';
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

// ---------------------------------------------------------------------------
// Top-level component
// ---------------------------------------------------------------------------

type AdminOverviewTheme = 'legacy' | 'clinician';

interface Props {
  /** Server-rendered seed data; the client mutates `activity` from the SSE stream. */
  initial: AdminOverviewInitialData;
  /** Email of the current SUPER_ADMIN, shown in the header avatar. */
  userEmail: string;
  theme?: AdminOverviewTheme;
}

export default function AdminOverview({ initial, userEmail, theme = 'legacy' }: Props) {
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

  // Phase 4 — Apple Cinematic anim-1 reveal sweep.
  //
  // The CinematicAdminHero in admin/layout.tsx already drives the eyebrow
  // + "Operations." word + downstream `.av1-*` animation timeline on the
  // initial page load. But Next.js App Router keeps the layout mounted
  // across in-app navigation between admin pages, so when a SUPER_ADMIN
  // navigates /admin → /admin/users → /admin and lands back on the
  // overview, the AdminOverview component re-mounts but the hero's
  // useEffect (a one-shot on hero mount) doesn't re-fire. Without this
  // sweep, the stat cards would render in their .av1-card initial state
  // (blurred + translated) and never reveal.
  //
  // This effect runs on every AdminOverview mount and adds `.show` to
  // every `.av1-*` element in this component's tree using the same
  // staggered timeline as the hero. It is purely visual — does not
  // touch SSE, mutations, or data fetching, and respects reduced motion.
  useEffect(() => {
    if (theme !== 'clinician') return;
    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (reducedMotion) {
      document
        .querySelectorAll<HTMLElement>('.av1-word, .av1-fade, .av1-card, .av1-cta')
        .forEach((el) => el.classList.add('show'));
      return;
    }

    const timers: Array<ReturnType<typeof setTimeout>> = [];

    const raf = requestAnimationFrame(() => {
      document.querySelectorAll<HTMLElement>('.av1-card').forEach((c) => {
        const d = parseInt(c.dataset.d ?? '600', 10);
        timers.push(setTimeout(() => c.classList.add('show'), d));
      });
      document.querySelectorAll<HTMLElement>('.av1-fade').forEach((e, i) => {
        timers.push(setTimeout(() => e.classList.add('show'), 1500 + i * 90));
      });
      document.querySelectorAll<HTMLElement>('.av1-word').forEach((w) => {
        const d = parseInt(w.dataset.d ?? '0', 10);
        timers.push(setTimeout(() => w.classList.add('show'), d + 80));
      });
      document.querySelectorAll<HTMLElement>('.av1-cta').forEach((c, i) => {
        const d = parseInt(c.dataset.d ?? `${1400 + i * 100}`, 10);
        timers.push(setTimeout(() => c.classList.add('show'), d));
      });
    });

    return () => {
      timers.forEach((t) => clearTimeout(t));
      cancelAnimationFrame(raf);
    };
  }, [theme]);

  const lastUpdated = `${tick}s ago`;

  if (theme === 'clinician') {
    return (
      <div style={{ minHeight: '100vh', color: 'var(--ink)' }}>
        {/* Tailwind doesn't ship a one-off keyframe utility; this scoped block
            keeps the row-fade effect without dragging in a Tailwind plugin. */}
        <style>{`@keyframes qm-fade-in { from { opacity: 0; transform: translateY(-2px); } to { opacity: 1; transform: none; } }`}</style>

        <ClinicianDashboardHeader userEmail={userEmail} lastUpdated={lastUpdated} />
        <AdminNav theme="clinician" />

        <main className="mx-auto max-w-[1440px] px-6 py-6" style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
          {/* Phase 4 — Apple Cinematic anim-1 reveal stagger.
              The CinematicAdminHero (mounted by admin/layout.tsx above this
              tree) drives a single animation timeline that adds `.show` to
              every `.av1-*` element on the page. The four stat cards reveal
              at 600/700/800/900 ms with the .av1-card blur-to-sharp slide;
              the tables + drawers below use .av1-fade for a 1500 ms+ late
              reveal. Data fetching, mutation calls, and SSE subscription
              are unchanged — only wrappers + class names are added. */}
          <section className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="av1-card" data-d="600">
              <ClinicianStatusCard icon={Database} label="Database" health={initial.systemHealth.database} />
            </div>
            <div className="av1-card" data-d="700">
              <ClinicianStatusCard icon={Server} label="Redis" health={initial.systemHealth.redis} />
            </div>
            <div className="av1-card" data-d="800">
              <ClinicianStatusCard icon={HardDrive} label="Object storage" health={initial.systemHealth.minio} />
            </div>
            <div className="av1-card" data-d="900">
              <ClinicianStatusCard icon={Cloud} label="External APIs" health={initial.systemHealth.externalAPIs} />
            </div>
          </section>

          <div className="av1-fade">
            <ClinicianThreatsBar
              threats={initial.threats}
              onViewAll={() => router.push('/admin/threats')}
            />
          </div>

          <section className="grid grid-cols-1 gap-4 lg:grid-cols-5">
            <div className="lg:col-span-3 av1-fade" ref={activityFeedRef}>
              <ClinicianActivityFeed rows={rows} filter={filter} onFilter={setFilter} connected={connected} />
            </div>
            <div className="space-y-4 lg:col-span-2">
              <div className="av1-fade">
                <ClinicianPipelineMetricsCard data={initial.pipeline} />
              </div>
              <div className="av1-fade">
                <ClinicianTimelineChartCard data={initial.timeline} />
              </div>
              <div className="av1-fade">
                <ClinicianHipaaComplianceCard data={initial.hipaa} />
              </div>
            </div>
          </section>

          <footer style={{ paddingTop: 16, fontSize: 11, color: 'var(--ink-4)' }}>
            Audit logs retained 7 years per HIPAA §164.316(b)(2)(i). All admin actions on this page are themselves logged.
          </footer>
        </main>
      </div>
    );
  }

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
          <UserMenu userEmail={userEmail} />
        </div>
      </div>
    </header>
  );
}

/** Phase 6E — header user chip with a working dropdown. The previous
 *  version was a static `<button>` with no onClick; clicks did nothing.
 *  Hand-rolled instead of pulling in a popover primitive — consistent
 *  with the rest of the admin surface (no Radix / no headlessui). */
function UserMenu({ userEmail }: { userEmail: string }) {
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
      // signOut from next-auth/react clears the JWT cookie + redirects.
      // callbackUrl is host-relative on purpose: an admin signing out
      // from admin.quillmd.com should land on admin.quillmd.com/login,
      // not on app.quillmd.com (cookies are host-only).
      await signOut({ callbackUrl: '/login', redirect: true });
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
        className="ml-1 flex items-center gap-2 rounded-md border border-slate-200 bg-white px-2 py-1 text-xs hover:bg-slate-50"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-900 text-[10px] font-semibold text-white">
          {initial}
        </span>
        <span className="hidden font-medium text-slate-800 sm:inline">{userEmail}</span>
        <ChevronDown className="h-3 w-3 text-slate-500" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full z-30 mt-1.5 w-56 overflow-hidden rounded-md border border-slate-200 bg-white shadow-lg"
        >
          <div className="border-b border-slate-100 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-slate-500">Signed in as</div>
            <div className="mt-0.5 truncate text-xs font-mono text-slate-700">{userEmail}</div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={handleSignOut}
            disabled={signingOut}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-slate-800 hover:bg-slate-50 disabled:opacity-60"
          >
            <LogOut className="h-3.5 w-3.5 text-slate-500" />
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

function ThreatsBar({
  threats,
  onViewAll,
}: {
  threats: Threat[];
  onViewAll: () => void;
}) {
  // Phase 6G — render a calm empty state instead of vanishing the
  // whole bar. The previous behaviour (hide on empty) made admins
  // wonder whether the panel had broken vs. genuinely had nothing
  // to show. Silence-as-absence is bad signal here; an explicit
  // "no active threats" with a green check is better.
  if (threats.length === 0) {
    return (
      <div className="flex items-center gap-3 rounded-md border border-emerald-200 bg-emerald-50/60 px-4 py-3">
        <CheckCircle2
          className="h-4 w-4 shrink-0 text-emerald-700"
          strokeWidth={2.25}
        />
        <div className="min-w-0 flex-1 text-sm">
          <span className="font-medium text-emerald-900">No active threats</span>
          <span className="mx-2 text-emerald-700/40">·</span>
          <span className="text-emerald-800">
            last 24h failed-login bursts · last 24h cross-tenant attempts · last 24h
            blocked external email exports · last 7d privilege escalations
          </span>
        </div>
      </div>
    );
  }
  const headline = threats[0]!;
  return (
    <div className="flex items-center gap-3 rounded-md border border-amber-300 bg-amber-50 px-4 py-3">
      <AlertTriangle className="h-4 w-4 shrink-0 text-amber-700" strokeWidth={2.25} />
      <div className="min-w-0 flex-1">
        <div className="text-sm">
          <button
            type="button"
            onClick={onViewAll}
            className="font-semibold text-amber-900 underline decoration-amber-700/30 underline-offset-2 hover:decoration-amber-700"
          >
            {threats.length} active threat{threats.length === 1 ? '' : 's'}
          </button>
          <span className="mx-2 text-amber-700/40">·</span>
          <span className="text-amber-900">{headline.summary}</span>
        </div>
        <div className="mt-0.5 text-xs text-amber-800/80">{headline.detail}</div>
      </div>
      <button
        type="button"
        onClick={onViewAll}
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
  // Phase 7A consistency fix: every figure on this card now flows from a
  // single derivation. Previously the "Clear" status badge looked at
  // critical.total alone and missed pending high/medium findings, so the
  // card could read "Clear" while showing 3 pending high issues right
  // below — Kasra's drift bug. The header status, the per-severity row
  // counts, and the chart bars all read from `summary` now.
  // Phase 7B: card now click-throughs to /admin/hipaa where each
  // finding can be opened + resolved.
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
      className="block rounded-lg border border-slate-200 bg-white p-4 transition-colors hover:border-slate-300"
    >
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4 text-slate-600" />
          <h2 className="text-sm font-semibold text-slate-900">HIPAA compliance</h2>
        </div>
        <div className="flex items-center gap-2">
          <HipaaStatusBadge totalOpen={summary.totalOpen} />
          <span className="text-[11px] text-slate-500">reviewed {data.lastReview}</span>
        </div>
      </div>

      <ul className="space-y-2.5 text-sm">
        <li className="flex items-center justify-between" data-testid="hipaa-row-critical">
          <span className="inline-flex items-center gap-2 text-slate-800">
            <CheckCircle2
              className={cls(
                'h-4 w-4',
                critical.open === 0 ? 'text-emerald-600' : 'text-rose-600'
              )}
            />
            <span className="font-mono tabular-nums" data-testid="hipaa-critical-total">{critical.total}</span>
            critical
            <span className="text-slate-400">·</span>
            <span className="text-slate-500">
              <span data-testid="hipaa-critical-resolved">{critical.resolved}</span> resolved,{' '}
              <span data-testid="hipaa-critical-pending">{critical.open}</span> pending
            </span>
          </span>
        </li>

        <li data-testid="hipaa-row-high">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-2 text-slate-800">
              <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-amber-100 text-[10px] font-bold text-amber-800">!</span>
              <span className="font-mono tabular-nums" data-testid="hipaa-high-total">{high.total}</span> high
              <span className="text-slate-400">·</span>
              <span className="text-slate-500">
                <span data-testid="hipaa-high-resolved">{high.resolved}</span> resolved,{' '}
                <span data-testid="hipaa-high-pending">{high.open}</span> pending
              </span>
            </span>
          </div>
          <div className="mt-1.5 ml-6 h-1 w-full overflow-hidden rounded-full bg-amber-100">
            <div
              className="h-full bg-amber-500"
              style={{ width: `${(high.resolved / Math.max(1, high.total)) * 100}%` }}
            />
          </div>
        </li>

        <li className="flex items-center justify-between" data-testid="hipaa-row-medium">
          <span className="inline-flex items-center gap-2 text-slate-800">
            <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-600">·</span>
            <span className="font-mono tabular-nums" data-testid="hipaa-medium-total">{medium.total}</span> medium
            <span className="text-slate-400">·</span>
            <span className="text-slate-500">
              <span data-testid="hipaa-medium-resolved">{medium.resolved}</span> resolved,{' '}
              <span data-testid="hipaa-medium-pending">{medium.open}</span> pending
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
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-slate-500">
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
        className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 ring-1 ring-emerald-600/20"
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
      className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-800 ring-1 ring-amber-600/30"
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

// ---------------------------------------------------------------------------
// Clinician variants — render the same data using the .qm-cl-* catalog
// + warm cream/sage/ink tokens. Sub-components are duplicated rather
// than parameterised so the legacy slate-on-white path stays
// byte-for-byte unchanged for non-migrated routes (defense in depth
// for Strategy A).
// ---------------------------------------------------------------------------

function ClinicianDashboardHeader({
  userEmail,
  lastUpdated,
}: {
  userEmail: string;
  lastUpdated: string;
}) {
  return (
    <header
      style={{
        position: 'sticky',
        top: 0,
        zIndex: 20,
        borderBottom: '1px solid var(--line)',
        background: 'var(--cream-card)',
      }}
    >
      <div
        className="mx-auto max-w-[1440px] px-6 py-4 flex items-center justify-between"
      >
        <div>
          <div className="qm-cl-eyebrow" style={{ marginBottom: 4 }}>Admin · QuillMD</div>
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
            Admin dashboard
          </h1>
          <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-3)' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: 999,
                  background: 'var(--sage)',
                }}
              />
              Production
            </span>
            <span className="mx-2" style={{ color: 'var(--ink-4)' }}>·</span>
            last updated{' '}
            <span className="qm-cl-mono" style={{ fontVariantNumeric: 'tabular-nums' }}>
              {lastUpdated}
            </span>
          </div>
        </div>
        <ClinicianUserMenu userEmail={userEmail} />
      </div>
    </header>
  );
}

function ClinicianUserMenu({ userEmail }: { userEmail: string }) {
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const initial = userEmail.slice(0, 1).toUpperCase();

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
      await signOut({ callbackUrl: '/login', redirect: true });
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
        className="qm-cl-btn qm-cl-btn-soft"
        style={{ padding: '6px 12px', fontSize: 13 }}
      >
        <span
          aria-hidden
          className="qm-cl-avatar qm-cl-avatar-sage"
          style={{
            width: 26,
            height: 26,
            fontSize: 11,
            borderRadius: 8,
          }}
        >
          {initial}
        </span>
        <span className="hidden sm:inline" style={{ color: 'var(--ink-2)', fontWeight: 500 }}>
          {userEmail}
        </span>
        <ChevronDown style={{ width: 12, height: 12, color: 'var(--ink-3)' }} />
      </button>
      {open && (
        <div
          role="menu"
          className="qm-cl-card"
          style={{
            position: 'absolute',
            right: 0,
            top: '100%',
            zIndex: 30,
            marginTop: 6,
            width: 224,
            overflow: 'hidden',
            padding: 0,
          }}
        >
          <div
            style={{
              borderBottom: '1px solid var(--line)',
              padding: '10px 14px',
            }}
          >
            <div className="qm-cl-section-label">Signed in as</div>
            <div
              className="qm-cl-mono"
              style={{ marginTop: 2, fontSize: 12, color: 'var(--ink-2)' }}
            >
              {userEmail}
            </div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={handleSignOut}
            disabled={signingOut}
            style={{
              display: 'flex',
              width: '100%',
              alignItems: 'center',
              gap: 8,
              padding: '10px 14px',
              textAlign: 'left',
              fontSize: 12,
              fontWeight: 500,
              color: 'var(--ink-2)',
              background: 'transparent',
              border: 0,
              cursor: signingOut ? 'wait' : 'pointer',
              opacity: signingOut ? 0.6 : 1,
            }}
            className="hover:bg-clinician-cream-2"
          >
            <LogOut style={{ width: 14, height: 14, color: 'var(--ink-3)' }} />
            {signingOut ? 'Signing out…' : 'Sign out'}
          </button>
        </div>
      )}
    </div>
  );
}

function ClinicianStatusDot({ status }: { status: HealthStatus }) {
  const fill =
    status === 'healthy'
      ? 'var(--sage)'
      : status === 'degraded'
        ? 'var(--amber)'
        : 'var(--coral)';
  return (
    <span style={{ position: 'relative', display: 'inline-flex', width: 8, height: 8 }}>
      {status === 'healthy' && (
        <span
          className="qm-pulse"
          style={{
            position: 'absolute',
            inset: 0,
            borderRadius: 999,
            background: 'var(--sage)',
            opacity: 0.45,
          }}
        />
      )}
      <span
        style={{
          position: 'relative',
          width: 8,
          height: 8,
          borderRadius: 999,
          background: fill,
        }}
      />
    </span>
  );
}

function ClinicianStatusBadge({ status }: { status: HealthStatus }) {
  const tone = status === 'healthy' ? 'sage' : status === 'degraded' ? 'amber' : 'coral';
  const label = status === 'healthy' ? 'Healthy' : status === 'degraded' ? 'Degraded' : 'Down';
  return (
    <span className={`qm-cl-pill qm-cl-pill-${tone}`}>
      <ClinicianStatusDot status={status} />
      {label}
    </span>
  );
}

function ClinicianStatusCard({
  icon: Icon,
  label,
  health,
}: {
  icon: React.ComponentType<{ style?: React.CSSProperties }>;
  label: string;
  health: ServiceHealth;
}) {
  return (
    <div className="qm-cl-card qm-cl-lift" style={{ padding: 16 }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div
            style={{
              display: 'inline-flex',
              width: 30,
              height: 30,
              alignItems: 'center',
              justifyContent: 'center',
              borderRadius: 10,
              background: 'var(--sage-tint)',
            }}
          >
            <Icon style={{ width: 14, height: 14, color: 'var(--sage-deep)' }} />
          </div>
          <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--ink)' }}>{label}</div>
        </div>
        <ClinicianStatusBadge status={health.status} />
      </div>
      <div
        className="qm-cl-mono"
        style={{ marginTop: 12, fontSize: 12, color: 'var(--ink-3)' }}
      >
        {health.metric}
      </div>
    </div>
  );
}

function ClinicianThreatsBar({
  threats,
  onViewAll,
}: {
  threats: Threat[];
  onViewAll: () => void;
}) {
  if (threats.length === 0) {
    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          borderRadius: 12,
          border: '1px solid var(--sage-tint-strong)',
          background: 'var(--sage-tint)',
          padding: '12px 16px',
        }}
      >
        <CheckCircle2 style={{ width: 16, height: 16, color: 'var(--sage-deep)', flexShrink: 0 }} strokeWidth={2.25} />
        <div style={{ minWidth: 0, flex: 1, fontSize: 13 }}>
          <span style={{ fontWeight: 500, color: 'var(--sage-deep)' }}>No active threats</span>
          <span style={{ margin: '0 8px', color: 'var(--ink-4)' }}>·</span>
          <span style={{ color: 'var(--ink-2)' }}>
            last 24h failed-login bursts · last 24h cross-tenant attempts · last 24h blocked external email exports · last 7d privilege escalations
          </span>
        </div>
      </div>
    );
  }
  const headline = threats[0]!;
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        borderRadius: 12,
        border: '1px solid var(--amber-tint-strong, rgba(212,165,116,0.32))',
        background: 'var(--amber-tint)',
        padding: '12px 16px',
      }}
    >
      <AlertTriangle style={{ width: 16, height: 16, color: 'var(--amber-deep)', flexShrink: 0 }} strokeWidth={2.25} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontSize: 13 }}>
          <button
            type="button"
            onClick={onViewAll}
            style={{
              fontWeight: 600,
              color: 'var(--amber-deep)',
              background: 'transparent',
              border: 0,
              padding: 0,
              cursor: 'pointer',
              textDecoration: 'underline',
              textDecorationColor: 'rgba(122,79,31,0.3)',
              textUnderlineOffset: 2,
            }}
          >
            {threats.length} active threat{threats.length === 1 ? '' : 's'}
          </button>
          <span style={{ margin: '0 8px', color: 'var(--ink-4)' }}>·</span>
          <span style={{ color: 'var(--amber-deep)' }}>{headline.summary}</span>
        </div>
        <div style={{ marginTop: 2, fontSize: 12, color: 'var(--ink-2)' }}>{headline.detail}</div>
      </div>
      <button
        type="button"
        onClick={onViewAll}
        className="qm-cl-btn qm-cl-btn-soft"
        style={{ padding: '6px 12px', fontSize: 12 }}
      >
        View all <ArrowUpRight style={{ width: 12, height: 12 }} />
      </button>
    </div>
  );
}

function ClinicianFilterPill({
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
      style={{
        display: 'inline-flex',
        height: 28,
        alignItems: 'center',
        gap: 6,
        borderRadius: 999,
        padding: '0 12px',
        fontSize: 12,
        fontWeight: 500,
        background: active ? 'var(--sage-tint-strong)' : 'var(--cream-2)',
        color: active ? 'var(--sage-deep)' : 'var(--ink-2)',
        border: 0,
        cursor: 'pointer',
        transition: 'background 240ms var(--ease-clinician), color 240ms var(--ease-clinician)',
      }}
    >
      {children}
      {typeof count === 'number' && (
        <span
          className="qm-cl-mono"
          style={{
            borderRadius: 4,
            padding: '0 4px',
            fontSize: 10,
            color: active ? 'var(--sage-deep)' : 'var(--ink-3)',
            opacity: active ? 0.85 : 1,
          }}
        >
          {count}
        </span>
      )}
    </button>
  );
}

function ClinicianActionChip({ action, success }: { action: string; success: boolean }) {
  return (
    <span
      className="qm-cl-mono"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        borderRadius: 4,
        padding: '2px 6px',
        fontSize: 10,
        fontWeight: 500,
        letterSpacing: '-0.01em',
        background: success ? 'var(--cream-2)' : 'var(--coral-tint)',
        color: success ? 'var(--ink-2)' : 'var(--coral-deep)',
      }}
    >
      {action}
    </span>
  );
}

function ClinicianActivityFeed({
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
    <div className="qm-cl-card" style={{ padding: 0, overflow: 'hidden' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid var(--line)',
          padding: '12px 16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Live activity</h2>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11, color: 'var(--ink-3)' }}>
            <span
              className={connected ? 'qm-pulse' : ''}
              style={{
                width: 6,
                height: 6,
                borderRadius: 999,
                background: connected ? 'var(--sage)' : 'var(--ink-4)',
              }}
            />
            {connected ? 'Streaming' : 'Reconnecting…'}
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--ink-3)' }}>
          <Search style={{ width: 14, height: 14 }} />
          <span className="qm-cl-mono">{filtered.length} events</span>
        </div>
      </div>

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 6,
          borderBottom: '1px solid var(--line)',
          padding: '10px 16px',
        }}
      >
        {FILTER_TABS.map((t) => (
          <ClinicianFilterPill key={t.key} active={filter === t.key} onClick={() => onFilter(t.key)} count={counts[t.key]}>
            {t.label}
          </ClinicianFilterPill>
        ))}
      </div>

      <div style={{ maxHeight: 560, overflowY: 'auto' }}>
        {filtered.length === 0 ? (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              padding: '64px 24px',
              textAlign: 'center',
            }}
          >
            <div style={{ fontSize: 13, color: 'var(--ink-3)' }}>No events match this filter.</div>
            <button
              type="button"
              className="qm-cl-btn qm-cl-btn-soft"
              style={{ padding: '6px 12px', fontSize: 12 }}
              onClick={() => onFilter('all')}
            >
              Show all
            </button>
          </div>
        ) : (
          <ul
            style={{
              listStyle: 'none',
              margin: 0,
              padding: 0,
            }}
          >
            {filtered.map((row, idx) => (
              <li
                key={row.id}
                style={{
                  position: 'relative',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  padding: '10px 16px',
                  fontSize: 13,
                  color: 'var(--ink-2)',
                  borderTop: idx === 0 ? 'none' : '1px solid var(--line)',
                  transition: 'background 200ms var(--ease-clinician)',
                  ...(row.isNew ? { animation: 'qm-fade-in 200ms ease-out both' } : {}),
                }}
                className="hover:bg-clinician-cream-2"
              >
                <span
                  aria-hidden
                  style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    height: '100%',
                    width: 3,
                    background: row.success ? 'var(--sage)' : 'var(--coral)',
                    opacity: row.success ? 0.6 : 1,
                  }}
                />
                <span
                  className="qm-cl-mono"
                  style={{
                    fontSize: 11,
                    fontVariantNumeric: 'tabular-nums',
                    color: 'var(--ink-3)',
                    width: 68,
                    flexShrink: 0,
                  }}
                >
                  {row.timestamp}
                </span>
                <ClinicianActionChip action={row.action} success={row.success} />
                <span
                  style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                    color: 'var(--ink)',
                  }}
                >
                  {row.actorEmail}
                </span>
                {row.target && (
                  <>
                    <span style={{ color: 'var(--ink-4)' }}>·</span>
                    <span
                      className="qm-cl-mono"
                      style={{
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                        fontSize: 12,
                        color: 'var(--ink-3)',
                      }}
                    >
                      {row.target}
                    </span>
                  </>
                )}
                <span
                  className="qm-cl-mono"
                  style={{
                    marginLeft: 'auto',
                    fontSize: 11,
                    color: 'var(--ink-4)',
                  }}
                >
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

function ClinicianPipelineMetricsCard({ data }: { data: PipelineMetrics }) {
  const total = Math.max(1, data.total);
  const okPct = (data.succeeded / total) * 100;
  const failPct = (data.failed / total) * 100;
  const pendPct = (data.pending / total) * 100;
  return (
    <div className="qm-cl-card" style={{ padding: 16 }}>
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Transcription pipeline</h2>
        <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>last 24h</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div>
          <div
            className="qm-cl-serif"
            style={{
              fontSize: 24,
              fontWeight: 500,
              color: 'var(--ink)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {data.successRate.toFixed(1)}%
          </div>
          <div className="qm-cl-section-label">Success rate</div>
        </div>
        <div>
          <div
            className="qm-cl-serif"
            style={{
              fontSize: 24,
              fontWeight: 500,
              color: 'var(--ink)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {data.p50}
          </div>
          <div className="qm-cl-section-label">p50 latency</div>
        </div>
        <div>
          <div
            className="qm-cl-serif"
            style={{
              fontSize: 24,
              fontWeight: 500,
              color: 'var(--ink)',
              fontVariantNumeric: 'tabular-nums',
            }}
          >
            {data.p95}
          </div>
          <div className="qm-cl-section-label">p95 latency</div>
        </div>
      </div>

      <div style={{ marginTop: 16 }}>
        <div
          style={{
            display: 'flex',
            height: 6,
            width: '100%',
            overflow: 'hidden',
            borderRadius: 999,
            background: 'var(--cream-2)',
          }}
        >
          <div style={{ background: 'var(--sage)', width: `${okPct}%` }} />
          <div style={{ background: 'var(--coral)', width: `${failPct}%` }} />
          <div style={{ background: 'var(--amber)', width: `${pendPct}%` }} />
        </div>
        <div
          style={{
            marginTop: 8,
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: '4px 12px',
            fontSize: 11,
            color: 'var(--ink-3)',
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--sage)' }} />
            <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
              {data.succeeded.toLocaleString()}
            </span>{' '}
            succeeded
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--coral)' }} />
            <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
              {data.failed}
            </span>{' '}
            failed
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--amber)' }} />
            <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
              {data.pending}
            </span>{' '}
            pending
          </span>
        </div>
      </div>
    </div>
  );
}

function ClinicianTimelineChartCard({ data }: { data: TimelineBucket[] }) {
  const totalEvents = data.reduce((s, b) => s + b.total, 0);
  const totalFailed = data.reduce((s, b) => s + b.failed, 0);
  const [hover, setHover] = useState<number | null>(null);

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
    <div className="qm-cl-card" style={{ padding: 16 }}>
      <div
        style={{
          marginBottom: 12,
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>Audit events</h2>
          <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>last 24h</span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 11, color: 'var(--ink-3)' }}>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 12, height: 6, borderRadius: 2, background: 'var(--cream-3)' }} /> total{' '}
            <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
              {totalEvents.toLocaleString()}
            </span>
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 12, height: 6, borderRadius: 2, background: 'var(--coral)' }} /> failed{' '}
            <span className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
              {totalFailed}
            </span>
          </span>
        </div>
      </div>
      <div style={{ position: 'relative' }}>
        <svg viewBox={`0 0 ${W} ${H}`} className="block w-full" style={{ height: 120 }} preserveAspectRatio="none">
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
                  <rect
                    x={padL + i * slot}
                    y={padT}
                    width={slot}
                    height={innerH}
                    fill="rgba(122,166,140,0.06)"
                  />
                )}
                <rect
                  x={x}
                  y={yTotal}
                  width={barW}
                  height={totalH}
                  fill={isHover ? '#8A8278' : '#E8E1D3'}
                  rx="1"
                />
                {d.failed > 0 && <rect x={x} y={yFailed} width={barW} height={failedH} fill="#C97B6E" rx="1" />}
              </g>
            );
          })}
          <line
            x1={padL}
            x2={W - padR}
            y1={padT + innerH + 0.5}
            y2={padT + innerH + 0.5}
            stroke="rgba(43, 38, 32, 0.08)"
            strokeWidth="1"
          />
          {xTicks.map((h) => {
            const cx = padL + (h + 0.5) * slot;
            const label = h === 0 ? '12a' : h === 12 ? '12p' : h < 12 ? `${h}a` : `${h - 12}p`;
            return (
              <text
                key={h}
                x={cx}
                y={H - 4}
                fontSize="10"
                fill="#8A8278"
                textAnchor="middle"
                fontFamily="DM Sans, sans-serif"
              >
                {label}
              </text>
            );
          })}
        </svg>
        {hover !== null &&
          (() => {
            const d = data[hover]!;
            const cx = ((padL + (hover + 0.5) * slot) / W) * 100;
            const label =
              d.hour === 0 ? '12am' : d.hour === 12 ? '12pm' : d.hour < 12 ? `${d.hour}am` : `${d.hour - 12}pm`;
            return (
              <div
                style={{
                  pointerEvents: 'none',
                  position: 'absolute',
                  top: -4,
                  left: `${cx}%`,
                  zIndex: 10,
                  transform: 'translate(-50%, -100%)',
                  whiteSpace: 'nowrap',
                  borderRadius: 8,
                  border: '1px solid var(--line)',
                  background: 'var(--cream-card)',
                  padding: '4px 8px',
                  fontSize: 11,
                  boxShadow: 'var(--shadow-card)',
                }}
              >
                <div style={{ fontWeight: 500, color: 'var(--ink-2)' }}>{label}</div>
                <div className="qm-cl-mono" style={{ color: 'var(--ink-2)', fontVariantNumeric: 'tabular-nums' }}>
                  total {d.total}
                  {d.failed > 0 ? <span style={{ color: 'var(--coral-deep)' }}> · {d.failed} failed</span> : null}
                </div>
              </div>
            );
          })()}
      </div>
    </div>
  );
}

function ClinicianHipaaComplianceCard({ data }: { data: HipaaState }) {
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
      className="qm-cl-card qm-cl-lift"
      style={{ display: 'block', padding: 16, textDecoration: 'none', color: 'inherit' }}
    >
      <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ShieldCheck style={{ width: 16, height: 16, color: 'var(--ink-2)' }} />
          <h2 style={{ fontSize: 14, fontWeight: 600, color: 'var(--ink)' }}>HIPAA compliance</h2>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ClinicianHipaaStatusBadge totalOpen={summary.totalOpen} />
          <span style={{ fontSize: 11, color: 'var(--ink-3)' }}>reviewed {data.lastReview}</span>
        </div>
      </div>

      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <li
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
          data-testid="hipaa-row-critical"
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--ink-2)', fontSize: 13 }}>
            <CheckCircle2
              style={{
                width: 16,
                height: 16,
                color: critical.open === 0 ? 'var(--sage-deep)' : 'var(--coral-deep)',
              }}
            />
            <span className="qm-cl-mono" style={{ fontVariantNumeric: 'tabular-nums' }} data-testid="hipaa-critical-total">
              {critical.total}
            </span>{' '}
            critical
            <span style={{ color: 'var(--ink-4)' }}>·</span>
            <span style={{ color: 'var(--ink-3)' }}>
              <span data-testid="hipaa-critical-resolved">{critical.resolved}</span> resolved,{' '}
              <span data-testid="hipaa-critical-pending">{critical.open}</span> pending
            </span>
          </span>
        </li>

        <li data-testid="hipaa-row-high">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--ink-2)', fontSize: 13 }}>
              <span
                style={{
                  display: 'inline-flex',
                  width: 16,
                  height: 16,
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: 999,
                  background: 'var(--amber-tint)',
                  color: 'var(--amber-deep)',
                  fontSize: 10,
                  fontWeight: 700,
                }}
              >
                !
              </span>
              <span
                className="qm-cl-mono"
                style={{ fontVariantNumeric: 'tabular-nums' }}
                data-testid="hipaa-high-total"
              >
                {high.total}
              </span>{' '}
              high
              <span style={{ color: 'var(--ink-4)' }}>·</span>
              <span style={{ color: 'var(--ink-3)' }}>
                <span data-testid="hipaa-high-resolved">{high.resolved}</span> resolved,{' '}
                <span data-testid="hipaa-high-pending">{high.open}</span> pending
              </span>
            </span>
          </div>
          <div
            style={{
              marginTop: 6,
              marginLeft: 24,
              height: 4,
              overflow: 'hidden',
              borderRadius: 999,
              background: 'var(--amber-tint)',
            }}
          >
            <div
              style={{
                height: '100%',
                background: 'var(--amber)',
                width: `${(high.resolved / Math.max(1, high.total)) * 100}%`,
              }}
            />
          </div>
        </li>

        <li
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
          data-testid="hipaa-row-medium"
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--ink-2)', fontSize: 13 }}>
            <span
              style={{
                display: 'inline-flex',
                width: 16,
                height: 16,
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: 999,
                background: 'var(--cream-2)',
                color: 'var(--ink-3)',
                fontSize: 10,
                fontWeight: 700,
              }}
            >
              ·
            </span>
            <span
              className="qm-cl-mono"
              style={{ fontVariantNumeric: 'tabular-nums' }}
              data-testid="hipaa-medium-total"
            >
              {medium.total}
            </span>{' '}
            medium
            <span style={{ color: 'var(--ink-4)' }}>·</span>
            <span style={{ color: 'var(--ink-3)' }}>
              <span data-testid="hipaa-medium-resolved">{medium.resolved}</span> resolved,{' '}
              <span data-testid="hipaa-medium-pending">{medium.open}</span> pending
            </span>
          </span>
        </li>

        <li
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderTop: '1px solid var(--line)',
            paddingTop: 10,
          }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8, color: 'var(--ink-2)', fontSize: 13 }}>
            <Activity style={{ width: 16, height: 16, color: 'var(--sage-deep)' }} />
            Audit coverage{' '}
            <span className="qm-cl-mono" style={{ color: 'var(--ink)', fontVariantNumeric: 'tabular-nums' }}>
              {covPct.toFixed(0)}%
            </span>
            <span style={{ color: 'var(--ink-4)' }}>·</span>
            <span className="qm-cl-mono" style={{ fontSize: 12, color: 'var(--ink-3)' }}>
              {cov.covered}/{cov.total} actions
            </span>
          </span>
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 500, color: 'var(--ink-3)' }}>
            View all <ArrowUpRight style={{ width: 12, height: 12 }} />
          </span>
        </li>
      </ul>
    </Link>
  );
}

function ClinicianHipaaStatusBadge({ totalOpen }: { totalOpen: number }) {
  if (totalOpen === 0) {
    return (
      <span
        data-testid="hipaa-status-badge"
        data-open-count={0}
        className="qm-cl-pill qm-cl-pill-sage"
      >
        <CheckCircle2 style={{ width: 12, height: 12 }} />
        All clear
      </span>
    );
  }
  return (
    <span
      data-testid="hipaa-status-badge"
      data-open-count={totalOpen}
      className="qm-cl-pill qm-cl-pill-amber"
    >
      <AlertTriangle style={{ width: 12, height: 12 }} />
      {totalOpen} open
    </span>
  );
}

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
