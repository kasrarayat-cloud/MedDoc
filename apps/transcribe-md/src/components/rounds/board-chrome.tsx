// ============================================================================
// ROUNDS — the Board's chrome: top bar, day meter, filter strip.
// ----------------------------------------------------------------------------
// docs/rounds/SPEC.md, Screen 1. Everything here is derived from real counts
// passed in by the route; nothing is computed to look plausible.
//
// SEARCH AND PAGINATION ARE HERE ON PURPOSE. The spec: "the EXISTING
// whole-queue search restyled in (search and pagination survive; the designs'
// bans lose to shipped features)". A design that removes a shipped capability
// is a design proposal, not a decision — so they are carried over, restyled.
//
// The search is a plain GET form. No JS needed to search a queue, it survives
// a page reload with the query intact, and the result is linkable — which is
// what a doctor sending "look at this list" to a colleague actually needs.
// ============================================================================

import Link from 'next/link';

import type { BoardFilter } from '@/lib/rounds/board-data';

import { RoundsNewVisitCta } from './new-visit-cta';
import { RoundsTopBar } from './top-bar';

function hrefWith(
  base: Record<string, string | number | undefined>,
  over: Record<string, string | number | undefined>,
): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries({ ...base, ...over })) {
    if (v !== undefined && v !== '' && v !== null) p.set(k, String(v));
  }
  const s = p.toString();
  return s ? `/board?${s}` : '/board';
}

export function RoundsBoardChrome({
  clinicianName,
  progress,
  criticalTally,
  filter,
  query,
  page,
  pageSize,
  totalCount,
  nextReviewHref,
  shownCount,
  children,
}: {
  clinicianName: string;
  progress: { signed: number; toReview: number; live: number; total: number };
  criticalTally: number;
  filter: BoardFilter;
  query: string;
  page: number;
  pageSize: number;
  totalCount: number;
  nextReviewHref: string | null;
  shownCount: number;
  children: React.ReactNode;
}) {
  const params = { filter, q: query || undefined };
  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));
  // The meter's denominator is the day's whole queue, not the filtered view —
  // a filter changes what you are looking at, not how much work exists.
  const meterTotal = Math.max(1, progress.total);
  const pct = (n: number) => (n / meterTotal) * 100;

  const today = new Date().toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  return (
    /* C2 — THE OWNERSHIP ANCHOR, and it is the whole reason `/board` was green.
       `ownedByDom` stops at the first ancestor-or-self carrying ANY class and
       gates only a `qm-rounds-*` one. Every node in this file is inline-styled
       and classless — the top bar, the filter group, the search form, the
       pagination, the day meter — so each climbed past this root to
       `<body className="min-h-screen antialiased">` and filed as *inherited*:
       reported, never blocking. The `board` sweep has been passing on the lane
       rows alone, which carry classes of their own.
       One class here owns the whole subtree, because everything under it is
       classless by construction. */
    <div className="qm-rounds-boardchrome" style={{ minHeight: '100vh' }}>
      {/* ── Top bar ──────────────────────────────────────────────────────
          R1: this WAS ~110 lines of inline-styled brand + nav, and it was the
          only nav the Rounds skin had. `AppFrame` — every other authed route —
          had no Rounds branch at all, so the app read as two products. The bar
          now comes from `components/rounds/top-bar.tsx` and is the same node
          everywhere; only the right-hand instruments below are the board's.
          The board's own nav also hardcoded `n.label === 'Board'` as the
          current item, which is a bug the moment the component renders
          anywhere else — the shared one derives it from the path. */}
      <RoundsTopBar userName={clinicianName}>
        {/* Critical tally. Rendered ONLY when there is something to tally — a
            permanent "0 critical" badge trains the eye to ignore the place
            criticals appear. */}
        {criticalTally > 0 ? (
          <Link
            href={hrefWith(params, { filter: 'critical', page: undefined })}
            data-testid="rounds-critical-tally"
            style={{
              fontFamily: 'var(--rounds-font-mono)',
              fontSize: 11.5,
              // C2: the LABEL takes the on-dark variant, the BORDER keeps the
              // true red. Same token, two roles — which is the whole reason
              // this palette carries `-text` siblings.
              color: 'var(--rounds-critical-on-dark)',
              border: '1px solid var(--rounds-critical)',
              borderRadius: 999,
              padding: '3px 10px',
              textDecoration: 'none',
            }}
          >
            {criticalTally} critical
          </Link>
        ) : null}

        <RoundsDayMeter progress={progress} pct={pct} />

        {/* 2026-08-04 — the clinician's name used to be an inline-styled span
            RIGHT HERE, duplicating `app-frame-rounds`'s `.qm-rounds-topbar-who`
            with the same three declarations written out again. Both copies
            were name-only: neither had a sign-out. `RoundsTopBar` now renders
            the account menu from the `userName` prop passed above, so there is
            one copy and it cannot go missing on one caller. */}

        {/* ── R2 — the primary action, back on the landing screen ───────────
            Last, so it reads as the thing to DO after the instruments that say
            what the day looks like. THIS is the mount that owns the `n`
            shortcut; the empty state's copy must not, or one press queues two
            navigations. */}
        <RoundsNewVisitCta variant="bar" withShortcut />
      </RoundsTopBar>

      <div style={{ padding: '0 24px 40px' }}>

        {/* ── Filter strip ────────────────────────────────────────────────── */}
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 12,
            padding: '14px 0',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--rounds-font-ui)',
              fontSize: 13,
              color: 'var(--rounds-text-2)',
            }}
          >
            {today}
            <span style={{ color: 'var(--rounds-text-3)' }}>
              {' · '}
              {shownCount} of {totalCount}
            </span>
          </span>

          {/* ⚠️ R3.8 — THE FILTER CHIP ROW IS DELETED, NOT HIDDEN.
              Owner ruling: POSITION IS THE STATUS. The board is a
              patient-lanes × stage-columns matrix — a card's COLUMN already
              says where the visit is, so a chip row asking "Active / Ready /
              Signed / SOAP / Ultrasound / Critical / Failed" was a second,
              weaker encoding of the thing the layout already encodes, and it
              cost a row of chrome above the work.

              ⚠️ THE `filter` PARAM SURVIVES THE CHIPS, DELIBERATELY, and this is
              the part not to "tidy up" later. R1 ships a config redirect
              `/dashboard?tab=all → /board?filter=active`; the route still reads
              the param, and the search form below still forwards it. Deleting
              the param with the chips would turn that redirect into a link to
              nothing — a deep link a doctor may have bookmarked. What was
              removed is the CONTROL, not the capability. */}

          {/* The shipped whole-queue search, restyled. A plain GET form: no JS
              needed, survives reload with the query intact, and the result is a
              linkable URL. */}
          <form action="/board" method="get" style={{ display: 'flex', gap: 6 }}>
            <input type="hidden" name="filter" value={filter} />
            <label htmlFor="rounds-search" className="sr-only">
              Search visits
            </label>
            <input
              id="rounds-search"
              name="q"
              type="search"
              defaultValue={query}
              placeholder="Search patient or reason…"
              maxLength={100}
              data-testid="rounds-search"
              style={{
                height: 30,
                minWidth: 220,
                padding: '0 10px',
                borderRadius: 'var(--rounds-radius-sm)',
                border: '1px solid var(--rounds-line-1)',
                background: 'var(--rounds-surface-1)',
                color: 'var(--rounds-text-1)',
                fontFamily: 'var(--rounds-font-ui)',
                fontSize: 13,
              }}
            />
            <button
              type="submit"
              style={{
                height: 30,
                padding: '0 12px',
                borderRadius: 'var(--rounds-radius-sm)',
                border: '1px solid var(--rounds-line-2)',
                background: 'var(--rounds-surface-2)',
                color: 'var(--rounds-text-1)',
                fontFamily: 'var(--rounds-font-ui)',
                fontSize: 13,
                cursor: 'pointer',
              }}
            >
              Search
            </button>
          </form>

          <div style={{ flex: 1 }} />

          {nextReviewHref ? (
            <Link
              href={nextReviewHref}
              data-testid="rounds-open-next"
              style={{
                fontFamily: 'var(--rounds-font-ui)',
                fontSize: 13,
                fontWeight: 600,
                color: 'var(--rounds-accent-text)',
                textDecoration: 'none',
              }}
            >
              Open next review →
            </Link>
          ) : null}
        </div>

        <main id="main">{children}</main>

        {/* ── Pagination ──────────────────────────────────────────────────── */}
        {totalPages > 1 ? (
          <nav
            aria-label="Pagination"
            data-testid="rounds-pagination"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              marginTop: 20,
              fontFamily: 'var(--rounds-font-ui)',
              fontSize: 13,
              color: 'var(--rounds-text-2)',
            }}
          >
            {page > 1 ? (
              <Link href={hrefWith(params, { page: page - 1 })} data-testid="rounds-page-prev">
                ← Previous
              </Link>
            ) : null}
            <span>
              Page {page} of {totalPages}
            </span>
            {page < totalPages ? (
              <Link href={hrefWith(params, { page: page + 1 })} data-testid="rounds-page-next">
                Next →
              </Link>
            ) : null}
          </nav>
        ) : null}
      </div>
    </div>
  );
}

