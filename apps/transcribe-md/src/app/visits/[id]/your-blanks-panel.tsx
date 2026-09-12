'use client';

// ============================================================================
// REVIEW-DEFAULTS item 1 — "YOUR BLANKS", beside the document.
// ----------------------------------------------------------------------------
// Ruling #194 deleted the `keep` half: the machine never prints an undictated
// default. The doctor's own defaults did not disappear — they became a HUMAN
// ACT AT REVIEW, and this panel is where that act happens.
//
// ⚠️ WHY IT IS A PANEL AND NOT AN IN-PLACE CONTROL, MEASURED RATHER THAN
// PREFERRED. `DocumentPages` renders each page into a `<canvas role="img">`.
// There is no element for a field, no fieldId anywhere in the DOM, and no
// hit-testing — the only per-slot hook is keyed by SECTION HEADING and PAGE
// NUMBER, never by field. An "Insert my default" button on the control has
// nowhere to attach. The board filing assumed an in-place control; the surface
// cannot host one, so the list travels beside the page instead.
//
// ⚠️ AND THE PAGE ITSELF STAYS READ-ONLY PAPER. `soap-editor.tsx` refuses
// click-to-edit here for a recorded reason: it would put a second write path on
// the page the doctor is about to sign, with no audit distinction from the
// first. This panel does not edit the note. Each click stores an INPUT to the
// fill (`TemplateTwinFieldOverride`), exactly as the dropdown correction does,
// and the document is re-rendered from it.
//
// ⚠️ PANEL-1 (b) — MERGED. The builder groups identical scaffold texts into ONE
// row with a count: a form that ships the same wording on several controls
// shows that sentence once, not N times. But the PER-VISIT, PER-FIELD click is
// preserved — a group's Insert/Undo LOOPS the per-field action over the group's
// field ids, one call and one audit row each. An undictated exam is never
// printed automatically, and each field keeps its own audit row.
//
// ⚠️ PANEL-1 (c) — COLLAPSED BY DEFAULT. The panel opens as a single summary
// line, "N blanks — review", with "Insert all my defaults" as the primary
// action; the list opens on demand. The list is kept in the DOM and toggled via
// the `hidden` attribute rather than unmounted, so its testids resolve whether
// the panel is open or closed.
//
// ⚠️ "INSERT ALL" IS A LOOP OVER PER-FIELD INSERTS, NOT A BULK WRITER. Two
// recorded precedents say so: `chat-edit/intent.ts` — "There is also no bulk
// adopt. 'Accept all' is a LOOP over per-claim adopts" — and the twin confirm
// list's own bulk control. It matters here for a specific reason: the audit row
// is emitted PER FIELD, so a bulk writer would collapse N assertions into one
// and the trail could no longer say which defaults a doctor actually asserted.
// ============================================================================

import { useState, useTransition } from 'react';
import { toast } from 'sonner';

import {
  insertScaffoldDefaultAction,
  undoScaffoldDefaultAction,
} from '@/actions/set-template-control';

export interface InsertableDefaultGroup {
  /** The wording their template ships with, compiled. Shared by the group.
   *  PHI-free. */
  scaffoldText: string;
  /** The distinct control captions sharing this wording, in displayOrder.
   *  PHI-free. */
  labels: string[];
  /** Every field id sharing this wording, in displayOrder. */
  fieldIds: string[];
  /** The subset of `fieldIds` already inserted (reasonCode
   *  'clinician_scaffold_default'), so the surface offers UNDO for them. */
  insertedFieldIds: string[];
}

/** Per-viewer, per-browser expand/collapse memory. A convenience only — it is
 *  wrapped in try/catch and the panel defaults to COLLAPSED when nothing is
 *  stored (or storage is unavailable, e.g. a private window). */
const COLLAPSE_STORAGE_KEY = 'quillmd:your-blanks:collapsed';

