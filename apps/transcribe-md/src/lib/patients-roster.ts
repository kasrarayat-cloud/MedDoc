'use client';

// ============================================================================
// The patients roster's BEHAVIOUR, once, for every skin that draws it.
// ----------------------------------------------------------------------------
// R1 restyles /patients into Rounds. The C3 list it replaces is not a dumb
// grid — it carries a 220ms-debounced server search with request-race
// protection, keyset cursor pagination over (updatedAt, id), and a "Load more"
// that appends rather than replaces. Re-typing that beside a new set of class
// names is how two lists that are supposed to be the same list stop being it:
// one gets a fix, the other keeps the bug, and nothing fails.
//
// So the logic lives here — in `lib/`, not beside either skin, because a
// component under `components/rounds/` reaching back into `app/patients/` for
// its behaviour is the same coupling in the other direction.
//
// `reqIdRef` is the part worth naming: search results arrive out of order. A
// slow "Sm" landing after a fast "Smith" would repaint the list with the wrong
// rows, and it would look exactly like a search that does not work. Every
// response checks it is still the newest before it is allowed to write.
// ============================================================================

import { useCallback, useEffect, useRef, useState, useTransition } from 'react';

import { searchPatientsAction } from '@/actions/patients';
import type { C3PatientRow, C3PatientsCursor } from '@/lib/c3-list-pagination';

export const PATIENTS_SEARCH_DEBOUNCE_MS = 220;

export interface PatientsRoster {
  rows: C3PatientRow[];
  query: string;
  searching: boolean;
  loadingMore: boolean;
  /** True once the doctor has typed something — drives "no matches" vs "none". */
  isFiltered: boolean;
  /** Null when the list is exhausted, so "Load more" is absent, not disabled. */
  cursor: C3PatientsCursor | null;
  onQueryChange: (value: string) => void;
  clearQuery: () => void;
  loadMore: () => void;
}

export function usePatientsRoster(
  initialRows: C3PatientRow[],
  initialCursor: C3PatientsCursor | null,
): PatientsRoster {
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

  const onQueryChange = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(
        () => runSearch(value.trim()),
        PATIENTS_SEARCH_DEBOUNCE_MS,
      );
    },
    [runSearch],
  );

  const clearQuery = useCallback(() => {
    setQuery('');
    if (debounceRef.current) clearTimeout(debounceRef.current);
    runSearch('');
  }, [runSearch]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const loadMore = useCallback(() => {
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
  }, [cursor, query]);

  return {
    rows,
    query,
    searching,
    loadingMore,
    isFiltered: query.trim().length > 0,
    cursor,
    onQueryChange,
    clearQuery,
    loadMore,
  };
}

/** Shared row derivations, so the two skins print the same facts. */
export function initialsOf(name: string): string {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((s) => s[0]?.toUpperCase() ?? '')
      .join('') || '·'
  );
}

export function ageFrom(dobIso: string | null): number | null {
  if (!dobIso) return null;
  const d = new Date(dobIso);
  if (Number.isNaN(d.getTime())) return null;
  const now = new Date();
  let age = now.getFullYear() - d.getFullYear();
  const m = now.getMonth() - d.getMonth();
  if (m < 0 || (m === 0 && now.getDate() < d.getDate())) age--;
  return age >= 0 && age < 150 ? age : null;
}
