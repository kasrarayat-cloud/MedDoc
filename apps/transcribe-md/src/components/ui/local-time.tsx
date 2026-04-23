'use client';

// ============================================================================
// Client-side timestamp renderers.
// ----------------------------------------------------------------------------
// Drop-in replacement for raw timestamp rendering inside server
// components. Each variant defers formatting to the client so the
// viewer's browser timezone — not the Node container's TZ — wins.
//
// Uses useSyncExternalStore so React handles hydration cleanly:
//   getServerSnapshot() → placeholder '\u00A0' on the server.
//   getSnapshot()       → locale-formatted string on the client.
//
// The <time dateTime={iso}> wrapper carries machine-readable UTC for
// screen readers + copy-paste while the rendered text stays local.
// ============================================================================

import { useSyncExternalStore } from 'react';

import {
  formatLocalDate,
  formatLocalDateTime,
  formatLocalTime,
  formatLocalTimeWithDay,
  formatRelativeTime,
} from '@/lib/format-time';

type Variant = 'time' | 'timeWithDay' | 'date' | 'dateTime' | 'relative';

const FORMATTERS: Record<Variant, (iso: string) => string> = {
  time: formatLocalTime,
  timeWithDay: formatLocalTimeWithDay,
  date: formatLocalDate,
  dateTime: formatLocalDateTime,
  relative: formatRelativeTime,
};

// TZ doesn't flip during a session (other than rare OS-level changes
// we don't need to track), so the subscribe fn is a no-op: react will
// read the snapshot each render and compare values.
const noopSubscribe: () => () => void = () => () => {};

interface Props {
  /** ISO 8601 UTC string (e.g. "2026-04-23T08:41:00.000Z") or
   *  `null`/`undefined` for "no value" — renders nothing. */
  iso: string | null | undefined;
  variant?: Variant;
  /** Shown during SSR and before the client hydrates. */
  placeholder?: string;
}

export function LocalTime({
  iso,
  variant = 'time',
  placeholder = '\u00A0',
}: Props) {
  const text = useSyncExternalStore(
    noopSubscribe,
    () => (iso ? FORMATTERS[variant](iso) : ''),
    () => placeholder
  );

  if (!iso) return null;
  return (
    <time dateTime={iso} suppressHydrationWarning>
      {text}
    </time>
  );
}
