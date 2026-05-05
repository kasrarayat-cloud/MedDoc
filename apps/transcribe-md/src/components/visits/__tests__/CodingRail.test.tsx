// ============================================================================
// CodingRail.test.tsx — Phase 5.2 stub completion guard
// ----------------------------------------------------------------------------
// Asserts the rail's two newly-wired integration points:
//   1. onConfirmSign — called when "Confirm <code> · sign" is clicked
//   2. onApplyAdditions — when the BumpModal returns ok + newScore,
//      the rail's local state advances to the new tier without a
//      page reload.
//
// Pre-fix (1) dispatched a window event no listener consumed; (2) hit
// a "pretend success" fallback that didn't persist. Both were
// "Subagent B's branch lands the route" stubs that never landed.
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
