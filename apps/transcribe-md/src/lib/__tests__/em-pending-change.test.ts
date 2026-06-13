// ============================================================================
// em-pending-change — strict coercion + fail-closed sign-gate view.
// Pure functions, no mocks. Pins the boundary the suggestion actions, the
// sign route, and page.tsx all share (E/M visible-confirm, prod smoke #311).
// ============================================================================

import { describe, expect, it } from 'vitest';

import {
  parseEmPendingChange,
  unacknowledgedEmChange,
} from '../em-pending-change';

const VALID = {
  from: '99213',
  to: '99214',
  cause: 'suggestion_adopted',
  at: '2026-06-12T10:00:00.000Z',
};

describe('parseEmPendingChange — strict coercion', () => {
  it('round-trips a valid record (with and without acknowledgedAt)', () => {
    expect(parseEmPendingChange(VALID)).toEqual(VALID);
    const acked = { ...VALID, acknowledgedAt: '2026-06-12T11:00:00.000Z' };
    expect(parseEmPendingChange(acked)).toEqual(acked);
  });

  it('accepts both causes and nothing else', () => {
    expect(
      parseEmPendingChange({ ...VALID, cause: 'suggestion_dismissed' })
    ).toMatchObject({ cause: 'suggestion_dismissed' });
    expect(parseEmPendingChange({ ...VALID, cause: 'manual_edit' })).toBeNull();
  });

  it('nulls on every malformed shape', () => {
    expect(parseEmPendingChange(null)).toBeNull();
    expect(parseEmPendingChange(undefined)).toBeNull();
    expect(parseEmPendingChange('99213→99214')).toBeNull();
    expect(parseEmPendingChange([VALID])).toBeNull();
    expect(parseEmPendingChange({ ...VALID, from: '' })).toBeNull();
    expect(parseEmPendingChange({ ...VALID, to: 99214 })).toBeNull();
    expect(parseEmPendingChange({ ...VALID, at: undefined })).toBeNull();
    expect(
      parseEmPendingChange({ ...VALID, acknowledgedAt: 12345 })
    ).toBeNull();
  });
});

describe('unacknowledgedEmChange — the sign gate view', () => {
  it('null/undefined column → nothing to confirm', () => {
    expect(unacknowledgedEmChange(null)).toBeNull();
    expect(unacknowledgedEmChange(undefined)).toBeNull();
  });

  it('valid unacknowledged record → returned as-is', () => {
    expect(unacknowledgedEmChange(VALID)).toEqual(VALID);
  });

  it('acknowledged record → nothing to confirm', () => {
    expect(
      unacknowledgedEmChange({ ...VALID, acknowledgedAt: '2026-06-12T11:00:00.000Z' })
    ).toBeNull();
  });

  it('present-but-malformed record FAILS CLOSED (unknown sentinel, still demands confirmation)', () => {
    expect(unacknowledgedEmChange({ bogus: true })).toEqual({
      from: 'unknown',
      to: 'unknown',
      cause: 'suggestion_adopted',
      at: '',
    });
    expect(unacknowledgedEmChange('garbage')).toMatchObject({
      from: 'unknown',
      to: 'unknown',
    });
  });
});
