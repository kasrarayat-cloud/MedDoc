'use client';

// ============================================================================
// DashboardInboxC3 — the "Ready to sign" inbox as a finite WORK QUEUE.
// ----------------------------------------------------------------------------
// A sign queue is a do-this-next list, not an endless feed, so it's:
//   1. GROUPED into Today / This week / Older (by visit date) with small
//      headers, so the eye lands on a section instead of scrolling one wall;
//   2. PAGINATED into bounded pages (Page X of N + prev/next, ≤18 rows) so the
//      list NEVER runs off the screen regardless of total count;
//   3. SEARCHABLE up front — a prominent box that filters the WHOLE queue
//      server-side (all pages), not just the visible page.
//
// PRESENTATION ONLY: every page/search is the READ-ONLY, user-scoped
// searchInboxAction (offset paging + count over the SAME READY+unsigned query).
// Rows link to the existing /visits/[id]. No write path.
// ============================================================================

import { useCallback, useEffect, useRef, useState, useTransition } from 'react';
import Link from 'next/link';

import { c3Status } from '@/lib/visit-status-c3';
import { searchInboxAction } from '@/actions/visits';
import type { C3InboxRow } from '@/lib/c3-list-pagination';

type Group = { key: 'today' | 'week' | 'older'; label: string; rows: C3InboxRow[] };

/** Split the visible page into Today / This week / Older by visit date (local
 *  time). Newest-first order means Today leads; the labelled Older section
 *  keeps the backlog visible wherever it falls. Empty groups are dropped. */
function groupByDate(rows: C3InboxRow[]): Group[] {
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const sow = new Date(startOfToday);
  const dow = now.getDay();
  sow.setDate(sow.getDate() + (dow === 0 ? -6 : 1 - dow)); // Monday 00:00
  const startOfWeek = sow.getTime();

  const today: C3InboxRow[] = [];
  const week: C3InboxRow[] = [];
  const older: C3InboxRow[] = [];
  for (const r of rows) {
    const t = new Date(r.createdAt).getTime();
    if (Number.isNaN(t) || t >= startOfToday) today.push(r);
    else if (t >= startOfWeek) week.push(r);
    else older.push(r);
  }
  return (
    [
      { key: 'today', label: 'Today', rows: today },
      { key: 'week', label: 'This week', rows: week },
      { key: 'older', label: 'Older', rows: older },
    ] as Group[]
  ).filter((g) => g.rows.length > 0);
}

export function DashboardInboxC3({
  initialRows,
  total: initialTotal,
  totalPages: initialTotalPages,
}: {
  initialRows: C3InboxRow[];
  total: number;
  totalPages: number;
}) {
  const [rows, setRows] = useState<C3InboxRow[]>(initialRows);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(initialTotal);
  const [totalPages, setTotalPages] = useState(initialTotalPages);
  const [query, setQuery] = useState('');
  const [pending, startTransition] = useTransition();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Guards against an out-of-order response overwriting a newer one.
  const reqIdRef = useRef(0);

  const fetchPage = useCallback((q: string, p: number) => {
    const myReq = ++reqIdRef.current;
    startTransition(async () => {
      try {
        const res = await searchInboxAction(q, p);
        if (reqIdRef.current !== myReq) return; // superseded
        setRows(res.rows);
        setPage(res.page);
        setTotal(res.total);
        setTotalPages(res.totalPages);
      } catch {
        // Transient failure on a read-only path — leave the current view.
      }
    });
  }, []);

  const onQueryChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    // A new search always restarts at page 1 (it filters the WHOLE queue).
    debounceRef.current = setTimeout(() => fetchPage(value.trim(), 1), 220);
  };

  const goToPage = (p: number) => {
    if (p < 1 || p > totalPages || p === page) return;
    fetchPage(query.trim(), p);
  };

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const isFiltered = query.trim().length > 0;
  const groups = groupByDate(rows);

  return (
    <div>
      {/* Prominent search — the primary way into a large queue. */}
      <div className="qm-c3-search qm-c3-search--lg">
        <span className="qm-c3-search-ic" aria-hidden>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </span>
        <input
          type="search"
          inputMode="search"
          className="qm-c3-search-input qm-tap-44-input"
          placeholder="Search the whole queue by patient or chief complaint…"
          aria-label="Search notes to sign"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          autoComplete="off"
        />
        {pending && <span className="qm-c3-search-spin" aria-hidden />}
        {isFiltered && !pending && (
          <button
            type="button"
            className="qm-c3-search-clear qm-tap-44"
            aria-label="Clear search"
            onClick={() => {
              setQuery('');
              if (debounceRef.current) clearTimeout(debounceRef.current);
              fetchPage('', 1);
            }}
          >
            ✕
          </button>
        )}
      </div>

      {rows.length === 0 ? (
        <div className="qm-c3-list-empty" role="status">
          {isFiltered
            ? `No notes to sign match “${query.trim()}”.`
            : 'Nothing waiting to sign.'}
        </div>
      ) : (
        <>
          <div className={pending ? 'qm-c3-queue is-pending' : 'qm-c3-queue'}>
            {groups.map((g) => (
              <section className="qm-c3-grp" key={g.key} aria-label={g.label}>
                <h4 className="qm-c3-grp-h">
                  <span>{g.label}</span>
                  <span className="qm-c3-grp-n">{g.rows.length}</span>
                </h4>
                <div className="qm-c3-list" role="list">
                  {g.rows.map((v) => (
                    <InboxRow key={v.id} v={v} />
                  ))}
                </div>
              </section>
            ))}
          </div>

          {/* Pager — keeps a finite queue finite. "Page X of N" + prev/next so
              the list never runs off the screen regardless of total count. */}
          <div className="qm-c3-pager">
            <span className="qm-c3-list-count" aria-live="polite">
              {isFiltered
                ? `${total} match${total === 1 ? '' : 'es'}`
                : `${total} to sign`}
            </span>
            {totalPages > 1 && (
              <div className="qm-c3-pager-ctrls">
                <button
                  type="button"
                  className="qm-c3-pager-btn qm-tap-44"
                  onClick={() => goToPage(page - 1)}
                  disabled={page <= 1 || pending}
                  aria-label="Previous page"
                >
                  ← Prev
                </button>
                <span className="qm-c3-pager-label" aria-live="polite">
                  Page {page} of {totalPages}
                </span>
                <button
                  type="button"
                  className="qm-c3-pager-btn qm-tap-44"
                  onClick={() => goToPage(page + 1)}
                  disabled={page >= totalPages || pending}
                  aria-label="Next page"
                >
                  Next →
                </button>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function InboxRow({ v }: { v: C3InboxRow }) {
  const s = c3Status(v.status, v.needsReview);
  const name = v.patientName ?? 'Unknown patient';
  const meta = [v.specialty, v.chiefComplaint?.replace(/\s+/g, ' ').trim()]
    .filter(Boolean)
    .join(' · ');
  return (
    <Link
      href={`/visits/${v.id}`}
      role="listitem"
      className="qm-c3-row qm-tap-44"
      style={{ textDecoration: 'none' }}
    >
      <span style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
        <span style={{ fontSize: 13.5, color: 'var(--color-linear-text)', fontWeight: 500 }}>
          {name}
        </span>
        {meta && (
          <span
            style={{
              fontSize: 12,
              color: 'var(--color-linear-text-3)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {meta}
          </span>
        )}
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 'none' }}>
        <span className={s.pillClass}>{s.label}</span>
        <span aria-hidden style={{ color: 'var(--color-linear-text-3)', fontSize: 13 }}>→</span>
      </span>
    </Link>
  );
}
