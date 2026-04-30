'use client';

// ============================================================================
// Phase 3 Wave 2 (dashboard density) — Greeting line at the top of the
// Clinician dashboard.
// ----------------------------------------------------------------------------
// Renders the mockup's "Good morning, Dr. {firstName}." line where
// "morning" / "afternoon" / "evening" picks up the viewer's local hour.
// Above the heading sits an eyebrow row carrying the local date.
//
// Client component on purpose: deriving the hour from `new Date()` on
// the server would render against the Node container's timezone, not
// the doctor's, so a Tehran-evening user might see "Good morning"
// after midnight UTC. We pre-render a neutral "Hello" SSR fallback
// (zero hydration mismatch) and swap to the time-of-day variant once
// the client mounts.
//
// The italic accent on the time-of-day word matches the dashboard
// mockup (docs/design-directions-v3/clinician/dashboard.html L489–495)
// where "morning." sits in a sage-deep span. We use Source Serif italic
// via inline `fontStyle: 'italic'` to keep the typographic intent
// without inventing a new utility class.
//
// Subtitle slot is optional — the page wires in the live "11 visits ·
// 3 drafts waiting" copy from the same data the cards downstream will
// render. We keep it as React children so the page can pass JSX with
// sage-deep accents inline (the mockup paints a couple of phrases in
// sage-deep within the subtitle paragraph).
// ============================================================================

import { useEffect, useState, type ReactNode } from 'react';

interface GreetingProps {
  /** First name of the signed-in clinician — typically `session.user.name`
   *  split on whitespace. Pass null/empty to render "Hello, doctor." as
   *  a polite anonymous fallback. */
  firstName: string | null;
  /** Optional subtitle paragraph rendered under the heading. Passed as
   *  React children so callers can inline `<span>` accents without the
   *  Greeting component having to know about the data. */
  subtitle?: ReactNode;
}

type TimeOfDay = 'morning' | 'afternoon' | 'evening';

function timeOfDayFromHour(hour: number): TimeOfDay {
  // Mockup convention: morning < 12, afternoon < 18, otherwise evening.
  // Includes a small grace at the boundaries (11:55 still reads
  // "morning") because rounding the boundary to the minute would feel
  // arbitrary. Doctors don't use the dashboard as a clock.
  if (hour < 12) return 'morning';
  if (hour < 18) return 'afternoon';
  return 'evening';
}

/** "Wednesday, April 29 · Spring" — eyebrow line above the heading.
 *  Matches the mockup's date format (docs/.../dashboard.html L488).
 *  The "season" is a small touch from the same line; we derive it from
 *  the local month so northern-hemisphere readings land naturally for
 *  the launch market. */
function formatEyebrow(now: Date): string {
  const dow = now.toLocaleDateString(undefined, { weekday: 'long' });
  const month = now.toLocaleDateString(undefined, { month: 'long' });
  const day = now.getDate();
  const m = now.getMonth(); // 0–11
  let season = 'Spring';
  if (m === 11 || m === 0 || m === 1) season = 'Winter';
  else if (m >= 2 && m <= 4) season = 'Spring';
  else if (m >= 5 && m <= 7) season = 'Summer';
  else if (m >= 8 && m <= 10) season = 'Autumn';
  return `${dow}, ${month} ${day} · ${season}`;
}

export function Greeting({ firstName, subtitle }: GreetingProps) {
  // SSR + first paint: render the static neutral "Hello" variant so
  // hydration matches and there's no flicker. After mount we re-render
  // with the viewer's local time-of-day + date eyebrow.
  const [hydrated, setHydrated] = useState(false);
  const [tod, setTod] = useState<TimeOfDay>('morning');
  const [eyebrow, setEyebrow] = useState<string | null>(null);

  useEffect(() => {
    const now = new Date();
    setTod(timeOfDayFromHour(now.getHours()));
    setEyebrow(formatEyebrow(now));
    setHydrated(true);
  }, []);

  const namePart = firstName ? `Dr. ${firstName}` : 'doctor';
  const headingPrefix = hydrated ? `Good ` : 'Hello';
  const headingTail = hydrated ? '' : '';

  return (
    <div style={{ marginBottom: 28 }}>
      {hydrated && eyebrow ? (
        <div className="qm-cl-eyebrow" style={{ marginBottom: 10 }}>
          {eyebrow}
        </div>
      ) : (
        // Reserve the vertical space pre-hydration so the heading
        // doesn't jump down once the eyebrow paints. 19px ≈ the
        // computed height of the eyebrow line + its 10px margin.
        <div style={{ height: 26, marginBottom: 0 }} aria-hidden />
      )}
      <h1
        className="qm-cl-serif"
        style={{
          margin: 0,
          fontSize: 42,
          fontWeight: 400,
          letterSpacing: '-0.015em',
          lineHeight: 1.15,
          color: 'var(--ink)',
        }}
      >
        {hydrated ? (
          <>
            {headingPrefix}
            <em
              style={{
                fontStyle: 'italic',
                color: 'var(--sage-deep)',
                fontWeight: 400,
              }}
            >
              {tod}
            </em>
            {`, ${namePart}.`}
          </>
        ) : (
          <>{`Hello, ${namePart}.`}</>
        )}
        {headingTail}
      </h1>
      {subtitle && (
        <p
          className="qm-cl-serif"
          style={{
            margin: '10px 0 0',
            fontSize: 17,
            color: 'var(--ink-2)',
            maxWidth: 560,
            lineHeight: 1.55,
          }}
        >
          {subtitle}
        </p>
      )}
    </div>
  );
}
