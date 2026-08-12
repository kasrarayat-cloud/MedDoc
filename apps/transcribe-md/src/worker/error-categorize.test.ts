import { describe, it, expect, beforeEach } from 'vitest';
import { z } from 'zod';

import {
  categorizeError,
  _resetProviderFailuresForTesting,
} from './error-categorize';
import { AnthropicRefusalError, BillingAdmissionError } from '@meddoc/ai';

beforeEach(() => {
  _resetProviderFailuresForTesting();
});

describe('categorizeError — permanent', () => {
  it('treats ZodError as permanent', () => {
    const schema = z.object({ x: z.string() });
    const parsed = schema.safeParse({ x: 1 });
    if (parsed.success) throw new Error('test setup: should have failed');
    expect(categorizeError(parsed.error)).toBe('permanent');
  });

  it('Q1 #09.1: treats AnthropicRefusalError as permanent (no retry burn)', () => {
    expect(
      categorizeError(new AnthropicRefusalError('claude-opus-4-8', 'tm_soap_draft'))
    ).toBe('permanent');
  });

  it('flags "unsupported audio format" as permanent', () => {
    expect(categorizeError(new Error('Unsupported audio format: ogg/vorbis'))).toBe(
      'permanent'
    );
  });

  it('flags "file too short" as permanent', () => {
    expect(categorizeError(new Error('File is too short for transcription'))).toBe(
      'permanent'
    );
  });

  it('flags "audio is corrupt" as permanent', () => {
    expect(categorizeError(new Error('Audio file is corrupt'))).toBe(
      'permanent'
    );
  });

  it('flags zero-byte audio as permanent', () => {
    expect(categorizeError(new Error('Zero-byte audio rejected'))).toBe(
      'permanent'
    );
  });

  it('flags "could not decode audio" as permanent', () => {
    expect(
      categorizeError(new Error('Could not decode audio: invalid header'))
    ).toBe('permanent');
  });

  it('flags Deepgram "Keyterm limit exceeded" 400 as permanent', () => {
    // Real prod failure from the kasra 7-min retry — the categorizer
    // in commit 2 of #61 mis-classified this as transient because 400
    // wasn't in the transient status list. Now it pattern-matches the
    // message body and returns permanent so we don't burn 3 BullMQ
    // attempts on the same config bug.
    const err = Object.assign(
      new Error(
        'Deepgram batch failed: HTTP 400 Bad Request {"err_msg":"Bad Request: Keyterm limit exceeded. The maximum number of tokens across all keyterms is 500.","request_id":"019dc210"}'
      ),
      { status: 400 }
    );
    expect(categorizeError(err)).toBe('permanent');
  });

  it('flags "Maximum number of keyterms" as permanent', () => {
    expect(
      categorizeError(new Error('Maximum number of keyterms allowed is 500'))
    ).toBe('permanent');
  });

  it('flags "Invalid model" as permanent', () => {
    expect(
      categorizeError(
        Object.assign(new Error('Invalid model: nova-99-medical'), {
          status: 400,
        })
      )
    ).toBe('permanent');
  });

  it('flags "Unsupported sample rate" as permanent', () => {
    expect(
      categorizeError(
        Object.assign(new Error('Unsupported sample-rate: 96000'), {
          status: 400,
        })
      )
    ).toBe('permanent');
  });

  // Q2 follow-up — Anthropic SDK structured 4xx errors. The
  // BadRequestError shape is { status, error: { type: 'error',
  // error: { type: <api-error-type>, message: <text> } } }. Pre-fix
  // these were classified as transient and the worker burned 6
  // BullMQ attempts on the same wire payload. The kasra Opus-4.7
  // temperature-deprecation 400 is the canonical regression.
  it('flags Anthropic 400 invalid_request_error as permanent (Opus 4.7 temp deprecation)', () => {
    const err = Object.assign(new Error('400 Bad Request'), {
      status: 400,
      error: {
        type: 'error',
        error: {
          type: 'invalid_request_error',
          message: '`temperature` is deprecated for this model.',
        },
      },
    });
    expect(categorizeError(err)).toBe('permanent');
  });

  it('flags Anthropic 401 authentication_error as permanent', () => {
    const err = Object.assign(new Error('401 Unauthorized'), {
      status: 401,
      error: {
        type: 'error',
        error: { type: 'authentication_error', message: 'invalid x-api-key' },
      },
    });
    expect(categorizeError(err)).toBe('permanent');
  });

  it('flags Anthropic 403 permission_error as permanent', () => {
    const err = Object.assign(new Error('403 Forbidden'), {
      status: 403,
      error: {
        type: 'error',
        error: { type: 'permission_error', message: 'no access to this model' },
      },
    });
    expect(categorizeError(err)).toBe('permanent');
  });

  it('flags Anthropic 404 not_found_error as permanent', () => {
    const err = Object.assign(new Error('404 Not Found'), {
      status: 404,
      error: {
        type: 'error',
        error: { type: 'not_found_error', message: 'unknown model' },
      },
    });
    expect(categorizeError(err)).toBe('permanent');
  });

  it('flags Anthropic 413 request_too_large as permanent', () => {
    const err = Object.assign(new Error('413 Payload Too Large'), {
      status: 413,
      error: {
        type: 'error',
        error: { type: 'request_too_large', message: 'context too long' },
      },
    });
    expect(categorizeError(err)).toBe('permanent');
  });
});

