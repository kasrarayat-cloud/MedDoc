'use client';

// ============================================================================
// Phase 5 — Linear V1 Faithful greeting line.
// ----------------------------------------------------------------------------
// Reference: docs/design-directions-v8-linear/dashboard-v1.html (.greet)
//
// One status sentence at the top of the dashboard, in the same Linear-
// row vocabulary as the rest of the chrome:
//
//   Wednesday, April 30 · 11 to review · 3 drafts ready · 2:47 PM
//
// The full-height Source Serif heading + photo crossfade greeting from
// Phases 3-4 are gone. Pure typographic line on the dark canvas, with
// mono accent fragments for counts + time.
//
// Client component on purpose: the date + clock are local-time
// derived, so the SSR pass renders a neutral fallback and the client
// pass swaps in the time-of-day variant once mounted. This avoids a
// hydration mismatch when the server's TZ differs from the viewer's.
// ============================================================================

import { useEffect, useState, type ReactNode } from 'react';

interface GreetingProps {
  /** First name of the signed-in clinician. Pass null for the polite
   *  anonymous fallback ("Hello, doctor."). */
  firstName: string | null;
  /** Optional subtitle slot rendered after the greeting fragments. */
  subtitle?: ReactNode;
}

type TimeOfDay = 'morning' | 'afternoon' | 'evening';

function timeOfDayFromHour(hour: number): TimeOfDay {
  if (hour < 12) return 'morning';
  if (hour < 18) return 'afternoon';
  return 'evening';
}

/** "Wednesday, April 30" — local long-form date. */
function formatDate(now: Date): string {
  const dow = now.toLocaleDateString(undefined, { weekday: 'long' });
  const month = now.toLocaleDateString(undefined, { month: 'long' });
  const day = now.getDate();
  return `${dow}, ${month} ${day}`;
}

/** "2:47 PM" — local time without seconds. */
function formatClock(now: Date): string {
  return now.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  });
}

export function Greeting({ firstName, subtitle }: GreetingProps) {
  // SSR + first paint: render a stable "Hello, Dr. X" line so hydration
  // matches and there's no flicker. After mount we re-render with the
  // viewer's local time-of-day, date, and clock.
  const [hydrated, setHydrated] = useState(false);
  const [tod, setTod] = useState<TimeOfDay>('morning');
  const [date, setDate] = useState<string | null>(null);
  const [clock, setClock] = useState<string | null>(null);

  useEffect(() => {
    const now = new Date();
    setTod(timeOfDayFromHour(now.getHours()));
    setDate(formatDate(now));
    setClock(formatClock(now));
    setHydrated(true);
  }, []);

  const namePart = firstName ? `Dr. ${firstName}` : 'doctor';
  const headingLeft = hydrated
    ? `Good ${tod}, ${namePart}.`
    : `Hello, ${namePart}.`;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        flexWrap: 'wrap',
        fontFamily: 'var(--font-sans)',
        fontSize: 13,
        color: 'var(--color-linear-text-2)',
        marginBottom: 18,
        letterSpacing: '-0.005em',
      }}
    >
      <span
        style={{
          color: 'var(--color-linear-text)',
          fontWeight: 500,
        }}
      >
        {headingLeft}
      </span>
      {subtitle && (
        <>
          <span style={{ color: 'var(--color-linear-text-3)' }}>·</span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--color-linear-text-2)',
            }}
          >
            {subtitle}
          </span>
        </>
      )}
      {hydrated && date && (
        <>
          <span style={{ color: 'var(--color-linear-text-3)' }}>·</span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--color-linear-text-2)',
            }}
          >
            {date}
          </span>
        </>
      )}
      {hydrated && clock && (
        <>
          <span style={{ color: 'var(--color-linear-text-3)' }}>·</span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 12,
              color: 'var(--color-linear-text-2)',
            }}
          >
            {clock}
          </span>
        </>
      )}
    </div>
  );
}
