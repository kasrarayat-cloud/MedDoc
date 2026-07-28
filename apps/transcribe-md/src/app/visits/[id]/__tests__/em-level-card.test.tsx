// ============================================================================
// <EmLevelCard> — the documentation level, and the right to disagree with it.
// ----------------------------------------------------------------------------
// Every rule the rehomed override states was previously pinned by grepping the
// component's SOURCE, or by an E2E that skips itself when psql seeding is
// unavailable. Neither renders the thing. A source grep passes on a component
// that throws on mount, and a skipped test passes on anything at all.
//
// So: mount it, drive it, and assert what a doctor would see.
// ============================================================================

import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import { EmLevelCard } from '../em-level-card';

const noop = async () => ({ ok: true });

describe('EmLevelCard', () => {
  it('renders NOTHING when there is no level — an imaging report has none', () => {
    // The null-guard is the whole reason an ultrasound visit does not show an
    // office code here. Asserted by rendering, not by grepping for the `if`.
    const { container } = render(
      <EmLevelCard level={null} disabled={false} onAdjust={noop} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('states the level and offers to change it', () => {
    render(<EmLevelCard level="99213" disabled={false} onAdjust={noop} />);
    expect(screen.getByTestId('em-level-current').textContent).toBe('99213');
    expect(screen.getByTestId('em-level-adjust')).toBeTruthy();
    // Nothing is open until asked.
    expect(screen.queryByTestId('em-level-select')).toBeNull();
  });

  it('the adjust affordance is absent to a doctor who cannot use it', () => {
    render(<EmLevelCard level="99213" disabled onAdjust={noop} />);
    expect(
      (screen.getByTestId('em-level-adjust') as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it('SAVE IS NOT ARMED until the change is real AND a reason is given', () => {
    // Not a validation message after the fact: the control simply is not live
    // yet, so there is nothing to be told off about.
    render(<EmLevelCard level="99213" disabled={false} onAdjust={noop} />);
    fireEvent.click(screen.getByTestId('em-level-adjust'));

    const save = () => screen.getByTestId('em-level-save') as HTMLButtonElement;
    expect(save().disabled).toBe(true); // nothing changed, no reason

    fireEvent.change(screen.getByTestId('em-level-select'), {
      target: { value: '99214' },
    });
    expect(save().disabled).toBe(true); // changed, still no reason

    fireEvent.change(screen.getByTestId('em-level-reason'), {
      target: { value: 'Exam and MDM documented at this level.' },
    });
    expect(save().disabled).toBe(false);

    // A reason with no change is not a change.
    fireEvent.change(screen.getByTestId('em-level-select'), {
      target: { value: '99213' },
    });
    expect(save().disabled).toBe(true);
  });

  it('whitespace is not a reason', () => {
    render(<EmLevelCard level="99213" disabled={false} onAdjust={noop} />);
    fireEvent.click(screen.getByTestId('em-level-adjust'));
    fireEvent.change(screen.getByTestId('em-level-select'), {
      target: { value: '99214' },
    });
    fireEvent.change(screen.getByTestId('em-level-reason'), {
      target: { value: '   ' },
    });
    expect((screen.getByTestId('em-level-save') as HTMLButtonElement).disabled).toBe(true);
  });

  it('passes the trimmed code and reason to the caller', async () => {
    const onAdjust = vi.fn().mockResolvedValue({ ok: true });
    render(<EmLevelCard level="99213" disabled={false} onAdjust={onAdjust} />);
    fireEvent.click(screen.getByTestId('em-level-adjust'));
    fireEvent.change(screen.getByTestId('em-level-select'), {
      target: { value: '99212' },
    });
    fireEvent.change(screen.getByTestId('em-level-reason'), {
      target: { value: '  Straightforward visit.  ' },
    });
    fireEvent.click(screen.getByTestId('em-level-save'));

    await waitFor(() => expect(onAdjust).toHaveBeenCalledTimes(1));
    expect(onAdjust).toHaveBeenCalledWith('99212', 'Straightforward visit.');
  });

  it('A FAILED SAVE KEEPS THE FORM OPEN WITH THE DOCTOR’S WORDS IN IT', async () => {
    // Closing on failure discards what they typed and shows the old level as
    // though nothing had been attempted.
    const onAdjust = vi
      .fn()
      .mockResolvedValue({ ok: false, error: 'That level could not be saved.' });
    render(<EmLevelCard level="99213" disabled={false} onAdjust={onAdjust} />);
    fireEvent.click(screen.getByTestId('em-level-adjust'));
    fireEvent.change(screen.getByTestId('em-level-select'), {
      target: { value: '99214' },
    });
    fireEvent.change(screen.getByTestId('em-level-reason'), {
      target: { value: 'Time documented.' },
    });
    fireEvent.click(screen.getByTestId('em-level-save'));

    await waitFor(() =>
      expect(screen.getByTestId('em-level-error').textContent).toMatch(/could not be saved/i),
    );
    expect((screen.getByTestId('em-level-reason') as HTMLTextAreaElement).value).toBe(
      'Time documented.',
    );
    expect((screen.getByTestId('em-level-select') as HTMLSelectElement).value).toBe('99214');
  });

  it('SAYS SO when the level moves while the form is open', async () => {
    // The picker used to silently keep the old selection, so a doctor could be
    // looking at "changing 99213 → 99214" while the level had already become
    // 99215 — and save a move away from a level that was never current.
    const { rerender } = render(
      <EmLevelCard level="99213" disabled={false} onAdjust={noop} />,
    );
    fireEvent.click(screen.getByTestId('em-level-adjust'));
    fireEvent.change(screen.getByTestId('em-level-reason'), {
      target: { value: 'Reason typed before the level moved.' },
    });

    rerender(<EmLevelCard level="99215" disabled={false} onAdjust={noop} />);

    expect(screen.getByTestId('em-level-moved').textContent).toMatch(/changed to 99215/);
    // Their words survive; the picker follows the new level.
    expect((screen.getByTestId('em-level-reason') as HTMLTextAreaElement).value).toBe(
      'Reason typed before the level moved.',
    );
    expect((screen.getByTestId('em-level-select') as HTMLSelectElement).value).toBe('99215');
    // And saving is not armed, because "99215 → 99215" is not a change.
    expect((screen.getByTestId('em-level-save') as HTMLButtonElement).disabled).toBe(true);
  });

  it('follows the level when it moves while the form is CLOSED', () => {
    const { rerender } = render(
      <EmLevelCard level="99213" disabled={false} onAdjust={noop} />,
    );
    rerender(<EmLevelCard level="99214" disabled={false} onAdjust={noop} />);
    expect(screen.getByTestId('em-level-current').textContent).toBe('99214');
    // No "it moved" notice when nobody was mid-edit.
    expect(screen.queryByTestId('em-level-moved')).toBeNull();
  });

  it('NO REVENUE FRAMING AND NO DIRECTION in what it actually renders', () => {
    // The lexical guard in review-read-only-paper.test.ts reads the source. This
    // reads the DOM, and it reads it twice — once adjusting up, once down — and
    // requires the two to differ only by the codes themselves. A surface that
    // dresses one direction up as better is asking the doctor to document for
    // the number rather than number the documentation.
    const textFor = (level: string, target: string) => {
      const { container, unmount } = render(
        <EmLevelCard level={level} disabled={false} onAdjust={noop} />,
      );
      fireEvent.click(screen.getByTestId('em-level-adjust'));
      fireEvent.change(screen.getByTestId('em-level-select'), {
        target: { value: target },
      });
      const t = container.textContent ?? '';
      unmount();
      return t;
    };

    const up = textFor('99213', '99214');
    const down = textFor('99214', '99213');

    for (const banned of [
      /revenue/i,
      /reimburse/i,
      /\bup from\b/i,
      /\bdown from\b/i,
      /\bhigher\b/i,
      /\blower\b/i,
      /\bsupports\b/i,
      /\brvu/i,
      /[$£€]\s?\d/,
    ]) {
      expect(up, `framing in the upward case: ${banned}`).not.toMatch(banned);
      expect(down, `framing in the downward case: ${banned}`).not.toMatch(banned);
    }

    // Identical once the codes are removed — the copy cannot be telling the
    // doctor anything about direction if this holds.
    const skeleton = (s: string) => s.replace(/\b992\d\d\b/g, '#');
    expect(skeleton(up)).toBe(skeleton(down));
  });
});
