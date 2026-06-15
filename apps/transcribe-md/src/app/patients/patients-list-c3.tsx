'use client';

// ============================================================================
// PatientsListC3 — the calm C3 patients roster, made to scale.
// ----------------------------------------------------------------------------
// SSR'd first page + debounced name search + "Load more", all driven by the
// READ-ONLY searchPatientsAction (practice-scoped cursor pagination). Replaces
// the old card grid + 100-row client cap: a large roster paints one page, not
// the whole list. Rows link to the existing /patients/[id].
//
// PRESENTATION ONLY: no write path, no behavior change.
// ============================================================================

import { useCallback, useEffect, useRef, useState, useTransition } from 'react';
import Link from 'next/link';

import { c3Status } from '@/lib/visit-status-c3';
import { searchPatientsAction } from '@/actions/patients';
import type { C3PatientRow, C3PatientsCursor } from '@/lib/c3-list-pagination';

export function PatientsListC3({
  initialRows,
  initialCursor,
  total,
}: {
  initialRows: C3PatientRow[];
  initialCursor: C3PatientsCursor | null;
  total: number;
}) {
  const [rows, setRows] = useState<C3PatientRow[]>(initialRows);
  const [cursor, setCursor] = useState<C3PatientsCursor | null>(initialCursor);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [loadingMore, startLoadMore] = useTransition();
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reqIdRef = useRef(0);

  const runSearch = useCallback((q: string) => {
    const myReq = ++reqIdRef.current;
    setSearching(true);
    searchPatientsAction(null, q)
      .then((page) => {
        if (reqIdRef.current !== myReq) return;
        setRows(page.rows);
        setCursor(page.nextCursor);
      })
      .catch(() => {})
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
        const page = await searchPatientsAction(cursor, q);
        setRows((prev) => [...prev, ...page.rows]);
        setCursor(page.nextCursor);
      } catch {
        /* transient — keep current list */
      }
    });
  };

  const isFiltered = query.trim().length > 0;

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', padding: '4px 24px 80px' }}>
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
          placeholder="Search patients by name…"
          aria-label="Search patients"
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
            ? `No patients match “${query.trim()}”.`
            : 'No patients yet.'}
        </div>
      ) : (
        <>
          <div className="qm-c3-list" role="list">
            {rows.map((p) => (
              <PatientRow key={p.id} p={p} />
            ))}
          </div>
          <div className="qm-c3-list-foot">
            <span className="qm-c3-list-count">
              Showing {rows.length}
              {isFiltered ? ` match${rows.length === 1 ? '' : 'es'}` : ''}
              {!isFiltered && total > rows.length ? ` of ${total}` : ''}
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

function initialsOf(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((s) => s[0]?.toUpperCase() ?? '')
      .join('') || '·'
  );
}

function ageFrom(dobIso: string | null): number | null {
  if (!dobIso) return null;
  const d = new Date(dobIso);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age >= 0 && age < 150 ? age : null;
}

function PatientRow({ p }: { p: C3PatientRow }) {
  const age = ageFrom(p.dateOfBirth);
  const metaBits = [
    age != null ? `${age}y` : null,
    `${p.visitCount} visit${p.visitCount === 1 ? '' : 's'}`,
    p.lastVisitSpecialty
      ? p.lastVisitSpecialty.replace(/\b\w/g, (c) => c.toUpperCase())
      : null,
  ].filter(Boolean);
  const status =
    p.lastVisitStatus != null
      ? c3Status(p.lastVisitStatus, p.lastVisitNeedsReview)
      : null;

  return (
    <Link
      href={`/patients/${p.id}`}
      role="listitem"
      className="qm-c3-row qm-tap-44"
      style={{ textDecoration: 'none' }}
    >
      <span style={{ display: 'flex', alignItems: 'center', gap: 12, minWidth: 0 }}>
        <span className="qm-c3-pt-avatar" aria-hidden>
          {initialsOf(p.name)}
        </span>
        <span style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
          <span style={{ fontSize: 13.5, color: 'var(--color-linear-text)', fontWeight: 500 }}>
            {p.name}
          </span>
          <span
            style={{
              fontSize: 12,
              color: 'var(--color-linear-text-3)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            {metaBits.join(' · ') || 'No visits yet'}
          </span>
        </span>
      </span>
      <span style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 'none' }}>
        {status && <span className={status.pillClass}>{status.label}</span>}
        <span aria-hidden style={{ color: 'var(--color-linear-text-3)', fontSize: 13 }}>→</span>
      </span>
    </Link>
  );
}