function RoundsDayMeter({
  progress,
  pct,
}: {
  progress: { signed: number; toReview: number; live: number; total: number };
  pct: (n: number) => number;
}) {
  return (
    <div data-testid="rounds-day-meter" style={{ minWidth: 190 }}>
      <div
        style={{
          display: 'flex',
          gap: 10,
          fontFamily: 'var(--rounds-font-mono)',
          fontSize: 10.5,
          letterSpacing: '.05em',
          color: 'var(--rounds-text-3)',
          marginBottom: 4,
        }}
      >
        <span style={{ color: 'var(--rounds-ready-text)' }}>{progress.signed} signed</span>
        <span>{progress.toReview} to review</span>
        <span style={{ color: 'var(--rounds-processing-text)' }}>{progress.live} live</span>
      </div>
      <div
        style={{
          display: 'flex',
          height: 4,
          borderRadius: 2,
          overflow: 'hidden',
          background: 'var(--rounds-surface-3)',
        }}
      >
        {/* Widths are proportions of the day's whole queue, so the bar reads as
            "how much of today is done" rather than as a filtered view. */}
        <span style={{ width: `${pct(progress.signed)}%`, background: 'var(--rounds-ready)' }} />
        <span style={{ width: `${pct(progress.toReview)}%`, background: 'var(--rounds-text-3)' }} />
        <span style={{ width: `${pct(progress.live)}%`, background: 'var(--rounds-processing)' }} />
      </div>
    </div>
  );
}
