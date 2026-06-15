'use client';

// ============================================================================
// DashboardInboxC3 — the calm "Ready to sign" inbox, made to scale.
// ----------------------------------------------------------------------------
// Renders the server-SSR'd first page, then a debounced name search + a
// "Load more" affordance, both driven by the READ-ONLY searchInboxAction
// (cursor pagination over the same READY+unsigned, user-scoped query). The
// list never holds more than the pages the doctor has actually asked for —
// a 1,000-visit queue paints one 25-row page, not 1,000 rows.
//
// PRESENTATION ONLY: no write path. Rows link to the existing /visits/[id].
// ============================================================================

import { useCallback, useEffect, useRef, useState, useTransition } from 'react';
import Link from 'next/link';

import { c3Status } from '@/lib/visit-status-c3';
import { searchInboxAction } from '@/actions/visits';
import type { C3InboxCursor, C3InboxRow } from '@/lib/c3-list-pagination';

export function DashboardInboxC3({
  initialRows,
  initialCursor,
  total,
}: {
  initialRows: C3InboxRow[];
  initialCursor: C3InboxCursor | null;
  total: number;
}) {
  const [rows, setRows] = useState<C3InboxRow[]>(initialRows);
  const [cursor, setCursor] = useState<C3InboxCursor | null>(initialCursor);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [loadingMore, startLoadMore] = useTransition();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Guards against an out-of-order search response overwriting a newer one.
  const reqIdRef = useRef(0);

  const runSearch = useCallback((q: string) => {
    const myReq = ++reqIdRef.current;
    setSearching(true);
    searchInboxAction(null, q)
      .then((page) => {
        if (reqIdRef.current !== myReq) return; // a newer search superseded this
        setRows(page.rows);
        setCursor(page.nextCursor);
      })
      .catch(() => {
        if (reqIdRef.current !== myReq) return;
        // Leave the current rows in place on a transient failure; the
        // doctor can retype. No behaviour change — read-only path.
      })
      .finally(() => {
        if (reqIdRef.current === myReq) setSearching(false);
      });
  }, []);

  const onQueryChange = (value: string) => {
    setQuery(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => runSearch(value.trim()), 220);
  };

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const loadMore = () => {
    if (!cursor) return;
    const q = query.trim();
    startLoadMore(async () => {
      try {
        const page = await searchInboxAction(cursor, q);
        setRows((prev) => [...prev, ...page.rows]);
        setCursor(page.nextCursor);
      } catch {
        /* transient — keep current list */
      }
    });
  };

  const isFiltered = query.trim().length > 0;
  const showing = rows.length;

  return (
    <div>
      <div className="qm-c3-search">
        <span className="qm-c3-search-ic" aria-hidden>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
        </span>
        <input
          type="search"
          inputMode="search"
          className="qm-c3-search-input"
          placeholder="Search notes to sign by patient or chief complaint…"
          aria-label="Search notes to sign"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          autoComplete="off"
        />
        {searching && <span className="qm-c3-search-spin" aria-hidden />}
        {isFiltered && !searching && (
          <button
            type="button"
            className="qm-c3-search-clear qm-tap-44"
            aria-label="Clear search"
            onClick={() => {
              setQuery('');
              if (debounceRef.current) clearTimeout(debounceRef.current);
              runSearch('');
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
          <div className="qm-c3-list" role="list">
            {rows.map((v) => (
              <InboxRow key={v.id} v={v} />
            ))}
          </div>

          <div className="qm-c3-list-foot">
            <span className="qm-c3-list-count" aria-live="polite">
              Showing {showing}
              {isFiltered ? ' match' : ''}
              {isFiltered && showing !== 1 ? 'es' : ''}
              {!isFiltered && total > showing ? ` of ${total}` : ''}
            </span>
            {cursor && (
              <button
                type="button"
                className="qm-c3-loadmore qm-tap-44"
                onClick={loadMore}
                disabled={loadingMore}
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
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
