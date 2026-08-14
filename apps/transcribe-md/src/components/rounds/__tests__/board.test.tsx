// ============================================================================
// The Board renders what the row model says, and nothing else.
// ----------------------------------------------------------------------------
// The row model is already unit-tested (lib/rounds/__tests__/board-data). What
// these pin is the RENDERING contract — the parts a reader of the code cannot
// verify by inspection because they are spread across branches:
//
//   - a card sits in the column its lane is actually at
//   - each of the five lane kinds gets its own treatment
//   - RETRY exists on failed lanes and NOWHERE else
//   - the empty state is an invitation, not a shrug
// ============================================================================

import { describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';

// The retry affordance is a CLIENT component that calls router.refresh() after
// a successful retry — it needs the app router, which is not mounted in a bare
// render. Mocked rather than avoided, because the alternative (a form POST to a
// JSON route) is the bug this component exists to fix.
vi.mock('next/navigation', () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

import { RoundsBoard, cardEntranceDelayMs } from '../board';
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
    //
    // ⚠️ R2 RENAMED THIS FROM "Start a visit", and the expected value moved by
    // hand so the rename could not happen silently. SPEC.md's copy register is
    // "actions keep their names end-to-end": `/visits/new` is reached from
    // `/patients`, `/visits` and a patient's own page, and all three call it
    // "New visit". This surface was the only one using a different verb.
    const cta = screen.getByRole('link', { name: /new visit/i });
    expect(cta).toBeTruthy();
    expect(cta.getAttribute('href')).toBe('/visits/new');

    // AND THE OLD NAME IS GONE, not merely joined. Without this a card
    // rendering BOTH labels would satisfy the assertion above while leaving the
    // fourth name on screen — the exact "did the change land, or did it only
    // get added?" question a positive-only check cannot answer.
    expect(screen.queryByRole('link', { name: /start a visit/i })).toBeNull();
  });

  it('⚠️ the empty-state CTA does NOT register the keyboard shortcut', () => {
    // The board's top bar owns the `n` key. Two document-level listeners on one
    // key means one press queues two navigations, and a hint rendered without
    // the listener would promise a handler that is not there — the orphaned
    // "[E]" defect the action rail already paid for once.
    render(<RoundsBoard lanes={[]} />);
    const cta = screen.getByRole('link', { name: /new visit/i });
    expect(cta.getAttribute('data-shortcut')).toBeNull();
    expect(cta.querySelector('kbd')).toBeNull();
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

describe('THE SURFACE IS GONE — owner ruling #109', () => {
  // Replaces `critical lanes are findable` (3 tests: the data-critical marker,
  // the accessible name, and "no readable payload composes no line"). This is
  // the positive control for the DELETION — proving the marker is absent is
  // worth more than deleting the tests that asserted it was present, because a
  // half-applied removal leaves the attribute behind on a board nothing tints.
  it('no lane advertises a critical interaction any more', () => {
    render(<RoundsBoard lanes={[lane({})]} />);
    const card = screen.getByTestId('rounds-lane-card-v1');
    expect(card.getAttribute('data-critical')).toBeNull();
    expect(card.textContent).not.toMatch(/interaction/i);
    expect(screen.queryByRole('link', { name: /critical/i })).toBeNull();
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
  it('names all four', () => {
    render(<RoundsBoard lanes={[lane({})]} />);
    const legend = screen.getByTestId('rounds-board-legend');
    for (const label of ['Ready', 'Recording', 'Processing', 'Signed']) {
      expect(within(legend).getByText(label)).toBeTruthy();
    }
  });

  // ⚠️ AND THE OTHER DIRECTION, WHICH IS WHY THIS TEST'S TITLE WAS FALSE WHILE
  // IT PASSED. It asserted the legend NAMES five markers and never asserted the
  // legend names nothing it cannot draw. Owner ruling #109 removed every
  // producer of the red-bordered lane — the border, the ⚠ glyph, the
  // interaction line, the row tint, `criticalCount`, the `critical` filter —
  // and the legend kept advertising it. `tsc` could not see it: `items` is
  // typed `{ key: string }`, not `BoardFilter`.
  //
  // "Explains every marker it USES" is a claim in both directions. Now it is
  // tested in both.
  it('and names NOTHING it can no longer draw', () => {
    render(<RoundsBoard lanes={[lane({})]} />);
    const legend = screen.getByTestId('rounds-board-legend');
    expect(within(legend).queryByText('Critical')).toBeNull();
    expect(legend.textContent).not.toMatch(/critical|interaction/i);
  });
});

// ============================================================================
// RETRY MUST CALL THE API, NOT NAVIGATE TO IT.
// ----------------------------------------------------------------------------
// The board's first cut used <form action="/api/visits/[id]/retry" method="post">.
// That route exists and accepts POST — but it is a JSON API route. A native
// form submit would have NAVIGATED the browser to a page showing a JSON blob:
// the button appears to work, the board vanishes, and the doctor is staring at
// {"ok":true}. Nothing throws, and a screenshot of the click looks fine.
//
// Caught by verifying the route instead of trusting the convention. Pinned here
// so it cannot come back as a "simplification".
// ============================================================================

import { fireEvent, waitFor } from '@testing-library/react';

describe('retry integrates with the JSON route correctly', () => {
  it('is a BUTTON, not a form submit that would navigate away', () => {
    render(<RoundsBoard lanes={[lane({ status: 'FAILED' })]} />);
    const btn = screen.getByTestId('rounds-retry-v1');
    expect(btn.tagName).toBe('BUTTON');
    expect(btn.getAttribute('type')).toBe('button');
    // The killer: no ancestor form pointed at the JSON route.
    expect(btn.closest('form')).toBeNull();
  });

  it('POSTs to the route and refreshes', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal('fetch', fetchMock);
    render(<RoundsBoard lanes={[lane({ status: 'FAILED' })]} />);
    fireEvent.click(screen.getByTestId('rounds-retry-v1'));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/visits/v1/retry');
    expect(init.method).toBe('POST');
    vi.unstubAllGlobals();
  });

  it('surfaces STILL_PROCESSING as information, not as an error to retry', async () => {
    // 409 STILL_PROCESSING means a live worker is making progress. Telling the
    // doctor "failed, try again" would invite them to duplicate a running job.
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ code: 'STILL_PROCESSING' }),
    });
    vi.stubGlobal('fetch', fetchMock);
    render(<RoundsBoard lanes={[lane({ status: 'FAILED' })]} />);
    fireEvent.click(screen.getByTestId('rounds-retry-v1'));
    await waitFor(() =>
      expect(screen.getByTestId('rounds-retry-message-v1').textContent).toMatch(
        /still processing/i,
      ),
    );
    vi.unstubAllGlobals();
  });
});

