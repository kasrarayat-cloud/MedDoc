// ============================================================================
// Shared formatting helpers for the admin pages
// ----------------------------------------------------------------------------
// Framework-agnostic (no `server-only` directive) so both server components
// and `'use client'` components can import the same module. Every helper is
// pure — given the same input it always returns the same output, no I/O.
// ============================================================================

/** Stable, palette-rotated avatar background derived from a string id. */
export function avatarPalette(id: string): { bg: string; text: string; ring: string } {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  const ps = [
    { bg: 'bg-slate-100', text: 'text-slate-700', ring: 'ring-slate-200' },
    { bg: 'bg-stone-100', text: 'text-stone-700', ring: 'ring-stone-200' },
    { bg: 'bg-zinc-100', text: 'text-zinc-700', ring: 'ring-zinc-200' },
    { bg: 'bg-blue-50', text: 'text-blue-800', ring: 'ring-blue-100' },
    { bg: 'bg-teal-50', text: 'text-teal-800', ring: 'ring-teal-100' },
    { bg: 'bg-violet-50', text: 'text-violet-800', ring: 'ring-violet-100' },
    { bg: 'bg-amber-50', text: 'text-amber-800', ring: 'ring-amber-100' },
  ];
  return ps[Math.abs(h) % ps.length]!;
}

/** Smaller-context palette (used in the TopUsers list — no ring needed). */
export function avatarPaletteSm(id: string): { bg: string; text: string } {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  const ps = [
    { bg: 'bg-slate-100', text: 'text-slate-700' },
    { bg: 'bg-blue-50', text: 'text-blue-800' },
    { bg: 'bg-teal-50', text: 'text-teal-800' },
    { bg: 'bg-violet-50', text: 'text-violet-800' },
    { bg: 'bg-amber-50', text: 'text-amber-800' },
  ];
  return ps[Math.abs(h) % ps.length]!;
}

/** "Dr. John Smith" → "JS". Empty → "·". */
export function initials(name: string): string {
  const p = name
    .replace(/^Dr\.?\s+/i, '')
    .trim()
    .split(/\s+/);
  return ((p[0]?.[0] || '') + (p[1]?.[0] || '')).toUpperCase() || '·';
}

/** Alias kept for legibility at TopUsers call sites; same logic. */
export const userInitials = initials;

/** "$0.00" form. Returns the em-dash for zero. */
export function formatUsd(n: number): string {
  return n === 0 ? '—' : `$${n.toFixed(2)}`;
}

/** Locale-grouped USD with caller-controlled fraction digits (2 by default). */
export function formatUsd2(n: number, dec = 2): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: dec, maximumFractionDigits: dec })}`;
}

/** Compact count: 1.2M / 12.3k / 87. */
export function formatCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/** Compact count with the M variant carrying two fraction digits — used in
 *  the usage page where token counts read better as "47.30M". */
export function formatCount2(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return String(n);
}

/** "now" / "12m ago" / "3h ago" / "5d ago" / "2mo ago". */
export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return '—';
  const diff = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (diff < 60) return 'now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  const days = Math.floor(diff / 86400);
  if (days < 30) return `${days}d ago`;
  return `${Math.floor(days / 30)}mo ago`;
}

/** Whole days from `iso` to now. */
export function daysSince(iso: string): number {
  return Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
}

/** Format a YYYY-MM-DD bucket for chart x-axis labels — "Apr 25". */
export function formatDay(yyyymmdd: string): string {
  const d = new Date(`${yyyymmdd}T00:00:00Z`);
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', timeZone: 'UTC' });
}

/** Provider display labels — single source of truth. */
export const PROVIDER_LABEL: Record<string, string> = {
  deepgram: 'Deepgram',
  anthropic: 'Anthropic',
  whisper: 'Whisper',
  openai: 'OpenAI',
  resend: 'Resend',
};

/** Provider visual palette for stacked-area charts and breakdown bars. */
export const PROVIDER_COLOR: Record<
  string,
  { fill: string; stroke: string; chip: string }
> = {
  deepgram: { fill: '#14b8a6', stroke: '#0d9488', chip: 'bg-teal-500' },
  anthropic: { fill: '#8b5cf6', stroke: '#7c3aed', chip: 'bg-violet-500' },
  whisper: { fill: '#f59e0b', stroke: '#d97706', chip: 'bg-amber-500' },
  openai: { fill: '#10b981', stroke: '#059669', chip: 'bg-emerald-500' },
  resend: { fill: '#94a3b8', stroke: '#64748b', chip: 'bg-slate-400' },
};

/** Stable provider order for charts + bars. */
export const PROVIDER_ORDER = [
  'deepgram',
  'anthropic',
  'whisper',
  'openai',
  'resend',
] as const;

/** Window-key labels used in the API Usage page header + selector. */
export const WINDOW_LABELS: Record<string, string> = {
  '24h': 'Last 24 hours',
  '7d': 'Last 7 days',
  '30d': 'Last 30 days',
  month: 'This month',
};

/** Generic class joiner; mirrors clsx without the dep. */
export function cls(...a: (string | false | null | undefined)[]): string {
  return a.filter(Boolean).join(' ');
}

/** Best-effort unit label per provider — used in monthSpend rollups
 *  where the row only has a totalCostUsd and we synthesise a unit
 *  string for the drawer's per-provider breakdown. */
export function defaultUnitLabel(provider: string): string {
  if (provider === 'deepgram' || provider === 'whisper') return 'min';
  if (provider === 'anthropic' || provider === 'openai') return 'tokens';
  if (provider === 'resend') return 'emails';
  return '';
}

// ---------------------------------------------------------------------------
// HIPAA findings — single source of truth for the per-card derivations
// ----------------------------------------------------------------------------
// Phase 7A consistency sweep. The HIPAA card had a real drift bug: the
// status badge derived "Clear" from `critical.total === 0` while the
// per-severity rows below showed 3 pending high-severity issues. Anyone
// glancing at the card saw a green check + "Clear" and thought they
// were done.
//
// Centralising the derivation here means BOTH the header badge AND every
// per-severity row read the same numbers. A future Option-β swap (real
// findings table replacing the hardcoded list in dashboard-data.ts
// :getHipaaState) flows through here without touching the consumers.
// ---------------------------------------------------------------------------

import type { HipaaFinding } from '../_types';

export interface HipaaFindingsSummary {
  /** total findings across all severities (open + resolved). */
  totalCount: number;
  /** total open findings — i.e. (total - resolved) summed across severities.
   *  This is the number that drives "All clear" vs "N open" on the header. */
  totalOpen: number;
  /** total resolved findings, summed across severities. */
  totalResolved: number;
  /** per-severity breakdown with the same open/resolved math applied,
   *  so the chart rows can read from this object instead of recomputing. */
  bySeverity: Record<HipaaFinding['severity'], { total: number; open: number; resolved: number }>;
}

export function summarizeHipaaFindings(findings: HipaaFinding[]): HipaaFindingsSummary {
  const bySeverity: HipaaFindingsSummary['bySeverity'] = {
    critical: { total: 0, open: 0, resolved: 0 },
    high: { total: 0, open: 0, resolved: 0 },
    medium: { total: 0, open: 0, resolved: 0 },
  };
  let totalCount = 0;
  let totalOpen = 0;
  let totalResolved = 0;
  for (const f of findings) {
    const open = Math.max(0, f.total - f.resolved);
    bySeverity[f.severity] = { total: f.total, open, resolved: f.resolved };
    totalCount += f.total;
    totalOpen += open;
    totalResolved += f.resolved;
  }
  return { totalCount, totalOpen, totalResolved, bySeverity };
}
