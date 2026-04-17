// ============================================================================
// OutputError — ScribeOutput error sentinel stored in content JSON
// ----------------------------------------------------------------------------
// M4 D2: on extraction double-fail, the pipeline persists a
// { _error: {...} } blob into ScribeOutput.content. These tests lock in
// the shape + the isOutputError() guard the review UI uses.
// ============================================================================

import { describe, it, expect } from 'vitest';
import { OutputErrorSchema, isOutputError } from '@meddoc/types';

const validError = {
  _error: {
    code: 'SCHEMA_FAIL',
    message: 'Zod rejected output after retry.',
    attempts: 2,
    occurredAt: new Date().toISOString(),
  },
};

describe('OutputErrorSchema', () => {
  it('accepts a well-formed error blob', () => {
    expect(OutputErrorSchema.safeParse(validError).success).toBe(true);
  });

  it('rejects blobs missing the _error key', () => {
    expect(OutputErrorSchema.safeParse({ error: validError._error }).success).toBe(false);
  });

  it('rejects extra top-level keys (strict)', () => {
    expect(
      OutputErrorSchema.safeParse({ ...validError, confidence: 'low' }).success
    ).toBe(false);
  });

  it('rejects negative / non-integer attempts', () => {
    expect(
      OutputErrorSchema.safeParse({
        _error: { ...validError._error, attempts: -1 },
      }).success
    ).toBe(false);
    expect(
      OutputErrorSchema.safeParse({
        _error: { ...validError._error, attempts: 1.5 },
      }).success
    ).toBe(false);
  });
});

describe('isOutputError', () => {
  it('narrows true for a valid error blob', () => {
    expect(isOutputError(validError)).toBe(true);
  });

  it('returns false for success-shape payloads', () => {
    expect(isOutputError({ confidence: 'medium', icd10: [], cpt: [], ambiguities: [] })).toBe(
      false
    );
  });

  it('returns false for non-object inputs without throwing', () => {
    expect(isOutputError(null)).toBe(false);
    expect(isOutputError('error')).toBe(false);
    expect(isOutputError(42)).toBe(false);
    expect(isOutputError(undefined)).toBe(false);
  });
});
