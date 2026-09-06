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
// ⚠️ WHAT WOULD MAKE THIS FILE FAIL:
//   · the panel appears with nothing to offer     -> the emptiness block
//   · "Insert all" stops being a LOOP             -> the bulk block
//   · an already-inserted default offers INSERT
//     instead of UNDO                             -> the row block
//   · the compiled scaffold text stops being shown -> the row block
//   · a row's button sends the WRONG field id     -> the row block
//   · Undo calls INSERT instead of undo           -> the undo block
//   · a refusal still refetches the document      -> the refetch block
// ============================================================================

import { describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';

vi.mock('sonner', () => ({
  toast: Object.assign(vi.fn(), { success: vi.fn(), error: vi.fn(), warning: vi.fn() }),
}));

const insertAction = vi.fn(async () => ({ ok: true }));
const undoAction = vi.fn(async () => ({ ok: true }));
vi.mock('@/actions/set-template-control', () => ({
  insertScaffoldDefaultAction: (...a: unknown[]) => insertAction(...(a as [])),
  undoScaffoldDefaultAction: (...a: unknown[]) => undoAction(...(a as [])),
}));

import { YourBlanksPanel, type InsertableDefault } from '../your-blanks-panel';

const A: InsertableDefault = {
  fieldId: 'ttf_aaaaaaaaaaaaaaaaaaaaaaaa',
  label: 'Impression',
  scaffoldText: 'No acute findings.',
  inserted: false,
};
const B: InsertableDefault = {
  fieldId: 'ttf_bbbbbbbbbbbbbbbbbbbbbbbb',
  label: 'Technique',
  scaffoldText: 'Standard protocol followed.',
  inserted: false,
};

describe('⚠️ nothing is drawn when there is nothing to offer', () => {
  it('renders null on an empty list', () => {
    const { container } = render(
      <YourBlanksPanel visitId="v1" defaults={[]} onChanged={() => {}} />,
    );
    expect(container.firstChild).toBeNull();
    // An empty panel reading "no blanks with defaults" is a claim about the
    // form the doctor did not ask for, and on a form with no scaffolded
    // controls it would appear on every visit forever.
  });

  it('and DOES draw when there is — the arm above is not passing on a dead component', () => {
    render(<YourBlanksPanel visitId="v1" defaults={[A]} onChanged={() => {}} />);
    expect(screen.getByTestId('your-blanks-panel')).toBeTruthy();
  });
});

describe('⚠️ each row shows the compiled wording the doctor is being asked to assert', () => {
  it('quotes the scaffold text verbatim rather than summarising it', () => {
    render(<YourBlanksPanel visitId="v1" defaults={[A]} onChanged={() => {}} />);
    expect(screen.getByTestId(`your-blanks-text-${A.fieldId}`).textContent).toBe(
      'No acute findings.',
    );
    expect(screen.getByTestId(`your-blanks-insert-${A.fieldId}`)).toBeTruthy();
  });

  it('⚠️ the per-row button sends THAT row id and THIS visit id', async () => {
    // ⚠️ THE ARGUMENTS WERE UNASSERTED AND AN ADVERSARIAL PASS SAID SO: the
    // handler could send a fixed wrong fieldId — the FIRST row's, say — and
    // every arm here stayed green while the doctor's click landed on somebody
    // else's field. A per-field feature whose per-field argument is untested
    // is not a per-field feature.
    insertAction.mockClear();
    cleanup();
    render(<YourBlanksPanel visitId="v-42" defaults={[A, B]} onChanged={() => {}} />);
    fireEvent.click(screen.getByTestId(`your-blanks-insert-${B.fieldId}`));
    await waitFor(() => expect(insertAction).toHaveBeenCalledOnce());
    expect(insertAction.mock.calls[0]).toEqual(['v-42', B.fieldId]);
  });

  it('⚠️ an ALREADY-INSERTED default offers UNDO, never a second insert', () => {
    // The write is idempotent, so a second insert would not corrupt anything —
    // but offering it says the click did not land, and the doctor's next move
    // would be to click again rather than to undo.
    render(
      <YourBlanksPanel
        visitId="v1"
        defaults={[{ ...A, inserted: true }]}
        onChanged={() => {}}
      />,
    );
    expect(screen.getByTestId(`your-blanks-undo-${A.fieldId}`)).toBeTruthy();
    expect(screen.queryByTestId(`your-blanks-insert-${A.fieldId}`)).toBeNull();
  });
});

describe('⚠️ INSERT ALL IS A LOOP OVER PER-FIELD INSERTS, NOT A BULK WRITE', () => {
  it('calls the per-field action once PER FIELD, with that field id', async () => {
    // ⚠️ THE AUDIT ROW IS EMITTED PER FIELD. A bulk writer would collapse N
    // assertions into one and the trail could no longer say which defaults a
    // doctor actually asserted — which is the entire product claim of #194's
    // doctor-facing half. Two recorded precedents say the same thing:
    // `chat-edit/intent.ts` ("Accept all is a LOOP over per-claim adopts") and
    // the twin confirm list's own bulk control.
    insertAction.mockClear();
    render(<YourBlanksPanel visitId="v1" defaults={[A, B]} onChanged={() => {}} />);
    fireEvent.click(screen.getByTestId('your-blanks-insert-all'));
    await waitFor(() => expect(insertAction).toHaveBeenCalledTimes(2));
    expect(insertAction.mock.calls.map((c) => (c as unknown[])[1])).toEqual([
      A.fieldId,
      B.fieldId,
    ]);
  });

  it('⚠️ and it is not offered for a single blank — the count would be theatre', () => {
    cleanup();
    render(<YourBlanksPanel visitId="v1" defaults={[A]} onChanged={() => {}} />);
    expect(screen.queryByTestId('your-blanks-insert-all')).toBeNull();
  });

  it('⚠️ and it counts only what is INSERTABLE, not every row', () => {
    // A doctor who has already inserted one of three must not be offered
    // "Insert all 3 of my defaults" — the number would name work already done.
    cleanup();
    render(
      <YourBlanksPanel
        visitId="v1"
        defaults={[{ ...A, inserted: true }, B, { ...B, fieldId: 'ttf_cccccccccccccccccccccccc' }]}
        onChanged={() => {}}
      />,
    );
    expect(screen.getByTestId('your-blanks-insert-all').textContent).toContain('2');
  });
});

describe('⚠️ UNDO — it calls the UNDO action, with the right arguments', () => {
  // ⚠️ THIS BLOCK EXISTS BECAUSE AN ADVERSARIAL PASS FOUND THE UNDO HAD ZERO
  // EXECUTABLE COVERAGE, CLIENT OR SERVER, while this file's own header
  // advertised an "undo block". Both gate files stayed green while the Undo
  // button silently re-asserted the default instead of removing it.
  it('sends visitId and the row fieldId to undoScaffoldDefaultAction', async () => {
    undoAction.mockClear();
    insertAction.mockClear();
    cleanup();
    render(
      <YourBlanksPanel
        visitId="v-99"
        defaults={[{ ...A, inserted: true }]}
        onChanged={() => {}}
      />,
    );
    fireEvent.click(screen.getByTestId(`your-blanks-undo-${A.fieldId}`));
    await waitFor(() => expect(undoAction).toHaveBeenCalledOnce());
    expect(undoAction.mock.calls[0]).toEqual(['v-99', A.fieldId]);
    // ⚠️ AND IT IS NOT THE INSERT. The two actions differ by one word at the
    // call site, and the failure mode is an Undo button that re-asserts.
    expect(insertAction).not.toHaveBeenCalled();
  });
});

describe('⚠️ the document is re-fetched, or the doctor makes the change twice', () => {
  it('calls onChanged after a successful insert', async () => {
    const onChanged = vi.fn();
    cleanup();
    render(<YourBlanksPanel visitId="v1" defaults={[A]} onChanged={onChanged} />);
    fireEvent.click(screen.getByTestId(`your-blanks-insert-${A.fieldId}`));
    await waitFor(() => expect(onChanged).toHaveBeenCalledOnce());
  });

  it('⚠️ and does NOT on a refusal — a redrawn page would read as success', async () => {
    const onChanged = vi.fn();
    insertAction.mockResolvedValueOnce({ ok: false, error: 'nope' } as never);
    cleanup();
    render(<YourBlanksPanel visitId="v1" defaults={[A]} onChanged={onChanged} />);
    fireEvent.click(screen.getByTestId(`your-blanks-insert-${A.fieldId}`));
    await waitFor(() => expect(insertAction).toHaveBeenCalled());
    expect(onChanged).not.toHaveBeenCalled();
  });
});