export function YourBlanksPanel({
  visitId,
  groups,
  onChanged,
}: {
  visitId: string;
  groups: InsertableDefaultGroup[];
  /** Re-fetch the document. An insert that the doctor cannot SEE is one they
   *  will make twice — the same reason the writer invalidates the fill cache. */
  onChanged: () => void;
}) {
  const [pending, startTransition] = useTransition();
  const [busy, setBusy] = useState<string | null>(null);
  // COLLAPSED BY DEFAULT — (c). A remembered preference MAY override it, but the
  // default when nothing is stored is collapsed.
  const [collapsed, setCollapsed] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem(COLLAPSE_STORAGE_KEY);
      if (stored === 'open') return false;
      if (stored === 'closed') return true;
    } catch {
      // Private window / storage blocked — fall through to the default.
    }
    return true;
  });

  // ⚠️ NOTHING IS DRAWN WHEN THERE IS NOTHING TO OFFER. An empty panel reading
  // "no blanks with defaults" is a claim about the form the doctor did not ask
  // for, and on a form with no scaffolded controls it would appear on every
  // visit forever.
  if (groups.length === 0) return null;

  const uninsertedOf = (g: InsertableDefaultGroup) =>
    g.fieldIds.filter((id) => !g.insertedFieldIds.includes(id));

  // Every un-inserted field, across every group, in displayOrder — what "Insert
  // all" loops over, one call per field.
  const allUninserted = groups.flatMap((g) => uninsertedOf(g));
  // ⚠️ THE SUMMARY COUNTS BLANK CONTROLS, NOT WORDINGS. "N blanks" reads as a
  // count of blank fields; counting GROUPS would show "1 blank — review" for a
  // form with eight identical blank controls (adversarial finding), which
  // under-reports at the collapsed level the doctor sees first. The ×N badge on
  // each row still shows how many controls a wording covers.
  const blanks = allUninserted.length;

  const toggle = () => {
    setCollapsed((c) => {
      const next = !c;
      try {
        localStorage.setItem(COLLAPSE_STORAGE_KEY, next ? 'closed' : 'open');
      } catch {
        // Best effort — the preference is a convenience, never load-bearing.
      }
      return next;
    });
  };

  // ⚠️ A LOOP, SEQUENTIALLY, over the given field ids — one call per field so
  // each gets its own audit row and one refusal does not abandon the rest.
  const runLoop = (
    key: string,
    fieldIds: readonly string[],
    fn: (fieldId: string) => Promise<{ ok: boolean; error?: string; label?: string }>,
  ) => {
    if (fieldIds.length === 0) return;
    setBusy(key);
    startTransition(async () => {
      let failed = 0;
      let lastError: string | undefined;
      for (const fieldId of fieldIds) {
        const res = await fn(fieldId);
        if (!res.ok) {
          failed += 1;
          lastError = res.error;
        }
      }
      setBusy(null);
      // ⚠️ THE REFUSAL IS SPOKEN. Silence would make a refused act look like an
      // applied one — which matters here because the document is redrawn either
      // way and an unchanged page reads as "it worked, subtly".
      if (failed > 0) {
        toast.error(
          fieldIds.length === 1
            ? (lastError ?? 'That could not be applied.')
            : `${failed} of ${fieldIds.length} could not be applied.`,
        );
      }
      // ⚠️ REFETCH ONLY IF SOMETHING CHANGED. Nothing changed ⇔ every call
      // failed; refetching then would redraw an unchanged page and read as
      // success. A partial success still moved the document, so we refetch.
      if (failed < fieldIds.length) onChanged();
    });
  };

  return (
    <section
      data-testid="your-blanks-panel"
      aria-labelledby="your-blanks-heading"
      style={{
        marginTop: 16,
        padding: 16,
        border: '1px solid var(--color-linear-hairline)',
        borderRadius: 8,
      }}
    >
      <h3
        id="your-blanks-heading"
        style={{ fontSize: 14, margin: 0, color: 'var(--color-linear-text)' }}
      >
        Your blanks
      </h3>

      {/* PANEL-1 (c) — the collapsed summary line. Two SEPARATE buttons (nesting
          buttons is invalid): the summary toggles the list, and "Insert all my
          defaults" is the primary action. */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          marginTop: 8,
          flexWrap: 'wrap',
        }}
      >
        {/* ⚠️ A PLAIN BUTTON, NOT `SpecularButton`, AND THE REASON IS MEASURED:
            that component ENUMERATES its props and never spreads, so
            `data-testid` is silently dropped and every query against it fails.
            Using it here would have made these arms unwritable. */}
        <button
          type="button"
          data-testid="your-blanks-summary"
          aria-expanded={!collapsed}
          aria-controls="your-blanks-detail"
          className="qm-lin-btn qm-tap-44"
          style={{ fontSize: 13 }}
          onClick={toggle}
        >
          {blanks === 1 ? '1 blank — review' : `${blanks} blanks — review`}
        </button>

        {allUninserted.length > 0 && (
          <button
            type="button"
            disabled={pending}
            data-testid="your-blanks-insert-all"
            className="qm-lin-btn qm-tap-44"
            style={{ fontSize: 13, fontWeight: 600 }}
            onClick={() =>
              runLoop('__all__', allUninserted, (fieldId) =>
                insertScaffoldDefaultAction(visitId, fieldId),
              )
            }
          >
            {busy === '__all__' ? 'Inserting…' : 'Insert all my defaults'}
          </button>
        )}
      </div>

      {/* The detail — the explanation and the per-group list. Kept in the DOM
          and hidden when collapsed, so testids resolve either way. */}
      <div id="your-blanks-detail" hidden={collapsed}>
        <p style={{ fontSize: 13, marginTop: 8, color: 'var(--color-linear-text-3)' }}>
          Nothing was dictated for these, and your form has your usual wording for
          them. Inserting is your call — nothing is added unless you say so.
        </p>

        <ul
          data-testid="your-blanks-list"
          style={{ listStyle: 'none', padding: 0, margin: '4px 0 0' }}
        >
          {groups.map((g) => {
            // ⚠️ A STABLE PER-GROUP TESTID KEY — the group's FIRST field id, in
            // displayOrder. The whole group's Insert/Undo loops over its ids.
            const first = g.fieldIds[0]!;
            const uninserted = uninsertedOf(g);
            const count = g.fieldIds.length;
            return (
              <li
                key={first}
                data-testid={`your-blanks-row-${first}`}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  padding: '10px 0',
                  borderTop: '1px solid var(--color-linear-hairline)',
                }}
              >
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: 13, color: 'var(--color-linear-text)' }}>
                    {g.labels.join(', ')}
                    {count > 1 && (
                      <span
                        data-testid={`your-blanks-count-${first}`}
                        style={{ marginLeft: 6, color: 'var(--color-linear-text-3)' }}
                      >
                        ×{count}
                      </span>
                    )}
                  </div>
                  {/* The compiled scaffold text, shown verbatim. This is the
                      thing the doctor is being asked to assert, so it is quoted
                      rather than summarised. */}
                  <div
                    data-testid={`your-blanks-text-${first}`}
                    style={{ fontSize: 12, marginTop: 2, color: 'var(--color-linear-text-3)' }}
                  >
                    {g.scaffoldText}
                  </div>
                </div>
                {/* ⚠️ A MIXED GROUP OFFERS BOTH. When some fields of a shared
                    wording are inserted and some are not, show Insert (for the
                    rest) AND Undo (for the inserted subset) — pre-grouping, each
                    field had its own Undo, so a group must not hide the Undo of
                    its already-inserted members (adversarial finding). Each
                    button loops per-field, one audit row each. */}
                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                  {uninserted.length > 0 && (
                    <button
                      type="button"
                      disabled={pending}
                      data-testid={`your-blanks-insert-${first}`}
                      className="qm-lin-btn qm-tap-44"
                      style={{ fontSize: 13 }}
                      onClick={() =>
                        runLoop(first, uninserted, (fieldId) =>
                          insertScaffoldDefaultAction(visitId, fieldId),
                        )
                      }
                    >
                      {busy === first ? 'Inserting…' : 'Insert my default'}
                    </button>
                  )}
                  {g.insertedFieldIds.length > 0 && (
                    <button
                      type="button"
                      disabled={pending}
                      data-testid={`your-blanks-undo-${first}`}
                      className="qm-lin-btn qm-tap-44"
                      style={{ fontSize: 13 }}
                      onClick={() =>
                        runLoop(`${first}:undo`, g.insertedFieldIds, (fieldId) =>
                          undoScaffoldDefaultAction(visitId, fieldId),
                        )
                      }
                    >
                      {busy === `${first}:undo`
                        ? 'Removing…'
                        : g.insertedFieldIds.length > 1
                          ? 'Undo all'
                          : 'Undo'}
                    </button>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </section>
  );
}
