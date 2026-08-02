'use client';

// ============================================================================
// ROUNDS — the patients roster.
// ----------------------------------------------------------------------------
// Same list, same server search, same cursor pagination as the C3 roster: the
// behaviour is `usePatientsRoster`, shared, so a fix to one is a fix to both.
// This file is markup and tokens.
//
// FULL FUNCTION IS THE REQUIREMENT, not a subset that looks right in a
// screenshot. The C3 list that shipped is not a card grid — it does a
// 220ms-debounced practice-scoped search on the server and pages with a keyset
// cursor, which is what lets a large roster paint one page instead of a
// hundred rows. A restyle that quietly dropped either would be a regression
// wearing new paint.
//
// Unlike the C3 file this one carries `data-testid`s. There were NONE anywhere
// under app/patients — no contract to preserve, and therefore no safety net
// either. The proof R1 owes ("one nav, no aside, on every authed route") needs
// something to hold on to.
//
// ⚠️ IT LIVES HERE, NOT UNDER `app/patients/`, AND A GATE SAID SO.
// `gate-controls-contract` splits every `qm-rounds-*` class into two layers:
// Rounds' OWN screens (`components/rounds/`, `app/board/`) and existing
// surfaces wearing the skin — and the second layer must be documented row by
// row in SPEC.md's § Controls table. Under `app/patients/` these seventeen
// roster classes read as undocumented control primitives, which is exactly
// backwards: this is a Rounds-native screen, so it belongs on the native side
// of the boundary. Moving the file was the fix; widening the gate would have
// been the bug.
// ============================================================================

import Link from 'next/link';

import { c3Status } from '@/lib/visit-status-c3';
import type { C3PatientRow, C3PatientsCursor } from '@/lib/c3-list-pagination';

import {
  usePatientsRoster,
  initialsOf,
  ageFrom,
} from '@/lib/patients-roster';

export function RoundsPatientsRoster({
  initialRows,
  initialCursor,
  total,
}: {
  initialRows: C3PatientRow[];
  initialCursor: C3PatientsCursor | null;
  total: number;
}) {
  const {
    rows,
    query,
    searching,
    loadingMore,
    isFiltered,
    cursor,
    onQueryChange,
    clearQuery,
    loadMore,
  } = usePatientsRoster(initialRows, initialCursor);

  return (
    <div className="qm-rounds-roster" data-testid="rounds-patients">
      <div className="qm-rounds-roster-head">
        <h1 className="qm-rounds-roster-title">Patients</h1>
        <span
          className="qm-rounds-roster-count"
          data-testid="rounds-patients-count"
        >
          {total} patient{total === 1 ? '' : 's'}
        </span>
        <div style={{ flex: 1 }} />
        <Link
          href="/visits/new"
          className="qm-rounds-roster-new"
          data-testid="rounds-patients-new-visit"
        >
          New visit
        </Link>
      </div>

      <div className="qm-rounds-roster-search">
        <input
          type="search"
          inputMode="search"
          className="qm-rounds-roster-input"
          placeholder="Search patients by name…"
          aria-label="Search patients"
          data-testid="rounds-patients-search"
          value={query}
          onChange={(e) => onQueryChange(e.target.value)}
          autoComplete="off"
        />
        {/* `searching` and the clear button are mutually exclusive on purpose —
            a spinner and an ✕ in the same slot read as two controls. */}
        {searching ? (
          <span className="qm-rounds-roster-spin" aria-hidden />
        ) : isFiltered ? (
          <button
            type="button"
            className="qm-rounds-roster-clear"
            aria-label="Clear search"
            data-testid="rounds-patients-clear"
            onClick={clearQuery}
          >
            ✕
          </button>
        ) : null}
      </div>

      {rows.length === 0 ? (
        <div
          className="qm-rounds-roster-empty"
          role="status"
          data-testid="rounds-patients-empty"
        >
          {isFiltered
            ? `No patients match “${query.trim()}”.`
            : 'No patients yet. Start a visit and the record is created along the way.'}
        </div>
      ) : (
        <>
          <div className="qm-rounds-roster-list" role="list">
            {rows.map((p) => (
              <RosterRow key={p.id} p={p} />
            ))}
          </div>
          <div className="qm-rounds-roster-foot">
            <span className="qm-rounds-roster-shown" aria-live="polite">
              Showing {rows.length}
              {isFiltered ? ` match${rows.length === 1 ? '' : 'es'}` : ''}
              {!isFiltered && total > rows.length ? ` of ${total}` : ''}
            </span>
            {/* Absent, not disabled, when the list is exhausted: a permanently
                greyed "Load more" is a control that never does anything. */}
            {cursor ? (
              <button
                type="button"
                className="qm-rounds-roster-more"
                data-testid="rounds-patients-more"
                onClick={loadMore}
                disabled={loadingMore}
              >
                {loadingMore ? 'Loading…' : 'Load more'}
              </button>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

function RosterRow({ p }: { p: C3PatientRow }) {
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
      className="qm-rounds-roster-row"
      data-testid="rounds-patient-row"
    >
      <span className="qm-rounds-roster-avatar" aria-hidden>
        {initialsOf(p.name)}
      </span>
      <span className="qm-rounds-roster-idcol">
        <span className="qm-rounds-roster-name">{p.name}</span>
        <span className="qm-rounds-roster-meta">
          {metaBits.join(' · ') || 'No visits yet'}
        </span>
      </span>
      {status ? (
        <span className="qm-rounds-roster-status">{status.label}</span>
      ) : null}
      <span aria-hidden className="qm-rounds-roster-chev">
        →
      </span>
    </Link>
  );
}
