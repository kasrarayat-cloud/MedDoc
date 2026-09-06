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

export interface InsertableDefault {
  fieldId: string;
  /** The control's caption on the doctor's own form. PHI-free. */
  label: string;
  /** The wording their template ships with, compiled. PHI-free. */
  scaffoldText: string;
  inserted: boolean;
}

export function YourBlanksPanel({
  visitId,
  defaults,
  onChanged,
}: {
  visitId: string;
  defaults: InsertableDefault[];
  /** Re-fetch the document. An insert that the doctor cannot SEE is one they
   *  will make twice — the same reason the writer invalidates the fill cache. */
  onChanged: () => void;
}) {
  const [pending, startTransition] = useTransition();
  const [busyField, setBusyField] = useState<string | null>(null);

  // ⚠️ NOTHING IS DRAWN WHEN THERE IS NOTHING TO OFFER. An empty panel reading
  // "no blanks with defaults" is a claim about the form the doctor did not ask
  // for, and on a form with no scaffolded controls it would appear on every
  // visit forever.
  if (defaults.length === 0) return null;

  const insertable = defaults.filter((d) => !d.inserted);

  const run = (
    fieldId: string,
    fn: () => Promise<{ ok: boolean; error?: string; label?: string }>,
  ) => {
    setBusyField(fieldId);
    startTransition(async () => {
      const res = await fn();
      setBusyField(null);
      // ⚠️ THE REFUSAL IS SPOKEN. The server's message is the doctor-facing one
      // and silence would make a refused insert look like an applied one —
      // which matters more here than usual, because the document is redrawn
      // either way and an unchanged page reads as "it worked, subtly".
      if (!res.ok) toast.error(res.error ?? 'That could not be applied.');
      else onChanged();
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
      <p style={{ fontSize: 13, marginTop: 4, color: 'var(--color-linear-text-3)' }}>
        Nothing was dictated for these, and your form has your usual wording for
        them. Inserting is your call — nothing is added unless you say so.
      </p>

      {insertable.length > 1 && (
        <div style={{ marginTop: 12 }}>
          {/* ⚠️ A PLAIN BUTTON, NOT `SpecularButton`, AND THE REASON IS
              MEASURED: that component ENUMERATES its props and never spreads,
              so `data-testid` is silently dropped and every query against it
              fails. Using it here would have made these arms unwritable — and
              worse, an arm that somehow passed would be finding a different
              element. Same class as the members panel, which passes testids
              into it today that never reach the DOM. */}
          <button
            type="button"
            disabled={pending}
            data-testid="your-blanks-insert-all"
            className="qm-lin-btn qm-tap-44"
            style={{ fontSize: 13 }}
            onClick={() => {
              // ⚠️ A LOOP, SEQUENTIALLY, so each field gets its own audit row
              // and one refusal does not abandon the rest.
              setBusyField('__all__');
              startTransition(async () => {
                let failed = 0;
                for (const d of insertable) {
                  const res = await insertScaffoldDefaultAction(visitId, d.fieldId);
                  if (!res.ok) failed += 1;
                }
                setBusyField(null);
                if (failed > 0) {
                  toast.error(
                    `${failed} of ${insertable.length} could not be inserted.`,
                  );
                }
                onChanged();
              });
            }}
          >
            {busyField === '__all__'
              ? 'Inserting…'
              : `Insert all ${insertable.length} of my defaults`}
          </button>
          {/* ⚠️ THE LIST IS SHOWN, WHICH THE BOARD FILING ASKED FOR BY NAME. A
              bulk control whose contents the doctor cannot see is a button that
              asks them to trust a number. Every row below IS the list. */}
        </div>
      )}

      <ul
        data-testid="your-blanks-list"
        style={{ listStyle: 'none', padding: 0, margin: '12px 0 0' }}
      >
        {defaults.map((d) => (
          <li
            key={d.fieldId}
            data-testid={`your-blanks-row-${d.fieldId}`}
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
                {d.label}
              </div>
              {/* The compiled scaffold text, shown verbatim. This is the thing
                  the doctor is being asked to assert, so it is quoted rather
                  than summarised. */}
              <div
                data-testid={`your-blanks-text-${d.fieldId}`}
                style={{ fontSize: 12, marginTop: 2, color: 'var(--color-linear-text-3)' }}
              >
                {d.scaffoldText}
              </div>
            </div>
            {d.inserted ? (
              <button
                type="button"
                disabled={pending}
                data-testid={`your-blanks-undo-${d.fieldId}`}
                className="qm-lin-btn qm-tap-44"
                style={{ fontSize: 13 }}
                onClick={() =>
                  run(d.fieldId, () => undoScaffoldDefaultAction(visitId, d.fieldId))
                }
              >
                {busyField === d.fieldId ? 'Removing…' : 'Undo'}
              </button>
            ) : (
              <button
                type="button"
                disabled={pending}
                data-testid={`your-blanks-insert-${d.fieldId}`}
                className="qm-lin-btn qm-tap-44"
                style={{ fontSize: 13 }}
                onClick={() =>
                  run(d.fieldId, () => insertScaffoldDefaultAction(visitId, d.fieldId))
                }
              >
                {busyField === d.fieldId ? 'Inserting…' : 'Insert my default'}
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