describe('categorizeError — transient', () => {
  it('flags ECONNRESET as transient', () => {
    expect(categorizeError(new Error('socket hang up: ECONNRESET'))).toBe(
      'transient'
    );
  });

  it('flags ETIMEDOUT as transient', () => {
    expect(categorizeError(new Error('connect ETIMEDOUT 1.2.3.4:443'))).toBe(
      'transient'
    );
  });

  it('flags 5xx status as transient', () => {
    const err = Object.assign(new Error('Deepgram returned 502'), {
      status: 502,
    });
    // First hit — still "transient", not yet "provider_down".
    expect(categorizeError(err)).toBe('transient');
  });

  it('flags 408 / 429 as transient', () => {
    expect(
      categorizeError(Object.assign(new Error('rate limited'), { status: 429 }))
    ).toBe('transient');
    expect(
      categorizeError(Object.assign(new Error('timeout'), { status: 408 }))
    ).toBe('transient');
  });

  it('handles SDK errors with .response.status', () => {
    const err = Object.assign(new Error('upstream'), {
      response: { status: 503 },
    });
    expect(categorizeError(err)).toBe('transient');
  });

  it('falls back to transient on unknown error shape', () => {
    expect(categorizeError(new Error('something weird happened'))).toBe(
      'transient'
    );
  });

  it('treats string error as transient by default', () => {
    expect(categorizeError('mystery thrown string')).toBe('transient');
  });
});

