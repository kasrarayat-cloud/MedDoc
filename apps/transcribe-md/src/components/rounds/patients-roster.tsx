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

import { RoundsNewVisitCta } from './new-visit-cta';

import { c3Status } from '@/lib/visit-status-c3';
import type { C3PatientRow, C3PatientsCursor } from '@/lib/c3-list-pagination';

import {
  usePatientsRoster,
  ageFrom,
} from '@/lib/patients-roster';

import { cardEntranceDelayMs } from './board';

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
      {/* ── R3.1 — THE DISPLAY-FACE HEADER, and the Rounds top pattern ──────
          The title takes `--rounds-font-display` (Bricolage), which is what the
          board's own headings use; the count sits beside it as a mono kicker
          rather than as body copy, because a count is looked up, not read.
          Search and the primary sit on the SAME row — the Rounds top pattern —
          instead of the search living in a band of its own below. */}
      <div className="qm-rounds-roster-head">
        <div className="qm-rounds-roster-headline">
          <h1 className="qm-rounds-roster-title">Patients</h1>
          <span
            className="qm-rounds-roster-count"
            data-testid="rounds-patients-count"
          >
            {total} patient{total === 1 ? '' : 's'}
          </span>
        </div>
        <div style={{ flex: 1 }} />
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
        {/* ⚠️ THE SAME COMPONENT AS THE BOARD'S PRIMARY, not a second button
            wearing the same words. `actions keep their names end-to-end`, and
            R2 already had to rename this surface's sibling once — one renderer
            means the label, the href and the hover treatment cannot drift.
            No shortcut here: the board's top-bar mount owns `n`, and two
            document listeners on one key double-navigate. */}
        <RoundsNewVisitCta variant="bar" />
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
          {/* A GRID OF MARKER CARDS, not a list of rows. Same `role="list"`
              semantics — the change is anatomy, not accessibility. */}
          <div className="qm-rounds-roster-list" role="list">
            {rows.map((p, i) => (
              <RosterRow key={p.id} p={p} index={i} />
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

// ── R3.1 — THE MARKER CARD, the board's anatomy applied to a patient ────────
// The owner's verdict on the previous cut was "a redesign, not a recolor", and
// this is the difference: the old row was avatar + name + meta + a status WORD
// + a chevron, which is a list item wearing Rounds colours. A marker card is
// name, a MONO kicker of things you look up rather than read, and status
// expressed as a TREATMENT of the card itself.
//
// ⚠️ STATUS IS THE CARD, NOT A CHIP. `c3Status` hands back a `pillClass` full
// of `qm-lin-pill*` — the legacy chip. It is deliberately not used here: the
// key drives `data-status`, and the stylesheet paints the card's own border and
// its status line from that. Rendering the pill would have re-imported the
// exact legacy family this round exists to remove, on the one surface the
// census reported clean.
function RosterRow({ p, index }: { p: C3PatientRow; index: number }) {
  const age = ageFrom(p.dateOfBirth);
  // Mono, uppercased by the stylesheet: age · visits · modality. Only what the
  // row model genuinely has — a patient with no visits says so rather than
  // rendering an empty kicker.
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
      className="qm-rounds-pcard"
      data-testid="rounds-patient-row"
      data-status={status?.key ?? 'none'}
      /* The stagger is R2.3's, shared rather than re-derived — and capped in
         the same place for the same reason: a long roster must not make its
         last card wait, which reads as a load failure. */
      style={{ animationDelay: `${cardEntranceDelayMs(index)}ms` }}
      aria-label={`${p.name}${status ? `, ${status.label}` : ''}`}
    >
      <span className="qm-rounds-pcard-name">{p.name}</span>
      <span className="qm-rounds-pcard-kicker">
        {metaBits.join(' · ') || 'No visits yet'}
      </span>
      {status ? (
        <span className="qm-rounds-pcard-status">{status.label}</span>
      ) : null}
    </Link>
  );
}
