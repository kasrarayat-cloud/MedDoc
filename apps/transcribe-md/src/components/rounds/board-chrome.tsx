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

const FILTER_LABELS: { id: BoardFilter; label: string }[] = [
  { id: 'active', label: 'Active' },
  { id: 'signed', label: 'Signed' },
  { id: 'soap', label: 'SOAP' },
  { id: 'ultrasound', label: 'Ultrasound' },
  { id: 'critical', label: 'Critical' },
  { id: 'failed', label: 'Failed' },
];

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
    <div style={{ minHeight: '100vh', padding: '0 24px 40px' }}>
      {/* ── Top bar ─────────────────────────────────────────────────────── */}
      <header
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 20,
          padding: '16px 0',
          borderBottom: '1px solid var(--rounds-line-1)',
        }}
      >
        <Link
          href="/board"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 8,
            textDecoration: 'none',
          }}
        >
          <span
            aria-hidden
            style={{
              display: 'grid',
              placeItems: 'center',
              width: 26,
              height: 26,
              borderRadius: 7,
              background: 'var(--rounds-accent)',
              color: '#fff',
              fontFamily: 'var(--rounds-font-display)',
              fontWeight: 700,
              fontSize: 14,
            }}
          >
            Q
          </span>
          <span
            style={{
              fontFamily: 'var(--rounds-font-display)',
              fontWeight: 600,
              fontSize: 16,
              color: 'var(--rounds-text-1)',
            }}
          >
            QuillMD
          </span>
        </Link>

        <nav aria-label="Main" style={{ display: 'flex', gap: 14 }}>
          {[
            { href: '/board', label: 'Board' },
            { href: '/settings/note-format', label: 'Templates' },
            { href: '/settings', label: 'Settings' },
          ].map((n) => (
            <Link
              key={n.href}
              href={n.href}
              style={{
                fontFamily: 'var(--rounds-font-ui)',
                fontSize: 13.5,
                color:
                  n.label === 'Board'
                    ? 'var(--rounds-text-1)'
                    : 'var(--rounds-text-2)',
                textDecoration: 'none',
              }}
            >
              {n.label}
            </Link>
          ))}
        </nav>

        <div style={{ flex: 1 }} />

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
              color: 'var(--rounds-critical)',
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

        <span
          style={{
            fontFamily: 'var(--rounds-font-ui)',
            fontSize: 13,
            color: 'var(--rounds-text-2)',
          }}
        >
          {clinicianName}
        </span>
      </header>

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

        <div role="group" aria-label="Filters" style={{ display: 'flex', gap: 6 }}>
          {FILTER_LABELS.map((f) => {
            const active = f.id === filter;
            return (
              <Link
                key={f.id}
                href={hrefWith(params, { filter: f.id, page: undefined })}
                aria-current={active ? 'true' : undefined}
                data-testid={`rounds-filter-${f.id}`}
                style={{
                  fontFamily: 'var(--rounds-font-ui)',
                  fontSize: 12.5,
                  padding: '4px 10px',
                  borderRadius: 999,
                  textDecoration: 'none',
                  color: active ? 'var(--rounds-text-1)' : 'var(--rounds-text-2)',
                  background: active ? 'var(--rounds-accent-tint-16)' : 'transparent',
                  border: `1px solid ${active ? 'var(--rounds-accent)' : 'var(--rounds-line-1)'}`,
                }}
              >
                {f.label}
              </Link>
            );
          })}
        </div>

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
              color: 'var(--rounds-accent)',
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
        <span style={{ color: 'var(--rounds-ready)' }}>{progress.signed} signed</span>
        <span>{progress.toReview} to review</span>
        <span style={{ color: 'var(--rounds-processing)' }}>{progress.live} live</span>
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
