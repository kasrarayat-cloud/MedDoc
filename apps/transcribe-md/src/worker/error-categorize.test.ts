import { describe, it, expect, beforeEach } from 'vitest';
import { z } from 'zod';

import {
  categorizeError,
  _resetProviderFailuresForTesting,
} from './error-categorize';

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
});
