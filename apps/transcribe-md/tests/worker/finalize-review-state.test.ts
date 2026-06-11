// ============================================================================
// applyAdditiveReviewState — audit BLOCK-2 regression pin (2026-06-11).
// ----------------------------------------------------------------------------
// The worker's final READY write used to assign needsReview/reviewReason
// unconditionally, clobbering review state set earlier in the pipeline (the
// L6 fabrication-gate rejection banner, L6 unfixable-criticals, the 02.8
// allergy flag) whenever the L7 fan-out was clean. These tests pin the
// replacement's ADDITIVE semantics at the SQL level: needsReview can only be
// OR-ed on, reviewReason COALESCE-concatenates (existing reason first), and
// the no-op case skips the write entirely.
// ============================================================================

import { beforeEach, describe, expect, it, vi } from 'vitest';

const mocks = vi.hoisted(() => ({
  executeRaw: vi.fn(),
}));

vi.mock('@meddoc/db', () => ({
  default: {
    $executeRaw: mocks.executeRaw,
  },
}));

import { applyAdditiveReviewState } from '@/worker/finalize-review-state';

beforeEach(() => {
  vi.clearAllMocks();
  mocks.executeRaw.mockResolvedValue(1);
});

/** Reassemble the tagged-template SQL the mock received. */
function receivedSql(): { sql: string; values: unknown[] } {
  const call = mocks.executeRaw.mock.calls[0];
  const strings = call[0] as readonly string[];
  const values = call.slice(1);
  return { sql: strings.join('?'), values };
}

describe('applyAdditiveReviewState (audit BLOCK-2)', () => {
  it('no-op input (false/null) skips the UPDATE entirely', async () => {
    await applyAdditiveReviewState('v1', {
      needsReview: false,
      reviewReason: null,
    });
    expect(mocks.executeRaw).not.toHaveBeenCalled();
  });

  it('the SQL is ADDITIVE: needsReview ORs onto the row value, never assigns', async () => {
    await applyAdditiveReviewState('v1', {
      needsReview: true,
      reviewReason: 'automation incomplete',
    });

    const { sql, values } = receivedSql();
    // The row's own column participates in the new value — that is the
    // anti-clobber property. A future refactor to a plain assignment
    // ("needsReview" = $1) fails this pin.
    expect(sql).toMatch(/"needsReview"\s*=\s*"needsReview"\s+OR\s+\?/);
    expect(values).toContain(true);
  });

  it('the SQL COALESCE-concatenates reviewReason (existing reason survives, first)', async () => {
    await applyAdditiveReviewState('v1', {
      needsReview: true,
      reviewReason: 'automation incomplete',
    });

    const { sql } = receivedSql();
    // NULL-safe concat: COALESCE(row || ' ' || incoming, row, incoming) —
    // both → concatenated (row first); row-only → row; incoming-only →
    // incoming. A replacement that assigns the incoming reason directly
    // ("reviewReason" = $n with no COALESCE) fails this pin.
    expect(sql).toMatch(
      /"reviewReason"\s*=\s*COALESCE\(\s*"reviewReason"\s*\|\|\s*' '\s*\|\|\s*\?\s*,\s*"reviewReason"\s*,\s*\?\s*\)/
    );
  });

  it('targets exactly the given visit id', async () => {
    await applyAdditiveReviewState('vis-42', {
      needsReview: true,
      reviewReason: null,
    });

    const { sql, values } = receivedSql();
    expect(sql).toMatch(/WHERE id = \?/);
    expect(values).toContain('vis-42');
  });
});
