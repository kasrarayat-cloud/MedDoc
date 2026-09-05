// ============================================================================
// THE FIVE ROW STATES, AND THE ORDER IN WHICH THEY ARE TESTED
// ----------------------------------------------------------------------------
// The owner's frame `icd-code-row-states` approves five states. They map
// one-for-one onto the five buckets the coding surface already distinguishes,
// which is why the redesign carries the same information rather than less.
// ============================================================================

import { describe, expect, it } from 'vitest';

import { icdRowState, ICD_ROW_STATE_LABEL } from '@/lib/icd-row-state';
import type { IcdDecisionProjection } from '@/lib/icd-decisions';

const P = (over: Partial<IcdDecisionProjection> = {}): IcdDecisionProjection =>
  ({
    suggested: [], accepted: [], rejected: [], undecided: [], orphaned: [],
    duplicateSuggestions: 0, decisions: {},
  } as unknown as IcdDecisionProjection);

describe('the five row states', () => {
  it('maps each bucket to its frame state', () => {
    expect(icdRowState('K21.9', { ...P(), accepted: ['K21.9'] })).toBe('pre-accepted');
    expect(icdRowState('K21.9', { ...P(), rejected: ['K21.9'] })).toBe('rejected');
    expect(icdRowState('K21.9', { ...P(), orphaned: ['K21.9'] })).toBe('orphaned');
    // undecided is the DEFAULT — a code the projection says nothing about is
    // held for review, never silently accepted.
    expect(icdRowState('K21.9', P())).toBe('held');
  });

  it('⚠️ ORPHANED WINS OVER A DECISION — the order of tests is the property', () => {
    // An orphaned code IS one carrying a decision. A decision-first test would
    // render it as an ordinary accept and hide that the suggester has withdrawn
    // it — and an orphaned ACCEPT must never read as a live one, because the
    // note it was made against is not the note on screen.
    const p = { ...P(), accepted: ['K21.9'], orphaned: ['K21.9'] };
    expect(icdRowState('K21.9', p)).toBe('orphaned');
    const q = { ...P(), rejected: ['K21.9'], orphaned: ['K21.9'] };
    expect(icdRowState('K21.9', q)).toBe('orphaned');
  });

  it('uses the SHARED matcher, so a differently-cased code lands in one bucket', () => {
    expect(icdRowState(' k21.9 ', { ...P(), accepted: ['K21.9'] })).toBe('pre-accepted');
    expect(icdRowState('K21.9', { ...P(), accepted: [' k21.9 '] })).toBe('pre-accepted');
  });

  it('the default is HELD, never pre-accepted — the fail-safe direction', () => {
    // A code the projection has no opinion about must ask the doctor, not
    // present itself as already agreed. Getting this backwards would put an
    // undecided code on a claim as accepted.
    expect(icdRowState('ZZZ.9', P())).toBe('held');
  });

  it('every state has a label, and they are distinct', () => {
    const labels = Object.values(ICD_ROW_STATE_LABEL);
    expect(labels).toHaveLength(5);
    expect(new Set(labels).size).toBe(5);
  });
});
