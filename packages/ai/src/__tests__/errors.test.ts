// ============================================================================
// ModelOutputMalformedError — FIND-P1-010 unit tests
// ----------------------------------------------------------------------------
// Pins the class shape + the behavior contract:
//   - instanceof Error (compatible with generic catch handlers)
//   - message preserves the legacy "Anthropic response was not valid JSON"
//     prefix (model-client retry's startsWith fallback still works)
//   - rawTextSlice capped at 200 chars
//   - parseError + optional attempt preserved
//   - name='ModelOutputMalformedError' for instanceof-by-name checks in
//     worker/error-categorize.ts (the categorize module can't import
//     the class without a cross-package dependency cycle).
// ============================================================================

import { describe, expect, it } from 'vitest';

import { ModelOutputMalformedError } from '../errors';
import { defaultIsTransient } from '../retry';

describe('ModelOutputMalformedError — class shape', () => {
  it('is an instance of Error', () => {
    const err = new ModelOutputMalformedError('garbage', new Error('parse'));
    expect(err).toBeInstanceOf(Error);
    expect(err).toBeInstanceOf(ModelOutputMalformedError);
  });

  it('exposes name=ModelOutputMalformedError for cross-package instanceof-by-name', () => {
    const err = new ModelOutputMalformedError('garbage', new Error('parse'));
    expect(err.name).toBe('ModelOutputMalformedError');
  });

  it('preserves the legacy message prefix for retry-loop backward compatibility', () => {
    const err = new ModelOutputMalformedError(
      'garbage',
      new SyntaxError('Unexpected token { at position 42')
    );
    // model-client.ts retry-loop fallback does:
    //   err.message.startsWith('Anthropic response was not valid JSON')
    expect(err.message.startsWith('Anthropic response was not valid JSON')).toBe(true);
    // Include the parse-error message so logs carry the diagnostic.
    expect(err.message).toContain('Unexpected token { at position 42');
  });

  it('caps rawTextSlice at 200 chars (PHI bound)', () => {
    const huge = 'x'.repeat(2000);
    const err = new ModelOutputMalformedError(huge, new Error('parse'));
    expect(err.rawTextSlice).toHaveLength(200);
    expect(err.rawTextSlice).toBe('x'.repeat(200));
  });

  it('preserves the original parseError reference', () => {
    const parseErr = new SyntaxError('Unexpected end of JSON input');
    const err = new ModelOutputMalformedError('garbage', parseErr);
    expect(err.parseError).toBe(parseErr);
  });

  it('accepts non-Error parseError values (string, undefined)', () => {
    const err = new ModelOutputMalformedError('garbage', 'some string');
    expect(err.parseError).toBe('some string');
    expect(err.message).toContain('some string');

    const err2 = new ModelOutputMalformedError('garbage', undefined);
    expect(err2.parseError).toBeUndefined();
  });

  it('optional attempt is preserved', () => {
    const err = new ModelOutputMalformedError('garbage', new Error('parse'), {
      attempt: 2,
    });
    expect(err.attempt).toBe(2);
  });

  it('handles empty / null-ish rawText gracefully', () => {
    // The constructor coerces null/undefined to '' via the `?? ''` guard.
    const err = new ModelOutputMalformedError('', new Error('parse'));
    expect(err.rawTextSlice).toBe('');
  });
});

describe('ModelOutputMalformedError — interaction with defaultIsTransient', () => {
  it('is NOT considered transient (withRetry from Cluster 2 should not retry)', () => {
    // The error has no HTTP status, no Node network code, no Anthropic
    // structured-error type — so defaultIsTransient returns false. The
    // model-client.ts retry loop has its own gate (instanceof) for
    // controlled in-loop retries.
    const err = new ModelOutputMalformedError(
      '{"oops":',
      new SyntaxError('Unexpected end of JSON input')
    );
    expect(defaultIsTransient(err)).toBe(false);
  });
});
