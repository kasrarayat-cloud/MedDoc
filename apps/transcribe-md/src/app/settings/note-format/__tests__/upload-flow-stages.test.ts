// ============================================================================
// UX simplification pack (A) — the staged-processing state machine.
// ----------------------------------------------------------------------------
// These stages are the honesty contract of the upload flow: each one maps to a
// REAL awaited step and may only advance when that step actually completed.
// The tests below pin that contract, because the failure mode we care about is
// a future change quietly making the animation run on a timer — which would
// turn an honest progress display into a decorative one.
// ============================================================================

import { describe, expect, it } from 'vitest';
import { advance, initialStages, type StageModel } from '../upload-flow';

const keys = (s: StageModel[]) => s.map((x) => x.key);
const states = (s: StageModel[]) => s.map((x) => x.state);
const byKey = (s: StageModel[], k: string) => s.find((x) => x.key === k)!;

describe('initialStages', () => {
  it('always lists the four steps in pipeline order', () => {
    expect(keys(initialStages(true))).toEqual(['read', 'sections', 'fields', 'sample']);
  });

  it('file path starts by reading the file', () => {
    const s = initialStages(true);
    expect(byKey(s, 'read').state).toBe('active');
    expect(byKey(s, 'sections').state).toBe('pending');
  });

  it('paste path SKIPS the read step rather than showing it instantly complete', () => {
    // There is genuinely no file to read when the doctor pastes, so claiming
    // "Reading your form ✓" would be a small lie. It is skipped instead.
    const s = initialStages(false);
    expect(byKey(s, 'read').state).toBe('skipped');
    expect(byKey(s, 'sections').state).toBe('active');
  });
});

describe('advance', () => {
  it('completing a step lights exactly the next one', () => {
    const s = advance(initialStages(true), 'read', 'done');
    expect(states(s)).toEqual(['done', 'active', 'pending', 'pending']);
  });

  it('never lights a skipped step — it steps over it', () => {
    // Paste path: completing `sections` must light `fields`, and `read` must
    // stay skipped rather than being revived.
    const s = advance(initialStages(false), 'sections', 'done');
    expect(byKey(s, 'read').state).toBe('skipped');
    expect(byKey(s, 'fields').state).toBe('active');
  });

  it('records the detail it is given and leaves it alone afterwards', () => {
    let s = advance(initialStages(true), 'read', 'done');
    s = advance(s, 'sections', 'done', '12');
    expect(byKey(s, 'sections').detail).toBe('12');
    // A later unrelated advance must not clobber an earlier detail.
    s = advance(s, 'fields', 'done', 'none');
    expect(byKey(s, 'sections').detail).toBe('12');
    expect(byKey(s, 'fields').detail).toBe('none');
  });

  it('is pure — the input array is not mutated', () => {
    const before = initialStages(true);
    const snapshot = states(before);
    advance(before, 'read', 'done');
    expect(states(before)).toEqual(snapshot);
  });

  it('ignores an unknown key instead of throwing', () => {
    const before = initialStages(true);
    // @ts-expect-error — deliberately probing the defensive branch
    expect(states(advance(before, 'nope', 'done'))).toEqual(states(before));
  });

  it('advancing the LAST step completes without lighting anything else', () => {
    let s = initialStages(true);
    s = advance(s, 'read', 'done');
    s = advance(s, 'sections', 'done');
    s = advance(s, 'fields', 'done');
    s = advance(s, 'sample', 'done');
    expect(states(s)).toEqual(['done', 'done', 'done', 'done']);
  });

  it('a full file run reaches all-done in the real call order', () => {
    // read → sections → fields → sample: the exact order runParse drives.
    let s = initialStages(true);
    expect(byKey(s, 'read').state).toBe('active');
    s = advance(s, 'read', 'done');
    expect(byKey(s, 'sections').state).toBe('active');
    s = advance(s, 'sections', 'done', '8');
    expect(byKey(s, 'fields').state).toBe('active');
    s = advance(s, 'fields', 'done', '5');
    expect(byKey(s, 'sample').state).toBe('active');
    s = advance(s, 'sample', 'done');
    expect(s.every((x) => x.state === 'done')).toBe(true);
  });

  it('a failed sample still resolves the row — the card must never hang', () => {
    // previewNoteTemplateAction failing marks the stage done with an honest
    // detail rather than leaving it spinning forever.
    let s = initialStages(true);
    s = advance(s, 'read', 'done');
    s = advance(s, 'sections', 'done', '3');
    s = advance(s, 'fields', 'done', 'none');
    s = advance(s, 'sample', 'done', 'unavailable');
    expect(byKey(s, 'sample').state).toBe('done');
    expect(byKey(s, 'sample').detail).toBe('unavailable');
  });
});
