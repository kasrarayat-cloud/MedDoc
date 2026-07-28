// ============================================================================
// CodingRail.test.tsx — Phase 5.2 stub completion + orphan-completion guard
// ----------------------------------------------------------------------------
// Asserts the rail's wired integration points:
//   1. onConfirmSign — called when "Confirm <code> · sign" is clicked
//      (PR #132 — fixed Bug A from the original two-bug pair)
//   2. onApplyAdditions — when the BumpModal returns ok + newScore,
//      the rail's local state advances to the new tier without a
//      page reload (PR #132 — fixed Bug B)
//   3. onApplyOverride — when the doctor picks an override code, the
//      rail calls the parent persistence handler instead of
//      dispatching a window event no listener consumed (this PR —
//      fixed F-01 from the QA agent's 20260505T230801Z report)
//   4. Bump-CTA highlight — clicking "Bump to 99214" calls
//      onHighlightCriteria with the gap criterion ids (this PR —
//      fixed F-02)
// ============================================================================

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() },
}));

import { CodingRail } from '../CodingRail';
import type { EmScore } from '@/lib/em-coding-ui/types';

function emScoreFixture(overrides: Partial<EmScore> = {}): EmScore {
  return {
    suggestedCode: '99213',
    visitType: 'established',
    mdmTier: 'low',
    llmJudged: false,
    confidence: 0.85,
    timeBand: { code: '99213', min: 1200, max: 1740 },
    visitTimeSec: 900,
    groups: [
      {
        id: 'history',
        title: 'History (HPI)',
        summary: '2 of 3 satisfied',
        items: [],
      },
      { id: 'exam', title: 'Exam', summary: '2 systems', items: [] },
      {
        id: 'mdm',
        title: 'Medical Decision Making',
        summary: 'Low tier (2 of 4)',
        items: [],
      },
    ],
    bump: {
      mode: 'almost-there',
      toCode: '99214',
      gaps: [
        {
          criterionId: 'hpi.elements',
          label: 'HPI: 3 of 4 elements',
          suggestion: 'e.g. "Severity 6/10..."',
        },
      ],
      revenueDelta: 32,
    },
    computedAt: new Date().toISOString(),
    ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe('CodingRail — onConfirmSign wiring (Bug 1)', () => {
  it('calls onConfirmSign when the Confirm-sign button is clicked', () => {
    const onConfirmSign = vi.fn();
    render(
      <CodingRail
        emScore={emScoreFixture()}
        visitId="v1"
        readonly={false}
        onConfirmSign={onConfirmSign}
      />,
    );
    // Button label format: "✓ Confirm 99213 · sign  ⌘ ↵"
    const btn = screen.getByRole('button', { name: /Confirm 99213 · sign/i });
    fireEvent.click(btn);
    expect(onConfirmSign).toHaveBeenCalledTimes(1);
  });

  it('hides the Confirm-sign button when onConfirmSign is undefined', () => {
    render(
      <CodingRail
        emScore={emScoreFixture()}
        visitId="v1"
        readonly={false}
      />,
    );
    expect(
      screen.queryByRole('button', { name: /Confirm 99213 · sign/i }),
    ).toBeNull();
  });

  it('hides the Confirm-sign button entirely when readonly (no CTA block)', () => {
    const onConfirmSign = vi.fn();
    render(
      <CodingRail
        emScore={emScoreFixture()}
        visitId="v1"
        readonly={true}
        onConfirmSign={onConfirmSign}
      />,
    );
    // The whole CTA block (BumpCta + Confirm) is gated by !readonly.
    expect(
      screen.queryByRole('button', { name: /Confirm 99213 · sign/i }),
    ).toBeNull();
  });
});

describe('CodingRail — onApplyOverride wiring (Bug F-01)', () => {
  it('calls onApplyOverride with the picked CPT code', async () => {
    const onApplyOverride = vi
      .fn()
      .mockResolvedValue({ ok: true, newScore: undefined });
    render(
      <CodingRail
        emScore={emScoreFixture()}
        visitId="v1"
        readonly={false}
        onApplyOverride={onApplyOverride}
      />,
    );
    // Open the override listbox.
    fireEvent.click(screen.getByRole('button', { name: /override/i }));
    // Pick 99214 from the listbox — the option is an <li> wrapping a
    // <button>; firing on the button is what triggers handleOverrideSelect.
    const opt = screen.getByRole('option', { name: '99214' });
    fireEvent.click(opt.querySelector('button') as HTMLButtonElement);

    // The override picker now awaits the async persistence call.
    await Promise.resolve();
    expect(onApplyOverride).toHaveBeenCalledTimes(1);
    expect(onApplyOverride).toHaveBeenCalledWith('99214');
  });

  it('updates local score when onApplyOverride resolves with a newScore', async () => {
    const newScore = emScoreFixture({
      override: {
        code: '99214',
        reason: 'Higher MDM than the AI captured.',
        overriddenAt: new Date().toISOString(),
      },
    });
    const onApplyOverride = vi
      .fn()
      .mockResolvedValue({ ok: true, newScore });
    render(
      <CodingRail
        emScore={emScoreFixture()}
        visitId="v1"
        readonly={false}
        onApplyOverride={onApplyOverride}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /override/i }));
    fireEvent.click(
      screen
        .getByRole('option', { name: '99214' })
        .querySelector('button') as HTMLButtonElement,
    );

    // The doctor-set badge appears once score.override is populated —
    // the rail awaits onApplyOverride then setScore, so use findByText
    // to wait through the React batch update.
    expect(await screen.findByText(/doctor-set/i)).toBeInTheDocument();
  });

  it('keeps the prior score and shows an error toast when onApplyOverride returns ok:false', async () => {
    const { toast } = await import('sonner');
    const onApplyOverride = vi.fn().mockResolvedValue({
      ok: false,
      error: 'Server unhappy: 503',
    });
    render(
      <CodingRail
        emScore={emScoreFixture()}
        visitId="v1"
        readonly={false}
        onApplyOverride={onApplyOverride}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: /override/i }));
    fireEvent.click(
      screen
        .getByRole('option', { name: '99214' })
        .querySelector('button') as HTMLButtonElement,
    );

    await Promise.resolve();
    await Promise.resolve();

    // Real error toast (no more lying success toast).
    expect(toast.error).toHaveBeenCalledWith('Server unhappy: 503');
    // Original code still displayed.
    expect(screen.queryByText(/doctor-set/i)).toBeNull();
  });

  it('DRAWS NO OVERRIDE CONTROL AT ALL when no parent handler is wired', () => {
    // This used to assert that clicking the unwired dropdown produced an
    // "Override is not wired — reload or contact support" toast. That was the
    // best available answer while the rail was the override's home: better a
    // real error than a lying success toast (Bug F-01).
    //
    // It is the wrong answer now. The override moved to the review page's gate
    // stack, which is the only surface that can collect the reason the route
    // requires, so the rail is deliberately passed no handler — and a control
    // that renders only to tell the doctor their browser is broken is worse
    // than no control. Absent is the honest rendering, and it is what keeps a
    // reasonless caller from existing at all.
    render(<CodingRail emScore={emScoreFixture()} visitId="v1" readonly={false} />);

    expect(screen.queryByRole('button', { name: /override/i })).toBeNull();
    expect(screen.queryByRole('option', { name: '99214' })).toBeNull();
  });

  it('still draws it when a handler IS wired — the rail is not dead, just unwired here', () => {
    // The negative control for the test above: absence must be caused by the
    // missing handler, not by the dropdown having been deleted outright.
    render(
      <CodingRail
        emScore={emScoreFixture()}
        visitId="v1"
        readonly={false}
        onApplyOverride={vi.fn().mockResolvedValue({ ok: true })}
      />,
    );

    expect(screen.getByRole('button', { name: /override/i })).toBeTruthy();
  });
});

describe('CodingRail — bump-CTA highlight wiring (Bug F-02)', () => {
  it('forwards gap criterion ids to onHighlightCriteria when the bump CTA is clicked', () => {
    const onHighlightCriteria = vi.fn();
    render(
      <CodingRail
        emScore={emScoreFixture()}
        visitId="v1"
        readonly={false}
        onHighlightCriteria={onHighlightCriteria}
      />,
    );
    // The bump CTA button mirrors the v6 mockup — name pattern
    // "Bump from 99213 to 99214, revenue delta +$32" via aria-label.
    const btn = screen.getByRole('button', { name: /bump from 99213 to 99214/i });
    fireEvent.click(btn);
    expect(onHighlightCriteria).toHaveBeenCalledTimes(1);
    expect(onHighlightCriteria).toHaveBeenCalledWith(['hpi.elements']);
  });

  it('silently no-ops when onHighlightCriteria is undefined', () => {
    render(
      <CodingRail
        emScore={emScoreFixture()}
        visitId="v1"
        readonly={false}
      />,
    );
    // Clicking should not throw; the modal still opens.
    const btn = screen.getByRole('button', { name: /bump from 99213 to 99214/i });
    expect(() => fireEvent.click(btn)).not.toThrow();
  });
});
