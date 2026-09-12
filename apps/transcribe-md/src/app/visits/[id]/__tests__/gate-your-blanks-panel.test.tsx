// ============================================================================
// GATE — "YOUR BLANKS": what the review surface DRAWS for REVIEW-DEFAULTS.
// ----------------------------------------------------------------------------
// ⚠️ THIS FILE PROVES NOTHING ABOUT THE WRITE, and says so rather than implying
// otherwise. Every guard that matters — blank-only, per-field, fail-closed —
// lives on the server and is measured in `gate-review-defaults-insert`. What is
// proved here is the other half: that the doctor is offered exactly the acts
// the server will accept, and that a bulk control does not quietly become a
// bulk WRITE.
//
// ⚠️ PANEL-1 (b)+(c) — THE MODEL IS NOW PER-GROUP, COLLAPSED BY DEFAULT. The
// builder merges identical scaffold texts into one group `{ scaffoldText,
// labels, fieldIds, insertedFieldIds }`, and the panel opens as a single
// summary line "N blanks — review" with the list toggled behind it. The
// invariants below are RE-EXPRESSED for that model, NOT dropped: a per-group
// act still calls the per-field action ONCE PER field id in the group, in
// order; "Insert all" still loops one call per un-inserted field across all
// groups; an already-inserted group still offers UNDO; `onChanged` still fires
// on success and NOT on a total refusal.
//
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL:
//   · the panel appears with nothing to offer     -> the emptiness block
//   · "Insert all" stops being a LOOP             -> the bulk block
//   · two fields with the SAME wording stop
//     merging into one row                        -> the merge block (b)
//   · the panel stops opening collapsed, or the
//     summary stops expanding on click            -> the collapse block (c)
//   · an already-inserted group offers INSERT
//     instead of UNDO                             -> the group block
//   · the compiled scaffold text stops being shown -> the group block
//   · a group's button sends the WRONG field id(s) -> the group / merge block
//   · Undo calls INSERT instead of undo           -> the undo block
//   · a total refusal still refetches the document -> the refetch block
// ============================================================================

import { describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

const insertAction = vi.fn(async () => ({ ok: true }));
const undoAction = vi.fn(async () => ({ ok: true }));
vi.mock('@/actions/set-template-control', () => ({
  insertScaffoldDefaultAction: (...a: unknown[]) => insertAction(...(a as [])),
  undoScaffoldDefaultAction: (...a: unknown[]) => undoAction(...(a as [])),
}));

import { YourBlanksPanel, type InsertableDefaultGroup } from '../your-blanks-panel';

const A_ID = 'ttf_aaaaaaaaaaaaaaaaaaaaaaaa';
const B_ID = 'ttf_bbbbbbbbbbbbbbbbbbbbbbbb';
const C_ID = 'ttf_cccccccccccccccccccccccc';

// One group, one field.
const GA: InsertableDefaultGroup = {
  scaffoldText: 'No acute findings.',
  labels: ['Impression'],
  fieldIds: [A_ID],
  insertedFieldIds: [],
};
// A second, distinct group.
const GB: InsertableDefaultGroup = {
  scaffoldText: 'Standard protocol followed.',
  labels: ['Technique'],
  fieldIds: [B_ID],
  insertedFieldIds: [],
};
// PANEL-1 (b): two controls that ship the SAME wording — ONE merged group.
const GMERGED: InsertableDefaultGroup = {
  scaffoldText: 'No acute findings.',
  labels: ['Impression', 'Right knee'],
  fieldIds: [A_ID, C_ID],
  insertedFieldIds: [],
};

/** Open the collapsed panel so the per-group list is not `hidden`. Interaction
 *  works either way in jsdom, but expanding is what a doctor actually does. */
function expand() {
  fireEvent.click(screen.getByTestId('your-blanks-summary'));
}

describe('⚠️ nothing is drawn when there is nothing to offer', () => {
  it('renders null on an empty list', () => {
    const { container } = render(
      <YourBlanksPanel visitId="v1" groups={[]} onChanged={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
    // An empty panel reading "no blanks with defaults" is a claim about the
    // form the doctor did not ask for, and on a form with no scaffolded
    // controls it would appear on every visit forever.
  });

  it('and DOES draw when there is — the arm above is not passing on a dead component', () => {
    render(<YourBlanksPanel visitId="v1" groups={[GA]} onChanged={() => {}} />);
    expect(screen.getByTestId('your-blanks-panel')).toBeTruthy();
  });
});

describe('⚠️ PANEL-1 (c) — COLLAPSED BY DEFAULT, expands on click', () => {
  it('opens as a summary line with the list hidden, then reveals it on click', () => {
    cleanup();
    render(<YourBlanksPanel visitId="v1" groups={[GA]} onChanged={() => {}} />);
    // The summary is present...
    expect(screen.getByTestId('your-blanks-summary')).toBeTruthy();
    // ...and the list, though in the DOM (so its testids resolve), is hidden.
    expect(screen.getByTestId('your-blanks-list').closest('[hidden]')).toBeTruthy();
    // Click the summary -> the list is no longer under a hidden ancestor.
    expand();
    expect(screen.getByTestId('your-blanks-list').closest('[hidden]')).toBeNull();
  });

  it('the summary counts GROUPS with something left to insert, singular and plural', () => {
    cleanup();
    render(<YourBlanksPanel visitId="v1" groups={[GA]} onChanged={() => {}} />);
    expect(screen.getByTestId('your-blanks-summary').textContent).toBe('1 blank — review');
    cleanup();
    render(<YourBlanksPanel visitId="v1" groups={[GA, GB]} onChanged={() => {}} />);
    expect(screen.getByTestId('your-blanks-summary').textContent).toBe('2 blanks — review');
  });
});

describe('⚠️ PANEL-1 (b) — identical scaffold texts merge into ONE row', () => {
  it('renders a single row for the group, with a count badge and no second row', () => {
    cleanup();
    render(<YourBlanksPanel visitId="v1" groups={[GMERGED]} onChanged={() => {}} />);
    expand();
    // ONE row, keyed on the group's first field id; the second field id gets NO
    // row of its own — that is the merge.
    expect(screen.getByTestId(`your-blanks-text-${A_ID}`).textContent).toBe('No acute findings.');
    expect(screen.queryByTestId(`your-blanks-text-${C_ID}`)).toBeNull();
    expect(screen.queryByTestId(`your-blanks-row-${C_ID}`)).toBeNull();
    // ...and the count badge names how many controls share the wording.
    expect(screen.getByTestId(`your-blanks-count-${A_ID}`).textContent).toBe('×2');
  });

  it('⚠️ the group INSERT loops the per-field action once PER field id, in order', async () => {
    // ⚠️ THE PER-FIELD CLICK IS PRESERVED THROUGH THE MERGE. A group of two must
    // emit TWO inserts — one audit row each — not a single bulk write. If the
    // handler collapsed the group into one call, the trail could no longer say
    // which defaults the doctor asserted.
    insertAction.mockClear();
    cleanup();
    render(<YourBlanksPanel visitId="v-42" groups={[GMERGED]} onChanged={() => {}} />);
    expand();
    fireEvent.click(screen.getByTestId(`your-blanks-insert-${A_ID}`));
    await waitFor(() => expect(insertAction).toHaveBeenCalledTimes(2));
    expect(insertAction.mock.calls.map((c) => c as unknown[])).toEqual([
      ['v-42', A_ID],
      ['v-42', C_ID],
    ]);
  });

  it('a single-field group shows no count badge — the number would be theatre', () => {
    cleanup();
    render(<YourBlanksPanel visitId="v1" groups={[GA]} onChanged={() => {}} />);
    expand();
    expect(screen.queryByTestId(`your-blanks-count-${A_ID}`)).toBeNull();
  });
});

describe('⚠️ each group shows the compiled wording the doctor is being asked to assert', () => {
  it('quotes the scaffold text verbatim rather than summarising it', () => {
    cleanup();
    render(<YourBlanksPanel visitId="v1" groups={[GA]} onChanged={() => {}} />);
    expand();
    expect(screen.getByTestId(`your-blanks-text-${A_ID}`).textContent).toBe('No acute findings.');
    expect(screen.getByTestId(`your-blanks-insert-${A_ID}`)).toBeTruthy();
  });

  it('⚠️ a single-field group INSERT sends THAT field id and THIS visit id', async () => {
    // ⚠️ A per-field feature whose per-field argument is untested is not a
    // per-field feature: the handler could send a fixed wrong id and every
    // other arm would stay green.
    insertAction.mockClear();
    cleanup();
    render(<YourBlanksPanel visitId="v-42" groups={[GA, GB]} onChanged={() => {}} />);
    expand();
    fireEvent.click(screen.getByTestId(`your-blanks-insert-${B_ID}`));
    await waitFor(() => expect(insertAction).toHaveBeenCalledOnce());
    expect(insertAction.mock.calls[0]).toEqual(['v-42', B_ID]);
  });

  it('⚠️ an ALREADY-INSERTED group offers UNDO, never a second insert', () => {
    // The write is idempotent, so a second insert would not corrupt anything —
    // but offering it says the click did not land, and the doctor's next move
    // would be to click again rather than to undo.
    cleanup();
    render(
      <YourBlanksPanel
        visitId="v1"
        groups={[{ ...GA, insertedFieldIds: [A_ID] }]}
        onChanged={() => {}}
      />,
    );
    expand();
    expect(screen.getByTestId(`your-blanks-undo-${A_ID}`)).toBeTruthy();
    expect(screen.queryByTestId(`your-blanks-insert-${A_ID}`)).toBeNull();
  });
});

describe('⚠️ INSERT ALL IS A LOOP OVER PER-FIELD INSERTS, NOT A BULK WRITE', () => {
  it('calls the per-field action once PER un-inserted field across ALL groups, in order', async () => {
    // ⚠️ THE AUDIT ROW IS EMITTED PER FIELD. A bulk writer would collapse N
    // assertions into one and the trail could no longer say which defaults a
    // doctor actually asserted — the entire product claim of #194's
    // doctor-facing half.
    insertAction.mockClear();
    cleanup();
    render(<YourBlanksPanel visitId="v1" groups={[GMERGED, GB]} onChanged={() => {}} />);
    fireEvent.click(screen.getByTestId('your-blanks-insert-all'));
    await waitFor(() => expect(insertAction).toHaveBeenCalledTimes(3));
    expect(insertAction.mock.calls.map((c) => (c as unknown[])[1])).toEqual([
      A_ID,
      C_ID,
      B_ID,
    ]);
  });

  it('⚠️ and it loops ONLY over what is INSERTABLE, never an already-inserted field', () => {
    // A doctor who has already inserted one group's field must not have it
    // re-asserted by "Insert all" — the loop covers un-inserted fields only,
    // and the summary counts only groups with work left.
    insertAction.mockClear();
    cleanup();
    render(
      <YourBlanksPanel
        visitId="v1"
        groups={[{ ...GA, insertedFieldIds: [A_ID] }, GB, { ...GB, fieldIds: [C_ID], labels: ['Findings'] }]}
        onChanged={() => {}}
      />,
    );
    // GA is fully inserted, so it is not one of the "blanks".
    expect(screen.getByTestId('your-blanks-summary').textContent).toBe('2 blanks — review');
    fireEvent.click(screen.getByTestId('your-blanks-insert-all'));
    return waitFor(() => {
      expect(insertAction).toHaveBeenCalledTimes(2);
      expect(insertAction.mock.calls.map((c) => (c as unknown[])[1])).toEqual([B_ID, C_ID]);
    });
  });

  it('⚠️ and it is not offered when every field is already inserted', () => {
    cleanup();
    render(
      <YourBlanksPanel
        visitId="v1"
        groups={[{ ...GA, insertedFieldIds: [A_ID] }]}
        onChanged={() => {}}
      />,
    );
    expect(screen.queryByTestId('your-blanks-insert-all')).toBeNull();
  });
});

describe('⚠️ UNDO — it calls the UNDO action, once per inserted field, with the right arguments', () => {
  // ⚠️ THIS BLOCK EXISTS BECAUSE AN ADVERSARIAL PASS FOUND THE UNDO HAD ZERO
  // EXECUTABLE COVERAGE, CLIENT OR SERVER, while this file's own header
  // advertised an "undo block". Both gate files stayed green while the Undo
  // button silently re-asserted the default instead of removing it.
  it('sends visitId and the field id to undoScaffoldDefaultAction, not the insert', async () => {
    undoAction.mockClear();
    insertAction.mockClear();
    cleanup();
    render(
      <YourBlanksPanel
        visitId="v-99"
        groups={[{ ...GA, insertedFieldIds: [A_ID] }]}
        onChanged={() => {}}
      />,
    );
    expand();
    fireEvent.click(screen.getByTestId(`your-blanks-undo-${A_ID}`));
    await waitFor(() => expect(undoAction).toHaveBeenCalledOnce());
    expect(undoAction.mock.calls[0]).toEqual(['v-99', A_ID]);
    // ⚠️ AND IT IS NOT THE INSERT. The two actions differ by one word at the
    // call site, and the failure mode is an Undo button that re-asserts.
    expect(insertAction).not.toHaveBeenCalled();
  });

  it('a fully-inserted MERGED group undoes once per inserted field id, in order', async () => {
    undoAction.mockClear();
    cleanup();
    render(
      <YourBlanksPanel
        visitId="v-99"
        groups={[{ ...GMERGED, insertedFieldIds: [A_ID, C_ID] }]}
        onChanged={() => {}}
      />,
    );
    expand();
    fireEvent.click(screen.getByTestId(`your-blanks-undo-${A_ID}`));
    await waitFor(() => expect(undoAction).toHaveBeenCalledTimes(2));
    expect(undoAction.mock.calls.map((c) => (c as unknown[])[1])).toEqual([A_ID, C_ID]);
  });
});

describe('⚠️ the document is re-fetched, or the doctor makes the change twice', () => {
  it('calls onChanged after a successful insert', async () => {
    const onChanged = vi.fn();
    insertAction.mockClear();
    cleanup();
    render(<YourBlanksPanel visitId="v1" groups={[GA]} onChanged={onChanged} />);
    expand();
    fireEvent.click(screen.getByTestId(`your-blanks-insert-${A_ID}`));
    await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  });

  it('⚠️ and does NOT on a total refusal — a redrawn page would read as success', async () => {
    const onChanged = vi.fn();
    insertAction.mockClear();
    insertAction.mockResolvedValueOnce({ ok: false, error: 'nope' } as never);
    cleanup();
    render(<YourBlanksPanel visitId="v1" groups={[GA]} onChanged={onChanged} />);
    expand();
    fireEvent.click(screen.getByTestId(`your-blanks-insert-${A_ID}`));
    await waitFor(() => expect(insertAction).toHaveBeenCalled());
    expect(onChanged).not.toHaveBeenCalled();
  });
});
