// ============================================================================
// Timezone-safe date + time formatters.
// ----------------------------------------------------------------------------
// Timestamps in this codebase live as Postgres `Timestamptz(6)` values —
// stored in UTC, returned through Prisma as JS `Date` objects, and
// serialised to ISO 8601 strings (e.g. "2026-04-23T08:41:00.000Z") on
// the wire. UI rendering must land in the viewer's browser timezone:
// a physician in Tehran should see 12:11 while a physician in LA sees
// 01:41 for the same row.
//
// These helpers are intentionally pure and SSR-safe: they work the
// same in any environment, but their OUTPUT depends on where they
// run. Callers should invoke them CLIENT-SIDE (inside 'use client'
// components) so the user's browser timezone — not the Node container
// timezone — drives the formatted output.
//
// Accepts `string | Date | null | undefined` and returns `''` for any
// missing/unparseable input so UI code can spread them without guards.
// ============================================================================

type DateInput = string | Date | null | undefined;

function toDate(input: DateInput): Date | null {
  if (input == null) return null;
  const d = input instanceof Date ? input : new Date(input);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** 24-hour HH:MM in the viewer's local timezone. */
export function formatLocalTime(input: DateInput): string {
  const d = toDate(input);
  if (!d) return '';
  return d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

/** "Mon 14:20" — abbreviated weekday + 24-hour HH:MM in local TZ. */
export function formatLocalTimeWithDay(input: DateInput): string {
  const d = toDate(input);
  if (!d) return '';
  const dow = d.toLocaleDateString(undefined, { weekday: 'short' });
  const hm = d.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  return `${dow} ${hm}`;
}

/** "Apr 23, 2026" by default; pass `opts` for other formats. */
export function formatLocalDate(
  input: DateInput,
  opts: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }
): string {
  const d = toDate(input);
  if (!d) return '';
  return d.toLocaleDateString(undefined, opts);
}

/** "Apr 23, 2026, 14:30" — medium date + 24h time in local TZ. */
export function formatLocalDateTime(input: DateInput): string {
  const d = toDate(input);
  if (!d) return '';
  return `${formatLocalDate(d)}, ${formatLocalTime(d)}`;
}

/** "just now" / "5m ago" / "2h ago" / "yesterday" / "3d ago" / "2w ago"
 *  / "Apr 14". The unit breakdown is TZ-independent (walltime millis);
 *  the final month/day fallback picks up local TZ for the date. */
export function formatRelativeTime(input: DateInput): string {
  const d = toDate(input);
  if (!d) return '';
  const diffMs = Date.now() - d.getTime();
  const diffMin = diffMs / 60_000;
  if (diffMin < 1) return 'just now';
  if (diffMin < 60) return `${Math.round(diffMin)}m ago`;
  const diffH = diffMin / 60;
  if (diffH < 24) return `${Math.round(diffH)}h ago`;
  if (diffH < 48) return 'yesterday';
  const diffD = diffH / 24;
  if (diffD < 7) return `${Math.round(diffD)}d ago`;
  if (diffD < 30) return `${Math.round(diffD / 7)}w ago`;
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/** Start of the viewer's local day (00:00:00.000). */
export function startOfLocalDay(d: Date = new Date()): Date {
  const c = new Date(d);
  c.setHours(0, 0, 0, 0);
  return c;
}

/** Start of the viewer's local week (Monday 00:00). Follows ISO 8601
 *  (week starts Monday) since that matches the handoff's grouping
 *  examples and is consistent across en-US / non-en-US locales. */
export function startOfLocalWeek(d: Date = new Date()): Date {
  const c = startOfLocalDay(d);
  const dow = c.getDay(); // 0 = Sunday, 1 = Monday, …, 6 = Saturday
  const diff = dow === 0 ? -6 : 1 - dow;
  c.setDate(c.getDate() + diff);
  return c;
}

/** Bucket ID for the grouped visit list. All comparisons happen in
 *  LOCAL time so a visit at 23:30 UTC on April 23 sits in "Today" for
 *  a viewer in Los Angeles (April 23 16:30 local) and in "Yesterday"
 *  for a viewer in Tehran (April 24 03:00 local). */
export type DayBucket = 'Today' | 'Yesterday' | 'This week' | 'Earlier';

export function bucketForLocalDay(input: DateInput): DayBucket | null {
  const d = toDate(input);
  if (!d) return null;
  const today = startOfLocalDay();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  const weekStart = startOfLocalWeek();
  if (d >= today) return 'Today';
  if (d >= yesterday) return 'Yesterday';
  if (d >= weekStart) return 'This week';
  return 'Earlier';
}
