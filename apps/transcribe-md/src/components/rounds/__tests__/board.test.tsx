// ============================================================================
// The Board renders what the row model says, and nothing else.
// ----------------------------------------------------------------------------
// The row model is already unit-tested (lib/rounds/__tests__/board-data). What
// these pin is the RENDERING contract — the parts a reader of the code cannot
// verify by inspection because they are spread across branches:
//
//   - a card sits in the column its lane is actually at
//   - each of the five lane kinds gets its own treatment
//   - a critical lane tints the ROW, not just the card
//   - RETRY exists on failed lanes and NOWHERE else
//   - the empty state is an invitation, not a shrug
// ============================================================================

import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';

import { RoundsBoard } from '../board';
import { toBoardLane } from '@/lib/rounds/board-data';

const base = {
  id: 'v1',
  patientName: 'Aisha Rahman',
  patientFallback: null,
  specialty: 'primary-care',
  status: 'READY',
  createdAt: '2026-07-29T09:00:00.000Z',
  signedAt: null,
  audioDurationSec: 300,
};

const lane = (over: Partial<Parameters<typeof toBoardLane>[0]>) =>
  toBoardLane({ ...base, ...over });

describe('the empty state invites', () => {
  it('offers the next action rather than describing the absence', () => {
    render(<RoundsBoard lanes={[]} />);
    expect(screen.getByTestId('rounds-board-empty')).toBeTruthy();
    // The thing a doctor would want to do next, as a real link.
    expect(screen.getByRole('link', { name: /start a visit/i })).toBeTruthy();
  });
});

describe('lane kinds each get their own treatment', () => {
  it.each([
    ['READY', null, 'ready'],
    ['QUEUED', null, 'recording'],
    ['POLISHING', null, 'processing'],
    ['FAILED', null, 'failed'],
    ['SIGNED', '2026-07-29T08:52:00.000Z', 'signed'],
  ])('%s renders as %s', (status, signedAt, kind) => {
    render(<RoundsBoard lanes={[lane({ status, signedAt })]} />);
    const card = screen.getByTestId('rounds-lane-card-v1');
    expect(card.getAttribute('data-lane-kind')).toBe(kind);
  });

  it('a signed card carries its time, because "when" is the useful part', () => {
    render(
      <RoundsBoard
        lanes={[lane({ status: 'SIGNED', signedAt: '2026-07-29T08:52:00.000Z' })]}
      />,
    );
    expect(screen.getByText(/signed 8:52/i)).toBeTruthy();
  });

  it('a recording lane shows REC', () => {
    render(<RoundsBoard lanes={[lane({ status: 'QUEUED' })]} />);
    expect(screen.getByText('REC')).toBeTruthy();
  });
});

describe('critical lanes are findable', () => {
  const criticalLane = lane({
    rxDrafts: {
      warnings: [{ severity: 'critical', drugA: 'warfarin', drugB: 'amiodarone' }],
    },
  });

  it('marks the card AND names the interaction on one line', () => {
    render(<RoundsBoard lanes={[criticalLane]} />);
    const card = screen.getByTestId('rounds-lane-card-v1');
    expect(card.getAttribute('data-critical')).toBe('true');
    expect(screen.getByText('warfarin + amiodarone')).toBeTruthy();
  });

  it('the accessible name says critical — not colour alone', () => {
    // A red border is invisible to a screen reader and to a greyscale printout.
    render(<RoundsBoard lanes={[criticalLane]} />);
    expect(
      screen.getByRole('link', { name: /critical interaction/i }),
    ).toBeTruthy();
  });

  it('a critical with NO readable payload shows no line rather than a made-up one', () => {
    render(
      <RoundsBoard lanes={[lane({ rxDrafts: { warnings: [{ severity: 'critical' }] } })]} />,
    );
    const card = screen.getByTestId('rounds-lane-card-v1');
    expect(card.getAttribute('data-critical')).toBe('true');
    // Nothing invented to fill the space.
    expect(card.textContent).not.toMatch(/interaction|warning|check/i);
  });
});

describe('RETRY belongs to failed lanes and nowhere else', () => {
  it('appears on a failed lane', () => {
    render(<RoundsBoard lanes={[lane({ status: 'FAILED' })]} />);
    expect(screen.getByTestId('rounds-retry-v1')).toBeTruthy();
  });

  it.each(['READY', 'QUEUED', 'POLISHING', 'SIGNED'])(
    'does NOT appear on %s',
    (status) => {
      render(
        <RoundsBoard
          lanes={[lane({ status, signedAt: status === 'SIGNED' ? base.createdAt : null })]}
        />,
      );
      expect(screen.queryByTestId('rounds-retry-v1')).toBeNull();
    },
  );
});

describe('the matrix actually positions', () => {
  it('a card sits in the column its stage says, not the first one', () => {
    // The whole reason this is a matrix and not a list. If every card rendered
    // in column 1 the screen would still "look right" in a screenshot.
    const { container } = render(
      <RoundsBoard lanes={[lane({ status: 'DRAFTING' })]} />,
    );
    const row = container.querySelector('[data-testid="rounds-lane-v1"] .qm-rounds-board-grid')!;
    const cells = Array.from(row.children);
    expect(cells).toHaveLength(5);
    // 'DRAFTING' is stage 3 → index 2.
    expect(within(cells[2] as HTMLElement).getByTestId('rounds-lane-card-v1')).toBeTruthy();
    expect(cells[0].children.length).toBe(0);
  });

  it('column counts reflect where cards actually are', () => {
    render(
      <RoundsBoard
        lanes={[
          lane({ id: 'a', status: 'DRAFTING' }),
          lane({ id: 'b', status: 'DRAFTING' }),
          lane({ id: 'c', status: 'READY' }),
        ]}
      />,
    );
    expect(screen.getByTestId('rounds-stage-count-drafted').textContent).toBe('2');
    expect(screen.getByTestId('rounds-stage-count-ready').textContent).toBe('1');
    expect(screen.getByTestId('rounds-stage-count-captured').textContent).toBe('0');
  });

  it('a signed lane parks at the end of the run', () => {
    const { container } = render(
      <RoundsBoard
        lanes={[lane({ status: 'SIGNED', signedAt: '2026-07-29T08:52:00.000Z' })]}
      />,
    );
    const cells = Array.from(
      container.querySelector('[data-testid="rounds-lane-v1"] .qm-rounds-board-grid')!.children,
    );
    expect(within(cells[4] as HTMLElement).getByTestId('rounds-lane-card-v1')).toBeTruthy();
  });

  it('a failed lane parks where it died, not at the end', () => {
    const { container } = render(
      <RoundsBoard lanes={[lane({ status: 'FAILED', lastKnownStatus: 'TRANSCRIBING' })]} />,
    );
    const cells = Array.from(
      container.querySelector('[data-testid="rounds-lane-v1"] .qm-rounds-board-grid')!.children,
    );
    // Stage 2 → index 1.
    expect(within(cells[1] as HTMLElement).getByTestId('rounds-lane-card-v1')).toBeTruthy();
  });
});

describe('the legend explains every marker it uses', () => {
  it('names all five', () => {
    render(<RoundsBoard lanes={[lane({})]} />);
    const legend = screen.getByTestId('rounds-board-legend');
    for (const label of ['Ready', 'Recording', 'Processing', 'Critical', 'Signed']) {
      expect(within(legend).getByText(label)).toBeTruthy();
    }
  });
});