// ── R2 — the entrance stagger, and the cap that keeps it honest ────────────
describe('the entrance stagger is bounded', () => {
  it('steps 28ms per lane and STOPS at the tenth', () => {
    // The cap is the assertion, not the step. Uncapped, a 60-lane board makes
    // the last card wait 1.68s and a doctor scrolling a busy morning sees an
    // empty column — indistinguishable from a load failure.
    expect(cardEntranceDelayMs(0)).toBe(0);
    expect(cardEntranceDelayMs(1)).toBe(28);
    expect(cardEntranceDelayMs(9)).toBe(252);
    expect(cardEntranceDelayMs(10)).toBe(280);

    // Everything past the tenth starts WITH the tenth.
    expect(cardEntranceDelayMs(11)).toBe(280);
    expect(cardEntranceDelayMs(60)).toBe(280);
    expect(cardEntranceDelayMs(5000)).toBe(280);

    // NON-VACUITY: a function that returned 280 for everything would satisfy
    // every cap assertion above. The early values must actually differ.
    expect(cardEntranceDelayMs(0)).not.toBe(cardEntranceDelayMs(1));
  });

  it('the whole run is under a third of a second, however long the board', () => {
    // A ceiling stated as a duration rather than as a step count, so changing
    // the step without re-thinking the cap trips here.
    expect(cardEntranceDelayMs(Number.MAX_SAFE_INTEGER)).toBeLessThanOrEqual(300);
  });

  it('every card carries the class the motion and states are defined on', () => {
    // The hover lift, the pressed state, the focus ring and the entrance are
    // all `[data-skin="rounds"] .qm-rounds-lane-card` rules in
    // rounds-tokens.css. A card rendered without the class silently loses all
    // four — and no rendering assertion elsewhere would notice, because the
    // inline colours are what the other tests read.
    render(<RoundsBoard lanes={[lane({ status: 'READY' })]} />);
    const card = screen.getByTestId('rounds-lane-card-v1');
    expect(card.className).toContain('qm-rounds-lane-card');
    // And the per-card delay reached the DOM, or the stagger is dead code.
    expect(card.getAttribute('style')).toMatch(/animation-delay:\s*0ms/);
  });
});