describe('categorizeError — provider_down', () => {
  it('flips to provider_down after 3 deepgram 5xx hits in the window', () => {
    const make = () =>
      Object.assign(new Error('Deepgram api error 503'), { status: 503 });
    expect(categorizeError(make())).toBe('transient');
    expect(categorizeError(make())).toBe('transient');
    // 3rd hit crosses the threshold.
    expect(categorizeError(make())).toBe('provider_down');
  });

  it('does not bleed across providers', () => {
    const dg = () =>
      Object.assign(new Error('Deepgram 503'), { status: 503 });
    const an = () =>
      Object.assign(new Error('Anthropic 503'), { status: 503 });
    // Two deepgram hits + one anthropic — neither has crossed the bar.
    expect(categorizeError(dg())).toBe('transient');
    expect(categorizeError(dg())).toBe('transient');
    expect(categorizeError(an())).toBe('transient');
    // Third anthropic hit doesn't borrow Deepgram's count.
    expect(categorizeError(an())).toBe('transient');
    // Third Deepgram hit crosses.
    expect(categorizeError(dg())).toBe('provider_down');
  });

  it('does not flip on permanent input errors even if pattern repeats', () => {
    const make = () => new Error('Unsupported audio format');
    expect(categorizeError(make())).toBe('permanent');
    expect(categorizeError(make())).toBe('permanent');
    expect(categorizeError(make())).toBe('permanent');
    // Permanent errors don't feed the provider-down ring.
  });

  it('FIND-P1-010 — treats ModelOutputMalformedError as permanent (by name)', () => {
    // The categorizer can't import the class without a cross-package
    // edge (worker → packages/ai/src/errors), so it matches by
    // `err.name`. The class sets name='ModelOutputMalformedError' in
    // its constructor — these tests pin the contract on both sides.
    class ModelOutputMalformedError extends Error {
      constructor(message: string) {
        super(message);
        this.name = 'ModelOutputMalformedError';
      }
    }
    const err = new ModelOutputMalformedError(
      'Anthropic response was not valid JSON: Unexpected token'
    );
    expect(categorizeError(err)).toBe('permanent');
  });
});

// ============================================================================
// B8 step 2 — A BILLING ADMISSION REFUSAL CARRIES ITS OWN RETRY CATEGORY
// ----------------------------------------------------------------------------
// The two refusals are different events and must not be filed as one:
//
//   insufficient_balance / credit_not_spendable → the practice is out of money.
//                                                 Retrying cannot change it.
//   balance_unreadable                          → OUR database was unreachable,
//                                                 or the ledger disagreed with
//                                                 itself. The practice may be
//                                                 perfectly solvent.
//
// Filing the second under the first tells a paid-up doctor they are out of
// credit because our pool was exhausted — and it is the half of B8 that the
// auto-credit exists to compensate, so a fault misfiled as a balance problem is
// a fault the credit will never find.
// ============================================================================

describe('categorizeError — B8 billing admission', () => {
  it('an empty wallet is permanent — retry cannot add money', () => {
    expect(
      categorizeError(new BillingAdmissionError('insufficient_balance', 'x'))
    ).toBe('permanent');
    expect(
      categorizeError(new BillingAdmissionError('credit_not_spendable', 'x'))
    ).toBe('permanent');
  });

  it('an unreadable balance is TRANSIENT — our fault, not the practice being empty', () => {
    expect(
      categorizeError(new BillingAdmissionError('balance_unreadable', 'x'))
    ).toBe('transient');
  });

  it('stays permanent even when the DETAIL contains transient words', () => {
    // The whole reason the category travels as a property. Without the
    // structural arm running first, `isLikelyTransient` would match these and
    // spend BullMQ's retry budget on a balance that cannot move.
    const err = new BillingAdmissionError(
      'insufficient_balance',
      'socket hang up / network error / fetch failed'
    );
    expect(categorizeError(err)).toBe('permanent');
  });

  it('NEGATIVE CONTROL — a look-alike MESSAGE gets no billing semantics', () => {
    // AGENTS.md records four sightings of the substring trap, one of them a
    // matcher that hit its own explanatory comment. An ordinary error that
    // merely quotes a refusal must not be classified as one.
    const impostor = new Error(
      'billing admission refused (insufficient_balance): not really'
    );
    expect(categorizeError(impostor)).toBe('transient');
  });

  it('NEGATIVE CONTROL — the class name alone does not force permanent', () => {
    // The category is what decides, so a same-named error carrying the
    // transient category is transient. This is what makes the arm structural
    // rather than a second name check wearing a property's clothes.
    const named = new Error('anything') as Error & { retryCategory?: string };
    named.name = 'BillingAdmissionError';
    named.retryCategory = 'transient';
    expect(categorizeError(named)).toBe('transient');
  });
});
