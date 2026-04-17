'use client';

// ============================================================================
// MetricsDashboard — system health snapshot for the admin command center
// ----------------------------------------------------------------------------
// Pure presentational client component. All data comes from the server page
// via the `snapshot` prop — we only need `use client` for framer-motion.
// ============================================================================

import { motion } from 'framer-motion';
import {
  Activity,
  Users,
  Globe,
  Shield,
  AlertTriangle,
  Terminal,
  Zap,
  Database,
  Gauge,
  UserCheck,
  TrendingUp,
  Cpu,
  DollarSign,
} from 'lucide-react';

function formatUsd(amount: number): string {
  // 4 decimals under $1 so tiny transcription runs don't vanish into $0.00.
  if (amount < 1) return `$${amount.toFixed(4)}`;
  return `$${amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export interface EndpointLatency {
  path: string;
  p50: number;
  p95: number;
  status: 'healthy' | 'degraded' | 'down';
}

export interface TopConsumer {
  userId: string;
  email: string;
  name: string | null;
  /** Call count in the window (24h). */
  count: number;
  /** Sum of tokens — relevant for DOC_EDITOR rollups, null otherwise. */
  tokens: number | null;
  /** Sum of audio seconds — relevant for TRANSCRIBE rollups, null otherwise. */
  durationSeconds: number | null;
  /** USD estimate computed at read time from the sums above + count fallback. */
  costUsd: number;
}

/** Per-feature cost breakdown row. Aggregated from apiUsage grouped by
 *  `feature` — no assumption about which features exist; the page learns
 *  them from the data. */
export interface FeatureCostRow {
  feature: string;
  count: number;
  tokens: number | null;
  durationSeconds: number | null;
  costUsd: number;
}

export interface MetricsSnapshot {
  totalUsers: number;
  activeUsers: number;
  adminUsers: number;
  activeSessions: number;
  sessions24h: number;
  auditEvents24h: number;
  failedLogins24h: number;
  apiCalls24h: number;
  /** Total estimated spend across all features in the 24h window (USD). */
  estimatedCost24hUsd: number;
  /** Cost + volume broken down by feature, sorted by cost desc. */
  featureBreakdown: FeatureCostRow[];
  topConsumers: TopConsumer[];
  endpoints: EndpointLatency[];
  dbHealthy: boolean;
}

type StatAccent = 'cyan' | 'emerald' | 'violet' | 'orange' | 'amber' | 'rose';

const ACCENT: Record<StatAccent, { text: string; bg: string; border: string }> = {
  cyan: { text: 'text-cyan-400', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30' },
  emerald: { text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' },
  violet: { text: 'text-violet-400', bg: 'bg-violet-500/10', border: 'border-violet-500/30' },
  orange: { text: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/30' },
  amber: { text: 'text-amber-300', bg: 'bg-amber-500/10', border: 'border-amber-500/30' },
  rose: { text: 'text-rose-400', bg: 'bg-rose-500/10', border: 'border-rose-500/30' },
};

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  accent,
  delay = 0,
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: React.ComponentType<{ className?: string }>;
  accent: StatAccent;
  delay?: number;
}) {
  const a = ACCENT[accent];
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-4"
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono text-slate-500 uppercase tracking-wider">
          {label}
        </span>
        <div className={`p-1.5 rounded-md ${a.bg} border ${a.border}`}>
          <Icon className={`w-3.5 h-3.5 ${a.text}`} />
        </div>
      </div>
      <p className={`text-2xl font-bold font-mono ${a.text}`}>{value}</p>
      {sub && (
        <p className="text-[10px] font-mono text-slate-600 mt-1">{sub}</p>
      )}
    </motion.div>
  );
}

function latencyColor(ms: number): string {
  if (ms < 150) return 'text-emerald-400';
  if (ms < 300) return 'text-amber-300';
  return 'text-rose-400';
}

function statusPill(status: EndpointLatency['status']): {
  label: string;
  className: string;
} {
  switch (status) {
    case 'healthy':
      return {
        label: 'HEALTHY',
        className: 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300',
      };
    case 'degraded':
      return {
        label: 'DEGRADED',
        className: 'bg-amber-500/10 border-amber-500/30 text-amber-300',
      };
    case 'down':
      return {
        label: 'DOWN',
        className: 'bg-rose-500/10 border-rose-500/30 text-rose-300',
      };
  }
}

export default function MetricsDashboard({
  snapshot,
}: {
  snapshot: MetricsSnapshot;
}) {
  const avgP50 =
    snapshot.endpoints.length === 0
      ? 0
      : Math.round(
          snapshot.endpoints.reduce((a, e) => a + e.p50, 0) /
            snapshot.endpoints.length
        );

  return (
    <div className="min-h-screen bg-[#0a0e17] text-slate-200">
      {/* Grid overlay */}
      <div
        className="fixed inset-0 pointer-events-none z-0 opacity-[0.03]"
        style={{
          backgroundImage:
            'linear-gradient(rgba(255,255,255,.1) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.1) 1px,transparent 1px)',
          backgroundSize: '40px 40px',
        }}
      />

      <div className="relative z-10 mx-auto max-w-7xl px-6 py-8">
        {/* Top bar */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-orange-500/10 border border-orange-500/30">
              <Terminal className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">
                System Metrics
              </h1>
              <p className="text-[11px] text-slate-500 font-mono">
                /system-admin/metrics &mdash; health snapshot
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <div
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${
                snapshot.dbHealthy
                  ? 'bg-emerald-500/10 border-emerald-500/30'
                  : 'bg-amber-500/10 border-amber-500/30'
              }`}
            >
              <Database
                className={`w-3 h-3 ${
                  snapshot.dbHealthy ? 'text-emerald-400' : 'text-amber-300'
                }`}
              />
              <span
                className={`text-[10px] font-mono ${
                  snapshot.dbHealthy ? 'text-emerald-300' : 'text-amber-300'
                }`}
              >
                {snapshot.dbHealthy ? 'DB CONNECTED' : 'DB OFFLINE (MOCK)'}
              </span>
            </div>
            <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              <span className="text-[10px] font-mono text-slate-400">
                SYSTEM ONLINE
              </span>
            </div>
          </div>
        </div>

        {/* User + session stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
          <StatCard
            label="Total Users"
            value={snapshot.totalUsers}
            sub={`${snapshot.adminUsers} admin`}
            icon={Users}
            accent="cyan"
            delay={0}
          />
          <StatCard
            label="Active Users"
            value={snapshot.activeUsers}
            sub={`${snapshot.totalUsers - snapshot.activeUsers} deactivated`}
            icon={UserCheck}
            accent="emerald"
            delay={0.04}
          />
          <StatCard
            label="Active Sessions"
            value={snapshot.activeSessions}
            sub="last 30 min"
            icon={Globe}
            accent="violet"
            delay={0.08}
          />
          <StatCard
            label="Logins · 24h"
            value={snapshot.sessions24h}
            sub="all users"
            icon={Zap}
            accent="orange"
            delay={0.12}
          />
        </div>

        {/* Compliance + latency + cost quick stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
          <StatCard
            label="Est. Cost · 24h"
            value={formatUsd(snapshot.estimatedCost24hUsd)}
            sub="All OpenAI features"
            icon={DollarSign}
            accent="emerald"
            delay={0.14}
          />
          <StatCard
            label="API Calls · 24h"
            value={snapshot.apiCalls24h}
            sub="authenticated hits"
            icon={Cpu}
            accent="cyan"
            delay={0.16}
          />
          <StatCard
            label="Audit Events · 24h"
            value={snapshot.auditEvents24h}
            sub="HIPAA §164.312(b)"
            icon={Shield}
            accent="amber"
            delay={0.2}
          />
          <StatCard
            label="Failed Logins · 24h"
            value={snapshot.failedLogins24h}
            sub={
              snapshot.failedLogins24h > 10 ? 'elevated — review' : 'within baseline'
            }
            icon={AlertTriangle}
            accent={snapshot.failedLogins24h > 10 ? 'rose' : 'emerald'}
            delay={0.24}
          />
          <StatCard
            label="Avg API p50"
            value={`${avgP50}ms`}
            sub="mocked · replace with probe"
            icon={Gauge}
            accent={avgP50 < 150 ? 'emerald' : avgP50 < 300 ? 'amber' : 'rose'}
            delay={0.28}
          />
        </div>

        {/* Cost breakdown by feature — where is the $$ actually going?
            Sorted descending by cost; unpriced / $0 features still listed
            so admins see the full surface. */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="rounded-xl bg-white/[0.02] border border-white/[0.06] overflow-hidden mb-6"
        >
          <div className="flex items-center gap-2 px-5 py-3 border-b border-white/[0.06]">
            <DollarSign className="w-4 h-4 text-emerald-400" />
            <h2 className="text-xs font-mono font-semibold text-white uppercase tracking-widest">
              Cost Breakdown · 24h
            </h2>
            <span className="ml-auto text-[10px] font-mono text-slate-500">
              grouped by feature
            </span>
          </div>
          {snapshot.featureBreakdown.length === 0 ? (
            <div className="px-5 py-6 text-center text-xs font-mono text-slate-500">
              No API activity in the last 24h.
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {snapshot.featureBreakdown.map((row) => {
                const usageStr =
                  row.durationSeconds != null && row.durationSeconds > 0
                    ? `${Math.round(row.durationSeconds / 60)} min`
                    : row.tokens != null && row.tokens > 0
                      ? `${row.tokens.toLocaleString()} units`
                      : `${row.count} calls`;
                return (
                  <div
                    key={row.feature}
                    className="flex items-center gap-3 px-5 py-2.5"
                  >
                    <span className="text-[11px] font-mono text-slate-300 min-w-[140px] truncate">
                      {row.feature}
                    </span>
                    <span className="text-[11px] text-slate-500 flex-1">
                      {row.count} calls · {usageStr}
                    </span>
                    <span className="text-sm font-mono font-semibold text-emerald-300 min-w-[72px] text-right">
                      {formatUsd(row.costUsd)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </motion.div>

        {/* Top API Consumers */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.32 }}
          className="rounded-xl bg-white/[0.02] border border-white/[0.06] overflow-hidden mb-6"
        >
          <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyan-400" />
              <h2 className="text-xs font-mono font-semibold text-white uppercase tracking-widest">
                Top Transcription Users · 24h
              </h2>
            </div>
            <span className="text-[10px] font-mono text-slate-600">
              top {snapshot.topConsumers.length} by call count
            </span>
          </div>

          {snapshot.topConsumers.length === 0 ? (
            <div className="py-12 text-center">
              <Cpu className="w-8 h-8 text-slate-700 mx-auto mb-3" />
              <p className="text-sm text-slate-600 font-mono">
                No API usage recorded in the last 24h
              </p>
            </div>
          ) : (
            <div className="divide-y divide-white/[0.04]">
              {(() => {
                const maxCount = Math.max(
                  ...snapshot.topConsumers.map((c) => c.count),
                  1
                );
                return snapshot.topConsumers.map((c, i) => {
                  const pct = Math.round((c.count / maxCount) * 100);
                  return (
                    <div
                      key={c.userId}
                      className="grid grid-cols-12 gap-3 px-5 py-3 items-center hover:bg-white/[0.02] transition-colors"
                    >
                      {/* Rank */}
                      <div className="col-span-1 flex items-center">
                        <span className="text-[10px] font-mono font-bold text-slate-600">
                          #{i + 1}
                        </span>
                      </div>

                      {/* User */}
                      <div className="col-span-4 flex items-center gap-2 min-w-0">
                        <div className="w-6 h-6 rounded-md bg-gradient-to-br from-cyan-500/20 to-violet-500/20 border border-white/[0.06] flex items-center justify-center shrink-0">
                          <span className="text-[9px] font-bold text-white font-mono">
                            {(c.name ?? c.email)[0]?.toUpperCase() ?? '?'}
                          </span>
                        </div>
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-white truncate">
                            {c.name ?? c.email.split('@')[0]}
                          </p>
                          <p className="text-[10px] font-mono text-slate-500 truncate">
                            {c.email}
                          </p>
                        </div>
                      </div>

                      {/* Bar */}
                      <div className="col-span-4 h-2 rounded-full bg-white/[0.04] overflow-hidden">
                        <motion.div
                          initial={{ width: 0 }}
                          animate={{ width: `${pct}%` }}
                          transition={{ delay: 0.4 + i * 0.05, duration: 0.6 }}
                          className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-violet-500"
                        />
                      </div>

                      {/* Count */}
                      <div className="col-span-2 text-right">
                        <span className="text-xs font-mono font-bold text-cyan-300">
                          {c.count.toLocaleString()}
                        </span>
                        <span className="text-[10px] font-mono text-slate-600 ml-1">
                          calls
                        </span>
                      </div>

                      {/* Est. cost */}
                      <div className="col-span-1 text-right">
                        <span className="text-[10px] font-mono text-emerald-300">
                          {formatUsd(c.costUsd)}
                        </span>
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
          )}

          <div className="px-5 py-3 border-t border-white/[0.06] flex items-center justify-between">
            <p className="text-[10px] font-mono text-slate-600">
              Source: api_usage where feature=TRANSCRIBE · grouped by user, 24h
            </p>
            <p className="text-[10px] font-mono text-slate-600 italic">
              cost = duration × $0.006/min (estimate; rates may change)
            </p>
          </div>
        </motion.div>

        {/* Latency table */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.28 }}
          className="rounded-xl bg-white/[0.02] border border-white/[0.06] overflow-hidden"
        >
          <div className="flex items-center justify-between px-5 py-3 border-b border-white/[0.06]">
            <div className="flex items-center gap-2">
              <Activity className="w-4 h-4 text-orange-400" />
              <h2 className="text-xs font-mono font-semibold text-white uppercase tracking-widest">
                API Latency
              </h2>
            </div>
            <span className="text-[10px] font-mono text-slate-600">
              mocked · {snapshot.endpoints.length} endpoints
            </span>
          </div>

          <div className="hidden md:grid grid-cols-12 gap-3 px-5 py-3 border-b border-white/[0.06] text-[9px] font-mono text-slate-600 uppercase tracking-widest">
            <div className="col-span-6">Endpoint</div>
            <div className="col-span-2 text-right">p50</div>
            <div className="col-span-2 text-right">p95</div>
            <div className="col-span-2 text-center">Status</div>
          </div>

          <div className="divide-y divide-white/[0.04]">
            {snapshot.endpoints.map((ep) => {
              const pill = statusPill(ep.status);
              return (
                <div
                  key={ep.path}
                  className="grid grid-cols-1 md:grid-cols-12 gap-2 md:gap-3 px-5 py-3 hover:bg-white/[0.02] transition-colors"
                >
                  <div className="md:col-span-6 flex items-center gap-2">
                    <span className="text-xs font-mono text-slate-300 truncate">
                      {ep.path}
                    </span>
                  </div>
                  <div
                    className={`md:col-span-2 text-right text-xs font-mono ${latencyColor(
                      ep.p50
                    )}`}
                  >
                    {ep.p50}ms
                  </div>
                  <div
                    className={`md:col-span-2 text-right text-xs font-mono ${latencyColor(
                      ep.p95
                    )}`}
                  >
                    {ep.p95}ms
                  </div>
                  <div className="md:col-span-2 flex items-center justify-center">
                    <span
                      className={`inline-flex items-center px-2 py-0.5 rounded border text-[9px] font-mono font-bold ${pill.className}`}
                    >
                      {pill.label}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>

          <div className="px-5 py-3 border-t border-white/[0.06] flex items-center justify-between">
            <p className="text-[10px] font-mono text-slate-600">
              Snapshot rendered server-side · refresh page for latest
            </p>
            <p className="text-[10px] font-mono text-slate-600 italic">
              latency values are placeholders until a probe pipeline is wired up
            </p>
          </div>
        </motion.div>
      </div>
    </div>
  );
}
